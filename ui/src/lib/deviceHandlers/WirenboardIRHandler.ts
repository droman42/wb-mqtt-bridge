import type { DeviceClassHandler, ProcessedAction } from '../../types/ProcessedDevice';
import type { DeviceConfig, DeviceGroups, GroupAction } from '../../types/DeviceConfig';
import type { RemoteDeviceStructure } from '../../types/RemoteControlLayout';
import { IconResolver } from '../IconResolver';
import { ZoneDetection } from '../ZoneDetection';

export class WirenboardIRHandler implements DeviceClassHandler {
  deviceClass = 'WirenboardIRDevice';
  private iconResolver = new IconResolver();
  private zoneDetection = new ZoneDetection();
  
  analyzeStructure(config: DeviceConfig, groups: DeviceGroups): RemoteDeviceStructure {
    console.log(`🎮 [WirenboardIR] Analyzing structure for ${config.device_id}`);
    
    // Generate remote control structure directly
    const remoteStructure = this.generateRemoteStructure(config, groups);
    
    console.log(`✅ [WirenboardIR] Generated remote control structure with ${remoteStructure.remoteZones.length} zones`);
    return remoteStructure;
  }

  /**
   * Phase 4: Generate remote control structure for WirenboardIR devices
   */
  private generateRemoteStructure(config: DeviceConfig, groups: DeviceGroups): RemoteDeviceStructure {
    console.log(`🔧 [WirenboardIR] Generating remote control zones for ${config.device_id}`);
    
    try {
      // Process all actions from groups
      const allActions = this.processAllGroupActions(groups);
      
      // Use zone detection to create remote zones
      const remoteZones = this.zoneDetection.analyzeDeviceGroups(groups, allActions);
      
      // Phase 3: Extract input commands for dynamic dropdown
      const inputOptions = this.extractInputCommandsForDropdown(config);
      
      // Phase 3: Populate Media Stack zone with input commands
      const mediaStackZone = remoteZones.find(zone => zone.zoneId === 'media-stack');
      if (mediaStackZone && mediaStackZone.content && inputOptions.length > 0) {
        mediaStackZone.content.inputsDropdown = {
          type: 'inputs',
          populationMethod: 'commands',
          options: inputOptions,
          loading: false,
          empty: false
        };
        console.log(`📺 [WirenboardIR] Populated Media Stack with ${inputOptions.length} input options`);
      } else if (mediaStackZone && mediaStackZone.content && inputOptions.length === 0) {
        // 🛡️ DEFENSIVE: Remove inputsDropdown if no inputs found to prevent API calls
        if (mediaStackZone.content.inputsDropdown) {
          console.log(`🛡️ [WirenboardIR] Removing inputsDropdown - no input commands found for ${config.device_id}`);
          delete mediaStackZone.content.inputsDropdown;
        }
      }
      
      console.log(`✅ [WirenboardIR] Generated ${remoteZones.length} remote control zones`);
      
      return {
        deviceId: config.device_id,
        deviceName: config.device_name,
        deviceClass: config.device_class,
        remoteZones: remoteZones,
        stateInterface: this.createBasicStateInterface(config),
        actionHandlers: this.createActionHandlers(config.commands),
        specialCases: [{
          deviceClass: 'WirenboardIRDevice',
          caseType: 'wirenboard-ir-commands',
          configuration: {
            usesCommands: true,
            inputsFromCommands: true
          }
        }]
      };
    } catch (error) {
      console.error('❌ Error generating remote structure:', error);
      throw error;
    }
  }

  /**
   * Process all group actions into ProcessedAction format
   */
  private processAllGroupActions(groups: DeviceGroups): ProcessedAction[] {
    if (!groups.groups) {
      console.log('⚠️  No groups found in device groups');
      return [];
    }
    
    const allActions: ProcessedAction[] = [];
    
    for (const group of groups.groups) {
      if (!group.actions) {
        console.log(`⚠️  No actions found in group: ${group.group_name}`);
        continue;
      }
      const groupActions = this.processGroupActions(group.actions);
      allActions.push(...groupActions);
    }
    
    console.log(`📊 Processed ${allActions.length} total actions from ${groups.groups.length} groups`);
    return allActions;
  }

  /**
   * Process group actions into ProcessedAction format
   */
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
  
  /**
   * Format action names for display
   */
  private formatDisplayName(actionName: string): string {
    // Convert snake_case or camelCase to Title Case
    return actionName
      .replace(/([a-z])([A-Z])/g, '$1 $2') // camelCase to spaces
      .replace(/_/g, ' ') // snake_case to spaces
      .split(' ')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
      .join(' ');
  }

  /**
   * Phase 3: Extract input commands for dynamic dropdown population
   * This method identifies input-related commands from WirenboardIR device commands
   */
  private extractInputCommandsForDropdown(config: DeviceConfig): import('../../types/RemoteControlLayout').DropdownOption[] {
    const inputOptions: import('../../types/RemoteControlLayout').DropdownOption[] = [];
    
    if (!config.commands) {
      console.log('⚠️  No commands found in device config');
      return inputOptions;
    }

    // Look for input-related commands in the device configuration
    const inputPatterns = [
      /^input[_-]?(\w+)$/i, // input_hdmi1, input-hdmi2, etc.
      /^(\w+)[_-]?input$/i, // hdmi_input, hdmi-input, etc.
      /^source[_-]?(\w+)$/i, // source_hdmi1, source-cable, etc.
      /^(\w+)[_-]?source$/i, // hdmi_source, cable-source, etc.
      /^(hdmi|av|component|composite|optical|coax|usb|dvd|blu[_-]?ray|cable|antenna|phono|line|aux)\d*$/i // direct input names
    ];

    Object.entries(config.commands).forEach(([commandName, command]) => {
      // Check if this command matches input patterns
      for (const pattern of inputPatterns) {
        const match = commandName.match(pattern);
        if (match) {
          const inputId = commandName;
          const displayName = this.formatInputDisplayName(commandName);
          
          inputOptions.push({
            id: inputId,
            displayName: displayName,
            description: command.description || displayName
          });
          
          console.log(`🎛️  Found input command: ${inputId} -> ${displayName}`);
          break; // Don't match the same command with multiple patterns
        }
      }
    });

    console.log(`📺 Extracted ${inputOptions.length} input options from commands`);
    return inputOptions;
  }

  /**
   * Format input command names for display
   */
  private formatInputDisplayName(commandName: string): string {
    return commandName
      .replace(/^input[_-]?/i, '') // Remove "input_" or "input-" prefix
      .replace(/[_-]?input$/i, '') // Remove "_input" or "-input" suffix
      .replace(/^source[_-]?/i, '') // Remove "source_" or "source-" prefix
      .replace(/[_-]?source$/i, '') // Remove "_source" or "-source" suffix
      .replace(/[_-]/g, ' ') // Replace underscores/hyphens with spaces
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