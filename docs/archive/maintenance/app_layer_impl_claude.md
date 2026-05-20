# WB-MQTT Bridge: App Layer Implementation Plan

## Background & Current State

The codebase has already implemented a significant portion of the strong typing standardization in the device layer:

- **BaseDevice** has been updated with standard methods for handler registration (`_register_handlers()`)
- Handlers in device classes have been standardized with the `handle_` prefix and consistent signatures
- Standard error methods (`set_error()`, `clear_error()`) have been implemented
- Method naming conventions have been established
- Pydantic models are being used for configuration

The following types are already defined in `app/types.py`:
```python
from typing import Dict, Any, List, Optional, TypeVar, Generic, Union, Callable, Awaitable, TypedDict
from app.schemas import BaseDeviceState, BaseCommandConfig

# Define state type variable for generic typing
StateT = TypeVar('StateT', bound=BaseDeviceState)

# Standard return type for individual handlers
class CommandResult(TypedDict, total=False):
    """Return type for device action handlers."""
    success: bool
    message: Optional[str]
    error: Optional[str]
    mqtt_command: Optional[Dict[str, Any]]
    # Other optional fields

# Standard return type for execute_action
class CommandResponse(TypedDict):
    """Return type for BaseDevice.execute_action."""
    success: bool
    device_id: str
    action: str
    state: Dict[str, Any]
    error: Optional[str]
    mqtt_command: Optional[Dict[str, Any]]

# Type definition for action handlers
ActionHandler = Callable[[BaseCommandConfig, Dict[str, Any]], Awaitable[CommandResult]]
```

## Implementation Plan

### Phase 1: CommandResponse Generics Update

1. **Modify CommandResponse in app/types.py**
   ```python
   # Current
   class CommandResponse(TypedDict):
       """Return type for BaseDevice.execute_action."""
       success: bool
       device_id: str
       action: str
       state: Dict[str, Any]
       error: Optional[str]
       mqtt_command: Optional[Dict[str, Any]]

   # Modified
   class CommandResponse(TypedDict, Generic[StateT]):
       """Return type for BaseDevice.execute_action."""
       success: bool
       device_id: str
       action: str
       state: StateT  # Now properly typed with specific state class
       error: Optional[str]
       mqtt_command: Optional[Dict[str, Any]]
   ```

2. **Verify BaseDevice.execute_action() Method**
   - Ensure it returns the appropriate typed state:
   ```python
   # In BaseDevice.execute_action()
   async def execute_action(self, action: str, params: Dict[str, Any]) -> CommandResponse[StateT]:
       result: CommandResult = await self._execute_single_action(...)
       
       # Transform to properly typed CommandResponse
       response: CommandResponse[StateT] = {
           "success": result["success"],
           "device_id": self.device_id,
           "action": action,
           "state": self.state,  # This should now be properly typed
           "error": result.get("error"),
           "mqtt_command": result.get("mqtt_command")
       }
       return response
   ```

3. **Review Derived Classes**
   - Check all derived device classes to ensure they:
     - Define and use proper state subclasses (e.g., `KitchenHoodState`, `LgTvState`)
     - Handle typed CommandResponse objects correctly
     - Publish the correct state type in MQTT messages

### Phase 2: State Preservation in BaseDevice

1. **Verify or Update update_state() Method**
   ```python
   # Current (likely)
   def update_state(self, **updates):
       updated_data = self.state.dict(exclude_unset=True)
       updated_data.update(updates)
       self.state = BaseDeviceState(**updated_data)  # Loses concrete subclass
   
   # Required changes
   def update_state(self, **updates):
       data = self.state.dict(exclude_unset=True)
       data.update(updates)
       state_cls = type(self.state)  # Preserves concrete type (e.g., KitchenHoodState)
       self.state = state_cls(**data)
   ```

2. **Audit Device Classes**
   - Review all device classes to ensure they're not bypassing `update_state()`
   - Check for custom state update methods that should be removed
   - Verify each device properly initializes its specific state subclass

