# Device Function Test Script Specification

## Overview
This document specifies a Python-based test script for automated functional testing of devices managed by the MQTT Web Service. The script will:
- Take a device configuration as input
- Test all device functions by executing all available commands
- Support both REST API and MQTT interfaces
- Log all actions, results, and device states

## Goals
- Ensure all device commands work as expected via both REST and MQTT
- Provide a repeatable, automated way to validate device integrations
- Log detailed results for troubleshooting and future reporting

## Architecture
- **Script Location**: `tests/` folder
- **Language**: Python (reuses existing classes and infrastructure)
- **Inputs**:
  - `--config <path>`: Path to device config file (e.g., `config/devices/device1.json`)
  - `--mode <rest|mqtt|both>`: Interface to use for command execution
- **Configuration**:
  - Uses `config/system.json` for device class mapping and MQTT broker/auth info
  - Device configs in `config/devices/`
  - Loads device class using loader in `app/` (see `app/main.py`)

## Test Flow
1. **Load device class** using the provided config
2. **Discover all available commands** from the config's `commands` section
3. **Group commands** by their `group` property
4. **Identify power command(s)**:
    - If only one power command, use it for both ON (start) and OFF (end)
    - If separate ON/OFF, use accordingly
5. **Sort and execute commands**:
    - Start with power ON
    - Execute all other commands, grouped (excluding `power`)
    - End with power OFF
6. **For each command**:
    - Announce the command about to be executed (log)
    - Prompt the user for required parameters (based on Pydantic schemas in `app/schemas.py`)
    - Execute via selected interface (REST or MQTT)
    - Log result (success/failure, response, errors)
    - Check and log device state after execution (using standard function from `BaseDevice`)
    - On error: log and continue

## Command Execution
- **REST**: Uses endpoints and parameter schemas from `app/main.py` and `app/schemas.py`
- **MQTT**: Uses broker/auth info from `config/system.json` and existing classes in `app/`
- **Sequential execution**: All commands are executed one after another
- **No mocking**: Script interacts with real devices/services
- **Authentication**: Uses info from `config/system.json` and existing class functionality

## Logging
- Logs to stdout:
  - For each command: name, group, parameters, execution result, response, errors, and device state after execution
- (Future: Option to output JSON/HTML reports)

## Future Enhancements
- Add support for structured (JSON/HTML) reports
- Parallelize tests for independent command groups
- Integrate with CI/CD pipelines
- Add support for test parameter presets

---
This specification is the basis for the implementation plan and script development. 