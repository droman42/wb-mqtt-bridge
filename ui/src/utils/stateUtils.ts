import { BaseDeviceState } from '../types/BaseDeviceState';

/**
 * Creates a default state object for a device, ensuring all required BaseDeviceState fields are present
 */
export const createDefaultDeviceState = <T extends BaseDeviceState>(
  deviceId: string,
  additionalFields: Partial<Omit<T, keyof BaseDeviceState>> = {}
): T => {
  const baseState: BaseDeviceState = {
    deviceId,
    deviceName: '',
    lastCommand: null,
    error: null,
    isConnected: false,
    lastUpdated: null,
  };

  return { ...baseState, ...additionalFields } as T;
};

/**
 * Maps backend response data to frontend state format
 * Handles both snake_case (backend) and camelCase (frontend) field naming
 */
export const mapBackendDataToState = (backendData: any): Partial<BaseDeviceState> => {
  const mapped: Partial<BaseDeviceState> = {};
  
  // Map backend field names to frontend field names (snake_case -> camelCase)
  if (backendData.device_id !== undefined) {
    mapped.deviceId = backendData.device_id;
  }
  if (backendData.device_name !== undefined) {
    mapped.deviceName = backendData.device_name;
  }
  if (backendData.last_command !== undefined) {
    mapped.lastCommand = backendData.last_command;
  }
  if (backendData.error !== undefined) {
    mapped.error = backendData.error;
  }
  
  // Direct mappings (already in correct camelCase format)
  if (backendData.deviceId !== undefined) {
    mapped.deviceId = backendData.deviceId;
  }
  if (backendData.deviceName !== undefined) {
    mapped.deviceName = backendData.deviceName;
  }
  if (backendData.lastCommand !== undefined) {
    mapped.lastCommand = backendData.lastCommand;
  }
  
  return mapped;
};

/**
 * Updates state with automatic lastUpdated timestamp
 */
export const createStateUpdate = <T extends BaseDeviceState>(
  currentState: T,
  updates: Partial<T>
): T => {
  return {
    ...currentState,
    ...updates,
    lastUpdated: new Date(),
  };
}; 