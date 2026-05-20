# Device UI Page Generation Implementation Plan

## Overview

This document outlines the implementation plan for generating device-specific UI pages based on device configurations retrieved from the API. The system will replace the current YAML-based prompt system with dynamic page generation that leverages actual device configurations and command structures.

## Objectives

1. **Solve Multiple Device Problem**: Each device instance gets its own generated page
2. **Eliminate Manual Maintenance**: Pages auto-generate from API configurations
3. **Leverage Backend Structure**: Use existing command grouping and parameter definitions
4. **Type Safety**: Generate device-specific TypeScript state interfaces
5. **Consistent UI Patterns**: Apply device-class-specific UI generation rules

## Script Interface

### Command Line Parameters

```bash
node src/scripts/generate-device-pages.mjs \
  --api-base-url http://localhost:8000 \
  --device-id living_room_tv \
  --output-dir src/pages/devices \
  --state-file backend/devices/lg_tv_state.py \
  --state-class LgTvState \
  --param-ui-mode sliders|buttons
```

### Parameters Description

- `--api-base-url`: Base URL for the device configuration API
- `--device-id`: Specific device ID to generate page for
- `--output-dir`: Directory to output generated page components
- `--state-file`: Optional Python file containing device state class
- `--state-class`: Optional Python class name for state type generation
- `--param-ui-mode`: UI preference for range parameters (sliders or buttons)

## Device Configuration Analysis

### API Endpoints Used

1. `GET /config/device/{device_id}` - Get device configuration
2. `GET /devices/{device_id}/groups` - Get device command groups

### API Call Sequence

For each device page generation:
1. Call `GET /config/device/{device_id}` to get device configuration
2. Call `GET /devices/{device_id}/groups` to get organized group structure
3. Use groups response for UI organization and ordering
4. Generate the device-specific page component

### Device Configuration Structure

```typescript
interface DeviceConfig {
  device_id: string;
  device_name: string;
  device_class: string;  // Key for UI generation strategy
  config_class: string;
  commands: Record<string, DeviceCommand>;
}

interface DeviceCommand {
  action: string;
  topic: string;
  description: string;
  group: string | null;
  params: CommandParameter[] | null;
}

interface CommandParameter {
  name: string;
  type: 'range' | 'string' | 'integer';
  required: boolean;
  default: any;
  min: number | null;
  max: number | null;
  description: string;
}
```

### Device Groups Structure

```typescript
interface DeviceGroups {
  device_id: string;
  groups: DeviceGroup[];
}

interface DeviceGroup {
  group_id: string;
  group_name: string;
  actions: GroupAction[];
  status: string;
}

interface GroupAction {
  name: string;
  description: string;
  params: CommandParameter[] | null;
}
```

## UI Generation Rules by Device Class

### WirenboardIRDevice

**Strategy**: Strictly follow group and command structure from API config

**UI Mapping**:
- Each group becomes a UI section
- Commands with `params: null` → Button components
- Groups with directional commands (up/down/left/right/ok) → NavCluster component
- Maintain original group ordering from API

**Example Groups**:
- `power` → Power control buttons
- `menu` → Navigation cluster
- `inputs` → Input selection buttons
- `volume` → Volume control buttons

### LgTv

**Strategy**: Use device class hints with special pointer handling

**UI Mapping**:
- `pointer` group → PointerPad component
  - `move_cursor(x, y)` → Absolute mode
  - `move_cursor_relative(dx, dy)` → Relative mode
  - `click()` → Integrated click functionality
- Other groups → Standard button grids
- Menu groups → NavCluster component

### EMotivaXMC2 (Audio Processor)

**Strategy**: Multi-zone parameter expansion

**UI Mapping**:
- Commands with `zone` parameter → Generate multiple controls
  - Use parameter `min`/`max` to determine zone count
  - `set_volume(level, zone)` → "Main Zone Volume" + "Zone 2 Volume" sliders
  - Zone parameter hidden from user, auto-populated
- Other commands → Standard button grids

### BroadlinkKitchenHood

**Strategy**: Parameter-driven controls

**UI Mapping**:
- `range` parameters → SliderControl or stepped buttons (based on script parameter)
- `string` parameters → Dropdown or button groups
- `integer` parameters → Number input or buttons
- Group commands in sections

### AppleTVDevice

**Strategy**: Standard button grids (to be expanded later)

**UI Mapping**:
- Groups → Button sections
- Menu group → NavCluster
- Playback controls → Button grid

### Default/Unknown Device Classes

**Strategy**: Generic analysis-based generation

**UI Mapping**:
- Analyze command patterns to infer UI components
- Default to button grids for simple commands
- Group commands by their `group` property

## State Type Generation

### Python File Analysis

**Process**:
1. Parse specified Python file using AST or regex
2. Find class definition matching `--state-class` parameter
3. Extract field names and type annotations
4. Generate corresponding TypeScript interface

