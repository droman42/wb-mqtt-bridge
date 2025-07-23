# Scenario System Enhancement: WB Virtual Device Integration
*Version: 2025-01-03-domain-architecture*

---

## 1 Problem Statement

The current scenario system provides excellent **device aggregation** and the existing `group` parameter already provides good functional categorization. However, scenarios are only accessible via REST API, limiting their integration with the Wirenboard ecosystem.

### Current Limitations
- **No MQTT Interface**: Scenarios cannot be controlled via MQTT
- **WB UI Gap**: Scenarios don't appear in Wirenboard web interface
- **Client Complexity**: REST clients need to understand which device fills which role for each scenario

### What Works Well ✅
- **Domain-Centric Architecture**: Code restructuring completed - clean separation between domain, infrastructure, and presentation layers
- **Scenario Architecture**: One `Scenario` class + multiple JSON configs (in `domain/scenarios/`)
- **Device Configs**: Already well-structured with good group categorization
- **Parameter Handling**: `BaseDevice` handles type conversion, validation, defaults at runtime
- **WB Device Pattern**: Already implemented and proven in `infrastructure/devices/base.py`
- **Port/Adapter Pattern**: Clean abstractions via `MessageBusPort`, `DeviceBusPort`, `StateRepositoryPort`

---

## 2 Proposed Solution: Apply BaseDevice WB Pattern to Scenarios

Extend the scenario system to implement the same **WB virtual device pattern** used by `BaseDevice`, creating virtual devices for scenarios that expose standardized group-based controls.

### Architectural Approach (Domain-Centric)

Following the established domain-centric architecture:

- **Domain Layer** (`domain/scenarios/`): Core scenario business logic, role action execution
- **Infrastructure Layer** (`infrastructure/`): WB MQTT device implementation, topic handling  
- **Application Layer** (`app/`): Wiring scenarios to MQTT infrastructure via dependency injection

### Core Concept
```
/devices/movie_ld/controls/playbook_play/on        → scenario.execute_role_action("playback", "play")
/devices/movie_ld/controls/playbook_pause/on       → scenario.execute_role_action("playbook", "pause")
/devices/movie_ld/controls/volume_set_level/on     → scenario.execute_role_action("volume", "set_volume", {"level": payload})
/devices/movie_ld/controls/volume_mute/on          → scenario.execute_role_action("volume", "mute")
```

Each active scenario becomes a WB virtual device with **role-prefixed controls** that route to `scenario.execute_role_action()`.

---

## 3 Implementation: Follow BaseDevice WB Pattern

### 3.1 BaseDevice Pattern Analysis ✅

**Current BaseDevice WB Implementation** (in `infrastructure/devices/base.py`):
```python
# 1. Virtual Device Generation
BaseDevice._setup_wb_virtual_device()
├── _publish_wb_device_meta()           # /devices/{device_id}/meta
├── _publish_wb_control_metas()         # /devices/{device_id}/controls/{cmd_name}/meta
└── _setup_wb_last_will()              # Offline detection

# 2. Topic Subscription  
BaseDevice.subscribe_topics() → ["/devices/{device_id}/controls/{cmd_name}/on", ...]

# 3. Command Handling
BaseDevice.handle_message() 
├── _is_wb_command_topic()              # Check /on suffix
├── _handle_wb_command()                # Parse topic → cmd_name
├── _process_wb_command_payload()       # payload → params
└── _execute_single_action()            # Execute handler
```

### 3.2 Domain Layer Extensions

**Extend ScenarioManager** (`domain/scenarios/service.py`) with WB abstraction methods:

