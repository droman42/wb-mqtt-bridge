import json
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from wb_mqtt_bridge.domain.scenarios.service import ScenarioManager
from wb_mqtt_bridge.domain.scenarios.scenario import Scenario, ScenarioError
from wb_mqtt_bridge.domain.scenarios.models import ScenarioState, DeviceState, ManualStep

pytestmark = pytest.mark.unit

# Sample scenario data for testing
SAMPLE_SCENARIOS = {
    "movie_mode": {
        "scenario_id": "movie_mode",
        "name": "Movie Mode",
        "description": "Optimized for movie watching",
        "room_id": "living_room",
        "roles": {"screen": "tv", "audio": "soundbar"},
        "devices": ["tv", "soundbar", "lights"],
        "startup_sequence": [
            {"device": "tv", "command": "power_on", "params": {}},
            {"device": "soundbar", "command": "power_on", "params": {}},
            {"device": "tv", "command": "set_input", "params": {"input": "hdmi1"}},
            {"device": "lights", "command": "set_scene", "params": {"scene": "movie"}}
        ],
        "shutdown_sequence": [
            {"device": "tv", "command": "power_off", "params": {}},
            {"device": "soundbar", "command": "power_off", "params": {}},
            {"device": "lights", "command": "set_scene", "params": {"scene": "bright"}}
        ]
    },
    "reading_mode": {
        "scenario_id": "reading_mode",
        "name": "Reading Mode",
        "description": "Comfortable lighting for reading",
        "room_id": "living_room",
        "roles": {"lighting": "lights"},
        "devices": ["lights"],
        "startup_sequence": [
            {"device": "lights", "command": "set_scene", "params": {"scene": "reading"}}
        ],
        "shutdown_sequence": [
            {"device": "lights", "command": "set_scene", "params": {"scene": "bright"}}
        ]
    }
}

# Mock classes for testing
class MockDeviceManager:
    """Mock DeviceManager for testing ScenarioManager"""
    def __init__(self, devices=None):
        self.devices = devices or {}
    
    def get_device(self, device_id):
        return self.devices.get(device_id)

class MockDevice:
    """Mock device for testing. Carries a `room` (defaulting to `living_room` to match
    the test fixtures' scenario.room_id), exposed via `get_room()` so the new scenario
    room-membership validator passes."""
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
        return {cmd: SimpleNamespace(parameters=None) for cmd in [
            "power_on", "power_off", "set_input", "set_scene",
            "set_volume", "volume_up", "volume_down",
        ]}

class MockRoomManager:
    """Mock RoomManager for testing"""
    def __init__(self):
        self.rooms = {
            "living_room": MagicMock(
                room_id="living_room",
                devices=["tv", "soundbar", "lights"],
                default_scenario="movie_mode"
            )
        }
    
    def get(self, room_id):
        return self.rooms.get(room_id)
    
    def contains_device(self, room_id, device_id):
        room = self.rooms.get(room_id)
        return room and device_id in room.devices

class MockStateStore:
    """Mock StateStore for testing - implements both old (get/set) and new (load/save) API names"""
    def __init__(self):
        self.data = {}

    async def get(self, key):
        return self.data.get(key)

    async def set(self, key, value):
        self.data[key] = value
        return True

    async def load(self, key):
        return self.data.get(key)

    async def save(self, key, value):
        self.data[key] = value
        return True

# Utility to create scenario file mocks
def mock_scenario_files(tmp_path):
    """Create mock scenario files in a temporary directory"""
    scenario_dir = tmp_path / "scenarios"
    scenario_dir.mkdir(exist_ok=True)
    
    for scenario_id, data in SAMPLE_SCENARIOS.items():
        scenario_file = scenario_dir / f"{scenario_id}.json"
        scenario_file.write_text(json.dumps(data))
    
    return scenario_dir

@pytest.fixture
def scenario_dir(tmp_path):
    """Create and return a temporary directory with scenario files"""
    return mock_scenario_files(tmp_path)

@pytest.fixture
def mock_device_manager():
    """Return a mock device manager with sample devices"""
    tv = MockDevice("tv")
    soundbar = MockDevice("soundbar")
    lights = MockDevice("lights")
    return MockDeviceManager({
        "tv": tv, 
        "soundbar": soundbar,
        "lights": lights
    })

