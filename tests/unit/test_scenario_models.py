import pytest
from pydantic import ValidationError
from app.scenario_models import (
    ManualInstructions,
    CommandStep,
    ScenarioDefinition,
    DeviceState,
    ScenarioState,
    RoomDefinition,
    ConfigDelta,
    DeviceConfig
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
            roles={"screen": "device1", "audio": "device2"},
            devices={
                "device1": {"groups": ["screen"]},
                "device2": {"groups": ["audio"]}
            },
            startup_sequence=[
                CommandStep(device="device1", command="power_on"),
                CommandStep(device="device2", command="power_on")
            ],
            shutdown_sequence={
                "complete": [
                    CommandStep(device="device1", command="power_off"),
                    CommandStep(device="device2", command="power_off")
                ],
                "transition": [
                    CommandStep(device="device1", command="standby"),
                    CommandStep(device="device2", command="standby")
                ]
            }
        )
        
        assert scenario.scenario_id == "test_scenario"
        assert scenario.name == "Test Scenario"
        assert len(scenario.startup_sequence) == 2
        assert len(scenario.shutdown_sequence["complete"]) == 2
        assert len(scenario.shutdown_sequence["transition"]) == 2
    
    def test_shutdown_sequence_validation(self):
        with pytest.raises(ValueError, match="shutdown_sequence missing keys"):
            ScenarioDefinition(
                scenario_id="test_scenario",
                name="Test Scenario",
                roles={"screen": "device1"},
                devices={"device1": {"groups": ["screen"]}},
                startup_sequence=[],
                shutdown_sequence={
                    # Missing "transition" key
                    "complete": []
                }
            )
    
    def test_device_references_validation(self):
        # Role references non-existent device
        with pytest.raises(ValueError, match="Role 'screen' references device 'device1'"):
            ScenarioDefinition(
                scenario_id="test_scenario",
                name="Test Scenario",
                roles={"screen": "device1"},
                devices={"device2": {"groups": ["screen"]}},  # device1 not in devices
                startup_sequence=[],
                shutdown_sequence={"complete": [], "transition": []}
            )
        
        # Startup sequence references non-existent device
        with pytest.raises(ValueError, match="Device 'device3' in startup sequence"):
            ScenarioDefinition(
                scenario_id="test_scenario",
                name="Test Scenario",
                roles={"screen": "device1"},
                devices={"device1": {"groups": ["screen"]}},
                startup_sequence=[
                    CommandStep(device="device3", command="power_on")  # device3 not in devices
                ],
                shutdown_sequence={"complete": [], "transition": []}
            )
        
        # Shutdown sequence references non-existent device
        with pytest.raises(ValueError, match="Device 'device3' in shutdown sequence 'complete'"):
            ScenarioDefinition(
                scenario_id="test_scenario",
                name="Test Scenario",
                roles={"screen": "device1"},
                devices={"device1": {"groups": ["screen"]}},
                startup_sequence=[],
                shutdown_sequence={
                    "complete": [
                        CommandStep(device="device3", command="power_off")  # device3 not in devices
                    ],
                    "transition": []
                }
            )

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

class TestDeviceConfig:
    def test_required_fields(self):
        with pytest.raises(ValidationError):
            DeviceConfig()  # Missing required fields
    
    def test_valid_config(self):
        config = DeviceConfig(
            input="hdmi1",
            output="display"
        )
        
        assert config.input == "hdmi1"
        assert config.output == "display"
        assert config.power_on_delay == 0
    
    def test_diff_with_changes(self):
        config1 = DeviceConfig(input="hdmi1", output="display")
        config2 = DeviceConfig(input="hdmi2", output="display")
        
        delta = config1.diff(config2)
        
        assert delta.requires_io_switch is True
        assert delta.io_args == {"input": "hdmi1", "output": "display"}
    
    def test_diff_without_changes(self):
        config1 = DeviceConfig(input="hdmi1", output="display")
        config2 = DeviceConfig(input="hdmi1", output="display")
        
        delta = config1.diff(config2)
        
        assert delta.requires_io_switch is False
        assert delta.io_args == {} 