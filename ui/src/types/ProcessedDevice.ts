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

export interface ProcessedParameter {
  name: string;
  type: 'range' | 'string' | 'integer';
  required: boolean;
  default: any;
  min: number | null;
  max: number | null;
  description: string;
}

export interface ActionIcon {
  iconLibrary: 'material' | 'custom' | 'fallback';
  iconName: string;
  iconVariant?: 'filled' | 'outlined' | 'rounded' | 'sharp' | 'two-tone';
  fallbackIcon: string;
  confidence: number;
}

export interface UIHints {
  buttonSize?: 'small' | 'medium' | 'large';
  buttonStyle?: 'primary' | 'secondary' | 'destructive';
  isPointerAction?: boolean;
  hasParameters?: boolean;
  zoneNumber?: number;
}

export interface LayoutConfig {
  columns?: number;
  spacing?: 'small' | 'medium' | 'large';
  fullWidth?: boolean;
  zoneNumber?: number;
}

export interface StateDefinition {
  interfaceName: string;
  fields: StateField[];
  imports: string[];
  extends: string[];
}

export interface StateField {
  name: string;
  type: string;
  optional: boolean;
  description: string;
}

export interface ActionHandler {
  actionName: string;
  handlerCode: string;
  dependencies: string[];
}

export type ComponentType = 'ButtonGrid' | 'NavCluster' | 'SliderControl' | 'PointerPad';

export interface DeviceClassHandler {
  deviceClass: string;
  analyzeStructure(config: import('./DeviceConfig').DeviceConfig, groups: import('./DeviceConfig').DeviceGroups): DeviceStructure;
} 