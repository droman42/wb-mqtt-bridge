---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: Completed Phase 01 Plan 01 — dependency re-pinning and upper bounds
last_updated: "2026-05-20T10:56:51.933Z"
last_activity: 2026-05-20
progress:
  total_phases: 7
  completed_phases: 0
  total_plans: 3
  completed_plans: 2
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-20)

**Core value:** It actually works — every device action works and every scenario runs end-to-end on real Wirenboard hardware.
**Current focus:** Phase 1 — Dependency Reproducibility Hardening

## Current Position

Phase: 1 (Dependency Reproducibility Hardening) — EXECUTING
Plan: 3 of 3
Status: Ready to execute
Last activity: 2026-05-20

Progress: [███████░░░] 67%

## Performance Metrics

**Velocity:**

- Total plans completed: 0
- Average duration: — min
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**

- Last 5 plans: none yet
- Trend: —

*Updated after each plan completion*
| Phase 01-dependency-reproducibility-hardening P01 | 2 | 3 tasks | 2 files |
| Phase 01-dependency-reproducibility-hardening P02 | 8 | 2 tasks | 1 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- ADRs 0001–0005 LOCKED (contract coupling, additive OpenAPI injection, backend-owned mapping, runtime URLs, Miele/SprutHub pruning)
- Dependency hardening is Phase 1 (inserted 2026-05-20) — reproducible build before functional work, since two libs are git-pinned to a moving branch / bare commit
- Scenario fix is Phase 2 — the #1 success criterion and headline gap (follows dependency hardening)
- P1/P2 hardening + test-CI work recorded as completed context, not open phases
- [Phase ?]: openhomedevice: keep fork at SHA 6e862a1022f59a21c57c501dcf040f81d12ebfaf — upstream PyPI 2.3.1 still has lxml, ARMv7 constraint preserved (DEP-01)
- [Phase ?]: pyatv: migrated from git commit f75e718 to PyPI pyatv==0.17.0 — protobuf fix shipped in 0.16.1+, no API breaks for AppleTVDevice driver (DEP-01)
- [Phase ?]: paho-mqtt capped at <2: 2.x has breaking callback-signature changes; cap at 1.x forced aiomqtt 2.3.2 to 2.0.1 (cascading constraint, aiomqtt 2.0.1 + paho 1.6.1 work with existing code)
- [Phase ?]: pin-guard test
- [Phase ?]: aiomqtt 2.0.1 + paho-mqtt 1.6.1 confirmed regression-free: all 236 amd64 tests pass
- [Phase ?]: pyatv 0.17.0 and openhomedevice SHA 6e862a1 both confirmed API-compatible with their drivers

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 1] Dependency supply-chain risk: `openhomedevice` tracks a moving fork branch (`remove-lxml-dependency`) and `pyatv` a bare upstream commit; direct PyPI deps lack upper bounds. A force-push/delete or breaking release can make the build unrecoverable. Files: `pyproject.toml:50-53`, `pyproject.toml:133-137` (`[tool.uv.sources]`).
- [Phase 2] Scenario layer is broken (confirmed 2026-05-20) — root cause undiagnosed. Codebase audit flags: no scenario lifecycle state machine, no end-to-end scenario tests, circular-dependency risk device↔scenario, no scenario action rollback. Files: `domain/scenarios/scenario.py`, `domain/scenarios/service.py`, `infrastructure/scenarios/wb_adapter.py`.
- [Cross-cutting] Success is measured on real Wirenboard (ARMv7) hardware, not just CI — `requires_device` tests don't run in CI.
- [Open decisions] Repo structure, deploy target, `device_category` behavior, button-placement mechanism, WB8+/arm64 timing — gate Phases 3/6/7. See PROJECT.md Open Questions.

## Deferred Items

Items acknowledged and carried forward:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Ops | GHCR images + top-level compose (Phase 6, OPS-01/02) | Deferred (P3) | 2026-05-20 |
| Hardware | arm64 image for WB8+ (Phase 7, ARCH-01) | Deferred — revisit at migration | 2026-05-20 |
| Workflow | GSD adoption (REQ-adopt-gsd-workflow) | Completing — this bootstrap is Step D | 2026-05-20 |

## Session Continuity

Last session: 2026-05-20T10:56:51.924Z
Stopped at: Completed Phase 01 Plan 01 — dependency re-pinning and upper bounds
Resume file: None
