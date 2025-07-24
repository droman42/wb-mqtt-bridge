from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# Create router with appropriate prefix and tags
router = APIRouter(
    tags=["Rooms"]
)

# Global reference that will be set during initialization
room_manager = None

def initialize(room_mgr):
    """Initialize global references needed by router endpoints."""
    global room_manager
    room_manager = room_mgr

class RoomDefinitionResponse(BaseModel):
    """Response model for room definitions."""
    room_id: str
    names: Dict[str, str]
    description: str
    devices: List[str]
    default_scenario: Optional[str] = None

@router.get("/room/list", response_model=List[RoomDefinitionResponse])
async def list_rooms():
    """
    Get a list of all room definitions.
    
    Returns:
        List[RoomDefinitionResponse]: List of room definitions
        
    Raises:
        HTTPException: If service not initialized
    """
    if not room_manager:
        raise HTTPException(status_code=503, detail="Service not fully initialized")
    
    return room_manager.list()

@router.get("/room/{room_id}", response_model=RoomDefinitionResponse)
async def get_room(room_id: str):
    """
    Get a specific room definition.
    
    Args:
        room_id: The ID of the room to retrieve
        
    Returns:
        RoomDefinitionResponse: The room definition
        
    Raises:
        HTTPException: If room not found or service not initialized
    """
    if not room_manager:
        raise HTTPException(status_code=503, detail="Service not fully initialized")
    
    room = room_manager.get(room_id)
    if not room:
        raise HTTPException(status_code=404, detail=f"Room '{room_id}' not found")
    
    return room 