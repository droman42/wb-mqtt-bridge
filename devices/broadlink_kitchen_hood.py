import json
import logging
import base64
import asyncio
from typing import Dict, Any, List, Optional
import broadlink
from devices.base_device import BaseDevice

logger = logging.getLogger(__name__)

class BroadlinkKitchenHood(BaseDevice):
    """Implementation of a kitchen hood controlled through Broadlink RF."""
    
    async def setup(self) -> bool:
        """Initialize the device."""
        try:
            # Initialize Broadlink device as an instance variable
            self.broadlink_device = None
            
            # Initialize device state
            self.state = {
                "light": "off",
                "speed": 0,
                "last_command": None,
                "available_commands": self.config.get("commands", {}),
                "device_id": self.config.get("device_id"),  # Use device_id from config
                "connection_status": "disconnected"
            }
            
            # Initialize Broadlink device
            broadlink_config = self.config.get("broadlink", {})
            if not broadlink_config:
                logger.error(f"No Broadlink configuration for device {self.get_name()}")
                self.state["connection_status"] = "error"
                self.state["error"] = "No Broadlink configuration"
                # Return True to keep device accessible in UI even with errors
                return True
            
            try:
                # Initialize Broadlink device using discovery
                devices = broadlink.discover(timeout=5, discover_ip_address=broadlink_config["host"])
                if not devices:
                    err_msg = f"No Broadlink devices found at {broadlink_config['host']}"
                    logger.error(err_msg)
                    self.state["connection_status"] = "error"
                    self.state["error"] = err_msg
                    # Return True to keep device accessible in UI even with errors
                    return True
                
                self.broadlink_device = devices[0]
                
                # Authenticate with the device
                self.broadlink_device.auth()
                logger.info(f"Successfully connected to Broadlink device for {self.get_name()}")
                self.state["connection_status"] = "connected"
                
            except Exception as e:
                err_msg = f"Failed to initialize Broadlink device: {str(e)}"
                logger.error(err_msg)
                self.state["connection_status"] = "error"
                self.state["error"] = err_msg
                # Return True to keep device accessible in UI even with errors
                return True
            
            logger.info(f"Kitchen hood {self.get_name()} initialized with {len(self.state['available_commands'])} commands")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize kitchen hood {self.get_name()}: {str(e)}")
            self.state = {
                "connection_status": "error",
                "error": str(e),
                "available_commands": self.config.get("commands", {})
            }
            # Return True to keep device accessible in UI even with errors
            return True
    
    async def shutdown(self) -> bool:
        """Cleanup device resources."""
        try:
            # Nothing to cleanup for Broadlink device
            logger.info(f"Kitchen hood {self.get_name()} shutdown complete")
            return True
        except Exception as e:
            logger.error(f"Error during device shutdown: {str(e)}")
            return False
    
    def subscribe_topics(self) -> List[str]:
        """Define the MQTT topics this device should subscribe to."""
        topics = []
        
        # Add command topics
        for command in self.state.get("available_commands", {}).values():
            topic = command.get("topic")
            if topic:
                topics.append(topic)
        
        # Add key pressed topic
        key_pressed_topic = self.config.get("key_pressed_topic")
        if key_pressed_topic:
            topics.append(key_pressed_topic)
        
        logger.debug(f"Device {self.get_name()} subscribing to topics: {topics}")
        return topics
    
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
    
    async def handle_message(self, topic: str, payload: str):
        """Handle incoming MQTT messages for this device."""
        logger.debug(f"Kitchen hood received message on {topic}: {payload}")
        
        try:
            # Handle key pressed topic (wall switch)
            if topic == self.config.get("key_pressed_topic"):
                if payload.lower() in ["1", "true"]:
                    # Toggle light
                    current_light_state = self.state.get("light", "off")
                    new_light_state = "off" if current_light_state == "on" else "on"
                    
                    # Get appropriate light command based on desired state
                    command_name = "light_off" if current_light_state == "on" else "light_on"
                    light_command = self.state["available_commands"].get(command_name)
                    logger.info(f"Light command: {light_command}")
                    
                    if light_command:
                        # Send RF code
                        if await self._send_rf_code(light_command["rf_code"]):
                            # Update state
                            self.update_state({
                                "light": new_light_state,
                                "last_command": {
                                    "button": command_name,
                                    "source": "wall_switch"
                                }
                            })
                            logger.debug(f"Light state updated to {new_light_state}")
                return
            
            # Handle command topics
            for cmd_name, cmd_config in self.state["available_commands"].items():
                if topic == cmd_config["topic"] and payload.lower() in ["1", "true"]:
                    # Send RF code
                    if await self._send_rf_code(cmd_config["rf_code"]):
                        # Update state based on command
                        state_update = {
                            "last_command": {
                                "button": cmd_config["button"],
                                "source": "mqtt"
                            }
                        }
                        
                        # Update specific states based on command
                        if cmd_name == "light_on":
                            state_update["light"] = "on"
                        elif cmd_name == "light_off":
                            state_update["light"] = "off"
                        elif cmd_name == "hood_speed1":
                            state_update["speed"] = 1
                        elif cmd_name == "hood_speed2":
                            state_update["speed"] = 2
                        elif cmd_name == "hood_speed3":
                            state_update["speed"] = 3
                        elif cmd_name == "hood_speed4":
                            state_update["speed"] = 4
                        elif cmd_name == "hood_off":
                            state_update["speed"] = 0
                        
                        self.update_state(state_update)
                    break
            
        except Exception as e:
            logger.error(f"Error handling message for {self.get_name()}: {str(e)}")
    
    def get_available_commands(self) -> Dict[str, Any]:
        """Return the list of available commands for this device."""
        return self.state.get("available_commands", {})
    
    def get_current_state(self) -> Dict[str, Any]:
        """Return the current state of the hood."""
        return {
            "light": self.state.get("light", "off"),
            "speed": self.state.get("speed", 0),
            "last_command": self.state.get("last_command"),
            "connection_status": self.state.get("connection_status", "unknown"),
            "error": self.state.get("error")
        }
        
    def get_state(self) -> Dict[str, Any]:
        """Override BaseDevice get_state to ensure we safely return state."""
        # Ensure self.state exists, even if initialization had problems
        if not hasattr(self, 'state') or self.state is None:
            return {
                "connection_status": "error",
                "error": "Device state not properly initialized"
            }
        return self.state 