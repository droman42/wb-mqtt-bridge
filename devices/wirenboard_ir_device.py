import json
import logging
from typing import Dict, Any, List, Optional, Callable, Awaitable, Tuple, cast
from datetime import datetime
from devices.base_device import BaseDevice
from app.schemas import WirenboardIRState, LastCommand, WirenboardIRDeviceConfig, IRCommandConfig
from app.mqtt_client import MQTTClient

logger = logging.getLogger(__name__)

class WirenboardIRDevice(BaseDevice):
    """Implementation of an IR device controlled through Wirenboard."""
    
    def __init__(self, config: Dict[str, Any], mqtt_client: Optional[MQTTClient] = None):
        super().__init__(config, mqtt_client)
        self._state_schema = WirenboardIRState
        
        # Get and use the typed config
        self.typed_config = cast(WirenboardIRDeviceConfig, self.config)
        
        self.state = {
            "last_command": None,
            "alias": self.typed_config.device_name
        }
        
        # Pre-initialize handlers for all commands
        self._initialize_action_handlers()
    
    async def setup(self) -> bool:
        """Initialize the device."""
        try:
            # Load and validate commands configuration
            commands = self.typed_config.commands
            if not commands:
                logger.error(f"No commands defined for device {self.get_name()}")
                self.state["error"] = "No commands defined"
                return True  # Return True to allow device to be initialized even without commands
            
            logger.info(f"Wirenboard IR device {self.get_name()} initialized with {len(commands)} commands")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Wirenboard IR device {self.get_name()}: {str(e)}")
            self.state["error"] = str(e)
            return True  # Return True to allow device to be initialized even with errors
    
    async def shutdown(self) -> bool:
        """Cleanup device resources."""
        try:
            logger.info(f"Wirenboard IR device {self.get_name()} shutdown complete")
            return True
        except Exception as e:
            logger.error(f"Error during device shutdown: {str(e)}")
            return False
    
    def get_current_state(self) -> Dict[str, Any]:
        """Return the current state of the device."""
        # Create a Pydantic model instance and convert to dictionary
        state = WirenboardIRState(
            device_id=self.device_id,
            device_name=self.device_name,
            alias=self.state.get("alias", self.device_name),
            last_command=self.state.get("last_command"),
            error=self.state.get("error")
        )
        # Return dictionary representation for API compatibility
        return state.dict()
    
    def subscribe_topics(self) -> List[str]:
        """Define the MQTT topics this device should subscribe to."""
        alias = self.state.get("alias", self.device_name)
        commands = self.get_available_commands()
        
        # Create subscription topics for each command action
        topics = []
        for command in commands.values():
            topic = command.get("topic")
            if topic:
                topics.append(topic)
            else:
                logger.error(f"MQTT subscription topic {command.get('action')} not found for {alias}")
        
        logger.debug(f"Device {self.get_name()} subscribing to topics: {topics}")
        return topics
    
    def _get_command_topic(self, command_config: IRCommandConfig) -> str:
        """
        Construct the MQTT topic for sending a command based on its configuration.
        Override this method if topic construction rules change.
        """
        # Construct topic using location and rom_position fields
        location = command_config.location
        rom_position = command_config.rom_position
        
        if not location or not rom_position:
            logger.warning("Missing location or rom_position in command config")
            return ""
            
        # Use the original format without /on suffix
        return f"/devices/{location}/controls/Play from ROM{rom_position}/on"
    
    def _validate_parameter(self, 
                           param_name: str, 
                           param_value: Any, 
                           param_type: str, 
                           required: bool = True, 
                           min_value: Optional[float] = None, 
                           max_value: Optional[float] = None) -> Tuple[bool, Any, Optional[str]]:
        """Validate a parameter against its definition and convert to correct type.
        
        Args:
            param_name: Name of the parameter
            param_value: Value of the parameter
            param_type: Expected type ('string', 'integer', 'float', 'boolean', 'range')
            required: Whether the parameter is required
            min_value: Minimum value (for numeric types)
            max_value: Maximum value (for numeric types)
            
        Returns:
            Tuple of (is_valid, converted_value, error_message)
            where error_message is None if validation passed
        """
        # Check if parameter is required but missing
        if required and param_value is None:
            return False, None, f"Missing required '{param_name}' parameter"
            
        # Return early if parameter is not required and not provided
        if not required and param_value is None:
            return True, None, None
            
        converted_value = param_value
        
        # Convert value to the correct type
        try:
            if param_type == "integer":
                converted_value = int(param_value)
                
                # Check range constraints if specified
                if min_value is not None and converted_value < min_value:
                    return False, converted_value, f"{param_name} value {converted_value} is below minimum {min_value}"
                if max_value is not None and converted_value > max_value:
                    return False, converted_value, f"{param_name} value {converted_value} is above maximum {max_value}"
                    
            elif param_type in ("float", "range"):
                converted_value = float(param_value)
                
                # Check range constraints if specified
                if min_value is not None and converted_value < min_value:
                    return False, converted_value, f"{param_name} value {converted_value} is below minimum {min_value}"
                if max_value is not None and converted_value > max_value:
                    return False, converted_value, f"{param_name} value {converted_value} is above maximum {max_value}"
                    
            elif param_type == "boolean":
                if isinstance(param_value, str):
                    converted_value = param_value.lower() in ("yes", "true", "1", "on")
                else:
                    converted_value = bool(param_value)
                    
        except (ValueError, TypeError):
            error_msg = f"Invalid {param_name} value: {param_value}. Must be a {param_type} value."
            return False, param_value, error_msg
            
        return True, converted_value, None
    
    def _create_response(self, 
                        success: bool, 
                        action: str, 
                        message: Optional[str] = None, 
                        error: Optional[str] = None,
                        **extra_fields) -> Dict[str, Any]:
        """Create a standardized response dictionary.
        
        Args:
            success: Whether the action was successful
            action: The name of the action
            message: Optional success message
            error: Optional error message
            **extra_fields: Additional fields to include in the response
            
        Returns:
            A standardized response dictionary
        """
        response = {
            "success": success,
            "action": action,
            "device_id": self.device_id
        }
        
        if success and message:
            response["message"] = message
            
        if not success and error:
            response["error"] = error
            
        # Add any extra fields
        response.update(extra_fields)
        
        return response
    
    def record_last_command(self, action: str, params: Dict[str, Any] = None, 
                           command_topic: Optional[str] = None,
                           command_payload: Any = None):
        """Record the last command executed with its parameters.
        
        Args:
            action: The name of the action executed
            params: Any parameters used with the command
            command_topic: The MQTT topic the command was sent to (IR-specific)
            command_payload: The payload sent with the command (IR-specific)
        """
        # Store MQTT-specific details in params to maintain compatibility
        if command_topic or command_payload is not None:
            if params is None:
                params = {}
            if command_topic:
                params["command_topic"] = command_topic
            if command_payload is not None:
                params["command_payload"] = command_payload
                
        # Create a standard LastCommand object
        self.state["last_command"] = LastCommand(
            action=action,
            source=self.device_name,
            timestamp=datetime.now(),
            params=params
        ).dict()
    
    async def handle_message(self, topic: str, payload: str):
        """Handle incoming MQTT messages for this device."""
        logger.debug(f"Wirenboard IR device received message on {topic}: {payload}")
        try:
            # Find matching command configuration by comparing full topic
            matching_cmd_name = None
            matching_cmd_config = None
            
            for cmd_name, cmd_config in self.get_available_commands().items():
                if cmd_config.get("topic") == topic:
                    matching_cmd_name = cmd_name
                    matching_cmd_config = cmd_config
                    break
            
            if not matching_cmd_name or not matching_cmd_config:
                logger.warning(f"No command configuration found for topic: {topic}")
                return
            
            # Process parameters if defined in the command
            params = {}
            param_definitions = matching_cmd_config.get("params", [])
            
            if param_definitions:
                # Try to parse payload as JSON for any parameters
                try:
                    params = json.loads(payload)
                except json.JSONDecodeError:
                    # For single parameter commands, try to map raw payload to the first parameter
                    if len(param_definitions) == 1:
                        param_def = param_definitions[0]
                        param_name = param_def["name"]
                        param_type = param_def["type"]
                        
                        # Use validation helper to convert and validate
                        is_valid, converted_value, error_message = self._validate_parameter(
                            param_name=param_name,
                            param_value=payload,
                            param_type=param_type,
                            required=param_def.get("required", True),
                            min_value=param_def.get("min"),
                            max_value=param_def.get("max")
                        )
                        
                        if is_valid:
                            params = {param_name: converted_value}
                        else:
                            logger.error(f"Failed to convert payload '{payload}': {error_message}")
                            return self._create_response(False, matching_cmd_name, 
                                                      error=f"Invalid payload format: {payload}")
                    else:
                        logger.error(f"Payload is not valid JSON and command expects multiple parameters: {payload}")
                        return self._create_response(False, matching_cmd_name, 
                                                  error="Invalid JSON format for multi-parameter command")
            
            # Check if the payload indicates command should be executed
            # For IR device, we typically expect "1" or "true" to trigger the action
            if payload.lower() in ["1", "true"] or param_definitions:
                # Get the topic to publish the command
                command_topic = self._get_command_topic(matching_cmd_config)
                if not command_topic:
                    error_msg = f"Could not determine command topic for topic: {topic}"
                    logger.error(error_msg)
                    return self._create_response(False, matching_cmd_name, error=error_msg)
                
                # Command payload is typically 1 for IR commands
                command_payload = matching_cmd_config.get('payload', 1)  
                
                # Record this as the last command sent
                self.record_last_command(
                    action=matching_cmd_name,
                    params=params,
                    command_topic=command_topic,
                    command_payload=command_payload
                )
                
                # Return the topic and payload to be published
                # This is crucial for both MQTT subscription handling and API action handling
                return {
                    "topic": command_topic,
                    "payload": command_payload
                }
            
        except Exception as e:
            logger.error(f"Error handling message for {self.get_name()}: {str(e)}")
            return self._create_response(False, "unknown", error=str(e))
    
    def get_last_command(self) -> Optional[Dict[str, Any]]:
        """Return information about the last executed command."""
        return self.state.get("last_command") 
    
    def _initialize_action_handlers(self):
        """Initialize action handlers for all commands."""
        self._action_handlers = {}
        
        # For each command in the config, create a handler
        for cmd_name, cmd_config in self.typed_config.commands.items():
            # The action field is now optional with CommandConfig
            action_name = cmd_config.action if cmd_config.action else cmd_name
            self._action_handlers[action_name] = self._create_generic_handler(action_name, cmd_config)
            logger.debug(f"Registered handler for action '{action_name}'")
    
    def _create_generic_handler(self, action_name: str, cmd_config: IRCommandConfig):
        """Create a generic handler for a command."""
        
        async def generic_handler(cmd_config: IRCommandConfig, params: Dict[str, Any] = None):
            """Generic action handler for IR commands."""
            logger.debug(f"Executing generic IR action: {action_name}")
            
            try:
                # Get the topic for this command
                topic = self._get_command_topic(cmd_config)
                if not topic:
                    error_msg = f"Failed to construct topic for {action_name}"
                    logger.error(error_msg)
                    return self._create_response(False, action_name, error=error_msg)
                
                # For IR commands, the payload is always "1"
                payload = "1"
                
                # Record this command as the last executed
                if params is None:
                    params = {}
                
                params["mqtt_topic"] = topic
                params["mqtt_payload"] = payload
                self.record_last_command(action_name, params, topic, payload)
                
                # If MQTT client is available, publish the command
                if self.mqtt_client:
                    try:
                        await self.mqtt_client.publish(topic, payload)
                        logger.info(f"Published IR command '{action_name}' to {topic}")
                        return self._create_response(
                            success=True, 
                            action=action_name, 
                            message=f"Successfully executed IR command '{action_name}'",
                            mqtt_topic=topic,
                            mqtt_payload=payload
                        )
                    except Exception as e:
                        error_msg = f"Failed to publish IR command '{action_name}': {str(e)}"
                        logger.error(error_msg)
                        return self._create_response(False, action_name, error=error_msg)
                else:
                    error_msg = "MQTT client not available"
                    logger.error(error_msg)
                    return self._create_response(False, action_name, error=error_msg)
                    
            except Exception as e:
                error_msg = f"Error in generic IR handler for '{action_name}': {str(e)}"
                logger.error(error_msg)
                return self._create_response(False, action_name, error=error_msg)
        
        return generic_handler

    def _get_action_handler(self, action_name: str) -> Optional[Callable[..., Any]]:
        """Get the handler for the specified action from pre-initialized handlers."""
        # Convert to lower case for case-insensitive lookup
        action_name = action_name.lower()
        
        # Look up the handler directly from the pre-initialized dictionary
        handler = self._action_handlers.get(action_name)
        if handler:
            return handler
        
        # If not found, check if maybe it's in camelCase and we have a handler for snake_case
        if '_' not in action_name:
            # Convert camelCase to snake_case and try again
            snake_case = ''.join(['_' + c.lower() if c.isupper() else c for c in action_name]).lstrip('_')
            handler = self._action_handlers.get(snake_case)
            if handler:
                return handler
        
        # No handler found
        logger.warning(f"No action handler found for action: {action_name}")
        return None
    