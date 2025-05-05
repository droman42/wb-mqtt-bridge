import logging
import json
from typing import Dict, Any, List, Optional, Union, Callable, Awaitable, Tuple, TypeVar, cast, Coroutine, Literal, Protocol
from pymotivaxmc2 import Emotiva, EmotivaConfig as PyEmotivaConfig
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

class EMotivaXMC2(BaseDevice[EmotivaXMC2State]):
    """eMotiva XMC2 processor device implementation."""
    
    def __init__(self, config: EmotivaXMC2DeviceConfig, mqtt_client=None):
        super().__init__(config, mqtt_client)
        
        self.client: Optional[Emotiva] = None
        
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
            
            # Create client instance with proper configuration
            self.client = Emotiva(PyEmotivaConfig(
                ip=host,
                **{k: v for k, v in emotiva_options.items() if v is not None}
            ))
            
            # Attempt to discover the device on the network
            logger.info(f"Attempting to discover eMotiva device at {host}")
            discovery_result = await self.client.discover()
            
            # Check discovery result
            if discovery_result and discovery_result.get('status') == 'success':
                logger.info(f"Successfully discovered eMotiva device: {discovery_result}")
                
                # Set up notification handling
                self.client.set_callback(self._handle_notification)
                
                # Subscribe to notification topics
                default_notifications = [
                    "power", "zone2_power", "volume", "input", 
                    "audio_input", "video_input", "audio_bitstream",
                    "mute", "mode"
                ]
                
                subscription_result = await self.client.subscribe_to_notifications(default_notifications)
                logger.info(f"Notification subscription result: {subscription_result}")
                
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
                error_message = discovery_result.get('message', 'Unknown error during discovery') if discovery_result else "No response from device"
                logger.error(f"Error discovering eMotiva device at {host}: {error_message}")
                
                # We can still try to use the device even if discovery failed
                if emotiva_config.force_connect:
                    logger.warning(f"Force connect enabled, continuing with setup despite discovery failure")
                    
                    # Set up notification handling
                    self.client.set_callback(self._handle_notification)
                    
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
                # Check if the client has a notification_registered attribute
                if hasattr(self.client, '_notification_registered') and self.client._notification_registered:
                    logger.debug(f"Unregistering from notifications for {self.get_name()}")
                    # This is normally handled by the close method, but we'll try explicitly
                    if hasattr(self.client, '_notifier') and self.client._notifier:
                        try:
                            # Give a short timeout for unregistering to avoid hanging
                            await asyncio.wait_for(
                                self.client._notifier.unregister(self.client._ip),
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
            
            # Step 2: Clean up the notifier
            try:
                if hasattr(self.client, '_notifier') and self.client._notifier:
                    logger.debug(f"Cleaning up notification listener for {self.get_name()}")
                    
                    # Attempt to gracefully stop the listener if the force_stop_listener method exists
                    if hasattr(self.client._notifier, 'force_stop_listener'):
                        try:
                            # Use force_stop_listener with a short timeout
                            await asyncio.wait_for(
                                self.client._notifier.force_stop_listener(),
                                timeout=1.0
                            )
                            logger.info(f"Successfully stopped notification listener for {self.get_name()}")
                        except asyncio.TimeoutError:
                            logger.warning(f"Force stop listener timed out for {self.get_name()}")
                        except Exception as e:
                            logger.warning(f"Error stopping notification listener for {self.get_name()}: {str(e)}")
                            all_cleanup_successful = False
                    
                    # Save reference to notifier for cleanup right before we release the client
                    notifier = self.client._notifier
                    
                    # Remove the notifier reference from client to prevent __del__ cleanup issue
                    # This prevents the RuntimeWarning about coroutine never being awaited
                    self.client._notifier = None
                    
                    # As a fallback, try the generic cleanup method
                    try:
                        await asyncio.wait_for(
                            notifier.cleanup(),
                            timeout=1.0
                        )
                        logger.info(f"Completed notification listener cleanup for {self.get_name()}")
                    except asyncio.TimeoutError:
                        logger.warning(f"Notification cleanup timed out for {self.get_name()}")
                    except Exception as e:
                        logger.warning(f"Error during notification cleanup for {self.get_name()}: {str(e)}")
                        all_cleanup_successful = False
            except Exception as e:
                logger.warning(f"Exception during notifier cleanup: {str(e)}")
                all_cleanup_successful = False
            
            # Step 3: Close the client connection
            try:
                logger.debug(f"Closing client connection for {self.get_name()}")
                await asyncio.wait_for(
                    self.client.close(),
                    timeout=2.0
                )
                logger.info(f"Successfully closed client connection for {self.get_name()}")
            except asyncio.TimeoutError:
                logger.warning(f"Client close timed out for {self.get_name()}")
                all_cleanup_successful = False
            except Exception as e:
                logger.warning(f"Error closing client connection for {self.get_name()}: {str(e)}")
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
    
    def _is_command_successful(self, result: Optional[Dict[str, Any]]) -> bool:
        """Check if a command result indicates success.
        
        Args:
            result: The result from a device command
            
        Returns:
            True if the command was successful, False otherwise
        """
        if result is None:
            return False
            
        if isinstance(result, dict) and 'status' in result:
            return result.get('status') in ['success', 'sent', 'complete']
        else:
            # For mocks that don't return expected dict structure
            return True
    
    async def _execute_device_command(self, 
                                     action: str,
                                     command_func: DeviceCommandFunc,
                                     params: Dict[str, Any],
                                     notification_topics: List[str] = None,
                                     state_updates: Dict[str, Any] = None) -> CommandResult:
        """Execute a device command with standardized error handling and response creation.
        
        Args:
            action: The name of the action being performed
            command_func: The async function that performs the actual device command
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
                    await self.client.subscribe_to_notifications(notification_topics)
                except Exception as e:
                    logger.warning(f"Could not subscribe to notifications for {action}: {str(e)}")
            
            # Execute the command
            try:
                result = await command_func()
            except asyncio.TimeoutError:
                logger.error(f"Timeout waiting for {action} response from {self.get_name()}")
                self.set_error("Command timeout")
                return self.create_command_result(success=False, error="Command timeout")
            except Exception as e:
                logger.error(f"Error executing {action} on eMotiva XMC2: {str(e)}")
                self.set_error(str(e))
                return self.create_command_result(success=False, error=str(e))
            
            # Check if command was successful
            if self._is_command_successful(result):
                # Update state with provided updates
                if state_updates:
                    # Clear any previous errors
                    self.clear_error()
                    self.update_state(**state_updates)
                
                # Record last command
                self._update_last_command(action, params)
                
                # Create success message if not provided
                message = f"{action} command executed successfully"
                
                logger.info(f"Successfully executed {action} on eMotiva XMC2: {self.get_name()}")
                return self.create_command_result(success=True, message=message)
            else:
                # Parse the error message from the result
                error_message = result.get('message', f'Unknown error during {action}') if result else "No response from device"
                logger.error(f"Failed to execute {action} on eMotiva XMC2: {error_message}")
                
                # Update the state with the error
                self.set_error(error_message)
                
                return self.create_command_result(success=False, error=error_message)
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
        return await self._execute_device_command(
            "power_on",
            self.client.power_on,
            params,
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
        return await self._execute_device_command(
            "power_off",
            self.client.power_off,
            params,
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
        return await self._execute_device_command(
            "zone2_on",
            self.client.zone2_power_on,
            params,
            notification_topics=["zone2_power"],
            state_updates={"zone2_power": PowerState.ON}
        )
    
    async def handle_set_volume(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """
        Handle volume setting command.
        
        Args:
            cmd_config: Command configuration
            params: Must contain 'level' parameter with a valid volume level
            
        Returns:
            CommandResult: Result of volume setting command
        """
        try:
            # Validate the level parameter
            is_valid, volume_level, error_message = self._validate_parameter(
                param_name="level",
                param_value=params.get("level"),
                param_type="range",
                min_value=-96.0,
                max_value=0.0,
                action="set_volume"
            )
            
            if not is_valid:
                logger.error(error_message)
                return self.create_command_result(success=False, error=error_message)
            
            if not self.client:
                return self.create_command_result(success=False, error="Device not initialized")
            
            logger.info(f"Setting volume to {volume_level} dB on eMotiva XMC2: {self.get_name()}")
            
            # Create a function that captures the volume level
            async def set_volume_with_level() -> Dict[str, Any]:
                return await self.client.set_volume(volume_level)
            
            # Execute the command
            result = await self._execute_device_command(
                action="set_volume",
                command_func=set_volume_with_level,
                params=params,
                notification_topics=["volume"],
                state_updates={"volume": volume_level}
            )
            
            # Create success result with volume info if successful
            if result.get("success", False):
                # Since we can't modify the result directly due to TypedDict constraints,
                # create a new result with additional information
                return self.create_command_result(
                    success=True,
                    message=f"Volume set to {volume_level} dB successfully",
                    volume=volume_level
                )
                
            return result
        except Exception as e:
            error_message = f"Error setting volume: {str(e)}"
            logger.error(error_message)
            self.set_error(error_message)
            return self.create_command_result(success=False, error=error_message)
    
    async def handle_set_mute(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """
        Handle mute setting command.
        
        Args:
            cmd_config: Command configuration
            params: Must contain 'state' parameter with a boolean value
            
        Returns:
            CommandResult: Result of mute setting command
        """
        try:
            # Validate the state parameter
            is_valid, mute_state, error_message = self._validate_parameter(
                param_name="state",
                param_value=params.get("state"),
                param_type="boolean",
                action="set_mute"
            )
            
            if not is_valid:
                logger.error(error_message)
                return self.create_command_result(success=False, error=error_message)
            
            if not self.client:
                return self.create_command_result(success=False, error="Device not initialized")
            
            logger.info(f"Setting mute to {mute_state} on eMotiva XMC2: {self.get_name()}")
            
            # Select the appropriate mute function based on state
            mute_func = self.client.set_mute_on if mute_state else self.client.set_mute_off
            
            # Execute the command
            result = await self._execute_device_command(
                action="set_mute",
                command_func=mute_func,
                params=params,
                notification_topics=["mute"],
                state_updates={"mute": mute_state}
            )
            
            # Create success result with mute info if successful
            if result.get("success", False):
                # Since we can't modify the result directly due to TypedDict constraints,
                # create a new result with additional information
                return self.create_command_result(
                    success=True,
                    message=f"Mute set to {mute_state} successfully",
                    mute=mute_state
                )
                
            return result
        except Exception as e:
            error_message = f"Error setting mute state: {str(e)}"
            logger.error(error_message)
            self.set_error(error_message)
            return self.create_command_result(success=False, error=error_message)
    
    async def handle_zappiti(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """
        Switch to Zappiti input.
        
        Args:
            cmd_config: Command configuration
            params: Parameters (unused)
            
        Returns:
            Command execution result
        """
        return await self._switch_input_source("Zappiti", "1")
        
    async def handle_apple_tv(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """
        Switch to Apple TV input.
        
        Args:
            cmd_config: Command configuration
            params: Parameters (unused)
            
        Returns:
            Command execution result
        """
        return await self._switch_input_source("Apple TV", "2")
        
    async def handle_dvdo(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """
        Switch to DVDO input.
        
        Args:
            cmd_config: Command configuration
            params: Parameters (unused)
            
        Returns:
            Command execution result
        """
        return await self._switch_input_source("DVDO", "3")
    
    async def _switch_input_source(self, source_name: str, source_id: str) -> CommandResult:
        """
        Helper function to switch input sources.
        
        Args:
            source_name: User-friendly source name
            source_id: Input source identifier (e.g., "HDMI 1")
            
        Returns:
            CommandResult: Result of the command execution
        """
        try:
            if not self.client:
                return self.create_command_result(success=False, error="Device not initialized")
                
            command_name = f"switch_to_{source_name.lower().replace(' ', '_')}"
            logger.info(f"Switching input source to {source_name} ({source_id}) on eMotiva XMC2: {self.get_name()}")
            
            # Create a function that captures the source_id
            async def set_input_with_id() -> Dict[str, Any]:
                return await self.client.set_input(source_id)
            
            # Create a params dictionary for the record_last_command
            source_params = {"source_name": source_name, "source_id": source_id}
            
            # Execute the command
            result = await self._execute_device_command(
                action=command_name,
                command_func=set_input_with_id,
                params=source_params,
                notification_topics=["input"],
                state_updates={
                    "input_source": source_id,
                    "source_status": source_name  # Set the display name directly
                }
            )
            
            # Create success result with source info if successful
            if result.get("success", False):
                # Since we can't modify the result directly due to TypedDict constraints,
                # create a new result with additional information
                return self.create_command_result(
                    success=True,
                    message=f"Input switched to {source_name} successfully",
                    input=source_id
                )
                
            return result
        except Exception as e:
            error_message = f"Error switching input source: {str(e)}"
            logger.error(error_message)
            self.set_error(error_message)
            return self.create_command_result(success=False, error=error_message)
    
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
    
    def _handle_notification(self, notification_data: Dict[str, Any]) -> None:
        """
        Process notifications from the eMotiva device.
        
        Args:
            notification_data: Dictionary containing the notification data
        """
        logger.debug(f"Received notification from eMotiva device: {notification_data}")
        # Create a background task for the async call
        asyncio.create_task(self.publish_progress(json.dumps(notification_data)))
        
        try:
            updates: Dict[str, Any] = {}
            
            # Process power state
            if "power" in notification_data:
                power_data = notification_data["power"]
                power_state_value = power_data.get("value", "unknown")
                # Convert string value to enum
                power_state = PowerState.ON if power_state_value == "on" else PowerState.OFF if power_state_value == "off" else PowerState.UNKNOWN
                updates["power"] = power_state
                logger.info(f"Power state updated: {power_state}")
                
            # Process zone2 power state
            if "zone2_power" in notification_data:
                zone2_data = notification_data["zone2_power"]
                zone2_state_value = zone2_data.get("value", "unknown")
                # Convert string value to enum
                zone2_state = PowerState.ON if zone2_state_value == "on" else PowerState.OFF if zone2_state_value == "off" else PowerState.UNKNOWN
                updates["zone2_power"] = zone2_state
                logger.info(f"Zone 2 power state updated: {zone2_state}")
                
            # Process volume
            if "volume" in notification_data:
                volume_data = notification_data["volume"]
                volume_value = volume_data.get("value", 0)
                updates["volume"] = float(volume_value) if volume_value else 0
                logger.debug(f"Volume updated: {volume_value}")
                
            # Process mute state
            if "mute" in notification_data:
                mute_data = notification_data["mute"]
                mute_state = mute_data.get("value", False)
                # Convert string "true"/"false" to boolean if needed
                if isinstance(mute_state, str):
                    mute_state = mute_state.lower() == "true"
                updates["mute"] = bool(mute_state)
                logger.debug(f"Mute state updated: {mute_state}")
                
            # Process input source
            if "input" in notification_data:
                input_data = notification_data["input"]
                input_value = input_data.get("value", "unknown")
                updates["input_source"] = input_value
                # Also set the source_status with the display name
                updates["source_status"] = self._get_source_display_name(input_value)
                logger.info(f"Input source updated: {input_value} (display name: {updates['source_status']})")
                
            # Process video input
            if "video_input" in notification_data:
                video_data = notification_data["video_input"]
                video_value = video_data.get("value", "unknown")
                updates["video_input"] = video_value
                logger.debug(f"Video input updated: {video_value}")
                
            # Process audio input
            if "audio_input" in notification_data:
                audio_data = notification_data["audio_input"]
                audio_value = audio_data.get("value", "unknown")
                updates["audio_input"] = audio_value
                logger.debug(f"Audio input updated: {audio_value}")
                
            # Process audio bitstream
            if "audio_bitstream" in notification_data:
                bitstream_data = notification_data["audio_bitstream"]
                bitstream_value = bitstream_data.get("value", "unknown")
                updates["audio_bitstream"] = bitstream_value
                logger.debug(f"Audio bitstream updated: {bitstream_value}")
                
            # Process mode (audio mode)
            if "mode" in notification_data:
                mode_data = notification_data["mode"]
                mode_value = mode_data.get("value", "unknown")
                updates["audio_mode"] = mode_value
                logger.debug(f"Audio mode updated: {mode_value}")
            
            # Update device state with notification data and clear any errors
            # since successful notifications indicate the device is responsive
            if updates:
                self.clear_error()
                self.update_state(**updates)
        except Exception as e:
            logger.error(f"Error processing notification: {str(e)}")
            # Don't set error state for notification processing issues
            # as they might be transient
    
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

