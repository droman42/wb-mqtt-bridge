# Strong Typing Implementation Plan

This document outlines the implementation details for standardizing strong typing across each device class.

## BaseDevice

After a thorough review of the BaseDevice implementation, the following changes are required to standardize typing and ensure consistency:

### 1. Define Standard Type Definitions

Create a dedicated module `app/types.py` with standard type definitions:

```python
from typing import Dict, Any, List, Optional, TypeVar, Generic, Union, Callable, Awaitable, TypedDict
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
class CommandResponse(TypedDict, Generic[StateT]):
    """Return type for BaseDevice.execute_action."""
    success: bool
    device_id: str
    action: str
    state: StateT
    error: Optional[str]
    mqtt_command: Optional[Dict[str, Any]]

# Type definition for action handlers
ActionHandler = Callable[[BaseCommandConfig, Dict[str, Any]], Awaitable[CommandResult]]
```

### 2. Update BaseDevice Class Type Annotations

```python
class BaseDevice(ABC, Generic[StateT]):
    """Base class for all device implementations."""
    
    def __init__(self, config: BaseDeviceConfig, mqtt_client: Optional["MQTTClient"] = None):
        # Update type annotation for handlers dictionary
        self._action_handlers: Dict[str, ActionHandler] = {}
```

### 3. Add Standard Handler Registration Method

Add a method to be overridden by subclasses:

```python
def _register_handlers(self) -> None:
    """
    Register all action handlers for this device.
    
    This method should be overridden by all device subclasses to register
    their action handlers in a standardized way.
    
    Example:
        self._action_handlers.update({
            'power_on': self.handle_power_on,
            'power_off': self.handle_power_off,
        })
    """
    pass  # To be implemented by subclasses
```

Update the `__init__` method to call this:

```python
def __init__(self, config: BaseDeviceConfig, mqtt_client: Optional["MQTTClient"] = None):
    # Existing initialization code...
    
    # Register action handlers
    self._register_handlers()
    
    # Build action group index
    self._build_action_groups_index()
```

### 4. Add Standard Result Creation Method

Add a utility method to create standardized results:

```python
def create_command_result(
    self, 
    success: bool, 
    message: Optional[str] = None, 
    error: Optional[str] = None, 
    **extra_fields
) -> CommandResult:
    """
    Create a standardized CommandResult.
    
    Args:
        success: Whether the command was successful
        message: Optional success message
        error: Optional error message (only if success is False)
        **extra_fields: Additional fields to include in the result
        
    Returns:
        CommandResult: A standardized result dictionary
    """
    result: CommandResult = {
        "success": success
    }
    
    if message:
        result["message"] = message
        
    if not success and error:
        result["error"] = error
        
    # Add any additional fields
    for key, value in extra_fields.items():
        result[key] = value
        
    return result
```

### 5. Update Handler Method Signature in _execute_single_action

Update the handler execution to match the new signature and return type:

```python
async def _execute_single_action(
    self, 
    action_name: str, 
    cmd_config: BaseCommandConfig, 
    params: Dict[str, Any] = None
) -> Optional[CommandResult]:
    """
    Execute a single action based on its configuration.
    
    Args:
        action_name: The name of the action to execute
        cmd_config: The command configuration
        params: Optional dictionary of parameters (will be validated)
        
    Returns:
        CommandResult: The result from the handler or None if execution failed
    """
    try:
        # Get the action handler method from the instance
        handler = self._get_action_handler(action_name)
        if not handler:
            logger.warning(f"No action handler found for action: {action_name} in device {self.get_name()}")
            return self.create_command_result(
                success=False, 
                error=f"No handler found for action: {action_name}"
            )

        # Process parameters if not already provided
        if params is None:
            # Try to resolve parameters from cmd_config
            try:
                params = self._resolve_and_validate_params(cmd_config.params or [], {})
            except ValueError as e:
                # Parameter validation failed
                error_msg = f"Parameter validation failed for {action_name}: {str(e)}"
                logger.error(error_msg)
                return self.create_command_result(success=False, error=error_msg)
        
        logger.debug(f"Executing action: {action_name} with handler: {handler}, params: {params}")
        
        # Call the handler with the new parameter-based approach
        result = await handler(cmd_config=cmd_config, params=params)
        
        # Update state with information about the last command executed
        self.update_state(last_command=LastCommand(
            action=action_name,
            source="mqtt" if cmd_config.topic else "api",
            timestamp=datetime.now(),
            params=params
        ))
        
        # Return the result
        return result
            
    except Exception as e:
        error_msg = f"Error executing action {action_name}: {str(e)}"
        logger.error(error_msg)
        return self.create_command_result(success=False, error=error_msg)
```

### 6. Update execute_action Method

Update to use CommandResult and CommandResponse types:

```python
async def execute_action(
    self, 
    action: str, 
    params: Optional[Dict[str, Any]] = None
) -> CommandResponse[StateT]:
    """Execute an action identified by action name."""
    try:
        # Find the command configuration for this action
        cmd = None
        for cmd_name, command_config in self.get_available_commands().items():
            if cmd_name == action:
                cmd = command_config
                break
        
        if not cmd:
            error_msg = f"Action {action} not found in device configuration"
            return CommandResponse(
                success=False,
                device_id=self.device_id,
                action=action,
                state=self.state,
                error=error_msg
            )
        
        # Validate parameters
        validated_params = {}
        if cmd.params:
            try:
                # Validate and process parameters
                validated_params = self._resolve_and_validate_params(cmd.params, params or {})
            except ValueError as e:
                # Re-raise with more specific message
                error_msg = f"Parameter validation failed for action '{action}': {str(e)}"
                return CommandResponse(
                    success=False,
                    device_id=self.device_id,
                    action=action,
                    state=self.state,
                    error=error_msg
                )
        elif params:
            # No parameters defined in config but params were provided
            validated_params = params
        
        # Execute the action with validated parameters
        result = await self._execute_single_action(action, cmd, validated_params)
        
        # Create the response based on the result
        success = result.get("success", True) if result else False
        response = CommandResponse(
            success=success,
            device_id=self.device_id,
            action=action,
            state=self.state
        )
        
        # Add error if present in result
        if not success and result and "error" in result:
            response["error"] = result["error"]
            
        # Add mqtt_command if present in result
        if result and "mqtt_command" in result:
            response["mqtt_command"] = result["mqtt_command"]
        
        if success:
            await self.publish_progress(f"Action {action} executed successfully")
            
        return response
            
    except Exception as e:
        error_msg = f"Error executing action {action} for device {self.device_id}: {str(e)}"
        logger.error(error_msg)
        return CommandResponse(
            success=False,
            device_id=self.device_id,
            action=action,
            state=self.state,
            error=error_msg
        )
```

### 7. Add Standard Error Handling Methods

```python
def set_error(self, error_message: str) -> None:
    """
    Set an error message in the device state.
    
    Args:
        error_message: The error message to set
    """
    self.update_state(error=error_message)
    
def clear_error(self) -> None:
    """Clear any error message from the device state."""
    self.update_state(error=None)
```

### 8. Update _get_action_handler Method

Update the method with proper typing:

```python
def _get_action_handler(self, action: str) -> Optional[ActionHandler]:
    """Get the handler function for the specified action."""
    # Convert to lower case for case-insensitive lookup
    action = action.lower()
    
    # DEBUG: Log handler lookup attempt
    logger.debug(f"[{self.device_name}] Looking up handler for action: '{action}'")
    logger.debug(f"[{self.device_name}] Available handlers: {list(self._action_handlers.keys())}")
    
    # Check if we have a handler for this action
    handler = self._action_handlers.get(action)
    if handler:
        logger.debug(f"[{self.device_name}] Found direct handler for '{action}'")
        return handler
        
    # If not found, check if maybe it's in camelCase and we have a handler for snake_case
    if '_' not in action:
        # Convert camelCase to snake_case and try again
        snake_case = ''.join(['_' + c.lower() if c.isupper() else c for c in action]).lstrip('_')
        logger.debug(f"[{self.device_name}] Trying snake_case variant: '{snake_case}'")
        handler = self._action_handlers.get(snake_case)
        if handler:
            logger.debug(f"[{self.device_name}] Found handler for snake_case variant '{snake_case}'")
            return handler
    
    # DEBUG: Check if we have a method named handle_X directly
    method_name = f"handle_{action}"
    if hasattr(self, method_name) and callable(getattr(self, method_name)):
        logger.debug(f"[{self.device_name}] Found method {method_name} but it's not in _action_handlers")
            
    logger.debug(f"[{self.device_name}] No handler found for action '{action}'")
    return None
```

