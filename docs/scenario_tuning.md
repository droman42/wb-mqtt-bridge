# Scenario System Enhancement: Role Interface Standardization
*Version: 2025-01-03-draft*

---

## 1 Problem Statement

The current scenario system provides **device aggregation** but lacks **command interface abstraction**. This creates several issues:

### Current Limitations
- **Device-Specific UI Logic**: UI clients must know individual device command interfaces
- **Incomplete Role Abstraction**: Roles identify devices but don't standardize interfaces
- **Scenario Incompatibility**: Switching scenarios may break UI functionality
- **Command Fragmentation**: Same logical action requires different commands across devices

### Example Problem
```json
// LD Player scenario - UI must use:
{"role": "playback", "command": "play", "params": {}}

// VHS Player scenario - UI must use: 
{"role": "playback", "command": "play_pause_toggle", "params": {}}
```

**Same role, different commands → UI complexity increases**

---

## 2 Solution Strategy: Role Interface Standardization

### 2.1 Core Concept
Transform scenarios from **"device locators"** into **"capability abstractors"** by adding a command translation layer between role interfaces and device implementations.

### 2.2 Architecture Components

#### A. Standard Role Command Interfaces
Define canonical command sets for each role type:

| Role Type | Standard Commands | Parameters |
|-----------|------------------|------------|
| **playback** | `play`, `pause`, `stop`, `next`, `previous`, `seek` | `position` (seconds) |
| **volume_control** | `set_level`, `mute`, `unmute`, `volume_up`, `volume_down` | `level` (0-100) |
| **screen** | `set_input`, `set_aspect_ratio`, `set_brightness` | `input`, `ratio`, `brightness` |
| **lighting** | `set_brightness`, `set_color`, `on`, `off` | `brightness` (0-100), `color` (hex) |
| **source_control** | `set_input`, `next_input`, `previous_input` | `input` (string) |

#### B. Device Capability Registration
Extend device definitions with role command mappings:

```json
{
  "device_id": "ld_player",
  "role_capabilities": {
    "playback": {
      "command_mappings": {
        "play": {"device_command": "play", "params": {}},
        "pause": {"device_command": "pause", "params": {}},
        "stop": {"device_command": "stop", "params": {}},
        "seek": {"device_command": "seek_to", "params": {"position": "position"}}
      }
    }
  }
}
```

```json
{
  "device_id": "vhs_player", 
  "role_capabilities": {
    "playback": {
      "command_mappings": {
        "play": {"device_command": "play_pause_toggle", "requires_state": "paused"},
        "pause": {"device_command": "play_pause_toggle", "requires_state": "playing"},
        "stop": {"device_command": "stop", "params": {}}
      }
    }
  }
}
```

#### C. Command Translation Layer
Add translation mechanism in scenario execution:
1. **Standard Interface Lookup**: Check if device supports standard role command
2. **Parameter Transformation**: Convert standard parameters to device-specific format
3. **State-Aware Translation**: Handle toggle commands requiring current state
4. **Fallback to Direct**: Use original command if no translation exists

#### D. Enhanced Role Definitions
Scenarios define roles with interface contracts:

```json
{
  "roles": {
    "playback": {
      "device_id": "ld_player",
      "interface": "standard_playback_v1",
      "custom_mappings": {
        "seek": {"device_command": "jump_to_chapter", "params": {"chapter": "position"}}
      }
    }
  }
}
```

---

## 3 Implementation Phases

### Phase 1: Foundation (Week 1-2)
**Goal**: Establish basic translation infrastructure

#### Tasks:
1. **Define Standard Interfaces**
   - Create `role_interfaces.json` with canonical command definitions
   - Start with `playback` and `volume_control` roles
   - Document parameter formats and validation rules

2. **Extend Device Models**
   - Add `role_capabilities` field to device configurations
   - Create Pydantic models for command mappings
   - Implement basic validation

3. **Command Translation Engine**
   - Add `RoleCommandTranslator` class
   - Implement direct mapping (1:1 command translation)
   - Add fallback to existing direct command execution

#### Success Criteria:
- LD Player and VHS Player both respond to standard `play` command
- Existing direct commands continue to work
- Translation layer has comprehensive logging

### Phase 2: State-Aware Translation (Week 3)
**Goal**: Handle complex command mappings requiring device state

#### Tasks:
1. **State-Aware Mappings**
   - Implement `requires_state` condition evaluation
   - Add device state querying before command execution
   - Handle toggle commands intelligently

2. **Parameter Transformation**
   - Add parameter mapping and validation
   - Implement range conversions (e.g., volume 0-100 → device range)
   - Add parameter defaults and constraints

3. **Error Handling Enhancement**
   - Add translation-specific error types
   - Implement retry logic for state-dependent commands
   - Provide clear error messages for unsupported operations

#### Success Criteria:
- VHS Player `play` command works correctly regardless of current state
- Volume control works consistently across different amplifier ranges
- Clear error messages when translations fail

### Phase 3: Advanced Features (Week 4)
**Goal**: Complete the abstraction with advanced capabilities

