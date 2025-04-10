import json
import logging
import asyncio
from typing import Dict, Any, List, Optional
from devices.base_device import BaseDevice
from app.schemas import BaseDeviceState, RevoxA77ReelToReelState

logger = logging.getLogger(__name__)

class RevoxA77ReelToReel(BaseDevice):
    """Implementation of a Revox A77 reel-to-reel controlled through Wirenboard IR."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._state_schema = RevoxA77ReelToReelState
        self.state = {
            "last_command": None,
            "connection_status": "connected",
            "device_id": self.config.get("device_id"),
            "device_name": self.config.get("device_name")
        }
        # Get sequence delay configuration
        self.sequence_delay = self.config.get("parameters", {}).get("sequence_delay", 5)  # Default 5 seconds

    async def setup(self) -> bool:
        """Initialize the device."""
        try:
            logger.info(f"Revox A77 reel-to-reel {self.get_name()} initialized with {len(self.get_available_commands())} commands")
            logger.info(f"Sequence delay set to {self.sequence_delay} seconds")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize device {self.get_name()}: {str(e)}")
            self.state["connection_status"] = "error"
            self.state["error"] = str(e)
            return True

    async def shutdown(self) -> bool:
        """Cleanup device resources."""
        try:
            logger.info(f"Revox A77 reel-to-reel {self.get_name()} shutdown complete")
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

    async def _send_ir_command(self, action_config: Dict[str, Any], command_name: str) -> Optional[Dict[str, str]]:
        """
        Helper function to send IR commands via MQTT.
        
        Args:
            action_config: Configuration for the action containing location and rom_position
            command_name: Name of the command to update in state
            
        Returns:
            Dict containing MQTT topic and payload if successful, None otherwise
        """
        location = action_config.get("location")
        rom_position = action_config.get("rom_position")
        
        if not location or not rom_position:
            logger.error(f"Missing location or rom_position for {command_name} command")
            return None
            
        mqtt_command = {
            "topic": f"/devices/{location}/controls/Play from ROM{rom_position}/on",
            "payload": "1"
        }
        
        self.update_state({"last_command": command_name})
        logger.info(f"Sending {command_name} command to {location} at position {rom_position}")
        return mqtt_command

    async def _execute_sequence(self, action_config: Dict[str, Any], command_name: str) -> Optional[Dict[str, str]]:
        """
        Helper function to execute a command sequence: stop -> wait -> action.
        
        Args:
            action_config: Configuration for the action to execute
            command_name: Name of the command to execute
            
        Returns:
            Dict containing MQTT topic and payload if successful, None otherwise
        """
        try:
            # First, get the stop command configuration
            stop_config = self.get_available_commands().get("stop")
            if not stop_config:
                logger.error("Stop command configuration not found")
                return None

            # Send stop command immediately
            stop_command = await self._send_ir_command(stop_config, "stop")
            if stop_command:
                # Publish stop command immediately
                from app.main import mqtt_client
                if mqtt_client:
                    await mqtt_client.publish(stop_command["topic"], stop_command["payload"])
                    logger.info("Published stop command")
                else:
                    logger.error("MQTT client not available")
                    return None

            # Wait for configured delay
            logger.info(f"Waiting {self.sequence_delay} seconds before sending {command_name} command")
            await asyncio.sleep(self.sequence_delay)

            # Now send the requested command
            return await self._send_ir_command(action_config, command_name)

        except Exception as e:
            logger.error(f"Error in {command_name} sequence: {str(e)}")
            return None

    async def handle_play(self, action_config: Dict[str, Any]):
        """Handle play action with stop -> wait -> play sequence."""
        return await self._execute_sequence(action_config, "play")

    async def handle_stop(self, action_config: Dict[str, Any]):
        """Handle stop action."""
        return await self._send_ir_command(action_config, "stop")

    async def handle_rewind_forward(self, action_config: Dict[str, Any]):
        """Handle rewind forward action with stop -> wait -> rewind sequence."""
        return await self._execute_sequence(action_config, "rewind_forward")

    async def handle_rewind_backward(self, action_config: Dict[str, Any]):
        """Handle rewind backward action with stop -> wait -> rewind sequence."""
        return await self._execute_sequence(action_config, "rewind_backward")

    async def handle_message(self, topic: str, payload: str):
        """Handle incoming MQTT messages for this device."""
        try:
            # Handle command topics from configuration
            for cmd_name, cmd_config in self.get_available_commands().items():
                if topic == cmd_config["topic"]:
                    if payload.lower() in ["1", "true", "on"]:
                        # Map command names to handler methods
                        handler_map = {
                            "play": self.handle_play,
                            "stop": self.handle_stop,
                            "rewind_forward": self.handle_rewind_forward,
                            "rewind_backward": self.handle_rewind_backward
                        }
                        
                        # Get the appropriate handler
                        handler = handler_map.get(cmd_name)
                        if handler:
                            return await handler(cmd_config)
                        else:
                            logger.warning(f"No handler found for command: {cmd_name}")
                    break
            
        except Exception as e:
            logger.error(f"Error handling message for {self.get_name()}: {str(e)}")

    def get_current_state(self) -> RevoxA77ReelToReelState:
        """Return the current state of the device."""
        return RevoxA77ReelToReelState(
            device_id=self.device_id,
            device_name=self.device_name,
            last_command=self.state.get("last_command"),
            connection_status=self.state.get("connection_status", "unknown"),
            error=self.state.get("error")
        ) 