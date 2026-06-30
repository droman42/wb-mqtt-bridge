# Initial project survey — 2026-05 (archived snapshot)

**Status:** FROZEN historical analysis — the starting-state survey written 2026-05-19→05-20 when
the action plan was first drafted, extracted verbatim from `action_plan.md` §1–§3 on 2026-06-30
(plan task §5.2 #4). **Superseded — do not read as current:** the device fleet, the UI↔backend
coupling, and the Docker/CI pipeline it describes have all been rebuilt since. For current truth see
`docs/architecture/*`, `docs/design/ui_backend_contract.md`, and `ops/` (+ `ops/INSTALL.md`). Kept
for provenance only.

---

## 1. Current State Snapshot

### 1.1 Where development paused
Both repos last meaningfully active on **2025-07-27**. Both landed a commit called `SSE goes thru!!!` within 33 seconds of each other; nothing since. The project is paused, not abandoned.

`main` has three uncommitted edits (the WIP — see §2).

The arc of the last ~10 commits in this repo shows the focus moved from *adding device support* to *hardening for production*: scenario lifecycle (startup/shutdown/validation/conditions), SSE event streaming, and exposing scenarios as Wirenboard virtual devices. Version is still `0.5.0 Alpha` in `pyproject.toml`.

### 1.2 Supported devices (seven driver classes)

| Driver | Library | Hardware | Maturity |
|---|---|---|---|
| `LgTv` | asyncwebostv (PyPI 0.2.7) | LG OLED TVs | Mature, ~2.5k LoC |
| `EMotivaXMC2` | pymotivaxmc2 (PyPI 0.6.8) | eMotiva XMC-2 AVR | Mature, dual-zone |
| `AppleTVDevice` | pyatv (git pinned) | Apple TV | Mature, ~1.8k LoC |
| `AuralicDevice` | openhomedevice (git, ARM lxml fix) | Auralic Altair G1 | Mature, UPnP + IR fallback |
| `BroadlinkKitchenHood` | broadlink | RF kitchen hood | Solid |
| `WirenboardIRDevice` | aiomqtt | Generic IR via Wirenboard | Solid |
| `RevoxA77ReelToReel` | aiomqtt (IR via WB) | Revox A77 tape deck | Solid |

**Thirteen config files** in `config/devices/`: 2× LG TV, 2× Apple TV, eMotiva, kitchen hood, Auralic streamer, DVDO upscaler, Panasonic VHS, Pioneer LD, MF amplifier, Revox tape, Zappiti media player (`video`).

**Four scenarios** in `config/scenarios/`: `movie_appletv`, `movie_ld`, `movie_vhs`, `movie_zappiti`.

**Local lib siblings**: `../asyncwebostv` and `../pymotivaxmc2` exist but `pyproject.toml` now consumes them from PyPI. Path deps were removed during the migration; clones are for upstream debugging only.

### 1.3 UI / backend coupling

**As originally surveyed (2026-05-19):**
- UI's Dockerfile did `pip3 install -e ./wb-mqtt-bridge` and codegen imported backend Python models directly (e.g. `wb_mqtt_bridge.domain.devices.models:WirenboardIRState`).
- UI's `config/device-state-mapping.json` referenced backend paths and Python module names.
- UI's `src/types/api.ts` was hand-maintained, not generated from OpenAPI.
- `nginx.conf` hardcoded `192.168.110.250:8000`.
- `VITE_MQTT_URL=ws://192.168.110.250:9001` was baked in at UI build time.

**Resolved by P1 (2026-05-20):** Python is gone from the UI build (#3.5) — state types now come from the backend's `/openapi.json` contract (#3); the mapping file moved to the backend (#4.5); the proxy IP and MQTT URL are container-runtime config (#4). The coupling is now contract-based: the UI build still consumes a sibling backend checkout for device configs + `openapi.json`, but no longer imports Python. The choice was "loose contract vs tight contract" — we now have the loose contract.

---

## 2. WIP Diff Analysis

**Footprint:** +29 / −321 across 3 files. Net: a **cleanup with one preparatory hook**, not a feature.

### 2.1 What changes
- **`models.py`** — adds `DeviceCategory` enum (`DEVICE` | `APPLIANCE`) and a `device_category` field on `BaseDeviceConfig`, default `DEVICE`. Backwards-compatible.
- **`kitchen_hood.json`** — sets `device_category: "appliance"`.
- **`base.py`** — deletes 321 lines:
  1. Dead breadcrumb comments (`# X is now handled by WBVirtualDeviceService`)
  2. An orphaned docstring at line 105 of the original — broken code from an earlier botched edit
  3. Four real methods (`_validate_wb_controls_config`, `_validate_wb_state_mappings`, `validate_wb_configuration`, `_validate_handler_wb_compatibility`) whose logic now lives on `WBVirtualDeviceService._validate_wb_configuration_from_config` (`src/wb_mqtt_bridge/infrastructure/wb_device/service.py:756`).

### 2.2 Findings to address before commit
1. **`device_category` is unused.** No code reads it yet. This is fine but should be explicit in the commit message — it's a hook for a future feature, not a behavior change.
2. **The diff breaks 4 tests in `tests/test_wb_virtual_device_phase3.py`** (lines 204, 237, 278, 302 call the removed methods). That file's docstring says *"Tests for Phase 3 WB Virtual Device implementation"* — it's tied to a completed migration phase. Its successor is `tests/unit/test_wb_virtual_device_service.py` (31 tests vs the old 13, covers the same surface via the new service).
   **Decision:** delete the phase3 file as part of this commit.

### 2.3 Suggested commit
Single commit:
```
refactor(base): remove WB validation logic now owned by WBVirtualDeviceService

- Delete duplicate validation methods from BaseDevice (logic lives on WBVirtualDeviceService)
- Delete tests/test_wb_virtual_device_phase3.py (covered by test_wb_virtual_device_service.py)
- Add DeviceCategory enum and BaseDeviceConfig.device_category field (default: device); kitchen_hood marked appliance. No behavior change yet.
```

---

## 3. Docker / CI / CD Analysis

### 3.1 The pipeline as it actually runs

```
GitHub Actions (Ubuntu + QEMU)
  │
  ├─ Backend: docker buildx --platform linux/arm/v7 → /tmp/wb-mqtt-bridge.tar.gz
  │           (no tests, no lint, no type-check — build only)
  │           uploaded as artifact, 7-day TTL
  │
  └─ UI: checks out BOTH repos (UI repo + wb-mqtt-bridge as subdir)
         → pip install -e ./wb-mqtt-bridge  (in UI's builder stage)
         → npm run gen:device-pages --mode=package  (imports Python models)
         → npm run typecheck:all
         → docker buildx --platform linux/arm/v7
         → artifact, 30-day TTL
         (no Jest, no Playwright in CI)

User's machine (Wirenboard ARMv7)
  │
  ./manage_docker.sh deploy <name>
    → GitHub API call (PAT from local plaintext config) → latest successful run
    → download .tar.gz → docker load
    → docker run -d --network host
      backend mounts: /opt/wb-bridge/{config,logs,data}
      UI mounts:      /etc/localtime only
```

### 3.2 What works well
- **`LEAN=true` build arg** strips ~everything non-essential from `/opt/venv` for ARMv7.
- **UV** (Astral) as the Python installer with PiWheels fallback for ARM.
- **SSE-correct nginx**: `proxy_buffering off`, `proxy_read_timeout 24h`, `Connection ""` on `/events/`.
- **`manage_docker.sh`** (1079 lines) is legitimate, well-structured ops glue.

### 3.3 Rough edges

| # | Issue | Where | Severity |
|---|-------|-------|----------|
| 1 | No tests run in either CI workflow | both `build-arm.yml` | High |
| 2 | No lint / mypy / ruff in backend CI; UI has typecheck only | both | Medium |
| 3 | Hardcoded `192.168.110.250:8000` in nginx | `wb-mqtt-ui/nginx.conf:35,44` | High |
| 4 | Hardcoded `ws://192.168.110.250:9001` baked into UI bundle at build time | `wb-mqtt-ui/Dockerfile:50` | High |
| 5 | GitHub PAT in plaintext on the Wirenboard | `docker_manager_config.json` | High |
| 6 | UI build requires sibling backend checkout, no submodule or orchestration | `wb-mqtt-ui/Dockerfile:34` | Medium |
| 7 | Codegen depends on Python module paths — rename = silent UI build break | `device-state-mapping.json` | Medium |
| 8 | Two git deps (`openhomedevice` branch, `pyatv` commit) can disappear; no vendoring | `pyproject.toml:52-53` | Medium |
| 9 | Artifacts ephemeral (7d / 30d) — no GHCR, no registry | both `build-arm.yml` | Medium |
| 10 | `no-cache: true` on backend buildx — every build from scratch | backend `build-arm.yml:33` | Low (intentional) |
| 11 | Hardcoded `linux/arm/v7` — no amd64 dev image | both | Low |

### 3.4 Effect of plausible deployment changes
- **GHCR push instead of artifacts**: kills the API-+-PAT machinery in `manage_docker.sh`; gives durable image history. Small change.
- **Top-level docker-compose**: kills the sibling-repo COPY trick; forces a clear answer on where prod config lives. Small change.
- **Parameterize URLs**: `envsubst` on `nginx.conf.template` at container start; `/config.js` runtime shim for `VITE_MQTT_URL` instead of build-time baking. Small change, big flexibility win.

---
