# Wirenboard Virtual Device Emulation Implementation Plan

## Overview and Motivation

This document outlines the implementation strategy for emulating Wirenboard (WB) virtual devices from our external Python service (`wb-mqtt-bridge`) via MQTT. Instead of defining virtual devices in `wb-rules`, our Python service will act as a **custom MQTT driver/publisher** that adheres to all Wirenboard MQTT conventions, making each device appear and behave identically to native WB devices.

**Key Benefits:**
- **Single Source of Truth**: Python service remains authoritative for device state and logic
- **No Sync Issues**: Eliminates drift between static WB definitions and dynamic Python logic
- **Native Integration**: Devices appear in WB web interface exactly like built-in devices
- **Automatic Discovery**: No manual WB device configuration required

## Wirenboard MQTT Device Conventions

Based on WB's official MQTT conventions, each device must follow this standardized topic hierarchy:

### Device-Level Topics

**Device Metadata**: `/devices/<device_id>/meta`
```json
{
  "driver": "wb_mqtt_bridge",
  "title": {"en": "Living Room TV", "ru": "Телевизор в гостиной"}
}
```
- Must be **retained** for persistence
- `driver` identifies our service as the device publisher
- `title` provides localized display names

**Device Error Topic**: `/devices/<device_id>/meta/error`
- Set to non-null value when device is offline/error state
- Use MQTT Last Will Testament to set "offline" if service disconnects
- Clear (set to null) when device is healthy

### Control-Level Topics

**Control Metadata**: `/devices/<device_id>/controls/<control_name>/meta`
```json
{
  "type": "range",
  "min": 0,
  "max": 100,
  "units": "%",
  "order": 2,
  "readonly": false,
  "title": {"en": "Volume", "ru": "Громкость"}
}
```

**Control State**: `/devices/<device_id>/controls/<control_name>`
- Current value of the control (e.g., `"50"` for 50% volume)
- Must be **retained** for persistence
- Published by our service when state changes

**Control Commands**: `/devices/<device_id>/controls/<control_name>/on`
- WB UI and other clients send commands here
- Our service subscribes to these topics
- Values sent here trigger our device handlers

### Control Types and Expected Behavior

| Type | Description | Value Format | UI Behavior |
|------|-------------|--------------|-------------|
| `switch` | Binary on/off toggle | `"0"` or `"1"` | Toggle switch |
| `range` | Numeric slider | `"0"` to `"100"` | Slider with min/max |
| `value` | Numeric display | Any number | Read-only display |
| `text` | Text status | Any string | Text display |
| `pushbutton` | Momentary action | `"1"` when pressed | Button (non-retained) |

## Current Architecture Analysis

### Existing MQTT Topic Structure

Our current device configurations explicitly define MQTT topics:
```json
{
  "commands": {
    "power_on": {
      "action": "power_on",
      "topic": "/devices/living_room_tv/controls/power_on",
      "description": "Power On",
      "group": "power"
    }
  }
}
```

**Key Finding**: Current topics already follow WB conventions! We just need to add:
- Device and control metadata publishing
- Subscription to `/on` command topics
- Proper retained message handling

### Handler Registration Mechanism

BaseDevice uses two registration methods:
1. **Manual**: `_register_handlers()` method (overridden by subclasses)
2. **Automatic**: `_auto_register_handlers()` discovers `handle_*` methods

Current flow:
```python
# Auto-discovered handler
async def handle_power_on(self, cmd_config, params) -> CommandResult:
    # Implementation

# Gets registered as:
self._action_handlers['power_on'] = self.handle_power_on
```

### MQTT Message Flow

Current message handling in BaseDevice:
1. `subscribe_topics()` returns list of topics from config
2. `handle_message()` finds matching command by topic
3. Calls `_execute_single_action()` with handler and parameters

## Implementation Strategy: Option 1 - Pure BaseDevice Integration

### Core Approach

Add WB virtual device emulation directly to BaseDevice class with automatic activation for all devices. This leverages existing infrastructure and requires minimal code changes.

### Key Components

#### 1. BaseDevice Constructor Enhancement
```python
class BaseDevice(ABC, Generic[StateT]):
    def __init__(self, config: BaseDeviceConfig, mqtt_client: Optional["MQTTClient"] = None):
        # ... existing initialization ...
        
        # Register action handlers (existing)
        self._register_handlers()
        self._build_action_groups_index()
        self._auto_register_handlers()
        
        # NEW: Add WB virtual device publishing
        if self.should_publish_wb_virtual_device():
            self._setup_wb_virtual_device()
```

