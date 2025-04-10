import os
import importlib.util
import logging
import inspect
import sys
from typing import Dict, Any, Callable, List, Optional
from devices.base_device import BaseDevice
from app.schemas import DeviceConfig
from app.mqtt_client import MQTTClient

logger = logging.getLogger(__name__)

class DeviceManager:
    """Manages device modules and their message handlers."""
    
    def __init__(self, devices_dir: str = "devices", mqtt_client: Optional[MQTTClient] = None):
        self.devices_dir = devices_dir
        self.device_classes = {}  # Stores class definitions
        self.devices = {}  # Stores device instances
        self.mqtt_client = mqtt_client
    
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
    
    async def initialize_devices(self, configs: Dict[str, DeviceConfig]):
        """Initialize devices from their configurations."""
        for device_id, config in configs.items():
            try:
                device_type = config.device_type
                device_class = self.device_classes.get(device_type)
                
                if not device_class:
                    logger.error(f"Device type {device_type} not found for device {device_id}")
                    continue
                
                # Create device instance with MQTT client
                device = device_class(config.dict(), self.mqtt_client)
                await device.setup()
                self.devices[device_id] = device
                logger.info(f"Initialized device {device_id} of type {device_type}")
                
            except Exception as e:
                logger.error(f"Failed to initialize device {device_id}: {str(e)}")
    
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
    
    def get_all_devices(self) -> List[str]:
        """Get a list of all device IDs."""
        return list(self.devices.keys()) 