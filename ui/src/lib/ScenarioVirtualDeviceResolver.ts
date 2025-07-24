import * as fs from 'fs/promises';
import * as path from 'path';
import type { DeviceConfig, DeviceGroups, DeviceGroup } from '../types/DeviceConfig';

export interface ScenarioConfig {
  scenario_id: string;
  name: string;
  description: string;
  room_id: string;
  roles: Record<string, string>; // role -> device_id mapping
  devices: string[];
  startup_sequence: any[];
  shutdown_sequence: any[];
  manual_instructions?: {
    startup?: string[];
    shutdown?: string[];
  };
}

export interface ScenarioVirtualDeviceInfo {
  deviceId: string;
  deviceName: string;
  deviceClass: string;
  roles: Record<string, string>;
  enabledGroups: string[];
}

/**
 * Resolves scenario configurations into virtual device structures
 * Works in both local and CI modes by scanning scenario config files
 */
export class ScenarioVirtualDeviceResolver {
  
  constructor(private scenarioConfigPath: string) {}

  /**
   * Discover all scenario virtual devices from config files
   */
  async discoverScenarioDevices(): Promise<ScenarioVirtualDeviceInfo[]> {
    try {
      // Check if scenarios directory exists
      await fs.access(this.scenarioConfigPath);
    } catch {
      console.warn(`⚠️  Scenario config path not found: ${this.scenarioConfigPath}`);
      return [];
    }

    const devices: ScenarioVirtualDeviceInfo[] = [];

    try {
      const files = await fs.readdir(this.scenarioConfigPath);
      const jsonFiles = files.filter(file => file.endsWith('.json'));

      console.log(`🔍 Found ${jsonFiles.length} scenario config files in ${this.scenarioConfigPath}`);

      for (const file of jsonFiles) {
        try {
          const filePath = path.join(this.scenarioConfigPath, file);
          const scenarioConfig = await this.parseScenarioConfig(filePath);
          const deviceInfo = this.createVirtualDeviceInfo(scenarioConfig);
          devices.push(deviceInfo);
          console.log(`✅ Processed scenario: ${scenarioConfig.scenario_id} (${Object.keys(scenarioConfig.roles).length} roles)`);
        } catch (error) {
          const errorMessage = error instanceof Error ? error.message : String(error);
          console.warn(`⚠️  Failed to process scenario file ${file}: ${errorMessage}`);
        }
      }

      console.log(`📊 Discovered ${devices.length} scenario virtual devices`);
      return devices;

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      console.error(`❌ Failed to scan scenario directory: ${errorMessage}`);
      return [];
    }
  }

  /**
   * Generate a virtual device config for a specific scenario
   */
  async generateVirtualDeviceConfig(scenarioId: string): Promise<DeviceConfig> {
    const scenarioPath = path.join(this.scenarioConfigPath, `${scenarioId}.json`);
    
    try {
      const scenarioConfig = await this.parseScenarioConfig(scenarioPath);
      return this.createVirtualDeviceConfig(scenarioConfig);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      throw new Error(`Failed to generate virtual device config for scenario ${scenarioId}: ${errorMessage}`);
    }
  }

  /**
   * Generate virtual device groups with selective enablement
   */
  async generateVirtualDeviceGroups(scenarioId: string): Promise<DeviceGroups> {
    const scenarioPath = path.join(this.scenarioConfigPath, `${scenarioId}.json`);
    
    try {
      const scenarioConfig = await this.parseScenarioConfig(scenarioPath);
      return this.createVirtualDeviceGroups(scenarioConfig);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      throw new Error(`Failed to generate virtual device groups for scenario ${scenarioId}: ${errorMessage}`);
    }
  }

  private async parseScenarioConfig(filePath: string): Promise<ScenarioConfig> {
    const content = await fs.readFile(filePath, 'utf8');
    const config = JSON.parse(content) as ScenarioConfig;
    
    // Validate required fields
    if (!config.scenario_id || !config.name || !config.roles) {
      throw new Error(`Invalid scenario config: missing required fields`);
    }

    return config;
  }

  private createVirtualDeviceInfo(config: ScenarioConfig): ScenarioVirtualDeviceInfo {
    // Extract enabled groups from roles
    const enabledGroups = Object.keys(config.roles);
    
    return {
      deviceId: config.scenario_id,
      deviceName: config.name,
      deviceClass: 'ScenarioDevice',
      roles: config.roles,
      enabledGroups
    };
  }

  private createVirtualDeviceConfig(config: ScenarioConfig): DeviceConfig {
    // Create virtual device config with scenario control commands
    return {
      device_id: config.scenario_id,
      device_name: config.name,
      device_class: 'ScenarioDevice',
      config_class: 'ScenarioDeviceConfig',
      commands: {
        // Scenario power commands (always enabled)
        power_on: {
          action: 'start_scenario',
          location: 'scenario',
          description: `Start ${config.name}`,
          group: 'power',
          params: null
        },
        power_off: {
          action: 'stop_scenario',
          location: 'scenario', 
          description: `Stop ${config.name}`,
          group: 'power',
          params: null
        },
        
        // Virtual commands for role-mapped groups
        // These will be enabled/disabled based on roles
        ...this.generateRoleBasedCommands(config)
      }
    };
  }

