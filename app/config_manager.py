import json
import os
import logging
from typing import Dict, Any, List, Optional
from app.schemas import SystemConfig, DeviceConfig, MQTTBrokerConfig

logger = logging.getLogger(__name__)

class ConfigManager:
    """Manages configuration for the MQTT web service and devices."""
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = config_dir
        self.system_config_file = os.path.join(config_dir, "system.json")
        self.devices_dir = os.path.join(config_dir, "devices")
        self.system_config = SystemConfig(
            mqtt_broker=MQTTBrokerConfig(
                host="localhost",
                port=1883,
                client_id="mqtt_web_service"
            ),
            web_service={
                "host": "0.0.0.0",
                "port": 8000
            },
            log_level="INFO",
            log_file="logs/service.log",
            devices={}
        )
        self.device_configs: Dict[str, DeviceConfig] = {}
        
        # Ensure config directories exist
        os.makedirs(self.devices_dir, exist_ok=True)
        
        # Load configurations
        self._load_system_config()
        self._load_device_configs()
        
        # Extract group definitions
        self._groups = self.system_config.groups or {}
        logger.info(f"Loaded {len(self._groups)} function groups from system config")
        
        # Override MQTT broker config with environment variables
        # self._apply_environment_variables()
    
    def _load_system_config(self):
        """Load the system configuration from JSON file."""
        try:
            with open(self.system_config_file, 'r') as f:
                config_data = json.load(f)
                self.system_config = SystemConfig(**config_data)
            logger.info("System configuration loaded successfully")
        except FileNotFoundError:
            logger.warning(f"System config file not found at {self.system_config_file}")
            self._save_system_config()
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in system config file {self.system_config_file}")
            raise
    
    def _save_system_config(self):
        """Save the system configuration to JSON file."""
        try:
            with open(self.system_config_file, 'w') as f:
                json.dump(self.system_config.model_dump(), f, indent=2)
            logger.info("System configuration saved successfully")
        except Exception as e:
            logger.error(f"Failed to save system config: {str(e)}")
            raise
    
    def _load_device_configs(self):
        """Load all device configurations based on system config."""
        self.device_configs = {}
        
        devices_config = self.system_config.devices
        
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
                    self.device_configs[device_id] = DeviceConfig(**device_config)
                    logger.info(f"Loaded config for device: {device_id}")
            except Exception as e:
                logger.error(f"Error loading device config {config_file}: {str(e)}")
    
    def get_device_class_name(self, device_id: str) -> Optional[str]:
        """Get the class name for a device."""
        devices_config = self.system_config.devices
        device_info = devices_config.get(device_id, {})
        return device_info.get('class')
    
    def get_system_config(self) -> SystemConfig:
        """Get the system configuration."""
        return self.system_config
    
    def get_device_config(self, device_name: str) -> Optional[DeviceConfig]:
        """Get the configuration for a specific device."""
        return self.device_configs.get(device_name)
    
    def get_all_device_configs(self) -> Dict[str, DeviceConfig]:
        """Get configurations for all devices."""
        return self.device_configs
    
    def get_mqtt_broker_config(self) -> MQTTBrokerConfig:
        """Get the MQTT broker configuration."""
        return self.system_config.mqtt_broker
    
    def get_all_progress_topics(self) -> Dict[str, str]:
        """Get all progress topics for all devices."""
        topics = {}
        for device_name, config in self.device_configs.items():
            topics[device_name] = config.mqtt_progress_topic
        return topics
    
    def reload_configs(self):
        """Reload all configurations from disk."""
        self._load_system_config()
        self._load_device_configs()
        logger.info("All configurations reloaded")
        return True
    
    def _apply_environment_variables(self):
        """Apply environment variables to configuration."""
        mqtt_config = self.system_config.mqtt_broker
        
        # Update MQTT broker configuration
        mqtt_config.host = os.getenv('MQTT_BROKER_HOST', mqtt_config.host)
        mqtt_config.port = int(os.getenv('MQTT_BROKER_PORT', str(mqtt_config.port)))
        
        # Add authentication only if credentials are provided and non-empty
        username = os.getenv('MQTT_USERNAME')
        password = os.getenv('MQTT_PASSWORD')
        if username and password and username.strip() and password.strip():
            mqtt_config.auth = {"username": username, "password": password}
            logger.info("Using MQTT authentication credentials from environment variables")
        
        # Update the system configuration
        self.system_config.mqtt_broker = mqtt_config 
    
    def get_groups(self) -> Dict[str, str]:
        """Get the function groups defined in the system configuration."""
        groups = dict(self._groups)
        
        # Ensure default group exists
        if "default" not in groups:
            groups["default"] = "Default Group"
            
        return groups 