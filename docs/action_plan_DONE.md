# Action Plan — Completed Tasks (frozen archive)

**Status:** Frozen archive of completed `action_plan.md` tasks, organized by section. Split out 2026-06-30 (§5.2 #2) per the `single-task-ledger` two-file-split rule: one ledger, **every ID in exactly one file**. A task **moves** here from `action_plan.md` on completion (same change as its journal entry); this file is move-only — never re-edited except to receive a newly completed task. Cross-references by ID (e.g. "P1 #3.5", "§P3.7 #13") resolve across both files. The dated narrative lives in `action_plan_journal.md`; this file holds the task-level completion records.

**Scope of the initial split (2026-06-30):** the seven fully-completed phase bands **P0, P0.5, P1, P2, P2.5, P2.6, P3**. In-flight phases (P3.6, P3.7, P4) stay in `action_plan.md` until they complete or §5.2 #1 defines how to represent a partially-done phase across the two files.

---

## 4. Action Plan — completed phases

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
| 3.5 | **DONE** 2026-05-20 — backend `6bc30fc`, UI `5a71929`. Eliminate the Python AST dependency in UI codegen. Type the backend's `/devices/{id}/persisted_state` endpoint with a discriminated union of state models (`LgTvState`, `EmotivaXMC2State`, …) so they land in `/openapi.json` automatically. Rewrite `wb-mqtt-ui/src/lib/StateTypeGenerator.ts` (the actual Python-spawning logic lives there — `spawn(python3, ['-c', importlib + ast.parse(...)])` — invoked by `src/scripts/generate-device-pages.ts`) to consume the OpenAPI schema instead of spawning a Python subprocess and AST-parsing imported Pydantic classes. Remove `pip install -e ./wb-mqtt-bridge` and Python from the UI Dockerfile. Closes the "silent break on backend rename" failure mode. See `docs/archive/codegen_alternatives.md` (Option 1). | ~1 day |
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
| 10 | **DONE** — subsumed by the **Layer-3 backend layout manifest** (option 2: backend owns placement; served at `/devices/{id}/layout` + `/scenario/{id}/layout`, consumed by `RemoteControlLayout`). The implicit config-order convention is retired — ordered zones follow capability-declaration order. See `ui_backend_contract.md` "Layout Manifest & Runtime Rendering" + §6 cutover (2026-05-24). _Original task:_ **Design a contract-based button/action placement.** Today, *where* a control renders inside its remote zone is governed by an **implicit, undocumented convention**, not a contract — and we want to replace it. Two mechanisms, both verified in code (2026-05-20): (a) **slot zones** (power / volume / nav-cluster / pointer) fill fixed slots by **action-name substring matching** (`ZoneDetection.createPowerButtonsConfig`, `createMenuZone`, `createVolumeZone`, `createPointerZone` — e.g. name contains `off`→left, `on`→right; `up/down/left/right/ok`→D-pad); (b) **array-order zones** (screen vertical stack, playback row, tracks row) render in the order actions appear, which traces back through `deriveGroupsFromConfig` → `processAllGroupActions` to the **key order of `config/devices/*.json` commands**. This is fragile (reordering a config silently moves buttons; renaming/retyping an action can drop it from a slot or land it in the wrong one) and surprising. **Action: discuss options and design an explicit placement contract.** Candidate directions to weigh — (1) explicit per-action `slot`/`position`/`order` fields in the device config; (2) a dedicated **layout manifest** owned by the backend and served/consumed as a contract (aligns with codegen Option 2 — `docs/archive/codegen_alternatives.md`, runtime-driven UI); (3) command-level UI annotations (`x-ui-*`-style). Trade-off: authoring effort vs. determinism + reviewability. Touches both repos. **Design first — not yet scoped for implementation.** | TBD (design) |

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
   (`docs/design/scenarios/*`, `docs/devices/*`, etc.) were intentionally excluded** — read them
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
