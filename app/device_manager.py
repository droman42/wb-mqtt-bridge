import os
import importlib.util
import logging
import inspect
from typing import Dict, Any, Callable, List, Optional
from devices.base_device import BaseDevice

logger = logging.getLogger(__name__)

class DeviceManager:
    """Manages device modules and their message handlers."""
    
    def __init__(self, devices_dir: str = "devices"):
        self.devices_dir = devices_dir
        self.device_classes = {}  # Stores class definitions
        self.devices = {}  # Stores device instances
    
    async def load_device_modules(self):
        """Dynamically load all device modules from the devices directory."""
        if not os.path.exists(self.devices_dir):
            logger.warning(f"Devices directory not found: {self.devices_dir}")
            return
        
        for filename in os.listdir(self.devices_dir):
            if filename.endswith('.py') and not filename.startswith('__') and filename != 'base_device.py':
                module_name = filename[:-3]
                module_path = os.path.join(self.devices_dir, filename)
                
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
    
    async def initialize_devices(self, configs: Dict[str, Dict[str, Any]]):
        """Initialize all devices with their configurations."""
        for device_id, config in configs.items():
            try:
                # Get the device class name from config
                class_name = config.get('device_class')
                if not class_name:
                    logger.error(f"No device class specified for device {device_id}")
                    continue
                
                # Get the device class
                device_class = self.device_classes.get(class_name)
                if not device_class:
                    logger.error(f"Device class {class_name} not found for device {device_id}")
                    continue
                
                # Create device instance
                device = device_class(config)
                
                # Initialize the device
                if await device.setup():
                    self.devices[device_id] = device
                    logger.info(f"Initialized device: {device_id} (class: {class_name})")
                else:
                    logger.error(f"Failed to initialize device: {device_id}")
            
            except Exception as e:
                logger.error(f"Error initializing device {device_id}: {str(e)}")
    
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
    
    def get_message_handler(self, device_name: str) -> Optional[Callable]:
        """Get the message handler for a device."""
        device = self.devices.get(device_name)
        if not device:
            logger.warning(f"No device found: {device_name}")
            return None
        return device.handle_message
    
    def get_device_state(self, device_name: str) -> Dict[str, Any]:
        """Get the current state of a device."""
        device = self.devices.get(device_name)
        if not device:
            logger.warning(f"No device found: {device_name}")
            return {}
        return device.get_state() 