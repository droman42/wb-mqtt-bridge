"""VWB-23 — room-scoped group addressing (canonical_first.md §10).

Covers the three layers the feature spans:

- the `group` overlay on capabilities (default = domain name; profile override;
  explicit-null opt-out) and pure-domain membership resolution;
- the `POST /rooms/{room_id}/canonical` endpoint: scope policy (auto/all/one),
  the fan-out allow-list rail, per-member statuses, speakable errors;
- the projections: catalog `group`/`group_defaults`, RoomManager's load-time
  validation of authored `group_defaults`.
"""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from locveil_bridge.app import app as main_app
from locveil_bridge.domain.capabilities.models import Capability, CapabilityMap
from locveil_bridge.domain.rooms.groups import FANOUT_ALLOWED_GROUPS, resolve_members
from locveil_bridge.domain.rooms.service import RoomManager
from locveil_bridge.presentation.api.catalog import build_catalog
from locveil_bridge.presentation.api.routers import devices as devices_router
from locveil_bridge.presentation.api.routers import rooms as rooms_router

LIGHT_SWITCH_MAP = {  # the tagged illumination profile shape
    "power": {"kind": "momentary", "group": "light",
              "actions": {"on": {"command": "power_on"}, "off": {"command": "power_off"}}},
}
POWER_SWITCH_MAP = {  # the untagged twin (sockets, the oven guard)
    "power": {"kind": "momentary",
              "actions": {"on": {"command": "power_on"}, "off": {"command": "power_off"}}},
}
HOOD_LIGHT_MAP = {  # a real `light` domain — matches group "light" implicitly
    "light": {"kind": "stateful", "state_field": "light",
              "actions": {"on": {"command": "set_light", "params": {"state": "on"}},
                          "off": {"command": "set_light", "params": {"state": "off"}}}},
}
COVER_MAP = {
    "cover": {"kind": "stateful", "state_field": "position",
              "actions": {"open": {"command": "open"}, "close": {"command": "close"}}},
}


def _device(device_id: str, room: str, cap_map: dict, state=None):
    d = SimpleNamespace(
        config=SimpleNamespace(
            device_id=device_id, room=room, names={"en": device_id},
            device_class="WbPassthroughDevice", commands=None, state_topics=None,
        ),
        capabilities=CapabilityMap.model_validate(cap_map),
        state=state or {"power": "off"},
    )
    d.get_room = lambda _d=d: _d.config.room
    return d


# ---- the group overlay ------------------------------------------------------------


def test_effective_group_defaults_to_domain():
    cap = Capability.model_validate(COVER_MAP["cover"])
    assert cap.effective_group("cover") == "cover"


def test_effective_group_profile_override():
    cap = Capability.model_validate(LIGHT_SWITCH_MAP["power"])
    assert cap.effective_group("power") == "light"


def test_effective_group_explicit_null_opts_out():
    spec = {**POWER_SWITCH_MAP["power"], "group": None}
    cap = Capability.model_validate(spec)
    assert cap.effective_group("power") is None


def test_resolve_members_overlay_and_room_scoping():
    devices = {
        "lamp": _device("lamp", "kitchen", LIGHT_SWITCH_MAP),
        "hood": _device("hood", "kitchen", HOOD_LIGHT_MAP),
        "socket": _device("socket", "kitchen", POWER_SWITCH_MAP),
        "other_room_lamp": _device("other_room_lamp", "bedroom", LIGHT_SWITCH_MAP),
    }
    members = resolve_members(devices, "kitchen", "light")
    # the socket (group=power by default) and the bedroom lamp are NOT members;
    # each member carries its OWN capability name (lamp: power, hood: light)
    assert [(m.device_id, m.capability) for m in members] == [
        ("hood", "light"), ("lamp", "power"),
    ]
    # the socket IS a member of group "power" — which is not fan-out-eligible
    assert [m.device_id for m in resolve_members(devices, "kitchen", "power")] == ["socket"]
    assert "power" not in FANOUT_ALLOWED_GROUPS


# ---- the endpoint -----------------------------------------------------------------


@pytest.fixture
def world():
    devices = {
        "lamp_a": _device("lamp_a", "living_room", LIGHT_SWITCH_MAP),
        "lamp_b": _device("lamp_b", "living_room", LIGHT_SWITCH_MAP),
        "socket": _device("socket", "living_room", POWER_SWITCH_MAP),
        "curtain": _device("curtain", "living_room", COVER_MAP),
    }
    dm = SimpleNamespace(
        devices=devices,
        get_device=lambda i: devices.get(i),
        perform_action=AsyncMock(return_value={"success": True, "data": {}}),
    )
    room = SimpleNamespace(room_id="living_room", group_defaults=None)
    rm = SimpleNamespace(
        get=lambda rid: room if rid == "living_room" else None,
        list=lambda: [room],
    )
    devices_router.initialize(MagicMock(), dm, None, None)
    rooms_router.initialize(rm, dm)
    return SimpleNamespace(client=TestClient(main_app), dm=dm, room=room, devices=devices)


def _post(world, body, room_id="living_room"):
    return world.client.post(f"/rooms/{room_id}/canonical", json=body)


