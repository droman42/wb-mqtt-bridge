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

class DeviceConfig(BaseModel):
    """Schema for device configuration."""
    device_id: str
    device_name: str
    device_class: str
    mqtt_topics: List[str] = []
    parameters: Dict[str, Any] = {}
    commands: Dict[str, Any] = {}
    broadlink: Optional[Dict[str, Any]] = None
    tv: Optional[Dict[str, Any]] = None

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
    last_command: str
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