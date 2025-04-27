from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
import os

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

class DeviceConfig(BaseModel):
    """Schema for device configuration."""
    device_id: str
    device_name: str
    device_class: str
    mqtt_progress_topic: str = ""
    parameters: Dict[str, Any] = {}
    commands: Dict[str, Any] = {}
    broadlink: Optional[BroadlinkConfig] = None
    tv: Optional[LgTvConfig] = None
    emotiva: Optional[EmotivaConfig] = None
    apple_tv: Optional[AppleTVConfig] = None

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

class ExampleDeviceState(BaseDeviceState):
    """Schema for example device state."""
    power: str
    last_reading: Optional[Dict[str, Any]]
    update_interval: int
    threshold: float

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
    """Schema for device state."""
    device_id: str
    device_name: str
    state: Dict[str, Any]
    last_command: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class DeviceActionResponse(BaseModel):
    """Schema for device action response."""
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
    topic: str
    payload: Any
    qos: int = 0
    retain: bool = False

class SystemInfo(BaseModel):
    """Schema for system information."""
    version: str = "1.0.0"
    mqtt_broker: MQTTBrokerConfig
    devices: List[str]

class DeviceAction(BaseModel):
    """Schema for device action requests."""
    action: str = Field(..., description="Action to execute on the device")
    params: Optional[Dict[str, Any]] = Field(
        None, 
        description="Parameters for the action. Structure depends on the action type."
    )
    
    # Example in the model description
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "action": "move_cursor",
                    "params": {
                        "x": 500,
                        "y": 300,
                        "drag": False
                    }
                },
                {
                    "action": "move_cursor_relative",
                    "params": {
                        "dx": 100,
                        "dy": -50,
                        "drag": True
                    }
                },
                {
                    "action": "click",
                    "params": {
                        "x": 500,
                        "y": 300
                    }
                },
                {
                    "action": "launch_app",
                    "params": {
                        "app_name": "Netflix"
                    }
                },
                {
                    "action": "set_volume",
                    "params": {
                        "volume": 30
                    }
                },
                {
                    "action": "set_mute",
                    "params": {
                        "mute": True
                    }
                },
                {
                    "action": "set_input_source",
                    "params": {
                        "input_source": "HDMI 1"
                    }
                },
                {
                    "action": "send_action",
                    "params": {
                        "command": "up"
                    }
                },
                {
                    "action": "power_on",
                    "params": {}
                },
                {
                    "action": "power_off",
                    "params": {}
                },
                {
                    "action": "wake_on_lan",
                    "params": {}
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

# Mouse control action parameter schemas
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

# TV control action parameter schemas
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
    # No parameters required for wake_on_lan action, but defined for consistency
    pass

class PowerOnParams(BaseModel):
    """Parameters for power_on action."""
    # No parameters required for power_on action, but defined for consistency
    pass

class PowerOffParams(BaseModel):
    """Parameters for power_off action."""
    # No parameters required for power_off action, but defined for consistency
    pass

# Enum for TV actions
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

# Define Union type for action parameters
ActionParams = Union[
    Dict[str, Any],  # Generic parameters
    MoveCursorParams,
    MoveCursorRelativeParams,
    ClickParams,
    LaunchAppParams,
    SetVolumeParams,
    SetMuteParams,
    SetInputSourceParams,
    SendActionParams,
    WakeOnLanParams,
    PowerOnParams,
    PowerOffParams
]
