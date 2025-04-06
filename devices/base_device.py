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