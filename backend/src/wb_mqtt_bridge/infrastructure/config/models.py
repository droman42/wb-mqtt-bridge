from typing import Dict, Any, List, Literal, Optional, Union
from pydantic import BaseModel, ConfigDict, Field, field_validator
import os

# Device-config base models are pure domain data — they live in the domain layer
# and are re-exported here so existing infrastructure/test importers keep working.
from wb_mqtt_bridge.domain.devices.config import (  # noqa: F401
    BaseCommandConfig,
    BaseDeviceConfig,
    CommandParameterDefinition,
    DeviceCategory,
    LocalizedName,
    StandardCommandConfig,
)

class MQTTBrokerConfig(BaseModel):
    """Schema for MQTT broker configuration."""
    host: str
    port: int
    client_id: str
    auth: Optional[Dict[str, str]] = None
    keepalive: int = 60

class EmotivaConfig(BaseModel):
    """Schema for Emotiva XMC2 device configuration."""
    host: str
    port: int = 7002
    mac: Optional[str] = None
    update_interval: int = 60
    timeout: Optional[float] = None
    max_retries: Optional[int] = None
    retry_delay: Optional[float] = None
    force_connect: bool = False

class AppleTVProtocolConfig(BaseModel):
    """Schema for Apple TV protocol configuration."""
    identifier: Optional[str] = None
    credentials: str
    data: Optional[Any] = None

class AppleTVConfig(BaseModel):
    """Schema for Apple TV device configuration."""
    ip_address: str
    name: Optional[str] = None
    protocols: Dict[str, AppleTVProtocolConfig]
    gesture_threshold: float = 10.0
    touch_delay: float = 0.1
    select_delay: float = 0.2
    # IR volume control: Apple TV exposes no usable Companion volume (no `_mcF` Volume flag;
    # see §5.1 #7), so volume_up/volume_down fire learned IR codes through a WB IR blaster ROM
    # slot instead (same pattern as the Auralic's ir_power_*_topic). When unset, the handlers
    # fall back to the (typically inert) Companion HID button.
    ir_volume_up_topic: Optional[str] = Field(
        None, description="MQTT topic (WB IR-blaster ROM-play) fired for volume up"
    )
    ir_volume_down_topic: Optional[str] = Field(
        None, description="MQTT topic (WB IR-blaster ROM-play) fired for volume down"
    )

class LgTvConfig(BaseModel):
    """Schema for LG WebOS TV device configuration."""
    ip_address: str
    mac_address: Optional[str] = None
    broadcast_ip: Optional[str] = None
    secure: bool = True
    client_key: Optional[str] = None
    cert_file: Optional[str] = None
    ssl_options: Optional[Dict[str, Any]] = None
    timeout: int = 15
    reconnect_interval: int = Field(
        30,
        ge=10,
        le=600,
        description=(
            "Seconds between TCP probes to the TV's WSS port (3001). The health loop "
            "uses this cadence to disambiguate 'TV off' (probe fails) from 'WS hiccup' "
            "(probe OK → reconnect). Lower = faster recovery, more network noise."
        ),
    )
    
    def model_post_init(self, __context: Any) -> None:
        """Validate that cert_file exists if secure=True"""
        if self.secure and self.cert_file:
            if not os.path.exists(self.cert_file):
                raise ValueError(f"Certificate file {self.cert_file} does not exist")

class BroadlinkConfig(BaseModel):
    """Schema for Broadlink device configuration."""
    host: str
    mac: str
    device_code: str
    timeout: Optional[int] = None
    retry_count: Optional[int] = None

class AuralicConfig(BaseModel):
    """Configuration for Auralic device."""
    ip_address: str
    update_interval: int = 10  # seconds
    discovery_mode: bool = False
    device_url: Optional[str] = None
    # IR control parameters
    ir_power_on_topic: Optional[str] = Field(
        None,
        description="MQTT topic to send IR power on command (required for true power on from deep sleep)"
    )
    ir_power_off_topic: Optional[str] = Field(
        None,
        description="MQTT topic to send IR power off command (required for true power off)"
    )
    device_boot_time: int = Field(
        15,
        description="Time in seconds to wait for device to boot after IR power on",
        ge=5,  # At least 5 seconds
        le=60  # At most 60 seconds
    )
    op_timeout: float = Field(
        5.0,
        description="Per-call timeout (seconds) for OpenHome operations, so a wedged/standby "
                    "device cannot hang the polling loop or an action",
        gt=0,
        le=30,
    )
    reconnect_interval: int = Field(
        60,
        description="Minimum seconds between automatic SSDP re-discovery attempts while the "
                    "device is unreachable (it reassigns its HTTP port on each boot)",
        ge=10,
        le=600,
    )