#### 2. WB Virtual Device Setup
```python
def _setup_wb_virtual_device(self):
    """Set up Wirenboard virtual device emulation."""
    if not self.mqtt_client:
        logger.warning(f"Cannot setup WB virtual device for {self.device_id}: no MQTT client")
        return
    
    # Publish device metadata
    self._publish_wb_device_meta()
    
    # Publish control metadata and initial states
    self._publish_wb_control_metas()
    
    # Set up Last Will Testament for offline detection
    self._setup_wb_last_will()
    
    logger.info(f"WB virtual device emulation enabled for {self.device_id}")
```

#### 3. Device Metadata Publishing
```python
def _publish_wb_device_meta(self):
    """Publish WB device metadata."""
    device_meta = {
        "driver": "wb_mqtt_bridge",
        "title": {"en": self.device_name}
    }
    
    topic = f"/devices/{self.device_id}/meta"
    self.mqtt_client.publish(topic, json.dumps(device_meta), retain=True)
    logger.debug(f"Published WB device meta for {self.device_id}")
```

#### 4. Control Metadata Generation
```python
def _publish_wb_control_metas(self):
    """Publish WB control metadata for all handlers."""
    for handler_name in self._action_handlers:
        if not handler_name.startswith('_'):
            control_meta = self._generate_wb_control_meta(handler_name)
            
            # Publish control metadata
            meta_topic = f"/devices/{self.device_id}/controls/{handler_name}/meta"
            self.mqtt_client.publish(meta_topic, json.dumps(control_meta), retain=True)
            
            # Publish initial control state
            initial_state = self._get_initial_wb_control_state(handler_name)
            state_topic = f"/devices/{self.device_id}/controls/{handler_name}"
            self.mqtt_client.publish(state_topic, str(initial_state), retain=True)
            
            logger.debug(f"Published WB control meta for {self.device_id}/{handler_name}")
```

#### 5. Smart Control Type Detection
```python
def _generate_wb_control_meta(self, handler_name: str) -> Dict[str, Any]:
    """Generate WB control metadata with smart defaults."""
    
    # Check for explicit WB configuration in device config
    if hasattr(self.config, 'wb_controls') and handler_name in self.config.wb_controls:
        return self.config.wb_controls[handler_name]
    
    # Generate smart defaults based on handler name
    meta = {
        "title": {"en": handler_name.replace('_', ' ').title()},
        "readonly": False,
        "order": self._get_control_order(handler_name)
    }
    
    # Smart type detection based on naming patterns
    handler_lower = handler_name.lower()
    
    if any(x in handler_lower for x in ['power_on', 'power_off', 'play', 'pause', 'stop']):
        meta["type"] = "pushbutton"
    elif 'set_volume' in handler_lower or 'volume' in handler_lower:
        meta.update({
            "type": "range",
            "min": 0,
            "max": 100,
            "units": "%"
        })
    elif 'mute' in handler_lower:
        meta["type"] = "switch"
    elif 'set_' in handler_lower:
        meta["type"] = "range"  # Generic setter
    elif any(x in handler_lower for x in ['get_', 'list_', 'available']):
        meta.update({
            "type": "text",
            "readonly": True
        })
    else:
        meta["type"] = "pushbutton"  # Default for actions
    
    return meta
```

#### 6. Enhanced Topic Subscription
```python
def subscribe_topics(self) -> List[str]:
    """Enhanced to include WB command topics."""
    topics = []
    
    # Add existing configured topics
    for cmd in self.get_available_commands().values():
        if cmd.topic:
            topics.append(cmd.topic)
    
    # Add WB command topics for virtual device emulation
    if self.should_publish_wb_virtual_device():
        for handler_name in self._action_handlers:
            if not handler_name.startswith('_'):
                command_topic = f"/devices/{self.device_id}/controls/{handler_name}/on"
                topics.append(command_topic)
    
    return topics
```

#### 7. WB Command Message Handling
```python
async def handle_message(self, topic: str, payload: str):
    """Enhanced message handling for WB command topics."""
    
    # Check if this is a WB command topic
    if self._is_wb_command_topic(topic):
        await self._handle_wb_command(topic, payload)
        return
    
    # Existing message handling logic
    # ... existing implementation ...

def _is_wb_command_topic(self, topic: str) -> bool:
    """Check if topic is a WB command topic."""
    pattern = f"/devices/{self.device_id}/controls/(.+)/on"
    return bool(re.match(pattern, topic))

async def _handle_wb_command(self, topic: str, payload: str):
    """Handle WB command topic messages."""
    # Extract control name from topic
    match = re.match(f"/devices/{self.device_id}/controls/(.+)/on", topic)
    if not match:
        return
    
    control_name = match.group(1)
    
    # Find corresponding handler
    if control_name in self._action_handlers:
        # Create minimal command config for WB commands
        wb_cmd_config = BaseCommandConfig(
            action=control_name,
            topic=topic,
            description=f"WB command for {control_name}"
        )
        
        # Process parameters from payload
        params = self._process_wb_command_payload(control_name, payload)
        
        # Execute the handler
        await self._execute_single_action(control_name, wb_cmd_config, params, source="wb_command")
        
        # Update WB control state to reflect the command
        await self._update_wb_control_state(control_name, payload)
```

