# Action Plan — wb-mqtt-bridge

**Status:** Working draft. Updated 2026-05-19.
**Scope:** Both `wb-mqtt-bridge` (this repo) and the sibling UI repo at `../wb-mqtt-ui`.

This document captures the current state of the project, an analysis of the in-flight refactor and the Docker/CI pipeline, and a prioritized action plan. It is intended to be revised as we discuss open questions.

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
| `EMotivaXMC2` | pymotivaxmc2 (PyPI 0.6.7) | eMotiva XMC-2 AVR | Mature, dual-zone |
| `AppleTVDevice` | pyatv (git pinned) | Apple TV | Mature, ~1.8k LoC |
| `AuralicDevice` | openhomedevice (git, ARM lxml fix) | Auralic Altair G1 | Mature, UPnP + IR fallback |
| `BroadlinkKitchenHood` | broadlink | RF kitchen hood | Solid |
| `WirenboardIRDevice` | aiomqtt | Generic IR via Wirenboard | Solid |
| `RevoxA77ReelToReel` | aiomqtt (IR via WB) | Revox A77 tape deck | Solid |

**Twelve config files** in `config/devices/`: 2× LG TV, 2× Apple TV, eMotiva, kitchen hood, Auralic streamer, DVDO upscaler, Panasonic VHS, Pioneer LD, MF amplifier, Revox tape.

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

## 4. Action Plan

Ordered by **value / effort**. Each item sized for one focused PR.

### P0 — Unblock and stabilize

| # | Task | Effort |
|---|------|--------|
| 0a | **DONE** 2026-05-19 — backend `ab5402d`, UI `8ab2cfa`. On survey, the 8 modified UI files turned out to be one coherent appliance-category feature (not an unrelated layout refresh as initially thought) plus two unrelated SSE console-log cleanups; `docs/appliances.md` was the matching design doc. Shipped as a single paired commit per repo. `config/system.json` (UI) left untracked pending later check; `data/` added to UI `.gitignore`. | 30 min |
| 0b | **DONE** 2026-05-19. Deleted local + origin: backend `code_structure`, backend `feature/wb-virtual-device-emulation`, UI `code_structure`. Both repos now have only `main`. | 5 min |
| 1 | **DONE** 2026-05-19 — `ab5402d`. Shipped together with #0a as the backend half of the paired change. | 30 min |
| 2 | **DONE** 2026-05-19 — backend `36b54d8`, UI `5be5bd2`. Wired tests into CI on amd64, gated ARM build. Final state: 107 pass / 109 skip / 0 fail. **109 tests skipped with explicit `reason=`** are pre-existing API drift / collection hangs from the scenario+state-store refactors — deferred to a future cleanup PR, not deleted. UI side wires `npm run lint + typecheck:all + validate:generated-code + validate:components`; did **not** wire `npm test` (jest preset misconfigured, no test files exist). See commit body for the full skip inventory. | 1 hour planned → ~2 hrs |

### P1 — Reduce coupling without changing architecture

| # | Task | Effort |
|---|------|--------|
| 3 | **DONE** 2026-05-20 — backend `6bc30fc`, UI `312fa56`. Generate OpenAPI types for the UI. Hit FastAPI's `/openapi.json` and run `openapi-typescript` to produce `src/types/api.gen.ts`. Replace `src/types/api.ts` gradually, starting with the simplest endpoints. Removes the API-surface coupling (hand-maintained types). Does **not** remove the Python AST coupling in device-page codegen — see #3.5. | ~½ day |
| 3.5 | **DONE** 2026-05-20 — backend `6bc30fc`, UI `5a71929`. Eliminate the Python AST dependency in UI codegen. Type the backend's `/devices/{id}/persisted_state` endpoint with a discriminated union of state models (`LgTvState`, `EmotivaXMC2State`, …) so they land in `/openapi.json` automatically. Rewrite `wb-mqtt-ui/src/lib/StateTypeGenerator.ts` (the actual Python-spawning logic lives there — `spawn(python3, ['-c', importlib + ast.parse(...)])` — invoked by `src/scripts/generate-device-pages.ts`) to consume the OpenAPI schema instead of spawning a Python subprocess and AST-parsing imported Pydantic classes. Remove `pip install -e ./wb-mqtt-bridge` and Python from the UI Dockerfile. Closes the "silent break on backend rename" failure mode. See §7 (Codegen Alternatives — Option 1). | ~1 day |
| 4 | **DONE** 2026-05-20 — UI `395e538`. Parameterize nginx + MQTT URLs. `envsubst` on `nginx.conf.template` at start; runtime `runtime-config.js` shim for the MQTT URL instead of build-time bake. Defaults preserve `192.168.110.250` so existing deploys are unchanged. | 2 hours |
| 4.5 | **DONE** 2026-05-20 — backend `2e5674c`, UI `7c3f3a8`. Moved `device-state-mapping.json` from the UI repo to the backend repo. Paths inside are now relative to the mapping file's own directory; the UI resolves them, so one file serves both CI and local layouts (the `.local.json` was retired). | 30 min |