### Phase 3: Config Management Enhancements

1. **Implement Strict Validation in ConfigManager**
   ```python
   # In app/config_manager.py, _load_device_configs method
   def _load_device_configs(self):
       system_config = self._load_system_config()
       devices = {}
       
       for device_id, device_info in system_config.get("devices", {}).items():
           config_file = device_info.get("config_file")
           if not config_file:
               continue
               
           device_config_dict = self._load_json_file(config_file)
           
           # Add strict device_id validation
           if device_config_dict.get("device_id") != device_id:
               raise RuntimeError(
                   f"Config file '{config_file}' has device_id '{device_config_dict.get('device_id')}' "
                   f"but expected '{device_id}'"
               )
           
           # No fallback - let failures propagate as errors
           devices[device_id] = self._create_typed_config(device_config_dict)
       
       return devices
   ```

2. **Review Config Parsing Methods**
   - Remove any legacy fallback logic
   - Ensure errors during config loading are treated as hard errors
   - Verify all config classes use Pydantic validation correctly

### Phase 4: Device Manager Refactoring

1. **Remove DeviceConfigFactory**
   - Delete `app/device_config_factory.py` file
   - Remove any imports of this file from other modules

2. **Refactor DeviceManager.initialize_devices()**
   ```python
   # Current (likely)
   async def initialize_devices(self, configs: Dict[str, Union[DeviceConfig, BaseDeviceConfig]]):
       # Uses factory or hardcoded mapping
       
   # Changed version
   async def initialize_devices(self, configs: Dict[str, BaseDeviceConfig]):
       """Initialize devices with properly typed configs"""
       for device_id, config in configs.items():
           device_class_name = config.device_class
           # Use dynamic import and instantiation
           try:
               module = importlib.import_module(f"devices.{device_class_name.lower()}")
               class_obj = getattr(module, device_class_name)
               device = class_obj(config, self.mqtt_client)
               await device.setup()
               self.devices[device_id] = device
           except (ImportError, AttributeError) as e:
               raise RuntimeError(f"Failed to load device class '{device_class_name}': {str(e)}")
   ```

3. **Update Application Startup**
   - Ensure `app/main.py` calls this with properly typed configs
   - Use `config_manager.get_all_typed_configs()` instead of any legacy config method

### Phase 5: HTTP Layer Adjustments

1. **Update DeviceState Endpoint**
   ```python
   # In app/main.py, for GET /devices/{device_id}
   
   # Current
   @app.get("/devices/{device_id}", response_model=DeviceState)
   def get_device_state(device_id: str):
       device = device_manager.get_device(device_id)
       if not device:
           raise HTTPException(status_code=404)
       return {"state": device.get_current_state()}  # Wrapped in DeviceState
   
   # Changed
   @app.get("/devices/{device_id}", response_model=BaseDeviceState)
   def get_device_state(device_id: str):
       device = device_manager.get_device(device_id)
       if not device:
           raise HTTPException(status_code=404)
       return device.get_current_state()  # Direct state object
   ```

2. **Update Action Endpoint**
   ```python
   # In app/main.py, for POST /devices/{device_id}/action
   
   # Current
   @app.post("/devices/{device_id}/action", response_model=DeviceActionResponse)
   async def execute_device_action(device_id: str, action: DeviceAction):
       device = device_manager.get_device(device_id)
       if not device:
           raise HTTPException(status_code=404)
       
       result = await device.execute_action(action.action, action.params or {})
       if not result["success"]:
           raise HTTPException(status_code=400, detail=result.get("error", "Unknown error"))
       
       return {"success": True, "message": "Action executed", "state": result["state"]}
   
   # Changed
   @app.post("/devices/{device_id}/action", response_model=CommandResponse)
   async def execute_device_action(device_id: str, action: DeviceAction):
       device = device_manager.get_device(device_id)
       if not device:
           raise HTTPException(status_code=404)
       
       result = await device.execute_action(action.action, action.params or {})
       if not result["success"]:
           raise HTTPException(status_code=400, detail=result.get("error", "Unknown error"))
       
       return result  # Return the complete CommandResponse directly
   ```

