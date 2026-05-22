import json
import os
import logging
from typing import Dict, Any, Optional, Type

from wb_mqtt_bridge.infrastructure.config.models import (
    SystemConfig, 
    MQTTBrokerConfig,
    BaseDeviceConfig,
    StandardCommandConfig,
    IRCommandConfig,
    MaintenanceConfig
)
from wb_mqtt_bridge.utils.class_loader import load_class_by_name
from wb_mqtt_bridge.utils.validation import (
    validate_device_configs
)

# NOTE: This module now uses the 'device_class' and 'config_class' fields 
# from individual device configurations rather than a centralized mapping.

logger = logging.getLogger(__name__)

class ConfigManager:
    """Manages configuration for the MQTT web service and devices."""
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = config_dir
        self.system_config_file = os.path.join(config_dir, "system.json")
        self.devices_dir = os.path.join(config_dir, "devices")
        self.system_config = SystemConfig(
            service_name="MQTT Web Service",
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
            device_directory="devices"
        )
        # Store only typed configurations
        self.typed_configs: Dict[str, BaseDeviceConfig] = {}
        
        # Ensure config directories exist
        os.makedirs(self.devices_dir, exist_ok=True)
        
        # Load configurations
        self._load_system_config()
        self._discover_and_load_device_configs()
        
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
        
        # Set devices_dir based on system_config if specified
        if hasattr(self.system_config, 'device_directory') and self.system_config.device_directory:
            custom_devices_dir = os.path.join(self.config_dir, self.system_config.device_directory)
            if os.path.exists(custom_devices_dir) or os.path.isdir(custom_devices_dir):
                self.devices_dir = custom_devices_dir
                logger.info(f"Using custom device directory: {self.devices_dir}")
            else:
                logger.warning(
                    f"Custom device directory '{custom_devices_dir}' not found, using default: {self.devices_dir}"
                )
        
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
    
    def _load_config_class(self, config_class_name: str) -> Optional[Type[BaseDeviceConfig]]:
        """
        Dynamically load a configuration class by name.
        
        Args:
            config_class_name: Name of the configuration class
            
        Returns:
            The configuration class if found, None otherwise
        """
        return load_class_by_name(config_class_name, BaseDeviceConfig, "wb_mqtt_bridge.infrastructure.config.models.")
    
    def _process_commands(self, commands_data: Dict[str, Dict[str, Any]], config_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process commands from raw dictionary to typed command objects.
        This delegates to the specific config class's process_commands method if available.
        
        Args:
            commands_data: Raw dictionary of commands
            config_data: Device configuration data containing context information
            
        Returns:
            Dictionary of processed typed commands
        """
        # Get config_class from the data
        config_class_name = config_data.get("config_class")
        if not config_class_name:
            raise RuntimeError(f"Missing 'config_class' field in config data for device '{config_data.get('device_id')}'")
        
        # Load the configuration class
        config_class = self._load_config_class(config_class_name)
        if not config_class:
            raise RuntimeError(f"Config class '{config_class_name}' not found or invalid")
        
        # Use the config class's process_commands method if available
        try:
            return config_class.process_commands(commands_data)
        except Exception as e:
            logger.error(f"Error processing commands with {config_class_name}.process_commands: {str(e)}")
            logger.info("Falling back to general command processing")
            
            # Fall back to generic command processing if custom method fails
            processed_commands = {}
            
            for cmd_name, cmd_config in commands_data.items():
                # Skip if not a dictionary
                if not isinstance(cmd_config, dict):
                    raise RuntimeError(f"Command {cmd_name} has invalid format, must be a dictionary")
                    
                # Choose the appropriate command model based on command structure
                if "location" in cmd_config and "rom_position" in cmd_config:
                    processed_commands[cmd_name] = IRCommandConfig(**cmd_config)
                else:
                    # Use standard command for all other commands
                    processed_commands[cmd_name] = StandardCommandConfig(**cmd_config)
                    
            return processed_commands
    
    def _create_device_config(self, config_data: Dict[str, Any]) -> BaseDeviceConfig:
        """
        Create a typed device configuration using the config_class specified in the data.
        
        Args:
            config_data: Dictionary containing device configuration
            
        Returns:
            Typed device configuration object
            
        Raises:
            RuntimeError: If creation fails for any reason
        """
        # Get config_class from the data
        config_class_name = config_data.get("config_class")
        if not config_class_name:
            raise RuntimeError(f"Missing 'config_class' field in config data for device '{config_data.get('device_id')}'")
        
        # Load the configuration class
        config_class = self._load_config_class(config_class_name)
        if not config_class:
            raise RuntimeError(f"Config class '{config_class_name}' not found or invalid")
        
        # Process commands if present
        if "commands" in config_data and isinstance(config_data["commands"], dict):
            config_data["commands"] = self._process_commands(config_data["commands"], config_data)
        
        # Create instance of the config class
        try:
            return config_class(**config_data)
        except Exception as e:
            raise RuntimeError(f"Failed to create {config_class_name} instance: {str(e)}")
    
    def _discover_and_load_device_configs(self):
        """
        Discover and load all device configurations from the devices directory.
        
        This method replaces the old _load_device_configs method, implementing 
        file-based discovery instead of using the system.devices mapping.
        """
        self.typed_configs = {}
        validation_errors = []
        
        # Run validation on all device configs in the directory
        valid_configs, errors = validate_device_configs(self.devices_dir)
        
        if errors:
            for error in errors:
                logger.error(f"Device config validation error: {error}")
            
            # If there are validation errors, we should still continue with valid configs
            logger.warning(
                f"Found {len(errors)} validation errors in device configurations. "
                f"See log for details. Continuing with {len(valid_configs)} valid configs."
            )
        
        # Process the valid configurations
        for device_id, config_data in valid_configs.items():
            try:
                # Create typed configuration
                self.typed_configs[device_id] = self._create_device_config(config_data)
                logger.info(
                    f"Created typed configuration for device: {device_id} "
                    f"(class: {config_data.get('device_class')})"
                )
            except Exception as e:
                logger.error(f"Error creating typed config for device '{device_id}': {str(e)}")
                validation_errors.append(str(e))
        
        # Log summary
        if validation_errors:
            logger.warning(
                f"Skipped {len(validation_errors)} devices due to configuration errors. "
                f"Successfully loaded {len(self.typed_configs)} device configurations."
            )
        else:
            logger.info(f"Successfully loaded all {len(self.typed_configs)} device configurations")
    
    def get_device_class_name(self, device_id: str) -> Optional[str]:
        """
        Get the class name for a device from its configuration.
        
        Args:
            device_id: The device ID to look up
            
        Returns:
            The class name string or None if not found
        """
        device_config = self.typed_configs.get(device_id)
        if device_config and hasattr(device_config, 'device_class'):
            return device_config.device_class
        return None
    
    def get_system_config(self) -> SystemConfig:
        """Get the system configuration."""
        return self.system_config
    
    def get_service_name(self) -> str:
        """Get the service name from system configuration."""
        return self.system_config.service_name
    
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
    
    def get_maintenance_config(self) -> Optional[MaintenanceConfig]:
        """Get the maintenance configuration if it exists."""
        return self.system_config.maintenance
    
    def is_maintenance_enabled(self) -> bool:
        """Check if maintenance configuration is enabled."""
        return self.system_config.maintenance is not None
    

    
    def reload_configs(self):
        """Reload all configurations from disk."""
        self._load_system_config()
        self._discover_and_load_device_configs()
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
        """
        Check if a group is defined in the system configuration.
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

    def log_migration_guidance(self):
        """Log successful completion of Configuration Migration Phase C."""
        logger.info("✅ Configuration Migration Phase C completed: All devices now use auto-generated topics following WB conventions!") 