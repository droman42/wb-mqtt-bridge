# External Integrations

**Analysis Date:** 2026-05-20

## APIs & External Services

**LG TV Control:**
- Service: LG WebOS TV
- SDK/Client: `asyncwebostv` (0.2.7 from PyPI)
- Entry point: `wb_mqtt_bridge.infrastructure.devices.lg_tv.driver:LgTv`
- Auth: Client key pairing (stored in device config as `lg_tv.client_key`)
- Connection: WebSocket/HTTPS on port 3000 (default, configurable)
- Features: Volume, mute, app control, input switching, power state
- Configuration model: `LgTvDeviceConfig` with nested `LgTvConfig` in `wb_mqtt_bridge.infrastructure.config.models`

**Apple TV Control:**
- Service: Apple TV (tvOS devices)
- SDK/Client: `pyatv` (git commit f75e718bc0b from postlund/pyatv)
- Entry point: `wb_mqtt_bridge.infrastructure.devices.apple_tv.driver:AppleTVDevice`
- Auth: Protocol-specific credentials stored per protocol (HomeKit, etc.)
- Connection: Local network discovery via mDNS; typically port 3689
- Features: Power, playback control, app launching, AirPlay
- Configuration model: `AppleTVDeviceConfig` with nested `AppleTVConfig` and per-protocol `AppleTVProtocolConfig`

**Emotiva XMC2 Processor Control:**
- Service: Emotiva XMC-2 AV Processor
- SDK/Client: `pymotivaxmc2` (0.6.7 from PyPI)
- Entry point: `wb_mqtt_bridge.infrastructure.devices.emotiva_xmc2.driver:EMotivaXMC2`
- Connection: TCP/IP on port 7002 (configurable)
- Auth: None (LAN-only); connection via `EmotivaController` from library
- Features: Power (main + zone 2), volume, input selection, audio bitstream control
- Configuration model: `EmotivaXMC2DeviceConfig` with nested `EmotivaConfig`

**Broadlink RF Device Hub:**
- Service: Broadlink RM4 Pro and compatible IR/RF remotes
- SDK/Client: `broadlink` (0.18.0+)
- Entry point: `wb_mqtt_bridge.infrastructure.devices.broadlink_kitchen_hood.driver:BroadlinkKitchenHood`
- Connection: HTTP on port 80 (local network)
- Auth: Device authentication via `broadlink_device.auth()` (MAC address and device code required)
- Features: RF command transmission (e.g., kitchen hood control)
- Configuration model: `BroadlinkKitchenHoodConfig` with nested `BroadlinkConfig`
- CLI Tools: `broadlink-discovery`, `broadlink-cli` for device discovery and testing

**Auralic Altair G1 Audio Device:**
- Service: Auralic Altair G1 (HiFi audio system)
- SDK/Client: `openhomedevice` (git branch: remove-lxml-dependency from droman42/openhomedevice)
- Entry point: `wb_mqtt_bridge.infrastructure.devices.auralic.driver:AuralicDevice`
- Connection: UPnP/OpenHome protocol on dynamic port (typically 49152+)
- Auth: None (LAN-only)
- Features: Volume, source selection, standby mode (via UPnP); deep power-off via IR
- IR Integration: Uses MQTT topics (`ir_power_on_topic`, `ir_power_off_topic`) to control true power on/off via Wirenboard IR blaster
- Configuration model: `AuralicDeviceConfig` with nested `AuralicConfig`

**Wirenboard IR Blaster:**
- Service: Wirenboard MSW V3 IR interface (virtual MQTT device)
- Integration Type: MQTT topic publishing for IR command transmission
- Entry point: `wb_mqtt_bridge.infrastructure.devices.wirenboard_ir_device.driver:WirenboardIRDevice`
- Connection: Via MQTT broker (same as primary MQTT connection)
- Features: IR code emission for AV devices
- Configuration model: `WirenboardIRDeviceConfig`

**Revox A77 Reel-to-Reel Tape Recorder:**
- Service: Revox A77 (tape playback device)
- Integration Type: MQTT control via Wirenboard integration
- Entry point: `wb_mqtt_bridge.infrastructure.devices.revox_a77_reel_to_reel.driver:RevoxA77ReelToReel`
- Connection: MQTT topic messaging
- Features: Play, stop, fast-forward, rewind, etc.
- Configuration model: `RevoxA77DeviceConfig`

## Data Storage

**Databases:**
- SQLite (async via `aiosqlite`)
  - Connection: File-based database at path configured in `system.json` (default: `data/state.db`)
  - Client: `SQLiteStateStore` in `wb_mqtt_bridge.infrastructure.persistence.sqlite.py`
  - Schema: Single table `state_store` with columns `key` (TEXT PRIMARY KEY), `timestamp` (TEXT), `value` (TEXT for JSON blobs)
  - Purpose: Persistent storage of device states between service restarts
  - Interface: `StateRepositoryPort` in `wb_mqtt_bridge.domain.ports.py`

**File Storage:**
- Local filesystem (not cloud-based)
  - Config directory: `config/` (system, devices, scenarios)
  - Log directory: `logs/` (default: `logs/service.log` with daily rotation and 30-day retention)
  - Data directory: `data/` (SQLite database)
  - JSON-based configs with Pydantic validation

**Caching:**
- In-memory device caches:
  - LG TV: Cached app list and input sources (`_cached_apps`, `_cached_input_sources`)
  - Apple TV: Cached app list
  - No distributed cache (single-instance application)

## Authentication & Identity