3. **Remove or Deprecate DeviceState in schemas.py**
   ```python
   # In app/schemas.py
   
   # Remove or mark as deprecated
   class DeviceState(BaseModel):
       state: Dict[str, Any]
   
   class DeviceActionResponse(BaseModel):
       success: bool
       message: str
       state: Dict[str, Any]
   ```

4. **Update Config Endpoints**
   ```python
   # In app/main.py
   
   @app.get("/config/device/{device_id}", response_model=BaseDeviceConfig)
   def get_device_config(device_id: str):
       config = config_manager.get_typed_config(device_id)
       if not config:
           raise HTTPException(status_code=404)
       return config
   
   @app.get("/config/devices", response_model=Dict[str, BaseDeviceConfig])
   def get_all_device_configs():
       return config_manager.get_all_typed_configs()
   ```

### Phase 6: MQTT Command Propagation

1. **Audit CommandResult Creation**
   - Review all device handlers to ensure `mqtt_command` is properly included:
   ```python
   # In any device handler
   async def handle_power_on(self, cmd_config, params):
       # ... device logic ...
       return self.create_command_result(
           success=True, 
           message="Power on successful",
           mqtt_command={
               "topic": "device/control",
               "payload": {"power": "on"}
           }
       )
   ```

2. **Verify BaseDevice.execute_action**
   - Ensure it preserves the `mqtt_command` field:
   ```python
   response = {
       "success": result["success"],
       "device_id": self.device_id,
       "action": action,
       "state": self.state,
       "error": result.get("error"),
       "mqtt_command": result.get("mqtt_command")  # Preserve this field
   }
   ```

3. **Check HTTP Action Endpoint**
   - Ensure it returns the full response including `mqtt_command`

### Phase 7: Integration Testing

1. **Add Test for Type Preservation**
   ```python
   def test_state_type_preservation():
       # Initialize a specific device
       device = KitchenHood(config, mqtt_client)
       
       # Update state
       device.update_state(power="on")
       
       # Verify concrete type is preserved
       assert isinstance(device.state, KitchenHoodState)
       
       # Verify state values
       assert device.state.power == "on"
   ```

2. **Add Test for MQTT Command Propagation**
   ```python
   async def test_mqtt_command_propagation():
       # Initialize device
       device = KitchenHood(config, mqtt_client)
       
       # Execute action that includes mqtt_command
       result = await device.execute_action("power_on", {})
       
       # Verify result includes mqtt_command
       assert "mqtt_command" in result
       assert result["mqtt_command"]["topic"] == "device/control"
   ```

3. **Add Test for API Response**
   ```python
   async def test_api_response_includes_mqtt_command():
       # Setup FastAPI test client
       client = TestClient(app)
       
       # Execute action
       response = client.post("/devices/kitchen_hood/action", json={"action": "power_on", "params": {}})
       
       # Verify response includes mqtt_command
       assert response.status_code == 200
       data = response.json()
       assert "mqtt_command" in data
   ```

## Additional Considerations

1. **Documentation Updates**
   - Update API documentation to reflect new response formats
   - Add examples of typed responses for frontend developers

2. **Frontend Compatibility**
   - Check if frontend code expects the legacy wrapped responses
   - Update frontend code if needed to handle direct state objects

3. **Migration Plan**
   - Consider temporarily supporting both formats if needed
   - Deprecate old formats with warnings before removing completely

4. **Performance Impact**
   - Measure any performance changes from strong typing
   - Consider optimization if needed

## Success Criteria

The implementation is successful when:

1. All device states are properly typed with specific state classes
2. CommandResponse is generic and preserves specific state types
3. Concrete state types are preserved through update_state()
4. Config validation is strict with no fallbacks
5. DeviceConfigFactory is removed and instantiation is direct
6. HTTP endpoints return properly typed responses
7. MQTT commands propagate correctly through the system
8. All tests pass, verifying type safety and correct behavior 