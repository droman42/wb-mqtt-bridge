# Action Plan — wb-mqtt-bridge

**Status:** Living master plan. Updated 2026-06-06.
**Scope:** The `wb-mqtt-bridge` **monorepo** (`backend/` + `ui/` + `wb-rules/` + `ops/` + `docs/`). The
UI is no longer a separate repo — it was merged in during Phase 2.

This document captures the project state and a prioritized action plan, revised as we work.

---

## 0. Document map — master-doc convention (recorded 2026-05-25)

**`docs/action_plan.md` (this file) is the master driving document** — the overarching plan plus an
index of the **revision-log journal**. The dated history itself lives in
[`docs/action_plan_journal.md`](action_plan_journal.md) (extracted 2026-06-06 to keep this plan
focused on forward work). **Read the journal first** in any session for context on recent work;
everything else hangs off this file. As of 2026-05-25 the major redesign is delivered and hardware-verified
(scenario reconciler · monorepo · Layer-3 runtime rendering + the build-time-codegen cutover). What
remains is **§P3.6** (topology + round-2 scenarios), **§P3.7** (voice integration + native WB
onboarding — HIGH PRIORITY, agreed 2026-06-06; runs in parallel with the §5.1 rack pass), **§P4**
(final acceptance + the mandatory scenario↔WB design), and the **§5.1** backlog.

