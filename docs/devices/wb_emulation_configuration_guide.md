# Wirenboard Virtual Device Emulation Configuration Guide

## Overview

This guide explains how to configure devices for optimal Wirenboard (WB) virtual device emulation. With the completion of Configuration Migration Phase C, all devices now use auto-generated MQTT topics that automatically follow WB conventions.

## Basic Configuration Structure

All device configurations now use a simplified structure without explicit topic fields:

```json
{
  "device_name": "Living Room TV", 
  "device_id": "living_room_tv",
  "device_class": "LgTv",
  "config_class": "LgTvConfig",
  "enable_wb_emulation": true,
  "commands": {
    "power_on": {
      "action": "power_on",
      "description": "Power On",
      "group": "power"
    },
    "set_volume": {
      "action": "set_volume", 
      "description": "Set Volume",
      "group": "audio",
      "params": [
        {
          "name": "level",
          "type": "range",
          "min": 0,
          "max": 100,
          "required": true,
          "description": "Volume level (0-100)"
        }
      ]
    }
  }
}
```

## Auto-Generated Topics

All MQTT topics are now automatically generated following WB conventions:

- **Command Topics**: `/devices/{device_id}/controls/{command_name}/on`
- **State Topics**: `/devices/{device_id}/controls/{command_name}` 
- **Meta Topics**: `/devices/{device_id}/controls/{command_name}/meta`
- **Device Meta**: `/devices/{device_id}/meta`

### Examples:
```
/devices/living_room_tv/controls/power_on/on      # WB sends commands here
/devices/living_room_tv/controls/power_on         # Current state
/devices/living_room_tv/controls/power_on/meta    # Control metadata
/devices/living_room_tv/controls/set_volume/on    # Volume commands
/devices/living_room_tv/controls/set_volume       # Current volume
/devices/living_room_tv/meta                      # Device metadata
```

## WB Control Configuration

### Automatic Control Detection

The system automatically detects control types based on command names:

| Command Pattern | WB Control Type | Example Commands |
|----------------|-----------------|------------------|
| `power_on`, `power_off` | `pushbutton` | `power_on`, `power_off` |
| `*_volume*`, `set_volume` | `range` | `set_volume`, `volume_up` |
| `mute*`, `*_mute` | `switch` | `mute`, `mute_toggle` |
| `get_*`, `list_*` | `text` (readonly) | `get_status`, `list_apps` |
| `set_*` | `range` | `set_input`, `set_brightness` |
| Default | `pushbutton` | Most action commands |

### Custom WB Controls

For fine-grained control over WB interface appearance:

```json
{
  "device_id": "living_room_tv",
  "enable_wb_emulation": true,
  "wb_controls": {
    "set_volume": {
      "type": "range",
      "min": 0,
      "max": 100,
      "units": "%",
      "title": {"en": "Volume", "ru": "Громкость"},
      "order": 10
    },
    "power_on": {
      "type": "pushbutton", 
      "title": {"en": "Power On"},
      "order": 1
    },
    "get_status": {
      "type": "text",
      "readonly": true,
      "title": {"en": "Status"},
      "order": 50
    }
  }
}
```

### WB Control Types

| Type | Description | Properties | UI Appearance |
|------|-------------|------------|---------------|
| `switch` | Binary toggle | None | Toggle switch |
| `range` | Numeric slider | `min`, `max`, `units` | Slider |
| `value` | Read-only number | `units` | Numeric display |
| `text` | Text display | `readonly` | Text field |
| `pushbutton` | Momentary action | None | Button |

## State Synchronization

### Automatic State Mapping

The system automatically maps device state to WB controls:

```json
{
  "wb_state_mappings": {
    "power": "power_state",          # Device power → power_state control
    "volume": "set_volume",          # Device volume → set_volume control  
    "mute": "mute_state",           # Device mute → mute_state control
    "connected": "connection_status" # Device connected → connection_status control
  }
}
```

### State Value Conversion

- **Boolean**: `true` → `"1"`, `false` → `"0"`
- **Numbers**: Converted to strings with appropriate precision
- **Enums**: Mapped to string values
- **Objects**: JSON serialized for complex states

## Advanced Configuration

### Enabling/Disabling WB Emulation

```json
{
  "enable_wb_emulation": true   # Enable (default)
  // OR
  "enable_wb_emulation": false  # Disable for this device
}
```

### Control Ordering

Controls appear in WB interface based on `order` values:

```json
{
  "wb_controls": {
    "power_on": {"order": 1},      # Appears first
    "set_volume": {"order": 10},   # Appears second
    "get_status": {"order": 50}    # Appears last
  }
}
```

### Localization

Support multiple languages in control titles:

```json
{
  "wb_controls": {
    "set_volume": {
      "title": {
        "en": "Volume", 
        "ru": "Громкость",
        "de": "Lautstärke"
      }
    }
  }
}
```

## Device Type Examples

### IR-Controlled Device (TV, Amplifier)

```json
{
  "device_name": "Living Room TV",
  "device_id": "living_room_tv", 
  "device_class": "LgTv",
  "config_class": "LgTvConfig",
  "enable_wb_emulation": true,
  "commands": {
    "power_on": {
      "action": "power_on",
      "description": "Power On",
      "group": "power"
    },
    "volume_up": {
      "action": "volume_up",
      "description": "Volume Up", 
      "group": "audio"
    },
    "set_input_source": {
      "action": "set_input_source",
      "description": "Set Input Source",
      "group": "inputs",
      "params": [
        {
          "name": "source",
          "type": "string",
          "required": true,
          "description": "Input source name"
        }
      ]
    }
  },
  "wb_controls": {
    "set_input_source": {
      "type": "text",
      "title": {"en": "Input Source"},
      "order": 20
    }
  }
}
```

