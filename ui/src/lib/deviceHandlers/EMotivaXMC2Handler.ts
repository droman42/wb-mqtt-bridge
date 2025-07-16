import type { DeviceClassHandler, ProcessedAction, ComponentType } from '../../types/ProcessedDevice';
import type { DeviceConfig, DeviceGroups, DeviceGroup, GroupAction } from '../../types/DeviceConfig';
import type { RemoteDeviceStructure } from '../../types/RemoteControlLayout';
import { IconResolver } from '../IconResolver';
import { ZoneDetection } from '../ZoneDetection';

export class EMotivaXMC2Handler implements DeviceClassHandler {
  deviceClass = 'EMotivaXMC2';
  private iconResolver = new IconResolver();
  private zoneDetection = new ZoneDetection();
  
  analyzeStructure(config: DeviceConfig, groups: DeviceGroups): RemoteDeviceStructure {
    console.log(`🎛️ [EMotivaXMC2] Analyzing structure for ${config.device_id}`);
    
    // Generate remote control structure directly
    const remoteStructure = this.generateRemoteStructure(config, groups);
    
    console.log(`✅ [EMotivaXMC2] Generated remote control structure with ${remoteStructure.remoteZones.length} zones`);
    return remoteStructure;
  }

  /**
   * Phase 4: Generate Remote Control Structure for EMotivaXMC2
   * Special case: Multi-zone handling with Zone 2 Power button in middle position
   */
  private generateRemoteStructure(config: DeviceConfig, groups: DeviceGroups): RemoteDeviceStructure {
    try {
      // Process all actions first
      const allActions = this.processAllGroupActions(groups);
      
      console.log(`🔍 [EMotivaXMC2] Starting zone detection with ${allActions.length} actions`);
      const remoteZones = this.zoneDetection.analyzeDeviceGroups(groups, allActions);
      console.log(`🎯 [EMotivaXMC2] Generated ${remoteZones.length} remote control zones`);

      // Apply EMotivaXMC2 special case - Zone 2 Power in middle position
      this.applyEmotivaSpecialCases(remoteZones, allActions);

      return {
        deviceId: config.device_id,
        deviceName: config.device_name,
        deviceClass: config.device_class,
        remoteZones: remoteZones,
        stateInterface: this.createProcessorStateInterface(config),
        actionHandlers: this.createZoneAwareActionHandlers(config.commands, config.device_id),
        specialCases: [{
          deviceClass: 'EMotivaXMC2',
          caseType: 'emotiva-xmc2-power',
          configuration: {
            hasZone2Power: true,
            zone2VolumeOnly: true,
            multiZoneDevice: true
          }
        }]
      };
    } catch (error) {
      console.error('❌ [EMotivaXMC2] Error generating remote structure:', error);
      throw error;
    }
  }

  /**
   * Apply EMotivaXMC2-specific modifications to remote zones
   * Special Power Zone Layout: Left=Power OFF, Middle=Zone 2 Power, Right=Power ON
   */
  private applyEmotivaSpecialCases(remoteZones: import('../../types/RemoteControlLayout').RemoteZone[], allActions: ProcessedAction[]): void {
    // Find power zone and modify for EMotiva special case
    const powerZone = remoteZones.find(zone => zone.zoneId === 'power');
    if (powerZone && powerZone.content?.powerButtons) {
      console.log('🎛️  [EMotivaXMC2] Applying special power zone layout');
      
      // Find power_on action (which supports zone parameter)
      const powerOnAction = allActions.find(action => 
        action.actionName.toLowerCase() === 'power_on'
      );

      if (powerOnAction) {
        // Create Zone 2 Power toggle button using power_on action with zone=2 parameter
        const zone2PowerAction: ProcessedAction = {
          ...powerOnAction,
          actionName: 'zone2_power_toggle', // Give it a unique name for identification
          displayName: 'Zone 2 Toggle',
          description: 'Toggle Zone 2 power state',
          parameters: [{ name: 'zone', type: 'integer', required: true, default: 2, min: null, max: null, description: 'Zone ID (2 for zone2)' }] // Force zone=2
        };

        const zone2Button: import('../../types/RemoteControlLayout').PowerButtonConfig = {
          position: 'middle',
          action: zone2PowerAction,
          buttonType: 'power-toggle'
        };

        // Add the Zone 2 power button to the power buttons array
        powerZone.content.powerButtons.push(zone2Button);
        console.log('✅ [EMotivaXMC2] Added Zone 2 Power button to middle position');
      } else {
        console.log('⚠️  [EMotivaXMC2] power_on action not found for Zone 2 Power button');
      }
    }

    // Configure Volume Zone for Zone 2 only (as per spec)
    const volumeZone = remoteZones.find(zone => zone.zoneId === 'volume');
    if (volumeZone && volumeZone.content) {
      console.log('🔊 [EMotivaXMC2] Configuring volume zone for Zone 2');
      
      // Update volume controls to use zone 2
      if (volumeZone.content.volumeSlider) {
        volumeZone.content.volumeSlider.zone = 2;
      }
      if (volumeZone.content.volumeButtons) {
        volumeZone.content.volumeButtons.forEach(button => {
          button.zone = 2;
        });
      }
    }
  }

