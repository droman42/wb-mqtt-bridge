# Parameter Configuration Examples

This document provides examples of using parameters in device command definitions. See `optional_params.md` for the full implementation plan.

## Basic Parameter Definition

Parameters are defined in the device configuration JSON as an array of parameter objects under the `params` key of a command:

```json
{
  "commands": {
    "setBrightness": {
      "action": "set_brightness",
      "topic": "/devices/light/set",
      "description": "Set light brightness and optional transition",
      "params": [
        {
          "name": "level",
          "type": "range",
          "min": 0,
          "max": 100,
          "required": true,
          "description": "Brightness level 0-100"
        },
        {
          "name": "transition",
          "type": "integer",
          "required": false,
          "default": 0,
          "description": "Transition time in seconds"
        }
      ]
    }
  }
}
```

## Parameter Data Types

The system supports the following parameter types:

- **string**: Text values
- **integer**: Whole numbers
- **float**: Decimal numbers
- **boolean**: True/false values
- **range**: Numeric values within a specified range (validates min/max)

### String Parameter Example

```json
{
  "name": "mode",
  "type": "string",
  "required": true,
  "description": "Operating mode (e.g., 'normal', 'eco', 'boost')"
}
```

### Integer Parameter Example

```json
{
  "name": "channel",
  "type": "integer",
  "required": true,
  "description": "TV channel number"
}
```

### Float Parameter Example

```json
{
  "name": "temperature",
  "type": "float",
  "required": true,
  "description": "Target temperature in Celsius"
}
```

### Boolean Parameter Example

```json
{
  "name": "enabled",
  "type": "boolean",
  "required": true,
  "description": "Whether the feature is enabled"
}
```

### Range Parameter Example

```json
{
  "name": "volume",
  "type": "range",
  "min": 0,
  "max": 100,
  "required": true,
  "description": "Volume level (0-100)"
}
```

## Optional Parameters with Default Values

Parameters can be made optional by setting `required: false`. When doing so, you should typically provide a `default` value:

```json
{
  "name": "speed",
  "type": "integer",
  "required": false,
  "default": 1,
  "description": "Fan speed (default: 1)"
}
```

## Real-World Examples

### TV Input Selection

```json
{
  "commands": {
    "setInput": {
      "action": "set_input",
      "topic": "/devices/tv/input",
      "description": "Change TV input source",
      "params": [
        {
          "name": "source",
          "type": "string",
          "required": true,
          "description": "Input source name (e.g., 'HDMI1', 'HDMI2', 'TV')"
        },
        {
          "name": "wait_time",
          "type": "integer",
          "required": false,
          "default": 1000,
          "description": "Time to wait after changing input (in ms)"
        }
      ]
    }
  }
}
```

### Thermostat Control

```json
{
  "commands": {
    "setTargetTemperature": {
      "action": "set_target_temperature",
      "topic": "/devices/thermostat/target",
      "description": "Set target temperature",
      "params": [
        {
          "name": "temperature",
          "type": "range",
          "min": 10,
          "max": 30,
          "required": true,
          "description": "Target temperature in Celsius"
        },
        {
          "name": "mode",
          "type": "string",
          "required": false,
          "default": "auto",
          "description": "Operating mode (auto, heat, cool)"
        }
      ]
    }
  }
}
```

### Light Control with Color

```json
{
  "commands": {
    "setLight": {
      "action": "set_light",
      "topic": "/devices/light/set",
      "description": "Control light properties",
      "params": [
        {
          "name": "state",
          "type": "boolean",
          "required": true,
          "description": "Light on/off state"
        },
        {
          "name": "brightness",
          "type": "range",
          "min": 0,
          "max": 100,
          "required": false,
          "default": 100,
          "description": "Brightness level (0-100)"
        },
        {
          "name": "color_temp",
          "type": "range",
          "min": 2000,
          "max": 6500,
          "required": false,
          "default": 4000,
          "description": "Color temperature in Kelvin"
        }
      ]
    }
  }
}
```

## Parameter Validation

Parameters are validated according to their type and constraints:

- **Required parameters** must be provided or an error is raised
- **Range parameters** are checked against min/max values
- **Type validation** ensures values match their declared type

### Error Handling

Common validation errors include:

- Missing required parameter
- Value out of range
- Type conversion error (e.g., string that can't be converted to number)

The validation process will throw a `ValueError` with a descriptive message when validation fails. 