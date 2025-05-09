import asyncio
import logging
from typing import Any, Dict, List, Optional, Union
import traceback

from app.scenario_models import ScenarioDefinition, CommandStep
from app.device_manager import DeviceManager
from devices.base_device import BaseDevice

logger = logging.getLogger(__name__)

class ScenarioError(Exception):
    """Base class for scenario-related errors."""
    def __init__(self, msg: str, error_type: str, critical: bool = False):
        super().__init__(msg)
        self.error_type = error_type
        self.critical = critical

class ScenarioExecutionError(ScenarioError):
    """Error that occurs during scenario command execution."""
    def __init__(self, msg: str, role: str, device_id: str, command: str):
        super().__init__(msg, "execution")
        self.role = role
        self.device_id = device_id
        self.command = command

class Scenario:
    """
    Class representing a scenario that can be executed to coordinate multiple devices.
    
    A scenario consists of roles (device assignments), startup and shutdown sequences,
    and provides methods to execute actions on devices by their role.
    """
    def __init__(self, definition: ScenarioDefinition, device_manager: DeviceManager):
        """
        Initialize a scenario with its definition and device manager.
        
        Args:
            definition: The scenario definition containing all required configuration
            device_manager: The device manager for accessing devices
        """
        self.definition = definition
        self.device_manager = device_manager
        self.state: Dict[str, Any] = {}  # Runtime state
        self.scenario_id = definition.scenario_id

    async def execute_role_action(self, role: str, command: str, **params):
        """
        Execute an action on a device bound to a role.
        
        Args:
            role: The role name as defined in the scenario
            command: The command to execute on the device
            **params: Parameters to pass to the command
            
        Returns:
            Any: The result returned by the device command
            
        Raises:
            ScenarioError: If the role is not defined or the device is not found
            ScenarioExecutionError: If there's an error executing the command
        """
        if role not in self.definition.roles:
            raise ScenarioError(f"Role '{role}' not defined in scenario", "invalid_role", True)
            
        device_id = self.definition.roles[role]
        device = self.device_manager.get_device(device_id)
        
        if not device:
            raise ScenarioError(f"Device '{device_id}' not found for role '{role}'", "missing_device", True)
            
        try:
            result = await device.execute_command(command, params)
            return result
        except Exception as e:
            msg = f"Failed to execute {command} on {device_id}: {str(e)}"
            logger.error(msg)
            raise ScenarioExecutionError(msg, role, device_id, command)

    async def initialize(self):
        """
        Initialize the scenario by running the startup sequence.
        
        This method is typically called when switching to this scenario.
        """
        logger.info(f"Initializing scenario '{self.scenario_id}'")
        await self.execute_startup_sequence()

    async def execute_startup_sequence(self):
        """
        Execute the startup sequence for this scenario.
        
        This runs each command in the startup sequence in order, with any
        specified delays between steps.
        """
        logger.info(f"Executing startup sequence for scenario '{self.scenario_id}'")
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
                else:
                    logger.info(f"Skipping {step.command} on {step.device}: condition not met")
            except Exception as e:
                logger.error(f"Error executing startup step for {step.device}: {str(e)}")
                logger.debug(traceback.format_exc())

    async def execute_shutdown_sequence(self, complete: bool = True):
        """
        Execute the shutdown sequence for this scenario.
        
        Args:
            complete: If True, use the 'complete' sequence for full shutdown.
                     If False, use the 'transition' sequence for switching to another scenario.
        """
        key = "complete" if complete else "transition"
        logger.info(f"Executing {key} shutdown sequence for scenario '{self.scenario_id}'")
        
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
                else:
                    logger.info(f"Skipping {step.command} on {step.device}: condition not met")
            except Exception as e:
                logger.error(f"Error executing shutdown step for {step.device}: {str(e)}")
                logger.debug(traceback.format_exc())

    async def _evaluate_condition(self, condition: Optional[str], device: BaseDevice) -> bool:
        """
        Evaluate a condition string against a device's state.
        
        Example condition: "device.power != 'on'"
        
        Args:
            condition: A string expression to evaluate against device state
            device: The device to evaluate against
            
        Returns:
            bool: True if condition is None/empty or evaluates to True, False otherwise
        """
        if not condition:
            return True
            
        try:
            # Get device state
            device_state = device.get_current_state()
            
            # Create a limited context for evaluation
            # This restricts available names to just 'device' for security
            context = {"device": device_state}
            
            # Evaluate the condition with restricted builtins for security
            result = eval(condition, {"__builtins__": {}}, context)
            return bool(result)
        except Exception as e:
            logger.error(f"Error evaluating condition '{condition}': {str(e)}")
            return False

    def validate(self) -> List[str]:
        """
        Validate the scenario definition against system state.
        
        This checks that all devices referenced in the scenario exist in the system
        and that they are properly configured.
        
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
        
        # 3. Scenario-Room Containment
        if self.definition.room_id:
            room_mgr = getattr(self.device_manager, "room_manager", None)
            if room_mgr:
                for device_id in self.definition.devices:
                    if not room_mgr.contains_device(self.definition.room_id, device_id):
                        errors.append(f"Device '{device_id}' is not in room '{self.definition.room_id}'")
        
        return errors 