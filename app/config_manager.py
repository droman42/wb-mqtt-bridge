import json
import os
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class ConfigManager:
    """Manages configuration for the MQTT web service and devices."""
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = config_dir
        self.system_config_file = os.path.join(config_dir, "system.json")
        self.devices_dir = os.path.join(config_dir, "devices")
        self.system_config = {}
        self.device_configs = {}
        
        # Ensure config directories exist
        os.makedirs(self.devices_dir, exist_ok=True)
        
        # Load configurations
        self._load_system_config()
        self._load_device_configs()
    
    def _load_system_config(self):
        """Load the system configuration from JSON file."""
        try:
            with open(self.system_config_file, 'r') as f:
                self.system_config = json.load(f)
            logger.info("System configuration loaded successfully")
        except FileNotFoundError:
            logger.warning(f"System config file not found at {self.system_config_file}")
            self.system_config = {
                "mqtt_broker": {
                    "host": "localhost",
                    "port": 1883,
                    "client_id": "mqtt_web_service"
                },
                "web_service": {
                    "host": "0.0.0.0",
                    "port": 8000
                },
                "log_level": "INFO",
                "log_file": "logs/service.log"
            }
            self._save_system_config()
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in system config file {self.system_config_file}")
            raise
    
    def _save_system_config(self):
        """Save the system configuration to JSON file."""
        try:
            with open(self.system_config_file, 'w') as f:
                json.dump(self.system_config, f, indent=2)
            logger.info("System configuration saved successfully")
        except Exception as e:
            logger.error(f"Failed to save system config: {str(e)}")
            raise
    
    def _load_device_configs(self):
        """Load all device configurations based on system config."""
        self.device_configs = {}
        
        devices_config = self.system_config.get('devices', {})
        
        for device_id, device_info in devices_config.items():
            config_file = device_info.get('config_file')
            if not config_file:
                logger.warning(f"No config file specified for device {device_id}")
                continue
                
            config_path = os.path.join(self.devices_dir, config_file)
            try:
                with open(config_path, 'r') as f:
                    device_config = json.load(f)
                    # Add device_id to the config
                    device_config['device_id'] = device_id
                    # Add class information
                    device_config['device_class'] = device_info.get('class')
                    self.device_configs[device_id] = device_config
                    logger.info(f"Loaded config for device: {device_id}")
            except Exception as e:
                logger.error(f"Error loading device config {config_file}: {str(e)}")
    
    def get_device_class_name(self, device_id: str) -> str:
        """Get the class name for a device."""
        devices_config = self.system_config.get('devices', {})
        device_info = devices_config.get(device_id, {})
        return device_info.get('class')
    
    def get_system_config(self) -> Dict[str, Any]:
        """Get the system configuration."""
        return self.system_config
    
    def get_device_config(self, device_name: str) -> Dict[str, Any]:
        """Get the configuration for a specific device."""
        return self.device_configs.get(device_name, {})
    
    def get_all_device_configs(self) -> Dict[str, Dict[str, Any]]:
        """Get configurations for all devices."""
        return self.device_configs
    
    def get_mqtt_broker_config(self) -> Dict[str, Any]:
        """Get the MQTT broker configuration."""
        return self.system_config.get('mqtt_broker', {})
    
    def get_all_device_topics(self) -> Dict[str, List[str]]:
        """Get all topics for all devices."""
        topics = {}
        for device_name, config in self.device_configs.items():
            topics[device_name] = config.get('mqtt_topics', [])
        return topics
    
    def reload_configs(self):
        """Reload all configurations from disk."""
        self._load_system_config()
        self._load_device_configs()
        logger.info("All configurations reloaded")
        return True 