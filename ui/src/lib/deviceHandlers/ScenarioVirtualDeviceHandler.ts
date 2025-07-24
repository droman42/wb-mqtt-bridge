import type { DeviceConfig, DeviceGroups } from '../../types/DeviceConfig';
import type { RemoteDeviceStructure } from '../../types/RemoteControlLayout';
import type { ProcessedAction, ActionIcon, ActionHandler } from '../../types/ProcessedDevice';
import { ZoneDetection } from '../ZoneDetection';

export class ScenarioVirtualDeviceHandler {
  public readonly deviceClass = 'ScenarioDevice';
  private zoneDetection = new ZoneDetection();

  analyzeStructure(config: DeviceConfig, groups: DeviceGroups): RemoteDeviceStructure {
    console.log(`🎮 [ScenarioDevice] Analyzing virtual device structure for ${config.device_id}`);

    // Process scenario device actions with selective enablement
    const allActions = this.processScenarioDeviceActions(config, groups);
    
    // Use zone detection to generate standard remote zones
    const remoteZones = this.zoneDetection.analyzeDeviceGroups(groups, allActions);

    // Apply selective enablement to zones based on available groups
    this.applySelectiveEnablement(remoteZones, groups);

    console.log(`🎯 [ScenarioDevice] Generated ${remoteZones.length} scenario control zones`);

    return {
      deviceId: config.device_id,
      deviceName: config.device_name,
      deviceClass: this.deviceClass,
      remoteZones,
      stateInterface: {
        interfaceName: `${config.device_id}ScenarioState`,
        fields: [
          {
            name: 'scenario_active',
            type: 'boolean',
            optional: false,
            description: 'Whether the scenario is currently active'
          },
          {
            name: 'last_scenario_action',
            type: 'string',
            optional: true,
            description: 'Last scenario action executed'
          }
        ],
        imports: ['BaseDeviceState'],
        extends: ['BaseDeviceState']
      },
      actionHandlers: this.createScenarioActionHandlers(config),
      specialCases: [{
        deviceClass: this.deviceClass,
        caseType: 'lg-tv-inputs-apps', // Reuse existing case type for scenario devices
        configuration: { 
          scenarioBased: true,
          powerGroupMapsToScenario: true,
          selectiveEnablement: true
        }
      }]
    };
  }

  private processScenarioDeviceActions(config: DeviceConfig, groups: DeviceGroups): ProcessedAction[] {
    const actions: ProcessedAction[] = [];

    // Add scenario power actions (mapped to start/stop)
    actions.push({
      actionName: 'power_on',
      displayName: 'Start Scenario',
      description: `Start ${config.device_name}`,
      parameters: [],
      group: 'power',
      icon: this.createIcon('PlayArrow'),
      uiHints: { buttonStyle: 'primary' }
    });

    actions.push({
      actionName: 'power_off',
      displayName: 'Stop Scenario',
      description: `Stop ${config.device_name}`,
      parameters: [],
      group: 'power',
      icon: this.createIcon('Stop'),
      uiHints: { buttonStyle: 'secondary' }
    });

    // Process commands from config (role-mapped device controls)
    Object.entries(config.commands || {}).forEach(([commandKey, command]) => {
      // Skip power commands as they're handled specially above
      if (commandKey === 'power_on' || commandKey === 'power_off') {
        return;
      }
      
      actions.push({
        actionName: commandKey,
        displayName: command.description || commandKey,
        description: command.description || `Control: ${commandKey}`,
        parameters: this.convertParamsToParameters(command.params || []),
        group: command.group || 'controls',
        icon: this.createIcon(this.getIconForGroup(command.group || 'controls')),
        uiHints: { hasParameters: !!(command.params && command.params.length > 0) }
      });
    });

    console.log(`📊 [ScenarioDevice] Processed ${actions.length} scenario device actions`);
    return actions;
  }

  private applySelectiveEnablement(remoteZones: any[], groups: DeviceGroups): void {
    // Get available group IDs from the device groups
    const availableGroups = new Set(groups.groups.map(group => group.group_id));
    
    console.log(`🔧 [ScenarioDevice] Available groups: ${Array.from(availableGroups).join(', ')}`);
    
    // Apply enablement to zones based on available groups
    remoteZones.forEach(zone => {
      if (zone.zoneId === 'power') {
        // Power zone always enabled for scenarios
        zone.enabled = true;
        console.log(`✅ [ScenarioDevice] Power zone enabled`);
      } else {
        // Other zones enabled only if corresponding group exists
        zone.enabled = availableGroups.has(zone.zoneId);
        const status = zone.enabled ? '✅' : '❌';
        console.log(`${status} [ScenarioDevice] Zone '${zone.zoneId}' ${zone.enabled ? 'enabled' : 'disabled'}`);
      }
    });
  }

  private getIconForGroup(group: string): string {
    const iconMap: Record<string, string> = {
      'power': 'PowerSettings',
      'volume': 'VolumeUp',
      'playback': 'PlayArrow',
      'navigation': 'Navigation',
      'tracks': 'Album',
      'menu': 'Menu',
      'screen': 'AspectRatio',
      'controls': 'Settings'
    };
    
    return iconMap[group] || 'Settings';
  }

  private createScenarioActionHandlers(config: DeviceConfig): ActionHandler[] {
    return [{
      actionName: 'scenario_activate',
      handlerCode: `executeDeviceAction(${JSON.stringify(config.device_id)}, 'scenario_activate')`,
      dependencies: ['executeDeviceAction']
    }];
  }

