# Scenario System Documentation

## Overview

The scenario system provides a way to automate common device configurations and state transitions. Each scenario represents a predefined setup for a specific activity or environment, like "Movie Night", "Gaming", or "Home Office".

## Scenario Definition

A scenario is defined by a JSON configuration file with the following structure:

```json
{
  "scenario_id": "unique_identifier",
  "name": "Human-readable name",
  "description": "Detailed description of the scenario",
  "room_id": "room_identifier",
  "roles": {
    "role1": "device_id1",
    "role2": "device_id2"
  },
  "devices": [
    "device_id1",
    "device_id2",
    "device_id3"
  ],
  "startup_sequence": [
    {
      "device": "device_id1",
      "command": "power_on",
      "params": {},
      "condition": "device.power != True",
      "delay_after_ms": 1000
    },
    {
      "device": "device_id2",
      "command": "set_input",
      "params": {"input": "hdmi1"},
      "condition": "device.input != 'hdmi1'"
    }
  ],
  "shutdown_sequence": [
    {
      "device": "device_id1",
      "command": "power_off",
      "params": {},
      "condition": "device.power == True",
      "delay_after_ms": 500
    },
    {
      "device": "device_id2",
      "command": "power_off",
      "params": {},
      "condition": "device.power == True"
    }
  ],
  "manual_instructions": {
    "startup": "Step-by-step instructions for manual startup",
    "shutdown": "Step-by-step instructions for manual shutdown"
  }
}
```

### Key Components

1. **Basic Information**: 
   - `scenario_id`: Unique identifier for the scenario
   - `name`: Human-readable name for display
   - `description`: Detailed description of the scenario's purpose
   - `room_id`: Associated room identifier

2. **Roles**:
   - Maps functional roles to specific device IDs
   - Defines the purpose of each device in the scenario

3. **Devices**:
   - Lists all devices used in the scenario
   - A simple array of device IDs
   - Device capabilities are sourced from the DeviceManager at runtime

4. **Startup Sequence**:
   - List of commands to execute when activating the scenario
   - Each command includes device, command name, parameters, and optional conditions/delays

5. **Shutdown Sequence**:
   - List of commands to execute when deactivating the scenario
   - Similar structure to startup sequence
   - System automatically detects power commands and handles transitions intelligently

6. **Manual Instructions**:
   - Human-readable instructions for manual operation

## Command Structure

Each command in a sequence has the following properties:

```json
{
  "device": "device_id",         // ID of the target device
  "command": "command_name",     // Name of the command to execute
  "params": {},                  // Parameters for the command
  "condition": "expression",     // Optional condition to evaluate
  "delay_after_ms": 1000         // Optional delay after execution
}
```

### Conditions

Conditions allow for conditional execution of commands based on the current state of devices. This helps avoid unnecessary operations and improves transition efficiency.

The condition is a string expression that evaluates to a boolean value. The expression can reference:

- `device`: The current state of the target device
- Standard Python comparison operators and logical operators

Examples:
- `"condition": "device.power == True"`
- `"condition": "device.input != 'hdmi1'"`
- `"condition": "device.volume < 50"`

## Smart Transitions

The system includes intelligent transition logic that:

1. Detects power commands (power_on, power_off, etc.)
2. Skips unnecessary power cycling for devices shared between scenarios
3. Optimizes the transition sequence based on the destination scenario

This significantly improves the user experience by providing seamless transitions between scenarios.

## Example Scenarios

See the [example.json](../config/scenarios/example.json) file for a complete reference implementation demonstrating best practices.

## Managing Scenarios

Scenarios are managed by the `ScenarioManager` class, which provides the following functionality:

- Loading scenario definitions from configuration files
- Activating and deactivating scenarios
- Managing transitions between scenarios
- Executing command sequences

## Migration From Previous Format

If upgrading from a previous version, please see the [Scenario System Upgrade Guide](scenario_upgrade_guide.md) for details on migrating existing configurations. 