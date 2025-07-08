import type { DeviceClassHandler, ProcessedAction, ComponentType } from '../../types/ProcessedDevice';
import type { DeviceConfig, DeviceGroups, GroupAction } from '../../types/DeviceConfig';
import type { RemoteDeviceStructure } from '../../types/RemoteControlLayout';
import { IconResolver } from '../IconResolver';
import { ZoneDetection } from '../ZoneDetection';

export class BroadlinkKitchenHoodHandler implements DeviceClassHandler {
  deviceClass = 'BroadlinkKitchenHood';
  private iconResolver = new IconResolver();
  private zoneDetection = new ZoneDetection();
  
  analyzeStructure(config: DeviceConfig, groups: DeviceGroups): RemoteDeviceStructure {
    console.log(`🏠 [BroadlinkKitchenHood] Analyzing structure for ${config.device_id}`);
    
    // Generate remote control structure directly
    const remoteStructure = this.generateRemoteStructure(config, groups);
    
    console.log(`✅ [BroadlinkKitchenHood] Generated remote control structure with ${remoteStructure.remoteZones.length} zones`);
    return remoteStructure;
  }

  /**
   * Phase 4: Generate Remote Control Structure for Kitchen Hood
   * Maps kitchen hood controls to remote control zones
   */
  private generateRemoteStructure(config: DeviceConfig, groups: DeviceGroups): RemoteDeviceStructure {
    try {
      // Process all actions first
      const allActions = this.processAllGroupActions(groups);
      
      console.log(`🔍 [KitchenHood] Starting zone detection with ${allActions.length} actions`);
      const remoteZones = this.zoneDetection.analyzeDeviceGroups(groups, allActions);
      console.log(`🎯 [KitchenHood] Generated ${remoteZones.length} remote control zones`);

      return {
        deviceId: config.device_id,
        deviceName: config.device_name,
        deviceClass: config.device_class,
        remoteZones: remoteZones,
        stateInterface: this.createKitchenHoodStateInterface(config),
        actionHandlers: this.createParameterAwareActionHandlers(config.commands),
        specialCases: [{
          deviceClass: 'BroadlinkKitchenHood',
          caseType: 'kitchen-hood-controls',
          configuration: {
            hasFanSpeedSlider: true,
            hasLightControls: true,
            hasParameterizedActions: true
          }
        }]
      };
    } catch (error) {
      console.error('❌ [KitchenHood] Error generating remote structure:', error);
      throw error;
    }
  }

  /**
   * Process all group actions into ProcessedAction format
   */
  private processAllGroupActions(groups: DeviceGroups): ProcessedAction[] {
    if (!groups.groups) {
      console.log('⚠️  [KitchenHood] No groups found in device groups');
      return [];
    }
    
    const allActions: ProcessedAction[] = [];
    
    for (const group of groups.groups) {
      if (!group.actions) {
        console.log(`⚠️  [KitchenHood] No actions found in group: ${group.group_name}`);
        continue;
      }
      const groupActions = this.processParameterActions(group.actions);
      allActions.push(...groupActions);
    }
    
    console.log(`📊 [KitchenHood] Processed ${allActions.length} total actions from ${groups.groups.length} groups`);
    return allActions;
  }
  
  private processParameterActions(actions: GroupAction[]): ProcessedAction[] {
    return actions.map(action => ({
      actionName: action.name,
      displayName: this.formatDisplayName(action.name),
      description: action.description,
      parameters: this.processParameters(action.params || []),
      group: 'default',
      icon: this.getKitchenHoodIcon(action.name),
      uiHints: { 
        buttonSize: 'medium', 
        buttonStyle: 'secondary',
        hasParameters: (action.params?.length || 0) > 0
      }
    }));
  }
  
  private processParameters(params: import('../../types/DeviceConfig').CommandParameter[]): import('../../types/ProcessedDevice').ProcessedParameter[] {
    return params.map(param => ({
      name: param.name,
      type: param.type,
      required: param.required,
      default: param.default,
      min: param.min,
      max: param.max,
      description: param.description
    }));
  }
  
  private formatDisplayName(actionName: string): string {
    return actionName
      .replace(/([a-z])([A-Z])/g, '$1 $2')
      .replace(/_/g, ' ')
      .split(' ')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
      .join(' ');
  }
  
  private getKitchenHoodIcon(actionName: string): import('../../types/ProcessedDevice').ActionIcon {
    // For power actions, use IconResolver to get custom icons when available
    const cleanName = actionName.toLowerCase();
    if (cleanName.includes('power')) {
      return this.iconResolver.selectIconForAction(actionName);
    }
    
    const kitchenHoodMappings: Record<string, string> = {
      'fan': 'Toys',
      'speed': 'Speed',
      'light': 'Lightbulb',
      'timer': 'Timer',
      'filter': 'FilterAlt',
      'turbo': 'FlashOn',
      'mode': 'Settings'
    };
    
    for (const [key, iconName] of Object.entries(kitchenHoodMappings)) {
      if (cleanName.includes(key)) {
        return {
          iconLibrary: 'material',
          iconName,
          iconVariant: 'outlined',
          fallbackIcon: key,
          confidence: 0.9
        };
      }
    }
    
    return this.iconResolver.selectIconForActionWithLibrary(actionName, 'material');
  }
  
  private createKitchenHoodStateInterface(config: DeviceConfig): import('../../types/ProcessedDevice').StateDefinition {
    return {
      interfaceName: `${config.device_class}State`,
      fields: [
        {
          name: 'light',
          type: 'string',
          optional: false,
          description: 'Kitchen hood light state'
        },
        {
          name: 'speed',
          type: 'number',
          optional: false,
          description: 'Fan speed level'
        },
        {
          name: 'connection_status',
          type: 'string',
          optional: false,
          description: 'Device connection status'
        }
      ],
      imports: ['BaseDeviceState'],
      extends: ['BaseDeviceState']
    };
  }
  
  private createParameterAwareActionHandlers(commands: Record<string, import('../../types/DeviceConfig').DeviceCommand>): import('../../types/ProcessedDevice').ActionHandler[] {
    return Object.entries(commands).map(([commandName, command]) => ({
      actionName: commandName,
      handlerCode: `
        executeAction.mutate({ 
          deviceId: '${command.topic.split('/')[0]}', 
          action: { action: '${command.action}', params: payload } 
        });
      `,
      dependencies: ['useExecuteDeviceAction']
    }));
  }

  // Legacy methods maintained for backward compatibility during transition
  private determineComponentType(actions: GroupAction[]): ComponentType {
    const hasRangeParams = actions.some(action => 
      action.params?.some(param => param.type === 'range')
    );
    
    // Check for fan speed controls specifically
    const hasFanSpeed = actions.some(action => 
      action.name.toLowerCase().includes('speed') ||
      action.name.toLowerCase().includes('fan')
    );
    
    if (hasRangeParams || hasFanSpeed) {
      return 'SliderControl';
    }
    
    return 'ButtonGrid';
  }

  private getLayoutForComponentType(componentType: ComponentType): import('../../types/ProcessedDevice').LayoutConfig {
    switch (componentType) {
      case 'SliderControl':
        return { columns: 1, spacing: 'large' };
      case 'ButtonGrid':
        return { columns: 2, spacing: 'medium' };
      default:
        return { columns: 2, spacing: 'medium' };
    }
  }
} 