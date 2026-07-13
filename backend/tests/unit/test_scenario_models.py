import pytest
from pydantic import ValidationError
from locveil_bridge.domain.scenarios.models import (
    ManualInstructions,
    ScenarioDefinition,
    DeviceState,
    ScenarioState,
    RoomDefinition
)

pytestmark = pytest.mark.unit

class TestManualInstructions:
    def test_default_values(self):
        instructions = ManualInstructions()
        assert instructions.startup == []
        assert instructions.shutdown == []

    def test_with_values(self):
        startup_steps = ["Step 1", "Step 2"]
        shutdown_steps = ["Step 3"]
        instructions = ManualInstructions(startup=startup_steps, shutdown=shutdown_steps)

        assert instructions.startup == startup_steps
        assert instructions.shutdown == shutdown_steps

class TestScenarioDefinition:
    def test_required_fields(self):
        with pytest.raises(ValidationError):
            ScenarioDefinition()  # Missing required fields

    def test_valid_scenario(self):
        scenario = ScenarioDefinition(
            scenario_id="test_scenario",
            names={"ru": "Тест", "en": "Test Scenario"},
            description="A test scenario",
            room_id="living_room",
            roles={"screen": "device1"},
            devices=["device1", "device2"],
            source="device2",
            display="device1",
        )

        assert scenario.scenario_id == "test_scenario"
        assert scenario.names.en == "Test Scenario"
        assert scenario.description == "A test scenario"
        assert scenario.room_id == "living_room"
        assert scenario.roles == {"screen": "device1"}
        assert "device1" in scenario.devices
        assert "device2" in scenario.devices
        assert scenario.source == "device2"
        assert scenario.display == "device1"
        assert scenario.audio is None

    def test_device_references_validation(self):
        # Role references non-existent device
        with pytest.raises(ValueError, match="Role 'screen' references device 'device2' which is not in devices"):
            ScenarioDefinition(
                scenario_id="test_scenario",
                names={"ru": "Тест", "en": "Test Scenario"},
                roles={"screen": "device2"},  # device2 not in devices
                devices=["device1"],
            )

        # Test with valid references
        valid = ScenarioDefinition(
            scenario_id="test_scenario",
            names={"ru": "Тест", "en": "Test Scenario"},
            roles={"screen": "device1"},
            devices=["device1"],
        )
        assert valid is not None

    def test_thin_scenario_skips_devices_cross_check(self):
        # Thin scenarios normally author no devices list — role references are
        # resolved against the DeviceManager at load time, not the model.
        thin = ScenarioDefinition(
            scenario_id="thin_scenario",
            names={"ru": "Тонкий", "en": "Thin Scenario"},
            roles={"screen": "device1"},
            source="device2",
        )
        assert thin.devices == []
        assert thin.source == "device2"

class TestDeviceState:
    def test_default_values(self):
        state = DeviceState()
        assert state.power is None
        assert state.input is None
        assert state.extra == {}

    def test_with_values(self):
        state = DeviceState(
            power=True,
            input="hdmi1",
            extra={"volume": 50}
        )

        assert state.power is True
        assert state.input == "hdmi1"
        assert state.extra == {"volume": 50}

class TestScenarioState:
    def test_required_fields(self):
        with pytest.raises(ValidationError):
            ScenarioState()  # Missing scenario_id

    def test_with_values(self):
        state = ScenarioState(
            scenario_id="test_scenario",
            devices={
                "device1": DeviceState(power=True),
                "device2": DeviceState(power=False)
            }
        )

        assert state.scenario_id == "test_scenario"
        assert len(state.devices) == 2
        assert state.devices["device1"].power is True
        assert state.devices["device2"].power is False

    def test_empty_scenario_id_validation(self):
        with pytest.raises(ValueError, match="scenario_id must be non-empty"):
            ScenarioState(scenario_id="")

class TestRoomDefinition:
    def test_required_fields(self):
        with pytest.raises(ValidationError):
            RoomDefinition()  # Missing required fields

        with pytest.raises(ValidationError):
            RoomDefinition(room_id="living_room", devices=[])  # Missing names

    def test_valid_room(self):
        room = RoomDefinition(
            room_id="living_room",
            names={"en": "Living Room", "es": "Sala de Estar"},
            description="Main living area",
            devices=["tv", "soundbar", "lights"],
            default_scenario="movie_night"
        )

        assert room.room_id == "living_room"
        assert room.names == {"en": "Living Room", "es": "Sala de Estar"}
        assert room.description == "Main living area"
        assert room.devices == ["tv", "soundbar", "lights"]
        assert room.default_scenario == "movie_night"

    def test_locale_validation(self):
        with pytest.raises(ValueError, match="At least one locale name must be defined"):
            RoomDefinition(
                room_id="living_room",
                names={},  # Empty names dict
                devices=["tv"]
            )
