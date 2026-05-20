# Codebase Structure

**Analysis Date:** 2026-05-20

## Directory Layout

```
wb-mqtt-bridge/
├── src/wb_mqtt_bridge/          # Main Python package
│   ├── app/                      # FastAPI bootstrap and entry point
│   │   ├── __init__.py           # Exports FastAPI app instance
│   │   ├── bootstrap.py          # create_app() + lifespan setup
│   │   └── main.py               # Console entry point (uvicorn runner)
│   │
│   ├── domain/                   # Pure business logic (no I/O)
│   │   ├── ports.py              # Abstract ports (MessageBusPort, DeviceBusPort, StateRepositoryPort)
│   │   ├── devices/              # Device management domain
│   │   │   ├── models.py         # State models (BaseDeviceState, LgTvState, etc.)
│   │   │   └── service.py        # DeviceManager (load, initialize, route messages)
│   │   ├── scenarios/            # Scenario system domain
│   │   │   ├── models.py         # ScenarioDefinition, ScenarioState
│   │   │   ├── scenario.py       # Scenario execution logic
│   │   │   └── service.py        # ScenarioManager (load, start, shutdown)
│   │   └── rooms/                # Room management domain
│   │       └── service.py        # RoomManager
│   │
│   ├── infrastructure/           # External adapters and implementations
│   │   ├── devices/              # Device driver implementations (7 drivers)
│   │   │   ├── base.py           # BaseDevice abstract class (lifecycle, action dispatch)
│   │   │   ├── lg_tv/
│   │   │   │   └── driver.py     # LgTv (WebOS TV) driver
│   │   │   ├── apple_tv/
│   │   │   │   └── driver.py     # AppleTVDevice driver
│   │   │   ├── auralic/
│   │   │   │   └── driver.py     # AuralicDevice driver
│   │   │   ├── emotiva_xmc2/
│   │   │   │   └── driver.py     # EMotivaXMC2 (receiver) driver
│   │   │   ├── broadlink_kitchen_hood/
│   │   │   │   └── driver.py     # BroadlinkKitchenHood driver
│   │   │   ├── wirenboard_ir_device/
│   │   │   │   └── driver.py     # WirenboardIRDevice (MSW V3 IR) driver
│   │   │   └── revox_a77_reel_to_reel/
│   │   │       └── driver.py     # RevoxA77ReelToReel driver
│   │   ├── mqtt/                 # MQTT client (MessageBusPort adapter)
│   │   │   └── client.py         # MQTTClient (aiomqtt wrapper)
│   │   ├── persistence/          # State storage (StateRepositoryPort adapter)
│   │   │   └── sqlite.py         # SQLiteStateStore (aiosqlite wrapper)
│   │   ├── config/               # Configuration management
│   │   │   ├── manager.py        # ConfigManager (load/validate JSON configs)
│   │   │   └── models.py         # Pydantic config models (BaseDeviceConfig subclasses, SystemConfig, etc.)
│   │   ├── wb_device/            # Wirenboard virtual device emulation
│   │   │   └── service.py        # WBVirtualDeviceService (publishes devices as WB virtual devices)
│   │   ├── scenarios/            # Scenario infrastructure
│   │   │   ├── models.py         # ScenarioWBConfig (WB mapping)
│   │   │   └── wb_adapter.py     # ScenarioWBAdapter (publishes scenarios as WB devices)
│   │   └── maintenance/          # System maintenance
│   │       └── wirenboard_guard.py # WirenboardMaintenanceGuard
│   │
│   ├── presentation/             # HTTP API layer
│   │   └── api/
│   │       ├── routers/          # FastAPI route handlers
│   │       │   ├── devices.py    # Device CRUD, actions, config
│   │       │   ├── scenarios.py  # Scenario start/switch/shutdown/state
│   │       │   ├── rooms.py      # Room endpoints
│   │       │   ├── state.py      # Device/scenario state query
│   │       │   ├── events.py     # SSE endpoints
│   │       │   ├── mqtt.py       # MQTT publish endpoint
│   │       │   ├── groups.py     # Action group endpoints
│   │       │   ├── system.py     # System info/health
│   │       │   └── __init__.py   # Router import/export
│   │       ├── schemas.py        # Pydantic response schemas
│   │       └── sse_manager.py    # SSE channel management, fanout
│   │
│   ├── cli/                      # Command-line utilities
│   │   ├── device_test.py        # Device testing tool
│   │   ├── mqtt_sniffer.py       # MQTT traffic monitor
│   │   ├── broadlink_discovery.py # Broadlink device discovery
│   │   ├── broadlink_cli.py      # Broadlink command CLI
│   │   └── dump_openapi.py       # Export OpenAPI schema
│   │
│   ├── utils/                    # Cross-cutting utilities
│   │   ├── types.py              # CommandResult, CommandResponse, StateT type variable
│   │   ├── class_loader.py       # Dynamic class resolution (for config_class, device_class)
│   │   ├── validation.py         # Runtime validation helpers
│   │   └── serialization_utils.py # JSON serialization for state/config
│   │
│   ├── __init__.py               # Package export
│   └── __version__.py            # Version string
│
├── config/                       # Configuration files (JSON)
│   ├── system.json               # System config (MQTT broker, logging, persistence, etc.)
│   ├── devices/                  # Device configurations
│   │   ├── lg_tv.json           # LG TV config example
│   │   ├── apple_tv.json        # Apple TV config example
│   │   └── ...                   # Other device configs
│   └── scenarios/                # Scenario definitions
│       ├── watch_tv.json        # Example scenario
│       └── ...                   # Other scenarios
│
├── tests/                        # Test suite
│   ├── conftest.py               # Pytest fixtures (MQTT broker, config, mocks)
│   ├── test_*.py                 # Test modules (unit, integration)
│   ├── devices/                  # Device-specific tests
│   │   ├── test_lg_tv.py
│   │   ├── test_apple_tv.py
│   │   └── ...
│   ├── mock_sqlite.py            # SQLite mock for tests
│   ├── device_test.py            # Device test helper
│   └── ...
│
├── docs/                         # Documentation
│   ├── architecture.md           # Architecture overview
│   ├── ui_backend_contract.md    # UI↔backend API contract
│   ├── adr/                      # Architecture Decision Records
│   └── ...
│
├── Dockerfile                    # Docker image definition
├── .dockerignore                 # Docker build exclusions
├── pyproject.toml                # Project metadata, dependencies, scripts, entry-points
├── mypy.ini                      # MyPy type checker config
├── README.md                     # Project overview
└── .env.example                  # Example environment file
```

