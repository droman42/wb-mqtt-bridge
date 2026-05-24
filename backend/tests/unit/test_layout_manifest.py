"""LayoutManifest must stay a faithful mirror of the UI's RemoteDeviceStructure.

Every frozen oracle (`docs/scenarios/layer3_oracle/*.json`, extracted from the now-deleted
`.gen.tsx`) must parse into `LayoutManifest` with `extra="forbid"` — so any drift between this
model and the renderer's structure fails loudly. This is the Step-1 fidelity guard.

The oracle files are kept frozen as a structural snapshot; fields the model has since dropped
(``specialCases`` — retired at the Layer-3 Step-4 cutover, B2) are stripped here before validation.
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


# Fields present in the frozen oracle that the model has intentionally dropped since.
_RETIRED_KEYS = ("specialCases",)


@pytest.mark.skipif(not ORACLES, reason="layer3_oracle/ not present (backend tested standalone)")
@pytest.mark.parametrize("oracle", ORACLES, ids=lambda p: p.stem)
def test_oracle_parses_into_layout_manifest(oracle):
    data = json.loads(oracle.read_text())
    for key in _RETIRED_KEYS:
        data.pop(key, None)
    LayoutManifest.model_validate(data)


@pytest.mark.skipif(not ORACLES, reason="layer3_oracle/ not present")
def test_all_device_oracles_present():
    assert len(ORACLES) == 13
