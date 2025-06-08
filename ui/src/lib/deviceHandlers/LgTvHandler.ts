import type { DeviceClassHandler, DeviceStructure, UISection, ProcessedAction, ComponentType } from '../../types/ProcessedDevice';
import type { DeviceConfig, DeviceGroups, DeviceGroup, GroupAction } from '../../types/DeviceConfig';
import { IconResolver } from '../IconResolver';

export class LgTvHandler implements DeviceClassHandler {
  deviceClass = 'LgTv';
  private iconResolver = new IconResolver();
  
  analyzeStructure(config: DeviceConfig, groups: DeviceGroups): DeviceStructure {
    const uiSections = groups.groups.map(group => {
      if (group.group_id === 'pointer' || this.isPointerGroup(group)) {
        return this.createPointerSection(group);
      }
      return this.createStandardSection(group);
    });
    
    return {
      deviceId: config.device_id,
      deviceName: config.device_name,
      deviceClass: config.device_class,
      uiSections,
      stateInterface: this.createLgTvStateInterface(config),
      actionHandlers: this.createActionHandlers(config.commands)
    };
  }
  
  private isPointerGroup(group: DeviceGroup): boolean {
    const pointerActions = ['move_cursor', 'click', 'drag', 'scroll'];
    return group.actions.some(action => 
      pointerActions.some(pointer => action.name.toLowerCase().includes(pointer))
    );
  }
  
  private createPointerSection(group: DeviceGroup): UISection {
    return {
      sectionId: 'pointer_control',
      sectionName: 'Pointer Control',
      componentType: 'PointerPad',
      actions: this.processPointerActions(group.actions),
      layout: { fullWidth: true }
    };
  }
  
  private createStandardSection(group: DeviceGroup): UISection {
    return {
      sectionId: group.group_id,
      sectionName: group.group_name,
      componentType: this.determineComponentType(group),
      actions: this.processGroupActions(group.actions),
      layout: { columns: 2, spacing: 'medium' }
    };
  }
  
  private determineComponentType(group: DeviceGroup): ComponentType {
    const directionalCommands = ['up', 'down', 'left', 'right', 'ok', 'enter'];
    const hasDirectional = group.actions.some(action => 
      directionalCommands.some(dir => action.name.toLowerCase().includes(dir))
    );
    return hasDirectional ? 'NavCluster' : 'ButtonGrid';
  }
  
  private processPointerActions(actions: GroupAction[]): ProcessedAction[] {
    return actions.map(action => ({
      actionName: action.name,
      displayName: this.formatPointerAction(action.name),
      description: action.description,
      parameters: action.params || [],
      group: 'pointer',
      icon: this.getPointerIcon(action.name),
      uiHints: { isPointerAction: true }
    }));
  }
  
  private processGroupActions(actions: GroupAction[]): ProcessedAction[] {
    return actions.map(action => ({
      actionName: action.name,
      displayName: this.formatDisplayName(action.name),
      description: action.description,
      parameters: action.params || [],
      group: 'default',
      icon: this.iconResolver.selectIconForAction(action.name),
      uiHints: { buttonSize: 'medium', buttonStyle: 'secondary' }
    }));
  }
  
  private formatPointerAction(actionName: string): string {
    const pointerMappings: Record<string, string> = {
      'move_cursor': 'Move Cursor',
      'click': 'Click',
      'double_click': 'Double Click',
      'right_click': 'Right Click',
      'drag': 'Drag',
      'scroll': 'Scroll'
    };
    
    return pointerMappings[actionName] || this.formatDisplayName(actionName);
  }
  
  private getPointerIcon(actionName: string): import('../../types/ProcessedDevice').ActionIcon {
    const pointerIconMappings: Record<string, string> = {
      'move_cursor': 'CursorArrowRaysIcon',
      'click': 'HandRaisedIcon',
      'double_click': 'HandRaisedIcon',
      'right_click': 'HandRaisedIcon',
      'drag': 'HandRaisedIcon',
      'scroll': 'ArrowsUpDownIcon'
    };
    
    const iconName = pointerIconMappings[actionName] || 'CursorArrowRaysIcon';
    
    return {
      iconLibrary: 'heroicons',
      iconName,
      iconVariant: 'outline',
      fallbackIcon: 'cursor',
      confidence: 0.9
    };
  }
  
  private formatDisplayName(actionName: string): string {
    return actionName
      .replace(/([a-z])([A-Z])/g, '$1 $2')
      .replace(/_/g, ' ')
      .split(' ')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
      .join(' ');
  }
  
  private createLgTvStateInterface(config: DeviceConfig): import('../../types/ProcessedDevice').StateDefinition {
    return {
      interfaceName: `${config.device_class}State`,
      fields: [
        {
          name: 'power',
          type: 'boolean',
          optional: true,
          description: 'TV power state'
        },
        {
          name: 'input',
          type: 'string',
          optional: true,
          description: 'Current input source'
        },
        {
          name: 'volume',
          type: 'number',
          optional: true,
          description: 'Current volume level'
        },
        {
          name: 'channel',
          type: 'number',
          optional: true,
          description: 'Current channel'
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
          action: { action: '${command.action}', params: payload } 
        });
      `,
      dependencies: ['useExecuteDeviceAction']
    }));
  }
} 