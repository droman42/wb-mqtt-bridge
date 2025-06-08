// API Types - Extracted from OpenAPI generated models
// Clean TypeScript interfaces for our backend API

// Device Related Types
export interface DeviceAction {
  action: string;
  params?: { [key: string]: any } | null;
}

export interface LastCommand {
  action: string;
  source: string;
  timestamp: string;
  params?: { [key: string]: any } | null;
}

export interface BaseDeviceState {
  deviceId: string;
  deviceName: string;
  lastCommand?: LastCommand | null;
  error?: string | null;
}

export interface DeviceState {
  power?: boolean | null;
  input?: string | null;
  output?: string | null;
  extra?: { [key: string]: any };
}

export interface CommandResponse {
  success: boolean;
  deviceId: string;
  action: string;
  state: BaseDeviceState;
  error?: string | null;
  mqttCommand?: { [key: string]: any } | null;
  data?: any | null;
}

// Room Related Types
export interface RoomDefinitionResponse {
  room_id: string;
  names: { [key: string]: string };
  description: string;
  devices: Array<string>;
  defaultScenario?: string | null;
}

// Scenario Related Types
export interface CommandStep {
  device: string;
  command: string;
  params?: { [key: string]: any };
  condition?: string | null;
  delayAfterMs?: number;
}

export interface ManualInstructions {
  startup?: Array<string>;
  shutdown?: Array<string>;
}

export interface ScenarioDefinition {
  scenarioId: string;
  name: string;
  description?: string;
  room_id?: string | null;
  roles: { [key: string]: string };
  devices: Array<string>;
  startupSequence: Array<CommandStep>;
  shutdownSequence: Array<CommandStep>;
  manualInstructions?: ManualInstructions | null;
}

export interface ScenarioState {
  scenarioId: string;
  devices?: { [key: string]: DeviceState };
}

export interface ScenarioResponse {
  status: string;
  message: string;
}

export interface SwitchScenarioRequest {
  id: string;
  graceful?: boolean;
}

export interface ActionRequest {
  role: string;
  command: string;
  params?: { [key: string]: any };
}

// Group Related Types
export interface Group {
  id: string;
  name: string;
}

export interface ActionGroup {
  groupId: string;
  groupName: string;
  actions: Array<{ [key: string]: any }>;
  status?: string;
}

export interface GroupActionsResponse {
  deviceId: string;
  groupId: string;
  groupName?: string | null;
  status: string;
  message?: string | null;
  actions?: Array<{ [key: string]: any }>;
}

export interface GroupedActionsResponse {
  deviceId: string;
  groups: Array<ActionGroup>;
  defaultIncluded?: boolean;
}

// MQTT Related Types
export interface MQTTMessage {
  topic: string;
  payload?: any | null;
  qos?: number;
  retain?: boolean;
}

export interface MQTTPublishResponse {
  success: boolean;
  message: string;
  topic: string;
  timestamp?: string;
  error?: string | null;
}

export interface MQTTBrokerConfig {
  host: string;
  port: number;
  clientId: string;
  auth?: { [key: string]: string } | null;
  keepalive?: number;
}

// System Related Types
export interface ServiceInfo {
  service: string;
  version: string;
  status: string;
}

export interface SystemInfo {
  version?: string;
  mqttBroker: MQTTBrokerConfig;
  devices: Array<string>;
}

export interface PersistenceConfig {
  dbPath?: string;
}

export interface SystemConfig {
  mqttBroker: MQTTBrokerConfig;
  webService: { [key: string]: any };
  logLevel: string;
  logFile: string;
  loggers?: { [key: string]: string } | null;
  devices?: { [key: string]: { [key: string]: any } | null } | null;
  groups?: { [key: string]: string };
  persistence?: PersistenceConfig;
  deviceDirectory?: string;
}

export interface ReloadResponse {
  status: string;
  message?: string | null;
  timestamp?: string;
}

// Error Related Types
export interface ErrorResponse {
  detail: string;
  errorCode?: string | null;
}

export interface ValidationErrorLocInner {
  // Can be string or number for array indices
}

export interface ValidationError {
  loc: Array<ValidationErrorLocInner>;
  msg: string;
  type: string;
}

export interface HTTPValidationError {
  detail?: Array<ValidationError>;
} 