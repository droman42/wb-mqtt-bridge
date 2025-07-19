# Codebase Restructuring Plan: Domain-Centric Architecture

> **Audience:** project maintainers & contributors  
> **Goal:** migrate *wb-mqtt-bridge* from the current mixed layout to a clean, domain-centric (DDD/Hexagonal) structure without rewriting core logic.

---

## 1. Why This Change?
1. **Discoverability** – domain logic, API code, and drivers are currently mixed under `app/` and `devices/`.
2. **Testing** – unit tests must import FastAPI & MQTT side-effects today.
3. **Extensibility** – adding new UIs or persistence layers requires reaching across module boundaries.

A domain-centric structure isolates **what** the application does (business rules) from **how** it talks to the outside world (HTTP, MQTT, SQLite, etc.).

---

## 2. Target Folder Layout (after migration)
```text
src/wb_mqtt_bridge/
├─ __init__.py
├─ __version__.py
├─ app/                  # application bootstrap (FastAPI instance)
├─ cli/                  # command-line utilities
│   ├─ mqtt_sniffer.py
│   └─ device_test.py
├─ domain/               # pure business logic (no I/O)
│   ├─ devices/
│   ├─ scenarios/
│   └─ rooms/
├─ infrastructure/       # adapters / gateways
│   ├─ mqtt/
│   ├─ persistence/
│   └─ devices/          # concrete device drivers
└─ presentation/
    └─ api/              # FastAPI routers & HTTP schemas
```

### Dependency Rule
```mermaid
flowchart LR
    presentation --> app
    app --> domain
    infrastructure --> app
    infrastructure --> domain
    style domain fill:#fafafa,stroke:#333,stroke-width:1px
```
*   **domain** has *no* imports from the other layers.
*   **infrastructure** is allowed to import from **domain** to implement interfaces (ports).
*   **presentation** (FastAPI) depends on **app** and indirectly on **domain** via services.

---

## 3. File-by-File Mapping
| Current Location | New Location | Change Required |
| --- | --- | --- |
| `app/device_manager.py` | `domain/devices/service.py` | Replace MQTT calls with `DeviceBusPort` interface. |
| `devices/*.py` | `infrastructure/devices/*/driver.py` | Move unchanged; implement `DeviceDriver` ABC. |
| `app/mqtt_client.py` | `infrastructure/mqtt/client.py` | No logic change. |
| `app/state_store.py` | `infrastructure/persistence/sqlite.py` | No logic change. |
| `app/routers/*` | `presentation/api/routers/*` | Update import paths. |
| `app/schemas.py` (API‐facing) | `presentation/api/schemas.py` | Split internal vs HTTP models. |
| `app/schemas.py` (domain models) | `domain/*/models.py` | Move intact. |
| `app/main.py` | `wb_mqtt_bridge/app/main.py` | Remains the FastAPI entry-point; adjust imports & wiring. |
| `mqtt_sniffer.py` | `cli/mqtt_sniffer.py` | Move unchanged; expose via `mqtt-sniffer` console script. |
| `device_test_cli.py` | `cli/device_test.py` | Move unchanged; expose via `device-test` console script. |

---

## 4. Phased Rollout Schedule

### Phase 1 — Skeleton & Packaging
* Create the `src/` package layout and update `pyproject.toml` (`tool.setuptools.package-dir = {"" = "src"}`).
* Move stateless helpers (`serialization_utils.py`, `class_loader.py`, etc.) to `wb_mqtt_bridge/utils`.
* Run `ruff --fix` to rewrite import paths.

**Exit criteria:** All tests pass from the new package root.

### Phase 2 — CLI Relocation
* Add `src/wb_mqtt_bridge/cli/`.
* Move `mqtt_sniffer.py` → `cli/mqtt_sniffer.py` and `device_test_cli.py` → `cli/device_test.py`.
* Expose both via `console_scripts` in `pyproject.toml`:
  ```toml
  [project.scripts]
  mqtt-sniffer = "wb_mqtt_bridge.cli.mqtt_sniffer:main"
  device-test  = "wb_mqtt_bridge.cli.device_test:main"
  ```
* Replace `if __name__ == "__main__":` blocks with a `main()` entry point where needed.

**Exit criteria:** Commands run after `pip install -e .`; tests remain green.

### Phase 3 — Ports Definition
* Introduce `domain/ports.py` containing ABCs (e.g., `MessageBusPort`, `DeviceBusPort`, `StateRepositoryPort`).

