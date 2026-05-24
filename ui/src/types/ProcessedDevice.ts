// ACTIVE INTERFACES - Used in the remote control system

export interface ProcessedAction {
  actionName: string;
  displayName: string;
  description: string;
  parameters: ProcessedParameter[];
  group: string;
  icon: ActionIcon;
  uiHints: UIHints;
  sourceDeviceId?: string; // For scenario inherited actions - which device to actually send the HTTP request to
  params?: Record<string, any>; // fixed native params the UI always sends (e.g. { zone: 2 }) — Layer 3
}

export interface ProcessedParameter {
  name: string;
  type: 'range' | 'string' | 'integer' | 'boolean';
  required: boolean;
  default?: any;
  min?: number | null;
  max?: number | null;
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