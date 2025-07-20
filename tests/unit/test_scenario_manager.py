import json
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from wb_mqtt_bridge.domain.scenarios.service import ScenarioManager
from wb_mqtt_bridge.domain.scenarios.scenario import Scenario, ScenarioError
from wb_mqtt_bridge.domain.scenarios.models import ScenarioState, DeviceState

# Sample scenario data for testing
SAMPLE_SCENARIOS = {
    "movie_mode": {
        "scenario_id": "movie_mode",
        "name": "Movie Mode",
        "description": "Optimized for movie watching",
        "room_id": "living_room",
        "roles": {"screen": "tv", "audio": "soundbar"},
        "devices": {
            "tv": {"groups": ["screen"]},
            "soundbar": {"groups": ["audio"]},
            "lights": {"groups": ["ambience"]}
        },
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
        "devices": {
            "lights": {"groups": ["ambience"]}
        },
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
    """Mock device for testing"""
    def __init__(self, device_id):
        self.device_id = device_id
        self.state = {"power": False}
        self.execute_command = AsyncMock(return_value={"status": "success"})
    
    def get_current_state(self):
        return self.state

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
    """Mock StateStore for testing"""
    def __init__(self):
        self.data = {}
    
    async def get(self, key):
        return self.data.get(key)
    
    async def set(self, key, value):
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
        store=mock_store,
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
    async def test_load_scenarios(self, scenario_manager):
        """Test loading scenarios from files"""
        await scenario_manager.load_scenarios()
        
        assert len(scenario_manager.scenario_definitions) == 2
        
        # Check that ScenarioDefinition objects were created correctly
        movie_def = scenario_manager.scenario_definitions["movie_night"]
        assert movie_def.name == "Movie Night"
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
            store=mock_store,
            scenario_dir=nonexistent_dir
        )
        
        # Should log a warning but not raise an exception
        with patch("logging.Logger.warning") as mock_warning:
            await manager.load_scenarios()
            
            assert mock_warning.called
            assert len(manager.scenario_definitions) == 0

    @pytest.mark.asyncio
    async def test_load_scenarios_invalid_json(self, mock_device_manager, mock_room_manager, mock_store, tmp_path):
        """Test handling of invalid JSON in scenario files"""
        scenario_dir = tmp_path / "scenarios"
        scenario_dir.mkdir(exist_ok=True)
        
        # Create a file with invalid JSON
        invalid_file = scenario_dir / "invalid.json"
        invalid_file.write_text("This is not valid JSON")
        
        # Create a valid file too
        valid_file = scenario_dir / "valid.json"
        valid_file.write_text(json.dumps(SAMPLE_SCENARIOS["movie_night"]))
        
        manager = ScenarioManager(
            device_manager=mock_device_manager,
            room_manager=mock_room_manager,
            store=mock_store,
            scenario_dir=scenario_dir
        )
        
        # Should log an error but not raise an exception
        with patch("logging.Logger.error") as mock_error:
            await manager.load_scenarios()
            
            # Should log error for the invalid file
            assert mock_error.called
            
            # Should still load the valid file
            assert len(manager.scenario_definitions) == 1
            assert "movie_night" in manager.scenario_definitions

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
        
        mock_tv.execute_command.assert_any_call("power_on", {})
        mock_soundbar.execute_command.assert_any_call("power_on", {})
        
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
        await scenario_manager.switch_scenario("movie_night")
        
        # Reset the mock calls
        for device in scenario_manager.device_manager.devices.values():
            device.execute_command.reset_mock()
        
        # Switch to the same scenario again
        await scenario_manager.switch_scenario("movie_night")
        
        # No device commands should have been executed
        for device in scenario_manager.device_manager.devices.values():
            device.execute_command.assert_not_called()

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
        
        mock_tv.execute_command.reset_mock()
        mock_soundbar.execute_command.reset_mock()
        mock_lights.execute_command.reset_mock()
        
        # Now switch to reading mode which shares the 'lights' device
        result = await scenario_manager.switch_scenario("reading_mode")
        
        # Check that the non-shared devices were shut down
        mock_tv.execute_command.assert_called_once_with("power_off", {})
        mock_soundbar.execute_command.assert_called_once_with("power_off", {})
        
        # Check that lights received a command but not power_on
        mock_lights.execute_command.assert_called_once_with("set_scene", {"scene": "reading"})
        
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
        
        mock_tv.execute_command.reset_mock()
        mock_soundbar.execute_command.reset_mock()
        mock_lights.execute_command.reset_mock()
        
        # Now switch to reading mode with graceful=False
        result = await scenario_manager.switch_scenario("reading_mode", graceful=False)
        
        # In non-graceful mode, the shutdown sequence is executed directly
        # No direct device.execute_command calls should be made for TV and soundbar
        
        # Lights should receive its commands as part of the reading mode startup
        mock_lights.execute_command.assert_called_with("set_scene", {"scene": "reading"})
        
        # Verify the result object has no shared devices
        assert result["success"] is True
        assert len(result["shared_devices"]) == 0

    @pytest.mark.asyncio
    async def test_execute_role_action_success(self, scenario_manager, mock_device_manager):
        """Test successful execution of a role action"""
        # First load the scenarios and switch to movie night
        await scenario_manager.initialize()
        await scenario_manager.switch_scenario("movie_night")
        
        # Reset the mock calls
        for device in scenario_manager.device_manager.devices.values():
            device.execute_command.reset_mock()
        
        # Execute a role action
        result = await scenario_manager.execute_role_action("screen", "set_input", {"input": "hdmi1"})
        
        # Verify that the command was executed on the correct device
        mock_device_manager.devices["tv"].execute_command.assert_called_once_with("set_input", {"input": "hdmi1"})
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
        await scenario_manager.switch_scenario("movie_night")
        
        # Execute a role action with an invalid role
        with pytest.raises(ScenarioError, match="Role 'invalid' not defined in scenario"):
            await scenario_manager.execute_role_action("invalid", "set_input", {"input": "hdmi1"})

    @pytest.mark.asyncio
    async def test_persist_state(self, scenario_manager, mock_store):
        """Test that state is persisted"""
        # First load the scenarios and switch to movie night
        await scenario_manager.initialize()
        await scenario_manager.switch_scenario("movie_night")
        
        # Check that the state was saved to the store
        state_data = await mock_store.get("scenario:last")
        assert state_data is not None
        assert state_data["scenario_id"] == "movie_night"
        assert "devices" in state_data

    @pytest.mark.asyncio
    async def test_restore_state(self, mock_device_manager, mock_room_manager, mock_store, scenario_dir):
        """Test that state is restored on initialization"""
        # Create a saved state
        saved_state = ScenarioState(
            scenario_id="movie_night",
            devices={
                "tv": DeviceState(power=True, input="hdmi1"),
                "soundbar": DeviceState(power=True, volume=30)
            }
        )
        
        # Save the state to the store
        await mock_store.set("scenario:last", saved_state.model_dump())
        
        # Create a new manager and initialize it
        manager = ScenarioManager(
            device_manager=mock_device_manager,
            room_manager=mock_room_manager,
            store=mock_store,
            scenario_dir=scenario_dir
        )
        
        await manager.initialize()
        
        # Check that the state was restored
        assert manager.scenario_state is not None
        assert manager.scenario_state.scenario_id == "movie_night"
        assert manager.current_scenario is not None
        assert manager.current_scenario.scenario_id == "movie_night"

    @pytest.mark.asyncio
    async def test_restore_state_nonexistent_scenario(self, mock_device_manager, mock_room_manager, mock_store, scenario_dir):
        """Test handling when saved state references a nonexistent scenario"""
        # Create a saved state with a nonexistent scenario
        saved_state = ScenarioState(
            scenario_id="nonexistent",
            devices={}
        )
        
        # Save the state to the store
        await mock_store.set("scenario:last", saved_state.model_dump())
        
        # Create a new manager and initialize it
        manager = ScenarioManager(
            device_manager=mock_device_manager,
            room_manager=mock_room_manager,
            store=mock_store,
            scenario_dir=scenario_dir
        )
        
        # Should log a warning but not raise an exception
        with patch("logging.Logger.warning") as mock_warning:
            await manager.initialize()
            
            # State should be restored but current_scenario should not
            assert manager.scenario_state is not None
            assert manager.scenario_state.scenario_id == "nonexistent"
            assert manager.current_scenario is None
            
            # Should log a warning
            assert mock_warning.called

    @pytest.mark.asyncio
    async def test_refresh_state(self, scenario_manager, mock_device_manager):
        """Test refreshing scenario state from device states"""
        # First load the scenarios and switch to movie night
        await scenario_manager.initialize()
        await scenario_manager.switch_scenario("movie_night")
        
        # Update device states
        mock_device_manager.devices["tv"].state = {"power": True, "input": "hdmi1"}
        mock_device_manager.devices["soundbar"].state = {"power": True, "volume": 30}
        
        # Refresh the state
        await scenario_manager._refresh_state()
        
        # Check that the state was updated
        assert scenario_manager.scenario_state.devices["tv"].power is True
        assert scenario_manager.scenario_state.devices["tv"].input == "hdmi1"
        assert scenario_manager.scenario_state.devices["soundbar"].power is True
        assert scenario_manager.scenario_state.devices["soundbar"].extra["volume"] == 30 