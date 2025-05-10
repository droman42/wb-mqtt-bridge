from typing import Dict, Any, List, Optional, Union, Literal, Type, TypeVar, Generic, Set, Tuple
from pydantic import BaseModel, Field, validator
from datetime import datetime
from enum import Enum
import os
from typing_extensions import Protocol
import json

# NOTE: This module is transitioning away from using 'device_class' in device configurations.
# The proper way to specify the device class is to use the 'class' field in the system configuration.
# The 'device_class' field in device configurations is deprecated and will be removed in a future version.

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
    device_code: str
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

class AuralicConfig(BaseModel):
    """Configuration for Auralic device."""
    ip_address: str
    update_interval: int = 10  # seconds
    discovery_mode: bool = False
    device_url: Optional[str] = None

class AuralicDeviceConfig(BaseDeviceConfig):
    """Configuration for Auralic device."""
    commands: Dict[str, StandardCommandConfig]
    auralic: AuralicConfig

# The rest of the state models remain unchanged
class LastCommand(BaseModel):
    """Schema for last executed command."""
    action: str
    source: str
    timestamp: datetime
    params: Optional[Dict[str, Any]] = None
    
    def model_dump(
        self,
        *,
        mode: str = "python",
        include: Optional[Union[Set[str], Dict[str, Any]]] = None,
        exclude: Optional[Union[Set[str], Dict[str, Any]]] = None,
        by_alias: bool = False,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
        round_trip: bool = False,
        warnings: bool = True,
    ) -> Dict[str, Any]:
        """
        Generate a dictionary representation of the model, optionally specifying which fields to include or exclude.
        Compatible with Pydantic v2's model_dump method with fallback to dict() for v1.
        
        Returns:
            Dict[str, Any]: Dictionary with the model's data.
        """
        # Get the basic dict representation
        data = {
            "action": self.action,
            "source": self.source,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "params": self.params
        }
        
        # Handle exclusions if needed
        if exclude:
            for field in exclude:
                if isinstance(field, str) and field in data:
                    data.pop(field)
        
        # Handle exclusion of None values
        if exclude_none:
            data = {k: v for k, v in data.items() if v is not None}
            
        return data
        
    def dict(self, **kwargs) -> Dict[str, Any]:
        """Backwards compatibility method for Pydantic v1."""
        return self.model_dump(**kwargs)

