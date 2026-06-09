# Device Page Generation - 3-Phase Implementation Plan

## Overview

This document provides a complete implementation plan for the device-specific UI page generation system. This plan is self-contained and includes all technical specifications needed for implementation.

## System Summary

**Goal**: Generate device-specific React UI pages dynamically from API configurations, replacing manual YAML-based maintenance.

**Core Features**:
- API-driven page generation from device configurations  
- Device class-specific UI patterns (buttons, navigation clusters, sliders, pointer pads)
- TypeScript state interface generation from Python classes
- Automatic icon selection from Heroicons/Lucide libraries
- Generated files become part of source base for manual customization

**Key APIs**:
- `GET /config/device/{device_id}` → Device configuration
- `GET /devices/{device_id}/groups` → Command groups

---

## Phase 1: Core Infrastructure (Weeks 1-2)

### Phase 1 Goal
Generate a functional page for one WirenboardIRDevice with basic validation.

### Phase 1 Deliverables

#### 1.1 Data Layer Foundation

**API Client Implementation**
```typescript
// File: src/lib/DeviceConfigurationClient.ts
export class DeviceConfigurationClient {
  constructor(private baseUrl: string) {}
  
  async fetchDeviceConfig(deviceId: string): Promise<DeviceConfig> {
    const response = await fetch(`${this.baseUrl}/config/device/${deviceId}`);
    if (!response.ok) throw new Error(`API Error: ${response.status}`);
    return response.json();
  }
  
  async fetchDeviceGroups(deviceId: string): Promise<DeviceGroups> {
    const response = await fetch(`${this.baseUrl}/devices/${deviceId}/groups`);
    if (!response.ok) throw new Error(`API Error: ${response.status}`);
    return response.json();
  }
  
  async validateConnectivity(): Promise<boolean> {
    try {
      const response = await fetch(`${this.baseUrl}/health`);
      return response.ok;
    } catch { return false; }
  }
}
```

**Core Data Interfaces**
```typescript
// File: src/types/DeviceConfig.ts
export interface DeviceConfig {
  device_id: string;
  device_name: string;
  device_class: string;
  config_class: string;
  commands: Record<string, DeviceCommand>;
}

export interface DeviceCommand {
  action: string;
  topic: string;
  description: string;
  group: string | null;
  params: CommandParameter[] | null;
}

export interface CommandParameter {
  name: string;
  type: 'range' | 'string' | 'integer';
  required: boolean;
  default: any;
  min: number | null;
  max: number | null;
  description: string;
}

export interface DeviceGroups {
  device_id: string;
  groups: DeviceGroup[];
}

export interface DeviceGroup {
  group_id: string;
  group_name: string;
  actions: GroupAction[];
  status: string;
}

export interface GroupAction {
  name: string;
  description: string;
  params: CommandParameter[] | null;
}
```

**Basic Validation**
```typescript
// File: src/lib/DataValidator.ts
import Ajv from 'ajv';

export class DataValidator {
  private ajv = new Ajv();
  
  validateDeviceConfig(data: unknown): DeviceConfig {
    // Basic structure validation
    if (!this.isValidDeviceConfig(data)) {
      throw new Error('Invalid device configuration structure');
    }
    return data as DeviceConfig;
  }
  
  private isValidDeviceConfig(data: any): boolean {
    return data && 
           typeof data.device_id === 'string' &&
           typeof data.device_name === 'string' &&
           typeof data.device_class === 'string' &&
           data.commands && typeof data.commands === 'object';
  }
}
```

#### 1.2 Processing Layer - WirenboardIR Handler

**Device Structure Interfaces**
```typescript
// File: src/types/ProcessedDevice.ts
export interface DeviceStructure {
  deviceId: string;
  deviceName: string;
  deviceClass: string;
  uiSections: UISection[];
  stateInterface: StateDefinition;
  actionHandlers: ActionHandler[];
}

export interface UISection {
  sectionId: string;
  sectionName: string;
  componentType: 'ButtonGrid' | 'NavCluster' | 'SliderControl' | 'PointerPad';
  actions: ProcessedAction[];
  layout: LayoutConfig;
}

export interface ProcessedAction {
  actionName: string;
  displayName: string;
  description: string;
  parameters: ProcessedParameter[];
  group: string;
  icon: ActionIcon;
  uiHints: UIHints;
}

export interface ActionIcon {
  iconLibrary: 'heroicons' | 'lucide' | 'fallback';
  iconName: string;
  iconVariant?: 'outline' | 'solid' | 'mini';
  fallbackIcon: string;
  confidence: number;
}
```