**Exit criteria:** Static analysis succeeds; no runtime usage yet.

### Phase 4 — Domain Service Extraction
* Refactor `DeviceManager`, `ScenarioManager`, `RoomManager`, etc., to receive ports via constructor.
* Move those managers and core models into `domain/*/` sub-packages.
* Add temporary shim modules that re-export classes from old paths to ease transition.

**Exit criteria:** Managers live in `domain/*`; shims pass tests with only deprecation warnings.

### Phase 5 — Adapters & Device Drivers
* Move concrete drivers from `devices/` to `infrastructure/devices/*/driver.py`.
* Implement MQTT and persistence adapters under `infrastructure/mqtt/` and `infrastructure/persistence/`.
* Register drivers via entry-points (`[project.entry-points."wb_mqtt_bridge.devices"]`).

**Exit criteria:** Device & MQTT integration tests pass.

### Phase 6 — Presentation Layer Split
* Move FastAPI routers to `presentation/api/routers/*`.
* Split `schemas.py` into HTTP DTOs (`presentation/api/schemas.py`) and pure domain models (`domain/*/models.py`).
* Wire dependencies in `app/__init__.py`.

**Exit criteria:** `uvicorn wb_mqtt_bridge.app:app` serves all endpoints; tests pass.

### Phase 7 — Cleanup & CI Hardening
* Remove temporary shims, run `ruff --fix` and static type checks.
* Update docs, Dockerfile, CI, and examples.
* Tag a release candidate and publish migration guide.

**Exit criteria:** No shims remain; green CI; migration guide published.

---

## 5. Migration Checklist
```mermaid
graph TD
    A[Create src/ skeleton] --> B[git mv utils + stateless helpers]
    B --> C[Introduce ports & adapters]
    C --> D[Update imports with ruff --fix]
    D --> E[Move domain services]
    E --> F[Move device drivers]
    F --> G[Split schemas]
    G --> H[Update tests & CI]
```

1. **Create `src/` layout**  
   *Add `tool.setuptools.package-dir` → `"" = "src"` in* `pyproject.toml`.
2. **Move low-level utilities** (`serialization_utils.py`, `class_loader.py`) to `wb_mqtt_bridge/utils/`.
3. **Define abstract ports** in `domain/ports.py` (e.g. `MessageBusPort`, `StateRepositoryPort`).
4. **Refactor managers** to accept those ports via constructor; remove direct MQTT/DB imports.
5. **Relocate device drivers** under `infrastructure/devices/*` and register them via entry-points:
   ```toml
   [project.entry-points."wb_mqtt_bridge.devices"]
   lg_tv = "wb_mqtt_bridge.infrastructure.devices.lg_tv.driver:LgTv"
   ```
6. **Move CLI utilities** (`mqtt_sniffer.py`, `device_test_cli.py`) under `cli/` and add corresponding `console_scripts` in `pyproject.toml`.
7. **Split `schemas.py`** – keep pure models in domain; move HTTP DTOs to presentation.
8. **Bootstrap wiring** in `app/__init__.py`: instantiate adapters, inject into services, expose FastAPI app.
9. **Update tests / CI** to import from `wb_mqtt_bridge.*` packages only.
10. **Run full test suite**; ensure behaviour parity.

---

## 6. Effort & Timeline
| Task | Effort |
| --- | --- |
| File moves & import rewrites | 2–3 days |
| Introduce ports & refactor managers | 3–5 days |
| Split schemas & update routers | 1–2 days |
| CI updates, docs, cleanup | 1–2 days |
| **Total** | **7–12 dev days** |

---

## 7. FAQs
**Q 1:** *Do we rewrite algorithms?*  
**A:** No. Logic stays untouched; only module boundaries change.

**Q 2:** *Can we migrate gradually?*  
**A:** Yes – layers compile independently. Move one service at a time while keeping temporary import shims.

**Q 3:** *What happens to config JSON files?*  
**A:** The `config/` directory remains at the repository root and is copied (or mounted) alongside the application. `ConfigManager` will continue to default to that path.  
- You *may* override the location with an environment variable (`WB_CONFIG_DIR=/path/to/config`) if you want to mount it elsewhere (e.g. in Docker).  
- Keeping configs outside the package avoids rebuilding the wheel every time you adjust a JSON file.  
- Third-party drivers can still ship their own **default** configs via `importlib.resources`; that has no impact on the in-tree files.

---

*Last updated: {{DATE}}* 