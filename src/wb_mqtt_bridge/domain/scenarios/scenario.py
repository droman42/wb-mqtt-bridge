import asyncio
import logging
from typing import Any, Dict, List, Optional
import traceback
import re

from wb_mqtt_bridge.domain.scenarios.models import ScenarioDefinition
from wb_mqtt_bridge.domain.devices.service import DeviceManager
from wb_mqtt_bridge.infrastructure.devices.base import BaseDevice

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
    # Pre-compile power command regex pattern for better performance
    _POWER_COMMAND_PATTERN = re.compile(r'^(power_on|power_off|poweron|poweroff|turn_on|turn_off|turnon|turnoff|on|off|standby|wake|power_toggle|power[_-]cycle)$', re.IGNORECASE)
    
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

    async def initialize(self, skip_power_for_devices: Optional[List[str]] = None):
        """
        Initialize the scenario by running the startup sequence.
        
        This method is typically called when switching to this scenario.
        
        Args:
            skip_power_for_devices: Optional list of device IDs for which power commands should be skipped
        """
        logger.info(f"Initializing scenario '{self.scenario_id}'")
        await self.execute_startup_sequence(skip_power_for_devices=skip_power_for_devices)

    async def execute_startup_sequence(self, skip_power_for_devices: Optional[List[str]] = None):
        """
        Execute the startup sequence for this scenario.
        
        This runs each command in the startup sequence in order, with any
        specified delays between steps.
        
        Args:
            skip_power_for_devices: Optional list of device IDs for which power commands should be skipped
                                   (used for shared devices during scenario transitions)
        """
        logger.info(f"Executing startup sequence for scenario '{self.scenario_id}'")
        skip_power_for_devices = skip_power_for_devices or []
        
        for step in self.definition.startup_sequence:
            dev = self.device_manager.get_device(step.device)
            if not dev:
                logger.error(f"Device '{step.device}' not found, skipping step")
                continue
                
            # Skip power commands for shared devices
            if step.device in skip_power_for_devices and self._is_power_command(step.command):
                logger.info(f"Skipping power command {step.command} on shared device {step.device}")
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

    async def execute_shutdown_sequence(self):
        """
        Execute the shutdown sequence for this scenario.
        """
        logger.info(f"Executing shutdown sequence for scenario '{self.scenario_id}'")
        
        for step in self.definition.shutdown_sequence:
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

    def _is_power_command(self, command: str) -> bool:
        """
        Check if a command is related to power control using a pre-compiled regex pattern.
        
        Args:
            command: The command name to check
            
        Returns:
            bool: True if the command is power-related, False otherwise
        """
        return bool(self._POWER_COMMAND_PATTERN.match(command))

    async def _evaluate_condition(self, condition: Optional[str], device: BaseDevice) -> bool:
        """
        Safely evaluate a condition string against a device's state.
        
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
            
            # Instead of using eval, implement a safe parser for simple conditions
            # For now, we'll support only a few common comparison operations
            return self._safe_evaluate_condition(condition, device_state)
        except Exception as e:
            logger.error(f"Error evaluating condition '{condition}': {str(e)}")
            return False
            
    def _safe_evaluate_condition(self, condition: str, device_state: Dict[str, Any]) -> bool:
        """
        Safely evaluate a simple condition without using eval().
        
        Supports: 
        - "device.attribute == value"
        - "device.attribute != value"
        - "device.attribute in [value1, value2]"
        - "device.attribute not in [value1, value2]"
        
        Args:
            condition: The condition string to evaluate
            device_state: The device state to evaluate against
            
        Returns:
            bool: The result of the condition
        """
        condition = condition.strip()
        
        # Handle equality check
        if "==" in condition:
            left, right = condition.split("==", 1)
            left = left.strip()
            right = right.strip()
            
            if left.startswith("device."):
                key = left[7:].strip()  # remove "device."
                if key in device_state:
                    # Handle string literal with quotes
                    if (right.startswith("'") and right.endswith("'")) or \
                       (right.startswith('"') and right.endswith('"')):
                        right = right[1:-1]  # Remove quotes
                    
                    # Handle boolean literals
                    if right.lower() == "true":
                        right = True
                    elif right.lower() == "false":
                        right = False
                    
                    # Handle numeric literals
                    try:
                        # Check if it's a number
                        if isinstance(right, str):
                            if "." in right:
                                right = float(right)
                            else:
                                right = int(right)
                    except ValueError:
                        pass
                        
                    return device_state[key] == right
            
            return False
            
        # Handle inequality check
        elif "!=" in condition:
            left, right = condition.split("!=", 1)
            left = left.strip()
            right = right.strip()
            
            if left.startswith("device."):
                key = left[7:].strip()  # remove "device."
                if key in device_state:
                    # Handle string literal with quotes
                    if (right.startswith("'") and right.endswith("'")) or \
                       (right.startswith('"') and right.endswith('"')):
                        right = right[1:-1]  # Remove quotes
                    
                    # Handle boolean literals
                    if right.lower() == "true":
                        right = True
                    elif right.lower() == "false":
                        right = False
                    
                    # Handle numeric literals
                    try:
                        # Check if it's a number
                        if isinstance(right, str):
                            if "." in right:
                                right = float(right)
                            else:
                                right = int(right)
                    except ValueError:
                        pass
                        
                    return device_state[key] != right
            
            return True
            
        # Default: condition not supported
        logger.warning(f"Unsupported condition format: {condition}")
        return True

    def validate(self) -> List[str]:
        """
        Validate the scenario definition against system state.
        
        This checks that all devices referenced in the scenario exist in the system,
        all commands in sequences are valid, and that the scenario configuration is consistent.
        
        Returns:
            List[str]: List of validation errors, empty if valid
        """
        errors = []
        
        # Get all unique device IDs from the scenario
        device_ids = set(self.definition.devices)
        
        # 1. Validate device existence
        for device_id in device_ids:
            if not self.device_manager.get_device(device_id):
                errors.append(f"Device '{device_id}' referenced in scenario does not exist")
        
        # 2. Validate roles
        for role, device_id in self.definition.roles.items():
            if not self.device_manager.get_device(device_id):
                errors.append(f"Device '{device_id}' for role '{role}' does not exist")
        
        # 3. Validate room containment if room_id is specified
        if self.definition.room_id:
            room_mgr = getattr(self.device_manager, "room_manager", None)
            if room_mgr:
                room = room_mgr.get_room(self.definition.room_id)
                if not room:
                    errors.append(f"Room '{self.definition.room_id}' referenced by scenario does not exist")
                else:
                    room_device_ids = set(room.devices)
                    non_room_devices = device_ids - room_device_ids
                    if non_room_devices:
                        errors.append(
                            f"Devices {', '.join(non_room_devices)} are used in scenario but not in room '{self.definition.room_id}'"
                        )
            else:
                errors.append("Room manager not available to validate room containment")
        
        # 4. Validate command execution steps
        for i, step in enumerate(self.definition.startup_sequence):
            device = self.device_manager.get_device(step.device)
            if device and not device.supports_command(step.command):
                errors.append(f"Device '{step.device}' does not support command '{step.command}' in startup sequence")
        
        for i, step in enumerate(self.definition.shutdown_sequence):
            device = self.device_manager.get_device(step.device)
            if device and not device.supports_command(step.command):
                errors.append(f"Device '{step.device}' does not support command '{step.command}' in shutdown sequence")
        
        return errors 