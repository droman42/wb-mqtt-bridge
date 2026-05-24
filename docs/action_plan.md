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

## 4. Action Plan

Ordered by **value / effort**. Each item sized for one focused PR.

### P0 — Unblock and stabilize

| # | Task | Effort |
|---|------|--------|
| 0a | **DONE** 2026-05-19 — backend `ab5402d`, UI `8ab2cfa`. On survey, the 8 modified UI files turned out to be one coherent appliance-category feature (not an unrelated layout refresh as initially thought) plus two unrelated SSE console-log cleanups; `docs/appliances.md` was the matching design doc. Shipped as a single paired commit per repo. `config/system.json` (UI) left untracked pending later check; `data/` added to UI `.gitignore`. | 30 min |
| 0b | **DONE** 2026-05-19. Deleted local + origin: backend `code_structure`, backend `feature/wb-virtual-device-emulation`, UI `code_structure`. Both repos now have only `main`. | 5 min |
| 1 | **DONE** 2026-05-19 — `ab5402d`. Shipped together with #0a as the backend half of the paired change. | 30 min |
| 2 | **DONE** 2026-05-19 — backend `36b54d8`, UI `5be5bd2`. Wired tests into CI on amd64, gated ARM build. Final state: 107 pass / 109 skip / 0 fail. **109 tests skipped with explicit `reason=`** are pre-existing API drift / collection hangs from the scenario+state-store refactors — deferred to a future cleanup PR, not deleted. UI side wires `npm run lint + typecheck:all + validate:generated-code + validate:components`; did **not** wire `npm test` (jest preset misconfigured, no test files exist). See commit body for the full skip inventory. | 1 hour planned → ~2 hrs |

### P0.5 — Functional correctness (top functional priority)

