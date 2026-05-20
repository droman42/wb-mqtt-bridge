# Phase 1: Dependency Reproducibility Hardening — Research

**Researched:** 2026-05-20
**Domain:** Python dependency management (uv, PyPI, git-sourced packages)
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01 (openhomedevice — research-conditional):** Fork exists solely to drop `lxml`, which
does not build/work on ARMv7. Before changing the pin, verify whether upstream has, in a
*published release*, removed `lxml` or made it optional.
- If yes → migrate to official upstream PyPI release, pin exact; drop the fork.
- If no → keep the fork, but replace the moving branch with an **immutable ref** (commit SHA
  or user-created tag).
- Hard constraint: resolved dependency MUST keep ARMv7 build `lxml`-free.

**D-02 (pyatv — research-conditional):** Commit pin `f75e718...` carries a protobuf fix not
yet released at pin time. Verify whether the fix is contained in the current pyatv PyPI release.
- If yes → switch to latest pyatv PyPI release, pin exact; re-verify `AppleTVDevice` driver.
- If no → keep commit pin, mirror `postlund/pyatv` under user's account.

**D-03 (pymotivaxmc2, asyncwebostv):** Already exact-pinned on PyPI (`==0.6.7`, `==0.2.7`).
No action this phase.

### Claude's Discretion

- **DEP-03 bounds policy:** Add upper bounds capping the next major on direct PyPI deps.
  Give `httpx` and `requests` explicit lower AND upper bounds. No dependabot/renovate in
  this phase.
- **DEP-02 recovery:** Committed `uv.lock` is pin-of-record. Write short recovery runbook.
  Proactively mirror only a source that is (a) not the user's own repo and (b) staying on a
  git ref after research — i.e. `pyatv` only if it stays on the commit pin.
- **Verification scope:** Full suite green on amd64 (225 pass) + `AuralicDevice` +
  `AppleTVDevice` driver tests pass (mocked). On-hardware re-verification is NOT required
  here (Phase 5).

### Deferred Ideas (OUT OF SCOPE)

- Apple TV tvOS "who's watching" startup profile-picker screen (Phase 5 / DEV-01).
- pymotivaxmc2 / asyncwebostv distribution strategy revisit.

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DEP-01 | No dependency tracks a moving git ref — `openhomedevice` pinned to immutable ref, `pyatv` on immutable ref | See Conditional D-01 and D-02 resolutions below |
| DEP-02 | Documented recovery path for git-sourced deps if upstream disappears | See Recovery section below |
| DEP-03 | Direct PyPI deps carry upper bounds so a breaking major can't be pulled silently | See Upper Bounds section below |

</phase_requirements>

---

## Summary

Phase 1 has two research-conditional decisions and one default policy area. All three are
now resolved with evidence.

**Conditional D-01 (openhomedevice) — RESOLVED: keep the fork, pin to immutable SHA.**
The upstream `bazwilliams/openhomedevice` main branch removed `lxml` in commit `d1794aa20c`
(2025-06-07), but the latest PyPI release is still `2.3.1` (published August 2024) which
retains `lxml>=4.8.0` as a mandatory dependency. No new release has been cut from the
lxml-free main branch. Migrating to PyPI would reintroduce `lxml` and break the ARMv7 build.
Action: keep the fork, change `[tool.uv.sources]` from `branch = "..."` to `rev = "6e862a1022f59a21c57c501dcf040f81d12ebfaf"` (the SHA already recorded in uv.lock). No PyPI migration possible until upstream publishes a post-2.3.1 release without lxml.

