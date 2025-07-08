import type { DeviceClassHandler, ProcessedAction, ComponentType } from '../../types/ProcessedDevice';
import type { DeviceConfig, DeviceGroups, GroupAction } from '../../types/DeviceConfig';
import type { RemoteDeviceStructure } from '../../types/RemoteControlLayout';
import { IconResolver } from '../IconResolver';
import { ZoneDetection } from '../ZoneDetection';

export class AuralicDeviceHandler implements DeviceClassHandler {
  deviceClass = 'AuralicDevice';
  private iconResolver = new IconResolver();
  private zoneDetection = new ZoneDetection();
  
  analyzeStructure(config: DeviceConfig, groups: DeviceGroups): RemoteDeviceStructure {
    console.log(`🎵 [AuralicDevice] Analyzing structure for ${config.device_id}`);
    
    // Generate remote control structure directly
    const remoteStructure = this.generateRemoteStructure(config, groups);
    
    console.log(`✅ [AuralicDevice] Generated remote control structure with ${remoteStructure.remoteZones.length} zones`);
    return remoteStructure;
  }

  /**
   * Phase 4: Generate Remote Control Structure for Auralic Device
   * Maps audio streaming device controls to remote control zones
   */
  private generateRemoteStructure(config: DeviceConfig, groups: DeviceGroups): RemoteDeviceStructure {
    try {
      // Process all actions first
      const allActions = this.processAllGroupActions(groups);
      
      console.log(`🔍 [Auralic] Starting zone detection with ${allActions.length} actions`);
      const remoteZones = this.zoneDetection.analyzeDeviceGroups(groups, allActions);
      console.log(`🎯 [Auralic] Generated ${remoteZones.length} remote control zones`);

      return {
        deviceId: config.device_id,
        deviceName: config.device_name,
        deviceClass: config.device_class,
        remoteZones: remoteZones,
        stateInterface: this.createAuralicStateInterface(config),
        actionHandlers: this.createActionHandlers(config.commands),
        specialCases: [{
          deviceClass: 'AuralicDevice',
          caseType: 'auralic-streaming',
          configuration: {
            usesInputsAPI: true,
            hasMediaControls: true,
            hasVolumeSlider: true,
            isNetworkStreamer: true
          }
        }]
      };
    } catch (error) {
      console.error('❌ [Auralic] Error generating remote structure:', error);
      throw error;
    }
  }

  /**
   * Process all group actions into ProcessedAction format
   */
  private processAllGroupActions(groups: DeviceGroups): ProcessedAction[] {
    if (!groups.groups) {
      console.log('⚠️  [Auralic] No groups found in device groups');
      return [];
    }
    
    const allActions: ProcessedAction[] = [];
    
    for (const group of groups.groups) {
      if (!group.actions) {
        console.log(`⚠️  [Auralic] No actions found in group: ${group.group_name}`);
        continue;
      }
      const groupActions = this.processGroupActions(group.actions);
      allActions.push(...groupActions);
    }
    
    console.log(`📊 [Auralic] Processed ${allActions.length} total actions from ${groups.groups.length} groups`);
    return allActions;
  }
  
  private processGroupActions(actions: GroupAction[]): ProcessedAction[] {
    return actions.map(action => ({
      actionName: action.name,
      displayName: this.formatDisplayName(action.name),
      description: action.description,
      parameters: action.params || [],
      group: 'default',
      icon: this.getAuralicIcon(action.name),
      uiHints: { 
        buttonSize: 'medium', 
        buttonStyle: this.getButtonStyle(action.name)
      }
    }));
  }