| # | Task | Effort |
|---|------|--------|
| 12 | **Investigate and fix the scenario layer — currently broken.** Per the project vision, the #1 success criterion is "it actually works": every device action + every scenario, end-to-end on real hardware. Device actions mostly work; **scenarios do not** (confirmed by the user 2026-05-20). This is the headline gap between today and "done = my house works", and is distinct from the architecture/docs/GSD track. Scope: reproduce the failure(s), determine whether it's startup/shutdown sequencing, condition evaluation, role-action dispatch, WB-adapter, or state — then fix and verify on hardware. | TBD (investigation first) |

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
| 11 | **ADOPTED THEN DROPPED** 2026-05-20 (too slow for a solo project — see §6 revision log; the dependency-hardening work it produced was kept). ~~**Adopt GSD** ([gsd-build/get-shit-done](https://github.com/gsd-build/get-shit-done)) as the dev workflow.~~ *(Reverses the earlier "out of scope" verdict — re-study 2026-05-20 found GSD is built for solo devs, has a brownfield path (`/gsd-map-codebase` + `/gsd-ingest-docs`), and handles multi-repo via `/gsd-workspace --repos`.)* Sequencing: **(A) archive stale docs — DONE**; **(B) fix living docs to match code — DONE**; **(C) author the GSD-seed artifacts** (PROJECT vision, ARCHITECTURE, the UI↔backend CONTRACT, CONVENTIONS) + ADRs 0001–0005 — DONE; **(D) install GSD + map-codebase + ingest-docs — DONE.** Outcome: backend-primary, `.planning/` **tracked** in git (no `/gsd-workspace`). 6-phase ROADMAP generated; **Phase 1 = Fix the Scenario Layer** (= P0.5 #12). See the Step D runbook below for the as-run sequence. | DONE |

#### Step D runbook — GSD bootstrap (DONE 2026-05-20; as-run record)

Bootstrapped **backend-primary** (`.planning/` lives here and is **tracked** in git; UI
referenced via the contract doc; no `/gsd-workspace` — revisit only if two-repo
coordination gets painful). As-run sequence:

1. `/gsd-config` → committed `b931430`. model profile **balanced**, **branching off**
   (push to `main`), `commit_docs=true` (`.planning/` tracked), `auto_advance=false`.
   ⚠️ **Ordering gotcha:** in the installed SDK version `/gsd-config` **cannot create
   `.planning/` on its own** — `config-ensure-section` / `config-set` both require the
   file to pre-exist. The config workflow must bootstrap via
   `gsd-sdk query config-new-project '{"commit_docs": true}'` (creates `.planning/` +
   canonical `config.json`). So config is only "step 1" *after* something creates
   `.planning/`; either run it via `config-new-project` (as done) or run step 2/3 first.
2. `/gsd-map-codebase` → committed `4223f39`. 4 parallel mapper agents wrote 7 docs:
   `.planning/codebase/{STACK,INTEGRATIONS,ARCHITECTURE,STRUCTURE,CONVENTIONS,TESTING,CONCERNS}.md`.
3. `/gsd-ingest-docs` (mode=new) → committed `98664f3`. Used a **curated 10-doc manifest**
   (5 ADRs + `ui_backend_contract` SPEC + `project`/`action_plan` PRDs +
   `architecture`/`conventions` DOCs) to stay on-intent and under the 50-doc cap — the raw
   `docs/` tree (53 `.md`) would have swept in the 29 archived "don't ingest" docs.
   Pipeline: 10 classifier agents → synthesizer → roadmapper. 0 conflicts. Produced
   `.planning/{PROJECT,REQUIREMENTS,ROADMAP,STATE}.md` + `intel/`. **Subsystem specs
   (`docs/scenarios/*`, `docs/devices/*`, etc.) were intentionally excluded** — read them
   at plan-time, or merge-ingest later with a narrow manifest.
4. `/gsd-progress` — **next** (routes onward). ROADMAP already finalized by ingest, so a
   separate `/gsd-new-project` is not needed.

First real phase to tackle via GSD: **ROADMAP Phase 1 = Fix the Scenario Layer**
(= P0.5 #12), the top functional priority
(`/gsd-discuss-phase 1` → `/gsd-plan-phase 1` → `/gsd-execute-phase 1`).

### P3 — Real ops improvements (later, optional)

| # | Task | Effort |
|---|------|--------|
| 7 | Push images to GHCR instead of artifacts. Simplifies `manage_docker.sh`, removes the GitHub-API + PAT machinery, gives durable image history. | ~½ day |
| 8 | Top-level `docker-compose.yml` that pulls both GHCR images and wires them by service name. Requires #7. | 2 hours |
| 9 | Decide on monorepo vs. shared contract. **Defer until after P1.** | — |

### Explicitly out of scope (for now)
- **Multi-arch builds** — *time-limited* out-of-scope. Deployment is Wirenboard-only, but the planned move to **Wirenboard 8+ (arm64/64-bit)** will require an **arm64** image alongside (or replacing) the current ARMv7 one. Revisit when the WB8+ migration is scheduled. (amd64 stays CI/dev-only — not a deploy target.)
- **Rewriting `manage_docker.sh`** — works fine; touch it only when GHCR lands.

### P3.6 — Topology + scenarios, round 2 (after Layer 3, before P4)

**Decided 2026-05-23.** `config/topology.json` + the 4 `movie_*` scenarios currently cover the
**living-room A/V chain only**. The remaining systems have capability maps (so their device pages
already render) but **no topology links and no scenarios**. Author them as a dedicated step **after
Phase 3 (Layer 3) completes** — so the new scenario pages render at runtime instead of through the
build-time codegen we're about to delete (no throwaway UI work). User is fine deferring to after
Layer 3.

Scope (confirmed reconciler-driven scenarios): **Music — Auralic → amp**, **Music — Revox → amp**,
**+ "some more"** (children's room TV+AppleTV likely; full list TBD with the user). `kitchen_hood`
stays appliance-only (no topology, correct).

**Blocked on a wiring interview from the user** (cannot be invented): which `mf_amplifier` input the
Auralic and the Revox each use; whether the children's room is standalone (TV + AppleTV, no routing)
or feeds anywhere. Then it's mechanical: add topology `links` (+ any `ordering`/`delay_ms`), write
thin `source/display/audio` scenario configs, let the existing reconciler drive them.

### P4 — Final acceptance & cleanup (do this LAST, after the whole redesign lands)

The scenario reconciler + monorepo + Layer 3 runtime rendering are being done **gradually**, so a
deliberate final pass is required once all phases are in. Gradual migration always leaves stale
code/models/config behind — budget real time for this; do not skip it.

1. **All devices migrated.** Capability maps exist for **every** driver class and device instance,
   not just the `movie_appletv` set + IR fleet built first — check `streamer` (Auralic),
   `reel_to_reel` (Revox), `kitchen_hood` (appliance), `children_room_tv`/`appletv_children`, etc.
2. **All scenarios migrated.** Every scenario is thin (`source/display/audio`) and reconciler-driven;
   no legacy `startup_sequence`/`shutdown_sequence` escape-hatch left unless deliberately kept (and
   documented why).
3. **UI works for everything.** Every device page **and** every scenario page renders and functions
   under the runtime model (Layer 3); `manual_steps` are displayed; nothing depends on the retired
   build-time codegen.
4. **Thorough code review + dead-code sweep.** Remove what the gradual migration superseded —
   likely candidates: the legacy imperative path (`Scenario.execute_startup_sequence` /
   `execute_shutdown_sequence`, the old shared-device `switch_scenario` branch, the string-condition
   evaluator, the dead `_validate_parameters`, vestigial `DeviceState.output`); the UI's duplicate
   scenario inheritance (`ScenarioVirtualDeviceHandler`/`Resolver`) + build-time generators once
   Layer 3 is authoritative; the `WB_SCENARIO_RECONCILER` kill-switch once the reconciler is the only
   path; any unused escape-hatch model fields; and superseded docs. Confirm the contract is clean
   (`openapi.json` has no orphaned models/fields).
5. **Hardware re-verification** of the whole system end-to-end after the cleanup (cleanups regress).
6. **Lifecycle-robustness leftovers (deferred from the 2026-05-22 hardware session).** The
   lifecycle cluster (Bug 2 non-fatal load · keep failed-setup devices registered · hardware-
   transparent shutdown + assumed-state persistence) shipped; these lower-value tails were
   deferred here:
   - **Defensive startup-failure cleanup.** The lifespan startup isn't wrapped, so a *rare/
     unexpected* error during startup (not the now-handled device/scenario cases) leaks partial
     resources (sockets/ports → a hung process). Wrap startup → best-effort release on failure +
     re-raise. (The common zombie cause — `load_scenarios` `SystemExit` — is already fixed.)
   - **Teardown noise.** `Task was destroyed but it is pending` (pyatv `CompanionAPI.disconnect`
     not awaited to completion) and `_GatheringFuture exception was never retrieved` (the 2 s
     cancel-gather); also tune the 2 s background-task cancellation. Cosmetic — the process exits
     fine on SIGTERM today.
   - **Device auto-reconnect/retry** for devices that failed setup (kept registered as
     disconnected) — so an off-at-boot eMotiva becomes controllable once it powers on, without a
     restart. (Follow-up to keep-registered.)
   - **Apple TV driver hygiene:** dead `device_update` / `device_error` methods (not part of any
     registered pyatv listener); the app-list fetch logs at ERROR + writes `state.error` when the
     device is merely asleep — defer the fetch until the device is awake (ties to §15 tvOS
     "Who's watching?").
   - **WB virtual device offline on shutdown.** Only *scenario* WB devices are torn down at
     bootstrap shutdown; regular-device WB virtual devices keep `meta/available=1` on the broker
     after the bridge stops, so their cards look live in the WB UI. Wire regular-device WB cleanup
     (mark `available=0`) into bootstrap shutdown. (Deferred companion to the empty-retained-value
     fix, 2026-05-22.)

7. **Scenario ↔ Wirenboard integration (DESIGN DISCUSSION — decide before re-enabling).** As of
   2026-05-22, publishing each scenario as its own WB virtual device (`type=scenario`,
   `/devices/movie_*`) is **disabled** (bootstrap no longer calls
   `setup_wb_emulation_for_all_scenarios`; the 4 retained scenario WB devices were cleared from the
   broker). The previous model is under review — it clutters the WB device list, conflates a
   "scenario" with a "device," and its control semantics (a control per scenario? activate/
   deactivate?) were never clearly defined. **Decide how scenarios should integrate with
   Wirenboard**, considering at least:
   - **(a) No WB representation** — scenarios live only in the bridge API + the (future Layer 3) UI;
     Wirenboard sees only the underlying devices.
   - **(b) A single "Scenario Manager" WB device** — one virtual device with an enum/selector
     control (current scenario) + activate/deactivate, instead of one device per scenario.
   - **(c) One WB device per scenario** (the disabled approach) — only if the semantics (controls,
     activation, state feedback, manual-step surfacing) are properly defined.
   - **(d) Wirenboard scenes/rules** — map scenarios onto WB's native scene/rule mechanism.
   Tie-in: this overlaps Layer 3 runtime rendering and the manual-steps surfacing. The reconciler
   itself does not depend on any WB scenario representation (scenarios activate via the API), so
   this can be decided independently of the reconciler work.

---

## 5. Open Questions (to be decided before acting)

*Use this section to capture decisions as we discuss. Each answered question will inform revisions above.*

- [ ] **Are we keeping the project on ARMv7 / Wirenboard exclusively, or do we want a dev path on amd64 too?** Affects #2 (test target arch), #7 (multi-arch GHCR tags), #11.
- [ ] **Is the Wirenboard the only deployment target, or do we want to deploy to a separate Linux box and talk to the WB controller over MQTT?** Affects the urgency of items #3, #4 (hardcoded IPs).
- [ ] **Is the long-term direction one repo or two?** If "one," do #3 anyway (OpenAPI contract) and then merge — much cheaper post-contract. If "two," do #3 for sure, and the contract is the *point*.
- [ ] **Are there device drivers planned that aren't shipped yet (Roborock, Apple TV app launching, IR learning UI from the old TODO)?** Affects whether §1.2 is the final list or a checkpoint. *(Miele dropped 2026-05-20 — repeated integration attempts failed, `asyncmiele` dependency removed. SprutHub dropped 2026-05-20 — see §5.1.)*
- [ ] **Is `device_category` going to drive real behavior soon?** If yes — what differs between `device` and `appliance`? If not — should we even ship the enum now, or wait until we know what it gates?
- [ ] **Do we also want to move to runtime-driven UI rendering (Codegen Alternatives — Option 2)?** Eliminates `.gen.tsx` codegen entirely; UI fetches a per-device manifest from the backend and renders dynamically. Strong industry-practice alignment (Home Assistant / ioBroker pattern). ~2–3 day refactor. Default position: defer until after #3.5 ships and we feel actual pain that justifies it.
- [ ] **How should button/action placement be made explicit/contract-based instead of relying on config command order?** See item #10. The current implicit convention works (verified unchanged by the P1 work) but the user explicitly dislikes layout depending on undocumented config ordering. Decide between: explicit per-action `slot`/`order` fields, a backend-owned layout manifest (couples naturally with Option 2 above), or command annotations. This question and the Option-2 question are related — a runtime layout manifest could subsume both.
- [ ] _Add others as we discuss._

### 5.1 Backlog carried over from the old TODO

These were the only **unfinished** items in `docs/TODO.md` when it was archived to `docs/history/phase1-2.md` (2026-05-20). Kept here so live work is tracked in one place; Roborock is already covered by the planned-drivers question above.

- [ ] **Transition-aware manual notes (load-bearing — don't drop)** — surface a topology **manual node's** instruction (e.g. Dodocus RCA hub → "set the hub to LD/VHS") **only when that link activates** in a scenario transition. Activation-time: the reconciler diffs active links and emits the bound note. **Required for `movie_ld`/`movie_vhs` to have audio** — deferred to the reconciler/activation work, NOT the scenario page build. Decision recorded: `scenario_system_redesign.md` §13.2 + `ui_backend_contract.md` "Manual instructions". (Baseline static `manual_instructions` ship with the scenario page from the definition — no manifest change.)
- [ ] **Apple TV app launching** — `Запуск приложений на AppleTV`.
- [ ] **Re-verify the Revox reel-to-reel after the Wirenboard refactor** — `Проверить катушечник после рефакторинга Варенборда`. Device tests were rewritten in the hexagonal pass, but on-hardware behaviour is unconfirmed.
- **Voice control (Yandex Alisa) — out of scope here.** SprutHub was a stopgap and is **dropped** (2026-05-20). The plan is to rely on **Wirenboard's future native Alisa bridge**; because this system already exposes every foreign device as a WB virtual device, those devices become voice-controllable for free once that bridge ships. (The two former SprutHub backlog items are retired.)
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
  - **Step C DONE** (GSD-seed docs): ✅ **CONTRACT** (`docs/ui_backend_contract.md`, `50e94b0`; UI pointer `f4d0e7b`); ✅ **ARCHITECTURE** (`docs/architecture.md`, `a2456bc`); ✅ **PROJECT vision** (`docs/project.md`, `ef4421e`); ✅ **CONVENTIONS** (`docs/conventions.md`, `b1f4543`); ✅ **ADRs 0001–0005** (`docs/adr/`, `531a5bb`). **Step D DONE** — see next entry.
- **2026-05-20** — Vision-gathering surfaced two items folded into the plan: **P0.5 #12** (scenarios are broken — top functional priority) and a revised "multi-arch" note (WB8+/arm64 is the planned hardware trajectory, so an arm64 image will be needed). SprutHub dropped; Yandex Alisa delegated to Wirenboard's future native bridge.
- **2026-05-20** — **Completed P2.6 #11 Step D — GSD is now bootstrapped** (`.planning/` tracked, backend-primary). Three commits:
  - **D.1 `/gsd-config`** (`b931430`): balanced profile, branching off, `commit_docs=true`, `auto_advance=false`. Found that `/gsd-config` can't create `.planning/` in this SDK version (`config-ensure-section`/`config-set` need a pre-existing file) — bootstrapped via `gsd-sdk query config-new-project`. The Step D runbook was corrected to note this ordering.
  - **D.2 `/gsd-map-codebase`** (`4223f39`): 4 parallel mapper agents wrote 7 docs to `.planning/codebase/` (STACK, INTEGRATIONS, ARCHITECTURE, STRUCTURE, CONVENTIONS, TESTING, CONCERNS; 1720 lines).
  - **D.3 `/gsd-ingest-docs`** (mode=new, `98664f3`): curated 10-doc manifest (5 ADR + ui_backend_contract SPEC + project/action_plan PRD + architecture/conventions DOC) → classifier×10 → synthesizer → roadmapper. 0 conflicts. Generated `.planning/{PROJECT,REQUIREMENTS,ROADMAP,STATE}.md` + `intel/`. ROADMAP = **6 phases (4 active + 2 deferred)**: 1 Fix Scenario Layer · 2 Button-Placement Contract · 3 CI Quality Gates · 4 Planned Device Features · 5 Ops/GHCR (deferred) · 6 arm64 for WB8+ (deferred). P1/P2 recorded as completed context, not phases. Subsystem specs (`docs/scenarios/*` etc.) deliberately not ingested.
- **2026-05-20** — **Shipped a dependency-reproducibility-hardening pass** (ran as GSD "Phase 1", inserted ahead of the scenario fix). Commits `6d75760`, `4282e2c`, `321e391`, `3461289`, `10c0c0c`, `6419b09`. The durable results (independent of GSD):
  - **`openhomedevice`**: kept the fork (`droman42/openhomedevice`) but moved the `[tool.uv.sources]` entry from the moving `branch=remove-lxml-dependency` to the immutable `rev=6e862a1022f59a21c57c501dcf040f81d12ebfaf`. Upstream dropped `lxml` on `main` but has **not** released it; PyPI `openhomedevice==2.3.1` still forces `lxml` → would break ARMv7. **Migration trigger:** switch to the official PyPI release once it ships lxml-free.
  - **`pyatv`**: migrated from a pinned git commit to PyPI `pyatv==0.17.0` (the protobuf-contradiction fix from the old commit shipped in 0.16.1; driver imports unchanged). Git source removed.
  - **Upper bounds** added to all 17 direct PyPI deps (`httpx`/`requests` were unconstrained). Side effect: `paho-mqtt<2` cascaded **aiomqtt 2.3.2 → 2.0.1** (paho 2.x→1.x). Full suite green (236 pass / 0 fail) — but the MQTT stack is now older; **verify on real Wirenboard hardware** when convenient.
  - Added `tests/test_dependency_pins.py` (7 pin-guard tests), `docs/maintenance/dependency-recovery.md`, and **ADR 0006** (dependency-pinning policy). `uv.lock` is the pin-of-record.
- **2026-05-20** — **Dropped GSD.** After completing the dependency pass via the full GSD loop (discuss→research→plan→plan-check→execute→verify), removed GSD: **too slow for the value on a solo project** — every phase spawns ~7 sub-agents and GSD had installed 10 global hooks that ran on *every* tool call in *every* Claude Code session. Kept all the deliverables above (they're plain code/docs). Removed `.planning/` (the GSD project state) and the global GSD install (hooks, skills, agents, `gsd-sdk` CLI). The roadmap intent survives in the P-sections of this doc; future work proceeds without GSD. **`docs/adr/0006` and `docs/maintenance/dependency-recovery.md` were authored during the GSD pass but are kept as normal project docs.**
- **2026-05-21** — **Scenario layer rebuilt (P0.5 #12)** on branch `feat/scenario-redesign` (10 commits, **not merged**; full suite 270). Designed and implemented the Harmony-model redesign end to end:
  - **Design docs:** `docs/scenarios/scenario_system_redesign.md` (Layers 0/1/2/R + §16 capability maps + §15 tvOS note), the "Layout Manifest & Runtime Rendering" section of `docs/ui_backend_contract.md` (Layer 3 — runtime page construction replaces build-time `.gen.tsx`; subsumes P2.5 #10 + Codegen Option 2), and `docs/monorepo_migration_plan.md` (P3 #9, Phase 2).
  - **Build order decided = B:** backend scenario fix (current repos) → monorepo (Phase 2) → Layer 3 (Phase 3). Branching: one feature branch per phase, merged between phases (the monorepo step rewrites history, so no branch may straddle it).
  - **Implemented:** Layer 0 topology (`config/topology.json` + `infrastructure/topology/`); Layer 1 capability maps (hot-fixable JSON under `config/capabilities/{classes,devices}/` + `infrastructure/capabilities/`, attached at bootstrap); optimistic `WirenboardIRState.input`; Layer R reconciler (`infrastructure/scenarios/reconciler.py`: resolve→diff→translate→order→execute + teardown) wired into `ScenarioManager` behind `WB_SCENARIO_RECONCILER`. **All four scenarios migrated to thin** `source/display/audio`. Manual steps (Dodocus) surfaced via `ScenarioResponse.manual_steps` + SSE. Fixes RC1/RC2/RC3 (mock-verified). ~45 new tests.
  - **Remaining for P0.5 #12 = hardware verification only** (gating/delay tuning, ordering/ARC, Dodocus hub, tvOS who's-watching). UI follow-ups (display `manual_steps`; re-run scenario codegen against thin configs) land with Layer 3. Full as-built record + caveats: `docs/scenarios/scenario_redesign_progress.md`.
- **2026-05-22** — **Phase 1 hardware-verified + merged to `main`; Phase 2 (monorepo) executed end-to-end.**
  - **Hardware verification (Phase 1):** clean boot on the live system (all 13 devices, 4 thin scenarios, topology + capability maps). Fixed the AppleTV/pyatv 0.17.0 listener (`eaecb7c`); shipped a **lifecycle-robustness cluster** (non-fatal `load_scenarios` = Bug 2; keep failed-setup devices registered; hardware-transparent shutdown + correct optimistic-assumed-state persistence); fixed **four hardware-only IR / WB-virtual-device bugs** via the amp test (`result.success` on a dict; double IR blast on the API path; broken `handle_message` override that killed WB-UI control; empty-retained value hiding WB controls). Stopped publishing scenarios as WB devices (pending design — P4 #7). kitchen_hood failure diagnosed as a hung device, not a regression. Full record: `scenario_redesign_progress.md` §1a.
  - **Phase 1 merged to `main`** (fast-forward); `pre-monorepo` recovery tags pushed on both repos.
  - **Phase 2 monorepo COMPLETE** (increments 1-7, `monorepo_migration_plan.md` §4): backend → `backend/` (git mv, native history); UI grafted → `ui/` (git-filter-repo, full 83-commit history); top-level peers `wb-rules/` + `ops/`; cross-cutting `docs/` (+ consolidated `docs/archive/` from the staleness sweep + `docs/device_setup/`); **one unified CI** builds both ARM images **green**; deploy (`ops/manage_docker.sh` + a sample config) repointed so both images come from the single repo; old `droman42/wb-mqtt-ui` **archived** read-only.
  - **Interim CI gating:** the slow QEMU arm/v7 image builds (~14 min for the UI) are gated to **manual-only** (`workflow_dispatch`) for the heavy-iteration period; fast checks (backend tests + UI codegen/typecheck/lint) run on every push. Build images on demand: `gh workflow run "Build ARM Docker Images (backend + ui)"`. Revert = delete the two `if:` lines.
  - **Backlog noted:** UI image build is slow purely from arm/v7 *emulation* of the Node build (863s) → future fix = build the JS on amd64 + assemble only the arm nginx layer (or arm runners). Plus §3b (root README authoring; wb-rules GitHub→WB deploy) and a fuller `ui/docs/page_instructions.md` Python-residue cleanup.
  - **Post-monorepo doc-staleness — found + FIXED in the 2026-05-22 wrap-up audit:** rewrote `project.md`, `conventions.md`, `ui_backend_contract.md`, and `architecture.md` to the monorepo (UI reads `../backend`; one layout) and added dated monorepo-update notes to ADR-0001 + ADR-0003 (decisions unchanged). **Still pending:** pin a sqlite-capable Python (`backend/.python-version` = 3.11.12) — the local `/usr/local/python3.11.4` lacks `_sqlite3`.
  - **Remaining (Phase 3 / deferred):** Layer 3 runtime rendering; the deferred **full scenario-reconciler hardware test** (resync the amp's drifted optimistic state first); verify the aiomqtt 2.0.1 downgrade on real WB hardware. **Deploy host action:** set the WB's `docker_manager_config.json` ui repo → `droman42/wb-mqtt-bridge`.
- **2026-05-23** — **Phase 3 prep: groups-vs-capabilities judgement, dormant-command design, and Alisa-bridge research.**
  - **Groups → capabilities.** Analyzed the device-config `group` concept vs the Layer-1 capability **domains**. Judgement: **capabilities subsume groups** — `group` becomes a transitional fallback, retired once capability coverage is complete. Recorded in `scenario_system_redesign.md` **§17**: the group→domain map (9/11 collapse 1:1; `gestures` is dead; `noops`/`media` are orphan actions); **dormant-command design** — `exposed: false` on the config command (invisible to UI/WB/HTTP) + a load-time validation rule (every command is `exposed:false` OR capability-backed) + a NEW `execute_action` exposure gate (verified absent today — `base.py:748` dispatches any command), sequenced to flip AFTER full coverage; coverage targets (author maps for `streamer` + `reel_to_reel`; `kitchen_hood` is the only appliance → deferred). Cross-ref added in `ui_backend_contract.md` placement-engine section.
  - **Alisa-bridge research.** Background agent (web blocked in its sandbox) + a main-thread web-verification pass → `docs/research/wb-alice-bridge.md` (web-verified). Verdict: WB's native `wb-mqtt-alice` (release wb-2602) exposes only `on_off`/`color_setting`/`range` (+ `toggle`), has **no `mode`** (AV input switching not voice-expressible), **cannot use `pushbutton` controls**, uses a **manual configurator** (not auto-discovery), and is **cloud-dependent** — so `project.md`'s "voice-controllable *for free* via WB virtual devices" is **falsified**. The one clean win is **publishing scenarios as `switch` controls** ("Алиса, включи кино"), feeding the P4 #7 decision. **PARKED** — revisit only after the scenario migration is fully done, all devices hardware-tested, and the house works end-to-end. Flagged for later: correct the "for free" wording (`project.md` §"Non-goals", `action_plan` P-context) and decide the cloud-dependency vs LAN-only non-goal.

- **2026-05-23 (cont.)** — **Phase 3 (Layer 3) — Step 0 + Step-1 model batch executed.** **Step 0:** layout analysis (zone↔domain taxonomy; config `group` ↔ capability `domain` align 1:1 → groups-retirement safe) → `docs/scenarios/layer3_step0_layout_analysis.md`; authored capability maps for `reel_to_reel` (playback) + `streamer` (input/volume/playback, then power); froze the fidelity oracle → `docs/scenarios/layer3_oracle/*.json`. **Step-1 model batch:** added `Capability.reconcile` + widened `on_value` to `str|bool|int` + `BaseCommandConfig.exposed`; reconciler skips `reconcile:false`; completed `streamer` power (feedback on the bool `connected`) + `upscaler` power (`reconcile:false` — manual page power, reconciler still auto-powers it) + tagged 5 dormant commands `exposed:false`; added the `execute_action` exposure gate + load-time `validate_command_exposure` (drift guard = **0 violations** → full capability coverage of in-scope devices). 279 backend tests pass. **Next:** the `LayoutManifest` Pydantic + domain→zone placement engine + `GET /devices/{id}/layout` (reproduce the oracle), then Steps 2-4 (UI renderer → rollout → cutover).

- **2026-05-23 (cont. 2)** — **Phase 3 Step-1 manifest started.** Built the `LayoutManifest` Pydantic model (`presentation/api/layout_manifest.py` — mirrors the UI `RemoteDeviceStructure`, `extra=forbid`; all 13 frozen oracles parse) + the placement-engine **foundation** (`presentation/api/layout_engine.py` `build_device_manifest`: the domain→zone framework + the **power** and **playback** zone builders; `reel_to_reel` + `vhs_player` reproduce their oracle structurally). Ordered-zone control order follows **capability-declaration order** (retires the config-key convention), so the fidelity check compares control *sets* for ordered zones. Icons are placeholders (port the UI IconResolver vs keep UI-side = open). **Remaining (Step 1):** the volume/input/tracks/menu/apps/screen/pointer zone builders → all 13 devices, then `GET /devices/{id}/layout`. 295 backend tests pass.

- **2026-05-23 (cont. 3)** — **Placement engine: volume + input builders.** Added the volume (volumeSlider when the cap has a `set` action, else up/down volumeButtons) and input (api-populated dropdown for a parametric `select`; commands dropdown from `by_value`) zone builders. Engine now covers **4/9 domains** (power, playback, volume, input); **3/13 devices** reproduce their oracle (reel_to_reel, vhs_player, mf_amplifier — `tests/unit/test_layout_engine.py`). Fixed `_is_empty` (empty collections count as empty); the fidelity check compares control *sets* for ordered zones + dropdowns by type/populationMethod/count. **Remaining (Step 1):** tracks/menu/screen/apps/pointer builders + multi-zone power (emotiva special case) + icons decision + the `GET /devices/{id}/layout` endpoint. 296 backend tests pass.

- **2026-05-23 (cont. 4)** — **Phase 3 Step 1 COMPLETE.** Placement engine covers all 9 domains and all 13 devices: the 12 standard devices reproduce their frozen oracle (`backend/tests/unit/test_layout_engine.py`), plus **eMotiva multi-zone power** (zone 1 off/on + zone 2 native `zone2_power` toggle — added the config command + driver `handle_zone2_power_toggle` calling the lib's `power_toggle(ZONE2)` + a cap `toggle` action; the reconciler still drives zones via on/off). `GET /devices/{id}/layout` serves the `LayoutManifest` (in `openapi.json` + UI `api.gen.ts`). **Icons decided — resolved UI-side:** the manifest carries semantics (`actionName`+domain), the UI's `IconResolver` maps to glyphs at render → keeps the manifest **skin-agnostic** (UI can be reskinned with no backend change); the `icon` field is an optional override. So Step 1 = model + engine (13/13) + endpoint + icon decision, all done; full suite 306. **Next: Step 2** — the UI runtime renderer behind a flag (where icon resolution lands).

- **2026-05-24 (cont. 22)** — **Scenario UI core built** (`52b685d`). `RuntimeScenarioPage` renders the composite-remote manifest via `RemoteControlLayout`; `handleAction` routes power_on/off → start/shutdown, every other control → its **role device** (`targetDeviceId`=sourceDeviceId); guard: a non-lifecycle control with no role device warns + skips (never posts to `/devices/{scenario}`). `useScenarioLayout` hook; dropdown `sourceDeviceId` routing in `useInputsData`/`useAppsData`/`useInputSelection`/`useAppLaunching`; **manual-steps** collapsible section at the remote bottom (scenario-only); `App.tsx` flag-routes the 4 `movie_*` scenarios. **Latent bug fixed:** `RemoteControlLayout`'s internal `handleAction` wrapper dropped the `targetDeviceId` 3rd arg (harmless for devices = target is the device; broke scenarios → all controls fell back to `/devices/{scenario}`). Validated end-to-end (Playwright/mock): movie_appletv renders the composite remote; volume→`/devices/mf_amplifier/action`, menu/apps→`/devices/appletv_living/action`, Start/Stop→`/scenario/start`+`/shutdown`. typecheck+lint+`npm run check` green; backend 307. **Remaining scenario-UI polish (state feedback):** the device/scenario **SSE→cache liveness fix** (Layout.tsx:74-80 drops `state_change`), the **lifecycle active-state coloring** (power zone running/stopped from `/scenario/state`), and per-`sourceDeviceId` **volume-slider value** binding (slider scenarios). THEN Step 4 cutover.

- **2026-05-24 (cont. 21)** — **Scenario BACKEND built** (`0aca1d1`). `build_scenario_manifest(scenario_def, device_manager)` — composite remote assembled per role from the role-devices' capabilities (volume/playback/tracks/menu/screen/apps/pointer; **inputs role skipped** = reconciler-derived); every control tagged `sourceDeviceId` (apps/inputs dropdowns get `DropdownConfig.sourceDeviceId`); **power zone = lifecycle** (power_off/power_on, no sourceDeviceId → UI routes to /scenario/shutdown+start); `manual_instructions` carried (new `ManualInstructions` + `LayoutManifest.manualInstructions`, scenario-only); `entityKind="scenario"`. + `GET /scenario/{id}/layout` (exclude_none). **Consistency fix:** `get_scenario_state` now **recomputes** the active scenario's devices from live `device.get_current_state()` (was a frozen snapshot, service.py:542) → can't drift after a manual device-page fix. Regen openapi/api.gen.ts (33 paths). **Validation = conformance** (`tests/unit/test_scenario_layout.py`, not oracle-diff). Backend **307** + UI typecheck/lint green. **Next: scenario UI** (`RuntimeScenarioPage` + per-`sourceDeviceId` state binding + device/scenario SSE→cache liveness + manual-steps bottom section + lifecycle active-state coloring).

- **2026-05-24 (cont. 20)** — **Scenario lifecycle active-state DECIDED → all scenario design questions settled.** The lifecycle power zone reflects running/stopped: one global active scenario (`current_scenario`), so a scenario is "running" iff it's the active one; UI reads `/scenario/state` (existing `useScenarioState`), live via `/events/scenarios` + the SSE→cache fix — **no new backend**. State-aware button coloring; both buttons stay functional (start-on-running = re-reconcile; start-on-stopped = switch). Recorded in `ui_backend_contract.md` "Scenario lifecycle (power zone) active-state". **Scenario scoping COMPLETE** — all four open questions resolved (state binding, virtual_config, manual_instructions placement, lifecycle active-state). Ready to build: `build_scenario_manifest` + `GET /scenario/{id}/layout` + `RuntimeScenarioPage` (+ the `get_scenario_state` recompute, SSE→cache, manual-instructions section). No code yet.

- **2026-05-24 (cont. 19)** — **manual_instructions placement = Option B (in the remote, scenarios-only).** Refines cont. 18: baseline `manual_instructions` are **part of the remote layout**, not a side panel — so they **ride the scenario manifest** (new top-level `manualInstructions?: {startup[],shutdown[]}`; `build_scenario_manifest` copies from the def; **device manifests omit it**). The renderer shows a collapsible "Manual steps" section at the **bottom of `.remote-zones`** (inside the remote box) **only when present** → scenario-only, no space wasted on device pages. **Supersedes** cont. 18's "read from `/scenario/definition`, no manifest change." Recorded in `ui_backend_contract.md` "Manual instructions".

- **2026-05-24 (cont. 18)** — **Scenario design decisions recorded (state binding + manual_instructions); no code yet.** State binding: one source of truth = `device.state` (reconciler diffs live ✓; UI controls fan out per `sourceDeviceId` = Option B + lifecycle→`ScenarioState`; `get_scenario_state` must recompute `devices` from live state — today a frozen snapshot, service.py:542; + wire device/scenario SSE→query cache). virtual_config RESOLVED (web-UI fallback, retired once all scenarios have `/layout`; WB publication separate). **manual_instructions:** baseline static lists shipped with the scenario page from `/scenario/definition/{id}` (no manifest change, collapsible panel); **transition-aware notes (Dodocus RCA hub etc.) DEFERRED to the reconciler/activation work but flagged LOAD-BEARING** (LD/VHS have no audio without them) — tracked as an open checklist item + §13.2 strengthened so it isn't dropped. Recorded in `ui_backend_contract.md` ("Scenarios = composite remote" / "Scenario state binding" / "Manual instructions") + `scenario_system_redesign.md` §13.2. **Still open:** scenario active-state on the power zone (next).

- **2026-05-24 (cont. 17)** — **Step 3 — Auralic on runtime; ALL device pages migrated (12/13)** (`b00c938`). Last device: Auralic (`streamer`), which needed the **slider value-param** generalization — its set-volume native param is `volume` not `level`. `VolumeSliderConfig` gains `valueParam` (from the set action's param_map: Auralic `{level:volume}`→`volume`, else `level`); the slider sends `{[valueParam ?? 'level']: newVolume, ...action.params}`. Enabled `streamer`. **All device_category devices are now on the runtime renderer; only `kitchen_hood` (the sole appliance) is excluded** (bespoke appliance pages out of Layer-3-v1). Validated (Playwright/mock): Auralic power off/on, INPUTS populate + `set_input {input:hdmi1}`, playback, volume slider 0-100. Regen openapi/api.gen.ts; backend 306 + `npm run check` green. **Step 3 device rollout COMPLETE.** Remaining: **scenarios** (`/scenario/{id}/layout` + the ⚠ `/scenario/virtual_config` decision), then **Step 4 cutover** (delete codegen, retire groups, full `specialCases` removal).

- **2026-05-24 (cont. 16)** — **Step 3 — LG + Apple TV + reel_to_reel on runtime (apps B5)** (`fe9a8c1`). **11/13** devices now. Generalized B5 to the **apps domain**: `_apps_dropdown` emits `setParam` (from the launch param_map: LG `{app:app_name}`→`app_name`, else `app` for AppleTV); `useAppLaunching` sends `{[setParam]:appId}` (was hardcoded `app_name` — buggy for AppleTV, which wants `app`). Enabled `living_room_tv`, `children_room_tv`, `appletv_living`, `appletv_children` + `reel_to_reel` (Revox, playback-only, no new work). LG inputs already worked via the generic param_map derivation (`set_input_source`/`source`); both TVs' volume sliders use the U2 valueField. (DropdownConfig already had `setParam` from cont. 14, so no openapi change.) **Validated end-to-end** (Playwright/mock): LG inputs/playback/menu/volume-slider/apps + launch `{app_name:netflix}` + pointer; AppleTV playback/menu/volume/apps + launch `{app:netflix}` + pointer, no INPUTS (pure source); reel_to_reel playback. Backend 306 + `npm run check` green. **Remaining Step 3:** Auralic/streamer (slider value-param generalization — native `volume` not `level`), kitchen_hood (appliance, deferred); then scenarios; then Step 4.

- **2026-05-24 (cont. 15)** — **Fix: eMotiva zone-2 power showed "2" instead of the power glyph** (`9b5dcec`). Found validating eMotiva. Two causes: (1) **IconResolver digit-key bug** — number-pad mappings (`'1'..'9'`) are integer-like keys that JS iterates first, so the partial-substring match matched `'2'` inside `zone2powertoggle` before `'power'` (affected any digit-containing action: aux2, hdmi2, …); fixed by skipping numeric keys in the partial loop (they're exact-match only — a literal `"2"` still resolves via the direct match). (2) the zone-2 **yellow-when-off color** was keyed on buttonType `power-toggle`, but Step 1 changed it to `zone2-power`; `getIconColor` now handles both. The old codegen never hit this — it spread `power_on`'s icon onto the synthesized zone2 action. Validated in-browser (red/yellow/green power glyphs); UI-only, check green.

- **2026-05-24 (cont. 14)** — **Step 3 — eMotiva on runtime (fixed-params flow + B5 + U2)** (`6a2e95f`). Enabled `processor` (eMotiva), the first api/slider device — 6/13 now on the runtime renderer. Surfaced + fixed a **latent param-passing bug**: the renderer sent the param *spec array* (`action.parameters`) as the payload, not values — harmless for the 5 no-param devices already rolled, broken for eMotiva. Three changes: (1) **fixed-params flow** — `ProcessedAction.params` carries the capability action's fixed native params (zone:1 power, zone:2 volume/mute); the engine threads them through the power+volume builders; the renderer sends `action.params` (buttons) + `{ level, ...params }` (slider). (2) **B5** — `DropdownConfig.setParam` (the native value param, from `param_map`: eMotiva `input`, LG `source`); `selectInput` sends `{ [setParam]: value }`. (3) **U2** — slider reads `deviceState[valueField]` (eMotiva `zone2_volume`), deleting `deviceClass==='EMotivaXMC2'`. **Validated end-to-end** (Playwright/mock): power sends `{zone:1}`/`{}`/`{zone:1}`, api inputs populate via `get_available_inputs` + select sends `set_input {input:hdmi2}`, slider renders the dB scale; the 5 rolled devices unaffected. Regen openapi/api.gen.ts; backend 306 + `npm run check` green. **Remaining Step 3:** LG/AppleTV (apps `setParam` generalization) + Auralic (slider value-param, native `volume` not `level`) + reel_to_reel (easy, playback-only) + kitchen_hood (appliance, deferred); then scenarios; then Step 4.

- **2026-05-24 (cont. 13)** — **Phase 3 Step 3 started — runtime render rolled to the easy WirenboardIR devices** (`1ebd5d8`). Enabled the runtime layout flag for `ld_player`, `video`, `vhs_player`, `upscaler` (+ the mf_amplifier pilot) — all WirenboardIR, commands/buttons only, **no api dropdowns** (verified), so none of the deferred hardening (B5/U2) is needed. **Validated render-level** (Playwright, real manifests via the mock): video = two power buttons (off/on) + PLAYBACK (4) + TRACKS (2) + menu nav-cluster; upscaler = power off/on + INPUTS (commands, 2 by_value) + SCREEN (3 aspect buttons) + menu cluster — all the new zone types (playback/tracks/menu/screen) render correctly. typecheck + lint + `npm run check` green. **Remaining in Step 3:** the api/slider devices (eMotiva, LG, AppleTV) — each needs B5 (api-select param) + U2 (slider) before its flag flips — then scenarios (`/scenario/{id}/layout` + the ⚠ `/scenario/virtual_config` decision). Also (cont. 13): fixed **§17.3** in `scenario_system_redesign.md` (`a3fd8d2`) — capability coverage is now MET (streamer/reel_to_reel mapped; drift guard 0 violations), so it no longer gates groups-retirement; only rollout (Step 3) + cutover (Step 4) remain.

- **2026-05-23 (cont. 12)** — **Step-2 hardening commit 2 DONE + re-scoped to mf_amplifier** (`94dd612`). U1: inputs/apps static-vs-fetch now obey the manifest's `populationMethod` (deleted the `specialCases`/`isWirenboardIR`/`usesAppsAPI` reads + hardcoded `get_available_*`); `selectInput`/`launchApp` route by `populationMethod` + use the manifest's `setAction`. **Scope correction (user):** other devices + scenarios are **Step 3**, so the LG/AppleTV **api-select param** (B5) + **eMotiva slider** (U2) + **full `specialCases` removal** (B2/U3) moved there — done per-device as each migrates + is hardware-tested. (Found while scoping: the old api-select hardcodes were *buggy* — LG `set_input` doesn't exist (cap = `set_input_source`/`source`); AppleTV `launch_app` wants `app` not `app_name`. Flagged TODO in `useRemoteControlData.ts`.) **Validated** mf_amplifier via the render mock: INPUTS populate from commands, apps empty/no-fetch, Navigation correctly empty (capability-driven) — matches the build-time page. backend 306 + `npm run check` green. **Step 2 is functionally complete for mf_amplifier** (real-world proof at the next UI deploy — flag defaults to mf_amplifier).

- **2026-05-23 (cont. 11)** — **Step-2 hardening commit 1 DONE (backend contract)** (`d0ca91e`). B1: `GET /devices/{id}/layout` now serves `response_model_exclude_none=True` → empty content fields omitted (not `null`), fixing the spurious-fetch bug + matching the codegen "absent = not present" contract. B3: added `state_field` to the 4 slider devices' volume capability (eMotiva→`zone2_volume`, LG/Auralic/AppleTV→`volume`) + new `valueField` on `VolumeSliderConfig`, emitted by the engine — **snake_case**, because device state serializes snake_case (no camel alias); the old hardcode read camelCase `zone2Volume` so eMotiva's slider value was silently broken. B4: **no-op** — every slider device already declares its set-volume `range` (eMotiva −96..0, others 0..100), surfaced via the action params. Regenerated `openapi.json` + `api.gen.ts` (VolumeSliderConfig gained `valueField`). Backend 306 + UI typecheck/lint green. **Next:** commit 2 (UI declarative — U1/U2), commit 3 (atomic `specialCases` removal — B2/U3).

- **2026-05-23 (cont. 10)** — **Step 2 visual check found 3 gaps; clean-fix plan agreed (NOT yet executed).** Spun up the dev server (zero-dep mock serving the *real* generated manifest, to avoid colliding with the live system's MQTT `client_id`) + Playwright screenshots of mf_amplifier runtime vs build-time. **Correction to (cont. 9):** the "adapter MATCHES oracle" result was a **false positive** — the frozen `layer3_oracle/*.json` compares distilled structure only; the rendered pages diverged. **3 gaps** (full detail in `ui_backend_contract.md` "Step 2 hardening"): (1) **`specialCases`** — a hardcoded back-channel + literal `deviceClass==='WirenboardIRDevice'` drives inputs/apps static-vs-fetch, ignoring the manifest's `populationMethod`; (2) **null vs undefined** — the manifest emits `appsDropdown: null`, the renderer checks `!== undefined` → false-positive zone that fetches and errors; (3) **empty menu/zones** — *NOT a bug*: capability-driven empty rendering is correct/preferred (user: showing controls for absent functionality is misleading in low light); empty zones stay as labeled `(Empty)` placeholders. **Decided principle:** manifest = complete + declarative + **class-agnostic**; renderer never branches on `deviceClass`/`specialCases`; `populationMethod` is the law. **Clean-fix plan (ALL devices; runtime-render flag stays per-device):** Backend B1 `exclude_none` on `/layout`, B2 drop `special_cases`, B3 volume `state_field`→`valueField`, B4 set-volume `range` via manifest; UI U1 `populationMethod`-driven inputs/apps, U2 volume reads `valueField`+range, U3 remove `specialCases` + the 8 handler emissions; Validation = render-level diff (retire the frozen oracle). **Records updated, not executed** — paused for review.

- **2026-05-23 (cont. 9)** — **Phase 3 Step 2 STARTED — UI runtime renderer behind a flag (mf_amplifier pilot)** (commit `d1da2db`). First consumption of `GET /devices/{id}/layout`: a device page rendered at runtime from the backend manifest via the existing `RemoteControlLayout`, gated per-device. Built: `isRuntimeLayoutEnabled()` allowlist flag in `config/runtime.ts` (`VITE_RUNTIME_LAYOUT_DEVICES`/`window.RUNTIME_CONFIG`; `*`=all, `""`/`none`=off; default pilot = `mf_amplifier`); `useDeviceLayout()` hook (`useApi.ts`, staleTime Infinity); `lib/layoutManifestAdapter.ts` (manifest → `RemoteDeviceStructure`, **resolves icons UI-side** via `IconResolver` since the engine emits `fallback` placeholders — matches the codegen's `selectIconForActionWithLibrary(name,'material')`; clones to avoid mutating the query cache; stubs the unused `stateInterface`); `components/RuntimeDevicePage.tsx` (replicates the `.gen.tsx` scaffolding, **falls back to the generated page on fetch error**); `app/App.tsx` routes the flagged device to it. Live data flow unchanged (`/state` + `/action` + SSE). **Validated:** the adapter output structurally diffs **MATCH** vs the frozen oracle (`layer3_oracle/mf_amplifier.json`), incl. resolved icons (power→PowerSettingsNew, volume→VolumeUp/Down/Off) and empty-zone flags; typecheck + lint + `npm run check` green. **Remaining for Step 2:** in-browser visual confirm of mf_amplifier against the build-time page (needs a running backend+browser), then Step 3 (roll to more devices → scenarios).

- **2026-05-23 (cont. 8)** — **Doc↔backend sync pass ("backend is king").** Audited the design docs against the shipped capability model (`infrastructure/capabilities/models.py`), `config/capabilities/*`, `config/topology.json`, and `openapi.json`; fixed real drift. `scenario_system_redesign.md`: §4.1 topology example `processor:zone1`→`zone2` (matches config; zone 2 = amplified); §5.2 replaced the non-existent `delays:{after_on_ms,settle_ms}` field with the real `gate:{poll_timeout_ms,delay_ms}`, added `list` + `reconcile` to the example; §5 "Key fields" now documents `gate`, `reconcile`, widened `on_value` (`str|bool|int`), `list`, `zones`; §5.4 rewrote the eMotiva prose to the actual `zones` dict (`ZonePower` per zone) + the Step-1 native zone-2 `toggle`; §16.3 worked map gained the zone-2 `toggle` action. `ui_backend_contract.md`: REST list marks the groups endpoints LEGACY/dead + adds `/devices/{id}/layout`. `action_plan.md`: device-config count `Twelve`→`Thirteen` (+ the Zappiti `video`). Verified residual stale patterns = 0; eMotiva worked-map braces balanced. No code change.

- **2026-05-23 (cont. 7)** — **Verified the Layer-3 plan covers all backend calls (pre-Step-2 audit).** Cross-checked `openapi.json` (32 ops) × the UI client (`useApi.ts` + `useEventSource.ts`) × the plan. Findings + fixes in `ui_backend_contract.md` "Layout Manifest & Runtime Rendering": (1) the manifest sketch was **stale** (draft `entity_id/zones[]/zone_type/state_schema` vs shipped `deviceId/deviceName/deviceClass/remoteZones[]/entityKind/deviceCategory/stateInterface/actionHandlers/specialCases`) → rewrote it to the implemented model; (2) status updated to "Step 0+1 implemented, Step 2 next"; (3) `/scenario/{id}/layout` marked NOT-yet-built (Step 3); (4) added an explicit **backend-call inventory** table mapping every endpoint to its Layer-3 fate — runtime data/control calls (`/devices/{id}/state`, `/action`, SSE `/events/*`, `/config/*`, `/room/*`, `/scenario/*` runtime, `/system`, `/publish`, `/reload`) **KEEP**; `/layout` **ADD**; the **groups** endpoints (`/groups`, `/devices/{id}/groups`, `…/actions`) **RETIRE** (UI hooks are dead — defined, no runtime caller); `/` + `/events/stats` + `/events/test` are unused. (5) Flagged an **⚠ open decision** for Step 3: the scenario **runtime** WB virtual-device controls (`/scenario/virtual_config/*` → `useScenarioVirtualDevice` → `<ScenarioVirtualDeviceControls>`, rendered in `App.tsx`) — does `/scenario/{id}/layout` subsume them, or do they stay a separate widget? The plan only deleted the *build-time* resolver/handler, never addressed this runtime path. No code change.

- **2026-05-23 (cont. 6)** — **UI lint/typecheck tightened before Step 2** (commit `9e90139`). Closed the long-standing "passes locally, fails on GitHub" gap (ESLint wasn't type-aware and didn't extend the standard TS ruleset; `lint`/`typecheck` are separate scripts). Four changes: (A) new **`npm run check`** mirrors the CI ui-validate job exactly (gen → typecheck:all → lint → validate:*); (B) extend `@typescript-eslint/recommended`; (C) un-exclude `IconResolver.ts` + the 2 type files from `tsconfig.json` (the Step-2 icon path was typechecked by nothing; 0 errors when added); (D) **type-aware lint** (`recommended-type-checked` + `parserOptions.project`), scoped to shipped app code (codegen tooling ignored — still in `typecheck:scripts`, deleted at Step 4), keeping the async-correctness rules (no-floating/misused-promises) and disabling the `any`-driven no-unsafe-* noise. Fixed the 22 real issues it surfaced (15 un-awaited promises → `void`, 3 async handlers in JSX attrs → wrapped, 2 `{}`-types → `Record<string,unknown>`, 1 redundant assertion, 1 `.apply` → spread). `npm run check` green end-to-end. No backend change.

- **2026-05-23 (cont. 5)** — **Topology/scenario scope clarified → new P3.6.** User flagged that `config/topology.json` + the 4 `movie_*` scenarios cover the **living-room A/V chain only**; the audio sources (Auralic, Revox) and the children's room (lg_tv_children, appletv_children) have capability maps (device pages render) but **no topology links and no scenarios**. Confirmed this is *not* a Layer-3 dependency (Layer 3 renders off capability maps; topology only feeds the scenario reconciler) and was only implied by P4 acceptance, never scheduled. **Decision: defer to after Phase 3 (Layer 3)** so new scenario pages render at runtime, not via the soon-deleted codegen — captured as **§ P3.6**. Confirmed scope: Music Auralic→amp, Music Revox→amp, + "some more" (children's room likely; full list TBD). Blocked on a wiring interview (which amp input each source uses; children's-room routing). No code change this entry.

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
