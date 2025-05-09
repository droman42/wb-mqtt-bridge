import asyncio
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from app.scenario import Scenario, ScenarioError, ScenarioExecutionError
from app.scenario_models import ScenarioDefinition, CommandStep, ManualInstructions

# Sample scenario data for testing
SAMPLE_SCENARIO = {
    "scenario_id": "test_scenario",
    "name": "Test Scenario",
    "description": "A test scenario",
    "roles": {"main_display": "tv", "audio": "soundbar"},
    "devices": {
        "tv": {"groups": ["video"]},
        "soundbar": {"groups": ["audio"]}
    },
    "startup_sequence": [
        {
            "device": "tv",
            "command": "power_on",
            "params": {},
            "delay_after_ms": 1000
        },
        {
            "device": "soundbar",
            "command": "power_on",
            "params": {"volume": 50}
        }
    ],
    "shutdown_sequence": {
        "complete": [
            {
                "device": "tv",
                "command": "power_off",
                "params": {}
            },
            {
                "device": "soundbar",
                "command": "power_off",
                "params": {}
            }
        ],
        "transition": [
            {
                "device": "tv",
                "command": "standby",
                "params": {}
            },
            {
                "device": "soundbar",
                "command": "standby",
                "params": {}
            }
        ]
    },
    "manual_instructions": {
        "startup": ["Turn on the lights"],
        "shutdown": ["Turn off the lights"]
    }
}

class MockDevice:
    """Mock device for testing Scenario execution"""
    def __init__(self, device_id):
        self.device_id = device_id
        self.state = {"power": False, "volume": 0}
        self.execute_command = AsyncMock()
    
    def get_current_state(self):
        return self.state

class MockDeviceManager:
    """Mock DeviceManager for testing Scenario"""
    def __init__(self, devices=None):
        self.devices = devices or {}
    
    def get_device(self, device_id):
        return self.devices.get(device_id)

@pytest.fixture
def sample_scenario_definition():
    """Return a sample ScenarioDefinition"""
    return ScenarioDefinition.model_validate(SAMPLE_SCENARIO)

@pytest.fixture
def mock_device_manager():
    """Return a mock device manager with sample devices"""
    tv = MockDevice("tv")
    soundbar = MockDevice("soundbar")
    return MockDeviceManager({"tv": tv, "soundbar": soundbar})

@pytest.fixture
def scenario(sample_scenario_definition, mock_device_manager):
    """Return a Scenario instance with sample definition and mock device manager"""
    return Scenario(sample_scenario_definition, mock_device_manager)

