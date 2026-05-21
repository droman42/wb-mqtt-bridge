"""Tests for the capability-map schema + loader (scenario redesign, Layer 1)."""

import json
from pathlib import Path

import pytest

from wb_mqtt_bridge.infrastructure.capabilities.loader import load_capability_map
from wb_mqtt_bridge.infrastructure.capabilities.models import Capability

CAPS = Path(__file__).resolve().parents[2] / "config" / "capabilities"


def test_lgtv_class_map_loads_and_translates_input():
    m = load_capability_map("LgTv", "living_room_tv", CAPS)
    assert {"power", "input", "volume", "menu", "playback", "apps", "pointer"} <= set(m.domains())
    # RC1 fix: canonical `input` -> native `source`
    assert m.get("input").select.param_map == {"input": "source"}
    assert m.get("input").select.command == "set_input_source"
    assert m.get("power").feedback is True
    assert m.get("power").gate.poll_timeout_ms == 8000
    # menu D-pad maps to native keys (LG `enter` is canonical `ok`)
    assert m.get("menu").actions["ok"].command == "enter"


def test_emotiva_multizone_power():
    m = load_capability_map("EMotivaXMC2", "processor", CAPS)
    power = m.get("power")
    assert power.zones is not None and set(power.zones) == {"1", "2"}
    assert power.zones["2"].state_field == "zone2_power"
    assert power.zones["1"].actions["on"].params == {"zone": 1}
    # identity param (canonical `input` == native `input`) needs no param_map
    assert m.get("input").select.command == "set_input"
    assert m.get("input").select.param_map == {}


def test_appletv_has_no_input_and_maps_pointer():
    m = load_capability_map("AppleTVDevice", "appletv_living", CAPS)
    assert "input" not in m.domains()  # pure source
    assert m.get("pointer").actions["move"].param_map == {"dx": "deltaX", "dy": "deltaY"}
    assert m.get("power").feedback is True


def test_mf_amp_device_map_toggle_power_and_value_mapped_input():
    m = load_capability_map("WirenboardIRDevice", "mf_amplifier", CAPS)
    assert m.get("power").feedback is False
    assert "toggle" in m.get("power").actions  # no discrete on/off
    by_value = m.get("input").select.by_value
    assert by_value["aux2"].command == "input_aux2"
    assert by_value["cd"].command == "input_cd"
    assert m.get("input").gate.delay_ms == 500


def test_device_file_deep_merges_over_class_default(tmp_path):
    (tmp_path / "classes").mkdir()
    (tmp_path / "devices").mkdir()
    (tmp_path / "classes" / "LgTv.json").write_text(json.dumps({
        "power": {"kind": "stateful", "feedback": True, "state_field": "power",
                  "actions": {"on": {"command": "power_on"}}, "gate": {"poll_timeout_ms": 8000}}
    }))
    (tmp_path / "devices" / "tv1.json").write_text(json.dumps({
        "power": {"gate": {"poll_timeout_ms": 12000}}
    }))
    m = load_capability_map("LgTv", "tv1", tmp_path)
    assert m.get("power").gate.poll_timeout_ms == 12000   # device wins
    assert m.get("power").actions["on"].command == "power_on"  # class retained


def test_missing_files_yield_empty_map(tmp_path):
    m = load_capability_map("Nope", "nobody", tmp_path)
    assert m.domains() == []


def test_invalid_select_rejected():
    with pytest.raises(Exception):
        Capability.model_validate({"kind": "stateful", "select": {}})  # neither command nor by_value


def test_action_needs_exactly_one_invocation():
    with pytest.raises(Exception):
        Capability.model_validate({"kind": "momentary", "actions": {"x": {}}})  # no command/sequence
