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
    devices: List[str] = Field(..., description="List of device IDs used in the scenario")
    startup_sequence: List[CommandStep] = Field(..., description="Sequence of commands to run when starting")
    shutdown_sequence: List[CommandStep] = Field(
        ..., 
        description="Sequence of commands to run when shutting down"
    )
    manual_instructions: Optional[ManualInstructions] = Field(
        None, 
        description="Instructions requiring human intervention"
    )

    @model_validator(mode="after")
    def validate_references(self):
        """Validates internal references but not system device existence (done at runtime)."""
        # Validate that roles reference devices in the devices list
        for role, device_id in self.roles.items():
            if device_id not in self.devices:
                raise ValueError(f"Role '{role}' references device '{device_id}' which is not in devices list")
        
        # Validate references in startup sequence
        for i, step in enumerate(self.startup_sequence):
            if step.device not in self.devices:
                raise ValueError(
                    f"Device '{step.device}' in startup sequence (step {i+1}) is not in devices list"
                )
        
        # Validate references in shutdown sequence
        for i, step in enumerate(self.shutdown_sequence):
            if step.device not in self.devices:
                raise ValueError(
                    f"Device '{step.device}' in shutdown sequence (step {i+1}) is not in devices list"
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