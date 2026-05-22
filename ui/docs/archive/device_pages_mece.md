# Device UI Page Generation System (MECE Architecture)

## Overview

This document outlines the implementation of a device-specific UI page generation system that dynamically creates React components from API configurations. The system replaces manual YAML-based page maintenance with automated generation leveraging backend device structures.

## System Architecture

The system is organized into five distinct domains, each with clear responsibilities and interfaces:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Data Layer    │───▶│ Processing Layer│───▶│Generation Layer │
│ API Integration │    │Device Analysis  │    │Component Output │
│   Validation    │    │Type Generation  │    │File Management  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 ▼
         ┌─────────────────┐    ┌─────────────────┐
         │Integration Layer│    │Operations Layer │
         │Build/Deploy     │    │Error Handling   │
         │Version Control  │    │Performance      │
         └─────────────────┘    │Monitoring       │
                                └─────────────────┘
```

---

## 1. Data Layer

### 1.1 API Integration

#### Primary Endpoints
```typescript
// Device configuration endpoint
GET /config/device/{device_id} → DeviceConfig

// Device command groups endpoint  
GET /devices/{device_id}/groups → DeviceGroups
```

#### Data Contracts

```typescript
interface DeviceConfig {
  device_id: string;
  device_name: string;
  device_class: string;  // Determines generation strategy
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
```

#### API Client Implementation
```typescript
class DeviceConfigurationClient {
  constructor(private baseUrl: string) {}
  
