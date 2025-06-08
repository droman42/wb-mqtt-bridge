import type { DeviceClassHandler, DeviceStructure, UISection, ProcessedAction, ComponentType } from '../../types/ProcessedDevice';
import type { DeviceConfig, DeviceGroups, DeviceGroup, GroupAction } from '../../types/DeviceConfig';
import { IconResolver } from '../IconResolver';

export class BroadlinkKitchenHoodHandler implements DeviceClassHandler {
  deviceClass = 'BroadlinkKitchenHood';
  private iconResolver = new IconResolver();
  
  analyzeStructure(config: DeviceConfig, groups: DeviceGroups): DeviceStructure {
    const uiSections = groups.groups.map(group => {
      const componentType = this.determineComponentType(group.actions);
      return {
        sectionId: group.group_id,
        sectionName: group.group_name,
        componentType,
        actions: this.processParameterActions(group.actions),
        layout: this.getLayoutForComponentType(componentType)
      };
    });
    
    return {
      deviceId: config.device_id,
      deviceName: config.device_name,
      deviceClass: config.device_class,
      uiSections,
      stateInterface: this.createKitchenHoodStateInterface(config),
      actionHandlers: this.createParameterAwareActionHandlers(config.commands)
    };
  }
  
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
  
  private formatDisplayName(actionName: string): string {
    return actionName
      .replace(/([a-z])([A-Z])/g, '$1 $2')
      .replace(/_/g, ' ')
      .split(' ')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
      .join(' ');
  }
  
  private getKitchenHoodIcon(actionName: string): import('../../types/ProcessedDevice').ActionIcon {
    const kitchenHoodMappings: Record<string, string> = {
      'power': 'PowerIcon',
      'fan': 'CubeTransparentIcon',
      'speed': 'ArrowTrendingUpIcon',
      'light': 'LightBulbIcon',
      'timer': 'ClockIcon',
      'filter': 'FunnelIcon',
      'turbo': 'BoltIcon',
      'mode': 'Cog6ToothIcon'
    };
    
    const cleanName = actionName.toLowerCase();
    for (const [key, iconName] of Object.entries(kitchenHoodMappings)) {
      if (cleanName.includes(key)) {
        return {
          iconLibrary: 'heroicons',
          iconName,
          iconVariant: 'outline',
          fallbackIcon: key,
          confidence: 0.9
        };
      }
    }
    
    return this.iconResolver.selectIconForAction(actionName);
  }
  
  private createKitchenHoodStateInterface(config: DeviceConfig): import('../../types/ProcessedDevice').StateDefinition {
    return {
      interfaceName: `${config.device_class}State`,
      fields: [
        {
          name: 'power',
          type: 'boolean',
          optional: true,
          description: 'Hood power state'
        },
        {
          name: 'fanSpeed',
          type: 'number',
          optional: true,
          description: 'Current fan speed level'
        },
        {
          name: 'lightState',
          type: 'boolean',
          optional: true,
          description: 'Light on/off state'
        },
        {
          name: 'timerRemaining',
          type: 'number',
          optional: true,
          description: 'Timer remaining in minutes'
        },
        {
          name: 'filterStatus',
          type: 'string',
          optional: true,
          description: 'Filter status indicator'
        },
        {
          name: 'lastAction',
          type: 'string',
          optional: true,
          description: 'Last executed action'
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
} 