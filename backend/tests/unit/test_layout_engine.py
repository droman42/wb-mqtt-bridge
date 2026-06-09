"""Layer-3 placement engine — surviving behaviour tests.

The parametrized 12-device oracle-fidelity sweep (`test_engine_reproduces_oracle`) was
retired 2026-06-09 alongside the frozen-oracle JSON archive (`docs/design/scenarios/
layer3_oracle/` → `docs/archive/layer3_oracle/`). Render-level diff (`/devices/{id}/layout`
served + the UI's `RuntimeDevicePage` consuming it) has been the working contract since
the 2026-05-24 Layer-3 cutover; the oracle was kept as a deferred structural snapshot
and never re-engaged because the engine has been stable + the UI rendering surface is
what users actually see. The eMotiva multi-zone test below survives because it was
authored as a property assertion (not an oracle diff) — multi-zone power intentionally
diverged from the old codegen, so it needed an inline contract from the start.
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


def _make_device(name: str, device_class: str):
    cfg = json.loads((ROOT / "config" / "devices" / f"{name}.json").read_text())
    commands = {n: StandardCommandConfig.model_validate(c) for n, c in cfg["commands"].items()}
    config = SimpleNamespace(
        device_id=cfg["device_id"], names=SimpleNamespace(**cfg["names"]),
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


@pytest.mark.skipif(ROOT is None, reason="config/ not present")
def test_engine_emotiva_multizone_power():
    """eMotiva power is multi-zone: zone 1 discrete off/on + zone 2 native toggle (`zone2-power`,
    the real zone2_power command). Validated explicitly as a property assertion (the old codegen
    synthesized a `zone2_power_toggle` command + used the generic `power-toggle` buttonType — the
    capability-driven engine intentionally diverges)."""
    manifest = build_device_manifest(_make_device("emotiva_xmc2", "EMotivaXMC2")).model_dump(by_alias=True)
    power = next(z for z in manifest["remoteZones"] if z["zoneId"] == "power")
    buttons = [(b["position"], b["buttonType"], b["action"]["actionName"]) for b in power["content"]["powerButtons"]]
    assert buttons == [
        ("left", "power-off", "power_off"),
        ("middle", "zone2-power", "zone2_power_toggle"),
        ("right", "power-on", "power_on"),
    ]
