# Context (DOCs)

Running notes from classified DOCs: `docs/architecture.md` and `docs/conventions.md`
(both precedence 3). Appended by topic with source attribution. These are descriptive /
guidance; lower precedence than ADRs, SPEC, and PRDs.

---

## Topic: System overview

- **source:** docs/architecture.md
- Python 3.11 async service bridging Wirenboard / AV-equipment devices to a FastAPI HTTP
  API and an MQTT broker. Exposes each device's actions over REST + MQTT, streams live
  state over SSE, persists state to SQLite, emulates Wirenboard virtual devices, and runs
  Logitech-Harmony-style scenarios across devices.
- Stack (from project.md): Python 3.11 / FastAPI / aiomqtt (backend); React / TypeScript
  / Vite (UI). Two repos developed in lockstep.

## Topic: Hexagonal layering

- **source:** docs/architecture.md, docs/conventions.md
- Domain-centric (ports & adapters); dependencies point inward. `presentation/` and
  `infrastructure/` depend on `domain/`; `domain/` depends on nothing external and
  reaches the outside only through ports.
- Layer placement rule (conventions): `domain/` = pure business logic, no I/O
  (`DeviceManager`, `ScenarioManager`, `RoomManager`, models); `infrastructure/` =
  adapters implementing ports (drivers, MQTT client, SQLite store, config, WB emulation);
  `presentation/` = FastAPI routers, SSE, schemas; `app/` = wiring only
  (`create_app` + `lifespan`); `cli/` = console tools. New external dependency must be
  hidden behind a port/adapter, never imported from `domain/`.

## Topic: Ports (the seams)

- **source:** docs/architecture.md
- Defined in `domain/ports.py`, implemented by infrastructure:
  `MessageBusPort` (used by ScenarioManager, WB services; impl
  `infrastructure/mqtt/client.MQTTClient`); `DeviceBusPort` (used by drivers; impl every
  `infrastructure/devices/*/driver.py` via `BaseDevice`); `StateRepositoryPort` (used by
  DeviceManager, ScenarioManager; impl `infrastructure/persistence/sqlite.SQLiteStateStore`).

## Topic: Device model

- **source:** docs/architecture.md, docs/conventions.md
- `BaseDevice(DeviceBusPort, ABC, Generic[StateT])` (`infrastructure/devices/base.py`) is
  the core. A driver is parameterized by its typed state model `StateT` (a
  `BaseDeviceState` subclass from `domain/devices/models.py`) and constructed from its
  typed config (`BaseDeviceConfig` subclass from `infrastructure/config/models.py`).
- Lifecycle: `async setup()`, `async shutdown()`, `subscribe_topics()`,
  `async handle_message(topic, payload)`. Action handlers:
  `async def handle_<action>(self, cmd_config, params) -> CommandResult`.
  `execute_action(...)` dispatches an action name to its handler, updates `self.state`,
  returns a typed `CommandResponse`.
- Typed contracts (`utils/types.py`): `CommandResult`
  `{success, message?, error?, mqtt_command?}`; `CommandResponse`
  `{success, device_id, action, state, error?, mqtt_command?, data?}`.
- Hard rule (conventions): no dict-shaped configs/state — type everything. Every device
  config JSON declares `device_class` (driver) and `config_class` (Pydantic config),
  both required and validated non-empty.
- The 7 drivers: `LgTv`, `EMotivaXMC2`, `AppleTVDevice`, `AuralicDevice`,
  `BroadlinkKitchenHood`, `WirenboardIRDevice`, `RevoxA77ReelToReel`. Registered as
  setuptools entry-points under `[project.entry-points."wb_mqtt_bridge.devices"]`.

## Topic: Key flows

- **source:** docs/architecture.md
- HTTP action: `POST /devices/{id}/action` → DeviceManager →
  `device.execute_action(action, params)` → handler mutates state → `CommandResponse`;
  state persisted; MQTT command published where relevant.
- Inbound MQTT: MQTTClient routes to
  `DeviceManager.get_message_handler(device_id)` → `device.handle_message(topic, payload)`.
- State persistence: DeviceManager saves serialized state under key
  `device:{device_id}` via SQLiteStateStore; read back via
  `GET /devices/{id}/persisted_state` and `/devices/persisted_states`; flushed on shutdown.
- Live state (SSE): `presentation/api/sse_manager.py` fans events to
  `GET /events/{devices,scenarios,system,stats}`.
- WB virtual-device emulation: `WBVirtualDeviceService` publishes each device (and each
  scenario via `ScenarioWBAdapter`) as a WB virtual device on MQTT; gated by
  `enable_wb_emulation`; set up after MQTT connects.

## Topic: Scenario system

- **source:** docs/architecture.md
- `ScenarioManager` (`domain/scenarios/service.py`) loads definitions from
  `config/scenarios/*.json`, runs startup/shutdown sequences, validates configuration and
  conditions, tracks `ScenarioState`, persists active-scenario state via
  `StateRepositoryPort`. `ScenarioWBAdapter` exposes scenarios as WB virtual devices.
  API: `GET|POST /scenario/*`. (NOTE: scenario layer is currently broken — see
  REQ-fix-scenario-layer.)

## Topic: Configuration

