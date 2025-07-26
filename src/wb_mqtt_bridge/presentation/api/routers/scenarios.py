import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from wb_mqtt_bridge.domain.scenarios.models import ScenarioDefinition
from wb_mqtt_bridge.domain.scenarios.scenario import ScenarioError, ScenarioExecutionError
from wb_mqtt_bridge.infrastructure.scenarios.models import ScenarioWBConfig
from wb_mqtt_bridge.presentation.api.sse_manager import sse_manager, SSEChannel

# Create logger for this module
logger = logging.getLogger(__name__)

# Create router with appropriate prefix and tags
router = APIRouter(
    tags=["Scenarios"]
)

# Global references that will be set during initialization
scenario_manager = None
room_manager = None
mqtt_client = None
scenario_wb_adapter = None

def initialize(scenario_mgr, room_mgr, mqt_client, scenario_wb_adptr=None):
    """Initialize global references needed by router endpoints."""
    global scenario_manager, room_manager, mqtt_client, scenario_wb_adapter
    scenario_manager = scenario_mgr
    room_manager = room_mgr
    mqtt_client = mqt_client
    scenario_wb_adapter = scenario_wb_adptr

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

class StartScenarioRequest(BaseModel):
    """Request model for starting a scenario."""
    id: str

class ShutdownScenarioRequest(BaseModel):
    """Request model for shutting down a scenario."""
    id: str
    graceful: bool = True

def check_initialized():
    """Check if the router is properly initialized with required dependencies."""
    if not scenario_manager:
        raise HTTPException(
            status_code=503, 
            detail="Scenario service not fully initialized"
        )

@router.get("/scenario/definition/{id}", response_model=ScenarioDefinition)
async def get_scenario_definition(id: str):
    """
    Get the definition of a specific scenario.
    
    Returns:
        ScenarioDefinition: The scenario definition
        
    Raises:
        HTTPException: If scenario not found or service not initialized
    """
    check_initialized()
    
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
    check_initialized()
    
    try:
        await scenario_manager.switch_scenario(data.id, graceful=data.graceful)
        
        # Broadcast scenario state change via SSE
        if scenario_manager.scenario_state:
            await sse_manager.broadcast(
                channel=SSEChannel.SCENARIOS,
                event_type="scenario_switched",
                data={
                    "scenario_id": data.id,
                    "state": scenario_manager.scenario_state.model_dump(),
                    "timestamp": datetime.now().isoformat()
                }
            )
        
        return ScenarioResponse(
            status="success",
            message=f"Successfully switched to scenario '{data.id}'"
        )
    except ValueError as e:
        # Scenario not found
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        # Log the full error with traceback for server logs
        logger.error(f"Error switching to scenario {data.id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to switch scenario: {str(e)}")

@router.post("/scenario/start", response_model=ScenarioResponse)
async def start_scenario(data: StartScenarioRequest):
    """
    Start a scenario if no scenario is currently active.
    
    This endpoint starts a scenario only if there is no currently active scenario.
    If a scenario is already running, it returns an error.
    
    Args:
        data: The start scenario request with scenario ID
        
    Returns:
        ScenarioResponse: Status of the operation
        
    Raises:
        HTTPException: If scenario not found, another scenario is active, or an error occurs
    """
    check_initialized()
    
    # Check if scenario exists
    if data.id not in scenario_manager.scenario_definitions:
        raise HTTPException(status_code=404, detail=f"Scenario '{data.id}' not found")
    
    # Check if another scenario is already active
    if scenario_manager.current_scenario:
        raise HTTPException(
            status_code=409, 
            detail=f"Cannot start scenario '{data.id}': scenario '{scenario_manager.current_scenario.scenario_id}' is already active"
        )
    
    try:
        # Use switch_scenario to start the scenario (since no current scenario exists)
        await scenario_manager.switch_scenario(data.id, graceful=True)
        
        # Broadcast scenario state change via SSE
        if scenario_manager.scenario_state:
            await sse_manager.broadcast(
                channel=SSEChannel.SCENARIOS,
                event_type="scenario_started",
                data={
                    "scenario_id": data.id,
                    "state": scenario_manager.scenario_state.model_dump(),
                    "timestamp": datetime.now().isoformat()
                }
            )
        
        return ScenarioResponse(
            status="success",
            message=f"Successfully started scenario '{data.id}'"
        )
    except Exception as e:
        # Log the full error with traceback for server logs
        logger.error(f"Error starting scenario {data.id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to start scenario: {str(e)}")

