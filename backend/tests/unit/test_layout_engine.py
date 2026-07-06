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


def _dropdown(manifest: dict, zone_id: str, key: str) -> dict:
    zone = next(z for z in manifest["remoteZones"] if z["zoneId"] == zone_id)
    dd = zone["content"][key]
    assert dd is not None
    return dd


@pytest.mark.skipif(ROOT is None, reason="config/ not present")
def test_inputs_dropdown_parametric_is_canonical(  # UI-9: dropdowns dispatch canonically
):
    """Parametric select (LG TV): api-populated, carries the `input.set {value}` tuple."""
    manifest = build_device_manifest(_make_device("lg_tv_living", "LgTv")).model_dump(by_alias=True)
    dd = _dropdown(manifest, "media-stack", "inputsDropdown")
    assert dd["populationMethod"] == "api"
    assert (dd["canonicalCapability"], dd["canonicalAction"], dd["canonicalParam"]) == (
        "input", "set", "value")
    assert dd["options"] == []


@pytest.mark.skipif(ROOT is None, reason="config/ not present")
def test_inputs_dropdown_by_value_option_ids_are_canonical_values():
    """by_value select (mf_amplifier): inline options whose ids are the table keys —
    the same canonical values `input.set {value}` accepts — NOT native command names."""
    manifest = build_device_manifest(_make_device("mf_amplifier", "AmplifierRelayDevice")).model_dump(by_alias=True)
    dd = _dropdown(manifest, "media-stack", "inputsDropdown")
    assert dd["populationMethod"] == "commands"
    assert (dd["canonicalCapability"], dd["canonicalAction"], dd["canonicalParam"]) == (
        "input", "set", "value")
    ids = [o["id"] for o in dd["options"]]
    assert ids and not any(i.startswith("input_") for i in ids)  # values, not command names
    # every option id round-trips through the select's own expansion (dispatchability)
    dev = _make_device("mf_amplifier", "AmplifierRelayDevice")
    sel = dict(dev.capabilities.root)["input"].select
    for i in ids:
        assert len(sel.expand(i)) >= 1


@pytest.mark.skipif(ROOT is None, reason="config/ not present")
def test_apps_dropdown_carries_launch_tuple():
    """apps dropdown: canonical `apps.launch {app}` (endpoint renames via param_map)."""
    manifest = build_device_manifest(_make_device("appletv_living", "AppleTVDevice")).model_dump(by_alias=True)
    dd = _dropdown(manifest, "apps", "appsDropdown")
    assert dd["populationMethod"] == "api"
    assert (dd["canonicalCapability"], dd["canonicalAction"], dd["canonicalParam"]) == (
        "apps", "launch", "app")


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
