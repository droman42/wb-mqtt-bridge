# Device Remote Control Layout Specification

## Overview
This document describes the conceptual layout for device pages that resemble a remote control interface. The design provides an intuitive, familiar interaction model while adapting dynamically to each device's specific capabilities.

## Layout Schema

```
    ┌─────────────────────────────────────┐
    │        DEVICE REMOTE CONTROL        │
    └─────────────────────────────────────┘
    
    ┌─────────────────────────────────────┐
    │  ① POWER GROUP [SHOW/HIDE ZONE]     │
    │  ┌─────────┬─────────┬─────────┐    │
    │  │ LEFT    │ MIDDLE  │ RIGHT   │    │
    │  │Power OFF│Zone2 Pwr│Power ON │    │
    │  │or Toggle│(EMotiva)│         │    │
    │  └─────────┴─────────┴─────────┘    │
    └─────────────────────────────────────┘
    
    ┌─────────────────────────────────────┐
    │  ② MEDIA STACK [SHOW/HIDE ZONES]   │
    │  ┌─────────────────────────────────┐ │
    │  │ INPUTS (Dropdown - API)         │ │
    │  └─────────────────────────────────┘ │
    │  ┌─────────────────────────────────┐ │
    │  │ PLAYBACK                        │ │
    │  └─────────────────────────────────┘ │
    │  ┌─────────────────────────────────┐ │
    │  │ TRACKS                          │ │
    │  └─────────────────────────────────┘ │
    └─────────────────────────────────────┘
    
    ┌─────────────────────────────────────┐
    │     CENTRAL CONTROL [ALWAYS PRESENT]│
    │  ┌───────┬─────────────┬───────────┐ │
    │  │③     │    MENU     │        ④ │ │
    │  │SCREEN │ (Nav Cluster)│   VOLUME  │ │
    │  │      │             │           │ │
    │  │Vert. │             │Priority:  │ │
    │  │Button│             │1.Slider+  │ │
    │  │Zone  │             │  Mute     │ │
    │  │      │             │2.Vol Up   │ │
    │  │(can  │   (can be   │  Vol Down │ │
    │  │be    │    empty)   │  Mute     │ │
    │  │empty)│             │           │ │
    │  └───────┴─────────────┴───────────┘ │
    └─────────────────────────────────────┘
    
    ┌─────────────────────────────────────┐
    │  ⑤ APPS [SHOW/HIDE ZONE]           │
    │  ┌─────────────────────────────────┐ │
    │  │ Dropdown Selector (API)         │ │
    │  └─────────────────────────────────┘ │
    └─────────────────────────────────────┘
    
    ┌─────────────────────────────────────┐
    │  ⑥ POINTER [SHOW/HIDE ZONE]        │
    │  ┌─────────────────────────────────┐ │
    │  │        Pointer Pad              │ │
    │  │      (Trackpad Area)            │ │
    │  └─────────────────────────────────┘ │
    └─────────────────────────────────────┘
```

## Zone Behavior Types

### 🟢 Always Present Zones
These zones maintain consistent layout structure regardless of device capabilities:
- **③ Screen Zone**: Vertical alignment area for screen control buttons
- **④ Volume Zone**: Volume control area  
- **⑦ Menu Nav Cluster**: Central navigation controls

**Behavior**: Zones are always visible in the layout. When empty, they show outlines and maintain space to preserve layout structure.

### 🔴 Show/Hide Zones  
These zones appear/disappear based on device configuration:
- **① Power Group**: Power control buttons
- **② Media Stack**: INPUTS, PLAYBACK, TRACKS sections
- **⑤ Apps Section**: Application selector
- **⑥ Pointer Section**: Trackpad/pointer control area

**Behavior**: Entire zones are hidden when device doesn't have the respective group in its configuration.

## Detailed Zone Specifications

### ① Power Group
**Population Logic** (left to right):

**Regular Case (2 buttons):**
- Left box: **Power OFF** button
- Right box: **Power ON** button  
- Middle box: stays empty

**Single Toggle Case (1 button):**
- Left box: **Power Toggle** button
- Right box: stays empty
- Middle box: stays empty

**Special Case - EMotiva Device (3 buttons):**
- Left box: **Power OFF** button
- Right box: **Power ON** button
- Middle box: **Zone 2 Power** button