**Python → TypeScript Type Mapping**:
```python
str          → string
int          → number
float        → number
bool         → boolean
List[T]      → T[]
Dict[K, V]   → Record<K, V>
Optional[T]  → T | null
Union[A, B]  → A | B
```

**Custom Classes**: Generate corresponding TypeScript classes

### Generated State Interface Example

```typescript
// Generated from LgTvState Python class
export interface LgTvState extends BaseDeviceState {
  cursor_x: number;
  cursor_y: number;
  current_app: string;
  volume_level: number;
  power_state: 'on' | 'off';
}
```

### State Hook Generation

```typescript
// Generated custom hook per device instance
export const useLivingRoomTvState = () => {
  return useDeviceState('living_room_tv') as UseQueryResult<LgTvState>;
};
```

## Component Generation Templates

### Base Component Structure

```typescript
// Auto-generated from device config - DO NOT EDIT
import React from 'react';
import { useLogStore } from '../../stores/useLogStore';
import { useExecuteDeviceAction } from '../../hooks/useApi';
import { use{DeviceId}State } from '../../hooks/devices/{deviceId}State';
import NavCluster from '../../components/NavCluster';
import SliderControl from '../../components/SliderControl';
import PointerPad from '../../components/PointerPad';
import { Button } from '../../components/ui/button';

function {DeviceId}Page() {
  const { addLog } = useLogStore();
  const { data: deviceState } = use{DeviceId}State();
  const executeAction = useExecuteDeviceAction();

  const handleAction = (action: string, payload?: any) => {
    executeAction.mutate({ 
      deviceId: '{device_id}', 
      action: { name: action, ...payload } 
    });
    addLog({
      level: 'info',
      message: `Action: ${action}`,
      details: payload
    });
  };

  return (
    <div className="p-6 space-y-6">
      <div className="text-center">
        <h1 className="text-2xl font-bold">{device_name}</h1>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Generated groups */}
      </div>
    </div>
  );
}

export default {DeviceId}Page;
```

### Component Generation Functions

```typescript
// Navigation cluster generation
function generateNavCluster(group: DeviceGroup): string {
  // Map directional commands to NavCluster props
}

// Button grid generation
function generateButtonGrid(group: DeviceGroup): string {
  // Generate button components from group actions
}

// Slider control generation
function generateSliderControls(commands: DeviceCommand[]): string {
  // Generate SliderControl components for range parameters
}

// Pointer pad generation
function generatePointerPad(group: DeviceGroup): string {
  // Generate PointerPad for pointer group
}

// Multi-zone control generation
function generateZoneControls(command: DeviceCommand): string {
  // Generate multiple controls for zone-based commands
}
```

## File Output Structure

### Generated Directory Structure

```
src/pages/devices/
├── living_room_tv.gen.tsx
├── bedroom_tv.gen.tsx  
├── kitchen_hood.gen.tsx
├── processor.gen.tsx
├── upscaler.gen.tsx
├── index.gen.ts
└── manifest.json

src/types/devices/
├── LgTvState.ts
├── ProcessorState.ts
└── index.ts

src/hooks/devices/
├── useLivingRoomTvState.ts
├── useBedroomTvState.ts
└── index.ts
```

### Generated Files

**Device Pages**: `{device_id}.gen.tsx`
- React component for device UI
- Device-specific state integration
- Command action handlers

**State Types**: `{DeviceClass}State.ts`
- TypeScript interfaces from Python classes
- Extend BaseDeviceState

**State Hooks**: `use{DeviceId}State.ts`
- Custom hooks per device instance
- Type-safe state access

**Index Files**: Barrel exports for easy importing

**Manifest**: JSON file with device metadata for router

### Router Integration

```typescript
// Updated router index
export const generatedDevicePages = {
  'living_room_tv': LivingRoomTvPage,
  'bedroom_tv': BedroomTvPage,
  // ...
};

export const devicePageManifest = [
  {
    id: 'living_room_tv',
    name: 'Living Room TV',
    deviceClass: 'LgTv', 
    path: 'src/pages/devices/living_room_tv.gen.tsx'
  },
  // ...
];
```

## Error Handling & Validation

### API Response Validation

```typescript
// Validate device configuration API response
function validateDeviceConfig(response: any): DeviceConfig {
  // Validate against DeviceConfig schema
  // Check required fields
  // Validate command structure
  // Ensure parameter types are valid
}

// Validate device groups API response
function validateDeviceGroups(response: any): DeviceGroups {
  // Validate against DeviceGroups schema
  // Check group structure
  // Validate action definitions
}
```

### Generation Error Handling

