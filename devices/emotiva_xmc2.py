import logging
import json
from typing import Dict, Any, List, Optional, Union, Callable, Awaitable, Tuple, TypeVar, cast, Coroutine, Literal, Protocol
from pymotivaxmc2 import EmotivaController
from pymotivaxmc2 import EmotivaConfig as PyEmotivaConfig
from pymotivaxmc2.protocol import CommandFormatter, ResponseParser
from pymotivaxmc2.network import SocketManager, EmotivaNetworkDiscovery
from pymotivaxmc2.notifier import NotificationRegistry, NotificationListener, EmotivaNotification
from pymotivaxmc2.state import DeviceState, PropertyChangeEvent
from datetime import datetime
import asyncio
from enum import Enum, auto

from devices.base_device import BaseDevice
from app.schemas import EmotivaXMC2State, LastCommand, EmotivaConfig, EmotivaXMC2DeviceConfig, StandardCommandConfig, CommandParameterDefinition
from app.types import StateT, CommandResult, CommandResponse, ActionHandler

logger = logging.getLogger(__name__)

# Define enums for strongly typed states
class PowerState(str, Enum):
    """Power state enum for eMotiva device."""
    ON = "on"
    OFF = "off"
    UNKNOWN = "unknown"

# Type hint for device command functions
DeviceCommandFunc = Callable[[], Awaitable[Dict[str, Any]]]