**WirenboardIR Device Handler**
```typescript
// File: src/lib/deviceHandlers/WirenboardIRHandler.ts
export class WirenboardIRHandler implements DeviceClassHandler {
  deviceClass = 'WirenboardIRDevice';
  
  analyzeStructure(config: DeviceConfig, groups: DeviceGroups): DeviceStructure {
    return {
      deviceId: config.device_id,
      deviceName: config.device_name,
      deviceClass: config.device_class,
      uiSections: this.createUISections(groups),
      stateInterface: this.createBasicStateInterface(config),
      actionHandlers: this.createActionHandlers(config.commands)
    };
  }
  
  private createUISections(groups: DeviceGroups): UISection[] {
    return groups.groups.map(group => ({
      sectionId: group.group_id,
      sectionName: group.group_name,
      componentType: this.determineComponentType(group),
      actions: this.processGroupActions(group.actions),
      layout: { columns: 2, spacing: 'medium' }
    }));
  }
  
  private determineComponentType(group: DeviceGroup): ComponentType {
    const directionalCommands = ['up', 'down', 'left', 'right', 'ok'];
    const hasDirectional = group.actions.some(action => 
      directionalCommands.includes(action.name.toLowerCase())
    );
    return hasDirectional ? 'NavCluster' : 'ButtonGrid';
  }
  
  private processGroupActions(actions: GroupAction[]): ProcessedAction[] {
    return actions.map(action => ({
      actionName: action.name,
      displayName: this.formatDisplayName(action.name),
      description: action.description,
      parameters: action.params || [],
      group: 'default',
      icon: this.resolveIcon(action.name),
      uiHints: { buttonSize: 'medium', buttonStyle: 'secondary' }
    }));
  }
}
```

**Icon Resolution (Phase 1 Basic)**
```typescript
// File: src/lib/IconResolver.ts
export class IconResolver {
  private iconMappings = {
    power: { heroicons: 'PowerIcon', lucide: 'power', fallback: 'power' },
    up: { heroicons: 'ChevronUpIcon', lucide: 'chevron-up', fallback: 'arrow-up' },
    down: { heroicons: 'ChevronDownIcon', lucide: 'chevron-down', fallback: 'arrow-down' },
    left: { heroicons: 'ChevronLeftIcon', lucide: 'chevron-left', fallback: 'arrow-left' },
    right: { heroicons: 'ChevronRightIcon', lucide: 'chevron-right', fallback: 'arrow-right' },
    ok: { heroicons: 'CheckIcon', lucide: 'check', fallback: 'check' },
    menu: { heroicons: 'Bars3Icon', lucide: 'menu', fallback: 'menu' },
    back: { heroicons: 'ArrowLeftIcon', lucide: 'arrow-left', fallback: 'back' }
  };
  
  selectIconForAction(actionName: string): ActionIcon {
    const cleanName = actionName.toLowerCase().replace(/[_-]/g, '');
    const mapping = this.iconMappings[cleanName];
    
    if (mapping) {
      return {
        iconLibrary: 'heroicons',
        iconName: mapping.heroicons,
        iconVariant: 'outline',
        fallbackIcon: mapping.fallback,
        confidence: 0.9
      };
    }
    
    return {
      iconLibrary: 'heroicons',
      iconName: 'CommandLineIcon',
      iconVariant: 'outline', 
      fallbackIcon: 'command',
      confidence: 0.3
    };
  }
}
```

#### 1.3 Generation Layer - Basic Templates

**Component Template System**
```typescript
// File: src/lib/generators/DevicePageTemplate.ts
export class DevicePageTemplate {
  generateComponent(structure: DeviceStructure): string {
    return `
// Auto-generated from device config - DO NOT EDIT
import React from 'react';
import { useLogStore } from '../../stores/useLogStore';
import { useExecuteDeviceAction } from '../../hooks/useApi';
import { Button } from '../../components/ui/button';
${this.generateIconImports(structure.uiSections)}