### 9. Implementation Steps

1. Create `app/types.py` with the type definitions
2. Update BaseDevice class with generics for state type
3. Add and update methods in BaseDevice:
   - Add `_register_handlers` method
   - Add `create_command_result` method
   - Update `_execute_single_action` method
   - Update `execute_action` method
   - Add error handling methods
   - Update parameter validation with proper return types
4. Update import statements in BaseDevice
5. Update BaseDevice docstrings and type annotations

### 10. Testing Plan

1. Create unit tests for the new methods
2. Test that existing device implementations still work with the changes
3. Create a test device that follows all the new type standards
4. Ensure backward compatibility with existing API calls and MQTT integration

## LgTv

After reviewing the LgTv implementation, the following changes are needed to align with the standardization plan:

### 1. Update Class Definition with Generic Type

```python
class LgTv(BaseDevice[LgTvState]):
    """Implementation of an LG TV controlled over the network using AsyncWebOSTV library."""
```

### 2. Update Handler Registration Method

Rename the existing method to match the standard name:

```python
def _register_handlers(self) -> None:
    """Register all action handlers for the LG TV.
    
    This method maps action names to their corresponding handler methods.
    All handlers follow the standardized signature:
    async def handle_X(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult
    """
    # Register handlers for media control actions
    self._action_handlers.update({
        'power_on': self.handle_power_on,
        'power_off': self.handle_power_off,
        'home': self.handle_home,
        # ... keep existing handler mappings ...
    })
```

And update the __init__ method to remove the direct call:
```python
def __init__(self, config: LgTvDeviceConfig, mqtt_client: Optional[MQTTClient] = None):
    # Initialize base device with config and state class
    super().__init__(config, mqtt_client)
    
    # Remove self._register_lg_tv_action_handlers() call as it will be called 
    # by BaseDevice._register_handlers() already
    
    # Rest of the initialization code...
```

### 3. Update Handler Method Signatures

All handler methods need to be updated to match the standard signature and return CommandResult instead of boolean:

```python
async def handle_power_on(
    self, 
    cmd_config: StandardCommandConfig, 
    params: Dict[str, Any]
) -> CommandResult:
    """Handle power on action.
    
    Args:
        cmd_config: Command configuration
        params: Dictionary containing optional parameters
        
    Returns:
        CommandResult: Result of the command execution
    """
    success = await self.power_on()
    return self.create_command_result(
        success=success,
        message="TV powered on successfully" if success else None,
        error="Failed to power on TV" if not success else None
    )
```

### 4. Update Helper Methods that Return Boolean

Update helper methods to use CommandResult approach or integrate with it:

```python
async def _execute_input_command(
    self,
    action_name: str, 
    button_method_name: str
) -> CommandResult:
    """Execute an input button command using InputControl.
    
    This helper method provides a consistent implementation for all button commands
    that use InputControl methods.
    
    Args:
        action_name: The name of the action (for logging and state updates)
        button_method_name: The name of the method to call on InputControl
        
    Returns:
        CommandResult: Result of the command execution
    """
    try:
        logger.info(f"Sending {action_name.upper()} button command to TV {self.get_name()}")
        
        if not self.client or not self.input_control or not self.state.connected:
            error_msg = f"Cannot send {action_name.upper()} command: Not connected or input control not available"
            logger.error(error_msg)
            self.set_error(error_msg)
            return self.create_command_result(success=False, error=error_msg)
            
        # Check if the button method exists on InputControl
        if not hasattr(self.input_control, button_method_name) or not callable(getattr(self.input_control, button_method_name)):
            error_msg = f"Button method '{button_method_name}' not found on InputControl"
            logger.error(error_msg)
            self.set_error(error_msg)
            return self.create_command_result(success=False, error=error_msg)
            
        # Call the button method on InputControl
        method = getattr(self.input_control, button_method_name)
        result = await method()
        
        if result:
            await self._update_last_command(action=action_name, source="api")
            self.clear_error()  # Clear any previous errors on success
            return self.create_command_result(
                success=True, 
                message=f"{action_name.upper()} button command executed successfully"
            )
        else:
            error_msg = f"{action_name.upper()} button command failed"
            logger.warning(error_msg)
            self.set_error(error_msg)
            return self.create_command_result(success=False, error=error_msg)
            
    except Exception as e:
        error_msg = f"Error sending {action_name.upper()} button command: {str(e)}"
        logger.error(error_msg)
        self.set_error(error_msg)
        return self.create_command_result(success=False, error=error_msg)
```

### 5. Update Media Command Execution

```python
async def _execute_media_command(
    self,
    action_name: str,
    media_method_name: str,
    state_key_to_update: Optional[str] = None,
    requires_level: bool = False,
    requires_state: bool = False,
    update_volume_after: bool = False,
    params: Optional[Dict[str, Any]] = None
) -> CommandResult:
    """Execute a media control command.
    
    Args:
        action_name: Name of the action (for logging and state updates)
        media_method_name: Name of the method to call on MediaControl
        state_key_to_update: Key in self.state to update with result
        requires_level: If True, needs a level parameter
        requires_state: If True, needs a state parameter
        update_volume_after: If True, update volume state after command
        params: Dictionary containing parameters for the command
        
    Returns:
        CommandResult: Result of the command execution
    """
    try:
        # Existing implementation...
        
        # Change return type to CommandResult
        if success:
            return self.create_command_result(
                success=True,
                message=f"{action_name} executed successfully"
            )
        else:
            return self.create_command_result(
                success=False,
                error=f"Command {action_name} failed: {result}"
            )
            
    except Exception as e:
        error_msg = f"Error executing media command {action_name}: {str(e)}"
        logger.error(error_msg)
        return self.create_command_result(success=False, error=error_msg)
```

### 6. Remove Custom execute_action Method

The LgTv class has a custom execute_action method that should be removed, as the standardized BaseDevice.execute_action will be used instead.

### 7. Implementation Steps for LgTv

1. Update imports to include the new types:
   ```python
   from app.types import CommandResult, CommandResponse, ActionHandler
   ```

2. Update class definition with generic type parameter:
   ```python
   class LgTv(BaseDevice[LgTvState]):
   ```

3. Rename `_register_lg_tv_action_handlers` to `_register_handlers`

4. Update all handler methods to match the standardized signature:
   - Change return type from `bool` to `CommandResult`
   - Add `cmd_config: StandardCommandConfig` parameter
   - Update method body to use `create_command_result`

5. Update helper methods to return `CommandResult` instead of `bool`

6. Remove the custom `execute_action` method

7. Remove the custom `_get_action_handler` method if it exists

8. Update all calls to handler methods to pass the new parameters

9. Update any code that directly calls the handlers to handle the new return type

### 8. Testing Steps for LgTv

1. Test each handler with the new signature
2. Test that MQTT command processing still works
3. Test that API calls still work
4. Test error handling with the new return types
5. Test that state updates still work correctly

## AppleTVDevice

After a thorough review of the AppleTVDevice implementation, the following changes are needed to align with the standardization plan:

### 1. Update Class Definition with Generic Type

```python
class AppleTVDevice(BaseDevice[AppleTVState]):
    """Apple TV device integration for wb-mqtt-bridge."""
```

### 2. Remove Redundant typed_config Storage

The AppleTVDevice class currently stores a duplicate of the config as `self.typed_config`. This should be removed in favor of using `self.config` directly:

```python
def __init__(self, config: AppleTVDeviceConfig, mqtt_client: Optional[MQTTClient] = None):
    # Call BaseDevice init with proper configuration
    super().__init__(config, mqtt_client)
    
    # Remove: self.typed_config = config
    
    # Get Apple TV configuration directly from the main config
    self.apple_tv_config = self.config.apple_tv
    
    # Rest of initialization...
```

### 3. Rename and Update Handler Methods

Currently, the AppleTVDevice uses non-standard handler naming, with methods like `turn_on` instead of `handle_power_on`. These should be renamed to follow the convention:

```python
# Update handler registration
def _register_handlers(self) -> None:
    """Register all action handlers for the Apple TV device."""
    self._action_handlers.update({
        "power_on": self.handle_power_on,  # Update from self.turn_on
        "power_off": self.handle_power_off,  # Update from self.turn_off
        "play": self.handle_play,  # Update from self.play
        "pause": self.handle_pause,  # Update from self.pause
        "stop": self.handle_stop,  # Update from self.stop
        "next": self.handle_next_track,  # Update from self.next_track
        "previous": self.handle_previous_track,  # Update from self.previous_track
        "set_volume": self.handle_set_volume,  # Update from self.set_volume
        "volume_up": self.handle_volume_up,  # Update from self.volume_up
        "volume_down": self.handle_volume_down,  # Update from self.volume_down
        "launch_app": self.handle_launch_app,  # Update from self.launch_app
        "refresh_status": self.handle_refresh_status,  # Update from self.refresh_status
        "menu": self.handle_menu,  # Update from self.menu
        "home": self.handle_home,  # Update from self.home
        "select": self.handle_select,  # Update from self.select
        "up": self.handle_up,  # Update from self.up
        "down": self.handle_down,  # Update from self.down
        "left": self.handle_left,  # Update from self.left
        "right": self.handle_right  # Update from self.right
    })
```

### 4. Update Handler Return Types

All the handler methods currently return boolean values but need to be updated to return CommandResult:

```python
async def handle_power_on(
    self, 
    cmd_config: StandardCommandConfig, 
    params: Dict[str, Any]
) -> CommandResult:
    """
    Turn on the Apple TV.
    
    Args:
        cmd_config: Command configuration
        params: Parameters (unused)
        
    Returns:
        CommandResult: Result of the command execution
    """
    logger.info(f"[{self.device_id}] Attempting to turn ON (wake)...")
    if await self._ensure_connected():
        try:
            await self.atv.power.turn_on()
            logger.info(f"[{self.device_id}] Executed power on command.")
            
            # Schedule refresh
            asyncio.create_task(self._delayed_refresh(delay=2.0))
            
            return self.create_command_result(
                success=True,
                message="Power on command executed successfully"
            )
        except NotImplementedError:
            logger.warning(f"[{self.device_id}] Direct power on not supported, trying to send key instead...")
            # Fallback to sending a key press to wake
            return await self._execute_remote_command("select")  # Return its CommandResult
        except Exception as e:
            error_msg = f"Error turning on: {str(e)}"
            logger.error(f"[{self.device_id}] {error_msg}", exc_info=True)
            self.state.error = error_msg
            await self.publish_state()
            return self.create_command_result(success=False, error=error_msg)
            
    return self.create_command_result(
        success=False,
        error="Failed to connect to Apple TV"
    )
```

### 5. Update Helper Methods

The `_execute_remote_command` method is a critical helper that needs to be updated to return CommandResult:

```python
async def _execute_remote_command(self, command_name: str) -> CommandResult:
    """
    Execute a remote control command on the Apple TV.
    
    Args:
        command_name: Name of the command to execute
        
    Returns:
        CommandResult: Result of the command execution
    """
    if not await self._ensure_connected():
        return self.create_command_result(
            success=False,
            error="Not connected to Apple TV"
        )
    
    try:
        remote = self.atv.remote
        if not hasattr(remote, command_name):
            error_msg = f"Remote command '{command_name}' not found in pyatv."
            logger.error(f"[{self.device_id}] {error_msg}")
            return self.create_command_result(success=False, error=error_msg)
            
        # Get the method reference and call it
        command_method = getattr(remote, command_name)
        await command_method()
        
        logger.info(f"[{self.device_id}] Executed remote command: {command_name}")
        
        # Add to last command history - this will be replaced by BaseDevice._execute_single_action
        self.update_state(last_command=LastCommand(
            action=command_name,
            source="api",
            timestamp=datetime.now(),
            params=None
        ))
        
        return self.create_command_result(
            success=True,
            message=f"Remote command {command_name} executed successfully"
        )
    except AttributeError:
        error_msg = f"Remote command '{command_name}' not found in pyatv."
        logger.error(f"[{self.device_id}] {error_msg}")
        return self.create_command_result(success=False, error=error_msg)
    except Exception as e:
        error_msg = f"Error executing remote command {command_name}: {str(e)}"
        logger.error(f"[{self.device_id}] {error_msg}", exc_info=True)
        self.state.error = f"Command error: {str(e)}"
        await self.publish_state()
        return self.create_command_result(success=False, error=error_msg)
```

### 6. Update refresh_status Method

The `refresh_status` method already has the correct parameters, but needs to be updated to return CommandResult:

```python
async def handle_refresh_status(
    self, 
    cmd_config: StandardCommandConfig, 
    params: Dict[str, Any]
) -> CommandResult:
    """
    Refresh the status of the Apple TV.
    
    Args:
        cmd_config: Command configuration
        params: Parameters (unused)
        
    Returns:
        CommandResult: Result of the refresh operation
    """
    try:
        publish = params.get("publish", True) if params else True
        success = await self.refresh_status(publish=publish)
        
        if success:
            return self.create_command_result(
                success=True,
                message="Status refreshed successfully"
            )
        else:
            return self.create_command_result(
                success=False,
                error="Failed to refresh status"
            )
    except Exception as e:
        error_msg = f"Error refreshing status: {str(e)}"
        logger.error(f"[{self.device_id}] {error_msg}", exc_info=True)
        return self.create_command_result(success=False, error=error_msg)
```

### 7. Remove Custom State Publishing

The AppleTVDevice has a custom `publish_state` method that should be replaced with BaseDevice's standard approach:

```python
# Remove: async def publish_state(self):

# Instead, use BaseDevice.update_state in methods
self.update_state(
    power=power_state,
    connected=True,
    # Other state attributes
)
```

### 8. Implementation Steps for AppleTVDevice

1. Update imports to include the new types:
   ```python
   from app.types import CommandResult, CommandResponse, ActionHandler
   ```

2. Update class definition with generic type parameter:
   ```python
   class AppleTVDevice(BaseDevice[AppleTVState]):
   ```

3. Remove redundant `typed_config` property in `__init__`

4. Add standard `_register_handlers` method

5. Rename handler methods to follow the naming convention:
   - `turn_on` -> `handle_power_on`
   - `turn_off` -> `handle_power_off`
   - `play` -> `handle_play`
   - `pause` -> `handle_pause`
   - `stop` -> `handle_stop`
   - `next_track` -> `handle_next_track`
   - `previous_track` -> `handle_previous_track`
   - `menu` -> `handle_menu`
   - `home` -> `handle_home`
   - `select` -> `handle_select`
   - `up` -> `handle_up`
   - `down` -> `handle_down`
   - `left` -> `handle_left`
   - `right` -> `handle_right`
   - `set_volume` -> `handle_set_volume`
   - `volume_up` -> `handle_volume_up`
   - `volume_down` -> `handle_volume_down`
   - `launch_app` -> `handle_launch_app`
   - `refresh_status` -> `handle_refresh_status`
   - `_execute_remote_command` -> `_execute_remote_command`

6. Update all handler methods to return CommandResult instead of boolean

7. Update helper methods to return CommandResult

8. Remove custom `publish_state` method and use `update_state` instead