```python
# In ScenarioManager class - Domain business logic only
class ScenarioManager:
    def __init__(self, message_bus: MessageBusPort, device_manager, state_repository: StateRepositoryPort):
        self.message_bus = message_bus  # Abstract interface
        # ... other dependencies

    def get_scenario_wb_controls(self, scenario: Scenario) -> Dict[str, Dict[str, Any]]:
        """Get WB control definitions for scenario (domain logic only)."""
        controls = {}
        
        for role, device_id in scenario.definition.roles.items():
            device = self.device_manager.get_device(device_id)
            if not device:
                continue
                
            # Get device commands grouped by the role's functional area
            role_commands = self._get_role_commands_for_device(device, role)
            
            for command_name, command_config in role_commands.items():
                control_name = f"{role}_{command_name}"  # e.g., "playback_play", "volume_set_level"
                
                # Generate control metadata (pure domain logic)
                control_meta = self._generate_scenario_control_meta(role, command_name, command_config)
                controls[control_name] = control_meta
                
        return controls

    def handle_scenario_wb_command(self, control_name: str, payload: str) -> Dict[str, Any]:
        """Handle scenario WB command (domain logic, no I/O)."""
        if not self.current_scenario:
            raise ValueError("No active scenario")
            
        # Parse role and command from control name
        if "_" not in control_name:
            raise ValueError(f"Invalid scenario control name format: {control_name}")
            
        role, command = control_name.split("_", 1)
        
        # Process parameters from payload
        params = self._process_scenario_wb_command_payload(role, command, payload)
        
        # Execute role action using existing scenario system (domain logic)
        return self.execute_role_action(role, command, params)

    def _get_role_commands_for_device(self, device, role: str) -> Dict[str, Any]:
        """Get commands from device that match the role's functional area."""
        available_commands = device.get_available_commands()
        role_commands = {}
        
        # Map role to expected command groups (leverages existing group system)
        role_group_mapping = {
            "playback": ["playback"],
            "volume": ["volume"], 
            "power": ["power"],
            "inputs": ["inputs", "apps"],
            "menu": ["menu", "navigation"],
            "display": ["screen", "display"]
        }
        
        expected_groups = role_group_mapping.get(role, [role])  # Fallback to role name as group
        
        for cmd_name, cmd_config in available_commands.items():
            if hasattr(cmd_config, 'group') and cmd_config.group in expected_groups:
                role_commands[cmd_name] = cmd_config
        
        return role_commands

    def _generate_scenario_control_meta(self, role: str, command: str, command_config) -> Dict[str, Any]:
        """Generate WB control metadata for scenario control (domain logic only)."""
        # Use BaseDevice control type detection logic
        control_type = "pushbutton"  # Default
        
        if hasattr(command_config, 'group') and command_config.group:
            if command_config.group == "volume" and command in ["set_volume", "set_level"]:
                control_type = "range"
            elif command_config.group == "volume" and command in ["mute"]:
                control_type = "switch"
            # Add more group-based type detection as needed
        
        meta = {
            "title": {"en": f"{role.title()} {command.replace('_', ' ').title()}"},
            "type": control_type,
            "readonly": False,
            "order": self._get_scenario_control_order(role, command)
        }
        
        # Add parameter metadata for range controls
        if control_type == "range" and hasattr(command_config, 'params'):
            first_param = command_config.params[0] if command_config.params else None
            if first_param:
                if hasattr(first_param, 'min'):
                    meta["min"] = first_param.min
                if hasattr(first_param, 'max'):
                    meta["max"] = first_param.max
        
        return meta

    def _process_scenario_wb_command_payload(self, role: str, command: str, payload: str) -> Dict[str, Any]:
        """Process scenario WB command payload into parameters (domain logic)."""
        params = {}
        
        # For range controls, payload is the value
        if command in ["set_volume", "set_level", "set_brightness"]:
            try:
                value = float(payload)
                # Map to appropriate parameter based on command
                if "volume" in command:
                    params["level"] = int(value)  # Volume typically integer
                else:
                    params["value"] = value
            except ValueError:
                params["value"] = payload
        
        return params

    def _get_scenario_control_order(self, role: str, command: str) -> int:
        """Get display order for scenario control (domain logic)."""
        # Order by role importance, then by command type
        role_order = {"power": 1, "inputs": 2, "playback": 3, "volume": 4, "menu": 5, "display": 6}
        command_order = {"on": 1, "off": 2, "play": 3, "pause": 4, "mute": 5, "set_level": 6}
        
        base_order = role_order.get(role, 10) * 100
        command_offset = command_order.get(command, 50)
        return base_order + command_offset
```

### 3.3 Infrastructure Layer Implementation - Pydantic Virtual Configs

**Create ScenarioWBConfig Pydantic Model** (`infrastructure/scenarios/models.py`):

