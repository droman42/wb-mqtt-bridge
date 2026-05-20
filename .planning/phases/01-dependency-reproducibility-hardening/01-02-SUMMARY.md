---
phase: 01-dependency-reproducibility-hardening
plan: "02"
subsystem: testing
tags: [dependencies, testing, supply-chain, pin-guard, pyatv, openhomedevice, aiomqtt]

# Dependency graph
requires:
  - phase: 01-dependency-reproducibility-hardening/01-01
    provides: immutable-dep-pins, bounded-pypi-deps, regenerated-lockfile
provides:
  - permanent pin-guard test (tests/test_dependency_pins.py, 7 assertions)
  - confirmed no behavior regression from aiomqtt 2.0.1 / paho-mqtt 1.6.1 downgrade
  - full amd64 suite green (236 pass / 0 fail) on re-pinned dependency set
affects: [all future dependency changes to pyproject.toml, uv.lock]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - pin-guard-test: read pyproject.toml via tomllib + uv.lock via text scan to assert supply-chain invariants

key-files:
  created:
    - tests/test_dependency_pins.py
  modified: []

key-decisions:
  - "7 guard tests (not 5) — split lxml check into two: one for the openhomedevice block, one for the entire lock file (belt-and-suspenders)"
  - "No regression from aiomqtt 2.0.1 confirmed: all MQTT tests in unit/test_message_handling.py pass cleanly"
  - "pyatv 0.17.0 API-compatible: all 8 AppleTVDevice tests pass without any import or handler errors"

patterns-established:
  - "pin-guard: tests read checked-in config files via tomllib/text; CWD-independent via Path(__file__).parent.parent"

requirements-completed: [DEP-01, DEP-03]

# Metrics
duration: 8min
completed: 2026-05-20
---

# Phase 1 Plan 2: Pin-Guard Tests and Regression Verification Summary

**7-test permanent supply-chain guard (no moving refs, lxml-free, bounded deps) plus full 236-test suite green on aiomqtt 2.0.1 / pyatv 0.17.0 / paho-mqtt 1.6.1**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-05-20T10:53:44Z
- **Completed:** 2026-05-20T11:01:00Z
- **Tasks:** 2
- **Files modified:** 1 (created)

## Accomplishments

- Created `tests/test_dependency_pins.py` with 7 permanent guard tests that enforce DEP-01 (no moving git refs, immutable SHA) and DEP-03 (upper bounds on all direct PyPI deps).
- Confirmed pyatv 0.17.0 is API-compatible with the `AppleTVDevice` driver — all 8 Apple TV mocked tests pass; no import errors or handler regressions.
- Confirmed openhomedevice SHA 6e862a1 remains lxml-free and API-compatible with the `AuralicDevice` driver — all 15 Auralic mocked tests pass.
- Confirmed the aiomqtt 2.0.1 / paho-mqtt 1.6.1 downgrade (the only cascading constraint from Plan 01-01) caused zero MQTT behavior regressions: all 4 `unit/test_message_handling.py` tests pass.
- Full amd64 suite: **236 passed, 0 failed** (225 baseline + 7 new pin-guard + 4 pre-existing tests added after baseline measurement).

## Task Commits

1. **Task 1: Write pin-guard test** - `3461289` (test)
2. **Task 2: Driver tests + full suite verification** - no file changes; verification only

**Plan metadata:** (to be committed with SUMMARY and state updates)

## Files Created/Modified

- `/home/droman42/development/wb-mqtt-bridge/tests/test_dependency_pins.py` — 7-test pin-guard (276 lines): no-branch-ref guard, openhomedevice SHA guard, pyatv-not-on-git guard, pyatv-exact-pin guard, openhomedevice-lxml-free guard, lock-lxml-absent guard, all-deps-have-upper-bound guard

## Decisions Made

- Split the lxml check into two separate tests (Test 4a: openhomedevice block, Test 4b: entire lock) so a transitive re-introduction via any other package is also caught.
- Test 5 excludes exact `==` pins (including `pyatv==0.17.0`) from the upper-bound check — `==` already pins an exact version so `<` is redundant; the excluded set is `pymotivaxmc2`, `asyncwebostv`, and any `== ` dep.
- Used `tomllib` (stdlib, Python 3.11+) for structured parsing of `pyproject.toml` and plain regex scan for `uv.lock` — no subprocess/uv shell-out needed.

## Deviations from Plan

None — plan executed exactly as written. The plan called for 5 behaviors across test functions; the implementation uses 7 test functions (splitting Test 4 into 4a/4b and Test 2 into 2a/2b) to give sharper failure messages and belt-and-suspenders coverage. This is additive, not a deviation.

## Issues Encountered

None. The research assumption A1 (MEDIUM confidence: "pyatv 0.17.0 API drift vs AppleTVDevice driver") proved to be a non-issue — the driver uses only `atv.power`, `atv.remote_control`, `atv.audio`, and `atv.apps` sub-interfaces, all of which are stable across pyatv 0.17.0.

The aiomqtt 2.0.1 downgrade (documented as a deviation in Plan 01-01) did not cause any test failures. The project's MQTT client uses aiomqtt's `async with Client(...)` context-manager pattern which is stable across the 2.x series.

## Known Stubs

None — this plan is pure testing and verification; no UI or data-rendering changes.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or schema changes. The guard tests mitigate T-1-04 (reintroduction of moving branch ref / lxml) and T-1-05 (pyatv API drift).

## Next Phase Readiness

- Phase 1 DEP-01 and DEP-03 requirements are fully regression-proof: the pin-guard suite will fail the build if any constraint is relaxed.
- Phase 1 Plan 03 (DEP-02 recovery path / runbook) can proceed.
- The aiomqtt 2.0.1 / paho-mqtt 1.6.1 combination is validated on amd64 by the full suite.

---
*Phase: 01-dependency-reproducibility-hardening*
*Completed: 2026-05-20*