### P2 — Documentation reconciliation

| # | Task | Effort |
|---|------|--------|
| 5 | Archive `docs/TODO.md` (move to `docs/history/phase1-2-done.md`); delete the Roborock bullet from the backend README. | 15 min |
| 6 | **DONE** 2026-05-19 — committed as-is in UI `8ab2cfa` as part of the appliance-category feature. The doc accurately describes the current code direction. | 15 min |

### P2.5 — UI architecture (design discussion, then implement)

| # | Task | Effort |
|---|------|--------|
| 10 | **Design a contract-based button/action placement.** Today, *where* a control renders inside its remote zone is governed by an **implicit, undocumented convention**, not a contract — and we want to replace it. Two mechanisms, both verified in code (2026-05-20): (a) **slot zones** (power / volume / nav-cluster / pointer) fill fixed slots by **action-name substring matching** (`ZoneDetection.createPowerButtonsConfig`, `createMenuZone`, `createVolumeZone`, `createPointerZone` — e.g. name contains `off`→left, `on`→right; `up/down/left/right/ok`→D-pad); (b) **array-order zones** (screen vertical stack, playback row, tracks row) render in the order actions appear, which traces back through `deriveGroupsFromConfig` → `processAllGroupActions` to the **key order of `config/devices/*.json` commands**. This is fragile (reordering a config silently moves buttons; renaming/retyping an action can drop it from a slot or land it in the wrong one) and surprising. **Action: discuss options and design an explicit placement contract.** Candidate directions to weigh — (1) explicit per-action `slot`/`position`/`order` fields in the device config; (2) a dedicated **layout manifest** owned by the backend and served/consumed as a contract (aligns with §7 Codegen Option 2, runtime-driven UI); (3) command-level UI annotations (`x-ui-*`-style). Trade-off: authoring effort vs. determinism + reviewability. Touches both repos. **Design first — not yet scoped for implementation.** | TBD (design) |

### P2.6 — Adopt get-shit-done (GSD) workflow

