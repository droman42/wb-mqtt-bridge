# Roadmap: wb-mqtt-bridge

## Overview

The 2026-05 hardening pass is done: the OpenAPI contract, the Python-free UI build,
runtime URL config, backend-owned state mapping, the repaired test suite in CI, and the
doc/Miele/SprutHub reconciliation all shipped (recorded as Validated context, not
phases). What remains is **functional correctness and the bounded backlog**. The journey:
first close the headline gap by **fixing the broken scenario layer** so the house
actually works on hardware (Phase 1); then make the **button-placement contract**
explicit so layout stops depending on undocumented config order (Phase 2); then harden
the pipeline with **CI quality gates** (Phase 3); then ship the **planned device
features** — Apple TV app launching, IR-code learning, Revox hardware re-verify, Roborock
+ appliance pages (Phase 4). Two further phases — **GHCR/compose ops** (Phase 5) and an
**arm64 image for WB8+** (Phase 6) — are deferred and gated on open decisions.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Fix the Scenario Layer** - Reproduce, root-cause, and fix scenarios so every one runs end-to-end on hardware (top priority)
- [ ] **Phase 2: Button-Placement Contract** - Design and adopt an explicit, reviewable control-placement contract
- [ ] **Phase 3: CI Quality Gates** - Backend lint/mypy/ruff gates + a working UI test step
- [ ] **Phase 4: Planned Device Features** - Apple TV app launching, IR-code learning page, Revox hardware re-verify, Roborock + appliance pages
- [ ] **Phase 5: Ops & Image Distribution** - GHCR images + top-level docker-compose (deferred)
- [ ] **Phase 6: arm64 Image for WB8+** - Produce an arm64 deployable image for the WB8+ migration (deferred)

## Phase Details

### Phase 1: Fix the Scenario Layer
**Goal**: Every shipped scenario runs end-to-end on real Wirenboard hardware — closing the headline gap to "my house works."
**Depends on**: Nothing (first phase; device actions already mostly work)
**Requirements**: SCEN-01, SCEN-02, SCEN-03, SCEN-04
**Success Criteria** (what must be TRUE):
  1. Each shipped scenario (`movie_appletv`, `movie_ld`, `movie_vhs`, `movie_zappiti`) can be invoked via the API or its WB virtual device and completes its startup sequence on hardware
  2. A scenario can be shut down cleanly and re-invoked; commands cannot be dispatched to an uninitialized or shutting-down scenario (lifecycle state machine guards this)
  3. The root cause is identified and documented (which of: startup/shutdown sequencing, condition evaluation, role-action dispatch, WB-adapter, or state)
  4. An end-to-end scenario test exists and fails if the regression returns
**Plans**: TBD

Plans:
- [ ] 01-01: Reproduce scenario failures and root-cause (instrument startup/shutdown, condition eval, role-action dispatch, WB-adapter, state)
- [ ] 01-02: Implement scenario lifecycle state machine + fix the diagnosed defect
- [ ] 01-03: Add end-to-end scenario test; verify all four scenarios on hardware

### Phase 2: Button-Placement Contract
**Goal**: Control placement within the remote is explicit, deterministic, and reviewable — no longer dependent on undocumented `config/devices/*.json` command ordering.
**Depends on**: Phase 1 (scenarios working frees focus for UI-contract design)
**Requirements**: PLACE-01, PLACE-02
**Success Criteria** (what must be TRUE):
  1. A placement-contract design is written and agreed before implementation (one of: per-action `slot`/`order` config fields, a backend-owned layout manifest, or `x-ui-*` command annotations)
  2. Reordering or renaming a command in a device config no longer silently moves or drops a button — placement is governed by the explicit contract
  3. The remote layout for at least one device renders identically through the new contract, proving the migration path
**Plans**: TBD
**UI hint**: yes

Plans:
- [ ] 02-01: Design the placement contract; weigh the three candidate mechanisms; agree the approach
- [ ] 02-02: Implement the chosen contract across backend + UI; migrate one device as proof

### Phase 3: CI Quality Gates
**Goal**: CI fails on type/lint regressions for the changed surface in both repos.
**Depends on**: Phase 1 (don't gate on lint while scenarios are broken)
**Requirements**: CI-01, CI-02
**Success Criteria** (what must be TRUE):
  1. Backend CI runs ruff/lint + mypy and fails the build on a regression in changed code
  2. UI CI runs a test step that actually executes (jest preset fixed or replaced) and fails on a failing test
  3. A deliberately-introduced lint/type error is caught by CI before merge
**Plans**: TBD

Plans:
- [ ] 03-01: Add ruff + mypy to backend CI (`build-arm.yml` / amd64 test job)
- [ ] 03-02: Fix or replace the UI jest preset; wire `npm test` into UI CI

### Phase 4: Planned Device Features
**Goal**: The remaining backlog device features work on real hardware, completing the home inventory.
**Depends on**: Phase 1 (working scenarios), Phase 2 (placement contract for new controls)
**Requirements**: DEV-01, DEV-02, DEV-03, DEV-04
**Success Criteria** (what must be TRUE):
  1. Apple TV app launching works on hardware (launch a named app from the remote)
  2. An IR-code learning page captures codes from a physical remote and persists them for reuse
  3. The Revox A77 reel-to-reel is re-verified working on hardware after the Wirenboard refactor
  4. Roborock and appliance pages render and control their devices on hardware
**Plans**: TBD
**UI hint**: yes

Plans:
- [ ] 04-01: Apple TV app launching (driver + remote control)
- [ ] 04-02: IR-code learning page (capture + persist + replay)
- [ ] 04-03: Revox A77 on-hardware re-verification
- [ ] 04-04: Roborock driver + appliance UI pages

### Phase 5: Ops & Image Distribution
**Goal**: Deployments pull durable, versioned images instead of ephemeral artifacts.
**Depends on**: Phase 4 (stable feature set worth distributing); gated on the repo-structure open decision
**Requirements**: OPS-01, OPS-02
**Success Criteria** (what must be TRUE):
  1. CI pushes versioned images to GHCR; deploys pull from GHCR (plaintext-PAT machinery in `manage_docker.sh` removed)
  2. A top-level `docker-compose.yml` wires both GHCR images by service name and brings the stack up
**Plans**: TBD

Plans:
- [ ] 05-01: Push backend + UI images to GHCR; retire the GitHub-API/PAT artifact path
- [ ] 05-02: Author the top-level docker-compose wiring both images

### Phase 6: arm64 Image for WB8+
**Goal**: An arm64 deployable image exists when the WB8+ migration is scheduled.
**Depends on**: Phase 5 (image distribution in place); gated on the WB8+ migration-timing open decision
**Requirements**: ARCH-01
**Success Criteria** (what must be TRUE):
  1. An arm64 (ARM64/64-bit) image builds in CI alongside or replacing the ARMv7 image
  2. The arm64 image runs the backend + UI on WB8+ hardware (verified when migration hardware is available)
**Plans**: TBD

Plans:
- [ ] 06-01: Add arm64 to the buildx platform matrix; produce + publish the arm64 image

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Fix the Scenario Layer | 0/3 | Not started | - |
| 2. Button-Placement Contract | 0/2 | Not started | - |
| 3. CI Quality Gates | 0/2 | Not started | - |
| 4. Planned Device Features | 0/4 | Not started | - |
| 5. Ops & Image Distribution | 0/2 | Deferred | - |
| 6. arm64 Image for WB8+ | 0/1 | Deferred | - |
