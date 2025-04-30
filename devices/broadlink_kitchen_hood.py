import json
import logging
import base64
import asyncio
from typing import Dict, Any, List, Optional
import broadlink
from devices.base_device import BaseDevice
from app.schemas import KitchenHoodState, BroadlinkConfig, BroadlinkKitchenHoodConfig, StandardCommandConfig
from app.mqtt_client import MQTTClient

logger = logging.getLogger(__name__)

class BroadlinkKitchenHood(BaseDevice):
    """Implementation of a kitchen hood controlled through Broadlink RF."""
    
    def __init__(self, config: BroadlinkKitchenHoodConfig, mqtt_client: Optional[MQTTClient] = None):
        super().__init__(config, mqtt_client)
        self.broadlink_device = None
        self._state_schema = KitchenHoodState
        
        # Store the typed config directly
        self.config = config
        
        # Initialize state using Pydantic model
        self.state = KitchenHoodState(
            device_id=self.device_id,
            device_name=self.device_name,
            light="off",
            speed=0,
            connection_status="disconnected"
        )
        
        # Load RF codes map from config directly
        self.rf_codes = self.config.rf_codes
        logger.debug(f"[{self.device_name}] Initialized with RF codes map: {list(self.rf_codes.keys())}")
        for category, codes in self.rf_codes.items():
            logger.debug(f"[{self.device_name}] RF codes category '{category}' contains {len(codes)} codes: {list(codes.keys())}")
        
        # Register action handlers with parameter-based approach only
        self._action_handlers = {
            "set_light": self.handle_set_light,
            "set_speed": self.handle_set_speed
        }
        logger.debug(f"[{self.device_name}] Registered action handlers: {list(self._action_handlers.keys())}")

    async def setup(self) -> bool:
        """Initialize the Broadlink device for the kitchen hood."""
        try:
            # Get Broadlink configuration directly from config
            broadlink_config = self.config.broadlink
            
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
            
            # Update state using model copy with update
            self.state = self.state.model_copy(update={"connection_status": "connected"})
            
            # Log RF codes map status - Adding detailed debug here
            logger.debug(f"[{self.device_name}] RF codes after init: {list(self.rf_codes.keys())}")
            logger.info(f"Loaded RF codes map with {len(self.rf_codes)} categories")
            for category, codes in self.rf_codes.items():
                logger.debug(f"  - {category}: {len(codes)} codes: {list(codes.keys())}")
            
            # Additional verification for speed codes specifically
            if "speed" in self.rf_codes:
                logger.debug(f"[{self.device_name}] Speed codes available: {list(self.rf_codes['speed'].keys())}")
            else:
                logger.warning(f"[{self.device_name}] 'speed' category missing from RF codes! Available: {list(self.rf_codes.keys())}")
            
            logger.info(f"Kitchen hood {self.get_name()} initialized with {len(self.get_available_commands())} commands")
            await self.publish_progress(f"successfully initialized with {len(self.get_available_commands())} commands")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize device {self.get_name()}: {str(e)}")
            
            # Update state using model copy with update
            self.state = self.state.model_copy(update={
                "connection_status": "error",
                "error": str(e)
            })
            
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
        commands = self.get_available_commands()
        logger.debug(f"[{self.device_name}] Available commands: {list(commands.keys())}")
        
        for cmd_name, command in commands.items():
            # Use attribute access instead of dictionary access
            topic = command.topic
            if topic:
                topics.append(topic)
                logger.debug(f"[{self.device_name}] Subscribing to topic '{topic}' for command '{cmd_name}'")
        
        logger.debug(f"Device {self.get_name()} subscribing to topics: {topics}")
        return topics
    
    # ============= Updated parameter-based handlers =============
    
    async def handle_set_light(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]):
        """
        Handle light control with parameters.
        
        Args:
            cmd_config: The command configuration
            params: The parameters dictionary with 'state' key
        """
        # Extract state parameter from params - keeping the original logic since params is still a dict
        state = params.get("state", "off")
        
        # Convert numeric values (0/1) to string values (off/on)
        if state == "0" or state == 0 or state == "false" or state == "False" or state is False:
            state = "off"
        elif state == "1" or state == 1 or state == "true" or state == "True" or state is True:
            state = "on"
        
        # Validate final state value
        state = str(state).lower()
        if state not in ["on", "off"]:
            logger.error(f"Invalid light state: {state}, must be 'on' or 'off'")
            await self.publish_progress(f"Invalid light state: {state}")
            return
        
        # Get RF code from the rf_codes map
        if "light" not in self.rf_codes:
            logger.error("No RF codes map found for 'light' category")
            await self.publish_progress("No RF codes map found for lights")
            return
        
        # Access RF code using proper typed structure
        # Note: We keep this as dict access since rf_codes is defined as Dict[str, Dict[str, str]] in the schema
        rf_code = self.rf_codes.get("light", {}).get(state)
        if not rf_code:
            logger.error(f"No RF code found for light state: {state}")
            await self.publish_progress(f"No RF code found for light state: {state}")
            return
            
        if await self._send_rf_code(rf_code):
            # Update state using model copy with update
            self.state = self.state.model_copy(update={"light": state})
            await self.publish_progress(f"Light turned {state}")
    
    async def handle_set_speed(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]):
        """
        Handle hood speed control with parameters.
        
        Args:
            cmd_config: The command configuration
            params: The parameters dictionary with 'level' key
        """
        logger.debug(f"[{self.device_name}] handle_set_speed called with params: {params}")
        logger.debug(f"[{self.device_name}] Current RF codes: {list(self.rf_codes.keys())}")
        
        # Convert level to int and validate range
        try:
            # Handle various input formats
            level_input = params.get("level", 0)
            
            # Convert to int regardless of input type
            level = int(level_input)
                
            if level < 0 or level > 4:
                logger.error(f"Invalid speed level: {level}, must be between 0 and 4")
                await self.publish_progress(f"Invalid speed level: {level}")
                return
        except (ValueError, TypeError):
            logger.error(f"Invalid speed level value: {params.get('level')}")
            await self.publish_progress(f"Invalid speed level value")
            return
        
        # Convert level to string for lookup in the RF codes map
        level_str = str(level)
        
        # Get RF code from the rf_codes map
        if "speed" not in self.rf_codes:
            logger.error("No RF codes map found for 'speed' category")
            await self.publish_progress("No RF codes map found for speed control")
            return
            
        # Access RF code using proper typed structure
        # Note: We keep this as dict access since rf_codes is defined as Dict[str, Dict[str, str]] in the schema
        rf_code = self.rf_codes.get("speed", {}).get(level_str)
        if not rf_code:
            logger.error(f"No RF code found for speed level: {level}")
            await self.publish_progress(f"No RF code found for speed level: {level}")
            return
            
        if await self._send_rf_code(rf_code):
            # Update state using model copy with update
            self.state = self.state.model_copy(update={"speed": level})
            await self.publish_progress(f"Speed set to {level}")
    
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
            
            # Update state using model copy with update
            self.state = self.state.model_copy(update={
                "connection_status": "error",
                "error": str(e)
            })
            
            return False
    
    def get_current_state(self) -> KitchenHoodState:
        """Return the current state of the kitchen hood."""
        return self.state

    def get_available_commands(self) -> Dict[str, StandardCommandConfig]:
        """
        Return available commands for this device.
        
        Returns:
            Dict[str, StandardCommandConfig]: Dictionary of command name to command config objects
        """
        # Call parent method which now returns StandardCommandConfig objects
        commands = super().get_available_commands()
        
        # Log commands to help with debugging
        logger.debug(f"[{self.device_name}] get_available_commands returning: {list(commands.keys())}")
        return commands 