  async fetchDeviceConfig(deviceId: string): Promise<DeviceConfig>
  async fetchDeviceGroups(deviceId: string): Promise<DeviceGroups>
  async validateConnectivity(): Promise<boolean>
}
```

### 1.2 Data Validation

#### Schema Validation
```typescript
// JSON Schema validators for API responses
const DeviceConfigSchema = { /* AJV schema */ };
const DeviceGroupsSchema = { /* AJV schema */ };

class DataValidator {
  validateDeviceConfig(data: unknown): DeviceConfig
  validateDeviceGroups(data: unknown): DeviceGroups  
  validateCommandStructure(commands: unknown): boolean
}
```

#### Validation Rules
- Device ID must be valid JavaScript identifier
- Commands must have non-empty action names
- Parameters must use supported types only
- Group IDs must be non-empty strings
- API responses must match exact schema structure

---

## 2. Processing Layer

### 2.1 Device Analysis

#### Device Class Registry
```typescript
interface DeviceClassHandler {
  deviceClass: string;
  analyzeStructure(config: DeviceConfig, groups: DeviceGroups): DeviceStructure;
  generateComponents(structure: DeviceStructure): ComponentDefinition[];
}

// Registry of all device class handlers
const DEVICE_CLASS_HANDLERS: Map<string, DeviceClassHandler> = new Map([
  ['WirenboardIRDevice', new WirenboardIRHandler()],
  ['LgTv', new LgTvHandler()],
  ['EMotivaXMC2', new ProcessorHandler()],
  ['BroadlinkKitchenHood', new KitchenHoodHandler()],
  ['AppleTVDevice', new AppleTVHandler()],
]);

#### Action Processing & Icon Resolution
```typescript
interface ActionProcessor {
  processDeviceActions(commands: DeviceCommand[], groups: DeviceGroup[]): ProcessedAction[];
  resolveActionIcons(actions: ProcessedAction[]): ProcessedAction[];
  generateUIHints(actions: ProcessedAction[], deviceClass: string): ProcessedAction[];
}

interface IconResolver {
  selectIconForAction(actionName: string, description: string, group: string): ActionIcon;
  mapActionToIcon(actionName: string): IconMapping;
  searchIconLibraries(keywords: string[]): IconSearchResult[];
  getFallbackIcon(group: string): ActionIcon;
}

// Icon mapping rules based on action patterns
const ACTION_ICON_MAPPINGS = {
  // Power controls
  power: { heroicons: 'PowerIcon', lucide: 'power', fallback: 'power' },
  'power_on': { heroicons: 'PlayIcon', lucide: 'power', fallback: 'play' },
  'power_off': { heroicons: 'StopIcon', lucide: 'power-off', fallback: 'stop' },
  
  // Navigation controls
  up: { heroicons: 'ChevronUpIcon', lucide: 'chevron-up', fallback: 'arrow-up' },
  down: { heroicons: 'ChevronDownIcon', lucide: 'chevron-down', fallback: 'arrow-down' },
  left: { heroicons: 'ChevronLeftIcon', lucide: 'chevron-left', fallback: 'arrow-left' },
  right: { heroicons: 'ChevronRightIcon', lucide: 'chevron-right', fallback: 'arrow-right' },
  ok: { heroicons: 'CheckIcon', lucide: 'check', fallback: 'check' },
  back: { heroicons: 'ArrowLeftIcon', lucide: 'arrow-left', fallback: 'back' },
  home: { heroicons: 'HomeIcon', lucide: 'home', fallback: 'home' },
  menu: { heroicons: 'Bars3Icon', lucide: 'menu', fallback: 'menu' },
  
  // Volume controls
  volume_up: { heroicons: 'SpeakerWaveIcon', lucide: 'volume-2', fallback: 'volume-up' },
  volume_down: { heroicons: 'SpeakerXMarkIcon', lucide: 'volume-1', fallback: 'volume-down' },
  mute: { heroicons: 'SpeakerXMarkIcon', lucide: 'volume-x', fallback: 'mute' },
  
  // Media controls
  play: { heroicons: 'PlayIcon', lucide: 'play', fallback: 'play' },
  pause: { heroicons: 'PauseIcon', lucide: 'pause', fallback: 'pause' },
  stop: { heroicons: 'StopIcon', lucide: 'square', fallback: 'stop' },
  next: { heroicons: 'ForwardIcon', lucide: 'skip-forward', fallback: 'next' },
  previous: { heroicons: 'BackwardIcon', lucide: 'skip-back', fallback: 'previous' },
  
  // Input/Source controls
  input: { heroicons: 'RectangleStackIcon', lucide: 'layers', fallback: 'input' },
  hdmi: { heroicons: 'TvIcon', lucide: 'monitor', fallback: 'tv' },
  usb: { heroicons: 'CircleStackIcon', lucide: 'usb', fallback: 'storage' },
  
  // Settings and controls
  settings: { heroicons: 'CogIcon', lucide: 'settings', fallback: 'settings' },
  info: { heroicons: 'InformationCircleIcon', lucide: 'info', fallback: 'info' },
  exit: { heroicons: 'XMarkIcon', lucide: 'x', fallback: 'close' },
  
  // Default fallbacks by group
  _group_fallbacks: {
    power: { heroicons: 'BoltIcon', lucide: 'zap', fallback: 'power' },
    volume: { heroicons: 'SpeakerWaveIcon', lucide: 'volume-2', fallback: 'volume' },
    navigation: { heroicons: 'CursorArrowRaysIcon', lucide: 'navigation', fallback: 'cursor' },
    media: { heroicons: 'PlayIcon', lucide: 'play', fallback: 'media' },
    input: { heroicons: 'RectangleStackIcon', lucide: 'layers', fallback: 'input' },
    default: { heroicons: 'CommandLineIcon', lucide: 'terminal', fallback: 'command' }
  }
};

interface IconMapping {
  heroicons: string;
  lucide: string;
  fallback: string;
}

interface IconSearchResult {
  library: 'heroicons' | 'lucide';
  iconName: string;
  confidence: number;
  matchType: 'exact' | 'partial' | 'semantic';
}
```
```

#### Device Structure Analysis
```typescript
interface DeviceStructure {
  deviceId: string;
  deviceName: string;
  deviceClass: string;
  uiSections: UISection[];
  stateInterface: StateDefinition;
  actionHandlers: ActionHandler[];
}

interface UISection {
  sectionId: string;
  sectionName: string;
  componentType: 'ButtonGrid' | 'NavCluster' | 'SliderControl' | 'PointerPad';
  actions: ProcessedAction[];
  layout: LayoutConfig;
}

interface ProcessedAction {
  actionName: string;
  displayName: string;
  description: string;
  parameters: ProcessedParameter[];
  group: string;
  icon: ActionIcon;  // Icon information resolved during processing
  uiHints: UIHints;
}

interface ActionIcon {
  iconLibrary: 'heroicons' | 'lucide' | 'fallback';
  iconName: string;
  iconVariant?: 'outline' | 'solid' | 'mini';
  fallbackIcon: string;
  confidence: number; // 0-1 confidence in icon selection
}

interface UIHints {
  buttonSize?: 'small' | 'medium' | 'large';
  buttonStyle?: 'primary' | 'secondary' | 'ghost';
  grouping?: string;
  priority?: number;
}
```

#### Device Class Strategies

**WirenboardIRDevice Strategy:**
- Strict adherence to API group structure
- Group-to-section mapping (1:1) 
- Button-based UI for all commands
- Preserve API ordering from backend
- No parameter-based controls (commands have params: null)
- DirectionalCommand detection for NavCluster generation

**LgTv Strategy:**
- Special handling for 'pointer' group → PointerPad component
  - `move_cursor(x, y)` → Absolute positioning mode
  - `move_cursor_relative(dx, dy)` → Relative movement mode
  - `click()` → Integrated click functionality
- Navigation groups (menu, directional) → NavCluster components
- Other command groups → Button grids
- State integration for cursor position tracking

**EMotivaXMC2 Strategy:**
- Multi-zone parameter expansion across all zone-based commands
- Zone parameter detection using min/max values to determine zone count
- `set_volume(level, zone)` → "Main Zone Volume" + "Zone 2 Volume" sliders
- Zone parameter hidden from UI, auto-populated per control instance
- Slider controls for range parameters, button grids for discrete commands

**BroadlinkKitchenHood Strategy:**
- Parameter-driven UI selection based on parameter types
- Range parameters → SliderControl or stepped buttons (configurable via --param-ui-mode)
- String parameters with limited values → Dropdown components
- Integer parameters → Number input or button increment/decrement
- Command grouping in logical sections (fan, light, etc.)

**AppleTVDevice Strategy:**
- Standard button grids for most command groups
- Menu/navigation groups → NavCluster for directional controls
- Playback controls → Specialized button grid layout
- Future expansion planned for Siri Remote simulation

**Default/Unknown Device Classes Strategy:**
- Generic pattern analysis for command structure inference
- Group-based organization using API group property
- Default to button grids for parameterless commands
- Parameter detection for control type selection
- Fallback UI generation with clear labeling for manual adjustment

### 2.2 State Type Generation

#### Complete State Generation Pipeline
```typescript
interface StateGenerationPipeline {
  // Python file analysis
  parsePythonStateClass(filePath: string, className: string): StateDefinition;
  
