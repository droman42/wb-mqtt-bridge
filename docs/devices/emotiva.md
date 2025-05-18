# Emotiva XMC2 Device

The Emotiva XMC2 device integration supports controlling an Emotiva XMC-2 audio processor, including multi-zone functionality.

## Configuration

Sample configuration in `config/devices/emotiva_xmc2.json`:

```json
{
  "device_id": "processor",
  "device_name": "eMotiva XMC2 Processor",
  "mqtt_progress_topic": "/devices/processor/controls/progress",
  "device_class": "EMotivaXMC2",
  "config_class": "EmotivaXMC2DeviceConfig",
  "emotiva": {
    "host": "192.168.1.100",
    "mac": "AA:BB:CC:DD:EE:FF",
    "port": 7002,
    "update_interval": 60,
    "force_connect": false
  },
  "commands": {
    "power_on": {
      "action": "power_on",
      "topic": "/devices/processor/controls/power_on",
      "group": "power",
      "description": "Turn on the processor",
      "params": [
        { "name": "zone", "type": "integer", "required": false, "default": 1, "description": "Zone ID (1 for main, 2 for zone2)" }
      ]
    },
    "power_off": {
      "action": "power_off",
      "topic": "/devices/processor/controls/power_off",
      "group": "power",
      "description": "Turn off the processor",
      "params": [
        { "name": "zone", "type": "integer", "required": false, "default": 1, "description": "Zone ID (1 for main, 2 for zone2)" }
      ]
    },
    "zone2_on": {
      "action": "power_on",
      "topic": "/devices/processor/controls/zone2_on",
      "group": "power",
      "description": "Turn on zone 2",
      "params": [
        { "name": "zone", "type": "integer", "required": false, "default": 2, "description": "Zone ID (2 for zone2)" }
      ]
    },
    "zone2_off": {
      "action": "power_off",
      "topic": "/devices/processor/controls/zone2_off",
      "group": "power",
      "description": "Turn off zone 2",
      "params": [
        { "name": "zone", "type": "integer", "required": false, "default": 2, "description": "Zone ID (2 for zone2)" }
      ]
    },
    "set_input": {
      "action": "set_input",
      "topic": "/devices/processor/controls/set_input",
      "group": "inputs",
      "description": "Switch input source",
      "params": [
        { "name": "input", "type": "string", "required": true, "description": "Input name (hdmi1, hdmi2, etc.)" }
      ]
    },
    "set_volume": {
      "action": "set_volume",
      "topic": "/devices/processor/controls/volume",
      "group": "volume",
      "description": "Set the volume level",
      "params": [
        { "name": "level", "type": "range", "min": -96.0, "max": 0.0, "required": true, "description": "Volume level in dB (-96.0 to 0.0)" },
        { "name": "zone", "type": "integer", "required": false, "default": 1, "description": "Zone ID (1 for main, 2 for zone2)" }
      ]
    },
    "zone2_volume": {
      "action": "set_volume",
      "topic": "/devices/processor/controls/zone2_volume",
      "group": "volume",
      "description": "Set the zone 2 volume level",
      "params": [
        { "name": "level", "type": "range", "min": -96.0, "max": 0.0, "required": true, "description": "Volume level in dB (-96.0 to 0.0)" },
        { "name": "zone", "type": "integer", "required": false, "default": 2, "description": "Zone ID (2 for zone2)" }
      ]
    },
    "mute_toggle": {
      "action": "mute_toggle",
      "topic": "/devices/processor/controls/mute_toggle",
      "group": "volume",
      "description": "Toggle mute state",
      "params": [
        { "name": "zone", "type": "integer", "required": false, "default": 1, "description": "Zone ID (1 for main, 2 for zone2)" }
      ]
    },
    "zone2_mute_toggle": {
      "action": "mute_toggle",
      "topic": "/devices/processor/controls/zone2_mute_toggle",
      "group": "volume",
      "description": "Toggle zone 2 mute state",
      "params": [
        { "name": "zone", "type": "integer", "required": false, "default": 2, "description": "Zone ID (2 for zone2)" }
      ]
    }
  }
}
```

## Multi-Zone Support

The Emotiva XMC2 supports two zones, which can be controlled independently:

- **Zone 1 (Main)**: The primary home theater zone
- **Zone 2**: Secondary zone for audio in another room

For zone-specific commands, you can specify the zone using the `zone` parameter:
- `1` for the main zone (default)
- `2` for zone 2

## Available Commands

### Power Control

