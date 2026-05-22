import type { DeviceClassHandler, ProcessedAction, ComponentType } from '../../types/ProcessedDevice';
import type { DeviceConfig, DeviceGroups, GroupAction } from '../../types/DeviceConfig';
import type { RemoteDeviceStructure } from '../../types/RemoteControlLayout';
import { IconResolver } from '../IconResolver';
import { ZoneDetection } from '../ZoneDetection';

export class RevoxA77ReelToReelHandler implements DeviceClassHandler {
  deviceClass = 'RevoxA77ReelToReel';
  private iconResolver = new IconResolver();
  private zoneDetection = new ZoneDetection();
  
  analyzeStructure(config: DeviceConfig, groups: DeviceGroups): RemoteDeviceStructure {
    console.log(`📼 [RevoxA77ReelToReel] Analyzing structure for ${config.device_id}`);
    
    // Generate remote control structure directly
    const remoteStructure = this.generateRemoteStructure(config, groups);
    
    console.log(`✅ [RevoxA77ReelToReel] Generated remote control structure with ${remoteStructure.remoteZones.length} zones`);
    return remoteStructure;
  }

  /**
   * Phase 4: Generate Remote Control Structure for Revox A77 Reel-to-Reel
   * Maps tape deck controls to remote control zones
   */
  private generateRemoteStructure(config: DeviceConfig, groups: DeviceGroups): RemoteDeviceStructure {
    try {
      // Process all actions first
      const allActions = this.processAllGroupActions(groups);
      
      console.log(`🔍 [RevoxA77] Starting zone detection with ${allActions.length} actions`);
      const remoteZones = this.zoneDetection.analyzeDeviceGroups(groups, allActions);
      console.log(`🎯 [RevoxA77] Generated ${remoteZones.length} remote control zones`);

      return {
        deviceId: config.device_id,
        deviceName: config.device_name,
        deviceClass: config.device_class,
        remoteZones: remoteZones,
        stateInterface: this.createRevoxStateInterface(config),
        actionHandlers: this.createActionHandlers(config.commands, config.device_id),
        specialCases: [{
          deviceClass: 'RevoxA77ReelToReel',
          caseType: 'revox-tape-deck',
          configuration: {
            hasTapeTransport: true,
            hasVolumeSlider: true,
            hasAnalogInputs: true,
            isVintageDevice: true
          }
        }]
      };
    } catch (error) {
      console.error('❌ [RevoxA77] Error generating remote structure:', error);
      throw error;
    }
  }

  /**
   * Process all group actions into ProcessedAction format
   */
  private processAllGroupActions(groups: DeviceGroups): ProcessedAction[] {
    if (!groups.groups) {
      console.log('⚠️  [RevoxA77ReelToReel] No groups found in device groups');
      return [];
    }
    
    // Filter out excluded groups before processing
    const filteredGroups = this.filterExcludedGroups(groups);
    
    const allActions: ProcessedAction[] = [];
    
    for (const group of filteredGroups.groups!) {
      if (!group.actions) {
        console.log(`⚠️  [RevoxA77ReelToReel] No actions found in group: ${group.group_name}`);
        continue;
      }
      const groupActions = this.processGroupActions(group.actions);
      allActions.push(...groupActions);
    }
    
    console.log(`📊 [RevoxA77ReelToReel] Processed ${allActions.length} total actions from ${filteredGroups.groups!.length} groups`);
    return allActions;
  }
  
  /**
   * Filter out groups that should not be displayed in the UI
   */
  private filterExcludedGroups(groups: DeviceGroups): DeviceGroups {
    const excludedGroupNames = ['noops', 'hidden', 'internal', 'debug'];
    
    if (!groups.groups) {
      return groups;
    }
    
    const originalCount = groups.groups.length;
    const filteredGroups = groups.groups.filter(group => {
      const shouldExclude = excludedGroupNames.some(excludedName => 
        group.group_name.toLowerCase().includes(excludedName.toLowerCase())
      );
      
      if (shouldExclude) {
        console.log(`🚫 [RevoxA77ReelToReel] Excluding group '${group.group_name}' from UI (${group.actions.length} actions)`);
      }
      
      return !shouldExclude;
    });
    
    if (filteredGroups.length !== originalCount) {
      console.log(`🔍 [RevoxA77ReelToReel] Filtered groups: ${originalCount} → ${filteredGroups.length} (excluded ${originalCount - filteredGroups.length} groups)`);
    }
    
    return {
      ...groups,
      groups: filteredGroups
    };
  }
  