class IRCommandConfig(BaseCommandConfig):
    """Command configuration for IR-controlled devices."""
    location: str = Field(..., description="IR blaster location identifier")
    rom_position: str = Field(..., description="ROM position for the IR code")


StateFieldType = Literal["str", "int", "float", "bool", "rgb", "enum"]


class StateTopicSpec(BaseModel):
    """Typed spec for one mirrored state field on a WB-passthrough device.

    Carries the MQTT value topic plus per-field metadata the driver uses to coerce the
    raw payload into a typed value (§P3.7 #19). `type` defaults to `"str"` so the
    bare-string config form (`"field": "topic"`) parses through this model unchanged
    via the `state_topics` validator. `encoding` (templates like `"{r};{g};{b}"`) and
    `values` (enum allowed list) are consulted only by the relevant `type` paths.
    """
    model_config = ConfigDict(extra="forbid")

    topic: str = Field(..., description="MQTT value topic to subscribe to.")
    type: StateFieldType = Field("str", description="Wire-to-typed coercion kind.")
    encoding: Optional[str] = Field(
        None,
        description="Template-with-placeholders for composite payloads, e.g. `\"{r};{g};{b}\"` "
                    "for `type=\"rgb\"`. Used to parse incoming echoes back into typed dicts.",
    )
    values: Optional[List[str]] = Field(
        None,
        description="Allowed values for `type=\"enum\"` (incoming payloads are validated against this list).",
    )
    unit: Optional[str] = Field(None, description="Display unit (`°C`, `%`, `ppm`, `lux`, `dB`).")
    invert: bool = Field(
        False,
        description=(
            "When True, the driver applies `100 - value` BOTH directions for this "
            "field: outbound (publishes to commands that target this state topic) and "
            "inbound (incoming mirror echoes). Catches inverted-percentage devices like "
            "the cabinet's `dooya_dm35eq_x_*` rollers, where wire 0=open and 100=closed "
            "instead of the natural sense. With this flag, voice/UI/configs all speak "
            "the natural convention (100=open) and the driver hides the device-family "
            "quirk. Only meaningful for `type` in {int, float}; ignored for str/rgb/enum."
        ),
    )


class WbPassthroughCommandConfig(BaseCommandConfig):
    """Command on a WB-passthrough device — publishes to a Wirenboard control topic.

    For parameter-less commands declare a static `value` (e.g. `"1"` for power_on).
    For single-param commands omit `value` and declare `params` via the inherited
    BaseCommandConfig.params: the driver renders the first param's value as the payload
    (matches the WB convention — one slider → one publish). For composite payloads
    (multi-param like RGB `color.set(r,g,b)` → `"r;g;b"`) declare `payload_template`
    with `{name}` placeholders matching the param names; the driver formats it with the
    invocation params (§P3.7 #19). See §P3.7 A1 for the slice `cabinet_spots.json` example.
    """
    topic: str = Field(..., description="MQTT topic to publish to (typically `/devices/<wb-device>/controls/<control>/on`).")
    value: Optional[str] = Field(None, description="Static payload published verbatim. Omit when `params` is set.")
    payload_template: Optional[str] = Field(
        None,
        description="Format string with `{param_name}` placeholders for composite payloads "
                    "(e.g. `\"{r};{g};{b}\"`). When set, overrides the default single-param "
                    "str-coerce; rendered via `template.format(**params)`.",
    )