**Conditional D-02 (pyatv) — RESOLVED: migrate to PyPI 0.16.1 (or 0.17.0).**
Commit `f75e718bc0bdaf0a3ff06eb00086f781b3f06347` ("deps: Bump protobuf to 30.2") is
present in the `0.16.1` release changelog (confirmed via GitHub API). Both `pyatv==0.16.1`
and `pyatv==0.17.0` ship with protobuf gencode regenerated for `6.31.1`, fully resolving the
original warnings. Recommendation: migrate to `pyatv==0.17.0` (latest stable, Jan 2026).
No API changes affect the `AppleTVDevice` driver's existing imports (`pyatv.scan`, `connect`,
`pyatv.const.PowerState`, `pyatv.interface.DeviceListener/Playing/AudioListener`,
`pyatv.exceptions`). One new requirement: pydantic v2 must be installed (the project already
uses `pydantic>=2.11.0`, so this is satisfied). No mirror needed: `postlund/pyatv` is an
active upstream and the move to PyPI eliminates the recovery risk entirely.

**Primary recommendation:** In `pyproject.toml`, replace the `pyatv` git URL with
`pyatv==0.17.0` and convert `openhomedevice` from branch to SHA rev.

---

## Conditional D-01: openhomedevice — RESOLVED

### Evidence

| Source | Finding | Confidence |
|--------|---------|------------|
| `pip3 index versions openhomedevice` | Latest PyPI release: `2.3.1` | [VERIFIED: PyPI registry] |
| `/tmp/ohd_inspect/openhomedevice-2.3.1/setup.py` | `install_requires = ['async_upnp_client>=0.40', 'lxml>=4.8.0']` — lxml is mandatory in 2.3.1 | [VERIFIED: PyPI sdist] |
| `gh api repos/bazwilliams/openhomedevice/commits` | Commit `d1794aa20c` "Remove lxml dependency from setup.py" merged to upstream main on **2025-06-07** | [VERIFIED: GitHub API] |
| `gh api repos/bazwilliams/openhomedevice/git/refs/tags` | Latest tag is `2.3.1` (commit `d96c7b5d68`, Aug 2024). No tag after `d1794aa20c`. | [VERIFIED: GitHub API] |
| `gh api repos/bazwilliams/openhomedevice/contents/setup.py` | Main branch setup.py has no lxml in `install_requires` but version string still reads `2.2.1` — upstream has not bumped the version or pushed to PyPI. | [VERIFIED: GitHub API] |

### Conclusion

**D-01 branch: NO — upstream has not published an lxml-free release.**

PyPI `2.3.1` retains `lxml>=4.8.0`. The lxml removal is in upstream `main` but unreleased.
Any move to PyPI today would reintroduce lxml and break ARMv7. **Keep the fork.**

### Required Change

Current `pyproject.toml` `[tool.uv.sources]`:
```toml
openhomedevice = { git = "https://github.com/droman42/openhomedevice.git", branch = "remove-lxml-dependency" }
```

Change to immutable SHA (already recorded in `uv.lock`):
```toml
openhomedevice = { git = "https://github.com/droman42/openhomedevice.git", rev = "6e862a1022f59a21c57c501dcf040f81d12ebfaf" }
```

Also update the `dependencies` array entry to use `rev` notation:
```toml
"openhomedevice @ git+https://github.com/droman42/openhomedevice.git@6e862a1022f59a21c57c501dcf040f81d12ebfaf",
```

The locked SHA `6e862a1022f59a21c57c501dcf040f81d12ebfaf` is `openhomedevice 2.2.1` with
one commit on top ("Remove lxml dependency from setup.py") relative to the upstream `2.3.1`
tag. Its only dependency is `async_upnp_client>=0.40` (no lxml). The uv.lock entry confirms:

```
name = "openhomedevice"
version = "2.2.1"
source = { git = "https://github.com/droman42/openhomedevice.git?branch=remove-lxml-dependency#6e862a1022f59a21c57c501dcf040f81d12ebfaf" }
dependencies = [
    { name = "async-upnp-client" },
]
```

No lxml in the transitive tree for `openhomedevice`. ARMv7 constraint is preserved.

### Recovery Path for openhomedevice (DEP-02)