### Network-Controlled Device (Processor, Streamer)

```json
{
  "device_name": "Emotiva Processor",
  "device_id": "processor",
  "device_class": "EMotivaXMC2", 
  "config_class": "EmotivaXMC2DeviceConfig",
  "enable_wb_emulation": true,
  "emotiva": {
    "host": "192.168.1.100",
    "port": 7002
  },
  "commands": {
    "power_on": {
      "action": "power_on",
      "group": "power",
      "description": "Turn on",
      "params": [
        {
          "name": "zone", 
          "type": "integer",
          "required": true,
          "default": 1,
          "min": 1,
          "max": 2,
          "description": "Zone ID"
        }
      ]
    },
    "set_volume": {
      "action": "set_volume",
      "group": "audio", 
      "description": "Set volume",
      "params": [
        {
          "name": "level",
          "type": "range", 
          "min": -96.0,
          "max": 0.0,
          "required": true,
          "description": "Volume in dB"
        }
      ]
    }
  },
  "wb_controls": {
    "set_volume": {
      "type": "range",
      "min": -96,
      "max": 0,
      "units": "dB",
      "title": {"en": "Volume"},
      "order": 10
    }
  }
}
```

### Wirenboard IR Device

```json
{
  "device_name": "Kitchen Hood",
  "device_id": "kitchen_hood",
  "device_class": "BroadlinkKitchenHood",
  "config_class": "BroadlinkKitchenHoodConfig", 
  "enable_wb_emulation": true,
  "commands": {
    "set_light": {
      "action": "set_light",
      "description": "Control light",
      "params": [
        {
          "name": "state",
          "type": "string", 
          "required": true,
          "description": "Light state - 'on' or 'off'"
        }
      ]
    },
    "set_speed": {
      "action": "set_speed",
      "description": "Control fan speed",
      "params": [
        {
          "name": "level",
          "type": "range",
          "min": 0,
          "max": 4,
          "required": true,
          "description": "Fan speed level"
        }
      ]
    }
  },
  "wb_controls": {
    "set_light": {
      "type": "switch",
      "title": {"en": "Light"},
      "order": 1
    },
    "set_speed": {
      "type": "range", 
      "min": 0,
      "max": 4,
      "title": {"en": "Fan Speed"},
      "order": 2
    }
  }
}
```

## Troubleshooting

### Device Not Appearing in WB Interface

1. **Check WB emulation is enabled**:
   ```json
   {"enable_wb_emulation": true}
   ```

2. **Verify device initialization**: Check logs for WB setup messages:
   ```
   INFO: WB virtual device emulation enabled for living_room_tv
   ```

3. **Check MQTT broker connectivity**: Ensure MQTT client is connected

4. **Validate configuration**: Run configuration validation:
   ```bash
   python -m pytest tests/test_config_manager.py -v
   ```

### Controls Not Working

1. **Check topic subscription**: Verify device subscribes to command topics
2. **Test MQTT manually**: Send test message to command topic:
   ```bash
   mosquitto_pub -h localhost -t "/devices/living_room_tv/controls/power_on/on" -m "1"
   ```
3. **Review handler registration**: Ensure command handlers are properly registered

### State Not Updating

1. **Check state mappings**: Verify `wb_state_mappings` configuration
2. **Test state publishing**: Check if state updates trigger MQTT publications
3. **Verify retained messages**: Ensure state topics use `retain=True`

### Configuration Validation Errors

1. **Control validation**: Check `wb_controls` configuration format
2. **Parameter validation**: Verify command parameter definitions
3. **Handler validation**: Ensure all referenced handlers exist

## Migration from Explicit Topics

**Note**: As of Configuration Migration Phase C, explicit topics are no longer supported. All topics are auto-generated.

### Before (Legacy Configuration):
```json
{
  "commands": {
    "power_on": {
      "action": "power_on",
      "topic": "/devices/living_room_tv/controls/power_on",  // ❌ Removed
      "description": "Power On"
    }
  }
}
```

### After (Current Configuration):
```json
{
  "commands": {
    "power_on": {
      "action": "power_on",
      "description": "Power On"  // ✅ Auto-generated: /devices/living_room_tv/controls/power_on
    }
  }
}
```

### Benefits of Auto-Generated Topics:

- ✅ **Cleaner Configuration**: Shorter, more maintainable files
- ✅ **WB Compliance**: Automatic adherence to WB conventions  
- ✅ **Consistency**: Uniform topic structure across all devices
- ✅ **Error Prevention**: No topic typos or mismatches
- ✅ **Future-Proof**: Ready for WB protocol updates

## Best Practices

### Configuration Organization

1. **Group Related Commands**: Use `group` field to organize commands
2. **Descriptive Names**: Use clear, descriptive command and parameter names  
3. **Consistent Naming**: Follow consistent naming patterns across devices
4. **Document Parameters**: Provide clear parameter descriptions

### WB Control Design

1. **Logical Ordering**: Order controls by importance and usage frequency
2. **Appropriate Types**: Choose correct control types for better UX
3. **Clear Titles**: Use descriptive, localized control titles
4. **Sensible Ranges**: Set appropriate min/max values for range controls

### State Management

1. **Map Important State**: Focus on state that users need to see
2. **Update Frequently**: Ensure state updates reflect device changes
3. **Handle Offline**: Properly handle device offline states
4. **Validate Values**: Validate state values before publishing

### Testing

1. **Test WB Interface**: Verify controls work in WB web interface
2. **Test State Sync**: Ensure state changes reflect in WB
3. **Test Offline/Online**: Verify offline detection works  
4. **Load Testing**: Test with multiple devices and frequent updates

This configuration approach ensures optimal integration with Wirenboard systems while maintaining clean, maintainable device configurations. 