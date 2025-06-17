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

// Phase 1: Local Configuration Mode Support
import type { DeviceStateMapping } from '../types/DeviceConfig';
import * as fs from 'fs/promises';
import { readFileSync } from 'fs';

export interface IDeviceConfigurationClient {
  fetchDeviceConfig(deviceId: string): Promise<DeviceConfig>;
  fetchDeviceGroups(deviceId: string): Promise<DeviceGroups>;
  validateConnectivity(): Promise<boolean>;
}

/**
 * Local Device Configuration Client for Phase 1
 * Enables device page generation without REST API dependencies by using 
 * local device configuration files.
 */
export class LocalDeviceConfigurationClient implements IDeviceConfigurationClient {
  constructor(private mappingFile: string) {}
  
  async fetchDeviceConfig(deviceId: string): Promise<DeviceConfig> {
    try {
      const mapping = await this.loadMapping();
      const configPath = this.findConfigPathByDeviceId(mapping, deviceId);
      const data = await fs.readFile(configPath, 'utf8');
      const config = JSON.parse(data);
      
      // Validate that device_id matches what we're looking for
      if (config.device_id !== deviceId) {
        throw new Error(`Device ID mismatch: expected '${deviceId}', found '${config.device_id}' in ${configPath}`);
      }
      
      return config;
    } catch (error) {
      if (error.code === 'ENOENT') {
        throw new Error(`Device config file not found for device_id: ${deviceId}. Please check the mapping file: ${this.mappingFile}`);
      }
      throw error;
    }
  }
  
  async fetchDeviceGroups(deviceId: string): Promise<DeviceGroups> {
    const config = await this.fetchDeviceConfig(deviceId);
    const { deriveGroupsFromConfig } = await import('../types/DeviceConfig');
    return deriveGroupsFromConfig(config);
  }
  
  async validateConnectivity(): Promise<boolean> {
    try {
      // Check if mapping file exists
      await fs.access(this.mappingFile);
      return true;
    } catch {
      return false;
    }
  }
  
  private async loadMapping(): Promise<DeviceStateMapping> {
    try {
      const data = await fs.readFile(this.mappingFile, 'utf8');
      return JSON.parse(data);
    } catch (error) {
      throw new Error(`Failed to load mapping file ${this.mappingFile}: ${error.message}`);
    }
  }
  
  private findConfigPathByDeviceId(mapping: DeviceStateMapping, deviceId: string): string {
    // Search all deviceConfigs arrays for matching device_id
    for (const [_deviceClass, classInfo] of Object.entries(mapping)) {
      for (const configPath of classInfo.deviceConfigs) {
        try {
          const configData = JSON.parse(readFileSync(configPath, 'utf8'));
          if (configData.device_id === deviceId) {
            return configPath;
          }
        } catch (error) {
          // Skip invalid config files and continue searching
          console.warn(`Warning: Could not read config file ${configPath}: ${error.message}`);
          continue;
        }
      }
    }
    throw new Error(`Device config not found for device_id: ${deviceId}`);
  }
  
  /**
   * Get all device IDs from the mapping file for batch processing
   */
  async getAllDeviceIds(): Promise<string[]> {
    const mapping = await this.loadMapping();
    const deviceIds: string[] = [];
    
    for (const [_deviceClass, classInfo] of Object.entries(mapping)) {
      for (const configPath of classInfo.deviceConfigs) {
        try {
          const configData = JSON.parse(readFileSync(configPath, 'utf8'));
          if (configData.device_id) {
            deviceIds.push(configData.device_id);
          }
        } catch (error) {
          console.warn(`Warning: Could not read config file ${configPath}: ${error.message}`);
        }
      }
    }
    
    return deviceIds;
  }
  
  /**
   * Get all device IDs for a specific device class
   */
  async getDeviceIdsByClass(deviceClass: string): Promise<string[]> {
    const mapping = await this.loadMapping();
    const deviceIds: string[] = [];
    
    const classInfo = mapping[deviceClass];
    if (!classInfo) {
      throw new Error(`Device class not found: ${deviceClass}`);
    }
    
    for (const configPath of classInfo.deviceConfigs) {
      try {
        const configData = JSON.parse(readFileSync(configPath, 'utf8'));
        if (configData.device_id) {
          deviceIds.push(configData.device_id);
        }
      } catch (error) {
        console.warn(`Warning: Could not read config file ${configPath}: ${error.message}`);
      }
    }
    
    return deviceIds;
  }
} 