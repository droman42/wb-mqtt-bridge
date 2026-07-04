"""SCN-6: per-room Scenario Manager proxy — domain resolution, canonical route,
catalog entities, WB card executor (canonical_first.md §3–§4)."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from wb_mqtt_bridge.app import app as main_app
from wb_mqtt_bridge.domain.capabilities.models import CapabilityMap
from wb_mqtt_bridge.domain.scenarios.proxy import (
    INHERITABLE_DOMAINS,
    NO_SCENARIO,
    ScenarioProxy,
    ScenarioProxyError,
)
from wb_mqtt_bridge.domain.scenarios.service import ScenarioManager
from wb_mqtt_bridge.infrastructure.scenarios.wb_adapter import ScenarioWBAdapter
from wb_mqtt_bridge.presentation.api.catalog import build_catalog
from wb_mqtt_bridge.presentation.api.routers import devices as devices_router

pytestmark = pytest.mark.unit


# ---- fixtures ---------------------------------------------------------------

VOLUME_MAP = {
    "volume": {
        "kind": "momentary",
        "actions": {
            "up": {"command": "volume_up"},
            "down": {"command": "volume_down"},
        },
    }
}
PLAYBACK_MAP = {
    "playback": {
        "kind": "momentary",
        "actions": {
            "play": {"command": "play"},
            "pause": {"command": "pause"},
            "set_pos": {"command": "seek", "param_map": {"pos": "position"},
                        "params": {"mode": "abs"}},
        },
    }
}


def _device(device_id, cap_dict, room="living_room"):
    d = SimpleNamespace(
        device_id=device_id,
        room=room,
        capabilities=CapabilityMap.model_validate(cap_dict),
        state={"power": False},
        execute_action=AsyncMock(return_value={"success": True}),
    )
    d.get_current_state = lambda _d=d: _d.state
    d.get_room = lambda _d=d: _d.room
    d.get_available_commands = lambda: {}
    return d


def _scenario(scenario_id, room, roles, source="amp"):
    return {
        "scenario_id": scenario_id,
        "names": {"ru": scenario_id, "en": scenario_id.replace("_", " ").title()},
        "room_id": room,
        "roles": roles,
        "source": source,
    }


@pytest.fixture
def world(tmp_path):
    """A two-room world: living_room (movie: volume+playback roles) and
    children_room (cartoons: playback role only)."""
    amp = _device("amp", VOLUME_MAP)
    player = _device("player", PLAYBACK_MAP)
    kid_tv = _device("kid_tv", PLAYBACK_MAP, room="children_room")

    scenario_dir = tmp_path / "scenarios"
    scenario_dir.mkdir()
    for data in (
        _scenario("movie", "living_room", {"volume": "amp", "playback": "player"}),
        _scenario("music", "living_room", {"volume": "amp"}),
        _scenario("cartoons", "children_room", {"playback": "kid_tv"}, source="kid_tv"),
    ):
        (scenario_dir / f"{data['scenario_id']}.json").write_text(json.dumps(data))

    devices = {"amp": amp, "player": player, "kid_tv": kid_tv}
    device_manager = SimpleNamespace(devices=devices, get_device=lambda i: devices.get(i))

    class _Store:
        def __init__(self):
            self.data = {}

        async def load(self, key):
            return self.data.get(key)

        async def save(self, key, value):
            self.data[key] = value

        async def delete(self, key):
            self.data.pop(key, None)

    manager = ScenarioManager(
        device_manager=device_manager,
        room_manager=SimpleNamespace(),
        state_repository=_Store(),
        scenario_dir=scenario_dir,
    )
    proxy = ScenarioProxy(manager, device_manager)
    return SimpleNamespace(manager=manager, proxy=proxy, devices=devices)


# ---- domain proxy -----------------------------------------------------------

@pytest.mark.asyncio
async def test_entity_registry_one_per_scenario_bearing_room(world):
    await world.manager.initialize()
    assert world.proxy.rooms() == ["children_room", "living_room"]
    assert world.proxy.entity_room("scenario_manager_living_room") == "living_room"
    assert world.proxy.entity_room("scenario_manager_bedroom") is None  # no scenarios there
    assert world.proxy.entity_room("mf_amplifier") is None


@pytest.mark.asyncio
async def test_resolve_requires_active_scenario_in_that_room(world):
    await world.manager.initialize()
    with pytest.raises(ScenarioProxyError) as e:
        world.proxy.resolve("living_room", "volume")
    assert e.value.code == "no_active_scenario"

    # Activating the OTHER room doesn't help — resolution is room-scoped.
    await world.proxy.activate("children_room", "cartoons")
    with pytest.raises(ScenarioProxyError) as e:
        world.proxy.resolve("living_room", "volume")
    assert e.value.code == "no_active_scenario"


@pytest.mark.asyncio
async def test_resolve_fire_time_against_the_rooms_active_scenario(world):
    await world.manager.initialize()
    await world.proxy.activate("living_room", "movie")
    assert world.proxy.resolve("living_room", "volume")[0] == "amp"
    assert world.proxy.resolve("living_room", "playback")[0] == "player"

    # Switch to music (no playback role) — same call now 409s: fire-time, not cached.
    await world.proxy.activate("living_room", "music")
    assert world.proxy.resolve("living_room", "volume")[0] == "amp"
    with pytest.raises(ScenarioProxyError) as e:
        world.proxy.resolve("living_room", "playback")
    assert e.value.code == "role_unbound"


@pytest.mark.asyncio
async def test_activate_validates_scenario_and_room(world):
    await world.manager.initialize()
    with pytest.raises(ScenarioProxyError) as e:
        await world.proxy.activate("living_room", "nope")
    assert e.value.code == "unknown_scenario"
    with pytest.raises(ScenarioProxyError) as e:
        await world.proxy.activate("living_room", "cartoons")  # belongs to children_room
    assert e.value.code == "scenario_room_mismatch"


@pytest.mark.asyncio
async def test_two_rooms_active_concurrently_and_deactivate_is_room_scoped(world):
    await world.manager.initialize()
    await world.proxy.activate("living_room", "movie")
    await world.proxy.activate("children_room", "cartoons")
    assert world.proxy.active_id("living_room") == "movie"
    assert world.proxy.active_id("children_room") == "cartoons"

    await world.proxy.deactivate("children_room")
    assert world.proxy.active_id("children_room") == NO_SCENARIO
    assert world.proxy.active_id("living_room") == "movie"  # untouched


@pytest.mark.asyncio
async def test_execute_translates_via_capability_map(world):
    await world.manager.initialize()
    await world.proxy.activate("living_room", "movie")

    result = await world.proxy.execute("living_room", "playback", "set_pos", {"pos": 42})
    assert result["executed_on"] == "player"
    assert result["command"] == "seek"
    # param_map renamed pos->position; fixed params overlaid.
    world.devices["player"].execute_action.assert_any_call(
        "seek", {"position": 42, "mode": "abs"}, source="scenario"
    )


@pytest.mark.asyncio
async def test_union_actions_is_config_static_not_activation_dependent(world):
    await world.manager.initialize()
    union = world.proxy.union_actions("living_room")
    assert union["volume"] == ["down", "up"]
    assert union["playback"] == ["pause", "play", "set_pos"]
    # Nothing active — the union is still there (static advertisement).
    assert world.proxy.active_id("living_room") == NO_SCENARIO


# ---- canonical REST route ----------------------------------------------------

@pytest.fixture
def client(world):
    dm = SimpleNamespace(
        devices=world.devices,
        get_device=lambda i: world.devices.get(i),
        perform_action=AsyncMock(return_value={"success": True, "data": {"no_op": True}}),
    )
    devices_router.initialize(MagicMock(), dm, None, world.proxy)
    return TestClient(main_app)


@pytest.mark.asyncio
async def test_route_scenario_set_and_off(world, client):
    await world.manager.initialize()

    r = client.post("/devices/scenario_manager_living_room/canonical",
                    json={"capability": "scenario", "action": "set", "params": {"value": "movie"}})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["device_id"] == "scenario_manager_living_room"
    assert body["state"]["scenario"] == "movie"

    r = client.post("/devices/scenario_manager_living_room/canonical",
                    json={"capability": "scenario", "action": "off"})
    assert r.status_code == 200
    assert r.json()["state"]["scenario"] == NO_SCENARIO


@pytest.mark.asyncio
async def test_route_inherited_domain_carries_executed_on(world, client):
    await world.manager.initialize()
    await world.proxy.activate("living_room", "movie")

    r = client.post("/devices/scenario_manager_living_room/canonical",
                    json={"capability": "volume", "action": "up"})
    assert r.status_code == 200
    body = r.json()
    assert body["device_id"] == "scenario_manager_living_room"
    assert body["executed_on"] == "amp"


@pytest.mark.asyncio
async def test_route_409_when_room_inactive_or_role_unbound(world, client):
    await world.manager.initialize()

    r = client.post("/devices/scenario_manager_living_room/canonical",
                    json={"capability": "volume", "action": "up"})
    assert r.status_code == 409
    assert r.json()["detail"]["error"]["code"] == "no_active_scenario"

    await world.proxy.activate("living_room", "music")  # music binds no playback role
    r = client.post("/devices/scenario_manager_living_room/canonical",
                    json={"capability": "playback", "action": "play"})
    assert r.status_code == 409
    assert r.json()["detail"]["error"]["code"] == "role_unbound"


# ---- catalog entities ---------------------------------------------------------

@pytest.mark.asyncio
async def test_catalog_carries_manager_entities_with_static_union(world):
    await world.manager.initialize()
    catalog = build_catalog(
        SimpleNamespace(devices={}), None, world.proxy
    )
    by_id = {d.id: d for d in catalog.devices}
    entity = by_id["scenario_manager_living_room"]
    assert entity.room == "living_room"
    caps = {c.name: c for c in entity.capabilities}

    # scenario select: value enum over the room's scenarios; field carries `none` too.
    # (params are typed CatalogParam since VWB-20 — attribute access, not dict.)
    set_param = caps["scenario"].actions[0].params[0]
    assert set_param.required is True
    assert {v.canonical for v in set_param.values} == {"movie", "music"}
    field_values = {v.canonical for v in caps["scenario"].fields[0].values}
    assert field_values == {"movie", "music", "none"}

    # static union of inheritable domains only.
    assert set(caps) - {"scenario"} <= set(INHERITABLE_DOMAINS)
    assert {a.name for a in caps["volume"].actions} == {"up", "down"}

    # children room entity exists independently.
    assert "scenario_manager_children_room" in by_id


@pytest.mark.asyncio
async def test_catalog_version_stable_across_activation(world):
    await world.manager.initialize()
    dm = SimpleNamespace(devices={})
    v_before = build_catalog(dm, None, world.proxy).version
    await world.proxy.activate("living_room", "movie")
    v_after = build_catalog(dm, None, world.proxy).version
    assert v_before == v_after  # byte-stable catalog across switches


# ---- WB card adapter -----------------------------------------------------------

@pytest.mark.asyncio
async def test_wb_card_setup_publishes_and_subscribes_per_room(world):
    await world.manager.initialize()
    wb = MagicMock()
    wb.setup_wb_device_from_config = AsyncMock(return_value=True)
    wb.get_subscription_topics_from_config = MagicMock(
        side_effect=lambda cfg: [f"/devices/{cfg['device_id']}/controls/scenario/on"]
    )
    wb.update_control_state = AsyncMock(return_value=True)
    bus = SimpleNamespace(subscribe=AsyncMock())

    adapter = ScenarioWBAdapter(world.proxy, wb, bus)
    await adapter.setup()

    assert wb.setup_wb_device_from_config.await_count == 2  # one card per room
    assert bus.subscribe.await_count == 2
    # value topic seeded with `none` for both rooms
    calls = {c.args for c in wb.update_control_state.await_args_list}
    assert ("scenario_manager_living_room", "scenario", NO_SCENARIO) in calls
    assert ("scenario_manager_children_room", "scenario", NO_SCENARIO) in calls

    # activation-changed hook installed: a switch republishes the value topic.
    wb.update_control_state.reset_mock()
    await world.proxy.activate("living_room", "movie")
    calls = {c.args for c in wb.update_control_state.await_args_list}
    assert ("scenario_manager_living_room", "scenario", "movie") in calls


@pytest.mark.asyncio
async def test_wb_card_executor_routes_scenario_and_pushbuttons(world):
    await world.manager.initialize()
    wb = MagicMock()
    wb.setup_wb_device_from_config = AsyncMock(return_value=True)
    wb.get_subscription_topics_from_config = MagicMock(return_value=[])
    wb.update_control_state = AsyncMock(return_value=True)
    adapter = ScenarioWBAdapter(world.proxy, wb, SimpleNamespace(subscribe=AsyncMock()))

    execute = adapter._executor("living_room")

    await execute("scenario", "movie", {"value": "movie"})
    assert world.proxy.active_id("living_room") == "movie"

    await execute("volume_up", "1", {})
    world.devices["amp"].execute_action.assert_any_call("volume_up", {}, source="scenario")

    await execute("scenario", "none", {"value": "none"})
    assert world.proxy.active_id("living_room") == NO_SCENARIO

    # A press with nothing active must not raise (logged, not thrown).
    await execute("play", "1", {})
