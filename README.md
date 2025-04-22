# MQTT Web Service

A Python-based web service that acts as an MQTT client to manage multiple devices using an object-oriented plugin-based architecture.

## Features

- FastAPI REST API for device management
- MQTT client for device communication
- Object-oriented device class architecture
- Plugin-based architecture for device modules
- JSON configuration files
- Logging system
- Action Groups for organizing device functions
- Support for various device types:
  - LG TV control
  - Broadlink RF devices (Kitchen Hood)
  - Wirenboard IR devices
  - Revox A77 Reel-to-Reel tape recorder
  - **eMotiva XMC2 Device (emotiva_xmc2.py)**
    - Manages eMotiva XMC2 processor device
    - Supports power on/off and Zone 2 power management
    - Handles notifications for power, volume, input, and more
    - Maintains device state including power and source status
    - Logs errors and updates state with error messages

## Architecture

- **Web Service**: Built with FastAPI, fully Pydantic-conformant
- **MQTT Client**: Based on `aiomqtt`
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
   - Edit `.env` for environment variables
   - Edit `config/system.json` for MQTT broker settings
   - Add device configurations in `config/devices/`

## Docker Deployment

The application can be deployed using Docker on various platforms including Wirenboard 7 (ARMv7 architecture).

### Basic Docker Deployment

1. Clone the repository and local dependencies:
```bash
git clone https://github.com/droman42/wb-mqtt-bridge.git
cd wb-mqtt-bridge
./docker_deploy.sh --deps
```

2. Configure the application:
```bash
# Edit .env file with your settings
nano .env
# Create your device configurations
mkdir -p config/devices
```

3. Build and start the Docker containers:
```bash
./docker_deploy.sh --build
```

4. To stop the containers:
```bash
./docker_deploy.sh --down
```

5. To restart the containers:
```bash
./docker_deploy.sh --restart
```

The web service will be available at http://localhost:8000 (API) and http://localhost:8081 (Nginx frontend).

### Wirenboard 7 Deployment

The application supports deployment to Wirenboard 7 controllers, which use ARMv7 architecture and Debian Bullseye.

#### Option 1: Direct Build on Wirenboard 7

If you're running the script directly on your Wirenboard 7:

```bash
git clone https://github.com/droman42/wb-mqtt-bridge.git
cd wb-mqtt-bridge
./docker_deploy.sh --deps
./docker_deploy.sh --build
```

#### Option 2: Cross-Platform Build and Transfer

If you're building on a different architecture (e.g., x86_64/amd64) and deploying to Wirenboard 7:

1. **Prerequisites**:
   - Docker with Buildx support
   - SSH access to your Wirenboard 7 device

2. **Build, save, and transfer in one step**:
```bash
# Replace 192.168.1.100 with your Wirenboard's IP address
./docker_deploy.sh -b --save --transfer 192.168.1.100
```

3. **Or build and save for later transfer**:
```bash
# Build and save images to ./images directory
./docker_deploy.sh -b --save ./images

# Later transfer the saved images
./docker_deploy.sh --transfer 192.168.1.100
```

The script will:
- Detect the need for cross-compilation
- Set up ARM emulation using QEMU
- Build ARM-compatible Docker images
- Package the images and configuration files
- Transfer everything to your Wirenboard device
- Set up and start the containers on the remote device

The web service will be available at http://wirenboard-ip:8081 after deployment.

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
- Action grouping and indexing
- Fixed sorting order for actions within groups
- Abstract methods that must be implemented by device-specific classes

### Action Groups

The system organizes device actions into functional groups for easier management and display:

- **Group Definition**: Groups are defined centrally in the `system.json` file
- **Default Group**: Actions not assigned to any group are automatically placed in a "default" group
- **Group API**: Access device actions by group through dedicated API endpoints
- **Fixed Sorting**: Actions within groups maintain the order defined in configuration files

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

4. **Revox A77 Reel-to-Reel (revox_a77_reel_to_reel.py)**
   - Control for Revox A77 tape recorder
   - Support for transport controls and tape operations

