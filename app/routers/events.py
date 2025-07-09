import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Request, HTTPException, Depends, Path, Body
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.sse_manager import sse_manager, SSEChannel

logger = logging.getLogger(__name__)

# Pydantic models for Swagger documentation
class SSEStats(BaseModel):
    """SSE connection statistics response model"""
    active_connections: Dict[str, int] = Field(
        description="Number of active connections per channel",
        example={"devices": 3, "scenarios": 1, "system": 2}
    )
    total_connections: int = Field(
        description="Total number of active connections across all channels",
        example=6
    )
    channels: List[str] = Field(
        description="List of available SSE channels",
        example=["devices", "scenarios", "system"]
    )

class TestEventData(BaseModel):
    """Test event data model for broadcasting"""
    message: str = Field(
        description="Test message content",
        example="This is a test event"
    )
    timestamp: Optional[str] = Field(
        description="Optional timestamp for the event",
        example="2024-01-01T12:00:00Z"
    )
    data: Optional[Dict[str, Any]] = Field(
        description="Optional additional data",
        example={"key": "value", "number": 42}
    )

class BroadcastResponse(BaseModel):
    """Response model for test broadcast operations"""
    status: str = Field(description="Operation status", example="success")
    message: str = Field(
        description="Descriptive message about the operation",
        example="Test event broadcasted to devices channel"
    )
    active_connections: int = Field(
        description="Number of active connections that received the event",
        example=3
    )

router = APIRouter(
    prefix="/events", 
    tags=["Server-Sent Events"],
    responses={
        503: {
            "description": "Service Unavailable - SSE service not initialized",
            "content": {
                "application/json": {
                    "example": {"detail": "SSE service not initialized"}
                }
            }
        }
    }
)

# Global dependencies will be injected here
_initialized = False

def check_initialized():
    """
    Check if the router has been initialized with dependencies.
    
    Raises:
        HTTPException: 503 status if the SSE service is not initialized
    """
    if not _initialized:
        raise HTTPException(status_code=503, detail="SSE service not initialized")

def initialize():
    """
    Initialize the SSE router.
    
    This function must be called during application startup to enable
    Server-Sent Events functionality. It sets up the necessary connections
    and marks the service as ready to handle client connections.
    """
    global _initialized
    _initialized = True
    logger.info("SSE events router initialized")

@router.get(
    "/devices",
    response_class=StreamingResponse,
    summary="Device Events Stream",
    description="Subscribe to real-time device events via Server-Sent Events"
)
async def devices_stream(request: Request):
    """
    Server-Sent Events stream for device-related events.
    
    This endpoint provides a persistent connection for real-time updates about:
    
    - **Device State Changes**: Power on/off, volume adjustments, input switching
    - **Connection Events**: Device connect/disconnect notifications
    - **Command Results**: Success/failure status of device commands
    - **Setup Events**: Device initialization and shutdown notifications
    - **Error States**: Device malfunction and error reporting
    - **Manager Operations**: Device manager lifecycle events
    
    The stream uses the SSE (Server-Sent Events) protocol, making it compatible
    with web browsers and standard HTTP clients. Events are sent as JSON objects
    with 'event', 'data', and optional 'id' fields.
    
    **Connection Management:**
    - The connection will remain open until the client disconnects
    - Automatic reconnection is supported by SSE-compatible clients
    - The server will clean up resources when clients disconnect
    
    **Event Format:**
    ```
    event: device_state_change
    data: {"device_id": "tv_1", "property": "power", "value": true, "timestamp": "2024-01-01T12:00:00Z"}
    ```
    
    Args:
        request: FastAPI request object (used for connection management)
        
    Returns:
        StreamingResponse: SSE stream with Content-Type: text/event-stream
        
    Raises:
        HTTPException: 503 if SSE service is not initialized
    """
    check_initialized()
    logger.info("New client connected to devices SSE stream")
    return await sse_manager.create_event_stream(SSEChannel.DEVICES, request)

@router.get(
    "/scenarios",
    response_class=StreamingResponse,
    summary="Scenario Events Stream",
    description="Subscribe to real-time scenario events via Server-Sent Events"
)
async def scenarios_stream(request: Request):
    """
    Server-Sent Events stream for scenario-related events.
    
    This endpoint provides real-time updates for scenario management including:
    
    - **Scenario State Changes**: Active/inactive status updates
    - **Switching Events**: Notifications when scenarios are activated/deactivated
    - **Execution Progress**: Step-by-step scenario execution updates
    - **Manager Operations**: Scenario manager lifecycle and configuration changes
    
    Scenarios represent predefined configurations that control multiple devices
    simultaneously (e.g., "Movie Night", "Sleep Mode", "Party Mode").
    
    **Event Examples:**
    - Scenario activation: When a scenario is triggered
    - Scenario completion: When all scenario actions have been executed
    - Scenario conflicts: When scenarios interfere with each other
    - Scenario updates: When scenario definitions are modified
    
    Args:
        request: FastAPI request object (used for connection management)
        
    Returns:
        StreamingResponse: SSE stream with Content-Type: text/event-stream
        
    Raises:
        HTTPException: 503 if SSE service is not initialized
    """
    check_initialized()
    logger.info("New client connected to scenarios SSE stream")
    return await sse_manager.create_event_stream(SSEChannel.SCENARIOS, request)

