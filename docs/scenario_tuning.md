# Scenario System Enhancement: WB Virtual Device Integration
*Version: 2025-01-03-basedevice-pattern*

---

## 1 Problem Statement

The current scenario system provides excellent **device aggregation** and the existing `group` parameter already provides good functional categorization. However, scenarios are only accessible via REST API, limiting their integration with the Wirenboard ecosystem.

### Current Limitations
- **No MQTT Interface**: Scenarios cannot be controlled via MQTT
- **WB UI Gap**: Scenarios don't appear in Wirenboard web interface
- **Client Complexity**: REST clients need to understand which device fills which role for each scenario

### What Works Well ✅
- **Scenario Architecture**: One `Scenario` class + multiple JSON configs (already aligned with requirements)
- **Device Configs**: Already well-structured with good group categorization
- **Parameter Handling**: `BaseDevice` handles type conversion, validation, defaults at runtime
- **WB Device Pattern**: Already implemented and proven in `BaseDevice` class (PR #1)

---

## 2 Proposed Solution: Apply BaseDevice WB Pattern to Scenarios

Extend `ScenarioManager` to implement the same **WB virtual device pattern** used by `BaseDevice`, creating virtual devices for scenarios that expose standardized group-based controls.

### Core Concept
```
/devices/movie_ld/controls/playback_play/on        → scenario.execute_role_action("playback", "play")
/devices/movie_ld/controls/playbook_pause/on       → scenario.execute_role_action("playbook", "pause")
/devices/movie_ld/controls/volume_set_level/on     → scenario.execute_role_action("volume", "set_volume", {"level": payload})
/devices/movie_ld/controls/volume_mute/on          → scenario.execute_role_action("volume", "mute")
```

Each active scenario becomes a WB virtual device with **role-prefixed controls** that route to `scenario.execute_role_action()`.

---

## 3 Implementation: Follow BaseDevice WB Pattern

### 3.1 BaseDevice Pattern Analysis ✅

**Current BaseDevice WB Implementation:**
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

### 3.2 Apply Pattern to ScenarioManager

**Add to ScenarioManager class:**

#### Step 1: WB Virtual Device Generation
```python
async def _setup_wb_virtual_device_for_scenario(self, scenario: Scenario):
    """Set up WB virtual device for active scenario (mirrors BaseDevice pattern)."""
    # Publish scenario device metadata
    await self._publish_scenario_wb_device_meta(scenario)
    
    # Generate controls based on scenario roles and available device commands
    await self._publish_scenario_wb_control_metas(scenario)
    
    # Setup Last Will Testament for scenario offline detection
    await self._setup_scenario_wb_last_will(scenario)

async def _publish_scenario_wb_device_meta(self, scenario: Scenario):
    """Publish WB device metadata for scenario (mirrors BaseDevice._publish_wb_device_meta)."""
    device_meta = {
        "driver": "wb_mqtt_bridge_scenario",
        "title": {"en": scenario.definition.name},
        "type": "scenario"
    }
    
    topic = f"/devices/{scenario.scenario_id}/meta"
    await self.mqtt_client.publish(topic, json.dumps(device_meta), retain=True)

async def _publish_scenario_wb_control_metas(self, scenario: Scenario):
    """Generate and publish WB controls for scenario roles (mirrors BaseDevice._publish_wb_control_metas)."""
    # For each role, analyze assigned device's available commands by group
    for role, device_id in scenario.definition.roles.items():
        device = self.device_manager.get_device(device_id)
        if not device:
            continue
            
        # Get device commands grouped by the role's functional area
        role_commands = self._get_role_commands_for_device(device, role)
        
        for command_name, command_config in role_commands.items():
            control_name = f"{role}_{command_name}"  # e.g., "playback_play", "volume_set_level"
            
            # Generate control metadata (mirrors BaseDevice._generate_wb_control_meta_from_config)
            control_meta = self._generate_scenario_control_meta(role, command_name, command_config)
            
            # Publish control metadata
            meta_topic = f"/devices/{scenario.scenario_id}/controls/{control_name}/meta"
            await self.mqtt_client.publish(meta_topic, json.dumps(control_meta), retain=True)
            
            # Publish initial control state
            initial_state = self._get_initial_scenario_control_state(command_config)
            state_topic = f"/devices/{scenario.scenario_id}/controls/{control_name}"
            await self.mqtt_client.publish(state_topic, str(initial_state), retain=True)
```

#### Step 2: Topic Subscription (Add to ScenarioManager)
```python
def subscribe_scenario_topics(self) -> List[str]:
    """Get MQTT topics for active scenario WB controls (mirrors BaseDevice.subscribe_topics)."""
    if not self.current_scenario:
        return []
        
    topics = []
    scenario = self.current_scenario
    
    # Subscribe to WB command topics for all scenario controls
    for role, device_id in scenario.definition.roles.items():
        device = self.device_manager.get_device(device_id)
        if not device:
            continue
            
        role_commands = self._get_role_commands_for_device(device, role)
        for command_name in role_commands.keys():
            control_name = f"{role}_{command_name}"
            command_topic = f"/devices/{scenario.scenario_id}/controls/{control_name}/on"
            topics.append(command_topic)
    
    return topics

async def handle_scenario_message(self, topic: str, payload: str):
    """Handle MQTT messages for scenario WB controls (mirrors BaseDevice.handle_message)."""
    if not self.current_scenario:
        return
        
    # Check if this is a scenario WB command topic (mirrors BaseDevice._is_wb_command_topic)
    if self._is_scenario_wb_command_topic(topic):
        await self._handle_scenario_wb_command(topic, payload)

def _is_scenario_wb_command_topic(self, topic: str) -> bool:
    """Check if topic is a scenario WB command topic (mirrors BaseDevice._is_wb_command_topic)."""
    if not self.current_scenario:
        return False
    pattern = f"/devices/{re.escape(self.current_scenario.scenario_id)}/controls/(.+)/on"
    return bool(re.match(pattern, topic))

async def _handle_scenario_wb_command(self, topic: str, payload: str):
    """Handle scenario WB command (mirrors BaseDevice._handle_wb_command)."""
    # Extract control name from topic: "role_command"
    match = re.match(f"/devices/{re.escape(self.current_scenario.scenario_id)}/controls/(.+)/on", topic)
    if not match:
        return
        
    control_name = match.group(1)  # e.g., "playback_play", "volume_set_level"
    
    # Parse role and command from control name
    if "_" not in control_name:
        logger.warning(f"Invalid scenario control name format: {control_name}")
        return
        
    role, command = control_name.split("_", 1)
    
    # Process parameters from payload (mirrors BaseDevice._process_wb_command_payload_from_config)
    params = self._process_scenario_wb_command_payload(role, command, payload)
    
    # Execute role action using existing scenario system
    try:
        await self.execute_role_action(role, command, params)
        
        # Update WB control state (mirrors BaseDevice._update_wb_control_state)
        await self._update_scenario_wb_control_state(control_name, payload)
    except Exception as e:
        logger.error(f"Error executing scenario role action {role}.{command}: {str(e)}")
```

#### Step 3: Helper Methods (Role Command Discovery)
```python
def _get_role_commands_for_device(self, device: BaseDevice, role: str) -> Dict[str, Any]:
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
    """Generate WB control metadata for scenario control (mirrors BaseDevice._generate_wb_control_meta_from_config)."""
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
    """Process scenario WB command payload into parameters (mirrors BaseDevice._process_wb_command_payload)."""
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
```

### 3.3 Integration Points

#### Step 4: MQTT Client Integration (Modify existing MQTT setup)
```python
# In main.py or wherever MQTT subscriptions are handled
# Add scenario topic subscriptions alongside device topics

async def setup_mqtt_subscriptions():
    # Existing device subscriptions
    for device in device_manager.devices.values():
        topics = device.subscribe_topics()
        for topic in topics:
            await mqtt_client.subscribe(topic, device.handle_message)
    
    # NEW: Add scenario subscriptions  
    scenario_topics = scenario_manager.subscribe_scenario_topics()
    for topic in scenario_topics:
        await mqtt_client.subscribe(topic, scenario_manager.handle_scenario_message)
```

#### Step 5: Scenario Lifecycle Integration (Modify ScenarioManager.switch_scenario)
```python
async def switch_scenario(self, target_id: str, *, graceful: bool = True) -> Dict[str, Any]:
    # ... existing scenario switch logic ...
    
    # NEW: Clean up WB virtual device for previous scenario
    if self.current_scenario:
        await self._cleanup_scenario_wb_device(self.current_scenario)
    
    # ... switch to new scenario ...
    
    # NEW: Set up WB virtual device for new scenario
    self.current_scenario = incoming
    await self._setup_wb_virtual_device_for_scenario(self.current_scenario)
    
    # NEW: Update MQTT subscriptions for new scenario
    await self._update_scenario_mqtt_subscriptions()
    
    # ... rest of existing logic ...
```

---

## 4 Implementation Plan

### Phase 1: Core WB Virtual Device Generation
1. **Add WB device methods to ScenarioManager** following BaseDevice pattern
2. **Implement role command discovery** using existing device group system
3. **Generate WB controls** for role + command combinations

### Phase 2: MQTT Integration  
1. **Add scenario topic subscription** alongside device topics
2. **Route scenario MQTT messages** to ScenarioManager.handle_scenario_message()
3. **Parse and execute role actions** from WB command topics

### Phase 3: Lifecycle Integration
1. **WB device generation** when scenario becomes active
2. **WB device cleanup** when scenario switches
3. **MQTT subscription updates** during scenario transitions

### Phase 4: State Synchronization
1. **Sync scenario control states** based on underlying device states
2. **Handle parameter mapping** between WB controls and device commands
3. **Update control states** after role actions

---

## 5 Benefits

### ✅ **Proven Pattern**
- Reuses the exact BaseDevice WB pattern that's already working
- No new concepts - just applying existing proven implementation

### ✅ **Minimal Changes**
- No device config changes required
- Builds on existing scenario architecture
- Leverages existing role system and group categorization

### ✅ **Integration**
- Scenarios appear natively in WB UI
- MQTT control interface for scenarios  
- Consistent with individual device patterns

### ✅ **Maintainability**
- Same patterns developers already understand
- Clear separation of concerns
- Reuses existing parameter handling and validation

---

## 6 Next Steps

1. **Implement ScenarioManager WB methods** following BaseDevice pattern exactly
2. **Add scenario MQTT subscription** to existing MQTT setup
3. **Integrate with scenario lifecycle** for WB device generation/cleanup
4. **Test role-based controls** work correctly through WB interface

This approach provides scenario MQTT/WB integration by applying the proven BaseDevice pattern, ensuring consistency and maintainability while enabling scenarios to appear natively in the Wirenboard ecosystem.

---
*© 2025 – droman42 / contributors* 