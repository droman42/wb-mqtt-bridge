import type { DeviceClassHandler, DeviceStructure, UISection, ProcessedAction, ComponentType } from '../../types/ProcessedDevice';
import type { DeviceConfig, DeviceGroups, DeviceGroup, GroupAction } from '../../types/DeviceConfig';
import { IconResolver } from '../IconResolver';

export class AppleTVDeviceHandler implements DeviceClassHandler {
  deviceClass = 'AppleTVDevice';
  private iconResolver = new IconResolver();
  
  analyzeStructure(config: DeviceConfig, groups: DeviceGroups): DeviceStructure {
    const uiSections = groups.groups.map(group => {
      const componentType = this.determineComponentType(group);
      return {
        sectionId: group.group_id,
        sectionName: group.group_name,
        componentType,
        actions: this.processGroupActions(group.actions),
        layout: this.getLayoutForComponentType(componentType)
      };
    });
    
    return {
      deviceId: config.device_id,
      deviceName: config.device_name,
      deviceClass: config.device_class,
      uiSections,
      stateInterface: this.createAppleTVStateInterface(config),
      actionHandlers: this.createActionHandlers(config.commands)
    };
  }
  
  private determineComponentType(group: DeviceGroup): ComponentType {
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
    const appleTVIconMappings: Record<string, string> = {
      'play': 'PlayIcon',
      'pause': 'PauseIcon',
      'stop': 'StopIcon',
      'next': 'ForwardIcon',
      'previous': 'BackwardIcon',
      'rewind': 'BackwardIcon',
      'fast_forward': 'ForwardIcon',
      'up': 'ChevronUpIcon',
      'down': 'ChevronDownIcon',
      'left': 'ChevronLeftIcon',
      'right': 'ChevronRightIcon',
      'ok': 'CheckIcon',
      'select': 'CheckIcon',
      'home': 'HomeIcon',
      'menu': 'Bars3Icon',
      'back': 'ArrowLeftIcon',
      'siri': 'MicrophoneIcon',
      'volume_up': 'SpeakerWaveIcon',
      'volume_down': 'SpeakerWaveIcon',
      'mute': 'SpeakerXMarkIcon',
      'power': 'PowerIcon',
      'tv': 'TvIcon',
      'app': 'Squares2X2Icon',
      'airplay': 'WifiIcon'
    };
    
    const cleanName = actionName.toLowerCase();
    for (const [key, iconName] of Object.entries(appleTVIconMappings)) {
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
  
  private createAppleTVStateInterface(config: DeviceConfig): import('../../types/ProcessedDevice').StateDefinition {
    return {
      interfaceName: `${config.device_class}State`,
      fields: [
        {
          name: 'power',
          type: 'boolean',
          optional: true,
          description: 'Apple TV power state'
        },
        {
          name: 'currentApp',
          type: 'string',
          optional: true,
          description: 'Currently active application'
        },
        {
          name: 'playbackState',
          type: 'string',
          optional: true,
          description: 'Current playback state (playing, paused, stopped)'
        },
        {
          name: 'volume',
          type: 'number',
          optional: true,
          description: 'Current volume level'
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