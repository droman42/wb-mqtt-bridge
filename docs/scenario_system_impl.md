# Scenario System Implementation Plan

## Overview

This document outlines the implementation plan for the Scenario System as specified in `docs/scenario_system_spec.md`. The Scenario System provides a framework for managing scenarios that control multiple devices in a coordinated way, with rooms providing spatial context.

## File Structure

```
app/
  ├── scenario_models.py     # Pydantic models for scenarios and rooms
  ├── room_manager.py        # RoomManager implementation
  ├── scenario.py            # Scenario class implementation
  ├── scenario_manager.py    # ScenarioManager implementation
config/
  ├── rooms.json             # Room definitions
  ├── scenarios/             # Directory for scenario JSON files
    ├── movie_night.json
    ├── cooking_mode.json
    └── ...
tests/
  ├── unit/
    ├── test_room_manager.py
    ├── test_scenario_manager.py
    ├── test_scenario.py
    └── test_scenario_models.py
```

## Implementation Steps

### Phase 1: Pydantic Models (app/scenario_models.py)

1. Implement all Pydantic models:
   - `CommandStep`
   - `ManualInstructions`
   - `ScenarioDefinition`
   - `DeviceConfig`
   - `ConfigDelta`
   - `DeviceState`
   - `ScenarioState`
   - `RoomDefinition`

2. Implement validation rules:
   - Device validation
   - Role validation
   - Group validation
   - Dependency validation
   - Function validation
   - Room validation
   - Scenario-Room containment
   - Manual instructions validation

### Phase 2: Room Management (app/room_manager.py)

1. Implement `RoomManager` class based on the skeleton:
   - Constructor to accept config directory and device manager
   - `reload()` method to load room definitions from JSON
   - `list()` method to get all rooms
   - `get(room_id)` method to get a specific room
   - `contains_device(room_id, device_id)` method
   - `default_scenario(room_id)` method
   - `_validate_devices_exist()` helper method

2. Create sample `rooms.json` in the config directory.

### Phase 3: Scenario Class (app/scenario.py)

1. Implement `Scenario` class:
   - Constructor to accept definition and device manager
   - `execute_role_action(role, command, **params)`
   - `initialize()` 
   - `execute_startup_sequence()`
   - `execute_shutdown_sequence(complete)`
   - `_evaluate_condition()` helper
   - `validate()` method

2. Implement error handling:
   - `ScenarioError` class
   - `ScenarioExecutionError` class

### Phase 4: Scenario Manager (app/scenario_manager.py)

1. Implement `ScenarioManager` class:
   - Constructor to accept dependencies (room_manager, device_manager, state_store)
   - `current_scenario` and `scenario_state` attributes
   - Diff-aware `switch_scenario(target_id, graceful)` method
   - Methods for saving and loading scenario state

2. Implement `DeviceConfig` class with diff contract

### Phase 5: REST API & MQTT Integration

1. Create REST API endpoints in app/routers/ directory:
   - GET `/scenario/state`
   - GET `/scenario/definition/{id}`
   - POST `/scenario/switch`
   - POST `/scenario/role_action`
   - GET `/room/list`
   - GET `/room/{room_id}`
   - POST `/room`
   - GET `/scenario/definition?room={id}`

2. Wire up MQTT topics for scenarios
   - Subscribe to command topics
   - Publish state changes

### Phase 6: Testing

1. Unit tests:
   - Test room manager functionality
   - Test scenario model validation
   - Test scenario execution
   - Test scenario manager transitions

2. Integration tests:
   - Test state persistence
   - Test API endpoints
   - Test end-to-end scenario transitions

## Detailed Implementation Breakdown

### app/scenario_models.py