The fork is already under the user's control (`droman42/openhomedevice`). No external mirror
needed — it cannot disappear without user action. The `uv.lock`-committed SHA provides an
additional layer of determinism: even if the branch is force-pushed, `uv sync` will fail
with a clear error rather than silently updating.

**Future migration trigger:** When `bazwilliams/openhomedevice` publishes a release `>=2.4.0`
(or whatever follows `2.3.1`) on PyPI without `lxml`, switch to
`openhomedevice>=2.4.0,<3` and drop the fork. Monitor the upstream repo for new tags.

---

## Conditional D-02: pyatv — RESOLVED

### Evidence

| Source | Finding | Confidence |
|--------|---------|------------|
| `gh api repos/postlund/pyatv/releases` | Latest release: `v0.17.0 "Velma"` (2026-01-21). Also: `v0.16.1 "Uter"` (2025-07-12). | [VERIFIED: GitHub API] |
| `gh api repos/postlund/pyatv/commits/f75e718...` | Commit date: 2025-03-28. Message: "deps: Bump protobuf to 30.2. Re-generate messages to get rid of some warnings. Relates to #2645". | [VERIFIED: GitHub API] |
| `CHANGES.md` at `v0.16.1` | `f75e718b deps: Bump protobuf to 30.2` is listed explicitly in the v0.16.1 changelog. | [VERIFIED: GitHub API — CHANGES.md content] |
| Wheel inspection `pyatv-0.16.1` metadata | `Requires-Dist: protobuf>=6.31.1` | [VERIFIED: PyPI wheel] |
| Wheel inspection `pyatv-0.16.1` protobuf gencode | `CryptoPairingMessage_pb2.py` header: "Protobuf Python Version: 6.31.1" — regenerated at 6.31.1, eliminating the version-mismatch warnings. | [VERIFIED: PyPI wheel] |
| `gh api repos/postlund/pyatv/issues/2645` | Issue title "Protobuf warning". The bug was UserWarning spam when protobuf runtime 6.x was installed but gencode was generated for 5.x. Closed. | [VERIFIED: GitHub API] |
| `pip3 index versions pyatv` | `pyatv (0.17.0)` is current. | [VERIFIED: PyPI registry] |

### Conclusion

**D-02 branch: YES — the protobuf fix is in both pyatv 0.16.1 and 0.17.0.**

Commit `f75e718b` is explicitly listed in the `v0.16.1` changelog. The underlying fix
(regenerating protobuf gencode for 6.31.1) is present in both PyPI releases. The original
bug was a UserWarning (not a crash or API incompatibility) caused by gencode/runtime version
mismatch.

**Recommendation: migrate to `pyatv==0.17.0`** (latest stable, 5 months newer than 0.16.1,
includes Connection fix for tvOS 18.4+ from 0.16.1 and per-device volume from 0.17.0).

### Required Change

Current `pyproject.toml`:
```toml
# dependencies array:
"pyatv @ git+https://github.com/postlund/pyatv.git@f75e718bc0bdaf0a3ff06eb00086f781b3f06347",

# [tool.uv.sources]:
pyatv = { git = "https://github.com/postlund/pyatv.git", rev = "f75e718bc0bdaf0a3ff06eb00086f781b3f06347" }
```

Replace with:
```toml
# dependencies array:
"pyatv==0.17.0",

# [tool.uv.sources]: REMOVE the pyatv entry entirely (it's now a pure PyPI dep)
```

### API Compatibility Assessment for AppleTVDevice Driver

The driver imports (`src/wb_mqtt_bridge/infrastructure/devices/apple_tv/driver.py`):
```python
from pyatv import scan, connect
from pyatv.const import Protocol as ProtocolType, PowerState
from pyatv.interface import DeviceListener, Playing, AudioListener
from pyatv.interface import KeyboardListener  # conditional import
from pyatv.exceptions import AuthenticationError, ConnectionFailedError
from pyatv.const import InputAction  # conditional import
```