@router.get(
    "/system",
    response_class=StreamingResponse,
    summary="System Events Stream",
    description="Subscribe to real-time system-wide events via Server-Sent Events"
)
async def system_stream(request: Request):
    """
    Server-Sent Events stream for system-wide events.
    
    This endpoint provides real-time updates for system-level operations:
    
    - **Startup/Shutdown Events**: System initialization and termination
    - **Configuration Reloads**: When system configuration is updated
    - **Maintenance Events**: Scheduled maintenance and system updates
    - **Status Updates**: General system health and status information
    - **Service Events**: Individual service start/stop notifications
    
    **System Event Categories:**
    - **Health**: CPU, memory, disk usage updates
    - **Services**: Individual service status changes
    - **Configuration**: Configuration file changes and reloads
    - **Security**: Authentication and authorization events
    - **Performance**: System performance metrics and alerts
    
    Args:
        request: FastAPI request object (used for connection management)
        
    Returns:
        StreamingResponse: SSE stream with Content-Type: text/event-stream
        
    Raises:
        HTTPException: 503 if SSE service is not initialized
    """
    check_initialized()
    logger.info("New client connected to system SSE stream")
    return await sse_manager.create_event_stream(SSEChannel.SYSTEM, request)

@router.get(
    "/stats",
    response_model=SSEStats,
    summary="SSE Connection Statistics",
    description="Get current statistics about active Server-Sent Events connections",
    responses={
        200: {
            "description": "Connection statistics retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "active_connections": {"devices": 3, "scenarios": 1, "system": 2},
                        "total_connections": 6,
                        "channels": ["devices", "scenarios", "system"]
                    }
                }
            }
        }
    }
)
async def get_sse_stats():
    """
    Get statistics about active SSE connections.
    
    This endpoint provides insights into the current state of Server-Sent Events
    connections across all channels. Useful for monitoring system load and
    debugging connection issues.
    
    **Statistics Include:**
    - Number of active connections per channel
    - Total connection count across all channels  
    - List of available channels
    
    **Use Cases:**
    - Monitoring system load and client activity
    - Debugging connection issues
    - Capacity planning for SSE infrastructure
    - Health checks and system diagnostics
    
    Returns:
        SSEStats: Connection statistics object containing:
            - active_connections: Dict mapping channel names to connection counts
            - total_connections: Sum of all active connections
            - channels: List of available SSE channels
            
    Raises:
        HTTPException: 503 if SSE service is not initialized
    """
    check_initialized()
    stats = await sse_manager.get_channel_stats()
    return {
        "active_connections": stats,
        "total_connections": sum(stats.values()),
        "channels": list(stats.keys())
    }

@router.post(
    "/test/{channel}",
    response_model=BroadcastResponse,
    summary="Broadcast Test Event",
    description="Send a test event to a specific SSE channel for development and testing",
    responses={
        200: {
            "description": "Test event broadcasted successfully",
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "message": "Test event broadcasted to devices channel",
                        "active_connections": 3
                    }
                }
            }
        },
        400: {
            "description": "Invalid channel name provided",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid channel: invalid_channel"}
                }
            }
        }
    }
)
async def test_broadcast(
    channel: str = Path(
        description="SSE channel to broadcast to",
        example="devices",
        regex="^(devices|scenarios|system)$"
    ),
    data: TestEventData = Body(
        description="Test event data to broadcast to connected clients",
        example={
            "message": "This is a test event",
            "timestamp": "2024-01-01T12:00:00Z",
            "data": {"test": True, "sequence": 1}
        }
    )
):
    """
    Test endpoint to broadcast a test event to a specific channel.
    
    This endpoint is designed for development and testing of SSE functionality.
    It allows developers to send custom events to any SSE channel and verify
    that clients are receiving events correctly.
    
    **Available Channels:**
    - `devices`: For device-related test events
    - `scenarios`: For scenario-related test events  
    - `system`: For system-wide test events
    
    **Event Broadcasting:**
    - Events are sent to all currently connected clients on the specified channel
    - The event type is automatically set to "test"
    - Custom data can be included in the event payload
    - Response includes the number of clients that received the event
    
    **Testing Workflow:**
    1. Connect to an SSE stream (e.g., GET /events/devices)
    2. Send a test event using this endpoint
    3. Verify the event is received by the SSE client
    4. Check the response for delivery confirmation
    
    Args:
        channel: The SSE channel to broadcast to (devices, scenarios, or system)
        data: Test event data containing message, timestamp, and optional payload
        
    Returns:
        BroadcastResponse: Status information including:
            - status: Operation result ("success" or "error")
            - message: Descriptive message about the operation
            - active_connections: Number of clients that received the event
            
    Raises:
        HTTPException: 400 if an invalid channel name is provided
        HTTPException: 503 if SSE service is not initialized
    """
    check_initialized()
    
    try:
        sse_channel = SSEChannel(channel)
    except ValueError:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid channel: {channel}. Valid channels are: {', '.join([c.value for c in SSEChannel])}"
        )
    
    # Convert Pydantic model to dict for broadcasting
    event_data = data.dict()
    
    await sse_manager.broadcast(
        channel=sse_channel,
        event_type="test",
        data=event_data
    )
    
    stats = await sse_manager.get_channel_stats()
    return {
        "status": "success",
        "message": f"Test event broadcasted to {channel} channel",
        "active_connections": stats.get(channel, 0)
    } 