9. Update method calls to use the new handler names and handle the new return types

### 9. Specific Method Changes

| Current Method | New Method | Change Required |
|---------------|------------|----------------|
| `turn_on` | `handle_power_on` | Rename + return CommandResult |
| `turn_off` | `handle_power_off` | Rename + return CommandResult |
| `play` | `handle_play` | Rename + return CommandResult |
| `pause` | `handle_pause` | Rename + return CommandResult |
| `stop` | `handle_stop` | Rename + return CommandResult |
| `next_track` | `handle_next_track` | Rename + return CommandResult |
| `previous_track` | `handle_previous_track` | Rename + return CommandResult |
| `menu` | `handle_menu` | Rename + return CommandResult |
| `home` | `handle_home` | Rename + return CommandResult |
| `select` | `handle_select` | Rename + return CommandResult |
| `up` | `handle_up` | Rename + return CommandResult |
| `down` | `handle_down` | Rename + return CommandResult |
| `left` | `handle_left` | Rename + return CommandResult |
| `right` | `handle_right` | Rename + return CommandResult |
| `set_volume` | `handle_set_volume` | Rename + return CommandResult |
| `volume_up` | `handle_volume_up` | Rename + return CommandResult |
| `volume_down` | `handle_volume_down` | Rename + return CommandResult |
| `launch_app` | `handle_launch_app` | Rename + return CommandResult |
| `refresh_status` | `handle_refresh_status` | Rename + return CommandResult |
| `_execute_remote_command` | `_execute_remote_command` | Update to return CommandResult |

### 10. Testing Steps for AppleTVDevice

1. Test each renamed handler with the new signature and return type
2. Test that action handler registration works correctly
3. Test that remote command execution works correctly
4. Test that API calls still function properly
5. Test error handling with the new return types
6. Test that state updates still work without the custom `publish_state` method

## EMotivaXMC2

After a thorough review of the EMotivaXMC2 implementation, the following changes are required to align with the strong typing standardization plan:

### 1. Update Class Definition with Generic Type

```python
class EMotivaXMC2(BaseDevice[EmotivaXMC2State]):
    """eMotiva XMC2 processor device implementation."""
```

### 2. Remove Redundant typed_config

```python
def __init__(self, config: EmotivaXMC2DeviceConfig, mqtt_client=None):
    super().__init__(config, mqtt_client)
    
    # Remove redundant typed_config storage
    # self.typed_config = config  # REMOVE THIS LINE
    
    self.client: Optional[Emotiva] = None
    
    # Initialize device state with Pydantic model
    self.state: EmotivaXMC2State = EmotivaXMC2State(
        device_id=self.config.device_id,  # Use self.config instead of self.typed_config
        device_name=self.config.device_name,
        power=None,
        zone2_power=None,
        input_source=None,
        video_input=None,
        audio_input=None,
        volume=None,
        mute=None,
        audio_mode=None,
        audio_bitstream=None,
        connected=False,
        ip_address=None,
        mac_address=None,
        startup_complete=False,
        notifications=False,
        last_command=None,
        error=None
    )
    
    # Remove direct handler registration - will be done in _register_handlers
```

### 3. Add Standard Handler Registration Method

```python
def _register_handlers(self) -> None:
    """Register action handlers for the eMotiva XMC2 device.
    
    All handlers follow the standardized signature:
    async def handle_x(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult
    """
    self._action_handlers.update({
        "power_on": self.handle_power_on,
        "power_off": self.handle_power_off,
        "zone2_on": self.handle_zone2_on,
        "zappiti": self.handle_zappiti,
        "apple_tv": self.handle_apple_tv,
        "dvdo": self.handle_dvdo,
        "set_volume": self.handle_set_volume,
        "set_mute": self.handle_set_mute
    })
```

### 4. Update setup Method for Config Access

```python
async def setup(self) -> bool:
    """Initialize the device."""
    try:
        # Get emotiva configuration directly from config
        emotiva_config: EmotivaConfig = self.config.emotiva  # Use self.config instead of self.typed_config
        
        # Rest of the setup method remains unchanged
        # ...
```

### 5. Update Handler Methods to Return CommandResult

Update all handler methods to use the standardized CommandResult return type:

```python
async def handle_power_on(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
    """Handle power on action."""
    try:
        if not self.client:
            return self.create_command_result(success=False, error="Device not initialized")
            
        logger.info(f"Powering on eMotiva device: {self.get_name()}")
        result = await self.client.power_on()
        
        if self._is_command_successful(result):
            return self.create_command_result(success=True, message="Power on command sent successfully")
        else:
            error_message = result.get("message", "Unknown error") if result else "Failed to send power on command"
            return self.create_command_result(success=False, error=error_message)
            
    except Exception as e:
        error_message = f"Error executing power on: {str(e)}"
        self.set_error(error_message)
        return self.create_command_result(success=False, error=error_message)
```

Apply the same pattern to all other action handlers.

### 6. Refactor _create_response and _execute_device_command

Replace the custom `_create_response` method with BaseDevice's `create_command_result`:

```python
# REMOVE the custom _create_response method and use create_command_result instead
```

Update the `_execute_device_command` method signature and implementation:

```python
async def _execute_device_command(
    self, 
    action: str,
    command_func: DeviceCommandFunc,
    params: Dict[str, Any],
    notification_topics: List[str] = None,
    state_updates: Dict[str, Any] = None
) -> CommandResult:
    """Execute a device command with consistent error handling and state updates."""
    try:
        # Check if client is initialized
        if not self.client:
            return self.create_command_result(
                success=False, 
                error="Device not initialized"
            )
            
        # Execute the command function
        logger.debug(f"Executing {action} for device {self.get_name()}")
        command_result = await command_func()
        
        # Check if command was successful
        success = self._is_command_successful(command_result)
        
        # Update state based on result
        if state_updates and success:
            self.update_state(**state_updates)
            
        # Record this command
        self.record_last_command(action, params)
        
        # Process result into standard CommandResult format
        if success:
            return self.create_command_result(
                success=True,
                message=f"{action.replace('_', ' ').title()} command sent successfully"
            )
        else:
            error_message = command_result.get("message", "Unknown error") if command_result else f"Failed to execute {action}"
            return self.create_command_result(
                success=False,
                error=error_message
            )
            
    except Exception as e:
        error_message = f"Error executing {action}: {str(e)}"
        self.set_error(error_message)
        return self.create_command_result(
            success=False,
            error=error_message
        )
```

### 7. Update State Handling

Use the standard error handling methods:

```python
# Instead of directly updating error state:
# self.update_state(error=error_message)

# Use:
self.set_error(error_message)

# And to clear errors:
self.clear_error()
```

### 8. Update _switch_input_source Method

```python
async def _switch_input_source(self, source_name: str, source_id: str) -> CommandResult:
    """Switch the input source to the specified source."""
    try:
        if not self.client:
            return self.create_command_result(success=False, error="Device not initialized")
            
        logger.info(f"Switching input to {source_name} (ID: {source_id}) on device: {self.get_name()}")
        
        # Define the command function
        async def set_input_with_id() -> Dict[str, Any]:
            return await self.client.set_input(source_id)
            
        # Execute the command with our helper
        return await self._execute_device_command(
            action=f"switch_to_{source_name.lower()}",
            command_func=set_input_with_id,
            params={"source": source_name, "source_id": source_id}
        )
            
    except Exception as e:
        error_message = f"Error switching input source: {str(e)}"
        self.set_error(error_message)
        return self.create_command_result(success=False, error=error_message)
```

### 9. Update Message Handling

Update the `handle_message` method to return CommandResult:

```python
async def handle_message(self, topic: str, payload: str) -> Optional[CommandResult]:
    """Handle incoming MQTT messages for the eMotiva device."""
    logger.debug(f"EMotivaXMC2 received message on topic {topic}: {payload}")
    # Rest of implementation can remain the same, just update return type to CommandResult
    # ...
    return await super().handle_message(topic, payload)
```

### 10. Implementation Steps

