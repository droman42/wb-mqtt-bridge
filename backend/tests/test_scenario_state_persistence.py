"""Scenario state persistence: end-to-end-ish tests using real ScenarioManager.

This file is a thin complement to tests/unit/test_scenario_manager.py — most
state-persistence behaviors are already covered there in unit form
(test_persist_state, test_restore_state, test_restore_state_nonexistent_scenario,
test_get_scenario_state_*, test_switch_scenario_transition). The case kept here
is the full round-trip: a persisted scenario_id, written by one ScenarioManager
instance, is observed by a freshly-constructed second instance.

Persistence shape: only the active scenario_id is stored under 'active_scenario'.
ScenarioState is recomputed live from current device states on every query (no
snapshot held).
"""
import json
import pytest
from unittest.mock import MagicMock, AsyncMock

from wb_mqtt_bridge.domain.scenarios.service import ScenarioManager


pytestmark = pytest.mark.integration


class _MockDevice:
    """A scenario-test device that responds to execute_action and exposes get_current_state.
    Carries `room` (default `living_room` to match scenario.room_id fixture) so the
    scenario room-membership validator passes."""

    def __init__(self, device_id, room="living_room"):
        self.device_id = device_id
        self.room = room
        self.state = {"power": False}
        self.execute_action = AsyncMock(return_value={"status": "success"})

    def get_current_state(self):
        return self.state

    def get_room(self):
        return self.room

    def get_available_commands(self):
        from types import SimpleNamespace
        # parameters=None bypasses parameter validation in scenario.validate_configuration().
        return {
            cmd: SimpleNamespace(parameters=None)
            for cmd in ["power_on", "power_off", "set_input", "set_scene", "standby"]
        }


class _MockDeviceManager:
    def __init__(self, devices=None):
        self.devices = devices or {}

    def get_device(self, device_id):
        return self.devices.get(device_id)


class _MockRoomManager:
    def __init__(self):
        # Mimic a single room that contains tv + soundbar so room-id validation
        # downstream is satisfied.
        self.rooms = {
            "living_room": MagicMock(
                room_id="living_room",
                devices=["tv", "soundbar"],
                default_scenario="movie_night",
            )
        }

    def get(self, room_id):
        return self.rooms.get(room_id)

    def contains_device(self, room_id, device_id):
        room = self.rooms.get(room_id)
        return room and device_id in room.devices


class _MockStateStore:
    """In-memory implementation of StateRepositoryPort (load/save)."""

    def __init__(self):
        self.data = {}

    async def load(self, key):
        return self.data.get(key)

    async def save(self, key, value):
        self.data[key] = value


@pytest.fixture
def scenario_dir(tmp_path):
    """Write a single movie_night scenario JSON in the current schema."""
    scenario_dir = tmp_path / "scenarios"
    scenario_dir.mkdir(exist_ok=True)

    movie_scenario = {
        "scenario_id": "movie_night",
        "name": "Movie Night",
        "description": "Optimal settings for watching movies",
        "room_id": "living_room",
        "roles": {"screen": "tv", "audio": "soundbar"},
        "devices": ["tv", "soundbar"],
        "startup_sequence": [
            {"device": "tv", "command": "power_on", "params": {}},
            {"device": "soundbar", "command": "power_on", "params": {}},
        ],
        "shutdown_sequence": [
            {"device": "tv", "command": "power_off", "params": {}},
            {"device": "soundbar", "command": "power_off", "params": {}},
        ],
    }

    with open(scenario_dir / "movie_night.json", "w") as f:
        json.dump(movie_scenario, f)

    return scenario_dir


@pytest.fixture
def device_manager():
    return _MockDeviceManager({"tv": _MockDevice("tv"), "soundbar": _MockDevice("soundbar")})


@pytest.fixture
def room_manager():
    return _MockRoomManager()


@pytest.fixture
def state_store():
    return _MockStateStore()


@pytest.mark.asyncio
async def test_save_and_restore_state_across_manager_instances(device_manager, room_manager, state_store, scenario_dir):
    """Activating a scenario writes its id to the store; a fresh manager reads it back and reactivates."""
    manager_a = ScenarioManager(
        device_manager=device_manager,
        room_manager=room_manager,
        state_repository=state_store,
        scenario_dir=scenario_dir,
    )
    await manager_a.initialize()
    await manager_a.switch_scenario("movie_night")

    # Persistence happened — the new persistence shape is just the scenario_id.
    assert await state_store.load("active_scenario") == "movie_night"

    # A brand-new manager reading from the same store reactivates movie_night.
    manager_b = ScenarioManager(
        device_manager=device_manager,
        room_manager=room_manager,
        state_repository=state_store,
        scenario_dir=scenario_dir,
    )
    await manager_b.initialize()

    assert manager_b.current_scenario is not None
    assert manager_b.current_scenario.scenario_id == "movie_night"


# Note: the live recompute in get_scenario_state() does NOT degrade gracefully when one
# device's get_current_state raises — the exception propagates. If/when production gains
# per-device try/except in get_scenario_state(), add a positive test for that here.