## Directory Purposes

**`src/wb_mqtt_bridge/app/`:**
- Purpose: FastAPI application setup, dependency injection, and console entry point.
- Contains: `create_app()` (FastAPI factory), `lifespan` context manager (startup/shutdown hooks), logging setup, console runner.
- Key files: `bootstrap.py` (orchestrates all component initialization), `main.py` (uvicorn entry point).

**`src/wb_mqtt_bridge/domain/`:**
- Purpose: Pure business logic isolated from external dependencies.
- Contains: service classes (DeviceManager, ScenarioManager, RoomManager), state models, abstract ports.
- Key files: `ports.py` (MessageBusPort, DeviceBusPort, StateRepositoryPort ABCs), `devices/service.py` (device orchestration), `scenarios/service.py` (scenario orchestration).

**`src/wb_mqtt_bridge/infrastructure/`:**
- Purpose: External system adapters and implementations.
- Contains: device drivers (7 implementations), MQTT client, SQLite store, config loader, WB emulation.
- Key files: `devices/base.py` (BaseDevice abstract class), `mqtt/client.py` (MQTT adapter), `persistence/sqlite.py` (state store), `config/manager.py` (config loader).

**`src/wb_mqtt_bridge/presentation/`:**
- Purpose: HTTP API and real-time event delivery.
- Contains: FastAPI routers (8 endpoint modules), response schemas, SSE fanout manager.
- Key files: `api/routers/` (endpoint implementations), `api/sse_manager.py` (SSE channel management).

**`src/wb_mqtt_bridge/cli/`:**
- Purpose: Standalone command-line utilities.
- Contains: device testing, MQTT monitoring, Broadlink discovery, OpenAPI export.
- Entry points: Registered in `pyproject.toml` as console scripts (mqtt-sniffer, device-test, etc.).

**`src/wb_mqtt_bridge/utils/`:**
- Purpose: Shared utilities and type definitions.
- Contains: command/response types, dynamic class loader, validation helpers, serialization utilities.
- Used by: all layers (domain, infrastructure, presentation).