#### 8. State Synchronization
```python
def update_state(self, **updates):
    """Enhanced state update with WB synchronization."""
    # Existing state update logic
    # ... existing implementation ...
    
    # Sync relevant state changes to WB control topics
    if self.should_publish_wb_virtual_device():
        self._sync_state_to_wb_controls(updates)

def _sync_state_to_wb_controls(self, state_updates: Dict[str, Any]):
    """Synchronize state changes to WB control topics."""
    if not self.mqtt_client:
        return
    
    # Map state fields to WB controls
    wb_control_mappings = {
        'power': 'power_state',
        'volume': 'volume_level',
        'mute': 'mute_state',
        'connected': 'connection_status'
    }
    
    for state_field, wb_control in wb_control_mappings.items():
        if state_field in state_updates and wb_control in self._action_handlers:
            value = state_updates[state_field]
            wb_value = self._convert_state_to_wb_value(state_field, value)
            
            control_topic = f"/devices/{self.device_id}/controls/{wb_control}"
            self.mqtt_client.publish(control_topic, str(wb_value), retain=True)
```

### Configuration Enhancement (Optional)

For devices requiring specific WB control definitions:

```python
# Enhanced device configuration schema
class BaseDeviceConfig(BaseModel):
    # ... existing fields ...
    
    # NEW: Optional WB virtual device configuration
    enable_wb_emulation: bool = True
    wb_controls: Optional[Dict[str, Dict[str, Any]]] = None

# Example device configuration
{
  "device_id": "living_room_tv",
  "device_name": "LG OLED77G1RLA",
  "device_class": "LgTv",
  "enable_wb_emulation": true,
  "wb_controls": {
    "set_volume": {
      "type": "range",
      "min": 0,
      "max": 100,
      "units": "%",
      "title": {"en": "Volume", "ru": "Громкость"},
      "order": 10
    },
    "power_on": {
      "type": "pushbutton",
      "title": {"en": "Power On"},
      "order": 1
    }
  },
  "commands": {
    // ... existing commands ...
  }
}
```

## Configuration Migration Strategy

### Current vs. Future State

**Current Config (with explicit topics):**
```json
{
  "commands": {
    "power_on": {
      "action": "power_on",
      "topic": "/devices/living_room_tv/controls/power_on",
      "description": "Power On",
      "group": "power"
    }
  }
}
```

**Future Config (auto-generated topics):**
```json
{
  "commands": {
    "power_on": {
      "action": "power_on",
      "description": "Power On", 
      "group": "power"
      // topic auto-generated as: /devices/{device_id}/controls/power_on
    }
  }
}
```

### Transition Strategy

#### Phase A: Dual Support (Backward Compatible)
- Keep explicit `topic` field working for existing configs
- Auto-generate topics when `topic` field is missing
- WB virtual device emulation uses auto-generated topics regardless

```python
def get_command_topic(self, handler_name: str, cmd_config: BaseCommandConfig) -> str:
    """Get topic for command - explicit or auto-generated."""
    if cmd_config.topic:
        return cmd_config.topic  # Use explicit topic if provided
    else:
        return f"/devices/{self.device_id}/controls/{handler_name}"  # Auto-generate
```

#### Phase B: Deprecation Warning
- Add warning when explicit topics are used
- Document migration path in config files
- Update all example configs to use auto-generated topics

#### Phase C: Remove Explicit Topics
- Remove `topic` field from config schema
- All topics auto-generated based on handler names
- Clean up all existing device configuration files

### Benefits of Auto-Generated Topics

1. **✅ Simplification**: Cleaner, shorter config files
2. **✅ Consistency**: All devices follow same WB naming convention  
3. **✅ Less Maintenance**: No manual topic management
4. **✅ WB Compliance**: Auto-generated topics always follow WB conventions
5. **✅ Reduced Errors**: No topic typos or mismatches

### What Remains in Config

Command configs keep the **essential metadata**:
```json
{
  "commands": {
    "set_volume": {
      "action": "set_volume",
      "description": "Set volume level",
      "group": "audio",
      "parameters": {
        "volume": {"type": "integer", "min": 0, "max": 100}
      }
    }
  }
}
```

### Special Cases

For devices requiring **non-WB topics** (integration with other systems), a separate configuration section can be used:
```json
{
  "commands": {
    // Standard WB commands (auto-generated topics)
  },
  "custom_integrations": {
    "legacy_system": {
      "topic": "/legacy/custom/topic",
      "handler": "handle_legacy_command"
    }
  }
}
```

