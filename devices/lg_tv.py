import json
import logging
import asyncio
import os
import ssl
from typing import Dict, Any, List, Optional, Tuple, TYPE_CHECKING, Union, cast, Protocol, TypeVar

# Import WebOSClient which should always be available
from asyncwebostv.connection import WebOSClient

# Direct import without try/except - if this fails, it means the dependency is missing
# which is a real error we want to know about
from asyncwebostv.secure_connection import SecureWebOSClient

from asyncwebostv.controls import (
    MediaControl,
    SystemControl,
    ApplicationControl,
    TvControl,
    InputControl,
    SourceControl
)
from devices.base_device import BaseDevice
from app.schemas import LgTvState, LgTvConfig, LastCommand
from app.mqtt_client import MQTTClient
from datetime import datetime

logger = logging.getLogger(__name__)

class LgTv(BaseDevice):
    """Implementation of an LG TV controlled over the network using AsyncWebOSTV library."""
    
    def __init__(self, config: Dict[str, Any], mqtt_client: Optional[MQTTClient] = None):
        super().__init__(config, mqtt_client)
        self._state_schema = LgTvState
        self.state = {
            "power": "unknown",
            "volume": 0,
            "mute": False,
            "current_app": None,
            "input_source": None,
            "last_command": None,
            "connected": False,
            "ip_address": None,
            "mac_address": None
        }
        self.client = None
        self.system = None
        self.media = None
        self.app = None
        self.tv_control = None
        self.input_control = None
        self.source_control = None
        self.client_key = None
        self.tv_config = None
    
    async def setup(self) -> bool:
        """Initialize the TV device configuration.
        
        This method validates the configuration and prepares the device for connection,
        but does not actually connect to the TV.
        """
        try:
            # Get TV-specific configuration
            tv_dict = self.config.get("tv", {})
            if not tv_dict:
                logger.error(f"Missing 'tv' configuration for {self.get_name()}")
                self.state["error"] = "Missing TV configuration"
                return False
                
            # Validate TV configuration with pydantic model
            try:
                self.tv_config = LgTvConfig(**tv_dict)
            except Exception as e:
                logger.error(f"Invalid TV configuration for device: {self.get_name()}: {str(e)}")
                self.state["error"] = f"Invalid TV configuration: {str(e)}"
                return False
                
            # Update state with configuration values
            self.state["ip_address"] = self.tv_config.ip_address
            self.state["mac_address"] = self.tv_config.mac_address
            
            # Store client key for WebOS authentication
            self.client_key = self.tv_config.client_key
            
            # Log a message if no client key is provided
            if not self.client_key:
                logger.warning(f"No client key provided for TV {self.get_name()}. Connection will likely fail.")
            
            # Configuration is valid
            logger.info(f"TV device {self.get_name()} is properly configured")
            
            # Attempt initial connection, but don't fail setup if it doesn't connect
            try:
                await self.connect()
            except Exception as e:
                logger.warning(f"Initial connection attempt failed for {self.get_name()}: {str(e)}")
                # Connection failure shouldn't cause setup to fail if config is valid
            
            # Setup is successful if configuration is valid
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize TV {self.get_name()}: {str(e)}")
            self.state["error"] = str(e)
            return False
    
    async def connect(self) -> bool:
        """Public method to establish a connection to the TV.
        
        This can be called during setup or anytime a reconnection is needed.
        The connection will only use the client key provided in the configuration.
        """
        try:
            # Verify we have a client key before attempting connection
            if not self.client_key:
                logger.error(f"Cannot connect to TV {self.get_name()}: No client key provided in configuration.")
                self.state["connected"] = False
                self.state["error"] = "Missing client key in configuration"
                return False
                
            connection_result = await self._connect_to_tv()
            
            if connection_result:
                logger.info(f"Successfully connected to TV {self.get_name()}")
                self.state["connected"] = True
                self.state["error"] = None
            else:
                logger.error(f"Failed to connect to TV {self.get_name()}")
                self.state["connected"] = False
                if not self.state.get("error"):
                    self.state["error"] = "Failed to connect to TV"
                    
            return connection_result
        except Exception as e:
            logger.error(f"Unexpected error connecting to TV {self.get_name()}: {str(e)}")
            self.state["connected"] = False
            self.state["error"] = str(e)
            return False
    
    async def shutdown(self) -> bool:
        """Clean up resources and disconnect from the TV."""
        try:
            # Disconnect from TV
            if self.client:
                await self.client.close()  # Use close() instead of disconnect()
                self.client = None
                self.state["connected"] = False
                logger.info(f"Disconnected from TV {self.get_name()}")
            return True
        except Exception as e:
            logger.error(f"Error during device shutdown: {str(e)}")
            return False
    
    async def _connect_to_tv(self) -> bool:
        """Connect to the TV using the configured parameters.
        
        This is an internal method that handles the WebOS connection logic.
        It will attempt to connect using the provided client key. If the connection
        fails and a MAC address is available, it will try to wake the TV using
        Wake-on-LAN and attempt the connection again.
        """
        try:
            # Check if we have configuration and IP address
            if not self.tv_config:
                logger.error("TV configuration not initialized")
                return False
                
            ip = self.state.get("ip_address")
            if not ip:
                logger.error("No IP address configured for TV")
                return False
                
            # Use secure WebSocket mode from config
            secure_mode = self.tv_config.secure
            
            # Get certificate file path if provided
            cert_file = self.tv_config.cert_file
            
            # Get any additional SSL options
            ssl_options = {}
            if hasattr(self.tv_config, 'ssl_options') and self.tv_config.ssl_options:
                ssl_options = self.tv_config.ssl_options
            
            # Verify we have a client key before attempting connection
            if not self.client_key:
                logger.error("No client key provided in configuration. Cannot connect to TV.")
                self.state["error"] = "Missing client key in configuration"
                return False
            
            # Create a new TV client with appropriate security settings
            if secure_mode:
                logger.info(f"Creating secure WebOS client for {ip}")
                
                # Ensure port is set to 3001 for secure WebSocket connections
                if 'port' not in ssl_options:
                    ssl_options['port'] = 3001
                
                # Let SecureWebOSClient handle the SSL context creation based on cert_file and verify_ssl
                # This ensures hostname verification is properly disabled
                self.client = SecureWebOSClient(
                    host=ip,
                    secure=True,
                    client_key=self.client_key,
                    verify_ssl=False,  # Critical: Always use False to disable hostname checking
                    cert_file=cert_file,  # Pass cert_file directly and let SecureWebOSClient handle it
                    **ssl_options
                )
            else:
                logger.info(f"Creating standard WebOS client for {ip}")
                self.client = WebOSClient(ip, secure=False, client_key=self.client_key)
            
            # First connection attempt
            connection_success = False
            try:
                logger.info(f"Attempting to connect to TV at {ip}...")
                await self.client.connect()
                connection_success = True
            except ssl.SSLError as ssl_error:
                logger.error(f"SSL error during connection: {str(ssl_error)}")
                self.state["error"] = f"SSL connection error: {str(ssl_error)}"
                
                # Check if it's a certificate verification error
                if "CERTIFICATE_VERIFY_FAILED" in str(ssl_error) and secure_mode:
                    logger.warning("Certificate verification failed. Consider extracting the TV certificate using extract_lg_tv_cert.py")
                    
                    # If fallback is possible, try without SSL context
                    has_fallback = False
                    if hasattr(self.tv_config, 'ssl_options') and self.tv_config.ssl_options:
                        has_fallback = self.tv_config.ssl_options.get("allow_insecure_fallback", False)
                        
                    if has_fallback:
                        logger.info("Attempting fallback connection without SSL context...")
                        try:
                            # Create a new client without cert_file to avoid SSL verification
                            self.client = SecureWebOSClient(
                                host=ip,
                                secure=True,
                                client_key=self.client_key,
                                verify_ssl=False,
                                # No cert_file to avoid verification issues
                                **ssl_options
                            )
                            await self.client.connect()
                            connection_success = True
                            logger.warning("Connected with insecure fallback (without SSL verification)")
                            self.state["error"] = "Connected with insecure fallback. Consider extracting TV certificate."
                        except Exception as fallback_error:
                            logger.error(f"Fallback connection also failed: {str(fallback_error)}")
                            self.state["error"] = f"SSL connection failed, fallback also failed: {str(fallback_error)}"
            except Exception as e:
                logger.warning(f"Initial connection attempt failed: {str(e)}")
                
                # The TV might be off, try to wake it using WOL if we have MAC address
                mac_address = self.state.get("mac_address")
                if mac_address:
                    logger.info(f"TV appears to be off. Attempting to wake it using WOL to MAC: {mac_address}")
                    wol_success = await self.send_wol_packet(mac_address)
                    
                    if wol_success:
                        logger.info("Wake-on-LAN packet sent successfully. Waiting for TV to boot...")
                        
                        # Wait for TV to boot up (typically takes 10-20 seconds)
                        boot_wait_time = self.tv_config.timeout or 15  # Default to 15 seconds if not specified
                        logger.info(f"Waiting {boot_wait_time} seconds for TV to boot...")
                        await asyncio.sleep(boot_wait_time)
                        
                        # Retry connection after TV has had time to boot
                        try:
                            # Recreate the client using the same logic as above
                            if secure_mode:
                                self.client = SecureWebOSClient(
                                    host=ip,
                                    secure=True,
                                    client_key=self.client_key,
                                    verify_ssl=False,
                                    cert_file=cert_file,  # Pass cert_file directly
                                    **ssl_options
                                )
                            else:
                                self.client = WebOSClient(ip, secure=False, client_key=self.client_key)
                                
                            logger.info("Retrying connection after WOL...")
                            await self.client.connect()
                            connection_success = True
                            logger.info("Connection successful after WOL!")
                        except Exception as retry_error:
                            logger.error(f"Connection failed even after WOL: {str(retry_error)}")
                            self.state["error"] = "Connection failed after wake-on-LAN. TV may not be responding."
                    else:
                        logger.error("Failed to send Wake-on-LAN packet")
                        self.state["error"] = "Failed to wake TV using Wake-on-LAN"
                else:
                    logger.warning("Cannot wake TV: No MAC address configured")
                    self.state["error"] = "Connection failed and no MAC address available for Wake-on-LAN"
            
            # If we still couldn't connect, return failure
            if not connection_success:
                if not self.state.get("error"):
                    self.state["error"] = "Failed to connect to TV"
                return False
            
            # Check if the client key is valid (the client should have a client_key after connection)
            if not self.client.client_key:
                logger.error("Invalid or rejected client key. Authentication failed.")
                self.state["error"] = "Invalid client key. Authentication failed."
                return False
            
            logger.info("Successfully authenticated with TV using provided client key")
            
            # Initialize controls
            self.media = MediaControl(self.client)
            self.system = SystemControl(self.client)
            self.app = ApplicationControl(self.client)
            self.tv_control = TvControl(self.client)
            self.input_control = InputControl(self.client)
            self.source_control = SourceControl(self.client)
            
            # Get initial TV state
            await self._update_tv_state()
            
            logger.info(f"Successfully connected to LG TV at {ip}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to LG TV: {str(e)}")
            self.state["error"] = f"Connection error: {str(e)}"
            return False
    
    async def _update_tv_state(self):
        """Update the TV state information."""
        try:
            # Get volume info
            try:
                if self.media:
                    # Call get_volume without parameters to avoid linter errors
                    volume_info = await self.media.get_volume()  # type: ignore
                    if volume_info:
                        self.state["volume"] = volume_info.get("volume", 0)
                        self.state["mute"] = volume_info.get("muted", False)
            except Exception as e:
                logger.debug(f"Could not get volume info: {str(e)}")
            
            # Get current app
            # Note: We don't get the current app as the asyncwebostv library doesn't provide a direct method
            # This would require additional implementation
            
            # Get input source 
            # Note: We don't get the source info as the asyncwebostv library doesn't provide a direct method
            # This would require additional implementation
            
            return True
        except Exception as e:
            logger.error(f"Error updating TV state: {str(e)}")
            return False
    
    async def power_on(self):
        """Power on the TV (if supported).
        
        This method tries two approaches to power on the TV:
        1. First, it attempts to use the WebOS API's system/turnOn method
        2. If that fails or there's no active connection, it falls back to Wake-on-LAN
           using the MAC address from the configuration
        """
        try:
            logger.info(f"Attempting to power on TV {self.get_name()}")
            success = False
            
            # First try using WebOS API if we have an active connection
            if self.system and self.client:
                try:
                    logger.info("Attempting to power on via WebOS API...")
                    await self.client.send_message('request', 'ssap://system/turnOn', {})
                    self.state["power"] = "on"
                    self.state["last_command"] = "power_on"
                    success = True
                    logger.info("Power on via WebOS API successful")
                except Exception as e:
                    logger.debug(f"WebOS API power on failed: {str(e)}")
            
            # If WebOS method failed or we don't have an active connection, try Wake-on-LAN
            if not success:
                mac_address = self.state.get("mac_address")
                if mac_address:
                    logger.info(f"Attempting to power on via Wake-on-LAN to MAC: {mac_address}")
                    # Use the send_wol_packet method from BaseDevice
                    wol_success = await self.send_wol_packet(mac_address)
                    if wol_success:
                        logger.info("Wake-on-LAN packet sent successfully")
                        # We can't be certain the TV will power on, but we've done our part
                        # Assume it worked for state tracking purposes
                        self.state["power"] = "on"
                        self.state["last_command"] = "power_on_wol"
                        success = True
                    else:
                        logger.error("Failed to send Wake-on-LAN packet")
                else:
                    logger.warning("Cannot use Wake-on-LAN: No MAC address configured for TV")
            
            # Update the state with the last command regardless of success
            if not success:
                self.state["last_command"] = "power_on_failed"
                
            return success
        except Exception as e:
            logger.error(f"Error powering on TV: {str(e)}")
            self.state["last_command"] = "power_on_error"
            return False
    
    async def power_off(self):
        """Power off the TV."""
        try:
            logger.info(f"Powering off TV {self.get_name()}")
            
            # Use system turnOff method
            if self.system and self.client:
                # Send turn off message directly
                await self.client.send_message('request', 'ssap://system/turnOff', {})
                self.state["power"] = "off"
                self.state["last_command"] = "power_off"
                return True
            
            return False
        except Exception as e:
            logger.error(f"Error powering off TV: {str(e)}")
            return False
    
    async def set_volume(self, volume):
        """Set the volume level."""
        try:
            volume = int(volume)
            logger.info(f"Setting TV {self.get_name()} volume to {volume}")
            
            if self.media and self.client:
                # Send volume message directly
                await self.client.send_message('request', 'ssap://audio/setVolume', {"volume": volume})
                self.state["volume"] = volume
                self.state["last_command"] = f"set_volume_{volume}"
                return True
            
            return False
        except Exception as e:
            logger.error(f"Error setting volume: {str(e)}")
            return False
    
    async def set_mute(self, mute=None):
        """Set mute state on TV."""
        try:
            # Convert "true"/"false" strings to bool if needed
            if isinstance(mute, str):
                mute = mute.lower() in ["true", "1", "yes"]
            
            logger.info(f"Setting mute to {mute} on TV {self.get_name()}")
            
            if not self.client:
                logger.error("TV client not initialized")
                return False
                
            # Send mute command directly
            await self.client.send_message('request', 'ssap://audio/setMute', {"mute": mute})
            
            # Update state
            self.state["mute"] = mute
            self.state["last_command"] = "mute_set"
            return True
            
        except Exception as e:
            logger.error(f"Error setting mute: {str(e)}")
            return False
    
    async def launch_app(self, app_name):
        """Launch an app by name or ID."""
        try:
            logger.info(f"Launching app {app_name} on TV {self.get_name()}")
            
            if not self.client:
                logger.error("TV client not initialized")
                return False
            
            # First retrieve list of available apps directly
            apps_response = await self.client.send_message('request', 'ssap://com.webos.applicationManager/listApps', {}, get_queue=True)  # type: ignore
            if not apps_response or not apps_response.get("payload") or not apps_response.get("payload").get("apps"):  # type: ignore
                logger.error("Could not retrieve list of apps")
                return False
            
            apps = apps_response.get("payload").get("apps", [])  # type: ignore
            
            # Try to find the app by name or ID
            target_app = None
            for app in apps:
                if app_name.lower() in app.get("title", "").lower() or app_name == app.get("id"):
                    target_app = app
                    break
            
            if not target_app:
                logger.error(f"App {app_name} not found on TV")
                return False
            
            # Launch the app directly
            await self.client.send_message('request', 'ssap://system.launcher/launch', {"id": target_app["id"]})
            self.state["current_app"] = target_app["id"]
            self.state["last_command"] = f"launch_app_{app_name}"
            return True
            
        except Exception as e:
            logger.error(f"Error launching app: {str(e)}")
            return False
    
    async def send_action(self, action):
        """Send a control action to the TV."""
        try:
            action = action.lower()
            logger.info(f"Sending action {action} to TV {self.get_name()}")
            
            if not self.client:
                logger.error("TV client not initialized")
                return False
                
            result = False
            
            # Mouse control actions
            if action.startswith("mouse_"):
                # Parse mouse command format: mouse_move_100_200 or mouse_click_100_200 or mouse_move_rel_10_20
                parts = action.split("_")
                if len(parts) >= 4:
                    mouse_action = parts[1]  # move, click, or move_rel
                    try:
                        # Extract coordinates
                        if mouse_action == "move" and len(parts) >= 4:
                            x = int(parts[2])
                            y = int(parts[3])
                            drag = False
                            if len(parts) >= 5 and parts[4] == "drag":
                                drag = True
                            result = await self.handle_move_cursor({"x": x, "y": y, "drag": drag})
                        elif mouse_action == "click" and len(parts) >= 4:
                            x = int(parts[2])
                            y = int(parts[3])
                            result = await self.handle_click({"x": x, "y": y})
                        elif mouse_action == "rel" and len(parts) >= 4:
                            dx = int(parts[2])
                            dy = int(parts[3])
                            drag = False
                            if len(parts) >= 5 and parts[4] == "drag":
                                drag = True
                            result = await self.handle_move_cursor_relative({"dx": dx, "dy": dy, "drag": drag})
                        else:
                            logger.error(f"Invalid mouse action format: {action}")
                    except ValueError:
                        logger.error(f"Invalid coordinate values in mouse action: {action}")
                else:
                    logger.error(f"Invalid mouse action format: {action}")
            # Media controls
            elif action == "play":
                await self.client.send_message('request', 'ssap://media.controls/play', {})
                result = True
            elif action == "pause":
                await self.client.send_message('request', 'ssap://media.controls/pause', {})
                result = True
            elif action == "stop":
                await self.client.send_message('request', 'ssap://media.controls/stop', {})
                result = True
            elif action == "rewind":
                await self.client.send_message('request', 'ssap://media.controls/rewind', {})
                result = True
            elif action == "fast_forward":
                await self.client.send_message('request', 'ssap://media.controls/fastForward', {})
                result = True
            elif action == "volume_up":
                await self.client.send_message('request', 'ssap://audio/volumeUp', {})
                result = True
            elif action == "volume_down":
                await self.client.send_message('request', 'ssap://audio/volumeDown', {})
                result = True
            elif action == "mute":
                result = await self.set_mute(True)
            elif action == "unmute":
                result = await self.set_mute(False)
                
            # TV navigation controls
            elif action == "channel_up":
                await self.client.send_message('request', 'ssap://tv/channelUp', {})
                result = True
            elif action == "channel_down":
                await self.client.send_message('request', 'ssap://tv/channelDown', {})
                result = True
            elif action in ["up", "down", "left", "right", "ok", "back", "home", 
                            "red", "green", "yellow", "blue", "menu", "exit", "guide"]:
                # These all use the networkinput service with button parameter
                await self.client.send_message('request', 
                                           'ssap://com.webos.service.networkinput/getPointerInputSocket', 
                                           {"button": action.upper()})
                result = True
            elif action in ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]:
                # Number buttons also use networkinput
                await self.client.send_message('request', 
                                           'ssap://com.webos.service.networkinput/getPointerInputSocket', 
                                           {"button": action})
                result = True
            else:
                logger.error(f"Unknown action: {action}")
                return False
            
            self.update_state({
                "last_command": LastCommand(
                    action=f"action_{action}",
                    source="api",
                    timestamp=datetime.now(),
                    position="button"
                ).dict()
            })
            return result
            
        except Exception as e:
            logger.error(f"Error sending action: {str(e)}")
            return False
    
    async def set_input_source(self, input_source):
        """Set the TV input source."""
        try:
            logger.info(f"Setting input source to {input_source} on TV {self.get_name()}")
            
            if not self.client:
                logger.error("TV client not initialized")
                return False
            
            # First retrieve list of available sources using direct message
            try:
                sources_response = await self.client.send_message('request', 'ssap://tv/getExternalInputList', {}, get_queue=True)  # type: ignore
                if not sources_response or not sources_response.get("payload"):  # type: ignore
                    logger.error("Could not retrieve list of sources")
                    return False
                
                sources = sources_response.get("payload", {}).get("devices", [])  # type: ignore
                if not sources:
                    logger.error("No input sources available")
                    return False
                
                # Try to find the source by name or ID
                target_source = None
                for source in sources:
                    if input_source.lower() in source.get("label", "").lower() or input_source == source.get("id"):
                        target_source = source
                        break
                
                if not target_source:
                    logger.error(f"Input source {input_source} not found on TV")
                    return False
                
                # Set the input source directly
                await self.client.send_message('request', 'ssap://tv/switchInput', {"inputId": target_source["id"]})
                self.state["input_source"] = target_source["id"]
                self.update_state({
                    "last_command": LastCommand(
                        action=f"set_input_{input_source}",
                        source="api",
                        timestamp=datetime.now(),
                        position="input"
                    ).dict()
                })
                return True
            except Exception as e:
                logger.error(f"Error sending input source request: {str(e)}")
                return False
        except Exception as e:
            logger.error(f"Error setting input source: {str(e)}")
            return False
    
    async def handle_message(self, topic: str, payload: str):
        """Handle incoming MQTT messages for this device."""
        try:
            logger.debug(f"LG TV {self.get_name()} handling message on topic {topic}: {payload}")
            
            # Find matching command configuration for this topic
            matching_command = None
            matching_command_name = None
            
            for cmd_name, cmd_config in self.get_available_commands().items():
                if cmd_config.get("topic") == topic:
                    matching_command = cmd_config
                    matching_command_name = cmd_name
                    break
            
            if not matching_command:
                logger.warning(f"No command configuration found for topic: {topic}")
                return
            
            # Check if this command has an 'appname' parameter
            appname = matching_command.get("appname")
            
            if appname:
                # Launch the specified app directly
                logger.info(f"Launching app {appname} based on MQTT message for {self.get_name()}")
                
                # Launch the app
                result = await self.launch_app(appname)
                
                # Update state with last command information
                self.update_state({
                    "last_command": LastCommand(
                        action=f"launch_app_{appname}",
                        source="mqtt",
                        timestamp=datetime.now(),
                        position="app"
                    ).dict()
                })
                
                return result
            else:
                # No appname parameter, let the base class handle it
                await super().handle_message(topic, payload)
                
        except Exception as e:
            logger.error(f"Error handling MQTT message in LG TV {self.get_name()}: {str(e)}")
    
    def get_current_state(self) -> LgTvState:
        """Get the current device state as a LgTvState model."""
        # Create a LgTvState model with current values
        return LgTvState(
            device_id=self.device_id,
            device_name=self.device_name,
            **self.state
        )
    
    # Get available apps on the TV
    async def get_available_apps(self):
        """Get a list of available apps."""
        if not self.client or not self.app:
            logger.error("Cannot get apps: Not connected to TV")
            return []
            
        try:
            # This call returns a list of applications
            # type-ignore comment is needed to suppress mypy errors with return type
            result = await self.app.list_apps()  # type: ignore
            if not result:
                return []
                
            # Filter out system apps if desired
            # apps = [app for app in result if not app.get("systemApp", False)]
            
            # Return all apps for now
            return result
        except Exception as e:
            logger.error(f"Failed to get apps: {str(e)}")
            return []
    
    async def execute_action(self, action: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """Execute a device-specific action."""
        # Initialize result
        result: Dict[str, Any] = {"success": False, "message": f"Unknown action: {action}"}
        params = params or {}
        
        # Look up handler for the requested action
        handler = self._get_action_handler(action)
        
        # Execute handler if found
        if handler:
            try:
                result = await handler(params)
            except Exception as e:
                logger.error(f"Error executing action '{action}': {str(e)}")
                result = {"success": False, "message": f"Error executing action: {str(e)}"}
        
        return result

    # Handler methods for cursor control
    async def handle_move_cursor(self, action_config: Dict[str, Any]) -> bool:
        """Handle move_cursor action.
        
        Args:
            action_config: Dictionary with parameters including x, y, and optional drag
            
        Returns:
            True if successful, False otherwise
        """
        try:
            x = action_config.get("x")
            y = action_config.get("y")
            drag = action_config.get("drag", False)
            
            if x is None or y is None:
                logger.error("Missing x or y parameters")
                return False
                
            try:
                x = int(x)
                y = int(y)
            except ValueError:
                logger.error("x and y must be integers")
                return False
                
            logger.info(f"Moving cursor to position x={x}, y={y}, drag={drag} on TV {self.get_name()}")
            
            if not self.client or not self.input_control:
                logger.error("TV client or input control not initialized")
                return False
                
            # Ensure we have a WebSocket connection to the input service
            try:
                if not self.input_control.ws_client:
                    await self.input_control.connect_input()
                    
                if not self.input_control.ws_client:
                    logger.error("Failed to establish WebSocket connection for pointer input")
                    return False
                    
                # Send the move command directly
                payload = {"x": x, "y": y, "drag": drag}
                await self.input_control.ws_client.send(json.dumps(payload))
                
                # Update state with last command information
                self.update_state({
                    "last_command": LastCommand(
                        action=f"move_cursor",
                        source="api",
                        timestamp=datetime.now(),
                        params={"x": x, "y": y, "drag": drag},
                        position="cursor"
                    ).dict()
                })
                
                return True
            except Exception as e:
                logger.error(f"WebSocket error in move_cursor: {str(e)}")
                return False
        except Exception as e:
            logger.error(f"Error moving cursor: {str(e)}")
            return False
            
    async def handle_move_cursor_relative(self, action_config: Dict[str, Any]) -> bool:
        """Handle move_cursor_relative action.
        
        Args:
            action_config: Dictionary with parameters including dx, dy, and optional drag
            
        Returns:
            True if successful, False otherwise
        """
        try:
            dx = action_config.get("dx")
            dy = action_config.get("dy")
            drag = action_config.get("drag", False)
            
            if dx is None or dy is None:
                logger.error("Missing dx or dy parameters")
                return False
                
            try:
                dx = int(dx)
                dy = int(dy)
            except ValueError:
                logger.error("dx and dy must be integers")
                return False
                
            logger.info(f"Moving cursor by dx={dx}, dy={dy}, drag={drag} on TV {self.get_name()}")
            
            if not self.client or not self.input_control:
                logger.error("TV client or input control not initialized")
                return False
                
            # Ensure we have a WebSocket connection to the input service
            try:
                if not self.input_control.ws_client:
                    await self.input_control.connect_input()
                    
                if not self.input_control.ws_client:
                    logger.error("Failed to establish WebSocket connection for pointer input")
                    return False
                    
                # Send the move_mouse command directly
                payload = {"dx": dx, "dy": dy, "drag": drag, "move": True}
                await self.input_control.ws_client.send(json.dumps(payload))
                
                # Update state with last command information
                self.update_state({
                    "last_command": LastCommand(
                        action=f"move_cursor_relative",
                        source="api",
                        timestamp=datetime.now(),
                        params={"dx": dx, "dy": dy, "drag": drag},
                        position="cursor"
                    ).dict()
                })
                
                return True
            except Exception as e:
                logger.error(f"WebSocket error in move_cursor_relative: {str(e)}")
                return False
        except Exception as e:
            logger.error(f"Error moving cursor relatively: {str(e)}")
            return False
            
    async def handle_click(self, action_config: Dict[str, Any]) -> bool:
        """Handle click action.
        
        Args:
            action_config: Dictionary with parameters including x and y
            
        Returns:
            True if successful, False otherwise
        """
        try:
            x = action_config.get("x")
            y = action_config.get("y")
            
            if x is None or y is None:
                logger.error("Missing x or y parameters")
                return False
                
            try:
                x = int(x)
                y = int(y)
            except ValueError:
                logger.error("x and y must be integers")
                return False
                
            logger.info(f"Clicking at position x={x}, y={y} on TV {self.get_name()}")
            
            if not self.client or not self.input_control:
                logger.error("TV client or input control not initialized")
                return False
                
            # Ensure we have a WebSocket connection to the input service
            try:
                if not self.input_control.ws_client:
                    await self.input_control.connect_input()
                    
                if not self.input_control.ws_client:
                    logger.error("Failed to establish WebSocket connection for pointer input")
                    return False
                    
                # Send the click command directly
                payload = {"x": x, "y": y, "click": True}
                await self.input_control.ws_client.send(json.dumps(payload))
                
                # Update state with last command information
                self.update_state({
                    "last_command": LastCommand(
                        action=f"click",
                        source="api",
                        timestamp=datetime.now(),
                        params={"x": x, "y": y},
                        position="cursor"
                    ).dict()
                })
                
                return True
            except Exception as e:
                logger.error(f"WebSocket error in click: {str(e)}")
                return False
        except Exception as e:
            logger.error(f"Error clicking: {str(e)}")
            return False

    # Action handlers for base class handle_message to use
    
    async def handle_power(self, action_config: Dict[str, Any]):
        """Handle power action."""
        await self.send_action("power")
        return True
        
    async def handle_home(self, action_config: Dict[str, Any]):
        """Handle home button action."""
        await self.send_action("home")
        return True
        
    async def handle_back(self, action_config: Dict[str, Any]):
        """Handle back button action."""
        await self.send_action("back")
        return True
        
    async def handle_up(self, action_config: Dict[str, Any]):
        """Handle up button action."""
        await self.send_action("up")
        return True
        
    async def handle_down(self, action_config: Dict[str, Any]):
        """Handle down button action."""
        await self.send_action("down")
        return True
        
    async def handle_left(self, action_config: Dict[str, Any]):
        """Handle left button action."""
        await self.send_action("left")
        return True
        
    async def handle_right(self, action_config: Dict[str, Any]):
        """Handle right button action."""
        await self.send_action("right")
        return True
        
    async def handle_enter(self, action_config: Dict[str, Any]):
        """Handle enter button action."""
        await self.send_action("ok")
        return True
        
    async def handle_volume_up(self, action_config: Dict[str, Any]):
        """Handle volume up action."""
        await self.send_action("volume_up")
        return True
        
    async def handle_volume_down(self, action_config: Dict[str, Any]):
        """Handle volume down action."""
        await self.send_action("volume_down")
        return True
        
    async def handle_mute(self, action_config: Dict[str, Any]):
        """Handle mute action."""
        await self.send_action("mute")
        return True
        
    # Generic handler for any action that can be directly passed to send_action
    async def handle_action(self, action_config: Dict[str, Any]):
        """Generic handler for any action."""
        action = action_config.get("action")
        if action:
            return await self.send_action(action)
        return False

    async def wake_on_lan(self) -> bool:
        """Send a Wake-on-LAN packet to the TV using the configured MAC address.
        
        This method can be used independently of the power_on method when you
        specifically want to use WOL without trying other power-on methods.
        
        Returns:
            bool: True if the WOL packet was sent successfully, False otherwise
        """
        try:
            mac_address = self.state.get("mac_address")
            if not mac_address:
                logger.error("Cannot use Wake-on-LAN: No MAC address configured for TV")
                self.state["last_command"] = "wol_failed_no_mac"
                return False
                
            logger.info(f"Sending Wake-on-LAN packet to TV {self.get_name()} (MAC: {mac_address})")
            
            # Use the send_wol_packet method from BaseDevice
            wol_success = await self.send_wol_packet(mac_address)
            
            if wol_success:
                logger.info("Wake-on-LAN packet sent successfully")
                self.state["last_command"] = "wake_on_lan"
                # We can't know for sure if the TV will turn on,
                # but update the expected state for consistency
                self.state["power"] = "on"
                return True
            else:
                logger.error("Failed to send Wake-on-LAN packet")
                self.state["last_command"] = "wol_failed"
                return False
                
        except Exception as e:
            logger.error(f"Error sending Wake-on-LAN packet: {str(e)}")
            self.state["last_command"] = "wol_error"
            return False

    async def handle_wake_on_lan(self, action_config: Dict[str, Any]):
        """Handle Wake-on-LAN action."""
        return await self.wake_on_lan()

    async def extract_certificate(self, output_file=None) -> Tuple[bool, str]:
        """
        Extract certificate from the TV and save it to a file.
        
        Args:
            output_file: Optional path where to save the certificate. 
                        If not provided, will use hostname_cert.pem
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Get TV IP address
            ip = self.state.get("ip_address")
            if not ip:
                return False, "No IP address configured for TV"
            
            # Set default output file if not provided
            if not output_file:
                output_file = f"{ip}_cert.pem"
            
            # Import the tools we need for certificate extraction
            import socket
            import ssl
            import OpenSSL.crypto as crypto
            
            # Create SSL context without verification
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            
            # Connect to the TV and get the certificate
            logger.info(f"Connecting to {ip}:3001 to extract certificate...")
            with socket.create_connection((ip, 3001)) as sock:
                with context.wrap_socket(sock, server_hostname=ip) as ssock:
                    cert_bin = ssock.getpeercert(binary_form=True)
                    if not cert_bin:
                        return False, "Failed to get certificate from TV"
                    
                    # Convert binary certificate to PEM format
                    x509 = crypto.load_certificate(crypto.FILETYPE_ASN1, cert_bin)
                    pem_data = crypto.dump_certificate(crypto.FILETYPE_PEM, x509)
                    
                    # Save to file
                    with open(output_file, 'wb') as f:
                        f.write(pem_data)
                    
                    logger.info(f"Certificate extracted and saved to {output_file}")
                    
                    # Update configuration to use this certificate
                    if self.tv_config:
                        self.tv_config.cert_file = os.path.abspath(output_file)
                        logger.info("Updated TV configuration to use the extracted certificate")
                    
                    return True, f"Certificate saved to {output_file}"
        
        except Exception as e:
            error_msg = f"Failed to extract certificate: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    async def verify_certificate(self) -> Tuple[bool, str]:
        """
        Verify if the current certificate matches the one on the TV.
        
        Returns:
            Tuple of (valid: bool, message: str)
        """
        try:
            # Check if we have a certificate file configured
            if not self.tv_config or not self.tv_config.cert_file:
                return False, "No certificate file configured"
            
            cert_file = self.tv_config.cert_file
            if not os.path.exists(cert_file):
                return False, f"Certificate file {cert_file} does not exist"
            
            # Get TV IP address
            ip = self.state.get("ip_address")
            if not ip:
                return False, "No IP address configured for TV"
            
            # Import the tools we need for certificate verification
            import socket
            import ssl
            import hashlib
            import OpenSSL.crypto as crypto
            
            # Load the saved certificate
            with open(cert_file, 'rb') as f:
                saved_cert_data = f.read()
                saved_cert = crypto.load_certificate(crypto.FILETYPE_PEM, saved_cert_data)
                saved_cert_bin = crypto.dump_certificate(crypto.FILETYPE_ASN1, saved_cert)
                saved_fingerprint = hashlib.sha256(saved_cert_bin).hexdigest()
            
            # Get the current certificate from the TV
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            
            with socket.create_connection((ip, 3001)) as sock:
                with context.wrap_socket(sock, server_hostname=ip) as ssock:
                    current_cert_bin = ssock.getpeercert(binary_form=True)
                    if not current_cert_bin:
                        return False, "Failed to get current certificate from TV"
                    
                    current_fingerprint = hashlib.sha256(current_cert_bin).hexdigest()
            
            # Compare fingerprints
            if saved_fingerprint == current_fingerprint:
                logger.info("Certificate verification successful: Certificate matches the one from the TV")
                return True, "Certificate is valid and matches the TV"
            else:
                logger.warning("Certificate verification failed: Certificate does not match the one from the TV")
                return False, "Certificate does not match the one from the TV. Consider refreshing it."
                
        except Exception as e:
            error_msg = f"Failed to verify certificate: {str(e)}"
            logger.error(error_msg)
            return False, error_msg 