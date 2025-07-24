import logging
from typing import List

from fastapi import APIRouter, HTTPException

from wb_mqtt_bridge.presentation.api.schemas import (
    Group,
    GroupActionsResponse,
    GroupedActionsResponse,
    ActionGroup
)

# Create router with appropriate tags
router = APIRouter(
    tags=["Groups"]
)

# Global references that will be set during initialization
config_manager = None
device_manager = None

def initialize(cfg_manager, dev_manager):
    """Initialize global references needed by router endpoints."""
    global config_manager, device_manager
    config_manager = cfg_manager
    device_manager = dev_manager

@router.get("/groups", response_model=List[Group])
async def get_groups():
    """List all available function groups."""
    if not config_manager:
        raise HTTPException(status_code=503, detail="Service not fully initialized")
    
    try:
        groups = config_manager.get_groups()
        return [{"id": group_id, "name": display_name} for group_id, display_name in groups.items()]
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error retrieving groups: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/devices/{device_id}/groups/{group_id}/actions", response_model=GroupActionsResponse)
async def get_actions_by_group(device_id: str, group_id: str):
    """List all actions in a group for a device, with status information."""
    logger = logging.getLogger(__name__)
    
    if not device_manager or not config_manager:
        raise HTTPException(status_code=503, detail="Service not fully initialized")
    
    try:
        # Check if device exists
        device = device_manager.get_device(device_id)
        if not device:
            raise HTTPException(status_code=404, detail=f"Device '{device_id}' not found")
            
        # Get group definitions
        groups = config_manager.get_groups()
        group_name = groups.get(group_id)
        
        # Case 1: Group is not defined in system.json and is not 'default'
        if not config_manager.is_valid_group(group_id):
            return GroupActionsResponse(
                device_id=device_id,
                group_id=group_id,
                status="invalid_group",
                message=f"Group '{group_id}' is not defined in system configuration"
            )
            
        # Case 2: Group is valid but device doesn't have it
        if group_id not in device.get_available_groups():
            if group_id == "default":
                # Special case for default group - it always exists but might be empty
                return GroupActionsResponse(
                    device_id=device_id,
                    group_id=group_id,
                    group_name="Default Group",
                    status="no_actions",
                    message=f"Device '{device_id}' has no actions in the 'default' group"
                )
            else:
                return GroupActionsResponse(
                    device_id=device_id,
                    group_id=group_id,
                    group_name=group_name,
                    status="unknown_group",
                    message=f"Device '{device_id}' does not support the '{group_id}' group"
                )
        
        # Case 3: Group exists but has no actions
        actions = device.get_actions_by_group(group_id)
        if not actions:
            return GroupActionsResponse(
                device_id=device_id,
                group_id=group_id,
                group_name=group_name,
                status="no_actions",
                message=f"Device '{device_id}' has no actions in the '{group_id}' group"
            )
            
        # Case 4: Success - group exists with actions
        return GroupActionsResponse(
            device_id=device_id,
            group_id=group_id,
            group_name=group_name,
            status="ok",
            actions=actions
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving actions for group '{group_id}' in device '{device_id}': {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/devices/{device_id}/groups", response_model=GroupedActionsResponse)
async def get_device_actions_by_groups(device_id: str):
    """Get all actions for a device organized by groups, including empty groups."""
    logger = logging.getLogger(__name__)
    
    if not device_manager or not config_manager:
        raise HTTPException(status_code=503, detail="Service not fully initialized")
    
    try:
        device = device_manager.get_device(device_id)
        if not device:
            raise HTTPException(status_code=404, detail=f"Device '{device_id}' not found")
        
        group_definitions = config_manager.get_groups()
        groups = []
        default_included = False
        
        # Get all device groups
        device_groups = device.get_available_groups()
        
        # Process all groups defined for this device
        for group_id in device_groups:
            group_name = group_definitions.get(group_id, group_id.title())
            actions = device.get_actions_by_group(group_id)
            
            # Create ActionGroup object
            action_group = ActionGroup(
                group_id=group_id,
                group_name=group_name,
                actions=actions,
                status="ok" if actions else "no_actions"
            )
            
            groups.append(action_group)
            
            # Track if default group is included
            if group_id == "default":
                default_included = True
        
        # Always include default group if not already included
        if not default_included:
            groups.append(ActionGroup(
                group_id="default",
                group_name="Default Group",
                actions=[],
                status="no_actions"
            ))
            default_included = True
        
        return GroupedActionsResponse(
            device_id=device_id,
            groups=groups,
            default_included=default_included
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving grouped actions for device '{device_id}': {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}") 