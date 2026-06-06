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

from wb_mqtt_bridge.domain.capabilities.models import CapabilityMap
from wb_mqtt_bridge.presentation.api.catalog import build_catalog
from wb_mqtt_bridge.presentation.api.routers import system as system_router


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
