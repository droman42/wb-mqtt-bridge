---
phase: 01-dependency-reproducibility-hardening
plan: "03"
subsystem: dependencies
tags: [dependencies, documentation, supply-chain, adr]
dependency_graph:
  requires: [01-01]
  provides: [dep-recovery-runbook, dep-pinning-adr]
  affects: [docs/maintenance/dependency-recovery.md, docs/adr/0006-dependency-pinning-policy.md, docs/adr/README.md]
tech_stack:
  added: []
  patterns: [runbook-as-maintenance-doc, adr-for-policy]
key_files:
  created:
    - docs/maintenance/dependency-recovery.md
    - docs/adr/0006-dependency-pinning-policy.md
  modified:
    - docs/adr/README.md
decisions:
  - "Recovery runbook documents uv sync --frozen as pin-of-record restore and openhomedevice re-push procedure using the immutable SHA"
  - "ADR 0006 records four-rule dependency pinning policy: personal libs via PyPI exact-pin, third-party git on immutable SHA, direct PyPI deps bounded, uv.lock as pin-of-record"
  - "Migration trigger documented: drop openhomedevice fork when upstream bazwilliams/openhomedevice publishes >=2.4.0 on PyPI without lxml"
metrics:
  duration_minutes: 5
  completed_date: "2026-05-20"
  tasks_completed: 2
  tasks_total: 2
  files_changed: 3
requirements_addressed: [DEP-02]
---

# Phase 1 Plan 3: Dependency Recovery Runbook and ADR 0006 Summary

**One-liner:** Recovery runbook documents uv sync --frozen as pin-of-record restore with openhomedevice re-push procedure; ADR 0006 encodes the four-rule dependency pinning policy as a durable architectural decision.

## What Was Built

### Task 1: Dependency recovery runbook

Created `docs/maintenance/dependency-recovery.md` (135 lines). The runbook covers:

- **Pin-of-record statement:** committed `uv.lock` is authoritative; `uv sync --frozen` installs the exact pinned environment and refuses any resolution update.
- **Per-source recovery table:** three rows — openhomedevice fork (user-owned, SHA `6e862a1022f59a21c57c501dcf040f81d12ebfaf`, re-push from clone/cache if lost); pyatv==0.17.0 (PyPI immutable wheel, no recovery action); all other deps (uv.lock + `uv sync --frozen`).
- **Step-by-step "git source disappeared" procedure:** locate source (local checkout → uv cache `~/.cache/uv/git-v0/` → another fork) → push to new GitHub repo → update `pyproject.toml` URL at both `dependencies` and `[tool.uv.sources]` (same SHA, new URL) → `uv lock && uv sync`.
- **Migration trigger:** drop the fork when upstream `bazwilliams/openhomedevice` publishes >=2.4.0 on PyPI without lxml.

### Task 2: ADR 0006 and updated ADR index

Created `docs/adr/0006-dependency-pinning-policy.md` and added row to `docs/adr/README.md`.

ADR 0006 records four rules:

1. **Personal libs:** distribute via PyPI, pin with `==`.
2. **Third-party git sources:** immutable SHA refs only (`rev =`); mirror if not owner-controlled; migrate to PyPI when possible.
3. **Direct PyPI deps:** carry lower and next-major upper bound (`>=x,<y`).
4. **`uv.lock` as pin-of-record:** `uv sync --frozen` is the deterministic restore.

The ADR documents the openhomedevice exception (SHA pin for ARMv7 lxml avoidance), its migration trigger, and the reference to the recovery runbook. Alternatives considered: always-mirror, git tags vs SHAs, exact-pinning all PyPI deps.

## Verification Passed

- `docs/maintenance/dependency-recovery.md` exists (135 lines, >30 minimum)
- Contains `uv sync --frozen`, SHA `6e862a1022f59a21c57c501dcf040f81d12ebfaf`, `pyatv`, `lxml` references
- `docs/adr/0006-dependency-pinning-policy.md` exists with `## Context`, `## Decision`, `## Consequences`
- All four policy points present (personal libs, git immutable ref, PyPI bounds, uv.lock record)
- `docs/adr/README.md` contains `0006` row linking to `0006-dependency-pinning-policy.md` with status `Accepted`

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — this plan is pure documentation with no UI or data-rendering changes.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or schema changes introduced.
Threat model threats T-1-06 (loss of openhomedevice fork) and T-1-07 (undocumented future dependency decisions) are both mitigated by this plan.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | 10c0c0c | docs(01-03): add dependency recovery runbook (DEP-02) |
| 2 | 6419b09 | docs(01-03): add ADR 0006 — dependency pinning policy |

## Self-Check

- [x] `docs/maintenance/dependency-recovery.md` exists (135 lines)
- [x] `docs/adr/0006-dependency-pinning-policy.md` exists
- [x] `docs/adr/README.md` contains 0006 row
- [x] Commits 10c0c0c, 6419b09 exist in git log
- [x] Automated verify commands pass for both tasks

## Self-Check: PASSED
