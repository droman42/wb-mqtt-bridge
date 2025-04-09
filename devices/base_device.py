from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import logging
import json

logger = logging.getLogger(__name__)

class BaseDevice(ABC):
    """Base class for all device implementations."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.device_id = config.get('device_id', 'unknown')
        self.device_name = config.get('device_name', 'unknown')
        self.state = {}  # Device state storage
        self._action_handlers = {}  # Cache for action handlers
    
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
                await handler(action_config)
                
                # Update state
                self.update_state({
                    "last_command": {
                        "action": action_name,
                        "source": "mqtt",
                        "timestamp": "timestamp_here"  # TODO: Add actual timestamp
                    }
                })
        except Exception as e:
            logger.error(f"Error executing action {action_name}: {str(e)}")
    
    def _get_action_handler(self, action_name: str) -> Optional[callable]:
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
        return self.state
    
    def update_state(self, updates: Dict[str, Any]):
        """Update the device state."""
        self.state.update(updates)
        logger.debug(f"Updated state for {self.device_name}: {updates}")
    
    async def execute_action(self, action: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
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
            await self._execute_single_action(action, cmd_config)
            
            return {
                "success": True,
                "device_id": self.device_id,
                "action": action,
                "state": self.get_state()
            }
            
        except Exception as e:
            logger.error(f"Error executing action {action} for device {self.device_id}: {str(e)}")
            return {
                "success": False,
                "device_id": self.device_id,
                "action": action,
                "error": str(e)
            }
    
    def get_available_commands(self) -> Dict[str, Any]:
        """Return the list of available commands for this device."""
        return self.config.get("commands", {})