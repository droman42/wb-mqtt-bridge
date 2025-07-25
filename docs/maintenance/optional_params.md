# Plan for Implementing Optional Parameters for Device Commands

This document outlines the plan to adapt the codebase to support optional parameters for device commands, as defined in the JSON configuration files (`config/devices/*.json`).

## 1. Configuration Schema Update

- **Introduce `params` Key:** Add an *optional* `params` key within each command definition object in the device JSON configuration files. If omitted, the command takes no parameters.
- **Parameter Definition Objects:** The `params` key will hold an array of objects, where each object defines a single parameter.
- **Parameter Object Fields:**
    - `name` (string): The parameter name.
    - `type` (string): Data type (e.g., "string", "integer", "float", "boolean", "range"). Used for potential validation.
    - `min` (number, optional): Minimum allowed value (used with `type: "range"`).
    - `max` (number, optional): Maximum allowed value (used with `type: "range"`).
    - `required` (boolean): `true` if the parameter must be provided, `false` otherwise.
    - `default` (any, optional): The default value to use if the parameter is not provided and `required` is `false`.
    - `description` (string, optional): A human-readable description.

- **Update Pydantic Schemas:** Modify the corresponding Pydantic models (e.g., `DeviceConfig` and related models in `app/schemas.py`) to include the new, *optional* `params` structure (including fields like `name`, `type`, `required`, `default`, `min`, `max`) for validation.

- **Example JSON Structure:**
  ```json
  {
    // ... other device config ...
    "commands": {
      "setBrightness": {
        "action": "set_brightness", 
        "topic": "/devices/light/set",
        "description": "Set light brightness and optional transition",
        "params": [
          { "name": "level", "type": "range", "min": 0, "max": 100, "required": true, "description": "Brightness level 0-100" },
          { "name": "transition", "type": "integer", "required": false, "default": 0, "description": "Transition time in seconds" }
        ]
      }
      // ... other commands ...
    }
  }
  ```

## 2. Parameter Processing Logic (`BaseDevice` / Subclasses)

