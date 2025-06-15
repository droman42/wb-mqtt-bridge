import type { DeviceClassHandler, DeviceStructure, UISection, ProcessedAction, ComponentType } from '../../types/ProcessedDevice';
import type { DeviceConfig, DeviceGroups, DeviceGroup, GroupAction } from '../../types/DeviceConfig';
import { IconResolver } from '../IconResolver';

export class WirenboardIRHandler implements DeviceClassHandler {
  deviceClass = 'WirenboardIRDevice';
  private iconResolver = new IconResolver();
  
  analyzeStructure(config: DeviceConfig, groups: DeviceGroups): DeviceStructure {
    return {
      deviceId: config.device_id,
      deviceName: config.device_name,
      deviceClass: config.device_class,
      uiSections: this.createUISections(groups),
      stateInterface: this.createBasicStateInterface(config),
      actionHandlers: this.createActionHandlers(config.commands)
    };
  }
  
  private createUISections(groups: DeviceGroups): UISection[] {
    return groups.groups.map(group => ({
      sectionId: group.group_id,
      sectionName: group.group_name,
      componentType: this.determineComponentType(group),
      actions: this.processGroupActions(group.actions),
      layout: { columns: 2, spacing: 'medium' }
    }));
  }
  
  private determineComponentType(group: DeviceGroup): ComponentType {
    // Menu groups should always use NavCluster for directional navigation
    const isMenuGroup = group.group_name.toLowerCase().includes('menu');
    if (isMenuGroup) {
      return 'NavCluster';
    }
    
    // Check if this is a volume-related group
    const isVolumeGroup = group.group_name.toLowerCase().includes('volume') || 
                         group.actions.some(action => action.name.toLowerCase().includes('volume'));
    
    if (isVolumeGroup) {
      // If any action has range parameters, use SliderControl
      const hasRangeParam = group.actions.some(action => 
        action.params?.some(param => param.type === 'range')
      );
      return hasRangeParam ? 'SliderControl' : 'ButtonGrid';
    }
    
    // For other groups, check for actual directional navigation
    const directionalCommands = ['up', 'down', 'left', 'right', 'ok', 'enter'];
    const hasDirectional = group.actions.some(action => 
      directionalCommands.some(dir => action.name.toLowerCase().includes(dir))
    );
    return hasDirectional ? 'NavCluster' : 'ButtonGrid';
  }
  
  private processGroupActions(actions: GroupAction[]): ProcessedAction[] {
    return actions.map(action => ({
      actionName: action.name,
      displayName: this.formatDisplayName(action.name),
      description: action.description,
      parameters: action.params || [],
      group: 'default',
      icon: this.iconResolver.selectIconForActionWithLibrary(action.name, 'material'),
      uiHints: { buttonSize: 'medium', buttonStyle: 'secondary' }
    }));
  }
  
  private formatDisplayName(actionName: string): string {
    // Convert snake_case or camelCase to Title Case
    return actionName
      .replace(/([a-z])([A-Z])/g, '$1 $2') // camelCase to spaces
      .replace(/_/g, ' ') // snake_case to spaces
      .split(' ')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
      .join(' ');
  }
  
  private createBasicStateInterface(config: DeviceConfig): import('../../types/ProcessedDevice').StateDefinition {
    return {
      interfaceName: `${config.device_class}State`,
      fields: [
        {
          name: 'power',
          type: 'boolean',
          optional: true,
          description: 'Device power state'
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
  
  private createActionHandlers(commands: Record<string, import('../../types/DeviceConfig').DeviceCommand>): import('../../types/ProcessedDevice').ActionHandler[] {
    return Object.entries(commands).map(([commandName, command]) => ({
      actionName: commandName,
      handlerCode: `
        executeAction.mutate({ 
          deviceId: '${command.topic.split('/')[0]}', 
          action: { name: '${command.action}', ...payload } 
        });
      `,
      dependencies: ['useExecuteDeviceAction']
    }));
  }
} 