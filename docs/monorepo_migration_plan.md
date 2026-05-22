# Monorepo Migration Plan

- **Status:** **EXECUTED / COMPLETE 2026-05-22** — increments 1-7 done (§4); structure is
  `backend/` + `ui/` + `wb-rules/` + `ops/` + `docs/`, unified CI builds both ARM images green,
  deploy repointed to the single repo, old `droman42/wb-mqtt-ui` **archived** read-only. Both
  histories preserved; `pre-monorepo` recovery tags pushed. Authored 2026-05-20.
- **INTERIM CI gating (2026-05-22):** the slow QEMU arm/v7 image builds (~14 min, UI) are gated to
  **manual-only** (`workflow_dispatch`) for the heavy-iteration period — fast checks run on every
  push; build images with `gh workflow run "Build ARM Docker Images (backend + ui)"`. Revert by
  deleting the two `if:` lines in `.github/workflows/build-arm.yml`.
- **Remaining follow-ups:** fuller `ui/docs/page_instructions.md` Python-residue cleanup; root
  README authoring (§3b); GHCR (#7) + wb-rules GitHub→WB deploy (§3b); **UI image build is slow
  purely from arm/v7 emulation of the Node build (863s)** → optimize by building JS on amd64 +
  assembling only the arm nginx layer (or arm runners). Deploy host: set the WB's
  `docker_manager_config.json` ui repo → `droman42/wb-mqtt-bridge`.
- **When:** **Phase 2** of the scenario redesign — *after* the backend scenario fix
  (Layers 0/1/2/R, done in the current two-repo structure) and *before* Layer 3
  (runtime rendering). See `docs/scenarios/scenario_system_redesign.md` and
  `docs/ui_backend_contract.md` → "Layout Manifest & Runtime Rendering".
- **Why now (and not earlier):** the consolidation is the **vehicle for Layer 3**, the only
  genuinely cross-repo phase (manifest schema ↔ renderer co-evolution, fidelity diffing against
  `.gen.tsx` at matched commits, deleting UI code as backend code lands). Atomic cross-repo commits
  + one CI make that sane. It is *not* needed for the backend-only scenario work, so it doesn't
  block "my house works."

This is action_plan **P3 #9** (unblocked now that P1 is done) and it touches **#7** (GHCR) and
**#8** (compose).

## 0. Guiding principle (decided 2026-05-22)

The **backend is the source of data & functionality truth** — it owns the API contract
(`openapi.json`), device/state models, scenario logic, and capabilities: *what exists and what it
does*. The **UI is the source of visual truth/goals** — layout, placement, look & feel: *how it is
presented*. The **contract (`openapi.json`, plus the future Layer-3 layout manifest) is the
negotiated boundary**: the backend never dictates visual layout (which is exactly what build-time
page codegen wrongly did), and the UI never invents data or behavior. This is *why* Layer 3 moves
rendering to runtime, and it is the invariant Phase 2 must preserve.

Concretely for Phase 2:
- A **contract-sync verification** is the **first step** and a **standing CI gate**: the UI must
  regenerate its API types + run its codegen + type-check/lint cleanly against the *current*
  backend `openapi.json` and configs (incl. the new thin scenarios). This is what catches backend
  API/structure changes that haven't reached the UI (the trigger for this section).
- The monorepo makes that gate single-repo and atomic; Layer 3 then replaces build-time codegen
  with runtime rendering driven by the same contract.

**Contract-sync verification — first run (2026-05-22):** the UI builds clean against the *current*
backend contract. The only drift was the UI's **committed `src/types/api.gen.ts`** snapshot, stale
since 2026-05-20 — it predated the redesign's `ScenarioDefinition` change (`devices`/`roles`/
`startup_sequence`/`shutdown_sequence` went required→optional; thin `source`/`display`/`audio`
added). After `gen:api-types`: `typecheck:all`, the device+scenario codegen (13 devices + **4 thin
`ScenarioDevice` pages**, 100%), `validate:all`, and `lint` all pass — **no UI code changes
needed**. Takeaway for the monorepo: the committed `api.gen.ts` snapshot silently drifts whenever
the backend API changes; in the monorepo it should be **CI-generated (not committed)** like the
other `.gen` artifacts, with the verification above as the CI gate.

---

## 1. Current state (the coupling we're removing)

| Repo | Visibility | Role |
|---|---|---|
| `droman42/wb-mqtt-bridge` | **public** | Backend (FastAPI+MQTT). Owns the contract (`openapi.json`, `config/*`). Also holds `manage_docker.sh` + `docker_manager_config.json` (gitignored). |
| `droman42/wb-mqtt-ui` | (private/sep.) | Frontend (React/Vite). Consumes the contract. |

