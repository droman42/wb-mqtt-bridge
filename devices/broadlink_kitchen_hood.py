import json
import logging
import base64
import asyncio
from typing import Dict, Any, List, Optional
import broadlink
from devices.base_device import BaseDevice
from app.schemas import KitchenHoodState, BroadlinkConfig, BroadlinkKitchenHoodConfig, StandardCommandConfig
from app.mqtt_client import MQTTClient
from app.types import CommandResult, CommandResponse, ActionHandler

logger = logging.getLogger(__name__)

class BroadlinkKitchenHood(BaseDevice[KitchenHoodState]):
    """Implementation of a kitchen hood controlled through Broadlink RF."""
    
    def __init__(self, config: BroadlinkKitchenHoodConfig, mqtt_client: Optional[MQTTClient] = None):
        super().__init__(config, mqtt_client)
        self.broadlink_device = None
        
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
        
    async def setup(self) -> bool:
        """Initialize the Broadlink device for the kitchen hood."""
        try:
            # Get Broadlink configuration directly from config
            broadlink_config = self.config.broadlink
            
            logger.info(f"Initializing Broadlink device: {self.get_name()} at {broadlink_config.host}")
            
            # Handle device_code
            if not broadlink_config.device_code:
                logger.warning(f"device_code not specified for {self.get_name()}, "
                              f"using default 0x520b (RM4 Pro)")
                devtype = 0x520b  # Default for RM4 Pro
            else:
                devtype = int(broadlink_config.device_code, 16)
            
            # Initialize the Broadlink device
            self.broadlink_device = broadlink.rm4pro(
                host=(broadlink_config.host, 80),
                mac=bytes.fromhex(broadlink_config.mac.replace(':', '')),
                devtype=devtype
            )
            
            # Authenticate with the device
            self.broadlink_device.auth()
            logger.info(f"Successfully connected to Broadlink device for {self.get_name()}")
            
            # Update state using update_state method
            self.update_state(connection_status="connected")
            self.clear_error()  # Clear any previous errors
            
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
            await self.emit_progress(f"successfully initialized with {len(self.get_available_commands())} commands", "action_success")
            
            return True
            
        except Exception as e:
            error_msg = f"Failed to initialize device {self.get_name()}: {str(e)}"
            logger.error(error_msg)
            
            # Use standard error handling method
            self.set_error(error_msg)
            self.update_state(connection_status="error")
            
            return False
    
    async def shutdown(self) -> bool:
        """Cleanup device resources."""
        try:
            # Nothing to cleanup for Broadlink device
            logger.info(f"Kitchen hood {self.get_name()} shutdown complete")
            await self.emit_progress(f"shutdown complete", "action_success")
            return True
        except Exception as e:
            error_msg = f"Error during device shutdown: {str(e)}"
            logger.error(error_msg)
            self.set_error(error_msg)
            return False
    
    async def handle_message(self, topic: str, payload: str) -> Optional[CommandResult]:
        """
        Handle incoming MQTT messages for this device.
        
        Args:
            topic: The MQTT topic
            payload: The message payload
            
        Returns:
            Optional[CommandResult]: Result of handling the message or None
        """
        logger.debug(f"Kitchen hood received message on {topic}: {payload}")
        
        # Delegate to parent class's handler
        return await super().handle_message(topic, payload)
    
    # ============= Updated parameter-based handlers =============
    
    async def _send_speed_rf_code(self, level: int) -> bool:
        """
        Helper function to send speed RF code for a given level.
        
        Args:
            level: Speed level (0-4)
            
        Returns:
            bool: True if successful, False otherwise
        """
        # Validate speed level range
        if level < 0 or level > 4:
            logger.error(f"[{self.device_name}] Invalid speed level: {level}, must be between 0 and 4")
            return False
        
        # Get RF code from the rf_codes map - the key is the level as string
        if "speed" not in self.rf_codes:
            logger.error(f"[{self.device_name}] No RF codes map found for 'speed' category")
            return False
            
        level_key = str(level)
        rf_code = self.rf_codes.get("speed", {}).get(level_key)
        if not rf_code:
            logger.error(f"[{self.device_name}] No RF code found for speed level: {level}")
            return False
            
        # Send the RF code
        return await self._send_rf_code(rf_code)

    async def handle_set_light(
        self, 
        cmd_config: StandardCommandConfig, 
        params: Dict[str, Any]
    ) -> CommandResult:
        """
        Handle light control with parameters.
        Includes compensation logic to restore fan speed if it was previously not 0,
        since the physical device resets speed when light is toggled.
        
        Args:
            cmd_config: The command configuration
            params: The parameters dictionary with 'state' key
            
        Returns:
            CommandResult: Result of the command execution
        """
        # Store the current speed before changing the light (for compensation)
        previous_speed = self.state.speed
        
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
            error_msg = f"Invalid light state: {state}, must be 'on' or 'off'"
            logger.error(error_msg)
            await self.emit_progress(f"Invalid light state: {state}", "action_error")
            return self.create_command_result(success=False, error=error_msg)
        
        # Get RF code from the rf_codes map
        if "light" not in self.rf_codes:
            error_msg = "No RF codes map found for 'light' category"
            logger.error(error_msg)
            await self.emit_progress("No RF codes map found for lights", "action_error")
            return self.create_command_result(success=False, error=error_msg)
        
        # Access RF code using proper typed structure
        # Note: We keep this as dict access since rf_codes is defined as Dict[str, Dict[str, str]] in the schema
        rf_code = self.rf_codes.get("light", {}).get(state)
        if not rf_code:
            error_msg = f"No RF code found for light state: {state}"
            logger.error(error_msg)
            await self.emit_progress(f"No RF code found for light state: {state}", "action_error")
            return self.create_command_result(success=False, error=error_msg)
            
        if await self._send_rf_code(rf_code):
            # Update state using update_state method
            self.update_state(light=state)
            await self.emit_progress(f"Light turned {state}", "action_success")
            
            # Compensation logic: If the previous speed was not 0, restore it
            # since the physical device resets speed when light is toggled
            if previous_speed > 0:
                logger.info(f"[{self.device_name}] Compensating for speed reset - restoring speed {previous_speed}")
                await self.emit_progress(f"Restoring fan speed to {previous_speed}", "action_progress")
                
                # Small delay to ensure the light command is processed first
                await asyncio.sleep(0.5)
                
                # Use helper function to send speed RF code
                if await self._send_speed_rf_code(previous_speed):
                    # Update state to restore the speed
                    self.update_state(speed=previous_speed)
                    logger.info(f"[{self.device_name}] Successfully restored speed to {previous_speed}")
                    await self.emit_progress(f"Speed restored to {previous_speed}", "action_success")
                else:
                    logger.warning(f"[{self.device_name}] Failed to restore speed to {previous_speed}")
                    await self.emit_progress(f"Failed to restore speed to {previous_speed}", "action_error")
                    # Update state to reflect that speed was reset to 0 by the physical device
                    self.update_state(speed=0)
            else:
                # If previous speed was 0, the physical device reset doesn't matter
                # but we should still update our state to reflect reality
                self.update_state(speed=0)
                logger.debug(f"[{self.device_name}] Previous speed was 0, no compensation needed")
            
            # Create a standardized result with MQTT command information
            return self.create_mqtt_command_result(
                success=True,
                mqtt_topic=f"kitchen_hood/light/state",
                mqtt_payload=state,
                message=f"Light turned {state}" + (f" (speed restored to {previous_speed})" if previous_speed > 0 else "")
            )
        else:
            error_msg = "Failed to send RF code for light command"
            return self.create_command_result(
                success=False,
                error=error_msg
            )
    
    async def handle_set_speed(
        self, 
        cmd_config: StandardCommandConfig, 
        params: Dict[str, Any]
    ) -> CommandResult:
        """
        Handle hood speed control with parameters.
        
        Args:
            cmd_config: The command configuration
            params: The parameters dictionary with 'level' key
            
        Returns:
            CommandResult: Result of the command execution
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
                error_msg = f"Invalid speed level: {level}, must be between 0 and 4"
                logger.error(error_msg)
                await self.emit_progress(f"Invalid speed level: {level}", "action_error")
                return self.create_command_result(success=False, error=error_msg)
        except (ValueError, TypeError):
            error_msg = f"Invalid speed level value: {params.get('level')}"
            logger.error(error_msg)
            await self.emit_progress(f"Invalid speed level value", "action_error")
            return self.create_command_result(success=False, error=error_msg)
            
        # Use helper function to send speed RF code
        if await self._send_speed_rf_code(level):
            # Update state using update_state method
            self.update_state(speed=level)
            await self.emit_progress(f"Speed set to {level}", "action_success")
            
            # Create a standardized result with MQTT command information
            return self.create_mqtt_command_result(
                success=True,
                mqtt_topic=f"kitchen_hood/speed/state",
                mqtt_payload=level,
                message=f"Speed set to {level}"
            )
        else:
            error_msg = "Failed to send RF code for speed command"
            return self.create_command_result(
                success=False,
                error=error_msg
            )
    
    async def _send_rf_code(self, rf_code_base64: str) -> bool:
        """
        Send RF code using Broadlink device.
        
        Args:
            rf_code_base64: Base64 encoded RF code
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not self.broadlink_device:
                logger.error("Broadlink device not initialized")
                self.set_error("Broadlink device not initialized")
                return False
            
            # Decode base64 RF code
            rf_code = base64.b64decode(rf_code_base64)
            
            # Send the code
            await asyncio.get_event_loop().run_in_executor(
                None, self.broadlink_device.send_data, rf_code
            )
            self.clear_error()  # Clear any previous errors
            return True
            
        except Exception as e:
            error_msg = f"Error sending RF code: {str(e)}"
            logger.error(error_msg)
            
            # Use standard error handling method
            self.set_error(error_msg)
            
            return False
    
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