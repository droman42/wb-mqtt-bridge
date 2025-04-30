from typing import Dict, Any, List, Optional, Union, Literal, Type, TypeVar, Generic
from pydantic import BaseModel, Field, validator
from datetime import datetime
from enum import Enum
import os
from typing_extensions import Protocol

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

class LgTvConfig(BaseModel):
    """Schema for LG WebOS TV device configuration."""
    ip_address: str
    mac_address: Optional[str] = None
    secure: bool = True
    client_key: Optional[str] = None
    cert_file: Optional[str] = None
    ssl_options: Optional[Dict[str, Any]] = None
    timeout: int = 15
    reconnect_interval: Optional[int] = None
    
    def model_post_init(self, __context: Any) -> None:
        """Validate that cert_file exists if secure=True"""
        if self.secure and self.cert_file:
            if not os.path.exists(self.cert_file):
                raise ValueError(f"Certificate file {self.cert_file} does not exist")

class BroadlinkConfig(BaseModel):
    """Schema for Broadlink device configuration."""
    host: str
    mac: str
    device_class: str
    timeout: Optional[int] = None
    retry_count: Optional[int] = None

class CommandParameterDefinition(BaseModel):
    """Schema for command parameter definition."""
    name: str = Field(..., description="Parameter name")
    type: str = Field(..., description="Data type (e.g., 'string', 'integer', 'float', 'boolean', 'range')")
    required: bool = Field(..., description="Whether this parameter must be provided")
    default: Optional[Any] = Field(None, description="Default value if parameter is not provided and not required")
    min: Optional[float] = Field(None, description="Minimum allowed value (used with type: 'range')")
    max: Optional[float] = Field(None, description="Maximum allowed value (used with type: 'range')")
    description: Optional[str] = Field(None, description="Human-readable description")

# New strongly-typed command configuration models
class BaseCommandConfig(BaseModel):
    """Base schema for command configuration."""
    action: Optional[str] = Field(None, description="Action identifier for this command")
    topic: Optional[str] = Field(None, description="MQTT topic this command listens to")
    description: Optional[str] = Field(None, description="Human-readable description of the command")
    group: Optional[str] = Field(None, description="Functional group this command belongs to")
    params: Optional[List[CommandParameterDefinition]] = Field(
        None, 
        description="Parameter definitions for this command"
    )

class StandardCommandConfig(BaseCommandConfig):
    """Standard command configuration with no additional fields."""
    pass

class IRCommandConfig(BaseCommandConfig):
    """Command configuration for IR-controlled devices."""
    location: str = Field(..., description="IR blaster location identifier")
    rom_position: str = Field(..., description="ROM position for the IR code")

class BroadlinkCommandConfig(BaseCommandConfig):
    """Command configuration for Broadlink devices."""
    rf_code: str = Field(..., description="Base64-encoded RF code to transmit")

# Device-specific parameter models
class RevoxA77ReelToReelParams(BaseModel):
    """Parameters specific to Revox A77 Reel-to-Reel device."""
    sequence_delay: int = Field(5, description="Delay between sequence steps in seconds")

# Base device configuration model
class BaseDeviceConfig(BaseModel):
    """Base schema for device configuration."""
    device_id: str
    device_name: str
    device_class: str
    mqtt_progress_topic: str = ""

# Device-specific configuration models
class WirenboardIRDeviceConfig(BaseDeviceConfig):
    """Configuration for Wirenboard IR devices."""
    commands: Dict[str, IRCommandConfig]

class RevoxA77ReelToReelConfig(BaseDeviceConfig):
    """Configuration for Revox A77 Reel-to-Reel device."""
    commands: Dict[str, IRCommandConfig]
    reel_to_reel: RevoxA77ReelToReelParams

class BroadlinkKitchenHoodConfig(BaseDeviceConfig):
    """Configuration for Broadlink kitchen hood device."""
    commands: Dict[str, StandardCommandConfig]
    broadlink: BroadlinkConfig
    rf_codes: Dict[str, Dict[str, str]] = Field(
        ...,
        description="RF codes mapped by category (light, speed) and state"
    )

class LgTvDeviceConfig(BaseDeviceConfig):
    """Configuration for LG TV device."""
    commands: Dict[str, StandardCommandConfig]
    tv: LgTvConfig

class AppleTVDeviceConfig(BaseDeviceConfig):
    """Configuration for Apple TV device."""
    commands: Dict[str, StandardCommandConfig]
    apple_tv: AppleTVConfig

class EmotivaXMC2DeviceConfig(BaseDeviceConfig):
    """Configuration for Emotiva XMC2 device."""
    commands: Dict[str, StandardCommandConfig]
    emotiva: EmotivaConfig