  // TypeScript interface generation  
  generateTypeScriptInterface(stateDefinition: StateDefinition): GeneratedFile;
  
  // Device-specific hook generation
  generateDeviceStateHook(deviceId: string, stateDefinition: StateDefinition): GeneratedFile;
  
  // State integration with components
  integrateStateWithComponents(deviceStructure: DeviceStructure): ComponentStateIntegration;
}
```

#### Python File Analysis
```typescript
interface PythonStateParser {
  parseStateClass(filePath: string, className: string): StateDefinition;
  extractFields(classNode: AST): FieldDefinition[];
  mapPythonTypeToTypeScript(pythonType: string): string;
  validateClassStructure(classNode: AST): ValidationResult;
  handleInheritance(classNode: AST): InheritanceInfo;
}

// Comprehensive type mapping rules
const TYPE_MAPPINGS = {
  // Primitive types
  'str': 'string',
  'int': 'number', 
  'float': 'number',
  'bool': 'boolean',
  
  // Collection types
  'List[T]': 'T[]',
  'Dict[K, V]': 'Record<K, V>',
  'Set[T]': 'Set<T>',
  'Tuple[T, U]': '[T, U]',
  
  // Optional and Union types
  'Optional[T]': 'T | null',
  'Union[A, B]': 'A | B',
  
  // Custom types
  'datetime': 'Date',
  'Enum': 'string',  // Enum values become string literals
};
```

#### TypeScript Interface Generation
```typescript
interface StateDefinition {
  interfaceName: string;
  fields: FieldDefinition[];
  imports: string[];
  extends: string[];  // Base interfaces to extend
  customTypes: CustomTypeDefinition[];
  enumDefinitions: EnumDefinition[];
}

interface FieldDefinition {
  name: string;
  type: string;
  optional: boolean;
  description?: string;
  defaultValue?: any;
  validation?: ValidationRule[];
}

interface CustomTypeDefinition {
  typeName: string;
  definition: string;
  sourceFile: string;
}

interface EnumDefinition {
  enumName: string;
  values: string[];
  sourceEnum: string;
}
```

#### Device State Hook Generation
```typescript
interface StateHookGenerator {
  generateDeviceStateHook(deviceId: string, stateType: string): GeneratedFile;
  generateStateHookInterface(deviceId: string): HookInterface;
  integrateWithQueryHooks(deviceId: string): QueryIntegration;
}

// Generated hook structure
interface DeviceStateHook {
  hookName: string;  // use{DeviceId}State
  returnType: string; // UseQueryResult<{StateType}>
  queryKey: string;   // Device-specific query key
  errorHandling: ErrorHandlingStrategy;
}
```

#### State-Component Integration
```typescript
interface ComponentStateIntegration {
  identifyStateFields(deviceStructure: DeviceStructure): StateFieldMapping[];
  generateStateBindings(structure: DeviceStructure): StateBinding[];
  createStateUpdateHandlers(structure: DeviceStructure): UpdateHandler[];
}

interface StateFieldMapping {
  stateField: string;
  uiComponent: string;
  bindingType: 'display' | 'input' | 'bidirectional';
  updateTrigger?: string;
}

interface StateBinding {
  componentId: string;
  stateProperty: string;
  transformFunction?: string;
  validationRule?: string;
}
```

---

## 3. Generation Layer

### 3.1 Component Generation

#### Template System
```typescript
interface ComponentTemplate {
  templateName: string;
  generateComponent(structure: DeviceStructure): string;
  generateImports(): string[];
  generateTypes(): string;
}

class DevicePageTemplate implements ComponentTemplate {
  generateComponent(structure: DeviceStructure): string {
    return `
    // Auto-generated from device config - DO NOT EDIT
    import React from 'react';
    ${this.generateImports()}
    
    function ${structure.deviceId}Page() {
      ${this.generateStateHooks(structure)}
      ${this.generateActionHandlers(structure)}
      
      return (
        <div className="p-6 space-y-6">
          ${this.generateHeader(structure)}
          ${this.generateSections(structure)}
        </div>
      );
    }
    
    export default ${structure.deviceId}Page;
    `;
  }
}
```

#### Component Generators
```typescript
// Specialized generators for each UI component type
class NavClusterGenerator {
  generate(actions: ProcessedAction[]): string;
  generateDirectionalButtons(actions: ProcessedAction[]): string;
  applyIconsToNavButtons(actions: ProcessedAction[]): string;
}

class ButtonGridGenerator {
  generate(actions: ProcessedAction[], layout: LayoutConfig): string;
  generateButtonWithIcon(action: ProcessedAction): string;
  resolveIconImport(icon: ActionIcon): string;
  generateIconComponent(icon: ActionIcon): string;
}

class SliderControlGenerator {
  generate(actions: ProcessedAction[]): string;
  generateSliderWithIcon(action: ProcessedAction): string;
}

class PointerPadGenerator {
  generate(actions: ProcessedAction[]): string;
}

// Icon integration for generated components
class IconIntegrationManager {
  generateIconImports(actions: ProcessedAction[]): string[];
  createIconComponents(icons: ActionIcon[]): IconComponent[];
  optimizeIconUsage(components: ComponentDefinition[]): IconOptimization;
  validateIconAvailability(icons: ActionIcon[]): IconValidationResult;
}

interface IconComponent {
  iconName: string;
  importStatement: string;
  componentUsage: string;
  library: 'heroicons' | 'lucide';
  variant?: string;
}

interface IconOptimization {
  uniqueIcons: ActionIcon[];
  duplicateIcons: string[];
  unusedIcons: string[];
  importStatements: string[];
}

interface IconValidationResult {
  validIcons: ActionIcon[];
  invalidIcons: ActionIcon[];
  suggestions: IconSuggestion[];
  fallbacksUsed: string[];
}

interface IconSuggestion {
  originalIcon: string;
  suggestedIcon: string;
  reason: string;
  library: 'heroicons' | 'lucide';
}

// Button generation with icon integration
interface ButtonComponentTemplate {
  generateButton(action: ProcessedAction): string;
  generateButtonWithIcon(action: ProcessedAction): string;
  generateIconImport(icon: ActionIcon): string;
  selectIconVariant(action: ProcessedAction, deviceClass: string): string;
}

// Example generated button component structure
const BUTTON_WITH_ICON_TEMPLATE = `
<Button
  variant="{variant}"
  size="{size}"
  onClick={() => handleAction('{actionName}', {parameters})}
  className="flex items-center gap-2"
>
  <{IconComponent} className="w-4 h-4" />
  {displayName}
</Button>
`;
```

### 3.2 File Output Management

#### Output Structure
```
src/pages/devices/
├── {device_id}.gen.tsx           # Device page components
├── index.gen.ts                  # Barrel exports
└── manifest.json                 # Device metadata

src/types/devices/
├── {DeviceClass}State.ts         # State interfaces
└── index.ts                      # Type exports

src/hooks/devices/
├── use{DeviceId}State.ts         # Device-specific hooks
└── index.ts                      # Hook exports
```

#### File Generation Pipeline
```typescript
interface FileGenerator {
  generateDevicePage(structure: DeviceStructure): GeneratedFile;
  generateIndexFiles(manifest: DeviceManifest): GeneratedFile[];
  generateRouterManifest(devices: DevicePageEntry[]): GeneratedFile;
  orchestrateFileGeneration(deviceStructure: DeviceStructure): FileGenerationResult;
}

interface GeneratedFile {
  filepath: string;
  content: string;
  dependencies: string[];
  checksum: string;
  generatedAt: Date;
  sourceHash: string; // Hash of source configuration
}

interface FileGenerationResult {
  devicePage: GeneratedFile;
  stateTypes: GeneratedFile;
  stateHook: GeneratedFile;
  indexUpdates: GeneratedFile[];
  manifestUpdate: GeneratedFile;
}
```

---

## 4. Integration Layer

### 4.1 Build System Integration

#### CLI Interface
```bash
node src/scripts/generate-device-pages.mjs \
  --api-base-url http://localhost:8000 \
  --device-id living_room_tv \
  --output-dir src/pages/devices \
  --state-file backend/devices/lg_tv_state.py \
  --state-class LgTvState \
  --param-ui-mode sliders
```

#### Batch Processing
```typescript
interface BatchProcessor {
  processAllDevices(config: BatchConfig): Promise<BatchResult>;
  processDeviceList(deviceIds: string[]): Promise<BatchResult>;
  validateOutputStructure(): Promise<ValidationResult>;
}
```

### 4.2 Version Control Strategy

#### Generated File Management
- Generated files marked with `.gen.` suffix
- Gitignore patterns for generated files
- Checksum-based change detection
- Incremental regeneration support

#### Change Detection
```typescript
interface ChangeDetector {
  detectConfigChanges(deviceId: string): Promise<boolean>;
  detectStateClassChanges(filePath: string): Promise<boolean>;
  requiresRegeneration(deviceId: string): Promise<boolean>;
}
```

### 4.3 Router Integration

#### Dynamic Route Registration
```typescript
// Router manifest integration
export interface DevicePageManifest {
  devices: DevicePageEntry[];
  generatedAt: string;
  apiVersion: string;
}

export interface DevicePageEntry {
  id: string;
  name: string;
  deviceClass: string;
  pagePath: string;
  statePath: string;
  hookPath: string;
}
```

---

## 5. Operations Layer

### 5.1 Unified Error Handling Strategy

#### Comprehensive Error Classification
```typescript
enum ErrorType {
  // Data Layer Errors
  API_CONNECTION = 'api_connection',
  API_VALIDATION = 'api_validation',
  API_TIMEOUT = 'api_timeout',
  API_RATE_LIMIT = 'api_rate_limit',
  
