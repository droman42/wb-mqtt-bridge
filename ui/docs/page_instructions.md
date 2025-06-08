# Device Page Generation Instructions

## Overview

This document provides complete instructions for generating device-specific UI pages using the automated device page generation system. The system creates React components, TypeScript interfaces, and hooks from device configurations via API calls.

## Prerequisites

1. **Backend API Running**: Ensure the backend API is accessible at the configured URL
2. **Device Configured**: Target device must be properly configured in the backend
3. **Dependencies Installed**: Run `npm install` to ensure all dependencies are available

## Basic Device Page Generation

### Single Device Generation

```bash
# Generate page for a specific device
npm run gen:device-pages -- --device-id=<device_id>

# Example
npm run gen:device-pages -- --device-id=living_room_tv
```

**What gets generated:**
- `src/pages/devices/<device_id>.gen.tsx` - React component for the device

### With Python State Class (Advanced)

```bash
# Generate page with custom Python state class
npm run gen:device-pages -- --device-id=<device_id> \
  --state-file=<path_to_python_file> \
  --state-class=<python_class_name>

# Example
npm run gen:device-pages -- --device-id=living_room_tv \
  --state-file=backend/devices/lg_tv_state.py \
  --state-class=LgTvState
```

**What gets generated:**
- `src/pages/devices/<device_id>.gen.tsx` - React component
- `src/types/generated/<StateClass>.state.ts` - Shared TypeScript state interface
- `src/pages/devices/<device_id>.hooks.ts` - Device-specific React state hook

**Important Notes:**
- State files are **shared** between devices using the same Python class
- First device creates the shared state interface
- Subsequent devices reuse existing state interface
- Each device gets its own hook file

## Batch Processing

### Generate All Available Devices

```bash
# Process all devices from the backend
npm run gen:device-pages -- --batch
```

### Generate Specific Device Classes

```bash
# Process all devices of specific classes
npm run gen:device-pages -- --device-classes=LgTv,AppleTVDevice
```

### Generate Multiple Specific Devices

```bash
# Process specific device IDs
npm run gen:device-pages -- --device-ids=living_room_tv,bedroom_tv,kitchen_speaker
```

## Advanced Options

### Validation and Quality Assurance

```bash
# Validate TypeScript compilation of generated files
npm run gen:device-pages -- --validate-code

# Validate React component structure
npm run gen:device-pages -- --validate-components

# Run complete validation suite
npm run gen:device-pages -- --run-validation
```

### Documentation and Integration

```bash
# Generate comprehensive documentation
npm run gen:device-pages -- --generate-docs

# Generate router integration files
npm run gen:device-pages -- --generate-router

# Full system generation (batch + docs + router + validation)
npm run gen:device-pages -- --batch --full-system
```

### Configuration Options

```bash
# Custom API base URL
npm run gen:device-pages -- --device-id=tv --api-base-url=http://192.168.1.100:8000

# Custom output directory
npm run gen:device-pages -- --device-id=tv --output-dir=src/components/generated

# Custom concurrency for batch processing
npm run gen:device-pages -- --batch --max-concurrency=5
```

## File Structure and Integration Points

### Generated Files Location

```
src/
├── pages/devices/                    # Device components and hooks
│   ├── <device_id>.gen.tsx          # React component (always generated)
│   └── <device_id>.hooks.ts         # State hook (only with Python state)
├── types/generated/                  # Shared state interfaces
│   └── <StateClass>.state.ts        # TypeScript interface (shared)
└── types/
    └── BaseDeviceState.ts           # Base state interface (framework)
```

### Router Integration Files (Generated with --generate-router)

```
src/
├── pages/devices/
│   ├── index.gen.ts                 # Router manifest
│   ├── registry.gen.ts              # Device registry
│   └── lazy-routes.gen.ts           # Lazy-loaded routes
└── config/
    └── device-navigation.gen.ts     # Navigation configuration
```

### Documentation Files (Generated with --generate-docs)

```
docs/
├── devices/                         # Device-specific documentation
│   └── <device_id>.md              # Individual device docs
└── system/
    └── generated-overview.md        # System documentation
```

## Verification and Integration Checks

### 1. Component Generation Check

**File Location**: `src/pages/devices/<device_id>.gen.tsx`

**What to verify:**
```tsx
// Check that file starts with auto-generation comment
// Auto-generated from device config - DO NOT EDIT

// Verify imports are present
import React, { useState } from 'react';
import { useLogStore } from '../../stores/useLogStore';
import { useExecuteDeviceAction } from '../../hooks/useApi';
import { Button } from '../../components/ui/button';

// Check function name matches device ID
function <DeviceId>Page() {
  // Component implementation
}

export default <DeviceId>Page;
```

