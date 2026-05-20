# Requirements: wb-mqtt-bridge

**Defined:** 2026-05-20
**Core Value:** It actually works — every device action works and every scenario runs end-to-end on real Wirenboard hardware.

> **Brownfield note.** The 2026-05 hardening pass (P1 contract decoupling + P2 test/doc
> reconciliation) is **done** and recorded as *Validated* below — it is completed
> context, not open work. The v1 scope here is the **remaining OPEN work**, scenario
> fix first. Source intel: `.planning/intel/requirements.md`,
> `.planning/intel/decisions.md`, `.planning/intel/constraints.md`, `docs/action_plan.md`.

## Validated Requirements

Shipped and confirmed through the hardening pass. Locked — recorded as completed context.

### Bridge & Drivers (shipped)

- ✓ **BRG-01**: Each foreign device is exposed as a WB virtual device over MQTT, usable by `wb-rules`
- ✓ **BRG-02**: Seven device drivers ship with working per-device actions (LgTv, EMotivaXMC2, AppleTVDevice, AuralicDevice, BroadlinkKitchenHood, WirenboardIRDevice, RevoxA77ReelToReel)
- ✓ **BRG-03**: Category-specific UI — Harmony-style remote for A/V `device`, bespoke pages for `appliance` — selected by `device_category`
- ✓ **BRG-04**: Live state streams over SSE; state persists to SQLite

### Contract & Hardening (shipped — P1/P2)

- ✓ **CON-01**: Committed `openapi.json` is the single source of truth for the REST surface + device-state model shapes (ADR 0001/0002)
- ✓ **CON-02**: No Python in the UI build; UI generates types from `openapi.json` (ADR 0001)
- ✓ **CON-03**: Backend owns `config/device-state-mapping.json` with directory-relative paths (ADR 0003)
- ✓ **CON-04**: Backend/MQTT URLs configured at container runtime via env vars (ADR 0004)
- ✓ **CON-05**: Test suite repaired + wired into CI on amd64 (225 pass / 0 skip / 0 fail)
- ✓ **CON-06**: Docs reconciled to reality; Miele + SprutHub pruned, voice delegated (ADR 0005)

## v1 Requirements

Open scope. Each maps to exactly one roadmap phase.

### Scenarios (top priority)

- [ ] **SCEN-01**: Scenario failures are reproduced and root-caused (startup/shutdown sequencing, condition evaluation, role-action dispatch, WB-adapter, or state)
- [ ] **SCEN-02**: A scenario lifecycle state machine guards init / running / shutdown so commands cannot dispatch to uninitialized or shutting-down scenarios
- [ ] **SCEN-03**: Every shipped scenario (`movie_appletv`, `movie_ld`, `movie_vhs`, `movie_zappiti`) runs end-to-end on real Wirenboard hardware
- [ ] **SCEN-04**: An end-to-end scenario test guards against regression (the original bug slipped past unit tests)

### Placement Contract (design first)

- [ ] **PLACE-01**: An explicit button/action placement contract is designed and agreed (per-action `slot`/`order` fields vs backend layout manifest vs `x-ui-*` annotations)
- [ ] **PLACE-02**: Control placement is deterministic and reviewable — layout no longer depends on undocumented `config/devices/*.json` command ordering

### CI Quality Gates

- [ ] **CI-01**: Backend CI fails on lint/mypy/ruff regressions for the changed surface
- [ ] **CI-02**: UI CI runs its test step (jest preset fixed or replaced; meaningful tests exist)

### Planned Device Features

- [ ] **DEV-01**: Apple TV app launching works on hardware (`Запуск приложений на AppleTV`)
- [ ] **DEV-02**: An IR-code learning page captures codes from physical remotes
- [ ] **DEV-03**: The Revox A77 reel-to-reel is re-verified on hardware after the Wirenboard refactor
- [ ] **DEV-04**: Roborock + appliance UI pages are added and work on hardware

## v2 Requirements

Deferred to a future release. Tracked but only loosely in the current roadmap (Phases 5–6 are deferred).

### Ops & Distribution

- **OPS-01**: Images push to GHCR instead of ephemeral artifacts (durable, versioned image history; removes GitHub-API + plaintext-PAT machinery in `manage_docker.sh`)
- **OPS-02**: A top-level `docker-compose.yml` wires both GHCR images by service name (requires OPS-01)

### Hardware Migration

- **ARCH-01**: An arm64 deployable image exists for the WB8+ (ARM64) migration

## Out of Scope

| Feature | Reason |
|---------|--------|
| Home Assistant replacement | Bounded to the home, not a general platform |
| Cloud dependency | LAN-only by design |
| Multi-home / multi-tenant | Single home; household usage is the aspiration, not multi-tenancy |
| Voice control built here | Delegated to WB's future Yandex Alisa bridge (ADR 0005); free once devices are WB virtual devices |
| Miele appliance support | Repeated integration attempts failed; `asyncmiele` dropped (ADR 0005) |
| SprutHub integration | Was a voice stopgap; dropped (ADR 0005) |
| amd64 deployment target | amd64 is CI/dev only; deployment is Wirenboard-exclusive |
| Runtime-driven UI rendering (Codegen Option 2) | Deferred until build-time codegen causes actual pain |
| Multi-arch builds beyond WB7→WB8 | Scope bounded by the home's hardware |

## Traceability

Which phases cover which requirements.

| Requirement | Phase | Status |
|-------------|-------|--------|
| SCEN-01 | Phase 1 | Pending |
| SCEN-02 | Phase 1 | Pending |
| SCEN-03 | Phase 1 | Pending |
| SCEN-04 | Phase 1 | Pending |
| PLACE-01 | Phase 2 | Pending |
| PLACE-02 | Phase 2 | Pending |
| CI-01 | Phase 3 | Pending |
| CI-02 | Phase 3 | Pending |
| DEV-01 | Phase 4 | Pending |
| DEV-02 | Phase 4 | Pending |
| DEV-03 | Phase 4 | Pending |
| DEV-04 | Phase 4 | Pending |
| OPS-01 | Phase 5 (deferred) | Pending |
| OPS-02 | Phase 5 (deferred) | Pending |
| ARCH-01 | Phase 6 (deferred) | Pending |

**Coverage:**
- v1 requirements: 12 total (SCEN, PLACE, CI, DEV)
- Mapped to phases: 12
- Unmapped: 0 ✓
- v2 requirements (deferred Phases 5–6): 3 (OPS-01, OPS-02, ARCH-01) — mapped but deferred

---
*Requirements defined: 2026-05-20*
*Last updated: 2026-05-20 after GSD ingest bootstrap*
