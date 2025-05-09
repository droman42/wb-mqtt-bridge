import asyncio
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

from app.scenario_models import ScenarioState, DeviceState
from app.scenario_manager import ScenarioManager
from app.scenario import Scenario

# Mock classes for testing
class MockDevice:
    """Mock device for testing"""
    def __init__(self, device_id):
        self.device_id = device_id
        self.state = {"power": False}
        self.execute_command = AsyncMock(return_value={"status": "success"})
    
    def get_current_state(self):
        return self.state

class MockDeviceManager:
    """Mock DeviceManager for testing"""
    def __init__(self, devices=None):
        self.devices = devices or {}
    
    def get_device(self, device_id):
        return self.devices.get(device_id)

class MockRoomManager:
    """Mock RoomManager for testing"""
    def __init__(self):
        self.rooms = {}
    
    def get(self, room_id):
        return self.rooms.get(room_id)

class MockStateStore:
    """Mock StateStore for testing with real storage"""
    def __init__(self):
        self.data = {}
    
    async def get(self, key):
        return self.data.get(key)
    
    async def set(self, key, value):
        self.data[key] = value
        return True

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
def scenario_dir(tmp_path):
    """Create and return a temporary directory with scenario files"""
    scenario_dir = tmp_path / "scenarios"
    scenario_dir.mkdir(exist_ok=True)
    
    # Create a sample scenario file
    movie_scenario = {
        "scenario_id": "movie_night",
        "name": "Movie Night",
        "description": "Optimal settings for watching movies",
        "room_id": "living_room",
        "roles": {"screen": "tv", "audio": "soundbar"},
        "devices": {
            "tv": {"groups": ["display"]},
            "soundbar": {"groups": ["audio"]}
        },
        "startup_sequence": [
            {"device": "tv", "command": "power_on", "params": {}},
            {"device": "soundbar", "command": "power_on", "params": {}}
        ],
        "shutdown_sequence": {
            "complete": [
                {"device": "tv", "command": "power_off", "params": {}},
                {"device": "soundbar", "command": "power_off", "params": {}}
            ],
            "transition": [
                {"device": "tv", "command": "standby", "params": {}},
                {"device": "soundbar", "command": "standby", "params": {}}
            ]
        }
    }
    
    with open(scenario_dir / "movie_night.json", "w") as f:
        json.dump(movie_scenario, f)
    
    return scenario_dir

