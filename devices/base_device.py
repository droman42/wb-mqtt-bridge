from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Type, Callable, TYPE_CHECKING
import logging
import json
from datetime import datetime
from socket import socket, AF_INET, SOCK_DGRAM, SOL_SOCKET, SO_BROADCAST

from app.schemas import BaseDeviceState, LastCommand
from app.mqtt_client import MQTTClient

logger = logging.getLogger(__name__)

class BaseDevice(ABC):
    """Base class for all device implementations."""
    
    def __init__(self, config: Dict[str, Any], mqtt_client: Optional["MQTTClient"] = None):
        self.config = config
        self.device_id = config.get('device_id', 'unknown')
        self.device_name = config.get('device_name', 'unknown')
        self.state = {}  # Device state storage
        self._action_handlers = {}  # Cache for action handlers
        self._state_schema: Optional[Type[BaseDeviceState]] = None
        self.mqtt_client = mqtt_client
        self.mqtt_progress_topic = config.get('mqtt_progress_topic', f'/devices/{self.device_id}/controls/progress')
    
    def get_id(self) -> str:
        """Return the device ID."""
        return self.device_id
    
    def get_name(self) -> str:
        """Return the device name."""
        return self.device_name
    
    @abstractmethod
    async def setup(self) -> bool:
        """Initialize the device. Called when the service starts."""
        pass
    
    @abstractmethod
    async def shutdown(self) -> bool:
        """Cleanup device resources. Called when the service stops."""
        pass
    
    def subscribe_topics(self) -> List[str]:
        """Define the MQTT topics this device should subscribe to."""
        topics = []
        for command in self.get_available_commands().values():
            topic = command.get("topic")
            if topic:
                topics.append(topic)
        return topics
    
    def _evaluate_condition(self, condition: str, payload: str) -> bool:
        """Evaluate a condition string against the payload."""
        try:
            # Simple equality check
            if condition.startswith("payload == "):
                expected_value = condition.split("==")[1].strip().strip("'\"")
                return payload == expected_value
            
            # Numeric comparison
            if any(op in condition for op in ["<=", ">=", "<", ">"]):
                try:
                    payload_num = float(payload)
                    condition_num = float(condition.split()[-1])
                    if "<=" in condition:
                        return payload_num <= condition_num
                    elif ">=" in condition:
                        return payload_num >= condition_num
                    elif "<" in condition:
                        return payload_num < condition_num
                    elif ">" in condition:
                        return payload_num > condition_num
                except ValueError:
                    return False
            
            # JSON path evaluation
            if condition.startswith("json:"):
                try:
                    payload_data = json.loads(payload)
                    path = condition[5:].strip()
                    # Simple path evaluation (can be enhanced with a proper JSON path library)
                    parts = path.split(".")
                    current = payload_data
                    for part in parts:
                        if isinstance(current, dict):
                            current = current.get(part)
                        else:
                            return False
                    return bool(current)
                except (json.JSONDecodeError, AttributeError):
                    return False
            
            return False
        except Exception as e:
            logger.error(f"Error evaluating condition '{condition}': {str(e)}")
            return False
    
    async def handle_message(self, topic: str, payload: str):
        """Handle incoming MQTT messages for this device."""
        logger.debug(f"Device {self.get_name()} received message on {topic}: {payload}")
        
        # Find matching command configuration
        matching_commands = []
        for cmd_name, cmd_config in self.get_available_commands().items():
            if cmd_config.get("topic") == topic:
                matching_commands.append((cmd_name, cmd_config))
        
        if not matching_commands:
            logger.warning(f"No command configuration found for topic: {topic}")
            return
        
        # Process each matching command
        for cmd_name, cmd_config in matching_commands:
            # Check if there are multiple actions defined
            actions = cmd_config.get("actions", [])
            if not actions:
                # Backward compatibility: single action
                if payload.lower() in ["1", "true"]:
                    await self._execute_single_action(cmd_name, cmd_config)
            else:
                # Process multiple actions
                for action in actions:
                    condition = action.get("condition")
                    if condition and self._evaluate_condition(condition, payload):
                        await self._execute_single_action(action["name"], action)
    
    async def _execute_single_action(self, action_name: str, action_config: Dict[str, Any]):
        """Execute a single action based on its configuration."""
        try:
            # Get the action handler
            handler = self._get_action_handler(action_name)
            logger.debug(f"Executing action: {action_name} with handler: {handler}")
            if handler:
                result = await handler(action_config)
                
                # Update state
                self.update_state({
                    "last_command": LastCommand(
                        action=action_name,
                        source="mqtt",
                        timestamp=datetime.now(),
                        params=action_config.get("params")
                    ).dict()
                })
                
                # Return any result from the handler
                return result
                
        except Exception as e:
            logger.error(f"Error executing action {action_name}: {str(e)}")
            return None
    
    def _get_action_handler(self, action_name: str) -> Optional[Callable]:
        """Get or create an action handler for the given action name."""
        if action_name not in self._action_handlers:
            handler_name = f"handle_{action_name}"
            handler = getattr(self, handler_name, None)
            if handler and callable(handler):
                self._action_handlers[action_name] = handler
            else:
                logger.warning(f"No handler found for action: {action_name}")
                return None
        return self._action_handlers[action_name]
    
    def get_state(self) -> Dict[str, Any]:
        """Get the current device state."""
        if self._state_schema:
            try:
                return self._state_schema(
                    device_id=self.device_id,
                    device_name=self.device_name,
                    **self.state
                ).dict()
            except Exception as e:
                logger.error(f"Error validating state with schema: {str(e)}")
                return self.state
        return self.state
    
    def update_state(self, updates: Dict[str, Any]):
        """Update the device state."""
        self.state.update(updates)
        logger.debug(f"Updated state for {self.device_name}: {updates}")
    
    async def execute_action(self, action: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute an action identified by action name."""
        try:
            # Find the command configuration for this action
            cmd_config = None
            for cmd_name, config in self.get_available_commands().items():
                if cmd_name == action:
                    cmd_config = config
                    break
                # Check in multiple actions if present
                for act in config.get("actions", []):
                    if act.get("name") == action:
                        cmd_config = act
                        break
            
            if not cmd_config:
                raise ValueError(f"Action {action} not found in device configuration")
            
            # Execute the action
            result = await self._execute_single_action(action, cmd_config)
            
            response = {
                "success": True,
                "device_id": self.device_id,
                "action": action,
                "state": self.get_state()
            }
            
            # If the action handler returned a result with mqtt_command, include it in the response
            if result and isinstance(result, dict) and "mqtt_command" in result:
                response["mqtt_command"] = result["mqtt_command"]
            
            return response
            
        except Exception as e:
            logger.error(f"Error executing action {action} for device {self.device_id}: {str(e)}")
            return {
                "success": False,
                "device_id": self.device_id,
                "action": action,
                "error": str(e)
            }
    
    async def send_wol_packet(self, mac_address: str, ip_address: str = '255.255.255.255', port: int = 9) -> bool:
        """
        Send a Wake-on-LAN magic packet to the specified MAC address.
        
        Args:
            mac_address: MAC address of the target device (format: xx:xx:xx:xx:xx:xx)
            ip_address: Broadcast IP address (default: 255.255.255.255)
            port: UDP port to send the packet to (default: 9)
            
        Returns:
            bool: True if the packet was sent successfully, False otherwise
        """
        try:
            if not mac_address:
                logger.error("No MAC address provided for Wake-on-LAN")
                return False
                
            # Convert MAC address to bytes
            mac_bytes = bytes.fromhex(mac_address.replace(':', ''))
            
            # Create the magic packet (6 bytes of 0xFF followed by MAC address repeated 16 times)
            magic_packet = b'\xff' * 6 + mac_bytes * 16
            
            # Send the packet
            sock = socket(AF_INET, SOCK_DGRAM)
            sock.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)
            sock.sendto(magic_packet, (ip_address, port))
            sock.close()
            
            logger.info(f"Sent WOL packet to {mac_address}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send WOL packet: {str(e)}")
            return False
    
    def get_available_commands(self) -> Dict[str, Any]:
        """Return the list of available commands for this device."""
        return self.config.get("commands", {})
    
    async def publish_progress(self, message: str) -> bool:
        """
        Publish a progress message to the configured MQTT progress topic.
        
        Args:
            message: The message to publish
            
        Returns:
            bool: True if the message was published successfully, False otherwise
        """
        try:
            if not self.mqtt_client:
                logger.warning(f"Cannot publish progress: MQTT client not available for device {self.device_id}")
                return False
                
            if not message:
                logger.warning(f"Empty progress message not published for device {self.device_id}")
                return False
                
            await self.mqtt_client.publish(self.mqtt_progress_topic, message)
            logger.debug(f"Published progress message to {self.mqtt_progress_topic}: {message}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to publish progress message: {str(e)}")
            return False