v0.17.0 changes relevant to the driver:
- **Pydantic v1 dropped**: project already uses `pydantic>=2.11.0` — no impact.
- **`asyncio.timeout` used for Python 3.11+**: internal change, no driver API impact.
- **Per-device volume added**: new capability, driver doesn't use it — no impact.
- **Guide/Control Center buttons added**: additive, no impact.
- **No breaking changes** to `scan`, `connect`, `PowerState`, `DeviceListener`, `Playing`,
  `AudioListener`, `AuthenticationError`, `ConnectionFailedError`, `InputAction`.

**The driver test (`tests/unit/test_apple_tv_params.py`) verifies mocked behavior and
does not import pyatv directly — it should pass without modification.** The `apple_tv_util.py`
utility script imports `pyatv` directly but is not part of the CI suite.

### Recovery Path for pyatv (DEP-02)

By migrating to PyPI, the recovery concern is eliminated. PyPI packages are immutable
(a given `pyatv==0.17.0` wheel is forever available). No mirror needed.

---

## Standard Stack

### Core — no new packages installed

This phase edits `pyproject.toml` and regenerates `uv.lock`. No new runtime dependencies.

### uv Mechanics for This Phase

**Changing a git source from branch to SHA rev** (`[tool.uv.sources]`):

```toml
# Before (moving branch — non-reproducible):
openhomedevice = { git = "https://github.com/droman42/openhomedevice.git", branch = "remove-lxml-dependency" }

# After (immutable SHA — reproducible):
openhomedevice = { git = "https://github.com/droman42/openhomedevice.git", rev = "6e862a1022f59a21c57c501dcf040f81d12ebfaf" }
```

uv records the full `?rev=SHA#SHA` fragment in `uv.lock`, which is already present:
```
source = { git = "...?branch=remove-lxml-dependency#6e862a1022f59a21c57c501dcf040f81d12ebfaf" }
```
Switching to `rev =` causes uv to record `?rev=SHA#SHA` instead — deterministic from both
sides. [VERIFIED: current uv.lock content]

**Removing a git source and switching to PyPI** (`pyatv`):

1. Remove the `pyatv = { git = ... }` line from `[tool.uv.sources]`
2. Change the `dependencies` entry from git URL to `"pyatv==0.17.0"`
3. Run `uv lock` — uv resolves from PyPI and writes a new lock entry with
   `source = { registry = "https://pypi.org/simple" }`

**Regenerating `uv.lock` deterministically:**

```bash
uv lock          # regenerate lock from pyproject.toml
uv sync          # install from regenerated lock
```

`uv lock` is deterministic given identical `pyproject.toml` and PyPI index state. The
lock file records exact versions + hashes for all packages. [VERIFIED: uv 0.6.14 on system]

---

## Package Legitimacy Audit

> slopcheck was unavailable at research time. All packages are marked based on registry age
> and known provenance. No new packages are being installed in this phase — this is a
> constraint tightening and source-switching exercise on existing deps.

| Package | Registry | Status | Disposition |
|---------|----------|--------|-------------|
| pyatv 0.17.0 | PyPI | Established project, 8+ years, active maintainer (postlund), 0.17.0 released Jan 2026 | Approved — migrating from git pin to this release |
| openhomedevice 2.3.1 | PyPI | NOT being used (lxml constraint); fork SHA retained | N/A — fork SHA kept |

*No new packages installed. No slopcheck concerns.*

---

## Upper Bounds Policy (DEP-03)

### Current State

From `pyproject.toml` `dependencies`:

