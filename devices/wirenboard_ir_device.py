import json
import logging
from typing import Dict, Any, List, Optional, Callable, Awaitable
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
        
        # Pre-initialize handlers for all commands
        self._initialize_action_handlers()
    
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
    
    def get_current_state(self) -> Dict[str, Any]:
        """Return the current state of the device."""
        # Create a Pydantic model instance and convert to dictionary
        state = WirenboardIRState(
            device_id=self.device_id,
            device_name=self.device_name,
            alias=self.state.get("alias", self.device_name),
            last_command=self.state.get("last_command"),
            error=self.state.get("error")
        )
        # Return dictionary representation for API compatibility
        return state.dict()
    
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
                        "timestamp": datetime.now().isoformat(),
                        "position": matching_command.get("position")
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
    
    def get_last_command(self) -> Optional[Dict[str, Any]]:
        """Return information about the last executed command."""
        return self.state.get("last_command") 
    
    def _initialize_action_handlers(self):
        """Initialize handlers for all configured commands in the 'commands' section."""
        commands_config = self.config.get('commands', {})
        
        for cmd_name, cmd_config in commands_config.items():
            action_name = cmd_name.lower()  # Use lowercase for case-insensitivity
            # Create the handler and store it
            self._action_handlers[action_name] = self._create_generic_handler(action_name, cmd_config)
            logger.debug(f"Registered handler for command: {action_name}")

    def _create_generic_handler(self, action_name: str, cmd_config: Dict[str, Any]):
        """Create a generic handler function for the given command."""
        async def generic_handler(action_config=None, payload=None, **kwargs):
            # Handle both calling conventions
            # Since we're using the cmd_config from initialization, we only need to handle
            # additional parameters from action_config if provided
            
            # Build the MQTT message from the command config
            command_topic = self._get_command_topic(cmd_config)
            command_payload = cmd_config.get('payload', 1)  # Default to numeric 1 if not specified
            
            logger.info(f"Executing IR command for action {action_name}: {command_topic} = {command_payload}")
            
            # Create MQTT command to send via the handle_message method
            mqtt_command = {
                "topic": command_topic,
                "payload": command_payload
            }
            
            # Record this as the last command sent
            self.state["last_command"] = {
                "action": action_name,
                "command": cmd_config.get('name', 'unknown'),
                "topic": command_topic,
                "payload": command_payload,
                "timestamp": datetime.now().isoformat()
            }
            
            # Send the command to the IR transmitter via MQTT
            if self.mqtt_client:
                success = await self.mqtt_client.publish(command_topic, command_payload)
                if success:
                    logger.info(f"Successfully sent IR command for action {action_name}")
                    return {"success": True, "message": f"Successfully sent IR command: {action_name}"}
                else:
                    logger.error(f"Failed to send IR command for action {action_name}")
                    return {"success": False, "message": f"Failed to send IR command: {action_name}"}
            else:
                logger.warning(f"No MQTT client available to send IR command for action {action_name}")
                logger.warning(f"No valid MQTT command returned from handle_message for {action_name}")
            
            return {}
        
        return generic_handler

    def _get_action_handler(self, action_name: str) -> Optional[Callable[..., Any]]:
        """Get the handler for the specified action from pre-initialized handlers."""
        # Convert to lower case for case-insensitive lookup
        action_name = action_name.lower()
        
        # Look up the handler directly from the pre-initialized dictionary
        handler = self._action_handlers.get(action_name)
        if handler:
            return handler
        
        # If not found, check if maybe it's in camelCase and we have a handler for snake_case
        if '_' not in action_name:
            # Convert camelCase to snake_case and try again
            snake_case = ''.join(['_' + c.lower() if c.isupper() else c for c in action_name]).lstrip('_')
            handler = self._action_handlers.get(snake_case)
            if handler:
                return handler
        
        # No handler found
        logger.warning(f"No action handler found for action: {action_name}")
        return None
    