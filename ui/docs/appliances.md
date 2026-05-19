# Appliance Pages Architecture

## Overview

This document outlines the architectural approach for appliance pages in the Smart Home UI v2 system. Unlike devices (TVs, streamers, processors) which use generated pages with `RemoteControlLayout`, appliances require static, hand-crafted pages due to their diverse and specialized UI requirements.

## Background & Context

### Current System Architecture

**Devices & Scenarios**: Generated pages using dynamic templates
```
Device Config → Generator → RemoteControlTemplate → Static Generated Page
```

**Key Characteristics**:
- Complex remote control interfaces
- Standardized button/navigation patterns
- Suitable for RemoteControlLayout template
- Generated from configuration files

### Appliance Requirements Analysis

**Problem**: Appliances have extremely diverse UI requirements that don't fit the RemoteControlLayout pattern:

1. **Kitchen Hood**: Simple fan speed sliders, light toggles
2. **Roborock Vacuum**: Interactive map display, room selection, cleaning modes
3. **Washing Machine**: Complex cycle selection, time/temperature controls
4. **Oven**: Temperature controls, timer displays, mode selection

**Key Insight**: Each appliance type requires domain-specific interactions that are too different to justify generation.

## Architectural Decision

### Static Appliance Pages Approach

**New Architecture for Appliances**:
```
Appliance Config → AppliancePage Router → Specific Component → Dynamic UI
```

**Core Philosophy**:
- **Devices**: Generated for consistency (similar UI patterns)
- **Appliances**: Hand-crafted for specialization (unique UI requirements)

### Benefits of This Approach

1. **Perfect UX Fit**: Each appliance gets optimal UI for its specific use case
2. **Rapid Development**: No complex generation logic for unique patterns
3. **Maintainable**: Focused components with clear boundaries
4. **Extensible**: Easy to add new appliance types without generation complexity
5. **Consistent Backend**: Same APIs and SSE system as devices

## System Integration

### Backend Integration

**Maintains Existing Patterns**:
- ✅ Same `/config/device/{id}` API for appliance configurations
- ✅ Same device action APIs for appliance controls
- ✅ Same SSE events for appliance state updates
- ✅ Same `device_category: "appliance"` categorization
- ✅ Same command structure in configuration

**Configuration Example**:
```typescript
{
  device_id: "roborock_vacuum",
  device_name: "Roborock S7",
  device_class: "RoborockVacuum", 
  device_category: "appliance",
  commands: {
    "start_cleaning": { action: "start_cleaning", ... },
    "return_dock": { action: "return_dock", ... }
  },
  // Optional appliance-specific metadata
  appliance_metadata?: {
    map_endpoint?: "/vacuum/map",
    room_endpoint?: "/vacuum/rooms", 
    ui_type: "map_based"
  }
}
```

### Frontend Integration

**Navigation & Discovery**:
- ✅ Appliances appear in existing appliance dropdown (already implemented)
- ✅ Room-based filtering works identically to devices
- ✅ Same global layout (header, sidebar, state panels)
- ✅ Consistent navigation patterns

**Route Structure**:
```typescript
// Current Generated Pages
/device/lg_tv_living     → Generated device page
/scenario/movie_night    → Generated scenario page

// New Static Pages
/appliance/kitchen_hood  → Static KitchenHoodPage
/appliance/roborock      → Static RoborockVacuumPage
/appliance/washing_machine → Static WashingMachinePage
```

## Detailed Architecture

### 1. AppliancePage Container Component

**Purpose**: Generic container that handles common concerns

**Responsibilities**:
- Load appliance configuration by ID
- Determine appliance type/class from config
- Route to appropriate appliance-specific component
- Handle loading states, errors, and navigation
- Provide consistent layout wrapper

**Interface**:
```typescript
// Route: /appliance/:applianceId
interface AppliancePageProps {
  applianceId: string; // From route params
}

function AppliancePage({ applianceId }: AppliancePageProps) {
  // Load config, determine type, render specific component
}
```

### 2. Appliance Component Registry

**Purpose**: Map appliance classes to their specific components

```typescript
const applianceComponents = {
  'BroadlinkKitchenHood': KitchenHoodPage,
  'RoborockVacuum': RoborockVacuumPage,
  'WashingMachine': WashingMachinePage,
  'Oven': OvenPage
} as const;

type ApplianceClass = keyof typeof applianceComponents;
```

### 3. Appliance-Specific Components

**Purpose**: Implement unique UI for each appliance type

**Standard Interface**:
```typescript
interface ApplianceComponentProps {
  config: DeviceConfig;           // Standard device config
  onAction: (action: string, params?: any) => Promise<void>;
  isActionPending?: boolean;
  actionError?: string | null;
}

// Example implementations
function KitchenHoodPage(props: ApplianceComponentProps) {
  // Fan speed sliders, light toggles
}

function RoborockVacuumPage(props: ApplianceComponentProps) {
  // Interactive map, room selection, cleaning modes
}
```

### 4. Shared Appliance UI Library