- **source:** docs/architecture.md
- `config/system.json` → `SystemConfig` (MQTT broker, web service, persistence `db_path`,
  logging, action groups, maintenance). `config/devices/*.json` → typed
  `BaseDeviceConfig` subclasses. `config/scenarios/*.json` → scenario definitions.
  `config/device-state-mapping.json` → consumed by the UI build (see contract).

## Topic: Bootstrap & lifecycle

- **source:** docs/architecture.md
- `app/bootstrap.py::create_app()` builds the FastAPI app + installs a `lifespan` context
  manager. Startup: load config → init SQLiteStateStore → create MQTTClient (optional
  WirenboardMaintenanceGuard) → DeviceManager loads drivers + inits devices from typed
  configs → connect MQTT & subscribe → set up WB emulation → init RoomManager,
  ScenarioManager, ScenarioWBAdapter → inject deps into routers. Shutdown: SSE drain,
  cancel background tasks, scenario/device shutdown, final state persistence, close store.
- `create_app()` also installs the OpenAPI override injecting device-state models into
  `/openapi.json` (`_install_openapi_with_state_models`).

## Topic: Git & workflow conventions

- **source:** docs/conventions.md
- Push directly to `main` on both repos (solo, no PR ceremony). Small focused commits,
  one logical change each. Detailed commit bodies explaining why, with file/line refs.
  AI-made commits include trailer
  `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` (HEREDOC for
  multi-line). Across both repos use `git -C <abs-path>` / absolute paths. Decisions
  tracked in `docs/action_plan.md` (revision log) and `docs/adr/`. Superseded docs
  archived to `docs/archive/`, not deleted.

## Topic: Formatting, typing, tests

- **source:** docs/conventions.md, docs/architecture.md
- Formatting: black + isort (black profile), line length 88, target py311. mypy via
  `./run_mypy.sh` (config `mypy.ini`, over `src/wb_mqtt_bridge/`); type hints expected on
  new code.
- Tests: pytest, `asyncio_mode = auto`, `testpaths = ["tests"]`. Markers: unit,
  integration, requires_mqtt, requires_device, slow. CI runs
  `pytest -m "not requires_device"` on amd64.
- Device-driver test recipe (uniform across all 7): build a typed Pydantic config; inject
  the driver's external client as an AsyncMock; bypass `setup()` (connects to real
  hardware); prime the connectivity gate (`state.connected = True`); stub network
  helpers; drive `handle_<action>` directly; assert (a) external client called as
  expected, (b) `device.state` mutations, (c) `CommandResult` shape. Don't name non-test
  helpers `test_*` (rename to `_check_*` / `_run_*`).

## Topic: Adding a device driver (checklist)

- **source:** docs/conventions.md
- (1) `infrastructure/devices/<name>/driver.py` subclassing `BaseDevice[StateT]`
  implementing setup/shutdown/subscribe_topics/handle_message + `handle_<action>` handlers;
  (2) add typed config model + state model; (3) register entry-point in `pyproject.toml`;
  (4) add `config/devices/<name>.json` with `device_class` + `config_class`;
  (5) Contract: add the state model to `OPENAPI_EXTRA_MODELS` + an entry in
  `device-state-mapping.json`, regenerate `openapi.json`, commit;
  (6) UI: add a device handler in `wb-mqtt-ui/src/lib/deviceHandlers/`; `device_class`
  must match across config, mapping, and handler.

## Topic: UI conventions

- **source:** docs/conventions.md
- No Python in the build. Generated artifacts gitignored (`*.gen.tsx`, `*.hooks.ts`,
  `src/types/generated/*.state.ts`, `index.gen.ts`), built fresh in CI;
  `src/types/api.gen.ts` committed. eslint ignores the sibling `wb-mqtt-bridge` checkout.
  Before committing: `npm run typecheck:all && npm run lint && npm run validate:all`.
  No hardcoded backend IPs / baked URLs (runtime config). UI layout chosen by
  `device_category` (A/V `device` → remote layout; `appliance` → bespoke page).

## Topic: Docs conventions

- **source:** docs/conventions.md
- Docs match reality — no aspirational/stale documentation in the live `docs/` tree.
  Superseded notes go to `docs/archive/` (marked "not current, don't ingest"), never
  silently deleted. Architectural decisions get a short ADR under `docs/adr/`.

## Topic: Project trajectory & non-goals (vision context)

- **source:** docs/project.md
- Audience trajectory: today built for the author alone (single user, single home, LAN);
  ultimate goal household usage; later open to the Wirenboard community once done/stable.
  Design values: strong typing end-to-end; hexagonal architecture; contract-based coupling
  over import coupling; deterministic reproducible builds (committed `openapi.json`,
  generated UI artifacts gitignored); solo-dev pragmatism; docs that match reality.
- Non-goals: not a Home Assistant replacement; no cloud (LAN-only); no multi-home /
  multi-tenant; voice control not built here (delegated to WB's future Yandex Alisa
  bridge); not an ever-growing platform — scope bounded by the home.
- Hardware trajectory: Wirenboard-exclusive deployment; today WB7 (ARMv7/32-bit, ~256 MB
  / 0.5 CPU); planned WB8+ (ARM64/64-bit); amd64 is CI/dev only, not a deploy target.