# For backward compatibility during transition
T = TypeVar('T', bound=BaseDeviceConfig)
class DeviceConfig(BaseModel):
    """Legacy schema for device configuration with mixed command types.
    This will be deprecated once all devices are migrated to typed configs.
    """
    device_id: str
    device_name: str
    device_class: str
    mqtt_progress_topic: str = ""
    parameters: Dict[str, Any] = {}
    commands: Dict[str, Union[Dict[str, Any], BaseCommandConfig]] = {}
    
    # Device-specific configurations
    broadlink: Optional[BroadlinkConfig] = None
    tv: Optional[LgTvConfig] = None
    emotiva: Optional[EmotivaConfig] = None
    apple_tv: Optional[AppleTVConfig] = None

# The rest of the state models remain unchanged
class LastCommand(BaseModel):
    """Schema for last executed command."""
    action: str
    source: str
    timestamp: datetime
    params: Optional[Dict[str, Any]] = None

class BaseDeviceState(BaseModel):
    """Base schema for device state."""
    device_id: str
    device_name: str
    last_command: Optional[LastCommand] = None
    error: Optional[str] = None

class KitchenHoodState(BaseDeviceState):
    """Schema for kitchen hood state."""
    light: str
    speed: int
    connection_status: str

class LgTvState(BaseDeviceState):
    """Schema for LG TV state."""
    power: str
    volume: int
    mute: bool
    current_app: Optional[str]
    input_source: Optional[str]
    connected: bool
    ip_address: Optional[str]
    mac_address: Optional[str]

class WirenboardIRState(BaseDeviceState):
    """Schema for Wirenboard IR device state."""
    alias: str

class RevoxA77ReelToReelState(BaseDeviceState):
    """Schema for Revox A77 reel-to-reel state."""
    connection_status: str

class AppleTVState(BaseDeviceState):
    """Schema for Apple TV device state."""
    connected: bool = False
    power: str = "unknown"
    app: Optional[str] = None
    playback_state: Optional[str] = None
    media_type: Optional[str] = None
    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    position: Optional[int] = None
    total_time: Optional[int] = None
    volume: Optional[int] = None
    ip_address: Optional[str] = None

class DeviceState(BaseModel):
    """
    Schema for device state.
    
    @deprecated: This schema is deprecated. Use specific device state models like KitchenHoodState, LgTvState, etc.
    """
    device_id: str
    device_name: str
    state: Dict[str, Any]
    last_command: Optional[LastCommand] = None
    error: Optional[str] = None

class DeviceActionResponse(BaseModel):
    """
    Schema for device action response.
    
    @deprecated: This schema is deprecated. Use CommandResponse from app.types instead.
    """
    success: bool
    device_id: str
    action: str
    state: Dict[str, Any]
    error: Optional[str] = None
    message: str

class DeviceActionsResponse(BaseModel):
    """Schema for device actions list response."""
    device_id: str
    actions: List[Dict[str, str]]

class SystemConfig(BaseModel):
    """Schema for system configuration."""
    mqtt_broker: MQTTBrokerConfig
    web_service: Dict[str, Any]
    log_level: str
    log_file: str
    loggers: Optional[Dict[str, str]] = None
    devices: Dict[str, Dict[str, Any]]
    groups: Dict[str, str] = Field(default_factory=dict)  # Internal name -> Display name

class ErrorResponse(BaseModel):
    """Schema for error responses."""
    detail: str
    error_code: Optional[str] = None

class MQTTMessage(BaseModel):
    """Schema for MQTT messages."""
    topic: str = Field(
        ..., 
        description="MQTT topic to publish the message to"
    )
    payload: Optional[Union[str, int, float, dict, list, bool]] = Field(
        default=None,
        description="Message payload to publish. Can be string, number, boolean, object, or array. If not provided, defaults to 1."
    )
    qos: int = Field(
        default=0, 
        description="Quality of Service level (0, 1, or 2)",
        ge=0,
        le=2
    )
    retain: bool = Field(
        default=False, 
        description="Whether to retain the message on the broker"
    )
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "topic": "/devices/light/set",
                    "payload": "on",
                    "qos": 1,
                    "retain": False
                },
                {
                    "topic": "/devices/thermostat/set_temp",
                    "payload": 22.5,
                    "qos": 1,
                    "retain": True
                },
                {
                    "topic": "/devices/tv/command",
                    "payload": {
                        "action": "channel",
                        "value": 5
                    },
                    "qos": 0,
                    "retain": False
                }
            ]
        }

# Keep the rest of the models as they were...
class SystemInfo(BaseModel):
    """Schema for system information."""
    version: str = "1.0.0"
    mqtt_broker: MQTTBrokerConfig
    devices: List[str]

class DeviceAction(BaseModel):
    """Schema for device action requests."""
    action: str = Field(..., description="Action to execute on the device")
    params: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional parameters for the action"
    )
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "action": "power_on",
                    "params": None
                },
                {
                    "action": "set_volume",
                    "params": {
                        "volume": 50
                    }
                }
            ]
        }

