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


class ValueLabel(BaseModel):
    """One entry of an enum value table — three layers per value (§P3.7 #26).

    * `wire` — what MQTT publishes / subscribes (e.g. `"2"` for HVAC mode "cool").
    * `canonical` — short identifier-safe English name used in canonical actions and
      stored in `state.mirrored` after inbound translation (e.g. `"cool"`).
    * `labels` — optional localized human strings (`{ru, en, de, ...}`) for UI dropdowns
      and voice intent matching. Absent on entries built from the bare-string back-compat
      form (`values: ["a", "b"]`) — they parse to `ValueLabel(wire="a", canonical="a")`
      with `labels=None`.

    Same symmetric-translation shape as the `invert` flag on `StateTopicSpec`: the driver
    translates canonical→wire on outbound publishes and wire→canonical on inbound mirror
    echoes. Catalog projects the full list so voice/UI can autodiscover.
    """
    model_config = ConfigDict(extra="forbid")

    wire: str = Field(..., description="MQTT wire payload for this enum value.")
    canonical: str = Field(..., description="Canonical identifier (action params + state.mirrored).")
    labels: Optional[LocalizedName] = Field(
        None,
        description="Localized human strings for UI / voice. Optional — bare-string back-compat "
                    "entries have `labels=None`.",
    )


def _normalise_value_labels(v: Any) -> Any:
    """Back-compat normaliser: accept bare `["a", "b"]` and widen each to
    `{wire: "a", canonical: "a"}`. Untouched when entries are already dicts/ValueLabels.

    Used by both `CapabilityField.values` and `StateTopicSpec.values` `mode="before"`
    validators (§P3.7 #26 back-compat: bare strings keep parsing)."""
    if v is None or not isinstance(v, list):
        return v
    out: List[Any] = []
    for item in v:
        if isinstance(item, str):
            out.append({"wire": item, "canonical": item})
        else:
            out.append(item)
    return out


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
    action: Optional[str] = Field(default=None, description="Action identifier for this command")
    description: Optional[str] = Field(default=None, description="Human-readable description of the command")
    exposed: bool = Field(
        default=True,
        description="Whether this command is surfaced (UI/manifest, WB/MQTT, HTTP). False = a "
                    "driver-supported but dormant action, hidden on every surface.",
    )
    params: Optional[List[CommandParameterDefinition]] = Field(
        default=None,
        description="Parameter definitions for this command",
    )


class StandardCommandConfig(BaseCommandConfig):
    """Standard command configuration with no additional fields."""
    pass


class BaseDeviceConfig(BaseModel):
    """Base schema for device configuration."""
    device_id: str
    names: LocalizedName = Field(..., description="Bilingual display name; see LocalizedName.")
    capability_profile: Optional[str] = Field(
        None,
        description="Name of a shared capability profile from `config/capabilities/profiles/`. "
                    "Lets many similar devices (every relay-light, every cover, every heating "
                    "loop) share one capability map authored once. The resolver merges the "
                    "profile on top of the class-level map and then merges any per-instance "
                    "override on top of that. `None` for devices whose capability shape is fully "
                    "captured by their device-class file (the AV pattern -- LgTv, AppleTVDevice, "
                    "etc.).",
    )
    room: Optional[str] = Field(
        None,
        description="Room id (matches an entry in `rooms.json`). A device belongs to **exactly "
                    "one** room. Aggregate whole-house controls (e.g. `all_lights`) live in the "
                    "special `global` room. Whole-house actions (\"выключи свет везде\") resolve "
                    "to a SINGLE canonical call against the matching aggregate device in `global` "
                    "-- Irene does NOT iterate rooms; the bridge ships the aggregates the v1 "
                    "voice command set needs (§P3.7 #22). `None` for AV gear that doesn't yet "
                    "have a room (populated during bulk onboarding, §P3.7 #21+#23).",
    )
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
