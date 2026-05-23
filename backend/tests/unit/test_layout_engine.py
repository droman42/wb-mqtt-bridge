"""Layer-3 placement engine — fidelity vs the frozen oracle.

Step 1 (incremental): the engine builds power + playback zones, so reel_to_reel (playback) and
vhs_player (power + playback) must reproduce their oracle structurally (zones present, isEmpty per
zone, control actionNames/positions/buttonType). Other devices/zones are added in later iterations.
"""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from wb_mqtt_bridge.infrastructure.capabilities.loader import load_capability_map
from wb_mqtt_bridge.infrastructure.config.models import StandardCommandConfig
from wb_mqtt_bridge.presentation.api.layout_engine import build_device_manifest


def _backend_root():
    for parent in Path(__file__).resolve().parents:
        if (parent / "config" / "devices").is_dir():
            return parent
    return None


ROOT = _backend_root()
ORACLE = (ROOT.parent / "docs" / "scenarios" / "layer3_oracle") if ROOT else None


def _make_device(name: str, device_class: str):
    cfg = json.loads((ROOT / "config" / "devices" / f"{name}.json").read_text())
    commands = {n: StandardCommandConfig.model_validate(c) for n, c in cfg["commands"].items()}
    config = SimpleNamespace(
        device_id=cfg["device_id"], device_name=cfg["device_name"],
        device_class=cfg["device_class"], device_category=cfg.get("device_category", "device"),
        commands=commands,
    )
    dev = SimpleNamespace(
        config=config,
        capabilities=load_capability_map(device_class, name, ROOT / "config" / "capabilities"),
        state=None,
    )
    dev.get_available_commands = lambda: commands
    return dev


def _structure(zones):
    """Distill to the layout-critical structure: zoneId -> (isEmpty, controls).

    Slot zones (power) keep order — position/buttonType are deterministic. Ordered zones
    (playback/…) compare as a SET: by design the new manifest orders them by capability-declaration
    order, which deliberately retires the old config-key order, so order may differ from the oracle;
    fidelity means the same controls are present (none lost/added)."""
    out = {}
    for z in zones:
        c = z["content"]
        ctrl = []
        if c.get("powerButtons"):
            ctrl = [(b["position"], b["buttonType"], b["action"]["actionName"]) for b in c["powerButtons"]]
        elif c.get("playbackSection"):
            ctrl = sorted(a["actionName"] for a in c["playbackSection"]["actions"])
        out[z["zoneId"]] = (z["isEmpty"], ctrl)
    return out


@pytest.mark.skipif(ROOT is None or ORACLE is None or not ORACLE.is_dir(), reason="config/ or oracle/ not present")
@pytest.mark.parametrize("name,device_class", [
    ("reel_to_reel", "RevoxA77ReelToReel"),
    ("vhs_player", "WirenboardIRDevice"),
])
def test_engine_reproduces_oracle(name, device_class):
    manifest = build_device_manifest(_make_device(name, device_class)).model_dump(by_alias=True)
    oracle = json.loads((ORACLE / f"{name}.json").read_text())
    assert _structure(manifest["remoteZones"]) == _structure(oracle["remoteZones"])