  private generateRoleBasedCommands(config: ScenarioConfig): Record<string, any> {
    const commands: Record<string, any> = {};
    
    // Generate placeholder commands for each possible group
    // These will be enabled/disabled in the UI based on roles
    const standardGroups = ['volume', 'playback', 'navigation', 'tracks', 'menu', 'screen'];
    
    for (const group of standardGroups) {
      if (config.roles[group]) {
        // This group is enabled for this scenario
        const targetDevice = config.roles[group];
        
        // Add common commands for this group
        switch (group) {
          case 'volume':
            commands.volume_up = {
              action: 'volume_up',
              location: targetDevice,
              description: 'Volume Up',
              group: 'volume',
              params: null
            };
            commands.volume_down = {
              action: 'volume_down',
              location: targetDevice, 
              description: 'Volume Down',
              group: 'volume',
              params: null
            };
            commands.mute = {
              action: 'mute',
              location: targetDevice,
              description: 'Mute',
              group: 'volume',
              params: null
            };
            break;
            
          case 'playback':
            commands.play = {
              action: 'play',
              location: targetDevice,
              description: 'Play',
              group: 'playback',
              params: null
            };
            commands.pause = {
              action: 'pause',
              location: targetDevice,
              description: 'Pause', 
              group: 'playback',
              params: null
            };
            commands.stop = {
              action: 'stop',
              location: targetDevice,
              description: 'Stop',
              group: 'playback',
              params: null
            };
            break;
            
          case 'navigation':
            commands.up = {
              action: 'up',
              location: targetDevice,
              description: 'Up',
              group: 'navigation',
              params: null
            };
            commands.down = {
              action: 'down',
              location: targetDevice,
              description: 'Down',
              group: 'navigation',
              params: null
            };
            commands.left = {
              action: 'left',
              location: targetDevice,
              description: 'Left',
              group: 'navigation',
              params: null
            };
            commands.right = {
              action: 'right',
              location: targetDevice,
              description: 'Right',
              group: 'navigation',
              params: null
            };
            commands.ok = {
              action: 'ok',
              location: targetDevice,
              description: 'OK',
              group: 'navigation',
              params: null
            };
            break;
            
          case 'tracks':
            commands.next_track = {
              action: 'next_track',
              location: targetDevice,
              description: 'Next Track',
              group: 'tracks',
              params: null
            };
            commands.prev_track = {
              action: 'prev_track',
              location: targetDevice,
              description: 'Previous Track',
              group: 'tracks',
              params: null
            };
            break;
        }
      }
    }
    
    return commands;
  }

  private createVirtualDeviceGroups(config: ScenarioConfig): DeviceGroups {
    // Create standard group structure with selective enablement
    const enabledGroups = Object.keys(config.roles);
    const groups: DeviceGroup[] = [];
    
    // Always add power group
    groups.push({
      group_id: 'power',
      group_name: 'Power',
      actions: [
        {
          name: 'power_on',
          description: `Start ${config.name}`,
          params: null
        },
        {
          name: 'power_off',
          description: `Stop ${config.name}`,
          params: null
        }
      ],
      status: 'active'
    });
    
    // Add enabled groups based on roles
    if (enabledGroups.includes('volume')) {
      groups.push({
        group_id: 'volume',
        group_name: 'Volume',
        actions: [
          { name: 'volume_up', description: 'Volume Up', params: null },
          { name: 'volume_down', description: 'Volume Down', params: null },
          { name: 'mute', description: 'Mute', params: null }
        ],
        status: 'active'
      });
    }
    
    if (enabledGroups.includes('playback')) {
      groups.push({
        group_id: 'playback',
        group_name: 'Playback',
        actions: [
          { name: 'play', description: 'Play', params: null },
          { name: 'pause', description: 'Pause', params: null },
          { name: 'stop', description: 'Stop', params: null }
        ],
        status: 'active'
      });
    }
    
    if (enabledGroups.includes('navigation')) {
      groups.push({
        group_id: 'navigation',
        group_name: 'Navigation',
        actions: [
          { name: 'up', description: 'Up', params: null },
          { name: 'down', description: 'Down', params: null },
          { name: 'left', description: 'Left', params: null },
          { name: 'right', description: 'Right', params: null },
          { name: 'ok', description: 'OK', params: null }
        ],
        status: 'active'
      });
    }
    
    if (enabledGroups.includes('tracks')) {
      groups.push({
        group_id: 'tracks',
        group_name: 'Tracks',
        actions: [
          { name: 'next_track', description: 'Next Track', params: null },
          { name: 'prev_track', description: 'Previous Track', params: null }
        ],
        status: 'active'
      });
    }
    
    if (enabledGroups.includes('menu')) {
      groups.push({
        group_id: 'menu',
        group_name: 'Menu',
        actions: [
          { name: 'menu', description: 'Menu', params: null },
          { name: 'back', description: 'Back', params: null },
          { name: 'home', description: 'Home', params: null }
        ],
        status: 'active'
      });
    }
    
    if (enabledGroups.includes('screen')) {
      groups.push({
        group_id: 'screen',
        group_name: 'Screen',
        actions: [
          { name: 'aspect_ratio', description: 'Aspect Ratio', params: null },
          { name: 'zoom', description: 'Zoom', params: null }
        ],
        status: 'active'
      });
    }
    
    return {
      device_id: config.scenario_id,
      groups
    };
  }
} 