Roles of the other docs **now** (they were "driving" during the redesign; they've since settled):
- `docs/ui_backend_contract.md` — **LIVING reference**: the UI↔backend contract + Layer-3 runtime
  rendering; its "Step 4 — cutover (canonical scope)" is the authoritative cutover record. Consult it
  for how the UI consumes the backend.
- `docs/scenarios/scenario_system_redesign.md` — **IMPLEMENTED → as-built spec** for the scenario
  architecture (Layers 0/1/2/R + §17 groups→capabilities). Describes what was built; not driving.
- `docs/scenarios/scenario_redesign_progress.md` — historical session / as-built record.
- `docs/monorepo_migration_plan.md` — DONE → historical.
- `project.md` / `architecture.md` / `conventions.md` / `docs/adr/*` — foundational project docs; the
  eventual master *set* once the plan is exhausted.

**Convention:** the project stays **plan-driven** (this file is master) until §P3.6 + §P4 land; then
it shifts to **architecture-driven** (`project.md` / `architecture.md` / `ui_backend_contract.md` as
the master set), the redesign specs fully retire to history, and a project-wide doc reconciliation
(tracked separately) formalizes the handover. **Until then: this file is master.**

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
| 12 | **DONE** — scenario layer rebuilt (Harmony/reconciler model) + **hardware-verified** 2026-05-22, re-verified at the Layer-3 cutover 2026-05-24 ("no degradation"). Tail: one deferred full-reconciler HW re-test (resync the amp's drifted optimistic state). See §6 (2026-05-21/22/24) + `scenario_redesign_progress.md`. _Original task:_ **Investigate and fix the scenario layer — currently broken.** Per the project vision, the #1 success criterion is "it actually works": every device action + every scenario, end-to-end on real hardware. Device actions mostly work; **scenarios do not** (confirmed by the user 2026-05-20). This is the headline gap between today and "done = my house works", and is distinct from the architecture/docs/GSD track. Scope: reproduce the failure(s), determine whether it's startup/shutdown sequencing, condition evaluation, role-action dispatch, WB-adapter, or state — then fix and verify on hardware. | TBD (investigation first) |

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
| 5 | **DONE** 2026-05-20 — archived `docs/TODO.md` → `docs/history/phase1-2.md` (open items migrated to §5.1); Roborock bullet kept (planned feature, not a false claim). P2 fully done. | 15 min |
| 6 | **DONE** 2026-05-19 — committed as-is in UI `8ab2cfa` as part of the appliance-category feature. The doc accurately describes the current code direction. | 15 min |

### P2.5 — UI architecture (design discussion, then implement)

| # | Task | Effort |
|---|------|--------|
| 10 | **DONE** — subsumed by the **Layer-3 backend layout manifest** (option 2: backend owns placement; served at `/devices/{id}/layout` + `/scenario/{id}/layout`, consumed by `RemoteControlLayout`). The implicit config-order convention is retired — ordered zones follow capability-declaration order. See `ui_backend_contract.md` "Layout Manifest & Runtime Rendering" + §6 cutover (2026-05-24). _Original task:_ **Design a contract-based button/action placement.** Today, *where* a control renders inside its remote zone is governed by an **implicit, undocumented convention**, not a contract — and we want to replace it. Two mechanisms, both verified in code (2026-05-20): (a) **slot zones** (power / volume / nav-cluster / pointer) fill fixed slots by **action-name substring matching** (`ZoneDetection.createPowerButtonsConfig`, `createMenuZone`, `createVolumeZone`, `createPointerZone` — e.g. name contains `off`→left, `on`→right; `up/down/left/right/ok`→D-pad); (b) **array-order zones** (screen vertical stack, playback row, tracks row) render in the order actions appear, which traces back through `deriveGroupsFromConfig` → `processAllGroupActions` to the **key order of `config/devices/*.json` commands**. This is fragile (reordering a config silently moves buttons; renaming/retyping an action can drop it from a slot or land it in the wrong one) and surprising. **Action: discuss options and design an explicit placement contract.** Candidate directions to weigh — (1) explicit per-action `slot`/`position`/`order` fields in the device config; (2) a dedicated **layout manifest** owned by the backend and served/consumed as a contract (aligns with §7 Codegen Option 2, runtime-driven UI); (3) command-level UI annotations (`x-ui-*`-style). Trade-off: authoring effort vs. determinism + reviewability. Touches both repos. **Design first — not yet scoped for implementation.** | TBD (design) |

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
| 7 | **DONE 2026-05-26** — CI pushes images to GHCR (`ghcr.io/droman42/wb-mqtt-bridge` + `wb-mqtt-ui`) with tags `:latest`/`:sha-<short>`/`:vYYYYMMDD-<short>`; auth via the workflow's GITHUB_TOKEN (no PAT). One-time manual flip in repo settings to make packages public. See §6 entry + commit `6a61766`. | ~½ day |
| 8 | **DONE 2026-05-26** — `ops/docker-compose.yml` (host network, mem/cpu limits) + `ops/wb-mqtt-bridge.service` (systemd) + `ops/update.sh` (~10 lines) + `ops/INSTALL.md` (WB-side cutover, recovery, rollback). Retires `ops/manage_docker.sh` (1081 lines) + the docker_manager_config.json PAT. See `fd61c93`. **WB-side cutover gated on the user** at the rack (INSTALL.md walks it). | 2 hours |
| 9 | **DONE** 2026-05-22 — chose **monorepo** (Phase 2 migration: `backend/`+`ui/`+`wb-rules/`+`ops/`+`docs/`; old UI repo archived read-only). See §6 (2026-05-22). | — |

### Explicitly out of scope (for now)
- **Multi-arch builds** — *time-limited* out-of-scope. Deployment is Wirenboard-only, but the planned move to **Wirenboard 8+ (arm64/64-bit)** will require an **arm64** image alongside (or replacing) the current ARMv7 one. Revisit when the WB8+ migration is scheduled. (amd64 stays CI/dev-only — not a deploy target.)
- **Rewriting `manage_docker.sh`** — works fine; touch it only when GHCR lands.

### P3.6 — Topology + scenarios, round 2 (after Layer 3, before P4)

**BUILT 2026-05-25 (mock-validated; pending hardware verification).** Wiring interview done; the four
round-2 **music** scenarios are authored + reconciler-driven (`f1455c6`, `368fbcb`, `59fb661`):

| Scenario | Source | Amp routing | Notes |
|---|---|---|---|
| `music_auralic` | `streamer` (Auralic) | direct → `mf_amplifier:balanced` | controllable; playback on the streamer |
| `music_reel` | `reel_to_reel` (Revox A77) | Dodocus **Reel** → `mf_amplifier:cd` | controllable (IR); Dodocus note auto-surfaces |
| `music_tape` | `b215` (Revox B215) | Dodocus **Tape** → `mf_amplifier:cd` | **passive** manual source; amp volume + "press Play" note |
| `music_turntable` | `kuzma` (Kuzma Stabi S) | → Sugden PA4 → Dodocus **Phono** → `mf_amplifier:cd` | **passive**; amp volume + manual notes (power on Sugden, set hub, cue the record) |

The Dodocus RCA hub is now the central analog selector (5 positions: ld/vhs/reel/tape/phono, all →
amp `cd`). The two passive sources (no driver) are modelled as **manual topology nodes** + a one-line
reconciler change (a manual-node `source` anchors the topology path so the amp input + the hub note
resolve, but isn't itself controlled) — see §6 (2026-05-25). `kitchen_hood` stays appliance-only.

**Remaining:** **hardware verification** of the four (amp powers + selects the right input; Dodocus
manual notes show; Auralic/A77 playback; passive ones show the right manual steps). The **children's
room** (children_room_tv + appletv_children) was **deferred by the user** (skipped this round) — a
possible round-3.

### P3.7 — Voice integration & native WB onboarding (HIGH PRIORITY — agreed 2026-06-06)

**Driving doc:** `docs/voice_integration_contract_draft.md` (AGREED bridge ↔ Irene contract).
Sister-project counterpart: `wb-mqtt-voice/docs/design/mqtt_integration.md` §10 (Irene's ARCH-8,
**blocked on this**).

**Strategic shift.** The bridge becomes the **single authoritative device catalog + actuation
backend for the whole house** — native Wirenboard gear *and* the AV devices it already bridges.
wb-rules retains all rule/automation logic on the controller (unchanged); the bridge MIRRORS
native control state by subscribing to MQTT value topics. Two writers (bridge + wb-rules), one
truth (the broker). The contract has three pillars:

- **A. Canonical action endpoint** — `POST /devices/{id}/canonical {capability, action, params}`,
  thin façade over `perform_action` via the existing capability map. 6-code structured error enum
  (HTTP-mirrored); synchronous with a **500 ms** default value-topic-echo timeout; subscribes to
  `wb-mqtt-serial`'s per-device error topic for deterministic offline detection.
- **B. Voice-friendly catalog read** — `GET /system/catalog` (neutral, not voice-specific), flat
  capability-shaped projection of devices + rooms; **all locales** for both rooms and devices;
  sensors as ONE `sensor` capability with read-only `fields`; **one device, one room** (whole-house
  controls like "выключи свет везде" resolved as a SINGLE canonical call against an aggregate
  device in `global` — e.g. `all_lights` — NOT by Irene iterating rooms; the bridge ships the
  aggregate devices the supported voice command set needs);
  refresh nudge via retained `bridge/catalog/version` (content hash).
- **C. Native WB onboarding** — generic **data-driven WB-passthrough driver** in
  `infrastructure/devices/wb_passthrough/`; explicit param types per command (no
  `meta/type` introspection); composite payloads (RGB, HVAC) handled **inside** the driver via
  typed `state_topics` metadata + `payload_template` (folded into #19; **no separate
  adapter layer**); `global` is a regular room holding whole-house aggregate devices; loop
  guard on the state-sync chokepoint (no WB-publish callback for passthrough devices).

**Vertical slice first** — prove the whole stack against one live voice command before bulk
onboarding:

| # | Task | Effort |
|---|------|--------|
| 13 | **DONE 2026-06-06.** Generic WB-passthrough driver (`infrastructure/devices/wb_passthrough/driver.py`): config-driven (one command = one publish; static `value` OR first-param-derived payload with int/bool/float coercion to match WB UI semantics); subscribes per state_topic AND its per-control `meta/error` companion (`r`/`w`/`p` flags drive `state.reachable`); state mirror flows through `update_state` — no direct `self.state.x =` (chokepoint static guard verified). Loop guard: `enable_wb_emulation` defaults to **False** on `WbPassthroughDeviceConfig` so BaseDevice skips `_setup_wb_virtual_device` (no feedback loop). New `room: Optional[str]` field on `BaseDeviceConfig` (default `None`; single-room model — see A1). 15 driver-pattern tests; full suite 417 passed. | DONE |
| 14 | **DONE 2026-06-06.** `backend/config/devices/wb-devices/cabinet/cabinet_spots.json` (first config in the new `wb-devices/<room>/` subtree) declaring `capability_profile: "light_switch"`; new shared profile `backend/config/capabilities/profiles/light_switch.json` (canonical `power.on/off` → native `power_on/power_off`) — every relay-light in the house will reference it (`light_switch`); `backend/config/rooms.json` extended with the `cabinet` entry. `wb_passthrough` entry point registered with the venv. New `tests/unit/test_slice_cabinet_spots.py` (4 tests) + 2 loader tests in `test_capabilities.py` pin Pydantic parse, recursive scanner discovery, profile resolution through `load_capability_map`, AV-path-unchanged regression, and rooms.json shape. Full suite 423 pass. | DONE |
| 15 | **DONE 2026-06-06.** `POST /devices/{id}/canonical` endpoint in `presentation/api/routers/devices.py`; new DTOs in `presentation/api/schemas.py` (`CanonicalActionRequest`/`Response`/`Error`/`ErrorCode` enum). Resolves canonical→native through the device's capability map (class → profile → per-device override; uses the #14 mechanism). 6-code error enum with HTTP-status mirror. Synchronous with a 500 ms wait for the value-topic echo via a one-shot `register_state_change_callback`: synchronous AV calls satisfy it during `perform_action`; WB-passthrough echoes satisfy it as the MQTT subscription mirrors the value back. After the wait, checks `state.reachable` — surfaces `device_unreachable` when a per-control `meta/error` `r` flag flips it (A3). 10 endpoint tests pinning the 6 error codes + the two happy paths (sync + async echo) + the `param_map` rename. Full suite 433 pass. | DONE |
| 16 | **DONE 2026-06-06.** `device_name → names: {ru, en}` schema widening + one-shot migration of the 13 existing AV configs (Pydantic `LocalizedName` model in `domain/devices/config.py`; configs rewritten; runtime DTOs `BaseDeviceState.device_name` + `LayoutManifest.device_name` preserved as flat strings projected from `names.ru` so the UI surface is unchanged; UI's one config-side read fixed in `useDataSync.ts`). 401 backend tests pass; UI typecheck + lint clean. | DONE |
| 17 | **DONE 2026-06-06.** `GET /system/catalog` in `routers/system.py` with the builder in `presentation/api/catalog.py`. Flat capability-shaped projection of devices + rooms (no Layer-3 layout coupling). New DTOs in `schemas.py` (`CatalogRoom`/`CatalogDevice`/`CatalogCapability`/`CatalogAction`/`CatalogResponse`). Rooms come from `RoomManager.list()` verbatim (all locales); devices from `DeviceManager.devices` iteration with capabilities walked from each `CapabilityMap` (class → profile → per-device override; uses #14). Devices + rooms sorted by id before hashing → deterministic `version` (16-hex short SHA-256). Retained `bridge/catalog/version` MQTT topic bumped at the end of `reload_system_task` so Irene's catalog consumer refetches on real change. 9 builder + endpoint tests pinning shape, all-locales, null-room AV devices, version determinism, version-changes-on-content-change, version-independent-of-insertion-order, the live FastAPI route, and the 503 path. Full suite 442 pass. | DONE |
| 18 | **DONE 2026-06-06.** End-to-end physically validated against the live wb-mr6c at slave 51 / K4 in the cabinet. `POST /devices/cabinet_spots/canonical {capability:"power", action:"on"}` → publish `1` → relay clicked → value-topic echo received **5 ms later** → `update_state(mirrored={'power':'1'})` → callback chain fired → **200 OK** with post-state. Surfaced two latent bootstrap/MQTT-framework bugs along the way (subscription wiring; see today's journal). Irene ARCH-8 sign-off remains via the sister project once Irene is on the controller. | DONE |

Slice total: ~3-4 dev days + a rack/Irene verification pass.

**Bulk onboarding** (after the slice proves out):

| # | Task | Effort |
|---|------|--------|
| 19 | **DONE 2026-06-08.** Capability vocab profiles + driver enrichment (folded the former #20 "composition layer"). **6 shared profiles** in `config/capabilities/profiles/`: `dimmable_light`, `rgb_light`, `cover`, `heating_loop`, `hvac`, `sensor_room` (5 fields, motion dropped — no v1 voice use case). **Schema widening**: new `StateTopicSpec(topic, type, encoding?, values?, unit?)` in `infrastructure/config/models.py`; `WbPassthroughDeviceConfig.state_topics: Dict[str, StateTopicSpec]` with a `mode="before"` field_validator normalising bare-string form (slice's `cabinet_spots.json` unchanged); new optional `payload_template` on `WbPassthroughCommandConfig`. New `CapabilityField(name, type, encoding?, values?, unit?, labels?)` in `domain/capabilities/models.py`; `Capability.fields: List[CapabilityField]`; `_shape` validator widened to accept stateful + empty actions + non-empty fields (the pure-sensor shape). **Driver helpers** in `wb_passthrough/driver.py` (~70 LOC): `_compose_payload` calls `payload_template.format(**params)` for composite payloads; `_parse_value` scalar-coerces / enum-validates / template-inverses (`"R;G;B"` → `{r,g,b}` via the new module-level `_parse_template`); `_coerce_mirror` looks up the field's spec, parses, logs on failure (does NOT touch `error_flags` — that's WB-protocol-only). `WbPassthroughState.mirrored` widened to `Dict[str, Any]` so typed values land directly. **Catalog**: new `CatalogField` DTO in `schemas.py`; `_project_capability_actions` walks `cap.fields[]` and emits them with type/encoding/unit/labels. Version hash now bumps when a capability `fields[]` entry is added (sensors becoming visible re-triggers Irene's fetch). **Fix the FieldInfo footgun**: `Capability.fields = Field(default_factory=lambda: [], ...)` — `default_factory=list` would resolve to the FieldInfo of the existing `list` field above via class-body name shadow. **Tests**: 11 new (7 capability profile, 4 catalog), 9 new driver tests (parse template, RGB compose + inverse, scalar coerce, slice bare-string regression, parse-failure log path), 1 slice test pin update. **474 passed** (was 453). Hexagonal LAW clean (domain → no infra/presentation imports). | DONE |
| ~~20~~ | ~~Composition layer above the driver~~ — **folded into #19** (DONE 2026-06-08; driver-side helpers + typed `state_topics` schema cover the RGB/HVAC/sensor cases without a separate adapter layer). | — |
| 21 | **DONE 2026-06-08.** `rooms.json` bootstrap — full sweep of the WB-UI dashboards from A2 findings (`entrance`, `hall`, `shower` for the WB `wc` dashboard per user's home semantics, `bathroom`, `bedroom`, `wardrobe`) plus the new **`global`** room for whole-house aggregate devices (#22). Existing rooms preserved: `living_room` (WB dashboard `livingroom`), `children_room` (WB dashboard `children`), `kitchen`, `cabinet` — kept their legacy symbolic ids per user direction; the WB-dashboard → bridge-room mapping is documented in each entry's `description` for the importer (a structured `wb_dashboard_id` field can land alongside the importer if needed). All 11 rooms now carry **trilingual `ru/en/de`** names (de added to the new rooms alongside the pre-slice rooms that already carried it). Authored by hand (11 entries is small enough; the full WB-config Python importer is deferred to #23 when device configs need it). 8 new tests in `test_rooms_bootstrap.py` pin: full 11-room set, every entry validates as `RoomDefinition`, every room has trilingual names, `global` starts empty, legacy room device memberships preserved, new rooms start empty, WB dashboard ids documented for the mapped rooms. Full suite **482 pass** (was 474). | DONE |
| 22 | **Aggregate devices in `global`** — author the v1 aggregate device configs the supported voice command set needs (`all_lights` first; cross-reference `wb-mqtt-voice` to decide whether `all_blinds` also ships in v1). Each is a normal `WbPassthroughDevice` config with `room: "global"`, `capability_profile: "light_switch"` (or matching profile), and a `commands.power_*` topic that points at a WB virtual control the wb-rules scene listens on. **Controller-side wb-rules fan-out scenes are user tech debt** — out of scope for this bridge work; the bridge only registers the aggregate device. | ~½ day |
| R | **DONE 2026-06-08.** **Room-architecture refactor** (follow-up cleanup from #23 architectural inconsistency). Eliminated rooms.json `devices` duplication: now `device.config.room` (single source of truth) → `BaseDevice.room` (flat attr) → `DevicePort.get_room()` (domain contract) → `RoomManager` derives `room.devices` at load time from `DeviceManager`. **Phase A**: Backfilled `room` on all 13 AV configs (appletv_children → children_room, kitchen_hood → kitchen, others → living_room). **Phase B**: `RoomManager.reload()` now strips JSON-side `devices` arrays and populates `room.devices` from `DeviceManager` via `device.get_room()`; replaces the legacy `_validate_devices_exist` (rooms.json → DeviceManager direction) with a forward `_populate_devices_from_device_manager` (DeviceManager → rooms.json direction) that warns on orphan devices. **Phase C**: `RoomDefinition.devices` widened to `default_factory=list`; dropped 19 `devices` arrays from rooms.json (metadata-only entries now); replaced drift-guard `test_rooms_json_devices_match_wb_passthrough_configs` with forward-direction `test_every_device_config_declares_a_known_room`. **Phase D**: Added abstract `get_room() -> Optional[str]` to `DevicePort` (domain contract, hexagon-clean — no `device.config.room` reach from domain managers), `self.room` flat attr + `get_room()` impl on `BaseDevice` (mirrors the existing `get_id`/`get_name` pattern). **Phase E**: Activated the long-dormant `ScenarioDefinition.room_id` invariant — `ScenarioManager._validate_room_membership()` runs after `load_scenarios()`, walks each scenario's device union (`devices ∪ {source, display, audio} ∪ roles.values()`), asserts each device's `get_room()` matches the scenario's declared `room_id`. **Hard-fail** on mismatch (raises `ScenarioError`) — catches typos, stale references, config drift. All 9 existing scenarios pass cleanly (they all declare `room_id: "living_room"` and reference only living_room devices). Tests: 1 drift-guard removed, 1 forward-direction added, 2 new scenario validation tests, several mocks updated (MockDevice gained `get_room()`, integration test configs gained `room`). Full suite **486 passing** (was 485 at #23 close). Hexagon LAW clean (grep verified zero domain → infra/presentation imports). | DONE |
| 23 | **DONE 2026-06-08.** Bulk device configs — **57 WB-passthrough device configs** across all 10 physical rooms, authored interactively from WB-UI widget JSONs. Per-profile distribution: `light_switch` × 23, `dimmable_light` × 13, `heating_loop` × 9, `cover` × 8, `hvac` × 3, `sensor_room` × 1 (the sauna's wb-msw2_100 pack). Per-room counts: bedroom 11, living_room 11, cabinet 6, children_room 6, shower 6, bathroom 5, kitchen 4, hall 3, entrance 3, wardrobe 2. Three Mitsubishi HVAC configs flagged for `ESP32ManagedDevice` migration when that class is introduced. Most multi-sensor onboarding (`wb-msw-v3_*`) deferred to a future global-room session for firmware-doc review; the sauna's wb-msw2_100 (2 fields only) included opportunistically. **Profile changes accumulated during authoring**: `cover.stop` dropped (no native WB control), `hvac` profile rewritten end-to-end against sister-firmware `mitsubishi2wb` to drop fictional enum fields + add `set_widevane`, `heating_loop.mode` dropped from `fields[]` to mirror `light_switch` pattern. **Catalog enhancement (§P3.7 #19 follow-up)**: `_project_capability_actions` gained `mirrored_field_names: Optional[set[str]]` filter so a device using a profile with N fields but mirroring only K<N of them surfaces only K in the catalog (triggered by the sauna's partial sensor_room mirror). **rooms.json drift-guard test added** that walks every WB-passthrough config and asserts its `device_id` appears in the correct room's `devices` list — caught a silent 19-device drift mid-#23 and now prevents recurrence. **Cabinet roller cover semantic fix**: `dooya_dm35eq_x_*` motors invert position (0=open, 100=closed); open/close action values swapped accordingly. **Subfolder convention correction**: `wb-devices/<room>/` uses bridge room_id (matches rooms.json), NOT the WB-UI dashboard id; action_plan A1 paragraph rewritten mid-session 2 to reflect this. **Live authoring log** at `docs/wb_device_authoring_log.md` captures every per-device decision, accumulated cross-room rules (14 entries), friction observations (7 entries), and automation opportunities (9 entries) — input for any future packaged version of this onboarding flow. Full suite **485 passing** (was 482 at #21 close). Two rooms remain conceptually unfinished: `global` (waiting on #22 aggregates) and most rooms' multi-sensors (waiting on focused WB-MSW firmware review). | DONE |
| 24 | `wb-msw-v3_*` sensor side — decide unified config (IR + `sensor`) vs split entry; implement. | ~½ day |
| 25 | Catalog completeness sweep + bulk end-to-end verification across rooms (including each `global` aggregate device's canonical call landing on the broker, even if its wb-rules backing is still owed). | ~1 day |
| 26 | **Value-label translation layer** for enum-encoded WB controls (proposed 2026-06-09; ready to start when user OKs). Extends the existing `values: List[str]` on `CapabilityField` + `StateTopicSpec` to a richer `List[ValueLabel]` form carrying three layers per entry: **`wire`** (what MQTT publishes, e.g. `"2"`), **`canonical`** (short identifier-safe English name, e.g. `"cool"`), **`labels`** (localized human strings, e.g. `{ru: "Охлаждение", en: "Cool", de: "Kühlen"}`). Driver translates symmetrically (same shape as the `invert` flag): **outbound** action `set_mode(mode="cool")` → look up canonical → publish wire `"2"`; **inbound** mirror echo `"2"` → look up → store `state.mirrored["mode"] = "cool"` (canonical). Catalog emits the full label table — voice (Irene) reads it via catalog autodiscovery + matches user utterances against locale-appropriate labels; UI renders dropdowns labeled per active locale, sends canonical names back. Wire format unchanged — wb-rules + firmware see the same integers they always saw. **Resolves the §2.3 / §2.9 / §2.14 enum-vs-wire mismatch** we'd previously declared unfixable without value translation: with the value table in place we can restore typed `mode` to the catalog (currently dropped from `heating_loop` + `hvac` profile fields[]) with truthful values. **NOT a derived driver class** — translation is a data-shaped concern that recurs across device families (HVAC mode/fan/vane/widevane, heating mode bool, future preset selectors), so it lives in the profile/state_topic schema, not in a `MitsubishiHvacDevice` subclass. `ESP32ManagedDevice` remains separately deferred for ESP32-firmware-specific telemetry (provisioning state, OTA progress, firmware version) that none of the value-table work touches. **UI consumer**: enables a fully React-authored `HvacPanel.tsx` that mirrors the firmware's `/control` page (mode/fan/vane/widevane dropdowns + setpoint input + read-only room temp) — replaces the deferred "embed firmware HTML" idea with a native panel that reads catalog labels and posts canonical actions. **Scope**: schema extension (~30 LOC + tests), driver translation helpers (~30 LOC + tests, same hooks as `_invert_wire_payload` / `_apply_inversion`), HVAC profile + 3 HVAC configs gain value tables, heating_loop.mode optionally restored to a typed field with bool wire/canonical/labels, UI panel (~150 LOC React). Backwards-compat: bare `values: ["a", "b"]` keeps parsing as `[{wire: "a", canonical: "a"}, ...]` with no labels. **Suggested sequencing**: (1) backend schema + driver + catalog (voice immediately benefits via catalog autodiscovery); (2) HVAC config value tables + profile updates; (3) React HvacPanel. Each is a clean self-contained commit. Total ~1.5 day backend + ~½ day UI. | ~2 days |

Bulk total: ~9-11.5 dev days (was ~7-9.5; +2 for #26 value-label layer added 2026-06-09).

**Pre-work findings — A1 (2026-06-06)**

Slice concrete artifacts — ready for #13 (driver) / #14 (config) / #15 (canonical endpoint) to
consume. Test room: **cabinet** (where the user works; observation closes the loop).

Three files to author for the slice:
- `backend/config/devices/wb-devices/cabinet/cabinet_spots.json` — WB-passthrough device
  config (new directory convention, see below); declares `capability_profile: "light_switch"`
- `backend/config/capabilities/profiles/light_switch.json` — shared capability profile (the
  canonical→native map) — written **once** for every relay-light in the house
- `backend/config/rooms.json` — extend with `cabinet`

**Directory convention — `wb-devices/<room>/<device_id>.json`** (settled 2026-06-06;
naming rule refined 2026-06-08). Existing AV configs stay flat at
`backend/config/devices/*.json`. **WB-passthrough configs live in
`backend/config/devices/wb-devices/<room>/<device_id>.json`** — one config file per logical
device, grouped by its (single) room. **A device belongs to exactly one room.** Devices
with no physical room (whole-house aggregate devices — see #22) live in
`backend/config/devices/wb-devices/global/<device_id>.json` and use room id `global`.
**Sub-directory name = the bridge's room_id (matches `rooms.json` exactly), NOT the WB-UI
dashboard id where they differ.** Examples: `wb-devices/living_room/` (bridge id
`living_room`, WB dashboard `livingroom`); `wb-devices/children_room/` (bridge id
`children_room`, WB dashboard `children`); `wb-devices/shower/` (bridge id `shower`, WB
dashboard `wc`); `wb-devices/cabinet/` (both match). Earlier draft of this paragraph said
"use WB-UI dashboard ids" — corrected mid-#23 once the inconsistency surfaced (device_id
prefix, room_id, and subfolder all now use the SAME identifier). Sensors follow the same
layout (e.g. `wb-devices/living_room/living_room_sensors.json`); no separate `sensors/`
subtree. The config scanner (`utils/validation.py`) recurses into subdirectories, so flat
AV configs continue to load unchanged.

**`cabinet_spots.json`** (WB-passthrough driver consumes this):

```json
{
  "device_id": "cabinet_spots",
  "device_class": "WbPassthroughDevice",
  "config_class": "WbPassthroughDeviceConfig",
  "names": {"ru": "Споты", "en": "Spots"},
  "capability_profile": "light_switch",
  "room": "cabinet",
  "commands": {
    "power_on":  {"topic": "/devices/wb-mr6c_51/controls/K4/on", "value": "1"},
    "power_off": {"topic": "/devices/wb-mr6c_51/controls/K4/on", "value": "0"}
  },
  "state_topics": {
    "power": "/devices/wb-mr6c_51/controls/K4"
  }
}
```

No explicit error topic field: per A3 below, errors are per-CONTROL and the WB-passthrough
driver subscribes to `<state_topic>/meta/error` automatically for every state mirror.

**Capability profiles — shared maps for the WB-passthrough family.** A new directory
`config/capabilities/profiles/<profile>.json` holds capability maps shared by many devices
of the same fixture kind. The resolver order is class → **profile** → per-instance override
(profile loaded only when `capability_profile` is set; AV devices set it to `None` and the
path stays byte-for-byte unchanged). Slice 1 uses **`light_switch`** = `power.on/off` →
`power_on/power_off` (the only capability cabinet_spots needs). The catalog of profiles we'll
author over the slice + bulk (matches §P3.7 A2's composite-control shapes):

| Profile | Capabilities | Used by (approx) |
|---|---|---|
| `light_switch` | `power` | wb-mr6c relay channels — ~25 |
| `dimmable_light` | `power` + `brightness` | wb-mdm3 switch+slider pairs — ~10 |
| `rgb_light` | `power` + `brightness` + `color` | wb-mrgbw-d RGB strips — ~5 |
| `cover` | `cover` (open/close/set_position) | dooya curtains — ~10 |
| `heating_loop` | `climate` (mode + setpoint + room-temp) | radiator / floor loops — ~9 |
| `hvac` | full `climate` (mode/fan/vane/setpoint) | hvac_* — 3 |
| `sensor_room` | `sensor` with fields | wb-msw-v3 sensor sides — ~9 |

The 3 HVAC units run on ESP32 and **will** be modeled as **`ESP32ManagedDevice`** — a new
device class (alongside future ESP32 work in this project, see PARKED entry in §5 for the
firmware scaffold). **At v1 ship, `ESP32ManagedDevice` is behaviourally identical to
`WbPassthroughDevice`** (subscribes to value topics, publishes to `/on`, type-coerces via the
profile metadata) — the `hvac` profile drives both. The distinct class exists so the HVAC
units have a stable identity to grow into: future versions will expose **additional
ESP32-specific capabilities to the system, specifically to the UI** (e.g. provisioning state,
OTA progress, NVS-stored identity, sleep/wake telemetry, firmware version) that don't belong
on a generic WB-passthrough device. Decision locked 2026-06-08.

**`rooms.json` additions**:

```json
[
  {"id": "cabinet", "names": {"ru": "Кабинет", "en": "Study"},
   "devices": ["cabinet_spots"]}
]
```

`cabinet` gets a single entry for the slice device. The `global` room holds **aggregate
devices** (e.g. `all_lights`) — one per supported whole-house command; `cabinet_spots` does not
belong there. **Whole-house actions** ("выключи свет везде") are a SINGLE canonical call
against the matching aggregate device in `global`; Irene does NOT iterate rooms. The bridge
config ships each aggregate device; the controller-side wb-rules scene that fans the aggregate
out to the real lights is **user tech debt** (the bridge writes to the aggregate's `/on`
topic, wb-rules handles the per-light fan-out).

**Names: bilingual from day one** (`names: {ru, en}`), per the contract's all-locales rule.
Slice authoring uses ru = WB-UI verbatim, en = natural home-context renderings: `Споты` =
Spots, `Кабинет` = Study. Adjust before #16 (the AV-configs migration) if other en
preferences exist (Office / Spotlights / …).

**Voice command the slice proves**: «включи свет в кабинете» / «включи споты»
(en: "turn on the study lights" / "turn on the spots").

**Validation steps for #18 (e2e at the rack, user observes from the cabinet)**:

1. `POST /devices/cabinet_spots/canonical {capability:"power", action:"on"}` → 200 within
   500 ms with `state: {power: "on"}`.
2. Spots physically on (observable).
3. Bridge subscription receives the value-topic echo on
   `/devices/wb-mr6c_51/controls/K4` → `update_state` runs the persist + SSE callbacks but
   **NOT** the WB-publish callback (loop guard verified by checking the broker for no
   bridge-originated echo back to the same topic).
4. `POST … action:"off"` → reverse, same path.
5. Independent wb-rules write to `/devices/wb-mr6c_51/controls/K4/on` (or the user flipping
   the wall switch if wired) → bridge mirrors the new state without re-publishing.

**Pre-work A1 status: DONE.**

**Pre-work findings — A3 (2026-06-06)**

**WB convention verified on the live broker + against the Wirenboard MQTT-conventions spec
(github.com/wirenboard/conventions).** Errors are **per-control, not per-device**:

- **Topic**: `/devices/{dev}/controls/{ctrl}/meta/error` — retained when present, absent when
  healthy. The slice slave's `wb-mr6c_51/K4` has no `meta/error` topic at all → healthy.
- **Payload**: single-character codes that combine — `r` = read error / device reports an
  error, `w` = write error, `p` = read period miss. Compound payloads are possible (e.g.
  `rw`, `rwp`). Live samples observed: three controls currently flagged `r`
  (`wb-msw2_100/Buzzer`, `dooya_0x0101/Position`, `dooya_0x0102/Position`).
- **Clearing semantics** (per spec): after a successful read, the `r` flag is removed and
  THEN the new good value is published — value-topic and error-flag are kept consistent. The
  `w` flag is removed only after a successful write.
- A **device-level `/devices/{dev}/meta/error`** is also defined by the convention but isn't
  populated on this controller from per-control errors; the per-control topic is the
  authoritative signal we'll subscribe to. The driver subscribes to the device-level topic
  too as a cheap redundant signal.

**Bridge wiring** (refines the §P3.7 pillar-A bullet — same idea, sharper shape):

- The WB-passthrough driver **derives error topics from `state_topics` automatically** — for
  every `state_topic` `/devices/X/controls/Y` the driver subscribes to
  `/devices/X/controls/Y/meta/error`. **No explicit error field in the device config.**
- The driver also subscribes to `/devices/{dev}/meta/error` for each unique device id seen in
  `commands` or `state_topics`.
- Any non-empty payload on a capability's monitoring error topic marks that capability —
  and consequently the device — `device_unreachable` for canonical-endpoint purposes.

**Net config impact**: A1's `cabinet_spots.json` example (above) now drops the
`error_topic` field; the driver does the work.

**Pre-work A3 status: DONE.** All three pre-work items (A1 + A2 + A3) resolved; #13 can
start.

**Pre-work findings — A2 (2026-06-06)**

**WB HomeUI config located**: `/etc/wb-webui.conf` → `/mnt/data/etc/wb-webui.conf` (860 KB
JSON). Top-level keys: `dashboards` (room navigation), `widgets` (top-level widget pool keyed
by id), `defaultDashboardId`. Each dashboard has `id`, Russian `name`, and an array of
widget-id references. Each widget has `cells` — `cell.id = "<wb-device>/<control>"` (maps to
`/devices/<wb-device>/controls/<control>`), `cell.name` is the Russian label (sometimes blank
for the paired slider of a composite control), `cell.type` is the widget kind
(`switch`/`range`/`temperature`/`rgb`/…). Importable rooms (10): `entrance / hall / livingroom
/ kitchen / wc / bathroom / bedroom / children / wardrobe / cabinet`. **Skip** during import:
SVG dashboards (`isSvg: true`), the 3 cross-cutting dashboards (`safe`, `power` = global
scenarios, `av_teaching`), and `*_permit_schedule` cells (wb-rules schedule flags, not device
controls).

**Modeling decision — one logical bridge device per cell, NOT per WB slave.** Cross-room
analysis of 40 unique WB slaves: **15 (38%) serve multiple rooms** — the worst cases serve 5
(`wb-mr6c_51/52`, `wb-mr6cu_31`, `setpoints_floor`, `wb-gpio`), plus `setpoints_radiator` (4),
the dimmers `wb-mdm3_83/87` (3 each), `wb-mr6c_47/58` (3), `setpoints_curtain` (3), and the
RGB dimmers `wb-mrgbw-d-fw3_10/238` (2). This is the install pattern, not an outlier — one
relay module is fanned out to wherever channels are needed. With the **single-room model**
(`room: str`, settled 2026-06-06 — see A1), a per-slave config can't answer "which one room
am I in?" for these slaves. Even single-room slaves often host several distinct logical
things (a dimmer slave = K1 relay-light + Channel 1 dimmer-light; an RGB slave = two paired
Channel/Brightness composite lights). Expected bulk count: **~50–80 logical devices** across
10 rooms, mechanically generated by #21 from the cells (placed at
`backend/config/devices/wb-devices/<room>/<device_id>.json` per the directory convention).

**Composite-control shapes the WB-passthrough driver + capability adapters must handle.**

- **Light: switch + paired brightness slider** — many lights are TWO cells rendered together:
  `<slave>/K<N>` (switch, has the human label) + `<slave>/Channel <N>` (range, no label,
  paired beneath). Examples: children's Споты = `wb-mdm3_87/K3` + `Channel 3`; cabinet
  Подсветка = `wb-mrgbw-d-fw3_238/Channel 2 (R)` + `Channel 2 (R) Brightness`. **Combine into
  one logical device** with `power` (on/off) + `brightness` (range) capabilities — no
  cross-device composition needed; just two-capability mapping in a single config.

- **Heating loop: actuator switch + setpoint slider + room-temp sensor** — cabinet alone has
  THREE such loops (radiator, warm-floor, windowsill heater), each the same shape: e.g.
  radiator = `wb-gpio/EXT3_R3A5` (actuator switch, no label) +
  `setpoints_radiator/cabinet_temp` (setpoint range) + `wb-msw-v3_219/Temperature` (room
  temperature sensor) + `setpoints_radiator/cabinet_permit_schedule` (wb-rules flag —
  **skip**). **Combine into one logical device per loop** with a `climate` capability:
  `set_mode(on/off)` → write the actuator switch; `set_setpoint(t)` → write the setpoint
  range; reads `room_temperature` from the sensor + `current_setpoint` from the setpoint
  cell. Multi-cell write — handled by the WB-passthrough driver's per-command topics (one
  config command per cell, no separate adapter; see #19's `state_topics` typed schema). Three
  logical devices in cabinet Обогрев (radiator, floor1, floor2), not twelve.

- **RGB strip: one cell encoded `"R;G;B"`** — e.g. `wb-mrgbw-d-fw3_*/RGB Strip`. One logical
  device with `power` + `brightness` + `color`; `color.set(r,g,b)` resolves via the
  `rgb_light` profile to a single driver command with `payload_template: "{r};{g};{b}"`;
  incoming echoes parse back into a typed `{r,g,b}` dict via the same template. All
  data-driven, no adapter. (#19 scope.)

- **Cover: single position slider** — `dooya_dm35eq_x_*/Position` (range 0–100). One logical
  device with `cover` capability: `open = set 100`, `close = set 0`, `set_position(pct)`.
  Stop semantics TBD during slice 2 (no obvious WB control for it — re-writing the same
  position is the likely answer).

- **HVAC: many cells, one device** — `hvac_children/*` has 7 cells
  (power / mode / fan / vane / widevane / temperature / room_temperature). One logical
  device, full `climate` capability — the most complex composite; do during bulk after the
  simpler shapes settle.

**Slice device locked**: `wb-mr6c_51/K4 "Споты"` → logical id `cabinet_spots`, room
`cabinet`, capability `power` (on/off only). The user works in the cabinet, so physical
observation closes the verification loop on slice step #18.

**Sequencing.** P3.7 runs in **parallel with the §5.1 rack pass** (different surfaces, no
contention). Settles **before P4** (final acceptance), which then sweeps the larger surface.

**Hexagonal LAW preserved** (`hexagonal-law-for-all-changes`): WB-passthrough driver in
`infrastructure/devices/wb_passthrough/`; capability mappings in `config/capabilities/`; capability
adapters next to the existing reconciler. No domain imports of infrastructure.

**Deferred to v2** (the only thing the contract leaves open): additional whole-house aggregate
devices beyond the v1 set (#22 ships the aggregates the v1 voice command set needs — e.g.
`all_lights`; more group/scene aggregates like `all_blinds`, per-floor groups, named scenes are
added as the voice command set grows, each as another normal device entry in `global` — no new
endpoint).

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
   - **Teardown noise → SUPERSEDED 2026-05-27 evening by §5.1 #8** (full root-cause diagnosis + 2-part fix path). Kept here for historical context; §5.1 #8 is the actionable item. Originally
     classified cosmetic (`Task was destroyed but it is pending` from pyatv `CompanionAPI.
     disconnect` not awaited to completion; `_GatheringFuture exception was never retrieved`
     from the 2 s cancel-gather). **Field-observed during the LG TV HW pass on 2026-05-27**
     while stopping the backend with Ctrl-C: user had to press Ctrl-C **three times**; the
     process hung for **~50 seconds** between the first cancel signal and the eventual force
     exit. Log analysis (`backend/logs/service.log`, 14:13:57 → 14:14:47) shows the **entire
     bootstrap lifespan shutdown phase (`bootstrap.py:285-357`, the code after `yield`) never
     executed** — none of its INFO lines (`"System shutting down..."`, `"Shutting down devices..."`,
     `"Disconnecting MQTT client..."`, `"System shutdown complete"`, etc.) appear. What logged
     instead: uvicorn's signal handler cancelling background tasks directly (SSE generators,
     pymotivaxmc2 dispatcher, MQTT client task), then 50 s silence, then **2 `Unclosed client
     session` aiohttp errors from GC** — almost certainly the 2 pyatv (Apple TV) instances
     whose `CompanionAPI.disconnect` doesn't drain on cancel. So the cluster of issues is:
     (a) lifespan shutdown phase is being **bypassed**, not just made noisy — uvicorn's
     SIGINT handler cancels the lifespan generator without resuming the after-`yield` block;
     (b) pyatv teardown keeps the loop alive for ~50 s before GC; (c) the orchestrated cleanup
     (state-store close, WB virtual-device offline marking, device.shutdown() per device,
     including the LG TV's `_teardown_subscriptions` added in `5a09fd1`) **is never reached**.
     **NOT caused by today's commits** — `_teardown_subscriptions` only runs from inside
     `LgTv.shutdown()` which only runs inside `shutdown_devices()` which is part of the
     bypassed lifespan phase. State integrity preserved (writes are transactional through
     the operating life of the process, not buffered until shutdown). **Workaround at the
     rack today:** `kill -TERM <pid>` (often handled differently by uvicorn) or accept the
     Ctrl-C-x3 dance — no data loss. **When fixing:** (1) register an explicit SIGINT/SIGTERM
     handler in the entry point that drives the lifespan shutdown explicitly before uvicorn's
     cancel cascade; (2) wrap `atv.disconnect()` in `asyncio.wait_for(..., timeout=2.0)` with
     per-device timeout logging; (3) investigate whether the FastAPI/uvicorn version we run
     has the lifespan-cancel-bypass regression that's been reported upstream in uvicorn 0.27+.
     Also tune the 2 s background-task cancellation if needed.
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

7. **Scenario ↔ Wirenboard integration (MANDATORY DESIGN DISCUSSION → clean rebuild).** **UPDATE
   2026-05-24 (Layer-3 WB re-key step 3, `f519605`): the old per-scenario WB virtual-device
   implementation has been DELETED** — `ScenarioWBAdapter`, `ScenarioWBConfig`,
   `setup_wb_emulation_for_all_scenarios` + the scenario MQTT-subscription setup, and the bootstrap/
   router wiring are gone. It was dormant (publishing disabled since 2026-05-22, no caller, no tests)
   and held the last scenario-side `group` reader. Per the user: the old implementation was disliked/
   orphaned, so it's removed and **a clean replacement is now MANDATORY before any scenario↔WB
   feature** — there is currently **NO** scenario representation on Wirenboard at all. Re-decide from
   scratch (the previous model clutters the WB device list and conflates "scenario" with "device";
   its control semantics were never clearly defined), considering at least:
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

- [x] **DONE 2026-05-26 — Transition-aware manual notes (load-bearing).** Backend `79c3588`: `ScenarioState.manual_steps` (single source of truth) populated by `ScenarioManager` on activation, cleared on deactivate/shutdown; dropped the redundant copies from `ScenarioResponse` + SSE event payloads + the `_switch_via_reconciler` return. UI `bd80cc5`: `RemoteControlLayout` new `manualSteps` prop renders a "For this activation" subsection (amber) above the static startup/shutdown notes; the `<details>` auto-opens when transition steps exist; `RuntimeScenarioPage` threads `ScenarioState.manual_steps`, guarded on `lifecycleActive`. New transition-case test (start appletv → switch to ld → Dodocus note appears; deactivate clears; next start is fresh). Phase-2 refinement (only emit notes for newly-activated links — diff-based, not every-activation) intentionally NOT done: over-prompting on every activation is correct for load-bearing notes. **Hardware verification still gated on the user.**
- [ ] **#7 — Per-driver HW verification pass, pre-P3.6 scenarios (IN PROGRESS — `LgTv` + `AppleTVDevice` DONE; `EMotivaXMC2` input redesign DONE + input HW-verified 2026-05-29 [power/volume/zones/scenario pending]; `BroadlinkKitchenHood` DONE 2026-05-29; `WirenboardIRDevice`/mf_amplifier BROKEN 2026-05-29).** Methodology gate added 2026-05-27 after the user's instinct (matches [[mock-tests-miss-driver-bugs]]): scenarios are composites; verifying scenarios first masks driver bugs inside composite flows and makes diagnosis confusing. So verify each of the seven driver classes on hardware **before** the P3.6 scenario pass. **Subsumes §5.1 #3 (A77 re-verify) — A77 is just one row of the pass.** Same shape per driver (and per config instance for the multi-instance ones):
  - **Setup.** Bridge starts cleanly; driver registers with no errors; the WB virtual device appears with `meta/available=1`; the device card shows in the WB UI.
  - **Action set.** Walk the concrete action list (below). State persists across a bridge restart (assumed-state DB does its job).
  - **State read-back.** Any value topic the driver publishes (`/devices/<id>/controls/<x>`) updates within ~1 s of the change.
  - **Error recovery.** Disconnect the device briefly (pull power, drop off Wi-Fi, etc.) → driver re-establishes cleanly on next attempt, no leaked tasks/sockets in the bridge log.

  | Driver | Instance(s) | Action set to walk |
  |---|---|---|
  | `LgTv` (asyncwebostv) | **LG living: DONE 2026-05-27** · LG children: deferred | DONE on the living-room OLED77G1RLA: power on (WoL → connect → 3 subscriptions register cleanly post-`tvpower` URI flip) · volume± + mute (subscription delivers physical-remote deltas via the `volumeStatus` unwrap) · foreground-app transitions (home / launch_app / browser) · `power_state` subscription delivers physical-remote off in ~0.5 s with `reason=remoteKey`, ~45 s before the WebSocket finally closes (audit canary closed) · `current_app` + `input_source` coalesced via `app_id_to_input_id` helper · pointer move + tap-click on the pointer socket. DEFERRED (non-blocking): `children_room_tv` smoke pass (config-only, identical driver — expected to mirror); reconnect-cycle test (TV unplug → reconnect, exercises asyncwebostv 0.3.4 close-callback registry + the discard-old-controls reconnect contract). See §6 entry 2026-05-27. |
  | `EMotivaXMC2` (pymotivaxmc2 0.6.8) | **input redesign DONE + input HW-verified 2026-05-29**; power/volume/zones + scenario pending | Input switched from physical HDMI connectors (`hdmiN`) to **logical sources** (`sourceN` via `select_source` + `get_input_names`) — `hdmiN` did a raw-connector switch (black-rectangle) at the rack; topology `processor:hdmiN`→`sourceN`, reconciler unchanged (data-driven). source1 (ZAPPITI) + source2 (AppleTV) verified clean. Remaining: zone1/zone2 power + independence, volume (+ the ack-reliability + protocol-impossible mute-read-back findings), scenario route. See §6 2026-05-29. |
  | `AppleTVDevice` (pyatv) | **living + children: DONE 2026-05-28** (tvOS 26.5) | DONE on both units: power on/off + clean connect (pyatv git-pinned to master SHA `9177803` for the `TVRCSessionStart` fix — tvOS 26.5 silently drops Companion *query* commands without it; see §6) · app list works · nav (up/down/left/right/select/menu/home) + playback (play/pause/stop/next/prev) via Companion HID · pointer pad: drag→directional gesture + tap→select (dx/dy param fix + capability `click`→`select`) · **volume±: absolute `set_volume` removed** (no `_mcF` Volume flag on tvOS 26.5 — Companion volume is dead), routed through the **WB IR blaster** (living `wb-msw-v3_207` ROM5/6; children `wb-msw-v3_220` ROM1/2); volume UI = up/down buttons, mf_amplifier-style (no slider/mute). app-launch-by-name works; dynamic-launch UX deferred to §5.1 #2. See §6 2026-05-28. |
  | `AuralicDevice` (openhomedevice + IR fallback) | Auralic Altair G1 (**wired LAN**) | **Robustness hardening pass DONE 2026-05-29** (mock-tested; **HW walk still owed**): per-call timeouts, liveness-probe-first poll, **auto-rediscovery** on stale connection (dynamic-port aware), quiet transition logging, `skip(1)`/`skip(-1)` bug fix, None-volume tolerance, isolated metadata, async SSDP discovery. OpenHome confirmed the correct protocol (Auralic has no usable UPnP-AV) — see §6 + [[auralic-streamer-openhome-direction]]. **Remaining (all gated on the HW walk at the rack; wired LAN):** (1) **bench-probe** the unit's real OpenHome services first — sources list, whether a Volume service is present, standby-vs-deep-sleep behaviour — to rule out a plain discovery/connectivity issue; (2) **action walk** — power on/off (IR), play/pause/stop, next (`skip(1)`) / previous (`skip(-1)`), volume±, mute, now-playing read-back; (3) **auto-reconnect cycle** (the headline fix to validate) — reboot or standby→wake the unit and confirm the periodic loop rediscovers the new HTTP port within `reconnect_interval` and state recovers, *without* an IR power-on; (4) **#7 setup/error-recovery** — clean start, WB virtual device `available=1`, state survives a bridge restart, brief disconnect → clean re-establish; (5) **follow-ups contingent on results** — `previous` now works (`skip(-1)`) but is **not exposed** in `streamer.json`/`AuralicDevice.json` (add a Previous button if wanted); if the unit has no Volume service, settle the volume UX; tune `op_timeout`/`reconnect_interval` to observed timings. Pass ⇒ streamer is ready for P3.6 `music_auralic` scenario verification (streamer → `mf_amplifier:balanced`). |
  | `WirenboardIRDevice` (aiomqtt → WB IR) | DVDO, Pioneer LD, Panasonic VHS, **MF amplifier: FIXED 2026-05-29**, Zappiti, Dodocus | per-instance: 2–3 representative actions from the device's configured action set; full coverage isn't needed if a sampled action proves the IR path. **mf_amplifier (Musical Fidelity M6si): root-caused + fixed** — IR was dead because `wb-msw-v3_207` bank 65 was stuck in edit mode (coil `5199+65`=1), which made the blaster return "Slave Device Busy" for *every* Play. Caused by an `ir_restore.py` bug (no edit-exit on a busy commit), **not** firmware. Cleared the lock live (amp responds) and hardened `ir_restore.py` (guaranteed edit-exit + busy-retry + preflight unstick). See §6 2026-05-29. |
  | `RevoxA77ReelToReel` (aiomqtt → WB IR) | A77 | stop / play / ff / rewind / record (gated); covers §5.1 #3 |
  | `BroadlinkKitchenHood` (RF, broadlink) | **kitchen_hood: DONE 2026-05-29 (tested working)** | hood power, fan speed, light on/off (orphan — no live scenario uses it, but verify the driver still works after the hexagonal pass) |

  **Also covered as a side-effect:** the aiomqtt 2.0.1 downgrade HW verify (every IR-via-WB driver row exercises the aiomqtt stack). Pass = ready to go into P3.6 scenario verification with isolated-driver confidence.
- [ ] **Apple TV app launching** — `Запуск приложений на AppleTV`.
- [ ] **~~Re-verify the Revox reel-to-reel after the Wirenboard refactor~~** — superseded by #7 above (A77 is one row of the per-driver pass).
- **Voice control (Yandex Alisa) — out of scope here.** SprutHub was a stopgap and is **dropped** (2026-05-20). The plan is to rely on **Wirenboard's future native Alisa bridge**; because this system already exposes every foreign device as a WB virtual device, those devices become voice-controllable for free once that bridge ships. (The two former SprutHub backlog items are retired.)
- [ ] **IR-code learning page** — capture codes from physical remotes (`Сделать страничку для обучения IR кодам с пультов`).
- [ ] **LG TV `audio_output` API — clean rework of the "press Home" hack + enable a true `watch_tv` (TV speakers only) scenario.** Discovered 2026-05-30: `asyncwebostv.controls.MediaControl` already exposes `set_audio_output(value)` (`ssap://audio/changeSoundOutput`) + subscribable `get_audio_output` (`ssap://audio/getSoundOutput`); valid values per library's `list_audio_output_sources` are `['tv_speaker', 'external_speaker', 'soundbar', 'bt_soundbar', 'tv_external_speaker']` (likely incomplete for newer webOS — `external_arc`, `external_optical`, `bt_headset`, `mobile`, `lineout` exist on some firmware; verify on OLED77G1RLA via `get_audio_output` first). **Architectural implication:** the TV's audio output is an INDEPENDENT axis from its video input — webOS lets you have HDMI 1 on screen while audio routes via ARC to the AVR. The current `tv_on_speakers` "press Home" mechanism (driver translates `set_input_source(arc)` → `handle_home`; commit `e5dffa4`) was correct for its PRIMARY video-side purpose (force TV out of HDMI input mode for the watch-TV-with-amp scenario) but uses the wrong axis. **Clean rework when next at LG TV:** (1) add `state.audio_output` field (subscribable); (2) add `handle_set_audio_output` action; (3) add `audio_output` capability domain with `source_modes` (reuses the symmetric src_port mechanism but on a different capability); (4) topology link's src_port becomes the audio-output value, translated in the driver to the webOS string (`arc` → `external_arc`, `tv_speaker` → `tv_speaker`, etc.). **Enables a clean `watch_tv` scenario** (TV speakers only, all other devices off — discarded today because the press-Home hack didn't fit). **HW verification gates before coding:** (a) exact webOS audio-output value for HDMI ARC on the OLED77G1RLA (call `get_audio_output` while on the current ARC-routing setup); (b) whether explicit ARC audio output is enough for eMotiva ARC engagement without forcing TV to internal mode (i.e., does the precondition observed today — "TV must be in TV mode" — go away if the TV is just explicitly broadcasting on ARC?); (c) whether the eMotiva still needs the power-cycle workaround for ARC engagement, or whether CEC + TV-broadcasting-on-ARC is sufficient; (d) subscription delivery reliability for `get_audio_output`. **No urgency** — current `tv_on_speakers` works for its purpose (still HW-pending anyway). File as a coherent LG-TV cleanup pass.
- [ ] **Per-action `force` flag — UI escape hatch for optimistic-state desync.** Adds a reserved boolean param `force` honored by handlers that contain idempotence guards ("skip if state already at target"). The optimistic-state model is correct overall (see [[state-sync-chokepoint]] + Harmony approach in `docs/scenarios/scenario_system_redesign.md`), but for **IR/RF devices with no feedback channel** the guards can lock the user out of resyncing: if optimistic state says `power=on` but the device is actually off (e.g. someone pressed the physical remote), clicking Power-On on the device page hits the guard at `wirenboard_ir_device/driver.py:235` → returns "already on, skipped" → **no IR sent, no state update** → the desync is unfixable from the UI. **Verified guard inventory** (grepped 2026-05-30, 8 idempotence guards total across 3 drivers):
  | Driver | Guards | Channel | Force value |
  |---|---|---|---|
  | `WirenboardIRDevice` | `power_on` (`:235`), `power_off` (`:270`) | IR, one-way | **HIGH** — only escape from desync trap |
  | `EMotivaXMC2` | `power_on` (`:745`), `power_off` (`:890`, `:914`), `set_input` (`:1079`), `set_volume` (`:1186`) | WebSocket, feedback | LOW — useful when an ack is missed (logged eMotiva issue) |
  | `AuralicDevice` | `power_on` (`:643`) | UPnP, feedback | LOW — feedback re-syncs anyway |

  `Revox A77`, `Broadlink Kitchen Hood`, `LG TV`, `Apple TV` have **zero** idempotence guards. For IR drivers this is structural: input/volume/channel/transport always send (the driver can't probe), so there's nothing to guard against — **`force` is only meaningful for the 2 IR power guards** in practice. **Wiring** (~30 LoC backend, ~50 LoC UI, no protocol change): (1) each guarded handler reads `params.get("force", False)` and skips the guard when truthy — existing `update_state(...)` call afterwards is unchanged; (2) capability map declares `force` on actions that honor it, so the UI only renders the checkbox where it does something; (3) UI adds a transient "Force next command" checkbox on the device-action panel (auto-unchecks after one fire, visually distinct while armed); (4) one regression test per guarded handler asserting force bypasses the skip. **Critical distinction:** force bypasses **idempotence** guards, NEVER **availability** guards (e.g. Auralic `:728` `_deep_sleep_mode and not openhome_device` is a "device unreachable" check, NOT idempotence — must not be force-bypassed; same for any `if not self.client or not self.state.connected` pattern). Convention: a comment-marker or helper like `_should_skip_for_idempotence(...)` at each guard site to make the distinction visible. **Explicit non-goal — no scenario-level `force`.** Considered and rejected: a scenario-activation force flag (bypass `reconciler.py:148/162/228` `already_satisfied`) would fire commands at every device in the scenario, including toggle-code devices (Revox/Pioneer/Panasonic IR) that would flip the wrong way, and devices that were correctly in state that get commanded anyway. Per-action force at the device level is the precision tool; once optimistic state is corrected per-device, the next normal scenario activation works because the reconciler reads fresh `device.get_current_state()`. **What this does NOT fix:** (a) toggle-code IR power (no guard to bypass — the toggle handler at `wirenboard_ir_device/driver.py:206` always sends and just decides which state to claim afterwards; the deeper issue is the state claim, not the send); (b) the underlying optimistic-state fragility — `force` is a user-mediated escape hatch, not feedback. For toggle-code cases, a complementary "set state without acting" affordance (writes `update_state` directly, no IR) would help — separate proposal, not part of this item. Hexagonal-LAW clean (handler-local change + capability flag in infra; no domain touch).
- [ ] **IR ROM backup/restore tooling — cleanup + remaining large-code functional check.** **UPDATE 2026-05-29:** the functional test happened via mf_amplifier (207 banks 17–25) and exposed a real `ir_restore.py` bug — a busy/interrupted commit could leave a bank **stuck in edit mode**, which locks the *whole* blaster's playback (bank 65 was stuck → Modbus exc 06 "Slave Device Busy" on every Play). **Fixed live + `ir_restore.py` hardened** (guaranteed edit-exit, busy-retry `WRITE_RETRIES`, preflight `clear_stuck_edit`; see §6 2026-05-29). Restore *content* is vindicated (ROM bytes + ROM-Size match the backup). **Tooling cleanup DONE 2026-05-29** (see §6) — only the functional *play* test the user owns remains. The toolset is now `wb-rules/{ir,ir_common,ir_backup,ir_restore,ir_verify}.py` + `scp_ir_tools.sh`, fronted by a unified CLI **`ir.py`** (`ir.py backup|restore|verify …`, shared bus flags via argparse subparsers; each module stays standalone-runnable): `ir_common.py` is the shared, **general-purpose** core (register map + `modbus_client` wrapper + codec + jitter-tolerant `compare` + the `bus_window` service-stop context, **no A/V knowledge**); `ir_backup.py` now dumps **every non-empty bank** read from the device itself (was: only banks an A/V config referenced — CSV schema dropped the `referenced_by` column); `ir_verify.py` (promoted out of the deleted `temp/`, folds the one-off `diag_*` scripts) does a read-only jitter-tolerant verify with a first-diff dump on mismatch; `scp_ir_tools.sh` deploys them to `/tmp/ir-tools` (push, optional `pull` of produced CSVs). They back up and re-write WB-MSW v3 IR ROM banks so a firmware upgrade can't lose learned codes — the AppleTV volume IR (`wb-msw-v3_207` ROM5/6 + `wb-msw-v3_220` ROM1/2, §5.1 #7 AppleTV row) rides on this. Restore is **HW-verified clean on 220** (2 banks) **and 218** (14/14) once the verify read gets a 6× spaced retry (`f0213af`; the earlier failures were transient post-commit reads). **207** has **7 persistent mismatches** on its large learned `ld_player`/`vhs` codes (ROM65/66/68/69/70/78/79): the stored copy differs from the backup at **capture-jitter magnitude** (±~3 quanta) and is **stored-side, not corruption** — `diag_chunk.py` proved the first-diff index is invariant to read-chunk size, and these are multi-repeat IR frames that already carry per-repeat jitter in the backup itself. **Decision gated on a functional IR test the user owns** (fire e.g. ROM65 `ld_player:tray` at the real device):
  - **If the functional test FAILS** → back to wb-rules: the jittery banks aren't reproducing usable codes → investigate write fidelity / an alternate write path / re-learn those banks.
  - **If it PASSES** → byte-exact verification is the wrong bar for learned multi-repeat codes → byte-exact was already replaced by the jitter-tolerant `--tol` compare in the cleanup (no further script work). **Cleanup itself is DONE regardless of the play result** (it was the right refactor either way); a *failing* play test would reopen the FAILS branch (write fidelity / re-learn), not the scripts. See [[wb-msw-ir-restore-supported]]; commits `a7d7e5f`/`f2dbfc8`/`b46a8f3`/`f0213af`/`34fd1ee`.
- [x] **#8 — Clean shutdown (SSE drain + pyatv teardown). DONE 2026-05-28 — HW-verified fully clean on a single Ctrl-C.** The diagnosis below was correct, but the fix grew from 2 parts to **4** as each layer came off at the rack: **Part 1** `c3f0305` — SSE generators poll uvicorn's `Server.should_exit` (new `sse_manager._shutdown_signaled()`; `app/main.py` switched to low-level `Config`+`Server` so the live server can be handed to the SSE manager) → 1st Ctrl-C drains the long-lived SSE connections instead of hanging forever. **Part 2** `bfa9614` — pyatv's `AppleTV.close()` is **sync but returns `Set[asyncio.Task]`** (per-protocol cleanup tasks the caller must await); the driver was dropping that set → 2 orphaned aiohttp ClientSessions per shutdown. Now captured + `asyncio.wait_for(asyncio.gather(*tasks), timeout=2.0)` + cancel stragglers on timeout. **Part 3** `1ada043` — bootstrap lifespan-shutdown blanket-cancelled `asyncio.all_tasks()` except the current one, which **includes uvicorn's own serve task** (parked in `lifespan.shutdown()` awaiting our completion); cancelling it produced a `CancelledError` traceback out the top of `asyncio.run` + an orphaned `_GatheringFuture` warning, and prematurely killed the MQTT task before the ordered disconnect. Block removed — the ordered teardown stops every task we own; `asyncio.run` mops up stragglers after the lifespan returns cleanly. **Part 4** `607b544` — uvicorn's `Server.capture_signals` deliberately **re-raises the captured SIGINT** after a graceful shutdown (server.py:326-330) so an embedder sees standard Ctrl-C semantics; the asyncio runner turns that into a `KeyboardInterrupt` out of `server.run()`. uvicorn's CLI relies on click catching it — our console_script `main()` now does the same (try/except `KeyboardInterrupt` → quiet exit). **Verified at the rack:** single Ctrl-C → full bootstrap sequence, both Apple TVs "pyatv cleanup tasks completed cleanly (2 task(s))", "System shutdown complete" → "Application shutdown complete." → "Finished server process", prompt returns immediately, **zero** `Unclosed client session`, **zero** `Exception ignored in: threading`, **zero** trailing traceback. 343 tests pass throughout; hexagonal LAW clean (changes confined to composition root + presentation). *Original diagnosis kept below for the record.* Promoted-and-diagnosed 2026-05-27 evening (subsumes the original P4 #6 "Teardown noise" sub-item — see §6 entry). **Full causal chain confirmed by terminal-traceback evidence during the post-HW-pass shutdown attempt:** SSE generators never respond to a shutdown signal → uvicorn's 1st Ctrl-C "graceful shutdown — waiting for connections to close" hangs forever on the 3 long-lived SSE connections (scenarios/devices/system) → 2nd Ctrl-C raises `KeyboardInterrupt` synchronously via uvicorn's signal handler (`asyncio.runners._on_sigint`, `runners.py:157`) → starlette lifespan is suspended at `await receive()` (waiting for a `lifespan.shutdown` message that never arrives in the queue) → the `@asynccontextmanager`-wrapped lifespan generator gets **`GeneratorExit`** at the `yield` point (NOT `CancelledError` — different exception class; the bridge's `try/except asyncio.CancelledError` at `bootstrap.py:359` cannot catch it) → after-`yield` block (orchestrated shutdown — `device_manager.shutdown_devices()`, `state_store.close()`, etc.) is structurally unreachable → Apple TV's `shutdown()` never runs → pyatv's underlying zeroconf/aiohttp resources are never properly torn down → Python's `threading._shutdown()` blocks indefinitely waiting for pyatv's non-daemon threads to terminate (observed as a **3-minute 2-second silent hang** in this session; the morning session was 50 s — varies with whatever pyatv was holding) → 3rd Ctrl-C interrupts `threading._shutdown()` (visible as `Exception ignored in: <module 'threading'> ... KeyboardInterrupt:` on stderr) → GC dumps **2 `Unclosed client session`** aiohttp warnings (one per AppleTV instance: `appletv_children` + `appletv_living`). The 2 unclosed sessions are the smoking gun — pyatv holds an aiohttp ClientSession per device that's only properly closed inside its `disconnect()` flow, which the lifespan would have triggered. **2-part fix** (estimated ~40 LoC total, 2 small focused commits): **Part 1** — make SSE generators in `presentation/api/sse_manager.py` poll uvicorn's `Server.should_exit` flag (or react to a shared `asyncio.Event` set on shutdown). Effect: 1st Ctrl-C drains the connections cleanly, uvicorn proceeds to send `lifespan.shutdown` via the protocol, after-`yield` block runs as designed, `device_manager.shutdown_devices()` is reached. **Part 2** — wrap pyatv teardown in the Apple TV driver's `shutdown()` with an explicit `await asyncio.wait_for(self.atv.close(), timeout=2.0)` + finally-clear; on timeout, log + return without blocking the rest of the shutdown sequence. Effect: even if pyatv's internal teardown is sluggish, we bound it, and the lifespan's other devices still get their `shutdown()` called. **Verification** (single rack-press test post-fix): single Ctrl-C produces the complete log line sequence `"System shutting down..."` → `"Shutting down SSE connections..."` → `"Cancelling background tasks..."` → `"Found N background tasks to cancel"` → `"Flushing pending persistence before shutdown..."` → `"Preparing device manager for shutdown..."` → `"Shutting down scenario manager..."` → `"Shutting down room manager..."` → `"Disconnecting MQTT client..."` → `"Shutting down devices..."` → `"Closing state persistence connection..."` → `"System shutdown complete"`, the process exits within ~5 s, no `Unclosed client session` errors, no `Exception ignored in: threading`. **Not blocking the per-driver HW pass** — workaround at the rack is `kill -TERM` or accept the 3-Ctrl-C dance (state is preserved either way, see [[state-sync-chokepoint]] and the original 0306898 P4 #6 promotion note).
- [ ] **System-router adapter cleanup — Item A only (Item B DONE 2026-05-26).** Item A: `POST /reload`'s `reload_system_task` constructs + drives a concrete `MQTTClient` inline; extract an application-layer reload service (e.g. `app/reload_service.py`) so the router stays a thin adapter. **Gated on hardware** — touches the live MQTT-reconnect path; can't be safely HW-verified without you at the rack. Item B (response DTO for `/config/system`) done in `73ee8d5` — new presentation `SystemConfigResponse` + nested DTOs; wire shape field-identical; `presentation/api/schemas.py` no longer imports the infra `SystemConfig`.
- [ ] **Dependency refresh — clear the Dependabot noise (88 alerts as of 2026-05-31).** Lockfiles haven't been bumped since the 2025-07 pause; GitHub now reports 1 critical / 28 high / 41 medium / 18 low. Audit (2026-05-31, before the UI image build) showed the headline number is misleading for this deployment: most are transitive duplicates of a few root packages, and almost none are exploitable on a LAN-only Wirenboard with a trusted UI↔backend channel. **Triage breakdown:**
  - **UI lockfile (`ui/package-lock.json`) — bulk of alerts.** Dominated by `axios` (~14 across H/M/L: prototype-pollution gadgets, NO_PROXY bypasses, header injection, DoS) — all need attacker-controlled config merging or hostile proxy config, neither applies (axios calls go to a fixed `apiBaseUrl`). The build-chain cluster (`vite`/`rollup`/`esbuild`/`postcss`/`picomatch`/`yaml`/`js-yaml`/`glob`/`minimatch`/`flatted`/`lodash`/`fast-uri`/`follow-redirects`/`form-data`/`@remix-run/router`/`react-router`) is **build-time only**, never in the deployed container. The 1 critical (`form-data` unsafe-random boundary, CVE-2025-7783) only matters across an attacker boundary — not the case here.
  - **Backend lockfile (`backend/uv.lock`).** `aiohttp` (~13) covers inbound HTTP parsing DoS / header injection — but we use aiohttp as a **CLIENT** (openhomedevice/pyatv/pymotivaxmc2 outbound to LAN devices), not a server, so the inbound surface isn't exposed. `urllib3` (5) is redirect/decompression-bomb stuff — we don't follow cross-origin redirects to untrusted hosts. `starlette` FileResponse Range DoS — we don't serve FileResponse. `black`/`pytest`/`Pygments`/`playwright` are dev tooling. `cryptography`/`pyopenssl` are TLS-tail issues; we're an MQTT client on a private LAN, not a public TLS server.
  - **Net real-world risk for the home deployment: low.** Threat model is "someone on the home LAN behaves maliciously" — almost nobody. Noise, not danger.

  **Plan (one focused PR, no rush):**
  1. **UI side:** `cd ui && npm update axios react-router @remix-run/router` first (kills ~half the high count); then `npm audit fix` for the build-chain tail (verify no major-version breakage); then `npm run typecheck:all && npm run validate:generated-code` and a local `npm run dev` smoke against the rack backend.
  2. **Backend side:** `cd backend && uv lock --upgrade-package aiohttp urllib3 starlette cryptography pyopenssl requests` (the high-value targets); regenerate uv.lock; `pytest -x` for the existing 401 tests; verify openhomedevice/pyatv/pymotivaxmc2 still import cleanly (those are the actual aiohttp consumers).
  3. **Defer:** the build-chain UI deps (vite/rollup/esbuild) — bump only if a real CVE in our actual runtime path appears. Mass-bumping the toolchain risks Vite-major-version churn without security benefit on a LAN UI.
  4. **Hexagonal LAW:** no domain touch, no config touch — pure dep bumps.

  **Gate:** do this on a quiet day, NOT before a hardware verification session (dep bumps add a confounder to whatever you're actually trying to debug at the rack). Re-pull the Dependabot count after the PR to confirm the drop.
- [ ] **PARKED: ESP32 firmware scaffold for the 4 transport-source bridges** (Revox A77 + Revox B215 + Pioneer CLD-D925 + Panasonic NV-FS90). Lives at `ESP32/` (PIO layout: `include/` + `src/` + `docs/`) — single image, identity selected at runtime via NVS + MQTT `/provision`. ~95% shared core (Wi-Fi auto-light-sleep + Wirenboard MQTT + MQTT-triggered `esp_https_ota` + record-arming + reel-motion interlock); 3 drivers cover 4 decks (Pioneer + Panasonic share `driver_ir.cpp` as baseband IR). **2026-05-26: rewritten from the original Arduino scaffold to pure ESP-IDF (C++17, framework=espidf, no Arduino libs); custom dual-OTA partition table (1.5 MB app slots); builds clean end-to-end from `pio run -t fullclean`** (RAM 11.2%, Flash 59.6% of 1.5 MB). Authoritative spec: `ESP32/REQUIREMENTS.md`. Subproject conventions + setup gotchas: `ESP32/CLAUDE.md`. Per-device hardware handoffs: `ESP32/docs/`. Deferred: bench fill-ins (IR codes, B215 frame values, GPIO/timing tuning) and first-light hardware verification, until **"everything works in my home"**. **Not in the active workstream** — do not pull into pre-P4 unless the user reactivates it.

---

## 6. Revision Log

The dated history lives in **[`docs/action_plan_journal.md`](action_plan_journal.md)** — extracted
2026-06-06 to keep this plan focused on forward work. References elsewhere in this plan
("see §6 (2026-XX-XX)") still resolve: they point at that file's dated entries.

**Recent entries** (newest first; full content + earlier entries in the journal):

- 2026-06-09 — **Proposal added: §P3.7 #26 value-label translation layer** — design discussion logged in the task table. Three-layer enum mapping (wire / canonical / labels) on existing `CapabilityField` + `StateTopicSpec`. Same shape as the `invert` flag — symmetric outbound/inbound translation in the driver, no derived class needed. Resolves the enum-vs-wire mismatch we'd shelved across heating_loop / hvac; enables a native React HvacPanel (replaces the deferred "embed firmware HTML" idea). ~2 dev days. **Not started — user thinking overnight, picking up tomorrow.**
- 2026-06-08 — **`invert` extended to bool type** — heating switch inversions (living/children/bedroom on wb-gpio/EXT3_R3A2-4) now use the same flag pattern as covers: configs in natural sense (`mode_on: "1"`), bool state_topic with `invert: true`, driver toggles at the wire. 8 new tests + no_op compare made type-aware (parses target to typed before compare). State.mirrored carries typed `True`/`False` natural-sense. **502 passing** (was 495)
- 2026-06-08 — **`invert` flag on StateTopicSpec** — fixes cabinet rollers' inverted position semantics end-to-end (cover.set_position(25) now correctly means "25% open" regardless of the dooya motor family); driver applies `100-value` symmetrically on outbound publish + inbound mirror; cabinet roller configs reverted to natural-sense open=100/close=0 plus `invert: true` on the position state_topic; 8 new driver tests cover static + param paths + roundtrip + uninverted regression; **495 passing** (was 486)
- 2026-06-08 — **Room-architecture refactor** — eliminated rooms.json `devices` duplication (single source of truth: `device.config.room` → `DevicePort.get_room()` → `RoomManager` derives at load); backfilled `room` on 13 AV configs; added `get_room()` to port + BaseDevice; activated long-dormant scenario room-membership invariant (`ScenarioManager._validate_room_membership` hard-fails on mismatch); all 9 existing scenarios pass; drift-guard replaced with forward-direction check; 486 passing
- 2026-06-08 — §P3.7 #23 DONE — **57 WB-passthrough device configs across all 10 physical rooms** authored interactively from WB-UI widget JSONs; 4 profile cleanups (cover.stop, hvac rewrite, heating_loop.mode, sauna sensor_room partial use); catalog gains state_topics-driven field filtering; drift-guard test catches stale rooms.json; live authoring log captures every decision + automation opportunities for any future packaged version; HVACs flagged for ESP32ManagedDevice migration; multi-sensor backlog deferred; **485 passing** (was 482)
- 2026-06-08 — §P3.7 #21 DONE — `rooms.json` full WB-UI sweep (6 new rooms inc. `shower` for WB `wc`) + `global` for aggregate devices (#22); trilingual `ru/en/de` across all 11 rooms; legacy `living_room`/`children_room` ids preserved per user direction; WB-dashboard mapping in each entry's description (importer deferred to #23); 8 new tests; **482 passing** (was 474)
- 2026-06-08 — §P3.7 #19 DONE — 6 capability profiles authored (motion dropped from sensor_room); typed `state_topics` + `payload_template` + capability `fields[]` schema landed; driver gains type-coerce/compose/inverse-parse helpers (~70 LOC); catalog emits typed field metadata; FieldInfo class-body shadow footgun fixed; **474 tests passing** (was 453); slice configs unchanged
- 2026-06-08 — §P3.7 #20 collapse — composition folds into the WB-passthrough driver via typed `state_topics` + `payload_template` (no separate adapter layer); HVAC class locked as `ESP32ManagedDevice` (v1: behaviourally WB-passthrough; grows UI-facing ESP32 surfaces later); #19 widens to ~1.5 day; bulk total ~7-9.5 days
- 2026-06-07 — §P3.7 plan reconcile — aggregate-device model for `global` (two stale lines fixed; new bulk task #22 for v1 aggregates like `all_lights`; renumber #22-#24→#23-#25; controller-side wb-rules scenes are user tech debt; no code touched)
- 2026-06-06 — §P3.7 #18 cold-start fix — retained-message opt-in per topic (broker's retained "current value" now seeds `state.mirrored` on connect; first `power_off` after restart works; 453 tests pass)
- 2026-06-06 — §P3.7 #18 follow-up #2 — AV-driver instantiation regression + fix + entry-point-signature test (drop `wb_service=` from `device_class(...)` call; 448 tests pass)
- 2026-06-06 — §P3.7 #18 follow-up — idempotency no_op short-circuit (repeat actions return 200, not 503; 447 tests pass)
- 2026-06-06 — §P3.7 slice #18 — DONE; voice integration slice physically validated (5 ms publish→echo round-trip, 200 OK; slice gate crossed)
- 2026-06-06 — §P3.7 #18 first rack run — two-prong subscription wiring bug + fix (bootstrap ordering + `_run_mqtt_client` union-of-handlers; 442 tests pass)
- 2026-06-06 — §P3.7 slice #17 — `GET /system/catalog` DONE (deterministic version hash, retained MQTT nudge on /reload, 9 tests; slice feature-complete on the bridge side)
- 2026-06-06 — §P3.7 slice #15 — canonical action endpoint DONE (6-code error enum, 500 ms echo timeout, 10 tests; Irene unblocked for AV)
- 2026-06-06 — §P3.7 — capability-profile mechanism + `light_switch` profile (cabinet_spots migrated; AV path unchanged; 423 tests pass)
- 2026-06-06 — §P3.7 slice #14 — cabinet_spots wired (device config + capability map + rooms.json entry; 421 tests pass)
- 2026-06-06 — §P3.7 — single-room model + `wb-devices/<room>/` directory convention (contract correction; recursive config scan)
- 2026-06-06 — §P3.7 slice #13 — generic WB-passthrough driver DONE (417 tests pass, loop guard verified)
- 2026-06-06 — §P3.7 slice #16 — device_name → names bilingual migration DONE (401 tests pass, UI clean)
- 2026-06-06 — A3 — wb-mqtt-serial error topic convention nailed (per-control, `r`/`w`/`p`); all pre-work DONE
- 2026-06-06 — A1 — slice artifacts nailed for cabinet_spots (room: cabinet)
- 2026-06-06 — A2 — WB HomeUI config located + composite-control patterns documented
- 2026-06-06 — voice integration contract agreed + new §P3.7 HIGH-PRIORITY phase
- 2026-05-30 — eMotiva rack pass + 2 sibling-library handoffs + LG TV silent-WS-death fix + HDMI ARC scenario
- 2026-05-30 — state-management audit → 2 stale-scenario-state bugs fixed + chokepoint static guard
- 2026-05-29 — Auralic streamer research → robustness hardening pass (OpenHome confirmed)
- 2026-05-29 — IR ROM tooling cleanup (unified `ir.py`, jitter-tolerant verify, `temp/` gone)
- 2026-05-29 — mf_amplifier root-caused (ir_restore.py edit-lock bug fixed live + tool hardened)
- 2026-05-29 — §5.1 #7 eMotiva input → logical-source clean cut + HW-verified
- 2026-05-28 — IR ROM backup/restore HW verification + 207 large-code diagnosis
- 2026-05-28 — §5.1 #7 AppleTVDevice DONE on both units (tvOS 26.5 Companion fix + WB IR for volume)
- 2026-05-28 — pointer-flood fix + LG input fix + CI bump
- 2026-05-28 — §5.1 #8 clean shutdown DONE, HW-verified
- 2026-05-27 — multi (LG TV row DONE, §5.1 #8 shutdown-hang diagnosis, chokepoint Invariants A+B, CI Python pin, asyncwebostv 0.3.0)
- 2026-05-26 — multi (P3 #7+#8 GHCR/compose retiring docker_manager, §5.1 system-router cleanup, §5.1 #1 manual notes)
- 2026-05-25 — P3.6 round-2 music scenarios BUILT (mock-validated)
- 2026-05-25 — Hexagonal-purity pass (`domain/` import-pure)
- Earlier entries (2026-05-19 → 2026-05-22) — initial draft, P0/P1/P2 execution, scenario layer rebuild — in the journal.

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

> **As-built (Layer 3, 2026-05-24).** This is the option we implemented — but the "harder static typing / `unknown`-shaped TS" tradeoff was **avoided**: the manifest is itself an `openapi.json` schema (`LayoutManifest`), so `api.gen.ts` types the renderer's input. Net effect: only `gen:device-pages` dies at cutover; the **REST type contract (`openapi.json` + `api.gen.ts`) survives and becomes more central**. Canonical scope = `ui_backend_contract.md` → "Step 4 — cutover (canonical scope)".

#### Option 3 — Reverse direction: backend owns codegen, UI consumes static manifests

**Mechanism.** Backend grows a CLI subcommand (`wb-bridge generate-manifests`) that walks configured devices and writes `manifests/{device_id}.json`. UI reads those JSON manifests at build time. No Python ever touches the UI build.

**What dies.** Python in the UI builder. The TypeScript-spawning-Python pattern.

**Tradeoff.** Manifests need to live somewhere both repos can reach (UI repo? backend repo published as releases? third "contract" repo?). Operationally awkward across two repos; rhymes with the broader mono-vs-multi-repo question. **Defer until the repo structure is decided.**

#### Option 4 — Drop codegen entirely, fully runtime, with rjsf for parameter dialogs

Like Option 2 plus `react-jsonschema-form` for command-parameter input dialogs. Most commands today are pushbuttons or simple ranges, so rjsf's automation doesn't pay off at our scale. **Skip.**

### 7.5 Recommendation

Adopt **Option 1 now** (P1 #3.5). Re-evaluate **Option 2** after Option 1 ships — once state models are in `/openapi.json`, Option 2 becomes a pure UI-side refactor with no further backend work. Keep **Option 3** in mind only if/when we move to a monorepo. **Skip Option 4** entirely.
