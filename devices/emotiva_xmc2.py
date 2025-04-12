import logging
import json
from typing import Dict, Any, List, Optional
from pymotivaxmc2 import Emotiva, EmotivaConfig
from datetime import datetime

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
            logger.info(f"Initializing eMotiva XMC2 device: {self.get_name()} at {self.host}")
            
            # Create client instance and prepare for discovery
            host = self.config.get("emotiva").get("host")
            self.client = Emotiva(EmotivaConfig(host))
            
            # Attempt to discover the device on the network
            discovery_result = await self.client.discover()
            if discovery_result:
                logger.info(f"Discovered eMotiva devices: {discovery_result}")
                if discovery_result.get('status') == 'success':
                    logger.info(f"Successfully discovered eMotiva devices: {discovery_result}")
                    
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
                    error_message = discovery_result.get('message', 'Unknown error during discovery')
                    logger.error(f"Error discovering eMotiva devices: {error_message}")
                    self.state["error"] = error_message
                    return False
            else:
                logger.error(f"No eMotiva devices discovered, using configured host: {host}")
                self.state["error"] = "Device discovery failed"
                return False

        except Exception as e:
            logger.error(f"Failed to initialize eMotiva XMC2 device {self.get_name()}: {str(e)}")
            self.state["error"] = str(e)
            return False
    
    async def shutdown(self) -> bool:
        """Cleanup device resources."""
        try:
            if self.client:
                # Unsubscribe from notifications if possible
                try:
                    # Ensure notification listener is stopped by cleaning up the notifier
                    if hasattr(self.client, '_notifier') and self.client._notifier:
                        await self.client._notifier.cleanup()
                        logger.info(f"Notification listener cleanup for {self.get_name()} completed")
                    
                    # Properly close the client connection
                    await self.client.close()
                    logger.info(f"Closed connection to eMotiva XMC2 device {self.get_name()}")
                except Exception as e:
                    logger.warning(f"Error during notification cleanup: {str(e)}")
                
                # Update state to reflect disconnected status
                self.update_state({
                    "connected": False,
                    "notifications": False
                })
            
            logger.info(f"eMotiva XMC2 device {self.device_name} shutdown complete")
            return True
        except Exception as e:
            logger.error(f"Error during eMotiva XMC2 device shutdown: {str(e)}")
            return False
        
    async def handle_power_on(self, action_config: Dict[str, Any]):
        """Handle power on action."""
        try:
            if not self.client:
                logger.error("Client not initialized")
                return
            
            logger.info(f"Turning on eMotiva XMC2: {self.get_name()}")
            
            # Use the set_power_on method which includes notification handling
            result = await self.client.set_power_on()
            
            if result and result.get('status') in ['success', 'sent', 'complete']:
                # Even if the command was sent successfully, the actual state change
                # will be handled by the notification callback, but we can set it preliminarily
                self.update_state({"power": "on"})
                self.record_last_command("power_on")
                logger.info(f"Successfully sent power on command to eMotiva XMC2: {self.get_name()}")
                return {"success": True, "action": "power_on"}
            else:
                error_message = result.get('message', 'Unknown error during power on') if result else "No response from device"
                logger.error(f"Failed to turn on eMotiva XMC2: {error_message}")
                self.state["error"] = error_message
                return {"success": False, "error": error_message, "action": "power_on"}
        except Exception as e:
            logger.error(f"Error turning on eMotiva XMC2: {str(e)}")
            self.state["error"] = str(e)
            return {"success": False, "error": str(e), "action": "power_on"}
    
    async def handle_power_off(self, action_config: Dict[str, Any]):
        """Handle power off action."""
        try:
            if not self.client:
                logger.error("Client not initialized")
                return
            
            logger.info(f"Turning off eMotiva XMC2: {self.get_name()}")
            
            # Use the set_power_off method which includes notification handling
            result = await self.client.set_power_off()
            
            if result and result.get('status') in ['success', 'sent', 'complete']:
                # Even if the command was sent successfully, the actual state change
                # will be handled by the notification callback, but we can set it preliminarily
                self.update_state({"power": "standby"})
                self.record_last_command("power_off")
                logger.info(f"Successfully sent power off command to eMotiva XMC2: {self.get_name()}")
                return {"success": True, "action": "power_off"}
            else:
                error_message = result.get('message', 'Unknown error during power off') if result else "No response from device"
                logger.error(f"Failed to turn off eMotiva XMC2: {error_message}")
                self.state["error"] = error_message
                return {"success": False, "error": error_message, "action": "power_off"}
        except Exception as e:
            logger.error(f"Error turning off eMotiva XMC2: {str(e)}")
            self.state["error"] = str(e)
            return {"success": False, "error": str(e), "action": "power_off"}
    
    async def handle_zone2_on(self, action_config: Dict[str, Any]):
        """Handle zone 2 on action."""
        try:
            if not self.client:
                logger.error("Client not initialized")
                return
            
            logger.info(f"Turning on Zone 2 for eMotiva XMC2: {self.get_name()}")
            
            # Use the set_zone2_power_on method which includes notification handling
            result = await self.client.set_zone2_power_on()
            
            if result and result.get('status') in ['success', 'sent', 'complete']:
                # Update zone status in the state - notifications will update the actual status
                zone_status = self.state.get("zone_status", {})
                zone_status["zone2"] = "on"
                self.update_state({
                    "zone_status": zone_status,
                    "zone2_power": "on"
                })
                self.record_last_command("zone2_on")
                logger.info(f"Successfully sent Zone 2 power on command for eMotiva XMC2: {self.get_name()}")
                return {"success": True, "action": "zone2_on"}
            else:
                error_message = result.get('message', 'Unknown error turning on Zone 2') if result else "No response from device"
                logger.error(f"Failed to turn on Zone 2: {error_message}")
                self.state["error"] = error_message
                return {"success": False, "error": error_message, "action": "zone2_on"}
        except Exception as e:
            logger.error(f"Error turning on Zone 2: {str(e)}")
            self.state["error"] = str(e)
            return {"success": False, "error": str(e), "action": "zone2_on"}
    
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
        """Helper method to switch input source."""
        try:
            if not self.client:
                logger.error("Client not initialized")
                return
            
            logger.info(f"Switching input source to {source_name} for eMotiva XMC2: {self.get_name()}")
            
            result = None
            
            # Check if the source_id is an HDMI source with a number (e.g., "hdmi1", "hdmi2", etc.)
            if source_id.startswith('hdmi') and len(source_id) > 4:
                try:
                    # Extract the HDMI number and use specialized HDMI switching
                    hdmi_number = int(source_id[4:])
                    if 1 <= hdmi_number <= 8:
                        logger.info(f"Using HDMI-specific switching for HDMI {hdmi_number}")
                        result = await self.client.switch_to_hdmi(hdmi_number)
                    else:
                        logger.warning(f"Invalid HDMI number: {hdmi_number}. Must be between 1 and 8.")
                except ValueError:
                    logger.warning(f"Could not parse HDMI number from {source_id}, using generic approach")
            
            # If not an HDMI source or HDMI parsing failed, use the switch_to_source method
            if result is None:
                logger.info(f"Using generic source switching for {source_id}")
                result = await self.client.switch_to_source(source_id)
            
            if result and result.get('status') in ['success', 'sent', 'complete']:
                self.update_state({"input_source": source_id})
                self.record_last_command(f"switch_to_{source_id}")
                logger.info(f"Successfully sent command to switch input source to {source_name}")
                return {"success": True, "action": f"switch_to_{source_id}", "source": source_name}
            else:
                error_message = result.get('message', f'Unknown error switching to {source_name}') if result else "No response from device"
                logger.error(f"Failed to switch input source: {error_message}")
                self.state["error"] = error_message
                return {"success": False, "error": error_message, "action": f"switch_to_{source_id}"}
        except Exception as e:
            logger.error(f"Error switching input source to {source_name}: {str(e)}")
            self.state["error"] = str(e)
            return {"success": False, "error": str(e), "action": f"switch_to_{source_id}"}
    
    def record_last_command(self, command: str):
        """Record the last command executed."""
        self.state["last_command"] = LastCommand(
            command=command,
            timestamp=datetime.now().isoformat(),
            device_id=self.device_id
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
            volume=self.state.get("volume", 0),
            input_source=self.state.get("input_source"),
            video_input=self.state.get("video_input"),
            audio_input=self.state.get("audio_input"),
            source_status=self._get_source_display_name(self.state.get("input_source")),
            tone_control=self.state.get("tone_control"),
            connected=self.state.get("connected", False),
            ip_address=self.state.get("ip_address"),
            zone_status=zone_status,
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
        