```python
from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional, Union
from wb_mqtt_bridge.infrastructure.config.models import StandardCommandConfig

class ScenarioWBConfig(BaseModel):
    """Virtual WB configuration generated from scenario definition."""
    
    # Required BaseDeviceConfig-compatible fields
    device_id: str              # Maps to scenario_id
    device_name: str            # Maps to scenario.name
    device_class: str = "Scenario"
    config_class: str = "ScenarioWBConfig"
    commands: Dict[str, StandardCommandConfig] = Field(default_factory=dict)
    
    # WB emulation fields
    enable_wb_emulation: bool = True
    wb_controls: Optional[Dict[str, Dict[str, Any]]] = None
    wb_state_mappings: Optional[Dict[str, Union[str, List[str]]]] = None
    
    # Virtual metadata (for internal tracking)
    _source_scenario: Any = Field(exclude=True)  # Reference to original ScenarioDefinition
    _virtual_entity_type: str = Field(default="scenario", exclude=True)
    
    @classmethod
    def from_scenario(cls, scenario_definition, device_manager) -> "ScenarioWBConfig":
        """Factory method to create virtual config from scenario."""
        return cls(
            device_id=scenario_definition.scenario_id,
            device_name=scenario_definition.name,
            commands=cls._generate_virtual_commands(scenario_definition, device_manager),
            _source_scenario=scenario_definition
        )
    
    @staticmethod
    def _generate_virtual_commands(scenario, device_manager) -> Dict[str, StandardCommandConfig]:
        """Generate virtual commands from scenario structure."""
        commands = {}
        
        # Critical: Startup/Shutdown as StandardCommandConfig
        commands["startup"] = StandardCommandConfig(
            action="execute_startup_sequence",
            description="Start scenario",
            group="power",
            params=[]
        )
        
        commands["shutdown"] = StandardCommandConfig(
            action="execute_shutdown_sequence", 
            description="Stop scenario",
            group="power",
            params=[]
        )
        
        # Role-based inheritance with proper typing
        for role, device_id in scenario.roles.items():
            device = device_manager.get_device(device_id)
            if device:
                role_commands = ScenarioWBConfig._extract_role_commands(device, role)
                for cmd_name, cmd_config in role_commands.items():
                    virtual_name = f"{role}_{cmd_name}"
                    commands[virtual_name] = StandardCommandConfig(
                        action="delegate_to_role_device",
                        description=f"{role.title()} {cmd_config.description or cmd_name}",
                        group=role,
                        params=cmd_config.params or []
                    )
        
        return commands
    
    @staticmethod
    def _extract_role_commands(device, role: str) -> Dict[str, Any]:
        """Extract commands from device that match the role's functional area."""
        available_commands = device.get_available_commands()
        role_commands = {}
        
        # Map role to expected command groups
        role_group_mapping = {
            "playback": ["playback"],
            "volume": ["volume"], 
            "power": ["power"],
            "inputs": ["inputs", "apps"],
            "menu": ["menu", "navigation"],
            "display": ["screen", "display"]
        }
        
        expected_groups = role_group_mapping.get(role, [role])
        
        for cmd_name, cmd_config in available_commands.items():
            if hasattr(cmd_config, 'group') and cmd_config.group in expected_groups:
                role_commands[cmd_name] = cmd_config
        
        return role_commands
```

**Create ScenarioWBAdapter** (`infrastructure/scenarios/wb_adapter.py`):