function ${this.formatComponentName(structure.deviceId)}Page() {
  const { addLog } = useLogStore();
  const executeAction = useExecuteDeviceAction();

  const handleAction = (action: string, payload?: any) => {
    executeAction.mutate({ 
      deviceId: '${structure.deviceId}', 
      action: { name: action, ...payload } 
    });
    addLog({
      level: 'info',
      message: \`Action: \${action}\`,
      details: payload
    });
  };

  return (
    <div className="p-6 space-y-6">
      <div className="text-center">
        <h1 className="text-2xl font-bold">${structure.deviceName}</h1>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        ${this.generateSections(structure.uiSections)}
      </div>
    </div>
  );
}

export default ${this.formatComponentName(structure.deviceId)}Page;
    `.trim();
  }
  
  private generateSections(sections: UISection[]): string {
    return sections.map(section => `
      <div className="space-y-4">
        <h2 className="text-lg font-semibold">${section.sectionName}</h2>
        ${this.generateSectionContent(section)}
      </div>
    `).join('\n');
  }
  
  private generateSectionContent(section: UISection): string {
    if (section.componentType === 'ButtonGrid') {
      return this.generateButtonGrid(section.actions);
    }
    return `<div>Component type ${section.componentType} not implemented yet</div>`;
  }
  
  private generateButtonGrid(actions: ProcessedAction[]): string {
    return `
      <div className="grid grid-cols-2 gap-2">
        ${actions.map(action => this.generateButton(action)).join('\n        ')}
      </div>
    `;
  }
  
  private generateButton(action: ProcessedAction): string {
    const IconComponent = action.icon.iconName;
    return `
      <Button
        variant="secondary"
        size="default"
        onClick={() => handleAction('${action.actionName}')}
        className="flex items-center gap-2"
      >
        <${IconComponent} className="w-4 h-4" />
        ${action.displayName}
      </Button>
    `;
  }
}
```

#### 1.4 Generation Script (Phase 1)

**CLI Script Structure**
```typescript
// File: src/scripts/generate-device-pages.mjs
import { DeviceConfigurationClient } from '../lib/DeviceConfigurationClient.js';
import { WirenboardIRHandler } from '../lib/deviceHandlers/WirenboardIRHandler.js';
import { DevicePageTemplate } from '../lib/generators/DevicePageTemplate.js';
import { DataValidator } from '../lib/DataValidator.js';
import fs from 'fs/promises';
import path from 'path';

export class DevicePageGenerator {
  constructor(apiBaseUrl, outputDir) {
    this.client = new DeviceConfigurationClient(apiBaseUrl);
    this.validator = new DataValidator();
    this.outputDir = outputDir;
    this.handlers = new Map([
      ['WirenboardIRDevice', new WirenboardIRHandler()]
    ]);
  }
  
  async generateDevicePage(deviceId) {
    try {
      console.log(`Generating page for device: ${deviceId}`);
      
      // Fetch device data
      const [config, groups] = await Promise.all([
        this.client.fetchDeviceConfig(deviceId),
        this.client.fetchDeviceGroups(deviceId)
      ]);
      
      // Validate data
      const validatedConfig = this.validator.validateDeviceConfig(config);
      
      // Get device handler
      const handler = this.handlers.get(validatedConfig.device_class);
      if (!handler) {
        throw new Error(`Unsupported device class: ${validatedConfig.device_class}`);
      }
      
      // Process device structure
      const structure = handler.analyzeStructure(validatedConfig, groups);
      
      // Generate component
      const template = new DevicePageTemplate();
      const componentCode = template.generateComponent(structure);
      
      // Write file
      const outputPath = path.join(this.outputDir, `${deviceId}.gen.tsx`);
      await fs.writeFile(outputPath, componentCode, 'utf8');
      
      console.log(`✅ Generated: ${outputPath}`);
      return { success: true, outputPath };
      
    } catch (error) {
      console.error(`❌ Generation failed for ${deviceId}:`, error.message);
      return { success: false, error: error.message };
    }
  }
}

// CLI Interface
if (import.meta.url === `file://${process.argv[1]}`) {
  const args = process.argv.slice(2);
  const deviceId = args.find(arg => arg.startsWith('--device-id='))?.split('=')[1];
  const apiBaseUrl = args.find(arg => arg.startsWith('--api-base-url='))?.split('=')[1] || 'http://localhost:8000';
  const outputDir = args.find(arg => arg.startsWith('--output-dir='))?.split('=')[1] || 'src/pages/devices';
  
  if (!deviceId) {
    console.error('❌ --device-id is required');
    process.exit(1);
  }
  
  const generator = new DevicePageGenerator(apiBaseUrl, outputDir);
  const result = await generator.generateDevicePage(deviceId);
  
  process.exit(result.success ? 0 : 1);
}
```

### Phase 1 Success Criteria

1. **CLI Script Works**: `node src/scripts/generate-device-pages.mjs --device-id=test_device` executes without errors
2. **API Integration**: Successfully fetches device config and groups from backend
3. **File Generation**: Produces valid `.gen.tsx` file in target directory
4. **TypeScript Compilation**: Generated file compiles without TypeScript errors
5. **Basic UI**: Generated component renders buttons with icons for WirenboardIR device
6. **Action Integration**: Buttons can execute device actions through existing API hooks

### Phase 1 Validation Steps

```bash
# Test script execution
node src/scripts/generate-device-pages.mjs --device-id=living_room_tv --api-base-url=http://localhost:8000

# Verify TypeScript compilation
npx tsc --noEmit src/pages/devices/living_room_tv.gen.tsx

# Test in browser (manual)
# - Navigate to generated device page
# - Verify buttons render with icons
# - Click buttons to verify action execution
# - Check browser console for errors
```

---

## Phase 2: Multi-Device Support (Weeks 3-4)

### Phase 2 Goal
Support all existing device classes with specialized UI patterns and error handling.

### Phase 2 Deliverables

#### 2.1 Complete Device Class Handlers

**LgTv Handler with PointerPad**
```typescript
// File: src/lib/deviceHandlers/LgTvHandler.ts
export class LgTvHandler implements DeviceClassHandler {
  deviceClass = 'LgTv';
  
  analyzeStructure(config: DeviceConfig, groups: DeviceGroups): DeviceStructure {
    const uiSections = groups.groups.map(group => {
      if (group.group_id === 'pointer') {
        return this.createPointerSection(group);
      }
      return this.createStandardSection(group);
    });
    
    return {
      deviceId: config.device_id,
      deviceName: config.device_name,
      deviceClass: config.device_class,
      uiSections,
      stateInterface: this.createLgTvStateInterface(config),
      actionHandlers: this.createActionHandlers(config.commands)
    };
  }
  
  private createPointerSection(group: DeviceGroup): UISection {
    return {
      sectionId: 'pointer_control',
      sectionName: 'Pointer Control',
      componentType: 'PointerPad',
      actions: this.processPointerActions(group.actions),
      layout: { fullWidth: true }
    };
  }
  
  private processPointerActions(actions: GroupAction[]): ProcessedAction[] {
    return actions.map(action => ({
      actionName: action.name,
      displayName: this.formatPointerAction(action.name),
      description: action.description,
      parameters: action.params || [],
      group: 'pointer',
      icon: this.getPointerIcon(action.name),
      uiHints: { isPointerAction: true }
    }));
  }
}
```

**EMotivaXMC2 Handler with Multi-Zone**
```typescript
// File: src/lib/deviceHandlers/EMotivaXMC2Handler.ts
export class EMotivaXMC2Handler implements DeviceClassHandler {
  deviceClass = 'EMotivaXMC2';
  
  analyzeStructure(config: DeviceConfig, groups: DeviceGroups): DeviceStructure {
    const processedSections = [];
    
    for (const group of groups.groups) {
      const zoneCommands = this.identifyZoneCommands(group.actions);
      
      if (zoneCommands.length > 0) {
        // Create separate sections for each zone
        const zoneCount = this.determineZoneCount(zoneCommands);
        for (let zone = 1; zone <= zoneCount; zone++) {
          processedSections.push(this.createZoneSection(group, zone));
        }
      } else {
        processedSections.push(this.createStandardSection(group));
      }
    }
    
    return {
      deviceId: config.device_id,
      deviceName: config.device_name,
      deviceClass: config.device_class,
      uiSections: processedSections,
      stateInterface: this.createProcessorStateInterface(config),
      actionHandlers: this.createZoneAwareActionHandlers(config.commands)
    };
  }
  
  private createZoneSection(group: DeviceGroup, zoneNumber: number): UISection {
    return {
      sectionId: `${group.group_id}_zone_${zoneNumber}`,
      sectionName: `${group.group_name} - Zone ${zoneNumber}`,
      componentType: 'SliderControl',
      actions: this.processZoneActions(group.actions, zoneNumber),
      layout: { zoneNumber }
    };
  }
}
```

**BroadlinkKitchenHood Handler with Parameters**
```typescript
// File: src/lib/deviceHandlers/BroadlinkKitchenHoodHandler.ts
export class BroadlinkKitchenHoodHandler implements DeviceClassHandler {
  deviceClass = 'BroadlinkKitchenHood';
  
  analyzeStructure(config: DeviceConfig, groups: DeviceGroups): DeviceStructure {
    const uiSections = groups.groups.map(group => {
      const componentType = this.determineComponentType(group.actions);
      return {
        sectionId: group.group_id,
        sectionName: group.group_name,
        componentType,
        actions: this.processParameterActions(group.actions),
        layout: this.getLayoutForComponentType(componentType)
      };
    });
    
    return {
      deviceId: config.device_id,
      deviceName: config.device_name,
      deviceClass: config.device_class,
      uiSections,
      stateInterface: this.createKitchenHoodStateInterface(config),
      actionHandlers: this.createParameterAwareActionHandlers(config.commands)
    };
  }
  
  private determineComponentType(actions: GroupAction[]): ComponentType {
    const hasRangeParams = actions.some(action => 
      action.params?.some(param => param.type === 'range')
    );
    return hasRangeParams ? 'SliderControl' : 'ButtonGrid';
  }
}
```

#### 2.2 Enhanced Component Generators

**PointerPad Generator**
```typescript
// File: src/lib/generators/PointerPadGenerator.ts
export class PointerPadGenerator {
  generate(actions: ProcessedAction[]): string {
    const moveAction = actions.find(a => a.actionName.includes('move_cursor'));
    const clickAction = actions.find(a => a.actionName.includes('click'));
    
    return `
      <div className="pointer-pad-container">
        <div className="text-center mb-4">
          <h3 className="text-lg font-medium">Pointer Control</h3>
        </div>
        <PointerPad
          onMove={(x, y) => handleAction('${moveAction?.actionName}', { x, y })}
          onClick={() => handleAction('${clickAction?.actionName}')}
          className="w-full h-64 border rounded-lg bg-gray-50"
        />
      </div>
    `;
  }
}
```

**SliderControl Generator**
```typescript
// File: src/lib/generators/SliderControlGenerator.ts
export class SliderControlGenerator {
  generate(actions: ProcessedAction[]): string {
    return actions.map(action => {
      const rangeParam = action.parameters.find(p => p.type === 'range');
      if (!rangeParam) return this.generateButton(action);
      
      return `
        <div className="slider-control">
          <label className="block text-sm font-medium mb-2">
            <${action.icon.iconName} className="w-4 h-4 inline mr-2" />
            ${action.displayName}
          </label>
          <SliderControl
            min={${rangeParam.min}}
            max={${rangeParam.max}}
            defaultValue={${rangeParam.default}}
            onValueChange={(value) => handleAction('${action.actionName}', { ${rangeParam.name}: value })}
            className="w-full"
          />
        </div>
      `;
    }).join('\n');
  }
}
```

#### 2.3 Error Handling & Operations

**Unified Error Handling**
```typescript
// File: src/lib/ErrorHandler.ts
export enum ErrorType {
  API_CONNECTION = 'api_connection',
  API_VALIDATION = 'api_validation',
  DEVICE_CLASS_UNSUPPORTED = 'device_class_unsupported',
  GENERATION_FAILURE = 'generation_failure',
  FILE_WRITE_ERROR = 'file_write_error'
}

export class ErrorHandler {
  handleError(error: Error, context: ErrorContext): RecoveryResult {
    const errorType = this.classifyError(error, context);
    
    switch (errorType) {
      case ErrorType.API_CONNECTION:
        return this.handleApiConnectionError(error, context);
      case ErrorType.DEVICE_CLASS_UNSUPPORTED:
        return this.handleUnsupportedDeviceClass(error, context);
      default:
        return this.handleGenericError(error, context);
    }
  }
  
  private handleApiConnectionError(error: Error, context: ErrorContext): RecoveryResult {
    return {
      success: false,
      action: 'retry',
      message: `API connection failed: ${error.message}`,
      retryAfter: 5000,
      manualSteps: ['Check if backend is running', 'Verify API base URL']
    };
  }
}
```

**Basic Performance Monitoring**
```typescript
// File: src/lib/PerformanceMonitor.ts
export class PerformanceMonitor {
  private metrics: GenerationMetrics = {
    totalGenerations: 0,
    successfulGenerations: 0,
    failedGenerations: 0,
    averageGenerationTime: 0,
    deviceClassBreakdown: {}
  };
  
  trackGenerationStart(deviceId: string): PerformanceTimer {
    return {
      deviceId,
      startTime: Date.now(),
      complete: (success: boolean, deviceClass: string) => {
        const duration = Date.now() - startTime;
        this.recordGeneration(success, deviceClass, duration);
      }
    };
  }
  
  recordGeneration(success: boolean, deviceClass: string, duration: number): void {
    this.metrics.totalGenerations++;
    if (success) {
      this.metrics.successfulGenerations++;
    } else {
      this.metrics.failedGenerations++;
    }
    
    this.updateAverageTime(duration);
    this.updateDeviceClassBreakdown(deviceClass);
  }
}
```

#### 2.4 Batch Processing

**Batch Generator**
```typescript
// File: src/lib/BatchProcessor.ts
export class BatchProcessor {
  constructor(private generator: DevicePageGenerator) {}
  
  async processDeviceList(deviceIds: string[]): Promise<BatchResult> {
    const results: GenerationResult[] = [];
    
    for (const deviceId of deviceIds) {
      console.log(`Processing ${deviceId}...`);
      const result = await this.generator.generateDevicePage(deviceId);
      results.push({ deviceId, ...result });
    }
    
    return this.summarizeResults(results);
  }
  
  async processAllDevices(): Promise<BatchResult> {
    // Discover all devices from API
    const devices = await this.discoverDevices();
    return this.processDeviceList(devices.map(d => d.device_id));
  }
  
  private summarizeResults(results: GenerationResult[]): BatchResult {
    const successful = results.filter(r => r.success);
    const failed = results.filter(r => !r.success);
    
    return {
      totalProcessed: results.length,
      successful: successful.length,
      failed: failed.length,
      successRate: (successful.length / results.length) * 100,
      failedDevices: failed.map(f => ({ deviceId: f.deviceId, error: f.error })),
      generatedFiles: successful.map(s => s.outputPath)
    };
  }
}
```

### Phase 2 Success Criteria

1. **All Device Classes Supported**: WirenboardIRDevice, LgTv, EMotivaXMC2, BroadlinkKitchenHood, AppleTVDevice
2. **Specialized UI Components**: PointerPad for LgTv, multi-zone controls for EMotivaXMC2, parameter-based controls for BroadlinkKitchenHood
3. **Error Handling**: Graceful handling of API failures, unsupported devices, and generation errors
4. **Batch Processing**: Can generate multiple devices in single run
5. **Performance Monitoring**: Basic metrics collection and reporting

---

## Phase 3: Production Readiness (Weeks 5-6)

### Phase 3 Goal
Production-ready system with full validation, monitoring, and documentation.

### Phase 3 Deliverables

#### 3.1 Complete Validation Framework

**Generated Code Validation**
```typescript
// File: src/lib/validation/CodeValidator.ts
export class CodeValidator {
  async validateTypeScriptCompilation(filePath: string): Promise<CompilationResult> {
    const ts = await import('typescript');
    const program = ts.createProgram([filePath], {
      noEmit: true,
      allowJs: false,
      checkJs: false
    });
    
    const diagnostics = ts.getPreEmitDiagnostics(program);
    const errors = diagnostics.filter(d => d.category === ts.DiagnosticCategory.Error);
    const warnings = diagnostics.filter(d => d.category === ts.DiagnosticCategory.Warning);
    
    return {
      success: errors.length === 0,
      errors: errors.map(this.formatDiagnostic),
      warnings: warnings.map(this.formatDiagnostic)
    };
  }
  
  async validateImportResolution(filePath: string): Promise<ImportValidationResult> {
    const content = await fs.readFile(filePath, 'utf8');
    const imports = this.extractImports(content);
    
    const results = await Promise.all(
      imports.map(async imp => ({
        import: imp,
        resolved: await this.canResolveImport(imp, filePath)
      }))
    );
    
    return {
      allImportsResolved: results.every(r => r.resolved),
      missingImports: results.filter(r => !r.resolved).map(r => r.import),
      circularDependencies: await this.detectCircularDependencies(filePath)
    };
  }
}
```

**Runtime Component Validation**
```typescript
// File: src/lib/validation/ComponentValidator.ts
export class ComponentValidator {
  async validateComponentRendering(componentPath: string): Promise<RenderValidationResult> {
    // Use React Testing Library for basic render validation
    const { render } = await import('@testing-library/react');
    const Component = await import(componentPath);
    
    try {
      const { container } = render(<Component.default />);
      
      return {
        rendersWithoutCrash: true,
        hasRequiredElements: this.checkRequiredElements(container),
        missingComponents: this.identifyMissingComponents(container),
        renderErrors: []
      };
    } catch (error) {
      return {
        rendersWithoutCrash: false,
        hasRequiredElements: false,
        missingComponents: [],
        renderErrors: [{ message: error.message, stack: error.stack }]
      };
    }
  }
}
```

#### 3.2 State Type Generation

**Python State Parser**
```typescript
// File: src/lib/StateTypeGenerator.ts
import { spawn } from 'child_process';

export class StateTypeGenerator {
  async generateFromPythonClass(filePath: string, className: string): Promise<StateDefinition> {
    // Use Python AST to parse state class
    const pythonScript = `
import ast
import sys

def extract_class_fields(file_path, class_name):
    with open(file_path, 'r') as f:
        tree = ast.parse(f.read())
    
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            fields = []
            for item in node.body:
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    fields.append({
                        'name': item.target.id,
                        'type': ast.unparse(item.annotation),
                        'optional': False
                    })
            return fields
    return []

fields = extract_class_fields(sys.argv[1], sys.argv[2])
import json
print(json.dumps(fields))
    `;
    
    return new Promise((resolve, reject) => {
      const process = spawn('python3', ['-c', pythonScript, filePath, className]);
      let output = '';
      
      process.stdout.on('data', (data) => {
        output += data.toString();
      });
      
      process.on('close', (code) => {
        if (code === 0) {
          const fields = JSON.parse(output);
          resolve(this.convertToStateDefinition(className, fields));
        } else {
          reject(new Error(`Python parsing failed with code ${code}`));
        }
      });
    });
  }
  
  private convertToStateDefinition(className: string, fields: any[]): StateDefinition {
    return {
      interfaceName: `${className}`,
      fields: fields.map(field => ({
        name: field.name,
        type: this.mapPythonTypeToTypeScript(field.type),
        optional: field.optional,
        description: ''
      })),
      imports: ['BaseDeviceState'],
      extends: ['BaseDeviceState']
    };
  }
}
```

#### 3.3 Complete Integration

**Router Integration**
```typescript
// File: src/lib/RouterIntegration.ts
export class RouterIntegration {
  generateRouterManifest(devices: DevicePageEntry[]): GeneratedFile {
    const manifestContent = {
      devices,
      generatedAt: new Date().toISOString(),
      apiVersion: '1.0'
    };
    
    const routerCode = `
// Auto-generated router manifest - DO NOT EDIT
import { lazy } from 'react';

${devices.map(device => `
const ${this.formatComponentName(device.id)}Page = lazy(() => import('./devices/${device.id}.gen'));
`).join('')}

export const generatedDevicePages = {
${devices.map(device => `  '${device.id}': ${this.formatComponentName(device.id)}Page`).join(',\n')}
};

export const devicePageManifest = ${JSON.stringify(devices, null, 2)};
    `;
    
    return {
      filepath: 'src/pages/devices/index.gen.ts',
      content: routerCode.trim(),
      dependencies: devices.map(d => `./devices/${d.id}.gen`),
      checksum: this.generateChecksum(routerCode),
      generatedAt: new Date(),
      sourceHash: this.generateChecksum(JSON.stringify(manifestContent))
    };
  }
}
```

#### 3.4 Documentation Generation

**Usage Guide Generator**
```typescript
// File: src/lib/DocumentationGenerator.ts
export class DocumentationGenerator {
  generateDeviceDocumentation(structure: DeviceStructure): GeneratedFile {
    const content = `
# ${structure.deviceName} - Generated Device Page

## Overview
- **Device ID**: ${structure.deviceId}
- **Device Class**: ${structure.deviceClass}
- **Generated At**: ${new Date().toISOString()}

## UI Sections

${structure.uiSections.map(section => `
### ${section.sectionName}
- **Component Type**: ${section.componentType}
- **Actions**: ${section.actions.length}

${section.actions.map(action => `
#### ${action.displayName}
- **Action**: ${action.actionName}
- **Description**: ${action.description}
- **Icon**: ${action.icon.iconName} (${action.icon.iconLibrary})
${action.parameters.length > 0 ? `
- **Parameters**:
${action.parameters.map(param => `  - ${param.name}: ${param.type}`).join('\n')}
` : ''}
`).join('')}
`).join('')}

## Integration

\`\`\`typescript
import ${this.formatComponentName(structure.deviceId)}Page from './devices/${structure.deviceId}.gen';

// Use in router
const deviceRoutes = [
  { path: '/devices/${structure.deviceId}', component: ${this.formatComponentName(structure.deviceId)}Page }
];
\`\`\`

## Manual Customization

This generated file can be manually customized after generation. The system will warn before overwriting customized files.
    `;
    
    return {
      filepath: `docs/devices/${structure.deviceId}.md`,
      content: content.trim(),
      dependencies: [],
      checksum: this.generateChecksum(content),
      generatedAt: new Date(),
      sourceHash: ''
    };
  }
}
```

### Phase 3 Success Criteria

1. **Complete Validation Suite**: TypeScript compilation, import resolution, component rendering validation
2. **State Type Generation**: Python class parsing and TypeScript interface generation
3. **Router Integration**: Automatic router configuration with lazy loading
4. **Documentation Generation**: Complete usage guides for all generated devices
5. **Production Deployment**: System ready for production use with monitoring

### Phase 3 Validation Steps

```bash
# Full system test
node src/scripts/generate-device-pages.mjs --batch --config-file=batch-config.json

# Validation suite
npm run validate:generated-code
npm run test:generated-components

# Build verification
npm run build
npm run type-check

# Manual testing checklist:
# □ All device pages load without errors
# □ Device actions execute correctly
# □ State updates reflect in UI
# □ Icons display properly
# □ Generated documentation is accurate
# □ Router integration works
```

---

## Implementation Timeline

### Week 1
- [ ] Data Layer: API client and validation
- [ ] Processing Layer: WirenboardIR handler
- [ ] Basic icon resolution system
- [ ] CLI script foundation

### Week 2
- [ ] Generation Layer: Component templates
- [ ] Button generation with icons
- [ ] File output system
- [ ] Phase 1 validation and testing

### Week 3
- [ ] All device class handlers
- [ ] Specialized component generators (PointerPad, SliderControl)
- [ ] Error handling framework
- [ ] Performance monitoring

### Week 4
- [ ] Batch processing system
- [ ] Enhanced icon resolution
- [ ] Multi-zone control generation
- [ ] Phase 2 validation and testing

### Week 5
- [ ] Validation framework
- [ ] State type generation
- [ ] Router integration
- [ ] Documentation generation

### Week 6
- [ ] Production hardening
- [ ] Complete testing suite
- [ ] Performance optimization
- [ ] Phase 3 validation and deployment

---

## Commands Reference

```bash
# Single device generation
node src/scripts/generate-device-pages.mjs \
  --device-id=living_room_tv \
  --api-base-url=http://localhost:8000 \
  --output-dir=src/pages/devices \
  --param-ui-mode=sliders

# Batch processing
node src/scripts/generate-device-pages.mjs \
  --batch \
  --config-file=device-batch-config.json

# Validation
npm run validate:generated-code
npm run test:device-pages

# Development
npm run dev  # Start Vite dev server
npm run build  # Build for production
```

## Success Metrics

- **Phase 1**: Generate 1 working device page in 2 weeks
- **Phase 2**: Support all 5+ device classes in 4 weeks total
- **Phase 3**: Production-ready system in 6 weeks total
- **Code Quality**: Generated TypeScript compiles without errors
- **Functionality**: All device actions execute successfully
- **Performance**: Generation completes in <30 seconds per device 