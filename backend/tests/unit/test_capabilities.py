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


def test_hvac_climate_actions_cover_mode_fan_vane_widevane_setpoint():
    """`hvac` profile gives voice/UI 7 actions on the `climate` capability: on/off plus
    set_mode / set_fan / set_vane / set_widevane / set_setpoint. Each enum-encoded
    field is a typed `fields[]` entry with a full ValueLabel table — wire values from
    the mitsubishi2wb firmware (sister repo, `html_pages.h` ~line 137), canonical
    names short identifier-safe, labels trilingual (ru/en/de). §P3.7 #26 reversed the
    earlier `2026-06-08` decision to leave these fields off the catalog: with the
    value-label layer in place, a typed `enum` claim is now truthful and voice can
    autodiscover the table."""
    m = load_capability_map("WbPassthroughDevice", "any_hvac",
                             capabilities_dir=CAPS, capability_profile="hvac")
    climate = m.get("climate")
    assert set(climate.actions) == {
        "on", "off", "set_mode", "set_fan", "set_vane", "set_widevane", "set_setpoint",
    }
    field_names = {f.name for f in climate.fields}
    assert field_names == {
        "temperature", "room_temperature", "mode", "fan", "vane", "widevane",
    }
    # `temperature` field is the SETPOINT (writable; mapped to WB control of the same
    # name in the firmware — see set_setpoint action's device-config topic).
    temperature = next(f for f in climate.fields if f.name == "temperature")
    assert temperature.type == "float" and temperature.unit == "°C"
    # Param-map renames are identity (canonical → native) for all set_* actions.
    assert climate.actions["set_widevane"].param_map == {"direction": "direction"}


def test_hvac_profile_mode_carries_firmware_wire_values_and_canonical_labels():
    """Mode field's value table mirrors the firmware dropdown order (AUTO/DRY/COOL/HEAT/FAN
    per mitsubishi2wb html_pages.h line ~137-141) and uses canonical `fan_only` for the
    "FAN" wire mode to avoid colliding with the `fan` field name."""
    m = load_capability_map("WbPassthroughDevice", "any_hvac",
                             capabilities_dir=CAPS, capability_profile="hvac")
    mode = next(f for f in m.get("climate").fields if f.name == "mode")
    assert mode.type == "enum"
    assert [v.wire for v in mode.values] == ["AUTO", "DRY", "COOL", "HEAT", "FAN"]
    assert [v.canonical for v in mode.values] == ["auto", "dry", "cool", "heat", "fan_only"]
    # Every entry carries trilingual labels (the catalog surface for voice/UI).
    for v in mode.values:
        assert v.labels is not None
        assert v.labels.ru and v.labels.en
        assert getattr(v.labels, "de", None)


def test_hvac_profile_widevane_carries_directional_canonical_for_firmware_symbols():
    """Widevane wire values are firmware-internal symbols (`<<`, `<`, `|`, `>`, `>>`, `<>`,
    `SWING`); canonical names are directional (`far_left`, `left`, `center`, `right`,
    `far_right`, `split`, `swing`) for voice + UI ergonomics."""
    m = load_capability_map("WbPassthroughDevice", "any_hvac",
                             capabilities_dir=CAPS, capability_profile="hvac")
    widevane = next(f for f in m.get("climate").fields if f.name == "widevane")
    assert {v.wire for v in widevane.values} == {"SWING", "<<", "<", "|", ">", ">>", "<>"}
    assert {v.canonical for v in widevane.values} == {
        "swing", "far_left", "left", "center", "right", "far_right", "split",
    }


def test_hvac_device_configs_state_topics_match_profile_value_tables():
    """Drift-guard: each of the 3 HVAC device configs must mirror the profile's wire ↔
    canonical pairs in its state_topics. Labels live only in the profile (catalog
    source-of-truth); the configs duplicate only what the driver needs to translate.
    Catches the silent failure where a wire value drifts between the profile and the
    config (voice would publish canonical, the unconfigured wire would not echo back)."""
    from wb_mqtt_bridge.infrastructure.config.models import WbPassthroughDeviceConfig

    DEVICES_ROOT = CAPS.parent / "devices" / "wb-devices"
    hvac_configs = [
        DEVICES_ROOT / "bedroom" / "bedroom_hvac.json",
        DEVICES_ROOT / "living_room" / "living_room_hvac.json",
        DEVICES_ROOT / "children_room" / "children_room_hvac.json",
    ]

    m = load_capability_map("WbPassthroughDevice", "any_hvac",
                             capabilities_dir=CAPS, capability_profile="hvac")
    profile_tables = {
        f.name: [(v.wire, v.canonical) for v in f.values]
        for f in m.get("climate").fields
        if f.values is not None
    }
    assert set(profile_tables) == {"mode", "fan", "vane", "widevane"}, (
        f"profile fields with value tables drifted: {sorted(profile_tables)}"
    )

    for path in hvac_configs:
        data = json.loads(path.read_text())
        cfg = WbPassthroughDeviceConfig.create_from_dict(data)
        for field in ("mode", "fan", "vane", "widevane"):
            spec = cfg.state_topics[field]
            assert spec.type == "enum", f"{path.name}.{field}.type must be enum"
            cfg_pairs = [(v.wire, v.canonical) for v in (spec.values or [])]
            assert cfg_pairs == profile_tables[field], (
                f"{path.name}.{field} state_topic value table drifted from profile: "
                f"config has {cfg_pairs}, profile has {profile_tables[field]}"
            )


