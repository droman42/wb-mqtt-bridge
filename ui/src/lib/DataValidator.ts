import type { DeviceConfig } from '../types/DeviceConfig';

export class DataValidator {
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