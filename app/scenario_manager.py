import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Callable, Awaitable, Union, Any, Set

from app.scenario_models import ScenarioDefinition, ScenarioState, DeviceState
from app.scenario import Scenario, ScenarioError, ScenarioExecutionError
from app.device_manager import DeviceManager
from app.room_manager import RoomManager
from app.state_store import StateStore

logger = logging.getLogger(__name__)

class ScenarioManager:
    """
    Manager for scenario definitions, transitions, and state persistence.
    
    Responsibilities:
    - Load scenario definitions from JSON files
    - Track the currently active scenario
    - Manage transitions between scenarios
    - Persist and restore scenario state
    - Execute role-based actions in the current scenario
    """
    
    def __init__(self, 
                 device_manager: DeviceManager, 
                 room_manager: RoomManager,
                 store: StateStore,
                 scenario_dir: Path):
        """
        Initialize the scenario manager.
        
        Args:
            device_manager: Manager for accessing devices
            room_manager: Manager for room definitions
            store: State persistence store
            scenario_dir: Directory containing scenario JSON files
        """
        self.device_manager = device_manager
        self.room_manager = room_manager
        self.store = store
        self.scenario_dir = scenario_dir
        
        self.scenario_map: Dict[str, Scenario] = {}  # scenario_id -> Scenario
        self.scenario_definitions: Dict[str, ScenarioDefinition] = {}  # scenario_id -> definition
        self.current_scenario: Optional[Scenario] = None
        self.scenario_state: Optional[ScenarioState] = None
    
    async def initialize(self) -> None:
        """
        Initialize the scenario manager by loading scenarios and restoring state.
        
        This method:
        1. Loads all scenario definitions from JSON files
        2. Creates Scenario instances for each definition
        3. Attempts to restore the previously active scenario
        """
        # Load all scenario definitions
        await self.load_scenarios()
        
        # Try to restore previous state
        await self._restore_state()
        
        logger.info("Scenario manager initialized")
    
    async def load_scenarios(self) -> None:
        """
        Load all scenario definitions from the scenarios directory.
        
        This reads all JSON files in the scenario_dir, validates them as
        ScenarioDefinition objects, and creates Scenario instances.
        """
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
    
    async def switch_scenario(self, target_id: str, *, graceful: bool = True) -> Dict[str, Any]:
        """
        Perform a smart transition between scenarios with efficient device handling.
        
        This method:
        1. Identifies devices shared between the outgoing and incoming scenarios
        2. For non-shared devices, runs the shutdown sequence
        3. For shared devices, skips shutdown commands entirely
        4. For the incoming scenario, skips power-on commands for shared devices
        5. Handles all device state transitions with minimal interruption
        
        Args:
            target_id: ID of the scenario to switch to
            graceful: If True (default), attempt minimal interruption to shared devices
                      If False, force full shutdown and restart of all devices
                
        Raises:
            ValueError: If the target scenario doesn't exist
        """
        # Validate target scenario exists
        if target_id not in self.scenario_map:
            raise ValueError(f"Scenario '{target_id}' not found")
            
        outgoing = self.current_scenario
        incoming = self.scenario_map[target_id]
        
        # If already active, do nothing
        if outgoing and outgoing.scenario_id == incoming.scenario_id:
            logger.info(f"Scenario '{target_id}' is already active")
            return {
                "success": True,
                "shared_devices": [],
                "power_cycled_devices": []
            }
        
        logger.info(f"Switching from '{outgoing.scenario_id if outgoing else 'None'}' to '{incoming.scenario_id}'")
        
        # Identify shared devices between scenarios
        shared_device_ids = set()
        if outgoing and graceful:
            outgoing_device_ids = set(outgoing.definition.devices)
            incoming_device_ids = set(incoming.definition.devices)
            shared_device_ids = outgoing_device_ids.intersection(incoming_device_ids)
            logger.info(f"Identified {len(shared_device_ids)} shared devices that will maintain power")
        
        # 1. Handle shutdown of non-shared devices from outgoing scenario
        if outgoing:
            # For non-graceful transitions, we'll run the full shutdown sequence
            if not graceful:
                logger.info(f"Executing full shutdown sequence for scenario '{outgoing.scenario_id}'")
                await outgoing.execute_shutdown_sequence()
            else:
                # For graceful transitions, we need to manually handle each device
                logger.info(f"Executing selective shutdown for scenario '{outgoing.scenario_id}'")
                
                # Shutdown devices that aren't shared with the incoming scenario
                for device_id in outgoing.definition.devices:
                    if device_id not in shared_device_ids:
                        dev = self.device_manager.get_device(device_id)
                        if dev:
                            logger.info(f"Shutting down non-shared device: {device_id}")
                            try:
                                await dev.execute_command("power_off", {})
                            except Exception as e:
                                logger.error(f"Error shutting down device {device_id}: {str(e)}")
        
        # 2. Initialize the incoming scenario, skipping power commands for shared devices
        logger.info(f"Initializing scenario '{incoming.scenario_id}'")
        await incoming.execute_startup_sequence(skip_power_for_devices=list(shared_device_ids))
        
        # 3. Update manager state
        self.current_scenario = incoming
        await self._refresh_state()
        
        # 4. Persist state
        await self._persist_state()
        
        logger.info(f"Successfully switched to scenario '{target_id}'")
        
        # Return summary of what was done
        return {
            "success": True,
            "shared_devices": list(shared_device_ids),
            "power_cycled_devices": list(set(incoming.definition.devices) - shared_device_ids)
        }
    
    async def execute_role_action(self, role: str, command: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an action on a device bound to a role in the current scenario.
        
        Args:
            role: The role name as defined in the current scenario
            command: The command to execute
            params: Parameters to pass to the command
            
        Returns:
            Dict[str, Any]: The result returned by the device command
            
        Raises:
            ScenarioError: If no scenario is active or the role is invalid
        """
        if not self.current_scenario:
            raise ScenarioError("No scenario is currently active", "no_active_scenario", True)
            
        try:
            result = await self.current_scenario.execute_role_action(role, command, **params)
            
            # Update scenario state after action
            await self._refresh_state()
            
            return result
        except Exception as e:
            logger.error(f"Error executing role action {role}.{command}: {str(e)}")
            raise
    
    async def _refresh_state(self) -> None:
        """
        Refresh the scenario state based on current device states.
        """
        if not self.current_scenario:
            self.scenario_state = None
            return
        
        # Create a new state object
        device_states = {}
        
        for dev_id in self.current_scenario.definition.devices:
            device = self.device_manager.get_device(dev_id)
            if device:
                state = device.get_current_state()
                device_states[dev_id] = DeviceState(
                    power=state.get("power"),
                    input=state.get("input"),
                    output=state.get("output"),
                    extra={k: v for k, v in state.items() 
                          if k not in ("power", "input", "output")}
                )
        
        self.scenario_state = ScenarioState(
            scenario_id=self.current_scenario.scenario_id,
            devices=device_states
        )
    
    async def _persist_state(self) -> None:
        """
        Persist the current scenario state.
        """
        if self.current_scenario:
            await self.store.save("active_scenario", self.current_scenario.scenario_id)
    
    async def _restore_state(self) -> None:
        """
        Restore the previously active scenario, if any.
        """
        try:
            scenario_id = await self.store.load("active_scenario")
            if scenario_id and scenario_id in self.scenario_map:
                logger.info(f"Restoring previously active scenario: {scenario_id}")
                try:
                    await self.switch_scenario(scenario_id)
                except Exception as e:
                    logger.error(f"Error restoring scenario {scenario_id}: {str(e)}")
        except Exception as e:
            logger.error(f"Error loading active scenario from store: {str(e)}")
    
    async def shutdown(self) -> None:
        """
        Gracefully shut down the current scenario, if any.
        """
        if self.current_scenario:
            logger.info(f"Shutting down scenario '{self.current_scenario.scenario_id}'")
            try:
                await self.current_scenario.execute_shutdown_sequence()
            except Exception as e:
                logger.error(f"Error shutting down scenario: {str(e)}")
            finally:
                self.current_scenario = None
                self.scenario_state = None 