  // Processing Layer Errors  
  DEVICE_CLASS_UNSUPPORTED = 'device_class_unsupported',
  DEVICE_ANALYSIS_FAILURE = 'device_analysis_failure',
  TYPE_GENERATION_ERROR = 'type_generation_error',
  PYTHON_PARSING_ERROR = 'python_parsing_error',
  
  // Generation Layer Errors
  TEMPLATE_GENERATION_FAILURE = 'template_generation_failure',
  COMPONENT_GENERATION_ERROR = 'component_generation_error',
  FILE_WRITE_ERROR = 'file_write_error',
  DEPENDENCY_RESOLUTION_ERROR = 'dependency_resolution_error',
  
  // Integration Layer Errors
  BUILD_INTEGRATION_ERROR = 'build_integration_error',
  ROUTER_INTEGRATION_ERROR = 'router_integration_error',
  VERSION_CONTROL_ERROR = 'version_control_error',
  
  // Schema Change Errors (from Change Management)
  SCHEMA_COMPATIBILITY_ERROR = 'schema_compatibility_error',
  BREAKING_CHANGE_ERROR = 'breaking_change_error',
  REGENERATION_CONFLICT = 'regeneration_conflict'
}

interface GenerationError {
  type: ErrorType;
  deviceId?: string;
  message: string;
  details: unknown;
  recoverable: boolean;
  layer: 'data' | 'processing' | 'generation' | 'integration' | 'operations';
  timestamp: Date;
  context: ErrorContext;
}

interface ErrorContext {
  operation: string;
  deviceClass?: string;
  filePath?: string;
  apiEndpoint?: string;
  stackTrace?: string;
}
```

#### Unified Error Recovery Framework
```typescript
interface UnifiedErrorRecoveryStrategy {
  // Data Layer Recovery
  handleApiConnectionError(deviceId: string, context: ErrorContext): Promise<RecoveryResult>;
  handleApiValidationError(error: ValidationError, context: ErrorContext): Promise<RecoveryResult>;
  
