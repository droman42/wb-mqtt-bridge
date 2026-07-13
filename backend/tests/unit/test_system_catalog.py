"""Tests for `GET /system/catalog` and the catalog builder (§P3.7 slice #17).

The catalog is the stable read contract Irene's catalog-consumer subscribes to. It must:

- Project devices' canonical capabilities (name + action names) — the slice's
  cabinet_spots device shows up with a `power` capability exposing `on` and `off`.
- Project rooms with all locales — the slice's `cabinet` room shows up bilingual.
- Carry a deterministic `version` content-hash so Irene only re-fetches on change. We
  pin that same-content -> same-hash AND content-change -> different-hash.
- Sort rooms + devices by id before hashing, so insertion order can't randomise the hash.
- Be served by the live FastAPI endpoint via the same wire shape.

The builder is exercised in isolation with simple fake managers (no MQTT, no FastAPI);
the endpoint test rides on the existing FastAPI TestClient pattern from the canonical
endpoint test file.
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Dict, List, Optional
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from locveil_bridge.domain.capabilities.models import CapabilityMap
from locveil_bridge.presentation.api.catalog import build_catalog
from locveil_bridge.presentation.api.routers import system as system_router


# ----- Test doubles ---------------------------------------------------------


def _fake_device(device_id: str, names: Dict[str, str], device_class: str,
                 room: Optional[str], cap_map_dict: Optional[Dict] = None):
    cfg = SimpleNamespace(
        device_id=device_id,
        names=SimpleNamespace(**names, model_dump=lambda d=names: d),
        device_class=device_class,
        room=room,
    )
    cap_map = CapabilityMap.model_validate(cap_map_dict) if cap_map_dict else None
    return SimpleNamespace(config=cfg, capabilities=cap_map)


def _fake_room(room_id: str, names: Dict[str, str], devices: List[str]):
    return SimpleNamespace(room_id=room_id, names=names, devices=devices)


def _light_switch_cap_map_dict() -> Dict:
    """Mirrors the on-disk `config/capabilities/profiles/light_switch.json`."""
    return {
        "power": {
            "kind": "momentary",
            "actions": {
                "on":  {"command": "power_on"},
                "off": {"command": "power_off"},
            },
        }
    }


@pytest.fixture
def slice_managers():
    """A device manager + room manager carrying just the slice device + room."""
    cabinet_spots = _fake_device(
        device_id="cabinet_spots",
        names={"ru": "Споты", "en": "Spots"},
        device_class="WbPassthroughDevice",
        room="cabinet",
        cap_map_dict=_light_switch_cap_map_dict(),
    )
    dm = SimpleNamespace(devices={"cabinet_spots": cabinet_spots})
    rm = MagicMock()
    rm.list.return_value = [
        _fake_room(
            "cabinet",
            {"ru": "Кабинет", "en": "Study", "de": "Arbeitszimmer"},
            ["cabinet_spots"],
        ),
    ]
    return dm, rm


# ----- Builder: shape ------------------------------------------------------


def test_catalog_carries_slice_device_with_power_capability(slice_managers):
    dm, rm = slice_managers
    cat = build_catalog(dm, rm)
    devs_by_id = {d.id: d for d in cat.devices}
    cab = devs_by_id["cabinet_spots"]
    assert cab.names == {"ru": "Споты", "en": "Spots"}
    assert cab.device_class == "WbPassthroughDevice"
    assert cab.room == "cabinet"
    # The `light_switch` profile contributes a `power` capability with `on` + `off`.
    caps_by_name = {c.name: c for c in cab.capabilities}
    assert "power" in caps_by_name
    action_names = {a.name for a in caps_by_name["power"].actions}
    assert action_names == {"on", "off"}


def test_catalog_carries_room_with_all_locales(slice_managers):
    dm, rm = slice_managers
    cat = build_catalog(dm, rm)
    rooms_by_id = {r.id: r for r in cat.rooms}
    cab = rooms_by_id["cabinet"]
    assert cab.names == {"ru": "Кабинет", "en": "Study", "de": "Arbeitszimmer"}
    assert cab.devices == ["cabinet_spots"]


def test_av_device_without_room_appears_with_null_room():
    """Existing AV configs don't have `room` set yet; the catalog must surface them with
    `room: null` (cleanly) so Irene can still see what exists. They get a room during
    bulk onboarding (§P3.7 #22)."""
    lg = _fake_device(
        device_id="lg_tv_living",
        names={"ru": "Телевизор", "en": "TV"},
        device_class="LgTv",
        room=None,
        cap_map_dict={"power": {"kind": "momentary", "actions": {"on": {"command": "power_on"}}}},
    )
    dm = SimpleNamespace(devices={"lg_tv_living": lg})
    rm = MagicMock(); rm.list.return_value = []
    cat = build_catalog(dm, rm)
    assert cat.devices[0].room is None
    assert cat.devices[0].id == "lg_tv_living"


def test_device_without_capabilities_appears_with_empty_list():
    dev = _fake_device("bare_thing", {"ru": "Штука", "en": "Thing"}, "Bare", "cabinet")
    dm = SimpleNamespace(devices={"bare_thing": dev})
    rm = MagicMock(); rm.list.return_value = []
    cat = build_catalog(dm, rm)
    assert cat.devices[0].capabilities == []


# ----- Builder: version semantics ------------------------------------------


def test_version_is_deterministic_for_same_content(slice_managers):
    dm, rm = slice_managers
    a = build_catalog(dm, rm).version
    b = build_catalog(dm, rm).version
    assert a == b
    assert len(a) == 16  # short SHA-256 hex


def test_version_changes_when_a_device_is_added(slice_managers):
    dm, rm = slice_managers
    before = build_catalog(dm, rm).version
    extra = _fake_device("hall_light", {"ru": "Свет", "en": "Light"},
                         "WbPassthroughDevice", "hall",
                         cap_map_dict=_light_switch_cap_map_dict())
    dm.devices["hall_light"] = extra
    after = build_catalog(dm, rm).version
    assert before != after


def test_version_is_independent_of_dict_insertion_order():
    """Two device managers with the same devices in different insertion order must hash
    to the same version. Otherwise restart order would silently bump the version."""
    dev_a = _fake_device("a", {"ru": "A", "en": "A"}, "X", None,
                         cap_map_dict={"power": {"kind": "momentary",
                                                  "actions": {"on": {"command": "power_on"}}}})
    dev_b = _fake_device("b", {"ru": "B", "en": "B"}, "X", None,
                         cap_map_dict={"power": {"kind": "momentary",
                                                  "actions": {"on": {"command": "power_on"}}}})
    rm = MagicMock(); rm.list.return_value = []
    forward = SimpleNamespace(devices={"a": dev_a, "b": dev_b})
    reverse = SimpleNamespace(devices={"b": dev_b, "a": dev_a})
    assert build_catalog(forward, rm).version == build_catalog(reverse, rm).version


# ----- Endpoint --------------------------------------------------------------


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(system_router.router)
    return app


def test_get_system_catalog_endpoint_returns_slice_payload(slice_managers):
    dm, rm = slice_managers
    system_router.initialize(
        cfg_manager=None, dev_manager=dm, mqt_client=None,
        room_mgr=rm,
    )
    try:
        client = TestClient(_app())
        r = client.get("/system/catalog")
        assert r.status_code == 200, r.text
        body = r.json()
        assert "version" in body and len(body["version"]) == 16
        assert any(d["id"] == "cabinet_spots" for d in body["devices"])
        assert any(r_["id"] == "cabinet" for r_ in body["rooms"])
    finally:
        system_router.initialize(None, None, None)


def test_get_system_catalog_503_when_managers_missing():
    system_router.initialize(None, None, None)
    client = TestClient(_app())
    r = client.get("/system/catalog")
    assert r.status_code == 503


# ----- §P3.7 #19 -- sensor capability fields surface in the catalog ---------


def _sensor_cap_map_dict() -> Dict:
    """Mirrors the on-disk `config/capabilities/profiles/sensor_room.json`."""
    return {
        "sensor": {
            "kind": "stateful", "reconcile": False,
            "fields": [
                {"name": "temperature", "type": "float", "unit": "°C",
                 "labels": {"ru": "температура", "en": "temperature"}},
                {"name": "humidity",    "type": "float", "unit": "%"},
                {"name": "co2",         "type": "int",   "unit": "ppm"},
                {"name": "illuminance", "type": "float", "unit": "lux"},
                {"name": "sound_level", "type": "float", "unit": "dB"},
            ],
        }
    }


def test_catalog_emits_sensor_fields_with_type_unit_labels():
    """A device that profiles `sensor_room` must surface its capability `fields[]` in the
    catalog so voice/UI consumers can read + render typed values without out-of-band
    knowledge."""
    sensors = _fake_device(
        device_id="livingroom_sensors",
        names={"ru": "Сенсоры", "en": "Sensors"},
        device_class="WbPassthroughDevice",
        room="livingroom",
        cap_map_dict=_sensor_cap_map_dict(),
    )
    dm = SimpleNamespace(devices={"livingroom_sensors": sensors})
    rm = MagicMock(); rm.list.return_value = []
    cat = build_catalog(dm, rm)
    cap = cat.devices[0].capabilities[0]
    assert cap.name == "sensor"
    assert cap.actions is None  # pure read surface, no actions
    fields_by_name = {f.name: f for f in cap.fields}
    assert set(fields_by_name) == {"temperature", "humidity", "co2", "illuminance", "sound_level"}
    assert fields_by_name["temperature"].type == "float"
    assert fields_by_name["temperature"].unit == "°C"
    assert fields_by_name["temperature"].labels == {"ru": "температура", "en": "temperature"}
    assert fields_by_name["co2"].type == "int"
    # No motion (dropped from v1 scope per §P3.7 #19 decision 2026-06-08).
    assert "motion" not in fields_by_name


def test_catalog_emits_rgb_field_with_encoding():
    """RGB color is a typed dict on the wire (`"R;G;B"`); the catalog must carry the
    `encoding` so Irene can parse the value-side echo back without guessing."""
    rgb = _fake_device(
        device_id="livingroom_rgb",
        names={"ru": "Подсветка", "en": "Mood Light"},
        device_class="WbPassthroughDevice",
        room="livingroom",
        cap_map_dict={
            "color": {
                "kind": "stateful", "feedback": True, "state_field": "color",
                "actions": {"set": {"command": "set_color", "param_map": {"r": "r", "g": "g", "b": "b"}}},
                "fields": [{"name": "color", "type": "rgb", "encoding": "{r};{g};{b}"}],
            }
        },
    )
    dm = SimpleNamespace(devices={"livingroom_rgb": rgb})
    rm = MagicMock(); rm.list.return_value = []
    cat = build_catalog(dm, rm)
    color = cat.devices[0].capabilities[0]
    assert color.actions and color.actions[0].name == "set"
    assert color.fields and color.fields[0].name == "color"
    assert color.fields[0].type == "rgb"
    assert color.fields[0].encoding == "{r};{g};{b}"


def test_catalog_filters_profile_fields_to_what_device_actually_mirrors():
    """§P3.7 #23 / sauna-sensor case (2026-06-08): a device using a profile with N fields
    but mirroring only K<N of them must surface ONLY the K mirrored fields in the catalog,
    not all N from the profile. The sauna in the shower room uses `sensor_room` (5 declared
    fields: temperature/humidity/co2/illuminance/sound_level) but its wb-msw2_100 only
    exposes temperature + humidity -- the catalog should reflect that truthfully so voice
    consumers don't see promised co2/illuminance/sound_level fields with nothing behind
    them."""
    cfg = SimpleNamespace(
        device_id="shower_sauna_sensors",
        names=SimpleNamespace(ru="Сенсоры сауны", en="Sauna Sensors",
                              model_dump=lambda: {"ru": "Сенсоры сауны", "en": "Sauna Sensors"}),
        device_class="WbPassthroughDevice",
        room="shower",
        # Only 2 of the profile's 5 sensor fields are actually mirrored.
        state_topics={
            "temperature": SimpleNamespace(topic="...", type="float", unit="°C"),
            "humidity":    SimpleNamespace(topic="...", type="float", unit="%"),
        },
    )
    cap_map = CapabilityMap.model_validate(_sensor_cap_map_dict())
    sensor = SimpleNamespace(config=cfg, capabilities=cap_map)
    dm = SimpleNamespace(devices={"shower_sauna_sensors": sensor})
    rm = MagicMock(); rm.list.return_value = []
    cat = build_catalog(dm, rm)
    cap = cat.devices[0].capabilities[0]
    assert cap.name == "sensor"
    field_names = {f.name for f in cap.fields}
    assert field_names == {"temperature", "humidity"}, (
        f"expected only the 2 mirrored fields; got {field_names}"
    )


def test_catalog_keeps_all_profile_fields_when_device_has_no_state_topics():
    """AV devices don't carry `state_topics` at all -- the filtering must SKIP for them
    so they keep emitting every profile-declared field unchanged. Regression guard for
    the §P3.7 #23 catalog filter change."""
    sensors = _fake_device(
        device_id="livingroom_sensors",
        names={"ru": "Сенсоры", "en": "Sensors"},
        device_class="WbPassthroughDevice",
        room="livingroom",
        cap_map_dict=_sensor_cap_map_dict(),
    )
    # The _fake_device helper does NOT add a `state_topics` attribute -- represents the
    # AV-config shape. The catalog must therefore keep all 5 sensor_room fields.
    assert not hasattr(sensors.config, "state_topics")
    dm = SimpleNamespace(devices={"livingroom_sensors": sensors})
    rm = MagicMock(); rm.list.return_value = []
    cat = build_catalog(dm, rm)
    cap = cat.devices[0].capabilities[0]
    field_names = {f.name for f in cap.fields}
    assert field_names == {"temperature", "humidity", "co2", "illuminance", "sound_level"}


def test_catalog_emits_value_labels_with_wire_canonical_labels():
    """§P3.7 #26: enum-typed fields project their `values` as the full ValueLabel triplet —
    `wire` (informational for clients, authoritative on bus), `canonical` (what voice/UI
    sends back via /devices/{id}/canonical), `labels` (per-locale strings for UI dropdowns
    + voice intent matching). Mirrors the HVAC mode shape."""
    climate = _fake_device(
        device_id="livingroom_hvac",
        names={"ru": "Кондиционер", "en": "AC"},
        device_class="WbPassthroughDevice",
        room="livingroom",
        cap_map_dict={
            "climate": {
                "kind": "stateful", "feedback": True,
                "actions": {"set_mode": {"command": "set_mode", "param_map": {"mode": "mode"}}},
                "fields": [{
                    "name": "mode", "type": "enum",
                    "values": [
                        {"wire": "1", "canonical": "heat", "labels": {"ru": "Обогрев", "en": "Heat", "de": "Heizen"}},
                        {"wire": "2", "canonical": "cool", "labels": {"ru": "Охлаждение", "en": "Cool", "de": "Kühlen"}},
                    ],
                }],
            }
        },
    )
    dm = SimpleNamespace(devices={"livingroom_hvac": climate})
    rm = MagicMock(); rm.list.return_value = []
    cat = build_catalog(dm, rm)
    cap = cat.devices[0].capabilities[0]
    mode = cap.fields[0]
    assert mode.type == "enum"
    assert mode.values is not None and len(mode.values) == 2
    assert mode.values[0].wire == "1" and mode.values[0].canonical == "heat"
    assert mode.values[0].labels == {"ru": "Обогрев", "en": "Heat", "de": "Heizen"}
    assert mode.values[1].wire == "2" and mode.values[1].canonical == "cool"


def test_catalog_emits_bare_string_values_with_canonical_equal_to_wire():
    """Back-compat regression: a profile authored with `values: ["a", "b"]` still projects
    into the catalog, with each entry's `wire == canonical` and `labels == None`. Lets
    profiles defer adding labels without losing catalog presence."""
    enum_field = _fake_device(
        device_id="x",
        names={"ru": "X", "en": "X"},
        device_class="WbPassthroughDevice",
        room=None,
        cap_map_dict={
            "climate": {
                "kind": "stateful", "feedback": True,
                "actions": {"set_mode": {"command": "set_mode", "param_map": {"mode": "mode"}}},
                "fields": [{"name": "mode", "type": "enum", "values": ["heat", "cool"]}],
            }
        },
    )
    dm = SimpleNamespace(devices={"x": enum_field})
    rm = MagicMock(); rm.list.return_value = []
    cat = build_catalog(dm, rm)
    vs = cat.devices[0].capabilities[0].fields[0].values
    assert vs is not None and len(vs) == 2
    assert vs[0].wire == "heat" and vs[0].canonical == "heat" and vs[0].labels is None
    assert vs[1].wire == "cool" and vs[1].canonical == "cool"


def test_version_changes_when_value_labels_change(slice_managers):
    """§P3.7 #26: any change to a field's value-label table MUST bump the catalog version
    so voice (Irene) re-fetches. Adding a label, adding an entry, renaming canonical — all
    surface."""
    dm, rm = slice_managers
    cap_map_v1 = {
        "climate": {
            "kind": "stateful", "feedback": True,
            "actions": {"set_mode": {"command": "set_mode", "param_map": {"mode": "mode"}}},
            "fields": [{
                "name": "mode", "type": "enum",
                "values": [{"wire": "1", "canonical": "heat", "labels": {"ru": "Обогрев", "en": "Heat"}}],
            }],
        }
    }
    dm.devices["cabinet_spots"].capabilities = CapabilityMap.model_validate(cap_map_v1)
    before = build_catalog(dm, rm).version
    cap_map_v2 = {
        "climate": {
            "kind": "stateful", "feedback": True,
            "actions": {"set_mode": {"command": "set_mode", "param_map": {"mode": "mode"}}},
            "fields": [{
                "name": "mode", "type": "enum",
                "values": [
                    {"wire": "1", "canonical": "heat", "labels": {"ru": "Обогрев", "en": "Heat", "de": "Heizen"}},
                ],
            }],
        }
    }
    dm.devices["cabinet_spots"].capabilities = CapabilityMap.model_validate(cap_map_v2)
    after = build_catalog(dm, rm).version
    assert before != after, "Adding a locale to a value label must bump catalog version"


def test_version_changes_when_a_capability_field_is_added(slice_managers):
    """Adding a `fields[]` entry to any capability MUST bump the catalog version, so Irene
    re-fetches when the typed surface widens (a new sensor field exposed, RGB encoding
    landed for a previously bare device, etc.)."""
    dm, rm = slice_managers
    before = build_catalog(dm, rm).version
    # Widen cabinet_spots's `power` capability with a (contrived) state field.
    extended_cap_map = {
        "power": {
            "kind": "momentary",
            "actions": {"on": {"command": "power_on"}, "off": {"command": "power_off"}},
        },
        "brightness": {
            "kind": "stateful", "feedback": True, "state_field": "level",
            "actions": {"set": {"command": "set_brightness", "param_map": {"level": "level"}}},
            "fields": [{"name": "level", "type": "int", "unit": "%"}],
        }
    }
    dm.devices["cabinet_spots"].capabilities = CapabilityMap.model_validate(extended_cap_map)
    after = build_catalog(dm, rm).version
    assert before != after


def test_catalog_derives_action_param_values_from_same_named_enum_field():
    """VWB-24: an action param whose canonical name matches an enum field derives the
    field's ValueLabel table — authored ONCE on the field, projected onto the param.
    The hvac profile's param_map renames (fan→speed etc.) exist to make names match."""
    hvac = _fake_device(
        device_id="bedroom_hvac",
        names={"ru": "Кондиционер", "en": "AC"},
        device_class="WbPassthroughDevice",
        room="bedroom",
        cap_map_dict={
            "climate": {
                "kind": "stateful", "feedback": True,
                "actions": {
                    "set_mode": {"command": "set_mode", "param_map": {"mode": "mode"}},
                    "set_fan": {"command": "set_fan", "param_map": {"fan": "speed"}},
                },
                "fields": [
                    {"name": "mode", "type": "enum", "values": [
                        {"wire": "COOL", "canonical": "cool",
                         "labels": {"ru": "охлаждение", "en": "cool", "de": "Kühlen"}},
                        {"wire": "HEAT", "canonical": "heat",
                         "labels": {"ru": "обогрев", "en": "heat", "de": "Heizen"}},
                    ]},
                    {"name": "fan", "type": "enum", "values": [
                        {"wire": "AUTO", "canonical": "auto",
                         "labels": {"ru": "авто", "en": "auto", "de": "Automatik"}},
                    ]},
                ],
            }
        },
    )
    _param = lambda name: SimpleNamespace(  # noqa: E731
        name=name, type="string", required=True, default=None,
        min=None, max=None, description=None, units=None,
    )
    hvac.config.commands = {
        "set_mode": SimpleNamespace(params=[_param("mode")]),
        "set_fan": SimpleNamespace(params=[_param("speed")]),
    }
    dm = SimpleNamespace(devices={"bedroom_hvac": hvac})
    rm = MagicMock(); rm.list.return_value = []
    cat = build_catalog(dm, rm)
    climate = cat.devices[0].capabilities[0]

    set_mode = next(a for a in climate.actions if a.name == "set_mode")
    (mode_param,) = set_mode.params
    assert mode_param.name == "mode"
    assert mode_param.values is not None and len(mode_param.values) == 2
    assert mode_param.values[0].wire == "COOL" and mode_param.values[0].canonical == "cool"
    assert mode_param.values[0].labels == {"ru": "охлаждение", "en": "cool", "de": "Kühlen"}
    assert mode_param.options_from is None

    set_fan = next(a for a in climate.actions if a.name == "set_fan")
    (fan_param,) = set_fan.params
    assert fan_param.name == "fan"  # canonical name = the FIELD name, not native "speed"
    assert fan_param.values is not None and fan_param.values[0].canonical == "auto"


def test_catalog_param_without_matching_enum_field_stays_untyped():
    """The derivation is by exact name match against an enum-with-values field — a param
    with no counterpart field keeps `values: None` (an honest open string)."""
    dev = _fake_device(
        device_id="x",
        names={"ru": "X", "en": "X"},
        device_class="WbPassthroughDevice",
        room=None,
        cap_map_dict={
            "climate": {
                "kind": "stateful", "feedback": True,
                "actions": {"set_mode": {"command": "set_mode", "param_map": {"mode": "mode"}}},
                "fields": [{"name": "other", "type": "enum", "values": ["a", "b"]}],
            }
        },
    )
    dev.config.commands = {
        "set_mode": SimpleNamespace(params=[SimpleNamespace(
            name="mode", type="string", required=True, default=None,
            min=None, max=None, description=None, units=None,
        )]),
    }
    dm = SimpleNamespace(devices={"x": dev})
    rm = MagicMock(); rm.list.return_value = []
    cat = build_catalog(dm, rm)
    set_mode = next(a for a in cat.devices[0].capabilities[0].actions if a.name == "set_mode")
    (mode_param,) = set_mode.params
    assert mode_param.values is None and mode_param.options_from is None
