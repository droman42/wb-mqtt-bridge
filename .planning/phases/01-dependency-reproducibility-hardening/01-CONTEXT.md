# Phase 1: Dependency Reproducibility Hardening - Context

**Gathered:** 2026-05-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Make the build reproducible and recoverable: no dependency tracks a moving git ref,
direct PyPI deps are bounded so a breaking release can't be pulled silently, and a
recovery path exists if a git source disappears. Maps to DEP-01 (immutable git pins),
DEP-02 (recovery path), DEP-03 (PyPI upper bounds).

**Not in this phase:** upgrading FastAPI/Pydantic/etc. to new *major* versions (that's a
separate effort — here we only bound and pin), changing device behavior, or deciding the
long-term distribution model for the user's own libraries.

</domain>

<decisions>
## Implementation Decisions

### openhomedevice (the fork — `git+https://github.com/droman42/openhomedevice.git@remove-lxml-dependency`)
- **D-01 (research-conditional):** The fork exists for ONE reason — to drop the `lxml`
  dependency, which does not build/work on ARMv7 (the deploy target). Before changing the
  pin, **verify whether upstream openhomedevice (the repo this was forked from) has, in a
  *published release*, removed `lxml` or made it optional.**
  - **If yes** → migrate to the official upstream PyPI release and pin it exact; drop the fork.
  - **If no** (main release still forces `lxml`) → keep the fork, but replace the *moving
    branch* `remove-lxml-dependency` with an **immutable ref** (the commit SHA the branch
    currently resolves to, or a tag created on the fork).
- **Hard constraint:** whatever the outcome, the resolved dependency MUST keep the ARMv7
  build `lxml`-free. Never reintroduce a mandatory `lxml`.

### pyatv (`git+https://github.com/postlund/pyatv.git@f75e718bc0bdaf0a3ff06eb00086f781b3f06347`)
- **D-02 (research-conditional):** This commit was pinned because, at the time, it carried
  a fix for a **protobuf contradiction bug** that was not yet in a `pyatv` PyPI release.
  **Verify whether that fix is contained in the current pyatv PyPI release.**
  - **If yes** → switch to the latest `pyatv` PyPI release and pin it exact; re-verify the
    `AppleTVDevice` driver (mocked tests + import) against the new version.
  - **If no** → keep the commit pin, and (since `postlund/pyatv` is *not* the user's repo)
    **mirror the repo under the user's account** so the build survives upstream
    deletion/force-push.

### Deferred dependency-strategy (pymotivaxmc2, asyncwebostv)
- **D-03:** Both are the user's own libraries, already exact-pinned on PyPI
  (`pymotivaxmc2==0.6.7`, `asyncwebostv==0.2.7`) — already reproducible, so **no action this
  phase.** The decision of whether to keep them on PyPI vs. another distribution model is
  explicitly deferred (see Deferred Ideas).

### Claude's Discretion (areas not selected for discussion — sensible defaults)
- **DEP-03 bounds policy (default):** Add upper bounds capping the next major on direct
  PyPI deps (e.g. `pydantic>=2.11.0,<3`, `fastapi>=0.103.0,<1`, `uvicorn`, `aiomqtt`,
  `aiohttp`, etc.). Give `httpx` and `requests` explicit lower **and** upper bounds — they
  are currently fully unconstrained (`pyproject.toml`). Leave the user's own exact-pinned
  libs as-is. **No** dependabot/renovate adoption in this phase (can revisit later).
- **DEP-02 recovery (default):** Treat the committed `uv.lock` as the pin-of-record and
  write a short recovery runbook (how to restore a git-sourced dep if upstream vanishes).
  Proactively **mirror** only a source that is (a) not the user's own repo and (b) staying
  on a git ref after research — i.e. `pyatv` *only if* it stays on the commit pin. The
  user's own `openhomedevice` fork needs no mirror (it's already under their control).
- **Verification scope (default):** "Done" for this phase = the full suite stays green on
  amd64 (currently 225 pass) and the `AuralicDevice` + `AppleTVDevice` driver tests pass
  (mocked, per the device-test pattern), with `uv.lock` regenerated and committed.
  **On-hardware** re-verification of Auralic/Apple TV is NOT required here — that belongs to
  Phase 5 (DEV).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & requirements
- `.planning/ROADMAP.md` — Phase 1 goal, success criteria, plans 01-01..01-03
- `.planning/REQUIREMENTS.md` — DEP-01, DEP-02, DEP-03 acceptance
- `.planning/codebase/CONCERNS.md` §"Dependency pinning for critical git sources" / §"Git-pinned dependencies without fallback" / §"PyPI versions without upper bounds" — the original risk write-up

### The pins themselves
- `pyproject.toml` — `dependencies` array (git pins on `openhomedevice`, `pyatv`; unconstrained `httpx`/`requests`; precedent: `pymotivaxmc2==0.6.7`, `asyncwebostv==0.2.7`)
- `pyproject.toml` — `[tool.uv.sources]` block (the `git`/`branch`/`rev` source declarations)
- `uv.lock` — resolved versions / current pin-of-record

No ADR governs dependencies yet — if Phase 1 lands a durable policy (e.g. "personal libs via PyPI, third-party git deps pinned to immutable refs + mirrored"), consider recording it as an ADR.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Device-test pattern** (`tests/.../test_auralic_device.py`, `test_apple_tv*.py`): inject an AsyncMock for the driver's external client (openhomedevice / pyatv), bypass `setup()`, drive handlers directly. This is how to verify the drivers still work after a re-pin **without hardware**.

### Established Patterns
- **Git→PyPI migration precedent:** `pymotivaxmc2` and `asyncwebostv` were already moved from git to exact-pinned PyPI versions (comment: "Migrated from Git to PyPI") — the same playbook applies if openhomedevice/pyatv can move to releases.
- **uv-managed:** sources live in `[tool.uv.sources]`; `uv.lock` is committed. Re-pinning means editing `pyproject.toml` + regenerating `uv.lock`.

### Integration Points
- `AuralicDevice` driver depends on `openhomedevice`; `AppleTVDevice` depends on `pyatv`.
- CI amd64 test job runs the suite — the bound/pin changes must keep it green.

</code_context>

<specifics>
## Specific Ideas

- **openhomedevice fork rationale (load-bearing):** lxml does not work on ARMv7 — the entire reason the fork exists. Any migration MUST preserve an lxml-free ARMv7 build.
- **pyatv commit rationale:** a protobuf-contradiction bug fixed in `f75e718…` but unreleased at pin time.

</specifics>

<deferred>
## Deferred Ideas

- **Apple TV tvOS "who's watching" startup screen** (new capability → Phase 5 / DEV-01): recent tvOS shows a profile-picker on startup (choose the family member tied to the Apple ID) before the device is controllable. Need a way to skip or auto-select the profile via `pyatv`/the AppleTV driver. Surfaced 2026-05-20 during the pyatv discussion. Not a Phase 1 dependency concern — track against the Apple TV feature work.
- **pymotivaxmc2 / asyncwebostv distribution strategy** (revisit later): both are the user's own libraries; the question of whether to keep distributing via PyPI vs. another model is deferred. Already reproducible (exact-pinned), so no urgency.

</deferred>

---

*Phase: 1-Dependency Reproducibility Hardening*
*Context gathered: 2026-05-20*
