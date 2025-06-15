import logging
import asyncio
from typing import Dict, Any, List, Optional, cast, Tuple
from datetime import datetime
from urllib.parse import urlparse
import xml.etree.ElementTree as ET
import requests
import socket
import time
import json

from openhomedevice.device import Device as OpenHomeDevice
from async_upnp_client.search import SsdpSearchListener

from devices.base_device import BaseDevice
from app.schemas import AuralicDeviceState, LastCommand, AuralicDeviceConfig, BaseCommandConfig
from app.mqtt_client import MQTTClient
from app.types import CommandResult, CommandResponse

logger = logging.getLogger(__name__)

# Note about Auralic devices:
# Auralic devices support two power states:
# 1. Sleep/Standby (≈7W) - Can be controlled via UPnP (SetStandby)
# 2. Deep Sleep/Power-off (≈0.3W) - Can ONLY be controlled via IR (physical power button long-press)
#
# This implementation uses a combination of UPnP/OpenHome control for regular functions
# and IR control via MQTT for true power on/off functionality. The IR control is 
# implemented through a Wirenboard IR blaster that can send the necessary signals.
#
# To use the IR control functionality, you must provide MQTT topics for power on/off
# in the configuration:
#
# auralic:
#   ir_power_on_topic: "wb-mqtt-bridge/wirenboard/ir_blaster/emit"    # Example topic
#   ir_power_off_topic: "wb-mqtt-bridge/wirenboard/ir_blaster/emit"   # Example topic 
#   device_boot_time: 15  # Time in seconds to wait for the device to boot
#
# Without these settings, the device can only be put into standby mode, not true power off.

