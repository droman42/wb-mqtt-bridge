import json
import logging
import base64
import asyncio
from typing import Dict, Any, List, Optional
import broadlink
from devices.base_device import BaseDevice
from app.schemas import KitchenHoodState, BroadlinkConfig
from app.mqtt_client import MQTTClient

logger = logging.getLogger(__name__)

class BroadlinkKitchenHood(BaseDevice):
    """Implementation of a kitchen hood controlled through Broadlink RF."""
    
    def __init__(self, config: Dict[str, Any], mqtt_client: Optional[MQTTClient] = None):
        super().__init__(config, mqtt_client)
        self.broadlink_device = None
        self._state_schema = KitchenHoodState
        self.state = {
            "light": "off",
            "speed": 0,
            "last_command": None,
            "device_id": self.config.get("device_id"),
            "connection_status": "disconnected"
        }

    async def setup(self) -> bool:
        """Initialize the Broadlink device for the kitchen hood."""
        try:
            # Get Broadlink-specific configuration
            broadlink_dict = self.config.get("broadlink", {})
            if not broadlink_dict:
                logger.error(f"Missing 'broadlink' configuration for device: {self.get_name()}")
                self.state["error"] = "Missing Broadlink configuration"
                return False
                
            # Validate Broadlink configuration with pydantic model
            try:
                broadlink_config = BroadlinkConfig(**broadlink_dict)
            except Exception as e:
                logger.error(f"Invalid Broadlink configuration for device: {self.get_name()}: {str(e)}")
                self.state["error"] = f"Invalid Broadlink configuration: {str(e)}"
                return False
                
            logger.info(f"Initializing Broadlink device: {self.get_name()} at {broadlink_config.host}")
            
            # Initialize the Broadlink device
            self.broadlink_device = broadlink.rm4pro(
                host=(broadlink_config.host, 80),
                mac=bytes.fromhex(broadlink_config.mac.replace(':', '')),
                devtype=int(broadlink_config.device_class, 16)
            )
            
            # Authenticate with the device
            self.broadlink_device.auth()
            logger.info(f"Successfully connected to Broadlink device for {self.get_name()}")
            self.state["connection_status"] = "connected"
            
            logger.info(f"Kitchen hood {self.get_name()} initialized with {len(self.get_available_commands())} commands")
            await self.publish_progress(f"successfully initialized with {len(self.get_available_commands())} commands")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize device {self.get_name()}: {str(e)}")
            self.state["connection_status"] = "error"
            self.state["error"] = str(e)
            return False
    
    async def shutdown(self) -> bool:
        """Cleanup device resources."""
        try:
            # Nothing to cleanup for Broadlink device
            logger.info(f"Kitchen hood {self.get_name()} shutdown complete")
            await self.publish_progress(f"shutdown complete")
            return True
        except Exception as e:
            logger.error(f"Error during device shutdown: {str(e)}")
            return False
    
    def subscribe_topics(self) -> List[str]:
        """Define the MQTT topics this device should subscribe to."""
        topics = []
        
        # Add command topics
        for command in self.get_available_commands().values():
            topic = command.get("topic")
            if topic:
                topics.append(topic)
        
        logger.debug(f"Device {self.get_name()} subscribing to topics: {topics}")
        return topics
    
    async def handle_light_on(self, action_config: Dict[str, Any]):
        """Handle light on action."""
        rf_code = action_config.get("rf_code")
        if not rf_code:
            logger.error("No RF code found for light on")
            await self.publish_progress("No RF code found for light on")
            return
            
        if await self._send_rf_code(rf_code):
            self.update_state({"light": "on"})
            await self.publish_progress("Light turned on")

    async def handle_light_off(self, action_config: Dict[str, Any]):
        """Handle light off action."""
        rf_code = action_config.get("rf_code")
        if not rf_code:
            logger.error("No RF code found for light off")
            await self.publish_progress("No RF code found for light off")
            return
            
        if await self._send_rf_code(rf_code):
            self.update_state({"light": "off"})
            await self.publish_progress("Light turned off")

    async def handle_speed_change(self, action_config: Dict[str, Any]):
        """Handle hood speed change action."""
        speed = action_config.get("speed")
        if speed is None:
            logger.error("Speed value not provided in action config")
            return

        rf_code = action_config.get("rf_code")
        if not rf_code:
            logger.error("No RF code found in action configuration")
            return
            
        if await self._send_rf_code(rf_code):
            self.update_state({"speed": speed})

    async def handle_hood_off(self, action_config: Dict[str, Any]):
        """Handle hood off action."""
        rf_code = action_config.get("rf_code")
        if not rf_code:
            logger.error("No RF code found in action configuration")
            return
            
        if await self._send_rf_code(rf_code):
            self.update_state({"speed": 0})

    async def _send_rf_code(self, rf_code_base64: str) -> bool:
        """Send RF code using Broadlink device."""
        try:
            if not self.broadlink_device:
                logger.error("Broadlink device not initialized")
                return False
            
            # Decode base64 RF code
            rf_code = base64.b64decode(rf_code_base64)
            
            # Send the code
            await asyncio.get_event_loop().run_in_executor(
                None, self.broadlink_device.send_data, rf_code
            )
            return True
            
        except Exception as e:
            logger.error(f"Error sending RF code: {str(e)}")
            self.state["connection_status"] = "error"
            self.state["error"] = str(e)
            return False
    
    def get_current_state(self) -> KitchenHoodState:
        """Return the current state of the hood."""
        return KitchenHoodState(
            device_id=self.device_id,
            device_name=self.device_name,
            light=self.state.get("light", "off"),
            speed=self.state.get("speed", 0),
            connection_status=self.state.get("connection_status", "unknown"),
            last_command=self.state.get("last_command"),
            error=self.state.get("error")
        )
        
    def get_state(self) -> Dict[str, Any]:
        """Override BaseDevice get_state to ensure we safely return state."""
        # Ensure self.state exists, even if initialization had problems
        if not hasattr(self, 'state') or self.state is None:
            return KitchenHoodState(
                device_id=self.device_id,
                device_name=self.device_name,
                light="off",
                speed=0,
                connection_status="error",
                error="Device state not properly initialized"
            ).model_dump()
        return super().get_state() 