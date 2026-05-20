# Monorepo Migration Plan

- **Status:** DRAFT for review (not executed). Authored 2026-05-20.
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
├── backend/                    # ← today's wb-mqtt-bridge repo
│   ├── src/ tests/ config/ docs/ pyproject.toml uv.lock Dockerfile openapi.json …
├── ui/                         # ← today's wb-mqtt-ui repo
│   ├── src/ scripts/ config/ Dockerfile nginx.conf.template package.json …
├── ops/                        # deploy glue (manage_docker.sh, docker_manager_config.* sample)
├── docs/                       # cross-cutting docs (this file, contract, scenario redesign)
├── .github/workflows/build-arm.yml   # one workflow, both images
└── docker-compose.yml          # (optional, with #8)
```

(Top-level `docs/` holds cross-repo docs — the UI↔backend contract, scenario redesign, this plan.
Backend- or UI-specific docs stay under `backend/docs` / `ui/docs`.)

---

## 3. Decisions to confirm (with leans)

1. **Repo name** — keep `wb-mqtt-bridge` (GitHub redirects the old URL; least churn) vs. rename to a
   neutral `wb-mqtt-home`/`wb-home`. **Lean: keep the name** for now; rename is cheap later.
2. **Subdir names** — `backend/` + `ui/`. **Lean: as shown.**
3. **Versioning** — each toolchain keeps its own manifest version (`backend/pyproject.toml`,
   `ui/package.json`); releases tagged once at the repo level. **Lean: independent manifests, single
   repo tag.**
4. **GHCR fold-in (#7)** — do the structural move *only* now and keep artifact-based deploy, or
   switch to GHCR images in the same pass. **Lean: structural move first (one change at a time);
   GHCR as the immediate follow-on**, since it also retires the plaintext PAT.
5. **Docker build context** — UI image built with **context = repo root**, Dockerfile `ui/Dockerfile`,
   copying `backend/config` + `backend/openapi.json` + `ui/`. **Lean: as described.**
6. **UI repo disposition** — archive `droman42/wb-mqtt-ui` read-only (history is preserved in the
   monorepo). **Lean: archive, don't delete.**

---

## 4. Migration procedure (mechanical, reversible)

Run on **fresh clones** (history rewriting with `git filter-repo` is destructive to the working
clone). Nothing here changes code behavior — it's moves + path/CI edits.

### 4.0 Pre-flight
- Both repos: clean working trees, everything pushed, **tag a rollback point** in each
  (`git tag pre-monorepo`).
- Tidy untracked cruft in the backend root that shouldn't enter the monorepo (logs, `__pycache__`,
  `*.log`, `share/`, `info/`, stray notebooks) — `.gitignore` already covers
  `docker_manager_config.json`; confirm no secrets are staged.
- Install `git-filter-repo`.

### 4.1 Rewrite each history into its subdir
```bash
# UI → ui/
git clone git@github.com:droman42/wb-mqtt-ui.git ui-fr && cd ui-fr
git filter-repo --to-subdirectory-filter ui
cd ..

# Backend → backend/   (fresh clone of the monorepo-to-be)
git clone git@github.com:droman42/wb-mqtt-bridge.git monorepo && cd monorepo
git filter-repo --to-subdirectory-filter backend
```

### 4.2 Merge UI history into the monorepo (preserves both histories)
```bash
# inside monorepo/
git remote add ui ../ui-fr
git fetch ui
git merge --allow-unrelated-histories ui/main -m "chore: merge wb-mqtt-ui into monorepo under ui/"
git remote remove ui
```

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