class BaseDeviceState(BaseModel):
    """Base schema for device state."""
    device_id: str
    device_name: str
    last_command: Optional[LastCommand] = None
    error: Optional[str] = None
    
    def model_dump(
        self,
        *,
        mode: str = "python",
        include: Optional[Union[Set[str], Dict[str, Any]]] = None,
        exclude: Optional[Union[Set[str], Dict[str, Any]]] = None,
        by_alias: bool = False,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
        round_trip: bool = False,
        warnings: bool = True,
    ) -> Dict[str, Any]:
        """
        Generate a dictionary representation of the model, optionally specifying which fields to include or exclude.
        Compatible with Pydantic v2's model_dump method.
        
        This method ensures proper serialization of all device state objects, including nested objects like LastCommand.
        All derived device state classes inherit this method, ensuring consistent serialization behavior.
        
        Returns:
            Dict[str, Any]: Dictionary with the model's data.
        """
        # Create base dictionary with class attributes
        data = {}
        
        # Get class fields 
        for field_name, field_value in self.__dict__.items():
            # Handle nested objects (like LastCommand)
            if hasattr(field_value, 'model_dump'):
                data[field_name] = field_value.model_dump(
                    include=include,
                    exclude=exclude,
                    by_alias=by_alias,
                    exclude_unset=exclude_unset,
                    exclude_defaults=exclude_defaults,
                    exclude_none=exclude_none
                )
            elif isinstance(field_value, datetime):
                # Handle datetime objects specially
                data[field_name] = field_value.isoformat()
            elif isinstance(field_value, Enum):
                # Handle Enum objects
                data[field_name] = field_value.value
            else:
                # Regular values
                data[field_name] = field_value
        
        # Handle exclusions
        if exclude:
            for field in exclude:
                if isinstance(field, str) and field in data:
                    data.pop(field)
        
        # Handle exclusions of None
        if exclude_none:
            data = {k: v for k, v in data.items() if v is not None}
        
        return data
    
    def dict(self, **kwargs) -> Dict[str, Any]:
        """Backwards compatibility method for Pydantic v1."""
        return self.model_dump(**kwargs)
        
    @classmethod
    def ensure_json_serializable(cls, state: 'BaseDeviceState') -> Dict[str, Any]:
        """
        Utility method to ensure any device state is converted to a JSON-serializable dictionary
        with enhanced error reporting.
        
        This is a safer alternative that tries multiple approaches and provides detailed
        error information if serialization fails.
        
        Args:
            state: The device state to convert to a JSON-serializable dictionary
            
        Returns:
            Dict[str, Any]: A JSON-serializable dictionary
            
        Raises:
            ValueError: If the state cannot be serialized after all attempts
        """
        errors = []
        
        # Try different serialization strategies
        try:
            # 1. Try model_dump first (Pydantic v2)
            if hasattr(state, 'model_dump'):
                try:
                    return state.model_dump()
                except Exception as e:
                    errors.append(f"model_dump() failed: {str(e)}")
            
            # 2. Try dict() (Pydantic v1)
            if hasattr(state, 'dict'):
                try:
                    return state.dict()
                except Exception as e:
                    errors.append(f"dict() failed: {str(e)}")
            
            # 3. Try direct serialization test
            try:
                # Test with json.dumps
                json_str = json.dumps(state)
                # If we get here, it's directly serializable but probably not what we want
                errors.append("Direct serialization succeeded but is not recommended")
            except Exception as e:
                errors.append(f"Direct serialization failed: {str(e)}")
            
            # 4. Try manual conversion to dict
            try:
                return {
                    field_name: (field_value.model_dump() if hasattr(field_value, 'model_dump') else 
                                 field_value.dict() if hasattr(field_value, 'dict') else
                                 field_value.isoformat() if isinstance(field_value, datetime) else
                                 field_value.value if isinstance(field_value, Enum) else
                                 str(field_value) if hasattr(field_value, '__dict__') else
                                 field_value)
                    for field_name, field_value in state.__dict__.items()
                }
            except Exception as e:
                errors.append(f"Manual conversion failed: {str(e)}")
            
            # If we get here, all attempts failed
            problematic_fields = []
            for field_name, field_value in state.__dict__.items():
                try:
                    json.dumps({field_name: field_value})
                except Exception:
                    problematic_fields.append(f"{field_name} ({type(field_value).__name__})")
            
            if problematic_fields:
                error_message = f"Serialization failed. Problematic fields: {', '.join(problematic_fields)}"
            else:
                error_message = f"Serialization failed for unknown reasons. Errors: {', '.join(errors)}"
                
            raise ValueError(error_message)
            
        except Exception as e:
            # Final fallback - convert everything to strings
            try:
                return {
                    field_name: str(field_value) 
                    for field_name, field_value in state.__dict__.items()
                }
            except Exception:
                raise ValueError(f"All serialization attempts failed: {str(e)}")
                
        # This should never happen due to the exception handling above
        raise ValueError("Failed to serialize state after all attempts")
        
    @staticmethod
    def is_json_serializable(value: Any) -> bool:
        """
        Check if a value is directly JSON serializable.
        
        Args:
            value: The value to check
            
        Returns:
            bool: True if the value is directly JSON serializable, False otherwise
        """
        try:
            json.dumps(value)
            return True
        except (TypeError, OverflowError):
            return False
            
    def validate_field_serializable(self, field_name: str, value: Any) -> Tuple[bool, Optional[str]]:
        """
        Validate that a specific field value is JSON serializable.
        
        Args:
            field_name: The name of the field to validate
            value: The value to validate
            
        Returns:
            Tuple[bool, Optional[str]]: (is_valid, error_message)
            Where error_message is None if the value is serializable
        """
        # Handle simple primitive types that are always serializable
        if value is None or isinstance(value, (str, int, float, bool)):
            return True, None
            
        # Handle collections with simple validation
        if isinstance(value, (list, tuple)):
            for i, item in enumerate(value):
                is_valid, error = self.validate_field_serializable(f"{field_name}[{i}]", item)
                if not is_valid:
                    return False, error
            return True, None
            
        if isinstance(value, dict):
            for k, v in value.items():
                is_valid, error = self.validate_field_serializable(f"{field_name}.{k}", v)
                if not is_valid:
                    return False, error
            return True, None
            
        # Handle Pydantic models
        if hasattr(value, 'model_dump') or hasattr(value, 'dict'):
            return True, None
            
        # Handle special types we know how to serialize
        if isinstance(value, (datetime, Enum)):
            return True, None
            
        # For other types, check direct JSON serialization
        if BaseDeviceState.is_json_serializable(value):
            return True, None
            
        # If we get here, the value is not JSON serializable
        return False, f"Field '{field_name}' with type '{type(value).__name__}' is not JSON serializable"
    
    def validate_serializable(self) -> Tuple[bool, List[str]]:
        """
        Validate that all fields in the state are JSON serializable.
        
        Returns:
            Tuple[bool, List[str]]: (is_valid, error_messages)
            Where is_valid is True if all fields are serializable, and error_messages
            contains a list of error messages for non-serializable fields.
        """
        errors = []
        for field_name, field_value in self.__dict__.items():
            is_valid, error = self.validate_field_serializable(field_name, field_value)
            if not is_valid and error:
                errors.append(error)
                
        return len(errors) == 0, errors

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
    
    # Override model_dump to handle any special cases specific to AppleTVState
    def model_dump(self, **kwargs) -> Dict[str, Any]:
        """
        Generate a dictionary representation of AppleTVState with special handling.
        
        This override adds specific handling for AppleTVState fields like
        playback_state and media_type which might come from enums in pyatv library.
        
        Returns:
            Dict[str, Any]: Dictionary representation of the state.
        """
        # Get basic serialization from parent class
        data = super().model_dump(**kwargs)
        
        # Ensure position and total_time are properly serialized as integers or None
        if self.position is not None:
            try:
                data["position"] = int(self.position)
            except (ValueError, TypeError):
                data["position"] = None
                
        if self.total_time is not None:
            try:
                data["total_time"] = int(self.total_time)
            except (ValueError, TypeError):
                data["total_time"] = None
                
        # Ensure playback_state and media_type are strings
        if self.playback_state and not isinstance(self.playback_state, str):
            data["playback_state"] = str(self.playback_state)
            
        if self.media_type and not isinstance(self.media_type, str):
            data["media_type"] = str(self.media_type)
        
        return data

