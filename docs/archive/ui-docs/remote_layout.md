> **RETIRED 2026-07-15 (archived).** This spec describes the *build-time codegen* remote
> layout — `ZoneDetection.ts`, `RemoteControlTemplate.ts`, per-device `*.gen.tsx`,
> `src/lib/deviceHandlers/`, `StateTypeGenerator.ts` — all of which have been **removed**
> from `ui/`. The shipped architecture is the **runtime Layout Manifest**
> (`GET /devices/{id}/layout` → `LayoutManifest`, rendered by
> `ui/src/components/RuntimeDevicePage.tsx` via `layoutManifestAdapter.ts`). Living truth:
> [`docs/architecture/ui.md`](../../architecture/ui.md), the `layout-manifest` diagram, and
> [`docs/design/scenarios/scenario_system_redesign.md`](../scenarios/scenario_system_redesign.md).
> Kept for historical reference only — do not implement from this document.

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

## Implementation

The zone system specified above is implemented and is the only layout system (the
old grid-based `DevicePageTemplate` / `UISection` were removed). At build time:

- `src/lib/ZoneDetection.ts` maps device groups/actions to the 7 zones.
- `src/lib/generators/RemoteControlTemplate.ts` renders each device's
  `RemoteDeviceStructure` into a `*.gen.tsx` page.
- Per-device handlers live in `src/lib/deviceHandlers/` (one per device class, plus
  `ScenarioVirtualDeviceHandler`).
- Device-state types come from the backend `openapi.json` contract via
  `src/lib/StateTypeGenerator.ts` (no Python in the build).

See the repo `README.md` and `docs/page_instructions.md` for running the generator.

**Within-zone placement.** Slot zones (power, volume, nav-cluster, pointer) bind
actions to fixed slots by matching the action name; array-order zones (screen,
playback, tracks) render in the order actions appear, which derives from the device
config's command order in `config/devices/*.json`. See `ZoneDetection.ts`. (Making
this placement an explicit contract is tracked as action_plan P2.5 #10 on the
backend repo.)