  /**
   * Process all group actions into ProcessedAction format with zone awareness
   */
  private processAllGroupActions(groups: DeviceGroups): ProcessedAction[] {
    if (!groups.groups) {
      console.log('⚠️  [EMotivaXMC2] No groups found in device groups');
      return [];
    }
    
    const allActions: ProcessedAction[] = [];
    
    for (const group of groups.groups) {
      if (!group.actions) {
        console.log(`⚠️  [EMotivaXMC2] No actions found in group: ${group.group_name}`);
        continue;
      }

      const zoneCommands = this.identifyZoneCommands(group.actions);
      
      if (zoneCommands.length > 0) {
        // Process zone-aware actions
        const zoneCount = this.determineZoneCount(zoneCommands);
        for (let zone = 1; zone <= zoneCount; zone++) {
          const zoneActions = this.filterActionsForZone(group.actions, zone);
          const processedZoneActions = this.processZoneActions(zoneActions, zone);
          allActions.push(...processedZoneActions);
        }
      } else {
        const groupActions = this.processGroupActions(group.actions);
        allActions.push(...groupActions);
      }
    }
    
    console.log(`📊 [EMotivaXMC2] Processed ${allActions.length} total actions from ${groups.groups.length} groups`);
    return allActions;
  }

  private identifyZoneCommands(actions: GroupAction[]): GroupAction[] {
    return actions.filter(action => 
      action.name.toLowerCase().includes('zone') ||
      action.name.toLowerCase().includes('volume') ||
      action.name.toLowerCase().includes('input')
    );
  }
  
  private determineZoneCount(zoneCommands: GroupAction[]): number {
    // Look for zone numbers in action names
    const zoneNumbers: number[] = [];
    
    zoneCommands.forEach(action => {
      const matches = action.name.match(/zone[_\s]*(\d+)/i);
      if (matches) {
        const zoneNum = parseInt(matches[1]);
        if (!zoneNumbers.includes(zoneNum)) {
          zoneNumbers.push(zoneNum);
        }
      }
    });
    
    // If no explicit zone numbers found, assume 2 zones (main + zone2)
    return zoneNumbers.length > 0 ? Math.max(...zoneNumbers) : 2;
  }
  
  private filterActionsForZone(actions: GroupAction[], zoneNumber: number): GroupAction[] {
    if (zoneNumber === 1) {
      // Zone 1 (main) gets actions without zone numbers or explicitly zone 1
      return actions.filter(action => 
        !action.name.match(/zone[_\s]*[2-9]/i) ||
        action.name.match(/zone[_\s]*1/i)
      );
    } else {
      // Other zones get actions with their specific zone number
      return actions.filter(action => 
        action.name.match(new RegExp(`zone[_\\s]*${zoneNumber}`, 'i'))
      );
    }
  }
  
  private processZoneActions(actions: GroupAction[], zoneNumber: number): ProcessedAction[] {
    return actions.map(action => ({
      actionName: action.name,
      displayName: this.formatZoneActionName(action.name),
      description: action.description,
      parameters: action.params || [],
      group: `zone_${zoneNumber}`,
      icon: this.getAudioIcon(action.name),
      uiHints: { 
        buttonSize: 'medium', 
        buttonStyle: 'secondary',
        zoneNumber 
      }
    }));
  }
  
