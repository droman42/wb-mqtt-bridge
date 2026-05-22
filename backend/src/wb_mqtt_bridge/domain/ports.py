"""Abstract ports for domain-infrastructure communication.

This module defines the interfaces (ports) that the domain layer uses to communicate
with external systems. These are implemented by adapters in the infrastructure layer.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Callable, List


class MessageBusPort(ABC):
    """Port for publish/subscribe operations to external message bus (MQTT today).
    
    Used by: ScenarioManager, RoomManager, future notification services
    Implemented by: infrastructure/mqtt/client.MQTTClient
    """
    
    @abstractmethod
    async def publish(
        self, 
        topic: str, 
        payload: str, 
        qos: int = 0, 
        retain: bool = False
    ) -> None:
        """Publish a message to the message bus.
        
        Args:
            topic: The topic to publish to
            payload: The message payload
            qos: Quality of service level (0, 1, or 2)
            retain: Whether the message should be retained
        """
        pass
    
    @abstractmethod
    async def subscribe(
        self, 
        topic: str, 
        callback: Callable[[str, str], None]
    ) -> None:
        """Subscribe to a topic on the message bus.
        
        Args:
            topic: The topic pattern to subscribe to
            callback: Function to call when messages arrive (topic, payload)
        """
        pass
    
    @abstractmethod
    async def connect(self) -> bool:
        """Connect to the message bus.
        
        Returns:
            True if connection successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the message bus."""
        pass


class DeviceBusPort(ABC):
    """Port for low-level device communication operations.
    
    Used by: Device drivers only
    Implemented by: every file in infrastructure/devices/*/driver.py
    
    This port defines the interface that device drivers must implement
    to communicate with their specific transport (MQTT, HTTP, Serial, etc.)
    """
    
    @abstractmethod
    async def send(self, command: str, params: Dict[str, Any]) -> Any:
        """Send a command to the device.
        
        Args:
            command: The command identifier
            params: Command parameters
            
        Returns:
            Command result or response
        """
        pass
    
    @abstractmethod
    def subscribe_topics(self) -> List[str]:
        """Get the list of topics this device should subscribe to.
        
        Returns:
            List of topic patterns for subscription
        """
        pass
    
    @abstractmethod
    async def handle_message(self, topic: str, payload: str) -> None:
        """Handle an incoming message from the device's topics.
        
        Args:
            topic: The topic the message arrived on
            payload: The message payload
        """
        pass


class StateRepositoryPort(ABC):
    """Port for persisting and retrieving aggregate/device state.
    
    Used by: DeviceManager, ScenarioManager
    Implemented by: infrastructure/persistence/sqlite.SQLiteStateStore
    """
    
    @abstractmethod
    async def load(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Load state for an entity by ID.
        
        Args:
            entity_id: Unique identifier for the entity
            
        Returns:
            Entity state dictionary or None if not found
        """
        pass
    
    @abstractmethod
    async def save(self, entity_id: str, state: Dict[str, Any]) -> None:
        """Save state for an entity.
        
        Args:
            entity_id: Unique identifier for the entity
            state: State dictionary to persist
        """
        pass
    
    @abstractmethod
    async def bulk_save(self, states: Dict[str, Dict[str, Any]]) -> None:
        """Save multiple entity states in a single operation.
        
        Args:
            states: Dictionary mapping entity_id to state dictionary
        """
        pass
    
    @abstractmethod
    async def delete(self, entity_id: str) -> None:
        """Delete state for an entity.
        
        Args:
            entity_id: Unique identifier for the entity to delete
        """
        pass
    
    @abstractmethod
    async def list_entities(self) -> List[str]:
        """List all entity IDs that have persisted state.
        
        Returns:
            List of entity identifiers
        """
        pass
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the state repository (create tables, etc.)."""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Close the state repository and clean up resources."""
        pass 