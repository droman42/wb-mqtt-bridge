"""Scenario WB Adapter - Infrastructure adapter for scenario WB virtual device functionality."""

import logging
from typing import Dict, Any, List

from wb_mqtt_bridge.domain.scenarios.service import ScenarioManager
from wb_mqtt_bridge.domain.scenarios.scenario import ScenarioError
from wb_mqtt_bridge.infrastructure.wb_device.service import WBVirtualDeviceService
from .models import ScenarioWBConfig

logger = logging.getLogger(__name__)


class ScenarioWBAdapter:
    """Infrastructure adapter for Scenario WB virtual device functionality using shared service.
    
    This adapter creates virtual WB device configurations from scenario definitions
    without modifying scenario config files. It uses the shared WBVirtualDeviceService
    for all WB operations and provides command execution delegation.
    """
    
    def __init__(
        self, 
        scenario_manager: ScenarioManager, 
        wb_service: WBVirtualDeviceService, 
        device_manager
    ):
        """Initialize scenario WB adapter.
        
        Args:
            scenario_manager: Domain scenario manager
            wb_service: Shared WB virtual device service
            device_manager: Device manager for role command extraction
        """
        self.scenario_manager = scenario_manager
        self.wb_service = wb_service
        self.device_manager = device_manager
        self._active_scenario_configs: Dict[str, ScenarioWBConfig] = {}  # Track virtual configs

    async def setup_wb_virtual_device_for_scenario(self, scenario) -> bool:
        """Set up scenario WB device using shared service with Pydantic virtual config.
        
        Args:
            scenario: Active scenario instance
            
        Returns:
            True if setup successful, False otherwise
        """
        try:
            scenario_id = scenario.definition.scenario_id
            
            # Generate strongly-typed virtual config (preserves scenario config files unchanged)
            virtual_config = ScenarioWBConfig.from_scenario(
                scenario.definition, 
                self.device_manager
            )
            
            # Store virtual config for later reference
            self._active_scenario_configs[scenario_id] = virtual_config
            
            # Use shared service with Pydantic model (maintains type safety)
            success = await self.wb_service.setup_wb_device_from_config(
                config=virtual_config,  # Pydantic model, not Dict
                command_executor=self._execute_scenario_command,
                driver_name="wb_mqtt_bridge_scenario", 
                device_type="scenario",
                entity_id=scenario.definition.scenario_id,      # Virtual entity abstraction
                entity_name=scenario.definition.name           # Virtual entity abstraction
            )
            
            if success:
                logger.info(f"Successfully set up WB virtual device for scenario {scenario_id}")
            else:
                logger.error(f"Failed to set up WB virtual device for scenario {scenario_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error setting up WB virtual device for scenario: {str(e)}")
            return False

    async def cleanup_scenario_wb_device(self, scenario) -> bool:
        """Clean up scenario WB device using shared service.
        
        Args:
            scenario: Scenario instance to clean up
            
        Returns:
            True if cleanup successful, False otherwise
        """
        try:
            scenario_id = scenario.definition.scenario_id
            
            # Clean up using shared service (use scenario config device_id for tracking)
            success = await self.wb_service.cleanup_wb_device(scenario_id)
            
            # Remove virtual config from tracking
            if scenario_id in self._active_scenario_configs:
                del self._active_scenario_configs[scenario_id]
            
            if success:
                logger.info(f"Successfully cleaned up WB virtual device for scenario {scenario_id}")
            else:
                logger.warning(f"Failed to clean up WB virtual device for scenario {scenario_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error cleaning up WB virtual device for scenario: {str(e)}")
            return False

    def get_scenario_subscription_topics(self, scenario) -> List[str]:
        """Get MQTT subscription topics using shared service.
        
        Args:
            scenario: Scenario instance
            
        Returns:
            List of MQTT topics to subscribe to
        """
        try:
            scenario_id = scenario.definition.scenario_id
            
            # Get virtual config
            if scenario_id in self._active_scenario_configs:
                virtual_config = self._active_scenario_configs[scenario_id]
            else:
                # Generate on-the-fly if not cached
                virtual_config = ScenarioWBConfig.from_scenario(
                    scenario.definition, 
                    self.device_manager
                )
            
            # Use shared service with virtual entity ID
            return self.wb_service.get_subscription_topics_from_config(
                virtual_config, 
                entity_id=scenario.definition.scenario_id
            )
            
        except Exception as e:
            logger.error(f"Error getting subscription topics for scenario: {str(e)}")
            return []

    async def handle_scenario_wb_message(self, topic: str, payload: str, scenario):
        """Handle MQTT messages using shared service routing.
        
        Args:
            topic: MQTT topic
            payload: MQTT payload
            scenario: Scenario instance
            
        Returns:
            Result of command execution
        """
        try:
            # Use shared service for message handling (pass virtual WB device ID)
            return await self.wb_service.handle_wb_message(
                topic, 
                payload, 
                scenario.definition.scenario_id  # Virtual WB device ID
            )
            
        except Exception as e:
            logger.error(f"Error handling scenario WB message: {str(e)}")
            return False
        
    async def _execute_scenario_command(self, control_name: str, payload: str, params: Dict[str, Any]):
        """Command executor callback for scenario WB service.
        
        This method routes scenario WB commands to the appropriate scenario methods.
        Follows the same pattern as device commands - direct calls to entity methods.
        
        Args:
            control_name: WB control name (e.g., "startup", "shutdown", "playback_play")
            payload: Raw MQTT payload
            params: Processed parameters dict
            
        Returns:
            Result of command execution
        """
        try:
            logger.debug(f"Executing scenario command: {control_name} with params: {params}")
            
            # Check if we have an active scenario
            if not self.scenario_manager.current_scenario:
                raise ScenarioError("No scenario is currently active", "no_active_scenario", True)
            
            current_scenario = self.scenario_manager.current_scenario
            
            if control_name == "startup":
                # Execute startup sequence directly on scenario (supercritical per requirements)
                logger.info(f"Executing startup sequence for scenario {current_scenario.scenario_id}")
                return await current_scenario.execute_startup_sequence()
                
            elif control_name == "shutdown":
                # Execute shutdown sequence directly on scenario (supercritical per requirements)
                logger.info(f"Executing shutdown sequence for scenario {current_scenario.scenario_id}")  
                return await current_scenario.execute_shutdown_sequence()
                
            elif "_" in control_name:
                # Role-based command delegation (goes through manager for role→device resolution)
                role, command = control_name.split("_", 1)
                logger.info(f"Delegating to role '{role}': {command}")
                return await self.scenario_manager.execute_role_action(role, command, params)
                
            else:
                raise ValueError(f"Unknown scenario command: {control_name}")
                
        except Exception as e:
            logger.error(f"Error executing scenario command {control_name}: {str(e)}")
            raise

    def get_active_virtual_configs(self) -> Dict[str, ScenarioWBConfig]:
        """Get currently active virtual configurations.
        
        Returns:
            Dict of scenario_id to ScenarioWBConfig
        """
        return self._active_scenario_configs.copy()

    def is_scenario_wb_device_active(self, scenario_id: str) -> bool:
        """Check if scenario WB device is currently active.
        
        Args:
            scenario_id: Scenario ID to check
            
        Returns:
            True if active, False otherwise
        """
        return scenario_id in self._active_scenario_configs 