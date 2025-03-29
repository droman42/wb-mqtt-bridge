import os
import importlib.util
import logging
import inspect
from typing import Dict, Any, Callable, List, Optional

logger = logging.getLogger(__name__)

class DeviceManager:
    """Manages device modules and their message handlers."""
    
    def __init__(self, devices_dir: str = "devices"):
        self.devices_dir = devices_dir
        self.device_modules = {}
        self.message_handlers = {}
    
    def load_device_modules(self):
        """Dynamically load all device modules from the devices directory."""
        if not os.path.exists(self.devices_dir):
            logger.warning(f"Devices directory not found: {self.devices_dir}")
            return
        
        # Get all Python files in the devices directory
        for filename in os.listdir(self.devices_dir):
            if filename.endswith('.py') and not filename.startswith('__'):
                module_name = filename[:-3]  # Remove .py extension
                module_path = os.path.join(self.devices_dir, filename)
                
                try:
                    # Load the module dynamically
                    spec = importlib.util.spec_from_file_location(module_name, module_path)
                    if not spec or not spec.loader:
                        logger.error(f"Failed to load spec for module: {module_name}")
                        continue
                        
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    # Verify that the module has the required functions
                    if not hasattr(module, 'subscribe_topics') or not hasattr(module, 'handle_message'):
                        logger.warning(f"Module {module_name} is missing required functions")
                        continue
                    
                    # Store the module
                    self.device_modules[module_name] = module
                    logger.info(f"Loaded device module: {module_name}")
                    
                    # Register the message handler
                    self.message_handlers[module_name] = module.handle_message
                
                except Exception as e:
                    logger.error(f"Error loading device module {module_name}: {str(e)}")
    
    def get_device_topics(self, device_name: str, device_config: Dict[str, Any]) -> List[str]:
        """Get the topics to subscribe for a device."""
        module = self.device_modules.get(device_name)
        if not module:
            logger.warning(f"No module found for device: {device_name}")
            return []
        
        try:
            # Call the subscribe_topics function from the device module
            if hasattr(module, 'subscribe_topics'):
                topics = module.subscribe_topics(device_config)
                logger.info(f"Got topics for {device_name}: {topics}")
                return topics
            else:
                logger.warning(f"Module {device_name} has no subscribe_topics function")
                return []
        except Exception as e:
            logger.error(f"Error getting topics for {device_name}: {str(e)}")
            return []
    
    def get_message_handler(self, device_name: str) -> Optional[Callable]:
        """Get the message handler for a device."""
        handler = self.message_handlers.get(device_name)
        if not handler:
            logger.warning(f"No message handler found for device: {device_name}")
        return handler
    
    def get_all_devices(self) -> List[str]:
        """Get a list of all loaded device modules."""
        return list(self.device_modules.keys())
    
    def reload_device_modules(self):
        """Reload all device modules."""
        self.device_modules = {}
        self.message_handlers = {}
        self.load_device_modules()
        logger.info("All device modules reloaded")
        return True 