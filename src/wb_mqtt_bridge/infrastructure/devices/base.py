from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, cast, Union, Generic, Tuple
import logging
import json
import re
from datetime import datetime
from enum import Enum
from socket import socket, AF_INET, SOCK_DGRAM, SOL_SOCKET, SO_BROADCAST
import psutil

from wb_mqtt_bridge.domain.devices.models import BaseDeviceState, LastCommand
from wb_mqtt_bridge.infrastructure.config.models import BaseDeviceConfig, BaseCommandConfig, CommandParameterDefinition
from wb_mqtt_bridge.infrastructure.mqtt.client import MQTTClient
from wb_mqtt_bridge.infrastructure.wb_device.service import WBVirtualDeviceService
from wb_mqtt_bridge.utils.types import StateT, CommandResult, CommandResponse, ActionHandler
from wb_mqtt_bridge.presentation.api.sse_manager import sse_manager, SSEChannel
from wb_mqtt_bridge.domain.ports import DeviceBusPort

logger = logging.getLogger(__name__)

class BaseDevice(DeviceBusPort, ABC, Generic[StateT]):
    """Base class for all device implementations."""
    
    def __init__(self, config: BaseDeviceConfig, mqtt_client: Optional["MQTTClient"] = None, wb_service: Optional[WBVirtualDeviceService] = None):
        self.config = config
        # Use typed config directly - no fallbacks to dictionary access
        self.device_id = config.device_id
        self.device_name = config.device_name
        
        # Initialize state with basic device identification
        self.state = BaseDeviceState(
            device_id=self.device_id,
            device_name=self.device_name
        )
        self._action_handlers: Dict[str, ActionHandler] = {}  # Cache for action handlers
        self._action_groups: Dict[str, List[Dict[str, Any]]] = {}  # Index of actions by group
        self.mqtt_client = mqtt_client
        self.wb_service = wb_service  # Injected WB virtual device service
        self._state_change_callback = None  # Callback for state changes
        
        # Register action handlers
        self._register_handlers()
        
        # Build action group index
        self._build_action_groups_index()
        
        # Auto-register handlers based on naming convention
        self._auto_register_handlers()
    
    def should_publish_wb_virtual_device(self) -> bool:
        """Check if WB virtual device emulation should be enabled for this device."""
        # Check if WB service is available
        if not self.wb_service:
            return False
            
        # Check if MQTT client is available (service needs it)
        if not self.mqtt_client:
            return False
            
        # Check configuration flag (defaults to True)
        return getattr(self.config, 'enable_wb_emulation', True)
    
    async def _setup_wb_virtual_device(self):
        """Set up Wirenboard virtual device emulation using WB service."""
        if not self.wb_service:
            logger.warning(f"Cannot setup WB virtual device for {self.device_id}: no WB service")
            return
        
        if not self.mqtt_client:
            logger.warning(f"Cannot setup WB virtual device for {self.device_id}: no MQTT client")
            return
        
        # Use WB service to set up virtual device
        success = await self.wb_service.setup_wb_device_from_config(
            config=self.config,
            command_executor=self._execute_wb_command_from_service,
            driver_name="wb_mqtt_bridge",
            device_type=self.config.device_class.lower() if hasattr(self.config, 'device_class') else None
        )
        
        if success:
            logger.info(f"WB virtual device emulation enabled for {self.device_id}")
        else:
            logger.error(f"Failed to setup WB virtual device for {self.device_id}")
    
    async def _execute_wb_command_from_service(self, control_name: str, payload: str, params: Dict[str, Any]):
        """Command executor callback for WB service - routes to BaseDevice execution logic."""
        try:
            # Find corresponding command configuration
            available_commands = self.get_available_commands()
            if control_name not in available_commands:
                logger.warning(f"No command configuration found for WB control: {control_name}")
                return
            
            cmd_config = available_commands[control_name]
            
            # Check if command has a handler
            if not cmd_config.action or cmd_config.action not in self._action_handlers:
                logger.warning(f"No handler found for WB control: {control_name} (action: {cmd_config.action})")
                return
            
            # Execute the handler using the action name
            await self._execute_single_action(cmd_config.action, cmd_config, params, source="wb_command")
            
        except Exception as e:
            logger.error(f"Error executing WB command {control_name} for device {self.device_id}: {str(e)}")
            raise
    
    # WB device metadata and control publishing is now handled by WBVirtualDeviceService
    
    # WB control metadata generation is now handled by WBVirtualDeviceService
        """Get initial state value for WB control from command configuration."""
        
        # If no parameters, it's a pushbutton (always 0)
        if not hasattr(cmd_config, 'params') or not cmd_config.params:
            return "0"
        
        first_param = cmd_config.params[0]
        param_type = getattr(first_param, 'type', 'string')
        
        # Use default value if specified
        if hasattr(first_param, 'default') and first_param.default is not None:
            if param_type == "boolean":
                return "1" if first_param.default else "0"
            else:
                return str(first_param.default)
        
        # Type-based defaults
        if param_type == "boolean":
            return "0"  # False
        elif param_type in ["range", "integer", "float"]:
            # Use minimum value or 0
            if hasattr(first_param, 'min') and first_param.min is not None:
                return str(first_param.min)
            else:
                return "0"
        elif param_type == "string":
            return ""  # Empty string
        else:
            return "0"  # Fallback

    # Legacy WB control metadata generation is now handled by WBVirtualDeviceService
    
    # WB control title generation and ordering are now handled by WBVirtualDeviceService
    
    # WB control state generation is now handled by WBVirtualDeviceService
    
    # WB Last Will Testament setup is now handled by WBVirtualDeviceService
    
    async def cleanup_wb_device_state(self):
        """
        Clean up WB device state on shutdown using WB service.
        """
        if not self.should_publish_wb_virtual_device():
            return
            
        if not self.wb_service:
            logger.warning(f"Cannot cleanup WB device for {self.device_id}: no WB service")
            return
        
        try:
            success = await self.wb_service.cleanup_wb_device(self.device_id)
            if success:
                logger.debug(f"Cleaned up WB device state for {self.device_id}")
            else:
                logger.warning(f"Failed to cleanup WB device state for {self.device_id}")
                
        except Exception as e:
            logger.warning(f"Error cleaning up WB device state for {self.device_id}: {str(e)}")
    
    async def setup_wb_emulation_if_enabled(self):
        """
        Helper method for subclasses to call during their setup() method.
        Sets up WB virtual device emulation if enabled.
        """
        if self.should_publish_wb_virtual_device():
            await self._setup_wb_virtual_device()
    
    # WB control state refresh is now handled by WBVirtualDeviceService
    
    async def handle_mqtt_reconnection(self):
        """
        Handle MQTT reconnection using WB service.
        This ensures retained messages are restored after connection loss.
        """
        if not self.should_publish_wb_virtual_device():
            return
            
        if not self.wb_service:
            logger.warning(f"Cannot handle MQTT reconnection for WB device {self.device_id}: no WB service")
            return
            
        try:
            success = await self.wb_service.handle_mqtt_reconnection(self.device_id)
            if success:
                logger.info(f"Successfully restored WB device state for {self.device_id}")
            else:
                logger.error(f"Failed to handle MQTT reconnection for WB device {self.device_id}")
            
        except Exception as e:
            logger.error(f"Error handling MQTT reconnection for {self.device_id}: {str(e)}")

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
        
        # For WB-enabled devices, use the WB service to get subscription topics
        if self.should_publish_wb_virtual_device() and self.wb_service:
            topics = self.wb_service.get_subscription_topics_from_config(self.config)
        else:
            # For non-WB devices, use legacy topic subscription for backward compatibility
            for cmd_name, cmd in self.get_available_commands().items():
                # Use the new get_command_topic method for backward compatibility
                topic = self.get_command_topic(cmd_name, cmd)
                if topic:
                    topics.append(topic)
        
        return topics
    
    def get_command_topic(self, handler_name: str, cmd_config: BaseCommandConfig) -> str:
        """Get auto-generated topic for command following WB conventions."""
        return f"/devices/{self.device_id}/controls/{handler_name}"
    
    async def handle_message(self, topic: str, payload: str):
        """Handle incoming MQTT messages for this device."""
        logger.debug(f"Device {self.get_name()} received message on {topic}: {payload}")
        
        # DEBUG: Enhanced logging for all device messages
        logger.debug(f"[BASE_DEVICE_DEBUG] handle_message for {self.device_id}: topic={topic}, payload='{payload}'")
        
        # Check if this is a WB command topic and handle it via service
        if self.should_publish_wb_virtual_device() and self.wb_service:
            try:
                handled = await self.wb_service.handle_wb_message(topic, payload, self.device_id)
                if handled:
                    return
            except Exception as e:
                logger.error(f"Error handling WB message via service for {self.device_id}: {str(e)}")
                # Continue to legacy handling as fallback
        
        # Find matching command configuration based on topic
        matching_commands = []
        for cmd_name, cmd in self.get_available_commands().items():
            # Use get_command_topic for consistent topic resolution
            expected_topic = self.get_command_topic(cmd_name, cmd)
            if expected_topic == topic:
                # Add command to matches when topic matches
                matching_commands.append((cmd_name, cmd))
        
        if not matching_commands:
            logger.warning(f"No command configuration found for topic: {topic}")
            return
        
        # DEBUG: Log matching commands for all devices
        logger.debug(f"[BASE_DEVICE_DEBUG] Found {len(matching_commands)} matching commands for {self.device_id}: {[cmd[0] for cmd in matching_commands]}")
        
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
            # DEBUG: Log command execution for all devices
            logger.debug(f"[BASE_DEVICE_DEBUG] Executing command '{cmd_name}' on {self.device_id} with params: {params}")
            
            logger.debug(f"Executing command '{cmd_name}' based on topic match.")
            await self._execute_single_action(cmd_name, cmd, params)
    
    async def send(self, command: str, params: Dict[str, Any]) -> Any:
        """Send a command to the device via MQTT (default implementation).
        
        This provides the default MQTT-based implementation for device communication.
        Devices using other protocols (HTTP, TCP, etc.) should override this method.
        
        Args:
            command: The command identifier
            params: Command parameters
            
        Returns:
            Command result or response
        """
        if not self.mqtt_client:
            logger.error(f"No MQTT client available for device {self.device_id}")
            return None
            
        # Find the command configuration
        available_commands = self.get_available_commands()
        if command not in available_commands:
            logger.error(f"Unknown command '{command}' for device {self.device_id}")
            return None
            
        cmd_config = available_commands[command]
        
        # Get the topic for this command
        topic = self.get_command_topic(command, cmd_config)
        if not topic:
            logger.error(f"No topic configured for command '{command}' on device {self.device_id}")
            return None
        
        # Prepare payload - for MQTT devices, this is typically the parameter value
        payload = "1"  # Default payload
        if params:
            # For simple commands with one parameter, use that value
            if len(params) == 1:
                payload = str(list(params.values())[0])
            else:
                # For complex commands, send JSON
                payload = json.dumps(params)
        
        try:
            # Publish the command via MQTT
            await self.mqtt_client.publish(topic, payload, qos=1)
            logger.debug(f"Sent MQTT command '{command}' to {topic}: {payload}")
            return {"success": True, "topic": topic, "payload": payload}
        except Exception as e:
            logger.error(f"Failed to send MQTT command '{command}' to device {self.device_id}: {e}")
            return {"success": False, "error": str(e)}
    
    # WB command topic handling is now handled by WBVirtualDeviceService
    
    # WB state synchronization is now handled by WBVirtualDeviceService
    
    # WB control mappings are now handled by WBVirtualDeviceService
    
    # WB value conversion is now handled by WBVirtualDeviceService

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
                # Handle simple JSON values (numbers, strings, booleans) when only one parameter is defined
                if len(param_defs) == 1:
                    param_def = param_defs[0]
                    param_name = param_def.name
                    param_type = param_def.type
                    
                    # Process the simple JSON value based on parameter type
                    try:
                        if param_type == "integer":
                            provided_params = {param_name: int(json_params)}
                        elif param_type == "float":
                            provided_params = {param_name: float(json_params)}
                        elif param_type == "boolean":
                            # Convert numeric values to boolean
                            if isinstance(json_params, (int, float)):
                                provided_params = {param_name: bool(json_params)}
                            elif isinstance(json_params, str):
                                provided_params = {param_name: json_params.lower() in ("1", "true", "yes", "on")}
                            else:
                                provided_params = {param_name: bool(json_params)}
                        else:  # string or any other type
                            provided_params = {param_name: str(json_params)}
                    except (ValueError, TypeError):
                        logger.error(f"Failed to convert JSON value '{json_params}' to type {param_type}")
                        raise ValueError(f"Failed to convert JSON value '{json_params}' to type {param_type}")
                else:
                    logger.error(f"Payload is a simple JSON value but command expects multiple parameters: {payload}")
                    raise ValueError("Simple value cannot be used with multiple parameters")
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
                raise ValueError("Payload is not valid JSON and command expects multiple parameters")
        
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
        if handler := self._action_handlers.get(action):
            logger.debug(f"[{self.device_name}] Found direct handler for '{action}'")
            return handler
            
        # If no direct handler, look for handle_<action> method
        name = f"handle_{action}"
        if hasattr(self, name) and callable(getattr(self, name)):
            logger.debug(f"[{self.device_name}] Using implicit handler {name}")
            return getattr(self, name)
            
        # If not found, check if maybe it's in camelCase and we have a handler for snake_case
        if '_' not in action:
            # Convert camelCase to snake_case and try again
            snake_case = ''.join(['_' + c.lower() if c.isupper() else c for c in action]).lstrip('_')
            logger.debug(f"[{self.device_name}] Trying snake_case variant: '{snake_case}'")
            if handler := self._action_handlers.get(snake_case):
                logger.debug(f"[{self.device_name}] Found handler for snake_case variant '{snake_case}'")
                return handler
            
            # Try the implicit handler with snake_case
            name = f"handle_{snake_case}"
            if hasattr(self, name) and callable(getattr(self, name)):
                logger.debug(f"[{self.device_name}] Using implicit handler {name} for camelCase action")
                return getattr(self, name)
        
        logger.debug(f"[{self.device_name}] No handler found for action '{action}'")
        return None
    
    def _auto_register_handlers(self) -> None:
        """
        Automatically register handler methods based on naming convention.
        
        This method discovers all methods named handle_<action> and registers them 
        as action handlers for <action>. It will not override existing handlers.
        """
        for attr in dir(self):
            if attr.startswith("handle_"):
                action = attr.removeprefix("handle_").lower()
                # Only register if not already registered
                self._action_handlers.setdefault(action, getattr(self, attr))
                logger.debug(f"[{self.device_name}] Auto-registered handler for action '{action}'")
    
    async def _execute_single_action(
        self, 
        action_name: str, 
        cmd_config: BaseCommandConfig, 
        params: Dict[str, Any] = None,
        source: str = "unknown"
    ) -> Optional[CommandResult]:
        """
        Execute a single action with the provided configuration and parameters.
        
        Args:
            action_name: Name of the action to execute
            cmd_config: Command configuration
            params: Optional parameters for the action
            source: Source of the command call (e.g., "api", "mqtt", "system")
            
        Returns:
            Optional[CommandResult]: Result of the action execution
        """
        if params is None:
            params = {}
            
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
            
            # DEBUG: Enhanced logging for all device action execution
            logger.debug(f"[BASE_DEVICE_DEBUG] Calling handler for {action_name} on {self.device_id}: handler={handler.__name__ if hasattr(handler, '__name__') else str(handler)}")
            
            # Call the handler with the new parameter-based approach
            result = await handler(cmd_config=cmd_config, params=params)
            
            # DEBUG: Log result for all devices
            logger.debug(f"[BASE_DEVICE_DEBUG] Handler result for {action_name} on {self.device_id}: {result}")
            
            # Update state with information about the last command executed
            # Use the provided source parameter instead of flawed topic-based logic
            self.update_state(last_command=LastCommand(
                action=action_name,
                source=source,
                timestamp=datetime.now(),
                params=params
            ))
            
            # Return the result
            return result
                
        except Exception as e:
            error_msg = f"Error executing action {action_name}: {str(e)}"
            logger.error(error_msg)
            return self.create_command_result(success=False, error=error_msg)
    
    def get_current_state(self) -> StateT:
        """Return a copy of the current device state."""
        return cast(StateT, self.state)
    
    def _validate_state_updates(self, updates: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate that state updates contain only JSON serializable values.
        
        This validation helps catch serialization issues early, before they cause 
        problems when attempting to persist state.
        
        Args:
            updates: Dictionary of state updates to validate
            
        Returns:
            Tuple[bool, List[str]]: (is_valid, error_messages)
            Where is_valid is True if all updates are serializable
        """
        errors = []
        
        # Check each field being updated
        for field_name, field_value in updates.items():
            try:
                # Handle simple primitives that are always serializable
                if field_value is None or isinstance(field_value, (str, int, float, bool)):
                    continue
                    
                # Handle special types we know how to serialize
                if hasattr(field_value, 'model_dump') or hasattr(field_value, 'dict'):
                    continue
                    
                if isinstance(field_value, (datetime, Enum)):
                    continue
                    
                # For other types, test JSON serialization
                try:
                    json.dumps({field_name: field_value})
                except (TypeError, OverflowError) as e:
                    errors.append(f"Field '{field_name}' with type '{type(field_value).__name__}' is not JSON serializable: {str(e)}")
            except Exception as e:
                errors.append(f"Error validating field '{field_name}': {str(e)}")
                
        return len(errors) == 0, errors
    
    def update_state(self, **updates):
        """
        Update the device state using keyword arguments.
        Each keyword argument will update the corresponding attribute in the state.
        
        This method now includes validation to detect non-serializable fields early.
        Only triggers state change notification if the state actually changes.
        """
        # Skip empty updates
        if not updates:
            return
        
        # Validate updates for serializability
        is_valid, errors = self._validate_state_updates(updates)
        if not is_valid:
            # Log warnings for non-serializable fields
            for error in errors:
                logger.warning(f"Device {self.device_id}: {error}")
            
            # Log a summary warning
            logger.warning(f"Device {self.device_id}: Updating state with {len(errors)} potentially non-serializable fields")
        
        # Store current state for comparison
        previous_state = self.state.dict(exclude_unset=True)
        
        # Create a new state object with updated values
        updated_data = self.state.dict(exclude_unset=True)
        updated_data.update(updates)
        
        # Check if there are actual changes
        has_changes = False
        for key, value in updates.items():
            if key not in previous_state or previous_state[key] != value:
                has_changes = True
                break
        
        # If no changes, exit early
        if not has_changes:
            # logger.debug(f"No actual state changes for {self.device_name}")
            return
        
        # Preserve the concrete state type when updating
        state_cls = type(self.state)  # Get the actual class of the current state
        self.state = state_cls(**updated_data)  # Create a new instance of the same class
        
        # Validate complete state after update
        if hasattr(self.state, 'validate_serializable'):
            is_state_valid, state_errors = self.state.validate_serializable()
            if not is_state_valid:
                logger.warning(f"Device {self.device_id}: State contains non-serializable fields after update: {', '.join(state_errors)}")
        
        logger.debug(f"Updated state for {self.device_name}: {updates}")
        
        # Notify about state change only if there were actual changes
        self._notify_state_change()
    
    def _notify_state_change(self):
        """Notify the registered callback about state changes and emit SSE event."""
        # Notify persistence callback
        if self._state_change_callback:
            try:
                # DEBUG: Log all state change notifications
                logger.debug(f"[BASE_DEVICE_DEBUG] _notify_state_change called for {self.device_id}")
                
                self._state_change_callback(self.device_id)
            except Exception as e:
                logger.error(f"Error notifying state change for device {self.device_id}: {str(e)}")
        
        # Emit state change via SSE
        try:
            import asyncio
            
            # Get current state for broadcast
            current_state = self.get_current_state()
            
            # Prepare state event data
            state_event_data = {
                "device_id": self.device_id,
                "device_name": self.device_name,
                "state": current_state.dict() if hasattr(current_state, 'dict') else current_state,
                "timestamp": datetime.now().isoformat()
            }
            
            # Create task to broadcast state change
            asyncio.create_task(
                sse_manager.broadcast(
                    channel=SSEChannel.DEVICES,
                    event_type="state_change",
                    data=state_event_data
                )
            )
            
            logger.debug(f"State change SSE event queued for device {self.device_id}")
            
        except Exception as e:
            logger.error(f"Error emitting state change SSE event for device {self.device_id}: {str(e)}")
                
    def register_state_change_callback(self, callback):
        """Register a callback to be notified when state changes."""
        self._state_change_callback = callback
    
    async def execute_action(
        self, 
        action: str, 
        params: Optional[Dict[str, Any]] = None,
        source: str = "unknown"
    ) -> CommandResponse[StateT]:
        """Execute an action identified by action name.
        
        Args:
            action: The action name to execute
            params: Optional parameters for the action
            source: Source of the command call (e.g., "api", "mqtt", "system")
            
        Returns:
            CommandResponse: Response containing success status, device state, and any additional data
        """
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
                    state=self.state,  # Now properly typed
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
                        state=self.state,  # Now properly typed
                        error=error_msg
                    )
            elif params:
                # No parameters defined in config but params were provided
                validated_params = params
            
            # Execute the action with validated parameters and source
            result = await self._execute_single_action(action, cmd, validated_params, source)
            
            # Create the response based on the result
            success = result.get("success", True) if result else True
            response: CommandResponse[StateT] = CommandResponse(
                success=success,
                device_id=self.device_id,
                action=action,
                state=self.state  # Now properly typed
            )
            
            # Add error if present in result
            if not success and result and "error" in result:
                response["error"] = result["error"]
                
            # Add mqtt_command if present in result
            if result and "mqtt_command" in result:
                response["mqtt_command"] = result["mqtt_command"]
                
            # Add data if present in result
            if result and "data" in result:
                response["data"] = result["data"]
            
            if success:
                await self.emit_progress(f"Action {action} executed successfully", "action_success")
                
            return response
                
        except Exception as e:
            error_msg = f"Error executing action {action} for device {self.device_id}: {str(e)}"
            logger.error(error_msg)
            return CommandResponse(
                success=False,
                device_id=self.device_id,
                action=action,
                state=self.state,  # Now properly typed
                error=error_msg
            )
    
    def get_broadcast_ip(self) -> str:
        """
        Auto-detect the broadcast IP address for the local network.
        
        Prefers non-virtual, active network interfaces and filters out loopback.
        Detects Docker bridge networks and warns about their limitations.
        Falls back to global broadcast (255.255.255.255) if detection fails.
        
        Returns:
            str: The broadcast IP address to use for WOL packets
        """
        try:
            # Get network interface statistics to identify active interfaces
            net_stats = psutil.net_if_stats()
            
            # Collect potential broadcast addresses with priority scoring
            candidates = []
            docker_bridge_detected = False
            
            for iface_name, iface_addrs in psutil.net_if_addrs().items():
                # Skip loopback interfaces
                if iface_name.startswith(('lo', 'Loopback')):
                    continue
                
                # Check if interface is up and running
                iface_stat = net_stats.get(iface_name)
                if not iface_stat or not iface_stat.isup:
                    continue
                
                for addr in iface_addrs:
                    # Only process IPv4 addresses with broadcast capability
                    if addr.family == AF_INET and addr.broadcast:
                        # Calculate priority score (higher is better)
                        priority = 0
                        ip_addr = addr.address
                        
                        # Detect Docker bridge networks (common ranges: 172.17.x.x, 172.18.x.x, etc.)
                        is_docker_bridge = (
                            iface_name.startswith('eth') and 
                            ip_addr.startswith('172.') and 
                            any(ip_addr.startswith(f'172.{subnet}.') for subnet in range(16, 32))
                        )
                        
                        if is_docker_bridge:
                            docker_bridge_detected = True
                            # Significantly penalize Docker bridge networks
                            priority -= 20
                            logger.warning(f"Detected Docker bridge network on {iface_name} ({ip_addr}). "
                                         f"Broadcast to {addr.broadcast} may not reach devices outside the container. "
                                         f"Consider using host networking or specifying the host's broadcast IP.")
                        
                        # Prefer ethernet/wifi interfaces (but not if they're Docker bridges)
                        if any(keyword in iface_name.lower() for keyword in ['eth', 'en', 'wlan', 'wifi']) and not is_docker_bridge:
                            priority += 10
                        
                        # Penalize virtual/tunnel interfaces
                        if any(keyword in iface_name.lower() for keyword in ['tun', 'tap', 'vpn', 'vbox', 'vmware', 'docker']):
                            priority -= 5
                        
                        # Prefer interfaces with typical private network ranges (but not Docker bridges)
                        if ip_addr.startswith(('192.168.', '10.')) or (ip_addr.startswith('172.') and not is_docker_bridge):
                            priority += 5
                        
                        candidates.append((priority, addr.broadcast, iface_name, ip_addr))
            
            if candidates:
                # Sort by priority (highest first) and return the best broadcast address
                candidates.sort(key=lambda x: x[0], reverse=True)
                best_candidate = candidates[0]
                
                # Additional warning if we're using a Docker bridge despite detection
                if docker_bridge_detected and best_candidate[3].startswith('172.') and any(best_candidate[3].startswith(f'172.{subnet}.') for subnet in range(16, 32)):
                    logger.warning(f"Using Docker bridge broadcast IP {best_candidate[1]} - WOL packets may not reach external devices. "
                                 f"For WOL to work with external devices, use --network=host or provide the host's broadcast IP explicitly.")
                
                logger.debug(f"Auto-detected broadcast IP: {best_candidate[1]} from interface {best_candidate[2]} ({best_candidate[3]})")
                return best_candidate[1]
            
            # If no suitable interface found, log warning and fall back to global broadcast
            logger.warning("Could not detect a suitable broadcast IP address, using global broadcast 255.255.255.255")
            return "255.255.255.255"
            
        except Exception as e:
            logger.warning(f"Failed to auto-detect broadcast IP: {str(e)}, falling back to 255.255.255.255")
            return "255.255.255.255"

    async def send_wol_packet(self, mac_address: str, ip_address: str, port: int = 9) -> bool:
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
            await self.emit_progress(f"WOL packet sent to {mac_address}", "action_progress")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send WOL packet: {str(e)}")
            return False
    
    def get_available_commands(self) -> Dict[str, BaseCommandConfig]:
        """Return the list of available commands for this device."""
        return self.config.commands
    
    async def emit_progress(self, message: str, event_type: str = "progress") -> bool:
        """
        Emit a progress message via Server-Sent Events.
        
        Args:
            message: The message to emit
            event_type: The type of event (default: "progress")
            
        Returns:
            bool: True if the message was emitted successfully, False otherwise
        """
        try:
            if not message:
                logger.warning(f"Empty progress message not emitted for device {self.device_id}")
                return False
                
            # Prepare event data
            event_data = {
                "device_id": self.device_id,
                "device_name": self.device_name,
                "message": message,
                "timestamp": datetime.now().isoformat()
            }
            
            # Emit to devices channel via SSE
            await sse_manager.broadcast(
                channel=SSEChannel.DEVICES,
                event_type=event_type,
                data=event_data
            )
            
            logger.debug(f"Emitted {event_type} event for device {self.device_id}: {message}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to emit progress message: {str(e)}")
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
    
    def create_mqtt_command_result(
        self, 
        success: bool, 
        mqtt_topic: str, 
        mqtt_payload: Any, 
        message: Optional[str] = None, 
        error: Optional[str] = None, 
        **extra_fields
    ) -> CommandResult:
        """
        Create a standardized CommandResult with MQTT command.
        
        Args:
            success: Whether the command was successful
            mqtt_topic: The MQTT topic to publish to
            mqtt_payload: The MQTT payload to publish (will be converted to string if not already)
            message: Optional success message
            error: Optional error message (only if success is False)
            **extra_fields: Additional fields to include in the result
            
        Returns:
            CommandResult: A standardized result dictionary with MQTT command
        """
        # Convert the payload to JSON string if it's a dict or list
        if isinstance(mqtt_payload, (dict, list)):
            mqtt_payload_str = json.dumps(mqtt_payload)
        else:
            mqtt_payload_str = str(mqtt_payload)
            
        # Create the MQTT command structure
        mqtt_command = {
            "topic": mqtt_topic,
            "payload": mqtt_payload_str
        }
        
        # Create the command result with the MQTT command
        result = self.create_command_result(
            success=success, 
            message=message, 
            error=error, 
            mqtt_command=mqtt_command,
            **extra_fields
        )
        
        return result
    
    def _validate_wb_controls_config(self) -> Dict[str, List[str]]:
        """
        Validate the wb_controls configuration and return any errors found.
        
        Returns:
            Dict[str, List[str]]: Dictionary mapping control names to lists of error messages
        """
        errors = {}
        
        if not hasattr(self.config, 'wb_controls') or not self.config.wb_controls:
            return errors  # No controls to validate
        
        valid_types = {'switch', 'range', 'value', 'text', 'pushbutton'}
        
        for control_name, control_config in self.config.wb_controls.items():
            control_errors = []
            
            # Validate control name
            if not control_name or not isinstance(control_name, str):
                control_errors.append("Control name must be a non-empty string")
            elif control_name.startswith('_'):
                control_errors.append("Control name cannot start with underscore")
            elif control_name not in self._action_handlers:
                control_errors.append(f"No handler found for control '{control_name}'")
            
            # Validate control config structure
            if not isinstance(control_config, dict):
                control_errors.append("Control configuration must be a dictionary")
                errors[control_name] = control_errors
                continue
            
            # Validate type field
            control_type = control_config.get('type')
            if not control_type:
                control_errors.append("Control type is required")
            elif control_type not in valid_types:
                control_errors.append(f"Invalid control type '{control_type}'. Valid types: {valid_types}")
            
            # Validate range-specific fields
            if control_type == 'range':
                min_val = control_config.get('min')
                max_val = control_config.get('max')
                
                if min_val is not None and not isinstance(min_val, (int, float)):
                    control_errors.append("'min' value must be a number")
                if max_val is not None and not isinstance(max_val, (int, float)):
                    control_errors.append("'max' value must be a number")
                if min_val is not None and max_val is not None and min_val >= max_val:
                    control_errors.append("'min' value must be less than 'max' value")
            
            # Validate title field
            title = control_config.get('title')
            if title is not None:
                if isinstance(title, dict):
                    if 'en' not in title:
                        control_errors.append("Title dictionary must contain 'en' key")
                    elif not isinstance(title['en'], str):
                        control_errors.append("Title 'en' value must be a string")
                elif not isinstance(title, str):
                    control_errors.append("Title must be a string or dictionary with 'en' key")
            
            # Validate order field
            order = control_config.get('order')
            if order is not None and not isinstance(order, int):
                control_errors.append("Order must be an integer")
            
            # Validate readonly field
            readonly = control_config.get('readonly')
            if readonly is not None and not isinstance(readonly, bool):
                control_errors.append("Readonly must be a boolean")
            
            if control_errors:
                errors[control_name] = control_errors
        
        return errors
    
    def _validate_wb_state_mappings(self) -> List[str]:
        """
        Validate the wb_state_mappings configuration and return any errors found.
        
        Returns:
            List[str]: List of error messages
        """
        errors = []
        
        if not hasattr(self.config, 'wb_state_mappings') or not self.config.wb_state_mappings:
            return errors  # No mappings to validate
        
        if not isinstance(self.config.wb_state_mappings, dict):
            errors.append("wb_state_mappings must be a dictionary")
            return errors
        
        for state_field, wb_controls in self.config.wb_state_mappings.items():
            # Validate state field name
            if not isinstance(state_field, str) or not state_field:
                errors.append(f"Invalid state field name: {state_field}")
                continue
            
            # Validate wb_controls value
            if isinstance(wb_controls, str):
                # Single control mapping
                if wb_controls not in self._action_handlers:
                    errors.append(f"State field '{state_field}' maps to unknown control '{wb_controls}'")
            elif isinstance(wb_controls, list):
                # Multiple control mapping
                for control in wb_controls:
                    if not isinstance(control, str):
                        errors.append(f"State field '{state_field}' contains non-string control name: {control}")
                    elif control not in self._action_handlers:
                        errors.append(f"State field '{state_field}' maps to unknown control '{control}'")
            else:
                errors.append(f"State field '{state_field}' mapping must be string or list of strings")
        
        return errors
    
    async def validate_wb_configuration(self) -> Tuple[bool, Dict[str, Any]]:
        """
        Comprehensive validation of WB emulation configuration.
        
        Returns:
            Tuple[bool, Dict[str, Any]]: (is_valid, validation_results)
        """
        validation_results = {
            'wb_controls_errors': {},
            'wb_state_mappings_errors': [],
            'handler_validation': {},
            'warnings': []
        }
        
        try:
            # Validate wb_controls configuration
            validation_results['wb_controls_errors'] = self._validate_wb_controls_config()
            
            # Validate wb_state_mappings configuration
            validation_results['wb_state_mappings_errors'] = self._validate_wb_state_mappings()
            
            # Validate that all handlers have reasonable WB control mappings
            for handler_name in self._action_handlers:
                if not handler_name.startswith('_'):
                    handler_validation = self._validate_handler_wb_compatibility(handler_name)
                    if handler_validation:
                        validation_results['handler_validation'][handler_name] = handler_validation
            
            # Check for potential issues
            warnings = []
            
            # Warn about missing MQTT client
            if not self.mqtt_client:
                warnings.append("MQTT client not available - WB emulation will be disabled")
            
            # Warn about disabled WB emulation
            if not self.should_publish_wb_virtual_device():
                warnings.append("WB emulation is disabled in configuration")
            
            # Warn about missing IR topics for devices that might need them
            if hasattr(self.config, 'auralic') and self.should_publish_wb_virtual_device():
                if not getattr(self.config.auralic, 'ir_power_on_topic', None):
                    warnings.append("IR power control not configured - power operations may be limited")
            
            validation_results['warnings'] = warnings
            
            # Determine if configuration is valid
            has_errors = (
                bool(validation_results['wb_controls_errors']) or
                bool(validation_results['wb_state_mappings_errors']) or
                bool(validation_results['handler_validation'])
            )
            
            is_valid = not has_errors
            
            # Log validation results
            if not is_valid:
                logger.warning(f"WB configuration validation failed for device {self.device_id}")
                for control, errors in validation_results['wb_controls_errors'].items():
                    for error in errors:
                        logger.warning(f"WB control '{control}': {error}")
                for error in validation_results['wb_state_mappings_errors']:
                    logger.warning(f"WB state mappings: {error}")
                for handler, issues in validation_results['handler_validation'].items():
                    for issue in issues:
                        logger.warning(f"Handler '{handler}': {issue}")
            
            if warnings:
                for warning in warnings:
                    logger.info(f"WB configuration warning for {self.device_id}: {warning}")
            
            return is_valid, validation_results
            
        except Exception as e:
            logger.error(f"Error during WB configuration validation for {self.device_id}: {str(e)}")
            validation_results['validation_error'] = str(e)
            return False, validation_results
    
    def _validate_handler_wb_compatibility(self, handler_name: str) -> List[str]:
        """
        Validate that a handler is compatible with WB control generation.
        
        Args:
            handler_name: Name of the handler to validate
            
        Returns:
            List[str]: List of compatibility issues
        """
        issues = []
        
        # Check if handler exists
        if handler_name not in self._action_handlers:
            issues.append("Handler method not found")
            return issues
        
        handler = self._action_handlers[handler_name]
        
        # Validate handler is callable
        if not callable(handler):
            issues.append("Handler is not callable")
        
        # Check if handler name suggests it needs parameters but no command config exists
        param_suggesting_names = ['set_', 'move_', 'launch_', 'click_']
        if any(handler_name.startswith(prefix) for prefix in param_suggesting_names):
            # Check if there's a command configuration for this handler
            command_configs = self.get_available_commands()
            if handler_name not in command_configs:
                issues.append("Handler suggests parameter usage but no command configuration found")
            else:
                cmd_config = command_configs[handler_name]
                if not hasattr(cmd_config, 'params') or not cmd_config.params:
                    issues.append("Handler suggests parameter usage but no parameters defined in configuration")
        
        return issues