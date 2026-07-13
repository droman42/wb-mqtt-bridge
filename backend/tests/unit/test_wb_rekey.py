"""WB virtual-device output must NOT change when its exposure/ordering/type classification is
re-keyed from the config ``group`` field to the capability ``domain``+``kind``+``exposed`` (Layer-3
cutover, step 1 — removing ``group`` as the source of truth).

Golden snapshot: ``tests/unit/wb_oracle/<config_name>.json`` freezes the WB output — subscription
topics + per-command control meta + initial state — for every device. The re-key reproduced the
old group-based output **byte-for-byte except** it now correctly drops ``exposed: false`` dormant
commands from WB (the old group exclusion only filtered hardcoded UI-only groups, so dormant
commands whose group wasn't in that set — ``streamer.refresh_inputs``, ``appletv*.refresh_status`` —
leaked onto WB as dead controls; the exposure gate already rejected executing them). The snapshot
here encodes the re-keyed (corrected) output. Set ``WB_ORACLE_CAPTURE=1`` to (re)write it.
"""
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from locveil_bridge.infrastructure.capabilities.loader import load_capability_map
from locveil_bridge.infrastructure.config.models import StandardCommandConfig
from locveil_bridge.infrastructure.wb_device.service import WBVirtualDeviceService


def _backend_root():
    for parent in Path(__file__).resolve().parents:
        if (parent / "config" / "devices").is_dir():
            return parent
    return None


ROOT = _backend_root()
ORACLE = Path(__file__).resolve().parent / "wb_oracle"

# (config file name, device_class) — every device that enables WB emulation.
DEVICES = [
    ("appletv_children", "AppleTVDevice"),
    ("appletv_living", "AppleTVDevice"),
    ("emotiva_xmc2", "EMotivaXMC2"),
    ("kitchen_hood", "BroadlinkKitchenHood"),
    ("ld_player", "WirenboardIRDevice"),
    ("lg_tv_children", "LgTv"),
    ("lg_tv_living", "LgTv"),
    ("mf_amplifier", "WirenboardIRDevice"),
    ("reel_to_reel", "RevoxA77ReelToReel"),
    ("streamer", "AuralicDevice"),
    ("upscaler", "WirenboardIRDevice"),
    ("vhs_player", "WirenboardIRDevice"),
    ("video", "WirenboardIRDevice"),
]


def _make_device(config_name: str, device_class: str):
    cfg = json.loads((ROOT / "config" / "devices" / f"{config_name}.json").read_text())
    commands = {n: StandardCommandConfig.model_validate(c) for n, c in cfg["commands"].items()}
    config = SimpleNamespace(
        device_id=cfg["device_id"], names=SimpleNamespace(**cfg["names"]),
        device_class=cfg["device_class"], device_category=cfg.get("device_category", "device"),
        enable_wb_emulation=cfg.get("enable_wb_emulation", True),
        wb_controls=cfg.get("wb_controls"),
        commands=commands,
    )
    capabilities = load_capability_map(device_class, config_name, ROOT / "config" / "capabilities")
    return config, capabilities


def _wb_output(config_name: str, device_class: str) -> dict:
    config, capabilities = _make_device(config_name, device_class)
    svc = WBVirtualDeviceService(message_bus=SimpleNamespace())  # pure methods only — no MQTT
    # Re-keyed path: classification comes from the capability domain (+ exposed), not config group.
    controls = svc.build_wb_controls_from_config(config, capabilities)
    # initial_state may be non-JSON-native (int/bool) — coerce to str for a stable snapshot.
    controls = {k: {"meta": v["meta"], "initial_state": str(v["initial_state"])} for k, v in controls.items()}
    return {
        "device_id": config.device_id,
        "subscription_topics": svc.get_subscription_topics_from_config(config, capabilities=capabilities),
        "controls": controls,
    }


@pytest.mark.skipif(ROOT is None, reason="backend config/ not present")
@pytest.mark.parametrize("config_name,device_class", DEVICES, ids=[d[0] for d in DEVICES])
def test_wb_output_matches_oracle(config_name: str, device_class: str):
    out = _wb_output(config_name, device_class)
    fixture = ORACLE / f"{config_name}.json"
    if os.environ.get("WB_ORACLE_CAPTURE") or not fixture.exists():
        ORACLE.mkdir(exist_ok=True)
        fixture.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
        pytest.skip(f"captured WB oracle for {config_name}")
    assert out == json.loads(fixture.read_text())
