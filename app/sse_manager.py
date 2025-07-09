import asyncio
import json
import logging
from typing import Dict, Set, Any, Optional
from datetime import datetime
from enum import Enum
from fastapi import Request
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

class SSEChannel(str, Enum):
    """Available SSE channels"""
    DEVICES = "devices"
    SCENARIOS = "scenarios" 
    SYSTEM = "system"

class SSEEvent:
    """Represents a Server-Sent Event"""
    
    def __init__(self, event_type: str, data: Any, channel: SSEChannel, id: Optional[str] = None):
        self.event_type = event_type
        self.data = data
        self.channel = channel
        self.id = id or str(int(datetime.now().timestamp() * 1000))
        self.timestamp = datetime.now()
    
    def format(self) -> str:
        """Format the event for SSE transmission"""
        lines = []
        
        if self.id:
            lines.append(f"id: {self.id}")
        
        lines.append(f"event: {self.event_type}")
        
        # Convert data to JSON if it's not already a string
        if isinstance(self.data, str):
            data_str = self.data
        else:
            data_str = json.dumps(self.data)
        
        # Handle multi-line data
        for line in data_str.split('\n'):
            lines.append(f"data: {line}")
        
        lines.append("")  # Empty line to end the event
        return "\n".join(lines)

class SSEManager:
    """Manages Server-Sent Event connections and broadcasting"""
    
    def __init__(self):
        # Active connections per channel
        self._connections: Dict[SSEChannel, Set[asyncio.Queue]] = {
            SSEChannel.DEVICES: set(),
            SSEChannel.SCENARIOS: set(),
            SSEChannel.SYSTEM: set()
        }
        self._connection_lock = asyncio.Lock()
    
    async def add_connection(self, channel: SSEChannel, queue: asyncio.Queue) -> None:
        """Add a new SSE connection to a channel"""
        async with self._connection_lock:
            self._connections[channel].add(queue)
            logger.info(f"New SSE connection added to {channel.value} channel. Total: {len(self._connections[channel])}")
    
    async def remove_connection(self, channel: SSEChannel, queue: asyncio.Queue) -> None:
        """Remove an SSE connection from a channel"""
        async with self._connection_lock:
            self._connections[channel].discard(queue)
            logger.info(f"SSE connection removed from {channel.value} channel. Total: {len(self._connections[channel])}")
    
    async def broadcast(self, channel: SSEChannel, event_type: str, data: Any, event_id: Optional[str] = None) -> None:
        """Broadcast an event to all connections on a channel"""
        if channel not in self._connections:
            logger.warning(f"Unknown SSE channel: {channel}")
            return
        
        event = SSEEvent(event_type, data, channel, event_id)
        formatted_event = event.format()
        
        async with self._connection_lock:
            connections = self._connections[channel].copy()
        
        if not connections:
            logger.debug(f"No active connections for {channel.value} channel")
            return
        
        logger.debug(f"Broadcasting {event_type} event to {len(connections)} connections on {channel.value} channel")
        
        # Send to all active connections
        dead_connections = set()
        for queue in connections:
            try:
                await queue.put(formatted_event)
            except Exception as e:
                logger.warning(f"Failed to send event to connection: {e}")
                dead_connections.add(queue)
        
        # Clean up dead connections
        if dead_connections:
            async with self._connection_lock:
                for dead_queue in dead_connections:
                    self._connections[channel].discard(dead_queue)
            logger.info(f"Removed {len(dead_connections)} dead connections from {channel.value} channel")
    
    async def get_channel_stats(self) -> Dict[str, int]:
        """Get connection statistics for all channels"""
        async with self._connection_lock:
            return {
                channel.value: len(connections) 
                for channel, connections in self._connections.items()
            }
    
    async def create_event_stream(self, channel: SSEChannel, request: Request):
        """Create an SSE event stream for a specific channel"""
        queue = asyncio.Queue(maxsize=100)  # Limit queue size to prevent memory issues
        
        await self.add_connection(channel, queue)
        
        async def event_generator():
            try:
                # Send initial connection event
                welcome_event = SSEEvent(
                    event_type="connected",
                    data={"message": f"Connected to {channel.value} channel", "timestamp": datetime.now().isoformat()},
                    channel=channel
                )
                yield welcome_event.format()
                
                while True:
                    # Check if client disconnected
                    if await request.is_disconnected():
                        logger.info(f"Client disconnected from {channel.value} channel")
                        break
                    
                    try:
                        # Wait for new events with timeout
                        event_data = await asyncio.wait_for(queue.get(), timeout=30.0)
                        yield event_data
                    except asyncio.TimeoutError:
                        # Send keepalive event
                        keepalive_event = SSEEvent(
                            event_type="keepalive",
                            data={"timestamp": datetime.now().isoformat()},
                            channel=channel
                        )
                        yield keepalive_event.format()
                        
            except Exception as e:
                logger.error(f"Error in SSE event stream for {channel.value}: {e}")
            finally:
                await self.remove_connection(channel, queue)
        
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Cache-Control"
            }
        )

# Global SSE manager instance
sse_manager = SSEManager() 