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
    4. **If `params` are NOT defined (or parsing fails/payload isn't JSON):**
        - Decide on handling: Treat raw payload as a single default param? Ignore? (Needs clarification based on command needs).
    5. Call `_execute_single_action` passing the *resolved* parameter dictionary.

- **`execute_action` (API/Direct Call):**
    1. Accepts `action` (string) and `params` (dict) as input.
    2. Find the corresponding `cmd_config` for the `action`.
    3. Retrieve the `params` definition from `cmd_config`. *If the `params` key is missing, treat it as an empty list.*
    4. Use a helper function (see Step 4) or inline logic to create the final parameter dictionary:
        - Start with default values specified in `cmd_config["params"]` (if any).
        - Override/add values from the `params` dictionary passed into `execute_action`.
    5. Validate the final dictionary: Ensure all `required: true` parameters have values. Optionally check types.
    6. Raise an error if validation fails.
    7. Call `_execute_single_action` passing the *validated, final* parameter dictionary.

## 3. Action Execution Refactoring

- **`_execute_single_action` Method:**
    - **Signature Change:** Modify the signature from `(self, action_name, action_config, payload)` to `async def _execute_single_action(self, action_name: str, cmd_config: Dict[str, Any], params: Dict[str, Any])`.
    - **Functionality:**
        - Retrieve the full command configuration (`cmd_config`) for the given `action_name`.
        - Resolve and validate parameters (`params`) using the helper function or inline logic, based on `cmd_config['params']` and the input parameters.
        - Get the handler method using `_get_action_handler(action_name)`.
        - Call the handler, passing both the command configuration and the resolved parameters: `await handler(cmd_config=cmd_config, params=params)`.
        - Update `LastCommand` state in `self.state` using the resolved `params` dictionary and potentially `action_name`.

- **Specific Action Handlers (e.g., `handle_power_on`, `handle_set_brightness`):**
    - **Signature Change:** Modify the signature of individual device action handlers to accept `self`, the command config (`cmd_config`), and the resolved `params` dictionary: `async def handle_some_action(self, cmd_config: Dict[str, Any], params: Dict[str, Any])`.
    - **Implementation:** These handlers will now use values from the provided `params` dictionary for dynamic inputs and can access static configuration (like RF codes, topics, location, etc.) from the `cmd_config` dictionary.

## 4. Helper Function (Recommended)

- **Create a Method:** Implement a helper method within `BaseDevice`, such as `_resolve_and_validate_params`.
- **Signature:** `_resolve_and_validate_params(self, cmd_config: Dict, provided_params: Dict) -> Dict`
- **Functionality:**
    - Takes the command configuration (specifically the `params` definition part) and the input parameters (either parsed from MQTT payload or passed via `execute_action`).
    - Applies default values for optional parameters.
    - Validates that all required parameters are present.
    - Optionally performs type checking (including checking `min`/`max` for `range` types).
    - Returns the final, validated dictionary of parameters.
    - Raises a `ValueError` or similar exception if validation fails.
- **Usage:** Call this helper from both `handle_message` (after parsing the payload) and `execute_action`.

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
            - Change signature to accept `self` and `params: Dict[str, Any]`.
            - Extract the parameter value (e.g., `state = params["state"]` or `level = params["level"]`).
            - Convert the parameter value to a string if necessary (for the `speed` map lookup).
            - Look up the correct RF code in the loaded `rf_codes` map using the parameter value.
            - Send the RF code using `_send_rf_code`.
            - Update the device state based on the parameter value.

This adaptation aligns the kitchen hood with the general parameter handling mechanism while accommodating its specific RF code mapping requirement.

## Summary

This plan centralizes parameter definition in JSON, creates a unified processing pipeline for parameters from MQTT and direct calls, and ensures action handlers receive a consistent, validated set of parameters. 