class WbPassthroughDeviceConfig(BaseDeviceConfig):
    """Configuration for a generic Wirenboard-passthrough device.

    The bridge is NOT the owner of the underlying WB control — wb-mqtt-serial (and any
    wb-rules acting through it) is. This device class mirrors the control's state by
    subscribing to its value topic AND its per-control `meta/error` topic (Wiren Board
    MQTT convention — see §P3.7 A3), and writes by publishing to the same `/on` topic
    when a canonical action lands. `enable_wb_emulation` defaults to False so the bridge
    skips its own WB virtual-device registration — that's the loop guard: no
    state-change callback re-publishes to the value topic (else we'd feedback-loop with
    the real device).
    """
    enable_wb_emulation: bool = Field(False, description="Passthrough mirrors, never owns. Override only with care.")
    commands: Dict[str, WbPassthroughCommandConfig] = Field(default_factory=dict)
    state_topics: Dict[str, StateTopicSpec] = Field(
        default_factory=dict,
        description="Map of state-field name → typed StateTopicSpec. Bare-string form "
                    "(`\"field\": \"/topic\"`) is back-compat: it normalises to "
                    "`StateTopicSpec(topic=value, type=\"str\")`. The driver mirrors each topic's "
                    "payload into `state.mirrored[name]` (typed per the spec) and subscribes to "
                    "`<topic>/meta/error` for the per-control error flag (`r`/`w`/`p`).",
    )

    @field_validator("state_topics", mode="before")
    @classmethod
    def _normalise_state_topics(cls, v: Any) -> Any:
        """Back-compat: accept bare-string `field: topic` entries and widen them to
        `StateTopicSpec(topic=..., type="str")`. Untouched if already a dict/StateTopicSpec."""
        if not isinstance(v, dict):
            return v
        out: Dict[str, Any] = {}
        for k, raw in v.items():
            if isinstance(raw, str):
                out[k] = {"topic": raw, "type": "str"}
            else:
                out[k] = raw
        return out

    @classmethod
    def process_commands(cls, commands_data: Dict[str, Dict[str, Any]]) -> Dict[str, WbPassthroughCommandConfig]:
        processed: Dict[str, WbPassthroughCommandConfig] = {}
        for cmd_name, cmd_config in commands_data.items():
            if not isinstance(cmd_config, dict):
                raise ValueError(f"Command {cmd_name} has invalid format, must be a dictionary")
            if "topic" not in cmd_config:
                raise ValueError(f"WB-passthrough command {cmd_name} missing required field: topic")
            processed[cmd_name] = WbPassthroughCommandConfig(**cmd_config)
        return processed

# Device-specific parameter models
class RevoxA77ReelToReelParams(BaseModel):
    """Parameters specific to Revox A77 Reel-to-Reel device."""
    sequence_delay: int = Field(5, description="Delay between sequence steps in seconds")

# Device-specific configuration models
class WirenboardIRDeviceConfig(BaseDeviceConfig):
    """Configuration for Wirenboard IR devices."""
    commands: Dict[str, IRCommandConfig] = Field(default_factory=dict)
    
    @classmethod
    def process_commands(cls, commands_data: Dict[str, Dict[str, Any]]) -> Dict[str, IRCommandConfig]:
        """
        Process commands specifically for Wirenboard IR devices.
        
        Args:
            commands_data: Raw command data
            
        Returns:
            Dictionary of processed IR commands
        """
        processed_commands = {}
        
        for cmd_name, cmd_config in commands_data.items():
            if not isinstance(cmd_config, dict):
                raise ValueError(f"Command {cmd_name} has invalid format, must be a dictionary")
                
            # Validate IR command structure
            if "location" not in cmd_config or "rom_position" not in cmd_config:
                raise ValueError(
                    f"IR Command {cmd_name} missing required fields: location and rom_position"
                )
                
            # Create IR command
            processed_commands[cmd_name] = IRCommandConfig(**cmd_config)
                
        return processed_commands

class RevoxA77ReelToReelConfig(BaseDeviceConfig):
    """Configuration for Revox A77 Reel-to-Reel device."""
    commands: Dict[str, IRCommandConfig] = Field(default_factory=dict)
    reel_to_reel: RevoxA77ReelToReelParams
    
    @classmethod
    def process_commands(cls, commands_data: Dict[str, Dict[str, Any]]) -> Dict[str, IRCommandConfig]:
        """
        Process commands specifically for Revox A77 Reel-to-Reel devices.
        Uses the same IR command processing as Wirenboard.
        
        Args:
            commands_data: Raw command data
            
        Returns:
            Dictionary of processed IR commands
        """
        return WirenboardIRDeviceConfig.process_commands(commands_data)

