from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Type, Callable, TYPE_CHECKING, Awaitable, Coroutine, TypeVar, cast, Union
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
        self.state: Dict[str, Any] = {}  # Device state storage
        self._action_handlers: Dict[str, Callable[..., Awaitable[Any]]] = {}  # Cache for action handlers
        self._action_groups: Dict[str, List[str]] = {}  # Index of actions by group
        self._state_schema: Optional[Type[BaseDeviceState]] = None
        self.mqtt_client = mqtt_client
        self.mqtt_progress_topic = config.get('mqtt_progress_topic', f'/devices/{self.device_id}/controls/progress')
        
        # Build action group index
        self._build_action_groups_index()
    
    def _build_action_groups_index(self):
        """Build an index of actions organized by group."""
        self._action_groups = {"default": []}  # Default group for actions with no group specified
        
        for cmd_name, cmd_config in self.get_available_commands().items():
            # Get the group for this command
            group = cmd_config.get("group", "default")
            
            # Add group to index if it doesn't exist
            if group not in self._action_groups:
                self._action_groups[group] = []
            
            # Add command to the group
            action_info = {
                "name": cmd_name,
                "description": cmd_config.get("description", ""),
                **{k: v for k, v in cmd_config.items() if k not in ["group", "description"]}
            }
            self._action_groups[group].append(action_info)
            
            # Handle multiple actions within a command if present
            actions = cmd_config.get("actions", [])
            for action in actions:
                # Get action group or inherit from parent command if not specified
                action_group = action.get("group", group)  # Inherit group from parent command if not specified
                
                # Add group to index if it doesn't exist
                if action_group not in self._action_groups:
                    self._action_groups[action_group] = []
                
                # Add action to the group
                action_info = {
                    "name": action.get("name", ""),
                    "description": action.get("description", ""),
                    **{k: v for k, v in action.items() if k not in ["group", "description"]}
                }
                self._action_groups[action_group].append(action_info)
    
    def get_available_groups(self) -> List[str]:
        """Get a list of all available action groups for this device."""
        return list(self._action_groups.keys())
    
    def get_actions_by_group(self, group: str) -> List[Dict[str, Any]]:
        """Get all actions in a specific group."""
        return self._action_groups.get(group, [])
    
    def get_actions(self) -> List[Dict[str, Any]]:
        """Return a list of supported actions for this device."""
        # Get all action handlers registered for this device
        actions = []
        for action_name in self._action_handlers:
            # Skip internal actions (starting with underscore)
            if action_name.startswith('_'):
                continue
                
            # Add action to the list
            actions.append({
                'name': action_name,
                'group': 'default'  # Default group for now
            })
            
        return actions
    
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
            # Ensure topic exists and matches
            if cmd_config.get("topic") == topic:
                matching_commands.append((cmd_name, cmd_config))
        
        if not matching_commands:
            logger.warning(f"No command configuration found for topic: {topic}")
            return
        
        # Process each matching command configuration found for the topic
        for cmd_name, cmd_config in matching_commands:
            # Check if there are multiple specific actions defined under this command config
            actions = cmd_config.get("actions", [])
            if actions:
                # Process multiple actions, checking conditions against payload
                processed_action = False
                for action in actions:
                    condition = action.get("condition")
                    # If condition exists and evaluates to true based on payload
                    if condition and self._evaluate_condition(condition, payload):
                        logger.debug(f"Condition '{condition}' met for action '{action.get('name')}' with payload '{payload}'")
                        await self._execute_single_action(action["name"], action, payload)
                        processed_action = True
                        # Decide if we should break after first match or allow multiple? Assuming first match for now.
                        break 
                if not processed_action:
                     logger.debug(f"No condition met for configured actions on topic {topic} with payload '{payload}'")
            else:
                # No specific actions array, treat the command config itself as the action
                # The base class previously checked payload == "1" or "true" here,
                # but we now pass the raw payload to the handler for more flexibility.
                logger.debug(f"Executing single action '{cmd_name}' based on topic match.")
                await self._execute_single_action(cmd_name, cmd_config, payload)
    
    async def _execute_single_action(self, action_name: str, action_config: Dict[str, Any], payload: str):
        """Execute a single action based on its configuration, passing the payload."""
        try:
            # Get the action handler method from the instance
            handler = self._get_action_handler(action_name)
            if not handler:
                 logger.warning(f"No action handler found for action: {action_name} in device {self.get_name()}")
                 return None

            logger.debug(f"Executing action: {action_name} with handler: {handler} and config: {action_config}")
            
            # Call the handler, passing both the config dict for this action and the raw payload
            # Handlers need to be defined like: async def my_handler(self, action_config: Dict[str, Any], payload: str)
            result = await handler(action_config=action_config, payload=payload)
            
            # Update state with information about the last command executed
            self.update_state({
                "last_command": LastCommand(
                    action=action_name,
                    source="mqtt",
                    timestamp=datetime.now(),
                    params=action_config.get("params"),
                    position=action_config.get("position")
                ).dict()
            })
            
            # Return any result from the handler
            return result
                
        except Exception as e:
            logger.error(f"Error executing action {action_name}: {str(e)}")
            return None
    
    def _get_action_handler(self, action: str) -> Optional[Callable[..., Any]]:
        """Get the handler function for the specified action."""
        # Convert to lower case for case-insensitive lookup
        action = action.lower()
        
        # Check if we have a handler for this action
        handler = self._action_handlers.get(action)
        if handler:
            return handler
            
        # If not found, check if maybe it's in camelCase and we have a handler for snake_case
        if '_' not in action:
            # Convert camelCase to snake_case and try again
            snake_case = ''.join(['_' + c.lower() if c.isupper() else c for c in action]).lstrip('_')
            handler = self._action_handlers.get(snake_case)
            if handler:
                return handler
                
        return None
    
    def get_current_state(self) -> Dict[str, Any]:
        """Get the current state of the device."""
        if self._state_schema:
            # Return validated state dict
            return self._state_schema(**self.state).dict()
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
            result = await self._execute_single_action(action, cmd_config, "")
            
            response = {
                "success": True,
                "device_id": self.device_id,
                "action": action,
                "state": self.get_current_state()
            }
            
            # If the action handler returned a result with mqtt_command, include it in the response
            if result and isinstance(result, dict) and "mqtt_command" in result:
                response["mqtt_command"] = result["mqtt_command"]
            
            await self.publish_progress(f"Action {action} executed successfully")
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
            await self.publish_progress(f"WOL packet sent to {mac_address}")
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
                
            await self.mqtt_client.publish(self.mqtt_progress_topic, f"{self.device_name}: {message}")
            logger.debug(f"Published progress message to {self.mqtt_progress_topic}: {message}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to publish progress message: {str(e)}")
            return False