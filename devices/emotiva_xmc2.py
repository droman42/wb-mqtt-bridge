import logging
import json
from typing import Dict, Any, List, Optional, Union, Callable, Awaitable, Tuple, TypeVar, cast, Coroutine
from pymotivaxmc2 import Emotiva, EmotivaConfig as PyEmotivaConfig
from datetime import datetime
import asyncio

from devices.base_device import BaseDevice
from app.schemas import EmotivaXMC2State, LastCommand, EmotivaConfig, EmotivaXMC2DeviceConfig, StandardCommandConfig

logger = logging.getLogger(__name__)

# Type hint for device command functions
T = TypeVar('T')
DeviceCommandFunc = Callable[..., Awaitable[Dict[str, Any]]]

class EMotivaXMC2(BaseDevice):
    """eMotiva XMC2 processor device implementation."""
    
    def __init__(self, config: Dict[str, Any], mqtt_client=None):
        super().__init__(config, mqtt_client)
        
        # Get and use typed config
        self.typed_config = cast(EmotivaXMC2DeviceConfig, self.config)
        
        self._state_schema = EmotivaXMC2State
        self.client = None
        
        # Initialize device state
        self.state = {
            "device_id": self.typed_config.device_id,
            "device_name": self.typed_config.device_name,
            "power": None,
            "zone2_power": None,
            "source_status": None,
            "video_input": None,
            "audio_input": None,
            "volume": None,
            "mute": None,
            "audio_mode": None,
            "audio_bitstream": None,
            "connected": False,
            "ip_address": None,
            "mac_address": None,
            "startup_complete": False,
            "notifications": False,
            "last_command": None,
            "error": None
        }
        
        # Register action handlers
        self._action_handlers = {
            "power_on": self.handle_power_on,
            "power_off": self.handle_power_off,
            "zone2_on": self.handle_zone2_on,
            "zappiti": self.handle_zappiti,
            "apple_tv": self.handle_apple_tv,
            "dvdo": self.handle_dvdo,
            "set_volume": self.handle_set_volume,
            "set_mute": self.handle_set_mute
        }
    
    async def setup(self) -> bool:
        """Initialize the device."""
        try:
            # Get emotiva configuration directly from typed config
            emotiva_config = self.typed_config.emotiva
            
            # Get the host IP address
            host = emotiva_config.host
            if not host:
                logger.error(f"Missing 'host' in emotiva configuration for device: {self.get_name()}")
                self.state["error"] = "Missing host configuration"
                return False
            
            # Store MAC address if available in config
            if emotiva_config.mac:
                self.state["mac_address"] = emotiva_config.mac
                
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
                self.update_state({
                    "connected": True,
                    "ip_address": host,
                    "startup_complete": True,
                    "notifications": True
                })
                
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
                    self.update_state({
                        "connected": True,
                        "ip_address": host,
                        "startup_complete": True,
                        "notifications": False,
                        "error": f"Discovery failed, using forced connection: {error_message}"
                    })
                    
                    return True
                else:
                    self.state["error"] = error_message
                    return False

        except ConnectionError as e:
            logger.error(f"Connection error initializing eMotiva XMC2 device {self.get_name()}: {str(e)}")
            self.state["error"] = f"Connection error: {str(e)}"
            return False
        except TimeoutError as e:
            logger.error(f"Timeout error initializing eMotiva XMC2 device {self.get_name()}: {str(e)}")
            self.state["error"] = f"Timeout error: {str(e)}"
            return False
        except Exception as e:
            logger.error(f"Failed to initialize eMotiva XMC2 device {self.get_name()}: {str(e)}")
            self.state["error"] = str(e)
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
            self.update_state({
                "connected": False,
                "notifications": False,
                "error": None if all_cleanup_successful else "Partial shutdown completed with errors"
            })
            
            # Release client reference
            self.client = None
            
            logger.info(f"eMotiva XMC2 device {self.get_name()} shutdown {'' if all_cleanup_successful else 'partially '}complete")
            return True
        except Exception as e:
            logger.error(f"Unexpected error during {self.get_name()} shutdown: {str(e)}")
            
            # Still update the state as disconnected even after errors
            self.update_state({
                "connected": False,
                "notifications": False,
                "error": f"Shutdown error: {str(e)}"
            })
            
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
    
    async def _execute_device_command(self, 
                                     action: str,
                                     command_func: DeviceCommandFunc,
                                     params: Dict[str, Any],
                                     notification_topics: List[str] = None,
                                     state_updates: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute a device command with standardized error handling and response creation.
        
        Args:
            action: The name of the action being performed
            command_func: The async function that performs the actual device command
            params: The parameters for the command
            notification_topics: List of notification topics to subscribe to before executing the command
            state_updates: Dictionary of state updates to apply on success
            
        Returns:
            A standardized response dictionary
        """
        if not self.client:
            logger.error(f"Client not initialized for action: {action}")
            return self._create_response(False, action, error="Client not initialized")
        
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
            self.state["error"] = "Command timeout"
            return self._create_response(False, action, error="Command timeout")
        except Exception as e:
            logger.error(f"Error executing {action} on eMotiva XMC2: {str(e)}")
            self.state["error"] = str(e)
            return self._create_response(False, action, error=str(e))
        
        # Check if command was successful
        if self._is_command_successful(result):
            # Update state with provided updates
            if state_updates:
                state_updates["error"] = None  # Clear any previous errors
                self.update_state(state_updates)
            
            # Record last command
            self.record_last_command(action, params)
            
            # Create success message if not provided
            message = f"{action} command executed successfully"
            
            logger.info(f"Successfully executed {action} on eMotiva XMC2: {self.get_name()}")
            return self._create_response(True, action, message=message)
        else:
            # Parse the error message from the result
            error_message = result.get('message', f'Unknown error during {action}') if result else "No response from device"
            logger.error(f"Failed to execute {action} on eMotiva XMC2: {error_message}")
            
            # Update the state with the error
            self.update_state({"error": error_message})
            
            return self._create_response(False, action, error=error_message)
    
    async def handle_power_on(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]):
        """
        Handle power on command.
        
        Args:
            cmd_config: Command configuration
            params: Parameters (unused)
        """
        return await self._execute_device_command(
            "power_on",
            self.client.power_on,
            params,
            notification_topics=["power"],
            state_updates={"power": "on"}
        )
    
    async def handle_power_off(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]):
        """
        Handle power off command.
        
        Args:
            cmd_config: Command configuration
            params: Parameters (unused)
        """
        return await self._execute_device_command(
            "power_off",
            self.client.power_off,
            params,
            notification_topics=["power"],
            state_updates={"power": "off"}
        )
    
    async def handle_zone2_on(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]):
        """
        Handle zone 2 power on command.
        
        Args:
            cmd_config: Command configuration
            params: Parameters (unused)
        """
        return await self._execute_device_command(
            "zone2_on",
            self.client.zone2_power_on,
            params,
            notification_topics=["zone2_power"],
            state_updates={"zone2_power": "on"}
        )
    
    async def handle_set_volume(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]):
        """
        Handle volume setting command.
        
        Args:
            cmd_config: Command configuration
            params: Must contain 'level' parameter with a valid volume level
        """
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
            return self._create_response(False, "set_volume", error=error_message)
        
        logger.info(f"Setting volume to {volume_level} dB on eMotiva XMC2: {self.get_name()}")
        
        # Create a function that captures the volume level
        async def set_volume_with_level():
            return await self.client.set_volume(volume_level)
        
        # Execute the command
        result = await self._execute_device_command(
            action="set_volume",
            command_func=set_volume_with_level,
            params=params,
            notification_topics=["volume"],
            state_updates={"volume": volume_level}
        )
        
        # Add volume to the response if successful
        if result["success"]:
            result["message"] = f"Volume set to {volume_level} dB successfully"
            result["volume"] = volume_level
            
        return result
    
    async def handle_set_mute(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]):
        """
        Handle mute setting command.
        
        Args:
            cmd_config: Command configuration
            params: Must contain 'mute' parameter with a boolean value
        """
        # Validate the state parameter
        is_valid, mute_state, error_message = self._validate_parameter(
            param_name="state",
            param_value=params.get("state"),
            param_type="boolean",
            action="set_mute"
        )
        
        if not is_valid:
            logger.error(error_message)
            return self._create_response(False, "set_mute", error=error_message)
        
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
        
        # Add mute state to the response if successful
        if result["success"]:
            result["message"] = f"Mute set to {mute_state} successfully"
            result["mute"] = mute_state
            
        return result
    
    async def handle_zappiti(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]):
        """Switch to Zappiti input."""
        return await self._switch_input_source("Zappiti", "2")
        
    async def handle_apple_tv(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]):
        """Switch to Apple TV input."""
        return await self._switch_input_source("Apple TV", "3")
        
    async def handle_dvdo(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]):
        """Switch to DVDO input."""
        return await self._switch_input_source("DVDO", "1")
    
    async def _switch_input_source(self, source_name: str, source_id: str):
        """
        Helper function to switch input sources.
        
        Args:
            source_name: User-friendly source name
            source_id: Input source identifier (e.g., "HDMI 1")
            
        Returns:
            Dictionary with command result
        """
        command_name = f"switch_to_{source_name.lower().replace(' ', '_')}"
        logger.info(f"Switching input source to {source_name} ({source_id}) on eMotiva XMC2: {self.get_name()}")
        
        # Create a function that captures the source_id
        async def set_input_with_id():
            return await self.client.set_input(source_id)
        
        # Create a params dictionary for the record_last_command
        source_params = {"source_name": source_name, "source_id": source_id}
        
        # Execute the command
        result = await self._execute_device_command(
            action=command_name,
            command_func=set_input_with_id,
            params=source_params,
            notification_topics=["input"],
            state_updates={"input_source": source_id}
        )
        
        # Add source info to the response if successful
        if result["success"]:
            result["message"] = f"Input switched to {source_name} successfully"
            result["input"] = source_id
            
        return result
    
    def record_last_command(self, command: str, params: Dict[str, Any] = None):
        """Record the last command executed with its parameters."""
        self.state["last_command"] = LastCommand(
            action=command,
            source=self.device_name,
            timestamp=datetime.now(),
            params=params
        ).dict()
    
    def get_current_state(self) -> EmotivaXMC2State:
        """Get a typed representation of the current state."""
        # Convert dictionary state to a proper schema object
        return EmotivaXMC2State(
            device_id=self.device_id,
            device_name=self.device_name,
            power=self.state.get("power", "standby"),
            zone2_power=self.state.get("zone2_power", "standby"),
            source_status=self._get_source_display_name(self.state.get("input_source")),
            video_input=self.state.get("video_input"),
            audio_input=self.state.get("audio_input"),
            startup_complete=self.state.get("startup_complete", False),
            notifications=self.state.get("notifications", False),
            last_command=self.state.get("last_command"),
            error=self.state.get("error")
        )
    
    def _get_source_display_name(self, source_id: Optional[str]) -> Optional[str]:
        """Convert numeric source IDs to their display names."""
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
    
    def _handle_notification(self, notification_data: Dict[str, Any]):
        """Process notifications from the eMotiva device.
        
        Args:
            notification_data: Dictionary containing the notification data
        """
        logger.debug(f"Received notification from eMotiva device: {notification_data}")
        # Create a background task for the async call
        asyncio.create_task(self.publish_progress(json.dumps(notification_data)))
        
        updates = {}
        
        # Process power state
        if "power" in notification_data:
            power_data = notification_data["power"]
            power_state = power_data.get("value", "unknown")
            updates["power"] = power_state
            logger.info(f"Power state updated: {power_state}")
            
        # Process zone2 power state
        if "zone2_power" in notification_data:
            zone2_data = notification_data["zone2_power"]
            zone2_state = zone2_data.get("value", "unknown")
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
            logger.info(f"Input source updated: {input_value}")
            
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
        
        # Update device state with notification data
        if updates:
            self.update_state(updates)

    async def handle_message(self, topic: str, payload: str):
        """Handle incoming MQTT messages for this device."""
        logger.debug(f"Device {self.get_name()} received message on {topic}: {payload}")
        
        # Find matching command configuration
        matching_commands = []
        for cmd_name, cmd_config in self.get_available_commands().items():
            if cmd_config.get("topic") == topic:
                matching_commands.append((cmd_name, cmd_config))
        
        if not matching_commands:
            logger.warning(f"No command configuration found for topic: {topic}")
            return None
        
        # Process each matching command configuration found for the topic
        for cmd_name, cmd_config in matching_commands:
            # Process parameters if defined
            params = {}
            param_definitions = cmd_config.get("params", [])
            
            if param_definitions:
                # Try to parse payload as JSON
                try:
                    params = json.loads(payload)
                except json.JSONDecodeError:
                    # For single parameter commands, try to map raw payload to the first parameter
                    if len(param_definitions) == 1:
                        param_def = param_definitions[0]
                        param_name = param_def["name"]
                        param_type = param_def["type"]
                        
                        # Use the validation helper to convert and validate the parameter
                        is_valid, converted_value, error_message = self._validate_parameter(
                            param_name=param_name,
                            param_value=payload,
                            param_type=param_type,
                            required=param_def.get("required", True),
                            min_value=param_def.get("min"),
                            max_value=param_def.get("max"),
                            action=cmd_name
                        )
                        
                        if is_valid:
                            params = {param_name: converted_value}
                        else:
                            logger.error(f"Failed to convert payload '{payload}': {error_message}")
                            return self._create_response(False, cmd_name, error=f"Invalid payload format: {payload}")
                    else:
                        logger.error(f"Payload is not valid JSON and command expects multiple parameters: {payload}")
                        return self._create_response(False, cmd_name, error="Invalid JSON format for multi-parameter command")
            
            # Get the handler method from registered handlers
            handler = self._action_handlers.get(cmd_name)
            if handler:
                logger.debug(f"Found handler for command {cmd_name}")
                return await handler(cmd_config=cmd_config, params=params)
            else:
                logger.warning(f"No handler found for command: {cmd_name}")
                
        return None