### ② Media Stack
**INPUTS Section:**
- **Type**: Dropdown selector
- **Population**: Dynamic via REST API call to device-specific function
- **Content**: Available inputs for the device

**PLAYBACK Section:**
- **Visibility**: Show only if device has playback group
- **Content**: Playback control buttons/components

**TRACKS Section:**  
- **Visibility**: Show only if device has tracks group
- **Content**: Track navigation controls

### ③ Screen Zone
- **Layout**: Vertical alignment zone for buttons/actions
- **Population**: Always present, can be empty
- **Content**: Vertically aligned buttons for screen controls (aspect ratio, zoom, display modes, etc.)
- **Button Arrangement**: Single column, vertical stacking
- **Behavior**: Shows outline and maintains space when no screen controls available

### ⑦ Menu Navigation Cluster (Center)
- **Layout**: Central position between Screen and Volume zones
- **Population**: Always present, can be empty  
- **Content**: Uses existing NavCluster component with adjusted styling for remote control appearance
- **Behavior**: Core navigation area for device interaction, shows outline when no menu controls available
- **Styling**: Current NavCluster functionality maintained, detailed beautification improvements planned for future

### ④ Volume Zone
**Priority-based Population:**

**Priority 1 - Volume Range + Volume Buttons Available:**
- **Main Control**: Vertical slider
  - Maximum volume at top
  - Minimum volume at bottom
- **Additional**: Mute button (if present) positioned below slider

**Priority 2 - Only Volume Up/Down Buttons Available:**
- **Vertical arrangement** (top to bottom):
  1. Volume Up button
  2. Volume Down button  
  3. Mute button (if present)

### ⑤ Apps Section
- **Type**: Dropdown selector  
- **Population**: Dynamic via REST API call to device-specific function
- **Content**: Available applications for the device
- **Behavior**: Same pattern as INPUTS section

### ⑥ Pointer Section
- **Type**: Pointer Pad / Trackpad area using existing PointerPad component
- **Functionality**: Touch/cursor control (laptop trackpad style) - existing implementation maintained
- **Styling**: Touchpad look and feel, styled lighter than main theme for visual distinction
- **Visibility**: Show only if device has pointer group

## API Integration

### Device Action System
All remote control functionality uses the unified device action system:
- **Endpoint**: `POST /devices/{device_id}/action`
- **Request Format**: `{"action": "action_name", "params": {...}}`
- **Response Format**: `{"success": boolean, "data": any, "state": {...}}`
- **Available Actions**: Listed in device groups via `GET /devices/{device_id}/groups`

**Key Actions for Remote Layout:**
- **get_available_inputs**: Returns list of available input sources
- **get_available_apps**: Returns list of available applications  
- **set_input**: Changes input source (params: `{"input": "input_id"}`)
- **launch_app**: Launches application (params: `{"app_name": "app_name"}`)
- **set_volume**: Sets volume level (params: `{"level": number, "zone": number}`)

### Zone Visibility Detection
- **Functionality**: Already available in existing codebase
- **Method**: Use existing `fetchDeviceGroups(deviceId)` response
- **Detection Logic**: Check if `groups.groups` contains specific group names/IDs for zone types
- **Implementation**: Extend existing group detection patterns in device handlers

### Dynamic Dropdowns

**INPUTS Dropdown (② Zone):**
- **WirenboardIRDevice Class**: 
  - Build list from inputs group commands when page loads
  - Display Name: Use `description` field of command
  - Action: Launch standard actions from dropdown list
- **Other Device Classes**:
  - Use `get_available_inputs` device action if inputs group present
  - Action: Use `set_input` device action with selected input ID

**APPS Dropdown (⑤ Zone):**
- **All Device Classes**: Use `get_available_apps` device action
- **Condition**: Only if apps group is present in device configuration
- **Action**: Launch app using `launch_app` device action
- **Population**: Dynamic call when page loads

### Device Action Response Format
- **Structure**: Device actions return data in response.data field with id ↔ display name mapping
- **Usage**: Use `input_id`/`app_id` field when forming device action calls for input selection/app launch
- **Example Response**: 
  ```json
  {
    "success": true,
    "data": [
      { "input_id": "hdmi1", "input_name": "HDMI 1" },
      { "app_id": "youtube.leanback.v4", "app_name": "YouTube" }
    ]
  }
  ```

