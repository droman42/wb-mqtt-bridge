"""Pin-guard tests: assert the supply-chain guarantees introduced in Phase 1.

These tests act as a permanent regression gate.  They will FAIL the build if any
future change reintroduces:

  - A moving ``branch =`` git ref in ``[tool.uv.sources]``         (DEP-01)
  - An ``lxml`` dependency on the openhomedevice path              (ARMv7 constraint)
  - An unbounded direct PyPI dependency specifier                  (DEP-03)
  - A removal of the immutable openhomedevice SHA or the immutable pyatv git-SHA pin

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
    """openhomedevice must be pinned to the immutable SHA 819b16102fb71e68c4f593af4d49c66a344d300a.

    The fork removes lxml (ARMv7 constraint) and carries the AURALiC
    HardwareConfig halt support (DRV-14; PR'd upstream as
    bazwilliams/openhomedevice#26).  Migrating to a different SHA requires a
    conscious decision, not an accidental branch-track.
    """
    expected_sha = "819b16102fb71e68c4f593af4d49c66a344d300a"
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


def test_pyatv_pinned_to_immutable_git_sha():
    """pyatv must be pinned to an IMMUTABLE upstream commit SHA — never a moving branch.

    pyatv was on a PyPI exact pin (==0.17.0), but tvOS 26.4/26.5 silently drop Companion
    *query* commands (FetchAttentionState→power, app_list, set_volume) unless a
    TVRCSessionStart handshake is sent at connect. That fix landed on master (#2855) but is
    not in any release yet (0.17.0 predates it), so pyatv is temporarily pinned to an
    immutable master SHA. The pin MUST be a 40-char commit SHA on postlund/pyatv (reproducible),
    NOT a branch (DEP-01 spirit). Move back to a PyPI exact pin once a release contains #2855.
    """
    data = _load_pyproject()
    deps: list[str] = data.get("project", {}).get("dependencies", [])

    pyatv_entries = [d for d in deps if re.match(r"\s*pyatv(\s|@|=|$)", d)]
    assert pyatv_entries, "pyatv is missing from [project].dependencies."

    spec = pyatv_entries[0]
    assert re.search(
        r"pyatv\s*@\s*git\+https://github\.com/postlund/pyatv@[0-9a-f]{40}\b", spec
    ), (
        "pyatv must be pinned to an immutable upstream commit SHA, e.g. "
        "'pyatv @ git+https://github.com/postlund/pyatv@<40-hex-sha>'. "
        f"Got: {spec!r}. (A branch ref or a non-SHA git ref is forbidden — DEP-01.)"
    )

    # Guard against a moving branch sneaking into [tool.uv.sources] for pyatv.
    sources: dict = data.get("tool", {}).get("uv", {}).get("sources", {})
    if "pyatv" in sources:
        assert "branch" not in sources["pyatv"], (
            "pyatv [tool.uv.sources] uses a moving 'branch =' ref; use an immutable 'rev =' SHA."
        )


# ---------------------------------------------------------------------------
# Test 3 — pyatv exact PyPI pin is present
# ---------------------------------------------------------------------------


def test_pyatv_pin_is_the_expected_sha():
    """The pyatv pin must be the reviewed, hardware-verified SHA.

    Advancing it is a conscious decision: bump the SHA here AND re-verify against a
    tvOS 26.x Apple TV that the Companion queries still work. When pyatv cuts a release
    containing #2855, switch back to a 'pyatv==X.Y.Z' PyPI pin (and update this test).
    """
    expected_sha = "9177803dec6a165d4610d5d63fe09562820fccdb"
    data = _load_pyproject()
    deps: list[str] = data.get("project", {}).get("dependencies", [])

    pyatv_entries = [d for d in deps if re.match(r"\s*pyatv(\s|@|=|$)", d)]
    assert pyatv_entries and expected_sha in pyatv_entries[0], (
        f"pyatv pin must be the reviewed SHA {expected_sha}; "
        f"got: {pyatv_entries[0] if pyatv_entries else None!r}. "
        "Update this test only when intentionally advancing the pin (re-verify on tvOS 26.x)."
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


# ---------------------------------------------------------------------------
# Test 6 — pyatv listener interface compatibility (runtime interface guard)
# ---------------------------------------------------------------------------


def test_pyatv_device_listener_implements_all_abstract_methods():
    """The AppleTV driver's PyATVDeviceListener must implement every abstract method
    required by the *installed* pyatv listener interfaces.

    pyatv 0.17.0 added ``AudioListener.volume_device_update``, which the driver did not
    implement — making the listener un-instantiable and breaking every Apple TV at device
    setup (a failure only visible on hardware). This guard turns that class of regression
    into a unit-test failure: if a future pyatv bump adds another abstract listener method,
    this fails here instead of in production.
    """
    from locveil_bridge.infrastructure.devices.apple_tv.driver import PyATVDeviceListener

    unimplemented = sorted(getattr(PyATVDeviceListener, "__abstractmethods__", frozenset()))
    assert not unimplemented, (
        "PyATVDeviceListener has unimplemented abstract methods required by the installed "
        f"pyatv version: {unimplemented}. Implement them on the listener "
        "(see AudioListener / DeviceListener in pyatv.interface)."
    )
