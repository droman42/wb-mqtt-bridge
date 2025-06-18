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
 * Handles snake_case field naming consistently and includes all device-specific fields
 */
export const mapBackendDataToState = (backendData: any): Partial<BaseDeviceState> => {
  const mapped: Partial<BaseDeviceState> = {};
  
  // Map all fields from backend data directly
  // This handles both base fields and device-specific fields
  for (const [key, value] of Object.entries(backendData)) {
    if (value !== undefined) {
      (mapped as any)[key] = value;
    }
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