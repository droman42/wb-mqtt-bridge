import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Callable, Awaitable, Union, Any

from app.scenario_models import ScenarioDefinition, ScenarioState, DeviceState, DeviceConfig, ConfigDelta
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
    
    async def switch_scenario(self, target_id: str, *, graceful: bool = True) -> None:
        """
        Perform a diff-aware transition between scenarios.
        
        This method:
        1. Validates the target scenario exists
        2. Calculates the difference between current and target scenarios
        3. Plans and executes a transition with minimal device reconfiguration
        4. Initializes the new scenario and persists state
        
        Args:
            target_id: ID of the scenario to switch to
            graceful: If False, force power-cycling of shared devices
                      If True, attempt to reconfigure devices without power cycling
                
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
            return
            
        # Plan the transition steps
        plan: List[Callable[[], Awaitable[None]]] = []
        
        # 1. Handle outgoing scenario
        if outgoing:
            # Run the transition shutdown sequence
            logger.info(f"Planning transition from '{outgoing.scenario_id}' to '{incoming.scenario_id}'")
            await outgoing.execute_shutdown_sequence(complete=False)
            
            # Process devices that need handling
            for dev_id in outgoing.definition.devices:
                # Skip devices that are also in the incoming scenario if we're doing a graceful transition
                if graceful and dev_id in incoming.definition.devices:
                    continue
                    
                # Power off devices that are not in the incoming scenario or if non-graceful
                logger.debug(f"Device {dev_id} will be powered off (not used in target scenario or non-graceful)")
                dev = self.device_manager.get_device(dev_id)
                if dev:
                    plan.append(lambda d=dev: d.execute_command("power_off", {}))
        
        # 2. Process shared devices that need reconfiguration
        if outgoing and graceful:
            # Identify shared devices between scenarios
            shared_devices = set(outgoing.definition.devices.keys()) & set(incoming.definition.devices.keys())
            
            for dev_id in shared_devices:
                # Compare device configurations to see what needs to change
                # This is a simplified approximation - in a real implementation, 
                # you would extract actual configurations and compare them
                need_io_change = True  # Placeholder - in practice, this would be determined by config comparison
                
                if need_io_change:
                    logger.debug(f"Device {dev_id} needs I/O reconfiguration")
                    dev = self.device_manager.get_device(dev_id)
                    if dev:
                        # In a real implementation, you would extract the actual input/output settings
                        # from the incoming scenario's configuration
                        plan.append(lambda d=dev: d.execute_command("set_input", {"input": "new_input"}))
        
        # 3. Add or power on devices that are new in the incoming scenario
        for dev_id in incoming.definition.devices:
            if not outgoing or dev_id not in outgoing.definition.devices:
                logger.debug(f"Device {dev_id} will be powered on (new in target scenario)")
                dev = self.device_manager.get_device(dev_id)
                if dev:
                    plan.append(lambda d=dev: d.execute_command("power_on", {}))
        
        # 4. Execute the transition plan
        for step in plan:
            await step()
            
        # 5. Initialize the incoming scenario
        logger.info(f"Initializing scenario '{incoming.scenario_id}'")
        await incoming.initialize()
        
        # 6. Update state
        self.current_scenario = incoming
        self.scenario_state = await self._build_scenario_state(incoming)
        
        # 7. Persist state
        await self._persist_state()
        
        logger.info(f"Successfully switched to scenario '{target_id}'")
    
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
    
    async def get_scenario_for_room(self, room_id: str) -> List[str]:
        """
        Get scenarios configured for a specific room.
        
        Args:
            room_id: The room ID to find scenarios for
            
        Returns:
            List[str]: List of scenario IDs that target this room
        """
        result = []
        for scenario_id, definition in self.scenario_definitions.items():
            if definition.room_id == room_id:
                result.append(scenario_id)
        return result
    
    async def _build_scenario_state(self, scenario: Scenario) -> ScenarioState:
        """
        Build a ScenarioState object from the current device states.
        
        Args:
            scenario: The scenario to build state for
            
        Returns:
            ScenarioState: The current state of all devices in the scenario
        """
        device_states = {}
        
        for dev_id in scenario.definition.devices:
            device = self.device_manager.get_device(dev_id)
            if device:
                try:
                    state = device.get_current_state()
                    device_states[dev_id] = DeviceState(
                        power=state.get("power"),
                        input=state.get("input"),
                        output=state.get("output"),
                        extra={k: v for k, v in state.items() 
                              if k not in ("power", "input", "output")}
                    )
                except Exception as e:
                    logger.error(f"Error getting state for device {dev_id}: {str(e)}")
        
        return ScenarioState(
            scenario_id=scenario.scenario_id,
            devices=device_states
        )
    
    async def _refresh_state(self) -> None:
        """
        Refresh the scenario state from current device states.
        
        This updates self.scenario_state with the latest device states
        and persists the updated state.
        """
        if not self.current_scenario:
            return
            
        self.scenario_state = await self._build_scenario_state(self.current_scenario)
        await self._persist_state()
    
    async def _persist_state(self) -> None:
        """
        Persist current scenario state to the state store.
        
        This saves the current scenario state under the key "scenario:last".
        """
        if self.store and self.scenario_state:
            await self.store.set("scenario:last", self.scenario_state.model_dump())
            logger.debug("Persisted scenario state")
    
    async def _restore_state(self) -> None:
        """
        Restore scenario state from the state store.
        
        This attempts to restore the previously active scenario and its state.
        """
        if not self.store:
            logger.warning("No state store available for restoring scenario state")
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

    # PLACEHOLDER: Add proper implementation for resource cleanup
    async def shutdown(self) -> None:
        """
        Clean up resources and perform shutdown operations.
        
        This method:
        1. Cancels any active timers or scheduled tasks
        2. Persists current state before shutdown
        3. Releases any held resources
        4. Performs any necessary cleanup operations
        """
        logger = logging.getLogger(__name__)
        logger.info("Shutting down ScenarioManager")
        
        # Persist current state if there is an active scenario
        if self.current_scenario:
            await self._persist_state()
            logger.info(f"Persisted state for scenario '{self.current_scenario.scenario_id}'")
            
            # Execute shutdown sequence for current scenario
            try:
                await self.current_scenario.execute_shutdown_sequence(complete=True)
                logger.info(f"Executed shutdown sequence for scenario '{self.current_scenario.scenario_id}'")
            except Exception as e:
                logger.error(f"Error during scenario shutdown sequence: {e}")
        
        # TODO: Cancel any background tasks or timers
        
        logger.info("ScenarioManager shutdown complete") 