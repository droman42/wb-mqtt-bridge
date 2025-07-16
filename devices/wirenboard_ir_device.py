import json
import logging
from typing import Dict, Any, List, Optional, Callable, Awaitable, Tuple, cast, Union
from datetime import datetime
from devices.base_device import BaseDevice
from app.schemas import WirenboardIRState, LastCommand, WirenboardIRDeviceConfig, IRCommandConfig, BaseCommandConfig
from app.mqtt_client import MQTTClient
from app.types import CommandResult, CommandResponse, ActionHandler

logger = logging.getLogger(__name__)

class WirenboardIRDevice(BaseDevice[WirenboardIRState]):
    """Implementation of an IR device controlled through Wirenboard."""
    
    def __init__(self, config: WirenboardIRDeviceConfig, mqtt_client: Optional[MQTTClient] = None) -> None:
        super().__init__(config, mqtt_client)
        
        # Initialize state with typed Pydantic model
        self.state: WirenboardIRState = WirenboardIRState(
            device_id=self.device_id,
            device_name=self.device_name,
            alias=self.config.device_name
        )
        
        # Do not initialize action handlers here as it will be done in _register_handlers
    
    def _register_handlers(self) -> None:
        """
        Register action handlers for the Wirenboard IR device.
        
        This method is called during initialization to register all
        action handlers for this device.
        """
        # Register handlers for each command
        for cmd_name, cmd_config in self.config.commands.items():
            # Get the action name from the command config
            action_name = cmd_config.action if cmd_config.action else cmd_name
            self._action_handlers[action_name] = self._create_generic_handler(action_name, cmd_config)
            logger.debug(f"Registered handler for action '{action_name}'")
    
    async def setup(self) -> bool:
        """Initialize the device."""
        try:
            # Load and validate commands configuration
            commands = self.config.commands
            if not commands:
                logger.error(f"No commands defined for device {self.get_name()}")
                self.update_state(error="No commands defined")
                await self.emit_progress(f"No commands defined for {self.device_name}", "action_error")
                return True  # Return True to allow device to be initialized even without commands
            
            logger.info(f"Wirenboard IR device {self.get_name()} initialized with {len(commands)} commands")
            await self.emit_progress(f"Wirenboard IR device {self.device_name} initialized with {len(commands)} commands", "action_success")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Wirenboard IR device {self.get_name()}: {str(e)}")
            self.update_state(error=str(e))
            await self.emit_progress(f"Failed to initialize {self.device_name}: {str(e)}", "action_error")
            return True  # Return True to allow device to be initialized even with errors
    
    async def shutdown(self) -> bool:
        """Cleanup device resources."""
        try:
            logger.info(f"Wirenboard IR device {self.get_name()} shutdown complete")
            await self.emit_progress(f"Wirenboard IR device {self.device_name} shutdown complete", "action_success")
            return True
        except Exception as e:
            logger.error(f"Error during device shutdown: {str(e)}")
            return False
    
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
    
    def record_last_command(self, 
                           action: str, 
                           params: Optional[Dict[str, Any]] = None, 
                           command_topic: Optional[str] = None,
                           command_payload: Any = None) -> None:
        """Record the last command executed with its parameters.
        
        Args:
            action: The name of the action executed
            params: Any parameters used with the command
            command_topic: The MQTT topic the command was sent to (IR-specific)
            command_payload: The payload sent with the command (IR-specific)
        """
        # Store MQTT-specific details in params to maintain compatibility
        effective_params: Dict[str, Any] = params or {}
        
        if command_topic or command_payload is not None:
            if command_topic:
                effective_params["command_topic"] = command_topic
            if command_payload is not None:
                effective_params["command_payload"] = command_payload
                
        # Create a standard LastCommand object and update state
        # Since WirenboardIR devices are typically called from MQTT messages in handle_message,
        # we use "mqtt" as the source here. API calls will be handled by BaseDevice.
        last_command = LastCommand(
            action=action,
            source="mqtt",
            timestamp=datetime.now(),
            params=effective_params
        )
        
        self.update_state(last_command=last_command)
    
    async def handle_message(self, topic: str, payload: str) -> Optional[CommandResult]:
        """
        Handle incoming MQTT messages for this device.
        
        Args:
            topic: The MQTT topic of the incoming message
            payload: The message payload
            
        Returns:
            Optional[CommandResult]: Result of handling the message or None
        """
        logger.debug(f"Wirenboard IR device received message on {topic}: {payload}")
        try:
            # Find matching command configuration by comparing full topic
            matching_cmd_name: Optional[str] = None
            matching_cmd_config: Optional[IRCommandConfig] = None
            
            for cmd_name, cmd_config in self.get_available_commands().items():
                auto_generated_topic = f"/devices/{self.device_id}/controls/{cmd_name}"
                if auto_generated_topic == topic:
                    matching_cmd_name = cmd_name
                    matching_cmd_config = cast(IRCommandConfig, cmd_config)
                    break
            
            if not matching_cmd_name or not matching_cmd_config:
                logger.warning(f"No command configuration found for topic: {topic}")
                return None
            
            # Process parameters if defined in the command
            params: Dict[str, Any] = {}
            param_definitions = matching_cmd_config.params if hasattr(matching_cmd_config, 'params') else []
            
            if param_definitions:
                # Try to parse payload as JSON for any parameters
                try:
                    params = json.loads(payload)
                except json.JSONDecodeError:
                    # For single parameter commands, try to map raw payload to the first parameter
                    if len(param_definitions) == 1:
                        param_def = param_definitions[0]
                        param_name = param_def.name
                        param_type = param_def.type
                        
                        # Use validation helper to convert and validate
                        is_valid, converted_value, error_message = self._validate_parameter(
                            param_name=param_name,
                            param_value=payload,
                            param_type=param_type,
                            required=param_def.required,
                            min_value=param_def.min,
                            max_value=param_def.max
                        )
                        
                        if is_valid:
                            params = {param_name: converted_value}
                        else:
                            logger.error(f"Failed to convert payload '{payload}': {error_message}")
                            return self.create_command_result(
                                success=False, 
                                error=f"Invalid payload format: {payload}"
                            )
                    else:
                        logger.error(f"Payload is not valid JSON and command expects multiple parameters: {payload}")
                        return self.create_command_result(
                            success=False, 
                            error="Invalid JSON format for multi-parameter command"
                        )
            
            # Check if the payload indicates command should be executed
            # For IR device, we typically expect "1" or "true" to trigger the action
            if payload.lower() in ["1", "true"] or param_definitions:
                # Get the topic to publish the command
                command_topic = self._get_command_topic(matching_cmd_config)
                if not command_topic:
                    error_msg = f"Could not determine command topic for topic: {topic}"
                    logger.error(error_msg)
                    return self.create_command_result(success=False, error=error_msg)
                
                # Record this as the last command sent
                self.record_last_command(
                    action=matching_cmd_name,
                    params=params,
                    command_topic=command_topic,
                    command_payload="1"
                )
                
                # Return the topic and payload to be published
                # This is crucial for both MQTT subscription handling and API action handling
                return self.create_command_result(
                    success=True,
                    message=f"IR command executed for topic {topic}",
                    mqtt_command={
                        "topic": command_topic,
                        "payload": 1
                    }
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Error handling message for {self.get_name()}: {str(e)}")
            return self.create_command_result(success=False, error=str(e))
    
    def get_last_command(self) -> Optional[LastCommand]:
        """Return information about the last executed command."""
        if self.state.last_command:
            return self.state.last_command
        return None
    
    def _create_generic_handler(self, action_name: str, cmd_config: IRCommandConfig) -> ActionHandler:
        """
        Create a generic handler for a command that follows the standard signature.
        
        Args:
            action_name: Name of the action
            cmd_config: IR command configuration
            
        Returns:
            ActionHandler: A handler function with the standardized signature
        """
        # Capture the original command config in closure
        original_cmd_config = cmd_config
        
        async def generic_handler(cmd_config: BaseCommandConfig, params: Dict[str, Any]) -> CommandResult:
            """
            Generic action handler for IR commands.
            
            Args:
                cmd_config: Command configuration
                params: Dictionary of parameters
                
            Returns:
                CommandResult: Result of the command execution
            """
            logger.debug(f"Executing generic IR action: {action_name}")
            
            try:
                # Type check for command_config - convert to IRCommandConfig if needed
                effective_cmd_config: IRCommandConfig
                if isinstance(cmd_config, IRCommandConfig):
                    effective_cmd_config = cmd_config
                else:
                    # For backward compatibility or if command_config is of a different type,
                    # fall back to the original_cmd_config from closure
                    effective_cmd_config = original_cmd_config
                
                # Get the topic for this command
                topic = self._get_command_topic(effective_cmd_config)
                if not topic:
                    error_msg = f"Failed to construct topic for {action_name}"
                    logger.error(error_msg)
                    return self.create_command_result(success=False, error=error_msg)
                
                # For IR commands, the payload is always "1"
                payload = "1"
                
                # Record this command as the last executed
                self.record_last_command(action_name, params, topic, payload)
                
                # If MQTT client is available, publish the command
                if self.mqtt_client:
                    try:
                        await self.emit_progress(f"Executing IR command '{action_name}' on {self.device_name}", "action_progress")
                        await self.mqtt_client.publish(topic, payload)
                        logger.info(f"Published IR command '{action_name}' to {topic}")
                        await self.emit_progress(f"IR command '{action_name}' sent successfully", "action_success")
                        return self.create_command_result(
                            success=True, 
                            message=f"Successfully executed IR command '{action_name}'",
                            mqtt_topic=topic,
                            mqtt_payload=payload
                        )
                    except Exception as e:
                        error_msg = f"Failed to publish IR command '{action_name}': {str(e)}"
                        logger.error(error_msg)
                        return self.create_command_result(success=False, error=error_msg)
                else:
                    error_msg = "MQTT client not available"
                    logger.error(error_msg)
                    return self.create_command_result(success=False, error=error_msg)
                    
            except Exception as e:
                error_msg = f"Error in generic IR handler for '{action_name}': {str(e)}"
                logger.error(error_msg)
                return self.create_command_result(success=False, error=error_msg)
        
        return generic_handler
    
    def get_available_commands(self) -> Dict[str, IRCommandConfig]:
        """Return the list of available commands for this device."""
        return cast(Dict[str, IRCommandConfig], self.config.commands)
    