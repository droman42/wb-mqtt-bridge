# Dependency Recovery Runbook

**Purpose:** How to restore the build if a dependency source disappears or the
environment needs to be reconstructed from scratch.

---

## 1. Pin-of-Record: `uv.lock`

The committed `uv.lock` file is the single authoritative record of the resolved
dependency graph. It captures exact versions, source URLs, and content hashes for
all packages (direct and transitive).

**To restore the exact environment deterministically:**

```bash
uv sync --frozen
```

`--frozen` instructs uv to install exactly what `uv.lock` specifies and to refuse
any resolution update. It fails with a clear error if the lock file and
`pyproject.toml` are out of sync, rather than silently re-resolving.

Never use `uv sync` alone (without `--frozen`) as the recovery command — it allows
uv to update the lock and may diverge from the pinned environment.

---

## 2. Per-Source Recovery Summary

| Source | After Phase 1 state | Recovery action required |
|--------|---------------------|--------------------------|
| `openhomedevice` (user fork) | `droman42/openhomedevice`, immutable SHA `6e862a1022f59a21c57c501dcf040f81d12ebfaf` | See section 3 — re-push from any clone if fork is lost |
| `pyatv==0.17.0` | PyPI immutable wheel | None — PyPI packages do not disappear; `uv sync --frozen` restores |
| All other direct + transitive deps | Exact versions in `uv.lock` | `uv sync --frozen` restores |

---

## 3. "Git Source Disappeared" Procedure

Applies to: the `droman42/openhomedevice` fork (the only residual git source after
Phase 1). If the fork is deleted or becomes inaccessible, follow these steps.

### Step 1 — Locate the source code

Try, in order:

1. **Your local checkout** — any local directory where the fork was previously cloned.
2. **uv's git cache** — `~/.cache/uv/git-v0/` may retain a full clone of the repo
   even after the upstream was deleted, keyed by URL. Browse subdirectories to find
   the `openhomedevice` tree.
3. **Another fork** — search GitHub for forks of `bazwilliams/openhomedevice` that
   are still accessible and contain the SHA.

Verify you have the correct commit:

```bash
git log --oneline | grep 6e862a1
```

### Step 2 — Re-publish to a new location

Push the repository (with its full history) to a new GitHub repo under your account:

```bash
git remote set-url origin https://github.com/droman42/openhomedevice-backup.git
git push origin --all
git push origin --tags
```

Or create a fresh repo on GitHub and push to it:

```bash
git remote add backup https://github.com/droman42/<new-repo-name>.git
git push backup --all
```

### Step 3 — Update `pyproject.toml` to point to the new URL

Edit `pyproject.toml` — two places:

1. The `dependencies` array entry:
   ```toml
   "openhomedevice @ git+https://github.com/droman42/<new-repo-name>.git@6e862a1022f59a21c57c501dcf040f81d12ebfaf",
   ```

2. The `[tool.uv.sources]` entry:
   ```toml
   openhomedevice = { git = "https://github.com/droman42/<new-repo-name>.git", rev = "6e862a1022f59a21c57c501dcf040f81d12ebfaf" }
   ```

The SHA `6e862a1022f59a21c57c501dcf040f81d12ebfaf` must remain **unchanged**.
This guarantees you get exactly the same code (openhomedevice 2.2.1, lxml-free)
regardless of the hosting URL.

### Step 4 — Regenerate the lockfile and verify

```bash
uv lock
uv sync
pytest tests/ -x --tb=short
```

`uv lock` will produce a new `uv.lock` with the updated URL but the same SHA fragment.
Commit `pyproject.toml` and `uv.lock` together.

---

## 4. Why the openhomedevice Fork Exists (and When to Drop It)

The fork `droman42/openhomedevice` exists for **one reason only**: upstream
`bazwilliams/openhomedevice` PyPI release `2.3.1` declares `lxml>=4.8.0` as a
mandatory dependency. `lxml` does not build on ARMv7 (the Wirenboard 7 deploy target),
making the upstream PyPI package unusable on-device.

The fork's `remove-lxml-dependency` branch removes `lxml` from `setup.py`. The
immutable SHA `6e862a1022f59a21c57c501dcf040f81d12ebfaf` captures openhomedevice
`2.2.1` at that exact commit — its sole dependency is `async_upnp_client>=0.40`.
No `lxml` in the transitive tree. The ARMv7 constraint is preserved.

**Migration trigger:** When `bazwilliams/openhomedevice` publishes a release `>=2.4.0`
on PyPI that does **not** declare `lxml` as a dependency, migrate to PyPI:

1. Remove the git entry from `[tool.uv.sources]`.
2. Change the `dependencies` entry to `openhomedevice>=2.4.0,<3`.
3. Run `uv lock && uv sync`.
4. Verify the ARMv7 build remains lxml-free: `uv pip show openhomedevice` should show
   no `lxml` requirement.
5. Drop the fork (`droman42/openhomedevice`) once the migration is confirmed.

Monitor: check `https://pypi.org/project/openhomedevice/` for releases newer than
`2.3.1` (the last lxml-carrying release as of 2026-05-20).

See also: the dependency policy in `CONTRIBUTING.md` (ex-ADR 0006, archived at `docs/archive/adr/`) for the durable
policy governing these decisions.
