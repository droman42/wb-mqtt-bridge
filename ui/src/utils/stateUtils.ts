import { BaseDeviceState } from '../types/BaseDeviceState';

/**
 * Creates a default state object for a device, ensuring all required BaseDeviceState fields are present
 */
export const createDefaultDeviceState = <T extends BaseDeviceState>(
  deviceId: string,
  additionalFields: Partial<Omit<T, keyof BaseDeviceState>> = {}
): T => {
  const baseState: BaseDeviceState = {
    device_id: deviceId,
    device_name: '',
    last_command: null,
    error: null,
  };

  return { ...baseState, ...additionalFields } as T;
};

/**
 * Maps backend response data to frontend state format
 * Handles snake_case field naming consistently
 */
export const mapBackendDataToState = (backendData: any): Partial<BaseDeviceState> => {
  const mapped: Partial<BaseDeviceState> = {};
  
  // Map backend field names (snake_case format)
  if (backendData.device_id !== undefined) {
    mapped.device_id = backendData.device_id;
  }
  if (backendData.device_name !== undefined) {
    mapped.device_name = backendData.device_name;
  }
  if (backendData.last_command !== undefined) {
    mapped.last_command = backendData.last_command;
  }
  if (backendData.error !== undefined) {
    mapped.error = backendData.error;
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
  };
}; 