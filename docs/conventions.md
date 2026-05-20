# Conventions — wb-mqtt-bridge (+ wb-mqtt-ui)

**Status:** current (2026-05-20). How we work in these two repos. See
[`architecture.md`](architecture.md) for structure and
[`ui_backend_contract.md`](ui_backend_contract.md) for the cross-repo seam.

## Git & workflow

- **Push directly to `main`** on both repos — solo workflow, no PR ceremony.
- **Small, focused commits** — one logical change each. Don't bundle unrelated work.
- **Detailed commit bodies** explaining *why* (what changed, what it fixes/removes), with
  file/line refs where useful. The body is the audit trail in lieu of PR descriptions.
- Always include the trailer `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` on AI-made commits; use a HEREDOC for multi-line messages.
- When operating across both repos in one session, use `git -C <abs-path>` / absolute
  paths — the shell cwd does not always reset cleanly between commands.
- **Decisions are tracked** in `docs/action_plan.md` (revision log) and `docs/adr/`.
  **Superseded docs are archived** to `docs/archive/`, not deleted.

## Backend — layering (hexagonal)

Dependencies point inward. When adding code, place it by layer:

- **`domain/`** — pure business logic, **no I/O**; reach the outside only through the
  ports in `domain/ports.py`. (`DeviceManager`, `ScenarioManager`, `RoomManager`, models.)
- **`infrastructure/`** — adapters that implement the ports (device drivers, MQTT client,
  SQLite store, config, WB emulation).
- **`presentation/`** — FastAPI routers, SSE, request/response schemas.
- **`app/`** — wiring only (`create_app` + `lifespan`). **`cli/`** — console tools.
- New external dependency? Hide it behind a port/adapter; don't import it from `domain/`.

## Backend — typed configs & state (a hard rule)

- Every device config JSON declares **`device_class`** (driver) **and `config_class`**
  (Pydantic config model) — both required, validated non-empty.
- Config models live in `infrastructure/config/models.py` (subclass `BaseDeviceConfig`).
- State models live in `domain/devices/models.py` (subclass `BaseDeviceState`); a driver
  is `BaseDevice[StateT]`.
- No dict-shaped configs/state — type everything.

## Backend — adding a device driver (checklist)

1. `infrastructure/devices/<name>/driver.py` — class subclassing `BaseDevice[StateT]`;
   implement `setup`, `shutdown`, `subscribe_topics`, `handle_message`, and
   `async def handle_<action>(self, cmd_config, params) -> CommandResult` handlers.
2. Add its typed **config model** (`infrastructure/config/models.py`) and **state model**
   (`domain/devices/models.py`).
3. Register the entry-point in `pyproject.toml`
   (`[project.entry-points."wb_mqtt_bridge.devices"]`).
4. Add `config/devices/<name>.json` (with `device_class` + `config_class`).
5. **Contract:** add the state model to `OPENAPI_EXTRA_MODELS`
   (`app/bootstrap.py`) and an entry in `config/device-state-mapping.json`; then
   **regenerate `openapi.json`** (`wb-openapi -o openapi.json`) and commit it.
6. UI side: add a device handler in `wb-mqtt-ui/src/lib/deviceHandlers/`; `device_class`
   must match across config, mapping, and handler.

## Backend — formatting & typing

- **black** + **isort** (black profile), line length **88**, target py311.
- **mypy** via `./run_mypy.sh` (config `mypy.ini`, over `src/wb_mqtt_bridge/`). Type
  hints are expected on new code.

## Backend — tests (the recipe)

- `pytest`, `asyncio_mode = auto`, `testpaths = ["tests"]`. Markers:
  `unit`, `integration`, `requires_mqtt`, `requires_device`, `slow`.
- **CI runs `pytest -m "not requires_device"`** (amd64) — keep CI-run tests free of real
  hardware / brokers.
- **Device-driver test recipe** (uniform across all 7 — see `tests/` and
  `docs/devices/`): build a typed Pydantic config; inject the driver's external client as
  an `AsyncMock`; **bypass `setup()`** (it connects to real hardware); prime the
  connectivity gate (`state.connected = True`, etc.); stub network helpers; drive
  `handle_<action>` directly; assert (a) the external client was called as expected,
  (b) `device.state` mutations, (c) `CommandResult` shape.
- Don't name non-test helpers `test_*` — pytest will try to collect them
  (rename CLI helpers to `_check_*` / `_run_*`).

## The OpenAPI contract (discipline)

The committed `openapi.json` — not a running server — is what the UI build consumes.

- **Regenerate + commit `openapi.json` (`wb-openapi`) whenever the API surface or any
  device-state model changes.** A test (`tests/unit/test_openapi_schema.py`) guards that
  every `OPENAPI_EXTRA_MODELS` entry is present.
- When the REST surface changes, also regenerate the UI's `src/types/api.gen.ts`
  (`npm run gen:api-types`) and commit it.
- Full rules + invariants: [`ui_backend_contract.md`](ui_backend_contract.md).

## UI conventions (`wb-mqtt-ui`)

- **No Python in the build.** Device-state types come from the backend `openapi.json`
  (`src/lib/StateTypeGenerator.ts`), not from importing the package.
- **Generated artifacts are gitignored** (`*.gen.tsx`, `*.hooks.ts`,
  `src/types/generated/*.state.ts`, `index.gen.ts`) — built fresh in CI.
  **`src/types/api.gen.ts` is committed.**
- eslint **ignores the sibling `wb-mqtt-bridge`** checkout. Before committing, run
  `npm run typecheck:all && npm run lint && npm run validate:all`.
- **No hardcoded backend IPs / baked URLs.** Backend proxy target is runtime
  (`BACKEND_HOST`/`BACKEND_PORT` via `docker-entrypoint.sh`); MQTT URL via
  `window.RUNTIME_CONFIG` (`/runtime-config.js`); `VITE_*` is local-dev fallback only.
- UI layout for a device is chosen by `device_category` (A/V `device` → remote layout;
  `appliance` → bespoke page).

## Docs conventions

- **Docs match reality** — no aspirational/stale documentation in the live `docs/` tree.
- Superseded design/implementation notes go to `docs/archive/` (kept for history, marked
  "not current, don't ingest"), never silently deleted.
- Architectural decisions get a short **ADR** under `docs/adr/`.