```toml
"fastapi>=0.103.0",          # uncapped
"uvicorn>=0.23.2",           # uncapped
"aiomqtt>=1.0.0",            # uncapped — NOTE: 2.x is available (may have breaking changes)
"pydantic>=2.11.0",          # uncapped
"python-dotenv>=1.0.0",      # uncapped
"typing_extensions>=4.7.0",  # uncapped
"paho-mqtt>=1.6.1",          # uncapped — NOTE: 2.x is available (breaking changes in 2.0)
"broadlink>=0.18.0",         # uncapped
"websockets>=15.0.1",        # uncapped — fast-moving major versions
"pyOpenSSL>=23.2.0",         # uncapped
"aiohttp>=3.8.1",            # uncapped
"httpx",                     # COMPLETELY unconstrained — no lower or upper bound
"requests",                  # COMPLETELY unconstrained — no lower or upper bound
"pyyaml>=6.0",               # uncapped
"jsonschema>=4.4.0",         # uncapped
"aiosqlite>=0.19.0",         # uncapped
"psutil>=7.0.0",             # uncapped
```

### Recommended Bounds

Latest versions verified via `pip3 index versions` on 2026-05-20. [VERIFIED: PyPI registry]

| Package | Current | Latest | Recommended Constraint | Notes |
|---------|---------|--------|------------------------|-------|
| fastapi | `>=0.103.0` | `0.136.1` | `>=0.103.0,<1` | 1.0 not yet released; cap at major |
| uvicorn | `>=0.23.2` | `0.47.0` | `>=0.23.2,<1` | Still 0.x; cap at 1 |
| aiomqtt | `>=1.0.0` | `2.5.1` | `>=2.0,<3` | **CORRECTED: uv.lock already locks 2.3.2 — cap at `<3`, NOT `<2` (a `<2` cap would force a downgrade of the installed 2.x). See A3 (resolved).** |
| pydantic | `>=2.11.0` | `2.13.4` | `>=2.11.0,<3` | v3 not released; standard cap |
| python-dotenv | `>=1.0.0` | (stable 1.x) | `>=1.0.0,<2` | Stable 1.x series |
| typing_extensions | `>=4.7.0` | (stable 4.x) | `>=4.7.0,<5` | Rarely breaking |
| paho-mqtt | `>=1.6.1` | `2.1.0` | `>=1.6.1,<2` | **2.x has breaking API changes (callback signatures); cap at 1.x** |
| broadlink | `>=0.18.0` | `0.19.0` | `>=0.18.0,<1` | Still 0.x |
| websockets | `>=15.0.1` | `16.0` | `>=15.0.1,<16` | Fast-moving majors with deprecation removals; cap at current |
| pyOpenSSL | `>=23.2.0` | `26.2.0` | `>=23.2.0,<27` | Cap at next major |
| aiohttp | `>=3.8.1` | `3.13.5` | `>=3.8.1,<4` | Still 3.x |
| httpx | (none) | `0.28.1` | `>=0.27.0,<1` | Add lower + upper; 1.0 not released |
| requests | (none) | `2.34.2` | `>=2.30.0,<3` | Add lower + upper; stable 2.x |
| pyyaml | `>=6.0` | `6.0.3` | `>=6.0,<7` | Cap at major |
| jsonschema | `>=4.4.0` | `4.26.0` | `>=4.4.0,<5` | Cap at major |
| aiosqlite | `>=0.19.0` | `0.22.1` | `>=0.19.0,<1` | Still 0.x |
| psutil | `>=7.0.0` | `7.2.2` | `>=7.0.0,<8` | Cap at major |

**Notable risks at current lower bounds without upper bounds:**
- `aiomqtt>=1.0.0` — 2.x renamed/restructured the client API. The repo is ALREADY on 2.3.2 (uv.lock), so the working cap is `>=2.0,<3` (not `<2`).
- `paho-mqtt>=1.6.1` — 2.x changed callback signatures (on_connect, on_message) and connection
  methods in a backwards-incompatible way. Without a cap, `pip install` could pull 2.x.
- `websockets>=15.0.1` — jumped from 14 to 15 to 16 rapidly; each major removes deprecated APIs.

---