1. Update imports to include the new types from app.types
2. Update class definition with generic type parameter
3. Remove redundant typed_config storage and update all references to use self.config
4. Implement _register_handlers and remove _initialize_action_handlers
5. Update _create_generic_handler to return ActionHandler and use CommandResult
6. Replace _create_response with create_command_result
7. Update handle_message to return CommandResult
8. Remove custom _get_action_handler
9. Simplify get_available_commands
10. Update record_last_command to use CommandResult if needed

### 11. Testing Plan

1. Create unit tests for all updated methods
2. Test each handler with the new signatures
3. Test MQTT message handling and command execution
4. Test error handling with the new return types
5. Test that state updates still work correctly
6. Ensure backward compatibility with existing API calls and MQTT integration

## WirenboardIrDevice

After a thorough review of the WirenboardIRDevice implementation, the following changes are required to align with the strong typing standardization plan:

### 1. Update Class Definition with Generic Type

```python
class WirenboardIRDevice(BaseDevice[WirenboardIRState]):
    """Implementation of an IR device controlled through Wirenboard."""
```

### 2. Update Custom Type Definitions

Replace local type definitions with the standard ones from app/types.py:

```python
# Remove these local type definitions
# class MQTTMessageResponse(TypedDict, total=False):
#     topic: str
#     payload: Union[str, int, float, bool, Dict[str, Any], List[Any]]

# class ResponseDict(TypedDict, total=False):
#     success: bool
#     action: str
#     device_id: str
#     message: Optional[str]
#     error: Optional[str]

# Replace with imports
from app.types import CommandResult, CommandResponse, ActionHandler
```

### 3. Remove Redundant typed_config Storage

```python
def __init__(self, config: WirenboardIRDeviceConfig, mqtt_client: Optional[MQTTClient] = None) -> None:
    super().__init__(config, mqtt_client)
    
    # Remove redundant typed_config storage
    # self.typed_config: WirenboardIRDeviceConfig = cast(WirenboardIRDeviceConfig, config)
    
    # Initialize state with typed Pydantic model
    self.state: WirenboardIRState = WirenboardIRState(
        device_id=self.device_id,
        device_name=self.device_name,
        alias=self.config.device_name  # Use self.config instead of self.typed_config
    )
    
    # Initialize handlers dictionary with proper type annotation
    # self._action_handlers: Dict[str, Callable[..., Awaitable[ResponseDict]]] = {}
    # Replace with:
    # self._action_handlers is now initialized in BaseDevice.__init__
    
    # Don't call _initialize_action_handlers() here as it will be handled by _register_handlers
```

### 4. Add Standard Handler Registration Method

```python
def _register_handlers(self) -> None:
    """
    Register action handlers for the Wirenboard IR device.
    
    This method is called during initialization to register all
    action handlers for this device.
    """
    # Rather than using the _initialize_action_handlers method, do it directly here
    for cmd_name, cmd_config in self.config.commands.items():
        # Get the action name from the command config
        action_name = cmd_config.action if cmd_config.action else cmd_name
        self._action_handlers[action_name] = self._create_generic_handler(action_name, cmd_config)
        logger.debug(f"Registered handler for action '{action_name}'")
```

### 5. Update Handler Return Types

Replace the `_create_generic_handler` method to use CommandResult:

```python
def _create_generic_handler(self, action_name: str, cmd_config: IRCommandConfig) -> ActionHandler:
    """
    Create a generic handler for a command that follows the standard signature.
    
    Args:
        action_name: Name of the action
        cmd_config: IR command configuration
        
    Returns:
        ActionHandler: A handler function with the standardized signature
    """
    # Capture the original command config in closure
    original_cmd_config = cmd_config
    
    async def generic_handler(cmd_config: BaseCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """
        Generic action handler for IR commands.
        
        Args:
            cmd_config: Command configuration
            params: Dictionary of parameters
            
        Returns:
            CommandResult: Result of the command execution
        """
        logger.debug(f"Executing generic IR action: {action_name}")
        
        try:
            # Type check for cmd_config - convert to IRCommandConfig
            effective_cmd_config: IRCommandConfig
            if isinstance(cmd_config, IRCommandConfig):
                effective_cmd_config = cmd_config
            else:
                # For backward compatibility or if cmd_config is of a different type,
                # fall back to the original_cmd_config from closure
                effective_cmd_config = original_cmd_config
            
            # Get the topic for this command
            topic = self._get_command_topic(effective_cmd_config)
            if not topic:
                error_msg = f"Failed to construct topic for {action_name}"
                logger.error(error_msg)
                return self.create_command_result(success=False, error=error_msg)
            
            # For IR commands, the payload is always "1"
            payload = "1"
            
            # Record this command as the last executed
            self.record_last_command(action_name, params, topic, payload)
            
            # If MQTT client is available, publish the command
            if self.mqtt_client:
                try:
                    await self.mqtt_client.publish(topic, payload)
                    logger.info(f"Published IR command '{action_name}' to {topic}")
                    return self.create_command_result(
                        success=True, 
                        message=f"Successfully executed IR command '{action_name}'",
                        mqtt_topic=topic,
                        mqtt_payload=payload
                    )
                except Exception as e:
                    error_msg = f"Failed to publish IR command '{action_name}': {str(e)}"
                    logger.error(error_msg)
                    return self.create_command_result(success=False, error=error_msg)
            else:
                error_msg = "MQTT client not available"
                logger.error(error_msg)
                return self.create_command_result(success=False, error=error_msg)
                
        except Exception as e:
            error_msg = f"Error in generic IR handler for '{action_name}': {str(e)}"
            logger.error(error_msg)
            return self.create_command_result(success=False, error=error_msg)
    
    return generic_handler
```

### 6. Replace _create_response with create_command_result

Remove the custom `_create_response` method and update all calls to use the standard `create_command_result` method:

```python
# Remove the custom _create_response method:
# def _create_response(self, 
#                    success: bool, 
#                    action: str, 
#                    message: Optional[str] = None, 
#                    error: Optional[str] = None,
#                    **extra_fields) -> ResponseDict:
#     """Create a standardized response dictionary."""
#     ...

# Update calls to use create_command_result:
return self.create_command_result(
    success=success,
    message=message,
    error=error,
    **extra_fields  # Keep extra fields for backward compatibility
)
```

### 7. Update Message Handling

Update the `handle_message` method to return CommandResult:

```python
async def handle_message(self, topic: str, payload: str) -> Optional[CommandResult]:
    """
    Handle incoming MQTT messages for this device.
    
    Args:
        topic: The MQTT topic of the incoming message
        payload: The message payload
        
    Returns:
        Optional[CommandResult]: Result of handling the message or None
    """
    logger.debug(f"Wirenboard IR device received message on {topic}: {payload}")
    try:
        # Find matching command configuration by comparing full topic
        matching_cmd_name: Optional[str] = None
        matching_cmd_config: Optional[IRCommandConfig] = None
        
        for cmd_name, cmd_config in self.get_available_commands().items():
            if cmd_config.topic == topic:
                matching_cmd_name = cmd_name
                matching_cmd_config = cast(IRCommandConfig, cmd_config)
                break
        
        if not matching_cmd_name or not matching_cmd_config:
            logger.warning(f"No command configuration found for topic: {topic}")
            return None
        
        # Rest of the implementation...
        
        # For error cases that previously returned ResponseDict, now return CommandResult:
        if error_condition:
            return self.create_command_result(
                success=False,
                error=error_message
            )
        
        # For successful cases that returned MQTTMessageResponse, we need to return CommandResult
        # but include the MQTT command information:
        return self.create_command_result(
            success=True,
            message=f"IR command executed for topic {topic}",
            mqtt_command={
                "topic": command_topic,
                "payload": 1
            }
        )
        
    except Exception as e:
        logger.error(f"Error handling message for {self.get_name()}: {str(e)}")
        return self.create_command_result(success=False, error=str(e))
```

### 8. Update _get_action_handler Method

