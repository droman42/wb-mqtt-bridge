# MQTT Command Propagation

## Overview

This document outlines the standard pattern for MQTT command propagation in the WB-MQTT Bridge. It ensures that device handlers correctly include MQTT command information in their responses, and that this information is properly propagated to the client for execution.

## Standard Pattern

The MQTT command propagation follows this pattern:

1. **Device handlers** create CommandResult objects with mqtt_command information
2. **BaseDevice.execute_action()** preserves this information in CommandResponse
3. **HTTP endpoints** return the full CommandResponse and execute MQTT commands in the background

## Helper Methods

The `BaseDevice` class provides two helper methods for creating CommandResult objects:

### 1. create_command_result

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
    # Implementation...
```

### 2. create_mqtt_command_result

```python
def create_mqtt_command_result(
    self, 
    success: bool, 
    mqtt_topic: str, 
    mqtt_payload: Any, 
    message: Optional[str] = None, 
    error: Optional[str] = None, 
    **extra_fields
) -> CommandResult:
    """
    Create a standardized CommandResult with MQTT command.
    
    Args:
        success: Whether the command was successful
        mqtt_topic: The MQTT topic to publish to
        mqtt_payload: The MQTT payload to publish (will be converted to string)
        message: Optional success message
        error: Optional error message (only if success is False)
        **extra_fields: Additional fields to include in the result
        
    Returns:
        CommandResult: A standardized result dictionary with MQTT command
    """
    # Implementation...
```

## Example: Correct Implementation

Here's an example of a device handler that correctly implements MQTT command propagation:

```python
async def handle_set_light(
    self, 
    cmd_config: StandardCommandConfig, 
    params: Dict[str, Any]
) -> CommandResult:
    # Process the command...
    
    # Return result with MQTT command
    if successful:
        return self.create_mqtt_command_result(
            success=True,
            mqtt_topic="device/lights/command",
            mqtt_payload={"state": "on"},
            message="Light turned on"
        )
    else:
        return self.create_command_result(
            success=False,
            error="Failed to turn on light"
        )
```

## MQTT Command Propagation Flow

1. **Device handler** creates CommandResult with `mqtt_command` field
2. **_execute_single_action** calls the handler and returns the CommandResult
3. **execute_action** includes the `mqtt_command` field in the CommandResponse:
   ```python
   # Add mqtt_command if present in result
   if result and "mqtt_command" in result:
       response["mqtt_command"] = result["mqtt_command"]
   ```
4. **HTTP endpoint** processes the CommandResponse:
   ```python
   # If there's an MQTT command to be published, do it in the background
   if "mqtt_command" in result and result["mqtt_command"] is not None and mqtt_client is not None:
       mqtt_cmd = result["mqtt_command"]
       background_tasks.add_task(
           mqtt_client.publish,
           mqtt_cmd["topic"],
           mqtt_cmd["payload"]
       )
   
   # Return the properly typed CommandResponse directly
   return result
   ```

## Audit Results

The following components have been audited for proper MQTT command propagation:

- ✅ **BaseDevice.execute_action**: Correctly preserves the `mqtt_command` field
- ✅ **BaseDevice._execute_single_action**: Correctly returns the CommandResult from the handler
- ✅ **HTTP Action Endpoint**: Correctly executes MQTT commands and returns the full CommandResponse
- ✅ **WirenboardIRDevice**: Uses `create_command_result` with `mqtt_command` field
- ✅ **BroadlinkKitchenHood**: Updated to use `create_mqtt_command_result` for improved MQTT command propagation

## Recommendations

1. **Use create_mqtt_command_result**: For handlers that need to publish MQTT commands
2. **Always include mqtt_command**: Even for internal state changes that don't require MQTT
3. **Test both API and MQTT paths**: Ensure both entry points correctly propagate commands

## Backward Compatibility

The `mqtt_command` field is optional in CommandResult and CommandResponse, so handlers that don't need to publish MQTT commands don't need to include it. This ensures backward compatibility with existing handlers.

## Conclusion

Properly implementing MQTT command propagation ensures that device actions triggered through the API will correctly publish MQTT commands as needed. This is critical for devices that need to communicate with external systems via MQTT.