- **power_on**: Turn on the specified zone
  - Parameters:
    - `zone`: Zone ID (1 for main, 2 for zone2), default: 1
  - Example: `{"action": "power_on", "params": {"zone": 1}}`

- **power_off**: Turn off the specified zone
  - Parameters:
    - `zone`: Zone ID (1 for main, 2 for zone2), default: 1
  - Example: `{"action": "power_off", "params": {"zone": 2}}`

### Volume Control

- **set_volume**: Set volume level for the specified zone
  - Parameters:
    - `level`: Volume level in dB (-96.0 to 0.0)
    - `zone`: Zone ID (1 for main, 2 for zone2), default: 1
  - Example: `{"action": "set_volume", "params": {"level": -40.5, "zone": 1}}`

- **mute_toggle**: Toggle mute state for the specified zone
  - Parameters:
    - `zone`: Zone ID (1 for main, 2 for zone2), default: 1
  - Example: `{"action": "mute_toggle", "params": {"zone": 2}}`

### Input Selection

- **set_input**: Select an input source
  - Parameters:
    - `input`: Input name (hdmi1, hdmi2, optical1, etc.)
  - Example: `{"action": "set_input", "params": {"input": "hdmi1"}}`

## State Properties

The device state includes the following properties:

- `power`: Power state of the main zone (on/off/unknown)
- `zone2_power`: Power state of zone 2 (on/off/unknown)
- `volume`: Volume level of the main zone in dB
- `zone2_volume`: Volume level of zone 2 in dB
- `mute`: Mute state of the main zone (true/false)
- `zone2_mute`: Mute state of zone 2 (true/false)
- `input_source`: Currently selected input
- `audio_input`: Currently active audio input
- `video_input`: Currently active video input
- `audio_mode`: Current audio processing mode
- `audio_bitstream`: Current audio bitstream format
- `connected`: Connection status to the device
- `notifications`: Whether notifications are active
- `ip_address`: IP address of the device
- `mac_address`: MAC address of the device

## MQTT Topics

The device registers listeners on these MQTT topics based on the configuration:

- `/devices/processor/controls/power_on`: Turn on the main zone
- `/devices/processor/controls/power_off`: Turn off the main zone
- `/devices/processor/controls/zone2_on`: Turn on zone 2
- `/devices/processor/controls/zone2_off`: Turn off zone 2
- `/devices/processor/controls/volume`: Set volume for the main zone
- `/devices/processor/controls/zone2_volume`: Set volume for zone 2
- `/devices/processor/controls/mute_toggle`: Toggle mute for the main zone
- `/devices/processor/controls/zone2_mute_toggle`: Toggle mute for zone 2
- `/devices/processor/controls/set_input`: Set the input source

## API Examples

### REST API

```bash
# Power on the main zone
curl -X POST http://localhost:8000/devices/processor/action \
  -H "Content-Type: application/json" \
  -d '{"action": "power_on", "params": {"zone": 1}}'

# Set volume for zone 2
curl -X POST http://localhost:8000/devices/processor/action \
  -H "Content-Type: application/json" \
  -d '{"action": "set_volume", "params": {"level": -35.5, "zone": 2}}'

# Toggle mute for zone 2
curl -X POST http://localhost:8000/devices/processor/action \
  -H "Content-Type: application/json" \
  -d '{"action": "mute_toggle", "params": {"zone": 2}}'

# Change input source
curl -X POST http://localhost:8000/devices/processor/action \
  -H "Content-Type: application/json" \
  -d '{"action": "set_input", "params": {"input": "hdmi1"}}'
```

### MQTT

```bash
# Power on the main zone
mosquitto_pub -t "/devices/processor/controls/power_on" -m ""

# Power on zone 2 
mosquitto_pub -t "/devices/processor/controls/zone2_on" -m ""

# Set volume for the main zone to -35.5 dB
mosquitto_pub -t "/devices/processor/controls/volume" -m '{"level": -35.5, "zone": 1}'

# Set volume for zone 2 to -40 dB
mosquitto_pub -t "/devices/processor/controls/zone2_volume" -m '{"level": -40.0}'

# Toggle mute for the main zone
mosquitto_pub -t "/devices/processor/controls/mute_toggle" -m ""

# Toggle mute for zone 2
mosquitto_pub -t "/devices/processor/controls/zone2_mute_toggle" -m ""

# Set input to HDMI 1
mosquitto_pub -t "/devices/processor/controls/set_input" -m '{"input": "hdmi1"}'
``` 