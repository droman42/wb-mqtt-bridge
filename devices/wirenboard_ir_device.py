import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from devices.base_device import BaseDevice
from app.schemas import WirenboardIRState
from app.mqtt_client import MQTTClient

logger = logging.getLogger(__name__)

class WirenboardIRDevice(BaseDevice):
    """Implementation of an IR device controlled through Wirenboard."""
    
    def __init__(self, config: Dict[str, Any], mqtt_client: Optional[MQTTClient] = None):
        super().__init__(config, mqtt_client)
        self._state_schema = WirenboardIRState
        self.state = {
            "last_command": None,
            "alias": self.config.get("alias", self.device_name)
        }
    
    async def setup(self) -> bool:
        """Initialize the device."""
        try:
            # Load and validate commands configuration
            commands = self.config.get("commands", {})
            if not commands:
                logger.error(f"No commands defined for device {self.get_name()}")
                self.state["error"] = "No commands defined"
                return True  # Return True to allow device to be initialized even without commands
            
            logger.info(f"Wirenboard IR device {self.get_name()} initialized with {len(commands)} commands")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Wirenboard IR device {self.get_name()}: {str(e)}")
            self.state["error"] = str(e)
            return True  # Return True to allow device to be initialized even with errors
    
    async def shutdown(self) -> bool:
        """Cleanup device resources."""
        try:
            logger.info(f"Wirenboard IR device {self.get_name()} shutdown complete")
            return True
        except Exception as e:
            logger.error(f"Error during device shutdown: {str(e)}")
            return False
    
    def get_current_state(self) -> WirenboardIRState:
        """Return the current state of the device."""
        return WirenboardIRState(
            device_id=self.device_id,
            device_name=self.device_name,
            alias=self.state.get("alias", self.device_name),
            last_command=self.state.get("last_command"),
            error=self.state.get("error")
        )
        
    def get_state(self) -> Dict[str, Any]:
        """Override BaseDevice get_state to ensure we safely return state."""
        if not hasattr(self, 'state') or self.state is None:
            return WirenboardIRState(
                device_id=self.device_id,
                device_name=self.device_name,
                alias=self.device_name,
                error="Device state not properly initialized"
            ).dict()
        return super().get_state()
    
    def subscribe_topics(self) -> List[str]:
        """Define the MQTT topics this device should subscribe to."""
        alias = self.state.get("alias", self.device_name)
        commands = self.get_available_commands()
        
        # Create subscription topics for each command action
        topics = []
        for command in commands.values():
            topic = command.get("topic")
            if topic:
                topics.append(topic)
            else:
                logger.error(f"MQTT subscription topic {command.get('action')} not found for {alias}")
        
        logger.debug(f"Device {self.get_name()} subscribing to topics: {topics}")
        return topics
    
    def _get_command_topic(self, command_config: Dict[str, Any]) -> str:
        """
        Construct the MQTT topic for sending a command based on its configuration.
        Override this method if topic construction rules change.
        """
        # Construct topic using location and rom_position fields
        location = command_config.get("location")
        rom_position = command_config.get("rom_position")
        
        if not location or not rom_position:
            logger.warning("Missing location or rom_position in command config")
            return ""
            
        # Use the original format without /on suffix
        return f"/devices/{location}/controls/Play from ROM{rom_position}/on"
    
    async def handle_message(self, topic: str, payload: str):
        """Handle incoming MQTT messages for this device."""
        logger.debug(f"Wirenboard IR device received message on {topic}: {payload}")
        try:
            # Find matching command configuration by comparing full topic
            matching_command = None
            for cmd_name, cmd_config in self.get_available_commands().items():
                if cmd_config.get("topic") == topic:
                    matching_command = cmd_config
                    break
            
            if not matching_command:
                logger.warning(f"No command configuration found for topic: {topic}")
                return
            
            # Check if the payload indicates command should be executed
            # Typically, Wirenboard sends "1" or "true" to trigger commands
            if payload.lower() in ["1", "true"]:
                # Get the topic to publish the command
                command_topic = self._get_command_topic(matching_command)
                if not command_topic:
                    logger.error(f"Could not determine command topic for topic: {topic}")
                    return
                
                # Update state
                self.update_state({
                    "last_command": {
                        "topic": topic,
                        "command_topic": command_topic,
                        "timestamp": datetime.now().isoformat()
                    }
                })
                
                # Return the topic and payload to be published
                # This is crucial for both MQTT subscription handling and API action handling
                return {
                    "topic": command_topic,
                    "payload": 1  # Use integer instead of string - many devices expect numeric values
                }
            
        except Exception as e:
            logger.error(f"Error handling message for {self.get_name()}: {str(e)}")
    
    def get_last_command(self) -> Dict[str, Any]:
        """Return information about the last executed command."""
        return self.state.get("last_command") 
    
    def _get_action_handler(self, action_name: str) -> callable:
        """
        Override the base _get_action_handler to create a generic handler
        that uses the handle_message logic for all actions.
        """
        # Check if we already cached this handler
        if action_name not in self._action_handlers:
            # Create a closure that will handle any action using our message handling logic
            async def generic_handler(action_config):
                logger.info(f"Executing {action_name} action for {self.get_name()} via generic handler")
                
                # Get the topic associated with this action
                topic = action_config.get("topic", "")
                if not topic:
                    raise ValueError(f"No topic defined for action {action_name}")
                
                # Simulate a message on this topic with payload "1"
                result = await self.handle_message(topic, "1")
                
                # If handle_message returns a message to publish, structure it for the API
                if result and isinstance(result, dict) and "topic" in result and "payload" in result:
                    logger.info(f"Publishing MQTT command for {action_name}: {result}")
                    return {
                        "mqtt_command": {
                            "topic": result["topic"],
                            "payload": result["payload"]
                        }
                    }
                else:
                    logger.warning(f"No valid MQTT command returned from handle_message for {action_name}")
                
                return {}
                
            # Cache the handler
            self._action_handlers[action_name] = generic_handler
            
        return self._action_handlers[action_name] 
    