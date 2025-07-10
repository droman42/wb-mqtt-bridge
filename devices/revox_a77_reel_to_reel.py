import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from devices.base_device import BaseDevice
from app.schemas import RevoxA77ReelToReelState, LastCommand, RevoxA77ReelToReelConfig, IRCommandConfig
from app.mqtt_client import MQTTClient
from app.types import CommandResult, CommandResponse, ActionHandler
import asyncio

logger = logging.getLogger(__name__)

class RevoxA77ReelToReel(BaseDevice[RevoxA77ReelToReelState]):
    """Implementation of a Revox A77 reel-to-reel controlled through Wirenboard IR."""
    
    def __init__(self, config: RevoxA77ReelToReelConfig, mqtt_client: Optional[MQTTClient] = None):
        super().__init__(config, mqtt_client)
        
        # Initialize state as a proper Pydantic model
        self.state = RevoxA77ReelToReelState(
            device_id=self.device_id,
            device_name=self.device_name,
            connection_status="connected"
        )
        
    async def setup(self) -> bool:
        """Initialize the device."""
        try:
            # Load and validate commands configuration
            commands = self.config.commands
            if not commands:
                error_msg = f"No commands defined for device {self.get_name()}"
                logger.error(error_msg)
                self.set_error(error_msg)  # Use standard error method
                return True  # Return True to allow device to be initialized even without commands
            
            logger.info(f"Revox A77 reel-to-reel {self.get_name()} initialized with {len(commands)} commands")
            return True
            
        except Exception as e:
            error_msg = f"Failed to initialize device {self.get_name()}: {str(e)}"
            logger.error(error_msg)
            self.set_error(error_msg)  # Use standard error method
            self.update_state(connection_status="error")
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
            topic = command.topic
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

    async def _send_ir_command(self, cmd_config: IRCommandConfig, command_name: str, params: Dict[str, Any] = None) -> CommandResult:
        """
        Send an IR command via MQTT.
        
        Args:
            cmd_config: Command configuration with location and rom_position
            command_name: Name of the command (for state tracking)
            params: Optional parameters for the command
            
        Returns:
            CommandResult: Result of the command execution
        """
        # Get location and ROM position from the config
        location = cmd_config.location
        rom_position = cmd_config.rom_position
        
        if not location or not rom_position:
            error_msg = f"Missing location or rom_position for {command_name} command"
            logger.error(error_msg)
            return self.create_command_result(success=False, error=error_msg)
            
        # Construct the MQTT topic
        topic = self._get_command_topic(cmd_config)
        payload = "1"
        
        if not topic:
            error_msg = f"Failed to create topic for {command_name} command"
            logger.error(error_msg)
            return self.create_command_result(success=False, error=error_msg)
        
        # Record this as the last command sent 
        if params is None:
            params = {}
            
        # Include MQTT-specific details in params
        params["mqtt_topic"] = topic
        params["mqtt_payload"] = payload
        
        # Create the LastCommand object and update state directly
        # Since this method is called from MQTT message handlers or internal sequences,
        # we use "mqtt" as the source. API calls will be handled by BaseDevice.
        last_command = LastCommand(
            action=command_name,
            source="mqtt",
            timestamp=datetime.now(),
            params=params
        )
        
        # Update state with the LastCommand object
        self.update_state(last_command=last_command)
        
        logger.info(f"Sending {command_name} command to {location} at position {rom_position}")
        
        # Send the command via MQTT if client is available
        if self.mqtt_client:
            try:
                await self.mqtt_client.publish(topic, payload)
                return self.create_command_result(
                    success=True, 
                    message=f"Sent {command_name} command to {location} at position {rom_position}",
                    mqtt_topic=topic,
                    mqtt_payload=payload
                )
            except Exception as e:
                error_msg = f"Failed to send {command_name} command: {str(e)}"
                logger.error(error_msg)
                return self.create_command_result(success=False, error=error_msg)
        else:
            # For testing without MQTT client
            logger.info(f"MQTT client not available, would send to {topic}: {payload}")
            return self.create_command_result(
                success=True, 
                message=f"Would send {command_name} command to {location} at position {rom_position}",
                mqtt_topic=topic,
                mqtt_payload=payload
            )

    async def _execute_sequence(self, cmd_config: IRCommandConfig, command_name: str, params: Dict[str, Any] = None) -> CommandResult:
        """
        Execute a command sequence: stop -> wait -> requested command.
        
        Args:
            cmd_config: Command configuration with location and rom_position
            command_name: Name of the command to execute
            params: Optional parameters for the command
            
        Returns:
            CommandResult: Result of the command execution
        """
        # 1. Find and execute the stop command first
        stop_cmd = self.get_available_commands().get("stop")
        if not stop_cmd:
            error_msg = "Stop command not found in available commands"
            logger.error(error_msg)
            return self.create_command_result(success=False, error=error_msg)
        
        try:
            # No need to convert to IRCommandConfig as it should already be typed
            stop_config = stop_cmd
            
            # Send the stop command
            stop_result = await self._send_ir_command(stop_config, "stop")
            
            # Check if stop command was successful
            if not stop_result.get("success", False):
                error_msg = stop_result.get("error", "Failed to execute stop command")
                logger.error(error_msg)
                return self.create_command_result(success=False, error=error_msg)
            
            # 2. Get the delay from the config
            sequence_delay = self.config.reel_to_reel.sequence_delay
            
            # 3. Wait for the configured delay
            await self.emit_progress(f"Waiting {sequence_delay}s before executing {command_name}", "action_progress")
            await asyncio.sleep(sequence_delay)
            
            # 4. Execute the requested command
            await self.emit_progress(f"Executing {command_name} command", "action_progress")
            result = await self._send_ir_command(cmd_config, command_name, params)
            
            return result
            
        except Exception as e:
            error_msg = f"Error in sequence execution: {str(e)}"
            logger.error(error_msg)
            return self.create_command_result(success=False, error=error_msg)
            
    async def handle_play(self, cmd_config: IRCommandConfig, params: Dict[str, Any] = None) -> CommandResult:
        """
        Handle play command by sending the IR signal.
        
        Args:
            cmd_config: Command configuration with location and rom_position
            params: Optional parameters for the command
            
        Returns:
            CommandResult: Result of the command execution
        """
        return await self._execute_sequence(cmd_config, "play", params)
        
    async def handle_stop(self, cmd_config: IRCommandConfig, params: Dict[str, Any] = None) -> CommandResult:
        """
        Handle stop command by sending the IR signal.
        
        Args:
            cmd_config: Command configuration with location and rom_position
            params: Optional parameters for the command
            
        Returns:
            CommandResult: Result of the command execution
        """
        return await self._send_ir_command(cmd_config, "stop", params)
        
    async def handle_rewind_forward(self, cmd_config: IRCommandConfig, params: Dict[str, Any] = None) -> CommandResult:
        """
        Handle rewind forward command by sending the IR signal.
        
        Args:
            cmd_config: Command configuration with location and rom_position
            params: Optional parameters for the command
            
        Returns:
            CommandResult: Result of the command execution
        """
        return await self._execute_sequence(cmd_config, "rewind_forward", params)
        
    async def handle_rewind_backward(self, cmd_config: IRCommandConfig, params: Dict[str, Any] = None) -> CommandResult:
        """
        Handle rewind backward command by sending the IR signal.
        
        Args:
            cmd_config: Command configuration with location and rom_position
            params: Optional parameters for the command
            
        Returns:
            CommandResult: Result of the command execution
        """
        return await self._execute_sequence(cmd_config, "rewind_backward", params)

    async def handle_message(self, topic: str, payload: str) -> Optional[CommandResult]:
        """
        Handle incoming MQTT messages for this device.
        
        Args:
            topic: The MQTT topic
            payload: The message payload
            
        Returns:
            Optional[CommandResult]: Result of handling the message or None
        """
        try:
            # Find matching command
            matching_cmd_name = None
            matching_cmd_config = None
            
            for cmd_name, cmd_config in self.get_available_commands().items():
                if topic == cmd_config.topic:
                    matching_cmd_name = cmd_name
                    matching_cmd_config = cmd_config
                    break
            
            if not matching_cmd_name or not matching_cmd_config:
                logger.warning(f"No command configuration found for topic: {topic}")
                return None
            
            # Check if the payload indicates command should be executed
            if payload.lower() in ["1", "true", "on"]:
                # Get the handler from our registered handlers
                handler = self._action_handlers.get(matching_cmd_name)
                if handler:
                    # No need to convert to IRCommandConfig, it should already be properly typed
                    # Call the handler with the typed config and empty params
                    return await handler(cmd_config=matching_cmd_config, params={})
                else:
                    logger.warning(f"No handler found for command: {matching_cmd_name}")
                    return self.create_command_result(
                        success=False, 
                        error=f"No handler found for command: {matching_cmd_name}"
                    )
            
            return None
            
        except Exception as e:
            error_msg = f"Error handling message for {self.get_name()}: {str(e)}"
            logger.error(error_msg)
            return self.create_command_result(success=False, error=error_msg) 