```python
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, validator
from enum import Enum

class ManualInstructions(BaseModel):
    startup: list[str] = Field(default_factory=list)
    shutdown: list[str] = Field(default_factory=list)

class CommandStep(BaseModel):
    device: str
    command: str
    params: Dict[str, Any] = Field(default_factory=dict)
    condition: Optional[str] = None
    delay_after_ms: int = 0

class ScenarioDefinition(BaseModel):
    scenario_id: str = Field(..., min_length=1)
    name: str
    description: str = ""
    room_id: Optional[str] = Field(
        None,
        description="If set, declares the primary room this scenario runs in."
    )
    roles: Dict[str, str]  # role_name → device_id
    devices: Dict[str, Dict[str, List[str]]]
    startup_sequence: List[CommandStep]
    shutdown_sequence: Dict[str, List[CommandStep]]  # keys: "complete", "transition"
    manual_instructions: Optional[ManualInstructions] = None

    @validator("shutdown_sequence")
    def _validate_shutdown(cls, v):
        missing = {"complete", "transition"} - v.keys()
        if missing:
            raise ValueError(f"shutdown_sequence missing keys: {missing}")
        return v

class DeviceState(BaseModel):
    power: Optional[bool] = Field(None, description="True = ON, False = OFF")
    input: Optional[str] = Field(None, description="Active input port")
    output: Optional[str] = Field(None, description="Active output port")
    extra: Dict[str, Any] = Field(default_factory=dict)

class ScenarioState(BaseModel):
    scenario_id: str
    devices: Dict[str, DeviceState] = Field(default_factory=dict)

    @validator("scenario_id")
    def non_empty(cls, v):
        if not v:
            raise ValueError("scenario_id must be non‑empty")
        return v

class RoomDefinition(BaseModel):
    room_id: str
    names: Dict[str, str]  # locale-code → string
    description: str = ""
    devices: list[str]
    default_scenario: Optional[str] = None

class ConfigDelta(BaseModel):
    requires_io_switch: bool = False
    io_args: Dict[str, Any] = Field(default_factory=dict)
    power_args: Dict[str, Any] = Field(default_factory=dict)

class DeviceConfig(BaseModel):
    input: str
    output: str
    power_on_delay: int = 0

    def diff(self, other: "DeviceConfig") -> ConfigDelta:
        """Compare two device configs and produce a delta for efficient transitions."""
        delta = ConfigDelta()
        
        # Check if I/O settings have changed
        if self.input != other.input or self.output != other.output:
            delta.requires_io_switch = True
            delta.io_args = {
                "input": self.input,
                "output": self.output
            }
            
        return delta
```

### app/room_manager.py

```python
from pathlib import Path
import json
import logging
from typing import Dict, List, Optional

from app.scenario_models import RoomDefinition

logger = logging.getLogger(__name__)

class RoomManager:
    def __init__(self, cfg_dir: Path, device_manager: "DeviceManager"):
        self._dir = cfg_dir
        self._device_mgr = device_manager
        self.rooms: Dict[str, RoomDefinition] = {}
        self.reload()

    # ------------- Public -------------
    def reload(self) -> None:
        """Load room definitions from rooms.json"""
        try:
            raw = json.loads(Path(self._dir / "rooms.json").read_text(encoding="utf-8"))
            self.rooms.clear()
            for rid, spec in raw.items():
                room = RoomDefinition(**spec)
                self._validate_devices_exist(room)
                self.rooms[rid] = room
            logger.info(f"Loaded {len(self.rooms)} rooms from configuration")
        except FileNotFoundError:
            logger.warning(f"Rooms configuration file not found at {self._dir}/rooms.json")
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing rooms.json: {str(e)}")
        except Exception as e:
            logger.error(f"Error loading rooms: {str(e)}")

    def list(self) -> list[RoomDefinition]:
        """Return a list of all room definitions"""
        return list(self.rooms.values())

    def get(self, room_id: str) -> Optional[RoomDefinition]:
        """Get a room definition by ID"""
        return self.rooms.get(room_id)

    def contains_device(self, room_id: str, device_id: str) -> bool:
        """Check if a room contains a specific device"""
        room = self.rooms.get(room_id)
        return room and device_id in room.devices

    def default_scenario(self, room_id: str) -> Optional[str]:
        """Get the default scenario for a room"""
        room = self.rooms.get(room_id)
        return room.default_scenario if room else None

    # ------------- Internal -------------
    def _validate_devices_exist(self, room: RoomDefinition) -> None:
        """Validate that all devices in a room exist in the system"""
        unknown = [d for d in room.devices if d not in self._device_mgr.devices]
        if unknown:
            raise ValueError(
                f"Room '{room.room_id}' references unknown devices {unknown}"
            )
```