class AuralicDeviceState(BaseDeviceState):
    """Schema for Auralic device state."""
    power: str = "unknown"  # on/off/unknown
    volume: int = 0
    mute: bool = False
    source: Optional[str] = None
    connected: bool = False
    ip_address: Optional[str] = None
    track_title: Optional[str] = None
    track_artist: Optional[str] = None
    track_album: Optional[str] = None
    transport_state: Optional[str] = None  # Playing, Paused, Stopped, Buffering, etc.

class PersistenceConfig(BaseModel):
    """Configuration for the persistence layer."""
    db_path: str = Field(default="data/state_store.db", description="Path to the SQLite database file")

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
    persistence: PersistenceConfig = Field(default_factory=PersistenceConfig)

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
    
    # Override model_dump to handle any special cases specific to EmotivaXMC2State
    def model_dump(self, **kwargs) -> Dict[str, Any]:
        """
        Generate a dictionary representation of EmotivaXMC2State with special handling.
        
        This override adds specific handling for EmotivaXMC2State fields like
        power and zone2_power which might be enums or special types.
        
        Returns:
            Dict[str, Any]: Dictionary representation of the state.
        """
        # Get basic serialization from parent class
        data = super().model_dump(**kwargs)
        
        # Special handling for power states that might be enums
        if self.power and not isinstance(self.power, str):
            data["power"] = str(self.power)
            
        if self.zone2_power and not isinstance(self.zone2_power, str):
            data["zone2_power"] = str(self.zone2_power)
        
        return data

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
