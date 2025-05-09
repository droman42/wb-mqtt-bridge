import os
import importlib
import logging
import inspect
import sys
import asyncio
from typing import Dict, Any, Callable, List, Optional, Union
from devices.base_device import BaseDevice
from app.schemas import BaseDeviceConfig
from app.mqtt_client import MQTTClient
from app.config_manager import ConfigManager

# NOTE: This module uses the 'class' field from system configuration
# to determine the device class for instantiation.
# The ConfigManager.get_device_class_name method is used to get class names.

logger = logging.getLogger(__name__)

class DeviceManager:
    """Manages device modules and their message handlers."""
    
    def __init__(self, devices_dir: str = "devices", mqtt_client: Optional[MQTTClient] = None, 
                 config_manager: Optional[ConfigManager] = None, store = None):
        self.devices_dir = devices_dir
        self.device_classes: Dict[str, type] = {}  # Stores class definitions
        self.devices: Dict[str, BaseDevice] = {}  # Stores device instances
        self.mqtt_client = mqtt_client
        self.config_manager = config_manager  # Store reference to ConfigManager
        self.store = store  # State persistence store
    
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
    
    async def initialize_devices(self, configs: Dict[str, BaseDeviceConfig]):
        """
        Initialize devices from typed configurations using dynamic imports.
        
        This method instantiates device objects based on their class name from the system config,
        dynamically loading the modules as needed rather than relying on a factory pattern.
        
        Args:
            configs: Dictionary of device configurations mapped by device_id
        """
        for device_id, config in configs.items():
            try:
                # Get the device class name from ConfigManager
                device_class_name = None
                if self.config_manager:
                    device_class_name = self.config_manager.get_device_class_name(device_id)
                
                if not device_class_name:
                    logger.error(f"No class name found for device '{device_id}'. "
                                f"Make sure 'class' is set in system config.")
                    continue
                
                # First try to get the class from already loaded classes
                device_class = self.device_classes.get(device_class_name)
                
                # If not found, attempt to dynamically import it
                if not device_class:
                    try:
                        # Convert class name to module name (e.g., LgTv -> lg_tv)
                        module_name = ''.join(['_'+c.lower() if c.isupper() else c for c in device_class_name]).lstrip('_')
                        logger.info(f"Attempting to dynamically import device class {device_class_name} from module devices.{module_name}")
                        
                        # Import the module and get the class
                        module = importlib.import_module(f"devices.{module_name}")
                        device_class = getattr(module, device_class_name)
                        
                        # Cache the class for future use
                        self.device_classes[device_class_name] = device_class
                        logger.info(f"Successfully imported device class {device_class_name}")
                    except (ImportError, AttributeError) as e:
                        logger.error(f"Failed to dynamically load device class '{device_class_name}': {str(e)}")
                        continue
                
                if not device_class:
                    logger.error(f"Device class {device_class_name} not found for device {device_id}")
                    continue
                
                # Instantiate the device with typed configuration
                device = device_class(config, self.mqtt_client)
                success = await device.setup()
                
                if not success:
                    logger.error(f"Failed to set up device {device_id} of type {device_class_name}")
                    continue
                    
                # Register state change callback if device supports it
                if hasattr(device, 'register_state_change_callback') and self.store:
                    device.register_state_change_callback(self._persist_state_callback)
                    
                self.devices[device_id] = device
                logger.info(f"Initialized device {device_id} of type {device_class_name}")
                
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
            state_dict = device.get_current_state()
            await self.store.set(f"device:{device_id}", state_dict)
            logger.debug(f"Persisted state for device: {device_id}")
        except Exception as e:
            logger.error(f"Failed to persist state for device {device_id}: {str(e)}")
            
    async def perform_action(self, device_id: str, action: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Perform an action on a device and persist its state."""
        device = self.get_device(device_id)
        if not device:
            logger.warning(f"Cannot perform action on unknown device: {device_id}")
            return {"success": False, "error": f"Device not found: {device_id}"}
            
        try:
            result = await device.handle_action(action, params)
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
    
    def _persist_state_callback(self, device_id: str):
        """
        Callback to handle device state changes. Schedules the state to be persisted.
        This method is designed to be called from device instances when their state changes.
        
        Args:
            device_id: The ID of the device whose state changed
        """
        if not self.store:
            logger.debug(f"State store not available, skipping persistence callback for device: {device_id}")
            return
            
        # Use asyncio.create_task to persist state asynchronously without blocking
        try:
            asyncio.create_task(self._persist_state(device_id))
        except RuntimeError:
            # We're not in an event loop, log a warning
            logger.warning(f"Cannot persist state for {device_id}: not in an event loop") 