| # | Task | Effort |
|---|------|--------|
| 11 | **Adopt GSD** ([gsd-build/get-shit-done](https://github.com/gsd-build/get-shit-done)) as the dev workflow. *(Reverses the earlier "out of scope" verdict — re-study 2026-05-20 found GSD is built for solo devs, has a brownfield path (`/gsd-map-codebase` + `/gsd-ingest-docs`), and handles multi-repo via `/gsd-workspace --repos`.)* Sequencing: **(A) archive stale docs — DONE**; **(B) fix living docs to match code — DONE**; **(C) author the GSD-seed artifacts** (PROJECT vision, ARCHITECTURE, the UI↔backend CONTRACT, CONVENTIONS) + a few ADRs for decisions already made (OpenAPI additive-injection, backend-owned mapping, runtime config, Miele removal); **(D) install GSD** (`npx get-shit-done-cc@latest`), run `/gsd-map-codebase` then `/gsd-ingest-docs` to bootstrap `.planning/`. Decide whether `.planning/` is tracked or gitignored, and whether to use `/gsd-workspace` across both repos. | C: ~½–1 day; D: ~½ day |

### P3 — Real ops improvements (later, optional)

| # | Task | Effort |
|---|------|--------|
| 7 | Push images to GHCR instead of artifacts. Simplifies `manage_docker.sh`, removes the GitHub-API + PAT machinery, gives durable image history. | ~½ day |
| 8 | Top-level `docker-compose.yml` that pulls both GHCR images and wires them by service name. Requires #7. | 2 hours |
| 9 | Decide on monorepo vs. shared contract. **Defer until after P1.** | — |

### Explicitly out of scope (for now)
- **Multi-arch builds** — only matters if dev moves off the ARMv7 target.
- **Rewriting `manage_docker.sh`** — works fine; touch it only when GHCR lands.

---

## 5. Open Questions (to be decided before acting)

*Use this section to capture decisions as we discuss. Each answered question will inform revisions above.*

- [ ] **Are we keeping the project on ARMv7 / Wirenboard exclusively, or do we want a dev path on amd64 too?** Affects #2 (test target arch), #7 (multi-arch GHCR tags), #11.
- [ ] **Is the Wirenboard the only deployment target, or do we want to deploy to a separate Linux box and talk to the WB controller over MQTT?** Affects the urgency of items #3, #4 (hardcoded IPs).
- [ ] **Is the long-term direction one repo or two?** If "one," do #3 anyway (OpenAPI contract) and then merge — much cheaper post-contract. If "two," do #3 for sure, and the contract is the *point*.
- [ ] **Are there device drivers planned that aren't shipped yet (Roborock, SprutHub, Apple TV app launching, IR learning UI from the old TODO)?** Affects whether §1.2 is the final list or a checkpoint. *(Miele dropped 2026-05-20 — repeated integration attempts failed; `asyncmiele` dependency removed.)*
- [ ] **Is `device_category` going to drive real behavior soon?** If yes — what differs between `device` and `appliance`? If not — should we even ship the enum now, or wait until we know what it gates?
- [ ] **Do we also want to move to runtime-driven UI rendering (Codegen Alternatives — Option 2)?** Eliminates `.gen.tsx` codegen entirely; UI fetches a per-device manifest from the backend and renders dynamically. Strong industry-practice alignment (Home Assistant / ioBroker pattern). ~2–3 day refactor. Default position: defer until after #3.5 ships and we feel actual pain that justifies it.
- [ ] **How should button/action placement be made explicit/contract-based instead of relying on config command order?** See item #10. The current implicit convention works (verified unchanged by the P1 work) but the user explicitly dislikes layout depending on undocumented config ordering. Decide between: explicit per-action `slot`/`order` fields, a backend-owned layout manifest (couples naturally with Option 2 above), or command annotations. This question and the Option-2 question are related — a runtime layout manifest could subsume both.
- [ ] _Add others as we discuss._

### 5.1 Backlog carried over from the old TODO

These were the only **unfinished** items in `docs/TODO.md` when it was archived to `docs/history/phase1-2.md` (2026-05-20). Kept here so live work is tracked in one place; Roborock is already covered by the planned-drivers question above.

- [ ] **Apple TV app launching** — `Запуск приложений на AppleTV`.
- [ ] **Re-verify the Revox reel-to-reel after the Wirenboard refactor** — `Проверить катушечник после рефакторинга Варенборда`. Device tests were rewritten in the hexagonal pass, but on-hardware behaviour is unconfirmed.
- [ ] **SprutHub templates for the new devices and all scenarios** — `Сделать/подобрать шаблоны SprutHub для новых девайсов и всех сценариев`.
- [ ] **Restore the SprutHub integration and connect it to Yandex Alice** — `Восстановить работу SprutHub, соединить с Алисой`.
- [ ] **IR-code learning page** — capture codes from physical remotes (`Сделать страничку для обучения IR кодам с пультов`).

---

## 6. Revision Log

- **2026-05-19** — Initial draft. Captures research from a deep survey of both repos plus WIP and CI/CD analysis.
- **2026-05-19** — Added §7 (Codegen Alternatives) after deep-dive into the device-page generation pipeline. Inserted P1 items #3.5 (eliminate Python AST coupling) and #4.5 (relocate `device-state-mapping.json`). Added a new Open Question about runtime-driven UI.
- **2026-05-19** — Branch audit. Confirmed `main` is the source of truth in both repos; all feature branches are fully merged. Discovered the UI repo has 8 modified + 3 untracked files, including a `generate-device-pages.ts` change paired with the backend `device_category` WIP. Added P0 items #0a (UI WIP triage) and #0b (delete stale branches). Revised P2 #6 — `wb-mqtt-ui/docs/appliances.md` is untracked rather than stale-committed; action is now "decide whether to commit at all."
- **2026-05-19** — Executed #0a, #1, #0b. Backend `ab5402d` + `b7aa246` (this doc) pushed to `origin/main`; UI `8ab2cfa` pushed to `origin/main`. Three stale branches deleted (local + origin): backend `code_structure`, backend `feature/wb-virtual-device-emulation`, UI `code_structure`. Both repos now have only `main`. `appliances.md` shipped as part of the paired feature, resolving P2 #6 as "commit as-is" (design doc reflects current code).
- **2026-05-19** — Executed #2 (wire tests into CI). Backend `36b54d8` + UI `5be5bd2` pushed. Discovered the test suite had significant pre-existing API drift (scenarios devices dict→list, ScenarioManager kwarg rename, execute_command→execute_action, validate()→validate_configuration() semantic change, ScenarioMockStateStore needing load/save). Fixed what was mechanical; marked 14 files + 18 individual tests as `pytest.mark.skip(reason=...)` for the rest. CI ships green; ~half the suite runs. **Follow-up needed**: incrementally repair the skipped tests in dedicated PRs.
- **2026-05-19** — Started repairing the skipped tests semantically (rewrite where production contracts moved, not just mechanical assertion patching). Pushed across 7 commits (`b05d6db`, `66c5018`, `939f2b9`, `4a9f6fa`, `864fa19`, `e18f9f7`). Final state: **151 passed / 58 skipped / 0 failed** (was 107 / 109 / 0). Recovered ~51 tests. Files fully repaired or consolidated: test_state_store, test_state_store_error_handling, test_config_manager, test_message_handling, test_scenario, test_scenario_manager, test_wb_virtual_device_service (individual skips), test_persistence_integration (complete rewrite), test_integration, test_kitchen_hood_parameters, test_wirenboard_ir_params, test_revox_params, test_scenario_state_persistence (consolidated). **Still skipped** (~58 tests across 6 files): test_emotiva_params.py (hangs at collection), test_lg_tv.py + test_lg_tv_params.py (collection / 17 failing fixture-drift), test_scenario_api_integration.py (~14 errors — FastAPI mocking), test_auralic_device.py + test_auralic_update_task.py (hang at collection — openhomedevice import-time side-effects). Each remaining file needs deeper rework; recommended as separate follow-up PRs to keep diff size sane.
- **2026-05-19** — Completed the remaining 6 files (rewritten as fresh tests against the post-hexagonal-refactor drivers, not mechanical fixes). Commits `c8c1b0e`, `7e2d7cd`, `9f6757f`, `7a50f6e`. **State: 199 passed / 0 skipped / 0 failed.** Approach for the device drivers: bypass setup() entirely (which connects to real hardware), inject AsyncMocks for the driver's external client (openhomedevice / pymotivaxmc2 EmotivaController / WebOS MediaControl / etc.), flip state.connected=True, then drive handle_X methods directly and assert delegation + state mutations. test_lg_tv.py contained CLI-tool helpers misnamed `test_*` — renamed to `_check_*`/`_run_*` so pytest stops trying to collect them. test_scenario_api_integration.py rewritten with correct state.initialize signature and updated response-envelope assertions.
- **2026-05-19** — Applied the same fresh-rewrite treatment to the device test files that had only received mechanical patches earlier (kitchen_hood, wirenboard_ir, revox, apple_tv). Commit `9501ff9`. **Final state: 225 passed / 0 skipped / 0 failed.** Every device-driver test file now follows the same hexagonal pattern: typed Pydantic config in the fixture, external dependency injected as an AsyncMock, setup() bypassed, handlers driven directly. Tests added cover compensation logic (kitchen_hood speed-after-light), sequence execution with configurable delay (revox), and full handler coverage (apple_tv remote control + audio + apps). Net +26 tests vs the previous round. All originally-skipped tests are now passing or have been replaced with meaningful equivalents under the new architecture.
- **2026-05-20** — Removed Miele appliance support (never implemented — no driver, config, or test ever existed; repeated integration attempts failed). Commit `5f63513`: dropped `asyncmiele==0.2.6` from `pyproject.toml`, regenerated `uv.lock`, removed the Miele bullet from `README.md` and the Miele task from the TODO. The Roborock bullet was **kept** — it is a planned future feature, not a false current claim (revises the original P2 #5 wording, which had called for deleting it).
- **2026-05-20** — Completed P2 #5. Archived `docs/TODO.md` → `docs/history/phase1-2.md` (history preserved via `git mv`, header note added). Its 5 still-open items were migrated to §5.1 (Backlog) so live work stays tracked rather than buried in an archive. **P2 is now fully done.**
- **2026-05-20** — Completed **all of P1** (#3, #3.5, #4, #4.5) in one session. The architectural prize — removing the UI build's dependency on the Python package — is shipped.
  - **#3** (backend `6bc30fc`, UI `312fa56`): backend exposes device-state models in `/openapi.json` via an additive `app.openapi()` override (`bootstrap._install_openapi_with_state_models`) — no endpoint signature change, so runtime serialization and the custom `model_dump` overrides are untouched. New `wb-openapi` CLI dumps a committed `openapi.json` snapshot (the contract). UI added `openapi-typescript` + `gen:api-types` → `src/types/api.gen.ts`. 4 new backend tests; suite 229 pass.
  - **#3.5** (backend in `6bc30fc`, UI `5a71929`): `StateTypeGenerator` reads state shapes from `components.schemas` instead of spawning `python3` + `ast.parse`. Discovered the prior `pip install -e` was already **dead** (state config was only loaded in `local` mode, never `package`/CI). Enabled state-gen in package mode too, then removed Python entirely from the UI Dockerfile + CI. Validated a clean package-mode build: 8 state classes, typecheck/lint/validate all green.
  - **#4.5** (backend `2e5674c`, UI `7c3f3a8`, +`9f7da0e` untracking an accidental `system.json`): mapping now lives in the backend with directory-relative paths; the UI client resolves them, retiring the `.local.json` duplicate and the scenario handler's duplicate loaders.
  - **#4** (UI `395e538`): nginx proxy IP via `envsubst` template + MQTT URL via the (newly-wired) `window.RUNTIME_CONFIG` runtime shim; defaults preserve current behavior. **P1 is now fully done — only P3 (ops, deferred) remains.**
- **2026-05-20** — Verified the P1 codegen changes did **not** alter the remote-control layout: regenerated all layout artifacts at the pre-change baseline (`5be5bd2`) vs HEAD — all 17 `.gen.tsx` files (13 device + 4 scenario) byte-identical; `index.gen.ts` identical apart from `generatedAt` timestamps. Traced the within-zone placement mechanism in code (slot-by-action-name for power/volume/nav/pointer; array-order for screen/playback/tracks, sourced from `config/devices/*.json` command key order). The alphabetized `openapi.json`/`*.state.ts` feeds only the `.hooks.ts` typing layer, never the layout. Added **P2.5 #10** (design a contract-based placement) + a matching §5 open question — the user dislikes layout depending on an implicit config-order convention and wants an explicit contract designed before any change.
- **2026-05-20** — **Decided to adopt GSD** (added **P2.6 #11**; removed it from "out of scope"). Re-studied the framework: solo-friendly, brownfield path, multi-repo via workspaces. Audited all documentation in both repos against current code (two subagents) and executed the doc-reconciliation prerequisites:
  - **Step A (archive):** moved 28 backend + 6 UI superseded design/implementation plans to `docs/archive/` with a "not current, don't ingest" header (backend `124ca55`, UI `8bb360b`). The live `docs/` surface is now 13 backend + 5 UI docs.
  - **Step B (fix living docs):** backend README de-stale'd + trimmed 1146→878 (`55ca7e6`); backend living-doc batch + emotiva (`db5c18b`, `0493df4`); UI README rewritten 299→121 for the Python-free contract build (`16b95dc`); UI deployment + network-config rewritten for runtime env-var config (`9d0745b`); remote_layout trimmed to the spec + accurate impl note, page_instructions + appliances corrected (`b8a15e9`).
  - **Step C/D pending** — see #11.

---

## 7. Codegen Alternatives (reference)

This section captures the analysis behind P1 #3.5 and the related Open Question. Keep it for context when revisiting the decision.

### 7.1 How the current device-page codegen actually works

The UI generates a React page per device at **build time**, producing static artifacts that are committed to git:

- 17 × `wb-mqtt-ui/src/pages/devices/{deviceId}.gen.tsx`
- 8 × `wb-mqtt-ui/src/types/generated/{StateClass}.state.ts`
- 1 × `wb-mqtt-ui/src/pages/devices/index.gen.ts` (router manifest)

The running UI **never regenerates them**. It fires actions via `POST /devices/{id}/action` and consumes state updates via SSE. The `.gen.tsx` files only describe the *shape* of each device's control panel (zones, buttons, groups), delegating rendering to a shared `RemoteControlLayout` component.

The generator (`wb-mqtt-ui/src/scripts/generate-device-pages.ts`, 802 lines) needs three inputs:

| # | Input | How it's obtained today | Coupling cost |
|---|---|---|---|
| **A** | Device config (commands, params, groups, names) | Reads `wb-mqtt-bridge/config/devices/*.json` from sibling checkout | Just a path. Cheap. |
| **B** | State model field info (name, type, optional, default) | Spawns `python` subprocess that does `importlib.import_module(...)` + `ast.parse(inspect.getsource(cls))` to walk Pydantic class fields | **The expensive coupling.** Requires `pip install -e ./wb-mqtt-bridge` in UI build, Python in the UI builder image, and breaks silently on backend rename. |
| **C** | Mapping: `DeviceClass → stateClassImport + configs` | `wb-mqtt-ui/config/device-state-mapping.json` (in the UI repo) | Hand-maintained; doesn't auto-sync with backend changes. |

The three `--mode=` flags only swap how input A is obtained (`api` hits a running backend, `local`/`package` read JSON from disk). They do not affect the Python coupling for input B.

### 7.2 What FastAPI exposes today vs. what codegen needs

Already in `/openapi.json`:
- `BaseDeviceConfig` (covers ~all of input A)
- `CommandResponse`, `GroupedActionsResponse`, `SystemInfo`, etc.

**Not** in `/openapi.json`:
- Device state models (`LgTvState`, `EmotivaXMC2State`, …) — the very classes codegen imports via Python. The `/devices/{id}/persisted_state` endpoint returns `Dict[str, Any]` instead of a typed state.
- Per-action parameter classes (`SetVolumeParams`, `MoveCursorParams`, …).

**Key leverage point:** typing one endpoint with a discriminated union of state models exposes every state class via OpenAPI automatically — ~10 lines on the backend.

### 7.3 Industry patterns

| Project | Pattern |
|---|---|
| Home Assistant | Backend sends schema-like dict per "config flow"; UI renders dynamically. Entities have a `domain` and the frontend has hardcoded "more-info" components per domain. Strong runtime introspection. |
| ioBroker | "JSON Config" schema spec; adapter ships a JSON file describing its admin UI. |
| openHAB | "Items" with types; UI auto-picks widgets per item type. Sitemaps = declarative UI DSL. |
| Node-RED | Nodes declare HTML template + edit dialog spec; editor renders dynamically. |

**Common thread:** a small set of well-known control primitives (switch, slider, select, button) keyed by device/entity type, with backend-owned schema served at runtime. **Almost nobody does build-time codegen of per-device React pages from server-side Python AST parsing.** We are an outlier here.

Of the JSON-Schema → form tools, only `react-jsonschema-form` (rjsf) has meaningful adoption in this neighborhood. Vendor-extension UI hints (`x-ui-*` in OpenAPI) have never standardized. For pure OpenAPI → TS types, `openapi-typescript` + `openapi-fetch` is the minimum-tax choice.

### 7.4 Four alternatives, ranked least → most disruptive

#### Option 1 — Keep build-time codegen, kill the Python AST step (**recommended; this is P1 #3.5**)

**Mechanism.** Type `/devices/{id}/persisted_state` with a discriminated union of state models so they land in `/openapi.json`. Rewrite `StateTypeGenerator.ts` to consume the OpenAPI schema. Remove Python + `pip install -e` from the UI Dockerfile.

**What dies.** Python AST parsing. `pip install -e ./wb-mqtt-bridge` in UI build. Python in the UI builder image. Silent break on rename.

**What survives.** Build-time codegen, `.gen.tsx` files, `RemoteControlLayout`, the mapping file (now derivable but can stay hand-maintained).

**Effort.** ~1 day, mostly UI-side.

**Tradeoff.** Backend still owns the schema; UI build needs an OpenAPI snapshot (fetched from a running backend at codegen time, or committed as `openapi.json`). Same operational shape as today, but the coupling is contract-based instead of import-based.

#### Option 2 — Backend ships a device-manifest endpoint; UI renders dynamically at runtime

**Mechanism.** `GET /devices/{id}/manifest` returns everything needed to render that device's page (metadata, command groups, parameter schemas, state shape as JSON Schema). UI ships a handful of generic primitives plus the `RemoteControlLayout` shell, fetches the manifest at page load, and renders.

**What dies.** The entire codegen pipeline. `gen:device-pages`. `device-state-mapping.json`. Python in UI build. The mapping problem.

**What survives.** `RemoteControlLayout`, the zone/group taxonomy from `docs/remote_layout.md`, action execution, SSE state stream.

**Effort.** ~2–3 days. Manifest endpoint is straightforward; the work is on the UI side (manifest-driven page renderer).

**Tradeoff.** One extra fetch per device page (invisible at this scale). Harder static typing (rendering from a runtime schema is `unknown`-shaped TypeScript). New devices on the backend appear in the UI on next refresh. Backend renames break loudly with a 404 at runtime, not silently at build time.

This is the industry-pattern answer. Recommended as a *follow-on* to Option 1, when/if we feel pain that justifies the refactor.

#### Option 3 — Reverse direction: backend owns codegen, UI consumes static manifests

**Mechanism.** Backend grows a CLI subcommand (`wb-bridge generate-manifests`) that walks configured devices and writes `manifests/{device_id}.json`. UI reads those JSON manifests at build time. No Python ever touches the UI build.

**What dies.** Python in the UI builder. The TypeScript-spawning-Python pattern.

**Tradeoff.** Manifests need to live somewhere both repos can reach (UI repo? backend repo published as releases? third "contract" repo?). Operationally awkward across two repos; rhymes with the broader mono-vs-multi-repo question. **Defer until the repo structure is decided.**

#### Option 4 — Drop codegen entirely, fully runtime, with rjsf for parameter dialogs

Like Option 2 plus `react-jsonschema-form` for command-parameter input dialogs. Most commands today are pushbuttons or simple ranges, so rjsf's automation doesn't pay off at our scale. **Skip.**

### 7.5 Recommendation

Adopt **Option 1 now** (P1 #3.5). Re-evaluate **Option 2** after Option 1 ships — once state models are in `/openapi.json`, Option 2 becomes a pure UI-side refactor with no further backend work. Keep **Option 3** in mind only if/when we move to a monorepo. **Skip Option 4** entirely.
