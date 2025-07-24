import type { DeviceConfig, DeviceGroups } from '../types/DeviceConfig';

export class DeviceConfigurationClient {
  constructor(private baseUrl: string) {}
  
  async fetchDeviceConfig(deviceId: string): Promise<DeviceConfig> {
    const response = await fetch(`${this.baseUrl}/config/device/${deviceId}`);
    if (!response.ok) {
      throw new Error(`API Error: ${response.status} - ${response.statusText}`);
    }
    return await response.json() as DeviceConfig;
  }
  
  async fetchDeviceGroups(deviceId: string): Promise<DeviceGroups> {
    const response = await fetch(`${this.baseUrl}/devices/${deviceId}/groups`);
    if (!response.ok) {
      throw new Error(`API Error: ${response.status} - ${response.statusText}`);
    }
    return await response.json() as DeviceGroups;
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
import { ScenarioVirtualDeviceResolver } from './ScenarioVirtualDeviceResolver';

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
      
      // Check if this is a scenario virtual device
      const scenarioDevice = await this.checkForScenarioDevice(mapping, deviceId);
      if (scenarioDevice) {
        return scenarioDevice;
      }
      
      const configPath = this.findConfigPathByDeviceId(mapping, deviceId);
      const data = await fs.readFile(configPath, 'utf8');
      const config = JSON.parse(data);
      
      // Validate that device_id matches what we're looking for
      if (config.device_id !== deviceId) {
        throw new Error(`Device ID mismatch: expected '${deviceId}', found '${config.device_id}' in ${configPath}`);
      }
      
      return config;
    } catch (error) {
      if (error && typeof error === 'object' && 'code' in error && error.code === 'ENOENT') {
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
      const errorMessage = error instanceof Error ? error.message : String(error);
      throw new Error(`Failed to load mapping file ${this.mappingFile}: ${errorMessage}`);
    }
  }
  
  private findConfigPathByDeviceId(mapping: DeviceStateMapping, deviceId: string): string {
    // Search all deviceConfigs arrays for matching device_id
          for (const [_deviceClass, classInfo] of Object.entries(mapping)) {
        // Skip device classes without deviceConfigs
        if (!classInfo.deviceConfigs || !Array.isArray(classInfo.deviceConfigs)) {
          continue;
        }
      
      for (const configPath of classInfo.deviceConfigs) {
        try {
          const configData = JSON.parse(readFileSync(configPath, 'utf8'));
          if (configData.device_id === deviceId) {
            return configPath;
          }
        } catch (error) {
          // Skip invalid config files and continue searching
          console.warn(`Warning: Could not read config file ${configPath}: ${error instanceof Error ? error.message : String(error)}`);
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
    
    for (const [deviceClass, classInfo] of Object.entries(mapping)) {
      // Handle scenario virtual devices
      if (classInfo.resolverType === 'scenario_virtual_device' && classInfo.scenarioConfigPath) {
        try {
          const scenarioIds = await this.getScenarioDeviceIds(classInfo.scenarioConfigPath);
          deviceIds.push(...scenarioIds);
          console.log(`📊 Found ${scenarioIds.length} scenario virtual devices for ${deviceClass}`);
          continue;
        } catch (error) {
          console.warn(`Warning: Could not load scenario devices for ${deviceClass}: ${error instanceof Error ? error.message : String(error)}`);
          continue;
        }
      }
      
      // Handle regular devices with deviceConfigs
      if (!classInfo.deviceConfigs || !Array.isArray(classInfo.deviceConfigs)) {
        console.warn(`Warning: Device class ${deviceClass} has no deviceConfigs array, skipping...`);
        continue;
      }
      
      for (const configPath of classInfo.deviceConfigs) {
        try {
          const configData = JSON.parse(readFileSync(configPath, 'utf8'));
          if (configData.device_id) {
            deviceIds.push(configData.device_id);
          }
        } catch (error) {
          console.warn(`Warning: Could not read config file ${configPath}: ${error instanceof Error ? error.message : String(error)}`);
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
    
    // Check if deviceConfigs exists (not all device classes have this, e.g., scenario devices)
    if (!classInfo.deviceConfigs) {
      console.warn(`Device class ${deviceClass} has no deviceConfigs array`);
      return deviceIds;
    }
    
    for (const configPath of classInfo.deviceConfigs) {
      try {
        const configData = JSON.parse(readFileSync(configPath, 'utf8'));
        if (configData.device_id) {
          deviceIds.push(configData.device_id);
        }
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        console.warn(`Warning: Could not read config file ${configPath}: ${errorMessage}`);
      }
    }
    
    return deviceIds;
  }

  /**
   * Check if a device ID corresponds to a scenario virtual device
   */
  private async checkForScenarioDevice(mapping: DeviceStateMapping, deviceId: string): Promise<DeviceConfig | null> {
    for (const [_deviceClass, classInfo] of Object.entries(mapping)) {
      if (classInfo.resolverType === 'scenario_virtual_device' && classInfo.scenarioConfigPath) {
        try {
          const resolver = new ScenarioVirtualDeviceResolver(classInfo.scenarioConfigPath);
          const scenarioDeviceConfig = await resolver.generateVirtualDeviceConfig(deviceId);
          return scenarioDeviceConfig;
        } catch (error) {
          // Not a scenario device with this ID, continue searching
          continue;
        }
      }
    }
    return null;
  }

  /**
   * Get scenario device IDs from scenario config path
   */
  private async getScenarioDeviceIds(scenarioConfigPath: string): Promise<string[]> {
    const resolver = new ScenarioVirtualDeviceResolver(scenarioConfigPath);
    const scenarioDevices = await resolver.discoverScenarioDevices();
    return scenarioDevices.map(device => device.deviceId);
  }
} 