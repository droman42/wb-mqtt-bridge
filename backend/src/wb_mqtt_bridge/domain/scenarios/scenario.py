import logging
from typing import List

from wb_mqtt_bridge.domain.scenarios.models import ScenarioDefinition
from wb_mqtt_bridge.domain.devices.service import DeviceManager

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

    A scenario is a thin ``source``/``display``/``audio`` selection plus role bindings;
    activation and teardown are derived from the topology by the reconciler
    (see ``domain/scenarios/reconciler.py``). This class carries the definition and
    provides role-based action execution for the active scenario.
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

    @staticmethod
    def _safe_get_device_field(device_state, field_name: str, default=None):
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

    def validate_configuration(self) -> None:
        """
        Validate the scenario configuration.

        Validates that the scenario is a thin selection (has a ``source``), that all
        referenced device IDs exist, and that role bindings resolve.

        Raises:
            ScenarioConfigurationError: If any validation errors are found
        """
        from wb_mqtt_bridge.domain.scenarios.models import ScenarioConfigurationError

        errors = []

        # 1. Thin selection is mandatory — without a source the reconciler has nothing
        #    to resolve and the scenario could never be activated.
        if not self.definition.source:
            errors.append(
                "Scenario must declare a thin 'source' selection (the imperative "
                "startup/shutdown-sequence format was removed)"
            )

        # 2. Validate device IDs
        errors.extend(self._validate_device_ids())

        # 3. Validate roles
        errors.extend(self._validate_roles())

        # If any errors found, raise exception with all details
        if errors:
            raise ScenarioConfigurationError(self.scenario_id, errors)

    def _validate_device_ids(self) -> List[str]:
        """Validate all device IDs in the explicit devices list exist in DeviceManager."""
        errors = []

        for device_id in self.definition.devices:
            device = self.device_manager.get_device(device_id)
            if not device:
                errors.append(f"Device '{device_id}' in devices list does not exist in DeviceManager")

        return errors

    def _validate_roles(self) -> List[str]:
        """Validate role assignments."""
        errors = []

        for role_name, device_id in self.definition.roles.items():
            device = self.device_manager.get_device(device_id)
            if not device:
                errors.append(f"Role '{role_name}' assigned to non-existent device '{device_id}'")

        return errors
