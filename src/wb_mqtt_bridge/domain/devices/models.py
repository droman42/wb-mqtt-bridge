from typing import Dict, Any, List, Optional, Union, Set
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
import json

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
    power: str = "off"  # Standardized power state: "on" or "off" (default)
    
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
                json.dumps(state)
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
            
    def validate_field_serializable(self, field_name: str, value: Any) -> tuple[bool, Optional[str]]:
        """
        Validate that a specific field value is JSON serializable.
        
        Args:
            field_name: The name of the field to validate
            value: The value to validate
            
        Returns:
            tuple[bool, Optional[str]]: (is_valid, error_message)
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
    
    def validate_serializable(self) -> tuple[bool, List[str]]:
        """
        Validate that all fields in the state are JSON serializable.
        
        Returns:
            tuple[bool, List[str]]: (is_valid, error_messages)
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
    volume: Optional[int] = None
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
    """
    Schema for Auralic device state.
    
    The power state can have the following values:
    - "on": Device is powered on and operational
    - "off": Device is in standby mode (UPnP control) or deep sleep mode (IR control)
    
    When the device is in deep sleep mode, connected will be False and power will be "off".
    """
    volume: int = 0
    mute: bool = False
    source: Optional[str] = None
    connected: bool = False
    ip_address: Optional[str] = None
    track_title: Optional[str] = None
    track_artist: Optional[str] = None
    track_album: Optional[str] = None
    transport_state: Optional[str] = None  # Playing, Paused, Stopped, Buffering, etc.
    deep_sleep: bool = False  # True when device is in deep sleep mode (true power off)
    message: Optional[str] = None  # User-friendly message about current state
    warning: Optional[str] = None  # Warning message if relevant
    
    # Override model_dump to ensure all fields are properly serialized
    def model_dump(self, **kwargs) -> Dict[str, Any]:
        """
        Generate a dictionary representation of AuralicDeviceState with complete field serialization.
        
        This override ensures that all AuralicDeviceState fields are properly included in
        the serialized state, addressing a serialization issue where some fields might
        be missing from the database record.
        
        Returns:
            Dict[str, Any]: Dictionary representation of the state.
        """
        # Get basic serialization from parent class
        data = super().model_dump(**kwargs)
        
        # Explicitly ensure all fields are included in the serialized output
        # This is the key fix - explicitly listing all fields ensures they're all included
        data.update({
            "device_id": self.device_id,
            "device_name": self.device_name,
            "volume": self.volume,
            "mute": self.mute,
            "source": self.source,
            "connected": self.connected,
            "ip_address": self.ip_address,
            "track_title": self.track_title,
            "track_artist": self.track_artist,
            "track_album": self.track_album,
            "transport_state": self.transport_state,
            "deep_sleep": self.deep_sleep,
            "message": self.message,
            "warning": self.warning
        })
        
        # Include error and last_command fields from parent state
        if hasattr(self, "error") and self.error is not None:
            data["error"] = self.error
            
        if hasattr(self, "last_command") and self.last_command is not None:
            if hasattr(self.last_command, "model_dump"):
                data["last_command"] = self.last_command.model_dump()
            else:
                data["last_command"] = self.last_command
        
        return data

class EmotivaXMC2State(BaseDeviceState):
    """Schema for eMotiva XMC2 device state."""
    zone2_power: Optional[str] = None
    input_source: Optional[str] = None
    video_input: Optional[str] = None
    audio_input: Optional[str] = None
    volume: Optional[int] = None
    mute: Optional[bool] = None
    zone2_volume: Optional[int] = None
    zone2_mute: Optional[bool] = None
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
        zone2_power which might be enums or special types.
        
        Returns:
            Dict[str, Any]: Dictionary representation of the state.
        """
        # Get basic serialization from parent class
        data = super().model_dump(**kwargs)
        
        # Special handling for zone2_power that might be enum
        if self.zone2_power and not isinstance(self.zone2_power, str):
            data["zone2_power"] = str(self.zone2_power)
        
        return data

# Action parameter models for commands
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

class EmotivaVolumeParams(BaseModel):
    """Parameters for Emotiva set_volume action."""
    level: float = Field(..., description="Volume level to set in dB (-96.0 to 0.0)")
    zone: int = Field(1, description="Zone ID: 1 for main zone, 2 for zone2")

class EmotivaMuteParams(BaseModel):
    """Parameters for Emotiva mute_toggle action."""
    zone: int = Field(1, description="Zone ID: 1 for main zone, 2 for zone2")

class EmotivaPowerParams(BaseModel):
    """Parameters for Emotiva power_on and power_off actions."""
    zone: int = Field(1, description="Zone ID: 1 for main zone, 2 for zone2")

class EmotivaInputParams(BaseModel):
    """Parameters for Emotiva set_input action."""
    input: str = Field(..., description="Input source name (e.g., hdmi1, hdmi2, optical1)")

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