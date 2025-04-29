import logging
from typing import Dict, Any, Type, Optional, Union, cast
import json
import os
from app.schemas import (
    BaseDeviceConfig,
    WirenboardIRDeviceConfig,
    RevoxA77ReelToReelConfig,
    BroadlinkKitchenHoodConfig,
    LgTvDeviceConfig,
    AppleTVDeviceConfig,
    EmotivaXMC2DeviceConfig,
    ExampleDeviceConfig,
    StandardCommandConfig,
    IRCommandConfig,
    BroadlinkCommandConfig,
    BaseCommandConfig
)

logger = logging.getLogger(__name__)

class DeviceConfigFactory:
    """Factory for creating typed device configuration objects."""

    # Mapping of device_class to configuration model
    _config_map: Dict[str, Type[BaseDeviceConfig]] = {
        "wirenboard_ir": WirenboardIRDeviceConfig,
        "revox_a77_reel_to_reel": RevoxA77ReelToReelConfig,
        "broadlink_kitchen_hood": BroadlinkKitchenHoodConfig,
        "lg_tv": LgTvDeviceConfig,
        "apple_tv_device": AppleTVDeviceConfig,
        "emotiva_xmc2": EmotivaXMC2DeviceConfig,
        "example_device": ExampleDeviceConfig
    }

    @classmethod
    def create_from_dict(cls, config_data: Dict[str, Any]) -> Optional[BaseDeviceConfig]:
        """
        Create a typed device configuration from a dictionary.
        
        Args:
            config_data: Dictionary containing the device configuration
            
        Returns:
            Typed device configuration object or None if creation fails
        """
        try:
            # Get the device class from the config
            device_class = config_data.get("device_class")
            if not device_class:
                logger.error(f"Missing device_class in device configuration: {config_data.get('device_id', 'unknown')}")
                return None
                
            # Get the config model for this device class
            config_model = cls._config_map.get(device_class)
            if not config_model:
                logger.warning(f"No typed config model found for device class: {device_class}")
                logger.warning(f"Available config models: {list(cls._config_map.keys())}")
                return None
                
            # Process commands to ensure they're properly typed
            if "commands" in config_data:
                processed_commands = {}
                commands = config_data["commands"]
                
                for cmd_name, cmd_config in commands.items():
                    # Skip if not a dictionary
                    if not isinstance(cmd_config, dict):
                        logger.warning(f"Command {cmd_name} has invalid format, skipping")
                        continue
                        
                    # Choose the appropriate command model
                    if device_class in ["wirenboard_ir", "revox_a77_reel_to_reel"]:
                        if "location" in cmd_config and "rom_position" in cmd_config:
                            processed_commands[cmd_name] = IRCommandConfig(**cmd_config)
                        else:
                            logger.error(f"IR Command {cmd_name} missing required fields: location and rom_position")
                            continue
                    elif device_class == "broadlink_kitchen_hood" and "rf_code" in cmd_config:
                        processed_commands[cmd_name] = BroadlinkCommandConfig(**cmd_config)
                    else:
                        # Use standard command for all other devices
                        processed_commands[cmd_name] = StandardCommandConfig(**cmd_config)
                        
                config_data["commands"] = processed_commands
                
            # Create and return the typed configuration
            return config_model(**config_data)
            
        except Exception as e:
            logger.error(f"Error creating device configuration: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return None
            
    @classmethod
    def create_from_file(cls, file_path: str) -> Optional[BaseDeviceConfig]:
        """
        Create a typed device configuration from a JSON file.
        
        Args:
            file_path: Path to the JSON configuration file
            
        Returns:
            Typed device configuration object or None if creation fails
        """
        try:
            if not os.path.exists(file_path):
                logger.error(f"Configuration file not found: {file_path}")
                return None
                
            with open(file_path, 'r') as f:
                config_data = json.load(f)
                
            return cls.create_from_dict(config_data)
            
        except Exception as e:
            logger.error(f"Error loading device configuration from {file_path}: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return None
            
    @classmethod
    def register_config_model(cls, device_class: str, config_model: Type[BaseDeviceConfig]):
        """
        Register a new configuration model for a device class.
        
        Args:
            device_class: Device class identifier
            config_model: Configuration model class
        """
        cls._config_map[device_class] = config_model
        logger.info(f"Registered config model for device class: {device_class}") 