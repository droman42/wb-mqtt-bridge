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
        self.devices: Dict[str, BaseDevice] = {}
    
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
                    
                    # Find device class (subclass of BaseDevice)
                    device_class = None
                    for item in dir(module):
                        obj = getattr(module, item)
                        if isinstance(obj, type) and issubclass(obj, BaseDevice) and obj != BaseDevice:
                            device_class = obj
                            break
                    
                    if not device_class:
                        logger.warning(f"No device class found in module: {module_name}")
                        continue
                    
                    logger.info(f"Loaded device module: {module_name}")
                    self.devices[module_name] = device_class
                
                except Exception as e:
                    logger.error(f"Error loading device module {module_name}: {str(e)}")
    
    async def initialize_devices(self, configs: Dict[str, Dict[str, Any]]):
        """Initialize all devices with their configurations."""
        for device_name, config in configs.items():
            device_type = config.get('device_type')
            if device_type not in self.devices:
                logger.warning(f"No device found for type: {device_type}")
                continue
            
            try:
                # Create device instance
                device_class = self.devices[device_type]
                device = device_class(config)
                
                # Initialize the device
                if await device.setup():
                    self.devices[device_name] = device
                    logger.info(f"Initialized device: {device_name}")
                else:
                    logger.error(f"Failed to initialize device: {device_name}")
            
            except Exception as e:
                logger.error(f"Error initializing device {device_name}: {str(e)}")
    
    async def shutdown_devices(self):
        """Shutdown all devices."""
        for device_name, device in self.devices.items():
            try:
                await device.shutdown()
                logger.info(f"Shutdown device: {device_name}")
            except Exception as e:
                logger.error(f"Error shutting down device {device_name}: {str(e)}")
    
    def get_device_topics(self, device_name: str) -> List[str]:
        """Get the topics to subscribe for a device."""
        device = self.devices.get(device_name)
        if not device:
            logger.warning(f"No device found: {device_name}")
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