  private processGroupActions(actions: GroupAction[]): ProcessedAction[] {
    return actions.map(action => ({
      actionName: action.name,
      displayName: this.formatDisplayName(action.name),
      description: action.description,
      parameters: action.params || [],
      group: 'default',
      icon: this.getRevoxIcon(action.name),
      uiHints: { 
        buttonSize: 'medium', 
        buttonStyle: this.getButtonStyle(action.name)
      }
    }));
  }

  private formatDisplayName(actionName: string): string {
    // Special cases for Revox A77 tape deck actions
    const specialMappings: Record<string, string> = {
      'ff': 'Fast Forward',
      'rew': 'Rewind',
      'rec': 'Record',
      'pb': 'Playback',
      'stop': 'Stop',
      'pause': 'Pause',
      'eject': 'Eject',
      'auto_stop': 'Auto Stop',
      'tape_speed': 'Tape Speed',
      'ips': 'IPS',
      '7_5_ips': '7.5 IPS',
      '15_ips': '15 IPS',
      'bias': 'Bias',
      'eq': 'EQ',
      'line_in': 'Line In',
      'mic_in': 'Mic In'
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
    const primaryActions = ['play', 'playback', 'pb'];
    const destructiveActions = ['stop', 'eject', 'power_off'];
    const recordActions = ['record', 'rec'];
    
    const cleanName = actionName.toLowerCase();
    if (primaryActions.some(action => cleanName.includes(action))) {
      return 'primary';
    } else if (destructiveActions.some(action => cleanName.includes(action))) {
      return 'destructive';
    } else if (recordActions.some(action => cleanName.includes(action))) {
      return 'destructive'; // Record is destructive (overwrites tape)
    }
    
    return 'secondary';
  }
  
    private getRevoxIcon(actionName: string): import('../../types/ProcessedDevice').ActionIcon {
    // For power actions, use IconResolver to get custom icons when available
    const cleanName = actionName.toLowerCase();
    if (cleanName.includes('power')) {
      return this.iconResolver.selectIconForAction(actionName);
    }
    
    const revoxIconMappings: Record<string, string> = {
      'play': 'PlayArrow',
      'playback': 'PlayArrow',
      'pb': 'PlayArrow',
      'pause': 'Pause',
      'stop': 'Stop',
      'record': 'FiberManualRecord',
      'rec': 'FiberManualRecord',
      'ff': 'FastForward',
      'fast_forward': 'FastForward',
      'rewind_forward': 'FastForward',
      'rew': 'FastRewind',
      'rewind': 'FastRewind',
      'rewind_backward': 'FastRewind',
      'eject': 'Eject',
      'volume': 'VolumeUp',
      'mute': 'VolumeOff',
      'input': 'Input',
      'mic': 'Mic',
      'line': 'Cable',
      'tape': 'AudioFile',
      'speed': 'Speed',
      'ips': 'Timer',
      'bias': 'Tune',
      'eq': 'Equalizer',
      'level': 'BarChart',
      'meter': 'Analytics',
      'auto': 'AutoMode',
      'manual': 'Settings'
    };

    for (const [key, iconName] of Object.entries(revoxIconMappings)) {
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
  
  private createRevoxStateInterface(config: DeviceConfig): import('../../types/ProcessedDevice').StateDefinition {
    return {
      interfaceName: `${config.device_class}State`,
      fields: [
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

  // Legacy methods maintained for backward compatibility during transition
  private determineComponentType(actions: GroupAction[]): ComponentType {
    // Check for level controls with range parameters
    const hasLevelRange = actions.some(action => 
      (action.name.toLowerCase().includes('level') ||
       action.name.toLowerCase().includes('volume')) &&
      action.params?.some(param => param.type === 'range')
    );
    
    if (hasLevelRange) {
      return 'SliderControl';
    }
    
    return 'ButtonGrid';
  }
} 