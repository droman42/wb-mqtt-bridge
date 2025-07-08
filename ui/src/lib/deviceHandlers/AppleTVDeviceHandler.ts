import type { DeviceClassHandler, ProcessedAction, ComponentType } from '../../types/ProcessedDevice';
import type { DeviceConfig, DeviceGroups, DeviceGroup, GroupAction } from '../../types/DeviceConfig';
import type { RemoteDeviceStructure } from '../../types/RemoteControlLayout';
import { IconResolver } from '../IconResolver';
import { ZoneDetection } from '../ZoneDetection';

export class AppleTVDeviceHandler implements DeviceClassHandler {
  deviceClass = 'AppleTVDevice';
  private iconResolver = new IconResolver();
  private zoneDetection = new ZoneDetection();
  
  analyzeStructure(config: DeviceConfig, groups: DeviceGroups): RemoteDeviceStructure {
    console.log(`📱 [AppleTVDevice] Analyzing structure for ${config.device_id}`);
    
    // Generate remote control structure directly
    const remoteStructure = this.generateRemoteStructure(config, groups);
    
    console.log(`✅ [AppleTVDevice] Generated remote control structure with ${remoteStructure.remoteZones.length} zones`);
    return remoteStructure;
  }

  /**
   * Phase 4: Generate Remote Control Structure for Apple TV
   * Maps streaming device controls to remote control zones
   */
  private generateRemoteStructure(config: DeviceConfig, groups: DeviceGroups): RemoteDeviceStructure {
    try {
      // Process all actions first
      const allActions = this.processAllGroupActions(groups);
      
      console.log(`🔍 [AppleTV] Starting zone detection with ${allActions.length} actions`);
      const remoteZones = this.zoneDetection.analyzeDeviceGroups(groups, allActions);
      console.log(`🎯 [AppleTV] Generated ${remoteZones.length} remote control zones`);

      return {
        deviceId: config.device_id,
        deviceName: config.device_name,
        deviceClass: config.device_class,
        remoteZones: remoteZones,
        stateInterface: this.createAppleTVStateInterface(config),
        actionHandlers: this.createActionHandlers(config.commands),
        specialCases: [{
          deviceClass: 'AppleTVDevice',
          caseType: 'appletv-streaming',
          configuration: {
            usesAppsAPI: true,
            hasMediaControls: true,
            hasDirectionalNav: true
          }
        }]
      };
    } catch (error) {
      console.error('❌ [AppleTV] Error generating remote structure:', error);
      throw error;
    }
  }

  /**
   * Process all group actions into ProcessedAction format
   */
  private processAllGroupActions(groups: DeviceGroups): ProcessedAction[] {
    if (!groups.groups) {
      console.log('⚠️  [AppleTV] No groups found in device groups');
      return [];
    }
    
    const allActions: ProcessedAction[] = [];
    
    for (const group of groups.groups) {
      if (!group.actions) {
        console.log(`⚠️  [AppleTV] No actions found in group: ${group.group_name}`);
        continue;
      }
      const groupActions = this.processGroupActions(group.actions);
      allActions.push(...groupActions);
    }
    
    console.log(`📊 [AppleTV] Processed ${allActions.length} total actions from ${groups.groups.length} groups`);
    return allActions;
  }
  
  private processGroupActions(actions: GroupAction[]): ProcessedAction[] {
    return actions.map(action => ({
      actionName: action.name,
      displayName: this.formatDisplayName(action.name),
      description: action.description,
      parameters: action.params || [],
      group: 'default',
      icon: this.getAppleTVIcon(action.name),
      uiHints: { 
        buttonSize: 'medium', 
        buttonStyle: this.getButtonStyle(action.name)
      }
    }));
  }
  
  private formatDisplayName(actionName: string): string {
    // Special cases for Apple TV actions
    const specialMappings: Record<string, string> = {
      'tv': 'TV',
      'app_switcher': 'App Switcher',
      'siri': 'Siri',
      'airplay': 'AirPlay',
      'home_button': 'Home',
      'volume_up': 'Volume Up',
      'volume_down': 'Volume Down'
    };
    
    const cleanName = actionName.toLowerCase();
    if (specialMappings[cleanName]) {
      return specialMappings[cleanName];
    }
    
    return actionName
      .replace(/([a-z])([A-Z])/g, '$1 $2')
      .replace(/_/g, ' ')
      .split(' ')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
      .join(' ');
  }
  