### app/scenario.py

```python
import asyncio
import logging
from typing import Any, Dict, List, Optional, Union
import traceback

from app.scenario_models import ScenarioDefinition, CommandStep

logger = logging.getLogger(__name__)

class ScenarioError(Exception):
    def __init__(self, msg: str, error_type: str, critical: bool = False):
        super().__init__(msg)
        self.error_type = error_type
        self.critical = critical

class ScenarioExecutionError(ScenarioError):
    def __init__(self, msg: str, role: str, device_id: str, command: str):
        super().__init__(msg, "execution")
        self.role = role
        self.device_id = device_id
        self.command = command

class Scenario:
    def __init__(self, definition: ScenarioDefinition, device_manager: "DeviceManager"):
        self.definition = definition
        self.device_manager = device_manager
        self.state: Dict[str, Any] = {}
        self.scenario_id = definition.scenario_id

    async def execute_role_action(self, role: str, command: str, **params):
        """Execute an action on a device bound to a role"""
        if role not in self.definition.roles:
            raise ScenarioError(f"Role '{role}' not defined in scenario", "invalid_role", True)
            
        device_id = self.definition.roles[role]
        device = self.device_manager.get_device(device_id)
        
        if not device:
            raise ScenarioError(f"Device '{device_id}' not found for role '{role}'", "missing_device", True)
            
        try:
            await device.execute_command(command, params)
        except Exception as e:
            msg = f"Failed to execute {command} on {device_id}: {str(e)}"
            logger.error(msg)
            raise ScenarioExecutionError(msg, role, device_id, command)

    async def initialize(self):
        """Initialize the scenario by running the startup sequence"""
        await self.execute_startup_sequence()

    async def execute_startup_sequence(self):
        """Execute the startup sequence for this scenario"""
        for step in self.definition.startup_sequence:
            dev = self.device_manager.get_device(step.device)
            if not dev:
                logger.error(f"Device '{step.device}' not found, skipping step")
                continue
                
            try:
                if await self._evaluate_condition(step.condition, dev):
                    logger.info(f"Executing {step.command} on {step.device}")
                    await dev.execute_command(step.command, step.params)
                    if step.delay_after_ms:
                        await asyncio.sleep(step.delay_after_ms / 1000)
            except Exception as e:
                logger.error(f"Error executing startup step for {step.device}: {str(e)}")
                logger.debug(traceback.format_exc())

    async def execute_shutdown_sequence(self, complete: bool = True):
        """Execute the shutdown sequence for this scenario"""
        key = "complete" if complete else "transition"
        for step in self.definition.shutdown_sequence[key]:
            dev = self.device_manager.get_device(step.device)
            if not dev:
                logger.error(f"Device '{step.device}' not found, skipping step")
                continue
                
            try:
                if await self._evaluate_condition(step.condition, dev):
                    logger.info(f"Executing {step.command} on {step.device}")
                    await dev.execute_command(step.command, step.params)
                    if step.delay_after_ms:
                        await asyncio.sleep(step.delay_after_ms / 1000)
            except Exception as e:
                logger.error(f"Error executing shutdown step for {step.device}: {str(e)}")
                logger.debug(traceback.format_exc())

    async def _evaluate_condition(self, condition: Optional[str], device: "BaseDevice") -> bool:
        """
        Evaluate a condition string against a device's state.
        
        Example condition: "device.power != 'on'"
        
        Returns True if:
        - condition is None or empty
        - condition evaluates to True
        """
        if not condition:
            return True
            
        try:
            # Get device state
            device_state = device.get_current_state()
            
            # Create a simplified context for evaluation
            context = {"device": device_state}
            
            # Evaluate the condition
            result = eval(condition, {"__builtins__": {}}, context)
            return bool(result)
        except Exception as e:
            logger.error(f"Error evaluating condition '{condition}': {str(e)}")
            return False

    def validate(self) -> List[str]:
        """
        Validate the scenario definition against system state.
        
        Returns:
            List[str]: List of validation errors, empty if valid
        """
        errors = []
        
        # 1. Device Validation
        for device_id in self.definition.devices:
            if not self.device_manager.get_device(device_id):
                errors.append(f"Device '{device_id}' referenced in scenario does not exist")
        
        for step in self.definition.startup_sequence:
            if not self.device_manager.get_device(step.device):
                errors.append(f"Device '{step.device}' referenced in startup sequence does not exist")
        
        for key in ["complete", "transition"]:
            for step in self.definition.shutdown_sequence[key]:
                if not self.device_manager.get_device(step.device):
                    errors.append(f"Device '{step.device}' referenced in shutdown sequence does not exist")
        
        # 2. Role Validation
        for role, device_id in self.definition.roles.items():
            if not self.device_manager.get_device(device_id):
                errors.append(f"Device '{device_id}' for role '{role}' does not exist")
        
        # 7. Scenario-Room Containment
        if self.definition.room_id:
            room_mgr = getattr(self.device_manager, "room_manager", None)
            if room_mgr:
                for device_id in self.definition.devices:
                    if not room_mgr.contains_device(self.definition.room_id, device_id):
                        errors.append(f"Device '{device_id}' is not in room '{self.definition.room_id}'")
        
        return errors
```