class TestStatePersistence:
    """Tests for scenario state persistence"""
    
    @pytest.mark.asyncio
    async def test_save_and_restore_state(self, mock_device_manager, mock_room_manager, mock_store, scenario_dir):
        """Test that state is saved during transitions and can be restored"""
        # Create a scenario manager
        manager = ScenarioManager(
            device_manager=mock_device_manager,
            room_manager=mock_room_manager,
            store=mock_store,
            scenario_dir=scenario_dir
        )
        
        # Load scenarios
        await manager.initialize()
        
        # Switch to a scenario
        await manager.switch_scenario("movie_night")
        
        # Verify the scenario is active
        assert manager.current_scenario is not None
        assert manager.current_scenario.scenario_id == "movie_night"
        assert manager.scenario_state is not None
        assert manager.scenario_state.scenario_id == "movie_night"
        
        # Update device states
        mock_device_manager.devices["tv"].state = {"power": True, "input": "hdmi1"}
        mock_device_manager.devices["soundbar"].state = {"power": True, "volume": 50}
        
        # Refresh state
        await manager._refresh_state()
        
        # Verify state has been updated
        assert manager.scenario_state.devices["tv"].power is True
        assert manager.scenario_state.devices["tv"].input == "hdmi1"
        assert manager.scenario_state.devices["soundbar"].power is True
        assert manager.scenario_state.devices["soundbar"].extra["volume"] == 50
        
        # Verify state has been saved to store
        saved_state = await mock_store.get("scenario:last")
        assert saved_state is not None
        assert saved_state["scenario_id"] == "movie_night"
        assert saved_state["devices"]["tv"]["power"] is True
        assert saved_state["devices"]["tv"]["input"] == "hdmi1"
        
        # Create a new manager instance to test state restoration
        new_manager = ScenarioManager(
            device_manager=mock_device_manager,
            room_manager=mock_room_manager,
            store=mock_store,
            scenario_dir=scenario_dir
        )
        
        # Initialize should restore state
        await new_manager.initialize()
        
        # Verify state was restored
        assert new_manager.current_scenario is not None
        assert new_manager.current_scenario.scenario_id == "movie_night"
        assert new_manager.scenario_state is not None
        assert new_manager.scenario_state.scenario_id == "movie_night"
        assert new_manager.scenario_state.devices["tv"].power is True
        assert new_manager.scenario_state.devices["tv"].input == "hdmi1"

    @pytest.mark.asyncio
    async def test_state_persistence_after_role_action(self, mock_device_manager, mock_room_manager, mock_store, scenario_dir):
        """Test that state is updated and persisted after role actions"""
        # Create a scenario manager
        manager = ScenarioManager(
            device_manager=mock_device_manager,
            room_manager=mock_room_manager,
            store=mock_store,
            scenario_dir=scenario_dir
        )
        
        # Load scenarios and switch to movie_night
        await manager.initialize()
        await manager.switch_scenario("movie_night")
        
        # Reset the mock calls
        for device in mock_device_manager.devices.values():
            device.execute_command.reset_mock()
        
        # Setup device to update its state when command is executed
        async def execute_set_input(command, params):
            if command == "set_input":
                mock_device_manager.devices["tv"].state["input"] = params.get("input")
            return {"status": "success"}
        
        mock_device_manager.devices["tv"].execute_command.side_effect = execute_set_input
        
        # Execute a role action
        await manager.execute_role_action("screen", "set_input", {"input": "hdmi2"})
        
        # Verify command was executed
        mock_device_manager.devices["tv"].execute_command.assert_called_once()
        
        # Verify state was updated
        assert manager.scenario_state.devices["tv"].input == "hdmi2"
        
        # Verify state was persisted
        saved_state = await mock_store.get("scenario:last")
        assert saved_state is not None
        assert saved_state["devices"]["tv"]["input"] == "hdmi2"

    @pytest.mark.asyncio
    async def test_restore_with_missing_scenario(self, mock_device_manager, mock_room_manager, mock_store, scenario_dir):
        """Test graceful handling when saved state references a missing scenario"""
        # Create a state for a nonexistent scenario
        missing_state = ScenarioState(
            scenario_id="nonexistent",
            devices={
                "tv": DeviceState(power=True, input="hdmi1"),
                "soundbar": DeviceState(power=True)
            }
        )
        
        # Save to store
        await mock_store.set("scenario:last", missing_state.model_dump())
        
        # Create a scenario manager
        manager = ScenarioManager(
            device_manager=mock_device_manager,
            room_manager=mock_room_manager,
            store=mock_store,
            scenario_dir=scenario_dir
        )
        
        # Initialize should not fail even though the scenario doesn't exist
        with patch("logging.Logger.warning") as mock_warning:
            await manager.initialize()
            
            # Verify warning was logged
            assert mock_warning.called
        
        # State should still be loaded
        assert manager.scenario_state is not None
        assert manager.scenario_state.scenario_id == "nonexistent"
        
        # But no active scenario
        assert manager.current_scenario is None

    @pytest.mark.asyncio
    async def test_preserve_device_state_across_scenarios(self, mock_device_manager, mock_room_manager, mock_store, scenario_dir):
        """Test that device state is preserved when switching between scenarios that share devices"""
        # Create a second scenario file
        reading_scenario = {
            "scenario_id": "reading",
            "name": "Reading Mode",
            "description": "Comfortable lighting for reading",
            "room_id": "living_room",
            "roles": {"lighting": "lights", "screen": "tv"},  # Shares the TV with movie_night
            "devices": {
                "tv": {"groups": ["display"]},
                "lights": {"groups": ["ambience"]}
            },
            "startup_sequence": [
                {"device": "tv", "command": "power_on", "params": {}},
                {"device": "lights", "command": "set_scene", "params": {"scene": "reading"}}
            ],
            "shutdown_sequence": {
                "complete": [
                    {"device": "tv", "command": "power_off", "params": {}},
                    {"device": "lights", "command": "power_off", "params": {}}
                ],
                "transition": [
                    {"device": "tv", "command": "standby", "params": {}},
                    {"device": "lights", "command": "standby", "params": {}}
                ]
            }
        }
        
        with open(scenario_dir / "reading.json", "w") as f:
            json.dump(reading_scenario, f)
        
        # Create a scenario manager
        manager = ScenarioManager(
            device_manager=mock_device_manager,
            room_manager=mock_room_manager,
            store=mock_store,
            scenario_dir=scenario_dir
        )
        
        # Load scenarios and switch to movie_night
        await manager.initialize()
        await manager.switch_scenario("movie_night")
        
        # Set TV input to hdmi1
        mock_device_manager.devices["tv"].state = {"power": True, "input": "hdmi1"}
        await manager._refresh_state()
        
        # Switch to reading scenario
        with patch("logging.Logger.debug") as mock_debug:
            await manager.switch_scenario("reading")
            
            # Should detect shared device (TV) with different configuration
            assert any("Device tv" in str(call) for call in mock_debug.call_args_list)
        
        # TV should still have the same input
        assert mock_device_manager.devices["tv"].state["input"] == "hdmi1"
        
        # Check that state reflects this
        assert manager.scenario_state.devices["tv"].input == "hdmi1"

    @pytest.mark.asyncio
    async def test_persistance_with_device_error(self, mock_device_manager, mock_room_manager, mock_store, scenario_dir):
        """Test that the system handles device errors gracefully during state operations"""
        # Create a scenario manager
        manager = ScenarioManager(
            device_manager=mock_device_manager,
            room_manager=mock_room_manager,
            store=mock_store,
            scenario_dir=scenario_dir
        )
        
        # Load scenarios and switch to movie_night
        await manager.initialize()
        
        # Make one of the devices fail during state retrieval
        mock_device_manager.devices["tv"].get_current_state = MagicMock(side_effect=Exception("Device error"))
        
        # Should handle the error gracefully and still switch scenarios
        with patch("logging.Logger.error") as mock_error:
            await manager.switch_scenario("movie_night")
            
            # Error should be logged
            assert mock_error.called
        
        # Scenario should still be active
        assert manager.current_scenario is not None
        assert manager.current_scenario.scenario_id == "movie_night"
        
        # State should still be created, but without the TV
        assert manager.scenario_state is not None
        assert "tv" not in manager.scenario_state.devices
        assert "soundbar" in manager.scenario_state.devices 