Remove the custom `_get_action_handler` method since BaseDevice will provide the standard implementation:

```python
# Remove this method as it's provided by BaseDevice
# def _get_action_handler(self, action_name: str) -> Optional[Callable[..., Awaitable[ResponseDict]]]:
#     """Get the handler for the specified action from pre-initialized handlers."""
#     ...
```

### 9. Update get_available_commands Method

Simplify the type casting in `get_available_commands`:

```python
def get_available_commands(self) -> Dict[str, IRCommandConfig]:
    """Return the list of available commands for this device."""
    # Using proper typing with the parent method
    return cast(Dict[str, IRCommandConfig], self.config.commands)
```

### 10. Implementation Steps

1. Update imports to include the new types from app.types
2. Update class definition with generic type parameter
3. Remove redundant typed_config storage and update all references to use self.config
4. Implement _register_handlers and remove _initialize_action_handlers
5. Update _create_generic_handler to return ActionHandler and use CommandResult
6. Replace _create_response with create_command_result
7. Update handle_message to return CommandResult
8. Remove custom _get_action_handler
9. Simplify get_available_commands
10. Update record_last_command to use CommandResult if needed

### 11. Testing Plan

1. Create unit tests for all updated methods
2. Test each handler with the new signatures
3. Test MQTT message handling and command execution
4. Test error handling with the new return types
5. Test that state updates still work correctly
6. Ensure backward compatibility with existing API calls and MQTT integration

## BroadlinkKitchenHood

After a thorough review of the BroadlinkKitchenHood implementation, the following changes are required to align with the strong typing standardization plan:

### 1. Update Class Definition with Generic Type

```python
class BroadlinkKitchenHood(BaseDevice[KitchenHoodState]):
    """Implementation of a kitchen hood controlled through Broadlink RF."""
```

### 2. Remove Redundant _state_schema

```python
def __init__(self, config: BroadlinkKitchenHoodConfig, mqtt_client: Optional[MQTTClient] = None):
    super().__init__(config, mqtt_client)
    self.broadlink_device = None
    
    # Remove redundant _state_schema attribute
    # self._state_schema = KitchenHoodState
    
    # Initialize state using Pydantic model
    self.state = KitchenHoodState(
        device_id=self.device_id,
        device_name=self.device_name,
        light="off",
        speed=0,
        connection_status="disconnected"
    )
    
    # Load RF codes map from config directly
    self.rf_codes = self.config.rf_codes
    # Logging statements can remain unchanged
```

### 3. Add Standard Handler Registration Method

Move handler registration to the standard method:

```python
def _register_handlers(self) -> None:
    """
    Register action handlers for the kitchen hood.
    
    This method maps action names to their corresponding handler methods
    following the standardized approach.
    """
    self._action_handlers.update({
        "set_light": self.handle_set_light,
        "set_speed": self.handle_set_speed
    })
    
    logger.debug(f"[{self.device_name}] Registered action handlers: {list(self._action_handlers.keys())}")
```

### 4. Update Handler Methods to Return CommandResult

Both handler methods currently don't return anything. They need to be updated to return CommandResult:

```python
async def handle_set_light(
    self, 
    cmd_config: StandardCommandConfig, 
    params: Dict[str, Any]
) -> CommandResult:
    """
    Handle light control with parameters.
    
    Args:
        cmd_config: The command configuration
        params: The parameters dictionary with 'state' key
        
    Returns:
        CommandResult: Result of the command execution
    """
    # Extract state parameter from params
    state = params.get("state", "off")
    
    # Convert numeric values (0/1) to string values (off/on)
    if state == "0" or state == 0 or state == "false" or state == "False" or state is False:
        state = "off"
    elif state == "1" or state == 1 or state == "true" or state == "True" or state is True:
        state = "on"
    
    # Validate final state value
    state = str(state).lower()
    if state not in ["on", "off"]:
        error_msg = f"Invalid light state: {state}, must be 'on' or 'off'"
        logger.error(error_msg)
        await self.publish_progress(f"Invalid light state: {state}")
        return self.create_command_result(success=False, error=error_msg)
    
    # Get RF code from the rf_codes map
    if "light" not in self.rf_codes:
        error_msg = "No RF codes map found for 'light' category"
        logger.error(error_msg)
        await self.publish_progress("No RF codes map found for lights")
        return self.create_command_result(success=False, error=error_msg)
    
    # Access RF code using proper typed structure
    rf_code = self.rf_codes.get("light", {}).get(state)
    if not rf_code:
        error_msg = f"No RF code found for light state: {state}"
        logger.error(error_msg)
        await self.publish_progress(f"No RF code found for light state: {state}")
        return self.create_command_result(success=False, error=error_msg)
        
    # Send the RF code
    if await self._send_rf_code(rf_code):
        # Update state using model copy with update
        self.state = self.state.model_copy(update={"light": state})
        await self.publish_progress(f"Light turned {state}")
        return self.create_command_result(
            success=True,
            message=f"Light turned {state}"
        )
    else:
        error_msg = "Failed to send RF code for light command"
        return self.create_command_result(
            success=False,
            error=error_msg
        )
```

Similarly, update the `handle_set_speed` method:

```python
async def handle_set_speed(
    self, 
    cmd_config: StandardCommandConfig, 
    params: Dict[str, Any]
) -> CommandResult:
    """
    Handle hood speed control with parameters.
    
    Args:
        cmd_config: The command configuration
        params: The parameters dictionary with 'level' key
        
    Returns:
        CommandResult: Result of the command execution
    """
    logger.debug(f"[{self.device_name}] handle_set_speed called with params: {params}")
    logger.debug(f"[{self.device_name}] Current RF codes: {list(self.rf_codes.keys())}")
    
    # Convert level to int and validate range
    try:
        # Handle various input formats
        level_input = params.get("level", 0)
        
        # Convert to int regardless of input type
        level = int(level_input)
            
        if level < 0 or level > 4:
            error_msg = f"Invalid speed level: {level}, must be between 0 and 4"
            logger.error(error_msg)
            await self.publish_progress(f"Invalid speed level: {level}")
            return self.create_command_result(success=False, error=error_msg)
    except (ValueError, TypeError):
        error_msg = f"Invalid speed level value: {params.get('level')}"
        logger.error(error_msg)
        await self.publish_progress(f"Invalid speed level value")
        return self.create_command_result(success=False, error=error_msg)
    
    # Convert level to string for lookup in the RF codes map
    level_str = str(level)
    
    # Get RF code from the rf_codes map
    if "speed" not in self.rf_codes:
        error_msg = "No RF codes map found for 'speed' category"
        logger.error(error_msg)
        await self.publish_progress("No RF codes map found for speed control")
        return self.create_command_result(success=False, error=error_msg)
        
    # Access RF code using proper typed structure
    rf_code = self.rf_codes.get("speed", {}).get(level_str)
    if not rf_code:
        error_msg = f"No RF code found for speed level: {level}"
        logger.error(error_msg)
        await self.publish_progress(f"No RF code found for speed level: {level}")
        return self.create_command_result(success=False, error=error_msg)
        
    # Send the RF code
    if await self._send_rf_code(rf_code):
        # Update state using model copy with update
        self.state = self.state.model_copy(update={"speed": level})
        await self.publish_progress(f"Speed set to {level}")
        return self.create_command_result(
            success=True,
            message=f"Speed set to {level}"
        )
    else:
        error_msg = "Failed to send RF code for speed command"
        return self.create_command_result(
            success=False,
            error=error_msg
        )
```

### 5. Update _send_rf_code to Use Standard Error Handling

