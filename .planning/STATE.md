---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: planning
stopped_at: Inserted Phase 1 (Dependency Reproducibility Hardening); phases renumbered 2–7
last_updated: "2026-05-20T09:55:00.105Z"
last_activity: 2026-05-20 — inserted Phase 1 (Dependency Reproducibility Hardening) before the scenario fix; phases renumbered 2–7
progress:
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-20)

**Core value:** It actually works — every device action works and every scenario runs end-to-end on real Wirenboard hardware.
**Current focus:** Phase 1 — Dependency Reproducibility Hardening

## Current Position

Phase: 1 of 7 (Dependency Reproducibility Hardening)
Plan: 0 of 3 in current phase
Status: Ready to plan
Last activity: 2026-05-20 — inserted Phase 1 (Dependency Reproducibility Hardening) before the scenario fix; phases renumbered 2–7

Progress: [░░░░░░░░░░] 0%

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

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- ADRs 0001–0005 LOCKED (contract coupling, additive OpenAPI injection, backend-owned mapping, runtime URLs, Miele/SprutHub pruning)
- Dependency hardening is Phase 1 (inserted 2026-05-20) — reproducible build before functional work, since two libs are git-pinned to a moving branch / bare commit
- Scenario fix is Phase 2 — the #1 success criterion and headline gap (follows dependency hardening)
- P1/P2 hardening + test-CI work recorded as completed context, not open phases

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

Last session: 2026-05-20
Stopped at: Inserted Phase 1 (Dependency Reproducibility Hardening) before the scenario fix; phases renumbered 2–7. Next: /gsd-plan-phase 1
Resume file: None
