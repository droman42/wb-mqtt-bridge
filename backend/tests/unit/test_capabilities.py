"""Tests for the capability-map schema + loader (scenario redesign, Layer 1)."""

import json
from pathlib import Path

import pytest

from wb_mqtt_bridge.infrastructure.capabilities.loader import load_capability_map
from wb_mqtt_bridge.domain.capabilities.models import Capability

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
    # Pad move passes {dx,dy} straight through (identity), matching what the UI dispatches;
    # the driver translates the delta into a directional swipe. Pad click → select (the
    # coordinate-free OK), since a relative pad can't supply touch_at_position's x/y.
    assert m.get("pointer").actions["move"].param_map == {"dx": "dx", "dy": "dy"}
    assert m.get("pointer").actions["click"].command == "select"
    assert "tap" not in m.get("pointer").actions
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


def test_profile_merges_under_class_and_above_device_override(tmp_path):
    """§P3.7 capability-profile resolution: class → profile → per-device, leaves win at the top.
    Lets many WB-passthrough devices share one capability file (`light_switch` etc.) without
    touching AV devices that don't set `capability_profile`."""
    (tmp_path / "classes").mkdir()
    (tmp_path / "profiles").mkdir()
    (tmp_path / "devices").mkdir()
    # Class default: not used by light_switch in practice, but the resolver must merge over it.
    (tmp_path / "classes" / "WbPassthroughDevice.json").write_text(json.dumps({
        "power": {"kind": "stateful", "feedback": True, "state_field": "power",
                  "actions": {"on": {"command": "from_class"}}}
    }))
    # Profile: the shared light_switch shape.
    (tmp_path / "profiles" / "light_switch.json").write_text(json.dumps({
        "power": {"kind": "momentary",
                  "actions": {"on": {"command": "power_on"}, "off": {"command": "power_off"}}}
    }))
    # Per-device override: stays valid for the rare instance tweak.
    (tmp_path / "devices" / "cabinet_spots.json").write_text(json.dumps({
        "power": {"actions": {"on": {"command": "instance_override"}}}
    }))
    m = load_capability_map("WbPassthroughDevice", "cabinet_spots", tmp_path,
                            capability_profile="light_switch")
    power = m.get("power")
    # Device override beats profile beats class at the action leaf.
    assert power.actions["on"].command == "instance_override"
    # Profile contributes `off` (class didn't have it).
    assert power.actions["off"].command == "power_off"
    # And kind comes from the profile (overrode the class default "stateful").
    assert power.kind == "momentary"


def test_profile_omitted_when_capability_profile_is_none(tmp_path):
    """A device that doesn't set capability_profile keeps the old class+device-override
    behaviour byte-for-byte -- the AV path must not change."""
    (tmp_path / "classes").mkdir()
    (tmp_path / "profiles").mkdir()
    (tmp_path / "classes" / "LgTv.json").write_text(json.dumps({
        "power": {"kind": "stateful", "feedback": True, "state_field": "power",
                  "actions": {"on": {"command": "power_on"}}}
    }))
    # A bogus profile sits next door; it must NOT be picked up.
    (tmp_path / "profiles" / "light_switch.json").write_text(json.dumps({
        "power": {"actions": {"on": {"command": "WRONG"}}}
    }))
    m = load_capability_map("LgTv", "tv1", tmp_path)  # capability_profile defaults to None
    assert m.get("power").actions["on"].command == "power_on"


def test_invalid_select_rejected():
    with pytest.raises(Exception):
        Capability.model_validate({"kind": "stateful", "select": {}})  # neither command nor by_value


def test_action_needs_exactly_one_invocation():
    with pytest.raises(Exception):
        Capability.model_validate({"kind": "momentary", "actions": {"x": {}}})  # no command/sequence


# --- §P3.7 #19 -- capability profiles authored for bulk onboarding -----------


def test_sensor_room_profile_has_5_read_only_fields_no_actions():
    """`sensor_room` is the wb-msw-v3 sensor side. It's a pure read surface: no actions,
    `reconcile=False` (the scenario reconciler shouldn't try to drive it), and a typed
    field per WB control we surface to voice/UI. Motion is intentionally OUT (no v1 voice
    use case per the §P3.7 #19 scope discussion 2026-06-08)."""
    m = load_capability_map("WbPassthroughDevice", "any_msw",
                             capabilities_dir=CAPS, capability_profile="sensor_room")
    sensor = m.get("sensor")
    assert sensor is not None and sensor.kind == "stateful"
    assert sensor.reconcile is False
    assert sensor.actions == {}
    names = [f.name for f in sensor.fields]
    assert names == ["temperature", "humidity", "co2", "illuminance", "sound_level"]
    # Field metadata is what catalog consumers (Irene, UI) need for typed parse + display.
    by = {f.name: f for f in sensor.fields}
    assert by["temperature"].type == "float" and by["temperature"].unit == "°C"
    assert by["co2"].type == "int" and by["co2"].unit == "ppm"
    assert by["temperature"].labels.ru == "температура"


