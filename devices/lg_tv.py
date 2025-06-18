import json
import logging
import asyncio
import os
import ssl
from typing import Dict, Any, List, Optional, Tuple, TYPE_CHECKING, Union, cast, Protocol, TypeVar

# Import WebOSTV classes for higher-level API access
from asyncwebostv import WebOSTV, SecureWebOSTV

# Keep original imports for backward compatibility
from asyncwebostv.connection import WebOSClient
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
from app.schemas import LgTvState, LgTvConfig, LastCommand, LgTvDeviceConfig, StandardCommandConfig
from app.mqtt_client import MQTTClient
from datetime import datetime
# Import the new type definitions
from app.types import CommandResult, CommandResponse, ActionHandler, StateT

logger = logging.getLogger(__name__)

class LgTv(BaseDevice[LgTvState]):
    """Implementation of an LG TV controlled over the network using AsyncWebOSTV library."""
    
    def __init__(self, config: LgTvDeviceConfig, mqtt_client: Optional[MQTTClient] = None):
        # Initialize base device with config and state class
        super().__init__(config, mqtt_client)
        
        # The base class now handles the typed config directly
        # No need to store self.typed_config separately
        
        # Initialize state schema for proper state handling
        self._state_schema = LgTvState
        
        # Create initial state with default values
        self.state = LgTvState(
            device_id=self.config.device_id,
            device_name=self.config.device_name,
            power="unknown",
            volume=None,  # Changed from 0 to None to indicate unknown initial volume
            mute=False,
            current_app=None,
            input_source=None,
            last_command=None,
            connected=False,
            ip_address=None,
            mac_address=None
        )
        
        self.client = None
        self.system = None
        self.media = None
        self.app = None
        self.tv_control = None
        self.input_control = None
        self.source_control = None
        
        # Get the TV config directly from the config
        self.tv_config = self.config.tv
        
        # Initialize client_key from TV configuration
        self.client_key = self.tv_config.client_key
        
        # Initialize IP address from TV configuration
        self.state.ip_address = self.tv_config.ip_address
        
        # Initialize MAC address from TV configuration if available
        self.state.mac_address = self.tv_config.mac_address
        
        # Cache for available apps and input sources
        self._cached_apps = []
        self._cached_input_sources = []

        # Initialize broadcast IP address from configuration or auto-detect
        if self.tv_config.broadcast_ip:
            self.broadcast_ip = self.tv_config.broadcast_ip
            logger.info(f"Using configured broadcast IP: {self.broadcast_ip}")
        else:
            self.broadcast_ip = self.get_broadcast_ip()
            logger.warning(f"No broadcast_ip configured, auto-detected: {self.broadcast_ip}. "
                         f"Consider adding 'broadcast_ip' to your TV configuration for better reliability.")
        
        # Register action handlers is now handled by BaseDevice via _register_handlers
        # self._register_lg_tv_action_handlers()
        
        # DEBUG: Look for handler methods in the class
        handler_methods = [m for m in dir(self) if m.startswith("handle_") and callable(getattr(self, m))]
        logger.debug(f"Found handler methods in {self.device_name}: {handler_methods}")
        logger.debug(f"Action handlers dictionary: {self._action_handlers}")
        
        # DEBUG: Check specific handlers
        has_power_on = hasattr(self, "handle_power_on") and callable(getattr(self, "handle_power_on"))
        logger.debug(f"Has handle_power_on method: {has_power_on}")
    
    def _create_webos_tv(self, secure: bool = False) -> Optional[Union[WebOSTV, SecureWebOSTV]]:
        """Create a WebOSTV client based on configuration.
        
        Args:
            secure: Whether to create a secure client
            
        Returns:
            WebOSTV instance or None if creation fails
        """
        try:
            # Check if we have configuration and IP address
            if not self.tv_config:
                logger.error("TV configuration not initialized")
                return None
                
            ip = self.state.ip_address
            if not ip:
                logger.error("No IP address configured for TV")
                return None
                
            # Use configuration from TV config
            secure_mode = secure if secure else self.tv_config.secure
            
            # Create the appropriate client type
            if secure_mode:
                logger.info(f"Creating secure WebOSTV client for {ip}")
                
                # Get certificate file path if provided
                cert_file = self.tv_config.cert_file
                
                # Get any additional SSL options
                ssl_options = {}
                if self.tv_config.ssl_options:
                    ssl_options = self.tv_config.ssl_options
                
                # Always set verify_ssl to False by default for WebOS TVs, as they use self-signed certificates
                # Only override if explicitly set in ssl_options
                verify_ssl = ssl_options.get('verify_ssl', False)
                
                # Ensure port is set to 3001 for secure WebSocket connections
                port = ssl_options.get('port', 3001)
                
                # Create a secure WebOSTV client
                return SecureWebOSTV(
                    host=ip,
                    port=port,
                    client_key=self.client_key,
                    cert_file=cert_file,
                    verify_ssl=verify_ssl,
                    ssl_options=ssl_options
                )
            else:
                logger.info(f"Creating standard WebOSTV client for {ip}")
                return WebOSTV(ip, client_key=self.client_key, secure=False)
                
        except Exception as e:
            logger.error(f"Error creating WebOSTV client: {str(e)}")
            self.set_error(f"Client creation error: {str(e)}")
            return None
            
    async def _initialize_control_interfaces(self) -> bool:
        """Initialize control interfaces mapping to WebOSTV's controls.
        
        Since WebOSTV already initializes controls, this method maps them to our class properties
        for compatibility with existing code.
        
        Returns:
            True if initialization was successful, False otherwise
        """
        try:
            if not self.client:
                logger.error("Cannot initialize controls: No client available")
                return False
                
            # Map WebOSTV control interfaces to our class properties
            self.system = self.client.system
            self.media = self.client.media
            self.app = self.client.application  # Note the name difference
            self.tv_control = self.client.tv
            self.input_control = self.client.input
            self.source_control = self.client.source
            
            # Verify we can access at least one control to confirm initialization is working
            try:
                # Use a simple non-state-changing call to check connection is working
                if self.system:
                    await self.system.info()
                    logger.info(f"Control interfaces successfully initialized for {self.get_name()}")
                    
                    # After successful initialization, cache the list of apps and input sources
                    await self._refresh_app_cache()
                    await self._refresh_input_sources_cache()
                else:
                    logger.warning("System control is not available, cannot verify connection")
                
            except Exception as control_err:
                logger.warning(f"Controls initialized but test call failed: {str(control_err)}")
                # We still consider initialization successful if objects were created
            
            return True
        except Exception as e:
            logger.error(f"Error initializing control interfaces: {str(e)}")
            return False
            
    async def _refresh_app_cache(self) -> bool:
        """Refresh the cached list of available apps from the TV.
        
        Returns:
            True if refresh was successful, False otherwise
        """
        try:
            if not self.app or not self.client or not self.state.connected:
                logger.debug("Cannot refresh app cache: Not connected to TV or app control not available")
                return False
                
            from typing import cast, Any
            
            # Cast to Any to avoid type checking issues
            app_control = cast(Any, self.app)
            apps = await app_control.list_apps()
            
            if apps is not None:
                self._cached_apps = apps
                logger.info(f"App cache refreshed: {len(apps)} apps available")
                
                # Log all available apps in a simplified format for easier debugging
                app_list = []
                for app in apps:
                    app_id, app_name = self._get_app_info(app, "Unknown")
                    app_list.append({"id": app_id, "name": app_name})
                
                logger.debug(f"Available apps: {json.dumps(app_list, indent=2, ensure_ascii=False)}")
                return True
            else:
                logger.warning("Failed to get app list from TV")
                return False
                
        except Exception as e:
            logger.error(f"Error refreshing app cache: {str(e)}")
            return False
            
    def _process_input_source(self, source) -> Optional[Dict[str, str]]:
        """Process a single input source into a standardized format.
        
        Args:
            source: The input source (dict, string, or other type)
            
        Returns:
            Standardized input source dict with id and name, or None if invalid
        """
        try:
            # Handle different source types (dict or string)
            if isinstance(source, dict):
                source_id = source.get("id", "unknown")
                source_name = source.get("label", source.get("title", "Unknown"))
            elif isinstance(source, str):
                # For string sources, use the string as both ID and name
                source_id = source
                source_name = source
            else:
                # Skip non-dict, non-string sources
                logger.debug(f"Skipping unsupported source type: {type(source)}")
                return None
            
            # Only include sources with valid IDs
            if not source_id or source_id == "unknown":
                return None
                
            return {"id": source_id, "name": source_name}
        except Exception as e:
            logger.debug(f"Error processing source {source}: {str(e)}")
            return None

    async def _refresh_input_sources_cache(self) -> bool:
        """Refresh the cached list of available input sources from the TV.
        
        Returns:
            True if refresh was successful, False otherwise
        """
        try:
            if not self.input_control and not self.source_control:
                logger.debug("Cannot refresh input sources cache: neither input_control nor source_control available")
                return False
            if not self.client:
                logger.debug("Cannot refresh input sources cache: client not available")
                return False
            if not self.state.connected:
                logger.debug("Cannot refresh input sources cache: TV not connected")
                return False
                
            from typing import cast, Any
            raw_sources = None
            
            # First try using input_control.list_inputs() if available
            if self.input_control:
                # Cast to Any to avoid type checking issues
                input_control = cast(Any, self.input_control)
                logger.debug(f"Calling list_inputs() on input control of type: {type(input_control)}")
                
                try:
                    raw_sources = await input_control.list_inputs()
                    logger.debug(f"list_inputs() returned: {type(raw_sources)} {raw_sources}")
                except Exception as input_error:
                    logger.error(f"Exception in list_inputs(): {str(input_error)}")
                    raw_sources = None
            
            # If input_control failed or isn't available, try source_control
            if raw_sources is None and self.source_control:
                logger.debug("Trying source_control to get input sources")
                try:
                    # Cast to Any to avoid type checking issues
                    source_control = cast(Any, self.source_control)
                    
                    # Try list_sources method if it exists
                    if hasattr(source_control, "list_sources") and callable(getattr(source_control, "list_sources")):
                        raw_sources = await source_control.list_sources()
                        logger.debug(f"source_control.list_sources() returned: {type(raw_sources)} {raw_sources}")
                except Exception as source_error:
                    logger.error(f"Exception in source_control.list_sources(): {str(source_error)}")
                    raw_sources = None
            
            # Process the raw sources to get the actual input list
            sources = []
            if raw_sources:
                # Extract the actual input list, handling different response formats
                if isinstance(raw_sources, dict):
                    # Handle response with nested 'devices' key
                    if "devices" in raw_sources and isinstance(raw_sources["devices"], list):
                        logger.debug("Found 'devices' list in response")
                        sources = raw_sources["devices"]
                    # Handle response with nested 'inputs' key
                    elif "inputs" in raw_sources and isinstance(raw_sources["inputs"], list):
                        logger.debug("Found 'inputs' list in response")
                        sources = raw_sources["inputs"]
                    # Special case for other formats - object itself might be an input
                    elif "id" in raw_sources or "label" in raw_sources:
                        logger.debug("Response itself appears to be a single input")
                        sources = [raw_sources]
                    else:
                        # Last resort - it might be a dict of inputs
                        logger.debug("Treating response keys as potential inputs list")
                        # Filter out common non-input keys
                        non_input_keys = ["returnValue", "status", "message", "error"]
                        sources = []
                        for key, value in raw_sources.items():
                            if key not in non_input_keys:
                                # If value is a dict, it might be the actual input
                                if isinstance(value, dict) and ("id" in value or "label" in value):
                                    sources.append(value)
                                # Otherwise, use the key/value as basic input info
                                else:
                                    sources.append({"id": key, "label": str(value)})
                elif isinstance(raw_sources, list):
                    # Already a list, use it directly
                    sources = raw_sources
                else:
                    # Single item (string or other type)
                    sources = [raw_sources]
                
                # Make sure we're not using keys from a response object as inputs
                # Check if the first items look like API response keys
                if len(sources) > 0 and isinstance(sources, list):
                    common_api_keys = ["returnValue", "devices", "inputs", "status", "message"]
                    if all(item in common_api_keys for item in sources[:2]):
                        logger.warning("Sources list appears to be API response keys, not actual inputs")
                        sources = []
            
            if sources:
                # Process and standardize each source
                processed_sources = []
                source_list = []  # For logging only
                
                # Debug entire sources structure before processing
                logger.debug(f"Raw source data structure: {type(sources)}")
                if isinstance(sources, list) and len(sources) > 0:
                    logger.debug(f"First source item type: {type(sources[0])}")
                
                for source in sources:
                    processed_source = self._process_input_source(source)
                    if processed_source:
                        processed_sources.append(source)  # Keep original source objects in cache
                        source_list.append(processed_source)  # Simplified version for logging
                
                if processed_sources:
                    self._cached_input_sources = processed_sources
                    logger.info(f"Input sources cache refreshed: {len(processed_sources)} sources available")
                    logger.debug(f"Processed input sources: {json.dumps(source_list, indent=2, ensure_ascii=False)}")
                    return True
                
            logger.warning("Failed to get input sources list from TV - all methods returned None or invalid format")
            return False
                
        except Exception as e:
            logger.error(f"Error refreshing input sources cache: {str(e)}")
            return False
            
    async def setup(self) -> bool:
        """Initialize the device and establish connection to TV.
        
        This method is called during device initialization to set up the LG TV device.
        It configures the connection parameters, attempts an initial connection,
        and initializes the device state.
        
        Returns:
            True if setup completed successfully (even if connection failed), 
            False on critical setup error
        """
        try:
            # Configure connection parameters from configuration
            logger.info(f"Setting up LG TV: {self.device_name}")
            
            # Use host from configuration directly
            self.state.ip_address = self.tv_config.ip_address
            self.state.mac_address = self.tv_config.mac_address
            
            # Initialize client key for WebOS 
            self.client_key = self.tv_config.client_key
            
            # For secure connections, check certificate exists
            if self.tv_config.secure and self.tv_config.cert_file:
                if not os.path.exists(self.tv_config.cert_file):
                    logger.warning(f"Certificate file not found: {self.tv_config.cert_file}")
            
            # Attempt initial connection
            connection_success = await self.connect()
            
            if connection_success:
                logger.info(f"Successfully connected to LG TV {self.device_name}")
                # Explicitly ensure we update the volume state
                await self._update_volume_state()
            else:
                logger.warning(f"Could not connect to LG TV {self.device_name}. Will try again later.")
                
            # Update power state based on connection result
            self.state.power = "off" if not connection_success else "on"
            
            # Base device is already initialized, no need to recreate the full state object
            
            return True  # Setup completed even if connection failed
            
        except Exception as e:
            logger.error(f"Error setting up LG TV device {self.device_name}: {str(e)}")
            self.set_error(str(e))
            return False
    
    async def connect(self) -> bool:
        """Establish a connection to the TV.
        
        This method can be called during setup or anytime a reconnection is needed.
        It attempts to connect to the TV using the configured parameters, initializes
        control interfaces, and updates the device state.
        
        Returns:
            True if connection was successful, False otherwise
        """
        try:
            logger.info(f"Connecting to LG TV {self.device_name} at {self.state.ip_address}")
            
            # Update state to indicate connection attempt
            self.state.connected = False
            
            # Attempt connection to the TV
            connection_result = await self._connect_to_tv()
            
            if connection_result:
                logger.info(f"Successfully connected to TV {self.get_name()}")
                self.state.connected = True
                self.clear_error()
                
                # Initialize control interfaces after successful connection
                await self._initialize_control_interfaces()
                
                # Update TV state after successful connection
                await self._update_tv_state()
            else:
                logger.error(f"Failed to connect to TV {self.get_name()}")
                self.state.connected = False
                if not self.state.error:
                    self.set_error("Failed to connect to TV")
                    
            return connection_result
        except Exception as e:
            logger.error(f"Unexpected error connecting to TV {self.get_name()}: {str(e)}")
            self.state.connected = False
            self.set_error(str(e))
            return False
    
    async def shutdown(self) -> bool:
        """Clean up resources and disconnect from the TV.
        
        This method is called when the device is being shut down.
        It ensures all resources are properly released and connection is closed.
        
        Returns:
            True if shutdown completed successfully, False on error
        """
        try:
            logger.info(f"Shutting down LG TV device: {self.device_name}")
            
            # Update state to indicate shutdown
            self.state.connected = False
            
            # Disconnect from TV
            if self.client:
                try:
                    # WebOSTV.close() handles closing all connections including input
                    await self.client.close()
                    logger.info(f"Disconnected from TV {self.get_name()}")
                except Exception as close_error:
                    logger.warning(f"Error while closing connection: {str(close_error)}")
                
                # Clear client reference
                self.client = None
                
                # Clear cached data
                self._cached_apps = []
                self._cached_input_sources = []
            
            # Set final state for reporting purposes
            self.state.power = "unknown"  # Power state is unknown after disconnection
            
            return True
        except Exception as e:
            logger.error(f"Error during device shutdown: {str(e)}")
            self.set_error(f"Shutdown error: {str(e)}")
            return False
    
    async def _connect_to_tv(self) -> bool:
        """Connect to the TV using the configured parameters.
        
        This is an internal method that handles the WebOS connection logic.
        It will attempt to connect using the provided client key. If the connection
        fails and a MAC address is available, it will try to wake the TV using
        Wake-on-LAN and attempt the connection again.
        """
        try:
            # Create a WebOSTV client
            self.client = self._create_webos_tv()
            if not self.client:
                return False
                
            # First connection attempt
            try:
                ip = self.state.ip_address
                logger.info(f"Attempting to connect to TV at {ip}...")
                
                # The WebOSTV connect method handles both connection and registration
                await self.client.connect()
                
                # After successful connection, store the client key
                if self.client.client_key and self.client.client_key != self.client_key:
                    self.client_key = self.client.client_key
                    logger.info(f"Obtained new client key for future use: {self.client_key}")
                
                logger.info(f"Successfully connected to TV at {ip}")
                return True
                
            except ssl.SSLError as ssl_error:
                # Handle SSL errors specially
                return await self._handle_ssl_error(ssl_error)
                
            except Exception as conn_error:
                # Handle connection errors
                return await self._handle_connection_error(conn_error)
                
        except Exception as e:
            logger.error(f"Error in _connect_to_tv: {str(e)}")
            self.set_error(str(e))
            return False
            
    async def _handle_ssl_error(self, ssl_error: ssl.SSLError) -> bool:
        """Handle SSL errors during connection.
        
        Args:
            ssl_error: The SSL error that occurred
            
        Returns:
            True if fallback connection succeeded, False otherwise
        """
        logger.error(f"SSL error during connection: {str(ssl_error)}")
        self.set_error(f"SSL connection error: {str(ssl_error)}")
        
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
            self.client = self._create_webos_tv(secure=False)
            if not self.client:
                return False
                
            # Connect with the non-secure client - this handles both connection and registration
            await self.client.connect()
            
            # After successful connection, store the client key if it was created or updated
            if self.client.client_key and self.client.client_key != self.client_key:
                self.client_key = self.client.client_key
                logger.info(f"Obtained new client key from insecure connection: {self.client_key}")
            
            logger.warning("Connected with insecure fallback (without SSL)")
            self.set_error("Connected with insecure fallback. Consider extracting TV certificate.")
            return True
                
        except Exception as fallback_error:
            logger.error(f"Fallback connection failed: {str(fallback_error)}")
            self.set_error(f"SSL connection failed, fallback also failed: {str(fallback_error)}")
            return False
            
    async def _handle_connection_error(self, conn_error: Exception) -> bool:
        """Handle general connection errors, potentially using WoL.
        
        Args:
            conn_error: The connection error that occurred
            
        Returns:
            True if connection was established or recovered, False otherwise
        """
        logger.error(f"Connection error: {str(conn_error)}")
        self.set_error(f"Connection error: {str(conn_error)}")
        
        # If we have a MAC address and the error suggests the TV is off, try Wake-on-LAN
        mac_address = self.state.mac_address
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
                    self.client = self._create_webos_tv()
                    if not self.client:
                        return False
                        
                    # Connect to the TV - WebOSTV handles both connection and registration
                    await self.client.connect()
                    
                    # After successful connection, store the client key if it was created or updated
                    if self.client.client_key and self.client.client_key != self.client_key:
                        self.client_key = self.client.client_key
                        logger.info(f"Obtained new client key after WoL: {self.client_key}")
                    
                    logger.info("Successfully connected after Wake-on-LAN")
                    return True
                        
                except Exception as wol_conn_error:
                    logger.error(f"Failed to connect after Wake-on-LAN: {str(wol_conn_error)}")
        
        return False
    
    async def _update_tv_state(self) -> bool:
        """Update the TV state information.
        
        Retrieves current volume, mute state, current app, and input source
        from the TV.
        
        Returns:
            True if at least some state information was updated, False otherwise
        """
        if not self.client or not self.state.connected:
            logger.debug("Cannot update TV state: Not connected")
            return False
            
        # Track if any updates happened
        update_success = False
        
        # Get volume info
        volume_updated = await self._update_volume_state()
        
        # Get current app
        app_updated = await self._update_current_app()
        
        # Get input source
        input_updated = await self._update_input_source()
        
        # Consider success if any of the updates worked
        update_success = volume_updated or app_updated or input_updated
        
        if not update_success:
            logger.debug("No TV state information could be updated")
        
        return update_success
        
    async def _update_volume_state(self) -> bool:
        """Update volume and mute state information.
        
        Returns:
            True if update was successful, False otherwise
        """
        from typing import cast, Any
        
        if not self.media:
            return False
            
        try:
            # Cast to Any to avoid type checking issues
            media_control = cast(Any, self.media)
            volume_info = await media_control.get_volume()
            if volume_info:
                # Use a default value of 0 only if nothing is returned from the TV
                self.state.volume = volume_info.get("volume", 0)
                self.state.mute = volume_info.get("muted", False)
                logger.debug(f"Updated volume state: volume={self.state.volume}, mute={self.state.mute}")
                return True
            logger.debug("Could not get volume info: empty response")
            return False
        except Exception as e:
            logger.debug(f"Could not get volume info: {str(e)}")
            return False
            
    async def _update_current_app(self) -> bool:
        """Update current app information using ApplicationControl.
        
        Returns:
            True if update was successful, False otherwise
        """
        if not self.app:
            return False
        
        try:
            # Use ApplicationControl's foreground_app method
            if self.app:
                foreground_app = await self.app.foreground_app()
                if foreground_app and isinstance(foreground_app, dict):
                    self.state.current_app = foreground_app.get("appId")
                    return True
            return False
        except Exception as e:
            logger.debug(f"Could not get current app info: {str(e)}")
            return False
            
    async def _update_input_source(self) -> bool:
        """Update input source information using InputControl.
        
        Returns:
            True if update was successful, False otherwise
        """
        if not self.input_control:
            return False
        
        try:
            # Use InputControl's get_input method directly
            input_info = await self.input_control.get_input()
            if input_info and "inputId" in input_info:
                self.state.input_source = input_info.get("inputId")
                return True
            return False
        except Exception as e:
            logger.debug(f"Could not get input source info: {str(e)}")
            return False
    
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
            
    async def handle_power_on(
        self, 
        cmd_config: StandardCommandConfig, 
        params: Dict[str, Any]
    ) -> CommandResult:
        """Handle power on action.
        
        Args:
            cmd_config: Command configuration
            params: Dictionary containing optional parameters
            
        Returns:
            CommandResult: Result of the command execution
        """
        success = await self.power_on()
        return self.create_command_result(
            success=success,
            message="TV powered on successfully" if success else None,
            error="Failed to power on TV" if not success else None
        )
        
    async def power_on(self) -> bool:
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
            if self.system and self.client and self.state.connected:
                try:
                    logger.info("Attempting to power on via WebOS API with monitoring...")
                    result = await self._execute_with_monitoring(
                        self.system, 
                        "power_on_with_monitoring", 
                        timeout=20.0
                    )
                    
                    if result.get("success", False):
                        self.state.power = "on"
                        self.state.last_command = LastCommand(
                            action="power_on",
                            source="api",
                            timestamp=datetime.now(),
                            params={"method": "webos_api"}
                        )
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
                
                logger.debug("Reconnecting to TV after power on")
                # Connect to re-initialize all control interfaces
                await self.connect()
            else:
                self.state.last_command = LastCommand(
                    action="power_on",
                    source="api",
                    timestamp=datetime.now(),
                    params={"status": "failed"}
                )
                
            return success
        except Exception as e:
            logger.error(f"Error powering on TV: {str(e)}")
            self.state.last_command = LastCommand(
                action="power_on",
                source="api",
                timestamp=datetime.now(),
                params={"error": str(e)}
            )
            return False
            
    async def _power_on_with_wol(self) -> bool:
        """Power on the TV using Wake-on-LAN.
        
        This is used by the power_on method when the WebOS API method fails
        or there is no active connection.
        
        Returns:
            True if WoL was sent successfully, False otherwise
        """
        mac_address = self.state.mac_address
        if not mac_address:
            logger.warning("Cannot use Wake-on-LAN: No MAC address configured for TV")
            return False
            
        logger.info(f"Attempting to power on via Wake-on-LAN to MAC: {mac_address}")
        # Use the send_wol_packet method from BaseDevice
        wol_success = await self.send_wol_packet(mac_address, self.broadcast_ip)
        if wol_success:
            logger.info("Wake-on-LAN packet sent successfully")
            # We can't be certain the TV will power on, but we've done our part
            # Assume it worked for state tracking purposes
            self.state.power = "on"
            
            # Use LastCommand object instead of string
            self.state.last_command = LastCommand(
                action="power_on",
                source="wol",
                timestamp=datetime.now(),
                params={"method": "wol", "mac_address": mac_address}
            )
            
            return True
        else:
            logger.error("Failed to send Wake-on-LAN packet")
            return False
            
    async def handle_power_off(
        self, 
        cmd_config: StandardCommandConfig, 
        params: Dict[str, Any]
    ) -> CommandResult:
        """Handle power off action.
        
        Args:
            cmd_config: Command configuration
            params: Dictionary containing optional parameters
            
        Returns:
            CommandResult: Result of the command execution
        """
        success = await self.power_off()
        return self.create_command_result(
            success=success,
            message="TV powered off successfully" if success else None,
            error="Failed to power off TV" if not success else None
        )
    
    async def handle_menu(
        self, 
        cmd_config: StandardCommandConfig, 
        params: Dict[str, Any]
    ) -> CommandResult:
        """Handle menu button action.
        
        Args:
            cmd_config: Command configuration
            params: Dictionary containing optional parameters (not used for menu)
            
        Returns:
            CommandResult: Result of the command execution
        """
        return await self._execute_input_command("menu", "menu")
    
    async def handle_volume_up(
        self, 
        cmd_config: StandardCommandConfig, 
        params: Dict[str, Any]
    ) -> CommandResult:
        """Handle volume up action.
        
        Args:
            cmd_config: Command configuration
            params: Dictionary containing optional parameters
            
        Returns:
            CommandResult: Result of the command execution
        """
        return await self._execute_media_command(
            action_name="volume_up",
            media_method_name="volume_up",
            state_key_to_update="volume",
            update_volume_after=True
        )
        
    async def handle_volume_down(
        self, 
        cmd_config: StandardCommandConfig, 
        params: Dict[str, Any]
    ) -> CommandResult:
        """Handle volume down action.
        
        Args:
            cmd_config: Command configuration
            params: Dictionary containing optional parameters
            
        Returns:
            CommandResult: Result of the command execution
        """
        return await self._execute_media_command(
            action_name="volume_down",
            media_method_name="volume_down",
            state_key_to_update="volume",
            update_volume_after=True
        )
        
    async def handle_mute(
        self, 
        cmd_config: StandardCommandConfig, 
        params: Dict[str, Any]
    ) -> CommandResult:
        """Handle mute toggle action.
        
        Args:
            cmd_config: Command configuration
            params: Dictionary containing optional parameters
            
        Returns:
            CommandResult: Result of the command execution
        """
        return await self._execute_media_command(
            action_name="mute",
            media_method_name="set_mute",
            state_key_to_update="mute",
            requires_state=True
        )

    def _get_app_info(self, app_obj: Any, fallback_name: str = "") -> Tuple[Optional[str], str]:
        """Extract app ID and title from an app object.
        
        Args:
            app_obj: The app object (either Application object or dictionary)
            fallback_name: Fallback name to use if title cannot be determined
            
        Returns:
            Tuple of (app_id, app_title) - app_id may be None if not found
        """
        app_id = None
        app_title = fallback_name
        
        try:
            # First, check if the app object has a data attribute (asyncwebostv.model.Application)
            if hasattr(app_obj, "data") and isinstance(app_obj.data, dict):
                # Application objects store properties in the data dictionary
                app_id = app_obj.data.get("id")
                app_title = app_obj.data.get("title", fallback_name)
                
                # If title is not found, try other common keys
                if not app_title or app_title == fallback_name:
                    app_title = app_obj.data.get("name", app_obj.data.get("label", fallback_name))
            
            # Dictionary-style access for direct dictionaries
            elif isinstance(app_obj, dict):
                app_id = app_obj.get("id")
                app_title = app_obj.get("title", fallback_name)
                
                # If title is not found, try other common keys
                if not app_title or app_title == fallback_name:
                    app_title = app_obj.get("name", app_obj.get("label", fallback_name))
            
            # Direct attribute access (legacy approach)
            elif hasattr(app_obj, "id"):
                app_id = app_obj.id
                # Try various possible title attribute names
                if hasattr(app_obj, "title"):
                    app_title = app_obj.title
                elif hasattr(app_obj, "name"):
                    app_title = app_obj.name
                elif hasattr(app_obj, "label"):
                    app_title = app_obj.label
            
            # Convert None to empty string for title to ensure we always have a string
            if app_title is None:
                app_title = fallback_name
                
        except Exception as e:
            logger.debug(f"Error extracting app info: {str(e)}")
            
        return app_id, app_title

    async def handle_launch_app(
        self, 
        cmd_config: StandardCommandConfig, 
        params: Dict[str, Any]
    ) -> CommandResult:
        """Handle launching an app on the TV.
        
        Args:
            cmd_config: Command configuration
            params: Dictionary containing either app_id or app_name parameter
            
        Returns:
            CommandResult: Result of the command execution
        """
        # Get app ID or name from params - support both app_id and app_name for compatibility
        app_identifier = None
        
        # Check for app_name parameter first (preferred)
        if params and "app_name" in params:
            app_identifier = params["app_name"]
        # Fall back to app_id for backward compatibility
        elif params and "app_id" in params:
            app_identifier = params["app_id"]
        
        if not app_identifier:
            error_msg = "Missing required parameter: at least one of 'app_name' or 'app_id' must be provided"
            logger.error(error_msg)
            return self.create_command_result(success=False, error=error_msg)
        
        try:
            if not self.app or not self.client or not self.state.connected:
                error_msg = f"Cannot launch app {app_identifier}: Not connected to TV"
                logger.error(error_msg)
                return self.create_command_result(success=False, error=error_msg)
            
            # Get available apps if not cached
            if not self._cached_apps:
                await self._refresh_app_cache()
            
            # Find the app by name or ID
            app_to_launch = self._find_app_by_name_or_id(self._cached_apps, app_identifier)
            
            if not app_to_launch:
                error_msg = f"App '{app_identifier}' not found on TV"
                logger.error(error_msg)
                return self.create_command_result(success=False, error=error_msg)
            
            # Get app ID and title
            actual_app_id, app_title = self._get_app_info(app_to_launch, app_identifier)
            
            if not actual_app_id:
                error_msg = f"Could not determine app ID for '{app_identifier}'"
                logger.error(error_msg)
                return self.create_command_result(success=False, error=error_msg)
            
            logger.info(f"Launching app '{app_title}' (ID: {actual_app_id})")
            
            # Launch the app
            if self.app:
                result = await self.app.launch(actual_app_id)
                
                # Add detailed logging of the result structure
                logger.debug(f"Launch app result type: {type(result)}, value: {result}")
                if isinstance(result, dict):
                    logger.debug(f"Result keys: {result.keys()}")
                    if "returnValue" in result:
                        logger.debug(f"returnValue: {result['returnValue']}")
            
            # WebOS API responses can vary:
            # 1. {'returnValue': True} - Direct response
            # 2. {'payload': {'returnValue': True}} - Nested response
            # 3. Empty dict but operation succeeded
            success = False
            
            if isinstance(result, dict):
                # Check for direct returnValue
                if "returnValue" in result and result["returnValue"] == True:
                    success = True
                # Check for nested returnValue in payload
                elif "payload" in result and isinstance(result["payload"], dict):
                    if "returnValue" in result["payload"] and result["payload"]["returnValue"] == True:
                        success = True
                # Empty dict with no error could also be a success
                elif not result:
                    # If result is empty and we received no error, assume success
                    # since the WebOS API sometimes returns empty responses for successful operations
                    success = True
                    logger.debug("Empty result dict received, assuming success")
            
            if success:
                logger.info(f"Successfully launched app '{app_title}'")
                # Update state
                await self._update_current_app()
                await self._update_last_command("launch_app", params, "api")
                return self.create_command_result(
                    success=True, 
                    message=f"Successfully launched app '{app_title}'"
                )
            
            error_msg = f"Failed to launch app: {result}"
            logger.error(error_msg)
            return self.create_command_result(success=False, error=error_msg)
            
        except Exception as e:
            error_msg = f"Error launching app {app_identifier}: {str(e)}"
            logger.error(error_msg)
            return self.create_command_result(success=False, error=error_msg)

    def _find_app_by_name_or_id(self, apps: List[Any], app_name: str) -> Optional[Any]:
        """Find an app by name or ID from a list of apps.
        
        Args:
            apps: List of app objects from the TV (either Application objects or dictionaries)
            app_name: The name or ID to search for
            
        Returns:
            The found app object or None if not found
        """
        if not apps:
            logger.debug("No apps available to search")
            return None

        # For improved debugging, log number of apps available
        logger.debug(f"Searching for app '{app_name}' among {len(apps)} available apps")
            
        for app in apps:
            try:
                # Use _get_app_info to extract app ID and title consistently
                app_id, app_title = self._get_app_info(app, "")
                
                # Match by ID (exact) or title (case-insensitive contains)
                if app_id and app_name == app_id:
                    logger.debug(f"Found app by exact ID match: {app_id} - {app_title}")
                    return app
                elif app_title and app_name.lower() in app_title.lower():
                    logger.debug(f"Found app by name match: {app_id} - {app_title}")
                    return app
                
            except Exception as e:
                # Log any errors but continue checking other apps
                logger.debug(f"Error matching app: {str(e)}")
                continue
                
        # If we got this far, no match was found
        logger.debug(f"No matching app found for '{app_name}'")
        
        # For diagnostic purposes, log some app names to help the user
        try:
            sample_size = min(5, len(apps))
            if sample_size > 0:
                sample_apps = []
                for i in range(sample_size):
                    app_id, app_title = self._get_app_info(apps[i], "Unknown")
                    sample_apps.append(f"{app_title} (ID: {app_id})")
                    
                logger.debug(f"Sample of available apps: {', '.join(sample_apps)}")
        except Exception as e:
            logger.debug(f"Error creating app sample: {str(e)}")
            
        return None
        
    async def _get_available_apps_internal(self) -> List[Dict[str, Any]]:
        """Internal method to get available apps from the TV.
        
        Returns:
            List of app dictionaries or empty list if retrieval fails
        """
        # If we have a cached list of apps, return it
        if self._cached_apps:
            return self._cached_apps
            
        # Otherwise try to refresh the cache
        if await self._refresh_app_cache():
            return self._cached_apps
        
        # If refresh failed, return empty list
        return []
            
    async def get_available_apps(self) -> List[Dict[str, Any]]:
        """Get a list of available apps.
        
        Returns:
            List of app dictionaries from the TV
        """
        return await self._get_available_apps_internal()
    
    # Handler methods for cursor control
    async def handle_move_cursor(
        self, 
        cmd_config: StandardCommandConfig, 
        params: Dict[str, Any]
    ) -> CommandResult:
        """Handle move cursor action.
        
        Moves the cursor to an absolute position on the screen, using percentage values (0-100).
        
        Args:
            cmd_config: Command configuration
            params: Dictionary containing x and y coordinates (0-100)
            
        Returns:
            CommandResult: Result of the command execution
        """
        # Validate parameters
        if not params or "x" not in params or "y" not in params:
            error_msg = "Missing required parameters: 'x' and 'y' are required"
            logger.error(error_msg)
            return self.create_command_result(success=False, error=error_msg)
        
        try:
            x = int(params["x"])
            y = int(params["y"])
        except (ValueError, TypeError):
            error_msg = f"Invalid coordinates: x={params.get('x')}, y={params.get('y')}"
            logger.error(error_msg)
            return self.create_command_result(success=False, error=error_msg)
        
        return await self._execute_pointer_command(
            action_name="move_cursor",
            required_params=True,
            use_ws_send=True,
            params={"x": x, "y": y}
        )

    async def handle_move_cursor_relative(
        self, 
        cmd_config: StandardCommandConfig, 
        params: Dict[str, Any]
    ) -> CommandResult:
        """Handle move cursor relative action.
        
        Moves the cursor by a relative amount in x and y directions (-50 to 50).
        
        Args:
            cmd_config: Command configuration
            params: Dictionary containing dx and dy displacement values (-50 to 50)
            
        Returns:
            CommandResult: Result of the command execution
        """
        # Validate parameters
        if not params or "dx" not in params or "dy" not in params:
            error_msg = "Missing required parameters: 'dx' and 'dy' are required"
            logger.error(error_msg)
            return self.create_command_result(success=False, error=error_msg)
        
        try:
            dx = int(params["dx"])
            dy = int(params["dy"])
        except (ValueError, TypeError):
            error_msg = f"Invalid displacement: dx={params.get('dx')}, dy={params.get('dy')}"
            logger.error(error_msg)
            return self.create_command_result(success=False, error=error_msg)
        
        return await self._execute_pointer_command(
            action_name="move_cursor_relative",
            required_params=True,
            use_ws_send=False,
            params={"dx": dx, "dy": dy}
        )

    async def handle_click(
        self, 
        cmd_config: StandardCommandConfig, 
        params: Dict[str, Any]
    ) -> CommandResult:
        """Handle click action at current cursor position.
        
        Args:
            cmd_config: Command configuration
            params: Dictionary containing optional parameters
            
        Returns:
            CommandResult: Result of the command execution
        """
        return await self._execute_pointer_command(
            action_name="click",
            required_params=False,
            use_ws_send=True,
            params=params or {}
        )

    # Action handlers for base class handle_message to use

    async def handle_home(
        self, 
        cmd_config: StandardCommandConfig, 
        params: Dict[str, Any]
    ) -> CommandResult:
        """Handle home button action.
        
        Args:
            cmd_config: Command configuration
            params: Dictionary containing optional parameters
            
        Returns:
            CommandResult: Result of the command execution
        """
        return await self._execute_input_command("home", "home")
    
    async def handle_back(
        self, 
        cmd_config: StandardCommandConfig, 
        params: Dict[str, Any]
    ) -> CommandResult:
        """Handle back button action.
        
        Args:
            cmd_config: Command configuration
            params: Dictionary containing optional parameters
            
        Returns:
            CommandResult: Result of the command execution
        """
        return await self._execute_input_command("back", "back")
    
    async def handle_up(
        self, 
        cmd_config: StandardCommandConfig, 
        params: Dict[str, Any]
    ) -> CommandResult:
        """Handle up button action.
        
        Args:
            cmd_config: Command configuration
            params: Dictionary containing optional parameters
            
        Returns:
            CommandResult: Result of the command execution
        """
        return await self._execute_input_command("up", "up")
    
    async def handle_down(
        self, 
        cmd_config: StandardCommandConfig, 
        params: Dict[str, Any]
    ) -> CommandResult:
        """Handle down button action.
        
        Args:
            cmd_config: Command configuration
            params: Dictionary containing optional parameters
            
        Returns:
            CommandResult: Result of the command execution
        """
        return await self._execute_input_command("down", "down")
    
    async def handle_left(
        self, 
        cmd_config: StandardCommandConfig, 
        params: Dict[str, Any]
    ) -> CommandResult:
        """Handle left button action.
        
        Args:
            cmd_config: Command configuration
            params: Dictionary containing optional parameters
            
        Returns:
            CommandResult: Result of the command execution
        """
        return await self._execute_input_command("left", "left")
    
    async def handle_right(
        self, 
        cmd_config: StandardCommandConfig, 
        params: Dict[str, Any]
    ) -> CommandResult:
        """Handle right button action.
        
        Args:
            cmd_config: Command configuration
            params: Dictionary containing optional parameters
            
        Returns:
            CommandResult: Result of the command execution
        """
        return await self._execute_input_command("right", "right")
    
    async def handle_enter(
        self, 
        cmd_config: StandardCommandConfig, 
        params: Dict[str, Any]
    ) -> CommandResult:
        """Handle enter/OK button action.
        
        Args:
            cmd_config: Command configuration
            params: Dictionary containing optional parameters
            
        Returns:
            CommandResult: Result of the command execution
        """
        return await self._execute_input_command("enter", "enter")
    
    async def handle_exit(
        self, 
        cmd_config: StandardCommandConfig, 
        params: Dict[str, Any]
    ) -> CommandResult:
        """Handle exit button action.
        
        Args:
            cmd_config: Command configuration
            params: Dictionary containing optional parameters
            
        Returns:
            CommandResult: Result of the command execution
        """
        return await self._execute_input_command("exit", "exit")
    
    async def handle_set_volume(
        self, 
        cmd_config: StandardCommandConfig, 
        params: Dict[str, Any]
    ) -> CommandResult:
        """Handle set volume action.
        
        Args:
            cmd_config: Command configuration
            params: Dictionary containing level parameter for volume level
            
        Returns:
            CommandResult: Result of the command execution
        """
        # Extract volume level from params
        if not params or "level" not in params:
            error_msg = "Missing required 'level' parameter"
            logger.error(error_msg)
            return self.create_command_result(success=False, error=error_msg)
        
        try:
            level = int(params["level"])
        except (ValueError, TypeError):
            error_msg = f"Invalid volume level: {params.get('level')}"
            logger.error(error_msg)
            return self.create_command_result(success=False, error=error_msg)
        
        return await self._execute_media_command(
            action_name="set_volume",
            media_method_name="set_volume",
            state_key_to_update="volume",
            requires_level=True,
            params=params
        )
            
    async def handle_play(
        self, 
        cmd_config: StandardCommandConfig, 
        params: Dict[str, Any]
    ) -> CommandResult:
        """Handle play action.
        
        Args:
            cmd_config: Command configuration
            params: Dictionary containing optional parameters
            
        Returns:
            CommandResult: Result of the command execution
        """
        return await self._execute_media_command(
            action_name="play",
            media_method_name="play"
        )
        
    async def handle_pause(
        self, 
        cmd_config: StandardCommandConfig, 
        params: Dict[str, Any]
    ) -> CommandResult:
        """Handle pause action.
        
        Args:
            cmd_config: Command configuration
            params: Dictionary containing optional parameters
            
        Returns:
            CommandResult: Result of the command execution
        """
        return await self._execute_media_command(
            action_name="pause",
            media_method_name="pause"
        )
        
    async def handle_stop(
        self, 
        cmd_config: StandardCommandConfig, 
        params: Dict[str, Any]
    ) -> CommandResult:
        """Handle stop action.
        
        Args:
            cmd_config: Command configuration
            params: Dictionary containing optional parameters
            
        Returns:
            CommandResult: Result of the command execution
        """
        return await self._execute_media_command(
            action_name="stop",
            media_method_name="stop"
        )
        
    async def handle_rewind_forward(
        self, 
        cmd_config: StandardCommandConfig, 
        params: Dict[str, Any]
    ) -> CommandResult:
        """Handle fast forward action.
        
        Args:
            cmd_config: Command configuration
            params: Dictionary containing optional parameters
            
        Returns:
            CommandResult: Result of the command execution
        """
        return await self._execute_media_command(
            action_name="rewind_forward",
            media_method_name="fast_forward"
        )
        
    async def handle_rewind_backward(
        self, 
        cmd_config: StandardCommandConfig, 
        params: Dict[str, Any]
    ) -> CommandResult:
        """Handle rewind action.
        
        Args:
            cmd_config: Command configuration
            params: Dictionary containing optional parameters
            
        Returns:
            CommandResult: Result of the command execution
        """
        return await self._execute_media_command(
            action_name="rewind_backward",
            media_method_name="rewind"
        )
        
    async def handle_wake_on_lan(
        self, 
        cmd_config: StandardCommandConfig, 
        params: Dict[str, Any]
    ) -> CommandResult:
        """Handle wake on LAN action.
        
        Args:
            cmd_config: Command configuration
            params: Dictionary containing optional parameters
            
        Returns:
            CommandResult: Result of the command execution
        """
        success = await self.wake_on_lan()
        return self.create_command_result(
            success=success,
            message="Wake-on-LAN packet sent successfully" if success else None,
            error="Failed to send Wake-on-LAN packet" if not success else None
        )

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
            ip = self.state.ip_address
            if not ip:
                return False, "No IP address configured for TV"
            
            # Set default output file if not provided
            if not output_file:
                output_file = f"{ip}_cert.pem"
            
            # Create a temporary SecureWebOSTV client to extract the certificate
            # without attempting a connection
            secure_client = SecureWebOSTV(
                host=ip,
                port=3001,
                client_key=self.client_key,
                verify_ssl=False
            )
            
            # Use the client's get_certificate method
            cert_pem = await secure_client.get_certificate(save_path=output_file)
            
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
            ip = self.state.ip_address
            if not ip:
                return False, "No IP address configured for TV"
            
            # Create a temporary SecureWebOSTV client for verification
            secure_client = SecureWebOSTV(
                host=ip,
                port=3001,
                client_key=self.client_key,
                cert_file=cert_file,
                verify_ssl=True
            )
            
            # If we can extract a new certificate and compare, that would be ideal
            try:
                # Extract current certificate to temporary file
                temp_cert_file = f"{ip}_temp_cert.pem"
                await secure_client.get_certificate(save_path=temp_cert_file)
                
                # Import tools for comparison
                import hashlib
                import OpenSSL.crypto as crypto
                
                # Load the saved certificate
                with open(cert_file, 'rb') as f:
                    saved_cert_data = f.read()
                    saved_cert = crypto.load_certificate(crypto.FILETYPE_PEM, saved_cert_data)
                    saved_cert_bin = crypto.dump_certificate(crypto.FILETYPE_ASN1, saved_cert)
                    saved_fingerprint = hashlib.sha256(saved_cert_bin).hexdigest()
                
                # Load the current certificate
                with open(temp_cert_file, 'rb') as f:
                    current_cert_data = f.read()
                    current_cert = crypto.load_certificate(crypto.FILETYPE_PEM, current_cert_data)
                    current_cert_bin = crypto.dump_certificate(crypto.FILETYPE_ASN1, current_cert)
                    current_fingerprint = hashlib.sha256(current_cert_bin).hexdigest()
                
                # Remove temporary file
                try:
                    os.remove(temp_cert_file)
                except:
                    pass
                
                # Compare fingerprints
                if saved_fingerprint == current_fingerprint:
                    logger.info("Certificate verification successful: Certificate matches the one from the TV")
                    return True, "Certificate is valid and matches the TV"
                else:
                    logger.warning("Certificate verification failed: Certificate does not match the one from the TV")
                    return False, "Certificate does not match the one from the TV. Consider refreshing it."
                    
            except Exception as verify_err:
                logger.error(f"Failed to verify certificate: {str(verify_err)}")
                return False, f"Failed to verify certificate: {str(verify_err)}"
                
        except Exception as e:
            error_msg = f"Failed to verify certificate: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    async def handle_set_input(
        self, 
        cmd_config: StandardCommandConfig, 
        params: Dict[str, Any]
    ) -> CommandResult:
        """Handle setting input source.
        
        Args:
            cmd_config: Command configuration
            params: Dictionary containing input parameter for input source
            
        Returns:
            CommandResult: Result of the command execution
        """
        # Extract input source from params
        if not params or "input" not in params:
            error_msg = "Missing required 'input' parameter"
            logger.error(error_msg)
            return self.create_command_result(success=False, error=error_msg)
        
        input_source = params["input"]
        
        try:
            if not self.source_control or not self.client or not self.state.connected:
                error_msg = f"Cannot set input source to {input_source}: Not connected to TV"
                logger.error(error_msg)
                return self.create_command_result(success=False, error=error_msg)
            
            # Get available input sources if not cached
            if not self._cached_input_sources:
                await self._refresh_input_sources_cache()
            
            # Find the input source by name or ID
            input_to_set = self._find_input_by_name_or_id(self._cached_input_sources, input_source)
            
            if not input_to_set:
                error_msg = f"Input source '{input_source}' not found on TV"
                logger.error(error_msg)
                return self.create_command_result(success=False, error=error_msg)
            
            # Extract input ID and name based on the type of input_to_set
            if isinstance(input_to_set, dict):
                input_id = input_to_set.get("id")
                input_name = input_to_set.get("label", input_source)
            else:  # String type
                input_id = input_to_set
                input_name = input_to_set
            
            logger.info(f"Setting input source to '{input_name}' (ID: {input_id})")
            
            # Switch to the input source
            if self.source_control:
                result = await self.source_control.set_source_input(input_id)
                
                if result.get("returnValue", False):
                    # Update state
                    self.state.input_source = input_name
                    await self._update_last_command("set_input", params, "api")
                    return self.create_command_result(
                        success=True,
                        message=f"Input source set to '{input_name}' successfully"
                    )
                
                error_msg = f"Failed to set input source: {result}"
                logger.error(error_msg)
                return self.create_command_result(success=False, error=error_msg)
            else:
                error_msg = "Source control is not available"
                logger.error(error_msg)
                return self.create_command_result(success=False, error=error_msg)
        except Exception as e:
            error_msg = f"Error setting input source to {input_source}: {str(e)}"
            logger.error(error_msg)
            return self.create_command_result(success=False, error=error_msg)

    async def _get_available_inputs(self) -> List[Dict[str, Any]]:
        """Get available input sources from the TV.
        
        Returns:
            List of input source dictionaries or empty list on failure
        """
        # If we have a cached list of input sources, return it
        if self._cached_input_sources:
            return self._cached_input_sources
            
        # Otherwise try to refresh the cache
        if await self._refresh_input_sources_cache():
            return self._cached_input_sources
        
        # If refresh failed, return empty list
        return []
            
    def _find_input_by_name_or_id(self, sources: List[Union[Dict[str, Any], str]], input_source: str) -> Optional[Union[Dict[str, Any], str]]:
        """Find an input source by name or ID.
        
        Args:
            sources: List of input source dictionaries or strings from the TV
            input_source: The name or ID to search for
            
        Returns:
            The found input source (dict or string) or None if not found
        """
        for source in sources:
            processed = self._process_input_source(source)
            if processed and (input_source.lower() == processed["id"].lower() or input_source.lower() in processed["name"].lower()):
                return source
        return None
    
    async def _update_last_command(self, action: str, params: Optional[Dict[str, Any]] = None, source: str = "api") -> None:
        """Helper method to update the last_command state with proper typing.
        
        Args:
            action: The action that was executed
            params: Parameters used in the action
            source: Source of the command (e.g., "api", "wol")
        """
        try:
            self.state.last_command = LastCommand(
                action=action,
                source=source,
                timestamp=datetime.now(),
                params=params if params else {}
            )
        except Exception as e:
            # Log error but don't prevent the main action from completing
            logger.error(f"Error updating last_command state for action '{action}': {e}")

    async def _execute_media_command(
        self,
        action_name: str,
        media_method_name: str,
        state_key_to_update: Optional[str] = None,
        requires_level: bool = False,
        requires_state: bool = False,
        update_volume_after: bool = False,
        params: Optional[Dict[str, Any]] = None
    ) -> CommandResult:
        """Execute a media control command.
        
        Args:
            action_name: Name of the action (for logging and state updates)
            media_method_name: Name of the method to call on MediaControl
            state_key_to_update: Key in self.state to update with result
            requires_level: If True, needs a level parameter
            requires_state: If True, needs a state parameter
            update_volume_after: If True, update volume state after command
            params: Dictionary containing parameters for the command
            
        Returns:
            CommandResult: Result of the command execution
        """
        try:
            logger.info(f"Executing media command: {action_name}")
            
            if not self.media or not self.client or not self.state.connected:
                error_msg = f"Cannot execute media command {action_name}: Not connected to TV"
                logger.error(error_msg)
                return self.create_command_result(success=False, error=error_msg)
            
            # Default params to empty dict if None
            if params is None:
                params = {}
            
            # Get level from params if required
            level = None
            if requires_level:
                level = params.get("level")
                if level is None:
                    error_msg = f"{action_name} requires level parameter"
                    logger.error(error_msg)
                    return self.create_command_result(success=False, error=error_msg)
                try:
                    level = int(level)
                except ValueError:
                    error_msg = f"Invalid level value: {level}"
                    logger.error(error_msg)
                    return self.create_command_result(success=False, error=error_msg)
            
            # Get state from params if required
            state = None
            if requires_state:
                state = params.get("state")
                if state is None:
                    # Toggle state if not provided
                    if state_key_to_update == "mute":
                        if self.media:
                            current_status = await self.media.get_volume()
                            state = not current_status.get("muted", False)
                        else:
                            error_msg = f"{action_name} requires state parameter and media control is not available"
                            logger.error(error_msg)
                            return self.create_command_result(success=False, error=error_msg)
                    else:
                        error_msg = f"{action_name} requires state parameter"
                        logger.error(error_msg)
                        return self.create_command_result(success=False, error=error_msg)
            
            # Execute the appropriate method based on parameters
            media_control_method = getattr(self.media, media_method_name)
            if media_control_method:
                if requires_level:
                    result = await media_control_method(level)
                elif requires_state:
                    result = await media_control_method(state)
                else:
                    result = await media_control_method()
                
                # Add detailed debug logging to see the exact structure
                logger.debug(f"Raw result from {media_method_name}: {type(result)} {result}")
                
                # Check result
                # Handle the nested payload structure in the response
                success = False
                if isinstance(result, dict):
                    logger.debug(f"Result is dict with keys: {result.keys()}")
                    # Check for returnValue in the payload (most common case)
                    if "payload" in result and isinstance(result["payload"], dict):
                        logger.debug(f"Found payload with content: {result['payload']}")
                        # Treat empty dict as success (library validation already confirmed it)
                        if not result["payload"]:
                            success = True
                            logger.debug("Empty payload dict treated as success")
                        else:
                            success = result["payload"].get("returnValue", False)
                        logger.debug(f"Payload returnValue: {success}")
                    # Fallback to checking at the top level
                    else:
                        # Treat empty dict as success (library validation already confirmed it)
                        if not result:
                            success = True
                            logger.debug("Empty result dict treated as success")
                        else:
                            success = result.get("returnValue", False)
                        logger.debug(f"Top level returnValue: {success}")
                else:
                    logger.debug(f"Result is not a dict, it's a {type(result)}")
                
                logger.debug(f"Final success determination: {success}")
                
                if success:
                    # Update state if needed
                    if state_key_to_update:
                        if requires_level:
                            self.state.volume = level
                        elif requires_state:
                            self.state.mute = state
                        
                    # Update volume state if requested
                    if update_volume_after:
                        await self._update_volume_state()
                    
                    # Update last command in state
                    await self._update_last_command(action_name, params, "api")
                    
                    return self.create_command_result(
                        success=True,
                        message=f"{action_name} executed successfully"
                    )
                else:
                    error_msg = f"Command {action_name} failed: {result}"
                    logger.error(error_msg)
                    return self.create_command_result(
                        success=False,
                        error=error_msg
                    )
            else:
                error_msg = f"Media control method not found: {media_method_name}"
                logger.error(error_msg)
                return self.create_command_result(success=False, error=error_msg)
        except Exception as e:
            error_msg = f"Error executing media command {action_name}: {str(e)}"
            logger.error(error_msg)
            return self.create_command_result(success=False, error=error_msg)

    async def power_off(self) -> bool:
        """Power off the TV.
        
        Returns:
            True if power off was successful, False otherwise
        """
        try:
            logger.info(f"Powering off TV {self.get_name()}")
            
            # Use system power_off_with_monitoring method
            if self.system and self.client and self.state.connected:
                result = await self._execute_with_monitoring(
                    self.system, 
                    "power_off_with_monitoring", 
                    timeout=10.0
                )
                
                if result.get("success", False):
                    self.state.power = "off"
                    self.state.last_command = LastCommand(
                        action="power_off",
                        source="api",
                        timestamp=datetime.now()
                    )
                    return True
                else:
                    logger.warning(f"Power off failed: {result.get('error', 'Unknown error')}")
                    error_msg = result.get('error', 'Unknown error')
                    self.state.last_command = LastCommand(
                        action="power_off",
                        source="api",
                        timestamp=datetime.now(),
                        params={"error": error_msg}
                    )
                    return False
            else:
                logger.error("Cannot power off: Not connected to TV")
                self.state.last_command = LastCommand(
                    action="power_off",
                    source="api",
                    timestamp=datetime.now(),
                    params={"error": "Not connected to TV"}
                )
                return False
            
        except Exception as e:
            logger.error(f"Error powering off TV: {str(e)}")
            self.state.last_command = LastCommand(
                action="power_off",
                source="api",
                timestamp=datetime.now(),
                params={"error": str(e)}
            )
            return False

    async def _execute_input_command(self, action_name: str, button_method_name: str) -> CommandResult:
        """Execute an input button command using InputControl.
        
        This helper method provides a consistent implementation for all button commands
        that use InputControl methods.
        
        Args:
            action_name: The name of the action (for logging and state updates)
            button_method_name: The name of the method to call on InputControl
            
        Returns:
            CommandResult: Result of the command execution
        """
        try:
            logger.info(f"Sending {action_name.upper()} button command to TV {self.get_name()}")
            
            if not self.client or not self.input_control or not self.state.connected:
                error_msg = f"Cannot send {action_name.upper()} command: Not connected or input control not available"
                logger.error(error_msg)
                self.set_error(error_msg)
                return self.create_command_result(success=False, error=error_msg)
                
            # Check if the button method exists on InputControl
            if not hasattr(self.input_control, button_method_name) or not callable(getattr(self.input_control, button_method_name)):
                error_msg = f"Button method '{button_method_name}' not found on InputControl"
                logger.error(error_msg)
                self.set_error(error_msg)
                return self.create_command_result(success=False, error=error_msg)
                
            # Call the button method on InputControl
            method = getattr(self.input_control, button_method_name)
            result = await method()
            
            if result:
                await self._update_last_command(action=action_name, source="api")
                self.clear_error()  # Clear any previous errors on success
                return self.create_command_result(
                    success=True, 
                    message=f"{action_name.upper()} button command executed successfully"
                )
            else:
                error_msg = f"{action_name.upper()} button command failed"
                logger.warning(error_msg)
                self.set_error(error_msg)
                return self.create_command_result(success=False, error=error_msg)
                
        except Exception as e:
            error_msg = f"Error sending {action_name.upper()} button command: {str(e)}"
            logger.error(error_msg)
            self.set_error(error_msg)
            return self.create_command_result(success=False, error=error_msg)
    
    async def refresh_app_list(self) -> bool:
        """Public method to manually refresh the app list cache.
        
        Returns:
            True if refresh was successful, False otherwise
        """
        logger.info(f"Manually refreshing app list for TV {self.get_name()}")
        return await self._refresh_app_cache()
        
    async def handle_refresh_app_list(
        self, 
        cmd_config: StandardCommandConfig, 
        params: Dict[str, Any]
    ) -> CommandResult:
        """Handle refresh app list action.
        
        Args:
            cmd_config: Command configuration
            params: Dictionary containing optional parameters
            
        Returns:
            CommandResult: Result of the command execution
        """
        success = await self.refresh_app_list()
        return self.create_command_result(
            success=success,
            message="App list refreshed successfully" if success else None,
            error="Failed to refresh app list" if not success else None
        )
        
    async def handle_refresh_input_sources(
        self, 
        cmd_config: StandardCommandConfig, 
        params: Dict[str, Any]
    ) -> CommandResult:
        """Handle refresh input sources action.
        
        Args:
            cmd_config: Command configuration
            params: Dictionary containing optional parameters
            
        Returns:
            CommandResult: Result of the command execution
        """
        success = await self.refresh_input_sources()
        return self.create_command_result(
            success=success,
            message="Input sources refreshed successfully" if success else None,
            error="Failed to refresh input sources" if not success else None
        )
        
    async def wake_on_lan(self) -> bool:
        """Send a Wake-on-LAN packet to the TV using the configured MAC address.
        
        This method can be used independently of the power_on method when you
        specifically want to use WOL without trying other power-on methods.
        
        Returns:
            bool: True if the WOL packet was sent successfully, False otherwise
        """
        try:
            mac_address = self.state.mac_address
            if not mac_address:
                logger.error("Cannot use Wake-on-LAN: No MAC address configured for TV")
                self.state.last_command = LastCommand(
                    action="wake_on_lan",
                    source="api",
                    timestamp=datetime.now(),
                    params={"error": "No MAC address configured"}
                )
                return False
                
            logger.info(f"Sending Wake-on-LAN packet to TV {self.get_name()} (MAC: {mac_address})")
            
            # Use the send_wol_packet method from BaseDevice
            wol_success = await self.send_wol_packet(mac_address, self.broadcast_ip)
            
            if wol_success:
                logger.info("Wake-on-LAN packet sent successfully")
                self.state.last_command = LastCommand(
                    action="wake_on_lan",
                    source="api",
                    timestamp=datetime.now(),
                    params={"mac_address": mac_address}
                )
                # We can't know for sure if the TV will turn on,
                # but update the expected state for consistency
                self.state.power = "on"
                return True
            else:
                logger.error("Failed to send Wake-on-LAN packet")
                self.state.last_command = LastCommand(
                    action="wake_on_lan",
                    source="api",
                    timestamp=datetime.now(),
                    params={"error": "Failed to send packet"}
                )
                return False
                
        except Exception as e:
            logger.error(f"Error sending Wake-on-LAN packet: {str(e)}")
            self.state.last_command = LastCommand(
                action="wake_on_lan",
                source="api",
                timestamp=datetime.now(),
                params={"error": str(e)}
            )
            return False
    
    async def _execute_pointer_command(
        self,
        action_name: str,
        required_params: bool,
        use_ws_send: bool,
        params: Optional[Dict[str, Any]] = None
    ) -> CommandResult:
        """Execute a pointer control command.
        
        Args:
            action_name: Name of the action (for logging and state updates)
            required_params: Whether parameters are required (x,y or dx,dy)
            use_ws_send: Whether to use direct WebSocket send
            params: Dictionary containing parameters for the command
            
        Returns:
            CommandResult: Result of the command execution
        """
        try:
            logger.info(f"Executing pointer command: {action_name}")
            
            # Default params to empty dict if None
            params = params or {}
            
            if not self.client or not self.state.connected:
                error_msg = f"Cannot execute pointer command {action_name}: Not connected to TV"
                logger.error(error_msg)
                self.set_error(error_msg)
                return self.create_command_result(success=False, error=error_msg)
                
            # Execute the appropriate pointer command based on action name
            if action_name == "move_cursor":
                # Absolute cursor movement (x,y)
                x = params.get("x")
                y = params.get("y")
                
                logger.debug(f"Moving cursor to position: x={x}, y={y}")
                
                # Construct WebOS command payload
                payload = {
                    "type": "move",
                    "payload": {
                        "x": float(x) / 100.0,  # Convert from 0-100 to 0-1 scale
                        "y": float(y) / 100.0
                    }
                }
                
                # Send command directly via WebSocket
                result = await self.client.send_message("ssap://com.webos.service.pointer/move", payload)
                
            elif action_name == "move_cursor_relative":
                # Relative cursor movement (dx,dy)
                dx = params.get("dx")
                dy = params.get("dy")
                
                logger.debug(f"Moving cursor by relative amount: dx={dx}, dy={dy}")
                
                # Construct WebOS command payload
                payload = {
                    "type": "moveBy",
                    "payload": {
                        "dx": float(dx) / 10.0,  # Convert to appropriate scale
                        "dy": float(dy) / 10.0
                    }
                }
                
                # Send command directly via WebSocket
                result = await self.client.send_message("ssap://com.webos.service.pointer/move", payload)
                
            elif action_name == "click":
                logger.debug("Sending click at current cursor position")
                
                # Send click command
                result = await self.client.send_message("ssap://com.webos.service.pointer/click", {})
                
            else:
                error_msg = f"Unknown pointer command: {action_name}"
                logger.error(error_msg)
                self.set_error(error_msg)
                return self.create_command_result(success=False, error=error_msg)
            
            # Update last command
            await self._update_last_command(action_name, params, "api")
            
            # Check result
            if result and isinstance(result, dict) and result.get("returnValue", False):
                self.clear_error()  # Clear any previous errors on success
                return self.create_command_result(
                    success=True,
                    message=f"Pointer command {action_name} executed successfully"
                )
            else:
                error_msg = f"Pointer command {action_name} failed: {result}"
                logger.error(error_msg)
                self.set_error(error_msg)
                return self.create_command_result(success=False, error=error_msg)
                
        except Exception as e:
            error_msg = f"Error executing pointer command {action_name}: {str(e)}"
            logger.error(error_msg)
            self.set_error(error_msg)
            return self.create_command_result(success=False, error=error_msg)

    async def handle_get_available_apps(
        self, 
        cmd_config: StandardCommandConfig, 
        params: Dict[str, Any]
    ) -> CommandResult:
        """Handle retrieving non-system apps from the TV.
        
        Returns a list of non-system apps as pairs of app_id and app_name.
        System apps are identified by the systemApp property in the app data.
        
        Args:
            cmd_config: Command configuration
            params: Dictionary containing optional parameters
            
        Returns:
            CommandResult: Result of the command execution with a list of non-system apps
        """
        try:
            logger.info("Retrieving non-system apps from TV")
            
            if not self.app or not self.client or not self.state.connected:
                error_msg = "Cannot retrieve apps: Not connected to TV"
                logger.error(error_msg)
                return self.create_command_result(success=False, error=error_msg)
            
            # Get all available apps
            all_apps = await self._get_available_apps_internal()
            
            if not all_apps:
                logger.warning("No apps found on TV")
                return self.create_command_result(
                    success=True,
                    message="No apps found on TV",
                    data=[]
                )
            
            # Filter out system apps and extract id and name
            non_system_apps = []
            
            for app in all_apps:
                try:
                    # Check if the app is a system app
                    is_system_app = False
                    
                    # Check the systemApp property in different possible locations
                    if hasattr(app, "data") and isinstance(app.data, dict):
                        is_system_app = app.data.get("systemApp", False)
                    elif isinstance(app, dict):
                        is_system_app = app.get("systemApp", False)
                    elif hasattr(app, "systemApp"):
                        is_system_app = app.systemApp
                    
                    # Skip system apps
                    if is_system_app:
                        continue
                    
                    # Get app ID and name using the existing helper method
                    app_id, app_name = self._get_app_info(app, "Unknown")
                    
                    # Only include apps with valid IDs
                    if app_id:
                        non_system_apps.append({
                            "app_id": app_id,
                            "app_name": app_name
                        })
                    
                except Exception as app_error:
                    logger.debug(f"Error processing app: {str(app_error)}")
                    continue
            
            logger.info(f"Found {len(non_system_apps)} non-system apps")
            
            # Update last command
            await self._update_last_command("get_public_apps", {}, "api")
            
            return self.create_command_result(
                success=True,
                message=f"Retrieved {len(non_system_apps)} non-system apps",
                data=non_system_apps
            )
            
        except Exception as e:
            error_msg = f"Error retrieving non-system apps: {str(e)}"
            logger.error(error_msg)
            return self.create_command_result(success=False, error=error_msg)

    async def handle_get_available_inputs(
        self, 
        cmd_config: StandardCommandConfig, 
        params: Dict[str, Any]
    ) -> CommandResult:
        """Handle retrieving available input sources from the TV.
        
        Returns a list of available input sources as pairs of input_id and input_name.
        
        Args:
            cmd_config: Command configuration
            params: Dictionary containing optional parameters
            
        Returns:
            CommandResult: Result of the command execution with a list of available inputs
        """
        try:
            logger.info("Retrieving available input sources from TV")
            
            if not (self.input_control or self.source_control) or not self.client or not self.state.connected:
                error_msg = "Cannot retrieve input sources: Not connected to TV or missing required controls"
                logger.error(error_msg)
                return self.create_command_result(success=False, error=error_msg)
            
            # Force a refresh of the cache to ensure we have the latest data
            await self._refresh_input_sources_cache()
            
            # Get all available input sources using the existing method
            input_sources = await self._get_available_inputs()
            
            if not input_sources:
                logger.warning("No input sources found on TV")
                return self.create_command_result(
                    success=True,
                    message="No input sources found on TV",
                    data=[]
                )
            
            # Format the input sources as pairs of input_id and input_name
            formatted_inputs = []
            
            for input_source in input_sources:
                processed_source = self._process_input_source(input_source)
                if processed_source:
                    formatted_inputs.append({
                        "input_id": processed_source["id"],
                        "input_name": processed_source["name"]
                    })
            
            logger.info(f"Found {len(formatted_inputs)} input sources")
            
            # Update last command
            await self._update_last_command("get_available_inputs", {}, "api")
            
            # Check if we found any valid inputs
            if not formatted_inputs:
                return self.create_command_result(
                    success=True,
                    message="No valid input sources found after processing",
                    data=[]
                )
            
            return self.create_command_result(
                success=True,
                message=f"Retrieved {len(formatted_inputs)} input sources",
                data=formatted_inputs
            )
            
        except Exception as e:
            error_msg = f"Error retrieving input sources: {str(e)}"
            logger.error(error_msg)
            return self.create_command_result(success=False, error=error_msg)

    async def refresh_input_sources(self) -> bool:
        """Public method to manually refresh the input sources cache.
        
        Returns:
            True if refresh was successful, False otherwise
        """
        logger.info(f"Manually refreshing input sources for TV {self.get_name()}")
        return await self._refresh_input_sources_cache()





