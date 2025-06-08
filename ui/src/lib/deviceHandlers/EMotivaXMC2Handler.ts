import type { DeviceClassHandler, DeviceStructure, UISection, ProcessedAction, ComponentType } from '../../types/ProcessedDevice';
import type { DeviceConfig, DeviceGroups, DeviceGroup, GroupAction } from '../../types/DeviceConfig';
import { IconResolver } from '../IconResolver';

export class EMotivaXMC2Handler implements DeviceClassHandler {
  deviceClass = 'EMotivaXMC2';
  private iconResolver = new IconResolver();
  
  analyzeStructure(config: DeviceConfig, groups: DeviceGroups): DeviceStructure {
    const processedSections: UISection[] = [];
    
    for (const group of groups.groups) {
      const zoneCommands = this.identifyZoneCommands(group.actions);
      
      if (zoneCommands.length > 0) {
        // Create separate sections for each zone
        const zoneCount = this.determineZoneCount(zoneCommands);
        for (let zone = 1; zone <= zoneCount; zone++) {
          processedSections.push(this.createZoneSection(group, zone));
        }
      } else {
        processedSections.push(this.createStandardSection(group));
      }
    }
    
    return {
      deviceId: config.device_id,
      deviceName: config.device_name,
      deviceClass: config.device_class,
      uiSections: processedSections,
      stateInterface: this.createProcessorStateInterface(config),
      actionHandlers: this.createZoneAwareActionHandlers(config.commands)
    };
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
  
  private createZoneSection(group: DeviceGroup, zoneNumber: number): UISection {
    const zoneActions = this.filterActionsForZone(group.actions, zoneNumber);
    
    return {
      sectionId: `${group.group_id}_zone_${zoneNumber}`,
      sectionName: `${group.group_name} - Zone ${zoneNumber}`,
      componentType: this.hasRangeParameters(zoneActions) ? 'SliderControl' : 'ButtonGrid',
      actions: this.processZoneActions(zoneActions, zoneNumber),
      layout: { zoneNumber, columns: 1, spacing: 'medium' }
    };
  }
  
  private createStandardSection(group: DeviceGroup): UISection {
    return {
      sectionId: group.group_id,
      sectionName: group.group_name,
      componentType: this.hasRangeParameters(group.actions) ? 'SliderControl' : 'ButtonGrid',
      actions: this.processGroupActions(group.actions),
      layout: { columns: 2, spacing: 'medium' }
    };
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
  
  private hasRangeParameters(actions: GroupAction[]): boolean {
    return actions.some(action => 
      action.params?.some(param => param.type === 'range')
    );
  }
  
  private processZoneActions(actions: GroupAction[], zoneNumber: number): ProcessedAction[] {
    return actions.map(action => ({
      actionName: action.name,
      displayName: this.formatZoneActionName(action.name, zoneNumber),
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
      icon: this.iconResolver.selectIconForAction(action.name),
      uiHints: { buttonSize: 'medium', buttonStyle: 'secondary' }
    }));
  }
  
  private formatZoneActionName(actionName: string, zoneNumber: number): string {
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
      'volume': 'SpeakerWaveIcon',
      'mute': 'SpeakerXMarkIcon',
      'input': 'ArrowsRightLeftIcon',
      'bass': 'SpeakerWaveIcon',
      'treble': 'SpeakerWaveIcon',
      'balance': 'ArrowsRightLeftIcon',
      'eq': 'AdjustmentsHorizontalIcon'
    };
    
    const cleanName = actionName.toLowerCase();
    for (const [key, iconName] of Object.entries(audioIconMappings)) {
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
  
  private createProcessorStateInterface(config: DeviceConfig): import('../../types/ProcessedDevice').StateDefinition {
    return {
      interfaceName: `${config.device_class}State`,
      fields: [
        {
          name: 'power',
          type: 'boolean',
          optional: true,
          description: 'Processor power state'
        },
        {
          name: 'mainVolume',
          type: 'number',
          optional: true,
          description: 'Main zone volume level'
        },
        {
          name: 'zone2Volume',
          type: 'number',
          optional: true,
          description: 'Zone 2 volume level'
        },
        {
          name: 'mainInput',
          type: 'string',
          optional: true,
          description: 'Main zone input source'
        },
        {
          name: 'zone2Input',
          type: 'string',
          optional: true,
          description: 'Zone 2 input source'
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
  
  private createZoneAwareActionHandlers(commands: Record<string, import('../../types/DeviceConfig').DeviceCommand>): import('../../types/ProcessedDevice').ActionHandler[] {
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