import logging
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel

from app.scenario_models import ScenarioDefinition, ScenarioState
from app.scenario import ScenarioError

# Create router with appropriate prefix and tags
router = APIRouter(
    tags=["Scenarios"]
)

# Global references that will be set during initialization
scenario_manager = None
room_manager = None
mqtt_client = None

def initialize(scenario_mgr, room_mgr, mqt_client):
    """Initialize global references needed by router endpoints."""
    global scenario_manager, room_manager, mqtt_client
    scenario_manager = scenario_mgr
    room_manager = room_mgr
    mqtt_client = mqt_client

# Request and response models
class SwitchScenarioRequest(BaseModel):
    """Request model for switching scenarios."""
    id: str
    graceful: bool = True

class ActionRequest(BaseModel):
    """Request model for executing a role action."""
    role: str
    command: str
    params: Dict[str, Any] = {}

class ScenarioResponse(BaseModel):
    """Base response model for scenario operations."""
    status: str
    message: str

@router.get("/scenario/definition/{id}", response_model=ScenarioDefinition)
async def get_scenario_definition(id: str):
    """
    Get the definition of a specific scenario.
    
    Returns:
        ScenarioDefinition: The scenario definition
        
    Raises:
        HTTPException: If scenario not found or service not initialized
    """
    if not scenario_manager:
        raise HTTPException(status_code=503, detail="Service not fully initialized")
    
    if id not in scenario_manager.scenario_definitions:
        raise HTTPException(status_code=404, detail=f"Scenario '{id}' not found")
    
    return scenario_manager.scenario_definitions[id]

@router.post("/scenario/switch", response_model=ScenarioResponse)
async def switch_scenario(data: SwitchScenarioRequest):
    """
    Switch to a different scenario.
    
    This endpoint performs a transition between scenarios, handling
    device state changes efficiently.
    
    Args:
        data: The switch scenario request with scenario ID and graceful flag
        
    Returns:
        ScenarioResponse: Status of the operation
        
    Raises:
        HTTPException: If scenario not found or an error occurs
    """
    if not scenario_manager:
        raise HTTPException(status_code=503, detail="Service not fully initialized")
    
    try:
        await scenario_manager.switch_scenario(data.id, graceful=data.graceful)
        
        # Publish state change on MQTT if a client is available
        if mqtt_client and scenario_manager.scenario_state:
            topic = f"scenario/state"
            payload = scenario_manager.scenario_state.model_dump()
            await mqtt_client.publish(topic, payload)
        
        return ScenarioResponse(
            status="success",
            message=f"Successfully switched to scenario '{data.id}'"
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error switching to scenario {data.id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/scenario/role_action", response_model=Dict[str, Any])
async def execute_role_action(data: ActionRequest):
    """
    Execute an action on a device bound to a role in the current scenario.
    
    Args:
        data: The role action request with role, command and params
        
    Returns:
        Dict[str, Any]: The result of the command execution
        
    Raises:
        HTTPException: If no active scenario or an error occurs
    """
    if not scenario_manager:
        raise HTTPException(status_code=503, detail="Service not fully initialized")
    
    try:
        result = await scenario_manager.execute_role_action(data.role, data.command, data.params)
        
        # Publish state change on MQTT if a client is available
        if mqtt_client and scenario_manager.scenario_state:
            topic = f"scenario/state/update"
            payload = scenario_manager.scenario_state.model_dump()
            await mqtt_client.publish(topic, payload)
            
        return {"status": "success", "result": result}
    except ScenarioError as e:
        status_code = 400 if e.error_type in ["invalid_role", "no_active_scenario"] else 500
        raise HTTPException(status_code=status_code, detail=str(e))
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error executing role action {data.role}.{data.command}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/scenario/definition", response_model=List[ScenarioDefinition])
async def get_scenarios_for_room(room: Optional[str] = Query(None, description="Filter scenarios by room ID")):
    """
    Get definitions of scenarios, optionally filtered by room.
    
    Args:
        room: Optional room ID to filter scenarios by
        
    Returns:
        List[ScenarioDefinition]: List of scenario definitions
        
    Raises:
        HTTPException: If service not initialized
    """
    if not scenario_manager:
        raise HTTPException(status_code=503, detail="Service not fully initialized")
    
    if room:
        scenarios = []
        for scenario_id, definition in scenario_manager.scenario_definitions.items():
            if definition.room_id == room:
                scenarios.append(definition)
        return scenarios
    else:
        return list(scenario_manager.scenario_definitions.values()) 