**Auth Provider:**
- Custom (no centralized auth provider)
- Device-level authentication:
  - LG TV: Client key pairing (device-specific)
  - Apple TV: Protocol-specific credentials (HomeKit, AirPlay, etc.)
  - Emotiva XMC2: No auth (LAN-only)
  - Broadlink: MAC address + device code
  - Auralic: No auth (LAN-only)
  - Wirenboard MQTT: Optional username/password via `MQTT_BROKER_HOST`, `MQTT_BROKER_PORT`, `MQTT_USERNAME`, `MQTT_PASSWORD` in env
  - Web API: No API key authentication (assumes trusted LAN)

**MQTT Authentication:**
- Optional username/password authentication
- Config: `mqtt_broker.auth` in `system.json` with `username` and `password` fields
- Implementation: Checked in `wb_mqtt_bridge.infrastructure.mqtt.client.MQTTClient.__init__()` and applied at connection time
- Anonymous mode: Supported if no credentials provided

## Monitoring & Observability

**Error Tracking:**
- No external error tracking service configured
- Errors logged via Python standard `logging` module

**Logs:**
- **Framework:** Python `logging` module
- **Output:** 
  - Console (stderr)
  - File: `logs/service.log` (default configurable in `system.json` as `system.log_file`)
  - Rotation: Daily rotation at midnight with 30-day retention
  - Format: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`
- **Levels:** Configurable per logger in `system.json` under `system.loggers`
- **Key Loggers:**
  - Root logger: Set via `LOG_LEVEL` env var or `system.log_level` config
  - Per-module loggers: Can override in `system.loggers` dict
  - Override: `OVERRIDE_LOG_LEVEL` env var for emergency debugging

**Health Check:**
- Docker: HTTP GET to `http://localhost:8000/` (Uvicorn health endpoint)
- Interval: Every 30 seconds
- Timeout: 10 seconds
- Retries: 3 before marking unhealthy

**SSE (Server-Sent Events):**
- Real-time event streaming to clients
- Channels: `devices`, `scenarios`, `system`
- Endpoints: `/api/v1/events/{channel}` in `wb_mqtt_bridge.presentation.api.routers.events.py`
- Manager: `SSEManager` in `wb_mqtt_bridge.presentation.api.sse_manager.py`
- Event Types: Device state changes, scenario transitions, system events

## CI/CD & Deployment

**Hosting:**
- Docker container deployment
- Target: Wirenboard 7 (ARMv7 Linux, Debian Bullseye)
- Also supports: amd64, arm64v8, and other Docker buildx architectures

**CI Pipeline:**
- GitHub Actions (inferred from Dockerfile GitHub mirror references)
- Multi-architecture builds via Docker buildx
- Build artifacts: Docker images pushed to GitHub Container Registry

**Deployment Tools:**
- `manage_docker.sh` - Comprehensive container management script on Wirenboard
  - Commands: deploy, redeploy, start, stop, restart, status, logs, cleanup, config
  - Docker Compose integration (if available on device)
  - Configuration file: `docker_manager_config.json`

**Container Optimization:**
- Multi-stage Docker build (builder + final)
- Lean optimization mode (`LEAN=true`) removes:
  - Test files, documentation, examples
  - Development headers and build artifacts (*.c, *.h, Makefiles)
  - Git metadata, CI configs
  - Package metadata and README/LICENSE files
- UV package manager for faster, reliable dependency resolution
- APT retries (3x) for unreliable ARM mirrors

## Environment Configuration

**Required Environment Variables:**
- `MQTT_BROKER_HOST` - MQTT broker hostname
- `MQTT_BROKER_PORT` - MQTT broker port
- `MQTT_USERNAME` - MQTT username (optional, empty = anonymous)
- `MQTT_PASSWORD` - MQTT password (optional, empty = anonymous)
- `API_PORT` - Web service port
- `LOG_LEVEL` - Root logger level (INFO, DEBUG, WARNING, ERROR, CRITICAL)
- `OVERRIDE_LOG_LEVEL` - Emergency override for log level
- `ARCH` - Docker architecture (arm32v7, amd64, etc.) for Wirenboard

**Optional Environment Variables:**
- `PYMOTIVAXMC2_PATH` - Path to pymotivaxmc2 for local development
- `ASYNCWEBOSTV_PATH` - Path to asyncwebostv for local development

**Secrets Location:**
- `.env` file (git-ignored, not committed)
- Environment variables passed to Docker container
- Device credentials stored in device config files under `config/devices/`
- No external secret management (assumes trusted LAN)

## Webhooks & Callbacks

**Incoming:**
- MQTT topics subscribed per device (configurable in device configs)
  - Example: Device receives commands via `wb-mqtt-bridge/devices/{device_id}/commands`
  - Handler: `DeviceManager.get_message_handler(device_id)` dispatches to device

**Outgoing:**
- MQTT topic publishing (message bus pattern)
  - Device state updates published to `wb-mqtt-bridge/devices/{device_id}/state`
  - Scenario state changes to `wb-mqtt-bridge/scenarios/{scenario_id}/state`
  - Wirenboard virtual device control updates to standard Wirenboard topic schema
  - Implementation: `MessageBusPort` interface in `wb_mqtt_bridge.domain.ports.py`

**SSE Events (Streaming):**
- Outgoing WebSocket-like events via HTTP Server-Sent Events
- Channels: `/api/v1/events/devices`, `/api/v1/events/scenarios`, `/api/v1/events/system`
- Event types: Device state changes, scenario transitions, system health

**Scenario Callbacks:**
- Auralic IR control: Publishes to `ir_power_on_topic` and `ir_power_off_topic` (MQTT)
- Implementation: `ScenarioWBAdapter` in `wb_mqtt_bridge.infrastructure.scenarios.wb_adapter.py`

---

*Integration audit: 2026-05-20*
