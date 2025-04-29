import asyncio
import json
import logging
import os
from typing import Dict, List, Any, Optional, cast
from functools import partial # Added for potential future use if needed

import pyatv
from pyatv import scan, connect
from pyatv.const import Protocol as ProtocolType, PowerState
from pyatv.interface import DeviceListener, Playing
from pyatv.exceptions import AuthenticationError, ConnectionFailedError

from devices.base_device import BaseDevice
from app.schemas import AppleTVState, AppleTVDeviceConfig, StandardCommandConfig, LastCommand
from app.mqtt_client import MQTTClient

logger = logging.getLogger(__name__) # Define logger for the module

class AppleTVDevice(BaseDevice):
    """Apple TV device integration for wb-mqtt-bridge, compliant with BaseDevice."""
    
    def __init__(self, config: AppleTVDeviceConfig, mqtt_client: Optional[MQTTClient] = None):
        """Initialize the Apple TV device."""
        # Call BaseDevice init first with proper Pydantic config
        super().__init__(config, mqtt_client)
        
        # Store the config directly as it's already a Pydantic model
        self.typed_config = config
        
        # Get Apple TV configuration directly from the typed config
        self.apple_tv_config = self.typed_config.apple_tv
        
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
            last_command=None  # Standard state field from BaseDevice
        )
        
        # Populate action handlers expected by BaseDevice
        # Action names (keys) should match the 'action' field in the device config JSON
        self._action_handlers = {
            "power_on": self.turn_on,
            "power_off": self.turn_off,
            "play": self.play,
            "pause": self.pause,
            "stop": self.stop,
            "next": self.next_track,
            "previous": self.previous_track,
            "set_volume": self.set_volume,
            "volume_up": self.volume_up,
            "volume_down": self.volume_down,
            "launch_app": self.launch_app,
            "refresh_status": self.refresh_status,
            "menu": self.menu, # Adding common remote buttons
            "home": self.home,
            "select": self.select,
            "up": self.up,
            "down": self.down,
            "left": self.left,
            "right": self.right
        }

        # Action groups (optional, but can be useful for organization)
        # self.action_groups remains available from BaseDevice via get_available_commands() in config
        
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
                self.state.error = f"No Apple TV found at {ip_address}"
                await self.publish_state() # Publish initial error state
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
             self.state.error = "Connection refused"
             await self.publish_state()
             return False
        except AuthenticationError as e:
             logger.error(f"[{self.device_id}] Authentication failed: {e}. Check credentials or pairing.")
             self.state.error = f"Authentication failed: {e}"
             await self.publish_state()
             return False
        except ConnectionFailedError as e:
            logger.error(f"[{self.device_id}] Connection failed: {e}")
            self.state.error = f"Connection failed: {e}"
            await self.publish_state()
            return False
        except Exception as e:
            logger.error(f"[{self.device_id}] Unexpected error during setup: {e}", exc_info=True)
            self.state.error = f"Setup error: {str(e)}"
            await self.publish_state()
            return False
    
    async def shutdown(self) -> bool:
        """Shut down the Apple TV device connection."""
        logger.info(f"[{self.device_id}] Shutting down connection.")
        return await self.disconnect_from_device()

    async def publish_state(self):
        """Publish the current device state to MQTT."""
        if not self.mqtt_client:
            logger.warning(f"[{self.device_id}] MQTT client not available, cannot publish state.")
            return

        try:
            # Publish full state to base topic
            state_topic = f"{self.base_topic}/state"
            # Use Pydantic's json() method to serialize the state model to JSON
            state_payload = self.state.model_dump_json()
            await self.mqtt_client.publish(state_topic, state_payload, retain=True) 
            logger.debug(f"[{self.device_id}] Published full state to {state_topic}")

            # Publish individual state components if configured/needed (Optional)
            # Example: Power state
            power_topic = f"{self.base_topic}/power_state"
            if self.state.power is not None:
                await self.mqtt_client.publish(power_topic, self.state.power, retain=True)

            # Example: Volume level
            volume_topic = f"{self.base_topic}/volume_level"
            if self.state.volume is not None:
                 await self.mqtt_client.publish(volume_topic, str(self.state.volume), retain=True)
                 
            # Example: Current App
            app_topic = f"{self.base_topic}/current_app"
            if self.state.app is not None:
                 await self.mqtt_client.publish(app_topic, self.state.app, retain=True)

            # Example: Playback details (as JSON)
            playback_topic = f"{self.base_topic}/playback_details"
            playback_state = {
                "state": self.state.playback_state,
                "media_type": self.state.media_type,
                "title": self.state.title,
                "artist": self.state.artist,
                "album": self.state.album,
                "position": self.state.position,
                "total_time": self.state.total_time
            }
            if playback_state["state"]: # Only publish if playback state is known
                await self.mqtt_client.publish(playback_topic, json.dumps(playback_state), retain=True)

        except Exception as e:
            logger.error(f"[{self.device_id}] Error publishing state: {e}", exc_info=True)

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
            
            self.state.connected = True
            self.state.ip_address = self.atv_config.address # Update IP just in case
            self.state.error = None # Clear previous errors
            
            # Assign listener for connection events and updates
            self.atv.listener = PyATVDeviceListener(self) 
            
            # Perform initial status refresh and app list update
            await self.refresh_status(publish=False) # Don't publish yet, wait for app list
            await self._update_app_list()
            
            # Now publish the full initial state
            await self.publish_state()
            return True
            
        except AuthenticationError as e:
             logger.error(f"[{self.device_id}] Authentication failed during connect: {e}. Check credentials/pairing.")
             self.state.connected = False
             self.state.error = f"Authentication failed: {e}"
             self.atv = None
             await self.publish_state()
             return False
        except ConnectionFailedError as e:
            logger.error(f"[{self.device_id}] Connection failed: {e}")
            self.state.connected = False
            self.state.error = f"Connection failed: {e}"
            self.atv = None
            await self.publish_state()
            return False
        except Exception as e:
            logger.error(f"[{self.device_id}] Unexpected error connecting: {e}", exc_info=True)
            self.state.connected = False
            self.state.error = f"Connection error: {str(e)}"
            self.atv = None
            await self.publish_state()
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
                self.state.connected = False
                self.state.power = "off" # Assume off if disconnected
                self.state.playback_state = None # Reset playback
                self.state.app = None # Reset app
                # Don't clear error here, might be reason for disconnect
                await self.publish_state()
        else:
             logger.info(f"[{self.device_id}] Already disconnected.")
             return True # Indicate success as it's already in desired state

    async def _update_app_list(self):
        """Fetch and store the list of installed applications."""
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
            # Keep the old list? Or clear it? Let's keep it for now.

    async def refresh_status(self, cmd_config: Optional[StandardCommandConfig] = None, params: Dict[str, Any] = None, *, publish: bool = True):
        """
        Refresh the Apple TV status.
        
        Args:
            cmd_config: Command configuration (optional)
            params: Parameters (unused)
            publish: Whether to publish the state after refresh
        """
        if not self.atv or not self.state.connected:
            logger.warning(f"[{self.device_id}] Cannot refresh status: not connected.")
            # Try to reconnect if requested via command? Maybe too aggressive.
            # Let's just update state to disconnected if possible.
            if self.state.connected:
                 self.state.connected = False
                 self.state.power = "off"
                 if publish: await self.publish_state()
            return
        
        logger.info(f"[{self.device_id}] Refreshing status...")
        try:
            # Power State (more reliable than just checking connection)
            power_info = self.atv.power.power_state
            self.state.power = power_info.name.lower() # Should be 'on' or 'off'
            
            # If power is off, no point checking media etc.
            if self.state.power != PowerState.On.name.lower():
                 logger.info(f"[{self.device_id}] Device is not powered on ({self.state.power}), skipping detailed status.")
                 # Reset media/app state if device turned off
                 self.state.app = None
                 self.state.playback_state = None 
                 self.state.title = None
                 self.state.artist = None
                 self.state.album = None
                 self.state.position = None
                 self.state.total_time = None
                 # Keep volume? Let's reset it for now.
                 # self.state.volume = None 
                 if publish: await self.publish_state()
                 return

            # Get current app (only if powered on)
            app_info = await self.atv.apps.current_app()
            self.state.app = app_info.name if app_info else None
            
            # Get playback state (only if powered on)
            playing_info = await self.atv.metadata.playing()
            self._update_playing_state(playing_info) # Use helper method

            # Get volume if available (only if powered on)
            if hasattr(self.atv, "audio") and hasattr(self.atv.audio, "volume"):
                try:
                    volume_level = await self.atv.audio.volume() # 0.0 to 1.0
                    if volume_level is not None:
                        self.state.volume = int(volume_level * 100)
                    else:
                         self.state.volume = None # Explicitly set to None if unavailable
                except NotImplementedError:
                    logger.debug(f"[{self.device_id}] Volume control not implemented by device/protocol.")
                    self.state.volume = None
                except Exception as e:
                    logger.warning(f"[{self.device_id}] Could not get volume: {e}")
                    self.state.volume = None # Ensure state reflects uncertainty
            else:
                 logger.debug(f"[{self.device_id}] Volume control not available via pyatv for this connection.")
                 self.state.volume = None

            self.state.error = None # Clear error on successful refresh
            logger.info(f"[{self.device_id}] Status refresh complete.")

        except Exception as e:
            logger.error(f"[{self.device_id}] Error refreshing status: {e}", exc_info=True)
            self.state.error = f"Status refresh error: {str(e)}"
            # Should we assume disconnected on error? Maybe too drastic. Keep connected state.
            
        # Publish updated state if requested
        if publish:
             await self.publish_state()
             
    def _update_playing_state(self, playing: Optional[Playing]):
        """Helper to update state dictionary from pyatv Playing object."""
        if playing and playing.device_state:
            self.state.playback_state = playing.device_state.name.lower() # idle, paused, playing, stopped, seeking, loading
            self.state.media_type = playing.media_type.name.lower() if playing.media_type else None # music, video, tv, unknown
            self.state.title = playing.title
            self.state.artist = playing.artist
            self.state.album = playing.album
            # Ensure position/total_time are ints or None
            self.state.position = int(playing.position) if playing.position is not None else None
            self.state.total_time = int(playing.total_time) if playing.total_time is not None else None
        else:
            # If nothing is playing or info is unavailable
            self.state.playback_state = "idle" # Assume idle if not explicitly known
            self.state.media_type = None
            self.state.title = None
            self.state.artist = None
            self.state.album = None
            self.state.position = None
            self.state.total_time = None

    # --- Action Handlers (called by BaseDevice._execute_single_action) ---
    # Signature: async def handler(self, action_config: Dict[str, Any], payload: str)

    async def _ensure_connected(self) -> bool:
        """Ensure device is connected, attempting to connect if not."""
        if self.atv and self.state.connected:
            return True
        logger.warning(f"[{self.device_id}] Not connected. Attempting to reconnect...")
        if await self.connect_to_device():
            # Brief pause to allow connection to stabilize before command
            await asyncio.sleep(0.5) 
            return True
        else:
            logger.error(f"[{self.device_id}] Reconnect failed. Cannot execute command.")
            return False
            
    async def _execute_remote_command(self, command_name: str):
        """Helper to execute a remote control command safely."""
        if not await self._ensure_connected():
             return False
        try:
            command_func = getattr(self.atv.remote_control, command_name)
            await command_func()
            logger.info(f"[{self.device_id}] Executed remote command: {command_name}")
            # Optional: Trigger a status refresh after a short delay
            # asyncio.create_task(self._delayed_refresh()) 
            return True
        except AttributeError:
             logger.error(f"[{self.device_id}] Remote command '{command_name}' not found in pyatv.")
             return False
        except Exception as e:
            logger.error(f"[{self.device_id}] Error executing remote command {command_name}: {e}", exc_info=True)
            self.state.error = f"Command error: {str(e)}"
            await self.publish_state() # Publish error state
            return False
            
    async def _delayed_refresh(self, delay: float = 1.0):
         """Schedule a status refresh after a delay."""
         await asyncio.sleep(delay)
         await self.refresh_status()

    async def turn_on(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]):
        """
        Turn on the Apple TV.
        
        Args:
            cmd_config: Command configuration
            params: Parameters (unused)
        """
        logger.info(f"[{self.device_id}] Attempting to turn ON (wake)...")
        if await self._ensure_connected():
            try:
                await self.atv.power.turn_on()
                logger.info(f"[{self.device_id}] Executed power on command.")
                # State should update via listener, but schedule refresh just in case
                asyncio.create_task(self._delayed_refresh(delay=2.0))
            except NotImplementedError:
                 logger.warning(f"[{self.device_id}] Direct power on not supported, trying to send key instead...")
                 # Fallback to sending a key press to wake
                 await self._execute_remote_command("select") # Menu/select often works
                 asyncio.create_task(self._delayed_refresh(delay=2.0))
            except Exception as e:
                logger.error(f"[{self.device_id}] Error turning on: {e}", exc_info=True)
                self.state.error = f"Turn on error: {str(e)}"
                await self.publish_state()

    async def turn_off(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]):
        """Turn off the Apple TV (put to sleep)."""
        logger.info(f"[{self.device_id}] Attempting to turn OFF (sleep)...")
        # Use power off command if available, otherwise fallback to long home press?
        if await self._ensure_connected():
            try:
                await self.atv.power.turn_off()
                logger.info(f"[{self.device_id}] Executed power off command.")
                # State should update via listener, but schedule refresh just in case
                asyncio.create_task(self._delayed_refresh(delay=2.0))
            except NotImplementedError:
                 logger.warning(f"[{self.device_id}] Direct power off not supported, trying long home press...")
                 # Fallback: Press and hold home button (might bring up power menu on some tvOS versions)
                 await self._execute_remote_command("home_hold") 
                 asyncio.create_task(self._delayed_refresh(delay=2.0))
            except Exception as e:
                logger.error(f"[{self.device_id}] Error turning off: {e}", exc_info=True)
                self.state.error = f"Turn off error: {str(e)}"
                await self.publish_state()

    async def play(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]):
        """Send Play command."""
        if await self._execute_remote_command("play"):
             asyncio.create_task(self._delayed_refresh()) # Refresh after action

    async def pause(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]):
        """Send Pause command."""
        if await self._execute_remote_command("pause"):
             asyncio.create_task(self._delayed_refresh()) # Refresh after action

    async def stop(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]):
        """Send Stop command."""
        if await self._execute_remote_command("stop"):
             asyncio.create_task(self._delayed_refresh()) # Refresh after action

    async def next_track(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]):
        """Send Next command."""
        if await self._execute_remote_command("next"):
             asyncio.create_task(self._delayed_refresh()) # Refresh after action

    async def previous_track(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]):
        """Send Previous command."""
        if await self._execute_remote_command("previous"):
             asyncio.create_task(self._delayed_refresh()) # Refresh after action
             
    async def menu(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]):
        """Send Menu command."""
        await self._execute_remote_command("menu")

    async def home(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]):
        """Send Home command."""
        await self._execute_remote_command("home")
        
    async def select(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]):
        """Send Select command."""
        await self._execute_remote_command("select")
        
    async def up(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]):
        """Send Up command."""
        await self._execute_remote_command("up")
        
    async def down(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]):
        """Send Down command."""
        await self._execute_remote_command("down")
        
    async def left(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]):
        """Send Left command."""
        await self._execute_remote_command("left")
        
    async def right(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]):
        """Send Right command."""
        await self._execute_remote_command("right")

    async def set_volume(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]):
        """Set the volume level (0-100)."""
        if not await self._ensure_connected():
             return
             
        if not hasattr(self.atv, "audio") or not hasattr(self.atv.audio, "set_volume"):
             logger.warning(f"[{self.device_id}] Volume control not available.")
             return

        try:
            # Get the level from params
            if "level" in params:
                level = params["level"]
                level = max(0, min(100, level))  # Clamp value to valid range
            else:
                logger.error(f"[{self.device_id}] No volume level provided in params")
                return
                
            normalized_level = level / 100.0
            
            logger.info(f"[{self.device_id}] Setting volume to {level}% ({normalized_level})...")
            await self.atv.audio.set_volume(normalized_level)
            
            # Update state immediately (optimistic) and schedule refresh
            self.state.volume = level
            asyncio.create_task(self._delayed_refresh()) 
            
        except ValueError:
             logger.error(f"[{self.device_id}] Invalid volume level: Must be integer 0-100.")
        except NotImplementedError:
             logger.warning(f"[{self.device_id}] Set volume not implemented by device/protocol.")
        except Exception as e:
            logger.error(f"[{self.device_id}] Error setting volume: {e}", exc_info=True)
            self.state.error = f"Set volume error: {str(e)}"
            await self.publish_state()

    async def volume_up(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]):
        """Increase the volume."""
        if await self._execute_remote_command("volume_up"):
             asyncio.create_task(self._delayed_refresh())

    async def volume_down(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]):
        """Decrease the volume."""
        if await self._execute_remote_command("volume_down"):
             asyncio.create_task(self._delayed_refresh())

    async def launch_app(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]):
        """
        Launch an app on the Apple TV.
        
        Args:
            cmd_config: Command configuration
            params: Parameters with app_name key
        """
        if not await self._ensure_connected():
            return

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
                    logger.error(f"[{self.device_id}] Cannot launch app: No app specified in params or config")
                    return
                logger.info(f"[{self.device_id}] Using app name from config: '{app_name}'")

        # If we have an app name but not an ID, look up the ID
        if app_name and not app_id_to_launch:
            logger.info(f"[{self.device_id}] Looking up app ID for name: '{app_name}'")
            
            # Ensure app list is populated
            if not self._app_list:
                 await self._update_app_list() # Try to fetch if empty
                 if not self._app_list:
                      logger.error(f"[{self.device_id}] App list is empty, cannot find app '{app_name}'.")
                      self.state.error = "App list unavailable"
                      await self.publish_state()
                      return

            # Perform case-insensitive lookup
            app_id_to_launch = self._app_list.get(app_name.lower())

            if not app_id_to_launch:
                 logger.error(f"[{self.device_id}] App '{app_name}' not found in the installed apps list.")
                 self.state.error = f"App not found: {app_name}"
                 await self.publish_state()
                 return
            else:
                 logger.info(f"[{self.device_id}] Found app ID: {app_id_to_launch} for name '{app_name}'")

        # Execute launch
        try:
            logger.info(f"[{self.device_id}] Launching app: {app_id_to_launch}...")
            await self.atv.apps.launch_app(app_id_to_launch)
            logger.info(f"[{self.device_id}] Launch command sent for {app_id_to_launch}.")
            # Schedule refresh to see if app changed
            asyncio.create_task(self._delayed_refresh(delay=2.0)) 
        except Exception as e:
            logger.error(f"[{self.device_id}] Error launching app {app_id_to_launch}: {e}", exc_info=True)
            self.state.error = f"Launch app error: {str(e)}"
            await self.publish_state()


