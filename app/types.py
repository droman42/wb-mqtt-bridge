from typing import Dict, Any, List, Optional, TypeVar, Generic, Union, Callable, Awaitable
from typing_extensions import TypedDict
from app.schemas import BaseDeviceState, BaseCommandConfig

# Define state type variable for generic typing
StateT = TypeVar('StateT', bound=BaseDeviceState)

# Standard return type for individual handlers
class CommandResult(TypedDict, total=False):
    """Return type for device action handlers."""
    success: bool
    message: Optional[str]
    error: Optional[str]
    mqtt_command: Optional[Dict[str, Any]]
    # Other optional fields

# Standard return type for execute_action
# Split into required and optional components
class CommandResponseRequired(TypedDict, Generic[StateT]):
    """Required fields for CommandResponse."""
    success: bool
    device_id: str
    action: str
    state: StateT  # Now properly typed with specific state class

class CommandResponseOptional(TypedDict, total=False):
    """Optional fields for CommandResponse."""
    error: Optional[str]
    mqtt_command: Optional[Dict[str, Any]]

class CommandResponse(CommandResponseRequired[StateT], CommandResponseOptional, Generic[StateT]):
    """Return type for BaseDevice.execute_action.
    
    This combines required fields (success, device_id, action, state)
    with optional fields (error, mqtt_command) to match FastAPI validation
    requirements while maintaining proper typing.
    """
    pass

# Type definition for action handlers
ActionHandler = Callable[[BaseCommandConfig, Dict[str, Any]], Awaitable[CommandResult]]