  private formatDisplayName(actionName: string): string {
    // Special cases for Auralic streaming device actions
    const specialMappings: Record<string, string> = {
      'dac': 'DAC',
      'usb': 'USB',
      'coax': 'Coaxial',
      'optical': 'Optical',
      'aes_ebu': 'AES/EBU',
      'wifi': 'Wi-Fi',
      'ethernet': 'Ethernet',
      'upnp': 'UPnP',
      'roon': 'Roon',
      'tidal': 'TIDAL',
      'qobuz': 'Qobuz',
      'spotify': 'Spotify'
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
    const primaryActions = ['play', 'pause', 'favorite', 'preset'];
    const destructiveActions = ['power_off', 'stop', 'reset'];
    
    const cleanName = actionName.toLowerCase();
    if (primaryActions.some(action => cleanName.includes(action))) {
      return 'primary';
    } else if (destructiveActions.some(action => cleanName.includes(action))) {
      return 'destructive';
    }
    
    return 'secondary';
  }
  
  private getAuralicIcon(actionName: string): import('../../types/ProcessedDevice').ActionIcon {
    // For power actions, use IconResolver to get custom icons when available
    const cleanName = actionName.toLowerCase();
    if (cleanName.includes('power')) {
      return this.iconResolver.selectIconForAction(actionName);
    }
    
    const auralicIconMappings: Record<string, string> = {
      'play': 'PlayArrow',
      'pause': 'Pause',
      'stop': 'Stop',
      'next': 'SkipNext',
      'previous': 'SkipPrevious',
      'shuffle': 'Shuffle',
      'repeat': 'Repeat',
      'favorite': 'Favorite',
      'preset': 'Bookmark',
      'volume': 'VolumeUp',
      'mute': 'VolumeOff',
      'input': 'Input',
      'dac': 'Memory',
      'filter': 'FilterList',
      'upsampling': 'TrendingUp',
      'wifi': 'Wifi',
      'ethernet': 'Cable',
      'usb': 'Usb',
      'coax': 'Cable',
      'optical': 'FiberOpticCable',
      'streaming': 'CloudQueue',
      'tidal': 'MusicNote',
      'spotify': 'MusicNote',
      'qobuz': 'MusicNote',
      'roon': 'MusicNote'
    };
    
    for (const [key, iconName] of Object.entries(auralicIconMappings)) {
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
  
  private createAuralicStateInterface(config: DeviceConfig): import('../../types/ProcessedDevice').StateDefinition {
    return {
      interfaceName: `${config.device_class}State`,
      fields: [
        {
          name: 'power',
          type: 'string',
          optional: true,
          description: 'Device power state ("on", "off", "booting", "unknown")'
        },
        {
          name: 'volume',
          type: 'number',
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
          name: 'source',
          type: 'string | null',
          optional: true,
          description: 'Currently selected input source'
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
          name: 'track_title',
          type: 'string | null',
          optional: true,
          description: 'Current track title'
        },
        {
          name: 'track_artist',
          type: 'string | null',
          optional: true,
          description: 'Current track artist'
        },
        {
          name: 'track_album',
          type: 'string | null',
          optional: true,
          description: 'Current track album'
        },
        {
          name: 'transport_state',
          type: 'string | null',
          optional: true,
          description: 'Current transport state (Playing, Paused, Stopped, etc.)'
        },
        {
          name: 'deep_sleep',
          type: 'boolean',
          optional: true,
          description: 'True when device is in deep sleep mode'
        },
        {
          name: 'message',
          type: 'string | null',
          optional: true,
          description: 'User-friendly message about current state'
        },
        {
          name: 'warning',
          type: 'string | null',
          optional: true,
          description: 'Warning message if relevant'
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
  private determineComponentType(actions: GroupAction[]): ComponentType {
    // Check for volume controls with range parameters
    const hasVolumeRange = actions.some(action => 
      action.name.toLowerCase().includes('volume') &&
      action.params?.some(param => param.type === 'range')
    );
    
    if (hasVolumeRange) {
      return 'SliderControl';
    }
    
    // Check for directional navigation
    const directionalCommands = ['up', 'down', 'left', 'right', 'ok', 'enter', 'select'];
    const hasDirectional = actions.some(action => 
      directionalCommands.some(dir => action.name.toLowerCase().includes(dir))
    );
    
    if (hasDirectional) {
      return 'NavCluster';
    }
    
    return 'ButtonGrid';
  }
} 