  private processGroupActions(actions: GroupAction[]): ProcessedAction[] {
    return actions.map(action => ({
      actionName: action.name,
      displayName: this.formatDisplayName(action.name),
      description: action.description,
      parameters: action.params || [],
      group: 'default',
      icon: this.isAudioAction(action.name) ? this.getAudioIcon(action.name) : this.iconResolver.selectIconForActionWithLibrary(action.name, 'material'),
      uiHints: { buttonSize: 'medium', buttonStyle: 'secondary' }
    }));
  }

  private isAudioAction(actionName: string): boolean {
    const cleanName = actionName.toLowerCase();
    return ['volume', 'mute', 'input', 'bass', 'treble', 'balance', 'eq'].some(keyword => 
      cleanName.includes(keyword)
    );
  }
  
  private formatZoneActionName(actionName: string): string {
    // Remove zone number from display name since it's already in the section title
    let displayName = actionName
      .replace(/zone[_\s]*\d+[_\s]*/gi, '')
      .replace(/([a-z])([A-Z])/g, '$1 $2')
      .replace(/_/g, ' ')
      .split(' ')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
      .join(' ');
    
    return displayName;
  }
  
  private formatDisplayName(actionName: string): string {
    return actionName
      .replace(/([a-z])([A-Z])/g, '$1 $2')
      .replace(/_/g, ' ')
      .split(' ')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
      .join(' ');
  }
  
  private getAudioIcon(actionName: string): import('../../types/ProcessedDevice').ActionIcon {
    const audioIconMappings: Record<string, string> = {
      'volume': 'VolumeUp',
      'mute': 'VolumeOff',
      'input': 'Input',
      'bass': 'GraphicEq',
      'treble': 'GraphicEq',
      'balance': 'Tune',
      'eq': 'Equalizer'
    };
    
    const cleanName = actionName.toLowerCase();
    for (const [key, iconName] of Object.entries(audioIconMappings)) {
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
  
  private createProcessorStateInterface(config: DeviceConfig): import('../../types/ProcessedDevice').StateDefinition {
    return {
      interfaceName: `${config.device_class}State`,
      fields: [
        {
          name: 'power',
          type: 'string | null',
          optional: true,
          description: 'Processor power state ("on", "off", or null)'
        },
        {
          name: 'zone2_power',
          type: 'string | null',
          optional: true,
          description: 'Zone 2 power state ("on", "off", or null)'
        },
        {
          name: 'volume',
          type: 'number | null',
          optional: true,
          description: 'Main zone volume level'
        },
        {
          name: 'zone2_volume',
          type: 'number | null',
          optional: true,
          description: 'Zone 2 volume level'
        },
        {
          name: 'input_source',
          type: 'string | null',
          optional: true,
          description: 'Main zone input source'
        },
        {
          name: 'connected',
          type: 'boolean',
          optional: true,
          description: 'Device connection status'
        },
        {
          name: 'mute',
          type: 'boolean | null',
          optional: true,
          description: 'Main zone mute status'
        },
        {
          name: 'zone2_mute',
          type: 'boolean | null',
          optional: true,
          description: 'Zone 2 mute status'
        }
      ],
      imports: ['BaseDeviceState'],
      extends: ['BaseDeviceState']
    };
  }
  
  private createZoneAwareActionHandlers(commands: Record<string, import('../../types/DeviceConfig').DeviceCommand>, deviceId: string): import('../../types/ProcessedDevice').ActionHandler[] {
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

  private determineComponentType(group: DeviceGroup, actions: GroupAction[]): ComponentType {
    // Menu groups should always use NavCluster for directional navigation
    const isMenuGroup = group.group_name.toLowerCase().includes('menu');
    if (isMenuGroup) {
      return 'NavCluster';
    }
    
    // Check if this is a volume-related group
    const isVolumeGroup = group.group_name.toLowerCase().includes('volume') || 
                         actions.some(action => action.name.toLowerCase().includes('volume'));
    
    if (isVolumeGroup) {
      // If any action has range parameters, use SliderControl
      const hasRangeParam = actions.some(action => 
        action.params?.some(param => param.type === 'range')
      );
      return hasRangeParam ? 'SliderControl' : 'ButtonGrid';
    }
    
    // For other groups, check if they have range parameters
    const hasRangeParam = actions.some(action => 
      action.params?.some(param => param.type === 'range')
    );
    return hasRangeParam ? 'SliderControl' : 'ButtonGrid';
  }
} 