### Error Handling
- **Strategy**: Show API errors in existing log panel
- **User Action**: Manual intervention required for resolution
- **Loading States**: Display loading indicators during API calls
- **Empty States**: Show appropriate "No inputs/apps available" messages

### Device Configuration
- **Data Sufficiency**: Existing `fetchDeviceConfig()` and `fetchDeviceGroups()` provide sufficient information
- **No Additional APIs**: Remote control layout implementation requires no new device configuration endpoints
- **Action Execution**: All inputs/apps functionality uses existing device action system via `POST /devices/{device_id}/action`

### Complete API Integration Coverage

**Standard Device Actions:** (All zones except INPUTS/APPS dropdowns)
- **Power Zone**: `power_on`, `power_off`, `zone2_power` actions
- **Media Stack**: `play`, `pause`, `stop`, etc. actions  
- **Screen Zone**: Display control actions (device-specific)
- **Menu Navigation**: `up`, `down`, `left`, `right`, `ok`, `back` actions
- **Pointer Zone**: Movement actions with `deltaX`, `deltaY` parameters
- **Error Handling**: All failures logged to existing log panel
- **Implementation**: Reuse existing device action infrastructure

**Volume Zone Action Priority:**
1. **set_volume device action** (if present for device class - same criteria as slider)
2. **Standard volume actions** (fallback: `volume_up`, `volume_down`, `mute` device actions)

**Real-time State Updates:**
- **INPUTS/APPS**: For device classes with respective groups (excluding WirenboardIRDevice)
- **Current Status**: Real-time state updates for inputs/apps not implemented
- **Future Implementation**: WebSocket/MQTT integration needed for state synchronization
- **Action Documentation**: All device actions documented in API Swagger at `/docs` endpoint

## Component Library Usage

### Dropdown Components (② INPUTS, ⑤ APPS)
- **Implementation**: Integrated inline dropdown pattern (not standalone component)
- **Features**: No filtering/search capabilities
- **Empty State**: Show empty box outline, no dropdown when empty
- **Loading State**: Empty box display during API calls

### Button Components (① Power, Other Zones)
- **Base Component**: Use existing `Button` from `ui/button.tsx`
- **Content**: Icon OR text (not both) to fit in rows
- **Disabled State**: Grayed out icons/text when device doesn't support function
- **Variants**: Use appropriate variants (primary/secondary/outline)

### Volume Zone (④) Components
- **Slider**: Extend existing `SliderControl` for vertical orientation
- **Mute Button**: Separate `Button` component
- **Dynamic Positioning**: Adjusts layout based on device state when page loads
- **Real-time Updates**: Handles device state changes

### Navigation Cluster (Menu Center)
- **Base Component**: Use existing `NavCluster`
- **Conditional Visibility**: Must support hiding unavailable buttons
- **Empty State**: Integrates with empty state styling
- **Layout**: Standard D-pad configuration

### Layout & Spacing
- **CSS Framework**: Tailwind utilities (most commonly used)
- **Container Components**: Best practice zone containers
- **Layout System**: Fixed remote control proportions (not responsive breakpoints)
- **Zone Spacing**: Context-dependent - varies by device state and screen size

### State Management
- **Empty Always-Present Zones**: Show outline to maintain layout structure
- **Empty Show/Hide Zones**: Completely hidden (no space reserved)
- **Loading States**: Empty box display (consistent with dropdown approach)  
- **Interaction Feedback**: Hover states for all interactive elements
- **Disabled States**: Visual distinction for unavailable functions

## Navigation Integration

### User Experience & Flow
- **Navigation System**: Current Navbar provides all navigation functionality and should remain unchanged
- **Interface Type**: Multi-device interface supporting current device selection
- **Future Support**: Scenario functionality planned (already present in Navbar structure)
- **Panel Controls**: Navbar handles log panel and state panel toggles
- **Integration**: Remote control layout works within existing navigation framework

## Visual Design Specifications

### Zone Container Styling
- **Background**: No specific preference (use existing system)
- **Borders**: Visible borders around each zone (`border border-border`)
- **Border Radius**: `rounded-md` for zone containers
- **Empty Zones**: No dashed borders, keep clean outline

