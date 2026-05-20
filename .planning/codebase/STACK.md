# Technology Stack

**Analysis Date:** 2026-05-20

## Languages

**Primary:**
- Python 3.11+ - All application code; requires Python 3.11 minimum per `pyproject.toml`

## Runtime

**Environment:**
- Python 3.11 (Docker: Debian Bullseye with python:3.11-slim base image)
- Uvicorn ASGI server (version 0.23.2+) - Event-loop based async web server
- Async I/O throughout via `asyncio` module

**Package Manager:**
- UV (Astral package manager) - Version specified in `Dockerfile`
- Pip fallback (traditional package management available)
- Lockfile: `uv.lock` (present, defines exact dependency versions)

## Frameworks

**Core:**
- FastAPI (version 0.103.0+) - REST API framework with OpenAPI auto-documentation
- Uvicorn (version 0.23.2+) - ASGI application server

**Async/Messaging:**
- aiomqtt (version 1.0.0+) - Async MQTT client library; core infrastructure component for Wirenboard integration
- paho-mqtt (version 1.6.1+) - Traditional MQTT library (fallback/compatibility)
- websockets (version 15.0.1+) - WebSocket support

**Configuration & Validation:**
- Pydantic (version 2.11.0+) - Schema validation and type-safe configuration models
- python-dotenv (version 1.0.0+) - Environment variable loading from `.env` files
- pyyaml (version 6.0+) - YAML configuration parsing
- jsonschema (version 4.4.0+) - JSON schema validation

**Testing:**
- pytest (version 7.0.0+) - Test framework
- pytest-asyncio (version 0.18.0+) - Async test support (required for async device tests)
- pytest-mock (version 3.7.0+) - Mocking support
- pytest-cov (version 2.0+) - Code coverage reporting

**Code Quality:**
- black (version 21.0+) - Code formatter (line-length: 88 per `pyproject.toml`)
- mypy (version 0.9+) - Static type checker (strict settings in `pyproject.toml`)
- flake8 (version 3.9+) - Linting
- isort (black profile) - Import organization

**Build/Dev:**
- setuptools (version 42+) - Package building
- wheel - Wheel package distribution format

## Key Dependencies

**Critical Device Libraries:**

Device integrations are implemented via PyPI packages (Phase 1 migration complete):

- `asyncwebostv` (0.2.7) - LG WebOS TV control via `wb_mqtt_bridge.infrastructure.devices.lg_tv`
- `pyatv` (git commit f75e718) - Apple TV control via `wb_mqtt_bridge.infrastructure.devices.apple_tv`
- `pymotivaxmc2` (0.6.7) - Emotiva XMC2 processor control via `wb_mqtt_bridge.infrastructure.devices.emotiva_xmc2`
- `broadlink` (0.18.0+) - RF device control (Broadlink hub) via `wb_mqtt_bridge.infrastructure.devices.broadlink_kitchen_hood`
- `openhomedevice` (git branch: remove-lxml-dependency) - Auralic device UPnP/OpenHome control via `wb_mqtt_bridge.infrastructure.devices.auralic`

**Network & HTTP:**
- aiohttp (3.8.1+) - Async HTTP client; used for device communication
- httpx - Alternative HTTP client
- requests - Fallback synchronous HTTP client
- pyOpenSSL (23.2.0+) - SSL/TLS for device connections
- websockets (15.0.1+) - WebSocket support

**Data & Persistence:**
- aiosqlite (0.19.0+) - Async SQLite database client; implements `SQLiteStateStore` in `wb_mqtt_bridge.infrastructure.persistence.sqlite`
- pyyaml (6.0+) - YAML configuration files parsing

**System/Utilities:**
- psutil (7.0.0+) - Process and system utilities for health checks and monitoring
- typing_extensions (4.7.0+) - Extended type hint support for Python 3.11
- async_upnp_client - UPnP device discovery (transitive dependency via openhomedevice)

**Logging:**
- Python standard `logging` module with `TimedRotatingFileHandler` configured in `wb_mqtt_bridge.app.bootstrap.setup_logging()`

## Configuration

**Environment:**
- Configuration via `.env` file (example: `.env.example`)
- Required environment variables:
  - `MQTT_BROKER_HOST` - MQTT broker hostname (default: localhost)
  - `MQTT_BROKER_PORT` - MQTT broker port (default: 1883)
  - `MQTT_USERNAME` - MQTT authentication username (optional)
  - `MQTT_PASSWORD` - MQTT authentication password (optional)
  - `API_PORT` - Web service port (default: 8000)
  - `LOG_LEVEL` - Logging level (default: INFO)
  - `PYMOTIVAXMC2_PATH` - Path to pymotivaxmc2 dependency (for development)
  - `ASYNCWEBOSTV_PATH` - Path to asyncwebostv dependency (for development)
  - `ARCH` - Docker architecture override for Wirenboard 7 (e.g., arm32v7)

**Application Config Files:**
- `config/system.json` - MQTT broker, logging, and system-level settings
- `config/devices/` - Device-specific configurations (strongly typed with Pydantic models per device type)
- `config/scenarios/` - Scenario definitions (optional, for AV device sequences)

**Build:**
- `pyproject.toml` - Package metadata, dependencies, build configuration
- `uv.lock` - Locked dependency versions (managed by UV)
- `Dockerfile` - Multi-stage Docker build with lean optimization support
- `.dockerignore` - Docker build context filtering
- `setup.cfg` and `pyproject.toml` - setuptools configuration

**Development:**
- `mypy.ini` - Type checking configuration
- `.eslintrc` - Not applicable (Python project)
- `.prettierrc` - Not applicable (uses Black instead)
- `pytest.ini` - Configured inline in `pyproject.toml`

## Platform Requirements

**Development:**
- Python 3.11+
- Virtual environment support (venv or UV)
- Bash shell for scripts (`run_mypy.sh`, `manage_docker.sh`)

**Production:**
- Docker (Docker Compose optional)
- Running MQTT broker (Wirenboard native or external)
- Network access to controlled devices (LAN):
  - LG TV: WebSocket/HTTPS connection on port 3000 (default)
  - Apple TV: Local network discovery via mDNS
  - Auralic devices: UPnP/HTTP on port 49152+ (dynamic)
  - Broadlink hub: Network access on port 80
  - Emotiva XMC2: Network access on port 7002 (default)
  - Wirenboard IR devices: MQTT topic messaging

**Docker Deployment:**
- Base: `python:3.11-slim-bullseye` (Debian Bullseye)
- Target: Wirenboard 7 (ARMv7, 32-bit)
- Architecture multi-stage builds: Supports `arm32v7`, `amd64`, and other Docker buildx architectures
- APK/APT retries: `Acquire::Retries=3` for unreliable mirror access (ARM builds)
- Container healthcheck: HTTP GET to `http://localhost:8000/` every 30 seconds

## Console Scripts (Entry Points)

Defined in `pyproject.toml` under `[project.scripts]`:
- `wb-mqtt-bridge` / `wb-api` - Start web service: `uvicorn wb_mqtt_bridge.app:app`
- `wb-openapi` - Dump OpenAPI schema to `openapi.json`
- `mqtt-sniffer` - Monitor MQTT traffic for debugging
- `device-test` - Test individual device configurations
- `broadlink-cli` - Broadlink device management CLI
- `broadlink-discovery` - Discover Broadlink devices on network

---

*Stack analysis: 2026-05-20*
