# Architecture — wb-mqtt-bridge

**Status:** current (2026-05-20). A map of the backend for humans and onboarding/agent
tooling. The cross-repo contract with the UI is documented separately in
[`ui_backend_contract.md`](ui_backend_contract.md).

## What this service is

A Python (3.11) async service that bridges Wirenboard / AV-equipment devices to a
FastAPI HTTP API and an MQTT broker. It exposes each device's actions over REST + MQTT,
streams live state over SSE, persists state to SQLite, emulates Wirenboard virtual
devices, and runs Logitech-Harmony-style **scenarios** across devices.

## Hexagonal layering

The code is organized domain-centric (ports & adapters). Dependencies point **inward**:
`presentation` and `infrastructure` depend on `domain`; `domain` depends on nothing
external (it talks to the outside only through **ports**).

```
                ┌───────────────────────────────────────────────┐
                │ presentation/  (FastAPI routers, SSE, schemas) │
                └───────────────────────┬───────────────────────┘
                                        │ calls
                ┌───────────────────────▼───────────────────────┐
                │ domain/  (DeviceManager, ScenarioManager,      │
                │          RoomManager, models, PORTS)           │
                └───────────────────────┬───────────────────────┘
                          ports (ABCs)  │  implemented by
                ┌───────────────────────▼───────────────────────┐
                │ infrastructure/ (device drivers, MQTT client,  │
                │   SQLite store, config, WB emulation)          │
                └────────────────────────────────────────────────┘
   app/ wires it all together (create_app + lifespan).  cli/ = console tools.
```

### Directory map (`src/wb_mqtt_bridge/`)

| Path | Layer | Contents |
|---|---|---|
| `domain/ports.py` | domain | The seams: `MessageBusPort`, `DeviceBusPort`, `StateRepositoryPort` (ABCs). |
| `domain/devices/` | domain | `service.py` (`DeviceManager`), `models.py` (state models, `BaseDeviceState`, `LastCommand`). |
| `domain/scenarios/` | domain | `service.py` (`ScenarioManager`), `scenario.py`, `models.py` (`ScenarioState`, definitions). |
| `domain/rooms/` | domain | `service.py` (`RoomManager`). |
| `infrastructure/devices/<name>/driver.py` | infra | The 7 device drivers (subclass `BaseDevice`). `base.py` = `BaseDevice`. |
| `infrastructure/mqtt/client.py` | infra | `MQTTClient` (implements `MessageBusPort`; aiomqtt). |
| `infrastructure/persistence/sqlite.py` | infra | `SQLiteStateStore` (implements `StateRepositoryPort`). |
| `infrastructure/config/` | infra | `manager.py` (`ConfigManager`), `models.py` (typed Pydantic configs). |
| `infrastructure/wb_device/service.py` | infra | `WBVirtualDeviceService` (Wirenboard virtual-device emulation). |
| `infrastructure/scenarios/` | infra | `wb_adapter.py` (`ScenarioWBAdapter`), `models.py` (`ScenarioWBConfig`). |
| `infrastructure/maintenance/wirenboard_guard.py` | infra | `WirenboardMaintenanceGuard`. |
| `presentation/api/routers/*.py` | presentation | FastAPI routers (system, devices, mqtt, groups, scenarios, rooms, state, events). |
| `presentation/api/sse_manager.py` | presentation | SSE fan-out. |
| `app/bootstrap.py` | app | `create_app()` + `lifespan` (dependency injection / wiring). `main.py` = console entry. |
| `cli/*.py` | cli | `mqtt-sniffer`, `device-test`, `broadlink-*`, `wb-openapi`. |
| `utils/` | cross-cutting | `class_loader.py`, `validation.py`, `types.py` (`CommandResult`/`CommandResponse`), `serialization_utils.py`. |

## The ports (the seams)

Defined in `domain/ports.py`; implemented by infrastructure. This is what keeps the
domain testable and the drivers swappable.

| Port | Used by | Implemented by |
|---|---|---|
| `MessageBusPort` | `ScenarioManager`, WB services | `infrastructure/mqtt/client.MQTTClient` |
| `DeviceBusPort` | device drivers themselves | every `infrastructure/devices/*/driver.py` (via `BaseDevice`) |
| `StateRepositoryPort` | `DeviceManager`, `ScenarioManager` | `infrastructure/persistence/sqlite.SQLiteStateStore` |

## Device model

`BaseDevice(DeviceBusPort, ABC, Generic[StateT])` (`infrastructure/devices/base.py`) is
the heart. A driver:

- Is parameterized by its **typed state model** `StateT` (a `BaseDeviceState` subclass
  from `domain/devices/models.py`) and constructed from its **typed config**
  (`BaseDeviceConfig` subclass from `infrastructure/config/models.py`).
- Implements the abstract lifecycle: `async setup()`, `async shutdown()`,
  `subscribe_topics()`, `async handle_message(topic, payload)`.
- Exposes **action handlers** with a uniform signature:
  `async def handle_<action>(self, cmd_config, params) -> CommandResult`.
- `execute_action(...)` (on `BaseDevice`) dispatches an action name to its handler,
  updates `self.state`, and returns a typed `CommandResponse`.

**Typed contracts** (`utils/types.py`):
- `CommandResult` (handler return): `{success, message?, error?, mqtt_command?}`.
- `CommandResponse` (API return): `{success, device_id, action, state, error?, mqtt_command?, data?}`.