### Zone State Behavior
- **Hidden Zones**: Compact layout (no empty space reserved) - applies to show/hide zones only
- **Visual Indicators**: No badges or icons for zone availability
- **Empty Always-Present Zones**: Show outlines and maintain space in layout
- **Empty Show/Hide Zones**: Completely hidden from layout
- **Animations**: No fade-in/fade-out transitions

### Remote Control Aesthetic
- **Overall Container**: Device-like border for physical remote appearance
- **Corner Styling**: Rounded corners for entire remote container
- **Elevation**: Subtle shadow (`shadow-lg`) for elevated appearance
- **Background**: Dark grey metal gradient/texture to mimic physical remote
- **Proportions**: Authentic remote control dimensions (NOT full panel width)
- **Aspect Ratio**: Traditional remote proportions (~3:8 or 4:9 ratio - tall and narrow)
- **Centering**: Container centers horizontally in available space
- **Target Orientation**: Optimized for vertical/portrait iPad orientation

### Button Styling Within Zones
- **Power Buttons**: 
  - Power OFF: `destructive` variant
  - Power ON: `default` variant
  - Zone 2 Power (EMotiva): `destructive` variant
- **Volume/Media/Screen/Menu Buttons**: `secondary` variant
- **Disabled State**: Use base variant with grey-out styling (not opacity-based)
- **Button Sizing**: Remote-specific sizing system (replaces existing `sm`/`default`)

**Note**: Apps zone uses dropdown selector, Pointer zone uses PointerPad component - neither use button variants.

### Dropdown Styling (② INPUTS, ⑤ APPS)
- **Pattern**: Follow existing Navbar dropdown styling (`bg-popover`, `border-border`)
- **Empty State**: Show "No inputs available" placeholder text
- **Loading State**: Display loading spinner during API calls
- **Dropdown Pattern**: Integrated/inline implementation (no separate button component)

### Volume Slider Styling (④)
- **Design**: Follow remote control styling theme
- **Mute Button**: Same styling as other remote buttons
- **Volume Indicator**: Display current value above slider
- **Orientation**: New vertical component (not rotated horizontal)

### Responsive Layout
- **Primary Target**: Vertical/portrait iPad orientation with authentic remote proportions
- **Desktop**: Remote appears centered with space on sides (not full width)
- **Mobile**: Scaled remote maintaining proportions (not stretched)
- **Landscape**: Remote stays proportional, doesn't expand to fill width
- **Container**: Fixed max-width with aspect ratio constraints
- **Touch Targets**: Size consideration TBD
- **Spacing**: Context-dependent spacing based on device state and screen size



## Implementation Strategy

### Page Generation System Integration
Based on analysis of `src/scripts/generate-device-pages.ts`:

**Current Architecture:**
- **Template System**: `DevicePageTemplate` generates standard grid-based device pages
- **Handler System**: Device-specific handlers create `UISection[]` with generic component types
- **Component Types**: `ButtonGrid`, `NavCluster`, `SliderControl`, `PointerPad`
- **Layout**: Standard responsive grid (`grid-cols-1 lg:grid-cols-2 gap-6`)

**Required Changes:**
- **Complete Replacement**: Fully replace existing template system (no backward compatibility)
- **Handler Modification**: Update existing device handlers to generate zone-based structure
- **Component Extension**: Extend existing components where possible, create new ones where needed
- **Zone Structure**: Replace `UISection[]` with `RemoteZone[]` for remote control layout
- **Layout System**: Replace responsive grid system with fixed-proportion remote control container

### Zone-Based Architecture

**New Core Interface:**
```typescript
interface RemoteZone {
  zoneId: 'power'|'media-stack'|'screen'|'volume'|'apps'|'menu'|'pointer';
  zoneName: string;
  zoneType: 'power'|'media-stack'|'screen'|'volume'|'apps'|'menu'|'pointer';
  showHide: boolean; // true = show/hide based on device config
  isEmpty: boolean;
  content: ZoneContent;
  layout: ZoneLayoutConfig;
}
```

**Note**: Circled digits (①②③④⑤) are for documentation reference only, not actual code identifiers.

