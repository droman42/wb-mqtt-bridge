# Device Configuration System Documentation

## Overview

The device configuration system is designed to manage and validate device configurations for various types of devices in the WB-MQTT Bridge application. The system provides a flexible framework for defining device-specific configurations, processing commands, and loading device classes dynamically.

## Key Components

### 1. Base Device Configuration Classes

The base configuration structure is defined in `app/schemas.py`:

- `BaseDeviceConfig`: Abstract base class for all device configurations
- `BaseCommandConfig`: Abstract base class for command configurations
- Device-specific configurations (e.g., `LgTvDeviceConfig`, `AuralicDeviceConfig`, etc.)

### 2. Configuration Manager

The `ConfigManager` class in `app/config_manager.py` handles loading, validating, and processing device configurations.

### 3. Class Loader

The `app/class_loader.py` module provides utilities for dynamically loading device and configuration classes based on their names.

### 4. Validation System

The `app/validation.py` module contains functions for validating device configurations and ensuring they meet the required format.

## Configuration File Structure

### Device Configuration Files

Device configuration files are stored in the `config/devices/` directory and follow this structure:

```json
{
  "device_name": "Device Display Name",
  "device_id": "unique_device_id",
  "alias": "optional_alias",
  "device_class": "DeviceClassName",
  "config_class": "DeviceConfigClassName",
  
  // Device-specific configuration fields
  
  "commands": {
    "command_id": {
      "action": "action_name",
      "topic": "/devices/device_id/controls/action_name",
      "description": "Human readable description",
      "group": "command_group",
      // Optional command parameters
      "params": [
        {
          "name": "param_name",
          "type": "string|integer|float|boolean|range",
          "required": true|false,
          "description": "Parameter description"
        }
      ]
    }
  }
}
```

### Required Fields

Every device configuration file must include these fields:

- `device_name`: Human-readable name of the device
- `device_id`: Unique identifier for the device (must match the filename)
- `device_class`: Name of the device implementation class
- `config_class`: Name of the configuration class for this device type

### System Configuration

The system configuration is stored in `config/system.json` and defines the devices to be loaded by the application:

```json
{
  "devices": {
    "device_id": {
      "class": "DeviceClassName",
      "config_file": "device_id.json"
    }
  }
}
```

## Command Processing

Each device type has specific command processing logic implemented in its configuration class:

1. Base command processing happens in `BaseDeviceConfig.process_commands()`
2. Device-specific processing is implemented in each device configuration class
3. Commands are validated based on the device type's requirements

## Dynamic Class Loading

The system uses reflection to load device and configuration classes dynamically:

1. The `class_loader.py` module provides utilities for loading classes by name
2. Classes are loaded from their respective modules based on naming conventions
3. Type checking ensures that loaded classes inherit from the correct base classes

## Validation

The configuration validation process includes:

1. File structure validation: Ensuring required fields are present
2. Class validation: Verifying that specified classes exist and can be loaded
3. Device ID validation: Ensuring device IDs are unique and match filenames
4. Command validation: Checking that commands have the required properties

## How to Add a New Device Type

To add a new device type to the system:

1. Create a new device class that inherits from the appropriate base device class
2. Create a new configuration class in `app/schemas.py` that inherits from `BaseDeviceConfig`
3. Implement the required methods, especially `process_commands()`
4. Create a device configuration file in `config/devices/`
5. Add the device to `config/system.json`

## Testing

The `test_device_configs.py` script provides comprehensive testing for the device configuration system:

- Validates all configuration files
- Tests class and device mapping
- Validates command processing for each device type
- Generates a detailed report of the results

## Error Handling

The system includes robust error handling:

1. Validation errors are collected and reported, not just the first error
2. Configuration loading failures are handled gracefully
3. Class loading errors provide detailed information about what went wrong
4. Fallback mechanisms ensure backward compatibility

## Best Practices

When working with the device configuration system:

1. Always validate new configurations before deployment
2. Follow the naming conventions for device IDs and files
3. Implement device-specific command processing when needed
4. Keep device configurations separate from device implementation 