class EMotivaXMC2(BaseDevice[EmotivaXMC2State], NotificationListener):
    """eMotiva XMC2 processor device implementation."""
    
    def __init__(self, config: EmotivaXMC2DeviceConfig, mqtt_client=None):
        super().__init__(config, mqtt_client)
        
        self.client: Optional[EmotivaController] = None
        
        # Initialize device state with Pydantic model
        self.state: EmotivaXMC2State = EmotivaXMC2State(
            device_id=self.config.device_id,
            device_name=self.config.device_name,
            power=None,
            zone2_power=None,
            source_status=None,
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
            emotiva_config: EmotivaConfig = self.config.emotiva
            
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
            
            # Prepare configuration with optional parameters
            emotiva_options = {
                "timeout": emotiva_config.timeout,
                "max_retries": emotiva_config.max_retries,
                "retry_delay": emotiva_config.retry_delay,
                "keepalive_interval": emotiva_config.update_interval
            }
            
            # Create EmotivaController with proper configuration
            config = PyEmotivaConfig(
                ip=host,
                **{k: v for k, v in emotiva_options.items() if v is not None}
            )
            
            self.client = EmotivaController(config=config)
            
            # Configure state listener for automatic state updates
            self.client.state.add_property_listener(self._handle_property_change)
            
            # Register as notification listener
            self.client.notifier.register_listener(self)
            
            # Attempt to discover the device on the network
            logger.info(f"Attempting to discover eMotiva device at {host}")
            discovery_result = await self.client.discovery.discover_devices(
                timeout=emotiva_config.timeout or 5.0
            )
            
            # Check discovery result
            if discovery_result and discovery_result.status == "success":
                logger.info(f"Successfully discovered eMotiva device: {discovery_result}")
                
                # Subscribe to notification topics
                default_notifications = [
                    "power", "zone2_power", "volume", "input", 
                    "audio_input", "video_input", "audio_bitstream",
                    "mute", "mode"
                ]
                
                subscription_result = await self.client.notifier.subscribe(default_notifications)
                logger.info(f"Notification subscription result: {subscription_result}")
                
                # Query initial device status through command executor
                try:
                    logger.info(f"Querying initial power status for {self.get_name()}")
                    power_response = await self.client.command_executor.execute_command(
                        command="get_power",
                        timeout=emotiva_config.timeout
                    )
                    
                    if power_response.is_successful:
                        power_value = power_response.value
                        power_state = PowerState.ON if power_value == "on" else PowerState.OFF if power_value == "off" else PowerState.UNKNOWN
                        self.update_state(power=power_state)
                        logger.info(f"Initial power state: {power_state}")
                    else:
                        logger.warning(f"Failed to get initial power state: {power_response.error}")
                except Exception as e:
                    logger.warning(f"Error getting power status: {str(e)}")
                
                try:
                    logger.info(f"Querying initial zone2 power status for {self.get_name()}")
                    zone2_response = await self.client.command_executor.execute_command(
                        command="get_zone2_power",
                        timeout=emotiva_config.timeout
                    )
                    
                    if zone2_response.is_successful:
                        zone2_value = zone2_response.value
                        zone2_state = PowerState.ON if zone2_value == "on" else PowerState.OFF if zone2_value == "off" else PowerState.UNKNOWN
                        self.update_state(zone2_power=zone2_state)
                        logger.info(f"Initial zone2 power state: {zone2_state}")
                    else:
                        logger.warning(f"Failed to get initial zone2 power state: {zone2_response.error}")
                except Exception as e:
                    logger.warning(f"Error getting zone2 power status: {str(e)}")
                
                # Update state with successful connection
                self.clear_error()  # Clear any previous errors
                self.update_state(
                    connected=True,
                    ip_address=host,
                    startup_complete=True,
                    notifications=True
                )
                
                return True
            else:
                # Handle discovery failure
                error_message = discovery_result.error if discovery_result else "No response from device"
                logger.error(f"Error discovering eMotiva device at {host}: {error_message}")
                
                # We can still try to use the device even if discovery failed
                if emotiva_config.force_connect:
                    logger.warning(f"Force connect enabled, continuing with setup despite discovery failure")
                    
                    # Update state
                    self.update_state(
                        connected=True,
                        ip_address=host,
                        startup_complete=True,
                        notifications=False
                    )
                    
                    # Set error but don't fail setup
                    self.set_error(f"Discovery failed, using forced connection: {error_message}")
                    
                    return True
                else:
                    self.set_error(error_message)
                    return False

        except ConnectionError as e:
            logger.error(f"Connection error initializing eMotiva XMC2 device {self.get_name()}: {str(e)}")
            self.set_error(f"Connection error: {str(e)}")
            return False
        except TimeoutError as e:
            logger.error(f"Timeout error initializing eMotiva XMC2 device {self.get_name()}: {str(e)}")
            self.set_error(f"Timeout error: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize eMotiva XMC2 device {self.get_name()}: {str(e)}")
            self.set_error(str(e))
            return False
            
    def _handle_property_change(self, event: PropertyChangeEvent) -> None:
        """Handle property change events from the device state.
        
        Args:
            event: Property change event containing property name, old value, and new value
        """
        property_name = event.property_name
        new_value = event.new_value
        logger.debug(f"Property change: {property_name} = {new_value}")
        
        # Map property changes to our state model
        updates = {}
        
        if property_name == "power":
            power_state = PowerState.ON if new_value == "on" else PowerState.OFF if new_value == "off" else PowerState.UNKNOWN
            updates["power"] = power_state
        elif property_name == "zone2_power":
            zone2_state = PowerState.ON if new_value == "on" else PowerState.OFF if new_value == "off" else PowerState.UNKNOWN
            updates["zone2_power"] = zone2_state
        elif property_name == "volume":
            updates["volume"] = float(new_value) if new_value is not None else 0
        elif property_name == "mute":
            updates["mute"] = bool(new_value)
        elif property_name == "input":
            updates["input_source"] = new_value
            updates["source_status"] = self._get_source_display_name(new_value)
        elif property_name == "video_input":
            updates["video_input"] = new_value
        elif property_name == "audio_input":
            updates["audio_input"] = new_value
        elif property_name == "audio_bitstream":
            updates["audio_bitstream"] = new_value
        elif property_name == "mode":
            updates["audio_mode"] = new_value
            
        # Apply state updates if any
        if updates:
            self.update_state(**updates)
            
    async def on_notification(self, notification: EmotivaNotification) -> None:
        """Process notifications from the eMotiva device.
        
        Args:
            notification: Notification object from the device
        """
        logger.debug(f"Received notification from eMotiva device: {notification}")
        
        # Create a background task for publishing
        notification_data = notification.to_dict()
        asyncio.create_task(self.publish_progress(json.dumps(notification_data)))
        
        try:
            updates: Dict[str, Any] = {}
            
            # Process based on notification type
            notification_type = notification.type
            value = notification.value
            
            if notification_type == "power":
                power_state = PowerState.ON if value == "on" else PowerState.OFF if value == "off" else PowerState.UNKNOWN
                updates["power"] = power_state
                logger.info(f"Power state updated: {power_state}")
                
            elif notification_type == "zone2_power":
                zone2_state = PowerState.ON if value == "on" else PowerState.OFF if value == "off" else PowerState.UNKNOWN
                updates["zone2_power"] = zone2_state
                logger.info(f"Zone 2 power state updated: {zone2_state}")
                
            elif notification_type == "volume":
                updates["volume"] = float(value) if value is not None else 0
                logger.debug(f"Volume updated: {value}")
                
            elif notification_type == "mute":
                # Convert string "true"/"false" to boolean if needed
                if isinstance(value, str):
                    value = value.lower() == "true"
                updates["mute"] = bool(value)
                logger.debug(f"Mute state updated: {value}")
                
            elif notification_type == "input":
                updates["input_source"] = value
                # Also set the source_status with the display name
                updates["source_status"] = self._get_source_display_name(value)
                logger.info(f"Input source updated: {value} (display name: {updates['source_status']})")
                
            elif notification_type == "video_input":
                updates["video_input"] = value
                logger.debug(f"Video input updated: {value}")
                
            elif notification_type == "audio_input":
                updates["audio_input"] = value
                logger.debug(f"Audio input updated: {value}")
                
            elif notification_type == "audio_bitstream":
                updates["audio_bitstream"] = value
                logger.debug(f"Audio bitstream updated: {value}")
                
            elif notification_type == "mode":
                updates["audio_mode"] = value
                logger.debug(f"Audio mode updated: {value}")
            
            # Update device state with notification data and clear any errors
            if updates:
                self.clear_error()
                self.update_state(**updates)
        except Exception as e:
            logger.error(f"Error processing notification: {str(e)}")
    
    async def shutdown(self) -> bool:
        """Cleanup device resources and properly shut down connections."""
        if not self.client:
            logger.info(f"No client initialized for {self.get_name()}, nothing to shut down")
            return True
            
        logger.info(f"Starting shutdown for eMotiva XMC2 device: {self.get_name()}")
        
        # Track if we completed all cleanup steps
        all_cleanup_successful = True
        
        try:
            # Step 1: Unregister from notifications
            try:
                logger.debug(f"Unregistering from notification listener for {self.get_name()}")
                # Unregister from notification registry
                if hasattr(self.client, 'notifier') and self.client.notifier:
                    try:
                        # Give a short timeout for unregistering
                        await asyncio.wait_for(
                            self.client.notifier.unregister_listener(self),
                            timeout=1.0
                        )
                        logger.info(f"Successfully unregistered from notifications for {self.get_name()}")
                    except asyncio.TimeoutError:
                        logger.warning(f"Notification unregister timed out for {self.get_name()}")
                    except Exception as e:
                        logger.warning(f"Error unregistering from notifications for {self.get_name()}: {str(e)}")
                        all_cleanup_successful = False
            except Exception as e:
                logger.warning(f"Exception during notification unregistration: {str(e)}")
                all_cleanup_successful = False
            
            # Step 2: Remove state listeners
            try:
                logger.debug(f"Removing state listeners for {self.get_name()}")
                if hasattr(self.client, 'state') and self.client.state:
                    self.client.state.remove_property_listener(self._handle_property_change)
                    logger.info(f"Successfully removed state listeners for {self.get_name()}")
            except Exception as e:
                logger.warning(f"Exception during state listener removal: {str(e)}")
                all_cleanup_successful = False
            
            # Step 3: Close the client
            try:
                logger.debug(f"Closing controller for {self.get_name()}")
                await asyncio.wait_for(
                    self.client.close(),
                    timeout=2.0
                )
                logger.info(f"Successfully closed controller for {self.get_name()}")
            except asyncio.TimeoutError:
                logger.warning(f"Controller close timed out for {self.get_name()}")
                all_cleanup_successful = False
            except Exception as e:
                logger.warning(f"Error closing controller for {self.get_name()}: {str(e)}")
                all_cleanup_successful = False
            
            # Final cleanup - update the state regardless of success
            if all_cleanup_successful:
                self.clear_error()
            else:
                self.set_error("Partial shutdown completed with errors")
                
            self.update_state(
                connected=False,
                notifications=False
            )
            
            # Release client reference
            self.client = None
            
            logger.info(f"eMotiva XMC2 device {self.get_name()} shutdown {'' if all_cleanup_successful else 'partially '}complete")
            return True
        except Exception as e:
            logger.error(f"Unexpected error during {self.get_name()} shutdown: {str(e)}")
            
            # Still update the state as disconnected even after errors
            self.set_error(f"Shutdown error: {str(e)}")
            self.update_state(
                connected=False,
                notifications=False
            )
            
            # Release client reference
            self.client = None
            
            return False
    
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
    
    async def _execute_device_command(self, 
                                     action: str,
                                     command: str,
                                     value: Any = None,
                                     params: Dict[str, Any] = None,
                                     notification_topics: List[str] = None,
                                     state_updates: Dict[str, Any] = None) -> CommandResult:
        """Execute a device command with standardized error handling and response creation.
        
        Args:
            action: The name of the action being performed
            command: The command name to execute
            value: Optional value parameter for the command
            params: The parameters for the command
            notification_topics: List of notification topics to subscribe to before executing the command
            state_updates: Dictionary of state updates to apply on success
            
        Returns:
            CommandResult: A standardized response dictionary
        """
        try:
            if not self.client:
                logger.error(f"Client not initialized for action: {action}")
                return self.create_command_result(success=False, error="Client not initialized")
            
            # Subscribe to notifications if provided
            if notification_topics:
                try:
                    await self.client.notifier.subscribe(notification_topics)
                except Exception as e:
                    logger.warning(f"Could not subscribe to notifications for {action}: {str(e)}")
            
            # Execute the command using the command executor
            try:
                # Prepare command execution options
                execute_options = {
                    "command": command,
                    "retries": self.config.emotiva.max_retries,
                    "timeout": self.config.emotiva.timeout
                }
                
                # Add value if provided
                if value is not None:
                    execute_options["value"] = value
                    
                # Execute through the command executor
                response = await self.client.command_executor.execute_command(**execute_options)
                
                # Check response
                if response.is_successful:
                    # Update state with provided updates
                    if state_updates:
                        # Clear any previous errors
                        self.clear_error()
                        self.update_state(**state_updates)
                    
                    # Record last command
                    self._update_last_command(action, params)
                    
                    # Create success message
                    message = f"{action} command executed successfully"
                    
                    logger.info(f"Successfully executed {action} on eMotiva XMC2: {self.get_name()}")
                    return self.create_command_result(success=True, message=message)
                else:
                    # Get error from response
                    error_message = response.error or f"Unknown error during {action}"
                    logger.error(f"Failed to execute {action} on eMotiva XMC2: {error_message}")
                    
                    # Update the state with the error
                    self.set_error(error_message)
                    
                    return self.create_command_result(success=False, error=error_message)
                    
            except asyncio.TimeoutError:
                logger.error(f"Timeout waiting for {action} response from {self.get_name()}")
                self.set_error("Command timeout")
                return self.create_command_result(success=False, error="Command timeout")
            except Exception as e:
                logger.error(f"Error executing {action} on eMotiva XMC2: {str(e)}")
                self.set_error(str(e))
                return self.create_command_result(success=False, error=str(e))
        except Exception as e:
            # Catch any unexpected exceptions in the command execution process
            error_message = f"Unexpected error executing {action}: {str(e)}"
            logger.error(error_message)
            self.set_error(error_message)
            return self.create_command_result(success=False, error=error_message)
    
    async def handle_power_on(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """
        Handle power on command.
        
        Args:
            cmd_config: Command configuration
            params: Parameters (unused)
            
        Returns:
            Command execution result
        """
        # Check current power state
        if self.state.power == PowerState.ON:
            logger.debug(f"Device {self.get_name()} is already powered on, skipping command")
            return self.create_command_result(
                success=True,
                message="Device is already powered on"
            )
            
        return await self._execute_device_command(
            action="power_on",
            command="power",
            value="on",
            params=params,
            notification_topics=["power"],
            state_updates={"power": PowerState.ON}
        )
    
    async def handle_power_off(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """
        Handle power off command.
        
        Args:
            cmd_config: Command configuration
            params: Parameters (unused)
            
        Returns:
            Command execution result
        """
        # Check current power state
        if self.state.power == PowerState.OFF:
            logger.debug(f"Device {self.get_name()} is already powered off, skipping command")
            return self.create_command_result(
                success=True,
                message="Device is already powered off"
            )
            
        return await self._execute_device_command(
            action="power_off",
            command="power",
            value="off",
            params=params,
            notification_topics=["power"],
            state_updates={"power": PowerState.OFF}
        )
    
    async def handle_zone2_on(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """
        Handle zone 2 power on command.
        
        Args:
            cmd_config: Command configuration
            params: Parameters (unused)
            
        Returns:
            Command execution result
        """
        # Check current zone2 power state
        if self.state.zone2_power == PowerState.ON:
            logger.debug(f"Zone 2 of device {self.get_name()} is already powered on, skipping command")
            return self.create_command_result(
                success=True,
                message="Zone 2 is already powered on"
            )
            
        return await self._execute_device_command(
            action="zone2_on",
            command="zone2_power",
            value="on",
            params=params,
            notification_topics=["zone2_power"],
            state_updates={"zone2_power": PowerState.ON}
        )
    
    async def handle_zone2_off(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """
        Handle zone 2 power off command.
        
        Args:
            cmd_config: Command configuration
            params: Parameters (unused)
            
        Returns:
            Command execution result
        """
        # Check current zone2 power state
        if self.state.zone2_power == PowerState.OFF:
            logger.debug(f"Zone 2 of device {self.get_name()} is already powered off, skipping command")
            return self.create_command_result(
                success=True,
                message="Zone 2 is already powered off"
            )
            
        return await self._execute_device_command(
            action="zone2_off",
            command="zone2_power",
            value="off",
            params=params,
            notification_topics=["zone2_power"],
            state_updates={"zone2_power": PowerState.OFF}
        )
    
    async def handle_set_volume(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """
        Handle volume setting command.
        
        Args:
            cmd_config: Command configuration
            params: Parameters containing volume level
            
        Returns:
            Command execution result
        """
        # Validate parameters
        if not params:
            return self.create_command_result(success=False, error="Missing volume parameters")
        
        # Get and validate volume parameter
        volume_param = cmd_config.get_parameter("volume")
        is_valid, volume, error_msg = self._validate_parameter(
            param_name="volume",
            param_value=params.get("volume"),
            param_type=volume_param.type if volume_param else "float",
            min_value=volume_param.min if volume_param else 0,
            max_value=volume_param.max if volume_param else 100,
            action="set_volume"
        )
        
        if not is_valid:
            return self.create_command_result(success=False, error=error_msg)
        
        # Execute the command with volume value
        result = await self._execute_device_command(
            action="set_volume",
            command="volume",
            value=volume,
            params=params,
            notification_topics=["volume"],
            state_updates={"volume": volume}
        )
        
        # Add volume information to success result
        if result.get("success", False):
            # Create a new result with additional information
            return self.create_command_result(
                success=True,
                message=f"Volume set to {volume} successfully",
                volume=volume
            )
        
        return result
    
    async def handle_set_mute(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """
        Handle mute setting command.
        
        Args:
            cmd_config: Command configuration
            params: Parameters containing mute state
            
        Returns:
            Command execution result
        """
        # Validate parameters
        if not params:
            return self.create_command_result(success=False, error="Missing mute parameters")
        
        # Get and validate mute parameter
        mute_param = cmd_config.get_parameter("state")
        is_valid, mute_state, error_msg = self._validate_parameter(
            param_name="state",
            param_value=params.get("state"),
            param_type=mute_param.type if mute_param else "boolean",
            action="set_mute"
        )
        
        if not is_valid:
            return self.create_command_result(success=False, error=error_msg)
        
        # Execute the command with mute value
        result = await self._execute_device_command(
            action="set_mute",
            command="mute",
            value="on" if mute_state else "off",
            params=params,
            notification_topics=["mute"],
            state_updates={"mute": mute_state}
        )
        
        # Add mute information to success result
        if result.get("success", False):
            # Create a new result with additional information
            return self.create_command_result(
                success=True,
                message=f"Mute set to {mute_state} successfully",
                mute=mute_state
            )
        
        return result
    
    async def handle_set_audio_mode(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """
        Handle setting audio mode.
        
        Args:
            cmd_config: Command configuration
            params: Parameters containing mode
            
        Returns:
            Command execution result
        """
        # Validate parameters
        if not params:
            return self.create_command_result(success=False, error="Missing audio mode parameters")
        
        # Get and validate mode parameter
        mode_param = cmd_config.get_parameter("mode")
        is_valid, mode, error_msg = self._validate_parameter(
            param_name="mode",
            param_value=params.get("mode"),
            param_type=mode_param.type if mode_param else "string",
            action="set_audio_mode"
        )
        
        if not is_valid:
            return self.create_command_result(success=False, error=error_msg)
        
        # Execute the command with mode value
        result = await self._execute_device_command(
            action="set_audio_mode",
            command="mode",
            value=mode,
            params=params,
            notification_topics=["mode"],
            state_updates={"audio_mode": mode}
        )
        
        # Add mode information to success result
        if result.get("success", False):
            return self.create_command_result(
                success=True,
                message=f"Audio mode set to {mode} successfully",
                mode=mode
            )
        
        return result
    
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
    
    def _get_source_display_name(self, source_id: Optional[str]) -> Optional[str]:
        """
        Convert numeric source IDs to their display names.
        
        Args:
            source_id: The source ID to convert
            
        Returns:
            The display name for the source ID, or the original source ID if no mapping exists
        """
        if not source_id:
            return None
            
        # Map numeric source IDs to their display names
        source_map = {
            "1": "Zappiti",
            "2": "Apple TV",
            "3": "DVDO"
        }
        
        # Check if source_id is in our custom mapping
        if source_id in source_map:
            return source_map[source_id]
            
        # For HDMI sources that use the hdmiX format, make them more readable
        if source_id.startswith('hdmi') and len(source_id) > 4:
            try:
                hdmi_number = int(source_id[4:])
                return f"HDMI {hdmi_number}"
            except ValueError:
                pass
                
        # Return the original value if no mapping found
        return source_id
    
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

    # Restore input source handlers with improved implementation
    async def handle_zappiti(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """
        Switch to Zappiti input.
        
        Args:
            cmd_config: Command configuration
            params: Parameters (unused)
            
        Returns:
            Command execution result
        """
        source_name = "Zappiti"
        source_id = "1"
        
        result = await self._execute_device_command(
            action=f"switch_to_{source_name.lower()}",
            command="input",
            value=source_id,
            params={"source_name": source_name, "source_id": source_id},
            notification_topics=["input"],
            state_updates={
                "input_source": source_id,
                "source_status": source_name
            }
        )
        
        # Add input information to success result
        if result.get("success", False):
            return self.create_command_result(
                success=True,
                message=f"Input switched to {source_name} successfully",
                input=source_id,
                display_name=source_name
            )
        
        return result
        
    async def handle_apple_tv(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """
        Switch to Apple TV input.
        
        Args:
            cmd_config: Command configuration
            params: Parameters (unused)
            
        Returns:
            Command execution result
        """
        source_name = "Apple TV"
        source_id = "2"
        
        result = await self._execute_device_command(
            action=f"switch_to_apple_tv",
            command="input",
            value=source_id,
            params={"source_name": source_name, "source_id": source_id},
            notification_topics=["input"],
            state_updates={
                "input_source": source_id,
                "source_status": source_name
            }
        )
        
        # Add input information to success result
        if result.get("success", False):
            return self.create_command_result(
                success=True,
                message=f"Input switched to {source_name} successfully",
                input=source_id,
                display_name=source_name
            )
        
        return result
        
    async def handle_dvdo(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """
        Switch to DVDO input.
        
        Args:
            cmd_config: Command configuration
            params: Parameters (unused)
            
        Returns:
            Command execution result
        """
        source_name = "DVDO"
        source_id = "3"
        
        result = await self._execute_device_command(
            action=f"switch_to_dvdo",
            command="input",
            value=source_id,
            params={"source_name": source_name, "source_id": source_id},
            notification_topics=["input"],
            state_updates={
                "input_source": source_id,
                "source_status": source_name
            }
        )
        
        # Add input information to success result
        if result.get("success", False):
            return self.create_command_result(
                success=True,
                message=f"Input switched to {source_name} successfully",
                input=source_id,
                display_name=source_name
            )
        
        return result
    
    async def handle_set_input(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """
        Handle setting input source by input ID.
        
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
        
        # Get display name for the input
        display_name = self._get_source_display_name(input_id)
        
        # Execute the command with input value
        result = await self._execute_device_command(
            action="set_input",
            command="input",
            value=input_id,
            params={"input": input_id},
            notification_topics=["input"],
            state_updates={
                "input_source": input_id,
                "source_status": display_name
            }
        )
        
        # Add input information to success result
        if result.get("success", False):
            return self.create_command_result(
                success=True,
                message=f"Input set to {display_name} ({input_id}) successfully",
                input=input_id,
                display_name=display_name
            )
        
        return result
    
    async def _switch_input_source(self, source_name: str, source_id: str) -> CommandResult:
        """
        Helper function to switch input sources.
        
        Args:
            source_name: User-friendly source name
            source_id: Input source identifier
            
        Returns:
            Command execution result
        """
        result = await self._execute_device_command(
            action=f"switch_to_{source_name.lower().replace(' ', '_')}",
            command="input",
            value=source_id,
            params={"source_name": source_name, "source_id": source_id},
            notification_topics=["input"],
            state_updates={
                "input_source": source_id,
                "source_status": source_name
            }
        )
        
        # Add input information to success result
        if result.get("success", False):
            return self.create_command_result(
                success=True,
                message=f"Input switched to {source_name} successfully",
                input=source_id,
                display_name=source_name
            )
        
        return result
    
    async def handle_reconnect(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """Handle reconnection request.
        
        Args:
            cmd_config: Command configuration
            params: Parameters (unused)
            
        Returns:
            Command execution result
        """
        logger.info(f"Reconnection requested for device: {self.get_name()}")
        
        # If we're already connected, first disconnect
        if self.client and self.state.connected:
            logger.info(f"Disconnecting before reconnection for: {self.get_name()}")
            # Perform a partial shutdown without releasing the client
            try:
                # Unregister from notifications
                if hasattr(self.client, 'notifier') and self.client.notifier:
                    try:
                        await asyncio.wait_for(
                            self.client.notifier.unregister_listener(self),
                            timeout=1.0
                        )
                    except Exception as e:
                        logger.warning(f"Error unregistering notifications during reconnect: {str(e)}")
                
                # Remove state listeners
                if hasattr(self.client, 'state') and self.client.state:
                    self.client.state.remove_property_listener(self._handle_property_change)
                
                # Close client connection but don't nullify the client reference
                await asyncio.wait_for(
                    self.client.close(),
                    timeout=2.0
                )
                
                # Update state to reflect disconnection
                self.update_state(
                    connected=False,
                    notifications=False
                )
                
                logger.info(f"Successfully disconnected {self.get_name()} for reconnection")
            except Exception as e:
                logger.error(f"Error during disconnect phase of reconnect: {str(e)}")
                self.set_error(f"Reconnect error: {str(e)}")
                return self.create_command_result(success=False, error=f"Reconnect failed: {str(e)}")
        
        # Now re-initialize
        try:
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
    
    async def handle_refresh_status(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """Handle status refresh request.
        
        Args:
            cmd_config: Command configuration
            params: Parameters (unused)
            
        Returns:
            Command execution result
        """
        if not self.client:
            return self.create_command_result(success=False, error="Device not initialized")
        
        logger.info(f"Status refresh requested for device: {self.get_name()}")
        
        try:
            # Prepare a list of status queries to execute
            status_queries = [
                ("power", "get_power", None),
                ("zone2_power", "get_zone2_power", None),
                ("volume", "get_volume", None),
                ("mute", "get_mute", None),
                ("input", "get_input", None),
                ("mode", "get_mode", None)
            ]
            
            # Track success rate
            successful_queries = 0
            total_queries = len(status_queries)
            status_updates = {}
            
            # Execute each query
            for status_type, command, args in status_queries:
                try:
                    response = await self.client.command_executor.execute_command(
                        command=command,
                        timeout=self.config.emotiva.timeout
                    )
                    
                    if response.is_successful:
                        successful_queries += 1
                        
                        # Convert to our state model
                        value = response.value
                        if status_type == "power":
                            status_updates["power"] = PowerState.ON if value == "on" else PowerState.OFF if value == "off" else PowerState.UNKNOWN
                        elif status_type == "zone2_power":
                            status_updates["zone2_power"] = PowerState.ON if value == "on" else PowerState.OFF if value == "off" else PowerState.UNKNOWN
                        elif status_type == "volume":
                            status_updates["volume"] = float(value) if value is not None else 0
                        elif status_type == "mute":
                            status_updates["mute"] = value == "on" if isinstance(value, str) else bool(value)
                        elif status_type == "input":
                            status_updates["input_source"] = value
                            status_updates["source_status"] = self._get_source_display_name(value)
                        elif status_type == "mode":
                            status_updates["audio_mode"] = value
                    else:
                        logger.warning(f"Failed to get {status_type} status: {response.error}")
                except Exception as e:
                    logger.warning(f"Error getting {status_type} status: {str(e)}")
            
            # Update device state with all gathered info
            if status_updates:
                self.clear_error()
                self.update_state(**status_updates)
            
            # Create response based on success rate
            if successful_queries == total_queries:
                return self.create_command_result(
                    success=True,
                    message=f"Successfully refreshed all device status"
                )
            elif successful_queries > 0:
                return self.create_command_result(
                    success=True,
                    message=f"Partially refreshed device status ({successful_queries}/{total_queries} successful)"
                )
            else:
                error_msg = "Failed to refresh any status information"
                self.set_error(error_msg)
                return self.create_command_result(success=False, error=error_msg)
        except Exception as e:
            error_msg = f"Error refreshing device status: {str(e)}"
            logger.error(error_msg)
            self.set_error(error_msg)
            return self.create_command_result(success=False, error=error_msg)

    async def handle_get_available_inputs(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """
        Handle request to get all available inputs.
        
        Args:
            cmd_config: Command configuration
            params: Parameters (unused)
            
        Returns:
            Command execution result with dictionary of input IDs to input names
        """
        if not self.client:
            return self.create_command_result(success=False, error="Device not initialized")
        
        logger.info(f"Retrieving available inputs for device: {self.get_name()}")
        
        try:
            # Query the device for available inputs
            response = await self.client.command_executor.execute_command(
                command="get_input_list",
                timeout=self.config.emotiva.timeout
            )
            
            if not response.is_successful:
                error_msg = f"Failed to retrieve input list: {response.error}"
                logger.error(error_msg)
                return self.create_command_result(success=False, error=error_msg)
            
            # The response.value might be a list or other structure with input information
            # Parse according to the actual API response format
            raw_inputs = response.value
            
            # Process the inputs into a dictionary
            all_inputs = {}
            
            # Handle different response formats
            if isinstance(raw_inputs, list):
                # If it's a list of input objects/values
                for input_item in raw_inputs:
                    # Adapt this extraction logic based on the actual structure
                    if isinstance(input_item, dict):
                        input_id = input_item.get('id') or input_item.get('input_id')
                        input_name = input_item.get('name') or input_item.get('display_name')
                        if input_id and input_name:
                            all_inputs[input_id] = input_name
                    elif isinstance(input_item, str):
                        # If it's just a string ID, use the display name mapping function
                        input_id = input_item
                        input_name = self._get_source_display_name(input_id)
                        all_inputs[input_id] = input_name
            elif isinstance(raw_inputs, dict):
                # If it's already a dictionary mapping
                all_inputs = raw_inputs
            else:
                # Fallback for unexpected formats or if device doesn't support input listing
                logger.warning(f"Unexpected input list format: {type(raw_inputs)}. Using fallback method.")
                
                # Query a list of current inputs via individual commands
                # This may be more reliable but slower
                try:
                    # Use the current input to determine available inputs
                    current_input_response = await self.client.command_executor.execute_command(
                        command="get_input",
                        timeout=self.config.emotiva.timeout
                    )
                    
                    if current_input_response.is_successful:
                        current_input = current_input_response.value
                        # Add current input to the list
                        all_inputs[current_input] = self._get_source_display_name(current_input)
                        
                        # Add standard inputs we know are supported
                        known_inputs = ["1", "2", "3", "hdmi1", "hdmi2", "hdmi3", "hdmi4", "hdmi5", "hdmi6", "hdmi7", "hdmi8"]
                        for input_id in known_inputs:
                            if input_id not in all_inputs:
                                all_inputs[input_id] = self._get_source_display_name(input_id)
                except Exception as e:
                    logger.warning(f"Error in fallback input determination: {str(e)}")
            
            # Record last command
            self._update_last_command("get_available_inputs", params)
            
            # Return success with inputs
            return self.create_command_result(
                success=True,
                message="Retrieved available inputs successfully",
                inputs=all_inputs
            )
        except Exception as e:
            error_msg = f"Error retrieving available inputs: {str(e)}"
            logger.error(error_msg)
            self.set_error(error_msg)
            return self.create_command_result(success=False, error=error_msg)