1. **API Connection Errors**: Graceful failure with error reporting
2. **Invalid API Responses**: Validate JSON structure against expected schemas
3. **Malformed Device Configurations**: Skip device with warning, continue with others
4. **File Write Errors**: Report failed outputs, continue with successful ones
5. **Type Generation Errors**: Fall back to BaseDeviceState

### Validation Rules

- Device ID must be valid identifier
- API responses must match expected JSON schemas
- Commands must have valid action names
- Parameters must have supported types
- Group IDs must be non-empty strings

## Implementation Steps

### Phase 1: Core Infrastructure
1. Set up script CLI interface with single device targeting
2. Implement API data fetching for device config and groups
3. Create JSON schema validation for API responses
4. Implement basic component generation templates

### Phase 2: Device Class Handlers
1. Implement WirenboardIRDevice generation (strict API following)
2. Implement LgTv generation (pointer group handling)
3. Implement EMotivaXMC2 generation (multi-zone expansion)
4. Implement BroadlinkKitchenHood generation (parameter controls)

### Phase 3: State Type Generation
1. Python file parser implementation
2. Type mapping system
3. TypeScript interface generation
4. Custom hook generation per device

### Phase 4: Configuration & Polish
1. API response validation and error handling
2. File output organization
3. Router integration updates
4. Batch processing capabilities (optional)

### Phase 5: Testing & Documentation
1. Test with all existing devices
2. Validate generated components
3. Performance optimization
4. Usage documentation

## Cleanup Phase

### Remove YAML-Based System

After successful implementation and testing of the new device page generation system, clean up the old YAML-based approach:

#### Files to Remove:
```
src/prompts/                     # Entire prompt directory
├── apple_tv.prompt.yaml
├── lg_tv.prompt.yaml  
├── movie_night.prompt.yaml
└── ...

src/scripts/generate-pages.mjs   # Old generation script
src/types/Prompt.ts             # YAML prompt type definitions
```

#### Files to Update:

**`src/pages/`**:
- Remove old generated files: `*.gen.tsx` (apple_tv.gen.tsx, lg_tv.gen.tsx, etc.)
- Remove old `index.gen.ts` and `manifest.json`
- Keep only `HomePage.tsx` and new device pages structure

**`package.json`**:
- Remove any prompt-related scripts
- Update generation scripts to point to new system

**Router Configuration**:
- Update `src/app/App.tsx` to use new device page routing
- Remove references to old generated pages
- Integrate new device page manifest

#### Database/Config Updates:
- Remove any YAML prompt file references from documentation
- Update deployment scripts to use new generation command
- Update development workflows and README instructions

#### Validation Steps:
1. Ensure all existing device functionality works with new generated pages
2. Verify no broken imports or missing components
3. Test device page routing and state management
4. Confirm all device actions execute correctly
5. Validate TypeScript compilation without errors

#### Migration Checklist:
- [ ] All devices have generated pages
- [ ] Device routing works correctly  
- [ ] State management functions properly
- [ ] All device actions execute successfully
- [ ] No TypeScript compilation errors
- [ ] Old YAML files removed
- [ ] Old generation script removed  
- [ ] Documentation updated
- [ ] Deployment scripts updated

## Dependencies

### Required Packages
- `glob`: File pattern matching
- `ajv`: JSON schema validation for API responses
- Existing project dependencies (React, TypeScript)

### API Dependencies
- Device configuration API access (`/config/device/{device_id}`)
- Device groups API access (`/devices/{device_id}/groups`)
- Python state class files (optional)
- Existing UI components (NavCluster, SliderControl, PointerPad)

## Success Criteria

1. **Completeness**: All existing devices generate valid React components
2. **Type Safety**: Generated TypeScript interfaces compile without errors
3. **Functionality**: Generated pages can execute device actions successfully
4. **Maintainability**: Easy to add new device classes and update generation rules
5. **Performance**: Page generation completes in reasonable time (<30s for all devices)

## Future Enhancements

1. **Real-time Updates**: Watch for device config changes and auto-regenerate
2. **Custom Templates**: Allow device-specific component templates
3. **State Validation**: Runtime validation of device state structures
4. **UI Customization**: Per-device UI theme and layout customizations
5. **Analytics**: Track which device actions are used most frequently

## Future Scenario Support

**Important Note**: This device page generation system is designed to be the foundation for a broader UI generation framework. After completing the device implementation, we will extend this system to support **scenario-based page generation** using similar principles:

- **Scenario API Integration**: Leverage `/scenario/definition` endpoints
- **Scenario-Specific UI Patterns**: Generate pages for scenario execution and management
- **Cross-Device Scenario Controls**: UI for scenarios that span multiple devices
- **Scenario State Management**: Generate TypeScript types for scenario states
- **Unified Generation Pipeline**: Extend the same script to handle both devices and scenarios

The device system should be architected with this future expansion in mind, ensuring that the core generation infrastructure can be reused and extended for scenario support. 