  // Processing Layer Recovery
  handleUnsupportedDeviceClass(deviceId: string, deviceClass: string): Promise<RecoveryResult>;
  handleTypeGenerationError(error: TypeError, context: ErrorContext): Promise<RecoveryResult>;
  
  // Generation Layer Recovery
  handleTemplateGenerationFailure(deviceId: string, error: Error): Promise<RecoveryResult>;
  handleFileWriteError(filepath: string, error: Error): Promise<RecoveryResult>;
  
  // Integration Layer Recovery
  handleBuildIntegrationError(error: Error): Promise<RecoveryResult>;
  
  // Schema Change Recovery (consolidated from Change Management)
  handleSchemaBreakingChange(changeType: SchemaChangeType, error: Error): Promise<RecoveryResult>;
  
  // Generic Recovery Strategy
  attemptGenericRecovery(error: GenerationError): Promise<RecoveryResult>;
}

interface RecoveryResult {
  success: boolean;
  action: 'retry' | 'skip' | 'abort' | 'manual_intervention';
  message: string;
  retryAfter?: number;
  manualSteps?: string[];
}
```

#### Error Handling Flow
```typescript
interface ErrorHandlingOrchestrator {
  categorizeError(error: Error, context: ErrorContext): GenerationError;
  selectRecoveryStrategy(error: GenerationError): ErrorRecoveryStrategy;
  executeRecovery(error: GenerationError, strategy: ErrorRecoveryStrategy): Promise<RecoveryResult>;
  logError(error: GenerationError, recoveryResult: RecoveryResult): void;
  escalateToManual(error: GenerationError): void;
}
```

### 5.2 Performance Management

#### Caching Strategy
```typescript
interface GenerationCache {
  cacheDeviceConfig(deviceId: string, config: DeviceConfig): void;
  getCachedConfig(deviceId: string): DeviceConfig | null;
  invalidateCache(deviceId: string): void;
  shouldRegenerateFile(filepath: string): Promise<boolean>;
}
```

#### Performance Monitoring
```typescript
interface PerformanceMetrics {
  apiCallDuration: number;
  generationDuration: number;
  fileWriteDuration: number;
  totalDevicesProcessed: number;
  errorRate: number;
}
```

### 5.3 Monitoring & Observability

#### Generation Metrics
```typescript
interface GenerationMonitor {
  trackGenerationStart(deviceId: string): void;
  trackGenerationComplete(deviceId: string, metrics: PerformanceMetrics): void;
  trackGenerationError(deviceId: string, error: GenerationError): void;
  getGenerationReport(): GenerationReport;
}
```

---

## 6. Change Management Strategy

### 6.1 Schema Evolution Approach

#### Fail-Forward Philosophy
The system adopts a **fail-forward approach** with no backward compatibility:
- Schema changes require immediate script adjustments and regeneration
- No version compatibility layers or migration paths
- Simple linear workflow: Schema Change → Script Adjustment → Regenerate → Test → Deploy

#### Schema Change Response Workflow
```typescript
interface SchemaChangeWorkflow {
  detectSchemaChange(): Promise<SchemaChangeType>;
  updateGenerationScript(changeType: SchemaChangeType): Promise<void>;
  regenerateAffectedPages(deviceIds: string[]): Promise<GenerationResult>;
  validateGeneratedOutput(): Promise<ValidationResult>;
}

enum SchemaChangeType {
  API_ENDPOINT_CHANGE = 'api_endpoint_change',
  DEVICE_CONFIG_STRUCTURE = 'device_config_structure', 
  COMMAND_PARAMETER_CHANGE = 'command_parameter_change',
  NEW_DEVICE_CLASS = 'new_device_class'
}
```

#### Fail-Forward Principles
- **No rollback mechanisms** - iterate development cycle until successful
- Failed generations require immediate fix and retry
- System demands strict adherence to current schema version
- Eliminates complexity of maintaining multiple schema versions
- All errors handled through unified Operations Layer error handling

### 6.2 Breaking Change Management

#### Change Impact Assessment
```typescript
interface ChangeImpactAnalyzer {
  analyzeSchemaChange(oldSchema: Schema, newSchema: Schema): ChangeImpact;
  identifyAffectedDevices(changeImpact: ChangeImpact): string[];
  estimateRegenerationScope(deviceIds: string[]): RegenerationScope;
  integrateWithErrorHandling(changeImpact: ChangeImpact): ErrorHandlingPlan;
}

interface ChangeImpact {
  affectedEndpoints: string[];
  affectedDeviceClasses: string[];
  requiredScriptChanges: ScriptChange[];
  estimatedEffort: EffortLevel;
  potentialErrors: ErrorType[];  // Link to unified error handling
}
```

#### Mandatory Regeneration Rules
- Any API schema change triggers full affected device regeneration
- New device classes require handler implementation before generation
- Parameter type changes mandate immediate script updates
- No partial or incremental schema adoption
- All regeneration errors handled through Operations Layer unified error handling

---

## 7. Development Workflow Integration

### 7.1 Manual Generation Control

#### Trigger-Based Generation
- **No automatic generation** for unsupported devices
- Developer explicitly triggers generation per device
- Generation script validates device compatibility before proceeding
- Unsupported device classes fail with clear guidance

#### Generation Scope Control
```typescript
interface GenerationController {
  validateDeviceSupport(deviceId: string): Promise<SupportValidation>;
  triggerSingleDeviceGeneration(deviceId: string): Promise<GenerationResult>;
  listSupportedDeviceClasses(): DeviceClassInfo[];
  checkPrerequisites(deviceId: string): Promise<PrerequisiteCheck>;
}

interface SupportValidation {
  isSupported: boolean;
  deviceClass: string;
  missingRequirements: string[];
  supportLevel: 'FULL' | 'PARTIAL' | 'UNSUPPORTED';
}
```

### 7.2 Generated Files as Source Code

#### Hybrid Source Management
- **Generated files become part of source base** after generation
- Manual post-generation adjustments permitted (especially layout)
- Developers can tweak generated components as needed
- No automatic overwriting without explicit regeneration

#### Post-Generation Workflow
```typescript
interface PostGenerationWorkflow {
  generateInitialFiles(deviceId: string): Promise<GeneratedFile[]>;
  enableManualCustomization(files: GeneratedFile[]): void;
  trackCustomizations(filepath: string): CustomizationRecord;
  warnOnRegeneration(customizedFiles: string[]): void;
}

interface CustomizationRecord {
  filepath: string;
  customized: boolean;
  lastModified: Date;
  customizationAreas: string[];
}
```

### 7.3 Local Development Integration

#### Current Development Stack
- **Vite development server** for local development
- **Browser Tools MCP** for testing and debugging (already installed)
- Standard React development workflow continues unchanged
- Generated components integrate seamlessly with existing structure

#### Development Tools Integration
```typescript
interface DevelopmentTools {
  viteDevServer: {
    hotReload: boolean;
    supports: 'generated-components';
  };
  browserToolsMCP: {
    installed: true;
    capabilities: ['debugging', 'testing', 'performance-analysis'];
  };
  workflowIntegration: 'seamless';
}
```

---

## 8. Testing Strategy

### 8.1 Manual Testing Approach

#### Primary Testing Philosophy
- **Manual testing focus** for initial implementation
- Unit tests as later enhancement, not blocking requirement
- Integration and E2E testing through manual validation
- Pragmatic approach prioritizing working functionality over test coverage

#### Manual Testing Workflow
```typescript
interface ManualTestingWorkflow {
  generateDevicePage(deviceId: string): Promise<void>;
  performManualValidation(deviceId: string): Promise<ValidationChecklist>;
  testDeviceInteractions(deviceId: string): Promise<InteractionResults>;
  validateUIResponsiveness(deviceId: string): Promise<UIValidation>;
}
```

### 8.2 Validation Testing Framework

#### Generated Code Validation
```typescript
interface CodeValidationSuite {
  // TypeScript compilation validation
  validateTypeScriptCompilation(filePath: string): Promise<CompilationResult>;
  
