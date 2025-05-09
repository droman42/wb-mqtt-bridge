import logging
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from app.schemas import (
    BaseDeviceConfig,
    DeviceAction,
    BaseDeviceState
)
from app.types import CommandResponse

# Create router with appropriate prefix and tags
router = APIRouter(
    tags=["Devices"]
)

# Global references that will be set during initialization
config_manager = None
device_manager = None
mqtt_client = None

def initialize(cfg_manager, dev_manager, mqt_client):
    """Initialize global references needed by router endpoints."""
    global config_manager, device_manager, mqtt_client
    config_manager = cfg_manager
    device_manager = dev_manager
    mqtt_client = mqt_client

@router.get("/config/device/{device_id}")
async def get_device_config(device_id: str):
    """Get full configuration for a specific device."""
    if not config_manager:
        raise HTTPException(status_code=503, detail="Service not fully initialized")
    
    try:
        # Get the typed configuration for this device
        typed_configs = config_manager.get_all_typed_configs()
        if device_id in typed_configs:
            return typed_configs[device_id]
        
        # No typed config found - return 404
        logger = logging.getLogger(__name__)
        logger.error(f"Typed configuration for device {device_id} not found")
        raise HTTPException(status_code=404, detail=f"Typed device configuration for {device_id} not found")
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error retrieving device config for {device_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/config/devices")
async def get_all_device_configs():
    """Get configurations for all devices."""
    if not config_manager:
        raise HTTPException(status_code=503, detail="Service not fully initialized")
    
    try:
        # Get all typed configurations
        typed_configs = config_manager.get_all_typed_configs()
        
        # Return typed configs (may be empty dict if none exist)
        return typed_configs
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error retrieving all device configs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/devices/{device_id}", response_model=BaseDeviceState)
async def get_device(device_id: str):
    """Get information about a specific device.
    
    Args:
        device_id: The ID of the device to retrieve
        
    Returns:
        BaseDeviceState: The device state with proper typing
        
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

@router.post("/devices/{device_id}/action", response_model=CommandResponse)
async def execute_device_action(
    device_id: str, 
    action: DeviceAction,
    background_tasks: BackgroundTasks
):
    """Execute an action on a specific device.
    
    This endpoint allows executing various actions on devices. The available actions depend on the device type.
    For LG TVs, the following mouse control actions are supported:
    
    * **move_cursor** - Move cursor to absolute position x,y
      ```json
      {
        "action": "move_cursor",
        "params": {
          "x": 500,
          "y": 300,
          "drag": false
        }
      }
      ```
    
    * **move_cursor_relative** - Move cursor by dx,dy relative to current position
      ```json
      {
        "action": "move_cursor_relative",
        "params": {
          "dx": 100,
          "dy": -50,
          "drag": false
        }
      }
      ```
    
    * **click** - Click at position x,y
      ```json
      {
        "action": "click",
        "params": {
          "x": 500,
          "y": 300
        }
      }
      ```
    
    * **launch_app** - Launch an app by name
      ```json
      {
        "action": "launch_app",
        "params": {
          "app_name": "Netflix"
        }
      }
      ```
    
    * **wake_on_lan** - Wake the TV using Wake-on-LAN
      ```json
      {
        "action": "wake_on_lan",
        "params": {}
      }
      ```
    
    Other common actions include:
    * **power_on** - Turn the TV on
    * **power_off** - Turn the TV off
    * **set_volume** - Set TV volume (params: volume)
    * **set_mute** - Set TV mute state (params: mute)
    * **set_input_source** - Change input source (params: input_source)
    * **send_action** - Send remote control command (params: command)
    """
    logger = logging.getLogger(__name__)
    if not device_manager:
        raise HTTPException(status_code=503, detail="Service not fully initialized")
    
    # Use the device_manager's perform_action method, which handles persistence
    logger.info(f"Executing action {action.action} for device {device_id} with params {action.params}")
    result = await device_manager.perform_action(device_id, action.action, action.params)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Unknown error"))
    
    # If there's an MQTT command to be published, do it in the background
    if "mqtt_command" in result and result["mqtt_command"] is not None and mqtt_client is not None:
        mqtt_cmd = result["mqtt_command"]
        background_tasks.add_task(
            mqtt_client.publish,
            mqtt_cmd["topic"],
            mqtt_cmd["payload"]
        )
    
    # Return the properly typed CommandResponse directly
    return result 