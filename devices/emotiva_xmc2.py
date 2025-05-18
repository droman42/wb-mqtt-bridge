import logging
import json
import asyncio
from datetime import datetime
from enum import Enum, auto
from typing import Dict, Any, List, Optional, Union, Callable, Awaitable, Tuple, TypeVar, cast

# Updated imports for new library
from pymotivaxmc2 import EmotivaController
from pymotivaxmc2.enums import Command, Property, Input, Zone

from devices.base_device import BaseDevice
from app.schemas import EmotivaXMC2State, LastCommand, EmotivaConfig as AppEmotivaConfig, EmotivaXMC2DeviceConfig, StandardCommandConfig, CommandParameterDefinition
from app.types import StateT, CommandResult, CommandResponse, ActionHandler

logger = logging.getLogger(__name__)

# Define enums for strongly typed states
class PowerState(str, Enum):
    """Power state enum for eMotiva device."""
    ON = "on"
    OFF = "off"
    UNKNOWN = "unknown"

class EMotivaXMC2(BaseDevice[EmotivaXMC2State]):
    """eMotiva XMC2 processor device implementation.
    
    This class implements control for the Emotiva XMC-2 processor using the pymotivaxmc2 library.
    
    Input Selection:
    - The device supports inputs like: hdmi1, hdmi2, coax1, optical1, tuner
    - These correspond to the values in the Input enum from pymotivaxmc2.enums
    
    State Management:
    - The device maintains state for power, volume, mute, inputs, etc.
    - Properties are automatically tracked via callbacks from the controller
    """
    
    # Define standard properties to monitor for consistent usage across methods
    PROPERTIES_TO_MONITOR = [
        Property.POWER,              # Main zone power
        Property.ZONE2_POWER,        # Zone 2 power
        Property.VOLUME,             # Main volume
        Property.MUTE,               # Mute status
        Property.INPUT,              # Current input
        Property.AUDIO_INPUT,        # Audio input
        Property.VIDEO_INPUT,        # Video input
        Property.AUDIO_BITSTREAM,    # Audio bitstream format
        Property.AUDIO_MODE          # Audio processing mode
    ]
    
    def __init__(self, config: EmotivaXMC2DeviceConfig, mqtt_client=None):
        super().__init__(config, mqtt_client)
        
        self.client: Optional[EmotivaController] = None
        
        # Initialize device state with Pydantic model
        self.state: EmotivaXMC2State = EmotivaXMC2State(
            device_id=self.config.device_id,
            device_name=self.config.device_name,
            power=None,
            zone2_power=None,
            input_source=None,
            video_input=None,
            audio_input=None,
            volume=None,
            mute=None,
            audio_mode=None,
            audio_bitstream=None,
            connected=False,
            ip_address=None,
            mac_address=None,
            startup_complete=False,
            notifications=False,
            last_command=None,
            error=None
        )
        
    async def setup(self) -> bool:
        """Initialize the device."""
        try:
            # Get emotiva configuration directly from config
            emotiva_config: AppEmotivaConfig = self.config.emotiva
            
            # Get the host IP address
            host = emotiva_config.host
            if not host:
                logger.error(f"Missing 'host' in emotiva configuration for device: {self.get_name()}")
                self.set_error("Missing host configuration")
                return False
            
            # Store MAC address if available in config
            if emotiva_config.mac:
                self.update_state(mac_address=emotiva_config.mac)
                
            logger.info(f"Initializing eMotiva XMC2 device: {self.get_name()} at {host}")
            
            # Create and initialize controller with simplified constructor
            self.client = EmotivaController(
                host=host,
                timeout=emotiva_config.timeout or 5.0,
                protocol_max="3.1"  # Use the most recent protocol version
            )
            
            # Update state with IP address at this point
            self.update_state(ip_address=host)
            
            # Connect to the device
            try:
                await self.client.connect()
                logger.info(f"Connected to device at {host}")
            except Exception as e:
                logger.error(f"Failed to connect to device at {host}: {str(e)}")
                self.set_error(f"Connection error: {str(e)}")
                return False
            
            # Set up callbacks for property changes
            for prop in self.PROPERTIES_TO_MONITOR:
                self._register_property_callback(prop)
            
            # Attempt to subscribe to properties
            try:
                await self.client.subscribe(self.PROPERTIES_TO_MONITOR)
                logger.info(f"Successfully subscribed to properties for {self.get_name()}")
                
                # Query initial device state
                await self._refresh_device_state()
                
                # Update state with successful connection
                self.clear_error()  # Clear any previous errors
                self.update_state(
                    connected=True,
                    ip_address=host,
                    startup_complete=True,
                    notifications=True
                )
                
                return True
            except Exception as e:
                # Handle subscription failure
                error_message = f"Error subscribing to properties: {str(e)}"
                logger.error(error_message)
                
                # The device might be in standby mode if subscription fails
                # Try to continue if force_connect is enabled
                if emotiva_config.force_connect:
                    logger.warning(f"Force connect enabled, continuing with setup despite subscription failure")
                    
                    # Update state assuming standby mode
                    self.update_state(
                        connected=True,
                        ip_address=host,
                        startup_complete=True,
                        notifications=False,
                        power=PowerState.OFF  # Assume standby mode which is a valid state
                    )
                    
                    # Set error but don't fail setup
                    self.set_error(f"Subscription failed, using forced connection: {error_message}")
                    
                    return True
                else:
                    self.set_error(error_message)
                    return False

        except Exception as e:
            logger.error(f"Failed to initialize eMotiva XMC2 device {self.get_name()}: {str(e)}")
            self.set_error(f"Initialization error: {str(e)}")
            return False

    async def shutdown(self) -> bool:
        """Cleanup device resources and properly shut down connections."""
        if not self.client:
            logger.info(f"No client initialized for {self.get_name()}, nothing to shut down")
            return True
            
        logger.info(f"Starting shutdown for eMotiva XMC2 device: {self.get_name()}")
        
        try:
            # Let the library handle all connection cleanup
            await self.client.disconnect()
            logger.info(f"Successfully disconnected {self.get_name()}")
            
            # Update our state
            self.clear_error()
            self.update_state(
                connected=False,
                notifications=False
            )
            
            # Release client reference
            self.client = None
            
            logger.info(f"eMotiva XMC2 device {self.get_name()} shutdown complete")
            return True
        except Exception as e:
            error_message = f"Failed to shutdown {self.get_name()}: {str(e)}"
            logger.error(error_message)
            self.set_error(str(e))
            return False

    async def publish_progress(self, message: str) -> None:
        """
        Publish a progress message to the MQTT progress topic for this device.
        
        Args:
            message: The message to publish
        """
        if not self.mqtt_client or not self.mqtt_progress_topic:
            return
            
        try:
            # Ensure the topic has proper prefix/suffix
            topic = self.mqtt_progress_topic
            if not topic.startswith('/'):
                topic = f'/{topic}'
                
            # Include device info in the progress message
            progress_data = {
                "device_id": self.device_id,
                "device_name": self.device_name,
                "timestamp": datetime.now().isoformat(),
                "message": message
            }
            
            # Publish to MQTT
            await self.mqtt_client.publish(topic, json.dumps(progress_data))
            logger.debug(f"Published progress message to {topic}: {message}")
        except Exception as e:
            logger.error(f"Error publishing progress message: {str(e)}")
            # Don't set error state for publishing issues as they might be transient
            # and not related to the device itself

    async def handle_set_input(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """
        Handle setting input source by input ID.
        
        This method supports setting inputs using the format recognized by the Emotiva controller.
        Supported inputs include: hdmi1-hdmi8, coax1-coax4, optical1-optical4, tuner
        
        Args:
            cmd_config: Command configuration
            params: Parameters containing input ID
            
        Returns:
            Command execution result
        """
        # Validate parameters
        if not params:
            return self.create_command_result(success=False, error="Missing input parameters")
        
        # Get and validate input parameter
        input_param = cmd_config.get_parameter("input")
        is_valid, input_id, error_msg = self._validate_parameter(
            param_name="input",
            param_value=params.get("input"),
            param_type=input_param.type if input_param else "string",
            action="set_input"
        )
        
        if not is_valid:
            return self.create_command_result(success=False, error=error_msg)
        
        try:
            # Normalize the input ID to lowercase
            normalized_input = input_id.lower()
            
            # Try to find the matching Input enum
            input_enum = None
            try:
                # First try to find the enum by name (uppercase, like HDMI1)
                input_enum = getattr(Input, normalized_input.upper())
            except (AttributeError, ValueError):
                # If not a direct match, try to find a close match
                for enum_value in Input:
                    if enum_value.value.lower() == normalized_input:
                        input_enum = enum_value
                        break
            
            if input_enum:
                # Use the enum directly
                await self.client.select_input(input_enum)
                logger.debug(f"Selected input using enum: {input_enum}")
            else:
                # Fall back to using string if enum not found
                logger.debug(f"No matching enum found for input '{normalized_input}', using string value")
                await self.client.select_input(normalized_input)
            
            # Update our internal state
            self.update_state(input_source=normalized_input)
            
            # Clear any errors
            self.clear_error()
            
            # Update the last command information
            self._update_last_command("set_input", {"input": normalized_input})
            
            # Return success result
            return self.create_command_result(
                success=True,
                message=f"Input set to {normalized_input} successfully",
                input=normalized_input
            )
        except Exception as e:
            error_message = f"Failed to set input to {input_id}: {str(e)}"
            logger.error(error_message)
            self.set_error(error_message)
            return self.create_command_result(
                success=False,
                error=error_message
            )
    
    async def _power_zone(self, zone_id: Union[int, str], power_on: bool) -> bool:
        """Control power for a specific zone.
        
        Args:
            zone_id: Zone ID (1 for main, 2 for zone2)
            power_on: True to power on, False to power off
            
        Returns:
            True if successful, False otherwise
        """
        if not self.client:
            logger.warning("Cannot control power: client not initialized")
            return False
            
        try:
            # Get the zone enum
            zone = self._get_zone(zone_id)
            
            # Control power for the specified zone
            if zone == Zone.MAIN:
                if power_on:
                    await self.client.power_on()
                    self.update_state(power=PowerState.ON)
                else:
                    await self.client.power_off()
                    self.update_state(power=PowerState.OFF)
            elif zone == Zone.ZONE2:
                # Use zone-specific power methods
                if power_on:
                    if hasattr(self.client, "zone_power_on"):
                        await self.client.zone_power_on(zone)
                    else:
                        await self.client.zone2_power_on()
                    self.update_state(zone2_power=PowerState.ON)
                else:
                    if hasattr(self.client, "zone_power_off"):
                        await self.client.zone_power_off(zone)
                    else:
                        await self.client.zone2_power_off()
                    self.update_state(zone2_power=PowerState.OFF)
            else:
                logger.warning(f"Unsupported zone: {zone}")
                return False
                
            logger.debug(f"Set power for zone {zone_id} to {'ON' if power_on else 'OFF'}")
            return True
        except Exception as e:
            logger.error(f"Error controlling power for zone {zone_id}: {str(e)}")
            return False

    async def handle_power_on(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """
        Handle power on command.
        
        Args:
            cmd_config: Command configuration
            params: Parameters (may include zone)
            
        Returns:
            Command execution result
        """
        # If client is not initialized or not connected, reconnect first
        if not self.client or not self.state.connected:
            logger.info(f"Device {self.get_name()} not connected, attempting reconnection before power on")
            try:
                await self.setup()
            except Exception as e:
                logger.error(f"Failed to reconnect device {self.get_name()} before power on: {str(e)}")
                return self.create_command_result(
                    success=False,
                    error=f"Failed to connect to device: {str(e)}"
                )
        
        # Get zone parameter if specified
        zone_id = 1  # Default to main zone
        
        if params and "zone" in params:
            zone_param = cmd_config.get_parameter("zone")
            is_valid, zone_value, error_msg = self._validate_parameter(
                param_name="zone",
                param_value=params.get("zone"),
                param_type=zone_param.type if zone_param else "integer",
                required=False,
                action="power_on"
            )
            
            if not is_valid:
                return self.create_command_result(success=False, error=error_msg)
                
            if zone_value is not None:
                zone_id = zone_value
                
        # Get zone as enum
        zone = self._get_zone(zone_id)
        
        # Check current power state
        current_power = None
        if zone == Zone.MAIN:
            current_power = self.state.power
        elif zone == Zone.ZONE2:
            current_power = self.state.zone2_power
                
        if current_power == PowerState.ON:
            logger.debug(f"Zone {zone_id} is already powered on, skipping command")
            return self.create_command_result(
                success=True,
                message=f"Zone {zone_id} is already powered on",
                zone=zone_id
            )
        
        try:
            # Use our zone-specific helper
            success = await self._power_zone(zone_id, True)
            
            if not success:
                return self.create_command_result(
                    success=False,
                    error=f"Failed to power on zone {zone_id}"
                )
            
            # Clear any errors
            self.clear_error()
            
            # Update the last command information
            self._update_last_command("power_on", {"zone": zone_id})
            
            logger.info(f"Zone {zone_id} powered on successfully")
            
            # If main zone was powered on, refresh full device state
            if zone == Zone.MAIN:
                try:
                    # Subscribe to all properties to ensure we get updates
                    await self.client.subscribe(self.PROPERTIES_TO_MONITOR)
                    
                    # Query full device state to refresh all properties
                    updated_properties = await self._refresh_device_state()
                    
                    # Update our connected and notification status
                    self.update_state(
                        connected=True,
                        startup_complete=True,
                        notifications=True
                    )
                    
                    # Update the success message to include refreshed state info
                    if updated_properties:
                        return self.create_command_result(
                            success=True,
                            message=f"Zone {zone_id} powered on and state refreshed successfully",
                            power=PowerState.ON.value,
                            zone=zone_id,
                            updated_properties=list(updated_properties.keys())
                        )
                    else:
                        # Partial success
                        return self.create_command_result(
                            success=True,
                            message=f"Zone {zone_id} powered on, but state refresh failed",
                            power=PowerState.ON.value,
                            zone=zone_id,
                            warnings=["Failed to refresh device state"]
                        )
                except Exception as e:
                    logger.error(f"Error during post-power-on state refresh: {str(e)}")
                    # Still return success for the power-on, but include warning
                    return self.create_command_result(
                        success=True,
                        message=f"Zone {zone_id} powered on, but state refresh had errors: {str(e)}",
                        power=PowerState.ON.value,
                        zone=zone_id,
                        warnings=["State refresh incomplete, some state updates may be missing"]
                    )
            else:
                # For non-main zones, just return success
                return self.create_command_result(
                    success=True,
                    message=f"Zone {zone_id} powered on successfully",
                    zone=zone_id,
                    zone2_power=PowerState.ON.value if zone == Zone.ZONE2 else None
                )
                
        except Exception as e:
            error_message = f"Failed to power on zone {zone_id}: {str(e)}"
            logger.error(error_message)
            self.set_error(error_message)
            return self.create_command_result(
                success=False,
                error=error_message
            )
        
    async def handle_power_off(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """
        Handle power off command.
        
        Args:
            cmd_config: Command configuration
            params: Parameters (may include zone)
            
        Returns:
            Command execution result
        """
        # Get zone parameter if specified
        zone_id = 1  # Default to main zone
        
        if params and "zone" in params:
            zone_param = cmd_config.get_parameter("zone")
            is_valid, zone_value, error_msg = self._validate_parameter(
                param_name="zone",
                param_value=params.get("zone"),
                param_type=zone_param.type if zone_param else "integer",
                required=False,
                action="power_off"
            )
            
            if not is_valid:
                return self.create_command_result(success=False, error=error_msg)
                
            if zone_value is not None:
                zone_id = zone_value
                
        # Get zone as enum
        zone = self._get_zone(zone_id)
        
        # Check current power state
        current_power = None
        if zone == Zone.MAIN:
            current_power = self.state.power
        elif zone == Zone.ZONE2:
            current_power = self.state.zone2_power
                
        if current_power == PowerState.OFF:
            logger.debug(f"Zone {zone_id} is already powered off, skipping command")
            return self.create_command_result(
                success=True,
                message=f"Zone {zone_id} is already powered off",
                zone=zone_id
            )
        
        try:
            # Use our zone-specific helper
            success = await self._power_zone(zone_id, False)
            
            if not success:
                return self.create_command_result(
                    success=False,
                    error=f"Failed to power off zone {zone_id}"
                )
            
            # Clear any errors
            self.clear_error()
            
            # Update the last command information
            self._update_last_command("power_off", {"zone": zone_id})
            
            if zone == Zone.MAIN:
                return self.create_command_result(
                    success=True,
                    message=f"Zone {zone_id} powered off successfully",
                    power=PowerState.OFF.value,
                    zone=zone_id
                )
            else:
                return self.create_command_result(
                    success=True,
                    message=f"Zone {zone_id} powered off successfully",
                    zone=zone_id,
                    zone2_power=PowerState.OFF.value if zone == Zone.ZONE2 else None
                )
        except Exception as e:
            error_message = f"Failed to power off zone {zone_id}: {str(e)}"
            logger.error(error_message)
            self.set_error(error_message)
            return self.create_command_result(
                success=False,
                error=error_message
            )
        
    async def handle_message(self, topic: str, payload: str) -> Optional[CommandResult]:
        """
        Handle incoming MQTT messages for this device.
        
        Args:
            topic: MQTT topic
            payload: Message payload
            
        Returns:
            Command execution result or None if no handler was found
        """
        logger.debug(f"Device {self.get_name()} received message on {topic}: {payload}")
        
        try:
            # Find matching command configuration
            matching_commands: List[Tuple[str, StandardCommandConfig]] = []
            
            for cmd_name, cmd_config in self.get_available_commands().items():
                # Only use properly typed StandardCommandConfig objects
                if isinstance(cmd_config, StandardCommandConfig) and cmd_config.topic == topic:
                    matching_commands.append((cmd_name, cmd_config))
            
            if not matching_commands:
                logger.warning(f"No command configuration found for topic: {topic}")
                return None
            
            # Process each matching command configuration found for the topic
            for cmd_name, cmd_config in matching_commands:
                # Process parameters if defined
                params: Dict[str, Any] = {}
                
                # Get parameters definitions
                param_definitions: List[CommandParameterDefinition] = cmd_config.params or []
                
                if param_definitions:
                    # Try to parse payload as JSON
                    try:
                        params = json.loads(payload)
                    except json.JSONDecodeError:
                        # For single parameter commands, try to map raw payload to the first parameter
                        if len(param_definitions) == 1:
                            param_def = param_definitions[0]
                            param_name = param_def.name
                            param_type = param_def.type
                            required = param_def.required
                            min_value = getattr(param_def, 'min', None)
                            max_value = getattr(param_def, 'max', None)
                            
                            # Use the validation helper to convert and validate the parameter
                            is_valid, converted_value, error_message = self._validate_parameter(
                                param_name=param_name,
                                param_value=payload,
                                param_type=param_type,
                                required=required,
                                min_value=min_value,
                                max_value=max_value,
                                action=cmd_name
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
                
                # Get the handler method from registered handlers
                handler = self._action_handlers.get(cmd_name)
                if handler:
                    logger.debug(f"Found handler for command {cmd_name}")
                    try:
                        return await handler(cmd_config=cmd_config, params=params)
                    except Exception as e:
                        error_message = f"Error executing handler for {cmd_name}: {str(e)}"
                        logger.error(error_message)
                        self.set_error(error_message)
                        return self.create_command_result(success=False, error=error_message)
                else:
                    logger.warning(f"No handler found for command: {cmd_name}")
            
            # If we got here, no matching handler was found or executed            
            return self.create_command_result(
                success=False, 
                error=f"No valid handler found for topic: {topic}"
            )
            
        except Exception as e:
            error_message = f"Unexpected error handling message on topic {topic}: {str(e)}"
            logger.error(error_message)
            self.set_error(error_message)
            return self.create_command_result(success=False, error=error_message)
    
    async def handle_reconnect(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """Handle reconnection request.
        
        Args:
            cmd_config: Command configuration
            params: Parameters (unused)
            
        Returns:
            Command execution result
        """
        logger.info(f"Reconnection requested for device: {self.get_name()}")
        
        try:
            # Disconnect if currently connected
            if self.client and self.state.connected:
                logger.info(f"Disconnecting before reconnection for: {self.get_name()}")
                
                # Let the library handle disconnection
                await self.client.disconnect()
                
                # Update state to reflect disconnection
                self.update_state(
                    connected=False,
                    notifications=False
                )
                
                logger.info(f"Successfully disconnected {self.get_name()} for reconnection")
            
            # Re-initialize - setup creates a new client and connects
            success = await self.setup()
            
            if success:
                self.clear_error()
                logger.info(f"Reconnection successful for: {self.get_name()}")
                return self.create_command_result(
                    success=True, 
                    message=f"Successfully reconnected to {self.get_name()}"
                )
            else:
                error_msg = f"Reconnection failed for: {self.get_name()}"
                logger.error(error_msg)
                return self.create_command_result(success=False, error=error_msg)
        except Exception as e:
            error_msg = f"Error during reconnection: {str(e)}"
            logger.error(error_msg)
            self.set_error(error_msg)
            return self.create_command_result(success=False, error=error_msg)

    def update_state(self, **kwargs) -> None:
        """
        Update the device state with the provided values.
        
        Args:
            **kwargs: State values to update
        """
        # Convert string power states to enum values if needed
        if 'power' in kwargs and isinstance(kwargs['power'], str):
            power_value = kwargs['power'].lower()
            kwargs['power'] = PowerState.ON if power_value == 'on' else PowerState.OFF if power_value == 'off' else PowerState.UNKNOWN
            
        if 'zone2_power' in kwargs and isinstance(kwargs['zone2_power'], str):
            zone2_value = kwargs['zone2_power'].lower()
            kwargs['zone2_power'] = PowerState.ON if zone2_value == 'on' else PowerState.OFF if zone2_value == 'off' else PowerState.UNKNOWN
            
        # Call the parent update_state method
        super().update_state(**kwargs)

    def _update_last_command(self, action: str, params: Dict[str, Any] = None):
        """Update last command in the device state."""
        # Create a LastCommand model with current information
        last_command = LastCommand(
            action=action,
            source="api",
            timestamp=datetime.now(),
            params=params
        )
        # Store the LastCommand model directly in the state
        self.update_state(last_command=last_command)
        
    def _validate_parameter(self, 
                           param_name: str, 
                           param_value: Any, 
                           param_type: str, 
                           required: bool = True, 
                           min_value: Optional[float] = None, 
                           max_value: Optional[float] = None, 
                           action: str = "") -> Tuple[bool, Any, Optional[str]]:
        """Validate a parameter against its definition and convert to correct type.
        
        Args:
            param_name: Name of the parameter
            param_value: Value of the parameter
            param_type: Expected type ('string', 'integer', 'float', 'boolean', 'range')
            required: Whether the parameter is required
            min_value: Minimum value (for numeric types)
            max_value: Maximum value (for numeric types)
            action: Action name for error messages
            
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

    def _register_property_callback(self, property: Property):
        """Register a callback for a specific property change.
        
        Args:
            property: The property to monitor for changes
        """
        if not self.client:
            return
            
        # Use the new decorator pattern for callbacks
        @self.client.on(property)
        async def property_callback(value):
            # Pass to our property change handler with property as enum
            logger.debug(f"Callback triggered for {property.value} = {value}")
            self._handle_property_change(property.value, None, value)
            
        logger.debug(f"Registered callback for property {property.value}")

    # Add zone-specific helpers
    def _get_zone(self, zone_id: Union[int, str] = 1) -> Zone:
        """Get the Zone enum corresponding to the zone ID.
        
        Args:
            zone_id: Zone ID (1 for main, 2 for zone2)
            
        Returns:
            Zone enum value
        """
        try:
            zone_id = int(zone_id)
            if zone_id == 1:
                return Zone.MAIN
            elif zone_id == 2:
                return Zone.ZONE2
            else:
                logger.warning(f"Invalid zone ID: {zone_id}, defaulting to main zone")
                return Zone.MAIN
        except (ValueError, TypeError):
            if str(zone_id).lower() == "main":
                return Zone.MAIN
            elif str(zone_id).lower() in ("zone2", "zone_2"):
                return Zone.ZONE2
            else:
                logger.warning(f"Invalid zone ID: {zone_id}, defaulting to main zone")
                return Zone.MAIN

    async def _refresh_device_state(self) -> Dict[str, Any]:
        """
        Refresh the full device state by querying all important properties.
        
        This is used after powering on from standby to ensure state is in sync.
        
        Returns:
            Dict[str, Any]: Dictionary of updated properties and their values
        """
        if not self.client:
            logger.warning("Cannot refresh device state: client not initialized")
            return {}
            
        try:
            # Query all properties we care about using the status API
            properties_to_query = [
                Property.POWER,              # Main zone power
                Property.ZONE2_POWER,        # Zone 2 power
                Property.VOLUME,             # Main volume
                Property.MUTE,               # Mute status
                Property.INPUT,              # Current input
                Property.AUDIO_INPUT,        # Audio input
                Property.VIDEO_INPUT,        # Video input
                Property.AUDIO_BITSTREAM,    # Audio bitstream format
                Property.AUDIO_MODE          # Audio processing mode
            ]
            
            # Use the status method to get all properties at once
            result = await self.client.status(*properties_to_query)
            
            # Process and update our state with the results
            updated_properties = {}
            for prop, value in result.items():
                # Convert property enum to string for our internal handling
                prop_name = prop.value
                
                # Process the value with our helper
                processed_value = self._process_property_value(prop_name, value)
                updated_properties[prop_name] = processed_value
                
                # Handle input property specially
                if prop == Property.INPUT:
                    self.update_state(input_source=value)
                else:
                    self.update_state(**{prop_name: processed_value})
                    
            logger.debug(f"Device state refresh completed for {self.get_name()} ({len(updated_properties)}/{len(properties_to_query)} properties)")
            return updated_properties
            
        except Exception as e:
            logger.warning(f"Error refreshing device state: {str(e)}")
            return {}

    def _handle_property_change(self, property_name: str, old_value: Any, new_value: Any) -> None:
        """Handle property change events from the device state.
        
        Args:
            property_name: Name of the property that changed
            old_value: Previous value of the property
            new_value: New value of the property
        """
        logger.debug(f"Property change: {property_name} = {new_value}")
        
        # Process the value with our helper
        processed_value = self._process_property_value(property_name, new_value)
        
        # Map property changes to our state model
        updates = {}
        
        if property_name == "power":
            updates["power"] = processed_value
        elif property_name == "zone2_power":
            updates["zone2_power"] = processed_value
        elif property_name == "volume":
            updates["volume"] = processed_value
        elif property_name == "mute":
            updates["mute"] = processed_value
        elif property_name == "input":
            updates["input_source"] = new_value  # Use raw value for input_source
        elif property_name == "video_input":
            updates["video_input"] = new_value
        elif property_name == "audio_input":
            updates["audio_input"] = new_value
        elif property_name == "audio_bitstream":
            updates["audio_bitstream"] = new_value
        elif property_name == "audio_mode":
            updates["audio_mode"] = new_value
            
        # Apply state updates if any
        if updates:
            self.update_state(**updates)

    def _process_property_value(self, property_name: str, value: Any) -> Any:
        """
        Process and convert property values to the correct type.
        
        Args:
            property_name: Name of the property
            value: Property value to convert
            
        Returns:
            Converted property value
        """
        if value is None:
            return None
            
        if property_name in ["power", "zone2_power"]:
            # Convert power values to our PowerState enum
            if isinstance(value, str):
                return PowerState.ON if value.lower() == "on" else PowerState.OFF if value.lower() == "off" else PowerState.UNKNOWN
            return value  # Already converted
        elif property_name == "volume":
            # Convert volume to float
            try:
                return float(value)
            except (ValueError, TypeError):
                return 0.0
        elif property_name == "mute":
            # Convert mute to boolean
            if isinstance(value, str):
                return value.lower() in ("on", "true", "1", "yes")
            return bool(value)
        
        # For other properties, return as is
        return value

    async def _set_zone_volume(self, zone_id: Union[int, str], level: float) -> bool:
        """Set volume for a specific zone.
        
        Args:
            zone_id: Zone ID (1 for main, 2 for zone2)
            level: Volume level in dB (-96.0 to 0.0)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.client:
            logger.warning("Cannot set volume: client not initialized")
            return False
            
        try:
            # Get the zone enum
            zone = self._get_zone(zone_id)
            
            # Set volume for the specified zone
            if zone == Zone.MAIN:
                await self.client.set_volume(level)
                self.update_state(volume=level)
            elif zone == Zone.ZONE2:
                # Use the set_zone_volume method if available, otherwise fall back to zone2 setting
                if hasattr(self.client, "set_zone_volume"):
                    await self.client.set_zone_volume(zone, level)
                else:
                    await self.client.set_zone2_volume(level)
                self.update_state(zone2_volume=level)
            else:
                logger.warning(f"Unsupported zone: {zone}")
                return False
                
            logger.debug(f"Set volume for zone {zone_id} to {level} dB")
            return True
        except Exception as e:
            logger.error(f"Error setting volume for zone {zone_id}: {str(e)}")
            return False

    async def handle_set_volume(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """
        Handle setting volume level.
        
        Args:
            cmd_config: Command configuration
            params: Parameters containing volume level
            
        Returns:
            Command execution result
        """
        # Validate parameters
        if not params:
            return self.create_command_result(success=False, error="Missing volume parameters")
        
        # Get and validate level parameter
        level_param = cmd_config.get_parameter("level")
        is_valid, level, error_msg = self._validate_parameter(
            param_name="level",
            param_value=params.get("level"),
            param_type=level_param.type if level_param else "range",
            min_value=level_param.min if level_param else -96.0,
            max_value=level_param.max if level_param else 0.0,
            action="set_volume"
        )
        
        if not is_valid:
            return self.create_command_result(success=False, error=error_msg)
            
        # Get zone parameter if specified
        zone_param = cmd_config.get_parameter("zone")
        zone_id = 1  # Default to main zone
        
        if zone_param:
            is_valid, zone_value, error_msg = self._validate_parameter(
                param_name="zone",
                param_value=params.get("zone"),
                param_type=zone_param.type if zone_param else "integer",
                required=False,
                action="set_volume"
            )
            
            if not is_valid:
                return self.create_command_result(success=False, error=error_msg)
                
            if zone_value is not None:
                zone_id = zone_value
        
        try:
            # Use our zone-specific helper
            success = await self._set_zone_volume(zone_id, level)
            
            if not success:
                return self.create_command_result(
                    success=False,
                    error=f"Failed to set volume for zone {zone_id}"
                )
            
            # Clear any errors
            self.clear_error()
            
            # Update the last command information
            self._update_last_command("set_volume", {"level": level, "zone": zone_id})
            
            return self.create_command_result(
                success=True,
                message=f"Volume for zone {zone_id} set to {level} dB successfully",
                volume=level,
                zone=zone_id
            )
        except Exception as e:
            error_message = f"Failed to set volume: {str(e)}"
            logger.error(error_message)
            self.set_error(error_message)
            return self.create_command_result(
                success=False,
                error=error_message
            )
            
    async def _toggle_zone_mute(self, zone_id: Union[int, str]) -> Tuple[bool, bool]:
        """Toggle mute state for a specific zone.
        
        Args:
            zone_id: Zone ID (1 for main, 2 for zone2)
            
        Returns:
            Tuple of (success status, new mute state)
        """
        if not self.client:
            logger.warning("Cannot toggle mute: client not initialized")
            return False, False
            
        try:
            # Get the zone enum
            zone = self._get_zone(zone_id)
            
            # Toggle mute for the specified zone
            if zone == Zone.MAIN:
                await self.client.mute()
                current_mute = self.state.mute
                new_mute = not current_mute if current_mute is not None else True
                self.update_state(mute=new_mute)
            elif zone == Zone.ZONE2:
                # Use the zone_mute method if available, otherwise fall back
                if hasattr(self.client, "zone_mute"):
                    await self.client.zone_mute(zone)
                else:
                    await self.client.zone2_mute()
                current_mute = getattr(self.state, "zone2_mute", None)
                new_mute = not current_mute if current_mute is not None else True
                self.update_state(zone2_mute=new_mute)
            else:
                logger.warning(f"Unsupported zone: {zone}")
                return False, False
                
            logger.debug(f"Toggled mute for zone {zone_id} to {new_mute}")
            return True, new_mute
        except Exception as e:
            logger.error(f"Error toggling mute for zone {zone_id}: {str(e)}")
            return False, False

    async def handle_mute_toggle(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """
        Handle toggling mute state.
        
        Args:
            cmd_config: Command configuration
            params: Parameters including optional zone
            
        Returns:
            Command execution result
        """
        # Get zone parameter if specified
        zone_id = 1  # Default to main zone
        
        if params and "zone" in params:
            zone_param = cmd_config.get_parameter("zone")
            is_valid, zone_value, error_msg = self._validate_parameter(
                param_name="zone",
                param_value=params.get("zone"),
                param_type=zone_param.type if zone_param else "integer",
                required=False,
                action="mute_toggle"
            )
            
            if not is_valid:
                return self.create_command_result(success=False, error=error_msg)
                
            if zone_value is not None:
                zone_id = zone_value
        
        try:
            # Use our zone-specific helper
            success, new_mute = await self._toggle_zone_mute(zone_id)
            
            if not success:
                return self.create_command_result(
                    success=False,
                    error=f"Failed to toggle mute for zone {zone_id}"
                )
            
            # Clear any errors
            self.clear_error()
            
            # Update the last command information
            self._update_last_command("mute_toggle", {"zone": zone_id})
            
            return self.create_command_result(
                success=True,
                message=f"Mute for zone {zone_id} {'enabled' if new_mute else 'disabled'} successfully",
                mute=new_mute,
                zone=zone_id
            )
        except Exception as e:
            error_message = f"Failed to toggle mute: {str(e)}"
            logger.error(error_message)
            self.set_error(error_message)
            return self.create_command_result(
                success=False,
                error=error_message
            )