### app/scenario_manager.py

```python
import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Callable, Awaitable, Union, Any

from app.scenario_models import ScenarioDefinition, ScenarioState, DeviceState
from app.scenario import Scenario, ScenarioError, ScenarioExecutionError

logger = logging.getLogger(__name__)

class ScenarioManager:
    def __init__(self, 
                 device_manager: "DeviceManager", 
                 room_manager: "RoomManager",
                 store: "StateStore",
                 scenario_dir: Path):
        self.device_manager = device_manager
        self.room_manager = room_manager
        self.store = store
        self.scenario_dir = scenario_dir
        
        self.scenario_map: Dict[str, Scenario] = {}  # scenario_id -> Scenario
        self.scenario_definitions: Dict[str, ScenarioDefinition] = {}  # scenario_id -> definition
        self.current_scenario: Optional[Scenario] = None
        self.scenario_state: Optional[ScenarioState] = None
    
    async def initialize(self) -> None:
        """Initialize the scenario manager by loading scenarios and restoring state"""
        # Load all scenario definitions
        await self.load_scenarios()
        
        # Try to restore previous state
        await self._restore_state()
    
    async def load_scenarios(self) -> None:
        """Load all scenario definitions from the scenarios directory"""
        self.scenario_map.clear()
        self.scenario_definitions.clear()
        
        if not self.scenario_dir.exists():
            logger.warning(f"Scenarios directory does not exist: {self.scenario_dir}")
            return
            
        for scenario_file in self.scenario_dir.glob("*.json"):
            try:
                scenario_data = json.loads(scenario_file.read_text(encoding="utf-8"))
                definition = ScenarioDefinition.model_validate(scenario_data)
                
                self.scenario_definitions[definition.scenario_id] = definition
                scenario = Scenario(definition, self.device_manager)
                self.scenario_map[definition.scenario_id] = scenario
                
                logger.info(f"Loaded scenario: {definition.scenario_id}")
            except Exception as e:
                logger.error(f"Error loading scenario from {scenario_file}: {str(e)}")
        
        logger.info(f"Loaded {len(self.scenario_map)} scenarios")
    
    async def switch_scenario(self, target_id: str, *, graceful: bool = True):
        """Perform a diff-aware transition between scenarios"""
        # Validate target scenario exists
        if target_id not in self.scenario_map:
            raise ValueError(f"Scenario '{target_id}' not found")
            
        outgoing = self.current_scenario
        incoming = self.scenario_map[target_id]
        
        # If already active, do nothing
        if outgoing and outgoing.scenario_id == incoming.scenario_id:
            logger.info(f"Scenario '{target_id}' is already active")
            return
            
        # Plan the transition steps
        plan: List[Callable[[], Awaitable[None]]] = []
        
        # 1. Remove / update shared devices
        if outgoing:
            logger.info(f"Planning transition from '{outgoing.scenario_id}' to '{incoming.scenario_id}'")
            
            for dev_id, dev_cfg in outgoing.definition.devices.items():
                if dev_id not in incoming.definition.devices:  # removed
                    logger.debug(f"Device {dev_id} will be powered off (not used in target scenario)")
                    dev = self.device_manager.get_device(dev_id)
                    if dev:
                        plan.append(lambda d=dev: d.execute_command("power_off", {}))
                else:  # shared
                    if not graceful:
                        logger.debug(f"Device {dev_id} will be power-cycled (graceful=False)")
                        dev = self.device_manager.get_device(dev_id)
                        if dev:
                            plan.append(lambda d=dev: d.execute_command("power_off", {}))
                    else:
                        # Determine if I/O needs to change
                        # This is simplified - in a real implementation you'd compare device configs
                        incoming_cfg = incoming.definition.devices[dev_id]
                        need_io_change = False
                        
                        if need_io_change:
                            logger.debug(f"Device {dev_id} needs I/O reconfiguration")
                            dev = self.device_manager.get_device(dev_id)
                            if dev:
                                plan.append(lambda d=dev: d.execute_command("set_input", {"input": "new_input"}))
        
        # 2. Add new devices
        for dev_id, dev_cfg in incoming.definition.devices.items():
            if not outgoing or dev_id not in outgoing.definition.devices:
                logger.debug(f"Device {dev_id} will be powered on (new in target scenario)")
                dev = self.device_manager.get_device(dev_id)
                if dev:
                    plan.append(lambda d=dev: d.execute_command("power_on", {}))
        
        # 3. Execute the plan
        for step in plan:
            await step()
            
        # 4. Initialize the incoming scenario
        logger.info(f"Initializing scenario '{incoming.scenario_id}'")
        await incoming.initialize()
        
        # 5. Update state
        self.current_scenario = incoming
        self.scenario_state = ScenarioState(
            scenario_id=incoming.scenario_id,
            devices={
                dev_id: DeviceState.model_validate(
                    self.device_manager.get_device(dev_id).get_current_state()
                )
                for dev_id in incoming.definition.devices
                if self.device_manager.get_device(dev_id)
            }
        )
        
        # 6. Persist state
        await self._persist_state()
        
        logger.info(f"Successfully switched to scenario '{target_id}'")
    
    async def execute_role_action(self, role: str, command: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an action on a device bound to a role in the current scenario"""
        if not self.current_scenario:
            raise ScenarioError("No scenario is currently active", "no_active_scenario", True)
            
        try:
            result = await self.current_scenario.execute_role_action(role, command, **params)
            
            # Update scenario state
            await self._refresh_state()
            
            return result
        except Exception as e:
            logger.error(f"Error executing role action {role}.{command}: {str(e)}")
            raise
    
    async def _refresh_state(self) -> None:
        """Refresh the scenario state from current device states"""
        if not self.current_scenario:
            return
            
        self.scenario_state = ScenarioState(
            scenario_id=self.current_scenario.scenario_id,
            devices={
                dev_id: DeviceState.model_validate(
                    self.device_manager.get_device(dev_id).get_current_state()
                )
                for dev_id in self.current_scenario.definition.devices
                if self.device_manager.get_device(dev_id)
            }
        )
        
        await self._persist_state()
    
    async def _persist_state(self) -> None:
        """Persist current scenario state to store"""
        if self.store and self.scenario_state:
            await self.store.set("scenario:last", self.scenario_state.model_dump())
            logger.debug("Persisted scenario state")
    
    async def _restore_state(self) -> None:
        """Restore scenario state from store"""
        if not self.store:
            return
            
        try:
            state_dict = await self.store.get("scenario:last")
            if state_dict:
                state = ScenarioState.model_validate(state_dict)
                self.scenario_state = state
                
                # Try to restore the active scenario
                if state.scenario_id in self.scenario_map:
                    self.current_scenario = self.scenario_map[state.scenario_id]
                    logger.info(f"Restored active scenario: {state.scenario_id}")
                else:
                    logger.warning(f"Could not restore scenario {state.scenario_id}: not found")
        except Exception as e:
            logger.error(f"Error restoring scenario state: {str(e)}")
```

