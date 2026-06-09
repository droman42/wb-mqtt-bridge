# Contributing

The repo is a monorepo (`backend/` + `ui/` + `wb-rules/` + `ops/` + `docs/`)
maintained solo. The conventions below are what every commit clears; treat
them as the rules of the road, not aspirations.

## Workflow

- **Push directly to `main`** — solo workflow, no PR ceremony.
- **Small, focused commits** — one logical change each. Don't bundle unrelated
  work into a single push.
- **Detailed commit bodies explain the *why*** — what changed, what it
  fixes/removes, with file/line refs where useful. The body is the audit trail
  in lieu of PR descriptions.
- AI-co-authored commits add the trailer
  `Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>`; pass multi-line
  messages via a HEREDOC.
- **Decisions land in `docs/action_plan.md`** (revision log) and the ADRs
  under `docs/adr/`. **Superseded docs move to `docs/archive/`** (or
  `docs/design/` / `docs/review/` if they remain authoritative or
  informational), never deleted.

## Backend — layering (hexagonal, enforced)

Dependencies point inward. When adding code, place it by layer:

- **`domain/`** — pure business logic, **no I/O**; reaches the outside only
  through the ports in `domain/ports.py`. (`DeviceManager`, `ScenarioManager`,
  `RoomManager`, the topology and capability models, the reconciler.)
- **`infrastructure/`** — adapters that implement the ports: device drivers,
  MQTT client, SQLite store, config + capability loaders, WB virtual-device
  emulation.
- **`presentation/`** — FastAPI routers, SSE, request/response schemas.
- **`app/`** — wiring only (`create_app()` + `lifespan`). **`cli/`** — console
  tools.
- A new external dependency goes behind a port + adapter; do not import it
  from `domain/`.

A presentation→infrastructure back-edge currently exists in
`presentation/api/routers/system.py` (`POST /reload` constructs an
`MQTTClient` directly for live reconnect). It is consciously accepted and
documented; do not add new ones.

See **[Architecture overview](docs/architecture/overview.md)** for the full
picture.

## Backend — typed configs + typed state (a hard rule)

- Every device config JSON declares **`device_class`** (the driver) and
  **`config_class`** (the Pydantic config model) — both required, both
  validated non-empty.
- Config models live in `infrastructure/config/models.py` (subclass
  `BaseDeviceConfig`).
- State models live in `domain/devices/models.py` (subclass `BaseDeviceState`);
  every driver is `BaseDevice[StateT]`.
- **No dict-shaped configs or state.** Type everything.

## Backend — formatting + typing

- **black** + **isort** (black profile), line length 88, target py311.
- **mypy** via `./run_mypy.sh` (config `mypy.ini`, scope
  `backend/src/wb_mqtt_bridge/`). Type hints expected on new code.

## Backend — tests (the recipe)

- `pytest`, `asyncio_mode = auto`, `testpaths = ["tests"]`. Markers:
  `unit`, `integration`, `requires_mqtt`, `requires_device`, `slow`.
- **CI runs `pytest -m "not requires_device"`** on amd64. Keep CI-run tests
  free of real hardware + brokers.
- **Device-driver test recipe** (the pattern every driver follows):
  1. Build a typed Pydantic config.
  2. Inject the driver's external client as an `AsyncMock`.
  3. **Bypass `setup()`** (it connects to real hardware).
  4. Prime the connectivity gate (`state.connected = True`, etc.).
  5. Stub network helpers.
  6. Drive `handle_<action>` directly.
  7. Assert the external client was called as expected, `device.state`
     mutations are right, the `CommandResult` shape matches.
- Don't name non-test helpers `test_*` — pytest will collect them. Rename
  CLI helpers to `_check_*` / `_run_*`.

## The OpenAPI contract (build-time discipline)

The committed `backend/openapi.json` — *not* a running server — is what the
UI build consumes.

- **Regenerate + commit `openapi.json`** (`wb-openapi -o openapi.json` from
  inside `backend/`) whenever the REST surface or any device-state model
  changes. A test (`tests/unit/test_openapi_schema.py`) guards that every
  `OPENAPI_EXTRA_MODELS` entry actually lands in the schema.
- When the REST surface changes, also regenerate the UI's
  `src/types/api.gen.ts` (`npm run gen:api-types` from inside `ui/`) and
  commit it.
- Full invariants: **[Architecture: UI](docs/architecture/ui.md)** and
  **[Architecture: interfaces](docs/architecture/interfaces.md)**.

## UI conventions

- **No Python in the build.** Device-state types come from the backend's
  `openapi.json`; the UI never imports the Python package.
- **Generated artifacts are gitignored** (`*.gen.tsx`, `*.hooks.ts`,
  `src/types/generated/*.state.ts`, `index.gen.ts`) — built fresh in CI.
  `src/types/api.gen.ts` is committed.
- Before committing UI changes, from `ui/`:
  `npm run typecheck:all && npm run lint && npm run validate:all`.
- **No hardcoded backend IPs or baked URLs.** Backend proxy target is
  runtime (`BACKEND_HOST` / `BACKEND_PORT` via `docker-entrypoint.sh`);
  MQTT URL via `window.RUNTIME_CONFIG` (`/runtime-config.js`). `VITE_*`
  is local-dev fallback only.
- UI layout for a device is chosen by `device_category` (`device` →
  runtime layout manifest via `RemoteControlLayout`; `appliance` →
  bespoke per-class page).

## CI gates each commit must clear

Two CI workflows fan out of the same push:

- **Fast (every push)** — `backend-test` (pytest -m "not requires_device" on
  amd64) and the UI fast checks (`gen:api-types` + `typecheck:all` +
  `validate:all`).
- **Slow (manual)** — QEMU `arm/v7` Docker image builds for backend + UI.
  Triggered via `gh workflow run "Build ARM Docker Images (backend + ui)"`
  or the Actions UI; they don't run on every push because they're ~14 min
  for the UI.

If you change a Dockerfile or anything in `ops/`, run the slow workflow
before merging.

## How-to references

- **[Add a device with an existing driver](docs/guides/howto-new-device.md)**
  — config-only, the WB-passthrough or one of the 7 AV driver classes.
- **[Add a new device driver with a native library](docs/guides/howto-new-driver.md)**
  — Python-side: typed config + state, driver subclass, entry-point,
  capability map, tests.
- **[Define a new AV scenario](docs/guides/howto-new-scenario.md)** — thin
  scenario config; the reconciler does the rest.

## Source of truth pointers

- **[Architecture overview](docs/architecture/overview.md)** — the hexagon
  and its ports.
- **[Architecture: key concepts](docs/architecture/key-concepts.md)** —
  topology, capabilities, configs, reconciler.
- **`docs/action_plan.md`** *(internal)* — the living revision log and
  open work.
- **`docs/adr/`** — design decisions with their context.