# === PyATV Listener ===

class PyATVDeviceListener(DeviceListener):
    """Listener for pyatv events (connection status, updates)."""
    
    def __init__(self, device: AppleTVDevice):
        self.device = device # Reference to the main AppleTVDevice instance
        self.loop = asyncio.get_event_loop()

    def connection_lost(self, exception):
        """Called by pyatv when connection is lost unexpectedly."""
        logger.warning(f"[{self.device.device_id}] Connection lost: {exception}")
        self.device.state.connected = False
        self.device.state.power = "off" # Assume off
        self.device.state.error = str(exception) if exception else "Connection lost"
        self.device.atv = None # Clear device instance
        
        # Schedule state publish in the event loop
        self.loop.call_soon_threadsafe(asyncio.create_task, self.device.publish_state())
    
    def connection_closed(self):
        """Called by pyatv when connection is closed intentionally (by self.atv.close())."""
        # This might be redundant if disconnect_from_device already handles state update,
        # but good to have as a fallback.
        if self.device.state.connected: # Only log/update if we thought we were connected
             logger.info(f"[{self.device.device_id}] Connection closed.")
             self.device.state.connected = False
             self.device.state.power = "off"
             self.device.atv = None
             # Schedule state publish in the event loop
             self.loop.call_soon_threadsafe(asyncio.create_task, self.device.publish_state())

    def device_update(self, playing: Playing):
        """Called by pyatv when media playback state changes."""
        logger.debug(f"[{self.device.device_id}] Received device update (playing): {playing}")
        # Update state using helper
        self.device._update_playing_state(playing)
        # Schedule state publish
        self.loop.call_soon_threadsafe(asyncio.create_task, self.device.publish_state())

    def device_error(self, error: Exception):
         """Called by pyatv on certain device errors (less common)."""
         logger.error(f"[{self.device.device_id}] Received device error from listener: {error}")
         self.device.state.error = f"Listener error: {str(error)}"
         # Potentially mark as disconnected? Depends on error type.
         # self.device.state.connected = False 
         self.loop.call_soon_threadsafe(asyncio.create_task, self.device.publish_state()) 