@pytest.fixture
def mock_room_manager():
    """Return a mock room manager"""
    return MockRoomManager()

@pytest.fixture
def mock_store():
    """Return a mock state store"""
    return MockStateStore()

@pytest.fixture
def scenario_manager(mock_device_manager, mock_room_manager, mock_store, scenario_dir):
    """Return a ScenarioManager with mock dependencies"""
    return ScenarioManager(
        device_manager=mock_device_manager,
        room_manager=mock_room_manager,
        state_repository=mock_store,
        scenario_dir=scenario_dir
    )

class TestScenarioManager:
    """Tests for the ScenarioManager class"""
    
    @pytest.mark.asyncio
    async def test_initialize_loads_scenarios(self, scenario_manager):
        """Test that initialize loads scenario definitions"""
        await scenario_manager.initialize()

        assert len(scenario_manager.scenario_definitions) == 2
        assert "movie_mode" in scenario_manager.scenario_definitions
        assert "reading_mode" in scenario_manager.scenario_definitions

        assert len(scenario_manager.scenario_map) == 2
        assert isinstance(scenario_manager.scenario_map["movie_mode"], Scenario)
        assert isinstance(scenario_manager.scenario_map["reading_mode"], Scenario)

    @pytest.mark.asyncio
    async def test_room_membership_validation_hard_fails_on_mismatch(
        self, mock_room_manager, mock_store, scenario_dir,
    ):
        """Scenario room-membership validation (room-refactor 2026-06-08): when a
        scenario declares `room_id` but one of its devices reports a DIFFERENT room
        via `get_room()`, bootstrap MUST hard-fail with a ScenarioError naming the
        violation. This catches typos / stale references / drift between scenario
        configs and device configs."""
        # Build a device manager where `tv` belongs to bedroom, NOT living_room as
        # the movie_mode scenario expects.
        tv = MockDevice("tv", room="bedroom")
        soundbar = MockDevice("soundbar", room="living_room")
        lights = MockDevice("lights", room="living_room")
        bad_dm = MockDeviceManager({"tv": tv, "soundbar": soundbar, "lights": lights})
        sm = ScenarioManager(
            device_manager=bad_dm,
            room_manager=mock_room_manager,
            state_repository=mock_store,
            scenario_dir=scenario_dir,
        )
        with pytest.raises(ScenarioError) as exc_info:
            await sm.initialize()
        msg = str(exc_info.value)
        assert "movie_mode" in msg
        assert "'tv'" in msg
        assert "bedroom" in msg

    @pytest.mark.asyncio
    async def test_room_membership_validation_passes_when_all_devices_align(
        self, scenario_manager,
    ):
        """Positive case: the default fixture has every device in living_room and both
        scenarios declare room_id=living_room. initialize() succeeds without raising."""
        await scenario_manager.initialize()  # default fixture; no exception expected
        # Sanity: validator did run and found nothing to complain about.
        assert "movie_mode" in scenario_manager.scenario_definitions
        assert "reading_mode" in scenario_manager.scenario_definitions

    @pytest.mark.asyncio
    async def test_load_scenarios(self, scenario_manager):
        """Test loading scenarios from files"""
        await scenario_manager.load_scenarios()
        
        assert len(scenario_manager.scenario_definitions) == 2
        
        # Check that ScenarioDefinition objects were created correctly
        movie_def = scenario_manager.scenario_definitions["movie_mode"]
        assert movie_def.name == "Movie Mode"
        assert movie_def.room_id == "living_room"
        assert len(movie_def.roles) == 2
        
        reading_def = scenario_manager.scenario_definitions["reading_mode"]
        assert reading_def.name == "Reading Mode"
        assert reading_def.room_id == "living_room"
        assert len(reading_def.roles) == 1

    @pytest.mark.asyncio
    async def test_load_scenarios_nonexistent_dir(self, mock_device_manager, mock_room_manager, mock_store, tmp_path):
        """Test handling of nonexistent scenario directory"""
        # Create a path that doesn't exist
        nonexistent_dir = tmp_path / "nonexistent"
        
        manager = ScenarioManager(
            device_manager=mock_device_manager,
            room_manager=mock_room_manager,
            state_repository=mock_store,
            scenario_dir=nonexistent_dir
        )
        
        # Should log a warning but not raise an exception
        with patch("logging.Logger.warning") as mock_warning:
            await manager.load_scenarios()
            
            assert mock_warning.called
            assert len(manager.scenario_definitions) == 0

    @pytest.mark.asyncio
    async def test_load_scenarios_invalid_json(self, mock_device_manager, mock_room_manager, mock_store, tmp_path):
        """An invalid scenario file is logged and skipped, never fatal (Bug 2).

        A bad or currently-unavailable scenario (malformed file, or a referenced device that's
        off/unreachable at boot) must NOT bring down the whole bridge. It is skipped and recorded
        in `scenario_load_errors` for visibility; the rest of the system still starts. (This
        reverses the earlier short-lived fail-fast `SystemExit` behavior.)
        """
        scenario_dir = tmp_path / "scenarios"
        scenario_dir.mkdir(exist_ok=True)

        invalid_file = scenario_dir / "invalid.json"
        invalid_file.write_text("This is not valid JSON")

        manager = ScenarioManager(
            device_manager=mock_device_manager,
            room_manager=mock_room_manager,
            state_repository=mock_store,
            scenario_dir=scenario_dir
        )

        # Must NOT raise — scenario loading is resilient.
        await manager.load_scenarios()

        assert "invalid" in manager.scenario_load_errors
        assert "invalid" not in manager.scenario_map

    @pytest.mark.asyncio
    async def test_switch_scenario_success(self, scenario_manager, mock_device_manager):
        """Test successful scenario switching"""
        # First load the scenarios
        await scenario_manager.initialize()
        
        # Switch to the movie mode scenario
        result = await scenario_manager.switch_scenario("movie_mode")
        
        # Check that the current scenario was set
        assert scenario_manager.current_scenario is not None
        assert scenario_manager.current_scenario.scenario_id == "movie_mode"
        
        # Check that device commands were executed
        mock_tv = mock_device_manager.get_device("tv")
        mock_soundbar = mock_device_manager.get_device("soundbar")
        mock_device_manager.get_device("lights")
        
        mock_tv.execute_action.assert_any_call("power_on", {}, source="scenario")
        mock_soundbar.execute_action.assert_any_call("power_on", {}, source="scenario")
        
        # Verify the result object
        assert "success" in result
        assert result["success"] is True
        assert "shared_devices" in result
        assert len(result["shared_devices"]) == 0  # No shared devices for first activation

    @pytest.mark.asyncio
    async def test_switch_scenario_nonexistent(self, scenario_manager):
        """Test error when switching to nonexistent scenario"""
        # First load the scenarios
        await scenario_manager.initialize()
        
        # Try to switch to a nonexistent scenario
        with pytest.raises(ValueError, match="Scenario 'nonexistent' not found"):
            await scenario_manager.switch_scenario("nonexistent")

    @pytest.mark.asyncio
    async def test_switch_scenario_already_active(self, scenario_manager):
        """Test handling when switching to already active scenario"""
        # First load the scenarios and switch to movie night
        await scenario_manager.initialize()
        await scenario_manager.switch_scenario("movie_mode")
        
        # Reset the mock calls
        for device in scenario_manager.device_manager.devices.values():
            device.execute_action.reset_mock()
        
        # Switch to the same scenario again
        await scenario_manager.switch_scenario("movie_mode")
        
        # No device commands should have been executed
        for device in scenario_manager.device_manager.devices.values():
            device.execute_action.assert_not_called()

    @pytest.mark.asyncio
    async def test_switch_scenario_transition(self, scenario_manager, mock_device_manager):
        """Test transitioning between scenarios with shared devices"""
        # Initialize and switch to movie mode first
        await scenario_manager.initialize()
        await scenario_manager.switch_scenario("movie_mode")
        
        # Reset all mocks to clear the call history
        mock_tv = mock_device_manager.get_device("tv")
        mock_soundbar = mock_device_manager.get_device("soundbar")
        mock_lights = mock_device_manager.get_device("lights")
        
        mock_tv.execute_action.reset_mock()
        mock_soundbar.execute_action.reset_mock()
        mock_lights.execute_action.reset_mock()
        
        # Now switch to reading mode which shares the 'lights' device
        result = await scenario_manager.switch_scenario("reading_mode")
        
        # Check that the non-shared devices were shut down
        mock_tv.execute_action.assert_called_once_with("power_off", {}, source="scenario")
        mock_soundbar.execute_action.assert_called_once_with("power_off", {}, source="scenario")
        
        # Check that lights received a command but not power_on
        mock_lights.execute_action.assert_called_once_with("set_scene", {"scene": "reading"}, source="scenario")
        
        # Verify the result object
        assert result["success"] is True
        assert "lights" in result["shared_devices"]
        assert len(result["shared_devices"]) == 1

    @pytest.mark.asyncio
    async def test_switch_scenario_graceful_false(self, scenario_manager, mock_device_manager):
        """Test non-graceful scenario transition that powers off all devices"""
        # Initialize and switch to movie mode first
        await scenario_manager.initialize()
        await scenario_manager.switch_scenario("movie_mode")
        
        # Reset all mocks to clear the call history
        mock_tv = mock_device_manager.get_device("tv")
        mock_soundbar = mock_device_manager.get_device("soundbar")
        mock_lights = mock_device_manager.get_device("lights")
        
        mock_tv.execute_action.reset_mock()
        mock_soundbar.execute_action.reset_mock()
        mock_lights.execute_action.reset_mock()
        
        # Now switch to reading mode with graceful=False
        result = await scenario_manager.switch_scenario("reading_mode", graceful=False)
        
        # In non-graceful mode, the shutdown sequence is executed directly
        # No direct device.execute_action calls should be made for TV and soundbar
        
        # Lights should receive its commands as part of the reading mode startup
        mock_lights.execute_action.assert_called_with("set_scene", {"scene": "reading"}, source="scenario")
        
        # Verify the result object has no shared devices
        assert result["success"] is True
        assert len(result["shared_devices"]) == 0

    @pytest.mark.asyncio
    async def test_execute_role_action_success(self, scenario_manager, mock_device_manager):
        """Test successful execution of a role action"""
        # First load the scenarios and switch to movie night
        await scenario_manager.initialize()
        await scenario_manager.switch_scenario("movie_mode")
        
        # Reset the mock calls
        for device in scenario_manager.device_manager.devices.values():
            device.execute_action.reset_mock()
        
        # Execute a role action
        result = await scenario_manager.execute_role_action("screen", "set_input", {"input": "hdmi1"})
        
        # Verify that the command was executed on the correct device
        mock_device_manager.devices["tv"].execute_action.assert_called_once_with("set_input", {"input": "hdmi1"}, source="scenario")
        assert result == {"status": "success"}

    @pytest.mark.asyncio
    async def test_execute_role_action_no_active_scenario(self, scenario_manager):
        """Test error when no active scenario"""
        # First load the scenarios but don't switch to any scenario
        await scenario_manager.initialize()
        
        # Execute a role action without an active scenario
        with pytest.raises(ScenarioError, match="No scenario is currently active"):
            await scenario_manager.execute_role_action("screen", "set_input", {"input": "hdmi1"})

    @pytest.mark.asyncio
    async def test_execute_role_action_invalid_role(self, scenario_manager):
        """Test error when role is invalid"""
        # First load the scenarios and switch to movie night
        await scenario_manager.initialize()
        await scenario_manager.switch_scenario("movie_mode")
        
        # Execute a role action with an invalid role
        with pytest.raises(ScenarioError, match="Role 'invalid' not defined in scenario"):
            await scenario_manager.execute_role_action("invalid", "set_input", {"input": "hdmi1"})

    @pytest.mark.asyncio
    async def test_persist_state(self, scenario_manager, mock_store):
        """Switching scenarios persists the active scenario_id to the store.

        Original test expected a full state dict under key 'scenario:last'.
        Production now persists only the active scenario_id under key 'active_scenario'
        (the full ScenarioState is rebuilt from current device state on restore).
        The semantic intent — "the manager remembers which scenario was last active
        so it can be restored after a restart" — is preserved.
        """
        await scenario_manager.initialize()
        await scenario_manager.switch_scenario("movie_mode")

        persisted_id = await mock_store.load("active_scenario")
        assert persisted_id == "movie_mode"

    @pytest.mark.asyncio
    async def test_restore_state(self, mock_device_manager, mock_room_manager, mock_store, scenario_dir):
        """On initialize(), the previously-active scenario is reactivated via switch_scenario.

        Rewritten for the new persistence shape: only the scenario_id is stored
        (under 'active_scenario'); the manager looks it up, finds it in scenario_map,
        and calls switch_scenario(scenario_id).
        """
        # Seed the store as production would have left it.
        await mock_store.save("active_scenario", "movie_mode")

        manager = ScenarioManager(
            device_manager=mock_device_manager,
            room_manager=mock_room_manager,
            state_repository=mock_store,
            scenario_dir=scenario_dir,
        )
        await manager.initialize()

        assert manager.current_scenario is not None
        assert manager.current_scenario.scenario_id == "movie_mode"
        # Live state recomputes from current device states (no snapshot is held).
        assert manager.get_scenario_state("movie_mode").scenario_id == "movie_mode"

    @pytest.mark.asyncio
    async def test_restore_state_nonexistent_scenario(self, mock_device_manager, mock_room_manager, mock_store, scenario_dir):
        """If the persisted scenario_id no longer exists in scenario_map, restore is a no-op.

        Production logs a debug message and skips restoration without raising. current_scenario
        stays None. We verify no crash and no current_scenario.
        """
        await mock_store.save("active_scenario", "scenario_that_does_not_exist")

        manager = ScenarioManager(
            device_manager=mock_device_manager,
            room_manager=mock_room_manager,
            state_repository=mock_store,
            scenario_dir=scenario_dir,
        )
        await manager.initialize()  # must not raise

        assert manager.current_scenario is None

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_get_scenario_state_covers_all_definition_devices(
        self, scenario_manager, mock_device_manager
    ):
        """The live-recompute path produces a ScenarioState keyed by the active id, with
        one DeviceState entry per device in the scenario definition (replaces the prior
        snapshot-based _refresh_state coverage)."""
        await scenario_manager.initialize()
        await scenario_manager.switch_scenario("movie_mode")

        live = scenario_manager.get_scenario_state("movie_mode")

        assert live.scenario_id == "movie_mode"
        assert set(live.devices.keys()) == {"tv", "soundbar", "lights"}

    @pytest.mark.asyncio
    async def test_get_scenario_state_recomputes_live_after_device_change(
        self, scenario_manager, mock_device_manager
    ):
        """get_scenario_state(active_id) must re-read each device's state on every
        call, never return the activation-time snapshot. Guards the bug fixed
        2026-05-30: GET /scenario/state used to return self.scenario_state, which
        drifted after any manual fix on a device page."""
        from types import SimpleNamespace

        await scenario_manager.initialize()
        await scenario_manager.switch_scenario("movie_mode")

        # Simulate a manual fix on the TV's device page AFTER activation.
        # SimpleNamespace exposes attributes the way _safe_get_device_field expects;
        # a plain dict returns None for every field (hasattr won't see dict keys).
        mock_device_manager.devices["tv"].state = SimpleNamespace(
            power=True, input="hdmi2"
        )

        live = scenario_manager.get_scenario_state("movie_mode")

        assert live.scenario_id == "movie_mode"
        assert live.devices["tv"].power is True
        assert live.devices["tv"].input == "hdmi2"

    @pytest.mark.asyncio
    async def test_get_scenario_state_includes_activation_manual_steps(
        self, scenario_manager
    ):
        """The live-recompute path must thread activation-scoped manual_steps
        through, so transition notes (Dodocus hub, "press Play", etc.) survive
        any query. Guards the bug fixed 2026-05-30: the live path silently
        dropped manual_steps, leaving the per-scenario endpoint without the
        load-bearing notes from the 2026-05-26 transition-aware-manual-notes
        work."""
        await scenario_manager.initialize()
        await scenario_manager.switch_scenario("movie_mode")

        scenario_manager._activation_manual_steps = [
            ManualStep(node="dodocus_hub", instruction="Set Dodocus hub to LD"),
            ManualStep(node="kuzma", instruction="Power on Kuzma, cue the record"),
        ]

        live = scenario_manager.get_scenario_state("movie_mode")

        assert len(live.manual_steps) == 2
        assert live.manual_steps[0].node == "dodocus_hub"
        assert live.manual_steps[0].instruction == "Set Dodocus hub to LD"
        assert live.manual_steps[1].node == "kuzma"