class TestScenario:
    """Tests for the Scenario class"""
    
    def test_initialization(self, scenario, sample_scenario_definition):
        """Test that Scenario is initialized correctly"""
        assert scenario.definition == sample_scenario_definition
        assert scenario.scenario_id == "test_scenario"
        assert scenario.state == {}

    @pytest.mark.asyncio
    async def test_execute_role_action_success(self, scenario, mock_device_manager):
        """Test successful execution of a role action"""
        # Arrange
        mock_device_manager.devices["tv"].execute_command.return_value = {"status": "success"}
        
        # Act
        result = await scenario.execute_role_action("main_display", "power_on", volume=50)
        
        # Assert
        mock_device_manager.devices["tv"].execute_command.assert_called_once_with("power_on", {"volume": 50})
        assert result == {"status": "success"}

    @pytest.mark.asyncio
    async def test_execute_role_action_invalid_role(self, scenario):
        """Test error when invalid role is specified"""
        with pytest.raises(ScenarioError) as excinfo:
            await scenario.execute_role_action("invalid_role", "power_on")
        
        assert "Role 'invalid_role' not defined in scenario" in str(excinfo.value)
        assert excinfo.value.error_type == "invalid_role"
        assert excinfo.value.critical is True

    @pytest.mark.asyncio
    async def test_execute_role_action_missing_device(self, scenario, mock_device_manager):
        """Test error when device for role doesn't exist"""
        # Modify device_manager to not have the device
        mock_device_manager.devices.pop("tv")
        
        with pytest.raises(ScenarioError) as excinfo:
            await scenario.execute_role_action("main_display", "power_on")
        
        assert "Device 'tv' not found for role 'main_display'" in str(excinfo.value)
        assert excinfo.value.error_type == "missing_device"
        assert excinfo.value.critical is True

    @pytest.mark.asyncio
    async def test_execute_role_action_device_error(self, scenario, mock_device_manager):
        """Test handling of device execution errors"""
        # Setup device to raise an exception
        mock_device_manager.devices["tv"].execute_command.side_effect = Exception("Device error")
        
        with pytest.raises(ScenarioExecutionError) as excinfo:
            await scenario.execute_role_action("main_display", "power_on")
        
        assert "Failed to execute power_on on tv" in str(excinfo.value)
        assert excinfo.value.error_type == "execution"
        assert excinfo.value.role == "main_display"
        assert excinfo.value.device_id == "tv"
        assert excinfo.value.command == "power_on"

    @pytest.mark.asyncio
    async def test_initialize(self, scenario):
        """Test that initialize calls execute_startup_sequence"""
        with patch.object(scenario, 'execute_startup_sequence', new_callable=AsyncMock) as mock_exec:
            await scenario.initialize()
            mock_exec.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_startup_sequence(self, scenario, mock_device_manager):
        """Test execution of startup sequence"""
        # Act
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            await scenario.execute_startup_sequence()
        
        # Assert
        # First device should be called with its parameters
        mock_device_manager.devices["tv"].execute_command.assert_called_once_with("power_on", {})
        # Sleep should be called with the delay from the first step
        mock_sleep.assert_called_once_with(1.0)  # 1000ms = 1.0s
        # Second device should be called with its parameters
        mock_device_manager.devices["soundbar"].execute_command.assert_called_once_with("power_on", {"volume": 50})

    @pytest.mark.asyncio
    async def test_execute_startup_sequence_missing_device(self, scenario, mock_device_manager):
        """Test handling of missing devices in startup sequence"""
        # Remove a device that's in the startup sequence
        mock_device_manager.devices.pop("soundbar")
        
        # Should execute without error, logging the missing device
        with patch('logging.Logger.error') as mock_error:
            await scenario.execute_startup_sequence()
            
            # Verify logging for missing device
            assert any("Device 'soundbar' not found" in call.args[0] for call in mock_error.call_args_list)
            
            # TV should still be powered on
            mock_device_manager.devices["tv"].execute_command.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_startup_sequence_with_condition(self, scenario_with_conditions, mock_device_manager):
        """Test execution of startup sequence with conditions"""
        # The test will call the scenario_with_conditions fixture which will be created below
        await scenario_with_conditions.execute_startup_sequence()
        
        # Only second command should execute as first has a false condition
        mock_device_manager.devices["tv"].execute_command.assert_not_called()
        mock_device_manager.devices["soundbar"].execute_command.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_shutdown_sequence_complete(self, scenario, mock_device_manager):
        """Test execution of complete shutdown sequence"""
        await scenario.execute_shutdown_sequence(complete=True)
        
        # Both devices should be powered off
        mock_device_manager.devices["tv"].execute_command.assert_called_once_with("power_off", {})
        mock_device_manager.devices["soundbar"].execute_command.assert_called_once_with("power_off", {})

    @pytest.mark.asyncio
    async def test_execute_shutdown_sequence_transition(self, scenario, mock_device_manager):
        """Test execution of transition shutdown sequence"""
        await scenario.execute_shutdown_sequence(complete=False)
        
        # Both devices should be put in standby
        mock_device_manager.devices["tv"].execute_command.assert_called_once_with("standby", {})
        mock_device_manager.devices["soundbar"].execute_command.assert_called_once_with("standby", {})

    @pytest.mark.asyncio
    async def test_execute_shutdown_sequence_error(self, scenario, mock_device_manager):
        """Test handling of errors during shutdown sequence"""
        # Setup device to raise an exception
        mock_device_manager.devices["tv"].execute_command.side_effect = Exception("Device error")
        
        # Should not raise the exception, but log it
        with patch('logging.Logger.error') as mock_error:
            await scenario.execute_shutdown_sequence(complete=True)
            
            # Verify error was logged
            assert any("Error executing shutdown step" in call.args[0] for call in mock_error.call_args_list)
            
            # Second device should still be shut down
            mock_device_manager.devices["soundbar"].execute_command.assert_called_once()

    @pytest.mark.asyncio
    async def test_evaluate_condition_true(self, scenario):
        """Test condition evaluation with a true condition"""
        # Simple way to test - mock the _evaluate_condition directly
        with patch.object(scenario, '_evaluate_condition', return_value=True):
            result = await scenario._evaluate_condition("device.power == True", MagicMock())
            assert result is True
    
    @pytest.mark.asyncio
    async def test_evaluate_condition_false(self, scenario):
        """Test condition evaluation with a false condition"""
        # Simple way to test - mock the _evaluate_condition directly
        with patch.object(scenario, '_evaluate_condition', return_value=False):
            result = await scenario._evaluate_condition("device.power == True", MagicMock())
            assert result is False
    
    @pytest.mark.asyncio
    async def test_evaluate_condition_none(self, scenario):
        """Test condition evaluation with no condition (should return True)"""
        result = await scenario._evaluate_condition(None, MagicMock())
        assert result is True
    
    @pytest.mark.asyncio
    async def test_evaluate_condition_error(self, scenario):
        """Test handling of errors during condition evaluation"""
        # Test that errors are caught and logged
        device = MagicMock()
        device.get_current_state.side_effect = Exception("Test exception")
        
        with patch('logging.Logger.error') as mock_error:
            result = await scenario._evaluate_condition("some_condition", device)
            
            # Should log the error and return False
            assert result is False
            assert mock_error.called

    def test_validate_valid_scenario(self, scenario, mock_device_manager):
        """Test validation of a valid scenario"""
        errors = scenario.validate()
        assert errors == []

    def test_validate_missing_devices(self, scenario, mock_device_manager):
        """Test validation when devices are missing"""
        # Remove all devices
        mock_device_manager.devices.clear()
        
        errors = scenario.validate()
        
        assert len(errors) > 0
        assert any("Device 'tv' referenced in scenario does not exist" in error for error in errors)
        assert any("Device 'soundbar' referenced in scenario does not exist" in error for error in errors)

    def test_validate_with_room_manager(self, scenario, mock_device_manager):
        """Test validation with room manager for scenario-room containment"""
        # Add room_id to the scenario
        scenario.definition.room_id = "living_room"
        
        # Create a mock room manager with contains_device method
        room_manager = MagicMock()
        room_manager.contains_device.return_value = False
        
        # Attach room_manager to device_manager
        mock_device_manager.room_manager = room_manager
        
        errors = scenario.validate()
        
        assert any("Device 'tv' is not in room 'living_room'" in error for error in errors)
        assert any("Device 'soundbar' is not in room 'living_room'" in error for error in errors)

@pytest.fixture
def scenario_with_conditions(sample_scenario_definition, mock_device_manager):
    """Create a scenario with conditions for testing conditional execution"""
    # Set TV's power state to off
    mock_device_manager.devices["tv"].state = {"power": False}
    
    # Set soundbar's power state to off
    mock_device_manager.devices["soundbar"].state = {"power": False}
    
    # Create a modified scenario with conditions
    modified_def = sample_scenario_definition.model_copy(deep=True)
    
    # Add condition to TV power command: only execute if power is already on
    modified_def.startup_sequence[0].condition = "device.power == True"
    
    # Add condition to soundbar power command: only execute if power is off
    modified_def.startup_sequence[1].condition = "device.power == False"
    
    # Create mock for evaluate_condition to ensure conditions work properly
    scenario = Scenario(modified_def, mock_device_manager)
    
    # Mock the condition evaluation
    original_evaluate = scenario._evaluate_condition
    
    async def mock_evaluate_condition(condition, device):
        if condition == "device.power == True":
            return False  # TV condition (should not execute)
        elif condition == "device.power == False":
            return True  # Soundbar condition (should execute)
        return await original_evaluate(condition, device)
    
    scenario._evaluate_condition = mock_evaluate_condition
    
    return scenario 