from abc import ABC, abstractmethod
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

class BaseDevice(ABC):
    """Base class for all device implementations."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.device_id = config.get('device_id', 'unknown')
        self.device_name = config.get('device_name', 'unknown')
        self.state = {}  # Device state storage
    
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
    
    @abstractmethod
    def subscribe_topics(self) -> List[str]:
        """Define the MQTT topics this device should subscribe to."""
        pass
    
    @abstractmethod
    async def handle_message(self, topic: str, payload: str):
        """Handle incoming MQTT messages for this device."""
        pass
    
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
            # Simulate MQTT message for the action
            device_alias = self.config.get('alias', self.device_name)
            topic = f"/devices/{device_alias}/controls/{action}"
            
            # Default payload for action press
            payload = "1"
            
            # Handle the message and get MQTT command if any
            logger.debug(f"Executing action {action} for device {self.device_id} with topic {topic} and payload {payload}")
            result = await self.handle_message(topic, payload)
            
            return {
                "success": True,
                "device_id": self.device_id,
                "action": action,
                "mqtt_command": result,
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