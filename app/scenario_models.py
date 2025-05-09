from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, validator, field_validator, model_validator
import logging

logger = logging.getLogger(__name__)

class ManualInstructions(BaseModel):
    """Instructions that require human intervention (cannot be automated)."""
    startup: List[str] = Field(default_factory=list, description="Steps to perform when starting the scenario")
    shutdown: List[str] = Field(default_factory=list, description="Steps to perform when shutting down the scenario")

class CommandStep(BaseModel):
    """A step in a scenario sequence (startup or shutdown)."""
    device: str = Field(..., description="Device ID to execute the command on")
    command: str = Field(..., description="Command name to execute")
    params: Dict[str, Any] = Field(default_factory=dict, description="Command parameters")
    condition: Optional[str] = Field(None, description="Expression to evaluate against device state, run only if True")
    delay_after_ms: int = Field(0, description="Delay in milliseconds after executing this command", ge=0)

class ScenarioDefinition(BaseModel):
    """Declarative definition of a scenario."""
    scenario_id: str = Field(..., min_length=1, description="Unique identifier for the scenario")
    name: str = Field(..., description="Human-readable name")
    description: str = Field("", description="Description of the scenario's purpose")
    room_id: Optional[str] = Field(
        None,
        description="If set, declares the primary room this scenario runs in. All devices must be in this room."
    )
    roles: Dict[str, str] = Field(..., description="Mapping of role name to device ID")
    devices: Dict[str, Dict[str, List[str]]] = Field(..., description="Devices used in the scenario with their groups")
    startup_sequence: List[CommandStep] = Field(..., description="Sequence of commands to run when starting")
    shutdown_sequence: Dict[str, List[CommandStep]] = Field(
        ..., 
        description="Sequences for shutdown: 'complete' (full power-off) and 'transition' (for switching to another scenario)"
    )
    manual_instructions: Optional[ManualInstructions] = Field(
        None, 
        description="Instructions requiring human intervention"
    )

    @field_validator("shutdown_sequence")
    @classmethod
    def _validate_shutdown(cls, v):
        missing = {"complete", "transition"} - v.keys()
        if missing:
            raise ValueError(f"shutdown_sequence missing keys: {missing}")
        return v

    @model_validator(mode="after")
    def validate_references(self):
        """Validates internal references but not system device existence (done at runtime)."""
        # Validate that roles reference devices in the devices dict
        for role, device_id in self.roles.items():
            if device_id not in self.devices:
                raise ValueError(f"Role '{role}' references device '{device_id}' which is not in devices dict")
        
        # Validate references in startup sequence
        for i, step in enumerate(self.startup_sequence):
            if step.device not in self.devices:
                raise ValueError(
                    f"Device '{step.device}' in startup sequence (step {i+1}) is not in devices dict"
                )
        
        # Validate references in shutdown sequences
        for key in ["complete", "transition"]:
            for i, step in enumerate(self.shutdown_sequence[key]):
                if step.device not in self.devices:
                    raise ValueError(
                        f"Device '{step.device}' in shutdown sequence '{key}' (step {i+1}) is not in devices dict"
                    )
        
        return self

class DeviceState(BaseModel):
    """Runtime state of a device."""
    power: Optional[bool] = Field(None, description="True = ON, False = OFF")
    input: Optional[str] = Field(None, description="Active input port")
    output: Optional[str] = Field(None, description="Active output port")
    extra: Dict[str, Any] = Field(default_factory=dict, description="Additional device-specific state fields")

class ScenarioState(BaseModel):
    """Runtime state of a scenario."""
    scenario_id: str = Field(..., description="ID of the active scenario")
    devices: Dict[str, DeviceState] = Field(default_factory=dict, description="Current state of all devices in the scenario")

    @field_validator("scenario_id")
    @classmethod
    def non_empty(cls, v):
        if not v:
            raise ValueError("scenario_id must be non-empty")
        return v

class RoomDefinition(BaseModel):
    """Definition of a room and its contained devices."""
    room_id: str = Field(..., description="Unique identifier for the room")
    names: Dict[str, str] = Field(..., description="Localized names (locale code -> name)")
    description: str = Field("", description="Description of the room")
    devices: List[str] = Field(..., description="List of device IDs in this room")
    default_scenario: Optional[str] = Field(None, description="Default scenario ID for this room")

    @model_validator(mode="after")
    def validate_locales(self):
        """Validates that at least one locale is defined."""
        if not self.names:
            raise ValueError("At least one locale name must be defined for the room")
        return self

class ConfigDelta(BaseModel):
    """Represents the difference between two device configurations."""
    requires_io_switch: bool = Field(False, description="Whether I/O settings need to be changed")
    io_args: Dict[str, Any] = Field(default_factory=dict, description="Arguments for I/O switching")
    power_args: Dict[str, Any] = Field(default_factory=dict, description="Arguments for power state changes")

class DeviceConfig(BaseModel):
    """Configuration for a device that can be compared to detect needed changes."""
    input: str = Field(..., description="Input configuration")
    output: str = Field(..., description="Output configuration")
    power_on_delay: int = Field(0, description="Delay in ms after powering on before further commands", ge=0)

    def diff(self, other: "DeviceConfig") -> ConfigDelta:
        """
        Compare two device configs and produce a delta for efficient transitions.
        
        Args:
            other: The other device configuration to compare against
            
        Returns:
            ConfigDelta: An object describing the required changes
        """
        delta = ConfigDelta()
        
        # Check if I/O settings have changed
        if self.input != other.input or self.output != other.output:
            delta.requires_io_switch = True
            delta.io_args = {
                "input": self.input,
                "output": self.output
            }
            
        return delta