- **`handle_message` (MQTT Input):**
    1. Find matching command configuration (`cmd_config`) based on the incoming `topic`.
    2. Check if `cmd_config` defines a `params` array. *If the `params` key is missing, treat it as an empty list.*
    3. **If `params` are defined (and not empty):**
        - Assume the MQTT `payload` is a JSON string representing parameters (e.g., `'{"level": 80, "transition": 5}'`).
        - Parse the payload using `json.loads(payload)`.
        - Use a helper function (see Step 4) or inline logic to validate parsed parameters against the `cmd_config["params"]` definition (check required fields, apply defaults).
        - **If JSON parsing fails:**
            - For single-parameter commands: Attempt to map the raw payload to the first parameter based on type.
            - For multi-parameter commands: Log an error and use defaults if available.
    4. **If `params` are NOT defined (or parsing fails/payload isn't JSON):**
        - Pass the raw payload to maintain backward compatibility with existing handlers.
    5. Call `_execute_single_action` passing both the *resolved* parameter dictionary and original `payload` for backward compatibility.

- **`execute_action` (API/Direct Call):**
    1. Accepts `action` (string) and `params` (dict) as input.
    2. Find the corresponding `cmd_config` for the `action`.
    3. Retrieve the `params` definition from `cmd_config`. *If the `params` key is missing, treat it as an empty list.*
    4. Use a helper function (see Step 4) or inline logic to create the final parameter dictionary:
        - Start with default values specified in `cmd_config["params"]` (if any).
        - Override/add values from the `params` dictionary passed into `execute_action`.
    5. Validate the final dictionary: Ensure all `required: true` parameters have values. Optionally check types.
    6. Raise an error if validation fails.
    7. Call `_execute_single_action` passing the *validated, final* parameter dictionary and `None` for the `raw_payload`.

## 3. Action Execution Refactoring

- **`_execute_single_action` Method:**
    - **Signature Change:** Modify the signature to support both parameter and payload approaches:
      ```python
      async def _execute_single_action(self, action_name: str, cmd_config: Dict[str, Any], 
                                      params: Dict[str, Any], raw_payload: Optional[str] = None)
      ```
    - **Backward Compatibility:** Maintain the `raw_payload` parameter to support existing devices during transition.
    - **Functionality:**
        - Retrieve the full command configuration (`cmd_config`) for the given `action_name`.
        - Get the handler method using `_get_action_handler(action_name)`.
        - Invoke the handler with appropriate parameters using a compatibility wrapper.
        - Update `LastCommand` state in `self.state` including both the action name and the resolved parameter dictionary:
          ```python
          self.update_state({
              "last_command": LastCommand(
                  action=action_name,
                  source="mqtt" if raw_payload is not None else "api",
                  timestamp=datetime.now(),
                  params=params
              ).dict()
          })
          ```

- **Handler Compatibility Wrapper:**
    - **Implement Utility Method:**
      ```python
      def _call_action_handler(self, handler, cmd_config: Dict[str, Any], 
                              params: Dict[str, Any], raw_payload: Optional[str])
      ```
    - Use reflection/inspection to determine if the handler:
        - Accepts the old signature `(action_config, payload)`, OR
        - Accepts the new signature `(cmd_config, params)`
    - Call handler with appropriate parameters based on its signature.
    - This allows gradual migration of device handlers without breaking existing functionality.

- **Specific Action Handlers (e.g., `handle_power_on`, `handle_set_brightness`):**
    - **New Signature:** `async def handle_some_action(self, cmd_config: Dict[str, Any], params: Dict[str, Any])`.
    - **Old Signature (supported during transition):** `async def handle_some_action(self, action_config: Dict[str, Any], payload: str)`.
    - **Implementation Guidelines:**
        - New handlers should always use the new signature with the `params` dictionary.
        - Update existing handlers gradually to use the new signature.
        - Document usage of parameters in handler docstrings.

- **Implementation Timeline:**
    - **Phased Approach:**
        1. ✅ Add parameter parsing and validation infrastructure.
        2. ✅ Update BaseDevice to support both old and new handler signatures.
        3. Update existing devices one by one, with BroadlinkKitchenHood as priority.
        4. ✅ Add comprehensive tests for parameter validation.

## 4. Helper Function (Recommended)

- **Create a Method:** Implement a helper method within `BaseDevice`, such as `_resolve_and_validate_params`.
- **Signature:** `_resolve_and_validate_params(self, cmd_config: Dict, provided_params: Dict, raw_payload: Optional[str] = None) -> Dict`
- **Functionality:**
    - Takes the command configuration (specifically the `params` definition part), the input parameters, and optionally the raw payload.
    - Applies default values for optional parameters.
    - Validates that all required parameters are present.
    - Handles type conversion if raw payload is provided for single-parameter commands.
    - Optionally performs type checking (including checking `min`/`max` for `range` types).
    - Returns the final, validated dictionary of parameters.
    - Raises a `ValueError` or similar exception if validation fails.
- **Error Handling:**
    - Return clear validation errors that can be logged or returned via API.
    - Provide standard payload conversion error handling for common data types.
- **Usage:** Call this helper from both `handle_message` (after attempting to parse the payload) and `execute_action`.

## 5. Specific Device Adaptation: BroadlinkKitchenHood

The `BroadlinkKitchenHood` device requires specific adaptation due to its reliance on mapping MQTT payload values to distinct RF codes.

- **Current State:** Relies on `condition` strings in the config's `actions` array, evaluated against the raw MQTT payload to select an action and its associated `rf_code`.
- **Required Changes:**
    - **Configuration (`config/devices/kitchen_hood.json`):**
        - Remove the `actions` array and the `condition` key.
        - Define simplified commands (`setLight`, `setSpeed`) using the new `params` structure (e.g., `setLight` takes a required string `state`, `setSpeed` takes a required integer `level`).
        - Introduce a new top-level `rf_codes` object to map parameter values to the corresponding base64 RF codes. This map will have sub-objects (e.g., `light`, `speed`) where keys are the parameter values (as strings, e.g., `"on"`, `"0"`, `"1"`) and values are the RF codes.
          ```json
          // Example snippet within kitchen_hood.json
          "rf_codes": {
            "light": {
              "on": "RF_CODE_LIGHT_ON...",
              "off": "RF_CODE_LIGHT_OFF..."
            },
            "speed": {
              "0": "RF_CODE_SPEED_0...", // Off
              "1": "RF_CODE_SPEED_1...",
              // ... other speeds
            }
          },
          "commands": {
            "setLight": {
              "action": "set_light",
              "topic": "/devices/kitchen_hood/controls/light",
              "params": [{ "name": "state", "type": "string", "required": true }]
            },
            // ... setSpeed command ...
          }
          ```
    - **Device Code (`devices/broadlink_kitchen_hood.py`):**
        - Load the `rf_codes` map from the configuration during initialization.
        - Consolidate existing action handlers (e.g., `handle_light_on`, `handle_light_off`) into new handlers matching the `action` defined in the commands (e.g., `handle_set_light`, `handle_set_speed`).
        - Update the `_action_handlers` dictionary to map the new action names to the new handlers.
        - Modify the new handlers:
            - Change signature to accept `self, cmd_config: Dict[str, Any], params: Dict[str, Any]`.
            - Extract the parameter value (e.g., `state = params["state"]` or `level = params["level"]`).
            - Convert the parameter value to a string if necessary (for the `speed` map lookup).
            - Look up the correct RF code in the loaded `rf_codes` map using the parameter value.
            - Send the RF code using `_send_rf_code`.
            - Update the device state based on the parameter value.
    - **Backward Compatibility:**
        - Maintain support for the old configuration format during the transition period.
        - Implement both handler approaches to support both calling patterns.

This adaptation aligns the kitchen hood with the general parameter handling mechanism while accommodating its specific RF code mapping requirement.

## 6. Cleanup After Full Migration

Once all devices have been migrated to the new parameter system, several cleanup steps should be performed to remove backward compatibility code and streamline the codebase. This section outlines the detailed cleanup process.

### 6.1. Code Cleanup in `BaseDevice`

- **`_execute_single_action` Method:**
    - **Remove Backward Compatibility:** Simplify the method signature by removing the `raw_payload` parameter:
      ```python
      async def _execute_single_action(self, action_name: str, cmd_config: Dict[str, Any], params: Dict[str, Any]):
      ```
    - **Update Implementation:**
      ```python
      async def _execute_single_action(self, action_name: str, cmd_config: Dict[str, Any], params: Dict[str, Any]):
          try:
              # Get the action handler method from the instance
              handler = self._get_action_handler(action_name)
              if not handler:
                   logger.warning(f"No action handler found for action: {action_name} in device {self.get_name()}")
                   return None
  
              logger.debug(f"Executing action: {action_name} with handler: {handler} and params: {params}")
              
              # Call the handler with the standardized parameter dictionary
              result = await handler(cmd_config=cmd_config, params=params)
              
              # Update state with information about the last command executed
              self.update_state({
                  "last_command": LastCommand(
                      action=action_name,
                      source="mqtt" if "topic" in cmd_config else "api",
                      timestamp=datetime.now(),
                      params=params
                  ).dict()
              })
              
              # Return any result from the handler
              return result
                  
          except Exception as e:
              logger.error(f"Error executing action {action_name}: {str(e)}")
              return None
      ```

- **Remove Handler Compatibility Wrapper:**
    - Delete the `_call_action_handler` utility method as it's no longer needed.
    - Remove all references to it in the codebase.

- **`handle_message` Method:**
    - Update to use the simplified parameter processing and standardized handler calling pattern:
      ```python
      async def handle_message(self, topic: str, payload: str):
          """Handle incoming MQTT messages for this device."""
          logger.debug(f"Device {self.get_name()} received message on {topic}: {payload}")
          
          # Find matching command configuration
          matching_commands = []
          for cmd_name, cmd_config in self.get_available_commands().items():
              if cmd_config.get("topic") == topic:
                  matching_commands.append((cmd_name, cmd_config))
          
          if not matching_commands:
              logger.warning(f"No command configuration found for topic: {topic}")
              return
          
          # Process each matching command configuration found for the topic
          for cmd_name, cmd_config in matching_commands:
              # Process parameters if defined
              params = {}
              param_definitions = cmd_config.get("params", [])
              
              if param_definitions:
                  # Try to parse payload as JSON
                  try:
                      params = json.loads(payload)
                  except json.JSONDecodeError:
                      # For single parameter commands, try to map raw payload to the first parameter
                      if len(param_definitions) == 1:
                          param_def = param_definitions[0]
                          # Convert based on type
                          try:
                              if param_def["type"] == "integer":
                                  params = {param_def["name"]: int(payload)}
                              elif param_def["type"] == "float":
                                  params = {param_def["name"]: float(payload)}
                              elif param_def["type"] == "boolean":
                                  params = {param_def["name"]: payload.lower() in ("1", "true", "yes", "on")}
                              else:  # string or any other type
                                  params = {param_def["name"]: payload}
                          except (ValueError, TypeError):
                              logger.error(f"Failed to convert payload '{payload}' to type {param_def['type']}")
                              # Use defaults if available
                              params = self._resolve_and_validate_params(cmd_config, {})
                      else:
                          logger.error(f"Payload is not valid JSON and command expects multiple parameters: {payload}")
                          # Use defaults if available
                          params = self._resolve_and_validate_params(cmd_config, {})
              
              # Validate parameters against definitions and apply defaults
              params = self._resolve_and_validate_params(cmd_config, params)
              
              # Execute the action with validated parameters
              await self._execute_single_action(cmd_name, cmd_config, params)
      ```

- **Update `_resolve_and_validate_params` Method:**
    - Simplify the method by removing the `raw_payload` parameter:
      ```python
      def _resolve_and_validate_params(self, cmd_config: Dict, provided_params: Dict) -> Dict:
      ```
    - Remove any code that handles raw payload conversion.

### 6.2. Device Implementation Cleanup

- **Standardize Handler Signatures:**
    - Update all action handler methods across all device implementations to use the standardized signature:
      ```python
      async def handler_name(self, cmd_config: Dict[str, Any], params: Dict[str, Any]):
      ```
    - Remove any handlers that were kept for backward compatibility.
    - Update the docstrings to reflect the new parameter usage.

- **Rename Outdated Handler References:**
    - Search for any remaining references to the old handler pattern (`action_config`, `payload`) and update them.
    - Update all handler registrations in device `__init__` methods that might still use old names.

- **BroadlinkKitchenHood Specific Cleanup:**
    - Remove the backward compatibility code from `BroadlinkKitchenHood`.
    - Ensure all references to the old `condition`-based actions are removed.
    - Finalize the transition to the new pattern of using the `rf_codes` map with parameters.

### 6.3. Configuration Cleanup

- **Remove Legacy Format Support:**
    - Review all device configuration files in `config/devices/*.json`.
    - Remove any legacy command formats (e.g., nested `actions` arrays with `condition` keys).
    - Ensure all commands use the new parameter-based approach consistently.

- **Update Pydantic Schemas:**
    - Remove any code in `app/schemas.py` that was added to support the transition.
    - Update validation logic to enforce the new format.
    - Remove any backward compatibility typings or optional fields that were needed during transition.

- **Documentation Updates:**
    - Update all documentation to reflect the finalized parameter system.
    - Remove references to the old style of command configuration.
    - Add examples showing the recommended patterns for various parameter types.
    - Add guidance on handling complex parameter needs.

### 6.4. Testing and Validation

- **Update Test Suite:**
    - Remove tests for backward compatibility features.
    - Add comprehensive tests for the parameter validation system.
    - Ensure full coverage of parameter types, validation, and error handling.
    - Add specific tests for single-value parameter mapping from non-JSON payloads.

- **Integration Testing:**
    - Perform thorough integration testing with real MQTT messages.
    - Test all devices with different parameter combinations.
    - Verify that validation errors are properly handled and reported.
    - Test edge cases like missing required parameters or parameters outside valid ranges.

- **Performance Analysis:**
    - Measure and compare performance before and after cleanup.
    - Identify any potential bottlenecks in parameter processing or validation.
    - Optimize as needed based on real-world usage patterns.

### 6.5. Deployment and Monitoring

- **Phased Deployment:**
    - Deploy the final cleanup changes in a controlled manner.
    - Monitor for any unexpected behavior or errors.
    - Have a rollback plan in case of significant issues.

- **Documentation for Users:**
    - Update user-facing documentation on how to configure devices.
    - Provide clear examples of device command configurations with parameters.
    - Add troubleshooting guidance for common parameter-related issues.

- **Monitoring Tools:**
    - Add specific logging for parameter validation errors to help diagnose issues.
    - Consider adding metrics collection for parameter usage patterns.
    - Set up alerts for repeated parameter validation failures.

### 6.6. Final Review

- **Code Review:**
    - Conduct a comprehensive code review to ensure all backward compatibility code has been removed.
    - Check for consistent implementation of the parameter system across all devices.
    - Verify that error handling is consistent and appropriate.
    - Ensure code style and documentation are up to standard.

- **Documentation Review:**
    - Update all internal and external documentation to reflect the finalized implementation.
    - Remove any outdated references or examples.
    - Add guidance for future device implementations.

- **Version Bump:**
    - After successful cleanup, consider bumping the major version number to indicate the significant architecture change.
    - Include clear migration guidance in the release notes.
    - Document the improved capabilities and any breaking changes.

By following this detailed cleanup plan, the codebase will be streamlined, more maintainable, and provide a consistent approach to parameter handling across all devices.

## Summary

This plan centralizes parameter definition in JSON, creates a unified processing pipeline for parameters from MQTT and direct calls, and ensures action handlers receive a consistent, validated set of parameters. The implementation approach maintains backward compatibility through a phased transition, allowing existing devices to continue functioning while new parameter capabilities are gradually adopted. 