## REST API Integration

The API endpoints will be added to the existing routers module. Here's an outline of what they will contain:

### app/routers/scenario.py

```python
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, List, Optional

from app.scenario_manager import ScenarioManager
from app.scenario_models import ScenarioDefinition, ScenarioState

router = APIRouter()

# Dependencies for getting manager instances
def get_scenario_manager():
    # Implementation depends on how services are instantiated in your app
    pass

@router.get("/scenario/state")
async def get_scenario_state(
    scenario_mgr: ScenarioManager = Depends(get_scenario_manager)
):
    """Get the current scenario state"""
    if not scenario_mgr.scenario_state:
        raise HTTPException(status_code=404, detail="No active scenario")
    return scenario_mgr.scenario_state.model_dump()

@router.get("/scenario/definition/{id}")
async def get_scenario_definition(
    id: str,
    scenario_mgr: ScenarioManager = Depends(get_scenario_manager)
):
    """Get the definition of a specific scenario"""
    if id not in scenario_mgr.scenario_definitions:
        raise HTTPException(status_code=404, detail=f"Scenario '{id}' not found")
    return scenario_mgr.scenario_definitions[id].model_dump()

@router.post("/scenario/switch")
async def switch_scenario(
    data: Dict[str, Any],
    scenario_mgr: ScenarioManager = Depends(get_scenario_manager)
):
    """Switch to a different scenario"""
    scenario_id = data.get("id")
    graceful = data.get("graceful", True)
    
    if not scenario_id:
        raise HTTPException(status_code=400, detail="Missing 'id' field")
        
    try:
        await scenario_mgr.switch_scenario(scenario_id, graceful=graceful)
        return {"status": "success", "scenario_id": scenario_id}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/scenario/role_action")
async def execute_role_action(
    data: Dict[str, Any],
    scenario_mgr: ScenarioManager = Depends(get_scenario_manager)
):
    """Execute an action on a device bound to a role in the current scenario"""
    role = data.get("role")
    command = data.get("command")
    params = data.get("params", {})
    
    if not role or not command:
        raise HTTPException(status_code=400, detail="Missing 'role' or 'command' fields")
        
    try:
        result = await scenario_mgr.execute_role_action(role, command, params)
        return {"status": "success", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

## Migration Strategy

1. Create app/scenario_models.py with all Pydantic models
2. Implement RoomManager in app/room_manager.py
3. Create a basic rooms.json in config/
4. Implement Scenario class in app/scenario.py
5. Implement ScenarioManager in app/scenario_manager.py
6. Add REST API endpoints
7. Create tests for each component
8. Integrate with main application

## Testing Strategy

The tests will cover:

1. Unit tests for models, validation, and core functionality
2. Integration tests for state persistence and API endpoints
3. Device simulation for scenario transitions

This will ensure the system is robust and behaves according to the specifications. 