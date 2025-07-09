# Wirenboard MQTT Bridge as Web Service

A Python-based web service that integrates as an MQTT client with Wirenboard wb-rules engine to manage multiple devices using an object-oriented plugin-based architecture.

## Features

- FastAPI REST API for device management
- MQTT client for device communication
- Object-oriented device class architecture
- Plugin-based architecture for device modules
- JSON configuration files with typed Pydantic models
- Optional parameters for device commands
- Logging system
- Action Groups for organizing device functions
- Scenario system for AV devices, inspired by Logitech Harmony universal remotes
- Dynamic device configuration system with validation and migration tools
- Support for various device types:
  - LG TV - multiple models using [asyncwebostv](https://github.com/droman42/asyncwebostv) library
  - Apple TV - multiple models using [pyatv](https://github.com/postlund/pyatv) library
  - RF devices - Kitchen Hood via Broadlink hub using [broadlink](https://github.com/mjg59/python-broadlink) library
  - Multiple AV devices - via Wirenboard MSW V3 IR interface
  - Revox A77 Reel-to-Reel tape recorder
  - eMotiva XMC2 Device - using [pymotivaxmc2](https://github.com/droman42/pymotivaxmc2) library
  - Auralic Altair G1 - using [openhomedevice](https://github.com/bazwilliams/openhomedevice) library in combination with Wirenboard MSW V3 IR interface
  - Miele home appliances - using [asyncmiele](https://github.com/droman42/asyncmiele) library
  - Roborock S8 vacuum cleaner - using [python-roborock](https://github.com/Python-roborock/python-roborock) library

## Architecture

- **Web Service**: Built with FastAPI, fully Pydantic-conformant
- **MQTT Client**: Based on `aiomqtt`
- **Device Architecture**:
  - `BaseDevice` abstract class with common functionality
  - Device-specific implementations that inherit from BaseDevice
  - Standardized parameter handling for device commands
- **Configuration**: Strongly-typed JSON files for system and device settings
- **Logging**: File-based logging
- **Dynamic Configuration System**:
  - Validation and error reporting for configuration files
  - Automatic device class detection for migration
  - Command processing specific to device types

## Installation

1. Clone the repository:
```bash
git clone https://github.com/droman42/wb-mqtt-bridge.git
cd wb-mqtt-bridge
```

2. Create a virtual environment and install dependencies:
```bash
# Using UV (recommended)
uv venv
uv sync

# Or using traditional pip
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e .
```

3. Configure the application:
   - Edit `.env` for environment variables
   - Edit `config/system.json` for MQTT broker settings
   - Add device configurations in `config/devices/`

## Docker Deployment

The application can be deployed using Docker on various platforms including Wirenboard 7 (ARMv7 architecture).

### Basic Docker Deployment

1. **Clone and setup**:
```bash
git clone https://github.com/droman42/wb-mqtt-bridge.git
cd wb-mqtt-bridge
```

2. **Configure the application**:
```bash
# Copy and edit environment variables
cp .env.example .env
nano .env

# Create device configurations directory
mkdir -p config/devices data logs
# Add your device configuration files to config/devices/
```

3. **Build and start** (optimized build by default):
```bash
./docker_deploy.sh --build
```

4. **Management commands**:
```bash
# Stop containers
./docker_deploy.sh --down

# Restart containers  
./docker_deploy.sh --restart

# Build without optimizations (for debugging)
./docker_deploy.sh --build --no-lean
```

The web service will be available at http://localhost:8000.

#### Dependency Optimization for Lean Images

The Docker build includes comprehensive optimizations to minimize image size by excluding unnecessary code from dependencies:

**1. Pip Installation Optimizations:**
```dockerfile
# Use binary wheels when possible to avoid compilation artifacts
pip install --no-cache-dir --only-binary=all --no-compile

# For Git dependencies, allow source installation but optimize later
pip install --no-cache-dir --only-binary=:none: git+https://...
```

**2. Comprehensive File Removal (when LEAN=true):**
- **Testing files**: `tests/`, `test/`, `testing/`, `*_test.py`
- **Documentation**: `docs/`, `doc/`, `examples/`, `samples/`
- **Development files**: `setup.py`, `*.egg-info/`, `.git*`, `.github/`
- **Build artifacts**: `*.c`, `*.h`, `Makefile*`, `CMakeFiles/`
- **Metadata**: `README*`, `LICENSE*`, `CHANGELOG*`, `AUTHORS*`
- **CI/Testing config**: `tox.ini`, `pytest.ini`, `.coveragerc`

**3. UV Dependency Management:**
```bash
# Dependencies are now managed via pyproject.toml
# Docker builds use UV for faster, more reliable dependency resolution
uv sync --frozen  # Uses exact versions from uv.lock
```

**4. Optimized Dependency Installation:**

UV provides better dependency resolution and faster installs:
```bash
# Production dependencies only (excludes dev dependencies)
uv sync --no-dev --frozen

# Development dependencies included
uv sync --frozen
```

**5. Measuring Optimization Impact:**
```bash
# Compare image sizes
docker build -t wb-mqtt-bridge:full --build-arg LEAN=false .
docker build -t wb-mqtt-bridge:lean --build-arg LEAN=true .
docker images | grep wb-mqtt-bridge

# Inspect what was removed
docker run --rm wb-mqtt-bridge:lean find /opt/venv -name "test*" -o -name "doc*" | wc -l
```

#### Volume Mounts and Data Persistence

The Docker deployment creates persistent volume mounts for:
- **Configuration**: `./config` → `/app/config` (read-only)
- **Logs**: `./logs` → `/app/logs` 
- **Database**: `./data` → `/app/data` (SQLite database persistence)

This ensures that device states, logs, and configurations survive container updates and restarts.

### Wirenboard 7 Deployment

The application is optimized for deployment on Wirenboard 7 controllers, which use ARMv7 architecture and Debian Bullseye. The Docker images are built with lean optimizations by default to minimize resource usage on these constrained devices.

#### Prerequisites

- **Wirenboard 7** with Docker support
- **SSH access** to your Wirenboard device
- **Docker with Buildx support** (for cross-platform builds)

#### Quick Start - Choose Your Deployment Method

| Method | Speed | Use Case | Prerequisites |
|--------|-------|----------|--------------|
| **GitHub Actions** ⚡ | ~15-20 min | Recommended for most users | GitHub account, git |
| **Local Cross-Build** 🐌 | ~60+ min | Development/customization | Docker Buildx, powerful machine |
| **Direct on WB7** 🏠 | ~45 min | Building directly on device | SSH access to Wirenboard |

**👍 Recommended: Use GitHub Actions** for fastest builds and easier management.

#### Option 1: Direct Build on Wirenboard 7

If you're running the deployment directly on your Wirenboard 7:

```bash
git clone https://github.com/droman42/wb-mqtt-bridge.git
cd wb-mqtt-bridge

# Configure your deployment
cp .env.example .env
nano .env

# Set up device configurations
mkdir -p config/devices
# Add your device configuration files to config/devices/

# Build and deploy (optimized build by default)
./docker_deploy.sh --build
```

#### Option 2: GitHub Actions Build (Recommended for Speed)

For fast ARM builds using GitHub's infrastructure instead of local cross-compilation:

1. **Setup and trigger build**:
```bash
git clone https://github.com/droman42/wb-mqtt-bridge.git
cd wb-mqtt-bridge

# Configure for your Wirenboard
cp .env.example .env
nano .env

# Add device configurations
mkdir -p config/devices
# Copy your device configuration files to config/devices/

# Push to GitHub to trigger ARM build (or use GitHub web interface)
git add .
git commit -m "Configure for Wirenboard deployment"
git push
```

2. **Download build artifacts**:
   - Go to your repository on GitHub
   - Click **"Actions"** tab
   - Click on the latest **"Build ARM Docker Image"** workflow run
   - Scroll down to **"Artifacts"** section
   - Download both files:
     - **`wb-mqtt-bridge-image`** (contains `wb-mqtt-bridge.tar.gz`)
     - **`wb-mqtt-bridge-config`** (contains `wb-mqtt-bridge-config.tar.gz`)

3. **Extract artifacts**:
```bash
# Create a directory for deployment files
mkdir -p ./deploy

# Extract the Docker image archive
unzip wb-mqtt-bridge-image.zip -d ./deploy
# This creates: ./deploy/wb-mqtt-bridge.tar.gz

# Extract the configuration archive  
unzip wb-mqtt-bridge-config.zip -d ./deploy
# This creates: ./deploy/wb-mqtt-bridge-config.tar.gz
```

4. **Transfer to Wirenboard**:
```bash
# Replace 192.168.1.100 with your Wirenboard's IP address
scp ./deploy/wb-mqtt-bridge.tar.gz root@192.168.1.100:/tmp/
scp ./deploy/wb-mqtt-bridge-config.tar.gz root@192.168.1.100:/tmp/

# SSH into Wirenboard and deploy
ssh root@192.168.1.100 '
  cd /tmp
  tar -xzf wb-mqtt-bridge-config.tar.gz
  docker load -i wb-mqtt-bridge.tar.gz
  docker stop wb-mqtt-bridge 2>/dev/null || true
  docker rm wb-mqtt-bridge 2>/dev/null || true
  docker run -d --name wb-mqtt-bridge --restart unless-stopped -p 8000:8000 \
    -v $(pwd)/config:/app/config:ro \
    -v $(pwd)/logs:/app/logs \
    -v $(pwd)/data:/app/data \
    --memory=256M --cpus=0.5 \
    wb-mqtt-bridge:latest
'
```

**Benefits of GitHub Actions approach:**
- ⚡ **Much faster**: ~15-20 minutes vs 1+ hour for local ARM cross-compilation
- 🔄 **Consistent builds**: Same environment every time
- 💻 **Saves local resources**: No impact on your development machine
- 🔒 **Cached builds**: Subsequent builds are even faster due to GitHub's cache

#### Option 3: Local Cross-Platform Build and Transfer

For building on a development machine and deploying to Wirenboard:

1. **Setup on development machine**:
```bash
git clone https://github.com/droman42/wb-mqtt-bridge.git
cd wb-mqtt-bridge

# Configure for your Wirenboard
cp .env.example .env
nano .env

# Add device configurations
mkdir -p config/devices
# Copy your device configuration files to config/devices/
```

2. **Build, save, and transfer in one step**:
```bash
# Replace 192.168.1.100 with your Wirenboard's IP address
./docker_deploy.sh -b --save --transfer 192.168.1.100
```

3. **Or build and save for later transfer**:
```bash
# Build optimized images and save to ./images directory
./docker_deploy.sh -b --save ./images

# Later transfer the saved images to Wirenboard
./docker_deploy.sh --transfer 192.168.1.100
```

#### Advanced Deployment Options

**Custom target directory on Wirenboard**:
```bash
./docker_deploy.sh -b --save --transfer 192.168.1.100 --target-dir /opt/mqtt-bridge
```

**Disable optimizations** (for debugging):
```bash
./docker_deploy.sh -b --no-lean --save --transfer 192.168.1.100
```

**Save to custom directory**:
```bash
./docker_deploy.sh -b --save /path/to/custom/directory
```

#### What Gets Deployed

The deployment script transfers and sets up:

1. **Docker Image** (`wb-mqtt-bridge.tar.gz`)
   - Optimized ARM image with lean build optimizations
   - Python application with all dependencies
   - Multi-stage build for minimal image size

2. **Configuration Archive** (`wb-mqtt-bridge-config.tar.gz`)
   - Configuration files (`config/`)
   - Log directory structure (`logs/`)
   - Data directory for SQLite database (`data/`)
   - Environment variables (`.env`)

3. **Persistent Volume Mounts**:
   - `config/` → `/app/config` (read-only)
   - `logs/` → `/app/logs` (log files)
   - `data/` → `/app/data` (SQLite database persistence)

#### Resource Configuration

The container is configured for Wirenboard's limited resources:
- **Memory limit**: 256MB
- **CPU limit**: 0.5 cores
- **Optimized builds**: Lean images remove unnecessary files
- **Health checks**: Monitor container status

#### Post-Deployment

After successful deployment:

1. **Check container status**:
```bash
ssh root@192.168.1.100 'docker ps --filter name=wb-mqtt-bridge'
```

2. **View logs**:
```bash
ssh root@192.168.1.100 'docker logs wb-mqtt-bridge'
```

3. **Access the web interface**:
   - http://your-wirenboard-ip:8000

4. **Monitor resource usage**:
```bash
ssh root@192.168.1.100 'docker stats wb-mqtt-bridge'
```

#### Troubleshooting

**Connection issues**:
```bash
# Verify SSH access
ssh root@192.168.1.100 'echo "Connection successful"'

# Check Docker service
ssh root@192.168.1.100 'systemctl status docker'
```

**Container issues**:
```bash
# Restart container
ssh root@192.168.1.100 'docker restart wb-mqtt-bridge'

# Check container logs
ssh root@192.168.1.100 'docker logs wb-mqtt-bridge --tail 50'
```

**Storage issues**:
```bash
# Check disk space on Wirenboard
ssh root@192.168.1.100 'df -h'

# Clean up old Docker images
ssh root@192.168.1.100 'docker system prune -f'
```

The web service will be available at http://wirenboard-ip:8000 after successful deployment.

#### Custom Volume Locations on Target Device

The deployment script uses relative paths (`$(pwd)/config`, `$(pwd)/logs`, `$(pwd)/data`) which work from the transfer directory. For custom volume locations on your Wirenboard:

**1. Create custom directories on Wirenboard:**
```bash
# SSH into your Wirenboard
ssh root@192.168.1.100

# Create persistent storage directories (recommended locations)
mkdir -p /mnt/data/wb-mqtt-bridge/config
mkdir -p /mnt/data/wb-mqtt-bridge/logs  
mkdir -p /mnt/data/wb-mqtt-bridge/data
mkdir -p /var/log/wb-mqtt-bridge  # Alternative for logs

# Or create in any custom location
mkdir -p /opt/mqtt-bridge/config
mkdir -p /opt/mqtt-bridge/logs
mkdir -p /opt/mqtt-bridge/data
```

**2. Transfer configuration files to custom location:**
```bash
# Transfer to custom directory
./docker_deploy.sh --transfer 192.168.1.100 --target-dir /opt/mqtt-bridge

# Then move configs to desired locations
ssh root@192.168.1.100 '
  cd /opt/mqtt-bridge
  cp -r config/* /mnt/data/wb-mqtt-bridge/config/
  # Keep logs and data directories where you want them
'
```

**3. Modify the Docker run command:**

After transfer, modify the container startup on the Wirenboard:

```bash
# SSH into Wirenboard
ssh root@192.168.1.100

# Stop the auto-started container
docker stop wb-mqtt-bridge
docker rm wb-mqtt-bridge

# Start with custom volume locations
docker run -d \
  --name wb-mqtt-bridge \
  --restart unless-stopped \
  -p 8000:8000 \
  -v /mnt/data/wb-mqtt-bridge/config:/app/config:ro \
  -v /mnt/data/wb-mqtt-bridge/logs:/app/logs \
  -v /mnt/data/wb-mqtt-bridge/data:/app/data \
  --memory=256M \
  --cpus=0.5 \
  wb-mqtt-bridge:latest
```

**4. Alternative: Modify the deployment script:**

Create a custom deployment script for your specific volume layout:

```bash
# Copy the original script
cp docker_deploy.sh docker_deploy_custom.sh

# Edit the SSH_COMMAND section in transfer_images function:
nano docker_deploy_custom.sh

# Change the docker run command to use your custom paths:
SSH_COMMAND="cd $target_dir && \
    tar -xzf wb-mqtt-bridge-config.tar.gz && \
    docker load -i wb-mqtt-bridge.tar.gz && \
    cp -r config/* /mnt/data/wb-mqtt-bridge/config/ && \
    docker stop wb-mqtt-bridge 2>/dev/null || true && \
    docker rm wb-mqtt-bridge 2>/dev/null || true && \
    docker run -d --name wb-mqtt-bridge --restart unless-stopped -p 8000:8000 \
    -v /mnt/data/wb-mqtt-bridge/config:/app/config:ro \
    -v /mnt/data/wb-mqtt-bridge/logs:/app/logs \
    -v /mnt/data/wb-mqtt-bridge/data:/app/data \
    --memory=256M --cpus=0.5 wb-mqtt-bridge:latest"
```

**5. Recommended Wirenboard storage locations:**

- **Persistent data**: `/mnt/data/` (survives firmware updates)
- **Logs**: `/var/log/` or `/mnt/data/logs/`
- **Temporary files**: `/tmp/` (cleared on reboot)
- **Application files**: `/opt/` or `/usr/local/`

**6. Verify volume mounts:**
```bash
ssh root@192.168.1.100 'docker inspect wb-mqtt-bridge | grep -A 10 "Mounts"'
```

#### Deployment Script Reference

The `docker_deploy.sh` script supports the following options:

```bash
Usage: ./docker_deploy.sh [options]

Options:
  -b, --build               Rebuild containers (with lean optimizations by default)
  -d, --down                Stop and remove containers
  -r, --restart             Restart containers
  --save [path]             After building, save images to tar files for transfer
  --transfer [ip]           Transfer saved images to Wirenboard at specified IP
  --target-dir [dir]        Specify target directory on Wirenboard (default: /mnt/data/docker_exchange)
  --no-lean                 Disable lean optimizations (build larger, unoptimized images)
  --help                    Show help message

Examples:
  ./docker_deploy.sh -b                                    # Build optimized containers locally
  ./docker_deploy.sh -b --save                             # Build and save images to current directory
  ./docker_deploy.sh --save ./images                       # Save images to ./images directory
  ./docker_deploy.sh --transfer 192.168.1.100              # Transfer previously saved images
  ./docker_deploy.sh -b --save --transfer 192.168.1.100    # Build, save, and transfer in one step
  ./docker_deploy.sh -b --no-lean                          # Build larger, unoptimized images
```

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
- Parameter validation and processing for commands
- Abstract methods that must be implemented by device-specific classes

### Command Parameters

The system now supports optional and required parameters for device commands:

- **Parameter Definition**: Parameters are defined in the device configuration JSON files
- **Validation**: Automatic validation of parameter types and constraints
- **Default Values**: Support for default values for optional parameters
- **JSON Support**: Parameters can be provided as JSON in MQTT payloads
- **API Support**: Parameters can be passed directly through the API

Example parameter definition in a device configuration:
```json
"setVolume": {
  "action": "set_volume",
  "topic": "/devices/living_room_tv/controls/set",
  "description": "Set Volume Level",
  "group": "volume",
  "params": [
    {"name": "level", "type": "range", "min": 0, "max": 100, "required": true, "description": "Volume level (0-100)"}
  ]
}
```

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
4. Implement action handlers with the standardized signature:
   ```python
   async def handle_action_name(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> bool:
   ```

Example:
```python
from devices.base_device import BaseDevice
from app.schemas import StandardCommandConfig
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
        # BaseDevice handles parameter parsing and validation
        print(f"Received on {topic}: {payload}")
        
    async def handle_set_value(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> bool:
        # Process the validated parameters
        value = params.get("value")
        if value is not None:
            # Do something with the value
            return True
        return False
```

## Implementation Status

The project has completed a major refactoring to implement optional parameters for device commands and introduced a strongly-typed configuration system:

- ✅ Parameter definition and validation infrastructure
- ✅ BaseDevice updates for parameter handling
- ✅ Migrated all devices to use the new parameter system
- ✅ Standardized handler method signatures across all devices
- ✅ Implemented strongly-typed configuration models
- ✅ Removed backward compatibility code
- ⏳ Finalizing documentation and preparing for release

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
  },
  "devices": {
    "kitchen_hood": {
      "class": "BroadlinkKitchenHood",
      "config_file": "kitchen_hood.json"
    },
    "lg_tv": {
      "class": "LgTv",
      "config_file": "lg_tv.json"
    }
  }
}
```

### Device Configuration (config/devices/{device_name}.json)

```json
{
  "device_id": "lg_tv",
  "device_name": "Living Room TV",
  "device_class": "LgTv",
  "config_class": "LgTvDeviceConfig",
  "commands": {
    "power_on": {
      "action": "power_on",
      "description": "Turn TV on"
    }
  },
  "tv": {
    "ip_address": "192.168.1.100",
    "mac_address": "AA:BB:CC:DD:EE:FF"
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
  "device_class": "LgTv",
  "config_class": "LgTvDeviceConfig",
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

# Apple TV Utility

A command-line utility for discovering, pairing, and connecting to Apple TV devices.

## Features

- Discover Apple TVs on your network
- Pair with Apple TVs using PIN codes
- Store and manage credentials for multiple devices
- Test connections to paired devices
- List and remove stored credentials

## Requirements

- Python 3.7+
- `pyatv` library

## Installation

1. Install the required dependencies:

```bash
pip install pyatv
```

2. Make the script executable:

```bash
chmod +x apple_tv_util.py
```

## Usage

### Scan for Apple TVs

To scan your entire network for Apple TV devices:

```bash
./apple_tv_util.py scan
```

To scan specific IP addresses:

```bash
./apple_tv_util.py scan --ip 192.168.1.10 192.168.1.20
```

### Pair with an Apple TV

To pair with an Apple TV at a specific IP address:

```bash
./apple_tv_util.py pair --ip 192.168.1.10
```

This will initiate the pairing process. If required, you'll be prompted to enter the PIN code displayed on your Apple TV.

### Test Connection

To test the connection to a paired Apple TV:

```bash
./apple_tv_util.py connect --ip 192.168.1.10
```

### List Stored Credentials

To list all stored credentials:

```bash
./apple_tv_util.py list
```

### Remove Stored Credentials

To remove stored credentials for a specific Apple TV:

```bash
./apple_tv_util.py remove --ip 192.168.1.10
```

## Credentials Storage

All credentials are stored in a JSON file (`apple_tv_credentials.json`) in the same directory as the script. This file contains the necessary credentials to connect to your paired Apple TVs.

## Integration

You can import the `AppleTVManager` class in your own Python code to integrate Apple TV functionality:

```python
from apple_tv_util import AppleTVManager
import asyncio

async def example():
    manager = AppleTVManager()
    
    # Discover devices
    devices = await manager.discover_devices()
    
    # Connect to a device
    if devices:
        atv = await manager.connect_to_device(devices[0].address)
        if atv:
            # Do something with the connected device
            print(f"Connected to {atv.device_info.name}")
            await atv.close()

if __name__ == "__main__":
    asyncio.run(example())
```

## Notes

- The utility will automatically select the first available protocol for pairing
- All credentials are stored locally on your system
- Pairing requires that your Apple TV is on the same network as your computer

## License

This project is open source and available under the MIT License.

# Configuration Structure Updates

## System Configuration

Device configuration files now include both `device_class` and `config_class` fields to support dynamic loading.

Example device configuration:

```json
{
  "device_id": "lg_tv",
  "device_name": "Living Room TV",
  "device_class": "LgTv",
  "config_class": "LgTvDeviceConfig",
  "commands": {
    "power_on": {
      "action": "power_on",
      "description": "Turn TV on"
    }
  },
  "tv": {
    "ip_address": "192.168.1.100",
    "mac_address": "AA:BB:CC:DD:EE:FF"
  }
}
``` 