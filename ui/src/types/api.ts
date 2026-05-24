// API Types - Extracted from OpenAPI generated models
// Clean TypeScript interfaces for our backend API

import { BaseDeviceState } from './BaseDeviceState';

// Device Related Types
export interface DeviceAction {
  action: string;
  params?: { [key: string]: any } | null;
}

// Moved LastCommand and BaseDeviceState to src/types/BaseDeviceState.ts
// Import them from there if needed: import { LastCommand, BaseDeviceState } from './BaseDeviceState';

export interface DeviceState {
  power?: boolean | null;
  input?: string | null;
  output?: string | null;
  extra?: { [key: string]: any };
}

export interface CommandResponse {
  success: boolean;
  device_id: string;
  action: string;
  state: BaseDeviceState;
  error?: string | null;
  mqtt_command?: { [key: string]: any } | null;
  data?: any | null;
}

// Room Related Types
export interface RoomDefinitionResponse {
  room_id: string;
  names: { [key: string]: string };
  description: string;
  devices: Array<string>;
  default_scenario?: string | null;
}

// Scenario Related Types
export interface CommandStep {
  device: string;
  command: string;
  params?: { [key: string]: any };
  condition?: string | null;
  delay_after_ms?: number;
}

export interface ManualInstructions {
  startup?: Array<string>;
  shutdown?: Array<string>;
}

export interface ScenarioDefinition {
  scenario_id: string;
  name: string;
  description?: string;
  room_id?: string | null;
  roles: { [key: string]: string };
  devices: Array<string>;
  startup_sequence: Array<CommandStep>;
  shutdown_sequence: Array<CommandStep>;
  manual_instructions?: ManualInstructions | null;
}

export interface ScenarioState {
  scenario_id: string;
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
  client_id: string;
  auth?: { [key: string]: string } | null;
  keepalive?: number;
}

// System Related Types
export interface SystemInfo {
  version?: string;
  mqttBroker: MQTTBrokerConfig;
  devices: Array<string>;
  scenarios: Array<string>;
  rooms: Array<string>;
}

export interface PersistenceConfig {
  db_path?: string;
}

export interface SystemConfig {
  mqtt_broker: MQTTBrokerConfig;
  web_service: { [key: string]: any };
  log_level: string;
  log_file: string;
  loggers?: { [key: string]: string } | null;
  devices?: { [key: string]: { [key: string]: any } | null } | null;
  persistence?: PersistenceConfig;
  device_directory?: string;
}

export interface ReloadResponse {
  status: string;
  message?: string | null;
  timestamp?: string;
}

export interface PersistedStatesResponse {
  [deviceId: string]: { [key: string]: any };
}