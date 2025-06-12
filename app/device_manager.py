import os
import importlib
import logging
import inspect
import sys
import asyncio
import json
from typing import Dict, Any, Callable, List, Optional, Union, Type
from devices.base_device import BaseDevice
from app.schemas import BaseDeviceState
from app.schemas import BaseDeviceConfig
from app.mqtt_client import MQTTClient
from app.config_manager import ConfigManager
from app.serialization_utils import safely_serialize, describe_serialization_issues
from app.class_loader import load_class_by_name

# NOTE: This module now uses the 'device_class' field directly from device configurations
# rather than looking up class names in the system config.

logger = logging.getLogger(__name__)

class DeviceManager:
    """Manages device modules and their message handlers."""
    
    def __init__(self, devices_dir: str = "devices", mqtt_client: Optional[MQTTClient] = None, 
                 config_manager: Optional[ConfigManager] = None, store = None):
        self.devices_dir = devices_dir
        self.device_classes: Dict[str, Type[BaseDevice]] = {}  # Stores class definitions
        self.devices: Dict[str, BaseDevice] = {}  # Stores device instances
        self.mqtt_client = mqtt_client
        self.config_manager = config_manager  # Store reference to ConfigManager
        self.store = store  # State persistence store
        self._persistence_tasks = set()  # Track active persistence tasks
        self._shutting_down = False  # Flag to indicate shutdown in progress
    
    async def load_device_modules(self):
        """Dynamically load all device modules from the devices directory."""
        if not os.path.exists(self.devices_dir):
            logger.warning(f"Devices directory not found: {self.devices_dir}")
            return
        
        # Add the parent directory to sys.path to enable absolute imports
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if parent_dir not in sys.path:
            sys.path.append(parent_dir)
            logger.info(f"Added {parent_dir} to Python path for imports")
        
        logger.info(f"Loading device modules from {self.devices_dir}")
        for filename in os.listdir(self.devices_dir):
            if filename.endswith('.py') and not filename.startswith('__') and filename != 'base_device.py':
                module_name = f"devices.{filename[:-3]}"
                module_path = os.path.join(self.devices_dir, filename)
                logger.info(f"Loading module: {module_name} from {module_path}")
                
                try:
                    spec = importlib.util.spec_from_file_location(module_name, module_path)
                    if not spec or not spec.loader:
                        logger.error(f"Failed to load spec for module: {module_name}")
                        continue
                    
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    # Find all device classes in the module
                    for item_name, item in module.__dict__.items():
                        if isinstance(item, type) and issubclass(item, BaseDevice) and item != BaseDevice:
                            self.device_classes[item.__name__] = item
                            logger.info(f"Registered device class: {item.__name__}")
                
                except Exception as e:
                    logger.error(f"Error loading device module {module_name}: {str(e)}")
                    import traceback
                    logger.error(traceback.format_exc())
        
        logger.info(f"Loaded device classes: {list(self.device_classes.keys())}")
    
    def _load_device_class(self, device_class_name: str) -> Optional[Type[BaseDevice]]:
        """
        Load a device implementation class either from loaded classes or by dynamic import.
        
        Args:
            device_class_name: Name of the device class to load
            
        Returns:
            Device class if found, None otherwise
        """
        # First try to get the class from already loaded classes
        if device_class_name in self.device_classes:
            return self.device_classes[device_class_name]
        
        # If not found, attempt to dynamically import it
        # Note: We pass 'object' as base class since we just want to import,
        # we'll check if it's a valid BaseDevice in the initialization
        cls = load_class_by_name(device_class_name, object, "devices.")
        
        if cls is not None:
            # Verify the class is a subclass of BaseDevice
            if issubclass(cls, BaseDevice):
                # Cache the class for future use
                self.device_classes[device_class_name] = cls
                logger.info(f"Successfully loaded device class {device_class_name} via class_loader")
                return cls
            else:
                logger.error(
                    f"Loaded class {device_class_name} is not a subclass of BaseDevice"
                )
        
        return None
    
    async def initialize_devices(self, configs: Dict[str, BaseDeviceConfig]):
        """
        Initialize devices from typed configurations using dynamic class loading.
        
        This method instantiates device objects based on their device_class field
        in the configuration, dynamically loading the classes as needed.
        
        Args:
            configs: Dictionary of device configurations mapped by device_id
        """
        for device_id, config in configs.items():
            try:
                # Get the device class name directly from the config
                device_class_name = getattr(config, 'device_class', None)
                
                if not device_class_name:
                    logger.error(f"No device_class field found in configuration for device '{device_id}'")
                    continue
                
                # Load the device class
                device_class = self._load_device_class(device_class_name)
                
                if not device_class:
                    logger.error(f"Device class {device_class_name} not found for device {device_id}")
                    continue
                
                # Verify that the class is concrete (not abstract) before instantiation
                if inspect.isabstract(device_class):
                    logger.error(f"Cannot instantiate abstract class {device_class_name} for device {device_id}")
                    continue
                
                # Instantiate the device with typed configuration
                try:
                    device = device_class(config, self.mqtt_client)
                except Exception as e:
                    logger.error(f"Failed to instantiate device {device_id} of type {device_class_name}: {str(e)}")
                    continue
                
                # Register state change callback if device supports it
                if hasattr(device, 'register_state_change_callback') and self.store:
                    device.register_state_change_callback(self._persist_state_callback)
                
                success = await device.setup()
                
                if not success:
                    logger.error(f"Failed to set up device {device_id} of type {device_class_name}")
                    continue
                    
                self.devices[device_id] = device
                logger.info(f"Initialized device {device_id} of type {device_class_name}")
                
                # Immediately persist the initial state after successful setup
                if self.store:
                    try:
                        await self._persist_state(device_id)
                        logger.info(f"Persisted initial state for device {device_id}")
                    except Exception as e:
                        logger.error(f"Failed to persist initial state for device {device_id}: {str(e)}")
                
            except Exception as e:
                logger.error(f"Failed to initialize device {device_id}: {str(e)}")
                logger.exception(e)
    
    async def shutdown_devices(self):
        """Shutdown all devices."""
        for device_name, device in self.devices.items():
            try:
                await device.shutdown()
                logger.info(f"Shutdown device: {device_name}")
            except Exception as e:
                logger.error(f"Error shutting down device {device_name}: {str(e)}")
    
    def get_device(self, device_id: str) -> Optional[BaseDevice]:
        """Get a device instance by its ID."""
        return self.devices.get(device_id)
    
    def get_device_topics(self, device_id: str) -> List[str]:
        """Get the topics to subscribe for a device."""
        device = self.devices.get(device_id)
        if not device:
            logger.warning(f"No device found with ID: {device_id}")
            return []
        return device.subscribe_topics()
    
    def get_message_handler(self, device_name: str) -> Optional[Callable[..., Any]]:
        """Get the message handler for a device."""
        device = self.devices.get(device_name)
        if not device:
            logger.warning(f"No device found: {device_name}")
            return None
        return device.handle_message
    
    async def get_device_state(self, device_name: str) -> Dict[str, Any]:
        """Get the current state of a device."""
        device = self.devices.get(device_name)
        if not device:
            logger.warning(f"No device found: {device_name}")
            return {}
        return device.get_current_state()
    
    def get_all_devices(self) -> List[str]:
        """Get a list of all device IDs."""
        return list(self.devices.keys())
        
    def _safely_serialize_state(self, state_obj: Any) -> Dict[str, Any]:
        """
        Safely convert a device state object to a serializable dictionary.
        
        This utility method ensures proper serialization of any device state,
        with special handling for device-specific state classes.
        
        Args:
            state_obj: The device state object to serialize
            
        Returns:
            Dict[str, Any]: A JSON-serializable dictionary representation of the state
            
        Raises:
            Exception: If serialization fails after all attempts
        """
        # Use our serialization utility function
        state_dict = safely_serialize(state_obj)
        
        # Check for potential issues and log warnings
        issues = describe_serialization_issues(state_obj)
        if issues:
            for issue in issues:
                logger.warning(f"Device state serialization issue: {issue}")
        
        return state_dict
        
    async def _persist_state(self, device_id: str):
        """
        Persist full device.state dict under key "device:{device_id}".
        """
        if not self.store:
            logger.debug(f"State store not available, skipping persistence for device: {device_id}")
            return
            
        device = self.devices.get(device_id)
        if not device:
            logger.warning(f"Cannot persist state for unknown device: {device_id}")
            return
            
        try:
            state_obj = device.get_current_state()
            
            # Use the safe serialization method to handle all state types
            state_dict = self._safely_serialize_state(state_obj)
            
            await self.store.set(f"device:{device_id}", state_dict)
            logger.debug(f"Persisted state for device: {device_id}")
                
        except Exception as e:
            logger.error(f"Failed to persist state for device {device_id}: {str(e)}")
            # Log the object type to help debugging
            if state_obj:
                logger.error(f"State object type: {type(state_obj).__name__}")
            
            # Try to identify which fields might be causing problems
            try:
                if hasattr(state_obj, '__dict__'):
                    problematic_fields = []
                    for key, value in state_obj.__dict__.items():
                        try:
                            json.dumps({key: value})
                        except (TypeError, OverflowError):
                            problematic_fields.append(f"{key} ({type(value).__name__})")
                    if problematic_fields:
                        logger.error(f"Problematic fields in {device_id} state: {', '.join(problematic_fields)}")
            except Exception:
                logger.error(f"Could not inspect state object structure for {device_id}")
            
    def _persist_state_callback(self, device_id: str):
        """
        Callback to handle device state changes. Schedules the state to be persisted.
        This method is designed to be called from device instances when their state changes.
        
        Args:
            device_id: The ID of the device whose state changed
        """
        # DEBUG: Log all state change callbacks
        logger.debug(f"[STATE_DEBUG] _persist_state_callback triggered for {device_id}")
        
        if not self.store:
            logger.debug(f"State store not available, skipping persistence callback for device: {device_id}")
            return
            
        # If we're shutting down, perform persistence synchronously to avoid race conditions
        if self._shutting_down:
            logger.debug(f"Performing synchronous persistence for {device_id} during shutdown")
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # We're in an event loop, so we can use run_until_complete
                    loop.run_until_complete(self._persist_state(device_id))
                else:
                    logger.warning(f"No event loop for synchronous persistence of {device_id} during shutdown")
            except Exception as e:
                logger.error(f"Failed to persist state for {device_id} during shutdown: {str(e)}")
            return
            
        # Normal operation mode: use asyncio.create_task to persist state asynchronously without blocking
        try:
            # DEBUG: Log task creation for all devices
            logger.debug(f"[STATE_DEBUG] Creating persistence task for {device_id}")
            
            task = asyncio.create_task(self._persist_state(device_id))
            # Track the task and automatically remove it when done
            self._persistence_tasks.add(task)
            task.add_done_callback(lambda t: self._persistence_tasks.discard(t))
        except RuntimeError as e:
            # We're not in an event loop, log a warning
            logger.warning(f"Cannot persist state for {device_id}: {str(e)}")
            
    async def wait_for_persistence_tasks(self, timeout: float = 5.0) -> bool:
        """
        Wait for all persistence tasks to complete within the given timeout.
        
        Args:
            timeout: Maximum time to wait in seconds
            
        Returns:
            bool: True if all tasks completed, False if there are still pending tasks
        """
        if not self._persistence_tasks:
            return True
            
        logger.info(f"Waiting for {len(self._persistence_tasks)} persistence tasks to complete (timeout: {timeout}s)")
        try:
            # Wait for pending tasks with timeout
            done, pending = await asyncio.wait(
                self._persistence_tasks, 
                timeout=timeout
            )
            
            # Handle tasks that didn't complete in time
            if pending:
                logger.warning(f"{len(pending)} persistence tasks did not complete within timeout")
                return False
                
            # Check for exceptions in completed tasks
            for task in done:
                if task.exception():
                    logger.error(f"Persistence task raised an exception: {task.exception()}")
                    
            return True
        except Exception as e:
            logger.error(f"Error waiting for persistence tasks: {str(e)}")
            return False
            
    async def persist_all_device_states(self) -> None:
        """
        Explicitly persist the state of all devices.
        This is useful during shutdown to ensure all final states are saved.
        """
        logger.info("Persisting final state for all devices")
        for device_id in self.devices:
            try:
                await self._persist_state(device_id)
            except Exception as e:
                logger.error(f"Failed to persist final state for device {device_id}: {str(e)}")
                
    async def prepare_for_shutdown(self) -> None:
        """
        Prepare the device manager for shutdown.
        This sets the shutdown flag to prevent new asynchronous persistence tasks.
        """
        logger.info("Preparing device manager for shutdown")
        self._shutting_down = True
            
    async def perform_action(self, device_id: str, action: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Perform an action on a device and persist its state."""
        # DEBUG: Log all device action executions
        logger.debug(f"[DEVICE_MGR_DEBUG] perform_action called: device_id={device_id}, action={action}, params={params}")
        
        device = self.get_device(device_id)
        if not device:
            logger.warning(f"Cannot perform action on unknown device: {device_id}")
            return {"success": False, "error": f"Device not found: {device_id}"}
            
        try:
            # DEBUG: Log before action execution
            logger.debug(f"[DEVICE_MGR_DEBUG] Executing action on device: {device.get_name()}")
            
            result = await device.execute_action(action, params)
            
            # DEBUG: Log action result
            logger.debug(f"[DEVICE_MGR_DEBUG] Action result for {device_id}: {result}")
            
            # Persist state after action
            await self._persist_state(device_id)
            return result
        except Exception as e:
            logger.error(f"Error performing action '{action}' on device {device_id}: {str(e)}")
            return {"success": False, "error": str(e)}
            
    async def initialize(self) -> None:
        """
        Initialize each device by loading persisted state.
        This should be called after devices are loaded but before application startup completes.
        """
        if not self.store:
            logger.info("State store not available, skipping state recovery")
            return
            
        logger.info("Initializing device states from persistence layer")
        for device_id in self.devices:
            try:
                stored_state = await self.store.get(f"device:{device_id}")
                if stored_state:
                    logger.info(f"Recovered state for device: {device_id}")
                    # Note: Full implementation of state recovery will be provided in a later phase
                    # This placeholder just logs that we found state
                else:
                    logger.info(f"No persisted state found for device: {device_id}")
            except Exception as e:
                logger.error(f"Error recovering state for device {device_id}: {str(e)}") 