class BroadlinkKitchenHoodConfig(BaseDeviceConfig):
    """Configuration for Broadlink kitchen hood device."""
    commands: Dict[str, BaseCommandConfig] = Field(default_factory=dict)
    broadlink: BroadlinkConfig
    rf_codes: Dict[str, Dict[str, str]] = Field(
        ...,
        description="RF codes mapped by category (light, speed) and state"
    )
    
    @classmethod
    def process_commands(cls, commands_data: Dict[str, Dict[str, Any]]) -> Dict[str, BaseCommandConfig]:
        """
        Process commands specifically for Broadlink kitchen hood devices.
        
        Args:
            commands_data: Raw command data
            
        Returns:
            Dictionary of processed commands
        """
        processed_commands = {}
        
        for cmd_name, cmd_config in commands_data.items():
            if not isinstance(cmd_config, dict):
                raise ValueError(f"Command {cmd_name} has invalid format, must be a dictionary")
                
            # Use StandardCommandConfig for all commands
            processed_commands[cmd_name] = StandardCommandConfig(**cmd_config)
                
        return processed_commands

class LgTvDeviceConfig(BaseDeviceConfig):
    """Configuration for LG TV device."""
    commands: Dict[str, StandardCommandConfig] = Field(default_factory=dict)
    tv: LgTvConfig

class AppleTVDeviceConfig(BaseDeviceConfig):
    """Configuration for Apple TV device."""
    commands: Dict[str, StandardCommandConfig] = Field(default_factory=dict)
    apple_tv: AppleTVConfig

class EmotivaXMC2DeviceConfig(BaseDeviceConfig):
    """Configuration for Emotiva XMC2 device."""
    commands: Dict[str, StandardCommandConfig] = Field(default_factory=dict)
    emotiva: EmotivaConfig

class AuralicDeviceConfig(BaseDeviceConfig):
    """Configuration for Auralic device."""
    commands: Dict[str, StandardCommandConfig] = Field(default_factory=dict)
    auralic: AuralicConfig
    
    @classmethod
    def process_commands(cls, commands_data: Dict[str, Dict[str, Any]]) -> Dict[str, StandardCommandConfig]:
        """
        Process commands specifically for Auralic devices.
        
        Args:
            commands_data: Raw command data
            
        Returns:
            Dictionary of processed standard commands
        """
        processed_commands = {}
        
        for cmd_name, cmd_config in commands_data.items():
            if not isinstance(cmd_config, dict):
                raise ValueError(f"Command {cmd_name} has invalid format, must be a dictionary")
                
            # Create standard command
            processed_commands[cmd_name] = StandardCommandConfig(**cmd_config)
                
        return processed_commands

class PersistenceConfig(BaseModel):
    """Configuration for the persistence layer."""
    db_path: str = Field(default="data/state_store.db", description="Path to the SQLite database file")

class MaintenanceConfig(BaseModel):
    """Configuration for system maintenance settings."""
    duration: int = Field(..., description="Maintenance duration in minutes")
    topic: str = Field(..., description="MQTT topic to monitor for maintenance status")

class SystemConfig(BaseModel):
    """Schema for system configuration."""
    service_name: str = Field(default="MQTT Web Service", description="Name of the service")
    mqtt_broker: MQTTBrokerConfig
    web_service: Dict[str, Any]
    log_level: str
    log_file: str
    loggers: Optional[Dict[str, str]] = None
    # Remove devices dictionary from required fields and make it optional
    devices: Optional[Dict[str, Dict[str, Any]]] = None
    persistence: PersistenceConfig = Field(default_factory=PersistenceConfig)
    maintenance: Optional[MaintenanceConfig] = Field(default=None, description="Maintenance configuration settings")
    # Add explicit device directory configuration
    device_directory: str = Field(default="devices", description="Directory containing device configuration files") 