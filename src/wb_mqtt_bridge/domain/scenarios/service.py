import json
import logging
from pathlib import Path
from typing import Dict, Optional, Any

from wb_mqtt_bridge.domain.scenarios.models import ScenarioDefinition, ScenarioState, DeviceState
from wb_mqtt_bridge.domain.scenarios.scenario import Scenario, ScenarioError
from wb_mqtt_bridge.domain.devices.service import DeviceManager
from wb_mqtt_bridge.domain.rooms.service import RoomManager
from wb_mqtt_bridge.domain.ports import StateRepositoryPort

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
                 state_repository: StateRepositoryPort,
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
        self.state_repository = state_repository
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
        # DEBUG: Log scenario manager initialization
        logger.debug("[SCENARIO_DEBUG] ScenarioManager.initialize() called")
        
        # Load all scenario definitions
        await self.load_scenarios()
        
        # DEBUG: Log loaded scenarios
        logger.debug(f"[SCENARIO_DEBUG] Loaded scenarios: {list(self.scenario_map.keys())}")
        
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
                
                # Create scenario instance
                scenario = Scenario(definition, self.device_manager)
                
                # Validate scenario configuration - this will raise ScenarioConfigurationError if invalid
                scenario.validate_configuration()
                
                # Only add to maps if validation passes
                self.scenario_definitions[definition.scenario_id] = definition
                self.scenario_map[definition.scenario_id] = scenario
                
                logger.info(f"Loaded and validated scenario: {definition.scenario_id}")
            except Exception as e:
                # This will catch both JSON parsing, Pydantic validation, and scenario configuration errors
                logger.error(f"FATAL: Failed to load scenario from {scenario_file}: {str(e)}")
                raise SystemExit(f"Scenario configuration error in {scenario_file.name}: {str(e)}")
        
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
        # DEBUG: Log scenario switch initiation
        logger.debug(f"[SCENARIO_DEBUG] switch_scenario called: target_id={target_id}, graceful={graceful}")
        
        # Validate target scenario exists
        if target_id not in self.scenario_map:
            raise ValueError(f"Scenario '{target_id}' not found")
            
        outgoing = self.current_scenario
        incoming = self.scenario_map[target_id]
        
        # DEBUG: Log scenario transition details
        logger.debug(f"[SCENARIO_DEBUG] Transition: outgoing={outgoing.scenario_id if outgoing else 'None'}, incoming={incoming.scenario_id}")
        
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
            
            # DEBUG: Log device analysis
            logger.debug(f"[SCENARIO_DEBUG] Device analysis: outgoing_devices={outgoing_device_ids}, incoming_devices={incoming_device_ids}, shared_devices={shared_device_ids}")
        
        # 1. Handle shutdown of non-shared devices from outgoing scenario
        if outgoing:
            # DEBUG: Log shutdown phase
            logger.debug(f"[SCENARIO_DEBUG] Starting shutdown phase for outgoing scenario: {outgoing.scenario_id}")
            
            # For non-graceful transitions, we'll run the full shutdown sequence
            if not graceful:
                logger.info(f"Executing full shutdown sequence for scenario '{outgoing.scenario_id}'")
                # DEBUG: Log full shutdown
                logger.debug(f"[SCENARIO_DEBUG] Full shutdown sequence triggered for {outgoing.scenario_id}")
                await outgoing.execute_shutdown_sequence()
            else:
                # For graceful transitions, we need to manually handle each device
                logger.info(f"Executing selective shutdown for scenario '{outgoing.scenario_id}'")
                
                # DEBUG: Log graceful shutdown process
                logger.debug(f"[SCENARIO_DEBUG] Graceful shutdown: processing {len(outgoing.definition.devices)} devices")
                
                # Shutdown devices that aren't shared with the incoming scenario
                for device_id in outgoing.definition.devices:
                    if device_id not in shared_device_ids:
                        dev = self.device_manager.get_device(device_id)
                        if dev:
                            logger.info(f"Shutting down non-shared device: {device_id}")
                            # DEBUG: Log individual device shutdown
                            logger.debug(f"[SCENARIO_DEBUG] Shutting down non-shared device: {device_id}")
                            try:
                                await dev.execute_action("power_off", {}, source="scenario")
                            except Exception as e:
                                logger.error(f"Error shutting down device {device_id}: {str(e)}")
                    else:
                        # DEBUG: Log skipped shutdown
                        logger.debug(f"[SCENARIO_DEBUG] Skipping shutdown for shared device: {device_id}")
        
        # 2. Initialize the incoming scenario, skipping power commands for shared devices
        logger.info(f"Initializing scenario '{incoming.scenario_id}'")
        # DEBUG: Log initialization phase
        logger.debug(f"[SCENARIO_DEBUG] Starting initialization for scenario: {incoming.scenario_id}, skipping power for: {list(shared_device_ids)}")
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
        # DEBUG: Log role action execution
        logger.debug(f"[SCENARIO_DEBUG] execute_role_action called: role={role}, command={command}, params={params}, active_scenario={self.current_scenario.scenario_id if self.current_scenario else 'None'}")
        
        if not self.current_scenario:
            raise ScenarioError("No scenario is currently active", "no_active_scenario", True)
            
        try:
            # DEBUG: Log before executing role action
            logger.debug(f"[SCENARIO_DEBUG] Executing role action on scenario {self.current_scenario.scenario_id}: {role}.{command}")
            
            result = await self.current_scenario.execute_role_action(role, command, **params)
            
            # DEBUG: Log role action result
            logger.debug(f"[SCENARIO_DEBUG] Role action result: {result}")
            
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
                device_states[dev_id] = self._convert_device_state(state)
        
        self.scenario_state = ScenarioState(
            scenario_id=self.current_scenario.scenario_id,
            devices=device_states
        )
    
    async def _persist_state(self) -> None:
        """
        Persist the current scenario state.
        """
        if self.current_scenario:
            await self.state_repository.save("active_scenario", self.current_scenario.scenario_id)
    
    async def _restore_state(self) -> None:
        """
        Restore the previously active scenario, if any.
        """
        # DEBUG: Log state restoration attempt
        logger.debug("[SCENARIO_DEBUG] _restore_state() called")
        
        try:
            scenario_id = await self.state_repository.load("active_scenario")
            
            # DEBUG: Log what was loaded from store
            logger.debug(f"[SCENARIO_DEBUG] Loaded scenario_id from store: {scenario_id}")
            
            if scenario_id and scenario_id in self.scenario_map:
                logger.info(f"Restoring previously active scenario: {scenario_id}")
                # DEBUG: Log restoration attempt
                logger.debug(f"[SCENARIO_DEBUG] Attempting to restore scenario: {scenario_id}")
                try:
                    await self.switch_scenario(scenario_id)
                    # DEBUG: Log successful restoration
                    logger.debug(f"[SCENARIO_DEBUG] Successfully restored scenario: {scenario_id}")
                except Exception as e:
                    logger.error(f"Error restoring scenario {scenario_id}: {str(e)}")
            else:
                # DEBUG: Log why restoration was skipped
                logger.debug(f"[SCENARIO_DEBUG] Restoration skipped: scenario_id={scenario_id}, exists_in_map={scenario_id in self.scenario_map if scenario_id else False}")
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

    async def setup_wb_emulation_for_all_scenarios(self, scenario_wb_adapter, mqtt_client) -> None:
        """
        Set up WB virtual device emulation for all scenarios.
        
        This method creates WB virtual devices for ALL declared scenarios during startup,
        allowing them to be visible in the WB interface regardless of which one is active.
        Only the currently active scenario can receive and execute commands.
        
        Args:
            scenario_wb_adapter: The scenario WB adapter for managing virtual devices
            mqtt_client: MQTT client for subscription management
        """
        if not self.scenario_map:
            logger.info("No scenarios found - skipping scenario WB virtual device setup")
            return
            
        logger.info(f"Setting up WB virtual devices for {len(self.scenario_map)} scenarios")
        scenario_setup_success_count = 0
        
        # Set up WB virtual device for each scenario
        for scenario_id, scenario in self.scenario_map.items():
            try:
                logger.info(f"Setting up WB virtual device for scenario: {scenario_id}")
                success = await scenario_wb_adapter.setup_wb_virtual_device_for_scenario(scenario)
                if success:
                    scenario_setup_success_count += 1
                    logger.debug(f"Scenario WB virtual device setup completed for {scenario_id}")
                else:
                    logger.warning(f"Failed to setup scenario WB virtual device for {scenario_id}")
            except Exception as e:
                logger.error(f"Error setting up scenario WB virtual device for {scenario_id}: {str(e)}")
        
        logger.info(f"Scenario WB virtual device setup completed: {scenario_setup_success_count}/{len(self.scenario_map)} scenarios")
        
        # Set up MQTT subscriptions for all scenarios
        await self._setup_mqtt_subscriptions_for_all_scenarios(scenario_wb_adapter, mqtt_client)
    
    async def _setup_mqtt_subscriptions_for_all_scenarios(self, scenario_wb_adapter, mqtt_client) -> None:
        """
        Set up MQTT subscriptions for all scenarios.
        
        Args:
            scenario_wb_adapter: The scenario WB adapter for getting subscription topics
            mqtt_client: MQTT client for subscription management
        """
        logger.info("Setting up MQTT subscriptions for scenarios")
        scenario_subscription_handlers = {}
        
        for scenario_id, scenario in self.scenario_map.items():
            try:
                topics = scenario_wb_adapter.get_scenario_subscription_topics(scenario)
                logger.debug(f"Scenario {scenario_id} subscription topics: {topics}")
                
                # Create message handler for this scenario
                async def create_scenario_handler(scenario_instance):
                    async def scenario_message_handler(topic: str, payload: str):
                        return await scenario_wb_adapter.handle_scenario_wb_message(
                            topic, payload, scenario_instance
                        )
                    return scenario_message_handler
                
                scenario_handler = await create_scenario_handler(scenario)
                
                # Add topics and handlers to subscription map
                for topic in topics:
                    scenario_subscription_handlers[topic] = scenario_handler
                    
            except Exception as e:
                logger.error(f"Error setting up MQTT subscriptions for scenario {scenario_id}: {str(e)}")
        
        # Subscribe to scenario topics
        if scenario_subscription_handlers:
            try:
                for topic, handler in scenario_subscription_handlers.items():
                    await mqtt_client.subscribe(topic, handler)
                logger.info(f"Subscribed to {len(scenario_subscription_handlers)} scenario MQTT topics")
            except Exception as e:
                logger.error(f"Error subscribing to scenario MQTT topics: {str(e)}")
        else:
            logger.info("No scenario MQTT topics to subscribe to")
    
    def get_scenario_state(self, scenario_id: str) -> ScenarioState:
        """
        Get the state of a specific scenario.
        
        Args:
            scenario_id: ID of the scenario to get state for
            
        Returns:
            ScenarioState: Current state if scenario is active, or basic state with empty devices if inactive
            
        Raises:
            ValueError: If scenario_id doesn't exist
        """
        # Check if scenario exists
        if scenario_id not in self.scenario_map:
            raise ValueError(f"Scenario '{scenario_id}' not found")
        
        # If this is the currently active scenario, return its state
        if (self.current_scenario and 
            self.current_scenario.scenario_id == scenario_id and 
            self.scenario_state):
            return self.scenario_state
        
        # For inactive scenarios, return a basic state without device states
        # since we can't get real-time device states for inactive scenarios
        return ScenarioState(
            scenario_id=scenario_id,
            devices={}  # Empty device states for inactive scenarios
        )
    
    def _convert_device_state(self, state) -> DeviceState:
        """
        Convert a device's Pydantic state model to a standardized DeviceState.
        
        This reuses the safe field access logic from the Scenario class
        to ensure consistent handling across the system.
        
        Args:
            state: Pydantic device state model (e.g., LgTvState, EmotivaXMC2State)
            
        Returns:
            DeviceState: Standardized state representation
        """
        # Use the current scenario's safe field access if available, otherwise fallback
        if self.current_scenario:
            scenario = self.current_scenario
        else:
            # Fallback: create a temporary scenario instance for field access
            # This shouldn't happen often, but provides safety
            from wb_mqtt_bridge.domain.scenarios.models import ScenarioDefinition
            temp_def = ScenarioDefinition(
                scenario_id="temp",
                name="temp",
                roles={},
                devices=[],
                startup_sequence=[],
                shutdown_sequence=[]
            )
            scenario = Scenario(temp_def, self.device_manager)
        
        # Extract and convert power state using scenario's safe field access
        power_value = None
        raw_power = scenario._safe_get_device_field(state, "power")
        if raw_power is not None:
            if isinstance(raw_power, bool):
                power_value = raw_power
            elif isinstance(raw_power, str):
                # Convert string power states to boolean
                power_value = raw_power.lower() in ("on", "true", "1", "powered_on", "active")
        
        # Extract input using safe field access (handles variations automatically)
        input_value = scenario._safe_get_device_field(state, "input")
        
        # Extract output - not all devices have this
        output_value = scenario._safe_get_device_field(state, "output")
        
        # Build extra dict with all other fields, excluding base fields and already mapped ones
        base_fields = {"device_id", "device_name", "last_command", "error"}
        mapped_fields = {"power", "input", "input_source", "video_input", "audio_input", "output"}
        excluded_fields = base_fields | mapped_fields
        
        extra = {}
        if hasattr(state, "model_dump"):
            # Get all fields from the Pydantic model
            all_fields = state.model_dump()
            for field_name, field_value in all_fields.items():
                if field_name not in excluded_fields and field_value is not None:
                    extra[field_name] = field_value
        
        return DeviceState(
            power=power_value,
            input=input_value,
            output=output_value,
            extra=extra
        ) 