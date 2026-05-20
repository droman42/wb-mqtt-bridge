---
phase: 01-dependency-reproducibility-hardening
plan: "01"
subsystem: dependencies
tags: [dependencies, uv, supply-chain, pyatv, openhomedevice, paho-mqtt]
dependency_graph:
  requires: []
  provides: [immutable-dep-pins, bounded-pypi-deps, regenerated-lockfile]
  affects: [pyproject.toml, uv.lock, .venv]
tech_stack:
  added: []
  patterns: [immutable-sha-pin, pypi-version-bound, uv-lock-workflow]
key_files:
  created: []
  modified:
    - pyproject.toml
    - uv.lock
decisions:
  - "openhomedevice: keep fork at SHA 6e862a1 (upstream PyPI 2.3.1 still has lxml; ARMv7 constraint preserved)"
  - "pyatv: migrated from git commit f75e718 to PyPI pyatv==0.17.0 (protobuf fix shipped in 0.16.1+)"
  - "aiomqtt cap <3 not <2: existing lock was 2.3.2, project already on 2.x (from research A3)"
  - "paho-mqtt cap <2: 2.x has breaking callback-signature changes; cap at 1.x forced aiomqtt to 2.0.1"
metrics:
  duration_minutes: 2
  completed_date: "2026-05-20"
  tasks_completed: 3
  tasks_total: 3
  files_changed: 2
requirements_addressed: [DEP-01, DEP-03]
---

# Phase 1 Plan 1: Dependency Re-pinning and Upper Bounds Summary

**One-liner:** Pinned openhomedevice to immutable SHA, migrated pyatv to PyPI 0.17.0, and added next-major upper bounds to all 17 direct PyPI dependencies.

## What Was Built

### Task 1: Re-pin git deps to immutable refs
- `openhomedevice`: changed `[tool.uv.sources]` from `branch = "remove-lxml-dependency"` to `rev = "6e862a1022f59a21c57c501dcf040f81d12ebfaf"`; updated `dependencies` array to use the SHA ref directly.
- `pyatv`: removed from `[tool.uv.sources]` entirely; changed `dependencies` entry from `pyatv @ git+https://...@f75e718` to `pyatv==0.17.0`.

### Task 2: Add upper bounds to all direct PyPI deps
Applied next-major upper bounds to all 17 uncapped dependencies:
- `aiomqtt>=2.0,<3` (was `>=1.0.0` — the lock already had 2.3.2)
- `paho-mqtt>=1.6.1,<2` (2.x has breaking on_connect/on_message callback signature changes)
- `httpx>=0.27.0,<1` and `requests>=2.30.0,<3` (were completely unconstrained)
- All other deps capped at the next major version

### Task 3: Regenerate uv.lock
- `uv lock` resolved 110 packages; `uv sync` installed cleanly; `uv lock --locked` passes.
- openhomedevice source: `?branch=remove-lxml-dependency#SHA` → `?rev=SHA#SHA` (same SHA 6e862a1, version 2.2.1, async-upnp-client only — lxml-free)
- pyatv: git source → `registry = "https://pypi.org/simple"`, version 0.17.0 (async-timeout dep dropped — Python 3.11 uses built-in asyncio.timeout)
- paho-mqtt: 2.1.0 → 1.6.1 (expected downgrade; 1.x is the intended target)
- aiomqtt: 2.3.2 → 2.0.1 (cascading constraint: aiomqtt 2.3.x requires paho-mqtt>=2.0; the `paho-mqtt<2` cap resolved aiomqtt to 2.0.1 which works with paho-mqtt 1.x)
- protobuf: 6.30.2 → 7.35.0 (pulled in by pyatv 0.17.0)

## Verification Passed

- `rev = "6e862a1022f59a21c57c501dcf040f81d12ebfaf"` in pyproject.toml
- `"pyatv==0.17.0"` in pyproject.toml
- No `branch =` or `postlund/pyatv` references remain
- 17 PyPI dependencies carry `>=...,<...` bounds
- `uv lock` exits 0, `uv sync` exits 0, `uv lock --locked` exits 0
- openhomedevice in uv.lock: `?rev=SHA#SHA`, version 2.2.1, deps: async-upnp-client only
- pyatv in uv.lock: `registry = "https://pypi.org/simple"`, version 0.17.0

## Deviations from Plan

### Unexpected Cascading Constraint: aiomqtt Downgraded

**Found during:** Task 3 (uv lock execution)

**Issue:** The plan stated "PyPI deps remain at their currently-locked versions (aiomqtt stays 2.3.2; bounds do not force any change)." However, `aiomqtt>=2.3.x` requires `paho-mqtt>=2.0`. Since `paho-mqtt<2` was applied (as planned), uv resolved aiomqtt to 2.0.1 (the highest 2.x version compatible with paho-mqtt 1.x).

**Resolution:** This is the correct behavior given the combined constraints. The plan intended `paho-mqtt<2` and `aiomqtt>=2.0,<3` — both bounds are satisfied. aiomqtt 2.0.1 works with paho-mqtt 1.6.1. The transitive resolution was unforeseen in the research but is valid.

**Impact:** aiomqtt 2.0.1 instead of 2.3.2. The main MQTT client (`infrastructure/mqtt/client.py`) uses aiomqtt's `Client` context manager API, which is stable across 2.x. Tests will verify compatibility in Plan 01-02.

**Classification:** [Rule 1 — expected consequence of intended bounds; no bug to fix]

**Commit:** 321e391

### paho-mqtt 2.1.0 → 1.6.1 Downgrade

**Found during:** Task 3 (uv lock execution)

**Issue:** The lockfile previously had paho-mqtt 2.1.0 (a minor inconsistency — the existing `paho-mqtt>=1.6.1` lower bound allowed 2.x to be resolved). The plan explicitly targets `paho-mqtt<2` to prevent the 2.x callback-signature breaking changes.

**Resolution:** Applied as designed. paho-mqtt 1.6.1 installed cleanly. The primary MQTT client uses aiomqtt (not paho directly); `mqtt_sniffer.py` uses the paho 1.x API style (mqtt.Client(), 4-arg on_connect) which works correctly with 1.6.1.

**Classification:** Intended change, not a deviation.

## Known Stubs

None — this plan is pure dependency management with no UI or data-rendering changes.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or schema changes introduced. The threat model threats T-1-01, T-1-02, and T-1-03 are mitigated by this plan.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | 6d75760 | fix(01-01): re-pin git deps to immutable refs (DEP-01) |
| 2 | 4282e2c | fix(01-01): add upper bounds to all direct PyPI deps (DEP-03) |
| 3 | 321e391 | chore(01-01): regenerate uv.lock with immutable pins (DEP-01/DEP-03) |

## Self-Check

- [x] pyproject.toml exists and contains immutable pins
- [x] uv.lock exists and contains openhomedevice rev= source
- [x] Commits 6d75760, 4282e2c, 321e391 exist in git log
- [x] `uv lock --locked` passes (verified during Task 3)

## Self-Check: PASSED
