# Phase 1: Dependency Reproducibility Hardening - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-20
**Phase:** 1-Dependency Reproducibility Hardening
**Areas discussed:** openhomedevice strategy, pyatv strategy

---

## openhomedevice strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Pin to commit SHA | Pin to the exact commit the branch resolves to now; zero effort, reproducible | |
| Tag a fork release | Create a git tag on the fork and pin to it; immutable + readable | |
| Upstream fix → PyPI | Get the ARM lxml fix upstream, switch to its PyPI release | |

**User's choice:** Research-conditional. Verify whether the fork's change (no mandatory `lxml`) is integrated into the upstream library's official release. If yes → use the official release; if `lxml` is still required in main → keep the fork (pinned to an immutable ref).
**Notes:** The fork exists specifically because `lxml` doesn't work on ARMv7. That constraint is load-bearing — any solution must keep the ARMv7 build lxml-free.

---

## pyatv strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Move to PyPI release | Switch to a published pyatv==X.Y.Z if the driver still works | |
| Keep commit + mirror | Keep the exact commit; mirror the repo for recovery | |
| Investigate first | Flag for research to determine whether a release covers it | ✓ (as a precondition) |

**User's choice:** Research-conditional. The commit was pinned for a protobuf-contradiction bugfix not yet released at the time. Check whether that fix is in the current PyPI release → if yes, switch to the latest version; if no, keep the commit (and mirror, since it's not the user's repo).
**Notes:** User also surfaced a future Apple TV need (tvOS "who's watching" startup profile-picker) — captured as a deferred idea, not Phase 1.

---

## Claude's Discretion

User chose "Apply defaults, write context" for the two unselected areas:
- **PyPI bounds policy (DEP-03):** cap next-major on direct deps (e.g. `pydantic<3`, `fastapi<1`); give `httpx`/`requests` explicit lower+upper bounds (currently unconstrained); no dependabot/renovate this phase.
- **Recovery mechanism (DEP-02):** `uv.lock` as pin-of-record + a recovery runbook; proactively mirror only a non-user git source that stays on a git ref after research (i.e. pyatv if it stays on the commit).
- **Verification scope:** amd64 suite green (225) + Auralic/AppleTV mocked driver tests pass; on-hardware re-verify deferred to Phase 5.

## Deferred Ideas

- **Apple TV tvOS "who's watching" startup profile-picker** — skip/auto-select the Apple-ID family profile before control is possible. New capability → Phase 5 (DEV-01, Apple TV).
- **pymotivaxmc2 / asyncwebostv distribution strategy** — user's own libs, already exact-pinned on PyPI; defer the PyPI-vs-other decision to later.
