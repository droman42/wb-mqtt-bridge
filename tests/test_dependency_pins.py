"""Pin-guard tests: assert the supply-chain guarantees introduced in Phase 1.

These tests act as a permanent regression gate.  They will FAIL the build if any
future change reintroduces:

  - A moving ``branch =`` git ref in ``[tool.uv.sources]``         (DEP-01)
  - An ``lxml`` dependency on the openhomedevice path              (ARMv7 constraint)
  - An unbounded direct PyPI dependency specifier                  (DEP-03)
  - A removal of the immutable openhomedevice SHA or the PyPI pyatv pin

The tests are pure-unit (no I/O other than reading the two checked-in config
files). They are CWD-independent because they resolve paths relative to *this*
file's location.
"""
import re
import tomllib
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _repo_root() -> Path:
    """Return the repository root (the directory that contains pyproject.toml)."""
    # This file lives at tests/test_dependency_pins.py, so the repo root is one
    # level up.
    return Path(__file__).parent.parent


def _load_pyproject() -> dict:
    root = _repo_root()
    with open(root / "pyproject.toml", "rb") as fh:
        return tomllib.load(fh)


def _lock_text() -> str:
    root = _repo_root()
    return (root / "uv.lock").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Test 1 — no moving git ref (DEP-01)
# ---------------------------------------------------------------------------


def test_no_moving_branch_ref_in_uv_sources():
    """pyproject.toml [tool.uv.sources] must not contain any ``branch =`` entry.

    A ``branch =`` pin tracks a mutable pointer; a force-push or branch deletion
    makes the build unrecoverable.  All git sources must use ``rev =`` (immutable
    commit SHA) or ``tag =`` (immutable tag).
    """
    data = _load_pyproject()
    sources: dict = data.get("tool", {}).get("uv", {}).get("sources", {})

    offenders = [
        f"{pkg}: {spec}"
        for pkg, spec in sources.items()
        if "branch" in spec
    ]

    assert not offenders, (
        "Found moving git branch references in [tool.uv.sources] — "
        "replace each with an immutable 'rev =' SHA or 'tag =':\n"
        + "\n".join(f"  {o}" for o in offenders)
    )


# ---------------------------------------------------------------------------
# Test 2 — openhomedevice uses immutable SHA; pyatv is on PyPI (not git)
# ---------------------------------------------------------------------------


def test_openhomedevice_pinned_to_immutable_sha():
    """openhomedevice must be pinned to the immutable SHA 6e862a1022f59a21c57c501dcf040f81d12ebfaf.

    The fork exists exclusively to remove lxml (ARMv7 constraint).  Migrating to
    a different SHA requires a conscious decision, not an accidental branch-track.
    """
    expected_sha = "6e862a1022f59a21c57c501dcf040f81d12ebfaf"
    data = _load_pyproject()
    sources: dict = data.get("tool", {}).get("uv", {}).get("sources", {})

    assert "openhomedevice" in sources, (
        "openhomedevice is missing from [tool.uv.sources] — it must remain on the "
        "immutable SHA fork to keep lxml off the ARMv7 build."
    )

    spec = sources["openhomedevice"]
    assert spec.get("rev") == expected_sha, (
        f"openhomedevice rev must be '{expected_sha}' (immutable SHA); "
        f"got: {spec.get('rev')!r}.  Update this test only if the fork SHA is "
        "intentionally advanced."
    )


def test_pyatv_not_on_git_source():
    """pyatv must NOT appear in [tool.uv.sources]; it must be a plain PyPI dep.

    The git-commit pin (postlund/pyatv@f75e718) was required because the protobuf
    fix was unreleased.  Once it shipped in pyatv 0.17.0 the dep was migrated to
    PyPI.  Reintroducing a git source (especially upstream ``postlund/pyatv``)
    would put us back on an ephemeral ref we cannot control.
    """
    data = _load_pyproject()
    sources: dict = data.get("tool", {}).get("uv", {}).get("sources", {})

    assert "pyatv" not in sources, (
        "pyatv must be installed from PyPI, not from a git source.  "
        "Remove it from [tool.uv.sources] and keep the 'pyatv==X.Y.Z' PyPI pin."
    )

    # Belt-and-suspenders: the dependencies array must not reference a git URL for pyatv.
    deps: list[str] = data.get("project", {}).get("dependencies", [])
    git_pyatv = [d for d in deps if "pyatv" in d and "git+" in d]
    assert not git_pyatv, (
        "Found a git+ URL for pyatv in [project].dependencies: "
        + ", ".join(git_pyatv)
        + ".  Use the PyPI exact-pin form 'pyatv==X.Y.Z' instead."
    )


# ---------------------------------------------------------------------------
# Test 3 — pyatv exact PyPI pin is present
# ---------------------------------------------------------------------------


