import type { DeviceClassHandler, ProcessedAction, ComponentType } from '../../types/ProcessedDevice';
import type { DeviceConfig, DeviceGroups, DeviceGroup, GroupAction } from '../../types/DeviceConfig';
import type { RemoteDeviceStructure } from '../../types/RemoteControlLayout';
import { IconResolver } from '../IconResolver';
import { ZoneDetection } from '../ZoneDetection';

export class LgTvHandler implements DeviceClassHandler {
  deviceClass = 'LgTv';
  private iconResolver = new IconResolver();
  private zoneDetection = new ZoneDetection();
  
  analyzeStructure(config: DeviceConfig, groups: DeviceGroups): RemoteDeviceStructure {
    console.log(`📺 [LgTv] Analyzing structure for ${config.device_id}`);
    
    // Generate remote control structure directly
    const remoteStructure = this.generateRemoteStructure(config, groups);
    
    console.log(`✅ [LgTv] Generated remote control structure with ${remoteStructure.remoteZones.length} zones`);
    return remoteStructure;
  }

  /**
   * Phase 4: Generate Remote Control Structure for LG TV
   * Maps TV controls to remote control zones
   */
  private generateRemoteStructure(config: DeviceConfig, groups: DeviceGroups): RemoteDeviceStructure {
    try {
      // Process all actions first
      const allActions = this.processAllGroupActions(groups);
      
      console.log(`🔍 [LgTv] Starting zone detection with ${allActions.length} actions`);
      const remoteZones = this.zoneDetection.analyzeDeviceGroups(groups, allActions);
      console.log(`🎯 [LgTv] Generated ${remoteZones.length} remote control zones`);

      return {
        deviceId: config.device_id,
        deviceName: config.device_name,
        deviceClass: config.device_class,
        remoteZones: remoteZones,
        stateInterface: this.createLgTvStateInterface(config),
        actionHandlers: this.createActionHandlers(config.commands, config.device_id),
        specialCases: [{
          deviceClass: 'LgTv',
          caseType: 'lg-tv-inputs-apps',
          configuration: {
            usesInputsAPI: true,
            usesAppsAPI: true,
            hasPointerControl: true
          }
        }]
      };
    } catch (error) {
      console.error('❌ [LgTv] Error generating remote structure:', error);
      throw error;
    }
  }

  /**
   * Process all group actions into ProcessedAction format
   */
  private processAllGroupActions(groups: DeviceGroups): ProcessedAction[] {
    if (!groups.groups) {
      console.log('⚠️  [LgTv] No groups found in device groups');
      return [];
    }
    
    const allActions: ProcessedAction[] = [];
    
    for (const group of groups.groups) {
      if (!group.actions) {
        console.log(`⚠️  [LgTv] No actions found in group: ${group.group_name}`);
        continue;
      }
      
      // Identify pointer groups and process differently
      if (this.isPointerGroup(group)) {
        const pointerActions = this.processPointerActions(group.actions);
        allActions.push(...pointerActions);
      } else {
        const groupActions = this.processGroupActions(group.actions);
        allActions.push(...groupActions);
      }
    }
    
    console.log(`📊 [LgTv] Processed ${allActions.length} total actions from ${groups.groups.length} groups`);
    return allActions;
  }
  
  private isPointerGroup(group: DeviceGroup): boolean {
    const pointerActions = ['move_cursor', 'click', 'drag', 'scroll'];
    return group.actions.some(action => 
      pointerActions.some(pointer => action.name.toLowerCase().includes(pointer))
    );
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
      icon: this.iconResolver.selectIconForActionWithLibrary(action.name, 'material'),
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
      'move_cursor': 'CropFree',
      'click': 'TouchApp',
      'double_click': 'TouchApp',
      'right_click': 'TouchApp',
      'drag': 'PanTool',
      'scroll': 'UnfoldMore'
    };
    
    const iconName = pointerIconMappings[actionName] || 'CursorArrowRaysIcon';
    
    return {
      iconLibrary: 'material',
      iconName,
      iconVariant: 'outlined',
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
          type: 'string',
          optional: true,
          description: 'TV power state ("on", "off", etc.)'
        },
        {
          name: 'volume',
          type: 'number | null',
          optional: true,
          description: 'Current volume level'
        },
        {
          name: 'mute',
          type: 'boolean',
          optional: true,
          description: 'Mute status'
        },
        {
          name: 'current_app',
          type: 'string | null',
          optional: true,
          description: 'Currently active application'
        },
        {
          name: 'input_source',
          type: 'string | null',
          optional: true,
          description: 'Current input source'
        },
        {
          name: 'connected',
          type: 'boolean',
          optional: true,
          description: 'Device connection status'
        },
        {
          name: 'ip_address',
          type: 'string | null',
          optional: true,
          description: 'Device IP address'
        },
        {
          name: 'mac_address',
          type: 'string | null',
          optional: true,
          description: 'Device MAC address'
        }
      ],
      imports: ['BaseDeviceState'],
      extends: ['BaseDeviceState']
    };
  }
  
  private createActionHandlers(commands: Record<string, import('../../types/DeviceConfig').DeviceCommand>, deviceId: string): import('../../types/ProcessedDevice').ActionHandler[] {
    return Object.entries(commands).map(([commandName, command]) => ({
      actionName: commandName,
      handlerCode: `
        executeAction.mutate({ 
          deviceId: '${deviceId}', 
          action: { action: '${command.action}', params: payload } 
        });
      `,
      dependencies: ['useExecuteDeviceAction']
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
    
    // For other groups, check for directional navigation
    const directionalCommands = ['up', 'down', 'left', 'right', 'ok', 'enter'];
    const hasDirectional = group.actions.some(action => 
      directionalCommands.some(dir => action.name.toLowerCase().includes(dir))
    );
    return hasDirectional ? 'NavCluster' : 'ButtonGrid';
  }
} 