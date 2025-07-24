import pytest
from pydantic import ValidationError
from wb_mqtt_bridge.domain.scenarios.models import (
    ManualInstructions,
    CommandStep,
    ScenarioDefinition,
    DeviceState,
    ScenarioState,
    RoomDefinition
)

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

class TestCommandStep:
    def test_required_fields(self):
        with pytest.raises(ValidationError):
            CommandStep()  # Missing required fields
            
        with pytest.raises(ValidationError):
            CommandStep(device="device1")  # Missing command
            
        # Should work with required fields
        step = CommandStep(device="device1", command="power_on")
        assert step.device == "device1"
        assert step.command == "power_on"
        assert step.params == {}
        assert step.condition is None
        assert step.delay_after_ms == 0
    
    def test_all_fields(self):
        step = CommandStep(
            device="device1",
            command="set_input",
            params={"input": "hdmi1"},
            condition="device.input != 'hdmi1'",
            delay_after_ms=1000
        )
        
        assert step.device == "device1"
        assert step.command == "set_input"
        assert step.params == {"input": "hdmi1"}
        assert step.condition == "device.input != 'hdmi1'"
        assert step.delay_after_ms == 1000
    
    def test_validation(self):
        with pytest.raises(ValidationError):
            CommandStep(device="device1", command="power_on", delay_after_ms=-100)  # Negative delay

class TestScenarioDefinition:
    def test_required_fields(self):
        with pytest.raises(ValidationError):
            ScenarioDefinition()  # Missing required fields
    
    def test_valid_scenario(self):
        scenario = ScenarioDefinition(
            scenario_id="test_scenario",
            name="Test Scenario",
            description="A test scenario",
            room_id="living_room",
            roles={"screen": "device1"},
            devices=["device1", "device2"],
            startup_sequence=[
                CommandStep(
                    device="device1",
                    command="power_on"
                )
            ],
            shutdown_sequence=[
                CommandStep(
                    device="device1",
                    command="power_off"
                )
            ]
        )
        
        assert scenario.scenario_id == "test_scenario"
        assert scenario.name == "Test Scenario"
        assert scenario.description == "A test scenario"
        assert scenario.room_id == "living_room"
        assert scenario.roles == {"screen": "device1"}
        assert "device1" in scenario.devices
        assert "device2" in scenario.devices
        assert len(scenario.startup_sequence) == 1
        assert scenario.startup_sequence[0].device == "device1"
        assert scenario.startup_sequence[0].command == "power_on"
        assert len(scenario.shutdown_sequence) == 1
        assert scenario.shutdown_sequence[0].device == "device1"
        assert scenario.shutdown_sequence[0].command == "power_off"
    
    def test_device_references_validation(self):
        # Role references non-existent device
        with pytest.raises(ValueError, match="Role 'screen' references device 'device2' which is not in devices"):
            valid_def = ScenarioDefinition(
                scenario_id="test_scenario",
                name="Test Scenario",
                roles={"screen": "device2"},  # device2 not in devices
                devices=["device1"],
                startup_sequence=[
                    CommandStep(
                        device="device1",
                        command="power_on"
                    )
                ],
                shutdown_sequence=[
                    CommandStep(
                        device="device1",
                        command="power_off"
                    )
                ]
            )
            valid_def.validate_references()  # Trigger validation
        
        # Startup sequence references non-existent device
        with pytest.raises(ValueError, match="Device 'device2' in startup sequence"):
            valid_def = ScenarioDefinition(
                scenario_id="test_scenario",
                name="Test Scenario",
                roles={"screen": "device1"},
                devices=["device1"],
                startup_sequence=[
                    CommandStep(
                        device="device2",  # device2 not in devices
                        command="power_on"
                    )
                ],
                shutdown_sequence=[
                    CommandStep(
                        device="device1",
                        command="power_off"
                    )
                ]
            )
            valid_def.validate_references()  # Trigger validation
        
        # Shutdown sequence references non-existent device
        with pytest.raises(ValueError, match="Device 'device2' in shutdown sequence"):
            valid_def = ScenarioDefinition(
                scenario_id="test_scenario",
                name="Test Scenario",
                roles={"screen": "device1"},
                devices=["device1"],
                startup_sequence=[
                    CommandStep(
                        device="device1",
                        command="power_on"
                    )
                ],
                shutdown_sequence=[
                    CommandStep(
                        device="device2",  # device2 not in devices
                        command="power_off"
                    )
                ]
            )
            valid_def.validate_references()  # Trigger validation
        
        # Test with valid references
        valid = ScenarioDefinition(
            scenario_id="test_scenario",
            name="Test Scenario",
            roles={"screen": "device1"},
            devices=["device1"],
            startup_sequence=[
                CommandStep(device="device1", command="power_on")
            ],
            shutdown_sequence=[
                CommandStep(device="device1", command="power_off")
            ]
        )
        assert valid is not None

class TestDeviceState:
    def test_default_values(self):
        state = DeviceState()
        assert state.power is None
        assert state.input is None
        assert state.output is None
        assert state.extra == {}
    
    def test_with_values(self):
        state = DeviceState(
            power=True,
            input="hdmi1",
            output="display",
            extra={"volume": 50}
        )
        
        assert state.power is True
        assert state.input == "hdmi1"
        assert state.output == "display"
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