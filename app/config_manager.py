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
        """Load all device configurations from the devices directory."""
        self.device_configs = {}
        
        if not os.path.exists(self.devices_dir):
            logger.warning(f"Devices directory not found at {self.devices_dir}")
            return
        
        for filename in os.listdir(self.devices_dir):
            if filename.endswith('.json'):
                device_path = os.path.join(self.devices_dir, filename)
                try:
                    with open(device_path, 'r') as f:
                        device_config = json.load(f)
                        device_name = device_config.get('device_name')
                        if device_name:
                            self.device_configs[device_name] = device_config
                            logger.info(f"Loaded config for device: {device_name}")
                        else:
                            logger.warning(f"Missing device_name in config: {device_path}")
                except Exception as e:
                    logger.error(f"Error loading device config {filename}: {str(e)}")
    
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