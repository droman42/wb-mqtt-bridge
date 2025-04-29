import json
import logging
from typing import Dict, Any, List, Optional, Tuple, cast
from datetime import datetime
from devices.base_device import BaseDevice
from app.schemas import RevoxA77ReelToReelState, LastCommand, RevoxA77ReelToReelConfig, IRCommandConfig
from app.mqtt_client import MQTTClient
import asyncio

logger = logging.getLogger(__name__)

class RevoxA77ReelToReel(BaseDevice):
    """Implementation of a Revox A77 reel-to-reel controlled through Wirenboard IR."""
    
    def __init__(self, config: Dict[str, Any], mqtt_client: Optional[MQTTClient] = None):
        super().__init__(config, mqtt_client)
        self._state_schema = RevoxA77ReelToReelState
        
        # Get and use the typed config
        self.typed_config = cast(RevoxA77ReelToReelConfig, self.config)
        
        self.state = {
            "last_command": None,
            "connection_status": "connected"
        }
        
        # Register action handlers
        self._action_handlers = {
            "play": self.handle_play,
            "stop": self.handle_stop,
            "rewind_forward": self.handle_rewind_forward,
            "rewind_backward": self.handle_rewind_backward
        }

    async def setup(self) -> bool:
        """Initialize the device."""
        try:
            # Load and validate commands configuration
            commands = self.typed_config.commands
            if not commands:
                logger.error(f"No commands defined for device {self.get_name()}")
                self.state["error"] = "No commands defined"
                return True  # Return True to allow device to be initialized even without commands
            
            logger.info(f"Revox A77 reel-to-reel {self.get_name()} initialized with {len(commands)} commands")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize device {self.get_name()}: {str(e)}")
            self.state["connection_status"] = "error"
            self.state["error"] = str(e)
            return True  # Return True to allow device to be initialized even with errors

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

    def _get_command_topic(self, cmd_config: IRCommandConfig) -> str:
        """
        Construct the MQTT topic for sending a command based on its configuration.
        
        Args:
            cmd_config: Command configuration with location and rom_position
            
        Returns:
            MQTT topic string
        """
        # Construct topic using location and rom_position fields
        location = cmd_config.location
        rom_position = cmd_config.rom_position
        
        if not location or not rom_position:
            logger.warning("Missing location or rom_position in command config")
            return ""
            
        # Use the original format with /on suffix
        return f"/devices/{location}/controls/Play from ROM{rom_position}/on"

    def _create_response(self, 
                        success: bool, 
                        action: str, 
                        message: Optional[str] = None, 
                        error: Optional[str] = None,
                        **extra_fields) -> Dict[str, Any]:
        """Create a standardized response dictionary.
        
        Args:
            success: Whether the action was successful
            action: The name of the action
            message: Optional success message
            error: Optional error message
            **extra_fields: Additional fields to include in the response
            
        Returns:
            A standardized response dictionary
        """
        response = {
            "success": success,
            "action": action,
            "device_id": self.device_id
        }
        
        if success and message:
            response["message"] = message
            
        if not success and error:
            response["error"] = error
            
        # Add any extra fields
        response.update(extra_fields)
        
        return response

    async def _send_ir_command(self, cmd_config: IRCommandConfig, command_name: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Send an IR command via MQTT.
        
        Args:
            cmd_config: Command configuration with location and rom_position
            command_name: Name of the command (for state tracking)
            params: Optional parameters for the command
            
        Returns:
            Dict with status information
        """
        # Get location and ROM position from the typed config
        location = cmd_config.location
        rom_position = cmd_config.rom_position
        
        if not location or not rom_position:
            error_msg = f"Missing location or rom_position for {command_name} command"
            logger.error(error_msg)
            return self._create_response(False, command_name, error=error_msg)
            
        # Construct the MQTT topic
        topic = self._get_command_topic(cmd_config)
        payload = "1"
        
        if not topic:
            error_msg = f"Failed to create topic for {command_name} command"
            logger.error(error_msg)
            return self._create_response(False, command_name, error=error_msg)
        
        # Record this as the last command sent 
        if params is None:
            params = {}
            
        # Include MQTT-specific details in params
        params["mqtt_topic"] = topic
        params["mqtt_payload"] = payload
        
        self.update_state({
            "last_command": LastCommand(
                action=command_name,
                source="mqtt",
                timestamp=datetime.now(),
                params=params
            ).dict()
        })
        
        logger.info(f"Sending {command_name} command to {location} at position {rom_position}")
        
        # Send the command via MQTT if client is available
        if self.mqtt_client:
            try:
                await self.mqtt_client.publish(topic, payload)
                return self._create_response(
                    True, 
                    command_name, 
                    message=f"Sent {command_name} command to {location} at position {rom_position}",
                    topic=topic,
                    payload=payload
                )
            except Exception as e:
                error_msg = f"Failed to send {command_name} command: {str(e)}"
                logger.error(error_msg)
                return self._create_response(False, command_name, error=error_msg)
        else:
            # For testing without MQTT client
            logger.info(f"MQTT client not available, would send to {topic}: {payload}")
            return self._create_response(
                True, 
                command_name, 
                message=f"Would send {command_name} command to {location} at position {rom_position}",
                topic=topic,
                payload=payload
            )

    async def _execute_sequence(self, cmd_config: IRCommandConfig, command_name: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute a command sequence: stop -> wait -> requested command.
        
        Args:
            cmd_config: Command configuration with location and rom_position
            command_name: Name of the command to execute
            params: Optional parameters for the command
            
        Returns:
            Dict with status information from the requested command
        """
        # 1. Find and execute the stop command first
        stop_cmd = self.get_available_commands().get("stop")
        if not stop_cmd:
            error_msg = "Stop command not found in available commands"
            logger.error(error_msg)
            return self._create_response(False, command_name, error=error_msg)
        
        try:
            # Convert the stop command to IRCommandConfig
            stop_config = IRCommandConfig(**stop_cmd)
            
            # Send the stop command
            stop_result = await self._send_ir_command(stop_config, "stop")
            
            # Check if stop command was successful
            if not stop_result.get("success", False):
                error_msg = stop_result.get("error", "Failed to execute stop command")
                logger.error(error_msg)
                return self._create_response(False, command_name, error=error_msg)
            
            # 2. Get the delay from the typed config
            sequence_delay = self.typed_config.reel_to_reel.sequence_delay
            
            # 3. Wait for the configured delay
            await self.publish_progress(f"Waiting {sequence_delay}s before executing {command_name}")
            await asyncio.sleep(sequence_delay)
            
            # 4. Execute the requested command
            await self.publish_progress(f"Executing {command_name} command")
            result = await self._send_ir_command(cmd_config, command_name, params)
            
            return result
            
        except Exception as e:
            error_msg = f"Error in sequence execution: {str(e)}"
            logger.error(error_msg)
            return self._create_response(False, command_name, error=error_msg)
            
    async def handle_play(self, cmd_config: IRCommandConfig, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Handle play command by sending the IR signal.
        
        Args:
            cmd_config: Command configuration with location and rom_position
            params: Optional parameters for the command
            
        Returns:
            Dict with status information
        """
        return await self._execute_sequence(cmd_config, "play", params)
        
    async def handle_stop(self, cmd_config: IRCommandConfig, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Handle stop command by sending the IR signal.
        
        Args:
            cmd_config: Command configuration with location and rom_position
            params: Optional parameters for the command
            
        Returns:
            Dict with status information
        """
        return await self._send_ir_command(cmd_config, "stop", params)
        
    async def handle_rewind_forward(self, cmd_config: IRCommandConfig, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Handle rewind forward command by sending the IR signal.
        
        Args:
            cmd_config: Command configuration with location and rom_position
            params: Optional parameters for the command
            
        Returns:
            Dict with status information
        """
        return await self._execute_sequence(cmd_config, "rewind_forward", params)
        
    async def handle_rewind_backward(self, cmd_config: IRCommandConfig, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Handle rewind backward command by sending the IR signal.
        
        Args:
            cmd_config: Command configuration with location and rom_position
            params: Optional parameters for the command
            
        Returns:
            Dict with status information
        """
        return await self._execute_sequence(cmd_config, "rewind_backward", params)

    async def handle_message(self, topic: str, payload: str):
        """Handle incoming MQTT messages for this device."""
        try:
            # Find matching command
            matching_cmd_name = None
            matching_cmd_config = None
            
            for cmd_name, cmd_config in self.get_available_commands().items():
                if topic == cmd_config["topic"]:
                    matching_cmd_name = cmd_name
                    matching_cmd_config = cmd_config
                    break
            
            if not matching_cmd_name or not matching_cmd_config:
                logger.warning(f"No command configuration found for topic: {topic}")
                return
            
            # Check if the payload indicates command should be executed
            if payload.lower() in ["1", "true", "on"]:
                # Get the handler from our registered handlers
                handler = self._action_handlers.get(matching_cmd_name)
                if handler:
                    # Convert to IRCommandConfig for typed handling
                    typed_config = IRCommandConfig(**matching_cmd_config)
                    # Call the handler
                    return await handler(cmd_config=typed_config)
                else:
                    logger.warning(f"No handler found for command: {matching_cmd_name}")
                    return self._create_response(False, matching_cmd_name, error="No handler found")
            
        except Exception as e:
            error_msg = f"Error handling message for {self.get_name()}: {str(e)}"
            logger.error(error_msg)
            return self._create_response(False, "unknown", error=error_msg)

    def get_current_state(self) -> RevoxA77ReelToReelState:
        """Return the current state of the device."""
        return RevoxA77ReelToReelState(
            device_id=self.device_id,
            device_name=self.device_name,
            last_command=self.state.get("last_command"),
            connection_status=self.state.get("connection_status", "unknown"),
            error=self.state.get("error")
        ) 