**Handler Updates Required:**
- `WirenboardIRHandler` → Generate remote zones instead of UI sections
- `LgTvHandler` → Map TV groups to remote control zones
- `EMotivaXMC2Handler` → Special multi-zone handling (see below)
- `BroadlinkKitchenHoodHandler` → Map kitchen hood controls to zones
- `AppleTVDeviceHandler` → Map Apple TV controls to remote layout
- `AuralicDeviceHandler` → **NEW**: Audio streaming device handler (discovered in API)
- `RevoxA77ReelToReelHandler` → **NEW**: Reel-to-reel tape deck handler (discovered in API)

### Device-Specific Handling

**EMotiva XMC2 Special Case:**
- **Power Zone (①)**: 
  - Left: Power OFF (both zones)
  - Middle: Zone 2 Power ON (special EMotiva case)
  - Right: Power ON (both zones)
- **Volume Zone (④)**: Zone 2 volume controls only
- **Other Zones**: Main zone controls as standard

**Component Extension Strategy:**
- **Buttons**: Extend existing `Button` component with remote-specific sizes and styling
- **Dropdowns**: Extend Navbar dropdown pattern for integrated inputs/apps selectors
- **Sliders**: Create new vertical slider component extending `SliderControl`
- **Zones**: New container components for remote control zone styling

### Migration Implementation

**Phase 1: Infrastructure**
1. Create `RemoteControlTemplate` class replacing `DevicePageTemplate`
2. Define `RemoteZone` interfaces and types
3. Create zone mapping utilities and population logic

**Phase 2: Handler Updates**
1. Modify all existing device handlers' `analyzeStructure()` methods
2. Replace `createUISections()` with `generateRemoteZones()`
3. Implement device-specific zone mapping logic

**Phase 3: Component Development**
1. Create vertical volume slider component
2. Build integrated dropdown components
3. Extend button system with remote control styling
4. Implement dark grey metal aesthetic

**Phase 4: Template Integration**
1. Replace `DevicePageTemplate` usage in generation script
2. Update all generated device pages to use remote control layout
3. Apply visual design specifications (borders, shadows, styling)

### API Integration
- **Current Assessment**: No API changes anticipated for initial implementation
- **Future Consideration**: May need device configuration enhancements for advanced zone customization

### Future Improvements
- **Device Class Coverage**: Add default/fallback handler for unknown device classes beyond the 7 supported handlers (WirenboardIR, LgTv, EMotiva, Broadlink, AppleTV, Auralic, RevoxA77)

## Legend
- **🔴 SHOW/HIDE ZONES**: Appear only if device has respective group
- **🟢 ALWAYS PRESENT**: Fixed layout zones (can be empty but space reserved)
- **API Dropdowns**: INPUTS & APPS populate dynamically  
- **Volume Priority**: Slider trumps buttons when both available

## Implementation Phases

### 🚀 **Phase 1: Foundation & Core Components (Week 1-2)**
**Goal**: Build the basic remote control container and zone system

**Deliverables**:
- New `RemoteControlLayout` component with authentic remote styling
- Zone container system (7 zones with proper numbering ①-⑦)
- Always-present vs show/hide zone behavior
- Basic zone detection from device groups
- Replace one device handler (WirenboardIRDevice) to generate `RemoteZone[]` instead of `UISection[]`

**Success Criteria**: One device displays in remote control layout with empty zone outlines

### 🎯 **Phase 2: Zone Population & Actions (Week 2-3)**
**Goal**: Implement all zone content types and device actions

**Deliverables**:
- **Power Zone**: 3-button layout with EMotiva special case
- **Volume Zone**: Priority-based (slider vs buttons) with vertical orientation
- **Screen Zone**: Vertical button alignment
- **Menu Navigation**: NavCluster integration with styling adjustments
- **Pointer Zone**: PointerPad with lighter theme styling
- Device action integration for all zones

**Success Criteria**: All zones functional with proper content and actions

### 🔄 **Phase 3: Dynamic Dropdowns & API Integration (Week 3-4)**
**Goal**: Implement INPUTS and APPS dropdowns with real-time data

**Deliverables**:
- **INPUTS Dropdown**: `get_available_inputs` + `set_input` actions
- **APPS Dropdown**: `get_available_apps` + `launch_app` actions
- **Media Stack**: PLAYBACK and TRACKS sections
- Loading states and error handling
- WirenboardIRDevice special handling (commands vs API)

**Success Criteria**: Dropdowns populate dynamically and execute actions correctly