Concrete cross-repo coupling points (verified 2026-05-20):

1. **UI CI** (`wb-mqtt-ui/.github/workflows/build-arm.yml`) does a **second checkout** of
   `droman42/wb-mqtt-bridge` into `./wb-mqtt-bridge`, then runs
   `gen:device-pages --mode=package --mapping-file=wb-mqtt-bridge/config/device-state-mapping.json`.
2. **UI Dockerfile** copies the backend into the build context:
   `COPY wb-mqtt-bridge/ ./wb-mqtt-bridge/`, and codegen reads
   `wb-mqtt-bridge/config/device-state-mapping.json` + `wb-mqtt-bridge/openapi.json`.
3. **Two CI workflows** (`build-arm.yml` in each repo) producing two artifacts
   (`wb-mqtt-bridge-image` + config archive; `wb-mqtt-ui-image`).
4. **Deploy** (`manage_docker.sh` + `docker_manager_config.json`) maps two `CONTAINER_REPOS`
   (`droman42/wb-mqtt-bridge`, `droman42/wb-mqtt-ui`) and pulls artifacts per-repo via a GitHub
   PAT.

> **Note:** post-Layer-3 the UI build no longer needs backend configs at build time at all (it
> renders from the runtime manifest), so coupling points #1/#2 disappear *anyway*. The monorepo's
> durable win is **atomic commits during the transition**; the build-context simplification is a
> bonus we get immediately.

---

## 2. Target structure

Keep `droman42/wb-mqtt-bridge` as the **monorepo root** (it's public, primary, and owns the
contract). Move each project into a subdir, preserving history:

```
wb-mqtt-bridge/                 (monorepo)
├── backend/                    # FastAPI+MQTT bridge: src tests config openapi.json pyproject uv.lock Dockerfile backend/docs …
│                               #   logs/ + data/ are runtime dirs → gitignored (app + Docker mkdir them)
├── ui/                         # React frontend: src scripts public package.json tsconfig* vite Dockerfile nginx … ui/docs
├── wb-rules/                   # Wirenboard automation rules (deployed to the WB controller) + scp_wb_rules.sh
├── ops/                        # container deploy glue (manage_docker.sh, docker_manager_config.* sample)
├── docs/                       # cross-cutting docs (contract, scenario redesign, action_plan, project, architecture, conventions, adr/, this plan)
│   ├── archive/                #   ALL stale docs from both repos, consolidated
│   └── device_setup/           #   kept device-setup references (e.g. broadlink-device-setup.ipynb)
├── .github/workflows/          # one CI, both images
└── docker-compose.yml          # (optional, with #8)
```

Three deployable components as top-level peers: **backend** (container), **ui** (container),
**wb-rules** (deployed onto the WB controller). Top-level `docs/` holds cross-repo docs; backend-
and UI-specific docs stay under `backend/docs` / `ui/docs`; everything stale lives in one
`docs/archive/`.

---

## 3. Decisions (LOCKED 2026-05-22)

1. **Reuse this repo** as the monorepo (do *not* create a new repo). Both histories preserved:
   backend native via `git mv`, UI grafted via subtree merge. Recovery point: `pre-monorepo` tags
   pushed on both repos (backend → `dfd5d68`, UI → `28c5a39`). Phase 1 is already merged to `main`.
2. **Top-level peers:** `backend/` + `ui/` + `wb-rules/` (three deployable components) + `ops/` +
   `docs/`. `scp_wb_rules.sh` stays inside `wb-rules/` for now.
3. **Repo name** — keep `wb-mqtt-bridge`; rename to a neutral name later (GitHub redirects).
4. **Docs** — cross-cutting → root `docs/`; backend-specific → `backend/docs/`; UI-specific →
   `ui/docs/`; **all stale docs → one `docs/archive/`** (contents in §3a); kept device-setup
   references → `docs/device_setup/`.
5. **Runtime dirs** — drop the tracked `logs/.gitkeep` + `data/.gitkeep` and **gitignore
   `backend/logs/` + `backend/data/`**. Verified safe: the app (`bootstrap.py:49`,
   `sqlite.py:53`) and the Docker image (`Dockerfile` `mkdir -p logs data config`, `.dockerignore`
   already excludes them) both create them on demand.
