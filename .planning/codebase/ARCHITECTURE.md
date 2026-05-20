<!-- refreshed: 2026-05-20 -->
# Architecture

**Analysis Date:** 2026-05-20

## System Overview

A Python 3.11 async web service that bridges Wirenboard / AV-equipment devices to a FastAPI HTTP API and MQTT broker. It exposes each device's actions over REST and MQTT, streams live state over SSE, persists state to SQLite, emulates Wirenboard virtual devices, and runs Logitech-Harmony-style scenarios across devices.

```text
┌────────────────────────────────────────────────────────────────┐
│           presentation/ (FastAPI routers, SSE, schemas)        │
│         `src/wb_mqtt_bridge/presentation/api/routers/`        │
│      Handles HTTP requests/responses, OpenAPI, SSE fanout      │
└────────────────────┬─────────────────────────────────────────┘
                     │ calls domain services
┌────────────────────▼─────────────────────────────────────────┐
│  domain/ (DeviceManager, ScenarioManager, RoomManager, PORTS) │
│        `src/wb_mqtt_bridge/domain/{devices,scenarios,rooms}/`  │
│   Pure business logic with no external I/O dependencies        │
└────────────────────┬─────────────────────────────────────────┘
          ports (ABCs) │  implemented by
┌────────────────────▼─────────────────────────────────────────┐
│  infrastructure/ (device drivers, MQTT, SQLite, config,        │
│       WB emulation, scenarios WB adapter)                      │
│  `src/wb_mqtt_bridge/infrastructure/{devices,mqtt,...}/`       │
└────────────────────┬─────────────────────────────────────────┘
                     │
         ┌───────────┼───────────┐
         ▼           ▼           ▼
    MQTT Broker   SQLite DB   External
                              (LG TV, Apple TV,
                               Broadlink, etc.)

     app/ wires it all together (create_app + lifespan).
    cli/ = console tools (mqtt-sniffer, device-test, etc.)
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| **DeviceManager** | Load device classes via entry points, instantiate from configs, route MQTT messages to handlers, persist state | `src/wb_mqtt_bridge/domain/devices/service.py` |
| **ScenarioManager** | Load scenario definitions, manage transitions, execute startup/shutdown sequences, persist scenario state | `src/wb_mqtt_bridge/domain/scenarios/service.py` |
| **RoomManager** | Manage room definitions and state | `src/wb_mqtt_bridge/domain/rooms/service.py` |
| **MQTTClient** | Connect to broker, subscribe to topics, route messages to handlers, publish commands | `src/wb_mqtt_bridge/infrastructure/mqtt/client.py` |
| **SQLiteStateStore** | Persist device and scenario state as JSON blobs under typed keys | `src/wb_mqtt_bridge/infrastructure/persistence/sqlite.py` |
| **ConfigManager** | Load and validate JSON configs (system, devices, scenarios); resolve device_class and config_class via class loader | `src/wb_mqtt_bridge/infrastructure/config/manager.py` |
| **BaseDevice** | Abstract base for all device drivers; lifecycle, action dispatch, WB emulation setup | `src/wb_mqtt_bridge/infrastructure/devices/base.py` |
| **WBVirtualDeviceService** | Emulate devices as Wirenboard virtual devices on MQTT | `src/wb_mqtt_bridge/infrastructure/wb_device/service.py` |
| **FastAPI Routers** | HTTP endpoints for devices, scenarios, rooms, state, events (SSE), MQTT, groups | `src/wb_mqtt_bridge/presentation/api/routers/{devices,scenarios,rooms,state,events,mqtt,groups,system}.py` |
| **SSEManager** | Fan-out state changes to connected WebSocket/SSE clients | `src/wb_mqtt_bridge/presentation/api/sse_manager.py` |

## Pattern Overview

**Overall:** Hexagonal Architecture (ports & adapters) with domain-centric design.

**Key Characteristics:**
- Dependencies point **inward**: presentation and infrastructure depend on domain; domain depends only on ports (ABCs).
- **Ports** are abstract interfaces (MessageBusPort, DeviceBusPort, StateRepositoryPort) defined in `domain/ports.py`; **adapters** implement them in infrastructure.
- **Device plugin system**: drivers registered via setuptools entry-points, loaded at startup via `entry_points()` API.
- **Typed configuration**: all device configs are Pydantic models, resolved at runtime by class name (e.g., `config_class: "LgTvConfig"`).
- **Async-first**: FastAPI + aiomqtt + aiosqlite; all I/O is non-blocking.
- **State-as-models**: device and scenario state stored as BaseDeviceState / ScenarioState subclasses (Pydantic).

## Layers

**Presentation (`presentation/`):**
- Purpose: HTTP API and server-sent events (SSE) for the UI.
- Location: `src/wb_mqtt_bridge/presentation/api/routers/`
- Contains: FastAPI routers (devices, scenarios, rooms, state, events, mqtt, groups, system), OpenAPI schema injection, SSE channel management.
- Depends on: domain services (DeviceManager, ScenarioManager, RoomManager).
- Used by: HTTP clients (UI, CLI tools).

**Domain (`domain/`):**
- Purpose: Pure business logic, no I/O or external dependencies.
- Location: `src/wb_mqtt_bridge/domain/{devices,scenarios,rooms}/`
- Contains: service classes (DeviceManager, ScenarioManager, RoomManager), state models (BaseDeviceState, ScenarioState), scenario logic, and **ports** (ABCs for MessageBusPort, DeviceBusPort, StateRepositoryPort).
- Depends on: only Pydantic for models; **ports** for external communication.
- Used by: presentation layer, infrastructure adapters.

**Infrastructure (`infrastructure/`):**
- Purpose: Implement domain ports; device drivers; external system adapters.
- Location: `src/wb_mqtt_bridge/infrastructure/{devices,mqtt,persistence,config,wb_device,scenarios,maintenance}/`
- Contains: 7 device drivers (LG TV, Apple TV, Auralic, Emotiva XMC2, Broadlink Kitchen Hood, Wirenboard IR, Revox A77), MQTT client (aiomqtt), SQLite state store, config manager, WB virtual device emulation, scenario WB adapter, maintenance guard.
- Depends on: domain (services, models, ports), external libraries (aiomqtt, aiosqlite, asyncwebostv, pyatv, broadlink, etc.).
- Used by: app layer (dependency injection).

**App (`app/`):**
- Purpose: Bootstrap and wiring (dependency injection, FastAPI setup, lifespan management).
- Location: `src/wb_mqtt_bridge/app/{bootstrap.py,main.py}`
- Contains: `create_app()` function (builds FastAPI + lifespan), logging setup, console entry point.
- Depends on: all layers (orchestrates them).

**CLI (`cli/`):**
- Purpose: Command-line utilities (standalone tools, not tied to the web service lifecycle).
- Location: `src/wb_mqtt_bridge/cli/`
- Contains: mqtt-sniffer, device-test, broadlink discovery/CLI, OpenAPI dump.

**Utils (`utils/`):**
- Purpose: Cross-cutting concerns (serialization, validation, class loading, type definitions).
- Location: `src/wb_mqtt_bridge/utils/`
- Contains: `types.py` (CommandResult, CommandResponse, StateT type variable), `class_loader.py`, `validation.py`, `serialization_utils.py`.

## Data Flow

### HTTP Action Request (Device Command)

1. **Entry:** `POST /devices/{id}/action` (`presentation/api/routers/devices.py:execute_action`)
2. **Domain dispatch:** `DeviceManager.execute_device_action(device_id, action, params)`
3. **Driver execution:** `device.execute_action(action, params)` dispatches to handler (e.g., `handle_power_on`)
4. **Handler logic:** action handler updates `self.state` (mutable BaseDeviceState), returns `CommandResult`
5. **State persistence:** `StateRepositoryPort.set(f"device:{device_id}", serialized_state)`
6. **MQTT publish:** handler may return `mqtt_command` dict; routed to `MQTTClient.publish(topic, payload)`
7. **Response:** `CommandResponse` (success, device_id, action, state, error?, mqtt_command?, data?) sent to client
8. **SSE fanout:** SSEManager broadcasts `device:state_changed` event to all listeners

### Inbound MQTT Message (Device State Update)

1. **Receive:** MQTTClient subscribed to device topics (via `device.subscribe_topics()`)
2. **Route:** message triggers handler registered at subscribe time → calls `DeviceManager.get_message_handler(device_id)`
3. **Handler:** `device.handle_message(topic, payload)` parses MQTT payload, updates `self.state`
4. **Persist:** state saved via `StateRepositoryPort.set(...)`
5. **SSE fanout:** event broadcast to connected clients

### Scenario Execution

1. **Start:** `POST /scenario/start/{scenario_id}` → `ScenarioManager.start_scenario(scenario_id)`
2. **Load definition:** scenario definition from JSON, validate, create Scenario instance
3. **Device dispatch:** scenario startup sequence calls each coordinated device's actions
4. **State tracking:** `ScenarioState` records active scenario and per-device states
5. **Persist:** scenario state saved via `StateRepositoryPort.set(f"scenario:{scenario_id}", ...)`
6. **WB emulation:** `ScenarioWBAdapter` publishes scenario as virtual Wirenboard device

### Wirenboard Virtual Device Emulation

1. **Setup (startup):** after MQTT connects, for each device: `device.setup_wb_emulation_if_enabled()`
2. **Publish:** `WBVirtualDeviceService.setup_wb_device_from_config(config, command_executor, ...)` publishes device metadata and controls to Wirenboard-standard MQTT topics
3. **Command callback:** when Wirenboard sends MQTT command to virtual device, callback routes to device action handler
4. **Command execution:** device executes action, updates state, returns result
5. **State publish:** new state published back to Wirenboard topics

### State Persistence and Recovery

1. **Startup:** `DeviceManager.initialize()` reads persisted state from SQLite (key: `device:{device_id}`)
2. **Deserialize:** SQLiteStateStore.get(key) returns JSON; DeviceManager reconstructs typed state models
3. **Restore:** each device's `self.state` updated with persisted values
4. **Scenario state:** ScenarioManager reads `scenario:{scenario_id}` and restores active scenario
5. **Shutdown:** `DeviceManager.shutdown()` and `ScenarioManager.shutdown()` flush final state to store before close

**State Management:**
- Device state: mutable `BaseDeviceState` subclass instance on each device; serialized to SQLite on every action.
- Scenario state: `ScenarioState` (current scenario ID, per-device role states); persisted in SQLite.
- Configuration: immutable Pydantic models, loaded once at startup from JSON files.

## Key Abstractions

**BaseDevice (Generic[StateT]):**
- Purpose: Abstract base for all device implementations; defines lifecycle and action dispatch.
- Examples: `LgTv`, `AppleTVDevice`, `EMotivaXMC2`, `BroadlinkKitchenHood`, `WirenboardIRDevice`, `AuralicDevice`, `RevoxA77ReelToReel` (all in `infrastructure/devices/*/driver.py`).
- Pattern: each driver subclasses BaseDevice, declares its state type (e.g., `LgTvState`), registers action handlers via `_register_handlers()` or `handle_<action>` naming convention, implements `subscribe_topics()`, `async setup()`, `async shutdown()`, `async handle_message(topic, payload)`.

**BaseDeviceState:**
- Purpose: Strongly-typed device state model (Pydantic BaseModel).
- Examples: `LgTvState`, `AppleTVState`, `EmotivaXMC2State`, `AuralicDeviceState`, `KitchenHoodState`, `WirenboardIRState`, `RevoxA77ReelToReelState` (all in `domain/devices/models.py`).
- Pattern: each device driver declares its state subclass with device-specific fields (e.g., `power: str`, `volume: int`, `app_name: str` for LG TV); BaseDeviceState provides common fields (device_id, device_name, last_command, error, power).

**Ports (Abstract Base Classes):**
- `MessageBusPort` (domain/ports.py): `async publish(topic, payload, qos, retain)`, `async subscribe(topic, callback)`, `async connect()`, `async disconnect()`. Implemented by `MQTTClient`.
- `DeviceBusPort` (domain/ports.py): `async send(command, params)`, `async connect()`, `async disconnect()`, etc. Implemented by each `BaseDevice` subclass.
- `StateRepositoryPort` (domain/ports.py): `async get(key)`, `async set(key, value)`, `async initialize()`, `async close()`. Implemented by `SQLiteStateStore`.

**ConfigManager / Typed Configs:**
- Purpose: Load and validate typed device/scenario/system configuration from JSON.
- Pattern: JSON file declares `device_class` (e.g., "LgTv") and `config_class` (e.g., "LgTvConfig"); ConfigManager resolves both via `utils/class_loader.py`, instantiates the config model, injects it into the device class constructor.

**Scenario:**
- Purpose: Logitech-Harmony-style orchestration of devices for an activity.
- Examples: "watch Apple TV" (power on AV receiver, switch input, set light brightness), "music listening" (stereo mode, Auralic input).
- Pattern: scenario definition JSON declares devices, roles (e.g., receiver: "emotiva_xmc2", source: "auralic"), and sequences (startup steps, shutdown steps); `ScenarioManager` loads, validates, and executes scenarios; `ScenarioWBAdapter` publishes them as WB virtual devices.

## Entry Points

**HTTP API (FastAPI):**
- Location: `src/wb_mqtt_bridge/app/bootstrap.py::create_app()`
- Triggers: Uvicorn startup (`uvicorn.run(...)` in `app/main.py:main()`)
- Responsibilities: create FastAPI app, install CORS middleware, set up lifespan context, register routers (devices, scenarios, rooms, state, events, mqtt, groups, system), inject OpenAPI state model overrides.

**MQTT Connection (MQTTClient):**
- Location: `app/bootstrap.py::lifespan` (startup phase)
- Triggers: FastAPI startup
- Responsibilities: instantiate MQTTClient with broker config, call `connect_and_subscribe()` with device topic handlers, wait for connection, log status.

**Device Initialization (DeviceManager):**
- Location: `app/bootstrap.py::lifespan` (startup phase)
- Triggers: after MQTT client created, before topics subscribed
- Responsibilities: `load_device_modules()` (discover drivers via entry-points), `initialize_devices()` (load device configs, instantiate drivers, inject MQTT/WB services), `initialize()` (restore persisted state), subscribe to topics.

**Scenario & Room Initialization:**
- Location: `app/bootstrap.py::lifespan` (startup phase)
- Triggers: after DeviceManager and MQTT initialized
- Responsibilities: `ScenarioManager.initialize()` (load scenarios, restore active scenario), `RoomManager.initialize()` (load rooms), `ScenarioWBAdapter` (set up WB virtual devices for scenarios).

**Shutdown (Lifespan Cleanup):**
- Location: `app/bootstrap.py::lifespan` (shutdown phase)
- Triggers: FastAPI shutdown (Ctrl+C, SIGTERM, etc.)
- Responsibilities: SSE drain, cancel background tasks, call `device.shutdown()` and `scenario.shutdown()`, flush final state to SQLite, close MQTT client, close database connection.

## Architectural Constraints

- **Threading:** Single-threaded event loop (async/await with asyncio). No worker threads for I/O; all external communication is async-awaited.
- **Global state:** None (all state managed by service instances; FastAPI dependency injection via lifespan). Config is immutable post-startup.
- **Circular imports:** None by design (dependencies point inward; ports ensure domain is self-contained).
- **Entry-point discovery:** Device drivers must be registered in `pyproject.toml` under `[project.entry-points."wb_mqtt_bridge.devices"]` to be discoverable at startup; no dynamic registration.
- **Configuration:** Immutable JSON files on disk; no hot-reload. Errors in config block startup (fail-fast).
- **MQTT topics:** Standardized by device (each driver's `subscribe_topics()` returns list of topics it monitors). Wirenboard virtual device topics follow Wirenboard conventions.
- **State serialization:** All state models must be Pydantic BaseModel subclasses to serialize/deserialize to/from SQLite JSON.

## Anti-Patterns

### Blocking I/O in Domain/Handlers

**What happens:** A device handler calls `requests.get(...)` or `time.sleep(...)` instead of `async` equivalents.
**Why it's wrong:** Blocks the event loop; other devices and HTTP requests starve.
**Do this instead:** Use `aiohttp.ClientSession` or `await asyncio.sleep(...)` in all device handlers. All handlers are async, declared as `async def handle_<action>(...)`.

### Bypassing Ports (Direct Library Calls)

**What happens:** A device handler imports and calls external libraries directly (e.g., `import broadlink; device.send_command(...)`) instead of delegating through the port-defined `send()` method.
**Why it's wrong:** Violates hexagonal architecture; makes domain layer aware of infrastructure choices; breaks testability.
**Do this instead:** Device drivers inherit from `BaseDevice(DeviceBusPort)` and implement the port interface; domain services depend on ports, not on concrete implementations. External library calls stay in drivers (infrastructure).

### Mutable Config After Startup

**What happens:** Device config is modified during operation (e.g., config dict reassigned) without persisting to JSON.
**Why it's wrong:** Changes are lost on restart; breaks the contract with UI (config is static).
**Do this instead:** Configs are immutable after startup. If a device needs runtime tuneable parameters, store them in state (BaseDeviceState subclass) and persist via StateRepositoryPort.

### SQLite State Without Serialization Check

**What happens:** Device state contains a field that isn't Pydantic-serializable (e.g., a raw socket object) and is saved to SQLite.
**Why it's wrong:** Serialization fails at runtime; state persists incorrectly; recovery on restart corrupts.
**Do this instead:** All state fields must be JSON-serializable (strings, ints, bools, dicts, lists, or Pydantic models). Complex types (sockets, client objects) are never stored in state; they live on the driver instance (not persisted).

### SSE Events Without Fanout Manager

**What happens:** A handler publishes state changes directly via `print()` or custom websocket logic instead of calling `SSEManager.publish()`.
**Why it's wrong:** UI doesn't receive live updates; testing is impossible; SSE channels aren't managed.
**Do this instead:** Call `sse_manager.publish(channel, event_data)` in BaseDevice after state mutation. SSEManager handles all fanout (see `presentation/api/sse_manager.py`).

## Error Handling

**Strategy:** Defensive (validate early, fail loudly, propagate exceptions up to HTTP/MQTT handlers).

**Patterns:**
- Configuration validation: Pydantic model parsing in ConfigManager; invalid JSON/schema causes startup failure (intended).
- Device action handlers: catch business logic errors, return `CommandResult(success=False, error=...)`, propagate to `CommandResponse`.
- MQTT message handlers: catch parse/dispatch errors; log and continue (don't block other devices).
- HTTP endpoints: FastAPI auto-converts exceptions to HTTP 500/400; custom exception handlers log details.

## Cross-Cutting Concerns

**Logging:** Configured in `app/bootstrap.py::setup_logging()` with daily rotating file handler + console. Levels per-logger configurable via `system.json`. All modules log via `logging.getLogger(__name__)`.

**Validation:** Pydantic models (config, state, request schemas) validate on construction. `utils/validation.py` provides helpers for runtime validation of device-specific parameters.

**Authentication:** MQTT client supports optional username/password (from `system.json`). HTTP API has no built-in auth (assumed to run in trusted network or behind reverse proxy with auth).

---

*Architecture analysis: 2026-05-20*
