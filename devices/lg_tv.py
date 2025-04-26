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
            "device_id": self.device_id,
            "device_name": self.device_name,
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
        
        # Register action handlers
        self._register_lg_tv_action_handlers()
        
        # DEBUG: Look for handler methods in the class
        handler_methods = [m for m in dir(self) if m.startswith("handle_") and callable(getattr(self, m))]
        logger.debug(f"Found handler methods in {self.device_name}: {handler_methods}")
        logger.debug(f"Action handlers dictionary: {self._action_handlers}")
        
        # DEBUG: Check specific handlers
        has_power_on = hasattr(self, "handle_power_on") and callable(getattr(self, "handle_power_on"))
        logger.debug(f"Has handle_power_on method: {has_power_on}")
    
    def _register_lg_tv_action_handlers(self):
        """Register all action handlers for the LG TV."""
        # Register handlers for media control actions
        self._action_handlers.update({
            'power_on': self.handle_power_on,
            'power_off': self.handle_power_off,
            'home': self.handle_home,
            'back': self.handle_back,
            'up': self.handle_up,
            'down': self.handle_down,
            'left': self.handle_left,
            'right': self.handle_right,
            'enter': self.handle_enter,
            'exit': self.handle_exit,
            'menu': self.handle_menu,
            'settings': self.handle_settings,
            'volume_up': self.handle_volume_up,
            'volume_down': self.handle_volume_down,
            'set_volume': self.handle_set_volume,
            'mute': self.handle_mute,
            'play': self.handle_play,
            'pause': self.handle_pause,
            'stop': self.handle_stop,
            'rewind_forward': self.handle_rewind_forward,
            'rewind_backward': self.handle_rewind_backward,
            
            # Pointer control
            'move_cursor': self.handle_move_cursor,
            'move_cursor_relative': self.handle_move_cursor_relative,
            'click': self.handle_click,
            
            # Input sources
            'hdmi1': self.handle_hdmi1,
            'hdmi2': self.handle_hdmi2,
            'hdmi3': self.handle_hdmi3,
            
            # Apps
            'kinopoisk': self.handle_kinopoisk,
            'ivi': self.handle_ivi,
            
            # Network
            'wake_on_lan': self.handle_wake_on_lan,
        })
    
    def _create_ssl_context(self, cert_file: Optional[str] = None, verify_ssl: bool = False) -> Optional[ssl.SSLContext]:
        """Create an SSL context for WebOS TV connections.
        
        Args:
            cert_file: Path to certificate file, if available
            verify_ssl: Whether to verify SSL certificates
            
        Returns:
            SSL context object or None if no cert_file is provided
        """
        if not cert_file:
            return None
            
        try:
            # Create SSL context with appropriate verification settings
            logger.info(f"Creating SSL context with certificate file {cert_file}")
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False  # Always disable hostname checking for TVs
            
            # Set verification mode based on verify_ssl
            if not verify_ssl:
                ssl_context.verify_mode = ssl.CERT_NONE
                logger.info("SSL certificate verification disabled")
            
            # Try to load the certificate file
            try:
                ssl_context.load_verify_locations(cert_file)
                logger.info(f"Loaded certificate from {cert_file}")
            except Exception as ssl_err:
                logger.error(f"Failed to load certificate file: {str(ssl_err)}")
                # If verification is required but certificate loading failed, we should fail
                if verify_ssl:
                    raise ssl_err
                # Otherwise continue without certificate (with CERT_NONE)
                logger.warning("Continuing without certificate verification")
            
            return ssl_context
            
        except Exception as e:
            logger.error(f"Error creating SSL context: {str(e)}")
            if verify_ssl:
                raise  # Re-raise if verification is required
            return None
            
    def _create_webos_client(self, secure: bool = False) -> Optional[Union[WebOSClient, SecureWebOSClient]]:
        """Create a WebOS client based on configuration.
        
        Args:
            secure: Whether to create a secure client
            
        Returns:
            WebOS client instance or None if creation fails
        """
        try:
            # Check if we have configuration and IP address
            if not self.tv_config:
                logger.error("TV configuration not initialized")
                return None
                
            ip = self.state.get("ip_address")
            if not ip:
                logger.error("No IP address configured for TV")
                return None
                
            # Use configuration from TV config
            secure_mode = secure if secure else self.tv_config.secure
            
            # Get certificate file path if provided
            cert_file = self.tv_config.cert_file
            
            # Get any additional SSL options
            ssl_options = {}
            if hasattr(self.tv_config, 'ssl_options') and self.tv_config.ssl_options:
                ssl_options = self.tv_config.ssl_options
                
            # Create the appropriate client type
            if secure_mode:
                logger.info(f"Creating secure WebOS client for {ip}")
                
                # Always set verify_ssl to False by default for WebOS TVs, as they use self-signed certificates
                # Only override if explicitly set in ssl_options
                verify_ssl = ssl_options.get('verify_ssl', False)
                
                # Create SSL context if needed
                ssl_context = self._create_ssl_context(cert_file, verify_ssl)
                
                # Ensure port is set to 3001 for secure WebSocket connections
                port = ssl_options.get('port', 3001)
                
                # Create the secure client
                return SecureWebOSClient(
                    host=ip,
                    port=port,
                    secure=True,
                    client_key=self.client_key,
                    ssl_context=ssl_context,
                    verify_ssl=verify_ssl,
                    cert_file=cert_file if not ssl_context else None
                )
            else:
                logger.info(f"Creating standard WebOS client for {ip}")
                return WebOSClient(ip, secure=False, client_key=self.client_key)
                
        except Exception as e:
            logger.error(f"Error creating WebOS client: {str(e)}")
            self.state["error"] = f"Client creation error: {str(e)}"
            return None
            
    async def _initialize_control_interfaces(self) -> bool:
        """Initialize control interfaces after successful connection.
        
        Returns:
            True if initialization was successful, False otherwise
        """
        try:
            if not self.client:
                logger.error("Cannot initialize controls: No client available")
                return False
                
            # Initialize control interfaces
            self.system = SystemControl(self.client)
            self.media = MediaControl(self.client)
            self.app = ApplicationControl(self.client)
            self.tv_control = TvControl(self.client)
            self.input_control = InputControl(self.client)
            self.source_control = SourceControl(self.client)
            
            return True
        except Exception as e:
            logger.error(f"Error initializing control interfaces: {str(e)}")
            return False
    
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
                logger.warning(f"No client key provided for TV {self.get_name()}. TV will require manual pairing on first connection.")
            
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
        
        Returns:
            True if connection was successful, False otherwise
        """
        try:
            connection_result = await self._connect_to_tv()
            
            if connection_result:
                logger.info(f"Successfully connected to TV {self.get_name()}")
                self.state["connected"] = True
                self.state["error"] = None
                
                # Initialize control interfaces after successful connection
                await self._initialize_control_interfaces()
                
                # Update TV state after successful connection
                await self._update_tv_state()
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
                await self.client.close()
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
            # Create a WebOS client
            self.client = self._create_webos_client()
            if not self.client:
                return False
                
            # First connection attempt
            try:
                ip = self.state.get("ip_address")
                logger.info(f"Attempting to connect to TV at {ip}...")
                await self.client.connect()
                
                # Once connected, register with the TV
                logger.info("Connected to TV. Registering client...")
                
                # Create a key store for the client key
                key_store = {}
                if self.client_key:
                    key_store["client_key"] = self.client_key
                
                # Register with the TV
                if await self._register_client(key_store):
                    return True
                else:
                    logger.error("Failed to register with TV")
                    return False
                
            except ssl.SSLError as ssl_error:
                # Handle SSL errors specially
                return await self._handle_ssl_error(ssl_error)
                
            except Exception as conn_error:
                # Handle connection errors
                return await self._handle_connection_error(conn_error)
                
        except Exception as e:
            logger.error(f"Error in _connect_to_tv: {str(e)}")
            self.state["error"] = str(e)
            return False
            
    async def _handle_ssl_error(self, ssl_error: ssl.SSLError) -> bool:
        """Handle SSL errors during connection.
        
        Args:
            ssl_error: The SSL error that occurred
            
        Returns:
            True if fallback connection succeeded, False otherwise
        """
        logger.error(f"SSL error during connection: {str(ssl_error)}")
        self.state["error"] = f"SSL connection error: {str(ssl_error)}"
        
        # Check if it's a certificate verification error and we're in secure mode
        if "CERTIFICATE_VERIFY_FAILED" in str(ssl_error) and self.tv_config and self.tv_config.secure:
            logger.warning("Certificate verification failed. Consider extracting the TV certificate using extract_lg_tv_cert.py")
            
            # Check if fallback is allowed in configuration
            has_fallback = False
            if hasattr(self.tv_config, 'ssl_options') and self.tv_config.ssl_options:
                has_fallback = self.tv_config.ssl_options.get("allow_insecure_fallback", False)
                
            if has_fallback:
                return await self._attempt_insecure_fallback()
                
        return False
        
    async def _attempt_insecure_fallback(self) -> bool:
        """Attempt a fallback connection without SSL.
        
        Returns:
            True if fallback succeeded, False otherwise
        """
        logger.info("Attempting fallback connection without SSL...")
        try:
            # Create a new non-secure client
            self.client = self._create_webos_client(secure=False)
            if not self.client:
                return False
                
            # Connect with the non-secure client
            await self.client.connect()
            
            # Register with the TV
            key_store = {}
            if self.client_key:
                key_store["client_key"] = self.client_key
                
            if await self._register_client(key_store):
                logger.warning("Connected with insecure fallback (without SSL)")
                self.state["error"] = "Connected with insecure fallback. Consider extracting TV certificate."
                return True
            else:
                logger.error("Fallback registration failed")
                return False
                
        except Exception as fallback_error:
            logger.error(f"Fallback connection failed: {str(fallback_error)}")
            self.state["error"] = f"SSL connection failed, fallback also failed: {str(fallback_error)}"
            return False
            
    async def _handle_connection_error(self, conn_error: Exception) -> bool:
        """Handle general connection errors, potentially using WoL.
        
        Args:
            conn_error: The connection error that occurred
            
        Returns:
            True if connection was established or recovered, False otherwise
        """
        logger.error(f"Connection error: {str(conn_error)}")
        self.state["error"] = f"Connection error: {str(conn_error)}"
        
        # If we have a MAC address and the error suggests the TV is off, try Wake-on-LAN
        mac_address = self.state.get("mac_address")
        if mac_address and "no response" in str(conn_error).lower():
            logger.info(f"TV may be off. Attempting Wake-on-LAN to {mac_address}")
            if await self.wake_on_lan():
                logger.info("WoL packet sent. Waiting for TV to boot...")
                # Wait for the TV to boot
                boot_wait_time = getattr(self.tv_config, "timeout", 15) if self.tv_config else 15
                await asyncio.sleep(boot_wait_time)
                
                # Try to connect again after WoL
                try:
                    # Create a fresh client
                    self.client = self._create_webos_client()
                    if not self.client:
                        return False
                        
                    await self.client.connect()
                    
                    # Register after WoL connection
                    key_store = {}
                    if self.client_key:
                        key_store["client_key"] = self.client_key
                        
                    if await self._register_client(key_store):
                        logger.info("Successfully connected after Wake-on-LAN")
                        return True
                    else:
                        logger.error("Failed to register after Wake-on-LAN")
                        return False
                        
                except Exception as wol_conn_error:
                    logger.error(f"Failed to connect after Wake-on-LAN: {str(wol_conn_error)}")
        
        return False
    
    async def _update_tv_state(self):
        """Update the TV state information.
        
        Retrieves current volume, mute state, current app, and input source
        from the TV.
        
        Returns:
            True if at least some state information was updated, False otherwise
        """
        if not self.client or not self.state.get("connected", False):
            logger.debug("Cannot update TV state: Not connected")
            return False
            
        update_success = False
        
        # Get volume info
        await self._update_volume_state()
        
        # Get current app
        await self._update_current_app()
        
        # Get input source
        await self._update_input_source()
        
        return True
        
    async def _update_volume_state(self):
        """Update volume and mute state information."""
        from typing import cast, Any
        
        if not self.media:
            return
            
        try:
            # Cast to Any to avoid type checking issues
            media_control = cast(Any, self.media)
            volume_info = await media_control.get_volume()
            if volume_info:
                self.state["volume"] = volume_info.get("volume", 0)
                self.state["mute"] = volume_info.get("muted", False)
        except Exception as e:
            logger.debug(f"Could not get volume info: {str(e)}")
            
    async def _update_current_app(self):
        """Update current app information."""
        if not self.client or not self.app:
            return
            
        try:
            # Use the client's request method directly for foreground app info
            queue = await self.client.send_message('request', 'ssap://com.webos.applicationManager/getForegroundAppInfo', {}, get_queue=True)
            app_info = await queue.get()
            if app_info and "payload" in app_info:
                self.state["current_app"] = app_info["payload"].get("appId")
        except Exception as e:
            logger.debug(f"Could not get current app info: {str(e)}")
            
    async def _update_input_source(self):
        """Update input source information."""
        from typing import cast, Any
        
        if not self.input_control:
            return
            
        try:
            # Cast to Any to avoid type checking issues
            input_control = cast(Any, self.input_control)
            input_info = await input_control.get_input()
            if input_info and "inputId" in input_info:
                self.state["input_source"] = input_info.get("inputId")
        except Exception as e:
            logger.debug(f"Could not get input source info: {str(e)}")
    
    async def _execute_with_monitoring(self, control, method_name: str, *args, **kwargs) -> Dict[str, Any]:
        """Execute a control method with monitoring and handle common result patterns.
        
        Args:
            control: The control interface (e.g., SystemControl, MediaControl)
            method_name: The name of the method to call
            *args, **kwargs: Arguments to pass to the method
            
        Returns:
            Dict containing the result from the control method
        """
        try:
            from typing import cast, Any
            
            # Ensure we have a control object
            if not control:
                logger.error(f"Cannot execute {method_name}: Control not initialized")
                return {"success": False, "error": "Control not initialized"}
            
            # Cast to Any to avoid type checking issues with the asyncwebostv library
            cast_control = cast(Any, control)
            
            # Check if the method exists
            method = getattr(cast_control, method_name, None)
            if not method:
                logger.error(f"Method {method_name} not found on control {type(control).__name__}")
                return {"success": False, "error": f"Method {method_name} not found"}
            
            # Execute the method
            result = await method(*args, **kwargs)
            
            # Process result
            success = False
            if isinstance(result, dict):
                # Check common success patterns in WebOS API responses
                if result.get("returnValue", False):
                    success = True
                elif result.get("status") in ["succeeded", "changed", "success", "launched", "powered_on", "powered_off"]:
                    success = True
            
            if success:
                return {"success": True, "result": result}
            else:
                logger.warning(f"{method_name} failed: {result}")
                return {"success": False, "result": result, "error": "Command did not return success status"}
            
        except Exception as e:
            logger.error(f"Error executing {method_name}: {str(e)}")
            return {"success": False, "error": str(e)}
            
    async def power_on(self):
        """Power on the TV (if supported).
        
        This method tries two approaches to power on the TV:
        1. First, it attempts to use the WebOS API's system/turnOn method with monitoring
        2. If that fails or there's no active connection, it falls back to Wake-on-LAN
           using the MAC address from the configuration
           
        Returns:
            True if power on was successful, False otherwise
        """
        try:
            logger.info(f"Attempting to power on TV {self.get_name()}")
            success = False
            
            # First try using WebOS API if we have an active connection
            if self.system and self.client and self.state.get("connected", False):
                try:
                    logger.info("Attempting to power on via WebOS API with monitoring...")
                    result = await self._execute_with_monitoring(
                        self.system, 
                        "power_on_with_monitoring", 
                        timeout=20.0
                    )
                    
                    if result.get("success", False):
                        self.state["power"] = "on"
                        self.state["last_command"] = LastCommand(
                            action="power_on",
                            source="api",
                            timestamp=datetime.now(),
                            params={"method": "webos_api"}
                        ).dict()
                        success = True
                        logger.info("Power on via WebOS API successful")
                except Exception as e:
                    logger.debug(f"WebOS API power on failed: {str(e)}")
            
            # If WebOS method failed or we don't have an active connection, try Wake-on-LAN
            if not success:
                success = await self._power_on_with_wol()
            
            # If power on was successful, ensure we connect to re-initialize everything
            if success:
                # Wait a moment for the TV to fully boot before connecting
                boot_wait_time = getattr(self.tv_config, "timeout", 5) if self.tv_config else 5
                await asyncio.sleep(boot_wait_time)
                
                # Connect to re-initialize all control interfaces
                await self.connect()
            else:
                self.state["last_command"] = LastCommand(
                    action="power_on",
                    source="api",
                    timestamp=datetime.now(),
                    params={"status": "failed"}
                ).dict()
                
            return success
        except Exception as e:
            logger.error(f"Error powering on TV: {str(e)}")
            self.state["last_command"] = LastCommand(
                action="power_on",
                source="api",
                timestamp=datetime.now(),
                params={"error": str(e)}
            ).dict()
            return False
            
    async def _power_on_with_wol(self) -> bool:
        """Power on the TV using Wake-on-LAN.
        
        This is used by the power_on method when the WebOS API method fails
        or there is no active connection.
        
        Returns:
            True if WoL was sent successfully, False otherwise
        """
        mac_address = self.state.get("mac_address")
        if not mac_address:
            logger.warning("Cannot use Wake-on-LAN: No MAC address configured for TV")
            return False
            
        logger.info(f"Attempting to power on via Wake-on-LAN to MAC: {mac_address}")
        # Use the send_wol_packet method from BaseDevice
        wol_success = await self.send_wol_packet(mac_address)
        if wol_success:
            logger.info("Wake-on-LAN packet sent successfully")
            # We can't be certain the TV will power on, but we've done our part
            # Assume it worked for state tracking purposes
            self.state["power"] = "on"
            
            # Use LastCommand object instead of string
            self.state["last_command"] = LastCommand(
                action="power_on",
                source="wol",
                timestamp=datetime.now(),
                params={"method": "wol", "mac_address": mac_address}
            ).dict()
            
            return True
        else:
            logger.error("Failed to send Wake-on-LAN packet")
            return False
            
    async def power_off(self):
        """Power off the TV.
        
        Returns:
            True if power off was successful, False otherwise
        """
        try:
            logger.info(f"Powering off TV {self.get_name()}")
            
            # Use system power_off_with_monitoring method
            if self.system and self.client and self.state.get("connected", False):
                result = await self._execute_with_monitoring(
                    self.system, 
                    "power_off_with_monitoring", 
                    timeout=10.0
                )
                
                if result.get("success", False):
                    self.state["power"] = "off"
                    self.state["last_command"] = LastCommand(
                        action="power_off",
                        source="api",
                        timestamp=datetime.now()
                    ).dict()
                    return True
                else:
                    logger.warning(f"Power off failed: {result.get('error', 'Unknown error')}")
                    error_msg = result.get('error', 'Unknown error')
                    self.state["last_command"] = LastCommand(
                        action="power_off",
                        source="api",
                        timestamp=datetime.now(),
                        params={"error": error_msg}
                    ).dict()
                    return False
            else:
                logger.error("Cannot power off: Not connected to TV")
                self.state["last_command"] = LastCommand(
                    action="power_off",
                    source="api",
                    timestamp=datetime.now(),
                    params={"error": "Not connected to TV"}
                ).dict()
                return False
                
        except Exception as e:
            logger.error(f"Error powering off TV: {str(e)}")
            self.state["last_command"] = LastCommand(
                action="power_off",
                source="api",
                timestamp=datetime.now(),
                params={"error": str(e)}
            ).dict()
            return False
    
    async def handle_mute(self, action_config: Dict[str, Any]):
        """Handle mute action.
        
        This method toggles or sets the mute state of the TV using MediaControl.
        
        Args:
            action_config: Configuration for the action, can contain 'state' to set specific mute state
            
        Returns:
            True if successful, False otherwise
        """
        return await self._execute_media_command(
            action_name="mute",
            media_method_name="set_mute_with_monitoring",
            action_config=action_config,
            state_key_to_update="mute",
            position="button",
            requires_state=True
        )
    
    async def launch_app(self, app_name):
        """Launch an app by name or ID.
        
        Args:
            app_name: The name or ID of the app to launch
            
        Returns:
            True if app launch was successful, False otherwise
        """
        try:
            logger.info(f"Launching app {app_name} on TV {self.get_name()}")
            
            if not self.client or not self.app or not self.state.get("connected", False):
                logger.error("TV client or application control not initialized")
                return False
            
            # First retrieve list of available apps
            try:
                apps = await self._get_available_apps_internal()
                
                if not apps:
                    logger.error("Could not retrieve list of apps")
                    return False
                
                # Try to find the app by name or ID
                target_app = self._find_app_by_name_or_id(apps, app_name)
                
                if not target_app:
                    logger.error(f"App {app_name} not found on TV")
                    return False
                
                # Launch the app with monitoring for more reliability
                result = await self._execute_with_monitoring(
                    self.app,
                    "launch_with_monitoring",
                    target_app["id"],
                    timeout=30.0
                )
                
                if result.get("success", False):
                    self.state["current_app"] = target_app["id"]
                    self.state["last_command"] = f"launch_app_{app_name}"
                    return True
                else:
                    logger.error(f"Failed to launch app: {result.get('error', 'Unknown error')}")
                    return False
                
            except Exception as e:
                logger.error(f"Error retrieving apps or launching app: {str(e)}")
                return False
            
        except Exception as e:
            logger.error(f"Error launching app: {str(e)}")
            return False
            
    def _find_app_by_name_or_id(self, apps, app_name):
        """Find an app by name or ID from a list of apps.
        
        Args:
            apps: List of app dictionaries from the TV
            app_name: The name or ID to search for
            
        Returns:
            The found app dictionary or None if not found
        """
        for app in apps:
            # Match by ID (exact) or title (case-insensitive contains)
            if app_name == app.get("id") or app_name.lower() in app.get("title", "").lower():
                return app
        return None
        
    async def _get_available_apps_internal(self):
        """Internal method to get available apps from the TV.
        
        Returns:
            List of app dictionaries or empty list if retrieval fails
        """
        from typing import cast, Any
        
        if not self.client or not self.app or not self.state.get("connected", False):
            logger.error("Cannot get apps: Not connected to TV")
            return []
            
        try:
            # Cast to Any to avoid type checking issues
            app_control = cast(Any, self.app)
            return await app_control.list_apps()
        except Exception as e:
            logger.error(f"Failed to get apps: {str(e)}")
            return []
            
    async def get_available_apps(self):
        """Get a list of available apps.
        
        Returns:
            List of app dictionaries from the TV
        """
        return await self._get_available_apps_internal()
    
    async def execute_action(self, action: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """Execute a device-specific action and return a Pydantic-compatible dictionary."""
        params = params or {}
        error_message: Optional[str] = None
        success_status: bool = False
        message: str = f"Action '{action}' initiated." # Default message

        # DEBUG: Log available handlers and the action being looked up
        logger.debug(f"Looking for handler for action: '{action}'")
        logger.debug(f"Available handlers: {list(self._action_handlers.keys())}")
        logger.debug(f"Handler method exists: {'handle_' + action in dir(self)}")

        handler = self._get_action_handler(action)

        # DEBUG: Log handler result
        logger.debug(f"Handler lookup result: {handler}")

        if not handler:
            error_message = f"Unknown action: {action}"
            message = error_message
            success_status = False
        else:
            try:
                # Execute the handler
                handler_result = await handler(params)

                # Check boolean result common to most handlers
                if isinstance(handler_result, bool):
                    success_status = handler_result
                    message = f"Action '{action}' {'succeeded' if success_status else 'failed'}."
                    if not success_status:
                        # Try to get more specific error from state if available after failed action
                        current_error_in_state = self.state.get("error") # Check state *after* handler execution
                        if current_error_in_state:
                           error_message = current_error_in_state
                        else:
                           error_message = f"Action '{action}' failed with no specific error reported."
                           # Keep message as "failed"
                # Potentially handle dict results if some handlers return more info
                # elif isinstance(handler_result, dict):
                #    success_status = handler_result.get("success", False)
                #    message = handler_result.get("message", f"Action '{action}' completed.")
                #    error_message = handler_result.get("error") if not success_status else None
                else:
                    # Handle unexpected return types
                    success_status = False
                    error_message = f"Action '{action}' handler returned unexpected type: {type(handler_result)}"
                    message = error_message

            except Exception as e:
                logger.error(f"Error executing action '{action}': {str(e)}")
                success_status = False
                error_message = f"Error executing action: {str(e)}"
                message = error_message

        # Get the current state *after* the action attempt
        # Assumes get_current_state() is inherited from BaseDevice and returns self.state
        current_state = self.get_current_state()

        # Construct the response dictionary matching DeviceActionResponse
        response_dict = {
            "success": success_status,
            "device_id": self.get_id(),
            "action": action,
            "state": current_state,
            "error": error_message,
            "message": message
        }
        return response_dict

    # Handler methods for cursor control
    async def handle_move_cursor(self, action_config: Dict[str, Any]) -> bool:
        """Handle move_cursor action.
        
        Args:
            action_config: Dictionary with parameters including x, y, and optional drag
            
        Returns:
            True if successful, False otherwise
        """
        return await self._execute_pointer_command(
            action_name="move_cursor",
            action_config=action_config,
            use_ws_send=True, 
            required_params=["x", "y"],
            optional_params={"drag": False}
        )
            
    async def handle_move_cursor_relative(self, action_config: Dict[str, Any]) -> bool:
        """Handle move_cursor_relative action.
        
        Args:
            action_config: Dictionary with parameters including dx, dy, and optional drag
            
        Returns:
            True if successful, False otherwise
        """
        return await self._execute_pointer_command(
            action_name="move_cursor_relative",
            action_config=action_config,
            use_ws_send=True,
            required_params=["dx", "dy"],
            optional_params={"drag": False}
        )
            
    async def handle_click(self, action_config: Dict[str, Any]) -> bool:
        """Handle click action.
        
        Args:
            action_config: Dictionary with parameters including x and y
            
        Returns:
            True if successful, False otherwise
        """
        return await self._execute_pointer_command(
            action_name="click",
            action_config=action_config,
            use_ws_send=False, # Uses input_control.click()
            required_params=["x", "y"]
        )

    # Action handlers for base class handle_message to use

    async def handle_power_on(self, params: Dict[str, Any] = None, **kwargs):
        """Handle power on action."""
        # Backward compatibility - params can come either as a named parameter or as kwargs['action_config']
        action_config = kwargs.get('action_config', params or {})
        result = await self.power_on()
        return result
        
    async def handle_home(self, action_config: Dict[str, Any]):
        """Handle home button action.
        
        This method sends a home button press command to the TV using the
        InputControl interface from the asyncwebostv library.
        
        Args:
            action_config: Configuration for the action (not used)
            
        Returns:
            True if successful, False otherwise
        """
        return await self._execute_simple_command(
            self.input_control,
            "home",
            "button"
        )
        
    async def handle_back(self, action_config: Dict[str, Any]):
        """Handle back button action.
        
        This method sends a back button press command to the TV using the
        InputControl interface from the asyncwebostv library.
        
        Args:
            action_config: Configuration for the action (not used)
            
        Returns:
            True if successful, False otherwise
        """
        return await self._execute_simple_command(
            self.input_control,
            "back",
            "button"
        )
        
    async def handle_up(self, action_config: Dict[str, Any]):
        """Handle up button action.
        
        This method sends a up button press command to the TV using the
        InputControl interface from the asyncwebostv library.
        
        Args:
            action_config: Configuration for the action (not used)
            
        Returns:
            True if successful, False otherwise
        """
        return await self._execute_simple_command(
            self.input_control,
            "up",
            "button"
        )
        
    async def handle_down(self, action_config: Dict[str, Any]):
        """Handle down button action.
        
        This method sends a down button press command to the TV using the
        InputControl interface from the asyncwebostv library.
        
        Args:
            action_config: Configuration for the action (not used)
            
        Returns:
            True if successful, False otherwise
        """
        return await self._execute_simple_command(
            self.input_control,
            "down",
            "button"
        )
        
    async def handle_left(self, action_config: Dict[str, Any]):
        """Handle left button action.
        
        This method sends a left button press command to the TV using the
        InputControl interface from the asyncwebostv library.
        
        Args:
            action_config: Configuration for the action (not used)
            
        Returns:
            True if successful, False otherwise
        """
        return await self._execute_simple_command(
            self.input_control,
            "left",
            "button"
        )
        
    async def handle_right(self, action_config: Dict[str, Any]):
        """Handle right button action.
        
        This method sends a right button press command to the TV using the
        InputControl interface from the asyncwebostv library.
        
        Args:
            action_config: Configuration for the action (not used)
            
        Returns:
            True if successful, False otherwise
        """
        return await self._execute_simple_command(
            self.input_control,
            "right",
            "button"
        )
        
    async def handle_enter(self, action_config: Dict[str, Any]):
        """Handle ok button action.
        
        This method sends a ok button press command to the TV using the
        InputControl interface from the asyncwebostv library.
        
        Args:
            action_config: Configuration for the action (not used)
            
        Returns:
            True if successful, False otherwise
        """
        return await self._execute_simple_command(
            self.input_control,
            "ok",
            "button"
        )
        
    async def handle_exit(self, action_config: Dict[str, Any]):
        """Handle exit button action.
        
        Args:
            action_config: Configuration for the action (not used)
            
        Returns:
            True if successful, False otherwise
        """
        # Assuming InputControl has an 'exit' method
        return await self._execute_simple_command(
            self.input_control,
            "exit",
            "button"
        )

    async def handle_menu(self, action_config: Dict[str, Any]):
        """Handle menu button action.
        
        Args:
            action_config: Configuration for the action (not used)
            
        Returns:
            True if successful, False otherwise
        """
        # Assuming InputControl has a 'menu' method
        return await self._execute_simple_command(
            self.input_control,
            "menu",
            "button"
        )

    async def handle_settings(self, action_config: Dict[str, Any]):
        """Handle settings button action.
        
        Args:
            action_config: Configuration for the action (not used)
            
        Returns:
            True if successful, False otherwise
        """
        # Assuming InputControl has a 'settings' method
        return await self._execute_simple_command(
            self.input_control,
            "settings",
            "button"
        )
        
    async def handle_volume_up(self, action_config: Dict[str, Any]):
        """Handle volume up action.
        
        This method increases the volume level of the TV using MediaControl.
        
        Args:
            action_config: Configuration for the action (not used)
            
        Returns:
            True if successful, False otherwise
        """
        return await self._execute_media_command(
            action_name="volume_up",
            media_method_name="volume_up_with_monitoring",
            action_config=action_config,
            state_key_to_update="volume",
            position="button",
            update_volume_after=True
        )
        
    async def handle_volume_down(self, action_config: Dict[str, Any]):
        """Handle volume down action.
        
        This method decreases the volume level of the TV using MediaControl.
        
        Args:
            action_config: Configuration for the action (not used)
            
        Returns:
            True if successful, False otherwise
        """
        return await self._execute_media_command(
            action_name="volume_down",
            media_method_name="volume_down_with_monitoring",
            action_config=action_config,
            state_key_to_update="volume",
            position="button",
            update_volume_after=True
        )
        
    async def handle_set_volume(self, action_config: Dict[str, Any]):
        """Handle set volume action.
        
        This method sets the volume level of the TV using MediaControl.
        
        Args:
            action_config: Configuration for the action, must contain 'level' for volume level
            
        Returns:
            True if successful, False otherwise
        """
        return await self._execute_media_command(
            action_name="set_volume",
            media_method_name="set_volume_with_monitoring",
            action_config=action_config,
            state_key_to_update="volume",
            position="volume",
            requires_level=True
        )
            
    async def handle_play(self, action_config: Dict[str, Any]):
        """Handle play button action."""
        return await self._execute_simple_command(self.media, "play", "playback")
        
    async def handle_pause(self, action_config: Dict[str, Any]):
        """Handle pause button action."""
        return await self._execute_simple_command(self.media, "pause", "playback")
        
    async def handle_stop(self, action_config: Dict[str, Any]):
        """Handle stop button action."""
        return await self._execute_simple_command(self.media, "stop", "playback")
        
    async def handle_rewind_forward(self, action_config: Dict[str, Any]):
        """Handle fast forward action (corresponds to rewind_forward in config)."""
        return await self._execute_simple_command(
            self.media, 
            "rewind_forward", 
            "playback", 
            control_method_name="fastForward"
        )
        
    async def handle_rewind_backward(self, action_config: Dict[str, Any]):
        """Handle rewind action (corresponds to rewind_backward in config)."""
        return await self._execute_simple_command(
            self.media, 
            "rewind_backward", 
            "playback", 
            control_method_name="rewind"
        )

    async def handle_kinopoisk(self, action_config: Dict[str, Any]):
        """Handle launching the Kinopoisk app using the configured appname."""
        appname = action_config.get("appname")
        if not appname:
            logger.error(f"Missing 'appname' in action configuration for {self.get_name()}: kinopoisk")
            return False
        logger.info(f"Executing configured action 'kinopoisk' to launch app '{appname}'")
        return await self.launch_app(appname)

    async def handle_ivi(self, action_config: Dict[str, Any]):
        """Handle launching the IVI app using the configured appname."""
        appname = action_config.get("appname")
        if not appname:
            logger.error(f"Missing 'appname' in action configuration for {self.get_name()}: ivi")
            return False
        logger.info(f"Executing configured action 'ivi' to launch app '{appname}'")
        return await self.launch_app(appname)

    async def handle_hdmi1(self, action_config: Dict[str, Any]):
        """Handle setting input source to HDMI1."""
        logger.info(f"Executing action 'hdmi1' to set input source on {self.get_name()}")
        return await self.set_input_source("hdmi1")
        
    async def handle_hdmi2(self, action_config: Dict[str, Any]):
        """Handle setting input source to HDMI2."""
        logger.info(f"Executing action 'hdmi2' to set input source on {self.get_name()}")
        return await self.set_input_source("hdmi2")
        
    async def handle_hdmi3(self, action_config: Dict[str, Any]):
        """Handle setting input source to HDMI3."""
        logger.info(f"Executing action 'hdmi3' to set input source on {self.get_name()}")
        return await self.set_input_source("hdmi3")

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
                self.state["last_command"] = LastCommand(
                    action="wake_on_lan",
                    source="api",
                    timestamp=datetime.now(),
                    params={"error": "No MAC address configured"}
                ).dict()
                return False
                
            logger.info(f"Sending Wake-on-LAN packet to TV {self.get_name()} (MAC: {mac_address})")
            
            # Use the send_wol_packet method from BaseDevice
            wol_success = await self.send_wol_packet(mac_address)
            
            if wol_success:
                logger.info("Wake-on-LAN packet sent successfully")
                self.state["last_command"] = LastCommand(
                    action="wake_on_lan",
                    source="api",
                    timestamp=datetime.now(),
                    params={"mac_address": mac_address}
                ).dict()
                # We can't know for sure if the TV will turn on,
                # but update the expected state for consistency
                self.state["power"] = "on"
                return True
            else:
                logger.error("Failed to send Wake-on-LAN packet")
                self.state["last_command"] = LastCommand(
                    action="wake_on_lan",
                    source="api",
                    timestamp=datetime.now(),
                    params={"error": "Failed to send packet"}
                ).dict()
                return False
                
        except Exception as e:
            logger.error(f"Error sending Wake-on-LAN packet: {str(e)}")
            self.state["last_command"] = LastCommand(
                action="wake_on_lan",
                source="api",
                timestamp=datetime.now(),
                params={"error": str(e)}
            ).dict()
            return False

    async def handle_wake_on_lan(self, action_config: Dict[str, Any]):
        """Handle Wake-on-LAN action."""
        result = await self.wake_on_lan()
        
        # If the wake_on_lan was successful and the action config requests waiting
        if result and action_config.get("wait_for_boot", False):
            # Wait for the TV to boot using the configured timeout
            boot_wait_time = getattr(self.tv_config, "timeout", 15) if self.tv_config else 15
            logger.info(f"Wake-on-LAN sent. Waiting {boot_wait_time} seconds for TV to boot...")
            await asyncio.sleep(boot_wait_time)
            
        return result

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
    
    async def _register_client(self, key_store: Optional[Dict[str, str]] = None) -> bool:
        """Register the client with the TV.
        
        This handles the WebOS registration flow, which is required
        even with an existing client key. Registration may require user
        confirmation on the TV.
        
        Args:
            key_store: Optional dictionary to store the client key
            
        Returns:
            True if registration completed successfully, False otherwise
        """
        try:
            if not self.client:
                logger.error("Cannot register: No client available")
                return False
                
            # Create a key store if not provided
            if key_store is None:
                key_store = {}
                if self.client_key:
                    key_store["client_key"] = self.client_key
            
            # Use the registration process which handles both new and existing keys
            connection_success = False
            registration_completed = False
            
            try:
                async for status in self.client.register(key_store):
                    if status == WebOSClient.PROMPTED:
                        logger.info(f"Please accept the connection on TV {self.get_name()}!")
                        self.state["error"] = "Waiting for user to accept connection on TV"
                    elif status == WebOSClient.REGISTERED:
                        logger.info(f"Registration successful for TV {self.get_name()}")
                        
                        # Update the client key if it was provided or changed
                        if key_store.get("client_key"):
                            self.client_key = key_store.get("client_key")
                            logger.info(f"Client key for future use: {self.client_key}")
                        
                        registration_completed = True
                
                # If we get here without errors, registration was successful
                connection_success = registration_completed
            except Exception as reg_error:
                logger.error(f"Registration error: {str(reg_error)}")
                self.state["error"] = f"Registration error: {str(reg_error)}"
                connection_success = False
            
            return connection_success
            
        except Exception as e:
            logger.error(f"Error during client registration: {str(e)}")
            self.state["error"] = f"Registration error: {str(e)}"
            return False

    async def set_input_source(self, input_source):
        """Set the TV input source.
        
        Args:
            input_source: The name or ID of the input source
            
        Returns:
            True if input source was successfully set, False otherwise
        """
        try:
            logger.info(f"Setting input source to {input_source} on TV {self.get_name()}")
            
            if not self.client or not self.input_control or not self.state.get("connected", False):
                logger.error("TV client or input control not initialized")
                return False
            
            # First retrieve list of available sources
            try:
                sources = await self._get_available_inputs()
                
                if not sources:
                    logger.error("No input sources available")
                    return False
                
                # Try to find the source by name or ID
                target_source = self._find_input_by_name_or_id(sources, input_source)
                
                if not target_source:
                    logger.error(f"Input source {input_source} not found on TV")
                    return False
                
                # Set the input source with monitoring for more reliable input switching
                result = await self._execute_with_monitoring(
                    self.input_control,
                    "set_input_with_monitoring",
                    target_source["id"],
                    timeout=10.0
                )
                
                if result.get("success", False):
                    self.state["input_source"] = target_source["id"]
                    await self._update_last_command(action=f"set_input_{input_source}", position="input")
                    return True
                else:
                    logger.warning(f"Input source set failed: {result.get('error', 'Unknown error')}")
                    return False
                
            except Exception as e:
                logger.error(f"Error retrieving or setting input source: {str(e)}")
                return False
        except Exception as e:
            logger.error(f"Error setting input source: {str(e)}")
            return False
            
    async def _get_available_inputs(self):
        """Get available input sources from the TV.
        
        Returns:
            List of input source dictionaries or empty list on failure
        """
        from typing import cast, Any
        
        if not self.client or not self.input_control or not self.state.get("connected", False):
            logger.error("Cannot get inputs: Not connected to TV")
            return []
            
        try:
            # Cast to Any to avoid type checking issues
            input_control = cast(Any, self.input_control)
            return await input_control.list_inputs()
        except Exception as e:
            logger.error(f"Failed to get input sources: {str(e)}")
            return []
            
    def _find_input_by_name_or_id(self, sources, input_source):
        """Find an input source by name or ID.
        
        Args:
            sources: List of input source dictionaries from the TV
            input_source: The name or ID to search for
            
        Returns:
            The found input source dictionary or None if not found
        """
        for source in sources:
            # Match by ID (exact) or label (case-insensitive contains)
            if input_source == source.get("id") or input_source.lower() in source.get("label", "").lower():
                return source
        return None
    
    async def _update_last_command(self, action: str, params: Optional[Dict[str, Any]] = None, position: Optional[str] = None, source: str = "api"):
        """Helper method to update the last_command state."""
        try:
            self.update_state({
                "last_command": LastCommand(
                    action=action,
                    source=source,
                    timestamp=datetime.now(),
                    params=params if params else {},
                    position=position
                ).dict()
            })
        except Exception as e:
            # Log error but don't prevent the main action from completing
            logger.error(f"Error updating last_command state for action '{action}': {e}")

    async def _execute_simple_command(
        self,
        control_instance: Any, # Pass the control object (e.g., self.input_control, self.media)
        action_name: str,
        position: str,          # Position for last_command state (e.g., "button", "playback")
        control_method_name: Optional[str] = None
    ) -> bool:
        """Executes a simple, parameter-less command using a given control instance.
        
        Handles connection checks, method invocation, state updates, and logging.
        
        Args:
            control_instance: The control object instance (e.g., self.input_control, self.media).
            action_name: The logical name of the action (e.g., "home", "play"). Used for logging and state update.
            position: The position identifier for the last_command state (e.g., "button", "playback").
            control_method_name: The specific method name on the control instance to call.
                                 Defaults to action_name if not provided.
                                 
        Returns:
            True if successful, False otherwise.
        """
        method_to_call = control_method_name if control_method_name else action_name
        control_name = type(control_instance).__name__ if control_instance else "None"
        try:
            logger.info(f"Sending {action_name.upper()} command via {control_name} to TV {self.get_name()}")
            
            # Check client connection and if the control instance is valid
            if not self.client or not control_instance or not self.state.get("connected", False):
                logger.error(f"Cannot send {action_name.upper()} command: Not connected or {control_name} not available")
                return False
                
            # Get the method from the provided control instance
            instance_method = getattr(control_instance, method_to_call, None)
            if not instance_method or not callable(instance_method):
                logger.error(f"{control_name} method '{method_to_call}' not found or not callable for action '{action_name}'")
                return False

            # Call the control instance method
            await instance_method()
            
            # Update state with last command information
            await self._update_last_command(action=action_name, position=position)
            
            return True
        except Exception as e:
            logger.error(f"Error sending {action_name.upper()} command via {control_name}: {str(e)}")
            # Optionally update last command state to reflect error
            # await self._update_last_command(action=f"{action_name}_error", position=position)
            return False

    async def _execute_media_command(
        self,
        action_name: str,
        media_method_name: str,
        action_config: Dict[str, Any],
        state_key_to_update: str,
        position: str,
        requires_level: bool = False,
        requires_state: bool = False,
        update_volume_after: bool = False
    ) -> bool:
        """Executes a command using MediaControl.
        
        Handles connection checks, parameter validation (level/state),
        execution via _execute_with_monitoring, state updates, and logging.
        """
        try:
            logger.info(f"Handling action '{action_name}' on TV {self.get_name()}")

            if not self.client or not self.media or not self.state.get("connected", False):
                logger.error(f"Cannot handle '{action_name}': Not connected or media control not available")
                return False

            params = {}
            args_for_method = []

            # Handle parameter validation and preparation
            if requires_level:
                if "level" not in action_config:
                    logger.error(f"Missing 'level' parameter for {action_name}")
                    return False
                level = action_config["level"]
                try:
                    level = int(level)
                except (ValueError, TypeError):
                    logger.error(f"Invalid volume level for {action_name}: {level}")
                    return False
                level = max(0, min(100, level)) # Clamp to 0-100
                args_for_method.append(level)
                params["level"] = level
            
            elif requires_state: # e.g., for mute
                if "state" in action_config:
                    state = action_config["state"]
                    if isinstance(state, str):
                        state = state.lower() in ["true", "1", "yes", "on"]
                else:
                    # Toggle if state not specified
                    current_state = self.state.get(state_key_to_update, False)
                    state = not current_state
                args_for_method.append(state)
                params["state"] = state
            
            # Execute the command using the monitoring helper
            result = await self._execute_with_monitoring(
                self.media,
                media_method_name,
                *args_for_method, 
                timeout=5.0
            )

            if result.get("success", False):
                # Update the specific state key (volume or mute)
                if requires_level:
                    self.state[state_key_to_update] = level
                elif requires_state:
                    self.state[state_key_to_update] = state
                
                # Optionally update volume state after the action
                if update_volume_after:
                    try:
                        volume_info = await cast(Any, self.media).get_volume()
                        if volume_info and "volume" in volume_info:
                            self.state["volume"] = volume_info["volume"]
                    except Exception as vol_err:
                        logger.debug(f"Could not update volume after {action_name}: {vol_err}")
                
                # Update last command
                await self._update_last_command(action=action_name, params=params, position=position)
                return True
            else:
                logger.warning(f"{action_name} failed: {result.get('error', 'Unknown error')}")
                return False

        except Exception as e:
            logger.error(f"Error handling {action_name} action: {str(e)}")
            return False
            
    async def _execute_pointer_command(
        self,
        action_name: str,
        action_config: Dict[str, Any],
        use_ws_send: bool,
        required_params: List[str],
        optional_params: Optional[Dict[str, Any]] = None,
        position: str = "cursor"
    ) -> bool:
        """Executes a pointer/cursor command (move, click).
        
        Handles connection checks, parameter validation, WebSocket ensure/send or click,
        state updates, and logging.
        """
        optional_params = optional_params or {}
        try:
            logger.info(f"Handling pointer action '{action_name}' on TV {self.get_name()}")
            
            if not self.client or not self.input_control or not self.state.get("connected", False):
                logger.error(f"Cannot handle '{action_name}': Not connected or input control not available")
                return False
                
            payload = {}
            # Validate required parameters
            for param in required_params:
                if param not in action_config:
                    logger.error(f"Missing '{param}' parameter for {action_name}")
                    return False
                try:
                    payload[param] = int(action_config[param])
                except (ValueError, TypeError):
                    logger.error(f"Parameter '{param}' for {action_name} must be an integer")
                    return False
            
            # Add optional parameters
            for param, default in optional_params.items():
                payload[param] = action_config.get(param, default)
                # Special handling for drag if it needs conversion
                if param == "drag" and isinstance(payload[param], str):
                    payload[param] = payload[param].lower() == 'true'
            
            # Execute the command
            if use_ws_send:
                 # Ensure WebSocket connection
                if not self.input_control.ws_client:
                    await self.input_control._ensure_pointer_socket()
                    
                if not self.input_control.ws_client:
                    logger.error(f"Failed to establish WebSocket connection for {action_name}")
                    return False
                    
                # Add required fields for specific ws commands
                if action_name == "move_cursor_relative":
                    payload["move"] = True # Required for relative move via ws
                
                # Send payload via WebSocket
                await self.input_control.ws_client.send(json.dumps(payload))
            else: # Use input_control.click()
                await self.input_control.click(**payload)
            
            # Update last command
            await self._update_last_command(action=action_name, params=payload, position=position)
            return True

        except Exception as e:
            logger.error(f"Error executing pointer action {action_name}: {str(e)}")
            return False

    async def handle_power_off(self, params: Dict[str, Any] = None, **kwargs):
        """Handle power off action."""
        # Backward compatibility - params can come either as a named parameter or as kwargs['action_config'] 
        action_config = kwargs.get('action_config', params or {})
        result = await self.power_off()
        return result

    