def test_pyatv_exact_pypi_pin_present():
    """pyproject.toml [project].dependencies must contain 'pyatv==0.17.0' (exact PyPI pin).

    The exact pin was chosen after verifying the protobuf fix shipped in 0.16.1+.
    Bumping to a different exact pin is fine; removing the pin or loosening it
    to a range without updating this test is not.
    """
    data = _load_pyproject()
    deps: list[str] = data.get("project", {}).get("dependencies", [])

    pyatv_entries = [d for d in deps if re.match(r"\s*pyatv", d)]
    assert pyatv_entries, (
        "pyatv is missing from [project].dependencies.  "
        "Add 'pyatv==0.17.0' (or a new exact pin after a conscious upgrade)."
    )

    exact_pins = [d for d in pyatv_entries if "==" in d]
    assert exact_pins, (
        "pyatv in [project].dependencies is not an exact pin (==).  "
        f"Found: {pyatv_entries}.  Use 'pyatv==X.Y.Z'."
    )


# ---------------------------------------------------------------------------
# Test 4 — openhomedevice is lxml-free in uv.lock (ARMv7 hard constraint)
# ---------------------------------------------------------------------------


def test_openhomedevice_lxml_free_in_lock():
    """uv.lock must not list lxml as a dependency of openhomedevice (ARMv7 constraint).

    lxml does not build on ARMv7 (the Wirenboard deploy target).  The fork exists
    specifically to remove this dependency.  Any upgrade that re-introduces lxml
    on the openhomedevice path will break the ARMv7 build.
    """
    lock = _lock_text()

    # Locate the openhomedevice package block.
    # uv.lock uses TOML-ish blocks separated by blank lines; each block starts
    # with [[package]] and ends before the next [[package]].
    blocks = re.split(r"\n(?=\[\[package\]\])", lock)
    oh_block = next(
        (b for b in blocks if re.search(r'name\s*=\s*"openhomedevice"', b)),
        None,
    )

    assert oh_block is not None, (
        "Could not find 'name = \"openhomedevice\"' in uv.lock — "
        "has the package been removed or renamed?"
    )

    assert "lxml" not in oh_block, (
        "lxml appeared in the openhomedevice block in uv.lock.  "
        "The ARMv7 (Wirenboard) build forbids lxml.  "
        "Investigate why the dep was reintroduced and fix the fork."
    )


def test_lxml_not_in_lock_at_all():
    """uv.lock must contain no top-level 'name = \"lxml\"' package entry.

    Even if openhomedevice's own block is clean, lxml could sneak in via another
    transitive path.  This test catches that scenario.
    """
    lock = _lock_text()

    # Match the exact TOML key pattern so we don't false-positive on strings like
    # "no-lxml-dependency" in a git URL comment.
    has_lxml = bool(re.search(r'^name\s*=\s*"lxml"', lock, re.MULTILINE))

    assert not has_lxml, (
        "Found 'name = \"lxml\"' in uv.lock — lxml must not appear anywhere "
        "in the resolved dependency tree (ARMv7 hard constraint)."
    )


# ---------------------------------------------------------------------------
# Test 5 — every direct PyPI dep carries an upper bound (DEP-03)
# ---------------------------------------------------------------------------


_EXACT_PINNED_PKGS = frozenset({"pymotivaxmc2", "asyncwebostv"})
"""Packages whose maintainer is the repo owner; they use exact == pins by design."""


def _pkg_name_from_dep(dep: str) -> str:
    """Extract the bare package name from a PEP-508 dependency string.

    Handles:
      "fastapi>=0.103.0,<1"   → "fastapi"
      "pyatv==0.17.0"          → "pyatv"
      "openhomedevice @ git+…" → "openhomedevice"
    """
    return re.split(r"[>=<!@\s\[]", dep.strip())[0].strip().lower()


def test_all_direct_pypi_deps_have_upper_bounds():
    """Every direct PyPI dependency (excl. exact pins and git sources) must carry '<' upper bound.

    This ensures that a future breaking release cannot be resolved silently.
    Excluded from this check:
      - Entries that are git URLs (``@ git+`` or appear in [tool.uv.sources] as git)
      - Exact pins with ``==`` (pymotivaxmc2, asyncwebostv, pyatv==0.17.0)
    """
    data = _load_pyproject()
    deps: list[str] = data.get("project", {}).get("dependencies", [])
    sources: dict = data.get("tool", {}).get("uv", {}).get("sources", {})

    # Build a set of package names that are git-sourced (via uv.sources).
    git_sourced = {
        pkg.lower()
        for pkg, spec in sources.items()
        if "git" in spec or "url" in spec
    }

    missing_upper_bound: list[str] = []

    for dep in deps:
        dep = dep.strip()
        if not dep or dep.startswith("#"):
            continue

        pkg_name = _pkg_name_from_dep(dep)

        # Skip git-sourced deps (they use a SHA rev, not a version range).
        if pkg_name in git_sourced or "@ git+" in dep:
            continue

        # Skip exact pins (== already pins an exact version; upper bound is redundant).
        if "==" in dep:
            continue

        # Skip explicitly excluded user-owned packages (already exact-pinned).
        if pkg_name in _EXACT_PINNED_PKGS:
            continue

        # All remaining entries must carry an upper-bound operator.
        if "<" not in dep:
            missing_upper_bound.append(dep)

    assert not missing_upper_bound, (
        "The following direct PyPI dependencies lack an upper bound '<'.\n"
        "Add ',<NEXT_MAJOR' to each to prevent silent breaking-release upgrades (DEP-03):\n"
        + "\n".join(f"  {d}" for d in missing_upper_bound)
    )
