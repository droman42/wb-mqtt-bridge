from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

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

class LgTvConfig(BaseModel):
    """Schema for LG WebOS TV device configuration."""
    ip_address: str
    mac_address: Optional[str] = None
    secure: bool = True
    client_key: Optional[str] = None
    timeout: int = 5
    reconnect_interval: Optional[int] = None

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
    last_command: str = ""
    connection_status: str

class ExampleDeviceState(BaseDeviceState):
    """Schema for example device state."""
    power: str
    last_reading: Optional[Dict[str, Any]]
    update_interval: int
    threshold: float

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
    action: str
    params: Optional[Dict[str, Any]] = None

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
