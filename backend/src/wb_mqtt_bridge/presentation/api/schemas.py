from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field
from datetime import datetime
from wb_mqtt_bridge.__version__ import __version__

# Import configuration models for API responses
from wb_mqtt_bridge.infrastructure.config.models import (
    SystemConfig,
    BaseDeviceConfig,
)

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

class DeviceActionsResponse(BaseModel):
    """Schema for device actions list response."""
    device_id: str
    actions: List[Dict[str, str]]

class SystemInfo(BaseModel):
    """Schema for system information."""
    version: str = __version__
    mqtt_broker: Dict[str, Any]  # Will be populated from MQTTBrokerConfig
    devices: List[str] = Field(default_factory=list, description="List of available devices")
    scenarios: List[str] = Field(default_factory=list, description="List of available scenarios")
    rooms: List[str] = Field(default_factory=list, description="List of available rooms")

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

class MQTTPublishResponse(BaseModel):
    """Schema for MQTT publish response."""
    success: bool
    message: str
    topic: str
    timestamp: datetime = Field(default_factory=datetime.now)
    error: Optional[str] = None

class ErrorResponse(BaseModel):
    """Schema for error responses."""
    detail: str
    error_code: Optional[str] = None

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