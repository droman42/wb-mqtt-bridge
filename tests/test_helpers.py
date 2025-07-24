"""
Test helpers for converting dictionary configurations to Pydantic models.
This allows us to run tests that use dictionary configuration with code that expects Pydantic models.
"""

from typing import Dict, Any, List, Optional, TypeVar
from wb_mqtt_bridge.infrastructure.config.models import (
    BaseDeviceConfig,
    BaseCommandConfig,
    StandardCommandConfig,
    IRCommandConfig,
    LgTvConfig,
    LgTvDeviceConfig,
    BroadlinkConfig,
    BroadlinkKitchenHoodConfig,
    EmotivaConfig,
    EmotivaXMC2DeviceConfig,
    AppleTVConfig,
    AppleTVDeviceConfig,
    RevoxA77ReelToReelConfig,
    WirenboardIRDeviceConfig,
    CommandParameterDefinition
)
# Import additional models that might be used
try:
    from wb_mqtt_bridge.infrastructure.config.models import RevoxA77ReelToReelParams
except ImportError:
    # This might be in a different location
    from wb_mqtt_bridge.infrastructure.config.models import RevoxA77ReelToReelParams

T = TypeVar('T')

def dict_to_command_config(config_dict: Dict[str, Any]) -> BaseCommandConfig:
    """Convert a dictionary to the appropriate CommandConfig model."""
    if "location" in config_dict and "rom_position" in config_dict:
        # Convert to IRCommandConfig
        return IRCommandConfig(**config_dict)
    else:
        # Default to StandardCommandConfig
        return StandardCommandConfig(**config_dict)

def create_command_params(params_dicts: List[Dict[str, Any]]) -> Optional[List[CommandParameterDefinition]]:
    """Convert a list of parameter dictionaries to CommandParameterDefinition objects."""
    if not params_dicts:
        return None
    
    return [CommandParameterDefinition(**param) for param in params_dicts]

def process_commands_dict(commands_dict: Dict[str, Dict[str, Any]]) -> Dict[str, BaseCommandConfig]:
    """Process a dictionary of commands into the appropriate CommandConfig models."""
    result = {}
    
    for cmd_name, cmd_config in commands_dict.items():
        # Make a copy of the dict to avoid modifying the original
        cmd_dict = cmd_config.copy()
        
        # Process params if they exist
        if "params" in cmd_dict:
            cmd_dict["params"] = create_command_params(cmd_dict["params"])
        
        # Convert to appropriate command config model
        result[cmd_name] = dict_to_command_config(cmd_dict)
    
    return result

def dict_to_device_config(config_dict: Dict[str, Any]) -> BaseDeviceConfig:
    """Convert a dictionary to a BaseDeviceConfig subclass based on its content."""
    # Make a copy to avoid modifying the original
    config = config_dict.copy()
    
    # Process commands if they exist
    if "commands" in config:
        config["commands"] = process_commands_dict(config["commands"])
    
    # Determine the appropriate device config class based on content
    if "tv" in config:
        # Ensure the 'tv' is a LgTvConfig
        if isinstance(config["tv"], dict):
            config["tv"] = LgTvConfig(**config["tv"])
        return LgTvDeviceConfig(**config)
    elif "broadlink" in config:
        # Ensure 'broadlink' is a BroadlinkConfig
        if isinstance(config["broadlink"], dict):
            config["broadlink"] = BroadlinkConfig(**config["broadlink"])
        return BroadlinkKitchenHoodConfig(**config)
    elif "emotiva" in config:
        # Ensure 'emotiva' is an EmotivaConfig
        if isinstance(config["emotiva"], dict):
            config["emotiva"] = EmotivaConfig(**config["emotiva"])
        return EmotivaXMC2DeviceConfig(**config)
    elif "apple_tv" in config:
        # Process apple_tv config - simplified without protocols handling for now
        if isinstance(config["apple_tv"], dict):
            config["apple_tv"] = AppleTVConfig(**config["apple_tv"])
        return AppleTVDeviceConfig(**config)
    elif "reel_to_reel" in config:
        # Ensure 'reel_to_reel' is a RevoxA77ReelToReelParams
        if isinstance(config["reel_to_reel"], dict):
            config["reel_to_reel"] = RevoxA77ReelToReelParams(**config["reel_to_reel"])
        return RevoxA77ReelToReelConfig(**config)
    else:
        # Default to a simple device config with IRCommandConfig
        return WirenboardIRDeviceConfig(**config)

def wrap_device_init(original_cls):
    """
    Create a wrapper around a device class's __init__ to automatically convert dictionary configs
    to Pydantic models.
    """
    original_init = original_cls.__init__
    
    def new_init(self, config, *args, **kwargs):
        # If config is a dict, convert it to a BaseDeviceConfig
        if isinstance(config, dict):
            config = dict_to_device_config(config)
        return original_init(self, config, *args, **kwargs)
    
    # Replace the original __init__ with the new one
    original_cls.__init__ = new_init
    return original_cls 