**`config/`:**
- Purpose: Runtime JSON configuration.
- Contains: `system.json` (MQTT, logging, persistence), `devices/*.json` (per-device config), `scenarios/*.json` (scenario definitions).
- Loaded at startup: ConfigManager reads all files, validates via Pydantic models, injects into services.

**`tests/`:**
- Purpose: Automated test suite.
- Contains: unit tests (mocked externals), integration tests (with real MQTT/SQLite mocks).
- Fixture: `conftest.py` provides reusable pytest fixtures (config, MQTT mock, async runner).
- Device tests: Follow hexagonal pattern (mock external deps, drive handlers directly, assert state mutations).

**`docs/`:**
- Purpose: Human-readable documentation (architecture, contracts, decisions).
- Contains: `architecture.md` (system overview), `ui_backend_contract.md` (API spec for UI), `adr/` (architecture decision records).

## Key File Locations

**Entry Points:**
- `src/wb_mqtt_bridge/app/bootstrap.py::create_app()` - FastAPI app factory (called by Uvicorn).
- `src/wb_mqtt_bridge/app/main.py::main()` - Console entry point (called by `wb-mqtt-bridge` / `wb-api` script).
- `src/wb_mqtt_bridge/cli/mqtt_sniffer.py::main()` - MQTT monitor CLI (called by `mqtt-sniffer` script).
- `src/wb_mqtt_bridge/cli/device_test.py::main()` - Device test CLI (called by `device-test` script).

**Configuration:**
- `config/system.json` - System settings (MQTT broker, logging, persistence path, action groups, maintenance).
- `config/devices/*.json` - Per-device config (device_id, device_name, device_class, config_class, MQTT topics, commands, device-specific sections).
- `config/scenarios/*.json` - Scenario definitions (scenario_id, devices, roles, startup/shutdown sequences).

**Core Logic:**
- `src/wb_mqtt_bridge/domain/devices/service.py` - DeviceManager (load drivers, instantiate, route messages, persist state).
- `src/wb_mqtt_bridge/domain/scenarios/service.py` - ScenarioManager (load scenarios, manage transitions, persist state).
- `src/wb_mqtt_bridge/infrastructure/devices/base.py` - BaseDevice (abstract base for all drivers; lifecycle, action dispatch, WB emulation).
- `src/wb_mqtt_bridge/infrastructure/mqtt/client.py` - MQTTClient (MQTT connection, pub/sub, message routing).
- `src/wb_mqtt_bridge/infrastructure/persistence/sqlite.py` - SQLiteStateStore (JSON persistence layer).

**Testing:**
- `tests/conftest.py` - Pytest fixtures (config, MQTT broker mock, async test setup).
- `tests/devices/` - Device-specific tests (LG TV, Apple TV, Auralic, Emotiva, Broadlink, Wirenboard IR, Revox).
- `tests/test_integration.py` - Full service integration tests (MQTT, state persistence, API).

## Naming Conventions

**Files:**
- Drivers: `{device_name}_driver.py` (e.g., `lg_tv/driver.py`). Main class exported: `LgTv`, `AppleTVDevice`, etc.
- Configs: `{name}.json` (e.g., `device_id.json`, `scenario_id.json`). Top-level keys match schema expectations.
- Tests: `test_{module}.py` (e.g., `test_lg_tv.py`) or `test_{feature}.py` (e.g., `test_integration.py`).
- Utilities: `{purpose}.py` (e.g., `validation.py`, `serialization_utils.py`).

**Functions/Classes:**
- Device drivers: PascalCase (e.g., `LgTv`, `AppleTVDevice`, `BroadlinkKitchenHood`).
- Managers: PascalCase with "Manager" suffix (e.g., `DeviceManager`, `ScenarioManager`).
- Services: PascalCase with "Service" suffix (e.g., `WBVirtualDeviceService`, `ConfigManager`).
- Action handlers: `handle_{action_name}` (e.g., `handle_power_on`, `handle_volume_up`). All async.
- Ports: PascalCase with "Port" suffix (e.g., `MessageBusPort`, `DeviceBusPort`, `StateRepositoryPort`).

**Variables/Attributes:**
- Config instances: snake_case (e.g., `mqtt_broker`, `system_config`).
- State fields: snake_case (e.g., `device_id`, `power`, `volume`).
- MQTT topics: snake_case with forward slashes (e.g., `devices/lg_tv_living_room/power`).

