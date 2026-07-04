from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, field_validator, model_validator
import logging

logger = logging.getLogger(__name__)

class ScenarioConfigurationError(Exception):
    """Raised when a scenario configuration is invalid during loading."""
    
    def __init__(self, scenario_id: str, errors: List[str]):
        self.scenario_id = scenario_id
        self.errors = errors
        error_details = '\n'.join(f"  - {error}" for error in errors)
        super().__init__(f"Scenario '{scenario_id}' configuration is invalid:\n{error_details}")

class ScenarioValidationError(Exception):
    """Raised when scenario validation fails with detailed context."""
    
    def __init__(self, scenario_id: str, validation_type: str, detail: str, location: str = ""):
        self.scenario_id = scenario_id
        self.validation_type = validation_type
        self.detail = detail
        self.location = location
        
        location_info = f" in {location}" if location else ""
        super().__init__(f"Scenario '{scenario_id}' {validation_type} validation failed{location_info}: {detail}")

class ManualInstructions(BaseModel):
    """Instructions that require human intervention (cannot be automated)."""
    startup: List[str] = Field(default_factory=list, description="Steps to perform when starting the scenario")
    shutdown: List[str] = Field(default_factory=list, description="Steps to perform when shutting down the scenario")

class ScenarioDefinition(BaseModel):
    """Declarative definition of a scenario.

    Scenarios are **thin**: a ``source``/``display``/``audio`` selection. Device membership,
    input values, and ordering are derived from ``config/topology.json`` by the reconciler.
    The pre-redesign imperative format (explicit ``startup_sequence``/``shutdown_sequence``
    steps) was removed once every shipped scenario had migrated.

    See docs/design/scenarios/scenario_system_redesign.md §6.
    """
    scenario_id: str = Field(..., min_length=1, description="Unique identifier for the scenario")
    name: str = Field(..., description="Human-readable name")
    description: str = Field(default="", description="Description of the scenario's purpose")
    room_id: Optional[str] = Field(
        default=None,
        description="If set, declares the primary room this scenario runs in. All devices must be in this room.",
    )
    roles: Dict[str, str] = Field(default_factory=dict, description="Mapping of role name to device ID")
    # Thin selection (preferred). The reconciler derives membership/inputs/ordering from topology.
    source: Optional[str] = Field(default=None, description="Primary content source device id")
    display: Optional[str] = Field(default=None, description="Primary video sink device id")
    audio: Optional[str] = Field(default=None, description="Active audio device id; binds the volume/mute roles")
    # Optional explicit device list (thin scenarios normally leave this empty — membership is
    # derived from the topology at resolve time).
    devices: List[str] = Field(default_factory=list, description="Explicit device list (optional)")
    manual_instructions: Optional[ManualInstructions] = Field(
        default=None,
        description="Instructions requiring human intervention",
    )

    @model_validator(mode="after")
    def validate_references(self):
        """Validate internal references when an explicit ``devices`` list is authored. Thin
        scenarios derive membership from the topology, so there is nothing to cross-check
        here (validated at resolve time)."""
        if not self.devices:
            return self

        # Validate that roles reference devices in the devices list
        for role, device_id in self.roles.items():
            if device_id not in self.devices:
                raise ValueError(f"Role '{role}' references device '{device_id}' which is not in devices list")

        return self

class DeviceState(BaseModel):
    """Runtime state of a device."""
    power: Optional[bool] = Field(None, description="True = ON, False = OFF")
    input: Optional[str] = Field(None, description="Active input port")
    extra: Dict[str, Any] = Field(default_factory=dict, description="Additional device-specific state fields")

class ManualStep(BaseModel):
    """A manual instruction surfaced by a topology manual node (e.g. set the Dodocus
    RCA hub to the LD position) — load-bearing when the activated path crosses a
    manual switch (audio path through the hub).
    """
    node: str = Field(..., description="Topology node id surfacing this instruction")
    instruction: str = Field(..., description="Human instruction to perform")

class ScenarioState(BaseModel):
    """Runtime state of a scenario."""
    scenario_id: str = Field(..., description="ID of the active scenario")
    devices: Dict[str, DeviceState] = Field(default_factory=dict, description="Current state of all devices in the scenario")
    manual_steps: List[ManualStep] = Field(
        default_factory=list,
        description="Manual notes from the most recent activation (e.g. 'set the Dodocus to LD'); "
                    "single source of truth — same data was previously duplicated in the SSE event "
                    "payload + ScenarioResponse; survives page reload via /scenario/state.",
    )

    @field_validator("scenario_id")
    @classmethod
    def non_empty(cls, v):
        if not v:
            raise ValueError("scenario_id must be non-empty")
        return v

class RoomDefinition(BaseModel):
    """Definition of a room and its contained devices.

    `devices` is DERIVED at load time by `RoomManager` from `DeviceManager` (each device
    declares its room via `DevicePort.get_room()`). Authored rooms.json files should
    carry only the spatial metadata (room_id + names + description + default_scenario);
    any legacy `devices` field is stripped and ignored. Default is an empty list so
    the manager can populate it imperatively after parsing.
    """
    room_id: str = Field(..., description="Unique identifier for the room")
    names: Dict[str, str] = Field(..., description="Localized names (locale code -> name)")
    description: str = Field("", description="Description of the room")
    devices: List[str] = Field(
        default_factory=list,
        description="Device IDs in this room — POPULATED by RoomManager from DeviceManager at "
                    "load time, NOT authored in rooms.json (any legacy authored array is ignored).",
    )
    default_scenario: Optional[str] = Field(None, description="Default scenario ID for this room")

    @model_validator(mode="after")
    def validate_locales(self):
        """Validates that at least one locale is defined."""
        if not self.names:
            raise ValueError("At least one locale name must be defined for the room")
        return self