@router.post("/scenario/shutdown", response_model=ScenarioResponse)
async def shutdown_scenario(data: ShutdownScenarioRequest):
    """
    Shutdown the currently active scenario.
    
    This endpoint shuts down the currently active scenario if it matches the provided ID.
    If no scenario is active or the active scenario doesn't match the provided ID, 
    it returns an appropriate error.
    
    Args:
        data: The shutdown scenario request with scenario ID and graceful flag
        
    Returns:
        ScenarioResponse: Status of the operation
        
    Raises:
        HTTPException: If no active scenario, scenario mismatch, or an error occurs
    """
    check_initialized()
    
    # Check if any scenario is currently active
    if not scenario_manager.current_scenario:
        raise HTTPException(status_code=404, detail="No scenario is currently active")
    
    # Check if the active scenario matches the requested shutdown ID
    if scenario_manager.current_scenario.scenario_id != data.id:
        raise HTTPException(
            status_code=409, 
            detail=f"Cannot shutdown scenario '{data.id}': scenario '{scenario_manager.current_scenario.scenario_id}' is currently active"
        )
    
    try:
        current_scenario_id = scenario_manager.current_scenario.scenario_id
        
        # Shutdown the current scenario
        await scenario_manager.shutdown()
        
        # Broadcast scenario state change via SSE
        await sse_manager.broadcast(
            channel=SSEChannel.SCENARIOS,
            event_type="scenario_shutdown",
            data={
                "scenario_id": current_scenario_id,
                "timestamp": datetime.now().isoformat()
            }
        )
        
        return ScenarioResponse(
            status="success",
            message=f"Successfully shut down scenario '{current_scenario_id}'"
        )
    except Exception as e:
        # Log the full error with traceback for server logs
        logger.error(f"Error shutting down scenario {data.id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to shutdown scenario: {str(e)}")

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
    check_initialized()
    
    try:
        result = await scenario_manager.execute_role_action(data.role, data.command, data.params)
        
        # Broadcast scenario state update via SSE
        if scenario_manager.scenario_state:
            await sse_manager.broadcast(
                channel=SSEChannel.SCENARIOS,
                event_type="role_action_executed",
                data={
                    "role": data.role,
                    "command": data.command,
                    "params": data.params,
                    "state": scenario_manager.scenario_state.model_dump(),
                    "timestamp": datetime.now().isoformat()
                }
            )
            
        return {"status": "success", "result": result}
    except ScenarioExecutionError as e:
        # Specifically handle execution errors
        logger.error(
            f"Execution error for role {data.role}, command {data.command}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Command execution failed: {str(e)}")
    except ScenarioError as e:
        # Map error types to appropriate HTTP status codes
        error_status_map = {
            "invalid_role": 400,
            "missing_device": 404,
            "no_active_scenario": 400,
            "execution": 500
        }
        status_code = error_status_map.get(e.error_type, 500)
        raise HTTPException(status_code=status_code, detail=str(e))
    except Exception as e:
        # Log any other exceptions
        logger.error(
            f"Error executing role action {data.role}.{data.command}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Failed to execute action: {str(e)}")

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
    check_initialized()
    
    try:
        if room:
            scenarios = []
            for scenario_id, definition in scenario_manager.scenario_definitions.items():
                if definition.room_id == room:
                    scenarios.append(definition)
            return scenarios
        else:
            return list(scenario_manager.scenario_definitions.values())
    except Exception as e:
        logger.error(f"Error retrieving scenario definitions: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve scenarios: {str(e)}") 

@router.get("/scenario/virtual_config/{id}", response_model=ScenarioWBConfig)
async def get_scenario_virtual_config(id: str):
    """
    Get the virtual WB device configuration for a specific scenario.
    
    This endpoint returns the virtual BaseDeviceConfig-compatible configuration
    that represents how a scenario appears as a WB virtual device. The configuration
    is generated dynamically from the scenario definition and includes:
    - Virtual commands (startup/shutdown and role-based commands)
    - WB control metadata and types
    - Parameter definitions inherited from role devices
    
    Args:
        id: Scenario ID to get virtual config for
        
    Returns:
        ScenarioWBConfig: The virtual WB device configuration
        
    Raises:
        HTTPException: If scenario not found, service not initialized, or error occurs
    """
    check_initialized()
    
    # Check if scenario exists
    if id not in scenario_manager.scenario_definitions:
        raise HTTPException(status_code=404, detail=f"Scenario '{id}' not found")
    
    try:
        # Check if we have an active virtual config for this scenario
        if scenario_wb_adapter and hasattr(scenario_wb_adapter, 'get_active_virtual_configs'):
            active_configs = scenario_wb_adapter.get_active_virtual_configs()
            if id in active_configs:
                return active_configs[id]
        
        # Generate virtual config on-demand if not active
        scenario_definition = scenario_manager.scenario_definitions[id]
        
        # We need the device manager to generate virtual configs
        # Access it through the scenario manager or scenario wb adapter
        if not scenario_wb_adapter:
            raise HTTPException(
                status_code=503, 
                detail="Scenario WB adapter not available - virtual configs cannot be generated"
            )
        
        # Generate virtual config using the adapter's device manager
        virtual_config = ScenarioWBConfig.from_scenario(
            scenario_definition, 
            scenario_wb_adapter.device_manager
        )
        
        return virtual_config
        
    except Exception as e:
        logger.error(f"Error generating virtual config for scenario {id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to generate virtual config for scenario: {str(e)}"
        )

@router.get("/scenario/virtual_configs", response_model=Dict[str, ScenarioWBConfig])
async def get_all_scenario_virtual_configs():
    """
    Get virtual WB device configurations for all available scenarios.
    
    This endpoint returns a mapping of scenario IDs to their virtual WB device
    configurations. For scenarios that are currently active, it returns the
    cached configuration. For inactive scenarios, it generates the configuration
    on-demand.
    
    Returns:
        Dict[str, ScenarioWBConfig]: Mapping of scenario ID to virtual config
        
    Raises:
        HTTPException: If service not initialized or error occurs
    """
    check_initialized()
    
    if not scenario_wb_adapter:
        raise HTTPException(
            status_code=503, 
            detail="Scenario WB adapter not available - virtual configs cannot be generated"
        )
    
    try:
        virtual_configs = {}
        
        # Get active virtual configs first
        active_configs = scenario_wb_adapter.get_active_virtual_configs()
        virtual_configs.update(active_configs)
        
        # Generate configs for scenarios that don't have active configs
        for scenario_id, scenario_definition in scenario_manager.scenario_definitions.items():
            if scenario_id not in virtual_configs:
                virtual_config = ScenarioWBConfig.from_scenario(
                    scenario_definition, 
                    scenario_wb_adapter.device_manager
                )
                virtual_configs[scenario_id] = virtual_config
        
        return virtual_configs
        
    except Exception as e:
        logger.error(f"Error generating virtual configs for scenarios: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to generate virtual configs: {str(e)}"
        ) 