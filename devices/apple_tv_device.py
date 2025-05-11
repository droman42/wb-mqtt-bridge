import asyncio
import json
import logging
import os
from typing import Dict, List, Any, Optional, cast, TypeVar
from functools import partial # Added for potential future use if needed
from datetime import datetime

import pyatv
from pyatv import scan, connect
from pyatv.const import Protocol as ProtocolType, PowerState
from pyatv.interface import DeviceListener, Playing
from pyatv.exceptions import AuthenticationError, ConnectionFailedError

from devices.base_device import BaseDevice
from app.schemas import AppleTVState, AppleTVDeviceConfig, StandardCommandConfig, LastCommand
from app.mqtt_client import MQTTClient
from app.types import CommandResult, CommandResponse

logger = logging.getLogger(__name__) # Define logger for the module

class AppleTVDevice(BaseDevice[AppleTVState]):
    """
    Apple TV device integration for wb-mqtt-bridge.
    
    This class provides a standardized interface to control Apple TV devices through
    the BaseDevice framework using PyATV for the actual communication.
    """
    
    def __init__(self, config: AppleTVDeviceConfig, mqtt_client: Optional[MQTTClient] = None):
        """Initialize the Apple TV device."""
        # Call BaseDevice init first with proper Pydantic config
        super().__init__(config, mqtt_client)
        
        # Get Apple TV configuration directly from the config
        self.apple_tv_config = self.config.apple_tv
        
        self.loop = None
        self.atv = None  # pyatv device instance (renamed from self.device)
        self.atv_config = None # pyatv config object (renamed from self.config)
        self._app_list: Dict[str, str] = {} # Maps lowercase app name to app identifier

        # Initialize state using the AppleTVState Pydantic model
        self.state = AppleTVState(
            device_id=self.device_id,
            device_name=self.device_name,
            connected=False,
            power="unknown",  # Corresponds to PowerState (on, off, unknown)
            app=None,
            playback_state=None,  # Corresponds to DeviceState (idle, playing, paused, etc.)
            media_type=None,  # Corresponds to MediaType (music, video, tv, unknown)
            title=None,
            artist=None,
            album=None,
            position=None,
            total_time=None,
            volume=None,  # 0-100
            error=None,
            ip_address=self.apple_tv_config.ip_address,
            last_command=LastCommand(
                action="init",
                source="system",
                timestamp=datetime.now(),
                params=None
            )
        )
        
        # Log instance creation
        logger.info(f"Initialized AppleTVDevice: {self.device_id} ({self.device_name})") # Use the module logger

    async def setup(self) -> bool:
        """Set up the Apple TV device connection."""
        self.loop = asyncio.get_event_loop()
        
        try:
            ip_address = self.apple_tv_config.ip_address
            logger.info(f"[{self.device_id}] Scanning for Apple TV at {ip_address}")
            
            # Scan for the device to get its configuration details
            atvs = await scan(hosts=[ip_address], loop=self.loop)
            
            if not atvs:
                logger.error(f"[{self.device_id}] No Apple TV found at {ip_address}")
                self.update_state(error=f"No Apple TV found at {ip_address}")
                return False
            
            self.atv_config = atvs[0]
            logger.info(f"[{self.device_id}] Found Apple TV: {self.atv_config.name} ({self.atv_config.identifier})")
            
            # Optional: Check if scanned name matches configured name
            if self.apple_tv_config.name and self.atv_config.name != self.apple_tv_config.name:
                logger.warning(f"[{self.device_id}] Found name '{self.atv_config.name}' doesn't match configured name '{self.apple_tv_config.name}'")
            
            # Load credentials from configuration
            if self.apple_tv_config.protocols:
                for protocol_name, protocol_config in self.apple_tv_config.protocols.items():
                    try:
                        protocol = ProtocolType[protocol_name]
                        if protocol_config.credentials:
                             self.atv_config.set_credentials(protocol, protocol_config.credentials)
                             logger.info(f"[{self.device_id}] Loaded credentials for protocol: {protocol_name}")
                        else:
                             logger.warning(f"[{self.device_id}] No credentials provided for protocol: {protocol_name}")
                    except KeyError:
                        logger.error(f"[{self.device_id}] Unknown protocol name in config: {protocol_name}")
                    except Exception as e:
                         logger.error(f"[{self.device_id}] Error setting credentials for {protocol_name}: {e}")

            # Attempt initial connection
            return await self.connect_to_device()
            
        except ConnectionRefusedError:
             logger.error(f"[{self.device_id}] Connection refused by Apple TV at {ip_address}. Ensure it's powered on and network remote control is enabled.")
             self.update_state(error="Connection refused")
             return False
        except AuthenticationError as e:
             logger.error(f"[{self.device_id}] Authentication failed: {e}. Check credentials or pairing.")
             self.update_state(error=f"Authentication failed: {e}")
             return False
        except ConnectionFailedError as e:
            logger.error(f"[{self.device_id}] Connection failed: {e}")
            self.update_state(error=f"Connection failed: {e}")
            return False
        except Exception as e:
            logger.error(f"[{self.device_id}] Unexpected error during setup: {e}", exc_info=True)
            self.update_state(error=f"Setup error: {str(e)}")
            return False
    
    async def shutdown(self) -> bool:
        """Shut down the Apple TV device connection."""
        logger.info(f"[{self.device_id}] Shutting down connection.")
        return await self.disconnect_from_device()

    async def connect_to_device(self) -> bool:
        """Establish connection to the Apple TV."""
        if self.atv:
            logger.info(f"[{self.device_id}] Already connected. Disconnecting first.")
            await self.disconnect_from_device()
        
        if not self.atv_config:
             logger.error(f"[{self.device_id}] Cannot connect: pyatv config not available (scan failed?).")
             return False
             
        try:
            logger.info(f"[{self.device_id}] Connecting to {self.atv_config.name} at {self.apple_tv_config.ip_address}...")
            self.atv = await connect(self.atv_config, loop=self.loop)
            # The device_info structure has changed, use a safer approach for the name
            device_name = getattr(self.atv_config, 'name', 'Unknown')
            logger.info(f"[{self.device_id}] Successfully connected to {device_name}")
            
            # Use update_state instead of directly modifying state
            self.update_state(
                connected=True,
                ip_address=str(self.atv_config.address),  # Convert IPv4Address to string
                error=None,  # Clear previous errors
                last_command=LastCommand(
                    action="connect",
                    source="system",
                    timestamp=datetime.now(),
                    params={"device_name": device_name}
                )
            )
            
            # Assign listener for connection events and updates
            self.atv.listener = PyATVDeviceListener(self) 
            
            # Perform initial status refresh and app list update
            await self.handle_refresh_status(
                StandardCommandConfig(id="refresh_status", action="refresh_status"),
                {"publish": False}
            ) # Don't publish yet, wait for app list
            await self._update_app_list()
            
            # Now publish the full initial state
            return True
            
        except AuthenticationError as e:
             logger.error(f"[{self.device_id}] Authentication failed during connect: {e}. Check credentials/pairing.")
             self.update_state(
                 connected=False,
                 error=f"Authentication failed: {e}",
                 last_command=LastCommand(
                     action="connect_error",
                     source="system",
                     timestamp=datetime.now(),
                     params={"error": str(e)}
                 )
             )
             self.atv = None
             return False
        except ConnectionFailedError as e:
            logger.error(f"[{self.device_id}] Connection failed: {e}")
            self.update_state(
                connected=False,
                error=f"Connection failed: {e}",
                last_command=LastCommand(
                    action="connect_error",
                    source="system",
                    timestamp=datetime.now(),
                    params={"error": str(e)}
                )
            )
            self.atv = None
            return False
        except Exception as e:
            logger.error(f"[{self.device_id}] Unexpected error connecting: {e}", exc_info=True)
            self.update_state(
                connected=False,
                error=f"Connection error: {str(e)}",
                last_command=LastCommand(
                    action="connect_error",
                    source="system",
                    timestamp=datetime.now(),
                    params={"error": str(e)}
                )
            )
            self.atv = None
            return False

    async def disconnect_from_device(self) -> bool:
        """Disconnect from the Apple TV."""
        if self.atv:
            try:
                logger.info(f"[{self.device_id}] Disconnecting...")
                self.atv.close() # pyatv close is synchronous
                logger.info(f"[{self.device_id}] Disconnected.")
                return True
            except Exception as e:
                logger.error(f"[{self.device_id}] Error during disconnect: {e}", exc_info=True)
                return False
            finally:
                # Update state even if close fails
                self.atv = None
                self.update_state(
                    connected=False,
                    power="off", # Assume off if disconnected
                    playback_state=None, # Reset playback
                    app=None, # Reset app
                    last_command=LastCommand(
                        action="disconnect",
                        source="system",
                        timestamp=datetime.now(),
                        params=None
                    )
                )
        else:
             logger.info(f"[{self.device_id}] Already disconnected.")
             return True # Indicate success as it's already in desired state

    async def _update_app_list(self):
        """
        Fetch and store the list of installed applications.
        
        This updates the internal dictionary mapping app names to app identifiers.
        """
        if not self.atv or not self.state.connected:
            logger.debug(f"[{self.device_id}] Cannot update app list: not connected.")
            return
            
        try:
            logger.info(f"[{self.device_id}] Fetching application list...")
            app_list_result = await self.atv.apps.app_list()
            new_app_list = {}
            for app in app_list_result:
                if app.name and app.identifier:
                    new_app_list[app.name.lower()] = app.identifier
            self._app_list = new_app_list
            logger.info(f"[{self.device_id}] Updated app list: {len(self._app_list)} apps found.")
            logger.debug(f"[{self.device_id}] App list: {self._app_list}")
        except Exception as e:
            logger.error(f"[{self.device_id}] Failed to fetch app list: {e}", exc_info=True)
            # Keep the old list
            self.update_state(
                error=f"Failed to update app list: {str(e)}",
                last_command=LastCommand(
                    action="update_app_list",
                    source="system",
                    timestamp=datetime.now(),
                    params={"error": str(e)}
                )
            )

    async def handle_refresh_status(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """
        Refresh the Apple TV status.
        
        Args:
            cmd_config: Command configuration
            params: Parameters with optional 'publish' key to control state publishing
            
        Returns:
            CommandResult: Result of the command execution
        """
        # Extract publish parameter if available, default to True
        publish = params.get('publish', True) if params else True
        
        if not self.atv or not self.state.connected:
            logger.warning(f"[{self.device_id}] Cannot refresh status: not connected.")
            # Try to reconnect
            if not await self._ensure_connected():
                error_msg = "Cannot refresh status: device disconnected and reconnection failed"
                self.update_state(
                    connected=False,
                    power="off",
                    last_command=LastCommand(
                        action="refresh_status",
                        source="system",
                        timestamp=datetime.now(),
                        params={"status": "disconnected"}
                    )
                )
                
                if publish:
                    return self.create_command_result(
                        success=False,
                        error=error_msg
                    )
                
            return self.create_command_result(
                success=False,
                error=error_msg
            )
        
        logger.info(f"[{self.device_id}] Refreshing status...")
        try:
            # Power State (more reliable than just checking connection)
            power_info = self.atv.power.power_state
            power_state = power_info.name.lower() # Should be 'on' or 'off'
            
            # If power is off, no point checking media etc.
            if power_state != PowerState.On.name.lower():
                logger.info(f"[{self.device_id}] Device is not powered on ({power_state}), skipping detailed status.")
                # Reset media/app state if device turned off
                self.update_state(
                    power=power_state,
                    app=None,
                    playback_state=None,
                    title=None,
                    artist=None,
                    album=None,
                    position=None,
                    total_time=None,
                    last_command=LastCommand(
                        action="refresh_status",
                        source="system",
                        timestamp=datetime.now(),
                        params={"power": power_state}
                    )
                )
                
                if publish:
                    return self.create_command_result(
                        success=True,
                        message=f"Status refreshed: Device is {power_state}"
                    )
                    
                return self.create_command_result(
                    success=True,
                    message=f"Status refreshed: Device is {power_state}"
                )

            # Get current app (only if powered on)
            app_info = await self.atv.apps.current_app()
            current_app = app_info.name if app_info else None
            
            # Get playback state (only if powered on)
            playing_info = await self.atv.metadata.playing()
            
            # Store the current values before calling _update_playing_state which modifies state
            # Get volume if available (only if powered on)
            volume_level = None
            if hasattr(self.atv, "audio") and hasattr(self.atv.audio, "volume"):
                try:
                    vol = await self.atv.audio.volume() # 0.0 to 1.0
                    if vol is not None:
                        volume_level = int(vol * 100)
                except (NotImplementedError, Exception) as e:
                    logger.debug(f"[{self.device_id}] Could not get volume: {e}")
            
            # Update playing state via the helper method (which now uses update_state)
            self._update_playing_state(playing_info)
            
            # Now update the app, power, and volume
            status_params = {
                "power": power_state,
                "app": current_app,
                "playback_state": self.state.playback_state,
            }
            
            self.update_state(
                power=power_state,
                app=current_app,
                volume=volume_level,
                error=None, # Clear error on successful refresh
                last_command=LastCommand(
                    action="refresh_status",
                    source="system",
                    timestamp=datetime.now(),
                    params=status_params
                )
            )
            
            logger.info(f"[{self.device_id}] Status refresh complete.")
            
            # Publish updated state if requested
            if publish:
                return self.create_command_result(
                    success=True,
                    message="Status refreshed successfully",
                    data=status_params
                )
                
            return self.create_command_result(
                success=True,
                message="Status refreshed successfully",
                data=status_params
            )

        except Exception as e:
            error_msg = f"Error refreshing status: {str(e)}"
            logger.error(f"[{self.device_id}] {error_msg}", exc_info=True)
            
            self.update_state(
                error=error_msg,
                last_command=LastCommand(
                    action="refresh_status",
                    source="system",
                    timestamp=datetime.now(),
                    params={"error": str(e)}
                )
            )
            
            # Publish updated state if requested
            if publish:
                return self.create_command_result(
                    success=False,
                    error=error_msg
                )
                
            return self.create_command_result(
                success=False,
                error=error_msg
            )

    def _update_playing_state(self, playing: Optional[Playing]):
        """Helper to update state dictionary from pyatv Playing object."""
        if playing and playing.device_state:
            # Use update_state to modify multiple state attributes at once
            updates = {
                'playback_state': playing.device_state.name.lower(),
                'media_type': playing.media_type.name.lower() if playing.media_type else None,
                'title': playing.title,
                'artist': playing.artist,
                'album': playing.album,
                'position': int(playing.position) if playing.position is not None else None,
                'total_time': int(playing.total_time) if playing.total_time is not None else None
            }
            self.update_state(**updates)
        else:
            # If nothing is playing or info is unavailable
            self.update_state(
                playback_state="idle", # Assume idle if not explicitly known
                media_type=None,
                title=None,
                artist=None,
                album=None,
                position=None,
                total_time=None
            )

    # --- Action Handlers (called by BaseDevice._execute_single_action) ---
    # Signature: async def handler(self, action_config: Dict[str, Any], payload: str)

    async def _ensure_connected(self) -> bool:
        """
        Ensure device is connected, attempting to connect if not.
        
        Returns:
            bool: True if connected or successfully reconnected, False otherwise
        """
        if self.atv and self.state.connected:
            return True
        
        logger.warning(f"[{self.device_id}] Not connected. Attempting to reconnect...")
        
        # Record connection attempt
        self.update_state(
            last_command=LastCommand(
                action="reconnect",
                source="system",
                timestamp=datetime.now(),
                params={"ip_address": self.state.ip_address}
            )
        )
        
        if await self.connect_to_device():
            # Brief pause to allow connection to stabilize before command
            await asyncio.sleep(0.5) 
            return True
        else:
            logger.error(f"[{self.device_id}] Reconnect failed. Cannot execute command.")
            return False
            
    async def _execute_remote_command(self, command_name: str) -> CommandResult:
        """
        Helper to execute a remote control command safely.
        
        Args:
            command_name: Name of the remote command to execute
            
        Returns:
            CommandResult: Result of the command execution
        """
        if not await self._ensure_connected():
            return self.create_command_result(
                success=False,
                error="Failed to connect to Apple TV"
            )
            
        try:
            command_func = getattr(self.atv.remote_control, command_name)
            await command_func()
            logger.info(f"[{self.device_id}] Executed remote command: {command_name}")
            
            # Record this command in last_command
            self.update_state(last_command=LastCommand(
                action=command_name,
                source="remote_control",
                timestamp=datetime.now(),
                params=None
            ))
            
            return self.create_command_result(
                success=True,
                message=f"Remote command {command_name} executed successfully"
            )
        except AttributeError:
            error_msg = f"Remote command '{command_name}' not found in pyatv."
            logger.error(f"[{self.device_id}] {error_msg}")
            return self.create_command_result(
                success=False, 
                error=error_msg
            )
        except Exception as e:
            error_msg = f"Error executing remote command {command_name}: {str(e)}"
            logger.error(f"[{self.device_id}] {error_msg}", exc_info=True)
            self.update_state(error=error_msg)
            await self.publish_progress(error_msg)
            return self.create_command_result(
                success=False,
                error=error_msg
            )
            
    async def handle_power_on(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """
        Turn on the Apple TV.
        
        Args:
            cmd_config: Command configuration
            params: Parameters (unused)
            
        Returns:
            CommandResult: Result of the command execution
        """
        logger.info(f"[{self.device_id}] Attempting to turn ON (wake)...")
        if await self._ensure_connected():
            try:
                await self.atv.power.turn_on()
                logger.info(f"[{self.device_id}] Executed power on command.")
                
                # Schedule refresh after command
                asyncio.create_task(self._delayed_refresh(delay=2.0))
                
                return self.create_command_result(
                    success=True,
                    message="Power on command executed successfully"
                )
            except NotImplementedError:
                logger.warning(f"[{self.device_id}] Direct power on not supported, trying to send key instead...")
                # Fallback to sending a key press to wake
                # Use the CommandResult returned by _execute_remote_command
                return await self._execute_remote_command("select")
            except Exception as e:
                error_msg = f"Error turning on: {str(e)}"
                logger.error(f"[{self.device_id}] {error_msg}", exc_info=True)
                self.update_state(error=error_msg)
                await self.publish_progress(error_msg)
                return self.create_command_result(
                    success=False,
                    error=error_msg
                )
        
        return self.create_command_result(
            success=False,
            error="Failed to connect to Apple TV"
        )

    async def handle_power_off(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """
        Turn off the Apple TV (put to sleep).
        
        Args:
            cmd_config: Command configuration
            params: Parameters (unused)
            
        Returns:
            CommandResult: Result of the command execution
        """
        logger.info(f"[{self.device_id}] Attempting to turn OFF (sleep)...")
        # Use power off command if available, otherwise fallback to long home press?
        if await self._ensure_connected():
            try:
                await self.atv.power.turn_off()
                logger.info(f"[{self.device_id}] Executed power off command.")
                # State should update via listener, but schedule refresh just in case
                asyncio.create_task(self._delayed_refresh(delay=2.0))
                
                return self.create_command_result(
                    success=True,
                    message="Power off command executed successfully"
                )
            except NotImplementedError:
                logger.warning(f"[{self.device_id}] Direct power off not supported, trying long home press...")
                # Fallback: Press and hold home button (might bring up power menu on some tvOS versions)
                # Use the CommandResult returned by _execute_remote_command
                return await self._execute_remote_command("home_hold")
            except Exception as e:
                error_msg = f"Error turning off: {str(e)}"
                logger.error(f"[{self.device_id}] {error_msg}", exc_info=True)
                self.update_state(error=error_msg)
                await self.publish_progress(error_msg)
                return self.create_command_result(
                    success=False,
                    error=error_msg
                )
                
        return self.create_command_result(
            success=False,
            error="Failed to connect to Apple TV"
        )

    async def handle_play(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """
        Send Play command.
        
        Args:
            cmd_config: Command configuration
            params: Parameters (unused)
            
        Returns:
            CommandResult: Result of the command execution
        """
        remote_cmd_result = await self._execute_remote_command("play")
        if remote_cmd_result:
            asyncio.create_task(self._delayed_refresh()) # Refresh after action
            return self.create_command_result(
                success=True,
                message="Play command executed successfully"
            )
        else:
            return self.create_command_result(
                success=False,
                error="Failed to send play command"
            )

    async def handle_pause(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """
        Send Pause command.
        
        Args:
            cmd_config: Command configuration
            params: Parameters (unused)
            
        Returns:
            CommandResult: Result of the command execution
        """
        remote_cmd_result = await self._execute_remote_command("pause")
        if remote_cmd_result:
            asyncio.create_task(self._delayed_refresh()) # Refresh after action
            return self.create_command_result(
                success=True,
                message="Pause command executed successfully"
            )
        else:
            return self.create_command_result(
                success=False,
                error="Failed to send pause command"
            )

    async def handle_stop(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """
        Send Stop command.
        
        Args:
            cmd_config: Command configuration
            params: Parameters (unused)
            
        Returns:
            CommandResult: Result of the command execution
        """
        remote_cmd_result = await self._execute_remote_command("stop")
        if remote_cmd_result:
            asyncio.create_task(self._delayed_refresh()) # Refresh after action
            return self.create_command_result(
                success=True,
                message="Stop command executed successfully" 
            )
        else:
            return self.create_command_result(
                success=False,
                error="Failed to send stop command"
            )

    async def handle_next_track(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """
        Send Next command.
        
        Args:
            cmd_config: Command configuration
            params: Parameters (unused)
            
        Returns:
            CommandResult: Result of the command execution
        """
        remote_cmd_result = await self._execute_remote_command("next")
        if remote_cmd_result:
            asyncio.create_task(self._delayed_refresh()) # Refresh after action
            return self.create_command_result(
                success=True,
                message="Next track command executed successfully"
            )
        else:
            return self.create_command_result(
                success=False,
                error="Failed to send next track command"
            )

    async def handle_previous_track(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """
        Send Previous command.
        
        Args:
            cmd_config: Command configuration
            params: Parameters (unused)
            
        Returns:
            CommandResult: Result of the command execution
        """
        remote_cmd_result = await self._execute_remote_command("previous")
        if remote_cmd_result:
            asyncio.create_task(self._delayed_refresh()) # Refresh after action
            return self.create_command_result(
                success=True,
                message="Previous track command executed successfully"
            )
        else:
            return self.create_command_result(
                success=False,
                error="Failed to send previous track command"
            )

    async def handle_menu(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """
        Send Menu command.
        
        Args:
            cmd_config: Command configuration
            params: Parameters (unused)
            
        Returns:
            CommandResult: Result of the command execution
        """
        remote_cmd_result = await self._execute_remote_command("menu")
        if remote_cmd_result:
            return self.create_command_result(
                success=True,
                message="Menu command executed successfully"
            )
        else:
            return self.create_command_result(
                success=False,
                error="Failed to send menu command"
            )

    async def handle_home(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """
        Send Home command.
        
        Args:
            cmd_config: Command configuration
            params: Parameters (unused)
            
        Returns:
            CommandResult: Result of the command execution
        """
        remote_cmd_result = await self._execute_remote_command("home")
        if remote_cmd_result:
            return self.create_command_result(
                success=True,
                message="Home command executed successfully"
            )
        else:
            return self.create_command_result(
                success=False,
                error="Failed to send home command"
            )

    async def handle_select(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """
        Send Select command.
        
        Args:
            cmd_config: Command configuration
            params: Parameters (unused)
            
        Returns:
            CommandResult: Result of the command execution
        """
        remote_cmd_result = await self._execute_remote_command("select")
        if remote_cmd_result:
            return self.create_command_result(
                success=True,
                message="Select command executed successfully"
            )
        else:
            return self.create_command_result(
                success=False,
                error="Failed to send select command"
            )

    async def handle_up(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """
        Send Up command.
        
        Args:
            cmd_config: Command configuration
            params: Parameters (unused)
            
        Returns:
            CommandResult: Result of the command execution
        """
        remote_cmd_result = await self._execute_remote_command("up")
        if remote_cmd_result:
            return self.create_command_result(
                success=True,
                message="Up command executed successfully"
            )
        else:
            return self.create_command_result(
                success=False,
                error="Failed to send up command"
            )

    async def handle_down(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """
        Send Down command.
        
        Args:
            cmd_config: Command configuration
            params: Parameters (unused)
            
        Returns:
            CommandResult: Result of the command execution
        """
        remote_cmd_result = await self._execute_remote_command("down")
        if remote_cmd_result:
            return self.create_command_result(
                success=True,
                message="Down command executed successfully"
            )
        else:
            return self.create_command_result(
                success=False,
                error="Failed to send down command"
            )

    async def handle_left(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """
        Send Left command.
        
        Args:
            cmd_config: Command configuration
            params: Parameters (unused)
            
        Returns:
            CommandResult: Result of the command execution
        """
        remote_cmd_result = await self._execute_remote_command("left")
        if remote_cmd_result:
            return self.create_command_result(
                success=True,
                message="Left command executed successfully"
            )
        else:
            return self.create_command_result(
                success=False,
                error="Failed to send left command"
            )

    async def handle_right(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """
        Send Right command.
        
        Args:
            cmd_config: Command configuration
            params: Parameters (unused)
            
        Returns:
            CommandResult: Result of the command execution
        """
        remote_cmd_result = await self._execute_remote_command("right")
        if remote_cmd_result:
            return self.create_command_result(
                success=True,
                message="Right command executed successfully"
            )
        else:
            return self.create_command_result(
                success=False,
                error="Failed to send right command"
            )

    async def handle_set_volume(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """
        Set the volume level (0-100).
        
        Args:
            cmd_config: Command configuration
            params: Parameters with 'level' key for volume level (0-100)
            
        Returns:
            CommandResult: Result of the command execution
        """
        if not await self._ensure_connected():
            return self.create_command_result(
                success=False,
                error="Failed to connect to Apple TV"
            )
             
        if not hasattr(self.atv, "audio") or not hasattr(self.atv.audio, "set_volume"):
            error_msg = "Volume control not available on this device"
            logger.warning(f"[{self.device_id}] {error_msg}")
            return self.create_command_result(
                success=False,
                error=error_msg
            )

        try:
            # Get the level from params
            if "level" in params:
                level = params["level"]
                level = max(0, min(100, level))  # Clamp value to valid range
            else:
                error_msg = "No volume level provided in params"
                logger.error(f"[{self.device_id}] {error_msg}")
                return self.create_command_result(
                    success=False,
                    error=error_msg
                )
                
            normalized_level = level / 100.0
            
            logger.info(f"[{self.device_id}] Setting volume to {level}% ({normalized_level})...")
            await self.atv.audio.set_volume(normalized_level)
            
            # Update state immediately (optimistic)
            self.update_state(
                volume=level,
                last_command=LastCommand(
                    action="set_volume",
                    source="api",
                    timestamp=datetime.now(),
                    params={"level": level}
                )
            )
            
            asyncio.create_task(self._delayed_refresh()) 
            return self.create_command_result(
                success=True,
                message=f"Volume set to {level}%"
            )
            
        except ValueError:
            error_msg = "Invalid volume level: Must be integer 0-100."
            logger.error(f"[{self.device_id}] {error_msg}")
            return self.create_command_result(
                success=False,
                error=error_msg
            )
        except NotImplementedError:
            error_msg = "Set volume not implemented by this device/protocol."
            logger.warning(f"[{self.device_id}] {error_msg}")
            return self.create_command_result(
                success=False,
                error=error_msg
            )
        except Exception as e:
            error_msg = f"Error setting volume: {str(e)}"
            logger.error(f"[{self.device_id}] {error_msg}", exc_info=True)
            self.update_state(error=error_msg)
            await self.publish_progress(error_msg)
            return self.create_command_result(
                success=False,
                error=error_msg
            )

    async def handle_volume_up(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """
        Increase the volume.
        
        Args:
            cmd_config: Command configuration
            params: Parameters (unused)
            
        Returns:
            CommandResult: Result of the command execution
        """
        remote_cmd_result = await self._execute_remote_command("volume_up")
        if remote_cmd_result:
            asyncio.create_task(self._delayed_refresh())
            return self.create_command_result(
                success=True,
                message="Volume up command executed successfully"
            )
        else:
            return self.create_command_result(
                success=False,
                error="Failed to send volume up command"
            )

    async def handle_volume_down(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """
        Decrease the volume.
        
        Args:
            cmd_config: Command configuration
            params: Parameters (unused)
            
        Returns:
            CommandResult: Result of the command execution
        """
        remote_cmd_result = await self._execute_remote_command("volume_down")
        if remote_cmd_result:
            asyncio.create_task(self._delayed_refresh())
            return self.create_command_result(
                success=True,
                message="Volume down command executed successfully"
            )
        else:
            return self.create_command_result(
                success=False,
                error="Failed to send volume down command"
            )

    async def handle_launch_app(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """
        Launch an app on the Apple TV.
        
        Args:
            cmd_config: Command configuration
            params: Parameters with app_name key
            
        Returns:
            CommandResult: Result of the command execution
        """
        if not await self._ensure_connected():
            return self.create_command_result(
                success=False,
                error="Failed to connect to Apple TV"
            )

        app_id_to_launch = None
        app_name = None
        
        # Try to get app name from params
        if "app" in params:
            app_name = params["app"]
            logger.info(f"[{self.device_id}] Using app name from params: '{app_name}'")
        else:
            # Access from StandardCommandConfig
            if hasattr(cmd_config, "appid") and cmd_config.appid:
                app_id_to_launch = cmd_config.appid
                logger.info(f"[{self.device_id}] Using app ID from config: {app_id_to_launch}")
            else:
                # Fallback to appname attribute from config
                if hasattr(cmd_config, "appname") and cmd_config.appname:
                    app_name = cmd_config.appname
                else:
                    error_msg = "Cannot launch app: No app specified in params or config"
                    logger.error(f"[{self.device_id}] {error_msg}")
                    return self.create_command_result(
                        success=False,
                        error=error_msg
                    )
                logger.info(f"[{self.device_id}] Using app name from config: '{app_name}'")

        # If we have an app name but not an ID, look up the ID
        if app_name and not app_id_to_launch:
            logger.info(f"[{self.device_id}] Looking up app ID for name: '{app_name}'")
            
            # Ensure app list is populated
            if not self._app_list:
                await self._update_app_list() # Try to fetch if empty
                if not self._app_list:
                    error_msg = f"App list is empty, cannot find app '{app_name}'."
                    logger.error(f"[{self.device_id}] {error_msg}")
                    self.update_state(error="App list unavailable")
                    return self.create_command_result(
                        success=False,
                        error=error_msg
                    )

            # Perform case-insensitive lookup
            app_id_to_launch = self._app_list.get(app_name.lower())

            if not app_id_to_launch:
                error_msg = f"App '{app_name}' not found in the installed apps list."
                logger.error(f"[{self.device_id}] {error_msg}")
                self.update_state(error=f"App not found: {app_name}")
                return self.create_command_result(
                    success=False,
                    error=error_msg
                )
            else:
                logger.info(f"[{self.device_id}] Found app ID: {app_id_to_launch} for name '{app_name}'")

        # Create the params for LastCommand
        command_params = {"app_id": app_id_to_launch}
        if app_name:
            command_params["app_name"] = app_name

        # Execute launch
        try:
            logger.info(f"[{self.device_id}] Launching app: {app_id_to_launch}...")
            await self.atv.apps.launch_app(app_id_to_launch)
            logger.info(f"[{self.device_id}] Launch command sent for {app_id_to_launch}.")
            
            # Update last_command with app launch details
            self.update_state(
                last_command=LastCommand(
                    action="launch_app",
                    source="api",
                    timestamp=datetime.now(),
                    params=command_params
                )
            )
            
            # Schedule refresh to see if app changed
            asyncio.create_task(self._delayed_refresh(delay=2.0)) 
            return self.create_command_result(
                success=True,
                message=f"App launch command sent for {app_name or app_id_to_launch}"
            )
        except Exception as e:
            error_msg = f"Error launching app {app_id_to_launch}: {str(e)}"
            logger.error(f"[{self.device_id}] {error_msg}", exc_info=True)
            self.update_state(error=error_msg)
            await self.publish_progress(error_msg)
            return self.create_command_result(
                success=False,
                error=error_msg
            )

    async def _delayed_refresh(self, delay: float = 1.0):
        """
        Schedule a status refresh after a delay.
        
        Args:
            delay: Delay in seconds before refreshing status
        """
        await asyncio.sleep(delay)
        
        # Create a minimal config for the handler
        config = StandardCommandConfig(
            id="refresh_status",
            action="refresh_status"
        )
        
        # Call the handler directly
        await self.handle_refresh_status(config, {})

    async def handle_get_app_list(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """
        Retrieve list of installed apps on the Apple TV.
        
        Args:
            cmd_config: Command configuration
            params: Parameters (unused)
            
        Returns:
            CommandResult: Result containing list of app_id and app_name pairs
        """
        logger.info(f"[{self.device_id}] Retrieving app list...")
        
        if not await self._ensure_connected():
            return self.create_command_result(
                success=False,
                error="Failed to connect to Apple TV"
            )
        
        try:
            # Update the app list to ensure it's current
            await self._update_app_list()
            
            if not self._app_list:
                error_msg = "Failed to retrieve app list or no apps found"
                logger.warning(f"[{self.device_id}] {error_msg}")
                return self.create_command_result(
                    success=False,
                    error=error_msg
                )
            
            # Transform the app list from {app_name_lowercase: app_id} format
            # to a list of {app_id, app_name} pairs
            app_list_result = []
            for app_name, app_id in self._app_list.items():
                app_list_result.append({
                    "app_id": app_id,
                    "app_name": app_name.title()  # Convert back to title case for display
                })
            
            # Sort by app name for easier browsing
            app_list_result.sort(key=lambda x: x["app_name"])
            
            # Update last_command state
            self.update_state(
                last_command=LastCommand(
                    action="get_app_list",
                    source="api",
                    timestamp=datetime.now(),
                    params={"count": len(app_list_result)}
                )
            )
            
            logger.info(f"[{self.device_id}] Retrieved {len(app_list_result)} apps")
            
            return self.create_command_result(
                success=True,
                message=f"Retrieved {len(app_list_result)} apps",
                data={"apps": app_list_result}
            )
            
        except Exception as e:
            error_msg = f"Error retrieving app list: {str(e)}"
            logger.error(f"[{self.device_id}] {error_msg}", exc_info=True)
            self.update_state(error=error_msg)
            await self.publish_progress(error_msg)
            return self.create_command_result(
                success=False,
                error=error_msg
            )


# === PyATV Listener ===

class PyATVDeviceListener(DeviceListener):
    """Listener for pyatv events (connection status, updates)."""
    
    def __init__(self, device: AppleTVDevice):
        """Initialize the listener with a reference to the AppleTVDevice."""
        self.device = device  # Reference to the main AppleTVDevice instance
        self.loop = asyncio.get_event_loop()

    def connection_lost(self, exception):
        """
        Called by pyatv when connection is lost unexpectedly.
        
        Args:
            exception: The exception that caused the connection loss, if any
        """
        logger.warning(f"[{self.device.device_id}] Connection lost: {exception}")
        
        self.device.update_state(
            connected=False,
            power="off",  # Assume off
            error=str(exception) if exception else "Connection lost",
            last_command=LastCommand(
                action="connection_lost",
                source="system",
                timestamp=datetime.now(),
                params={"error": str(exception) if exception else "Connection lost"}
            )
        )
        
        self.device.atv = None  # Clear device instance
        
        # Schedule state publish in the event loop
        self.loop.call_soon_threadsafe(asyncio.create_task, 
            self.device.publish_progress(f"Connection lost: {exception if exception else 'Unknown reason'}"))
    
    def connection_closed(self):
        """Called by pyatv when connection is closed intentionally (by self.atv.close())."""
        # This might be redundant if disconnect_from_device already handles state update,
        # but good to have as a fallback.
        if self.device.state.connected:  # Only log/update if we thought we were connected
            logger.info(f"[{self.device.device_id}] Connection closed.")
            
            self.device.update_state(
                connected=False,
                power="off",
                last_command=LastCommand(
                    action="connection_closed",
                    source="system",
                    timestamp=datetime.now(),
                    params=None
                )
            )
            
            self.device.atv = None
            
            # Schedule state publish in the event loop
            self.loop.call_soon_threadsafe(asyncio.create_task,
                self.device.publish_progress("Connection closed"))

    def device_update(self, playing: Playing):
        """
        Called by pyatv when media playback state changes.
        
        Args:
            playing: Object containing the current playback information
        """
        logger.debug(f"[{self.device.device_id}] Received device update (playing): {playing}")
        
        # Update state using helper
        self.device._update_playing_state(playing)
        
        # Record playback update in last_command
        if playing and playing.device_state:
            playback_info = {
                "state": playing.device_state.name.lower(),
                "title": playing.title,
                "artist": playing.artist,
            }
            
            self.device.update_state(
                last_command=LastCommand(
                    action="playback_update",
                    source="device",
                    timestamp=datetime.now(),
                    params=playback_info
                )
            )
        
        # Schedule state publish
        self.loop.call_soon_threadsafe(asyncio.create_task, 
            self.device.publish_progress(f"Playback state updated: {playing.device_state.name if playing and playing.device_state else 'idle'}"))

    def device_error(self, error: Exception):
        """
        Called by pyatv on certain device errors (less common).
        
        Args:
            error: The exception that occurred
        """
        logger.error(f"[{self.device.device_id}] Received device error from listener: {error}")
        
        self.device.update_state(
            error=f"Listener error: {str(error)}",
            last_command=LastCommand(
                action="device_error",
                source="device",
                timestamp=datetime.now(),
                params={"error": str(error)}
            )
        )
        
        self.loop.call_soon_threadsafe(asyncio.create_task, 
            self.device.publish_progress(f"Device error: {str(error)}")) 