  private getButtonStyle(actionName: string): 'primary' | 'secondary' | 'destructive' {
    const primaryActions = ['play', 'pause', 'home', 'siri'];
    const destructiveActions = ['power_off', 'stop'];
    
    const cleanName = actionName.toLowerCase();
    if (primaryActions.some(action => cleanName.includes(action))) {
      return 'primary';
    } else if (destructiveActions.some(action => cleanName.includes(action))) {
      return 'destructive';
    }
    
    return 'secondary';
  }
  
  private getAppleTVIcon(actionName: string): import('../../types/ProcessedDevice').ActionIcon {
    // For power actions, use IconResolver to get custom icons when available
    const cleanName = actionName.toLowerCase();
    if (cleanName.includes('power')) {
      return this.iconResolver.selectIconForAction(actionName);
    }
    
    const appleTVIconMappings: Record<string, string> = {
      'play': 'PlayArrow',
      'pause': 'Pause',
      'stop': 'Stop',
      'next': 'SkipNext',
      'previous': 'SkipPrevious',
      'rewind': 'FastRewind',
      'fast_forward': 'FastForward',
      'up': 'KeyboardArrowUp',
      'down': 'KeyboardArrowDown',
      'left': 'KeyboardArrowLeft',
      'right': 'KeyboardArrowRight',
      'ok': 'Check',
      'select': 'Check',
      'home': 'Home',
      'menu': 'Menu',
      'back': 'ArrowBack',
      'siri': 'Mic',
      'volume_up': 'VolumeUp',
      'volume_down': 'VolumeDown',
      'mute': 'VolumeOff',
      'tv': 'Tv',
      'app': 'Apps',
      'airplay': 'Cast'
    };
    
    for (const [key, iconName] of Object.entries(appleTVIconMappings)) {
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
  
  private createAppleTVStateInterface(config: DeviceConfig): import('../../types/ProcessedDevice').StateDefinition {
    return {
      interfaceName: `${config.device_class}State`,
      fields: [
        {
          name: 'connected',
          type: 'boolean',
          optional: true,
          description: 'Device connection status'
        },
        {
          name: 'power',
          type: 'string',
          optional: true,
          description: 'Apple TV power state ("on", "off", "unknown")'
        },
        {
          name: 'app',
          type: 'string | null',
          optional: true,
          description: 'Currently active application'
        },
        {
          name: 'playback_state',
          type: 'string | null',
          optional: true,
          description: 'Current playback state (playing, paused, stopped)'
        },
        {
          name: 'media_type',
          type: 'string | null',
          optional: true,
          description: 'Current media type'
        },
        {
          name: 'title',
          type: 'string | null',
          optional: true,
          description: 'Current media title'
        },
        {
          name: 'artist',
          type: 'string | null',
          optional: true,
          description: 'Current media artist'
        },
        {
          name: 'album',
          type: 'string | null',
          optional: true,
          description: 'Current media album'
        },
        {
          name: 'position',
          type: 'number | null',
          optional: true,
          description: 'Current playback position'
        },
        {
          name: 'total_time',
          type: 'number | null',
          optional: true,
          description: 'Total media duration'
        },
        {
          name: 'volume',
          type: 'number | null',
          optional: true,
          description: 'Current volume level'
        },
        {
          name: 'ip_address',
          type: 'string | null',
          optional: true,
          description: 'Device IP address'
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

  // Legacy methods maintained for backward compatibility during transition
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
    
    // Check for navigation/directional commands
    const directionalCommands = ['up', 'down', 'left', 'right', 'ok', 'enter', 'select'];
    const hasDirectional = group.actions.some(action => 
      directionalCommands.some(dir => action.name.toLowerCase().includes(dir))
    );
    
    // Check for media control commands
    const mediaCommands = ['play', 'pause', 'stop', 'next', 'previous', 'rewind', 'fast_forward'];
    const hasMediaControls = group.actions.some(action => 
      mediaCommands.some(media => action.name.toLowerCase().includes(media))
    );
    
    if (hasDirectional) {
      return 'NavCluster';
    } else if (hasMediaControls) {
      return 'ButtonGrid'; // Media controls work well as buttons
    }
    
    return 'ButtonGrid';
  }

  private getLayoutForComponentType(componentType: ComponentType): import('../../types/ProcessedDevice').LayoutConfig {
    switch (componentType) {
      case 'NavCluster':
        return { fullWidth: true, spacing: 'medium' };
      case 'ButtonGrid':
        return { columns: 3, spacing: 'medium' }; // 3 columns for media controls
      default:
        return { columns: 2, spacing: 'medium' };
    }
  }
} 