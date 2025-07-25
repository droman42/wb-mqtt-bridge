# Detailed Implementation Plan: App-Layer Adjustments

This document provides the step-by-step changes to the `app/` layer to fulfill strong-typing standardization and the new requirements.

---

## Step 1: Strict `device_id` Validation in ConfigManager

**File:** `app/config_manager.py`  
**Method:** `_load_device_configs`

1. After loading each device's JSON (`device_config_dict`), insert:

    ```python
    if device_config_dict.get("device_id") != device_id:
        raise RuntimeError(
            f"Config file '{config_file}' has device_id '
            f"{device_config_dict.get('device_id')}' but expected '{device_id}'"
        )
    ```

2. Remove any legacy fallback logic—if Pydantic parsing fails, allow the exception to propagate (hard error).

---

## Step 2: Collapse DeviceConfigFactory into DeviceManager

### 2.1 Delete the Factory

- Remove `app/device_config_factory.py` and all its imports.

### 2.2 Refactor `DeviceManager.initialize_devices()`

**File:** `app/device_manager.py`  
**Method:** `initialize_devices`

1. Change signature:

    ```diff
    - async def initialize_devices(self, configs: Dict[str, Union[DeviceConfig, BaseDeviceConfig]]):
    + async def initialize_devices(self, configs: Dict[str, BaseDeviceConfig]):
    ```

2. Simplify instantiation:

    ```diff
    for device_id, config in configs.items():
    -   device_class = self.device_classes.get(config.device_class)
    -   if not device_class:
    -       continue
    -   device = device_class(config, self.mqtt_client)
    +   device_class = self.device_classes.get(config.device_class)
    +   if not device_class:
    +       raise RuntimeError(
    +           f"Unknown device class '{config.device_class}' for '{device_id}'"
    +       )
    +   device = device_class(config, self.mqtt_client)
        await device.setup()
        self.devices[device_id] = device
    ```

3. In application startup, call this with `config_manager.get_all_typed_configs()`.

---

## Step 3: Preserve Concrete State in `update_state()`

**File:** `devices/base_device.py`  
**Method:** `update_state`

Replace:

```python
updated_data = self.state.dict(exclude_unset=True)
updated_data.update(updates)
self.state = BaseDeviceState(**updated_data)
```

With:

```python
data = self.state.dict(exclude_unset=True)
data.update(updates)
state_cls = type(self.state)  # e.g. KitchenHoodState, LgTvState
self.state = state_cls(**data)
```

---

## Step 4: Deprecate HTTP `DeviceState` & `DeviceActionResponse`

**File:** `app/schemas.py`

- Remove (or mark deprecated) these Pydantic models:

  ```python
  class DeviceState(BaseModel):
      ...

  class DeviceActionResponse(BaseModel):
      ...
  ```

---

## Step 5: Make `CommandResponse` Generic & Typed

**File:** `app/types.py`

Change:

```python
class CommandResponse(TypedDict):
    state: Dict[str, Any]
    error: Optional[str]
    mqtt_command: Optional[Dict[str, Any]]
```

To:

```python
from typing import Generic

class CommandResponse(TypedDict, Generic[StateT]):
    state: StateT
    error: Optional[str]
    mqtt_command: Optional[Dict[str, Any]]
```

---

## Step 6: Audit `mqtt_command` Propagation

- Verify all handlers using `create_command_result(..., mqtt_command={...})` now have that field preserved by `execute_action()` and returned by the HTTP API.

- Add an integration test in `tests/` to call a command that emits `mqtt_command` and assert the JSON response includes the same object.

---

## Step 7: FastAPI Endpoint Adjustments

**File:** `app/main.py`

Update these endpoints as follows:

| Endpoint                           | Model Before               | Model After                        | Change Snippet / Notes                                                    |
|------------------------------------|----------------------------|------------------------------------|---------------------------------------------------------------------------|
| GET `/config/device/{device_id}`   | `DeviceConfig` (legacy)    | `BaseDeviceConfig` (typed)        | ```diff
- @app.get(..., response_model=DeviceConfig)
+ @app.get(..., response_model=BaseDeviceConfig)
``` and in handler use `get_typed_config()` and 404 if missing.
| GET `/config/devices`              | `Dict[str,DeviceConfig]`   | `Dict[str,BaseDeviceConfig]`      | ```diff
- response_model=Dict[str, DeviceConfig]
+ response_model=Dict[str, BaseDeviceConfig]
``` return `get_all_typed_configs()`.
| GET `/devices/{device_id}`         | `DeviceState` wrapper      | `BaseDeviceState` (subclass)      | ```diff
- @app.get(..., response_model=DeviceState)
+ @app.get(..., response_model=BaseDeviceState)
``` return `device.get_current_state()` directly.
| POST `/devices/{device_id}/action` | `DeviceActionResponse`     | `CommandResponse[StateT]`         | ```diff
- response_model=DeviceActionResponse
+ response_model=CommandResponse
``` return raw `result` and raise 400 on `!success`.
| POST `/reload`                     | `ReloadResponse`           | `ReloadResponse`                  | Wrap `reload_configs()` so that `RuntimeError` becomes `HTTPException(500)`.

**No Changes Needed** for:

- GET `/`, GET `/system`, GET `/config/system`, POST `/publish`, GET `/groups`,
- GET `/devices/{device_id}/groups`, GET `/devices/{device_id}/groups/{group_id}/actions`

---

**After completing these steps and tests**, the app layer will:

1. Enforce strict config validation.  
2. Instantiate devices directly from Pydantic configs.  
3. Return strongly-typed state and responses.  
4. Drop legacy wrappers and factory code. 