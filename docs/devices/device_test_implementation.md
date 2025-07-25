# Device Function Test Script — Implementation Plan

## Deep Code & Config Analysis

### 1. Device Class Loading
- **Mapping**: `config/system.json` maps device IDs to class names and config files.
- **ConfigManager** (`app/config_manager.py`): Loads system and device configs, exposes device class and config info.
- **DeviceManager** (`app/device_manager.py`): Dynamically loads device classes from `devices/`, instantiates them with config and MQTT client.
- **BaseDevice** (`devices/base_device.py`): All device classes inherit from this; provides command discovery, state, and action execution.

### 2. Command Discovery & Grouping
- **Device Config**: Each device config (e.g., `config/devices/lg_tv_living.json`) has a `commands` section.
- **Command Structure**: Each command has properties like `action`, `topic`, `description`, `group`, and `position`.
- **Grouping**: The `group` property is used to group commands (e.g., `power`, `volume`, `menu`).
- **Power Commands**: Identified by `group: "power"` or by name (e.g., `power`, `power_on`, `power_off`).

### 3. Parameter Handling
- **Schemas**: Command parameters are described in Pydantic models in `app/schemas.py`.
- **REST**: Endpoints in `app/main.py` expect parameters matching these schemas.
- **Prompting**: The script will need to prompt the user for required parameters for each command, using the schema as a guide.

### 4. REST & MQTT Execution
- **REST**: Endpoints for device actions are in `app/main.py` (e.g., `/devices/{device_id}/action`).
- **MQTT**: Broker info and auth in `config/system.json`; topics per command in device config.
- **Existing Classes**: MQTT and REST logic is encapsulated in existing classes (`MQTTClient`, device classes).

### 5. Device State
- **Standard Function**: `BaseDevice.get_current_state()` returns the current device state as a dict.
- **State Schema**: State is validated/structured using Pydantic models in `app/schemas.py`.

### 6. Logging
- **Requirement**: Log to stdout before and after each command, including parameters, result, errors, and device state.

### 7. Error Handling
- **Continue on Error**: If a command fails, log the error and continue with the next command.

---

## Implementation Plan

### 1. Script Setup
- **Location**: Place script in `tests/` folder.
- **Arguments**: Parse `--config` and `--mode` (rest/mqtt/both) from command line.

### 2. Configuration Loading
- Use `ConfigManager` to load `system.json` and device config.
- Determine device class and config file from `system.json`.
- Load device config from `config/devices/`.

### 3. Device Class Instantiation
- Use `DeviceManager` to dynamically load device classes.
- Instantiate the device class with config and (if needed) MQTT client.

### 4. Command Discovery & Grouping
- Extract `commands` from device config.
- Group commands by `group` property.
- Identify power command(s):
  - If only one, use for both ON and OFF.
  - If separate, use accordingly.

### 5. Test Execution Order
- Start with power ON.
- Execute all other commands, grouped (excluding `power`).
- End with power OFF.

### 6. Parameter Prompting
- For each command, determine required parameters from Pydantic schemas in `app/schemas.py`.
- Prompt the user for each required parameter (with type and description if available).

### 7. Command Execution
- For each command:
  - Log the command about to be executed, with parameters.
  - Execute via REST or MQTT:
    - **REST**: Call `/devices/{device_id}/action` with action and parameters.
    - **MQTT**: Use topic and payload as defined in command config; use `MQTTClient` for sending.
  - Log the result (success/failure, response, errors).
  - Call `get_current_state()` on the device and log the state.

### 8. Error Handling
- If a command fails, log the error and continue with the next command.

### 9. Logging
- Log all actions, parameters, results, errors, and device state to stdout.

### 10. Extensibility
- Design script so that output format (e.g., JSON/HTML) can be added later.
- Consider modularizing parameter prompting and command execution for future parallelization or CI integration.

---

### Key Code/Config Touchpoints
- `config/system.json`: Device class mapping, MQTT broker/auth
- `config/devices/*.json`: Device commands, topics, groups
- `app/config_manager.py`: Config loading
- `app/device_manager.py`: Device class loading/instantiation
- `devices/base_device.py`: Command discovery, state, action execution
- `app/schemas.py`: Parameter and state schemas
- `app/main.py`: REST endpoints

---

**Review this plan before implementation. No code will be written until you approve.** 