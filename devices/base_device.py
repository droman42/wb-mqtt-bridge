from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Type, Callable, TYPE_CHECKING, Awaitable, Coroutine, TypeVar, cast, Union, Generic
import logging
import json
from datetime import datetime
from socket import socket, AF_INET, SOCK_DGRAM, SOL_SOCKET, SO_BROADCAST

from app.schemas import BaseDeviceState, LastCommand, BaseDeviceConfig, BaseCommandConfig, CommandParameterDefinition
from app.mqtt_client import MQTTClient
from app.types import StateT, CommandResult, CommandResponse, ActionHandler

logger = logging.getLogger(__name__)

class BaseDevice(ABC, Generic[StateT]):
    """Base class for all device implementations."""
    
    def __init__(self, config: BaseDeviceConfig, mqtt_client: Optional["MQTTClient"] = None):
        self.config = config
        # Use typed config directly - no fallbacks to dictionary access
        self.device_id = config.device_id
        self.device_name = config.device_name
        self.mqtt_progress_topic = config.mqtt_progress_topic
        
        # Initialize state with basic device identification
        self.state = BaseDeviceState(
            device_id=self.device_id,
            device_name=self.device_name
        )
        self._action_handlers: Dict[str, ActionHandler] = {}  # Cache for action handlers
        self._action_groups: Dict[str, List[Dict[str, Any]]] = {}  # Index of actions by group
        self.mqtt_client = mqtt_client
        
        # Register action handlers
        self._register_handlers()
        
        # Build action group index
        self._build_action_groups_index()
    
    def _register_handlers(self) -> None:
        """
        Register all action handlers for this device.
        
        This method should be overridden by all device subclasses to register
        their action handlers in a standardized way.
        
        Example:
            self._action_handlers.update({
                'power_on': self.handle_power_on,
                'power_off': self.handle_power_off,
            })
        """
        pass  # To be implemented by subclasses
    
    def create_command_result(
        self, 
        success: bool, 
        message: Optional[str] = None, 
        error: Optional[str] = None, 
        **extra_fields
    ) -> CommandResult:
        """
        Create a standardized CommandResult.
        
        Args:
            success: Whether the command was successful
            message: Optional success message
            error: Optional error message (only if success is False)
            **extra_fields: Additional fields to include in the result
            
        Returns:
            CommandResult: A standardized result dictionary
        """
        result: CommandResult = {
            "success": success
        }
        
        if message:
            result["message"] = message
            
        if not success and error:
            result["error"] = error
            
        # Add any additional fields
        for key, value in extra_fields.items():
            result[key] = value
            
        return result
        
    def set_error(self, error_message: str) -> None:
        """
        Set an error message in the device state.
        
        Args:
            error_message: The error message to set
        """
        self.update_state(error=error_message)
        
    def clear_error(self) -> None:
        """Clear any error message from the device state."""
        self.update_state(error=None)
    
    def _build_action_groups_index(self):
        """Build an index of actions organized by group."""
        self._action_groups = {"default": []}  # Default group for actions with no group specified
        
        for cmd_name, cmd in self.get_available_commands().items():
            # Get the group for this command
            group = cmd.group or "default"
            
            # Add group to index if it doesn't exist
            if group not in self._action_groups:
                self._action_groups[group] = []
            
            # Add command to the group
            action_info = {
                "name": cmd_name,
                "description": cmd.description or "",
                # Add other relevant properties from the command config
                # (excluding group and description which we've already handled)
                "params": cmd.params
            }
            self._action_groups[group].append(action_info)
    
    def get_available_groups(self) -> List[str]:
        """Get a list of all available action groups for this device."""
        return list(self._action_groups.keys())
    
    def get_actions_by_group(self, group: str) -> List[Dict[str, Any]]:
        """Get all actions in a specific group."""
        return self._action_groups.get(group, [])
    
    def get_actions(self) -> List[Dict[str, Any]]:
        """Return a list of supported actions for this device."""
        # Get all action handlers registered for this device
        actions = []
        for action_name in self._action_handlers:
            # Skip internal actions (starting with underscore)
            if action_name.startswith('_'):
                continue
                
            # Add action to the list
            actions.append({
                'name': action_name,
                'group': 'default'  # Default group for now
            })
            
        return actions
    
    def get_id(self) -> str:
        """Return the device ID."""
        return self.device_id
    
    def get_name(self) -> str:
        """Return the device name."""
        return self.device_name
    
    @abstractmethod
    async def setup(self) -> bool:
        """Initialize the device. Called when the service starts."""
        pass
    
    @abstractmethod
    async def shutdown(self) -> bool:
        """Cleanup device resources. Called when the service stops."""
        pass
    
    def subscribe_topics(self) -> List[str]:
        """Define the MQTT topics this device should subscribe to."""
        topics = []
        for cmd in self.get_available_commands().values():
            if cmd.topic:
                topics.append(cmd.topic)
        return topics
    
    def _evaluate_condition(self, condition: str, payload: str) -> bool:
        """Evaluate a condition string against the payload."""
        try:
            # Simple equality check
            if condition.startswith("payload == "):
                expected_value = condition.split("==")[1].strip().strip("'\"")
                return payload == expected_value
            
            # Numeric comparison
            if any(op in condition for op in ["<=", ">=", "<", ">"]):
                try:
                    payload_num = float(payload)
                    condition_num = float(condition.split()[-1])
                    if "<=" in condition:
                        return payload_num <= condition_num
                    elif ">=" in condition:
                        return payload_num >= condition_num
                    elif "<" in condition:
                        return payload_num < condition_num
                    elif ">" in condition:
                        return payload_num > condition_num
                except ValueError:
                    return False
            
            # JSON path evaluation
            if condition.startswith("json:"):
                try:
                    payload_data = json.loads(payload)
                    path = condition[5:].strip()
                    # Simple path evaluation (can be enhanced with a proper JSON path library)
                    parts = path.split(".")
                    current = payload_data
                    for part in parts:
                        if isinstance(current, dict):
                            current = current.get(part)
                        else:
                            return False
                    return bool(current)
                except (json.JSONDecodeError, AttributeError):
                    return False
            
            return False
        except Exception as e:
            logger.error(f"Error evaluating condition '{condition}': {str(e)}")
            return False
    
    async def handle_message(self, topic: str, payload: str):
        """Handle incoming MQTT messages for this device."""
        logger.debug(f"Device {self.get_name()} received message on {topic}: {payload}")
        
        # Find matching command configuration based on topic
        matching_commands = []
        for cmd_name, cmd in self.get_available_commands().items():
            if cmd.topic == topic:
                # For each command with a matching topic
                if cmd.condition:
                    # If command has a condition, evaluate it
                    if self._evaluate_condition(cmd.condition, payload):
                        matching_commands.append((cmd_name, cmd))
                else:
                    # Command has no condition, add it to matches
                    matching_commands.append((cmd_name, cmd))
        
        if not matching_commands:
            logger.warning(f"No command configuration found for topic: {topic}")
            return
        
        # Process each matching command configuration found for the topic
        for cmd_name, cmd in matching_commands:
            # Process parameters if defined for this command
            params = {}
            if cmd.params:
                try:
                    # Try to parse payload for parameter processing
                    params = self._process_mqtt_payload(payload, cmd.params)
                except ValueError as e:
                    logger.warning(f"Parameter validation failed for {cmd_name}: {str(e)}")
                    continue  # Skip this command if parameters failed validation
            
            # Execute the command with parameters
            logger.debug(f"Executing command '{cmd_name}' based on topic match.")
            await self._execute_single_action(cmd_name, cmd, params)
    
    def _process_mqtt_payload(self, payload: str, param_defs: List[CommandParameterDefinition]) -> Dict[str, Any]:
        """
        Process an MQTT payload into a parameters dictionary based on parameter definitions.
        
        Args:
            payload: The MQTT payload string
            param_defs: List of parameter definitions
            
        Returns:
            Dict[str, Any]: Processed parameters dictionary
            
        Raises:
            ValueError: If parameter validation fails
        """
        # Default empty parameters
        provided_params = {}
        
        # Try to parse as JSON first
        try:
            json_params = json.loads(payload)
            if isinstance(json_params, dict):
                provided_params = json_params
            else:
                logger.debug(f"Payload parsed as JSON but is not an object: {payload}")
        except json.JSONDecodeError:
            # Handle single parameter commands with non-JSON payload
            if len(param_defs) == 1:
                param_def = param_defs[0]
                param_name = param_def.name
                param_type = param_def.type
                
                # Convert raw payload based on parameter type
                try:
                    if param_type == "integer":
                        provided_params = {param_name: int(payload)}
                    elif param_type == "float":
                        provided_params = {param_name: float(payload)}
                    elif param_type == "boolean":
                        provided_params = {param_name: payload.lower() in ("1", "true", "yes", "on")}
                    else:  # string or any other type
                        provided_params = {param_name: payload}
                except (ValueError, TypeError):
                    logger.error(f"Failed to convert payload '{payload}' to type {param_type}")
                    raise ValueError(f"Failed to convert payload '{payload}' to type {param_type}")
            else:
                logger.error(f"Payload is not valid JSON and command expects multiple parameters: {payload}")
                raise ValueError(f"Payload is not valid JSON and command expects multiple parameters")
        
        # Create and validate full parameter dictionary
        return self._resolve_and_validate_params(param_defs, provided_params)
    
    def _get_action_handler(self, action: str) -> Optional[ActionHandler]:
        """Get the handler function for the specified action."""
        # Convert to lower case for case-insensitive lookup
        action = action.lower()
        
        # DEBUG: Log handler lookup attempt
        logger.debug(f"[{self.device_name}] Looking up handler for action: '{action}'")
        logger.debug(f"[{self.device_name}] Available handlers: {list(self._action_handlers.keys())}")
        
        # Check if we have a handler for this action
        handler = self._action_handlers.get(action)
        if handler:
            logger.debug(f"[{self.device_name}] Found direct handler for '{action}'")
            return handler
            
        # If not found, check if maybe it's in camelCase and we have a handler for snake_case
        if '_' not in action:
            # Convert camelCase to snake_case and try again
            snake_case = ''.join(['_' + c.lower() if c.isupper() else c for c in action]).lstrip('_')
            logger.debug(f"[{self.device_name}] Trying snake_case variant: '{snake_case}'")
            handler = self._action_handlers.get(snake_case)
            if handler:
                logger.debug(f"[{self.device_name}] Found handler for snake_case variant '{snake_case}'")
                return handler
        
        # DEBUG: Check if we have a method named handle_X directly
        method_name = f"handle_{action}"
        if hasattr(self, method_name) and callable(getattr(self, method_name)):
            logger.debug(f"[{self.device_name}] Found method {method_name} but it's not in _action_handlers")
                
        logger.debug(f"[{self.device_name}] No handler found for action '{action}'")
        return None
    
    async def _execute_single_action(
        self, 
        action_name: str, 
        cmd_config: BaseCommandConfig, 
        params: Dict[str, Any] = None
    ) -> Optional[CommandResult]:
        """
        Execute a single action based on its configuration.
        
        Args:
            action_name: The name of the action to execute
            cmd_config: The command configuration
            params: Optional dictionary of parameters (will be validated)
            
        Returns:
            CommandResult: The result from the handler or None if execution failed
        """
        try:
            # Get the action handler method from the instance
            handler = self._get_action_handler(action_name)
            if not handler:
                logger.warning(f"No action handler found for action: {action_name} in device {self.get_name()}")
                return self.create_command_result(
                    success=False, 
                    error=f"No handler found for action: {action_name}"
                )

            # Process parameters if not already provided
            if params is None:
                # Try to resolve parameters from cmd_config
                try:
                    params = self._resolve_and_validate_params(cmd_config.params or [], {})
                except ValueError as e:
                    # Parameter validation failed
                    error_msg = f"Parameter validation failed for {action_name}: {str(e)}"
                    logger.error(error_msg)
                    return self.create_command_result(success=False, error=error_msg)
            
            logger.debug(f"Executing action: {action_name} with handler: {handler}, params: {params}")
            
            # Call the handler with the new parameter-based approach
            result = await handler(cmd_config=cmd_config, params=params)
            
            # Update state with information about the last command executed
            self.update_state(last_command=LastCommand(
                action=action_name,
                source="mqtt" if cmd_config.topic else "api",
                timestamp=datetime.now(),
                params=params
            ))
            
            # Return the result
            return result
                
        except Exception as e:
            error_msg = f"Error executing action {action_name}: {str(e)}"
            logger.error(error_msg)
            return self.create_command_result(success=False, error=error_msg)
    
    def get_current_state(self) -> BaseDeviceState:
        """Get the current state of the device."""
        return self.state
    
    def update_state(self, **updates):
        """
        Update the device state using keyword arguments.
        Each keyword argument will update the corresponding attribute in the state.
        """
        # Create a new state object with updated values
        updated_data = self.state.dict(exclude_unset=True)
        updated_data.update(updates)
        self.state = BaseDeviceState(**updated_data)
        
        logger.debug(f"Updated state for {self.device_name}: {updates}")
    
    async def execute_action(
        self, 
        action: str, 
        params: Optional[Dict[str, Any]] = None
    ) -> CommandResponse:
        """Execute an action identified by action name."""
        try:
            # Find the command configuration for this action
            cmd = None
            for cmd_name, command_config in self.get_available_commands().items():
                if cmd_name == action:
                    cmd = command_config
                    break
            
            if not cmd:
                error_msg = f"Action {action} not found in device configuration"
                return CommandResponse(
                    success=False,
                    device_id=self.device_id,
                    action=action,
                    state=self.state.dict(),
                    error=error_msg
                )
            
            # Validate parameters
            validated_params = {}
            if cmd.params:
                try:
                    # Validate and process parameters
                    validated_params = self._resolve_and_validate_params(cmd.params, params or {})
                except ValueError as e:
                    # Re-raise with more specific message
                    error_msg = f"Parameter validation failed for action '{action}': {str(e)}"
                    return CommandResponse(
                        success=False,
                        device_id=self.device_id,
                        action=action,
                        state=self.state.dict(),
                        error=error_msg
                    )
            elif params:
                # No parameters defined in config but params were provided
                validated_params = params
            
            # Execute the action with validated parameters
            result = await self._execute_single_action(action, cmd, validated_params)
            
            # Create the response based on the result
            success = result.get("success", True) if result else True
            response = CommandResponse(
                success=success,
                device_id=self.device_id,
                action=action,
                state=self.state.dict()
            )
            
            # Add error if present in result
            if not success and result and "error" in result:
                response["error"] = result["error"]
                
            # Add mqtt_command if present in result
            if result and "mqtt_command" in result:
                response["mqtt_command"] = result["mqtt_command"]
            
            if success:
                await self.publish_progress(f"Action {action} executed successfully")
                
            return response
                
        except Exception as e:
            error_msg = f"Error executing action {action} for device {self.device_id}: {str(e)}"
            logger.error(error_msg)
            return CommandResponse(
                success=False,
                device_id=self.device_id,
                action=action,
                state=self.state.dict(),
                error=error_msg
            )
    
    async def send_wol_packet(self, mac_address: str, ip_address: str = '255.255.255.255', port: int = 9) -> bool:
        """
        Send a Wake-on-LAN magic packet to the specified MAC address.
        
        Args:
            mac_address: MAC address of the target device (format: xx:xx:xx:xx:xx:xx)
            ip_address: Broadcast IP address (default: 255.255.255.255)
            port: UDP port to send the packet to (default: 9)
            
        Returns:
            bool: True if the packet was sent successfully, False otherwise
        """
        try:
            if not mac_address:
                logger.error("No MAC address provided for Wake-on-LAN")
                return False
                
            # Convert MAC address to bytes
            mac_bytes = bytes.fromhex(mac_address.replace(':', ''))
            
            # Create the magic packet (6 bytes of 0xFF followed by MAC address repeated 16 times)
            magic_packet = b'\xff' * 6 + mac_bytes * 16
            
            # Send the packet
            sock = socket(AF_INET, SOCK_DGRAM)
            sock.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)
            sock.sendto(magic_packet, (ip_address, port))
            sock.close()
            
            logger.info(f"Sent WOL packet to {mac_address}")
            await self.publish_progress(f"WOL packet sent to {mac_address}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send WOL packet: {str(e)}")
            return False
    
    def get_available_commands(self) -> Dict[str, BaseCommandConfig]:
        """Return the list of available commands for this device."""
        return self.config.commands
    
    async def publish_progress(self, message: str) -> bool:
        """
        Publish a progress message to the configured MQTT progress topic.
        
        Args:
            message: The message to publish
            
        Returns:
            bool: True if the message was published successfully, False otherwise
        """
        try:
            if not self.mqtt_client:
                logger.warning(f"Cannot publish progress: MQTT client not available for device {self.device_id}")
                return False
                
            if not self.mqtt_progress_topic:
                logger.warning(f"No MQTT progress topic configured for device {self.device_id}")
                return False

            if not message:
                logger.warning(f"Empty progress message not published for device {self.device_id}")
                return False
                
            await self.mqtt_client.publish(self.mqtt_progress_topic, f"{self.device_name}: {message}")
            logger.debug(f"Published progress message to {self.mqtt_progress_topic}: {message}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to publish progress message: {str(e)}")
            return False
    
    def _resolve_and_validate_params(self, param_defs: List[CommandParameterDefinition], 
                                   provided_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resolves and validates command parameters against their definitions.
        
        Args:
            param_defs: List of parameter definitions
            provided_params: The parameters provided for this command execution
            
        Returns:
            Dict[str, Any]: The validated and resolved parameter dictionary
            
        Raises:
            ValueError: If required parameters are missing or validation fails
        """
        # Start with an empty result
        result = {}
        
        # If no parameters defined, return provided params as is
        if not param_defs:
            return provided_params
            
        # Process each parameter definition
        for param_def in param_defs:
            param_name = param_def.name
            param_type = param_def.type
            required = param_def.required
            default = param_def.default
            min_val = param_def.min
            max_val = param_def.max
            
            # Check if parameter is provided
            if param_name in provided_params:
                # Parameter is provided, validate it
                value = provided_params[param_name]
                
                # Type validation
                try:
                    if param_type == "integer":
                        value = int(value)
                    elif param_type == "float":
                        value = float(value)
                    elif param_type == "boolean":
                        if isinstance(value, str):
                            value = value.lower() in ("1", "true", "yes", "on")
                        else:
                            value = bool(value)
                    elif param_type == "range":
                        # Convert to float for range validation
                        value = float(value)
                        
                        # Validate range
                        if min_val is not None and value < min_val:
                            raise ValueError(f"Parameter '{param_name}' value {value} is below minimum {min_val}")
                        if max_val is not None and value > max_val:
                            raise ValueError(f"Parameter '{param_name}' value {value} is above maximum {max_val}")
                            
                        # Convert back to int if both min and max are integers
                        if (isinstance(min_val, int) or min_val is None) and (isinstance(max_val, int) or max_val is None):
                            value = int(value)
                    # String type doesn't need conversion
                except (ValueError, TypeError) as e:
                    raise ValueError(f"Parameter '{param_name}' has invalid type. Expected {param_type}: {str(e)}")
                    
                # Store validated value
                result[param_name] = value
                
            # Parameter not provided, handle based on whether it's required
            elif required:
                # Required parameter is missing
                raise ValueError(f"Required parameter '{param_name}' is missing")
            else:
                # Optional parameter, use default if available
                if default is not None:
                    result[param_name] = default
                    
        return result