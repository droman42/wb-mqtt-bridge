import pytest
from unittest.mock import AsyncMock

from wb_mqtt_bridge.domain.scenarios.scenario import Scenario, ScenarioError, ScenarioExecutionError
from wb_mqtt_bridge.domain.scenarios.models import ScenarioDefinition

pytestmark = pytest.mark.unit

# Sample scenario data for testing (thin format: source/display/audio selection;
# the imperative startup/shutdown-sequence format was removed by the dead-code sweep).
SAMPLE_SCENARIO = {
    "scenario_id": "test_scenario",
    "name": "Test Scenario",
    "description": "A test scenario",
    "roles": {"main_display": "tv", "audio": "soundbar"},
    "devices": ["tv", "soundbar"],
    "source": "tv",
    "display": "tv",
    "audio": "soundbar",
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
        self.execute_action = AsyncMock()

    def get_current_state(self):
        return self.state

    def get_available_commands(self):
        from types import SimpleNamespace
        # SimpleNamespace with parameters=None bypasses parameter validation
        return {cmd: SimpleNamespace(parameters=None) for cmd in [
            "power_on", "power_off", "set_input", "set_scene",
            "set_volume", "volume_up", "volume_down",
        ]}

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

    @pytest.mark.asyncio
    async def test_execute_role_action_success(self, scenario, mock_device_manager):
        """Test successful execution of a role action"""
        # Arrange
        mock_device_manager.devices["tv"].execute_action.return_value = {"status": "success"}

        # Act
        result = await scenario.execute_role_action("main_display", "power_on", volume=50)

        # Assert
        mock_device_manager.devices["tv"].execute_action.assert_called_once_with("power_on", {"volume": 50}, source="scenario")
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
        mock_device_manager.devices["tv"].execute_action.side_effect = Exception("Device error")

        with pytest.raises(ScenarioExecutionError) as excinfo:
            await scenario.execute_role_action("main_display", "power_on")

        assert "Failed to execute power_on on tv" in str(excinfo.value)
        assert excinfo.value.error_type == "execution"
        assert excinfo.value.role == "main_display"
        assert excinfo.value.device_id == "tv"
        assert excinfo.value.command == "power_on"

    def test_validate_valid_scenario(self, scenario, mock_device_manager):
        """A valid scenario passes validate_configuration() silently.

        The old API returned an error list; the current API raises
        ScenarioConfigurationError on errors and returns None on success.
        """
        # Production: validate_configuration() returns None on success.
        result = scenario.validate_configuration()
        assert result is None

    def test_validate_missing_devices(self, scenario, mock_device_manager):
        """validate_configuration() raises ScenarioConfigurationError when devices are missing.

        Semantic intent (preserved from the original test): a scenario referencing
        devices that the DeviceManager does not know about must be rejected at
        validation time, with the offending device IDs surfaced in the error.
        """
        from wb_mqtt_bridge.domain.scenarios.models import ScenarioConfigurationError

        # Strip all devices so the scenario's tv/soundbar references become invalid.
        mock_device_manager.devices.clear()

        with pytest.raises(ScenarioConfigurationError) as excinfo:
            scenario.validate_configuration()

        # ScenarioConfigurationError exposes `errors` (List[str]); each missing
        # device should be mentioned by ID somewhere in that list.
        errors = excinfo.value.errors
        flattened = "\n".join(errors)
        assert "'tv'" in flattened
        assert "'soundbar'" in flattened

    def test_validate_requires_thin_source(self, mock_device_manager):
        """A scenario without a thin `source` selection is rejected at validation time.

        With the imperative startup/shutdown-sequence format removed, a scenario
        that declares no source could never be activated (the reconciler would have
        nothing to resolve) — validation must catch it at load time.
        """
        from wb_mqtt_bridge.domain.scenarios.models import ScenarioConfigurationError

        data = {k: v for k, v in SAMPLE_SCENARIO.items() if k not in ("source", "display", "audio")}
        definition = ScenarioDefinition.model_validate(data)
        sourceless = Scenario(definition, mock_device_manager)

        with pytest.raises(ScenarioConfigurationError) as excinfo:
            sourceless.validate_configuration()

        assert any("source" in err for err in excinfo.value.errors)

    # The old test_validate_with_room_manager checked that a Scenario object
    # validates "this device is in the room declared by room_id". That responsibility
    # moved out of Scenario.validate_configuration() (which now only validates
    # internal definition references; room-vs-device containment is handled by
    # ScenarioManager / RoomManager). No replacement test in this file — the
    # responsibility is exercised at the manager layer.