```python
from wb_mqtt_bridge.domain.scenarios.service import ScenarioManager
from wb_mqtt_bridge.infrastructure.wb_device.service import WBVirtualDeviceService
from .models import ScenarioWBConfig
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class ScenarioWBAdapter:
    """Infrastructure adapter for Scenario WB virtual device functionality using shared service."""
    
    def __init__(self, scenario_manager: ScenarioManager, wb_service: WBVirtualDeviceService, device_manager):
        self.scenario_manager = scenario_manager
        self.wb_service = wb_service
        self.device_manager = device_manager

    async def setup_wb_virtual_device_for_scenario(self, scenario):
        """Set up scenario WB device using shared service with Pydantic virtual config."""
        
        # Generate strongly-typed virtual config (preserves scenario config files unchanged)
        virtual_config = ScenarioWBConfig.from_scenario(
            scenario.definition, 
            self.device_manager
        )
        
        # Use shared service with Pydantic model (maintains type safety)
        success = await self.wb_service.setup_wb_device_from_config(
            config=virtual_config,  # Pydantic model, not Dict
            command_executor=self._execute_scenario_command,
            driver_name="wb_mqtt_bridge_scenario", 
            device_type="scenario",
            entity_id=scenario.definition.scenario_id,      # Virtual entity abstraction
            entity_name=scenario.definition.name           # Virtual entity abstraction
        )
        
        return success

    async def cleanup_scenario_wb_device(self, scenario):
        """Clean up scenario WB device using shared service."""
        await self.wb_service.cleanup_wb_device(scenario.scenario_id)

    def get_scenario_subscription_topics(self, scenario) -> List[str]:
        """Get MQTT subscription topics using shared service."""
        virtual_config = ScenarioWBConfig.from_scenario(scenario.definition, self.device_manager)
        return self.wb_service.get_subscription_topics_from_config(virtual_config)

    async def handle_scenario_wb_message(self, topic: str, payload: str, scenario):
        """Handle MQTT messages using shared service routing."""
        return await self.wb_service.handle_wb_message(topic, payload, scenario.scenario_id)
        
    async def _execute_scenario_command(self, control_name: str, payload: str, params: Dict[str, Any]):
        """Command executor callback for scenario WB service."""
        if control_name == "startup":
            # Execute startup sequence
            return await self.scenario_manager.execute_startup_sequence()
        elif control_name == "shutdown":
            # Execute shutdown sequence  
            return await self.scenario_manager.execute_shutdown_sequence()
        elif "_" in control_name:
            # Role-based command delegation
            role, command = control_name.split("_", 1)
            return await self.scenario_manager.execute_role_action(role, command, params)
        else:
            raise ValueError(f"Unknown scenario command: {control_name}")
```

### 3.4 Application Layer Integration - Enhanced WB Service

**Update Bootstrap** (`app/bootstrap.py`):

```python
# Add to create_app() function in bootstrap.py

async def setup_scenario_wb_integration(app_state):
    """Set up scenario WB virtual device integration (application wiring)."""
    # Create scenario WB adapter using shared WB service (infrastructure)
    scenario_wb_adapter = ScenarioWBAdapter(
        scenario_manager=app_state.scenario_manager,
        wb_service=app_state.wb_virtual_device_service,  # Shared WB service
        device_manager=app_state.device_manager          # For virtual config generation
    )
    
    # Store adapter in app state for lifecycle management
    app_state.scenario_wb_adapter = scenario_wb_adapter
    
    # Set up WB device for current scenario if any
    if app_state.scenario_manager.current_scenario:
        await scenario_wb_adapter.setup_wb_virtual_device_for_scenario(
            app_state.scenario_manager.current_scenario
        )

async def setup_mqtt_subscriptions(app_state):
    """Set up MQTT subscriptions (application wiring)."""
    # Existing device subscriptions
    for device in app_state.device_manager.devices.values():
        topics = device.subscribe_topics()
        for topic in topics:
            await app_state.mqtt_client.subscribe(topic, device.handle_message)
    
    # NEW: Add scenario subscriptions  
    if (app_state.scenario_manager.current_scenario and 
        hasattr(app_state, 'scenario_wb_adapter')):
        scenario_topics = app_state.scenario_wb_adapter.get_scenario_subscription_topics(
            app_state.scenario_manager.current_scenario
        )
        for topic in scenario_topics:
            async def scenario_message_handler(topic=topic, payload=""):
                await app_state.scenario_wb_adapter.handle_scenario_wb_message(
                    topic, payload, app_state.scenario_manager.current_scenario
                )
            
            await app_state.mqtt_client.subscribe(topic, scenario_message_handler)
```

### 3.5 Domain Service Integration

**Update ScenarioManager.switch_scenario** (`domain/scenarios/service.py`):

```python
# In ScenarioManager class - coordinate with infrastructure via events/callbacks

class ScenarioManager:
    def __init__(self, message_bus: MessageBusPort, device_manager, state_repository: StateRepositoryPort):
        self.message_bus = message_bus
        self.device_manager = device_manager  
        self.state_repository = state_repository
        self._scenario_change_callbacks = []  # For infrastructure coordination

    def add_scenario_change_callback(self, callback):
        """Add callback for scenario change events (for infrastructure coordination)."""
        self._scenario_change_callbacks.append(callback)

    async def switch_scenario(self, target_id: str, *, graceful: bool = True) -> Dict[str, Any]:
        # ... existing scenario switch logic ...
        
        # Notify infrastructure layers of scenario change
        old_scenario = self.current_scenario
        
        # ... switch to new scenario ...
        
        self.current_scenario = incoming
        
        # Notify callbacks (infrastructure will handle WB device lifecycle)
        for callback in self._scenario_change_callbacks:
            await callback(old_scenario=old_scenario, new_scenario=self.current_scenario)
        
        # ... rest of existing logic ...
```

