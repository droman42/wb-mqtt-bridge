from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Type, Callable, TYPE_CHECKING, Awaitable, Coroutine, TypeVar, cast, Union, Generic, Tuple
import logging
import json
import re
from datetime import datetime
from enum import Enum
from socket import socket, AF_INET, SOCK_DGRAM, SOL_SOCKET, SO_BROADCAST
import psutil

from app.schemas import BaseDeviceState, LastCommand, BaseDeviceConfig, BaseCommandConfig, CommandParameterDefinition
from app.mqtt_client import MQTTClient
from app.types import StateT, CommandResult, CommandResponse, ActionHandler
from app.sse_manager import sse_manager, SSEChannel

logger = logging.getLogger(__name__)

class BaseDevice(ABC, Generic[StateT]):
    """Base class for all device implementations."""
    
    def __init__(self, config: BaseDeviceConfig, mqtt_client: Optional["MQTTClient"] = None):
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
        self._state_change_callback = None  # Callback for state changes
        
        # Register action handlers
        self._register_handlers()
        
        # Build action group index
        self._build_action_groups_index()
        
        # Auto-register handlers based on naming convention
        self._auto_register_handlers()
    
    def should_publish_wb_virtual_device(self) -> bool:
        """Check if WB virtual device emulation should be enabled for this device."""
        # Check if MQTT client is available
        if not self.mqtt_client:
            return False
            
        # Check configuration flag (defaults to True)
        return getattr(self.config, 'enable_wb_emulation', True)
    
    async def _setup_wb_virtual_device(self):
        """Set up Wirenboard virtual device emulation."""
        if not self.mqtt_client:
            logger.warning(f"Cannot setup WB virtual device for {self.device_id}: no MQTT client")
            return
        
        # Publish device metadata
        await self._publish_wb_device_meta()
        
        # Publish control metadata and initial states
        await self._publish_wb_control_metas()
        
        # Set up Last Will Testament for offline detection
        await self._setup_wb_last_will()
        
        logger.info(f"WB virtual device emulation enabled for {self.device_id}")
    
    async def _publish_wb_device_meta(self):
        """Publish WB device metadata."""
        device_meta = {
            "driver": "wb_mqtt_bridge",
            "title": {"en": self.device_name}
        }
        
        topic = f"/devices/{self.device_id}/meta"
        await self.mqtt_client.publish(topic, json.dumps(device_meta), retain=True)
        logger.debug(f"Published WB device meta for {self.device_id}")
    
    async def _publish_wb_control_metas(self):
        """Publish WB control metadata for all handlers."""
        for handler_name in self._action_handlers:
            if not handler_name.startswith('_'):
                control_meta = self._generate_wb_control_meta(handler_name)
                
                # Publish control metadata
                meta_topic = f"/devices/{self.device_id}/controls/{handler_name}/meta"
                await self.mqtt_client.publish(meta_topic, json.dumps(control_meta), retain=True)
                
                # Publish initial control state
                initial_state = self._get_initial_wb_control_state(handler_name)
                state_topic = f"/devices/{self.device_id}/controls/{handler_name}"
                await self.mqtt_client.publish(state_topic, str(initial_state), retain=True)
                
                logger.debug(f"Published WB control meta for {self.device_id}/{handler_name}")
    
    def _generate_wb_control_meta(self, handler_name: str) -> Dict[str, Any]:
        """Generate WB control metadata with smart defaults."""
        
        # Check for explicit WB configuration in device config
        if hasattr(self.config, 'wb_controls') and self.config.wb_controls and handler_name in self.config.wb_controls:
            return self.config.wb_controls[handler_name]
        
        # Generate smart defaults based on handler name
        meta = {
            "title": {"en": handler_name.replace('_', ' ').title()},
            "readonly": False,
            "order": self._get_control_order(handler_name)
        }
        
        # Smart type detection based on naming patterns
        handler_lower = handler_name.lower()
        
        if any(x in handler_lower for x in ['power_on', 'power_off', 'play', 'pause', 'stop']):
            meta["type"] = "pushbutton"
        elif 'set_volume' in handler_lower or 'volume' in handler_lower:
            meta.update({
                "type": "range",
                "min": 0,
                "max": 100,
                "units": "%"
            })
        elif 'mute' in handler_lower:
            meta["type"] = "switch"
        elif 'set_' in handler_lower:
            meta["type"] = "range"  # Generic setter
        elif any(x in handler_lower for x in ['get_', 'list_', 'available']):
            meta.update({
                "type": "text",
                "readonly": True
            })
        else:
            meta["type"] = "pushbutton"  # Default for actions
        
        return meta
    
    def _get_control_order(self, handler_name: str) -> int:
        """Generate control ordering based on handler name patterns."""
        handler_lower = handler_name.lower()
        
        # Power controls first
        if 'power_on' in handler_lower:
            return 1
        elif 'power_off' in handler_lower:
            return 2
        # Volume controls
        elif 'volume' in handler_lower:
            return 10
        elif 'mute' in handler_lower:
            return 11
        # Playback controls
        elif any(x in handler_lower for x in ['play', 'pause', 'stop']):
            return 20
        # Navigation controls
        elif any(x in handler_lower for x in ['home', 'back', 'menu']):
            return 30
        # Other controls
        else:
            return 50
    
    def _get_initial_wb_control_state(self, handler_name: str) -> str:
        """Get initial state value for WB control."""
        handler_lower = handler_name.lower()
        
        # Default states based on control type
        if 'mute' in handler_lower:
            return "0"  # Not muted
        elif 'volume' in handler_lower:
            return "50"  # Default volume
        elif any(x in handler_lower for x in ['power_on', 'power_off']):
            return "0"  # Not pressed
        else:
            return "0"  # Default for most controls
    
    async def _setup_wb_last_will(self):
        """Set up Last Will Testament for device offline detection."""
        # Set error state when device goes offline
        error_topic = f"/devices/{self.device_id}/meta/error"
        # Note: will_set is likely synchronous, but publish is async
        self.mqtt_client.will_set(error_topic, "offline", retain=True)
        
        # Clear error state on connection
        await self.mqtt_client.publish(error_topic, "", retain=True)
    
    async def setup_wb_emulation_if_enabled(self):
        """
        Helper method for subclasses to call during their setup() method.
        Sets up WB virtual device emulation if enabled.
        """
        if self.should_publish_wb_virtual_device():
            await self._setup_wb_virtual_device()

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
        
        # Add existing configured topics using the dual support method
        for cmd_name, cmd in self.get_available_commands().items():
            # Use the new get_command_topic method for backward compatibility
            topic = self.get_command_topic(cmd_name, cmd)
            if topic:
                topics.append(topic)
        
        # Add WB command topics for virtual device emulation
        if self.should_publish_wb_virtual_device():
            for handler_name in self._action_handlers:
                if not handler_name.startswith('_'):
                    command_topic = f"/devices/{self.device_id}/controls/{handler_name}/on"
                    topics.append(command_topic)
        
        return topics
    
    def get_command_topic(self, handler_name: str, cmd_config: BaseCommandConfig) -> str:
        """Get topic for command - explicit or auto-generated."""
        if cmd_config.topic:
            return cmd_config.topic  # Use explicit topic if provided
        else:
            return f"/devices/{self.device_id}/controls/{handler_name}"  # Auto-generate
    
    async def handle_message(self, topic: str, payload: str):
        """Handle incoming MQTT messages for this device."""
        logger.debug(f"Device {self.get_name()} received message on {topic}: {payload}")
        
        # DEBUG: Enhanced logging for all device messages
        logger.debug(f"[BASE_DEVICE_DEBUG] handle_message for {self.device_id}: topic={topic}, payload='{payload}'")
        
        # Check if this is a WB command topic
        if self._is_wb_command_topic(topic):
            await self._handle_wb_command(topic, payload)
            return
        
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
    
    def _is_wb_command_topic(self, topic: str) -> bool:
        """Check if topic is a WB command topic."""
        pattern = f"/devices/{re.escape(self.device_id)}/controls/(.+)/on"
        return bool(re.match(pattern, topic))

    async def _handle_wb_command(self, topic: str, payload: str):
        """Handle WB command topic messages."""
        # Extract control name from topic
        match = re.match(f"/devices/{re.escape(self.device_id)}/controls/(.+)/on", topic)
        if not match:
            return
        
        control_name = match.group(1)
        
        # Find corresponding handler
        if control_name in self._action_handlers:
            # Create minimal command config for WB commands
            from app.schemas import BaseCommandConfig
            wb_cmd_config = BaseCommandConfig(
                action=control_name,
                topic=topic,
                description=f"WB command for {control_name}"
            )
            
            # Process parameters from payload
            params = self._process_wb_command_payload(control_name, payload)
            
            # Execute the handler
            await self._execute_single_action(control_name, wb_cmd_config, params, source="wb_command")
            
            # Update WB control state to reflect the command
            await self._update_wb_control_state(control_name, payload)
        else:
            logger.warning(f"No handler found for WB control: {control_name}")
    
    def _process_wb_command_payload(self, control_name: str, payload: str) -> Dict[str, Any]:
        """Process WB command payload into parameters."""
        params = {}
        
        # For range controls, the payload is the value
        handler_lower = control_name.lower()
        if 'volume' in handler_lower or 'set_' in handler_lower:
            try:
                # Try to parse as numeric value
                value = float(payload)
                # Map volume to a generic parameter name
                if 'volume' in handler_lower:
                    params['volume'] = int(value)
                else:
                    params['value'] = value
            except ValueError:
                # If not numeric, treat as string
                params['value'] = payload
        
        return params
    
    async def _update_wb_control_state(self, control_name: str, payload: str):
        """Update WB control state topic with the new value."""
        if self.mqtt_client:
            state_topic = f"/devices/{self.device_id}/controls/{control_name}"
            await self.mqtt_client.publish(state_topic, payload, retain=True)

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
                    raise ValueError(f"Simple value cannot be used with multiple parameters")
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