class ServiceInfo(BaseModel):
    """Schema for service information."""
    service: str
    version: str
    status: str

class ReloadResponse(BaseModel):
    """Schema for system reload response."""
    status: str
    message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)

class MQTTPublishResponse(BaseModel):
    """Schema for MQTT publish response."""
    success: bool
    message: str
    topic: str
    timestamp: datetime = Field(default_factory=datetime.now)
    error: Optional[str] = None

class EmotivaXMC2State(BaseDeviceState):
    """Schema for eMotiva XMC2 device state."""
    power: Optional[str] = None
    zone2_power: Optional[str] = None
    source_status: Optional[str] = None
    video_input: Optional[str] = None
    audio_input: Optional[str] = None
    volume: Optional[int] = None
    mute: Optional[bool] = None
    audio_mode: Optional[str] = None
    audio_bitstream: Optional[str] = None
    connected: bool = False
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None
    startup_complete: bool = False
    notifications: bool = False

class Group(BaseModel):
    """Schema for a function group."""
    id: str
    name: str

class ActionGroup(BaseModel):
    """Schema for a group of actions."""
    group_id: str
    group_name: str
    actions: List[Dict[str, Any]]  # Reusing existing action representations
    status: str = "ok"  # Can be "ok" or "no_actions"

class GroupedActionsResponse(BaseModel):
    """Schema for API responses that return actions grouped by function."""
    device_id: str
    groups: List[ActionGroup]
    default_included: bool = False  # Whether the default group is included in the response

class GroupActionsResponse(BaseModel):
    """Schema for API responses that return actions for a specific group with status information."""
    device_id: str
    group_id: str
    group_name: Optional[str] = None
    status: str  # "ok", "no_actions", "invalid_group", "unknown_group"
    message: Optional[str] = None
    actions: List[Dict[str, Any]] = Field(default_factory=list)

# Keep other parameter models
class MoveCursorParams(BaseModel):
    """Parameters for move_cursor action."""
    x: int = Field(..., description="X coordinate (horizontal position)")
    y: int = Field(..., description="Y coordinate (vertical position)")
    drag: bool = Field(False, description="If True, perform drag operation")

class MoveCursorRelativeParams(BaseModel):
    """Parameters for move_cursor_relative action."""
    dx: int = Field(..., description="Delta X (horizontal movement)")
    dy: int = Field(..., description="Delta Y (vertical movement)")
    drag: bool = Field(False, description="If True, perform drag operation")

class ClickParams(BaseModel):
    """Parameters for click action."""
    x: int = Field(..., description="X coordinate (horizontal position)")
    y: int = Field(..., description="Y coordinate (vertical position)")

class LaunchAppParams(BaseModel):
    """Parameters for launch_app action."""
    app_name: str = Field(..., description="Name or ID of the app to launch. Can be a partial name which will be matched against available apps.")

class SetVolumeParams(BaseModel):
    """Parameters for set_volume action."""
    volume: int = Field(..., description="Volume level to set (typically 0-100)")

class SetMuteParams(BaseModel):
    """Parameters for set_mute action."""
    mute: bool = Field(..., description="Whether to mute (true) or unmute (false)")

class SetInputSourceParams(BaseModel):
    """Parameters for set_input_source action."""
    input_source: str = Field(..., description="Name or ID of the input source to select. Can be a partial name which will be matched against available sources.")

class SendActionParams(BaseModel):
    """Parameters for send_action action."""
    command: str = Field(..., description="Remote control command to send (e.g. 'up', 'down', 'ok', 'menu', 'play', 'pause', etc.)")

class WakeOnLanParams(BaseModel):
    """Parameters for wake_on_lan action."""
    mac_address: Optional[str] = Field(None, description="MAC address to send WOL packet to. If not provided, the device's configured MAC will be used.")
    ip_address: Optional[str] = Field(None, description="IP address to send WOL packet to. Defaults to broadcast (255.255.255.255)")
    port: int = Field(9, description="UDP port to send the WOL packet to")

class PowerOnParams(BaseModel):
    """Parameters for power_on action."""
    force: bool = Field(False, description="Whether to force power on even if already on")

class PowerOffParams(BaseModel):
    """Parameters for power_off action."""
    force: bool = Field(False, description="Whether to force power off even if already off")
    delay: Optional[int] = Field(None, description="Optional delay in seconds before powering off")

class TvActionType(str, Enum):
    POWER_ON = "power_on"
    POWER_OFF = "power_off"
    SET_VOLUME = "set_volume"
    SET_MUTE = "set_mute"
    LAUNCH_APP = "launch_app"
    SET_INPUT_SOURCE = "set_input_source"
    SEND_ACTION = "send_action"
    MOVE_CURSOR = "move_cursor"
    MOVE_CURSOR_RELATIVE = "move_cursor_relative"
    CLICK = "click"
    WAKE_ON_LAN = "wake_on_lan"
