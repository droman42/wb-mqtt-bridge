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

  **Planned (not yet implemented):** Roborock S8 vacuum cleaner ([python-roborock](https://github.com/Python-roborock/python-roborock)).

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

## Project Structure

The project follows a domain-centric (DDD/Hexagonal) architecture for better maintainability and testability:

```
src/wb_mqtt_bridge/
├── app/                     # Application bootstrap and configuration
│   ├── __init__.py         # FastAPI app export
│   ├── bootstrap.py        # Dependency injection and app setup
│   └── main.py             # Entry point for console scripts
├── cli/                     # Command-line utilities
│   ├── mqtt_sniffer.py     # MQTT traffic monitoring
│   ├── device_test.py      # Device testing utility
│   └── broadlink_*.py      # Broadlink discovery tools
├── domain/                  # Pure business logic (no I/O dependencies)
│   ├── devices/            # Device management domain
│   ├── scenarios/          # Scenario system domain  
│   └── rooms/              # Room management domain
├── infrastructure/         # External adapters and implementations
│   ├── mqtt/               # MQTT client implementation
│   ├── persistence/        # Database storage (SQLite)
│   ├── config/             # Configuration management
│   └── devices/            # Device driver implementations
│       ├── lg_tv/driver.py
│       ├── apple_tv/driver.py
│       └── ...
└── presentation/           # HTTP API layer
    └── api/                # FastAPI routers and schemas
```

**Key principles:**
- **Domain layer** contains pure business logic with no external dependencies
- **Infrastructure layer** implements interfaces defined by the domain
- **Presentation layer** handles HTTP requests and responses
- **App layer** wires everything together with dependency injection

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

After installation, the following console scripts will be available:
- `wb-mqtt-bridge` / `wb-api` - Start the web service
- `mqtt-sniffer` - Monitor MQTT traffic
- `device-test` - Test device configurations
- `broadlink-cli` / `broadlink-discovery` - Broadlink utilities

3. Configure the application:
   - Edit `.env` for environment variables
   - Edit `config/system.json` for MQTT broker settings
   - Add device configurations in `config/devices/`

## Docker Deployment

The backend ships as a Docker image for the Wirenboard 7 (ARMv7 architecture).

### Images come from GHCR

GitHub Actions builds the ARM images and pushes them to the GitHub Container
Registry (see `.github/workflows/build-arm.yml`; the slow ARM jobs run on manual
workflow dispatch):

- `ghcr.io/droman42/wb-mqtt-bridge` — this backend
- `ghcr.io/droman42/wb-mqtt-ui` — the UI

Every build is tagged `latest`, `sha-<short>`, and `vYYYYMMDD-<short>` — the
dated tags are what you pin for rollback. The packages are public, so the
Wirenboard pulls them anonymously; no credentials are involved anywhere in the
deployment path.

### Deploying on the Wirenboard

Deployment is standard Docker tooling: `ops/docker-compose.yml` (both services
on the host network, with memory/CPU limits), a systemd unit that brings the
stack up on boot, and `ops/update.sh` — pull the latest images, restart, prune
the replaced ones:

```bash
cd /mnt/data/mqtt-bridge-config
sudo git pull                  # config changes travel with the repo
sudo ./ops/update.sh           # pull images + restart + clean up dangling
```

The full runbook — first install, preserving the state DB across the cutover,
firmware-upgrade recovery, and rolling back to a pinned image — is
[`ops/INSTALL.md`](../ops/INSTALL.md).

The web service is available at http://wirenboard-ip:8000 (host networking),
the UI at port 3000.

#### Volume Mounts and Data Persistence

The compose file mounts (paths relative to `ops/`):

- **Configuration**: `../backend/config` → `/app/config` (read-only — config is
  the cloned repo itself; `git pull` updates it)
- **Database**: `../.state/data` → `/app/data` (SQLite state store)
- **Logs**: `../.state/logs` → `/app/logs`

`.state/` is gitignored, so device states and logs survive both image updates
and `git pull`.

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

## Running the Application

Start the web service using the console script:

```bash
# Using the main console script
wb-mqtt-bridge

# Or using the API-specific script
wb-api
```

Or use uvicorn directly:

```bash
uvicorn wb_mqtt_bridge.app:app --host 0.0.0.0 --port 8000
```

Other available console scripts:
```bash
# MQTT monitoring tool
mqtt-sniffer --help

# Device testing utility  
device-test --help

# Broadlink utilities
broadlink-cli --help
broadlink-discovery --help
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

Seven device drivers ship today, each under `src/wb_mqtt_bridge/infrastructure/devices/<name>/driver.py`:

1. **LG TV** (`lg_tv/driver.py`, class `LgTv`) — webOS TV over WebSocket (asyncwebostv); power, volume, app launching, input switching, pointer.
2. **eMotiva XMC2** (`emotiva_xmc2/driver.py`, class `EMotivaXMC2`) — dual-zone AV processor (pymotivaxmc2); power/Zone-2 power, volume, input, notifications.
3. **Apple TV** (`apple_tv/driver.py`, class `AppleTVDevice`) — pyatv; remote control, playback, app launching.
4. **Auralic Altair G1** (`auralic/driver.py`, class `AuralicDevice`) — openhomedevice (UPnP) with IR fallback via Wirenboard.
5. **Broadlink Kitchen Hood** (`broadlink_kitchen_hood/driver.py`, class `BroadlinkKitchenHood`) — RF light + fan-speed control via a Broadlink hub.
6. **Wirenboard IR Device** (`wirenboard_ir_device/driver.py`, class `WirenboardIRDevice`) — generic IR over the Wirenboard MQTT interface.
7. **Revox A77 Reel-to-Reel** (`revox_a77_reel_to_reel/driver.py`, class `RevoxA77ReelToReel`) — transport control for the tape deck (IR via Wirenboard).

## Creating New Device Implementations

To add support for a new device type:

1. Create a new directory and driver file: `src/wb_mqtt_bridge/infrastructure/devices/{device_name}/driver.py`
2. Create a class that inherits from `BaseDevice`
3. Register the device in `pyproject.toml` under `[project.entry-points."wb_mqtt_bridge.devices"]`
4. Implement the required abstract methods:
   - `async setup()` - Initialize the device
   - `async shutdown()` - Clean up device resources
   - `subscribe_topics()` - Return MQTT topics to subscribe to
   - `async handle_message(topic, payload)` - Process incoming MQTT messages
5. Implement action handlers with the standardized signature:
   ```python
   async def handle_action_name(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> bool:
   ```

Example (`src/wb_mqtt_bridge/infrastructure/devices/my_device/driver.py`):
```python
from wb_mqtt_bridge.infrastructure.devices.base import BaseDevice
from wb_mqtt_bridge.domain.devices.models import StandardCommandConfig
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

6. Register the device in `pyproject.toml`:
```toml
[project.entry-points."wb_mqtt_bridge.devices"]
my_custom_device = "wb_mqtt_bridge.infrastructure.devices.my_device.driver:MyCustomDevice"
```

7. Create a configuration file in `config/devices/my_custom_device.json`

## Implementation Status

Version `0.5.0 Alpha`. The codebase has completed its move to a hexagonal
(domain/infrastructure/presentation) architecture with strongly-typed Pydantic
configs and per-device state models:

- ✅ Optional/required parameter handling with validation
- ✅ Standardized handler signatures across all 7 drivers
- ✅ Strongly-typed configuration models (`device_class` + `config_class`)
- ✅ Per-device Pydantic state models, persisted to SQLite
- ✅ Scenario system + Wirenboard virtual-device emulation
- ✅ Device-state models exposed in `/openapi.json` (the contract the UI consumes)
- ✅ Test suite runs in CI (amd64); ARM image built via GitHub Actions

The OpenAPI snapshot (`openapi.json`) is regenerated with `wb-openapi` whenever the
API surface or a device-state model changes.

## API Endpoints

The full, authoritative surface is in `openapi.json` (and at `/docs` on a running
service). Key endpoints:

- `GET /` — service information; `GET /system` — system information
- `POST /reload` — reload configurations and devices
- `GET /config/devices`, `GET /config/device/{device_id}`, `GET /config/system` — configuration
- `GET /devices/{device_id}/state` — current typed device state
- `GET /devices/{device_id}/persisted_state`, `GET /devices/persisted_states` — persisted state
- `POST /devices/{device_id}/action` — execute a device action (body: `{"action": "...", "params": {...}}`)
- `GET /groups`, `GET /devices/{device_id}/groups`, `GET /devices/{device_id}/groups/{group_id}/actions` — action groups
- `POST /publish` — publish an MQTT message
- `GET /scenario/*`, `POST /scenario/{start,switch,shutdown,role_action}` — scenario lifecycle
- `GET /room/list`, `GET /room/{room_id}` — rooms
- `GET /events/{devices,scenarios,system,stats}` — SSE event streams

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

The project is deployed with Docker on the Wirenboard: CI-built images pulled
from GHCR, orchestrated by `ops/docker-compose.yml` + systemd, updated with
`ops/update.sh` (see the Docker Deployment section above and
[`ops/INSTALL.md`](../ops/INSTALL.md) for the full runbook).

## Development Tools

Installed as console scripts (see Installation): `mqtt-sniffer` (MQTT traffic
monitor), `device-test` (device config testing), `broadlink-cli` /
`broadlink-discovery` (Broadlink utilities). Standalone test/pairing helpers live
under `tests/` (e.g. `tests/apple_tv_util.py`, `tests/extract_lg_tv_cert.py`).

## LG TV SSL Support

LG webOS TVs can be controlled over a secure (`wss://`) connection. The relevant
fields in a TV device config's `tv` block (`LgTvConfig`) are:

- `secure` (default `true`) — use a secure WebSocket connection
- `client_key` — the persisted pairing key
- `cert_file` — path to the TV's certificate (validated to exist when `secure` is true)
- `ssl_options` — optional dict for finer SSL/TLS control

Use `tests/extract_lg_tv_cert.py <tv-ip> --output tv_cert.pem` to fetch a TV's
certificate. The driver also exposes `extract_certificate` and `verify_certificate`
actions.

Example `tv` block:

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
    "cert_file": "/path/to/tv_cert.pem"
  }
}
```

## License

MIT
