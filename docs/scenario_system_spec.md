# Scenario System Specification

## 1. Device Configuration

Commands already have a 'group' attribute which is used for organizing related functions. No configuration changes are needed - device configurations should be used as-is.

Example command structure:
```json
{
  "action": "POWER",
  "topic": "/devices/living_room_tv/controls/buttons/power",
  "description": "Power Button",
  "group": "power_control"
}
```

## 2. Scenario Configuration Structure

```json
{
  "scenario_id": "movie_night",
  "name": "Movie Night",
  "description": "Setup for watching movies with optimal audio and video settings",
  "devices": {
    "living_room_tv": {
      "groups": ["screen", "volume_control"]
    },
    "audio_receiver": {
      "groups": ["audio_control", "source_control"]
    }
  },
  "startup_sequence": [
    {
      "device": "audio_receiver",
      "command": "power",
      "params": {"state": "on"},
      "condition": "device.power != 'on'",
      "delay_after_ms": 2000
    },
    {
      "device": "audio_receiver",
      "command": "input",
      "params": {"input": "hdmi1"},
      "condition": "device.input != 'hdmi1'",
      "delay_after_ms": 1000
    },
    {
      "device": "living_room_tv",
      "command": "power",
      "params": {"state": "on"},
      "condition": "device.power != 'on'",
      "delay_after_ms": 2000
    },
    {
      "device": "living_room_tv",
      "command": "input_source",
      "params": {"source": "hdmi1"},
      "condition": "device.input_source != 'hdmi1'"
    }
  ],
  "shutdown_sequence": {
    "complete": [
      {
        "device": "living_room_tv",
        "command": "power",
        "params": {"state": "off"},
        "condition": "device.power == 'on'",
        "delay_after_ms": 1000
      },
      {
        "device": "audio_receiver",
        "command": "power",
        "params": {"state": "off"},
        "condition": "device.power == 'on'"
      }
    ],
    "transition": [
      {
        "device": "living_room_tv",
        "command": "input_source",
        "params": {"source": "tv"},
        "condition": "device.input_source != 'tv'"
      },
      {
        "device": "audio_receiver",
        "command": "input",
        "params": {"input": "tv"},
        "condition": "device.input != 'tv'"
      }
    ]
  }
}
```

## 3. Core Classes

### ScenarioManager
```python
class ScenarioManager:
    def __init__(self, device_manager: DeviceManager):
        self.device_manager = device_manager
        self.current_scenario = None
        self.scenario_state = {}
    
    async def load_scenarios(self):
        """Load and validate all scenario configurations"""
        pass
    
    async def switch_scenario(self, scenario_id: str, previous_scenario: Optional[str] = None):
        """Switch to a new scenario"""
        pass
    
    async def shutdown_scenario(self):
        """Shutdown current scenario"""
        pass
    
    def get_scenario_state(self) -> Dict[str, Any]:
        """Get current scenario state"""
        pass
```

### Scenario
```python
class Scenario:
    def __init__(self, config: Dict[str, Any], device_manager: DeviceManager):
        self.config = config
        self.device_manager = device_manager
        self.state = {}
    
    async def initialize(self, previous_scenario: Optional[str] = None):
        """Initialize scenario with previous scenario context"""
        pass
    
    async def execute_startup_sequence(self):
        """Execute startup sequence with configurable delays"""
        for step in self.config["startup_sequence"]:
            device = self.device_manager.get_device(step["device"])
            if await self._evaluate_condition(step.get("condition"), device):
                await device.execute_command(step["command"], step["params"])
                if "delay_after_ms" in step:
                    await asyncio.sleep(step["delay_after_ms"] / 1000)
    
    async def execute_shutdown_sequence(self, is_complete_shutdown: bool = True):
        """Execute shutdown sequence with configurable delays
        
        Args:
            is_complete_shutdown: If True, executes complete shutdown sequence.
                                 If False, executes transition sequence for devices
                                 that will be used in the next scenario.
        """
        sequence_type = "complete" if is_complete_shutdown else "transition"
        for step in self.config["shutdown_sequence"][sequence_type]:
            device = self.device_manager.get_device(step["device"])
            if await self._evaluate_condition(step.get("condition"), device):
                await device.execute_command(step["command"], step["params"])
                if "delay_after_ms" in step:
                    await asyncio.sleep(step["delay_after_ms"] / 1000)
    
    def validate(self) -> List[str]:
        """Validate scenario configuration"""
        pass
```

## 4. Error Handling Strategy

### Error Types
1. **Configuration Errors**
   - Circular dependencies
   - Duplicate functions (except startup/shutdown)
   - Missing required devices
   - Invalid command references

2. **Execution Errors**
   - Device command failures
   - Timeout errors
   - State validation errors

### Error Handling Approach
```python
class ScenarioError(Exception):
    def __init__(self, message: str, error_type: str, critical: bool = False):
        self.message = message
        self.error_type = error_type
        self.critical = critical

class ScenarioExecutionError(ScenarioError):
    def __init__(self, message: str, device_id: str, command: str):
        super().__init__(message, "execution", False)
        self.device_id = device_id
        self.command = command
```

## 5. REST API Endpoints

```python
@router.post("/scenarios/{scenario_id}/activate")
async def activate_scenario(scenario_id: str):
    """Activate a scenario"""
    pass

@router.post("/scenarios/current/deactivate")
async def deactivate_scenario():
    """Deactivate current scenario"""
    pass

@router.get("/scenarios")
async def list_scenarios():
    """List all available scenarios"""
    pass

@router.get("/scenarios/current")
async def get_current_scenario():
    """Get current scenario state"""
    pass
```

## 6. Validation Rules

1. **Device Validation**
   - All referenced devices must exist
   - All referenced commands must exist in device configuration
   - All referenced groups must be supported by device commands

2. **Dependency Validation**
   - No circular dependencies allowed
   - All dependencies must reference valid devices
   - Dependencies must be resolvable

3. **Function Validation**
   - No duplicate functions in scenario (except startup/shutdown)
   - All functions must reference valid commands
   - Conditions must be valid expressions

4. **Group Validation**
   - Each device must have at least one group
   - Groups must be unique within a device
   - Groups must be supported by device commands

## Open Questions

1. **State Management**
   - Should we implement a more sophisticated state tracking system for devices?
   - How should we handle state persistence between service restarts?

2. **Condition Syntax**
   - What syntax should we use for conditions in startup/shutdown sequences?
   - Should we support complex boolean expressions?

3. **Scenario Transitions**
   - Should we implement a transition phase between scenarios?
   - How should we handle devices that are shared between scenarios?

4. **Error Recovery**
   - Should we implement automatic retry mechanisms for failed commands?
   - How should we handle partial scenario activation failures?

5. **Performance Optimization**
   - Should we implement caching for scenario configurations?
   - How should we handle large numbers of devices in a scenario? 