**Directories:**
- Domain/infrastructure layers: snake_case (e.g., `devices`, `scenarios`, `wb_device`).
- Device driver dirs: snake_case (e.g., `lg_tv`, `apple_tv`, `broadlink_kitchen_hood`).

## Where to Add New Code

**New Device Driver:**
1. Create directory: `src/wb_mqtt_bridge/infrastructure/devices/{device_name}/`
2. Create driver file: `src/wb_mqtt_bridge/infrastructure/devices/{device_name}/driver.py` with class inheriting `BaseDevice(Generic[StateT])`
3. Add state model: add subclass of `BaseDeviceState` in `src/wb_mqtt_bridge/domain/devices/models.py` (e.g., `NewDeviceState`)
4. Add config model: add subclass of `BaseDeviceConfig` in `src/wb_mqtt_bridge/infrastructure/config/models.py` (e.g., `NewDeviceConfig`)
5. Register driver: add entry-point in `pyproject.toml`: `new_device = "wb_mqtt_bridge.infrastructure.devices.{device_name}.driver:NewDeviceClass"`
6. Create device config: `config/devices/{device_id}.json` with `device_class: "NewDeviceClass"`, `config_class: "NewDeviceConfig"`
7. Add tests: `tests/devices/test_{device_name}.py` following the hexagonal test pattern (mock external deps, drive handlers, assert state mutations).

**New API Endpoint:**
1. Create router file: `src/wb_mqtt_bridge/presentation/api/routers/{feature}.py` using FastAPI APIRouter.
2. Define schemas: add Pydantic models to `src/wb_mqtt_bridge/presentation/api/schemas.py`.
3. Register router: import and include in `src/wb_mqtt_bridge/app/bootstrap.py::create_app()` (lines ~280+ in `app.include_router(...)`).
4. Add route initialization: if the router needs manager instances, call `initialize(...)` in bootstrap's lifespan (startup phase).
5. Add tests: `tests/test_{feature}.py` testing the endpoint with mocked managers.

**New Domain Service:**
1. Create service: `src/wb_mqtt_bridge/domain/{feature}/service.py` with a service class (no I/O, use ports for external communication).
2. Define models: create `src/wb_mqtt_bridge/domain/{feature}/models.py` with Pydantic state/definition models.
3. Implement ports: if the service needs MQTT or state store, declare dependencies on `MessageBusPort` / `StateRepositoryPort` (don't import concrete MQTTClient/SQLiteStateStore).
4. Integrate: instantiate in bootstrap's lifespan, inject ports from infrastructure.
5. Add tests: `tests/test_{feature}.py` with mocked ports.

**New Scenario Feature:**
1. Scenario definitions live in `config/scenarios/*.json` (no code changes needed for new scenario logic).
2. If adding a new scenario action type, extend `Scenario` class in `src/wb_mqtt_bridge/domain/scenarios/scenario.py`.
3. Test: add scenario JSON to test fixtures, test via `ScenarioManager` in `tests/test_scenarios.py`.

**Utilities / Cross-Cutting:**
1. Add to `src/wb_mqtt_bridge/utils/{purpose}.py`.
2. Export from `src/wb_mqtt_bridge/utils/__init__.py` if widely used.
3. Use: import across layers (domain can import utils/types.py, infrastructure can import utils/class_loader.py, etc.).

## Special Directories

**`src/wb_mqtt_bridge.egg-info/`:**
- Purpose: Package metadata (generated by setuptools).
- Generated: Yes
- Committed: No (in .gitignore)

**`.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `__pycache__/`:**
- Purpose: Build/test artifacts.
- Generated: Yes
- Committed: No (in .gitignore)

**`data/`, `logs/`:**
- Purpose: Runtime output directories (persistence, logs).
- Generated: Yes (created at startup if missing)
- Committed: No (in .gitignore)

**`config/`:**
- Purpose: Configuration files (JSON).
- Generated: No
- Committed: Yes (part of app deployment; examples included)

**`.planning/codebase/`:**
- Purpose: GSD codebase mapping documents (written by /gsd:map-codebase).
- Generated: Yes
- Committed: Yes (tracked for continuous reference by other GSD commands)

---

*Structure analysis: 2026-05-20*