**Purpose**: Reusable components for common appliance patterns

```typescript
// Common appliance UI components
<ApplianceCard>           // Consistent card layout
<StatusIndicator>         // Status displays (on/off, running, etc.)
<SpeedSlider>             // Fan speeds, intensity controls
<ToggleSwitch>            // Simple on/off controls
<ModeSelector>            // Cleaning modes, cycle selection
<TimerDisplay>            // Time remaining, schedule displays
```

## Implementation Strategy

### Phase 1: Foundation (Week 1-2)

**Core Infrastructure**:
1. Create `AppliancePage` container component
2. Create appliance component registry system
3. Add `/appliance/:id` route to existing router
4. Build first appliance: `KitchenHoodPage`
5. Create shared appliance UI component library

**Deliverables**:
- Working kitchen hood appliance page
- Generic appliance page routing
- Foundation for additional appliances

### Phase 2: Integration (Week 3)

**System Integration**:
1. Update navigation to handle appliance routes properly
2. Modify device page generation to skip appliances
3. Add appliance-specific SSE event handling if needed
4. Update existing appliance dropdown to use new routes

**Deliverables**:
- Seamless navigation between devices and appliances
- Updated page generation logic
- Complete integration with existing UI

### Phase 3: Expansion (Week 4+)

**Scale to All Appliances**:
1. Build remaining appliance components (Roborock, etc.)
2. Enhance shared UI library based on patterns
3. Add complex features (maps, real-time updates)
4. Optimize and refine UX

**Deliverables**:
- All 4 planned appliances implemented
- Mature shared component library
- Production-ready appliance system

## Technical Considerations

### State Management Strategy

**Device State**: Continue using existing SSE + Zustand stores
- Appliances use same device state updates as regular devices
- State Panel shows appliance status identically

**Appliance-Specific State**: Local component state or dedicated stores
- Simple appliances (kitchen hood): Local React state
- Complex appliances (vacuum maps): Dedicated Zustand stores if needed

**Special Data**: Appliance-specific API calls
- Maps, room data, specialized endpoints
- Handled within individual appliance components

### Styling & Design Consistency

**Global Layout**: Same as devices
- Header, navigation, state panels unchanged
- Consistent with existing design system

**Component Styling**: Appliance-specific but using design tokens
- Tailwind CSS classes for consistency
- Custom styles only where necessary for appliance UX

**Responsive Design**: Each appliance handles its breakpoints
- Mobile-first approach maintained
- Appliance-specific responsive requirements

### Error Handling & Loading States

**Standard Patterns**:
- Loading skeletons during config fetch
- Error boundaries for appliance component failures
- Graceful degradation for network issues

**Appliance-Specific**:
- Map loading states for vacuum
- Connection status for real-time appliances
- Action feedback (success/failure states)

## Testing Strategy

### Component Testing
- Unit tests for each appliance component
- Mock device configs for testing
- Action handling verification

### Integration Testing
- Route navigation testing
- SSE event integration
- State management validation

### UX Testing
- Appliance-specific user flows
- Mobile responsiveness
- Accessibility compliance

## Future Considerations

### Scalability
- **Component Library Growth**: Monitor for common patterns to extract
- **Performance**: Lazy loading for complex appliances (maps, etc.)
- **Configuration**: Potential appliance-specific config schema

### Maintenance
- **Code Consistency**: Linting rules for appliance components
- **Documentation**: Component documentation standards
- **Updates**: Strategy for global changes across appliances

### Extensibility
- **New Appliance Types**: Clear process for adding new appliances
- **Feature Evolution**: How to handle new appliance capabilities
- **Third-party Integration**: Framework for external appliance APIs

## Current Status

### Completed
- ✅ Backend `device_category` field implementation
- ✅ Frontend device vs appliance categorization
- ✅ Separate appliance dropdown in navigation
- ✅ Room-based appliance filtering
- ✅ Architecture analysis and documentation

### Next Steps
1. Implement `AppliancePage` container component
2. Create appliance component registry
3. Build `KitchenHoodPage` as first appliance
4. Add `/appliance/:id` routing
5. Integrate with existing navigation system

### Known Appliances
1. **Kitchen Hood** (BroadlinkKitchenHood) - Current
2. **Roborock Vacuum** - Planned
3. **Washing Machine** - Planned  
4. **Oven** - Planned

## Decision Record

**Decision**: Implement static appliance pages instead of extending the generation system

**Rationale**: 
- Appliances have extremely diverse UI requirements (maps, sliders, complex controls)
- Generation would be too complex or too generic
- Static pages allow perfect UX fit for each appliance type
- Maintains consistent backend integration

**Trade-offs Accepted**:
- Manual maintenance vs automated generation
- Potential code duplication (mitigated by shared UI library)
- Two different page systems (devices generated, appliances static)

**Success Criteria**:
- All appliances have appropriate, usable interfaces
- Consistent navigation and integration with existing system
- Maintainable codebase with clear component boundaries
- Easy to add new appliance types 