# MQTT Web Service

A Python-based web service that acts as an MQTT client to manage multiple devices using an object-oriented plugin-based architecture.

## Features

- FastAPI REST API for device management
- MQTT client for device communication
- Object-oriented device class architecture
- Plugin-based architecture for device modules
- JSON configuration files
- Logging system
- Support for various device types:
  - LG TV control
  - Broadlink RF devices (Kitchen Hood)
  - Wirenboard IR devices

## Architecture

- **Web Service**: Built with FastAPI
- **MQTT Client**: Based on `asyncio-mqtt`
- **Device Architecture**:
  - `BaseDevice` abstract class with common functionality
  - Device-specific implementations that inherit from BaseDevice
- **Configuration**: JSON files for system and device settings
- **Logging**: File-based logging

## Installation

1. Clone the repository:
```bash
git clone https://github.com/droman42/wb-mqtt-bridge.git
cd wb-mqtt-bridge
```

2. Create a virtual environment and install dependencies:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. Configure the application:
   - Edit `config/system.json` for MQTT broker settings
   - Add device configurations in `config/devices/`

## Running the Application

Start the web service:

```bash
python -m app.main
```

Or use uvicorn directly:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Device Management

The application supports various device types through the following architecture:

### BaseDevice Class

The `BaseDevice` class provides common functionality for all devices:
- Device initialization and configuration
- State management
- Common utility methods like `get_available_commands()`
- Abstract methods that must be implemented by device-specific classes

### Supported Device Types

1. **LG TV (lg_tv.py)**
   - LG webOS TV control via WebSocket connection
   - Commands for power, volume, app launching, etc.

2. **Broadlink Kitchen Hood (broadlink_kitchen_hood.py)**
   - Controls kitchen hood via Broadlink RF commands
   - Support for light and fan speed control

3. **Wirenboard IR Device (wirenboard_ir_device.py)**
   - IR device control through Wirenboard MQTT interface
   - Custom command mapping

## Creating New Device Implementations

To add support for a new device type:

1. Create a new Python file in the `devices/` directory
2. Create a class that inherits from `BaseDevice`
3. Implement the required abstract methods:
   - `async setup()` - Initialize the device
   - `async shutdown()` - Clean up device resources
   - `subscribe_topics()` - Return MQTT topics to subscribe to
   - `async handle_message(topic, payload)` - Process incoming MQTT messages

Example:
```python
from devices.base_device import BaseDevice
from typing import Dict, Any, List

class MyCustomDevice(BaseDevice):
    async def setup(self) -> bool:
        # Initialize device
        self.state = {
            "device_specific_state": None
        }
        return True
        
    async def shutdown(self) -> bool:
        # Clean up resources
        return True
        
    def subscribe_topics(self) -> List[str]:
        # Return MQTT topics to subscribe to
        return [f"home/{self.get_name()}/command"]
        
    async def handle_message(self, topic: str, payload: str):
        # Process incoming messages
        print(f"Received on {topic}: {payload}")
```

## API Endpoints

- `GET /` - Service information
- `GET /system` - System information
- `POST /reload` - Reload configurations and devices
- `GET /devices` - List all devices
- `GET /devices/{device_id}` - Get information about a specific device
- `POST /devices/{device_id}/action/{action}` - Execute device action
- `POST /publish` - Publish a message to an MQTT topic

## Configuration Files

### System Configuration (config/system.json)

```json
{
  "mqtt_broker": {
    "host": "localhost",
    "port": 1883,
    "client_id": "mqtt_web_service",
    "auth": {
      "username": "mqtt_user",
      "password": "mqtt_password"
    }
  },
  "web_service": {
    "host": "0.0.0.0",
    "port": 8000
  },
  "log_level": "INFO",
  "log_file": "logs/service.log"
}
```

### Device Configuration (config/devices/{device_name}.json)

```json
{
  "device_id": "example_device",
  "device_name": "Example Device",
  "device_type": "example",
  "commands": {
    "power_on": {
      "topic": "home/example/power",
      "rf_code": "base64_encoded_rf_code_here",
      "action": "power_on"
    },
    "power_off": {
      "topic": "home/example/power",
      "rf_code": "base64_encoded_rf_code_here", 
      "action": "power_off"
    }
  }
}
```

## Deployment

The project includes several deployment options:

1. **Docker**
   - Use the provided Dockerfile and docker-compose.yml
   - Run `docker_deploy.sh` or `docker-compose up -d`

2. **Local Deployment**
   - Run `deploy_local.sh` for a local deployment

3. **Remote Deployment**
   - Run `deploy_remote.sh` for remote server deployment

## License

MIT

# MQTT Sniffer

A simple utility to monitor all MQTT topic changes on a broker and log them to a file.

## Installation

1. Make sure you have Python 3.6+ installed
2. Install the required dependency:

```bash
pip install paho-mqtt
```

## Usage

Run the MQTT sniffer with default settings:

```bash
python mqtt_sniffer.py
```

This will connect to a local MQTT broker on port 1883 and log all topic changes to `mqtt_sniffer.log`.

### Command Line Options

```
  -h, --help            Show this help message and exit
  -b BROKER, --broker BROKER
                        MQTT broker address (default: localhost)
  -p PORT, --port PORT  MQTT broker port (default: 1883)
  -u USERNAME, --username USERNAME
                        MQTT broker username
  -P PASSWORD, --password PASSWORD
                        MQTT broker password
  -l LOG_FILE, --log-file LOG_FILE
                        Path to log file (default: mqtt_sniffer.log)
  -t TOPIC, --topic TOPIC
                        MQTT topic filter (default: # - all topics)
```

### Examples

Connect to a remote broker:
```bash
python mqtt_sniffer.py -b mqtt.example.com
```

Connect with authentication:
```bash
python mqtt_sniffer.py -u myuser -P mypassword
```

Log only specific topics:
```bash
python mqtt_sniffer.py -t "home/sensors/#"
```

Specify a custom log file:
```bash
python mqtt_sniffer.py -l my_mqtt_traffic.log
```

## Output Format

The log file contains entries in the following format:
```
2023-06-01 12:34:56.789 - INFO - Topic: home/temperature | Payload: 22.5
```

Each entry includes a timestamp, log level, topic name, and message payload. 