  private createIcon(iconName: string): ActionIcon {
    return {
      iconLibrary: 'material',
      iconName: iconName,
      iconVariant: 'filled',
      fallbackIcon: 'Settings',
      confidence: 0.8
    };
  }

  private convertParamsToParameters(params: any[]): any[] {
    return params.map(param => ({
      name: param.name || 'value',
      type: param.type || 'string',
      required: param.required || false,
      default: param.default,
      min: param.min,
      max: param.max,
      description: param.description || `Parameter: ${param.name}`
    }));
  }

  private mapCommandToComponent(command: any): 'button' | 'slider' | 'input' {
    if (command.params && command.params.length > 0) {
      const param = command.params[0];
      switch (param.type) {
        case 'range':
        case 'integer':
          return 'slider';
        case 'string':
          return 'input';
        default:
          return 'button';
      }
    }
    return 'button';
  }

  private extractScenarioControlActions(config: DeviceConfig): any[] {
    const actions: any[] = [];
    
    // Add standard scenario control actions
    actions.push({
      id: 'scenario_activate',
      name: 'Activate Scenario',
      description: 'Activate this virtual scenario',
      type: 'button',
      group: 'scenario-control',
      params: {},
      className: 'scenario-activate-btn',
      variant: 'default'
    });

    actions.push({
      id: 'scenario_deactivate',
      name: 'Deactivate Scenario',
      description: 'Deactivate this virtual scenario',
      type: 'button',
      group: 'scenario-control',
      params: {},
      className: 'scenario-deactivate-btn',
      variant: 'outline'
    });

    // Extract any scenario-specific commands from config
    Object.entries(config.commands || {}).forEach(([commandKey, command]) => {
      if (this.isScenarioControlCommand(commandKey, command)) {
        actions.push({
          id: commandKey,
          name: command.description || commandKey,
          description: command.description || `Virtual scenario command: ${commandKey}`,
          type: 'button',
          group: 'scenario-control',
          params: command.params || {},
          className: 'scenario-command-btn'
        });
      }
    });

    return actions;
  }

  private extractVirtualCommandActions(config: DeviceConfig): any[] {
    const actions: any[] = [];

    Object.entries(config.commands || {}).forEach(([commandKey, command]) => {
      if (this.isVirtualCommand(commandKey, command)) {
        actions.push({
          id: commandKey,
          name: command.description || commandKey,
          description: command.description || `Virtual command: ${commandKey}`,
          type: this.mapCommandType(command),
          group: 'virtual-commands',
          params: command.params || {},
          className: 'virtual-command-control'
        });
      }
    });

    return actions;
  }

  private extractStatusActions(config: DeviceConfig): any[] {
    const actions: any[] = [];

    // Add virtual device status display
    actions.push({
      id: 'scenario_status',
      name: 'Scenario Status',
      description: 'Current scenario activation status',
      type: 'display',
      group: 'status',
      params: {},
      className: 'scenario-status-display'
    });

    actions.push({
      id: 'virtual_controls_status',
      name: 'Virtual Controls Status',
      description: 'Status of virtual WB controls',
      type: 'display',
      group: 'status',
      params: {},
      className: 'virtual-controls-status-display'
    });

    // Extract status-related commands
    Object.entries(config.commands || {}).forEach(([commandKey, command]) => {
      if (this.isStatusCommand(commandKey, command)) {
        actions.push({
          id: commandKey,
          name: command.description || commandKey,
          description: command.description || `Status: ${commandKey}`,
          type: 'display',
          group: 'status',
          params: command.params || {},
          className: 'status-display-item'
        });
      }
    });

    return actions;
  }

  private hasVirtualCommands(config: DeviceConfig): boolean {
    return Object.entries(config.commands || {}).some(([key, command]) => 
      this.isVirtualCommand(key, command)
    );
  }

  private isScenarioControlCommand(key: string, command: any): boolean {
    const scenarioKeywords = ['scenario', 'activate', 'deactivate', 'switch', 'startup', 'shutdown'];
    const keyLower = key.toLowerCase();
    
    return scenarioKeywords.some(keyword => 
      keyLower.includes(keyword) || 
      (command.description && command.description.toLowerCase().includes(keyword))
    );
  }

  private isVirtualCommand(key: string, command: any): boolean {
    const virtualKeywords = ['virtual', 'wb_', 'control', 'set_', 'get_'];
    const keyLower = key.toLowerCase();
    
    return virtualKeywords.some(keyword => 
      keyLower.includes(keyword) || 
      (command.description && command.description.toLowerCase().includes(keyword))
    ) && !this.isScenarioControlCommand(key, command) && !this.isStatusCommand(key, command);
  }

  private isStatusCommand(key: string, command: any): boolean {
    const statusKeywords = ['status', 'state', 'get_', 'read_', 'check_'];
    const keyLower = key.toLowerCase();
    
    return statusKeywords.some(keyword => 
      keyLower.includes(keyword) || 
      (command.description && command.description.toLowerCase().includes(keyword))
    );
  }

  private mapCommandType(command: any): string {
    // Map command properties to UI component types
    if (command.params && command.params.length > 0) {
      const param = command.params[0];
      
      switch (param.type) {
        case 'range':
        case 'integer':
          return 'slider';
        case 'string':
          return 'input';
        default:
          return 'button';
      }
    }
    
    return 'button';
  }
} 