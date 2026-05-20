---
phase: 1
slug: dependency-reproducibility-hardening
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-20
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (pytest-asyncio, pytest-mock, pytest-cov) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]` if present) / `tests/conftest.py` |
| **Quick run command** | `uv run pytest tests/devices/test_auralic_device.py tests/devices/test_apple_tv*.py -q` |
| **Full suite command** | `uv run pytest -q` |
| **Estimated runtime** | ~60 seconds (225 tests, amd64) |

> Note: exact test paths are placeholders for the planner to confirm against the repo tree;
> the device-test pattern (mock external client, bypass `setup()`) is documented in `01-CONTEXT.md`.

---

## Sampling Rate

- **After every task commit:** Run the quick command (Auralic + Apple TV driver tests — the two deps being re-pinned)
- **After every plan wave:** Run the full suite (`uv run pytest -q`)
- **Before `/gsd:verify-work`:** Full suite must be green (target: 225 pass / 0 fail) on amd64
- **Max feedback latency:** ~60 seconds

---

## Per-Task Verification Map

> Populated by the planner from the PLAN.md tasks. Each DEP requirement must map to an
> automated check; the re-pin tasks must be guarded by the driver tests and a lock-integrity check.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-01.T1 | 01-01 | 1 | DEP-01 | T-1-01, T-1-03 | git deps resolve to immutable refs (no `branch =`; pyatv on PyPI) | cmd | grep guard on `pyproject.toml` | ✅ | ⬜ pending |
| 01-01.T2 | 01-01 | 1 | DEP-03 | T-1-02 | every direct PyPI dep carries an upper bound | cmd | grep bounded-pattern count >= 17 | ✅ | ⬜ pending |
| 01-01.T3 | 01-01 | 1 | DEP-01 | T-1-01, T-1-03 | lockfile consistent; openhomedevice on SHA rev, pyatv 0.17.0 from PyPI | cmd | `uv lock && uv sync && uv lock --locked` + grep uv.lock | ✅ | ⬜ pending |
| 01-02.T1 | 01-02 | 2 | DEP-01 | T-1-04 | pin-guard: no `branch =`, lxml-free openhomedevice, bounds present | unit | `uv run pytest tests/test_dependency_pins.py -v` | ✅ (created in 01-02.T1) | ⬜ pending |
| 01-02.T2 | 01-02 | 2 | DEP-01 | T-1-05 | Auralic + Apple TV drivers unaffected by re-pin; full suite green | unit | quick driver tests + `uv run pytest -q` | ✅ | ⬜ pending |
| 01-03.T1 | 01-03 | 2 | DEP-02 | T-1-06 | recovery runbook documents per-source restore + `uv sync --frozen` | doc/cmd | grep `docs/maintenance/dependency-recovery.md` | ✅ (created in 01-03.T1) | ⬜ pending |
| 01-03.T2 | 01-03 | 2 | DEP-02 | T-1-07 | dependency-pinning policy recorded as ADR 0006 + indexed | doc/cmd | grep `docs/adr/0006-*.md` + index row | ✅ (created in 01-03.T2) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing pytest infrastructure covers all phase requirements (225 tests already pass on amd64).
A small **pin-guard test** may be added (assert no `branch =` git sources in `pyproject.toml`,
assert `openhomedevice` resolves lxml-free) — the planner decides whether to include it.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Auralic / Apple TV control on real hardware | (Phase 5 / DEV) | `requires_device` tests don't run in CI | Deferred to Phase 5 — NOT a Phase 1 gate |

Phase 1 automated verification = amd64 suite green + mocked driver tests. On-hardware re-verification is explicitly out of scope for this phase.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (none — existing pytest infra + 01-02 guard)
- [x] No watch-mode flags
- [x] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved (planner, 2026-05-20)