## Architecture Patterns

### pyproject.toml `[tool.uv.sources]` — immutable vs mutable refs

```toml
[tool.uv.sources]
# MUTABLE (tracks moving branch head — avoid):
openhomedevice = { git = "https://github.com/...", branch = "remove-lxml-dependency" }

# IMMUTABLE (locked SHA — reproducible):
openhomedevice = { git = "https://github.com/...", rev = "6e862a1022f59a21c57c501dcf040f81d12ebfaf" }

# PYPI (preferred when available — immutable by definition):
# No entry needed; normal dependency spec in [project.dependencies] is used
```

uv resolves `rev =` as a full commit SHA. Tags are also immutable:
```toml
openhomedevice = { git = "https://github.com/...", tag = "2.4.0" }
```

A tag can be force-moved; a SHA cannot. The SHA form is strictly more reproducible.
[VERIFIED: uv.lock current content shows SHA recorded in fragment]

### Git→PyPI Migration Precedent

From `pyproject.toml` comments:
```toml
"pymotivaxmc2==0.6.7",  # Migrated from Git to PyPI
"asyncwebostv==0.2.7",  # Migrated from Git to PyPI
```

The same playbook applies to `pyatv`: remove git URL, remove `[tool.uv.sources]` entry,
add PyPI version specifier, run `uv lock`. [CITED: pyproject.toml:38-39]

### Recommended uv.lock Workflow

```bash
# After editing pyproject.toml:
uv lock            # regenerate lock
uv sync            # install from new lock (verify no errors)
pytest tests/ -x   # confirm test suite is green
git add pyproject.toml uv.lock
git commit -m "deps: harden dependency pins (DEP-01/02/03)"
```

---

## Recovery Path Runbook (DEP-02)

For the committed `uv.lock` as pin-of-record:

```bash
# Restore exact environment from lock (normal case):
uv sync --frozen          # installs exactly what uv.lock specifies; refuses to update

# If a git source disappears (e.g., fork deleted):
# 1. Clone the repo from any available copy (local cache, another fork)
# 2. Push to a new location (e.g., github.com/droman42/<name>)
# 3. Update [tool.uv.sources] rev to the same SHA in the new location
# 4. Run: uv lock && uv sync

# uv's local cache (~/.cache/uv/git-v0/) may contain the repo even after upstream deletion.
# The SHA in uv.lock guarantees you get exactly the same code even from a re-cloned source.
```

**Per-source recovery actions after Phase 1:**

| Source | After Phase 1 | Recovery Action |
|--------|---------------|-----------------|
| `openhomedevice` fork (SHA) | User controls `droman42/openhomedevice`; SHA immutable | None needed — user owns the repo |
| `pyatv==0.17.0` | PyPI — immutable wheel | None needed — PyPI packages don't disappear |
| All PyPI deps | Exact versions in `uv.lock` | `uv sync --frozen` restores environment |

**Mirror requirement (from CONTEXT.md D-02):** Mirror `postlund/pyatv` only if it stays on
a commit pin. After Phase 1, `pyatv` moves to PyPI — **no mirror needed**.

---

## Common Pitfalls

### Pitfall 1: Leaving PEP 508 git URL in `dependencies` after adding `[tool.uv.sources]`

**What goes wrong:** uv uses `[tool.uv.sources]` to override the source for a package. If
the `dependencies` array still has a git URL (`pkg @ git+https://...`) AND `[tool.uv.sources]`
has a different entry, behavior is undefined / uv may error.

**How to avoid:** When switching `pyatv` to PyPI:
1. Change `"pyatv @ git+https://..."` in `dependencies` to `"pyatv==0.17.0"`.
2. Remove `pyatv = { git = ... }` from `[tool.uv.sources]`.
Both edits must happen together.

### Pitfall 2: Forgetting `uv sync` after `uv lock`

