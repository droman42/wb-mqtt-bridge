# UI Code Restructuring Action Plan
*Implementation guide for integrating wb-mqtt-ui with package-based wb-mqtt-bridge backend*

> This document outlines the step-by-step action plan to migrate wb-mqtt-ui from file-based Python imports to package-based imports using the restructured wb-mqtt-bridge backend.

---

## Overview

The wb-mqtt-bridge backend has been restructured into a proper Python package with domain-centric architecture. This action plan details the necessary changes to integrate wb-mqtt-ui with the new package-based approach.

**Goal**: Migrate from file-path based Python class imports to package-based imports using `importlib` and the installed `wb-mqtt-bridge` package.

---

## Phase 1: Core Infrastructure Updates

### 1.1 Update StateTypeGenerator Class
**File**: `src/lib/StateTypeGenerator.ts`
**Priority**: High
**Estimated Time**: 2-3 hours

**Tasks**:
- [x] Add new method `generateFromImportPath(importPath: string)`
- [x] Implement `importlib`-based Python class loading
- [x] Add fallback logic to support both old and new import methods during transition
- [x] Add error handling for import failures

**Implementation Details**:
```typescript
// Add to StateTypeGenerator class
async generateFromImportPath(importPath: string): Promise<TypeDefinition> {
  // Parse import path (e.g., "wb_mqtt_bridge.domain.devices.models:WirenboardIRState")
  const [modulePath, className] = importPath.split(':');
  
  // Use importlib to dynamically import the class
  const pythonScript = `
import importlib
module = importlib.import_module("${modulePath}")
cls = getattr(module, "${className}")
# Generate type information...
  `;
  
  // Execute Python script and process results
}

// Update existing generateFromPythonClass to use new method when stateClassImport is available
```

### 1.2 Update Device Configuration Schema
**Files**: 
- `config/device-state-mapping.json`
- `config/device-state-mapping.local.json`
**Priority**: High
**Estimated Time**: 1-2 hours

**Tasks**:
- [x] Add `stateClassImport` field to all device configurations
- [x] Keep existing `stateFile`/`stateClass` fields for backward compatibility
- [x] Add new `ScenarioDevice` configuration for virtual devices

**New Configuration Format**:
```jsonc
{
  "WirenboardIRDevice": {
    "stateClassImport": "wb_mqtt_bridge.domain.devices.models:WirenboardIRState",
    "deviceConfigs": ["config/devices/ld_player.json"],
    // Legacy fallback (remove in Phase 3)
    "stateFile": "app/schemas.py",
    "stateClass": "WirenboardIRState"
  },
  "ScenarioDevice": {
    "stateClassImport": "wb_mqtt_bridge.infrastructure.scenarios.models:ScenarioWBConfig",
    "scenarioConfigs": ["config/scenarios/*.json"],
    "description": "Virtual WB device configurations for scenarios"
  }
}
```

### 1.3 Update Build Scripts
**File**: `src/scripts/generate-device-pages.ts`
**Priority**: High
**Estimated Time**: 1-2 hours

**Tasks**:
- [x] Modify script to pass `stateClassImport` to StateTypeGenerator
- [x] Add logic to prefer `stateClassImport` over legacy methods
- [x] Add validation for import path format
- [x] Include error handling and logging

---

## Phase 2: New Features Integration

### 2.1 Scenario Virtual Device Support
**Files**: Multiple (to be determined during implementation)
**Priority**: Medium
**Estimated Time**: 4-6 hours

**Tasks**:
- [x] Add `ScenarioWBConfig` to type generation pipeline
- [x] Create TypeScript interfaces for scenario virtual configurations
- [x] Add UI components for scenario virtual device controls
- [x] Implement state management for virtual devices

### 2.2 New API Endpoints Integration
**Files**: 
- `src/hooks/useApi.ts`
- `src/types/api.ts`
**Priority**: Medium
**Estimated Time**: 2-3 hours

**Tasks**:
- [x] Add TypeScript types for new scenario endpoints
- [x] Implement API hooks for scenario virtual configurations:
  - `GET /scenario/virtual_config/{scenario_id}`
  - `GET /scenario/virtual_configs`
- [x] Add error handling and loading states
- [x] Update existing API integration patterns

**New API Types**:
```typescript
interface ScenarioWBConfig {
  device_id: string;
  device_name: string;
  device_class: string;
  commands: Command[];
  // ... additional fields based on backend model
}

// Add to useApi hook
const useScenarioVirtualConfig = (scenarioId: string) => {
  // Implementation
};

const useScenarioVirtualConfigs = () => {
  // Implementation
};
```

---

## Phase 3: Testing and Validation

### 3.1 Local Development Setup
**Priority**: High
**Estimated Time**: 1 hour

**Tasks**:
- [x] Document installation process: `pip install -e ../wb-mqtt-bridge`
- [x] Create validation script to test backend imports
- [x] Add development workflow documentation
- [x] Test type generation with new import paths