  // Import resolution validation  
  validateImportResolution(filePath: string): Promise<ImportValidation>;
  
  // API contract validation
  validateAPIContractAlignment(deviceId: string): Promise<ContractValidation>;
  
  // Runtime rendering validation
  validateComponentRendering(componentPath: string): Promise<RenderValidation>;
}

interface CompilationResult {
  success: boolean;
  errors: TypeScriptError[];
  warnings: TypeScriptWarning[];
}

interface ImportValidation {
  allImportsResolved: boolean;
  missingImports: string[];
  circularDependencies: string[];
}

interface ContractValidation {
  actionsMatch: boolean;
  parametersAlign: boolean;
  missingActions: string[];
  unexpectedActions: string[];
}

interface RenderValidation {
  rendersWithoutCrash: boolean;
  hasRequiredElements: boolean;
  missingComponents: string[];
  renderErrors: RenderError[];
}
```

#### Validation Test Categories
1. **Compilation Validation**: Ensures TypeScript compiles without errors
2. **Import Validation**: Verifies all imports resolve correctly
3. **API Contract Validation**: Confirms generated actions match device API
4. **Runtime Validation**: Validates components render without crashing

### 8.3 Testing Integration Points

#### Browser Tools MCP Integration
```typescript
interface BrowserTestingIntegration {
  runAccessibilityAudit(devicePageUrl: string): Promise<AccessibilityResults>;
  runPerformanceAudit(devicePageUrl: string): Promise<PerformanceResults>;
  captureInteractionFlow(deviceId: string): Promise<InteractionCapture>;
  validateUIResponsiveness(deviceId: string): Promise<ResponsivenessReport>;
}
```

#### Manual Validation Checklist
- Device page loads without errors
- All UI components render correctly
- Device actions execute successfully
- State updates reflect in UI
- Error handling works as expected
- Layout adapts to different screen sizes

---

## 9. Implementation Phases & Milestones

### 9.1 Phase Structure Overview

#### Three-Phase Approach
Maximum 3 phases before first working device page generation:
- **Phase 1**: Core Infrastructure & Single Device Class
- **Phase 2**: Multi-Device Class Support & Validation
- **Phase 3**: Production Readiness & Documentation

#### Success Criteria Per Phase
Each phase delivers concrete progress toward first working device page:
- Phase 1: Generate working page for one device class
- Phase 2: Support all existing device classes  
- Phase 3: Production-ready system with full validation

### 9.2 Phase Breakdown

#### Phase 1: Core Infrastructure (Week 1-2)
**Deliverables:**
- Data Layer: API client and validation framework
- Processing Layer: Single device class handler (WirenboardIRDevice)
- Generation Layer: Basic component generation templates
- Working generation script for single device

**Milestone:** Generate functional page for one WirenboardIRDevice

#### Phase 2: Multi-Device Support (Week 3-4)  
**Deliverables:**
- Processing Layer: All device class handlers implemented
- Generation Layer: Specialized component generators
- Operations Layer: Error handling and performance monitoring
- Integration Layer: Batch processing capabilities

**Milestone:** Generate pages for all existing device types

#### Phase 3: Production Readiness (Week 5-6)
**Deliverables:**
- Integration Layer: Full build system integration
- Operations Layer: Complete monitoring and observability
- Testing Strategy: Validation framework implementation
- Documentation: Complete usage and maintenance guides

**Milestone:** Production-ready system with full feature set

### 9.3 Risk Mitigation

#### No Rollback Strategy
- **Full throttle ahead approach** - no rollback mechanisms needed
- No existing working system to protect
- Failed implementations require immediate fix and retry
- Focus on rapid iteration rather than cautious rollback planning

#### Phase Transition Criteria
```typescript
interface PhaseTransition {
  phase1Complete: {
    canGenerateSingleDevice: boolean;
    basicValidationPasses: boolean;
    coreInfrastructureWorks: boolean;
  };
  