### 🏁 **Phase 4: Complete Device Handler Coverage (Week 4-5)**
**Goal**: Update all existing handlers + create missing device handlers

**Deliverables**:

**Existing Handler Updates**:
- `LgTvHandler` → TV groups to remote control zones
- `EMotivaXMC2Handler` → Multi-zone handling with special power layout
- `BroadlinkKitchenHoodHandler` → Kitchen hood controls to zones
- `AppleTVDeviceHandler` → Apple TV controls to remote layout

**NEW Device Handlers** (discovered in API analysis):
- `AuralicDeviceHandler` → Audio streaming device remote layout
- `RevoxA77ReelToReelHandler` → Reel-to-reel tape deck remote layout

**Final Polish**:
- Button variants and remote-specific sizing
- Responsive behavior for iPad portrait optimization
- Default/fallback handler for unknown device classes
- Final visual polish and comprehensive testing

**Cleanup & Migration Finalization**:
- Remove old grid-based device page files (`.gen.tsx` files using old template)
- Remove unused `DevicePageTemplate` class and related grid components
- Clean up temporary/backup files created during migration
- Remove feature flags and dual-template support code
- Update documentation to reflect new remote control layout as standard

**Success Criteria**: All 7 device classes work with remote control layout, old system completely removed

## Device Handler Coverage Summary

**Total Device Classes**: 7
1. ✅ **WirenboardIRDevice** (Phase 1)
2. 🔄 **LgTv** (Phase 4)
3. 🔄 **EMotivaXMC2** (Phase 4)
4. 🔄 **BroadlinkKitchenHood** (Phase 4)
5. 🔄 **AppleTVDevice** (Phase 4)
6. 🆕 **AuralicDevice** (Phase 4 - NEW)
7. 🆕 **RevoxA77ReelToReel** (Phase 4 - NEW)

**Implementation Strategy**:
- **Parallel Development**: Phase 1-2 can run in parallel (foundation + content)
- **Sequential Dependencies**: Phase 3 depends on Phase 2 completion
- **Overlap Opportunity**: Phase 4 can start during Phase 3 for non-dropdown zones
- **Risk Mitigation**: Keep existing system until Phase 4 complete with feature flag
- **Total Timeline**: 4-5 weeks with potential for 3-4 weeks if phases overlap effectively

**Phase 4 Workload**: 6 device handlers (4 updates + 2 new handlers for newly discovered device classes)

## Page Generator Integration

### State File Mapping Configuration

The page generator requires Python state file and class name parameters. Create a mapping configuration file:

```json
// config/device-state-mapping.json
{
  "WirenboardIRDevice": {
    "stateFile": "/home/development/wb-mqtt-bridge/app/schemas.py",
    "stateClass": "WirenboardIRState"
  },
  "LgTv": {
    "stateFile": "/home/development/wb-mqtt-bridge/app/schemas.py",
    "stateClass": "LgTvState"
  },
  "EMotivaXMC2": {
    "stateFile": "/home/development/wb-mqtt-bridge/app/schemas.py",
    "stateClass": "EmotivaXMC2State"
  },
  "BroadlinkKitchenHood": {
    "stateFile": "/home/development/wb-mqtt-bridge/app/schemas.py",
    "stateClass": "KitchenHoodState"
  },
  "AppleTVDevice": {
    "stateFile": "/home/development/wb-mqtt-bridge/app/schemas.py",
    "stateClass": "AppleTVState"
  },
  "AuralicDevice": {
    "stateFile": "/home/development/wb-mqtt-bridge/app/schemas.py",
    "stateClass": "AuralicDeviceState"
  },
  "RevoxA77ReelToReel": {
    "stateFile": "/home/development/wb-mqtt-bridge/app/schemas.py",
    "stateClass": "RevoxA77ReelToReelState"
  }
}
```

### Generator Commands by Phase

**Phase 1-3: Individual Device Generation**
```bash
npm run generate:device -- \
  --device-id living_room_ir \
  --template remote \
  --state-file /home/development/wb-mqtt-bridge/app/schemas.py \
  --state-class WirenboardIRState
```

**Phase 4: Batch Generation with State Mapping**
```bash
npm run generate:all-devices -- \
  --template remote \
  --state-mapping config/device-state-mapping.json
``` 