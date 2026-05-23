"""LayoutManifest must stay a faithful mirror of the UI's RemoteDeviceStructure.

Every frozen oracle (`docs/scenarios/layer3_oracle/*.json`, extracted from the current
`.gen.tsx`) must parse into `LayoutManifest` with `extra="forbid"` — so any drift between this
model and the renderer's structure fails loudly. This is the Step-1 fidelity guard.
"""
import json
from pathlib import Path

import pytest

from wb_mqtt_bridge.presentation.api.layout_manifest import LayoutManifest


def _oracle_dir():
    for parent in Path(__file__).resolve().parents:
        d = parent / "docs" / "scenarios" / "layer3_oracle"
        if d.is_dir():
            return d
    return None


_ORACLE = _oracle_dir()
ORACLES = sorted(_ORACLE.glob("*.json")) if _ORACLE else []


@pytest.mark.skipif(not ORACLES, reason="layer3_oracle/ not present (backend tested standalone)")
@pytest.mark.parametrize("oracle", ORACLES, ids=lambda p: p.stem)
def test_oracle_parses_into_layout_manifest(oracle):
    LayoutManifest.model_validate(json.loads(oracle.read_text()))


@pytest.mark.skipif(not ORACLES, reason="layer3_oracle/ not present")
def test_all_device_oracles_present():
    assert len(ORACLES) == 13
