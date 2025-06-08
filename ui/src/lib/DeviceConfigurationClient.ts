import type { DeviceConfig, DeviceGroups } from '../types/DeviceConfig';

export class DeviceConfigurationClient {
  constructor(private baseUrl: string) {}
  
  async fetchDeviceConfig(deviceId: string): Promise<DeviceConfig> {
    const response = await fetch(`${this.baseUrl}/config/device/${deviceId}`);
    if (!response.ok) {
      throw new Error(`API Error: ${response.status} - ${response.statusText}`);
    }
    return response.json();
  }
  
  async fetchDeviceGroups(deviceId: string): Promise<DeviceGroups> {
    const response = await fetch(`${this.baseUrl}/devices/${deviceId}/groups`);
    if (!response.ok) {
      throw new Error(`API Error: ${response.status} - ${response.statusText}`);
    }
    return response.json();
  }
  
  async validateConnectivity(): Promise<boolean> {
    try {
      const response = await fetch(`${this.baseUrl}/system`);
      return response.ok;
    } catch {
      return false;
    }
  }
} 