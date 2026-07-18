"""CORE-7 — core-py strict-pin conformance (the estate's first vendored RUNTIME code
bridge-side; the voice ARCH-58 test is the sibling).

Three legs, all hermetic:
1. the importable copy `utils/entry_point_loader.py` is BYTE-IDENTICAL to the pin
   `contracts/pins/core-py/entry_point_loader.py` (a local edit to the runtime file
   must break commit + CI — never edit a vendored copy, re-pin to move);
2. the pinned bytes match the sha256 the strict PIN.json records;
3. the pin's core fields and the owner STAMP agree, and the bridge singleton
   actually serves the pinned class.
"""

import hashlib
import json
from pathlib import Path

import pytest

from locveil_bridge.utils.entry_point_loader import DynamicLoader
from locveil_bridge.utils.entry_points import dynamic_loader

pytestmark = pytest.mark.unit

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PIN_DIR = _REPO_ROOT / "contracts" / "pins" / "core-py"
_RUNTIME = (
    _REPO_ROOT / "backend" / "src" / "locveil_bridge" / "utils" / "entry_point_loader.py"
)

PIN = json.loads((_PIN_DIR / "PIN.json").read_text(encoding="utf-8"))
STAMP = json.loads((_PIN_DIR / "STAMP.json").read_text(encoding="utf-8"))


def test_runtime_copy_is_byte_identical_to_pin():
    assert _RUNTIME.read_bytes() == (_PIN_DIR / "entry_point_loader.py").read_bytes(), (
        "utils/entry_point_loader.py differs from the pin — never edit the vendored "
        "copy; changes happen in locveil-commons packages/core-py, re-tag, re-pin "
        "(python3 scripts/repin.py core-py)"
    )


def test_pin_files_match_recorded_sha256():
    for name, recorded in PIN["files"].items():
        actual = hashlib.sha256((_PIN_DIR / name).read_bytes()).hexdigest()
        assert actual == recorded, f"pinned {name} does not match PIN.json sha256"


def test_pin_and_stamp_coherence():
    assert PIN["contract"] == STAMP["contract"] == "core-py"
    assert PIN["owner_repo"] == STAMP["owner_repo"] == "locveil-commons"
    assert PIN["tag"] == STAMP["tag"] == f"core-py-v{STAMP['version']}"
    assert "entry_point_loader.py" in STAMP["artifacts"][0]


def test_singleton_serves_the_pinned_class():
    assert isinstance(dynamic_loader, DynamicLoader)