class AuralicDevice(BaseDevice[AuralicDeviceState]):
    """
    Implementation of an Auralic device controlled through OpenHome UPnP with IR control for power.
    
    This class provides control for Auralic audio devices, supporting:
    - UPnP/OpenHome control for regular functions (volume, source, playback)
    - IR control via MQTT for true power on/off functionality
    - Automatic discovery of devices on the network
    - Robust handling of Auralic's dynamic port assignment
    - State tracking for both standby and deep sleep modes
    
    The implementation detects when a device is in deep sleep mode and uses IR commands
    through a Wirenboard IR blaster to power it on. Similarly, it can put the device into
    true power off state using IR commands.
    
    To use the IR control functionality, you must configure ir_power_on_topic and
    ir_power_off_topic in the configuration.
    """
    
    def __init__(self, config: AuralicDeviceConfig, mqtt_client: Optional[MQTTClient] = None) -> None:
        # Call the base class constructor first
        super().__init__(config, mqtt_client)
        
        # Initialize state with typed Pydantic model AFTER super().__init__
        self.state = AuralicDeviceState(
            device_id=config.device_id,
            device_name=config.device_name,
            ip_address=config.auralic.ip_address,
            # Initialize all remaining fields from the schema
            power="unknown",
            volume=0,
            mute=False,
            source=None,
            connected=False,
            track_title=None,
            track_artist=None,
            track_album=None,
            transport_state=None,
            deep_sleep=False,
            message=None,
            warning=None
        )
        
        # Store configuration and initialize instance variables
        self.config = cast(AuralicDeviceConfig, config)
        self.ip_address = self.config.auralic.ip_address
        self.update_interval = self.config.auralic.update_interval
        self.discovery_mode = self.config.auralic.discovery_mode
        self.device_url = self.config.auralic.device_url
        self.openhome_device = None
        self._update_task = None
        self._deep_sleep_mode = False  # Track if device is in deep sleep mode
        
        # IR control settings
        self.ir_power_on_topic = getattr(self.config.auralic, 'ir_power_on_topic', None)
        self.ir_power_off_topic = getattr(self.config.auralic, 'ir_power_off_topic', None)
        self.device_boot_time = getattr(self.config.auralic, 'device_boot_time', 15)  # Default 15 seconds
        self._discovery_task = None
        
        # Source caching variables
        self._sources_cache = []  # Cache for available sources
        self._sources_cache_timestamp = None  # When the cache was last updated
        self.sources_cache_ttl = 300  # Cache validity in seconds (5 minutes)
        
        # Validate IR control configuration
        if not (self.ir_power_on_topic and self.ir_power_off_topic):
            logger.warning("IR control topics not configured. Full power control will not be available.")
    
    async def setup(self) -> bool:
        """Initialize the device."""
        try:
            # Initialize openhomedevice
            self.openhome_device = await self._create_openhome_device()
            
            # Even if discovery fails, continue with setup but mark device
            # as potentially in deep sleep mode
            if not self.openhome_device:
                logger.warning(f"Failed to connect to Auralic device at {self.ip_address} - device may be in deep sleep")
                self.update_state(error=f"Device may be in deep sleep mode", connected=False, deep_sleep=True)
                self._deep_sleep_mode = True
            else:
                # Device was discovered, it's not in deep sleep
                self._deep_sleep_mode = False
                # Update initial state
                await self._update_device_state()

            # Start periodic state updates regardless of discovery success
            self._update_task = asyncio.create_task(self._update_state_periodically())
            
            # Check if IR control is properly configured
            if not (self.ir_power_on_topic and self.ir_power_off_topic):
                logger.warning("IR control not properly configured - true power off will not be available")
                self.update_state(warning="IR control not configured - only standby mode available")
            
            # Force a state persistence to ensure the database has all fields
            # This solves the issue of AuralicDeviceState not being fully serialized
            if self._state_change_callback:
                self._state_change_callback(self.device_id)
            
            logger.info(f"Auralic device {self.get_name()} initialized")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Auralic device {self.get_name()}: {str(e)}")
            self.update_state(error=str(e), connected=False, deep_sleep=False)
            return False
    
    async def shutdown(self) -> bool:
        """Cleanup device resources."""
        try:
            # Cancel update task
            if self._update_task:
                self._update_task.cancel()
                try:
                    await self._update_task
                except asyncio.CancelledError:
                    pass
            
            # Cancel discovery task if running
            if self._discovery_task and not self._discovery_task.done():
                self._discovery_task.cancel()
                try:
                    await self._discovery_task
                except asyncio.CancelledError:
                    pass
            
            logger.info(f"Auralic device {self.get_name()} shutdown complete")
            self.update_state(connected=False)
            return True
        except Exception as e:
            logger.error(f"Error during device shutdown: {str(e)}")
            return False
    
    def _get_device_properties(self, device_url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Extract device type, friendly name, and manufacturer from device XML.
        
        Args:
            device_url: The URL to the device's XML description
            
        Returns:
            Tuple containing (device_type, friendly_name, manufacturer)
        """
        try:
            response = requests.get(device_url, timeout=5)
            if response.status_code != 200:
                logger.debug(f"Failed to fetch device XML: HTTP {response.status_code}")
                return None, None, None
                
            # Parse XML
            root = ET.fromstring(response.text)
            
            # Find namespace
            ns = {"": root.tag.split("}")[0].strip("{") if "}" in root.tag else "urn:schemas-upnp-org:device-1-0"}
            
            # Extract device type and friendly name
            device_node = root.find(".//device", ns)
            if device_node is None:
                return None, None, None
                
            device_type = device_node.findtext("deviceType", "", ns)
            friendly_name = device_node.findtext("friendlyName", "", ns)
            manufacturer = device_node.findtext("manufacturer", "", ns)
            
            return device_type, friendly_name, manufacturer
        except Exception as e:
            logger.debug(f"Error extracting device properties: {str(e)}")
            return None, None, None
    
    async def _discover_device_url_async(self) -> Optional[str]:
        """Discover Auralic device URL using async_upnp_client, filtered by IP address."""
        try:
            logger.info(f"Discovering UPnP devices at IP {self.ip_address}...")
            
            # Store discovered devices
            discovered_devices = []
            
            def device_discovered(response):
                """Callback for when a device is discovered."""
                try:
                    # Extract location URL from SSDP response
                    location = response.get('LOCATION') or response.get('location')
                    if not location:
                        return
                    
                    # Extract IP from location URL  
                    parsed_url = urlparse(location)
                    device_ip = parsed_url.hostname
                    
                    # Only process devices at our target IP
                    if device_ip == self.ip_address:
                        logger.debug(f"Found device at {self.ip_address}: {location}")
                        
                        # Get device properties from XML description
                        device_type, friendly_name, manufacturer = self._get_device_properties(location)
                        
                        # Check if this is an Auralic device by manufacturer or name
                        is_auralic_by_manufacturer = (manufacturer and "AURALIC" in str(manufacturer).upper())
                        is_matching_name = (friendly_name and self.device_name.lower() in str(friendly_name).lower())
                        
                        if is_auralic_by_manufacturer or is_matching_name:
                            device_info = {
                                "location": location,
                                "friendly_name": friendly_name or 'Unknown',
                                "manufacturer": manufacturer or 'Unknown',
                                "device_type": device_type
                            }
                            
                            logger.info(f"Found potential device: {device_info['friendly_name']} ({device_info['device_type']}) at {location}")
                            discovered_devices.append(device_info)
                            
                except Exception as e:
                    logger.debug(f"Error processing discovered device: {e}")
            
            # Create SSDP search listener
            search_listener = SsdpSearchListener(
                callback=device_discovered,
                timeout=4,  # 4 second timeout
                search_target='ssdp:all'  # Search for all devices
            )
            
            # Start discovery
            await search_listener.async_start()
            try:
                # Perform the search
                search_listener.async_search()  # This is not an async method either
                
                # Wait for responses (timeout is handled by the listener)
                await asyncio.sleep(4.5)  # Slightly longer than timeout to catch late responses
                
            finally:
                search_listener.async_stop()  # This is not an async method
            
            if not discovered_devices:
                logger.error(f"No Auralic devices found at IP {self.ip_address}")
                return None
                
            logger.debug(f"Found {len(discovered_devices)} matching devices, applying prioritization")
            
            # Prioritize devices by device type and name match (same logic as before)
            media_renderer_devices = []
            name_matching_devices = []
            
            for device in discovered_devices:
                # Check if it's a MediaRenderer
                if device.get("device_type") and "MediaRenderer" in device.get("device_type", ""):
                    media_renderer_devices.append(device)
                
                # Check if name matches exactly
                if self.device_name.lower() in device.get("friendly_name", "").lower():
                    name_matching_devices.append(device)
            
            # Priority 1: MediaRenderer device that matches the name
            for device in media_renderer_devices:
                if device in name_matching_devices:
                    logger.info(f"Selected MediaRenderer device matching name: {device['friendly_name']} at {device['location']}")
                    return device["location"]
            
            # Priority 2: Any MediaRenderer device
            if media_renderer_devices:
                logger.info(f"Selected MediaRenderer device: {media_renderer_devices[0]['friendly_name']} at {media_renderer_devices[0]['location']}")
                return media_renderer_devices[0]["location"]
            
            # Priority 3: Any device matching the name
            if name_matching_devices:
                logger.info(f"Selected device matching name: {name_matching_devices[0]['friendly_name']} at {name_matching_devices[0]['location']}")
                return name_matching_devices[0]["location"]
            
            # Fallback: Use the first device
            logger.info(f"Using first discovered device: {discovered_devices[0]['friendly_name']} at {discovered_devices[0]['location']}")
            return discovered_devices[0]["location"]
            
        except Exception as e:
            logger.error(f"Error during device discovery: {str(e)}")
            return None

    def _discover_device_url(self) -> Optional[str]:
        """Synchronous wrapper for async device discovery."""
        # Since this is called from sync context, we need to run the async version
        try:
            # Try to use existing event loop
            loop = asyncio.get_running_loop()
            # If we're here, we're in an async context but being called synchronously
            # This shouldn't happen in normal operation, but let's handle it gracefully
            logger.warning("_discover_device_url called synchronously from async context")
            # Create a new thread to avoid blocking the current loop
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, self._discover_device_url_async())
                return future.result(timeout=10)  # 10 second timeout
        except RuntimeError:
            # No running loop, safe to create a new one
            return asyncio.run(self._discover_device_url_async())
        except Exception as e:
            logger.error(f"Error in sync wrapper for device discovery: {e}")
            return None
    
    async def _create_openhome_device(self) -> Optional[OpenHomeDevice]:
        """Create and initialize openhomedevice connection."""
        try:
            device_url = None
            
            if self.discovery_mode:
                # Use async_upnp_client to discover the device
                logger.info(f"Using discovery mode to find Auralic device at {self.ip_address}")
                device_url = self._discover_device_url()
                
                if not device_url:
                    logger.error(f"Failed to discover Auralic device at {self.ip_address}")
                    return None
            else:
                # Connect directly using IP address or custom URL
                if self.device_url:
                    logger.info(f"Connecting to Auralic device using custom URL: {self.device_url}")
                    device_url = self.device_url
                else:
                    # NOTE: We can't use a fixed URL format for Auralic devices
                    # They change their port number on each boot, so discovery is required
                    logger.warning(f"No fixed URL will work reliably with Auralic devices as they use dynamic ports")
                    logger.info(f"Attempting to discover Auralic device at {self.ip_address}")
                    device_url = self._discover_device_url()
                    
                    if not device_url:
                        logger.error(f"Failed to discover Auralic device at {self.ip_address}")
                        return None
            
            # Log the discovered URL - this contains the dynamic port needed for reliable connection
            parsed_url = urlparse(device_url)
            logger.info(f"Connecting to Auralic device at {parsed_url.netloc} (note the dynamic port)")
                    
            # Initialize the OpenHome device with the URL
            device = OpenHomeDevice(device_url)
            
            # Handle the device initialization (which sets up event subscriptions)
            try:
                await device.init()
                logger.info("Successfully initialized OpenHome device connection")
            except Exception as e:
                if "412" in str(e):
                    # This is likely due to the 10-second subscription timeout issue
                    logger.warning("Got 412 error during initialization - likely due to Auralic's 10-second event subscription limit")
                    logger.warning("Continuing anyway as basic control functions should still work")
                else:
                    # Reraise other errors
                    raise
            
            # Quick check to see if we can communicate with the device
            try:
                standby = await device.is_in_standby()
                logger.info(f"Successfully connected to Auralic device, standby state: {standby}")
            except Exception as e:
                logger.warning(f"Connected to device but got error checking standby state: {e}")
                if "412" in str(e):
                    logger.warning("This is likely due to the 10-second event subscription limit")
                    logger.warning("Basic control functions should still work despite these errors")
            
            return device
                
        except Exception as e:
            logger.error(f"Error connecting to Auralic device: {str(e)}")
            return None
    
    async def _update_state_periodically(self) -> None:
        """Periodically update device state in background."""
        consecutive_errors = 0
        max_errors = 3  # After this many errors, assume device is in deep sleep
        
        while True:
            try:
                # If device is marked as in deep sleep mode, update state accordingly
                if self._deep_sleep_mode:
                    # logger.debug("Device in deep sleep mode, skipping state update")
                    self.update_state(connected=False, power="off", deep_sleep=True)
                    consecutive_errors += 1
                else:
                    # Normal state update
                    await self._update_device_state()
                    consecutive_errors = 0  # Reset error counter on success
                
                await asyncio.sleep(self.update_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error updating device state: {str(e)}")
                consecutive_errors += 1
                
                # If we have too many consecutive errors, assume device is in deep sleep
                if consecutive_errors >= max_errors and not self._deep_sleep_mode:
                    logger.warning(f"Had {consecutive_errors} consecutive errors updating state - assuming device is in deep sleep")
                    self._deep_sleep_mode = True
                    self.update_state(connected=False, power="off", error="Lost connection to device", deep_sleep=True)
                
                await asyncio.sleep(self.update_interval)
    
    async def _update_device_state(self) -> None:
        """Update current device state."""
        if not self.openhome_device:
            self.update_state(connected=False, deep_sleep=self._deep_sleep_mode)
            return
        
        try:
            # Get transport state (playing, paused, etc)
            transport_state = await self.openhome_device.transport_state()
            
            # Get standby state
            in_standby = await self.openhome_device.is_in_standby()
            power_state = "off" if in_standby else "on"
            
            # Get current track info
            track_info = await self.openhome_device.track_info()
            
            # Get volume and mute status
            volume = await self.openhome_device.volume()
            mute = await self.openhome_device.is_muted()
            
            # Get current source
            sources = await self.openhome_device.sources()
            current_source = None
            
            try:
                # Use source() method instead of source_index()
                source_index = await self.openhome_device.source()
                # Check if source_index is a valid integer and in range
                if isinstance(source_index, int) and 0 <= source_index < len(sources):
                    current_source = sources[source_index]["name"]
            except Exception as e:
                logger.debug(f"Could not get current source: {str(e)}")
            
            # Update state
            self.update_state(
                connected=True,
                power=power_state,
                volume=volume,
                mute=mute,
                source=current_source,
                transport_state=transport_state,
                track_title=track_info.get("title"),
                track_artist=track_info.get("artist"),
                track_album=track_info.get("album"),
                deep_sleep=False  # Device is connected, so not in deep sleep
            )
            
        except Exception as e:
            logger.error(f"Error updating device state: {str(e)}")
            self.update_state(connected=False, error=str(e), deep_sleep=self._deep_sleep_mode)

    async def _refresh_sources_cache(self) -> bool:
        """Refresh the internal cache of available sources.
        
        This method queries the device for available sources and stores 
        them in the internal cache for future use.
        
        Returns:
            bool: True if refresh was successful, False otherwise
        """
        if not self.openhome_device or not self.state.connected:
            logger.debug("Cannot refresh sources: device not connected")
            return False
            
        try:
            # Get sources from OpenHome API
            sources = await self.openhome_device.sources()
            
            # Process sources into a consistent format
            formatted_sources = []
            for idx, source in enumerate(sources):
                formatted_sources.append({
                    "source_id": str(idx),
                    "source_name": source.get("name", f"Unknown Source {idx}"),
                    "type": source.get("type", "unknown"),
                    "visible": source.get("visible", True)
                })
            
            # Store in cache
            self._sources_cache = formatted_sources
            self._sources_cache_timestamp = datetime.now()
            
            logger.debug(f"Refreshed sources cache, found {len(formatted_sources)} sources")
            return True
        except Exception as e:
            logger.error(f"Failed to refresh sources cache: {str(e)}")
            # Clear cache on error
            self._sources_cache = []
            self._sources_cache_timestamp = None
            return False
    
    async def _get_available_sources(self) -> List[Dict[str, Any]]:
        """Get available sources, using cache if available and valid.
        
        This method returns the list of available input sources from the
        cache if it's valid, or refreshes the cache if needed.
        
        Returns:
            List[Dict[str, Any]]: List of available sources
        """
        # Check if cache is valid
        cache_valid = (
            self._sources_cache and
            self._sources_cache_timestamp and
            (datetime.now() - self._sources_cache_timestamp).total_seconds() < self.sources_cache_ttl
        )
        
        # Refresh cache if necessary
        if not cache_valid:
            logger.debug("Sources cache invalid or expired, refreshing")
            await self._refresh_sources_cache()
            
        return self._sources_cache

    # Handler methods

    async def handle_power_on(self, cmd_config: BaseCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """
        Handle power on command.
        
        For Auralic devices in deep sleep, this uses IR control via MQTT.
        UPnP/OpenHome control only works for waking from standby mode.
        
        Args:
            cmd_config: Command configuration
            params: Command parameters
                
        Returns:
            CommandResult: Result of the command
        """
        # Use MQTT topic from config (no override in params)
        mqtt_topic = self.ir_power_on_topic
        
        # CASE 1: Device is in deep sleep mode, use IR control
        if self._deep_sleep_mode:
            logger.info("Device in deep sleep mode, using IR control to power on")
            
            if not mqtt_topic:
                return self.create_command_result(
                    success=False,
                    error="IR control not configured - cannot power on from deep sleep"
                )
            
            # Send IR command via MQTT
            success = await self._send_ir_command(mqtt_topic)
            if not success:
                return self.create_command_result(
                    success=False,
                    error="Failed to send IR power on command"
                )
            
            # Update state to indicate we're waiting for the device to boot
            self.update_state(
                connected=False,
                power="booting",
                message="Device is powering on via IR command",
                deep_sleep=False  # No longer in deep sleep, now booting
            )
            
            # Start delayed discovery to connect to the device once it's booted
            self._start_delayed_discovery()
            
            return self.create_command_result(
                success=True,
                message="IR power on command sent. Device is booting...",
                info=f"Device discovery will be attempted in {self.device_boot_time} seconds"
            )
        
        # CASE 2: Device is connected but in standby, use OpenHome API
        elif self.openhome_device is not None:
            logger.info("Device in standby mode, using OpenHome API to wake")
            
            try:
                # Get current standby state to check if we need to do anything
                in_standby = await self.openhome_device.is_in_standby()
                if not in_standby:
                    logger.info("Device already powered on")
                    return self.create_command_result(
                        success=True,
                        message="Device is already powered on"
                    )
                    
                # Wake the device from standby
                await self.openhome_device.set_standby(False)
                
                # Refresh sources cache after waking from standby
                logger.debug("Refreshing sources cache after waking from standby")
                await self._refresh_sources_cache()
                
                # Update state
                await self._update_device_state()
                
                return self.create_command_result(
                    success=True,
                    message="Device woken from standby mode"
                )
            except Exception as e:
                logger.error(f"Error using OpenHome API to wake device: {str(e)}")
                # Continue to fallback IR control path below
                logger.warning("OpenHome control failed, falling back to IR control")
            
        # CASE 3: Fallback to IR control for any other case
        # - Device not connected 
        # - OpenHome API failed
        # - Inconsistent state
        else:
            logger.warning("Using IR control as fallback power on method")
            
            if not mqtt_topic:
                return self.create_command_result(
                    success=False,
                    error="IR control not configured and cannot use OpenHome API"
                )
            
            # Send IR command via MQTT
            success = await self._send_ir_command(mqtt_topic)
            if not success:
                return self.create_command_result(
                    success=False,
                    error="Failed to send IR power on command"
                )
            
            # Update state to indicate we're waiting for the device to boot
            self.update_state(
                connected=False,
                power="booting",
                message="Device is powering on via IR command",
                deep_sleep=False  # No longer in deep sleep, now booting
            )
            
            # Start delayed discovery
            self._start_delayed_discovery()
            
            return self.create_command_result(
                success=True,
                message="IR power on command sent",
                info=f"Device discovery will be attempted in {self.device_boot_time} seconds"
            )

    async def handle_power_off(self, cmd_config: BaseCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """
        Handle power off command.
        
        For Auralic devices, this uses IR control via MQTT to achieve true power off.
        UPnP/OpenHome can only put the device in standby mode.
        
        Args:
            cmd_config: Command configuration
            params: Command parameters
                standby_only: If True, only put the device in standby mode (no IR)
                
        Returns:
            CommandResult: Result of the command
        """
        try:
            # Check if we should only put the device in standby mode
            standby_only = params.get("standby_only", False)
            
            # If device already appears to be in deep sleep mode
            if self._deep_sleep_mode and not self.openhome_device:
                logger.info("Device already appears to be in deep sleep/off mode")
                return self.create_command_result(
                    success=True,
                    message="Device already appears to be powered off"
                )
            
            # Get MQTT topic from config for IR control
            mqtt_topic = self.ir_power_off_topic
            
            # CASE 1: Standby only mode requested and device is connected
            if standby_only and self.openhome_device:
                logger.info("Standby-only mode requested, putting device in standby mode")
                
                try:
                    # First try to stop playback if it's running
                    try:
                        transport_state = await self.openhome_device.transport_state()
                        if transport_state != "Stopped":
                            logger.info("Stopping playback before standby")
                            await self.openhome_device.stop()
                            await asyncio.sleep(0.5)  # Short delay after stopping playback
                    except Exception as e:
                        logger.warning(f"Error stopping playback: {e}")
                    
                    # Put the device in standby mode
                    await self.openhome_device.set_standby(True)
                    logger.info("Device put in standby mode")
                    
                    # Update state
                    await self._update_device_state()
                    
                    return self.create_command_result(
                        success=True,
                        message="Device put into standby mode as requested",
                        info="Use power_off without standby_only=true for full power off"
                    )
                except Exception as e:
                    logger.error(f"Error putting device in standby: {e}")
                    return self.create_command_result(
                        success=False,
                        error=f"Failed to put device in standby mode: {str(e)}"
                    )
            
            # CASE 2: Full power off requested (deep sleep via IR)
            
            # If IR control is not configured, we can't do true power off
            if not mqtt_topic:
                # If device is connected, try putting it in standby as a fallback
                if self.openhome_device:
                    logger.warning("IR control not configured - falling back to standby mode")
                    
                    try:
                        await self.openhome_device.set_standby(True)
                        logger.info("Device put in standby mode as fallback")
                        await self._update_device_state()
                        
                        return self.create_command_result(
                            success=True,
                            message="Device put into standby mode (IR control not available)",
                            warning="True power off not possible without IR control configuration"
                        )
                    except Exception as e:
                        logger.error(f"Failed to put device in standby: {e}")
                        return self.create_command_result(
                            success=False,
                            error=f"Failed to power off: {str(e)}"
                        )
                else:
                    return self.create_command_result(
                        success=False,
                        error="IR control not configured - cannot perform true power off"
                    )
            
            # Send IR command for true power off directly without standby step
            logger.info("Sending IR command for true power off")
            
            # Send IR command via MQTT
            success = await self._send_ir_command(mqtt_topic)
            if not success:
                return self.create_command_result(
                    success=False,
                    error="Failed to send IR power off command"
                )
            
            # Update state and set deep sleep mode
            self._deep_sleep_mode = True
            self.update_state(
                connected=False,
                power="off",
                message="Device powered off via IR command",
                deep_sleep=True
            )
            
            return self.create_command_result(
                success=True,
                message="IR power off command sent successfully",
                info="Device should now be in true power off state"
            )
                
        except Exception as e:
            logger.error(f"Error executing power off: {str(e)}")
            return self.create_command_result(
                success=False,
                error=f"Failed to power off: {str(e)}"
            )

    async def handle_play(self, cmd_config: BaseCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """Handle play command."""
        try:
            if not self.openhome_device:
                return self.create_command_result(
                    success=False,
                    error="Device not connected"
                )
                
            await self.openhome_device.play()
            await self._update_device_state()
            
            return self.create_command_result(
                success=True,
                message="Playback started"
            )
        except Exception as e:
            logger.error(f"Error executing play: {str(e)}")
            return self.create_command_result(
                success=False,
                error=f"Failed to start playback: {str(e)}"
            )

    async def handle_pause(self, cmd_config: BaseCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """Handle pause command."""
        try:
            if not self.openhome_device:
                return self.create_command_result(
                    success=False,
                    error="Device not connected"
                )
                
            await self.openhome_device.pause()
            await self._update_device_state()
            
            return self.create_command_result(
                success=True,
                message="Playback paused"
            )
        except Exception as e:
            logger.error(f"Error executing pause: {str(e)}")
            return self.create_command_result(
                success=False,
                error=f"Failed to pause playback: {str(e)}"
            )

    async def handle_stop(self, cmd_config: BaseCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """Handle stop command."""
        try:
            if not self.openhome_device:
                return self.create_command_result(
                    success=False,
                    error="Device not connected"
                )
                
            await self.openhome_device.stop()
            await self._update_device_state()
            
            return self.create_command_result(
                success=True,
                message="Playback stopped"
            )
        except Exception as e:
            logger.error(f"Error executing stop: {str(e)}")
            return self.create_command_result(
                success=False,
                error=f"Failed to stop playback: {str(e)}"
            )

    async def handle_next(self, cmd_config: BaseCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """Handle next track command."""
        try:
            if not self.openhome_device:
                return self.create_command_result(
                    success=False,
                    error="Device not connected"
                )
                
            await self.openhome_device.skip()  # Use skip() instead of next()
            await self._update_device_state()
            
            return self.create_command_result(
                success=True,
                message="Skipped to next track"
            )
        except Exception as e:
            logger.error(f"Error executing next: {str(e)}")
            return self.create_command_result(
                success=False,
                error=f"Failed to skip to next track: {str(e)}"
            )

    async def handle_previous(self, cmd_config: BaseCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """Handle previous track command."""
        try:
            if not self.openhome_device:
                return self.create_command_result(
                    success=False,
                    error="Device not connected"
                )
                
            # The OpenHome library doesn't have a previous() method
            # This needs to be implemented differently or skipped
            logger.warning("Previous track function not implemented in OpenHome library")
            
            return self.create_command_result(
                success=False,
                error="Previous track function is not supported"
            )
        except Exception as e:
            logger.error(f"Error executing previous: {str(e)}")
            return self.create_command_result(
                success=False,
                error=f"Failed to skip to previous track: {str(e)}"
            )

    async def handle_set_volume(self, cmd_config: BaseCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """Handle set volume command."""
        try:
            if not self.openhome_device:
                return self.create_command_result(
                    success=False,
                    error="Device not connected"
                )
                
            # Check for both parameter names for backward compatibility
            volume = params.get("volume")
            if volume is None:
                volume = params.get("level")  # Check old parameter name
                
            if volume is None:
                return self.create_command_result(
                    success=False,
                    error="Volume parameter is required"
                )
            
            # Ensure volume is within range (0-100)
            volume = max(0, min(100, int(volume)))
            
            # Set volume
            await self.openhome_device.set_volume(volume)
            
            # Update state
            await self._update_device_state()
            
            return self.create_command_result(
                success=True,
                message=f"Volume set to {volume}"
            )
        except Exception as e:
            logger.error(f"Error setting volume: {str(e)}")
            return self.create_command_result(
                success=False,
                error=f"Failed to set volume: {str(e)}"
            )

    async def handle_volume_up(self, cmd_config: BaseCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """Handle volume up command."""
        try:
            if not self.openhome_device:
                return self.create_command_result(
                    success=False,
                    error="Device not connected"
                )
                
            await self.openhome_device.increase_volume()
            await self._update_device_state()
            
            return self.create_command_result(
                success=True,
                message="Volume increased"
            )
        except Exception as e:
            logger.error(f"Error increasing volume: {str(e)}")
            return self.create_command_result(
                success=False,
                error=f"Failed to increase volume: {str(e)}"
            )

    async def handle_volume_down(self, cmd_config: BaseCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """Handle volume down command."""
        try:
            if not self.openhome_device:
                return self.create_command_result(
                    success=False,
                    error="Device not connected"
                )
                
            await self.openhome_device.decrease_volume()
            await self._update_device_state()
            
            return self.create_command_result(
                success=True,
                message="Volume decreased"
            )
        except Exception as e:
            logger.error(f"Error decreasing volume: {str(e)}")
            return self.create_command_result(
                success=False,
                error=f"Failed to decrease volume: {str(e)}"
            )

    async def handle_mute(self, cmd_config: BaseCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """Handle mute toggle command."""
        try:
            if not self.openhome_device:
                return self.create_command_result(
                    success=False,
                    error="Device not connected"
                )
                
            # Get current mute state
            is_muted = await self.openhome_device.is_muted()
            
            # Toggle mute state
            await self.openhome_device.set_mute(not is_muted)
            
            # Update state
            await self._update_device_state()
            
            return self.create_command_result(
                success=True,
                message=f"Device {'unmuted' if is_muted else 'muted'}"
            )
        except Exception as e:
            logger.error(f"Error toggling mute: {str(e)}")
            return self.create_command_result(
                success=False,
                error=f"Failed to toggle mute: {str(e)}"
            )

    async def handle_set_input(self, cmd_config: BaseCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """Handle set input command."""
        try:
            if not self.openhome_device:
                return self.create_command_result(
                    success=False,
                    error="Device not connected"
                )
                
            source = params.get("input")
            if source is None:
                return self.create_command_result(
                    success=False,
                    error="Input parameter is required"
                )
            
            # Get list of sources from cache or refresh if needed
            sources = await self._get_available_sources()
            
            # If source is numeric, use as index
            if isinstance(source, (int, str)) and str(source).isdigit():
                source_index = int(source)
                # We need raw sources for actual setting
                raw_sources = await self.openhome_device.sources()
                if 0 <= source_index < len(raw_sources):
                    await self.openhome_device.set_source(source_index)
                    source_name = raw_sources[source_index]["name"]
                else:
                    return self.create_command_result(
                        success=False,
                        error=f"Invalid source index: {source_index}"
                    )
            # Otherwise find source by name
            else:
                source_name = str(source)
                source_index = None
                raw_sources = await self.openhome_device.sources()
                
                for i, s in enumerate(raw_sources):
                    if source_name.lower() == s["name"].lower():
                        source_index = i
                        break
                
                if source_index is not None:
                    await self.openhome_device.set_source(source_index)
                else:
                    return self.create_command_result(
                        success=False,
                        error=f"Source not found: {source_name}"
                    )
            
            # Update state
            await self._update_device_state()
            
            return self.create_command_result(
                success=True,
                message=f"Source set to {source_name}"
            )
        except Exception as e:
            logger.error(f"Error setting source: {str(e)}")
            return self.create_command_result(
                success=False,
                error=f"Failed to set source: {str(e)}"
            )

    async def handle_track_info(self, cmd_config: BaseCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """Handle track info command."""
        try:
            if not self.openhome_device:
                return self.create_command_result(
                    success=False,
                    error="Device not connected"
                )
                
            # Get current track info
            track_info = await self.openhome_device.track_info()
            
            # Update state
            await self._update_device_state()
            
            return self.create_command_result(
                success=True,
                message="Track information retrieved",
                track_info=track_info
            )
        except Exception as e:
            logger.error(f"Error getting track info: {str(e)}")
            return self.create_command_result(
                success=False,
                error=f"Failed to get track info: {str(e)}"
            )

    async def handle_get_available_inputs(self, cmd_config: BaseCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """
        Handle retrieving available inputs from the device.
        
        Returns a list of available inputs as pairs of input_id and input_name.
        
        Args:
            cmd_config: Command configuration
            params: Command parameters
                refresh_cache: If True, force a cache refresh
                
        Returns:
            CommandResult: Result with list of available inputs
        """
        try:
            logger.info("Retrieving available inputs from device")
            
            # Check if device is connected
            if not self.openhome_device or not self.state.connected:
                # Check if we're in deep sleep mode
                if self._deep_sleep_mode:
                    return self.create_command_result(
                        success=False,
                        error="Device is powered off (deep sleep mode)"
                    )
                else:
                    return self.create_command_result(
                        success=False,
                        error="Device not connected"
                    )
            
            # Check if we should force a refresh
            force_refresh = params.get("refresh_cache", False)
            if force_refresh:
                logger.info("Forcing refresh of sources cache")
                await self._refresh_sources_cache()
            
            # Get available sources
            sources = await self._get_available_sources()
            
            if not sources:
                logger.warning("No sources found on device")
                return self.create_command_result(
                    success=True,
                    message="No sources found on device",
                    data=[]
                )
            
            logger.info(f"Found {len(sources)} sources")
            
            return self.create_command_result(
                success=True,
                message=f"Retrieved {len(sources)} sources",
                data=sources
            )
                
        except Exception as e:
            error_msg = f"Error retrieving sources: {str(e)}"
            logger.error(error_msg)
            return self.create_command_result(
                success=False, 
                error=error_msg
            )
    
    async def handle_refresh_inputs(self, cmd_config: BaseCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """
        Handle manual refresh of inputs cache.
        
        Args:
            cmd_config: Command configuration
            params: Command parameters
                
        Returns:
            CommandResult: Result of refresh operation
        """
        try:
            logger.info("Manually refreshing sources cache")
            
            # Check if device is connected
            if not self.openhome_device or not self.state.connected:
                if self._deep_sleep_mode:
                    return self.create_command_result(
                        success=False,
                        error="Device is powered off (deep sleep mode)"
                    )
                else:
                    return self.create_command_result(
                        success=False,
                        error="Device not connected"
                    )
            
            # Perform the refresh
            success = await self._refresh_sources_cache()
            
            if success:
                sources_count = len(self._sources_cache)
                return self.create_command_result(
                    success=True,
                    message=f"Successfully refreshed sources cache, found {sources_count} sources"
                )
            else:
                return self.create_command_result(
                    success=False,
                    error="Failed to refresh sources cache"
                )
                
        except Exception as e:
            error_msg = f"Error refreshing sources: {str(e)}"
            logger.error(error_msg)
            return self.create_command_result(
                success=False, 
                error=error_msg
            )

    async def _send_ir_command(self, mqtt_topic: str) -> bool:
        """
        Send an IR command via MQTT.
        
        Args:
            mqtt_topic: The MQTT topic to publish the command to
            
        Returns:
            bool: True if command was sent successfully, False otherwise
        """
        if not self.mqtt_client:
            logger.error("MQTT client not available for IR command")
            return False
            
        if not mqtt_topic:
            logger.error("MQTT topic not configured for IR command")
            return False
            
        try:
            logger.info(f"Sending IR command via MQTT topic: {mqtt_topic}")
            
            # Send empty payload or configured payload
            payload = "1"
            
            # Publish the message
            await self.mqtt_client.publish(mqtt_topic, payload)
            logger.info(f"IR command sent successfully to {mqtt_topic}")
            return True
        except Exception as e:
            logger.error(f"Failed to send IR command: {str(e)}")
            return False
            
    async def _delayed_discovery(self, delay: float = None) -> None:
        """
        Perform device discovery after a delay to allow device to boot.
        
        Args:
            delay: Delay in seconds before attempting discovery. If None, use device_boot_time.
        """
        if delay is None:
            delay = self.device_boot_time
            
        try:
            logger.info(f"Waiting {delay} seconds for device to boot before discovery")
            await asyncio.sleep(delay)
            
            logger.info("Attempting device discovery after boot delay")
            self.openhome_device = await self._create_openhome_device()
            
            if self.openhome_device:
                logger.info("Device successfully discovered after power on")
                self._deep_sleep_mode = False
                
                # Refresh sources cache after power on
                logger.debug("Refreshing sources cache after power on")
                await self._refresh_sources_cache()
                
                await self._update_device_state()
            else:
                logger.error("Failed to discover device after power on")
                self._deep_sleep_mode = True  # Still consider it in deep sleep mode
        except asyncio.CancelledError:
            logger.info("Delayed discovery cancelled")
        except Exception as e:
            logger.error(f"Error during delayed discovery: {str(e)}")
            
    def _start_delayed_discovery(self, delay: float = None) -> None:
        """
        Start a background task for delayed discovery.
        Cancels any existing discovery task first.
        
        Args:
            delay: Delay in seconds before discovery
        """
        # Cancel existing task if it exists
        if self._discovery_task and not self._discovery_task.done():
            self._discovery_task.cancel()
            
        # Create new task
        self._discovery_task = asyncio.create_task(self._delayed_discovery(delay)) 
        
    async def refresh_sources(self) -> bool:
        """Public method to manually refresh the sources cache.
        
        This can be called from external code to update the cache.
        
        Returns:
            bool: True if refresh was successful, False otherwise
        """
        logger.info(f"Manually refreshing sources for device {self.get_name()}")
        return await self._refresh_sources_cache() 