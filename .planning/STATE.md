# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-20)

**Core value:** It actually works — every device action works and every scenario runs end-to-end on real Wirenboard hardware.
**Current focus:** Phase 1 — Fix the Scenario Layer

## Current Position

Phase: 1 of 6 (Fix the Scenario Layer)
Plan: 0 of 3 in current phase
Status: Ready to plan
Last activity: 2026-05-20 — GSD ingest bootstrap; PROJECT/REQUIREMENTS/ROADMAP/STATE created from intel

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
- Scenario fix is Phase 1 — the #1 success criterion and headline gap
- P1/P2 hardening + test-CI work recorded as completed context, not open phases

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 1] Scenario layer is broken (confirmed 2026-05-20) — root cause undiagnosed. Codebase audit flags: no scenario lifecycle state machine, no end-to-end scenario tests, circular-dependency risk device↔scenario, no scenario action rollback. Files: `domain/scenarios/scenario.py`, `domain/scenarios/service.py`, `infrastructure/scenarios/wb_adapter.py`.
- [Cross-cutting] Success is measured on real Wirenboard (ARMv7) hardware, not just CI — `requires_device` tests don't run in CI.
- [Open decisions] Repo structure, deploy target, `device_category` behavior, button-placement mechanism, WB8+/arm64 timing — gate Phases 2/5/6. See PROJECT.md Open Questions.

## Deferred Items

Items acknowledged and carried forward:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Ops | GHCR images + top-level compose (Phase 5, OPS-01/02) | Deferred (P3) | 2026-05-20 |
| Hardware | arm64 image for WB8+ (Phase 6, ARCH-01) | Deferred — revisit at migration | 2026-05-20 |
| Workflow | GSD adoption (REQ-adopt-gsd-workflow) | Completing — this bootstrap is Step D | 2026-05-20 |

## Session Continuity

Last session: 2026-05-20
Stopped at: Created PROJECT.md, REQUIREMENTS.md, ROADMAP.md, STATE.md from intel (new-project from ingest)
Resume file: None
