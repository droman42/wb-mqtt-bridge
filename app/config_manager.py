import json
import os
import logging
import importlib
from typing import Dict, Any, List, Optional, Type, Union, cast, Set, Tuple
from pathlib import Path

from app.schemas import (
    SystemConfig, 
    MQTTBrokerConfig,
    BaseDeviceConfig,
    StandardCommandConfig,
    IRCommandConfig,
    BaseCommandConfig,
    MaintenanceConfig
)
from app.class_loader import load_class_by_name
from app.validation import (
    validate_device_configs,
    validate_config_file_structure,
    discover_config_files
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
        return load_class_by_name(config_class_name, BaseDeviceConfig, "app.schemas.")
    
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

    def check_deprecated_topic_usage(self) -> Dict[str, List[str]]:
        """
        Check all device configurations for deprecated explicit topic usage.
        
        Returns:
            Dict[str, List[str]]: Dictionary mapping device IDs to lists of commands with explicit topics
        """
        deprecated_usage = {}
        
        for device_id, config in self.typed_configs.items():
            commands_with_topics = []
            
            for cmd_name, cmd_config in config.commands.items():
                if hasattr(cmd_config, 'topic') and cmd_config.topic:
                    commands_with_topics.append(cmd_name)
            
            if commands_with_topics:
                deprecated_usage[device_id] = commands_with_topics
        
        return deprecated_usage
    
    def get_migration_guidance(self) -> Dict[str, Any]:
        """
        Get comprehensive migration guidance for moving from explicit to auto-generated topics.
        
        Returns:
            Dict[str, Any]: Migration guidance with statistics and recommendations
        """
        deprecated_usage = self.check_deprecated_topic_usage()
        
        total_devices = len(self.typed_configs)
        devices_needing_migration = len(deprecated_usage)
        total_commands_with_topics = sum(len(commands) for commands in deprecated_usage.values())
        
        guidance = {
            'summary': {
                'total_devices': total_devices,
                'devices_needing_migration': devices_needing_migration,
                'total_commands_with_explicit_topics': total_commands_with_topics,
                'migration_progress': f"{devices_needing_migration}/{total_devices} devices need migration"
            },
            'deprecated_usage': deprecated_usage,
            'migration_steps': [
                "1. Review each device configuration file",
                "2. Remove the 'topic' field from command definitions",
                "3. Test that auto-generated topics work correctly",
                "4. Update any external integrations to use new topic format",
                "5. Restart the service to apply changes"
            ],
            'auto_generated_topic_format': "/devices/{device_id}/controls/{command_name}",
            'benefits': [
                "Cleaner, shorter configuration files",
                "Consistent topic naming across all devices",
                "Automatic compliance with Wirenboard conventions",
                "Reduced configuration errors and typos",
                "Easier device configuration maintenance"
            ]
        }
        
        # Add specific migration examples
        examples = []
        for device_id, commands in list(deprecated_usage.items())[:3]:  # Show first 3 examples
            device_examples = []
            for cmd_name in commands[:2]:  # Show first 2 commands per device
                cmd_config = self.typed_configs[device_id].commands[cmd_name]
                example = {
                    'current_topic': cmd_config.topic,
                    'auto_generated_topic': f"/devices/{device_id}/controls/{cmd_name}",
                    'action': f"Remove 'topic' field from '{cmd_name}' command in {device_id} configuration"
                }
                device_examples.append(example)
            examples.append({
                'device_id': device_id,
                'examples': device_examples
            })
        
        guidance['migration_examples'] = examples
        
        return guidance
    
    def log_migration_guidance(self):
        """Log migration guidance for deprecated topic usage."""
        guidance = self.get_migration_guidance()
        
        if guidance['summary']['devices_needing_migration'] == 0:
            logger.info("✅ All device configurations are using auto-generated topics - no migration needed!")
            return
        
        logger.warning("📋 CONFIGURATION MIGRATION NEEDED:")
        logger.warning(f"   {guidance['summary']['migration_progress']} devices need topic migration")
        logger.warning(f"   {guidance['summary']['total_commands_with_explicit_topics']} commands have explicit topics")
        
        logger.warning("📌 Devices needing migration:")
        for device_id, commands in guidance['deprecated_usage'].items():
            logger.warning(f"   • {device_id}: {len(commands)} commands ({', '.join(commands[:3])}{'...' if len(commands) > 3 else ''})")
        
        logger.warning("🔄 Migration steps:")
        for step in guidance['migration_steps']:
            logger.warning(f"   {step}")
        
        logger.warning("📖 For detailed migration guidance, check the virtual_devices.md documentation") 