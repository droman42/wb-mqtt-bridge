# Plan for Implementing Optional Parameters for Device Commands

This document outlines the plan to adapt the codebase to support optional parameters for device commands, as defined in the JSON configuration files (`config/devices/*.json`).

## 1. Configuration Schema Update

- **Introduce `params` Key:** Add a `params` key within each command definition object in the device JSON configuration files.
- **Parameter Definition Objects:** The `params` key will hold an array of objects, where each object defines a single parameter.
- **Parameter Object Fields:**
    - `name` (string): The parameter name.
    - `type` (string): Data type (e.g., "string", "integer", "float", "boolean"). Used for potential validation.
    - `required` (boolean): `true` if the parameter must be provided, `false` otherwise.
    - `default` (any, optional): The default value to use if the parameter is not provided and `required` is `false`.
    - `description` (string, optional): A human-readable description.

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
          { "name": "level", "type": "integer", "required": true, "description": "Brightness level 0-100" },
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
    2. Check if `cmd_config` defines a `params` array.
    3. **If `params` are defined:**
        - Assume the MQTT `payload` is a JSON string representing parameters (e.g., `'{"level": 80, "transition": 5}'`).
        - Parse the payload using `json.loads(payload)`.
        - Use a helper function (see Step 4) or inline logic to validate parsed parameters against the `cmd_config["params"]` definition (check required fields, apply defaults).
    4. **If `params` are NOT defined (or parsing fails/payload isn't JSON):**
        - Decide on handling: Treat raw payload as a single default param? Ignore? (Needs clarification based on command needs).
    5. Call `_execute_single_action` passing the *resolved* parameter dictionary.

- **`execute_action` (API/Direct Call):**
    1. Accepts `action` (string) and `params` (dict) as input.
    2. Find the corresponding `cmd_config` for the `action`.
    3. Retrieve the `params` definition from `cmd_config`.
    4. Use a helper function (see Step 4) or inline logic to create the final parameter dictionary:
        - Start with default values specified in `cmd_config["params"]`.
        - Override/add values from the `params` dictionary passed into `execute_action`.
    5. Validate the final dictionary: Ensure all `required: true` parameters have values. Optionally check types.
    6. Raise an error if validation fails.
    7. Call `_execute_single_action` passing the *validated, final* parameter dictionary.

## 3. Action Execution Refactoring

- **`_execute_single_action` Method:**
    - **Signature Change:** Modify the signature from `(self, action_name, action_config, payload)` to `async def _execute_single_action(self, action_name: str, params: Dict[str, Any])`.
    - **Functionality:**
        - Get the handler method using `_get_action_handler(action_name)`.
        - Call the handler, passing only the resolved `params` dictionary: `await handler(params=params)`.
        - Update `LastCommand` state in `self.state` using the resolved `params` dictionary.

- **Specific Action Handlers (e.g., `handle_power_on`, `handle_set_brightness`):**
    - **Signature Change:** Modify the signature of individual device action handlers to accept `self` and the resolved `params` dictionary: `async def handle_some_action(self, params: Dict[str, Any])`.
    - **Implementation:** These handlers will now directly use the values from the provided `params` dictionary.

## 4. Helper Function (Recommended)

- **Create a Method:** Implement a helper method within `BaseDevice`, such as `_resolve_and_validate_params`.
- **Signature:** `_resolve_and_validate_params(self, cmd_config: Dict, provided_params: Dict) -> Dict`
- **Functionality:**
    - Takes the command configuration (specifically the `params` definition part) and the input parameters (either parsed from MQTT payload or passed via `execute_action`).
    - Applies default values for optional parameters.
    - Validates that all required parameters are present.
    - Optionally performs type checking.
    - Returns the final, validated dictionary of parameters.
    - Raises a `ValueError` or similar exception if validation fails.
- **Usage:** Call this helper from both `handle_message` (after parsing the payload) and `execute_action`.

## Summary

This plan centralizes parameter definition in JSON, creates a unified processing pipeline for parameters from MQTT and direct calls, and ensures action handlers receive a consistent, validated set of parameters. 