### 2. State Interface Check (if using Python state)

**File Location**: `src/types/generated/<StateClass>.state.ts`

**What to verify:**
```typescript
// Check imports
import { BaseDeviceState } from '../BaseDeviceState';

// Verify interface extends base state
export interface <StateClass>State extends BaseDeviceState {
  // Fields from Python class should be here
}

// Check default values export
export const default<StateClass>State: <StateClass>State = {
  // Default values should match Python class
};
```

### 3. State Hook Check (if using Python state)

**File Location**: `src/pages/devices/<device_id>.hooks.ts`

**What to verify:**
```typescript
// Check correct imports to shared state
import { <StateClass>State, default<StateClass>State } from '../../types/generated/<StateClass>.state';

// Verify hook function name
export function use<StateClass>(deviceId: string = '<device_id>') {
  // Hook implementation
}
```

### 4. Router Integration Check (if generated)

**File Location**: `src/pages/devices/index.gen.ts`

**What to verify:**
- Device entries are present in `generatedPages` export
- Lazy-loaded imports are correct
- Device registry contains all generated devices

### 5. Runtime Integration Check

**In your React application:**

```tsx
// Import generated component
import KitchenHoodPage from './pages/devices/kitchen_hood.gen';

// Import generated hook (if using Python state)
import { useLgTvState } from './pages/devices/living_room_tv.hooks';

// Use in your routing
<Route path="/devices/kitchen_hood" component={KitchenHoodPage} />
```

## Troubleshooting

### Common Issues and Solutions

#### 1. API Connection Errors

```bash
# Test API connectivity
npm run gen:device-pages -- --test-connection

# Common solutions:
# - Check if backend is running
# - Verify API base URL
# - Check network connectivity
```

#### 2. Device Not Found (404 Error)

```bash
# List supported device classes
npm run gen:device-pages -- --list-classes

# Solutions:
# - Verify device ID exists in backend
# - Check device configuration
# - Ensure device is properly registered
```

#### 3. Python State Generation Fails

```bash
# Error: "Failed to generate Python state types"

# Solutions:
# - Verify Python file exists and is readable
# - Check Python class name is correct
# - Ensure Python 3 is installed and accessible
# - Verify Python file has valid syntax
```

#### 4. TypeScript Compilation Errors

```bash
# Validate generated code
npm run gen:device-pages -- --validate-code

# Common issues:
# - Missing imports (check import paths)
# - Type conflicts (ensure unique state class names)
# - Syntax errors (re-generate the file)
```

#### 5. Component Validation Fails

```bash
# Validate components
npm run gen:device-pages -- --validate-components

# Common issues:
# - Missing required imports
# - Invalid React component structure
# - Missing onClick handlers or Button components
```

## Best Practices

### 1. Device ID Naming

- Use lowercase with underscores: `living_room_tv`
- Be descriptive and unique: `kitchen_main_speaker`
- Avoid special characters except underscores

### 2. Python State Classes

- Use descriptive class names: `LgTvState`, `AudioProcessorState`
- Keep classes focused on single device type
- Use type annotations for all fields
- Provide sensible default values

### 3. File Management

- **Never edit** `.gen.tsx` files manually (they get overwritten)
- Keep Python state files in version control
- Use shared state classes when devices have identical state

### 4. Testing Integration

1. Generate device page
2. Run validation suite: `npm run gen:device-pages -- --run-validation`
3. Test component in development environment
4. Verify state management (if using Python state)
5. Check router integration (if using router generation)

## CLI Quick Reference

```bash
# Basic commands
npm run gen:device-pages -- --device-id=<device_id>
npm run gen:device-pages -- --batch
npm run gen:device-pages -- --test-connection
npm run gen:device-pages -- --help

# With Python state
npm run gen:device-pages -- --device-id=<device_id> \
  --state-file=<path> --state-class=<class>

# Validation
npm run gen:device-pages -- --validate-code
npm run gen:device-pages -- --validate-components
npm run gen:device-pages -- --run-validation

# Advanced
npm run gen:device-pages -- --batch --full-system
npm run gen:device-pages -- --generate-docs --generate-router
npm run gen:device-pages -- --device-classes=LgTv,AppleTVDevice
```

## Support

For issues not covered in this guide:

1. Check console output for specific error messages
2. Run validation suite to identify issues
3. Verify API connectivity and device configuration
4. Review generated files for syntax errors
5. Check file permissions and directory structure 