def test_auto_without_default_fans_out_to_group_only(world):
    r = _post(world, {"group": "light", "action": "on", "wait": False})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["scope_applied"] == "fan_out"
    assert {(x["device_id"], x["status"]) for x in body["results"]} == {
        ("lamp_a", "executed"), ("lamp_b", "executed"),
    }
    # the socket was never touched — perform_action saw only the two lamps
    called_ids = {c.args[0] for c in world.dm.perform_action.await_args_list}
    assert called_ids == {"lamp_a", "lamp_b"}


def test_auto_with_default_targets_only_the_default(world):
    world.room.group_defaults = {"light": "lamp_a"}
    r = _post(world, {"group": "light", "action": "on", "wait": False})
    body = r.json()
    assert body["scope_applied"] == "default"
    assert [x["device_id"] for x in body["results"]] == ["lamp_a"]


def test_scope_all_overrides_the_default(world):
    world.room.group_defaults = {"light": "lamp_a"}
    r = _post(world, {"group": "light", "action": "on", "scope": "all", "wait": False})
    body = r.json()
    assert body["scope_applied"] == "fan_out"
    assert len(body["results"]) == 2


def test_scope_one_without_default_409s(world):
    r = _post(world, {"group": "light", "action": "on", "scope": "one", "wait": False})
    assert r.status_code == 409
    assert r.json()["detail"]["error"]["code"] == "no_default_device"


def test_consequential_group_refuses_fanout(world):
    r = _post(world, {"group": "power", "action": "off", "wait": False})
    assert r.status_code == 409
    assert r.json()["detail"]["error"]["code"] == "fanout_not_allowed"
    world.dm.perform_action.assert_not_awaited()


def test_consequential_group_default_is_allowed(world):
    # a configured default is a deliberate, named choice — no fan-out involved
    world.room.group_defaults = {"power": "socket"}
    r = _post(world, {"group": "power", "action": "off", "wait": False})
    assert r.status_code == 200
    assert r.json()["scope_applied"] == "default"


def test_empty_membership_404s(world):
    r = _post(world, {"group": "fan", "action": "on", "wait": False})
    assert r.status_code == 404
    assert r.json()["detail"]["error"]["code"] == "no_group_members"


def test_unknown_room_404s(world):
    r = _post(world, {"group": "light", "action": "on", "wait": False}, room_id="attic")
    assert r.status_code == 404


def test_member_lacking_action_is_skipped_not_failed(world):
    # lamp_b's map only knows `on` — a group `off` reports it skipped, lamp_a executes
    world.devices["lamp_b"].capabilities = CapabilityMap.model_validate({
        "power": {"kind": "momentary", "group": "light",
                  "actions": {"on": {"command": "power_on"}}},
    })
    r = _post(world, {"group": "light", "action": "off", "wait": False})
    body = r.json()
    assert body["success"] is True
    statuses = {x["device_id"]: x["status"] for x in body["results"]}
    assert statuses == {"lamp_a": "executed", "lamp_b": "skipped"}


def test_member_failure_reported_per_member_not_as_500(world):
    async def flaky(device_id, command, params):
        if device_id == "lamp_b":
            return {"success": False, "error": "driver exploded"}
        return {"success": True, "data": {}}

    world.dm.perform_action = AsyncMock(side_effect=flaky)
    r = _post(world, {"group": "light", "action": "on", "wait": False})
    assert r.status_code == 200
    body = r.json()
    statuses = {x["device_id"]: x["status"] for x in body["results"]}
    assert statuses == {"lamp_a": "executed", "lamp_b": "failed"}
    assert body["success"] is True  # partial success is still success


def test_no_op_member_reported_as_no_op(world):
    world.room.group_defaults = {"light": "lamp_a"}
    world.dm.perform_action = AsyncMock(return_value={"success": True, "data": {"no_op": True}})
    r = _post(world, {"group": "light", "action": "on"})  # wait=True path
    body = r.json()
    assert body["results"][0]["status"] == "no_op"
    assert body["success"] is True


# ---- projections ------------------------------------------------------------------


def test_catalog_exposes_effective_group_and_room_defaults(world):
    world.room.names = {"en": "Living Room"}
    world.room.devices = list(world.devices)
    world.room.group_defaults = {"light": "lamp_a"}
    catalog = build_catalog(world.dm, SimpleNamespace(list=lambda: [world.room]))
    by_id = {d.id: d for d in catalog.devices}
    lamp_power = by_id["lamp_a"].capabilities[0]
    assert (lamp_power.name, lamp_power.group) == ("power", "light")
    socket_power = by_id["socket"].capabilities[0]
    assert (socket_power.name, socket_power.group) == ("power", "power")
    assert catalog.rooms[0].group_defaults == {"light": "lamp_a"}


def test_room_manager_drops_invalid_group_defaults(tmp_path):
    (tmp_path / "rooms.json").write_text(json.dumps({
        "kitchen": {
            "names": {"en": "Kitchen"},
            "group_defaults": {
                "light": "lamp",        # valid: in room + member
                "cover": "lamp",        # invalid: lamp is not a cover
                "light2": "elsewhere",  # invalid: not in the room
            },
        },
    }), encoding="utf-8")
    devices = {
        "lamp": _device("lamp", "kitchen", LIGHT_SWITCH_MAP),
        "elsewhere": _device("elsewhere", "bedroom", LIGHT_SWITCH_MAP),
    }
    rm = RoomManager(tmp_path, SimpleNamespace(devices=devices))
    room = rm.get("kitchen")
    assert room is not None
    assert room.group_defaults == {"light": "lamp"}