6. **README** — new monorepo root `README.md` leading with the `project.md` framing ("bridge
   WB-unsupported A/V gear + appliances into Wirenboard") + `backend/README.md` + `ui/README.md` +
   short `wb-rules/README.md`. **Authoring the root README is deferred** (§3b); create the
   structure now, write content later.
7. **Versioning** — each toolchain keeps its own manifest version (`backend/pyproject.toml`,
   `ui/package.json`); release tagged once at the repo level.
8. **GHCR fold-in (#7)** — structural move **only** in this pass; keep artifact-based deploy; GHCR
   images as the immediate follow-on (also retires the plaintext PAT).
9. **Docker build context** — UI image built with context = repo root, Dockerfile `ui/Dockerfile`,
   copying `backend/config` + `backend/openapi.json` + `ui/`.
10. **UI repo disposition** — archive `droman42/wb-mqtt-ui` read-only (history preserved here); do
    not delete.
11. **Increment style** — land in small reviewable commits: move backend → `backend/` · graft UI →
    `ui/` · add `wb-rules/` · fix broken paths (UI codegen `../backend/…`, drop the CI second-
    checkout, Dockerfile `COPY backend/`) · unify CI · verify both build.

## 3a. Docs migration (from the 2026-05-22 staleness sweep)

**Move to `docs/archive/`** (5 stale backend docs; the UI repo had no new archive candidates):
- `docs/config_future.md` — config-redesign proposal never adopted
- `docs/scenarios/scenarios.md` — old scenario format, superseded by the redesign
- `docs/scenarios/scenario_system_spec.md` — old "merged" scenario spec, superseded
- `docs/scenarios/scenario_system.spec.ipynb` — old scenario design notebook
- `docs/spec_v1.ipynb` — genesis notebook (its markdown twin is already archived)

**Fix in place (not archive) during the move:**
- `docs/architecture.md` — refresh the "Scenario system" + "WB virtual-device emulation" sections
  (now stale on `main`: the reconciler replaced startup/shutdown sequences; scenario-as-WB-device
  publishing is disabled).
- `ui/docs/page_instructions.md` — strip the leftover "Python state generation" troubleshooting /
  best-practices (contradicts the Python-free build).
- Flip the pre-implementation status headers on `docs/scenarios/scenario_system_redesign.md` and
  this plan (both are built / in progress, not "DRAFT not implemented").
- Minor: `docs/project.md` "adopting the GSD workflow" wording (GSD was dropped).

## 3b. Deferred / backlog (captured, do later)

- **Author the monorepo root `README.md`** (lead with the `project.md` framing).
- **Automate wb-rules deployment GitHub → WB controller** (like the container deploy via
  `manage_docker.sh` / GHCR, replacing the manual `scp_wb_rules.sh`) — ops family, with #7/#8.

---

## 4. Migration procedure (mechanical, reversible)

Nothing here changes code behavior — it's moves + path/CI edits. Key constraint: **do NOT rewrite
the backend's history** (it's a public repo with the `pre-monorepo` tag + existing clones). The
backend moves with `git mv` (native history, SHAs preserved); only a *throwaway* UI clone is
rewritten to graft it under `ui/`.

### 4.0 Pre-flight  (DONE 2026-05-22, except the cruft tidy)
- Both repos clean + pushed; **`pre-monorepo` tags created + pushed** (backend `dfd5d68`, UI
  `28c5a39`); Phase 1 already merged to `main`. ✅
- Drop the tracked runtime placeholders and gitignore the dirs (decision #5):
  `git rm logs/.gitkeep data/.gitkeep` → gitignore `backend/logs/` + `backend/data/`.
- Confirm no secrets staged (`docker_manager_config.json` is gitignored). Install `git-filter-repo`.

### 4.1 Move the backend into `backend/`  (git mv — native history, NO SHA rewrite)
On `main`, `git mv` the backend-specific top-level entries into `backend/` in one commit
(`src tests config openapi.json pyproject.toml uv.lock Dockerfile .dockerignore .env.example` …).
**Leave the peers at the root**: `wb-rules/`, `.github/`, and the soon-to-be `docs/` + `ops/`.
`git log --follow backend/<file>` keeps full history; the `pre-monorepo` tag and all existing
SHAs/clones stay valid.

### 4.2 Graft the UI under `ui/`  (subtree merge — preserves UI history, backend untouched)
Rewrite a **throwaway clone** of the UI into a `ui/` subdir, then merge it in (this only rewrites
the disposable UI clone, never the backend):
```bash
git clone git@github.com:droman42/wb-mqtt-ui.git ui-fr && (cd ui-fr && git filter-repo --to-subdirectory-filter ui)
git remote add ui ./ui-fr && git fetch ui
git merge --allow-unrelated-histories ui/main -m "chore: merge wb-mqtt-ui under ui/"
git remote remove ui && rm -rf ui-fr
```
(Equivalent: `git subtree add --prefix=ui <ui-remote> main`.)

### 4.3 Hoist cross-cutting docs + ops
- Move the cross-repo docs to top-level `docs/` (UI↔backend contract, scenario redesign, this plan).
- Move `backend/manage_docker.sh` + the `docker_manager_config.json` *sample* to `ops/`.

### 4.4 Fix the UI build (remove the sibling-checkout assumption)
- **`ui/Dockerfile`**: drop `COPY wb-mqtt-bridge/ ./wb-mqtt-bridge/`; with context = repo root, copy
  `backend/config` + `backend/openapi.json` + `ui/` instead. Update the codegen flag to
  `--mapping-file=backend/config/device-state-mapping.json` (or a repo-root-relative path).
  *(The mapping's internal paths already resolve relative to the mapping file's dir — #4.5 — so only
  the argument path changes.)*
- **`ui/package.json`** scripts that reference `wb-mqtt-bridge/...` → `backend/...`.

### 4.5 Consolidate CI → one workflow
- New `.github/workflows/build-arm.yml` with jobs:
  - `backend-test` (amd64 pytest), `backend-build-arm` (buildx armv7, context `backend/`).
  - `ui-build-arm` — **no second checkout** (backend is in-tree); context = repo root,
    `file: ui/Dockerfile`; runs codegen against `backend/`.
  - Optional `paths:` filters so backend-only changes skip the UI build (and vice-versa).
- Delete the two per-repo workflows.

### 4.6 Update deploy
- `ops/docker_manager_config.json`: both containers now have `repo: droman42/wb-mqtt-bridge`;
  artifact names stay distinct (`wb-mqtt-bridge-image`, `wb-mqtt-ui-image`) and come from the
  **same** workflow run.
- `ops/manage_docker.sh`: adjust artifact-source resolution to one repo / one run.
  *(If we fold in GHCR #7 here instead, this whole PAT+artifact path is replaced by
  `docker pull ghcr.io/...` — see §6.)*

### 4.7 Validate
- CI green: backend tests pass; both ARM images build.
- Local: simulate a deploy (`manage_docker.sh deploy all`) end-to-end on the Wirenboard, or a dry run.
- Diff sanity: `openapi.json`, device configs, and UI codegen output unchanged vs. `pre-monorepo`.

### 4.8 Cutover
- Push the monorepo to `droman42/wb-mqtt-bridge`.
- **Archive** `droman42/wb-mqtt-ui` (read-only). Update any external references/bookmarks.
- Update local dev: one clone, two subdirs.

---

## 5. Rollback
- Nothing is deleted: `pre-monorepo` tags exist in both original repos; the UI repo is archived,
  not removed. If the monorepo state is bad, revert the backend repo to `pre-monorepo` and un-archive
  the UI repo. Because history is preserved (not squashed), this is low-risk.

---

## 6. Interactions & follow-ons

- **#7 GHCR (recommended immediate follow-on):** push both images to GHCR from the unified
  workflow; deploy via `docker pull`. **Retires the plaintext PAT** in `docker_manager_config.json`
  (uses `GITHUB_TOKEN` in CI; read-only pull on the device). Resolves action_plan rough-edge #5.
- **#8 docker-compose:** a top-level `docker-compose.yml` referencing both GHCR images, wired by
  service name — natural once #7 lands.
- **Secrets (#5):** independent of the move, **rotate the current PAT** (it surfaced in a session
  transcript) and keep it gitignored/out of the monorepo.
- **Layer 3 payoff:** after the move, manifest-schema (backend) and renderer (ui) changes land in
  **one commit**, and the `.gen.tsx` fidelity oracle is diffable at a single SHA.

---

## 7. What this explicitly does NOT do
- No code-behavior changes (pure moves + path/CI/deploy edits).
- No squashing of history.
- Does not, by itself, remove the build-time codegen — that's Layer 3. (Though post-Layer-3 the UI
  build stops needing `backend/` entirely, further simplifying the UI image.)

---

## 8. Open items to confirm before executing
- Decisions in §3 (name, subdirs, versioning, GHCR-in-this-pass?, UI repo archive).
- Whether to bundle **#7 GHCR** into the same pass (lean: separate, immediately after).
