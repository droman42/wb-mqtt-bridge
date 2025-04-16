import logging
import json
from typing import Dict, Any, List, Optional
from pymotivaxmc2 import Emotiva, EmotivaConfig
from datetime import datetime
import asyncio

from devices.base_device import BaseDevice
from app.schemas import EMotivaXMC2State, LastCommand

logger = logging.getLogger(__name__)

class EMotivaXMC2(BaseDevice):
    """eMotiva XMC2 processor device implementation."""
    
    def __init__(self, config: Dict[str, Any], mqtt_client=None):
        super().__init__(config, mqtt_client)
        self._state_schema = EMotivaXMC2State
        self.client = None
        
        # Initialize device state
        self.state = {
            "device_id": self.config.get("device_id"),
            "device_name": self.config.get("device_name"),
            "power": None,
            "zone2_power": None,
            "source_status": None,
            "video_input": None,
            "audio_input": None,
            "startup_complete": False,
            "notifications": False,
            "last_command": None,
            "error": None
        }
    
    async def setup(self) -> bool:
        """Initialize the device."""
        try:
            # Get emotiva-specific configuration
            emotiva_config = self.config.get("emotiva", {})
            if not emotiva_config:
                logger.error(f"Missing 'emotiva' configuration for device: {self.get_name()}")
                self.state["error"] = "Missing emotiva configuration"
                return False
                
            # Get the host IP address
            host = emotiva_config.get("host")
            if not host:
                logger.error(f"Missing 'host' in emotiva configuration for device: {self.get_name()}")
                self.state["error"] = "Missing host configuration"
                return False
                
            logger.info(f"Initializing eMotiva XMC2 device: {self.get_name()} at {host}")
            
            # Prepare configuration with optional parameters
            emotiva_options = {
                "timeout": emotiva_config.get("timeout", 2),
                "max_retries": emotiva_config.get("max_retries", 3),
                "retry_delay": emotiva_config.get("retry_delay", 1.0),
                "keepalive_interval": emotiva_config.get("keepalive_interval", 60)
            }
            
            # Create client instance with proper configuration
            self.client = Emotiva(EmotivaConfig(
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
                if emotiva_config.get("force_connect", False):
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
                    
                    # As a fallback, try the generic cleanup method
                    try:
                        await asyncio.wait_for(
                            self.client._notifier.cleanup(),
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
        
    async def handle_power_on(self, action_config: Dict[str, Any]):
        """Handle power on action."""
        try:
            if not self.client:
                logger.error("Client not initialized")
                return {"success": False, "error": "Client not initialized", "action": "power_on"}
            
            logger.info(f"Turning on eMotiva XMC2: {self.get_name()}")
            
            # Check if we need to use WoL first
            emotiva_config = self.config.get("emotiva", {})
            mac_address = emotiva_config.get("mac_address")
            
            # If MAC address is provided, send WoL packet first
            if mac_address:
                logger.info(f"Sending Wake-on-LAN packet to {mac_address} before power on command")
                # Get broadcast address if specified, otherwise use default
                broadcast_ip = emotiva_config.get("broadcast_ip", "255.255.255.255")
                wol_port = emotiva_config.get("wol_port", 9)
                
                # Send the WoL packet
                wol_result = await self.send_wol_packet(mac_address, broadcast_ip, wol_port)
                if wol_result:
                    logger.info(f"WoL packet sent successfully to {mac_address}")
                    
                    # Give the device time to wake up
                    wol_delay = emotiva_config.get("wol_delay", 2.0)
                    logger.info(f"Waiting {wol_delay} seconds for device to wake up")
                    await asyncio.sleep(wol_delay)
                else:
                    logger.warning(f"Failed to send WoL packet to {mac_address}")
            
            # First ensure we're subscribed to power notifications
            try:
                await self.client.subscribe_to_notifications(["power"])
            except Exception as e:
                logger.warning(f"Could not subscribe to power notifications: {str(e)}")
            
            # Use the set_power_on method which includes notification handling
            try:
                result = await asyncio.wait_for(
                    self.client.set_power_on(),
                    timeout=5.0  # Reasonable timeout for power on command
                )
            except asyncio.TimeoutError:
                logger.error(f"Timeout waiting for power on response from {self.get_name()}")
                self.state["error"] = "Command timeout"
                return {"success": False, "error": "Command timeout", "action": "power_on"}
            
            if result and result.get('status') in ['success', 'sent', 'complete']:
                # Even if the command was sent successfully, the actual state change
                # will be handled by the notification callback, but we can set it preliminarily
                self.update_state({
                    "power": "on",
                    "error": None  # Clear any previous errors
                })
                self.record_last_command("power_on")
                logger.info(f"Successfully sent power on command to eMotiva XMC2: {self.get_name()}")
                
                # Return a properly structured response
                return {
                    "success": True, 
                    "action": "power_on",
                    "device_id": self.device_id,
                    "message": "Power on command sent successfully"
                }
            else:
                # Parse the error message from the result
                error_message = result.get('message', 'Unknown error during power on') if result else "No response from device"
                logger.error(f"Failed to turn on eMotiva XMC2: {error_message}")
                
                # Update the state with the error
                self.update_state({
                    "error": error_message
                })
                
                # Return a properly structured error response
                return {
                    "success": False, 
                    "error": error_message, 
                    "action": "power_on",
                    "device_id": self.device_id
                }
        except Exception as e:
            logger.error(f"Error turning on eMotiva XMC2: {str(e)}")
            
            # Update the state with the error
            self.update_state({
                "error": str(e)
            })
            
            # Return a properly structured error response
            return {
                "success": False, 
                "error": str(e), 
                "action": "power_on",
                "device_id": self.device_id
            }
    
    async def handle_power_off(self, action_config: Dict[str, Any]):
        """Handle power off action."""
        try:
            if not self.client:
                logger.error("Client not initialized")
                return {"success": False, "error": "Client not initialized", "action": "power_off"}
            
            logger.info(f"Turning off eMotiva XMC2: {self.get_name()}")
            
            # First ensure we're subscribed to power notifications
            try:
                await self.client.subscribe_to_notifications(["power"])
            except Exception as e:
                logger.warning(f"Could not subscribe to power notifications: {str(e)}")
            
            # Use the set_power_off method which includes notification handling
            try:
                result = await asyncio.wait_for(
                    self.client.set_power_off(),
                    timeout=5.0  # Reasonable timeout for power off command
                )
            except asyncio.TimeoutError:
                logger.error(f"Timeout waiting for power off response from {self.get_name()}")
                self.state["error"] = "Command timeout"
                return {"success": False, "error": "Command timeout", "action": "power_off"}
            
            if result and result.get('status') in ['success', 'sent', 'complete']:
                # Even if the command was sent successfully, the actual state change
                # will be handled by the notification callback, but we can set it preliminarily
                self.update_state({
                    "power": "standby",
                    "error": None  # Clear any previous errors
                })
                self.record_last_command("power_off")
                logger.info(f"Successfully sent power off command to eMotiva XMC2: {self.get_name()}")
                
                # Return a properly structured response
                return {
                    "success": True, 
                    "action": "power_off",
                    "device_id": self.device_id,
                    "message": "Power off command sent successfully"
                }
            else:
                # Parse the error message from the result
                error_message = result.get('message', 'Unknown error during power off') if result else "No response from device"
                logger.error(f"Failed to turn off eMotiva XMC2: {error_message}")
                
                # Update the state with the error
                self.update_state({
                    "error": error_message
                })
                
                # Return a properly structured error response
                return {
                    "success": False, 
                    "error": error_message, 
                    "action": "power_off",
                    "device_id": self.device_id
                }
        except Exception as e:
            logger.error(f"Error turning off eMotiva XMC2: {str(e)}")
            
            # Update the state with the error
            self.update_state({
                "error": str(e)
            })
            
            # Return a properly structured error response
            return {
                "success": False, 
                "error": str(e), 
                "action": "power_off",
                "device_id": self.device_id
            }
    
    async def handle_zone2_on(self, action_config: Dict[str, Any]):
        """Handle zone 2 on action."""
        try:
            if not self.client:
                logger.error("Client not initialized")
                return {"success": False, "error": "Client not initialized", "action": "zone2_on"}
            
            logger.info(f"Turning on Zone 2 for eMotiva XMC2: {self.get_name()}")
            
            # First ensure we're subscribed to zone2_power notifications
            try:
                await self.client.subscribe_to_notifications(["zone2_power"])
            except Exception as e:
                logger.warning(f"Could not subscribe to zone2_power notifications: {str(e)}")
            
            # Use the set_zone2_power_on method which includes notification handling
            try:
                result = await asyncio.wait_for(
                    self.client.set_zone2_power_on(),
                    timeout=5.0  # Reasonable timeout for zone2 power on command
                )
            except asyncio.TimeoutError:
                logger.error(f"Timeout waiting for Zone 2 power on response from {self.get_name()}")
                self.state["error"] = "Command timeout"
                return {"success": False, "error": "Command timeout", "action": "zone2_on"}
            
            if result and result.get('status') in ['success', 'sent', 'complete']:
                # Update zone status in the state - notifications will update the actual status
                zone_status = self.state.get("zone_status", {})
                zone_status["zone2"] = "on"
                
                # Update multiple state properties at once
                self.update_state({
                    "zone_status": zone_status,
                    "zone2_power": "on",
                    "error": None  # Clear any previous errors
                })
                
                self.record_last_command("zone2_on")
                logger.info(f"Successfully sent Zone 2 power on command for eMotiva XMC2: {self.get_name()}")
                
                # Return a properly structured response
                return {
                    "success": True, 
                    "action": "zone2_on",
                    "device_id": self.device_id,
                    "message": "Zone 2 power on command sent successfully"
                }
            else:
                # Parse the error message from the result
                error_message = result.get('message', 'Unknown error turning on Zone 2') if result else "No response from device"
                logger.error(f"Failed to turn on Zone 2: {error_message}")
                
                # Update the state with the error
                self.update_state({
                    "error": error_message
                })
                
                # Return a properly structured error response
                return {
                    "success": False, 
                    "error": error_message, 
                    "action": "zone2_on",
                    "device_id": self.device_id
                }
        except Exception as e:
            logger.error(f"Error turning on Zone 2: {str(e)}")
            
            # Update the state with the error
            self.update_state({
                "error": str(e)
            })
            
            # Return a properly structured error response
            return {
                "success": False, 
                "error": str(e), 
                "action": "zone2_on",
                "device_id": self.device_id
            }
    
    async def handle_zappiti(self, action_config: Dict[str, Any]):
        """Handle switch to Zappiti input source."""
        await self._switch_input_source("Zappiti", "1")
    
    async def handle_apple_tv(self, action_config: Dict[str, Any]):
        """Handle switch to Apple TV input source."""
        await self._switch_input_source("Apple TV", "2")
    
    async def handle_dvdo(self, action_config: Dict[str, Any]):
        """Handle switch to DVDO input source."""
        await self._switch_input_source("DVDO", "3")
    
    async def _switch_input_source(self, source_name: str, source_id: str):
        """
        Helper method to switch input source.
        
        Args:
            source_name: Human-readable display name (e.g., "Apple TV", "Zappiti")
                         This is the primary value to use for switching.
            source_id: Single-digit numeric ID for fallback (e.g., "1", "2", "3")
        """
        try:
            if not self.client:
                logger.error("Client not initialized")
                return {"success": False, "error": "Client not initialized", "action": f"switch_to_{source_id}"}
            
            logger.info(f"Switching input source to {source_name} (Fallback ID: {source_id}) for eMotiva XMC2: {self.get_name()}")
            
            # First ensure we're subscribed to input notifications
            try:
                await self.client.subscribe_to_notifications(["input", "video_input", "audio_input"])
            except Exception as e:
                logger.warning(f"Could not subscribe to input notifications: {str(e)}")
            
            result = None
            
            # Primary approach: Try to switch using the source_name (human-readable name)
            # The library will map this to the appropriate source identifier internally
            try:
                logger.info(f"Attempting to switch to source by name: {source_name}")
                result = await asyncio.wait_for(
                    self.client.switch_to_source(source_name),
                    timeout=5.0  # Reasonable timeout for source switching
                )
            except asyncio.TimeoutError:
                logger.error(f"Timeout waiting for source switch response when using name: {source_name}")
                # We'll try the fallback approach, don't return error yet
            except Exception as e:
                logger.warning(f"Error switching to source by name ({source_name}): {str(e)}")
                # We'll try the fallback approach, don't return error yet
            
            # If switching by name failed or didn't get a successful result, try fallback to source_id
            if result is None or not (result and result.get('status') in ['success', 'sent', 'complete']):
                if source_id.isdigit() and len(source_id) == 1:
                    try:
                        logger.info(f"Using fallback source ID: {source_id}")
                        result = await asyncio.wait_for(
                            self.client.switch_to_source(source_id),
                            timeout=5.0  # Reasonable timeout for source switching
                        )
                    except asyncio.TimeoutError:
                        logger.error(f"Timeout waiting for source switch response when using ID: {source_id}")
                        self.state["error"] = "Source switch timeout"
                        return {"success": False, "error": "Command timeout", "action": f"switch_to_{source_id}"}
                    except Exception as e:
                        logger.error(f"Error switching to source by ID ({source_id}): {str(e)}")
                        self.state["error"] = str(e)
                        return {"success": False, "error": str(e), "action": f"switch_to_{source_id}"}
                else:
                    # If source_id is not a valid single digit, log an error
                    error_msg = f"Invalid source ID: {source_id}. Must be a single digit."
                    logger.error(error_msg)
                    self.state["error"] = error_msg
                    return {"success": False, "error": error_msg, "action": f"switch_to_{source_id}"}
            
            # Check result status
            if result and result.get('status') in ['success', 'sent', 'complete']:
                # Update the input_source and clear any errors
                self.update_state({
                    "input_source": source_id,  # Store the numeric ID for internal reference
                    "error": None  # Clear any previous errors
                })
                
                self.record_last_command(f"switch_to_{source_name}")
                logger.info(f"Successfully sent command to switch input source to {source_name}")
                
                # Return a properly structured response
                return {
                    "success": True, 
                    "action": f"switch_to_{source_name}", 
                    "source": source_name,
                    "device_id": self.device_id,
                    "message": f"Switched to {source_name} successfully"
                }
            else:
                # Parse the error message from the result
                error_message = result.get('message', f'Unknown error switching to {source_name}') if result else "No response from device"
                logger.error(f"Failed to switch input source: {error_message}")
                
                # Update the state with the error
                self.update_state({
                    "error": error_message
                })
                
                # Return a properly structured error response
                return {
                    "success": False, 
                    "error": error_message, 
                    "action": f"switch_to_{source_name}",
                    "device_id": self.device_id
                }
        except Exception as e:
            logger.error(f"Error switching input source to {source_name}: {str(e)}")
            
            # Update the state with the error
            self.update_state({
                "error": str(e)
            })
            
            # Return a properly structured error response
            return {
                "success": False, 
                "error": str(e), 
                "action": f"switch_to_{source_name}",
                "device_id": self.device_id
            }
    
    def record_last_command(self, command: str):
        """Record the last command executed."""
        self.state["last_command"] = LastCommand(
            action=command,
            source=self.device_name,
            timestamp=datetime.now()
        ).model_dump()
    
    def get_current_state(self) -> EMotivaXMC2State:
        """Return the current state of the device."""
        # Get the zone status info properly
        zone_status = self.state.get("zone_status", {})
        
        # Create a properly formatted state object
        return EMotivaXMC2State(
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
            
        # Process mode
        if "mode" in notification_data:
            mode_data = notification_data["mode"]
            mode_value = mode_data.get("value", "unknown")
            updates["mode"] = mode_value
            logger.debug(f"Mode updated: {mode_value}")
        
        # Update device state with notification data
        if updates:
            self.update_state(updates)
            
            # Publish updated state via MQTT if client is available
            # if self.mqtt_client:
                # state_topic = f"/devices/{self.device_id}/state"
                # self.mqtt_client.publish(state_topic, json.dumps(self.get_state()))
        
