# Implementation Plan for Function Groups

## 1. Centralized Group Definitions

- **Update `system.json`:**
  - Add a `groups` section to the `system.json` file to define all possible groups with their internal names and display names.
  - Example:
    ```json
    {
      "groups": {
        "volume": "Sound Volume",
        "screen": "Screen Control",
        "playback": "Playback"
      }
    }
    ```

## 2. Configuration Manager Enhancements

- **Load Group Definitions:**
  - Enhance the configuration manager to load group definitions from `system.json` during initialization.
  - Store these definitions in a centralized location accessible to all devices.

## 3. Base Device Modifications

- **Group Index Construction:**
  - Modify the `BaseDevice` class to construct indices for actions based on groups. This can be done during device initialization or when actions are loaded.
  - Implement methods in `BaseDevice` to retrieve actions by group, leveraging the indices for efficient access.
  - **Default Group Assignment:**
    - Ensure that any device action not explicitly assigned to a group is automatically assigned to a "default" group. This group does not need to be specified in any configuration file.
  - **Fixed Sorting Order:**
    - Maintain a fixed sorting order for actions within each group, based on their order of appearance in the respective configuration file. This ensures consistency and predictability in how actions are accessed and displayed.

## 4. Device-Specific Implementations

- **Reference Groups in Configurations:**
  - Update each device's configuration file to reference groups by their internal names.
  - Example:
    ```json
    {
      "actions": [
        {
          "name": "increase_volume",
          "group": "volume",
          "rf_code": "..."
        },
        {
          "name": "turn_on_screen",
          "group": "screen",
          "rf_code": "..."
        }
      ]
    }
    ```

## 5. FastAPI Integration

- **Define API Endpoints:**
  - **List All Groups:**
    - Create an endpoint to list all available function groups.
    - Example endpoint: `GET /api/groups`
  - **List Actions by Group:**
    - Create an endpoint to list all actions associated with a specific group for a given device.
    - Example endpoint: `GET /api/devices/{device_id}/groups/{group_id}/actions`

- **Implement API Logic:**
  - **Load Group Definitions:**
    - Ensure the FastAPI application accesses the centralized group definitions loaded by the configuration manager.
  - **Retrieve Actions by Group:**
    - Use the indices constructed in `BaseDevice` to efficiently retrieve actions for a specific device and group.

## 6. Pydantic Schema Updates

- **Update Existing Schemas:**
  - **SystemConfig Schema:**
    - Add a `groups` field to include group definitions in the system configuration.
    ```python
    class SystemConfig(BaseModel):
        mqtt_broker: MQTTBrokerConfig
        web_service: Dict[str, Any]
        log_level: str
        log_file: str
        devices: Dict[str, Dict[str, Any]]
        groups: Dict[str, str] = Field(default_factory=dict)  # Internal name -> Display name
    ```
  
  - **DeviceConfig Schema:**
    - Update the commands field to include group information.
    ```python
    # No direct changes needed as commands is already a Dict[str, Any]
    ```

- **Create New Schemas:**
  - **Group Schema:**
    - Create a schema to represent a function group with internal ID and display name.
    ```python
    class Group(BaseModel):
        id: str
        name: str
    ```
  
  - **ActionGroup Schema:**
    - Create a schema to represent a group of actions, leveraging existing action representations.
    ```python
    class ActionGroup(BaseModel):
        group_id: str
        group_name: str
        actions: List[Dict[str, Any]]  # Reusing existing action representations
    ```
  
  - **GroupedActionsResponse Schema:**
    - Create a schema for API responses that return actions grouped by function.
    ```python
    class GroupedActionsResponse(BaseModel):
        device_id: str
        groups: List[ActionGroup]
    ```

## 7. Testing and Validation

- **Comprehensive Testing:**
  - Test the updated configuration manager, base device, and FastAPI endpoints to ensure that actions are correctly associated with their groups and that the system behaves as expected.

## 8. Documentation

- **Update Documentation:**
  - Update any relevant documentation to reflect the new configuration structure and the concept of function groups.
  - Leverage FastAPI's automatic documentation generation for API endpoints.

## Example FastAPI Code

Here's a basic example of how the FastAPI endpoints might be structured, assuming the configuration manager and base device handle group management:

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict

app = FastAPI()

# Assume groups are loaded by the configuration manager
groups = {
    "volume": "Sound Volume",
    "screen": "Screen Control",
    "playback": "Playback",
    "default": "Default Group"
}

# Example device actions, indexed by group
device_actions = {
    "device1": {
        "volume": [{"name": "increase_volume", "rf_code": "..."}],
        "screen": [{"name": "turn_on_screen", "rf_code": "..."}],
        "default": [{"name": "unassigned_action", "rf_code": "..."}]
    }
}

class Group(BaseModel):
    id: str
    name: str

class Action(BaseModel):
    name: str
    rf_code: str

@app.get("/api/groups", response_model=List[Group])
async def get_groups():
    return [{"id": gid, "name": gname} for gid, gname in groups.items()]

@app.get("/api/devices/{device_id}/groups/{group_id}/actions", response_model=List[Action])
async def get_actions_by_group(device_id: str, group_id: str):
    if device_id not in device_actions or group_id not in device_actions[device_id]:
        raise HTTPException(status_code=404, detail="Device or group not found")
    return device_actions[device_id][group_id]
```

## Next Steps

- **Implement the Plan:** Follow the steps outlined above to update configurations, enhance the configuration manager, modify the base device, and implement FastAPI endpoints.
- **Testing and Validation:** Conduct thorough testing to ensure the changes work as intended.
- **Documentation:** Update documentation to reflect the new structure and API capabilities.

This plan centralizes group management, making it efficient and consistent across the system, while providing a structured way to expose these groups through FastAPI. 