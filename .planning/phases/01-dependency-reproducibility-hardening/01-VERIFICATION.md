---
phase: 01-dependency-reproducibility-hardening
verified: 2026-05-20T00:00:00Z
status: passed
score: 8/8
overrides_applied: 0
---

# Phase 1: Dependency Reproducibility Hardening — Verification Report

**Phase Goal:** The build is reproducible and recoverable — no dependency tracks a moving git ref, and direct PyPI deps are bounded so a breaking release can't be pulled silently.
**Verified:** 2026-05-20
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | No `branch =` in `[tool.uv.sources]` | VERIFIED | grep returns empty; only entry is `openhomedevice` with `rev = "6e862a1..."` |
| 2 | `openhomedevice` pinned to immutable SHA `6e862a1022f59a21c57c501dcf040f81d12ebfaf` | VERIFIED | `pyproject.toml` line 136 and `uv.lock` line 1038 both record the exact SHA |
| 3 | `pyatv` is NOT a git source; it resolves from PyPI at `==0.17.0` | VERIFIED | No `postlund/pyatv` in pyproject.toml; `uv.lock`: `version = "0.17.0"`, `source = { registry = "https://pypi.org/simple" }` |
| 4 | `uv lock --locked` exits 0 (lockfile consistent with pyproject.toml) | VERIFIED | Command ran: exit 0, "Resolved 110 packages in 1ms" |
| 5 | `uv.lock` is lxml-free (0 occurrences of `lxml`) | VERIFIED | `grep -c lxml uv.lock` returned 0 |
| 6 | Every direct runtime PyPI dependency carries a `<` upper bound | VERIFIED | Python tomllib parse: 0 deps missing upper bound out of 21 total; 17 use `>=...,<...` pattern |
| 7 | `aiomqtt>=2.0,<3`; `httpx>=0.27.0,<1`; `requests>=2.30.0,<3` bounds present | VERIFIED | Exact strings confirmed in `pyproject.toml` lines 31, 44, 45; `uv.lock` locks aiomqtt at 2.0.1 (within `>=2.0,<3`) |
| 8 | Recovery runbook and ADR 0006 exist, indexed, and substantive | VERIFIED | `dependency-recovery.md` (135 lines), `0006-dependency-pinning-policy.md` both exist; ADR README line 15 has the 0006 row |

**Score:** 8/8 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `pyproject.toml` | Immutable git pins + bounded PyPI specifiers | VERIFIED | `rev = "6e862a1..."` present; `pyatv==0.17.0`; 17 runtime deps with `>=...,<...`; no `branch =` |
| `uv.lock` | Pin-of-record with openhomedevice on rev SHA, pyatv from PyPI | VERIFIED | SHA fragment at line 1038; pyatv `registry = "https://pypi.org/simple"` at version 0.17.0 |
| `tests/test_dependency_pins.py` | 5+ guard tests; all green | VERIFIED | 7 test functions; all 7 PASSED in live run |
| `docs/maintenance/dependency-recovery.md` | Per-source recovery + `uv sync --frozen`; ≥30 lines | VERIFIED | 135 lines; contains `uv sync --frozen`, SHA, pyatv, lxml/ARMv7 migration trigger |
| `docs/adr/0006-dependency-pinning-policy.md` | Context/Decision/Consequences; all 4 policy rules | VERIFIED | All four rules present; openhomedevice exception documented; ref to recovery runbook |
| `docs/adr/README.md` | Row for 0006 with "Accepted" | VERIFIED | Line 15: `| [0006](0006-dependency-pinning-policy.md) | ... | Accepted |` |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `pyproject.toml [tool.uv.sources]` | `uv.lock` source fragment | `uv lock` | VERIFIED | `?rev=6e862a1022f59a21c57c501dcf040f81d12ebfaf#6e862a1022f59a21c57c501dcf040f81d12ebfaf` in uv.lock line 1038 |
| `pyproject.toml dependencies (pyatv==0.17.0)` | `uv.lock` registry source | `uv lock` resolves from PyPI | VERIFIED | `source = { registry = "https://pypi.org/simple" }`, version 0.17.0 |
| `docs/adr/README.md` | `docs/adr/0006-dependency-pinning-policy.md` | index table row | VERIFIED | `0006-dependency-pinning-policy.md` in README line 15 |
| `docs/maintenance/dependency-recovery.md` | `uv.lock` (as restore source) | documents `uv sync --frozen` | VERIFIED | "uv sync --frozen" appears in section 1 and section 4 |

---

### Data-Flow Trace (Level 4)

Not applicable. Phase produces configuration files and documentation — no components that render dynamic data.

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `uv lock --locked` passes (lockfile consistent) | `uv lock --locked` | exit 0, "Resolved 110 packages in 1ms" | PASS |
| Pin-guard test suite green | `uv run pytest tests/test_dependency_pins.py -v` | 7 passed, 0 failed | PASS |
| Full pytest suite green | `uv run pytest -q` | 236 passed, 0 failed, 25 warnings | PASS |
| aiomqtt version within `>=2.0,<3` cap | `grep -A3 'name = "aiomqtt"' uv.lock` | version = "2.0.1" | PASS |
| lxml absent from uv.lock | `grep -c lxml uv.lock` | 0 | PASS |

---

### Probe Execution

No probe scripts defined for this phase. `uv lock --locked` and `uv run pytest -q` serve as the functional proof.

---

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|---------------|-------------|--------|----------|
| DEP-01 | 01-01, 01-02 | No moving git ref; openhomedevice on immutable SHA; pyatv on PyPI | SATISFIED | `branch =` absent; SHA in pyproject.toml and uv.lock; pyatv from PyPI registry |
| DEP-02 | 01-03 | Documented recovery path for git-sourced deps; uv.lock as pin-of-record | SATISFIED | `dependency-recovery.md` (135 lines) covers all three sources; `uv sync --frozen` documented |
| DEP-03 | 01-01, 01-02 | Direct PyPI deps carry upper bounds | SATISFIED | 17 runtime deps with `>=...,<...`; Python parse confirms 0 unbounded runtime deps |

All 3 phase requirements satisfied. No orphaned requirements (REQUIREMENTS.md traceability table maps only DEP-01, DEP-02, DEP-03 to Phase 1).

---

### Anti-Patterns Found

Scanned: `pyproject.toml`, `tests/test_dependency_pins.py`, `docs/maintenance/dependency-recovery.md`, `docs/adr/0006-dependency-pinning-policy.md`, `docs/adr/README.md`

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | — | — | None found |

No `TBD`, `FIXME`, `XXX`, placeholder comments, stub returns, or empty implementations found in any phase-modified file.

---

### Human Verification Required

None. All must-haves are mechanically verifiable from file content and command exit codes. The phase produces no UI, no runtime behavior, and no external service integrations requiring human observation.

---

### Gaps Summary

No gaps. All 8 observable truths verified against the actual codebase. All 3 requirement IDs (DEP-01, DEP-02, DEP-03) satisfied with direct file evidence and passing test runs.

**Notable confirmation on aiomqtt cascade:** The SUMMARY claimed aiomqtt resolved down from 2.3.2 to 2.0.1 due to the `paho-mqtt<2` cap (paho-mqtt 2.x changed callback signatures). Confirmed: `uv.lock` records aiomqtt 2.0.1, which is within the `>=2.0,<3` bound. The full suite ran 236 pass / 0 fail — the version cascade introduced no regression.

---

_Verified: 2026-05-20_
_Verifier: Claude (gsd-verifier)_
