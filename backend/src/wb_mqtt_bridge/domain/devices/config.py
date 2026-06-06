"""Device configuration base models — domain data.

These are pure data structures (no I/O, no external system) that the domain
operates on, so they live in the domain layer. Transport-specific config
subclasses (e.g. ``IRCommandConfig``, the per-device configs) and the
system/persistence/MQTT configs remain in ``infrastructure/config/models.py``,
which re-exports these names for compatibility.
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, validator


class DeviceCategory(str, Enum):
    """Enumeration for device categories."""
    DEVICE = "device"
    APPLIANCE = "appliance"


class LocalizedName(BaseModel):
    """Bilingual display name for a device or room. `ru` + `en` required; additional locales
    accepted (e.g. `de`, `fr`) and surfaced as-is via the catalog. Lives on `BaseDeviceConfig`
    as `names` (replacing the previous flat `device_name`). Per §P3.7 voice-integration
    contract: every entity carries names in every locale the catalog supports."""
    model_config = ConfigDict(extra="allow")

    ru: str
    en: str


class CommandParameterDefinition(BaseModel):
    """Schema for command parameter definition."""
    name: str = Field(..., description="Parameter name")
    type: str = Field(..., description="Data type (e.g., 'string', 'integer', 'float', 'boolean', 'range')")
    required: bool = Field(..., description="Whether this parameter must be provided")
    default: Optional[Any] = Field(None, description="Default value if parameter is not provided and not required")
    min: Optional[float] = Field(None, description="Minimum allowed value (used with type: 'range')")
    max: Optional[float] = Field(None, description="Maximum allowed value (used with type: 'range')")
    description: Optional[str] = Field(None, description="Human-readable description")


class BaseCommandConfig(BaseModel):
    """Base schema for command configuration."""
    action: Optional[str] = Field(None, description="Action identifier for this command")
    description: Optional[str] = Field(None, description="Human-readable description of the command")
    exposed: bool = Field(
        True,
        description="Whether this command is surfaced (UI/manifest, WB/MQTT, HTTP). False = a "
                    "driver-supported but dormant action, hidden on every surface.",
    )
    params: Optional[List[CommandParameterDefinition]] = Field(
        None,
        description="Parameter definitions for this command"
    )


class StandardCommandConfig(BaseCommandConfig):
    """Standard command configuration with no additional fields."""
    pass


class BaseDeviceConfig(BaseModel):
    """Base schema for device configuration."""
    device_id: str
    names: LocalizedName = Field(..., description="Bilingual display name; see LocalizedName.")
    device_category: DeviceCategory = Field(DeviceCategory.DEVICE, description="The category of the device (e.g., 'device' or 'appliance')")
    # New required fields for dynamic class loading
    device_class: str = Field(..., description="The device implementation class name (e.g., 'LgTv')")
    config_class: str = Field(..., description="The configuration model class name (e.g., 'LgTvDeviceConfig')")
    commands: Dict[str, BaseCommandConfig] = Field(default_factory=dict)

    # Wirenboard virtual device emulation configuration
    enable_wb_emulation: bool = Field(True, description="Enable Wirenboard virtual device emulation")
    wb_controls: Optional[Dict[str, Dict[str, Any]]] = Field(None, description="Custom Wirenboard control definitions")
    wb_state_mappings: Optional[Dict[str, Union[str, List[str]]]] = Field(None, description="Custom state field to WB control mappings")

    @validator('device_class')
    def validate_device_class(cls, v):
        """Validate that device_class is not empty."""
        if not v or not v.strip():
            raise ValueError("device_class must not be empty")
        return v

    @validator('config_class')
    def validate_config_class(cls, v):
        """Validate that config_class is not empty."""
        if not v or not v.strip():
            raise ValueError("config_class must not be empty")
        return v

    @classmethod
    def process_commands(cls, commands_data: Dict[str, Dict[str, Any]]) -> Dict[str, BaseCommandConfig]:
        """
        Process raw command definitions into properly typed command objects.
        Each device config subclass can override this for custom command processing.

        Args:
            commands_data: Raw command data dictionary

        Returns:
            Dictionary of processed command objects
        """
        processed_commands = {}

        for cmd_name, cmd_config in commands_data.items():
            # Skip if not a dictionary
            if not isinstance(cmd_config, dict):
                raise ValueError(f"Command {cmd_name} has invalid format, must be a dictionary")

            # Use standard command for base implementation
            processed_commands[cmd_name] = StandardCommandConfig(**cmd_config)

        return processed_commands

    @classmethod
    def create_from_dict(cls, config_data: Dict[str, Any]) -> 'BaseDeviceConfig':
        """
        Create a configuration instance from a dictionary, processing commands appropriately.

        Args:
            config_data: Raw configuration dictionary

        Returns:
            Initialized configuration object

        Raises:
            ValueError: If the configuration is invalid
        """
        # Create a copy to avoid modifying the original
        config = dict(config_data)

        # Process commands if present
        if "commands" in config and isinstance(config["commands"], dict):
            config["commands"] = cls.process_commands(config["commands"])

        # Create and return the instance
        return cls(**config)