**Wire callback in bootstrap**:

```python
# In bootstrap.py setup
async def setup_scenario_change_handler(app_state):
    """Set up scenario change handling (application wiring)."""
    
    async def handle_scenario_change(old_scenario, new_scenario):
        """Handle scenario change for WB integration (application coordination)."""
        # Clean up old scenario WB device
        if old_scenario:
            await app_state.scenario_wb_adapter.cleanup_scenario_wb_device(old_scenario)
        
        # Set up new scenario WB device
        if new_scenario:
            await app_state.scenario_wb_adapter.setup_wb_virtual_device_for_scenario(new_scenario)
            
            # Update MQTT subscriptions
            await setup_mqtt_subscriptions(app_state)
    
    # Register callback with domain service
    app_state.scenario_manager.add_scenario_change_callback(handle_scenario_change)
```

---

## 4 Implementation Plan - Pydantic Virtual Configuration Approach

### Phase 1: Pydantic Virtual Config Models
1. **Create ScenarioWBConfig** Pydantic model in `infrastructure/scenarios/models.py`
2. **Implement factory method** `from_scenario()` for virtual config generation
3. **Add role-based command extraction** using existing device group system
4. **Ensure full BaseDeviceConfig compatibility** with type safety

### Phase 2: Enhanced WB Service Support
1. **Enhance WBVirtualDeviceService** to support entity ID and name overrides for virtual devices
2. **Update service interface** to accept `entity_id` and `entity_name` parameters
3. **Test virtual device abstraction** with scenario configs

### Phase 3: Infrastructure Layer with Shared Service
1. **Create ScenarioWBAdapter** in `infrastructure/scenarios/wb_adapter.py` using shared WB service
2. **Implement virtual config generation** from scenario definitions (preserves scenario config files unchanged)
3. **Use WBVirtualDeviceService** for all WB operations instead of direct MQTT
4. **Add command executor callback** for scenario command routing

### Phase 4: Application Layer Wiring
1. **Update bootstrap.py** to inject shared WB service into scenario adapter
2. **Wire scenario lifecycle events** with WB device management
3. **Test end-to-end** scenario WB functionality with type safety

### Phase 5: Validation & Documentation
1. **Verify scenario config files remain unchanged** throughout implementation
2. **Test startup/shutdown sequences** as critical power group commands
3. **Validate role-based command delegation** to underlying devices
4. **Document virtual configuration approach** and usage patterns

---

## 5 Benefits

### ✅ **Architectural Consistency**
- Follows established domain-centric architecture
- Proper separation of concerns between domain, infrastructure, and application layers
- Maintains dependency inversion with port/adapter pattern

### ✅ **Proven Pattern**
- Reuses the exact BaseDevice WB pattern that's already working
- No new concepts - just applying existing proven implementation in new architecture

### ✅ **Minimal Changes**
- No device config changes required
- Builds on existing scenario architecture
- Leverages existing role system and group categorization

### ✅ **Integration**
- Scenarios appear natively in WB UI
- MQTT control interface for scenarios  
- Consistent with individual device patterns

### ✅ **Maintainability**
- Clean separation between business logic and infrastructure concerns
- Domain layer remains pure (no I/O dependencies)
- Infrastructure adapters handle WB-specific MQTT patterns
- Application layer coordinates between domain and infrastructure

---

## 6 Next Steps

1. **Implement domain layer extensions** in `ScenarioManager` (business logic only)
2. **Create infrastructure adapter** in `infrastructure/scenarios/wb_adapter.py`
3. **Update application bootstrap** for scenario WB wiring and lifecycle management
4. **Test role-based controls** work correctly through WB interface

This approach provides scenario MQTT/WB integration by applying the proven BaseDevice pattern within the new domain-centric architecture, ensuring consistency, maintainability, and proper separation of concerns while enabling scenarios to appear natively in the Wirenboard ecosystem.

---
*© 2025 – droman42 / contributors* 