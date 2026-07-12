> **ARCHIVED 2026-07-12 (ADR class retired; the POLICY LIVES ON).** The four pinning
> rules moved verbatim in substance to **`CONTRIBUTING.md` → "Dependency policy"**, which
> is now the normative home (kept current there; this file is frozen at its 2026-07-10
> amendment, including the then-open pyatv mirror gap). Recovery runbook:
> `docs/design/maintenance/dependency-recovery.md`.

# ADR 0006 — Dependency pinning policy: immutable git refs, bounded PyPI, lockfile as record

- **Status:** Accepted · **Amended 2026-07-10 (REL-4 docs pass)**
- **Date:** 2026-05-20

> **Amendment 2026-07-10 — the four rules stand; concrete facts below have moved, and one
> Rule 2 compliance gap is now open.** This ADR is an immutable record; the body is kept as
> written and corrected here.
> - **Rule 1 versions (stale examples):** the owner's PyPI libraries are now
>   `pymotivaxmc2==0.7.0` and `asyncwebostv==0.4.0` (were 0.6.7 / 0.2.7). Still exact `==` pins —
>   rule intact.
> - **Rule 2 current exception (moved):** `openhomedevice` is now pinned at fork SHA
>   `819b16102fb71e68c4f593af4d49c66a344d300a` (upstream 2.3.1 minus lxml, plus the
>   HardwareConfig-halt branch — DRV-14, 2026-07-07). Same owner-controlled fork, same rationale.
> - **Rule 2 gap (open — the "only remaining git source" claim is now false):** `pyatv` is again
>   a git source — SHA-pinned (`postlund/pyatv@9177803…`, immutable, so the reproducibility half
>   holds) but **not** mirrored under the owner's account, which Rule 2 requires for repos the
>   owner does not control. The build is reproducible today; the residual risk is an upstream
>   force-push/deletion. The mirror-vs-accepted-exception decision is tracked as **OPS-19**
>   (deferred). A dev-only git dep `py-dev-gates@v0.1.1` is tag-pinned (owner-controlled;
>   noted, not urgent).

## Context

The project depends on a mix of the author's own libraries (distributed via PyPI), third-party
libraries sourced from git (at the time, tracking a moving branch or bare commit), and a broad
set of direct PyPI dependencies — none of which carried upper-bound constraints.

Before Phase 1 (2026-05-20), the build had three reproducibility gaps:

1. `openhomedevice` was pinned to a moving git branch (`remove-lxml-dependency`). A branch
   head can be force-pushed or deleted, silently changing what gets installed.
2. `pyatv` was pinned to a bare upstream commit SHA (`f75e718...`) on a repo the author does
   not own. A force-push or repo deletion would break the build with no recovery path.
3. Direct PyPI dependencies (17 packages) carried no upper bounds. A breaking major version
   could be pulled silently by a future `uv sync`.

The Phase 1 dependency hardening work (plans 01-01 through 01-03) resolved all three gaps and
produced a durable policy generalizing those specific decisions. That policy is recorded here
so future dependency decisions are consistent and the reasoning is not implicit in
`pyproject.toml` alone.

## Decision

The following four rules govern how dependencies are pinned in this project:

### Rule 1 — Personal libraries: PyPI exact-pin

Libraries authored and published by the project owner (currently `pymotivaxmc2==0.6.7` and
`asyncwebostv==0.2.7`) are distributed via PyPI and pinned with an exact `==` specifier.
These are already reproducible; no git source is needed.

### Rule 2 — Third-party git sources: immutable ref only

Any dependency that cannot yet move to PyPI and must come from a git source must be pinned to
an **immutable ref** — a full commit SHA (`rev = "..."` in `[tool.uv.sources]`). A moving
branch (`branch = "..."`) is prohibited because the resolved code changes without any change
to `pyproject.toml`.

Additionally:
- If the source repository is **not** under the project owner's control, it must be mirrored
  under the owner's GitHub account so the build survives upstream deletion or force-push.
- If an acceptable PyPI release becomes available, migrate to it (Rule 3) and remove the git
  source.

**Current exception:** `openhomedevice` is pinned to the author's fork at SHA
`6e862a1022f59a21c57c501dcf040f81d12ebfaf` (openhomedevice 2.2.1, lxml-free). The fork
exists solely because upstream PyPI release 2.3.1 declares `lxml>=4.8.0` as a mandatory
dependency, which does not build on ARMv7 (the Wirenboard 7 deploy target). The fork is
already under the owner's control, so no separate mirror is required. See
`docs/maintenance/dependency-recovery.md` for the full recovery runbook and the migration
trigger.

### Rule 3 — Direct PyPI dependencies: lower and next-major upper bound

Every direct PyPI dependency must carry both a lower bound and an upper bound that caps the
next major version, e.g. `>=2.11.0,<3`. An unconstrained dependency allows a future breaking
major to be pulled silently by `uv sync`.

The upper bound is the next integer major, not the current exact version, to allow minor and
patch updates within the pinned series to flow through via a lockfile refresh.

### Rule 4 — The committed `uv.lock` is the pin-of-record

The `uv.lock` file committed to the repository is the single authoritative record of all
resolved versions (direct and transitive). It records exact versions, content hashes, and
source URLs.

The deterministic restore command is:

```bash
uv sync --frozen
```

`--frozen` installs exactly what `uv.lock` specifies and refuses any resolution update.
`uv sync` (without `--frozen`) is not the recovery command — it may silently re-resolve.

`uv lock` is used to regenerate the lockfile after intentional changes to `pyproject.toml`
and must be followed by `uv sync` and a full test run before committing.

## Consequences

- The build is reproducible: given `uv.lock` and any available package sources, `uv sync
  --frozen` produces an identical environment.
- A breaking upstream change (force-push, deletion, new major release) cannot silently
  corrupt the environment — it will cause a clear failure rather than a silent divergence.
- Residual risk: loss of the `droman42/openhomedevice` fork (the only remaining git source)
  can break the build. The recovery procedure in `docs/maintenance/dependency-recovery.md`
  addresses this: the SHA in `uv.lock` plus uv's local cache (`~/.cache/uv/git-v0/`) or any
  clone provide the source for a re-push.
- As upstream `bazwilliams/openhomedevice` releases an lxml-free PyPI package (>=2.4.0), the
  fork should be dropped and openhomedevice migrated to a bounded PyPI specifier per Rule 3.
  This eliminates the last residual git source.

## Alternatives considered

**Always mirror third-party git sources regardless of ownership.** Rejected as over-engineering
when the source is already under the owner's control (`droman42/openhomedevice`). Mirror
requirement applies only to repos the owner does not control.

**Use git tags instead of SHAs for immutable refs.** Tags can be force-moved; SHAs cannot.
SHAs are strictly more reproducible. Tags may be used as a human-readable alias alongside a
SHA but cannot replace it as the reproducibility guarantee.

**Exact-pin all PyPI dependencies (not just lower + upper bounds).** Exact `==` pins for
transitive deps are already captured by `uv.lock`. Exact-pinning direct deps in `pyproject.toml`
adds churn (every patch release requires a manual edit) without adding safety over the
lower+upper bound + lockfile approach.
