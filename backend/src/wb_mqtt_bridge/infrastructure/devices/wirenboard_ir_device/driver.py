import logging
from typing import Dict, Any, Optional, Tuple, cast
from datetime import datetime
from wb_mqtt_bridge.infrastructure.devices.base import BaseDevice
from wb_mqtt_bridge.domain.devices.models import WirenboardIRState, LastCommand
from wb_mqtt_bridge.infrastructure.config.models import WirenboardIRDeviceConfig, IRCommandConfig, BaseCommandConfig
from wb_mqtt_bridge.infrastructure.mqtt.client import MQTTClient
from wb_mqtt_bridge.domain.devices.types import CommandResult, ActionHandler

logger = logging.getLogger(__name__)

class WirenboardIRDevice(BaseDevice[WirenboardIRState]):
    """Implementation of an IR device controlled through Wirenboard."""

    # Narrow self.config to the IR-specific config so pyright knows
    # commands are IRCommandConfig instances (BaseDevice declares BaseDeviceConfig).
    config: WirenboardIRDeviceConfig
    
    def __init__(self, config: WirenboardIRDeviceConfig, mqtt_client: Optional[MQTTClient] = None) -> None:
        super().__init__(config, mqtt_client)
        
        # Initialize state with typed Pydantic model
        self.state: WirenboardIRState = WirenboardIRState(
            device_id=self.device_id,
            device_name=self.device_name,
            alias=self.config.names.ru
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
            
            # Create special stateful handlers for power commands
            if action_name == "power":
                self._action_handlers[action_name] = self._create_power_toggle_handler(action_name, cmd_config)
            elif action_name == "power_on":
                self._action_handlers[action_name] = self._create_power_on_handler(action_name, cmd_config)
            elif action_name == "power_off":
                self._action_handlers[action_name] = self._create_power_off_handler(action_name, cmd_config)
            else:
                # Use generic handler for all other commands
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
    
    def _create_power_toggle_handler(self, action_name: str, cmd_config: IRCommandConfig) -> ActionHandler:
        """Create a power toggle handler that switches between on/off states."""
        original_cmd_config = cmd_config
        
        async def power_toggle_handler(cmd_config: BaseCommandConfig, params: Dict[str, Any]) -> CommandResult:
            """Toggle power state handler."""
            logger.debug(f"Executing power toggle for {self.device_name}")
            
            try:
                # Determine new power state (opposite of current). A forced reconcile
                # (SCN-11) passes `assume_state` = the plan target: when the belief is
                # wrong, blind-flipping it would recreate the desync mirrored — the
                # caller KNOWS which state the toggle lands on, so claim that instead.
                assume_state = (params or {}).get("assume_state")
                if assume_state in ("on", "off"):
                    new_power_state = assume_state
                else:
                    new_power_state = "off" if self.state.power == "on" else "on"

                # Execute the IR command
                result = await self._execute_ir_command(action_name, original_cmd_config, params)
                
                if result.get("success"):
                    # Update power state to toggled value (CommandResult is a dict)
                    self.update_state(power=new_power_state)
                    result["message"] = f"Power toggled to {new_power_state}"
                    logger.info(f"{self.device_name}: Power toggled to {new_power_state}")
                
                return result
                
            except Exception as e:
                logger.error(f"Error in power toggle handler: {str(e)}")
                return self.create_command_result(success=False, error=str(e))
        
        return power_toggle_handler
    
    def _create_power_on_handler(self, action_name: str, cmd_config: IRCommandConfig) -> ActionHandler:
        """Create a conditional power on handler that only executes if device is off."""
        original_cmd_config = cmd_config
        
        async def power_on_handler(cmd_config: BaseCommandConfig, params: Dict[str, Any]) -> CommandResult:
            """Conditional power on handler."""
            logger.debug(f"Executing power on for {self.device_name}")
            
            try:
                # Idempotence guard (honors `force` — the only escape from an
                # optimistic-state desync on a one-way IR channel, DRV-5).
                skip = self.idempotence_skip(
                    params, self.state.power == "on", "Device already on, command skipped"
                )
                if skip is not None:
                    logger.info(f"{self.device_name}: Device already on, skipping power_on command")
                    return skip

                # Device is off (or force), execute the IR command
                result = await self._execute_ir_command(action_name, original_cmd_config, params)
                
                if result.get("success"):
                    # Update power state to on (CommandResult is a dict)
                    self.update_state(power="on")
                    result["message"] = "Device powered on"
                    logger.info(f"{self.device_name}: Device powered on")
                
                return result
                
            except Exception as e:
                logger.error(f"Error in power on handler: {str(e)}")
                return self.create_command_result(success=False, error=str(e))
        
        return power_on_handler
    
    def _create_power_off_handler(self, action_name: str, cmd_config: IRCommandConfig) -> ActionHandler:
        """Create a conditional power off handler that only executes if device is on."""
        original_cmd_config = cmd_config
        
        async def power_off_handler(cmd_config: BaseCommandConfig, params: Dict[str, Any]) -> CommandResult:
            """Conditional power off handler."""
            logger.debug(f"Executing power off for {self.device_name}")
            
            try:
                # Idempotence guard (honors `force` — DRV-5, see power_on).
                skip = self.idempotence_skip(
                    params, self.state.power == "off", "Device already off, command skipped"
                )
                if skip is not None:
                    logger.info(f"{self.device_name}: Device already off, skipping power_off command")
                    return skip

                # Device is on (or force), execute the IR command
                result = await self._execute_ir_command(action_name, original_cmd_config, params)
                
                if result.get("success"):
                    # Update power state to off (CommandResult is a dict)
                    self.update_state(power="off")
                    result["message"] = "Device powered off"
                    logger.info(f"{self.device_name}: Device powered off")
                
                return result
                
            except Exception as e:
                logger.error(f"Error in power off handler: {str(e)}")
                return self.create_command_result(success=False, error=str(e))
        
        return power_off_handler
    
    async def _execute_ir_command(self, action_name: str, cmd_config: IRCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """Helper method to execute an IR command via MQTT."""
        try:
            # Get the topic for this command
            topic = self._get_command_topic(cmd_config)
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
                    await self.emit_progress(f"IR command '{action_name}' sent successfully", "action_success")

                    # Do NOT return mqtt_command here: we just published the IR directly. If we
                    # also returned it, the API action router (devices.py) would publish the same
                    # IR a second time — a double blast. (The no-client fallback below still
                    # returns it, since in that branch nothing was published.)
                    return self.create_command_result(
                        success=True,
                        message=f"IR command '{action_name}' executed successfully",
                    )
                except Exception as e:
                    error_msg = f"Failed to publish MQTT command: {str(e)}"
                    logger.error(error_msg)
                    await self.emit_progress(error_msg, "action_error")
                    return self.create_command_result(success=False, error=error_msg)
            else:
                # No MQTT client available - still report success for command preparation
                logger.warning(f"No MQTT client available for {self.device_name}")
                return self.create_command_result(
                    success=True,
                    message=f"IR command '{action_name}' prepared (no MQTT client)",
                    mqtt_command={"topic": topic, "payload": payload}
                )
                
        except Exception as e:
            logger.error(f"Error executing IR command {action_name}: {str(e)}")
            return self.create_command_result(success=False, error=str(e))

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
                        # Optimistic input tracking (IR has no feedback): record the input we just
                        # selected so the scenario reconciler can diff it. The value is derived from
                        # the capability `input` domain's by_value mapping (command -> value), NOT a
                        # command-name convention — e.g. the command bound to value "aux2".
                        input_cap = self.capabilities.get("input") if self.capabilities is not None else None
                        by_value = getattr(getattr(input_cap, "select", None), "by_value", None) or {}
                        input_value = next(
                            (v for v, ca in by_value.items() if getattr(ca, "command", None) == action_name),
                            None,
                        )
                        if input_value is not None:
                            self.update_state(input=input_value)
                        # No mqtt_topic/mqtt_payload: the IR was already published directly above.
                        # Returning it would double-publish via the API action router (devices.py).
                        return self.create_command_result(
                            success=True,
                            message=f"Successfully executed IR command '{action_name}'",
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
    