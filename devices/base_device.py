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
    
    async def execute_action(self, button: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute an action identified by button name."""
        try:
            # Simulate MQTT message for the button
            device_alias = self.config.get('alias', self.device_name)
            topic = f"/devices/{device_alias}/controls/{button}"
            
            # Default payload for button press
            payload = "1"
            
            # Handle the message and get MQTT command if any
            result = await self.handle_message(topic, payload)
            
            return {
                "success": True,
                "device_id": self.device_id,
                "button": button,
                "mqtt_command": result,
                "state": self.get_state()
            }
            
        except Exception as e:
            logger.error(f"Error executing action {button} for device {self.device_id}: {str(e)}")
            return {
                "success": False,
                "device_id": self.device_id,
                "button": button,
                "error": str(e)
            } 