"""VWB-17: sequence-form capability actions route through the canonical seam.

Covers the shared domain expansion (CapabilityAction.expand), the canonical REST
endpoint's step-by-step execution (order, per-step params, inter-step delays,
mid-sequence failure), and the Scenario Manager proxy's sequence execution.

No shipped capability map uses sequences yet (they were previously unroutable), so
every map here is synthetic — exactly the situation SCN-7 needs guarded: once the
UI rides canonical, one authored sequence-form action must not break a page button.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from wb_mqtt_bridge.app import app as main_app
from wb_mqtt_bridge.domain.capabilities.models import CapabilityAction, CapabilityMap
from wb_mqtt_bridge.presentation.api.routers import devices as devices_router

pytestmark = pytest.mark.unit


# ---- domain expansion --------------------------------------------------------

def test_expand_command_form_is_a_single_step():
    action = CapabilityAction.model_validate(
        {"command": "set_volume", "param_map": {"level": "value"}, "params": {"zone": 2}}
    )
    steps = action.expand({"level": 30})
    assert len(steps) == 1
    assert steps[0].command == "set_volume"
    assert steps[0].params == {"value": 30, "zone": 2}


def test_expand_sequence_each_step_applies_its_own_translation():
    action = CapabilityAction.model_validate({
        "sequence": [
            {"command": "wake", "delay_after_ms": 300},
            {"command": "open_tray", "param_map": {"slot": "tray"}},
            {"command": "confirm", "params": {"button": "ok"}},
        ]
    })
    steps = action.expand({"slot": 2})
    assert [s.command for s in steps] == ["wake", "open_tray", "confirm"]
    # incoming params rename per-step; steps without a matching param_map pass through
    assert steps[0].params == {"slot": 2}
    assert steps[1].params == {"tray": 2}
    assert steps[2].params == {"slot": 2, "button": "ok"}
    assert steps[0].delay_after_ms == 300


def test_expand_nested_sequences_flatten_in_order():
    action = CapabilityAction.model_validate({
        "sequence": [
            {"command": "a"},
            {"sequence": [{"command": "b"}, {"command": "c"}]},
            {"command": "d"},
        ]
    })
    assert [s.command for s in action.expand()] == ["a", "b", "c", "d"]


# ---- canonical REST endpoint ---------------------------------------------------

SEQUENCE_MAP = {
    "playback": {
        "kind": "momentary",
        "actions": {
            "open_tray": {
                "sequence": [
                    {"command": "wake", "delay_after_ms": 10},
                    {"command": "tray", "params": {"mode": "open"}},
                ]
            },
            "play": {"command": "play"},
        },
    }
}


@pytest.fixture
def sequence_world():
    device = SimpleNamespace(
        device_id="ld",
        capabilities=CapabilityMap.model_validate(SEQUENCE_MAP),
        state={"power": True},
    )
    calls: list = []

    async def perform_action(device_id, command, params):
        calls.append((command, dict(params)))
        return {"success": True, "data": {}}

    dm = SimpleNamespace(
        devices={"ld": device},
        get_device=lambda i: {"ld": device}.get(i),
        perform_action=AsyncMock(side_effect=perform_action),
    )
    devices_router.initialize(MagicMock(), dm, None, None)
    return SimpleNamespace(client=TestClient(main_app), calls=calls, dm=dm, device=device)


def test_sequence_action_executes_steps_in_order(sequence_world, monkeypatch):
    # The echo-wait would 503 (no state-change callback on this fake); short-circuit it
    # by making the waiter event pre-set via a zero timeout patch is overkill — instead
    # give the device a register hook that fires immediately after the last step.
    def register(cb):
        cb("ld", ["power"])  # settle the waiter synchronously

    sequence_world.device.register_state_change_callback = register
    sequence_world.device._state_change_callbacks = []

    r = sequence_world.client.post(
        "/devices/ld/canonical",
        json={"capability": "playback", "action": "open_tray"},
    )
    assert r.status_code == 200, r.text
    assert sequence_world.calls == [("wake", {}), ("tray", {"mode": "open"})]


def test_sequence_step_failure_names_the_step(sequence_world):
    async def perform_action(device_id, command, params):
        if command == "tray":
            return {"success": False, "error": "IR blaster busy"}
        return {"success": True, "data": {}}

    sequence_world.dm.perform_action = AsyncMock(side_effect=perform_action)

    r = sequence_world.client.post(
        "/devices/ld/canonical",
        json={"capability": "playback", "action": "open_tray"},
    )
    assert r.status_code == 500
    message = r.json()["detail"]["error"]["message"]
    assert "step 2/2" in message and "tray" in message


def test_single_command_path_unchanged(sequence_world):
    # no_op short-circuit still applies to single-step actions.
    async def perform_action(device_id, command, params):
        return {"success": True, "data": {"no_op": True}}

    sequence_world.dm.perform_action = AsyncMock(side_effect=perform_action)
    r = sequence_world.client.post(
        "/devices/ld/canonical", json={"capability": "playback", "action": "play"}
    )
    assert r.status_code == 200
    assert r.json()["success"] is True


# ---- Scenario Manager proxy ------------------------------------------------------

@pytest.mark.asyncio
async def test_proxy_executes_sequence_actions(tmp_path):
    import json as _json
    from wb_mqtt_bridge.domain.scenarios.proxy import ScenarioProxy
    from wb_mqtt_bridge.domain.scenarios.service import ScenarioManager

    device = SimpleNamespace(
        device_id="ld",
        room="living_room",
        capabilities=CapabilityMap.model_validate(SEQUENCE_MAP),
        state={"power": True},
        execute_action=AsyncMock(return_value={"success": True}),
    )
    device.get_current_state = lambda: device.state
    device.get_room = lambda: device.room
    device.get_available_commands = lambda: {}

    scenario_dir = tmp_path / "scenarios"
    scenario_dir.mkdir()
    (scenario_dir / "movie.json").write_text(_json.dumps({
        "scenario_id": "movie", "name": "Movie", "room_id": "living_room",
        "roles": {"playback": "ld"}, "source": "ld",
    }))

    class _Store:
        async def load(self, key):
            return None

        async def save(self, key, value):
            return None

        async def delete(self, key):
            return None

    dm = SimpleNamespace(devices={"ld": device}, get_device=lambda i: {"ld": device}.get(i))
    manager = ScenarioManager(
        device_manager=dm, room_manager=SimpleNamespace(),
        state_repository=_Store(), scenario_dir=scenario_dir,
    )
    await manager.initialize()
    proxy = ScenarioProxy(manager, dm)
    await proxy.activate("living_room", "movie")

    result = await proxy.execute("living_room", "playback", "open_tray")

    assert result["executed_on"] == "ld"
    assert result["command"] == "wake → tray"
    device.execute_action.assert_any_call("wake", {}, source="scenario")
    device.execute_action.assert_any_call("tray", {"mode": "open"}, source="scenario")
