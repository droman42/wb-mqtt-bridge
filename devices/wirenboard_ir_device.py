import json
import logging
from typing import Dict, Any, List
from devices.base_device import BaseDevice

logger = logging.getLogger(__name__)

class WirenboardIRDevice(BaseDevice):
    """Implementation of an IR device controlled through Wirenboard."""
    
    async def setup(self) -> bool:
        """Initialize the device."""
        try:
            # Initialize device state
            self.state = {
                "last_command": None,
                "available_commands": {},
                "alias": self.config.get("alias", self.device_name)
            }
            
            # Load and validate commands configuration
            commands = self.config.get("commands", {})
            if not commands:
                logger.error(f"No commands defined for device {self.get_name()}")
                return False
            
            # Store commands in state for easy access
            self.state["available_commands"] = commands
            
            logger.info(f"Wirenboard IR device {self.get_name()} initialized with {len(commands)} commands")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Wirenboard IR device {self.get_name()}: {str(e)}")
            return False
    
    async def shutdown(self) -> bool:
        """Cleanup device resources."""
        try:
            logger.info(f"Wirenboard IR device {self.get_name()} shutdown complete")
            return True
        except Exception as e:
            logger.error(f"Error during device shutdown: {str(e)}")
            return False
    
    def subscribe_topics(self) -> List[str]:
        """Define the MQTT topics this device should subscribe to."""
        alias = self.state.get("alias", self.device_name)
        commands = self.state.get("available_commands", {})
        
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
            
        return f"/devices/{location}/controls/Play from ROM{rom_position}"
    
    async def handle_message(self, topic: str, payload: str):
        """Handle incoming MQTT messages for this device."""
        logger.debug(f"Wirenboard IR device received message on {topic}: {payload}")
        try:
            # Find matching command configuration by comparing full topic
            matching_command = None
            for cmd_name, cmd_config in self.state["available_commands"].items():
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
                        "timestamp": "timestamp_here"  # You might want to add actual timestamp
                    }
                })
                
                # The actual command publishing will be handled by the MQTT client
                # We'll return the topic and value to be published
                return {
                    "topic": command_topic,
                    "payload": "true"
                }
            
        except Exception as e:
            logger.error(f"Error handling message for {self.get_name()}: {str(e)}")
    
    def get_available_commands(self) -> Dict[str, Any]:
        """Return the list of available commands for this device."""
        return self.state.get("available_commands", {})
    
    def get_last_command(self) -> Dict[str, Any]:
        """Return information about the last executed command."""
        return self.state.get("last_command") 
    