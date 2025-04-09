# MQTT Web Service

A Python-based web service that acts as an MQTT client to manage multiple devices using a plugin-based architecture.

## Features

- FastAPI REST API for device management
- MQTT client for device communication
- Plugin-based architecture for device modules
- JSON configuration files
- Logging system

## Architecture

- **Web Service**: Built with FastAPI
- **MQTT Client**: Based on `asyncio-mqtt`
- **Device Modules**: Plugin-based system for device-specific functionality
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

## API Endpoints

- `GET /` - Service information
- `GET /system` - System information
- `POST /reload` - Reload configurations and devices
- `GET /devices` - List all devices
- `GET /devices/{device_name}` - Get information about a specific device
- `POST /publish` - Publish a message to an MQTT topic

## Creating Device Modules

1. Create a new Python file in the `devices/` directory
2. Implement two main functions:
   - `subscribe_topics(config)` - Returns a list of MQTT topics to subscribe to
   - `handle_message(topic, payload)` - Processes incoming MQTT messages

Example:
```python
def subscribe_topics(config):
    device_name = config.get('device_name', 'default')
    return [f"home/{device_name}/command", f"home/{device_name}/status"]

async def handle_message(topic, payload):
    # Process the message
    print(f"Received on {topic}: {payload}")
```

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
  "device_name": "example_device",
  "device_type": "example",
  "mqtt_topics": [
    "home/example/status",
    "home/example/command"
  ],
  "auth": {
    "username": "device_user",
    "password": "device_password"
  },
  "parameters": {
    "update_interval": 60,
    "threshold": 25.5
  }
}
```

## Deployment

For production deployment, it's recommended to:

1. Run behind an Nginx reverse proxy
2. Use a process manager like Supervisor or systemd
3. Set up proper authentication
4. Use environment variables for sensitive configuration

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