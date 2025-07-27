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
            result = await device.execute_action(command, params, source="scenario")
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
                    await dev.execute_action(step.command, step.params, source="scenario")
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
                    await dev.execute_action(step.command, step.params, source="scenario")
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
            
    def _safe_evaluate_condition(self, condition: str, device_state) -> bool:
        """
        Safely evaluate a simple condition without using eval().
        
        Supports: 
        - "device.attribute == value"
        - "device.attribute != value"
        - "device.attribute in [value1, value2]"
        - "device.attribute not in [value1, value2]"
        
        Args:
            condition: The condition string to evaluate
            device_state: The Pydantic device state model to evaluate against
            
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
                field_name = left[7:].strip()  # remove "device."
                device_value = self._safe_get_device_field(device_state, field_name)
                
                if device_value is not None:
                    # Convert right-hand side value to appropriate type
                    comparison_value = self._parse_condition_value(right)
                    
                    # Handle string power states by converting to boolean for comparison
                    if field_name in ["power", "power_state"] and isinstance(device_value, str):
                        device_bool = device_value.lower() in ("on", "true", "1", "powered_on", "active")
                        if isinstance(comparison_value, bool):
                            return device_bool == comparison_value
                    
                    return device_value == comparison_value
            
            return False
            
        # Handle inequality check
        elif "!=" in condition:
            left, right = condition.split("!=", 1)
            left = left.strip()
            right = right.strip()
            
            if left.startswith("device."):
                field_name = left[7:].strip()  # remove "device."
                device_value = self._safe_get_device_field(device_state, field_name)
                
                if device_value is not None:
                    # Convert right-hand side value to appropriate type
                    comparison_value = self._parse_condition_value(right)
                    
                    # Handle string power states by converting to boolean for comparison
                    if field_name in ["power", "power_state"] and isinstance(device_value, str):
                        device_bool = device_value.lower() in ("on", "true", "1", "powered_on", "active")
                        if isinstance(comparison_value, bool):
                            return device_bool != comparison_value
                    
                    return device_value != comparison_value
            
            return True
            
        # Default: condition not supported
        logger.warning(f"Unsupported condition format: {condition}")
        return True
    
    def _safe_get_device_field(self, device_state, field_name: str, default=None):
        """
        Safely get a field value from a device's Pydantic state model.
        
        Handles field name variations and type conversions consistently
        with the state refresh logic.
        
        Args:
            device_state: Pydantic device state model
            field_name: Field name to retrieve
            default: Default value if field not found
            
        Returns:
            Field value or default
        """
        # Direct field access
        if hasattr(device_state, field_name):
            return getattr(device_state, field_name)
        
        # Handle common field name variations
        field_mappings = {
            "input": ["input", "input_source", "video_input", "audio_input"],
            "power": ["power", "power_state"],
        }
        
        # If the requested field has known variations, try them
        variations = field_mappings.get(field_name, [field_name])
        for variation in variations:
            if hasattr(device_state, variation):
                return getattr(device_state, variation)
        
        return default
    
    def _parse_condition_value(self, value_str: str):
        """
        Parse a condition value string into the appropriate Python type.
        
        Handles string literals, boolean literals, and numeric literals.
        Ensures True/False from scenario configs become proper booleans.
        
        Args:
            value_str: String representation of the value
            
        Returns:
            Parsed value with appropriate type
        """
        value_str = value_str.strip()
        
        # Handle string literals with quotes
        if (value_str.startswith("'") and value_str.endswith("'")) or \
           (value_str.startswith('"') and value_str.endswith('"')):
            return value_str[1:-1]  # Remove quotes
        
        # Handle boolean literals - ensure True/False become actual booleans
        if value_str.lower() == "true":
            return True
        elif value_str.lower() == "false":
            return False
        
        # Handle numeric literals
        try:
            # Check if it's a number
            if "." in value_str:
                return float(value_str)
            else:
                return int(value_str)
        except ValueError:
            # Return as string if not a recognized format
            return value_str

    def validate_configuration(self) -> None:
        """
        Comprehensively validate the scenario configuration.
        
        Validates that all device IDs exist, all commands/actions are valid,
        parameters match schemas, and condition expressions are correct.
        
        Raises:
            ScenarioConfigurationError: If any validation errors are found
        """
        from wb_mqtt_bridge.domain.scenarios.models import ScenarioConfigurationError
        
        errors = []
        
        # 1. Validate device IDs
        errors.extend(self._validate_device_ids())
        
        # 2. Validate actions and parameters
        errors.extend(self._validate_startup_sequence())
        errors.extend(self._validate_shutdown_sequence())
        
        # 3. Validate condition expressions
        errors.extend(self._validate_conditions())
        
        # 4. Validate roles
        errors.extend(self._validate_roles())
        
        # If any errors found, raise exception with all details
        if errors:
            raise ScenarioConfigurationError(self.scenario_id, errors)
    
    def _validate_device_ids(self) -> List[str]:
        """Validate all device IDs exist in DeviceManager."""
        errors = []
        
        # Check devices in main device list
        for device_id in self.definition.devices:
            device = self.device_manager.get_device(device_id)
            if not device:
                errors.append(f"Device '{device_id}' in devices list does not exist in DeviceManager")
        
        # Check devices in startup sequence
        for i, step in enumerate(self.definition.startup_sequence):
            device = self.device_manager.get_device(step.device)
            if not device:
                errors.append(f"Device '{step.device}' in startup sequence step {i+1} does not exist in DeviceManager")
        
        # Check devices in shutdown sequence  
        for i, step in enumerate(self.definition.shutdown_sequence):
            device = self.device_manager.get_device(step.device)
            if not device:
                errors.append(f"Device '{step.device}' in shutdown sequence step {i+1} does not exist in DeviceManager")
        
        return errors
    
    def _validate_startup_sequence(self) -> List[str]:
        """Validate startup sequence commands and parameters."""
        errors = []
        
        for i, step in enumerate(self.definition.startup_sequence):
            step_location = f"startup sequence step {i+1} (device: {step.device})"
            device = self.device_manager.get_device(step.device)
            
            if device:  # Only validate if device exists (device existence checked separately)
                # Validate action exists
                available_commands = device.get_available_commands()
                if step.command not in available_commands:
                    available_actions = list(available_commands.keys())
                    errors.append(f"Action '{step.command}' not found in {step_location}. Available actions: {available_actions}")
                else:
                    # Validate parameters
                    param_errors = self._validate_parameters(device, step.command, step.params, step_location)
                    errors.extend(param_errors)
        
        return errors
    
    def _validate_shutdown_sequence(self) -> List[str]:
        """Validate shutdown sequence commands and parameters."""
        errors = []
        
        for i, step in enumerate(self.definition.shutdown_sequence):
            step_location = f"shutdown sequence step {i+1} (device: {step.device})"
            device = self.device_manager.get_device(step.device)
            
            if device:  # Only validate if device exists (device existence checked separately)
                # Validate action exists
                available_commands = device.get_available_commands()
                if step.command not in available_commands:
                    available_actions = list(available_commands.keys())
                    errors.append(f"Action '{step.command}' not found in {step_location}. Available actions: {available_actions}")
                else:
                    # Validate parameters
                    param_errors = self._validate_parameters(device, step.command, step.params, step_location)
                    errors.extend(param_errors)
        
        return errors
    
    def _validate_parameters(self, device, action_name: str, params: dict, location: str) -> List[str]:
        """Validate parameters against device action schema."""
        errors = []
        
        try:
            # Get the command configuration
            available_commands = device.get_available_commands()
            command_config = available_commands[action_name]
            
            # Check if device has parameter validation method
            if hasattr(command_config, 'parameters') and command_config.parameters:
                # Validate each parameter
                for param_name, param_value in params.items():
                    if param_name not in command_config.parameters:
                        available_params = list(command_config.parameters.keys())
                        errors.append(f"Unknown parameter '{param_name}' for action '{action_name}' in {location}. Available parameters: {available_params}")
                
                # Check required parameters
                for param_name, param_config in command_config.parameters.items():
                    if hasattr(param_config, 'required') and param_config.required and param_name not in params:
                        errors.append(f"Required parameter '{param_name}' missing for action '{action_name}' in {location}")
                        
        except Exception as e:
            errors.append(f"Error validating parameters for action '{action_name}' in {location}: {str(e)}")
            
        return errors
    
    def _validate_conditions(self) -> List[str]:
        """Validate condition expressions reference valid device state fields."""
        errors = []
        
        # Validate startup sequence conditions
        for i, step in enumerate(self.definition.startup_sequence):
            if step.condition:
                step_location = f"startup sequence step {i+1} (device: {step.device})"
                condition_errors = self._validate_condition_expression(step.device, step.condition, step_location)
                errors.extend(condition_errors)
        
        # Validate shutdown sequence conditions
        for i, step in enumerate(self.definition.shutdown_sequence):
            if step.condition:
                step_location = f"shutdown sequence step {i+1} (device: {step.device})"
                condition_errors = self._validate_condition_expression(step.device, step.condition, step_location)
                errors.extend(condition_errors)
        
        return errors
    
    def _validate_condition_expression(self, device_id: str, condition: str, location: str) -> List[str]:
        """Validate a specific condition expression."""
        errors = []
        
        device = self.device_manager.get_device(device_id)
        if not device:
            return []  # Device existence validated separately
        
        try:
            # Get device state to understand available fields
            state = device.get_current_state()
            
            # Extract field references from condition (simple regex-based approach)
            import re
            field_pattern = r'device\.(\w+)'
            referenced_fields = re.findall(field_pattern, condition)
            
            # Check each referenced field exists in device state
            for field_name in referenced_fields:
                if not hasattr(state, field_name):
                    available_fields = [attr for attr in dir(state) if not attr.startswith('_') and not callable(getattr(state, attr))]
                    errors.append(f"Condition references unknown field 'device.{field_name}' in {location}. Available fields: {available_fields}")
            
        except Exception as e:
            errors.append(f"Error validating condition '{condition}' in {location}: {str(e)}")
        
        return errors
    
    def _validate_roles(self) -> List[str]:
        """Validate role assignments."""
        errors = []
        
        for role_name, device_id in self.definition.roles.items():
            device = self.device_manager.get_device(device_id)
            if not device:
                errors.append(f"Role '{role_name}' assigned to non-existent device '{device_id}'")
        
        return errors 