### Registration & loading
Drivers are registered as setuptools **entry-points** under
`[project.entry-points."wb_mqtt_bridge.devices"]` in `pyproject.toml` (e.g.
`lg_tv = ...lg_tv.driver:LgTv`). At startup `DeviceManager.load_device_modules()`
discovers them; `ConfigManager` loads each `config/devices/*.json`, and the
`config_class` field selects the typed config model (resolved via
`utils/class_loader.py`). `device_class` selects the driver.

The 7 drivers: `LgTv`, `EMotivaXMC2`, `AppleTVDevice`, `AuralicDevice`,
`BroadlinkKitchenHood`, `WirenboardIRDevice`, `RevoxA77ReelToReel`.

## Key flows

### HTTP action
`POST /devices/{id}/action` (`presentation/.../devices.py`) → `DeviceManager` →
`device.execute_action(action, params)` → handler runs, mutates `self.state`, returns
`CommandResponse`. The new state is persisted (see below) and, where relevant, an MQTT
command is published.

### Inbound MQTT
`MQTTClient` (subscribed to each device's `subscribe_topics()`) routes messages to
`DeviceManager.get_message_handler(device_id)` → `device.handle_message(topic, payload)`.

### State persistence
`DeviceManager` holds a `StateRepositoryPort` and saves each device's serialized state
under the key **`device:{device_id}`** via `SQLiteStateStore`. Read back through
`GET /devices/{id}/persisted_state` and `/devices/persisted_states`. Final state is
flushed on shutdown.

### Live state (SSE)
`presentation/api/sse_manager.py` fans device/scenario/system events out to
`GET /events/{devices,scenarios,system,stats}`. This is how the UI receives live state.

### Wirenboard virtual-device emulation
`WBVirtualDeviceService` (`infrastructure/wb_device/service.py`) publishes each **device** as a
Wirenboard virtual device on MQTT (device meta + per-control meta + value topics, retained), so
the bridge's devices appear natively in the Wirenboard ecosystem. Gated by `enable_wb_emulation`
in config; set up after MQTT connects (`device.setup_wb_emulation_if_enabled()`). Publishing
**scenarios** as WB virtual devices (`ScenarioWBAdapter`) is currently **disabled** pending a
design decision on scenario↔Wirenboard integration (see `action_plan.md` P4).

## Scenario system

A scenario (Logitech-Harmony-style) coordinates several devices for an activity (e.g.
"watch Apple TV"). Scenarios are **thin** (`source`/`display`/`audio` role selections); device
membership, input routing, and ordering are **derived at runtime** by a topology- and
capability-driven **reconciler** (`infrastructure/scenarios/reconciler.py`) rather than hardcoded
startup/shutdown sequences. The reconciler resolves desired targets from `config/topology.json`,
diffs them against the devices' optimistic *assumed* state (Harmony model: IR-first, optimistic,
manual resync), orders actions (power-before-input + topology ordering edges), and executes with
success-checked gating; capability maps (`config/capabilities/`) translate symbolic role/input
names into device commands. `ScenarioManager` (`domain/scenarios/service.py`) loads
`config/scenarios/*.json`, routes thin scenarios through the reconciler (behind the
`WB_SCENARIO_RECONCILER` flag), surfaces manual steps, tracks `ScenarioState`, and persists
active-scenario state. **Process shutdown is transparent to the hardware** — it does not power
devices off; that's the explicit `deactivate`. A legacy sequence path remains as an escape hatch.
API: `GET|POST /scenario/*`. (Scenario-as-WB-device publishing is disabled — see above.)

> Design + as-built record: `docs/scenarios/scenario_system_redesign.md` and
> `docs/scenarios/scenario_redesign_progress.md`.

## Configuration

- **`config/system.json`** → `SystemConfig` (`infrastructure/config/models.py`): MQTT
  broker, web service, persistence (`db_path`), logging, action groups, maintenance.
- **`config/devices/*.json`** → typed `BaseDeviceConfig` subclasses. Required fields:
  `device_id`, `device_name`, `device_class`, `config_class`; plus `device_category`
  (`device`|`appliance`), `commands`, and WB-emulation fields.
- **`config/scenarios/*.json`** → scenario definitions.
- **`config/device-state-mapping.json`** → consumed by the UI build (see the contract doc).

## Bootstrap & lifecycle

`app/bootstrap.py::create_app()` builds the FastAPI app and installs a `lifespan`
context manager that, on **startup**: loads config → initializes `SQLiteStateStore` →
creates `MQTTClient` (with optional `WirenboardMaintenanceGuard`) → `DeviceManager`
loads drivers and initializes devices from typed configs (a device that fails setup is kept
registered as disconnected, not dropped) → connects MQTT & subscribes → sets up per-device WB
emulation → initializes `RoomManager`, `ScenarioManager`, `ScenarioWBAdapter` → injects
dependencies into routers. On **shutdown**: SSE drain, flush pending state persistence, cancel
background tasks, scenario/device shutdown **transparent to the hardware** (no power-off, no
teardown-state persistence — that would corrupt the assumed state), close the store.

`create_app()` also installs the OpenAPI override that injects device-state models into
`/openapi.json` — the contract the UI consumes (`_install_openapi_with_state_models`;
see [`ui_backend_contract.md`](ui_backend_contract.md)).

## Testing model

Tests follow a uniform hexagonal recipe: build a typed Pydantic config, inject the
driver's external dependency as an `AsyncMock`, bypass `setup()`, drive `handle_<action>`
methods directly, and assert delegation + state mutations. See `docs/devices/` and the
existing `tests/` for the pattern. Suite runs in CI on amd64.

## Conventions & decisions

Coding conventions (and the rationale behind the OpenAPI-additive-injection,
backend-owned mapping, runtime-config, etc. decisions) will live in `conventions.md`
and `docs/adr/` — see `action_plan.md` P2.6 #11.
