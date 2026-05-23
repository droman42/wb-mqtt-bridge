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


def _name(a):
    return a["actionName"] if a else None


def _structure(zones, dormant=frozenset()):
    """Distill to the layout-critical structure per zone: zoneId -> (isEmpty, parts).

    Slot zones (power) keep order (position/buttonType deterministic). Ordered zones
    (playback/tracks/screen) and the menu compare as SETS — by design the new manifest orders them
    by capability-declaration order, deliberately retiring the old config-key order, so order may
    differ from the oracle; fidelity = the same controls present (none lost/added). Dropdowns
    compare type + populationMethod + option count (ids/labels are capability-derived now).
    `dormant` (exposed:false) command names are dropped — the oracle predates dormant-tagging, so the
    new manifest correctly omits them."""
    def keep(names):
        return [n for n in names if n not in dormant]

    out = {}
    for z in zones:
        c = z["content"]
        parts = {}
        if c.get("powerButtons"):
            pb = [(b["position"], b["buttonType"], b["action"]["actionName"])
                  for b in c["powerButtons"] if b["action"]["actionName"] not in dormant]
            if pb:
                parts["power"] = pb
        if c.get("playbackSection"):
            pv = sorted(keep(_name(a) for a in c["playbackSection"]["actions"]))
            if pv:
                parts["playback"] = pv
        if c.get("tracksSection"):
            tv = sorted(keep(_name(a) for a in c["tracksSection"]["actions"]))
            if tv:
                parts["tracks"] = tv
        if c.get("inputsDropdown"):
            d = c["inputsDropdown"]
            parts["inputs"] = (d["populationMethod"], len(d.get("options", [])))
        if c.get("volumeSlider"):
            vs = c["volumeSlider"]
            parts["vslider"] = (_name(vs["action"]), _name(vs.get("muteAction")))
        if c.get("volumeButtons"):
            vb = c["volumeButtons"][0]
            parts["vbuttons"] = (_name(vb.get("upAction")), _name(vb.get("downAction")), _name(vb.get("muteAction")))
        if c.get("screenActions"):
            sv = sorted(keep(_name(a) for a in c["screenActions"]))
            if sv:
                parts["screen"] = sv
        if c.get("appsDropdown"):
            d = c["appsDropdown"]
            parts["apps"] = (d["populationMethod"], len(d.get("options", [])))
        if c.get("navigationCluster"):
            mv = frozenset(n for n in (_name(v) for v in c["navigationCluster"].values() if v) if n not in dormant)
            if mv:
                parts["menu"] = mv
        if c.get("pointerPad"):
            parts["pointer"] = frozenset(k for k, v in c["pointerPad"].items() if v)
        # an empty zone is empty regardless of placeholder content shape (renderer-equivalent)
        out[z["zoneId"]] = (z["isEmpty"], {} if z["isEmpty"] else parts)
    return out


@pytest.mark.skipif(ROOT is None or ORACLE is None or not ORACLE.is_dir(), reason="config/ or oracle/ not present")
# (config filename, oracle filename, device_class) — oracle name = page id, which differs for some.
# emotiva (processor) is deferred: its inputs(api)+volume(slider) match, but multi-zone power is a
# special case (the old codegen synthesized a `zone2_power_toggle` command that doesn't exist) — the
# cap-driven engine will render it from cap.zones, intentionally diverging. Add it back with proper
# multi-zone power handling later.
@pytest.mark.parametrize("config_name,oracle_name,device_class", [
    ("reel_to_reel", "reel_to_reel", "RevoxA77ReelToReel"),
    ("vhs_player", "vhs_player", "WirenboardIRDevice"),
    ("mf_amplifier", "mf_amplifier", "WirenboardIRDevice"),
    ("ld_player", "ld_player", "WirenboardIRDevice"),
    ("video", "video", "WirenboardIRDevice"),
    ("upscaler", "upscaler", "WirenboardIRDevice"),
    ("streamer", "streamer", "AuralicDevice"),
    ("lg_tv_living", "living_room_tv", "LgTv"),
    ("lg_tv_children", "children_room_tv", "LgTv"),
    ("appletv_living", "appletv_living", "AppleTVDevice"),
    ("appletv_children", "appletv_children", "AppleTVDevice"),
    ("kitchen_hood", "kitchen_hood", "BroadlinkKitchenHood"),  # appliance — all remote zones empty
])
def test_engine_reproduces_oracle(config_name, oracle_name, device_class):
    cfg = json.loads((ROOT / "config" / "devices" / f"{config_name}.json").read_text())
    dormant = {n for n, c in (cfg.get("commands") or {}).items() if (c or {}).get("exposed") is False}
    manifest = build_device_manifest(_make_device(config_name, device_class)).model_dump(by_alias=True)
    oracle = json.loads((ORACLE / f"{oracle_name}.json").read_text())
    # the oracle predates dormant-tagging; drop exposed:false commands the new manifest correctly omits
    assert _structure(manifest["remoteZones"]) == _structure(oracle["remoteZones"], dormant)