  phase2Complete: {
    allDeviceClassesSupported: boolean;
    batchProcessingWorks: boolean;
    errorHandlingImplemented: boolean;
  };
  
  phase3Complete: {
    productionReadySystem: boolean;
    fullValidationSuite: boolean;
    documentationComplete: boolean;
  };
}
```

---

## 10. Cross-Cutting Concerns

### 10.1 Security & Validation Framework

#### Local Network Security Model
- **Environment**: Local network with strict router firewall
- **Threat Model**: Malformed configurations and code injection prevention
- **No Authentication**: Local network eliminates need for API authentication
- **Focus**: Code safety and input validation only

#### Input Sanitization & Validation
```typescript
interface ConfigurationSanitizer {
  sanitizeDeviceConfig(config: unknown): DeviceConfig;
  validateConfigurationStructure(config: unknown): ValidationResult;
  preventCodeInjection(userInput: string): string;
  sanitizeParameterValues(params: CommandParameter[]): CommandParameter[];
}

interface CodeSafetyValidator {
  validateGeneratedTypeScript(code: string): CodeSafetyResult;
  checkForUnsafePatterns(code: string): UnsafePattern[];
  validateImportPaths(imports: string[]): ImportValidationResult;
  ensureReactComponentSafety(componentCode: string): ComponentSafetyResult;
}

interface ValidationResult {
  isValid: boolean;
  sanitizedConfig: DeviceConfig;
  warningsRemoved: string[];
  errorsFound: ValidationError[];
}
```

#### Generated File Integrity
```typescript
interface FileIntegrityManager {
  generateChecksum(filePath: string): string;
  validateFileIntegrity(filePath: string, expectedChecksum: string): boolean;
  detectUnauthorizedChanges(generatedFiles: GeneratedFile[]): IntegrityReport;
  createIntegrityManifest(files: GeneratedFile[]): IntegrityManifest;
}

interface IntegrityManifest {
  files: FileIntegrityRecord[];
  generatedAt: Date;
  totalFiles: number;
  manifestChecksum: string;
}

interface FileIntegrityRecord {
  filepath: string;
  checksum: string;
  lastModified: Date;
  isGenerated: boolean;
  isModified: boolean;
}
```

### 10.2 Monitoring & Observability

#### Essential Metrics Collection
```typescript
interface BasicMetricsCollector {
  // Generation Performance
  trackGenerationDuration(deviceId: string, duration: number): void;
  trackGenerationSuccess(deviceId: string): void;
  trackGenerationFailure(deviceId: string, error: ErrorType): void;
  
  // System Health
  trackApiResponseTime(endpoint: string, duration: number): void;
  trackFileWriteOperations(successful: number, failed: number): void;
  
