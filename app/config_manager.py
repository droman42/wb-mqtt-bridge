import json
import os
import logging
from typing import Dict, Any, List, Optional, Type, Union, cast
from app.schemas import (
    SystemConfig, 
    DeviceConfig,
    MQTTBrokerConfig,
    BaseDeviceConfig,
    WirenboardIRDeviceConfig,
    RevoxA77ReelToReelConfig,
    BroadlinkKitchenHoodConfig,
    LgTvDeviceConfig,
    AppleTVDeviceConfig,
    EmotivaXMC2DeviceConfig,
    StandardCommandConfig,
    IRCommandConfig,
    BroadlinkCommandConfig,
    BaseCommandConfig
)

logger = logging.getLogger(__name__)

class ConfigManager:
    """Manages configuration for the MQTT web service and devices."""
    
    # Mapping of device class names to their specific config model classes
    _config_models: Dict[str, Type[BaseDeviceConfig]] = {
        "WirenboardIRDevice": WirenboardIRDeviceConfig,
        "RevoxA77ReelToReel": RevoxA77ReelToReelConfig,
        "BroadlinkKitchenHood": BroadlinkKitchenHoodConfig,
        "LgTv": LgTvDeviceConfig,
        "AppleTVDevice": AppleTVDeviceConfig,
        "EMotivaXMC2": EmotivaXMC2DeviceConfig
    }
    
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
        # Store only typed configurations
        self.typed_configs: Dict[str, BaseDeviceConfig] = {}
        
        # Ensure config directories exist
        os.makedirs(self.devices_dir, exist_ok=True)
        
        # Load configurations
        self._load_system_config()
        self._load_device_configs()
        
        # Extract group definitions
        self._groups = self.system_config.groups or {}
        logger.info(f"Loaded {len(self._groups)} function groups from system config")
    
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
        return self.system_config
    
    def _save_system_config(self):
        """Save the system configuration to JSON file."""
        try:
            with open(self.system_config_file, 'w') as f:
                json.dump(self.system_config.model_dump(), f, indent=2)
            logger.info("System configuration saved successfully")
        except Exception as e:
            logger.error(f"Failed to save system config: {str(e)}")
            raise
    
    def _create_typed_config(self, config_data: Dict[str, Any]) -> BaseDeviceConfig:
        """
        Create a typed device configuration from a dictionary.
        
        Args:
            config_data: Dictionary containing the device configuration
            
        Returns:
            Typed device configuration object
            
        Raises:
            RuntimeError: If creation fails for any reason
        """
        # Get the device class from the config
        device_class = config_data.get("device_class")
        if not device_class:
            raise RuntimeError(f"Missing device_class in device configuration: {config_data.get('device_id', 'unknown')}")
            
        # Get the config model for this device class
        config_model = self._config_models.get(device_class)
        if not config_model:
            available_models = list(self._config_models.keys())
            raise RuntimeError(
                f"No typed config model found for device class: {device_class}. "
                f"Available models: {available_models}"
            )
            
        # Process commands to ensure they're properly typed
        if "commands" in config_data:
            processed_commands = {}
            commands = config_data["commands"]
            
            for cmd_name, cmd_config in commands.items():
                # Skip if not a dictionary
                if not isinstance(cmd_config, dict):
                    raise RuntimeError(f"Command {cmd_name} has invalid format, must be a dictionary")
                    
                # Choose the appropriate command model based on device class
                if device_class == "WirenboardIRDevice" or device_class == "RevoxA77ReelToReel":
                    if "location" in cmd_config and "rom_position" in cmd_config:
                        processed_commands[cmd_name] = IRCommandConfig(**cmd_config)
                    else:
                        raise RuntimeError(f"IR Command {cmd_name} missing required fields: location and rom_position")
                elif device_class == "BroadlinkKitchenHood" and "rf_code" in cmd_config:
                    processed_commands[cmd_name] = BroadlinkCommandConfig(**cmd_config)
                else:
                    # Use standard command for all other devices
                    processed_commands[cmd_name] = StandardCommandConfig(**cmd_config)
                    
            config_data["commands"] = processed_commands
            
        # Create and return the typed configuration
        try:
            return config_model(**config_data)
        except Exception as e:
            raise RuntimeError(f"Failed to create {device_class} config: {str(e)}")
    
    def _load_device_configs(self):
        """Load all device configurations based on system config, with strict validation."""
        self.typed_configs = {}
        
        for device_id, device_info in self.system_config.devices.items():
            config_file = device_info.get("config_file")
            if not config_file:
                logger.error(f"Missing config_file in system config for device_id '{device_id}'")
                continue
                
            config_path = os.path.join(self.devices_dir, config_file)
            if not os.path.exists(config_path):
                logger.error(f"Config file '{config_path}' not found for device_id '{device_id}'")
                continue
            
            try:
                # Load device configuration data
                with open(config_path, 'r') as f:
                    device_config_dict = json.load(f)
                    
                # Add device_id to the config
                if "device_id" in device_config_dict and device_config_dict["device_id"] != device_id:
                    # Raise error if device_id in file doesn't match expected from system config
                    raise RuntimeError(
                        f"Config file '{config_file}' has device_id '{device_config_dict.get('device_id')}' "
                        f"but expected '{device_id}'"
                    )
                    
                device_config_dict["device_id"] = device_id
                
                # Add class information
                device_class = device_info.get("class")
                if not device_class:
                    raise RuntimeError(f"Missing 'class' field in system config for device_id '{device_id}'")
                    
                device_config_dict["device_class"] = device_class
                
                # Create typed config with no fallbacks - let failures raise errors
                self.typed_configs[device_id] = self._create_typed_config(device_config_dict)
                logger.info(f"Created typed configuration for device: {device_id} ({device_class})")
                
            except Exception as e:
                # Log error and re-raise to prevent loading this device
                logger.error(f"Error loading device config {config_file}: {str(e)}")
                raise RuntimeError(f"Failed to load config for device '{device_id}': {str(e)}")
    
    def get_device_class_name(self, device_id: str) -> Optional[str]:
        """Get the class name for a device."""
        devices_config = self.system_config.devices
        device_info = devices_config.get(device_id, {})
        return device_info.get('class')
    
    def get_system_config(self) -> SystemConfig:
        """Get the system configuration."""
        return self.system_config
    
    def get_device_config(self, device_id: str) -> Optional[BaseDeviceConfig]:
        """Get the configuration for a specific device."""
        return self.typed_configs.get(device_id)
    
    def get_typed_config(self, device_id: str) -> Optional[BaseDeviceConfig]:
        """Get the typed configuration for a specific device if available."""
        return self.typed_configs.get(device_id)
    
    def get_all_device_configs(self) -> Dict[str, BaseDeviceConfig]:
        """Get configurations for all devices."""
        return self.typed_configs
    
    def get_all_typed_configs(self) -> Dict[str, BaseDeviceConfig]:
        """Get typed configurations for all devices that have them."""
        return self.typed_configs
    
    def get_mqtt_broker_config(self) -> MQTTBrokerConfig:
        """Get the MQTT broker configuration."""
        return self.system_config.mqtt_broker
    
    def get_all_progress_topics(self) -> Dict[str, str]:
        """Get all progress topics for all devices."""
        topics = {}
        for device_id, config in self.typed_configs.items():
            topics[device_id] = config.mqtt_progress_topic
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

    def is_valid_group(self, group_id: str) -> bool:
        """Check if a group is defined in the system configuration.
        The 'default' group is always considered valid.
        
        Args:
            group_id: The group ID to validate
            
        Returns:
            bool: True if the group is valid, False otherwise
        """
        if group_id == "default":
            return True
        
        groups = self.get_groups()
        return group_id in groups

    @classmethod
    def register_config_model(cls, device_class: str, config_model: Type[BaseDeviceConfig]):
        """
        Register a new configuration model for a device class.
        
        Args:
            device_class: Device class name (e.g., "WirenboardIRDevice")
            config_model: Configuration model class
        """
        cls._config_models[device_class] = config_model
        logger.info(f"Registered config model for device class: {device_class}") 