#### Tasks:
1. **Scenario-Level Overrides**
   - Allow scenarios to define custom command mappings
   - Implement inheritance from device defaults
   - Add scenario-specific parameter transformations

2. **Multi-Device Roles**
   - Support roles that coordinate multiple devices
   - Implement broadcast commands (e.g., `all_lights.off`)
   - Add conditional execution based on device states

3. **Runtime Capability Discovery**
   - Add API endpoint to query available role commands
   - Implement dynamic interface negotiation
   - Provide capability metadata to UI clients

#### Success Criteria:
- UI can query available commands for any role
- Scenarios can override default device mappings
- Multi-device coordination works reliably

### Phase 4: Integration & Polish (Week 5)
**Goal**: Complete integration with existing system

#### Tasks:
1. **API Enhancement**
   - Add `/scenario/role/{role}/capabilities` endpoint
   - Enhance existing endpoints with translation support
   - Add translation debugging endpoints

2. **Documentation & Testing**
   - Complete API documentation
   - Add comprehensive unit tests
   - Create integration test scenarios

3. **Migration Tools**
   - Create tools to migrate existing device configs
   - Add validation for role capability definitions
   - Implement configuration upgrade scripts

#### Success Criteria:
- All existing scenarios work without modification
- New role interface system is fully documented
- Migration path is clear and automated

---

## 4 Technical Specifications

### 4.1 Role Interface Definition Format
```json
{
  "interface_id": "standard_playback_v1",
  "version": "1.0.0",
  "commands": {
    "play": {
      "description": "Start playback",
      "parameters": {},
      "returns": {"status": "string"}
    },
    "pause": {
      "description": "Pause playback",
      "parameters": {},
      "returns": {"status": "string"}
    },
    "seek": {
      "description": "Seek to position",
      "parameters": {
        "position": {"type": "integer", "min": 0, "description": "Position in seconds"}
      },
      "returns": {"new_position": "integer"}
    }
  }
}
```

### 4.2 Device Capability Mapping Format
```json
{
  "device_id": "example_device",
  "role_capabilities": {
    "playback": {
      "interface_version": "standard_playback_v1", 
      "command_mappings": {
        "play": {
          "device_command": "start_playback",
          "parameter_mappings": {},
          "requires_state": null,
          "pre_conditions": [],
          "post_actions": []
        }
      }
    }
  }
}
```

### 4.3 Translation Algorithm
```python
async def execute_role_action(self, role: str, command: str, **params):
    # 1. Get device for role
    device_id = self.get_device_for_role(role)
    device = self.device_manager.get_device(device_id)
    
    # 2. Check for standard interface translation
    translator = self.role_translator
    if translator.has_mapping(device_id, role, command):
        translated = await translator.translate_command(device, role, command, params)
        return await device.execute_command(translated.command, translated.params)
    
    # 3. Fallback to direct command
    return await device.execute_command(command, params)
```

---

## 5 Backward Compatibility

### 5.1 Compatibility Strategy
- **Graceful Degradation**: Unmapped commands fall back to direct execution
- **Progressive Enhancement**: Devices can be migrated incrementally
- **Explicit Override**: Scenarios can force direct command execution

### 5.2 Migration Path
1. **Phase 1**: Add role capability definitions to new devices
2. **Phase 2**: Migrate existing device configs with tooling
3. **Phase 3**: Update UI to use standard interfaces
4. **Phase 4**: Deprecate direct command usage (optional)

---

## 6 Benefits Analysis

### 6.1 For UI Developers
- **Simplified Logic**: Same commands work across all scenarios
- **Reduced Complexity**: No device-specific conditional logic needed
- **Better UX**: Consistent behavior regardless of active scenario
- **Future-Proof**: Adding new devices doesn't break existing UI

### 6.2 For System Administrators  
- **Device Flexibility**: Swap devices without reconfiguring UI
- **Easier Testing**: Standard interfaces enable automated testing
- **Better Documentation**: Clear contracts for each role
- **Reduced Support**: Fewer device-specific issues

### 6.3 For System Architecture
- **True Abstraction**: Scenarios become genuine capability aggregators
- **Cleaner APIs**: Standard interfaces reduce API surface complexity
- **Better Testability**: Mock standard interfaces for testing
- **Extensibility**: Easy to add new role types and capabilities

---

## 7 Open Questions

1. **Versioning Strategy**: How do we handle interface evolution over time?
2. **Performance Impact**: What's the overhead of translation layer?
3. **Complex Mappings**: How do we handle commands requiring multiple device calls?
4. **State Synchronization**: How do we handle state consistency across role abstractions?
5. **Error Recovery**: What happens when translation fails mid-execution?

---

## 8 Next Steps

1. **Review and Approve**: Get stakeholder approval for approach
2. **Detailed Design**: Create detailed technical specifications for Phase 1
3. **Prototype Development**: Build proof-of-concept for playback role
4. **Testing Strategy**: Define test cases and validation criteria
5. **Implementation Planning**: Create detailed sprint plans for each phase

---
*© 2025 – droman42 / contributors* 