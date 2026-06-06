from enum import Enum
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from wb_mqtt_bridge.__version__ import __version__


# ---- /config/system response DTOs ------------------------------------------
# Presentation owns its wire shape — these mirror the infrastructure config models
# (MQTTBrokerConfig, PersistenceConfig, MaintenanceConfig, SystemConfig) but decouple
# the API from infra. `from_attributes=True` lets us build them from the infra
# instances via `SystemConfigResponse.model_validate(infra_system_config)`.
# Half of the "system-router cleanup" hexagonal residual (action_plan §5.1); the
# other half (the /reload application-service extraction) is still HW-gated.

class MQTTBrokerConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    host: str
    port: int
    client_id: str
    auth: Optional[Dict[str, str]] = None
    keepalive: int = 60


class PersistenceConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    db_path: str = Field(default="data/state_store.db")


class MaintenanceConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    duration: int
    topic: str


class SystemConfigResponse(BaseModel):
    """API response shape for ``GET /config/system`` — independent of the infra
    ``SystemConfig`` so the wire contract isn't a leak of internal config layout."""
    model_config = ConfigDict(from_attributes=True)
    service_name: str = Field(default="MQTT Web Service")
    mqtt_broker: MQTTBrokerConfigResponse
    web_service: Dict[str, Any]
    log_level: str
    log_file: str
    loggers: Optional[Dict[str, str]] = None
    devices: Optional[Dict[str, Dict[str, Any]]] = None
    persistence: PersistenceConfigResponse = Field(default_factory=PersistenceConfigResponse)
    maintenance: Optional[MaintenanceConfigResponse] = None
    device_directory: str = Field(default="devices")


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


# ---- /devices/{id}/canonical request/response DTOs ------------------------
# §P3.7 voice-integration slice #15. Voice (Irene) speaks canonical
# (capability, action, params); the bridge resolves canonical -> native via the
# capability registry (class -> profile -> per-device override; see #14 + the
# capability-profile mechanism). Response is synchronous-with-timeout: the bridge
# waits up to ~500ms for the device's value-topic echo before returning.


class CanonicalActionRequest(BaseModel):
    """Voice-side request to invoke a canonical (capability, action, params) tuple."""
    capability: str = Field(..., description="Canonical capability name (e.g. 'power', 'volume', 'cover').")
    action: str = Field(..., description="Action within the capability (e.g. 'on', 'set', 'up').")
    params: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Canonical parameter names (renamed to native via the capability's param_map).",
    )


class CanonicalErrorCode(str, Enum):
    """Structured error codes for the canonical endpoint. HTTP status mirrors these
    (see /devices/{id}/canonical responses): 404 for the three 'not supported' codes,
    400 for param_invalid, 503 for device_unreachable, 500 for internal_error."""
    DEVICE_NOT_FOUND = "device_not_found"
    CAPABILITY_NOT_SUPPORTED = "capability_not_supported"
    ACTION_NOT_SUPPORTED = "action_not_supported"
    PARAM_INVALID = "param_invalid"
    DEVICE_UNREACHABLE = "device_unreachable"
    INTERNAL_ERROR = "internal_error"


class CanonicalError(BaseModel):
    """Error envelope. `field` + `reason` populated for param_invalid; both optional."""
    code: CanonicalErrorCode
    message: str
    field: Optional[str] = None
    reason: Optional[str] = None


class CanonicalActionResponse(BaseModel):
    """Response envelope for /devices/{id}/canonical. On success, `state` carries the
    post-action device state (after the value-topic echo within the 500ms window)."""
    success: bool
    device_id: str
    capability: str
    action: str
    state: Optional[Dict[str, Any]] = None
    error: Optional[CanonicalError] = None

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