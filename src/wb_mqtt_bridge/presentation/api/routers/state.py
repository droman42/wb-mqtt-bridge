import logging
from typing import Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import RootModel

from wb_mqtt_bridge.domain.devices.models import BaseDeviceState
from wb_mqtt_bridge.domain.scenarios.models import ScenarioState

# Create a model for the persisted states dictionary
class PersistedStatesResponse(RootModel):
    """Model for the collection of persisted device states."""
    root: Dict[str, Dict[str, Any]]

# Create router with appropriate prefix and tags
router = APIRouter(
    tags=["State"]
)

# Global references that will be set during initialization
config_manager = None
device_manager = None
state_store = None
scenario_manager = None

def initialize(cfg_manager, dev_manager, state_st, scenario_mgr=None):
    """Initialize global references needed by router endpoints."""
    global config_manager, device_manager, state_store, scenario_manager
    config_manager = cfg_manager
    device_manager = dev_manager
    state_store = state_st
    scenario_manager = scenario_mgr

@router.get("/devices/{device_id}/state")
async def get_device_state(device_id: str):
    """Get information about a specific device's current state.
    
    Args:
        device_id: The ID of the device to retrieve
        
    Returns:
        Device-specific state (e.g., LgTvState, AppleTVState, EmotivaXMC2State, etc.)
        that extends BaseDeviceState with device-specific fields like volume, power,
        input sources, playback information, and other operational data.
        
    Raises:
        HTTPException: If device is not found or an error occurs
    """
    logger = logging.getLogger(__name__)
    if not device_manager:
        raise HTTPException(status_code=503, detail="Service not fully initialized")
    
    try:
        device = device_manager.get_device(device_id)
        if not device:
            raise HTTPException(status_code=404, detail=f"Device {device_id} not found")
            
        try:
            # Return the properly typed state directly
            return device.get_current_state()
        except Exception as e:
            logger.error(f"Error getting device state for {device_id}: {str(e)}")
            # Create a minimal BaseDeviceState with error information
            return BaseDeviceState(
                device_id=device_id,
                device_name=device.get_name(),
                error=str(e)
            )
    except Exception as e:
        logger.error(f"Error getting device {device_id}: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/devices/{device_id}/persisted_state", response_model=Dict[str, Any])
async def get_device_persisted_state(device_id: str):
    """Get the persisted state of a specific device from the state store.
    
    Args:
        device_id: The ID of the device to retrieve state for
        
    Returns:
        JSON: The persisted device state
        
    Raises:
        HTTPException: If state persistence is not available or no state found
    """
    if not state_store:
        raise HTTPException(status_code=503, detail="State persistence not available")
    
    try:
        state = await state_store.get(f"device:{device_id}")
        if state is None:
            raise HTTPException(status_code=404, detail=f"No persisted state found for device: {device_id}")
        return state
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error retrieving device persisted state: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/devices/persisted_states", response_model=PersistedStatesResponse)
async def get_all_persisted_states():
    """Get the persisted states of all devices from the state store.
    
    Returns:
        Dict[str, Any]: Dictionary mapping device IDs to their persisted states
        
    Raises:
        HTTPException: If state persistence is not available
    """
    logger = logging.getLogger(__name__)
    if not state_store:
        raise HTTPException(status_code=503, detail="State persistence not available")
    
    try:
        # Get all device IDs
        device_ids = device_manager.get_all_devices() if device_manager else []
        
        # Create an empty result dictionary
        result = {}
        
        # For each device, try to get its persisted state
        for device_id in device_ids:
            try:
                state = await state_store.get(f"device:{device_id}")
                if state:
                    result[device_id] = state
            except Exception as e:
                logger.warning(f"Error retrieving persisted state for device {device_id}: {str(e)}")
                # Continue with other devices even if one fails
                continue
        
        return result
    except Exception as e:
        logger.error(f"Error retrieving all persisted states: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/scenario/state", response_model=ScenarioState)
async def get_scenario_state():
    """
    Get the current scenario state.
    
    Returns information about the active scenario and the state of all
    devices that are part of it.
    
    Returns:
        ScenarioState: Current scenario state
        
    Raises:
        HTTPException: If no active scenario or service not initialized
    """
    if not scenario_manager:
        raise HTTPException(status_code=503, detail="Service not fully initialized")
    
    if not scenario_manager.scenario_state:
        raise HTTPException(status_code=404, detail="No active scenario")
    
    return scenario_manager.scenario_state 