**What goes wrong:** `uv lock` regenerates `uv.lock` but does not install. If you run
`pytest` before `uv sync`, the old (git-sourced) package is still installed in the venv.

**How to avoid:** Always `uv sync` after `uv lock` in this workflow.

### Pitfall 3: `rev` SHA in uv.lock already matches — no lock change observed

**What goes wrong:** The existing `uv.lock` already records the SHA
`6e862a1022f59a21c57c501dcf040f81d12ebfaf` for openhomedevice (because uv records the
resolved SHA regardless of whether `branch =` or `rev =` was used in the source). After
changing `branch =` to `rev =` in `[tool.uv.sources]`, running `uv lock` may produce no
diff in `uv.lock` — this is **expected and correct**.

**How to confirm the change worked:** The `[tool.uv.sources]` entry in `pyproject.toml` will
show `rev =` instead of `branch =`. That is the only required change for DEP-01 compliance.

### Pitfall 4: async_timeout dep on Python 3.11+

**What goes wrong:** `pyatv 0.16.x` wheel has `async-timeout>=4.0.2; python_version < "3.11"`
as a conditional dep. `pyatv 0.17.0` drops this entirely. On Python 3.11, this is correct
behavior — `asyncio.timeout` is built-in. No action needed, but note that the `uv.lock`
will lose an `async-timeout` entry after upgrading to 0.17.0.

### Pitfall 5: paho-mqtt 2.x callback incompatibility

**What goes wrong:** If the `paho-mqtt>=1.6.1` cap is not added, future `uv sync` runs
could pull paho-mqtt 2.x, which changed `on_connect`, `on_message`, and `client.connect()`
signatures. The MQTT client (`infrastructure/mqtt/client.py`) uses paho callbacks.

