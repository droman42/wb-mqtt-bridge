# Strong Typing Standardization Plan

This document outlines the plan to standardize strong typing across all device classes in the codebase.

## 1. Typed Config Handling

**BaseDevice Convention**: BaseDevice accepts a typed Pydantic model (`BaseDeviceConfig`) and uses it directly as `self.config`.

**Solution**:
- Remove redundant `typed_config` properties from all device classes
- Access config through `self.config` directly
- Extract device-specific configs only once when needed:
  ```python
  self.device_specific_config = self.config.device_specific_section  # Only if needed
  ```

## 2. Handler Registration Procedures

**Solution**:
- Add a standard `_register_handlers()` method to BaseDevice
- Have all devices override this method for registration
- Standardize all handler methods with signature:
  ```python
  async def handle_method(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
  ```
- All handler methods should use `handle_` prefix (e.g., `handle_power_on`)

## 3. Return Type Consistency

**Solution**:
- Define two distinct types in a central location:

  ```python
  class CommandResult(TypedDict):
      """Return type for individual device handlers"""
      success: bool
      message: Optional[str] = None
      error: Optional[str] = None
      # Command-specific fields as needed
  
  class CommandResponse(TypedDict, Generic[StateT]):
      """Return type for BaseDevice.execute_action"""
      success: bool
      device_id: str
      action: str
      state: StateT  # Properly typed state (device-specific state class)
      error: Optional[str] = None
  ```

- Add helper method to BaseDevice:
  ```python
  def create_command_result(self, success: bool, message: Optional[str] = None, 
                          error: Optional[str] = None, **extra_fields) -> CommandResult:
      """Create a standardized CommandResult for handlers to return."""
  ```

- BaseDevice's `execute_action` transforms CommandResult to CommandResponse:
  ```python
  # In execute_action
  result: CommandResult = await self._execute_single_action(...)  # Handler result
  
  # Transform to CommandResponse
  response = CommandResponse(
      success=result["success"],
      device_id=self.device_id,
      action=action,
      state=self.state,  # Properly typed state
      error=result.get("error")
  )
  ```

## 4. State Handling

**Solution**:
- Define a proper state class hierarchy with BaseDeviceState as the base
- Each device should define a state class that extends BaseDeviceState
- All devices should use `self.update_state(**updates)` exclusively
- Remove custom state update methods
- BaseDevice should initialize state with the correct subclass based on config

## 5. Error Handling

**Solution**:
- Add standard error methods to BaseDevice:
  ```python
  def set_error(self, error_message: str) -> None:
      """Set an error message in the device state."""
      self.update_state(error=error_message)
      
  def clear_error(self) -> None:
      """Clear any error message."""
      self.update_state(error=None)
  ```
- All devices should use these methods for error handling
- Standardize error reporting through state updates

## 6. Method Naming

**Solution**:
- Action handlers: `handle_action_name`
- Internal helpers: `_method_name`
- Device-specific helpers: `_action_category_action`
- Standard helper methods in BaseDevice:
  - `_execute_command(action_name, command_func, params, **kwargs)`
  - `_validate_connection()`
  - `_ensure_connected()`

## 7. Type Annotations

**Solution**:
- Add comprehensive type annotations throughout BaseDevice
- Define standard type aliases in a central location:
  ```python
  # In app/types.py
  StateT = TypeVar('StateT', bound=BaseDeviceState)
  ActionHandler = Callable[[StandardCommandConfig, Dict[str, Any]], Awaitable[CommandResult]]
  ```
- Use typed dictionaries for command results and responses
- Make handler signatures consistent with proper type annotations

## Implementation Priority

1. Define the central types (CommandResult, CommandResponse)
2. Update BaseDevice with standard methods and proper typing
3. Standardize one device class completely as a reference implementation
4. Progressively update remaining device classes 