**Validation Script**:
```bash
#!/bin/bash
# Test backend package installation
python -c "from wb_mqtt_bridge.domain.devices.models import WirenboardIRState; print('✅ Device models import successful')"
python -c "from wb_mqtt_bridge.infrastructure.scenarios.models import ScenarioWBConfig; print('✅ Scenario models import successful')"

# Test console scripts
wb-api --help
device-test --help

# Generate types and verify
npm run generate
npm run type-check
```

### 3.2 Comprehensive Testing
**Priority**: High
**Estimated Time**: 3-4 hours

**Tasks**:
- [x] Test all existing device configurations with new import paths
- [x] Verify TypeScript generation for all device models
- [x] Test scenario virtual configuration generation
- [x] Validate UI components work with generated types
- [x] Test error handling for invalid import paths
- [x] Verify backward compatibility during transition

### 3.3 Integration Testing
**Priority**: Medium
**Estimated Time**: 2-3 hours

**Tasks**:
- [x] Test with live wb-mqtt-bridge backend
- [x] Verify new API endpoints integration
- [x] Test scenario virtual device controls
- [x] Validate end-to-end device control flows

---

## Phase 4: CI/CD and Deployment

### 4.1 GitHub Actions Updates
**Files**: `.github/workflows/*.yml`
**Priority**: Medium
**Estimated Time**: 2-3 hours

**Tasks**:
- [x] Update build workflow to install wb-mqtt-bridge package
- [x] Add artifact-based integration for cross-repo setup
- [x] Implement caching strategy for Python packages
- [x] Add validation steps for type generation

**Workflow Updates**:
```yaml
# Example workflow changes
- name: Set up Python 3.11
  uses: actions/setup-python@v4
  with:
    python-version: '3.11'  # wb-mqtt-bridge requires Python 3.11+

- name: Install backend package
  run: pip install -e ../wb-mqtt-bridge  # monorepo
  # or
  run: pip install wb-mqtt-bridge>=1.0.0  # separate repos

- name: Generate types
  run: npm run gen:device-pages

- name: Validate generated types
  run: npm run typecheck:all
```

### 4.2 Documentation Updates
**Priority**: Low
**Estimated Time**: 1-2 hours

**Tasks**:
- [x] Update README.md with new setup instructions
- [x] Document new development workflow
- [x] Add troubleshooting section for common import issues
- [x] Update deployment documentation

---

## Phase 5: Migration and Cleanup

### 5.1 Legacy Code Removal
**Priority**: Low
**Estimated Time**: 1-2 hours

**Tasks**:
- [ ] Remove `stateFile` and `stateClass` fields from configurations
- [ ] Remove legacy file-path based import logic
- [ ] Clean up unused code paths
- [ ] Update documentation to reflect final state

### 5.2 Performance Optimization
**Priority**: Low
**Estimated Time**: 1-2 hours

**Tasks**:
- [ ] Optimize type generation performance
- [ ] Add caching for generated types
- [ ] Minimize Python subprocess calls
- [ ] Benchmark generation time improvements

---

## Implementation Order

### Week 1: Core Infrastructure
1. Update StateTypeGenerator class (1.1)
2. Update device configuration files (1.2)
3. Update build scripts (1.3)
4. Set up local development environment (3.1)

### Week 2: Features and Testing
1. Implement scenario virtual device support (2.1)
2. Integrate new API endpoints (2.2)
3. Comprehensive testing (3.2)
4. Integration testing (3.3)

### Week 3: Deployment and Cleanup
1. Update CI/CD workflows (4.1)
2. Update documentation (4.2)
3. Legacy code removal (5.1)
4. Performance optimization (5.2)

---

## Risk Mitigation

### High Risk Items
- **Import path resolution**: Ensure all Python import paths are correct
- **Backward compatibility**: Maintain support for existing configurations during transition
- **CI/CD integration**: Verify cross-repo workflows function correctly

### Mitigation Strategies
- Implement comprehensive fallback logic
- Add extensive error handling and logging
- Create rollback plan for each phase
- Test thoroughly in development environment before deployment

---

## Success Criteria

- [ ] All device models generate TypeScript types using package imports
- [ ] New scenario virtual device features are fully functional
- [ ] CI/CD pipelines build and deploy successfully
- [ ] Local development workflow is streamlined
- [ ] Performance is maintained or improved
- [ ] No regression in existing functionality
- [ ] All tests pass
- [ ] Documentation is complete and accurate

---

## Dependencies

### External Dependencies
- wb-mqtt-bridge package must be installable
- Python environment with wb-mqtt-bridge installed
- Node.js environment for UI build

### Internal Dependencies
- Complete Phase 1 before starting Phase 2
- Testing phases should run in parallel with development
- CI/CD updates depend on successful local testing

---

*Document created: January 2025*
*Estimated total effort: 20-30 hours*
*Timeline: 2-3 weeks* 