def test_rgb_light_profile_carries_color_field_with_rgb_encoding():
    """`color.set(r,g,b)` resolves to a single native command on a single WB control whose
    payload is composed via the device config's `payload_template`. The PROFILE side
    carries the field metadata used to PARSE the incoming echo back into `{r,g,b}`."""
    m = load_capability_map("WbPassthroughDevice", "any_rgb",
                             capabilities_dir=CAPS, capability_profile="rgb_light")
    color = m.get("color")
    assert color.actions["set"].command == "set_color"
    assert color.actions["set"].param_map == {"r": "r", "g": "g", "b": "b"}
    color_field = next(f for f in color.fields if f.name == "color")
    assert color_field.type == "rgb"
    assert color_field.encoding == "{r};{g};{b}"


def test_hvac_climate_enum_fields_carry_allowed_values():
    """Enum fields (mode/fan/vane) declare their allowed values so the catalog consumer
    can validate set-action params and render a fixed list."""
    m = load_capability_map("WbPassthroughDevice", "any_hvac",
                             capabilities_dir=CAPS, capability_profile="hvac")
    climate = m.get("climate")
    mode = next(f for f in climate.fields if f.name == "mode")
    assert mode.type == "enum"
    assert set(mode.values) == {"off", "cool", "heat", "auto", "fan", "dry"}
    fan = next(f for f in climate.fields if f.name == "fan")
    assert fan.values == ["auto", "low", "medium", "high"]


def test_heating_loop_profile_has_climate_with_three_fields():
    """Heating loop is the most composite simple shape: actuator (on/off) + setpoint slider
    + room-temp sensor reads. Modeled as one `climate` capability with field reads."""
    m = load_capability_map("WbPassthroughDevice", "any_radiator",
                             capabilities_dir=CAPS, capability_profile="heating_loop")
    climate = m.get("climate")
    assert {a for a in climate.actions} == {"on", "off", "set_setpoint"}
    assert {f.name for f in climate.fields} == {"mode", "setpoint", "room_temperature"}


def test_dimmable_light_inherits_power_plus_brightness_with_level_field():
    m = load_capability_map("WbPassthroughDevice", "any_dimmer",
                             capabilities_dir=CAPS, capability_profile="dimmable_light")
    assert m.get("power").actions["on"].command == "power_on"
    bright = m.get("brightness")
    assert bright.actions["set"].command == "set_brightness"
    level = bright.fields[0]
    assert level.name == "level" and level.type == "int" and level.unit == "%"


def test_cover_profile_has_open_close_set_position_stop_actions():
    m = load_capability_map("WbPassthroughDevice", "any_cover",
                             capabilities_dir=CAPS, capability_profile="cover")
    actions = m.get("cover").actions
    assert {"open", "close", "set_position", "stop"} == set(actions.keys())
    assert actions["set_position"].param_map == {"pct": "pct"}


def test_stateful_capability_with_fields_only_is_valid_shape():
    """Sensor-shape: stateful, no actions, no select, no zones, but `fields` populated.
    The `_shape` validator must accept this (per §P3.7 #19 widening)."""
    cap = Capability.model_validate({
        "kind": "stateful", "reconcile": False,
        "fields": [{"name": "temperature", "type": "float", "unit": "°C"}],
    })
    assert cap.fields[0].name == "temperature"


def test_stateful_capability_with_nothing_at_all_still_rejected():
    """A stateful capability with NO actions/select/zones/fields is still meaningless."""
    with pytest.raises(Exception):
        Capability.model_validate({"kind": "stateful"})


def test_attach_capability_maps_assigns_per_device():
    from types import SimpleNamespace

    from wb_mqtt_bridge.infrastructure.capabilities.loader import attach_capability_maps

    devices = {
        "living_room_tv": SimpleNamespace(config=SimpleNamespace(device_class="LgTv"), capabilities=None),
        "mf_amplifier": SimpleNamespace(config=SimpleNamespace(device_class="WirenboardIRDevice"), capabilities=None),
    }
    attach_capability_maps(devices, CAPS)
    assert "input" in devices["living_room_tv"].capabilities.domains()
    assert "toggle" in devices["mf_amplifier"].capabilities.get("power").actions