5. **eMotiva XMC2 Device (emotiva_xmc2.py)**
   - Manages eMotiva XMC2 processor device
   - Supports power on/off and Zone 2 power management
   - Handles notifications for power, volume, input, and more
   - Maintains device state including power and source status
   - Logs errors and updates state with error messages

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
- `GET /api/groups` - List all available function groups
- `GET /api/devices/{device_id}/groups/{group_id}/actions` - List all actions associated with a specific group for a given device

## Configuration Files

### Environment Variables (.env)

```env
MQTT_BROKER_HOST=localhost
MQTT_BROKER_PORT=1883
MQTT_USERNAME=user
MQTT_PASSWORD=pass
LOG_LEVEL=INFO
```

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
  "log_file": "logs/service.log",
  "groups": {
    "volume": "Sound Volume",
    "screen": "Screen Control",
    "playback": "Playback"
  }
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
      "action": "power_on",
      "group": "power"
    },
    "volume_up": {
      "topic": "home/example/volume",
      "rf_code": "base64_encoded_rf_code_here", 
      "action": "volume_up",
      "group": "volume"
    },
    "play": {
      "topic": "home/example/playback",
      "rf_code": "base64_encoded_rf_code_here", 
      "action": "play",
      "group": "playback"
    },
    "unassigned_action": {
      "topic": "home/example/misc",
      "rf_code": "base64_encoded_rf_code_here", 
      "action": "misc_action"
    }
  }
}
```

## Deployment

The project is deployed using Docker:

- Use the provided Dockerfile and docker-compose.yml
- Run `docker_deploy.sh` with appropriate options (see Docker Deployment section)

## Development Tools

- `mqtt_sniffer.py` - MQTT topic monitoring tool
- `test_LGTV_living.ipynb` - Jupyter notebook for LG TV testing
- `test_broadlink.ipynb` - Jupyter notebook for Broadlink device testing

## License

MIT

## MQTT Sniffer

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
  -f FILTER_SUBSTRING, --filter-substring FILTER_SUBSTRING
                        Only report topics containing this substring
  -c, --config          Use broker parameters from config/system.json
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

Filter topics containing a specific substring:
```bash
python mqtt_sniffer.py -f "temperature"
```

Specify a custom log file:
```bash
python mqtt_sniffer.py -l my_mqtt_traffic.log
```

Use configuration from system.json:
```bash
python mqtt_sniffer.py -c
```

## Output Format

The log file contains entries in the following format:
```
2023-06-01 12:34:56.789 - INFO - Topic: home/temperature | Payload: 22.5
```

Each entry includes a timestamp, log level, topic name, and message payload. 

## LG TV SSL Support

The project now supports secure SSL connections to LG WebOS TVs. This enhancement allows for encrypted communication between the bridge and the TV, which is important for security.

### Features

1. **Certificate Management Tools**
   - Added `extract_lg_tv_cert.py` script to extract and save TV certificates
   - Certificate verification to ensure valid connections

2. **Secure Connection Options**
   - `secure`: Enable/disable secure WebSocket connections
   - `cert_file`: Path to the TV's certificate file
   - `verify_ssl`: Enable/disable SSL certificate verification
   - `ssl_options`: Additional SSL configuration options

3. **New Actions**
   - `extract_certificate`: Extract and save the TV's SSL certificate
   - `verify_certificate`: Verify if the current certificate matches the TV

### Usage

#### Extracting a Certificate

```bash
python extract_lg_tv_cert.py 192.168.1.100 --output tv_cert.pem
```

#### Configuration Example

```json
{
  "device_id": "living_room_tv",
  "device_name": "Living Room TV",
  "device_class": "lg_tv",
  "tv": {
    "ip_address": "192.168.1.100",
    "mac_address": "AA:BB:CC:DD:EE:FF",
    "client_key": "abcdef1234567890",
    "secure": true,
    "cert_file": "/path/to/tv_cert.pem",
    "verify_ssl": true
  }
}
```

#### API Actions

Extract certificate:
```json
{
  "action": "extract_certificate",
  "params": {
    "output_file": "/path/to/save/certificate.pem"
  }
}
```

Verify certificate:
```json
{
  "action": "verify_certificate"
}
``` 