def test_heating_loop_profile_has_climate_with_typed_measurement_fields():
    """Heating loop is the most composite simple shape: actuator (on/off) + setpoint slider
    + room-temp sensor reads. Modeled as one `climate` capability. Actions: on/off (momentary,
    publish to the actuator) + set_setpoint (param-carrying). Fields: `setpoint` and
    `room_temperature` only -- the on/off mode is INTENTIONALLY NOT a typed catalog field
    (mirrors the light_switch pattern: WB controls publish raw `"0"`/`"1"`, devices mirror
    that bare string for internal no_op detection, but the catalog doesn't promise a
    typed `mode` field whose values would diverge from the wire payload). Decision recorded
    2026-06-08 alongside cabinet heating-loop authoring."""
    m = load_capability_map("WbPassthroughDevice", "any_radiator",
                             capabilities_dir=CAPS, capability_profile="heating_loop")
    climate = m.get("climate")
    assert {a for a in climate.actions} == {"on", "off", "set_setpoint"}
    # Mode is reachable via on/off actions; intentionally NOT exposed as a typed field.
    assert {f.name for f in climate.fields} == {"setpoint", "room_temperature"}
    assert climate.state_field == "mode"  # reconciler still tracks on/off state internally


def test_dimmable_light_inherits_power_plus_brightness_with_level_field():
    m = load_capability_map("WbPassthroughDevice", "any_dimmer",
                             capabilities_dir=CAPS, capability_profile="dimmable_light")
    assert m.get("power").actions["on"].command == "power_on"
    bright = m.get("brightness")
    assert bright.actions["set"].command == "set_brightness"
    level = bright.fields[0]
    assert level.name == "level" and level.type == "int" and level.unit == "%"


def test_cover_profile_has_open_close_set_position_actions():
    """`cover` exposes open/close/set_position; `stop` is intentionally NOT in the
    profile -- Dooya position sliders have no native stop control and we don't (yet)
    have a driver helper that re-publishes the current mirrored position to halt
    motion mid-travel. Decision 2026-06-08 alongside living_room cover authoring:
    keep the contract truthful (don't promise an action we can't honour); reconsider
    if voice grows a stop-mid-motion command."""
    m = load_capability_map("WbPassthroughDevice", "any_cover",
                             capabilities_dir=CAPS, capability_profile="cover")
    actions = m.get("cover").actions
    assert {"open", "close", "set_position"} == set(actions.keys())
    assert "stop" not in actions
    assert actions["set_position"].param_map == {"pct": "pct"}


def test_capability_field_values_accept_bare_string_list_back_compat():
    """§P3.7 #26 back-compat: a `values: ["a", "b"]` entry on an enum field must keep
    parsing — normalised into `[ValueLabel(wire="a", canonical="a", labels=None), ...]`
    so existing profiles never had to be migrated."""
    cap = Capability.model_validate({
        "kind": "stateful", "reconcile": False,
        "fields": [{"name": "mode", "type": "enum", "values": ["heat", "cool", "auto"]}],
    })
    vs = cap.fields[0].values
    assert vs is not None and len(vs) == 3
    assert vs[0].wire == "heat" and vs[0].canonical == "heat" and vs[0].labels is None
    assert [v.canonical for v in vs] == ["heat", "cool", "auto"]


def test_capability_field_values_accept_full_value_label_with_labels():
    """§P3.7 #26 full form: every entry can declare `wire` (MQTT payload), `canonical`
    (action identifier), and localized `labels`. Matches the HVAC mode shape — wire
    integers, canonical English names, ru/en/de labels for UI + voice."""
    cap = Capability.model_validate({
        "kind": "stateful", "reconcile": False,
        "fields": [{
            "name": "mode", "type": "enum",
            "values": [
                {"wire": "1", "canonical": "heat", "labels": {"ru": "Обогрев", "en": "Heat", "de": "Heizen"}},
                {"wire": "2", "canonical": "cool", "labels": {"ru": "Охлаждение", "en": "Cool", "de": "Kühlen"}},
            ],
        }],
    })
    vs = cap.fields[0].values
    assert vs is not None and len(vs) == 2
    assert vs[0].wire == "1" and vs[0].canonical == "heat"
    assert vs[0].labels is not None and vs[0].labels.ru == "Обогрев" and vs[0].labels.en == "Heat"
    # Extra locales accepted via LocalizedName(extra="allow"):
    assert getattr(vs[0].labels, "de") == "Heizen"


def test_capability_field_values_mixed_back_compat_and_full_form_normalise():
    """Mixing forms inside one list is supported (transition aid). Bare strings widen
    to wire==canonical; dicts pass through with their declared shape."""
    cap = Capability.model_validate({
        "kind": "stateful", "reconcile": False,
        "fields": [{
            "name": "mode", "type": "enum",
            "values": [
                "auto",
                {"wire": "1", "canonical": "heat", "labels": {"ru": "Обогрев", "en": "Heat"}},
            ],
        }],
    })
    vs = cap.fields[0].values
    assert vs is not None
    assert vs[0].wire == "auto" and vs[0].canonical == "auto" and vs[0].labels is None
    assert vs[1].wire == "1" and vs[1].canonical == "heat" and vs[1].labels is not None


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