## Implementation Plan

### Phase 1: Core Infrastructure + Backward Compatibility (Week 1)
1. **Add WB emulation methods to BaseDevice**
   - `_setup_wb_virtual_device()`
   - `_publish_wb_device_meta()`
   - `_publish_wb_control_metas()`
   - `_generate_wb_control_meta()`

2. **Enhance MQTT topic subscription**
   - Update `subscribe_topics()` to include WB command topics
   - Add WB command detection and routing in `handle_message()`

3. **Add configuration support**
   - Add `enable_wb_emulation` flag to BaseDeviceConfig
   - Add `should_publish_wb_virtual_device()` method

4. **Implement Configuration Migration Phase A**
   - Add `get_command_topic()` method for dual support
   - Support both explicit and auto-generated topics
   - Ensure WB emulation always uses auto-generated topics

### Phase 2: Smart Defaults and State Sync (Week 2)
1. **Implement smart control type detection**
   - Handler name pattern matching
   - Automatic type assignment (switch, range, pushbutton, etc.)
   - Default value generation

2. **Add state synchronization**
   - Update `update_state()` to publish WB control states
   - Implement bidirectional state mapping
   - Handle retained message publishing

### Phase 3: Advanced Features + Configuration Migration Phase B (Week 3)
1. **Last Will Testament integration**
   - Set up LWT for device offline detection
   - Integrate with existing maintenance guard system

2. **Enhanced configuration support**
   - Add `wb_controls` configuration section
   - Support for explicit control definitions
   - Validation and error handling

3. **Implement Configuration Migration Phase B**
   - Add deprecation warnings for explicit `topic` fields
   - Update all example configurations to remove explicit topics
   - Document migration path for existing installations

4. **Testing and validation**
   - Test with WB controller
   - Verify all device types work correctly
   - Performance testing with multiple devices

### Phase 4: Configuration Migration Phase C + Documentation (Week 4)
1. **Complete Configuration Migration Phase C**
   - Remove `topic` field from BaseCommandConfig schema
   - Clean up all existing device configuration files
   - Ensure all topics are auto-generated

2. **Documentation updates**
   - Update device configuration examples
   - Add WB emulation configuration guide
   - Update API documentation

3. **Migration guide**
   - Document enabling/disabling WB emulation
   - Configuration migration examples
   - Troubleshooting guide

## Technical Considerations

### MQTT Message Handling
- **Retained Messages**: All WB meta and state topics must use `retain=True`
- **QoS Levels**: Use QoS 1 for reliable delivery of meta topics
- **Topic Permissions**: Ensure MQTT broker allows publishing to `/devices/*` topics

### Performance Impact
- **Startup**: Additional MQTT publishes during device initialization
- **Runtime**: Minimal overhead - only publish on state changes
- **Memory**: Small increase for WB control metadata storage

### Error Handling
- **MQTT Failures**: Graceful degradation if WB publishing fails
- **Invalid Configurations**: Validation and fallback to smart defaults
- **Device Offline**: Proper LWT setup for offline detection

### Compatibility
- **Existing Devices**: No changes required, WB emulation is automatic
- **Configuration**: Backward compatible, new fields are optional
- **WB Versions**: Compatible with all modern Wirenboard firmware

## Expected Outcomes

### Device Appearance in WB Interface
Each device will appear as a native WB device with:
- Device card showing device name and status
- Controls organized by type (switches, sliders, buttons)
- Real-time state updates
- Interactive control via WB web interface

### Example: LG TV Device
```
Device: Living Room TV (living_room_tv)
Driver: wb_mqtt_bridge

Controls:
├── Power On [Button]
├── Power Off [Button]  
├── Volume [Slider 0-100%]
├── Mute [Switch]
├── Home [Button]
├── Back [Button]
└── Set Input Source [Text Input]
```

### MQTT Topic Structure
```
/devices/living_room_tv/meta                     # Device metadata
/devices/living_room_tv/controls/power_on/meta   # Control metadata
/devices/living_room_tv/controls/power_on        # Control state
/devices/living_room_tv/controls/power_on/on     # Control command
/devices/living_room_tv/controls/volume/meta     # Volume metadata
/devices/living_room_tv/controls/volume          # Volume state (0-100)
/devices/living_room_tv/controls/volume/on       # Volume command
```

## Next Steps

1. **Review and approve** this implementation plan
2. **Create feature branch** for WB virtual device emulation
3. **Implement Phase 1** core infrastructure
4. **Test with single device** (e.g., LG TV) against WB controller
5. **Iterate and refine** based on testing results
6. **Roll out to all device types** progressively

This approach provides a clean, automatic way to expose all your existing devices as native Wirenboard virtual devices while maintaining your Python service as the single source of truth for device logic and state management. 