**How to avoid:** Add `paho-mqtt>=1.6.1,<2` as the upper bound for this package.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 7.0.0+ (configured in pyproject.toml) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/ -x --tb=short` |
| Full suite command | `pytest tests/ -v --tb=short` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DEP-01 | openhomedevice pin is immutable SHA | manual verify | `grep 'rev.*6e862a1' pyproject.toml` | N/A |
| DEP-01 | pyatv resolves from PyPI (not git) | manual verify | `grep 'pyatv==0.17.0' pyproject.toml` | N/A |
| DEP-01 | AuralicDevice driver tests pass after re-pin | unit (mocked) | `pytest tests/devices/test_auralic_device.py -v` | exists |
| DEP-01 | AppleTVDevice driver tests pass after re-pin | unit (mocked) | `pytest tests/unit/test_apple_tv_params.py -v` | exists |
| DEP-02 | uv.lock committed and contains exact SHA refs | manual verify | `git diff HEAD uv.lock` | N/A |
| DEP-03 | All direct deps have upper bounds | manual verify | `grep -E '>=.*,<' pyproject.toml` | N/A |

### Phase Gate

Full suite (225 pass baseline) must stay green on amd64 after all changes:
```bash
pytest tests/ -v --tb=short
```

No new test files needed — existing device tests are the primary gate for DEP-01.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| uv | `uv lock`, `uv sync` | Yes | 0.6.14 | None (required) |
| Python 3.11+ | Runtime | Yes | system Python 3.11 | None |
| GitHub API access | Verifying remote SHAs | Yes | gh CLI available | Direct web inspection |

---

## Open Questions (RESOLVED)

All three questions below are closed for Phase 1 planning. Q1 and Q2 are advisory
monitoring notes (no execution impact); Q3 is resolved with a corrected constraint.

1. **openhomedevice upstream release timing** — *advisory, no Phase 1 impact.*
   - What we know: upstream removed lxml from main on 2025-06-07; no new PyPI release yet.
   - Resolution: Keep the fork pinned to the SHA this phase. Track upstream
     `bazwilliams/openhomedevice` for a future lxml-free release; the migration trigger is
     documented in the recovery runbook / ADR 0006 (plan 01-03), not a blocker now.

2. **pyatv 0.17.0 pydantic version floor** — *advisory, low risk.*
   - What we know: 0.17.0 requires `pydantic>=2.0.0` (compatible — repo is on pydantic 2.x).
   - Resolution: The driver uses pyatv for control only and receives plain Python types
     (`PowerState` enum, `Playing` object). Covered by the driver mock tests in plan 01-02.

3. **aiomqtt 2.x compatibility** — **RESOLVED.**
   - A3 check run: `uv.lock` locks `aiomqtt==2.3.2` — the project is ALREADY on 2.x and
     green (225 tests pass), so no 1.x-specific API is in use.
   - Resolution: cap at `>=2.0,<3` (NOT `<2`, which would force a downgrade of the working
     2.3.2). The Upper Bounds table and plan 01-01 Task 2 both reflect this.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | pyatv 0.17.0 has no breaking changes for the existing `AppleTVDevice` driver imports | D-02 resolution | Driver import errors at test time; would need API migration |
| A2 | The protobuf UserWarning (issue #2645) was the original "protobuf contradiction" bug that motivated the commit pin, not a harder incompatibility | D-02 resolution | If there was a harder bug, it may or may not be in 0.17.0 — tests would catch it |
| A3 | ~~aiomqtt `>=1.0.0` currently resolves to a 1.x version~~ — **DISPROVEN/RESOLVED**: uv.lock locks `aiomqtt==2.3.2` | Upper bounds | N/A — cap corrected to `>=2.0,<3` |

**A3 check (DONE):** `grep "aiomqtt" uv.lock` → `version = "2.3.2"`. The repo is already on 2.x
and green, so the cap is `>=2.0,<3` (a `<2` cap would force a downgrade). Applied in the
Upper Bounds table and plan 01-01 Task 2.

---

## Sources

### Primary (HIGH confidence)
- PyPI registry (`pip3 index versions`) — version data for all packages [VERIFIED: PyPI registry]
- GitHub API (`gh api repos/postlund/pyatv/...`) — release changelog, commit ancestry [VERIFIED: GitHub API]
- GitHub API (`gh api repos/bazwilliams/openhomedevice/...`) — commit history, setup.py content [VERIFIED: GitHub API]
- PyPI wheel inspection (`pyatv-0.16.1-py3-none-any.whl`, `pyatv-0.17.0-py3-none-any.whl`) — metadata and gencode verification [VERIFIED: PyPI sdist/wheel]
- PyPI sdist inspection (`openhomedevice-2.3.1.tar.gz`) — setup.py lxml dep confirmed [VERIFIED: PyPI sdist]
- `uv.lock` — locked SHA `6e862a1022f59a21c57c501dcf040f81d12ebfaf` for openhomedevice [VERIFIED: uv.lock content]
- `pyproject.toml` — current dependency declarations [CITED: pyproject.toml]
- GitHub API (`gh api repos/postlund/pyatv/issues/2645`) — protobuf bug nature confirmed as UserWarning [VERIFIED: GitHub API]

### Tertiary (LOW confidence)
- pyatv API compatibility assessment: based on reading driver imports + release notes, not running the test suite against 0.17.0 [ASSUMED: A1]

---

## Metadata

**Confidence breakdown:**
- Conditional D-01 (openhomedevice): HIGH — PyPI 2.3.1 wheel inspected directly; upstream commit log verified
- Conditional D-02 (pyatv): HIGH — commit f75e718 is in v0.16.1 changelog; wheel gencode version verified
- Upper bounds policy: HIGH — all versions verified against PyPI registry
- API compatibility for pyatv upgrade: MEDIUM — based on changelog + driver import review, not test execution

**Research date:** 2026-05-20
**Valid until:** 2026-08-20 (3 months — stable domain; re-check if upstream openhomedevice
publishes a new release tag or if pyatv releases 0.18.0)