  // Basic Statistics
  getGenerationStats(): GenerationStats;
  getErrorRateByType(): ErrorRateReport;
}

interface GenerationStats {
  totalGenerations: number;
  successfulGenerations: number;
  failedGenerations: number;
  averageGenerationTime: number;
  lastGenerationTime: Date;
  deviceClassBreakdown: Record<string, number>;
}

interface ErrorRateReport {
  errorsByType: Record<ErrorType, number>;
  errorRate: number;
  mostCommonError: ErrorType;
  recentErrors: GenerationError[];
}
```

#### Simple Logging Framework
```typescript
interface BasicLogger {
  logGenerationStart(deviceId: string, deviceClass: string): void;
  logGenerationComplete(deviceId: string, duration: number): void;
  logGenerationError(deviceId: string, error: GenerationError): void;
  logApiCall(endpoint: string, duration: number, success: boolean): void;
  logFileOperation(operation: 'create' | 'update' | 'delete', filepath: string): void;
}

interface LogEntry {
  timestamp: Date;
  level: 'info' | 'warn' | 'error';
  operation: string;
  deviceId?: string;
  message: string;
  duration?: number;
  details?: Record<string, unknown>;
}
```

#### Basic Failure Detection
```typescript
interface FailureDetector {
  detectGenerationFailures(): FailureReport;
  detectApiConnectivityIssues(): ConnectivityReport;
  detectFileSystemIssues(): FileSystemReport;
  generateHealthReport(): SystemHealthReport;
}

interface FailureReport {
  recentFailures: GenerationError[];
  failurePattern: string | null;
  suggestedAction: string;
  requiresAttention: boolean;
}

interface SystemHealthReport {
  overallHealth: 'healthy' | 'degraded' | 'critical';
  lastSuccessfulGeneration: Date;
  consecutiveFailures: number;
  systemUptime: number;
  issues: HealthIssue[];
}
```

### 10.3 Maintenance & Lifecycle Management

#### Code Quality Assurance
```typescript
interface CodeQualityManager {
  lintGeneratedCode(filePath: string): LintResult;
  formatGeneratedCode(filePath: string): FormatResult;
  validateTypeScriptBestPractices(code: string): BestPracticesResult;
  enforceReactPatterns(componentCode: string): ReactPatternResult;
}

interface LintResult {
  hasErrors: boolean;
  hasWarnings: boolean;
  errors: LintError[];
  warnings: LintWarning[];
  fixableIssues: number;
  autoFixApplied: boolean;
}

interface BestPracticesResult {
  score: number; // 0-100
  violations: BestPracticeViolation[];
  recommendations: string[];
  criticalIssues: string[];
}
```

#### Technical Debt Prevention
```typescript
interface TechnicalDebtMonitor {
  analyzeGeneratedCode(files: GeneratedFile[]): TechnicalDebtReport;
  detectCodeDuplication(files: GeneratedFile[]): DuplicationReport;
  identifyComplexityIssues(code: string): ComplexityReport;
  preventDebtAccumulation(newFiles: GeneratedFile[]): DebtPreventionResult;
}

interface TechnicalDebtReport {
  overallDebtScore: number;
  highPriorityIssues: DebtIssue[];
  codeSmells: CodeSmell[];
  maintenanceRecommendations: string[];
  estimatedRefactoringEffort: number;
}

interface DebtIssue {
  type: 'duplication' | 'complexity' | 'naming' | 'structure';
  severity: 'low' | 'medium' | 'high' | 'critical';
  location: string;
  description: string;
  suggestedFix: string;
}
```

#### Documentation Lifecycle
```typescript
interface DocumentationManager {
  generateDeviceDocumentation(deviceStructure: DeviceStructure): GeneratedFile;
  updateSystemDocumentation(changes: SystemChange[]): DocumentationUpdate;
  maintainApiDocumentation(endpoints: ApiEndpoint[]): DocumentationMaintenance;
  generateUsageGuides(generatedComponents: GeneratedFile[]): UsageGuide[];
}

interface DocumentationUpdate {
  updatedFiles: string[];
  newSections: string[];
  removedSections: string[];
  changesApplied: DocumentationChange[];
}

interface UsageGuide {
  deviceId: string;
  deviceClass: string;
  componentPath: string;
  usageInstructions: string;
  exampleCode: string;
  integrationSteps: string[];
}
```

#### Automated Maintenance Tasks
```typescript
interface MaintenanceScheduler {
  scheduleCodeQualityChecks(interval: number): void;
  scheduleIntegrityVerification(interval: number): void;
  scheduleDocumentationUpdates(interval: number): void;
  scheduleDebtAssessment(interval: number): void;
  
  executeMaintenanceCycle(): MaintenanceReport;
}

interface MaintenanceReport {
  tasksExecuted: MaintenanceTask[];
  issuesFound: MaintenanceIssue[];
  actionsRequired: string[];
  nextScheduledMaintenance: Date;
  systemHealthAfterMaintenance: SystemHealthReport;
}

interface MaintenanceTask {
  taskType: 'quality_check' | 'integrity_verification' | 'documentation_update' | 'debt_assessment';
  executedAt: Date;
  duration: number;
  success: boolean;
  findings: string[];
}
```

---

## Script Interface

### Command Line Parameters
```bash
# Single device generation
node src/scripts/generate-device-pages.mjs \
  --device-id <device_id> \
  --api-base-url <url> \
  [--output-dir <path>] \
  [--state-file <path>] \
  [--state-class <class_name>] \
  [--param-ui-mode sliders|buttons] \
  [--force] \
  [--dry-run]

# Batch processing
node src/scripts/generate-device-pages.mjs \
  --batch \
  --config-file <batch_config.json> \
  [--parallel <number>]
``` 