```python
async def _send_rf_code(self, rf_code_base64: str) -> bool:
    """
    Send RF code using Broadlink device.
    
    Args:
        rf_code_base64: Base64 encoded RF code
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        if not self.broadlink_device:
            logger.error("Broadlink device not initialized")
            self.set_error("Broadlink device not initialized")  # Use standard method
            return False
        
        # Decode base64 RF code
        rf_code = base64.b64decode(rf_code_base64)
        
        # Send the code
        await asyncio.get_event_loop().run_in_executor(
            None, self.broadlink_device.send_data, rf_code
        )
        self.clear_error()  # Clear any previous errors
        return True
        
    except Exception as e:
        error_msg = f"Error sending RF code: {str(e)}"
        logger.error(error_msg)
        
        # Use standard error handling method
        self.set_error(error_msg)
        
        return False
```

### 6. Update setup and shutdown Methods

Update the `setup` method to use standard error handling:

```python
async def setup(self) -> bool:
    """Initialize the Broadlink device for the kitchen hood."""
    try:
        # Get Broadlink configuration directly from config
        broadlink_config = self.config.broadlink
        
        logger.info(f"Initializing Broadlink device: {self.get_name()} at {broadlink_config.host}")
        
        # Initialize the Broadlink device
        self.broadlink_device = broadlink.rm4pro(
            host=(broadlink_config.host, 80),
            mac=bytes.fromhex(broadlink_config.mac.replace(':', '')),
            devtype=int(broadlink_config.device_class, 16)
        )
        
        # Authenticate with the device
        self.broadlink_device.auth()
        logger.info(f"Successfully connected to Broadlink device for {self.get_name()}")
        
        # Update state using model copy with update
        self.update_state(connection_status="connected")
        
        # Log RF codes map status
        logger.debug(f"[{self.device_name}] RF codes after init: {list(self.rf_codes.keys())}")
        logger.info(f"Loaded RF codes map with {len(self.rf_codes)} categories")
        for category, codes in self.rf_codes.items():
            logger.debug(f"  - {category}: {len(codes)} codes: {list(codes.keys())}")
        
        # Additional verification for speed codes specifically
        if "speed" in self.rf_codes:
            logger.debug(f"[{self.device_name}] Speed codes available: {list(self.rf_codes['speed'].keys())}")
        else:
            logger.warning(f"[{self.device_name}] 'speed' category missing from RF codes! Available: {list(self.rf_codes.keys())}")
        
        logger.info(f"Kitchen hood {self.get_name()} initialized with {len(self.get_available_commands())} commands")
        await self.publish_progress(f"successfully initialized with {len(self.get_available_commands())} commands")
        return True
        
    except Exception as e:
        error_msg = f"Failed to initialize device {self.get_name()}: {str(e)}"
        logger.error(error_msg)
        
        # Use standard error handling method
        self.set_error(error_msg)
        self.update_state(connection_status="error")
        
        return False
```

### 7. Update State Handling Throughout the Code

Replace direct state updates with `update_state` calls:

```python
# Instead of:
# self.state = self.state.model_copy(update={"light": state})

# Use:
self.update_state(light=state)

# Instead of:
# self.state = self.state.model_copy(update={"connection_status": "error", "error": str(e)})

# Use:
self.set_error(str(e))
self.update_state(connection_status="error")
```

### 8. Message Handling Method

Add a standard `handle_message` method if needed:

```python
async def handle_message(self, topic: str, payload: str) -> Optional[CommandResult]:
    """
    Handle incoming MQTT messages for this device.
    
    Args:
        topic: The MQTT topic
        payload: The message payload
        
    Returns:
        Optional[CommandResult]: Result of handling the message or None
    """
    logger.debug(f"Kitchen hood received message on {topic}: {payload}")
    
    # Delegate to parent class's handler
    return await super().handle_message(topic, payload)
```

### 9. Remove Custom get_current_state Method

Remove this method since it's already handled by BaseDevice:

```python
# Remove this method as it's already provided by BaseDevice
# def get_current_state(self) -> KitchenHoodState:
#     """Return the current state of the kitchen hood."""
#     return self.state
```

### 10. Implementation Steps

1. Update imports to include the new types:
   ```python
   from app.types import CommandResult, CommandResponse, ActionHandler
   ```

2. Update class definition with generic type parameter:
   ```python
   class BroadlinkKitchenHood(BaseDevice[KitchenHoodState]):
   ```

3. Remove redundant _state_schema and simplify __init__ method

4. Add standard _register_handlers method and remove direct handler registration in __init__

5. Update all handler methods to return CommandResult:
   - handle_set_light
   - handle_set_speed

6. Update the _send_rf_code method to use standard error handling

7. Update setup and shutdown methods to use standard error handling

8. Replace direct state updates with update_state calls throughout the code

9. Add a standard handle_message method

10. Remove the custom get_current_state method

### 11. Testing Plan

1. Test initialization with various configurations
2. Test light control with different parameter formats:
   - "on"/"off" string values
   - 0/1 numeric values
   - true/false boolean values
3. Test speed control with various values and edge cases:
   - Valid range (0-4)
   - Invalid values (negative, out of range, non-numeric)
4. Test error handling with missing or invalid RF codes
5. Test error recovery scenarios
6. Verify MQTT topic subscription works correctly
7. Verify that error handling and state updates work consistently
8. Test backward compatibility with existing API calls

## RevoxA77ReelToReel

After a thorough review of the RevoxA77ReelToReel implementation, the following changes are required to align with the strong typing standardization plan:

### 1. Update Class Definition with Generic Type

```python
class RevoxA77ReelToReel(BaseDevice[RevoxA77ReelToReelState]):
    """Implementation of a Revox A77 reel-to-reel controlled through Wirenboard IR."""
```

### 2. Remove Redundant _state_schema and typed_config

```python
def __init__(self, config: RevoxA77ReelToReelConfig, mqtt_client: Optional[MQTTClient] = None):
    super().__init__(config, mqtt_client)
    
    # Remove redundant _state_schema attribute
    # self._state_schema = RevoxA77ReelToReelState
    
    # Remove redundant typed_config storage
    # self.typed_config = config
    
    # Initialize state as a proper Pydantic model
    self.state = RevoxA77ReelToReelState(
        device_id=self.device_id,
        device_name=self.device_name,
        connection_status="connected"
    )
    
    # Handler registration will be moved to _register_handlers()
```

### 3. Add Standard Handler Registration Method

```python
def _register_handlers(self) -> None:
    """
    Register action handlers for the Revox A77 reel-to-reel device.
    
    This method maps action names to their corresponding handler methods
    following the standardized approach.
    """
    self._action_handlers.update({
        "play": self.handle_play,
        "stop": self.handle_stop,
        "rewind_forward": self.handle_rewind_forward,
        "rewind_backward": self.handle_rewind_backward
    })
```

### 4. Replace _create_response with create_command_result

Replace the custom `_create_response` method with the standardized `create_command_result`:

```python
# Remove this custom method:
# def _create_response(self, 
#                     success: bool, 
#                     action: str, 
#                     message: Optional[str] = None, 
#                     error: Optional[str] = None,
#                     **extra_fields) -> Dict[str, Any]:
#    """Create a standardized response dictionary."""
#    ...

# Update all calls to use create_command_result instead:
# return self._create_response(False, command_name, error=error_msg)

# Becomes:
return self.create_command_result(success=False, error=error_msg)
```

### 5. Update Handler Methods to Return CommandResult

Update all handler methods to use the standardized CommandResult return type:

```python
async def handle_play(
    self, 
    cmd_config: StandardCommandConfig, 
    params: Dict[str, Any]
) -> CommandResult:
    """
    Handle play command by sending the IR signal.
    
    Args:
        cmd_config: Command configuration
        params: Optional parameters for the command
        
    Returns:
        CommandResult: Result of the command execution
    """
    return await self._execute_sequence(cmd_config, "play", params)
```

And similarly for the other handlers.

### 6. Update Helper Methods to Use CommandResult

Update helper methods to return CommandResult:

```python
async def _send_ir_command(
    self, 
    cmd_config: IRCommandConfig, 
    command_name: str, 
    params: Dict[str, Any] = None
) -> CommandResult:
    """
    Send an IR command via MQTT.
    
    Args:
        cmd_config: Command configuration with location and rom_position
        command_name: Name of the command (for state tracking)
        params: Optional parameters for the command
        
    Returns:
        CommandResult: Result of the command execution
    """
    # Get location and ROM position from the typed config
    location = cmd_config.location
    rom_position = cmd_config.rom_position
    
    if not location or not rom_position:
        error_msg = f"Missing location or rom_position for {command_name} command"
        logger.error(error_msg)
        return self.create_command_result(success=False, error=error_msg)
        
    # Construct the MQTT topic
    topic = self._get_command_topic(cmd_config)
    payload = "1"
    
    if not topic:
        error_msg = f"Failed to create topic for {command_name} command"
        logger.error(error_msg)
        return self.create_command_result(success=False, error=error_msg)
    
    # Record this as the last command sent 
    if params is None:
        params = {}
        
    # Include MQTT-specific details in params
    params["mqtt_topic"] = topic
    params["mqtt_payload"] = payload
    
    # Create the LastCommand object and update state directly
    last_command = LastCommand(
        action=command_name,
        source="mqtt",
        timestamp=datetime.now(),
        params=params
    )
    
    # Update state with the LastCommand object
    self.update_state(last_command=last_command)
    
    logger.info(f"Sending {command_name} command to {location} at position {rom_position}")
    
    # Send the command via MQTT if client is available
    if self.mqtt_client:
        try:
            await self.mqtt_client.publish(topic, payload)
            return self.create_command_result(
                success=True, 
                message=f"Sent {command_name} command to {location} at position {rom_position}",
                mqtt_topic=topic,
                mqtt_payload=payload
            )
        except Exception as e:
            error_msg = f"Failed to send {command_name} command: {str(e)}"
            logger.error(error_msg)
            return self.create_command_result(success=False, error=error_msg)
    else:
        # For testing without MQTT client
        logger.info(f"MQTT client not available, would send to {topic}: {payload}")
        return self.create_command_result(
            success=True, 
            message=f"Would send {command_name} command to {location} at position {rom_position}",
            mqtt_topic=topic,
            mqtt_payload=payload
        )
```

Also update the `_execute_sequence` method:

```python
async def _execute_sequence(
    self, 
    cmd_config: IRCommandConfig, 
    command_name: str, 
    params: Dict[str, Any] = None
) -> CommandResult:
    """
    Execute a command sequence: stop -> wait -> requested command.
    
    Args:
        cmd_config: Command configuration with location and rom_position
        command_name: Name of the command to execute
        params: Optional parameters for the command
        
    Returns:
        CommandResult: Result of the command execution
    """
    # 1. Find and execute the stop command first
    stop_cmd = self.get_available_commands().get("stop")
    if not stop_cmd:
        error_msg = "Stop command not found in available commands"
        logger.error(error_msg)
        return self.create_command_result(success=False, error=error_msg)
    
    try:
        # No need to convert to IRCommandConfig as it should already be typed
        stop_config = stop_cmd
        
        # Send the stop command
        stop_result = await self._send_ir_command(stop_config, "stop")
        
        # Check if stop command was successful
        if not stop_result.get("success", False):
            error_msg = stop_result.get("error", "Failed to execute stop command")
            logger.error(error_msg)
            return self.create_command_result(success=False, error=error_msg)
        
        # 2. Get the delay from the config
        sequence_delay = self.config.reel_to_reel.sequence_delay  # Use self.config instead of self.typed_config
        
        # 3. Wait for the configured delay
        await self.publish_progress(f"Waiting {sequence_delay}s before executing {command_name}")
        await asyncio.sleep(sequence_delay)
        
        # 4. Execute the requested command
        await self.publish_progress(f"Executing {command_name} command")
        result = await self._send_ir_command(cmd_config, command_name, params)
        
        return result
        
    except Exception as e:
        error_msg = f"Error in sequence execution: {str(e)}"
        logger.error(error_msg)
        return self.create_command_result(success=False, error=error_msg)
```

### 7. Update handle_message Method to Return CommandResult

```python
async def handle_message(self, topic: str, payload: str) -> Optional[CommandResult]:
    """
    Handle incoming MQTT messages for this device.
    
    Args:
        topic: The MQTT topic
        payload: The message payload
        
    Returns:
        Optional[CommandResult]: Result of handling the message or None
    """
    try:
        # Find matching command
        matching_cmd_name = None
        matching_cmd_config = None
        
        for cmd_name, cmd_config in self.get_available_commands().items():
            if topic == cmd_config.topic:
                matching_cmd_name = cmd_name
                matching_cmd_config = cmd_config
                break
        
        if not matching_cmd_name or not matching_cmd_config:
            logger.warning(f"No command configuration found for topic: {topic}")
            return None
        
        # Check if the payload indicates command should be executed
        if payload.lower() in ["1", "true", "on"]:
            # Get the handler from our registered handlers
            handler = self._action_handlers.get(matching_cmd_name)
            if handler:
                # Call the handler with the command config and empty params
                # This will now return CommandResult directly
                return await handler(cmd_config=matching_cmd_config, params={})
            else:
                logger.warning(f"No handler found for command: {matching_cmd_name}")
                return self.create_command_result(
                    success=False, 
                    error=f"No handler found for command: {matching_cmd_name}"
                )
        
        return None
        
    except Exception as e:
        error_msg = f"Error handling message for {self.get_name()}: {str(e)}"
        logger.error(error_msg)
        return self.create_command_result(success=False, error=error_msg)
```

### 8. Remove Custom get_current_state Method

Remove this method since it's already provided by BaseDevice:

```python
# Remove this method as it's already provided by BaseDevice
# def get_current_state(self) -> RevoxA77ReelToReelState:
#    """Return the current state of the device."""
#    return self.state
```

### 9. Update setup Method to Use Standard Error Handling

```python
async def setup(self) -> bool:
    """Initialize the device."""
    try:
        # Load and validate commands configuration
        commands = self.config.commands  # Use self.config instead of self.typed_config
        if not commands:
            error_msg = f"No commands defined for device {self.get_name()}"
            logger.error(error_msg)
            self.set_error(error_msg)  # Use standard error method
            return True  # Return True to allow device to be initialized even without commands
        
        logger.info(f"Revox A77 reel-to-reel {self.get_name()} initialized with {len(commands)} commands")
        return True
        
    except Exception as e:
        error_msg = f"Failed to initialize device {self.get_name()}: {str(e)}"
        logger.error(error_msg)
        self.set_error(error_msg)  # Use standard error method
        self.update_state(connection_status="error")
        return True  # Return True to allow device to be initialized even with errors
```

### 10. Implementation Steps

1. Update imports to include the new types:
   ```python
   from app.types import CommandResult, CommandResponse, ActionHandler
   ```

2. Update class definition with generic type parameter:
   ```python
   class RevoxA77ReelToReel(BaseDevice[RevoxA77ReelToReelState]):
   ```

3. Remove redundant _state_schema and typed_config in __init__ method

4. Add standard _register_handlers method and remove direct handler registration in __init__

5. Replace custom _create_response method with create_command_result calls

6. Update all handler methods to return CommandResult

7. Update helper methods to return CommandResult:
   - _send_ir_command
   - _execute_sequence

8. Update handle_message to return CommandResult

9. Remove the custom get_current_state method

10. Update setup and shutdown methods to use standard error handling

### 11. Update Config References

Replace all references to `self.typed_config` with `self.config`:

```python
# Instead of:
sequence_delay = self.typed_config.reel_to_reel.sequence_delay

# Use:
sequence_delay = self.config.reel_to_reel.sequence_delay
```

### 12. Testing Plan

1. Test initialization with various configurations
2. Test each command:
   - play
   - stop
   - rewind_forward
   - rewind_backward
3. Test sequence execution and timing
4. Test error handling:
   - Missing command configurations
   - MQTT client unavailable
   - Invalid command parameters
5. Test command execution through MQTT messages
6. Verify that error handling and state updates work consistently
7. Test backward compatibility with existing API calls
8. Verify that command sequence execution maintains correct timing
