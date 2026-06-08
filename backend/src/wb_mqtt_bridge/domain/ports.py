"""Abstract ports for domain-infrastructure communication.

This module defines the interfaces (ports) that the domain layer uses to communicate
with external systems. These are implemented by adapters in the infrastructure layer.
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Generic, List, Optional

from wb_mqtt_bridge.domain.devices.config import BaseCommandConfig
from wb_mqtt_bridge.utils.types import CommandResponse, StateT


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


class DevicePort(ABC, Generic[StateT]):
    """Application-facing device contract used by the domain managers.

    Used by: DeviceManager, Scenario (the domain layer)
    Implemented by: infrastructure/devices/base.BaseDevice (every driver subclasses it)

    This is the seam the domain depends on — richer than a raw transport: device
    lifecycle (setup/shutdown), command execution, state access and message
    routing. A driver's specific transport (MQTT, HTTP, serial, …) is a private
    concern hidden behind these methods.
    """

    @abstractmethod
    def get_id(self) -> str:
        """Return the device's unique identifier."""
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Return the device's human-readable name."""
        pass

    @abstractmethod
    def get_room(self) -> Optional[str]:
        """Return the device's room id (matching an entry in `rooms.json`), or `None`
        when the device hasn't been assigned to a room yet. Mirrors `get_id` /
        `get_name` -- the domain contract for a flat attribute projected from the
        device's config. RoomManager + ScenarioManager call this through the port
        instead of reaching into the concrete BaseDevice's `.config.room`, keeping
        the hexagonal boundary intact (no domain → infrastructure reach).
        """
        pass

    @abstractmethod
    async def setup(self) -> bool:
        """Initialise the device (connect, subscribe, restore state)."""
        pass

    @abstractmethod
    async def shutdown(self) -> bool:
        """Tear the device down and release its resources."""
        pass

    @abstractmethod
    def subscribe_topics(self) -> List[str]:
        """Return the MQTT topic patterns this device subscribes to."""
        pass

    @abstractmethod
    async def handle_message(self, topic: str, payload: str) -> None:
        """Handle an incoming message on one of the device's topics."""
        pass

    @abstractmethod
    def get_current_state(self) -> StateT:
        """Return the current device state."""
        pass

    @abstractmethod
    def register_state_change_callback(self, callback: Callable) -> None:
        """Register a callback invoked when the device state changes."""
        pass

    @abstractmethod
    async def execute_action(
        self,
        action: str,
        params: Optional[Dict[str, Any]] = None,
        source: str = "unknown",
    ) -> CommandResponse[StateT]:
        """Execute a named action and return the resulting CommandResponse."""
        pass

    @abstractmethod
    def get_available_commands(self) -> Dict[str, BaseCommandConfig]:
        """Return the device's available commands keyed by name."""
        pass


class EventPublisherPort(ABC):
    """Port for publishing device events to live subscribers (SSE today).

    Used by: device drivers (BaseDevice), to surface state changes + progress.
    Implemented by: presentation/api/sse_manager.SSEManager.

    Domain-framed on purpose: callers say "a device event happened", not "broadcast
    on the DEVICES SSE channel" — the channel is the adapter's concern.
    """

    @abstractmethod
    async def publish_device_event(
        self, event_type: str, data: Any, event_id: Optional[str] = None
    ) -> None:
        """Publish a device event (e.g. 'state_change') to device subscribers."""
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