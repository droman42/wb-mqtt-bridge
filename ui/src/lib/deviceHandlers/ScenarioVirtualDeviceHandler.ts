import type { DeviceConfig, DeviceGroups, DeviceGroup } from '../../types/DeviceConfig';
import type { RemoteDeviceStructure } from '../../types/RemoteControlLayout';
import type { ProcessedAction, ActionIcon, ActionHandler } from '../../types/ProcessedDevice';
import { ZoneDetection } from '../ZoneDetection';
import { IconResolver } from '../IconResolver';
import { LocalDeviceConfigurationClient } from '../DeviceConfigurationClient';
import type { IDeviceConfigurationClient } from '../DeviceConfigurationClient';
import { WirenboardIRHandler } from './WirenboardIRHandler';
import { LgTvHandler } from './LgTvHandler';
import { EMotivaXMC2Handler } from './EMotivaXMC2Handler';
import { BroadlinkKitchenHoodHandler } from './BroadlinkKitchenHoodHandler';
import { AppleTVDeviceHandler } from './AppleTVDeviceHandler';
import { AuralicDeviceHandler } from './AuralicDeviceHandler';
import { RevoxA77ReelToReelHandler } from './RevoxA77ReelToReelHandler';
import * as fs from 'fs/promises';
import { readFileSync } from 'fs';

export interface ScenarioConfig {
  scenario_id: string;
  name: string;
  description: string;
  room_id: string;
  roles: Record<string, string>; // role -> device_id mapping
  devices: string[];
  startup_sequence: any[];
  shutdown_sequence: any[];
  manual_instructions?: {
    startup?: string[];
    shutdown?: string[];
  };
}

export class ScenarioVirtualDeviceHandler {
  public readonly deviceClass = 'ScenarioDevice';
  private zoneDetection = new ZoneDetection();
  private iconResolver = new IconResolver();
  private client: IDeviceConfigurationClient;
  private deviceHandlers: Map<string, any>;

  constructor(client?: IDeviceConfigurationClient) {
    // Use provided client or create a default one
    this.client = client || new LocalDeviceConfigurationClient('config/device-state-mapping.json');
    
    // Initialize device handlers
    this.deviceHandlers = new Map<string, any>();
    this.deviceHandlers.set('WirenboardIRDevice', new WirenboardIRHandler());
    this.deviceHandlers.set('LgTv', new LgTvHandler());
    this.deviceHandlers.set('EMotivaXMC2', new EMotivaXMC2Handler());
    this.deviceHandlers.set('BroadlinkKitchenHood', new BroadlinkKitchenHoodHandler());
    this.deviceHandlers.set('AppleTVDevice', new AppleTVDeviceHandler());
    this.deviceHandlers.set('AuralicDevice', new AuralicDeviceHandler());
    this.deviceHandlers.set('RevoxA77ReelToReel', new RevoxA77ReelToReelHandler());
  }

  /**
   * Read device config file directly from disk using the mapping file
   */
  private async readDeviceConfigFile(deviceId: string): Promise<DeviceConfig> {
    try {
      // Use the existing LocalDeviceConfigurationClient logic to find the config path
      const mapping = await this.loadMapping();
      const configPath = this.findConfigPathByDeviceId(mapping, deviceId);
      
      // Read and parse the config file
      const data = await fs.readFile(configPath, 'utf8');
      const config = JSON.parse(data);
      
      // Validate that device_id matches what we're looking for
      if (config.device_id !== deviceId) {
        throw new Error(`Device ID mismatch: expected '${deviceId}', found '${config.device_id}' in ${configPath}`);
      }
      
      return config;
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      throw new Error(`Failed to read device config for ${deviceId}: ${errorMessage}`);
    }
  }

  /**
   * Load the device state mapping file
   */
  private async loadMapping(): Promise<Record<string, any>> {
    try {
      const mappingFile = (this.client as any).mappingFile || 'config/device-state-mapping.json';
      const data = await fs.readFile(mappingFile, 'utf8');
      return JSON.parse(data);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      throw new Error(`Failed to load mapping file: ${errorMessage}`);
    }
  }

  /**
   * Find device config file path by searching through all deviceConfigs arrays
   */
  private findConfigPathByDeviceId(mapping: Record<string, any>, deviceId: string): string {
    // Search all deviceConfigs arrays for matching device_id
    for (const [_deviceClass, classInfo] of Object.entries(mapping)) {
      // Skip device classes without deviceConfigs
      if (!classInfo || typeof classInfo !== 'object' || !classInfo.deviceConfigs || !Array.isArray(classInfo.deviceConfigs)) {
        continue;
      }
      
      for (const configPath of classInfo.deviceConfigs) {
        try {
          const configData = JSON.parse(readFileSync(configPath, 'utf8'));
          if (configData.device_id === deviceId) {
            return configPath;
          }
        } catch (error) {
          // Skip invalid config files and continue searching
          console.warn(`Warning: Could not read config file ${configPath}: ${error instanceof Error ? error.message : String(error)}`);
          continue;
        }
      }
    }
    throw new Error(`Device config not found for device_id: ${deviceId}`);
  }

  async analyzeStructure(config: DeviceConfig, groups: DeviceGroups): Promise<RemoteDeviceStructure> {
    console.log(`🎮 [ScenarioDevice] Analyzing virtual device structure for ${config.device_id}`);

    // Extract scenario config from device config
    const scenarioRoles = this.extractScenarioRoles(config);
    
    // Process scenario device actions with inheritance from source devices
    const allActions = await this.processScenarioDeviceActions(config, groups, scenarioRoles);
    
    // Use zone detection to generate standard remote zones  
    const remoteZones = this.zoneDetection.analyzeDeviceGroups(this.createDeviceGroupsFromActions(allActions), allActions);
    
    // Restore inherited zone content that may have been lost during zone detection
    await this.restoreInheritedZoneContent(remoteZones, scenarioRoles);

    // Apply enablement to zones (all inherited zones should be enabled, except inputs)
    this.applyInheritanceBasedEnablement(remoteZones, scenarioRoles);

    console.log(`🎯 [ScenarioDevice] Generated ${remoteZones.length} scenario control zones`);

    return {
      deviceId: config.device_id,
      deviceName: config.device_name,
      deviceClass: this.deviceClass,
      remoteZones,
      stateInterface: {
        interfaceName: `${config.device_id}ScenarioState`,
        fields: [
          {
            name: 'scenario_active',
            type: 'boolean',
            optional: false,
            description: 'Whether the scenario is currently active'
          },
          {
            name: 'last_scenario_action',
            type: 'string',
            optional: true,
            description: 'Last scenario action executed'
          }
        ],
        imports: ['BaseDeviceState'],
        extends: ['BaseDeviceState']
      },
      actionHandlers: this.createScenarioActionHandlers(config),
      specialCases: [{
        deviceClass: this.deviceClass,
        caseType: 'lg-tv-inputs-apps',
        configuration: { 
          scenarioBased: true,
          powerGroupMapsToScenario: true,
          selectiveEnablement: true
        }
      }]
    };
  }

  private extractScenarioRoles(config: DeviceConfig): Record<string, string> {
    // Extract roles from config commands that have location field
    const roles: Record<string, string> = {};
    
    Object.entries(config.commands || {}).forEach(([commandKey, command]) => {
      if (command.location && command.group && command.group !== 'power') {
        roles[command.group] = command.location;
      }
    });
    
    console.log(`📋 [ScenarioDevice] Extracted roles:`, roles);
    return roles;
  }

  private async processScenarioDeviceActions(
    config: DeviceConfig, 
    groups: DeviceGroups, 
    scenarioRoles: Record<string, string>
  ): Promise<ProcessedAction[]> {
    const actions: ProcessedAction[] = [];

    // Add scenario power actions (always scenario-specific)
    actions.push({
      actionName: 'power_on',
      displayName: 'Start Scenario',
      description: `Start ${config.device_name}`,
      parameters: [],
      group: 'power',
      icon: this.iconResolver.selectIconForAction('power_on'),
      uiHints: { buttonStyle: 'primary' }
    });

    actions.push({
      actionName: 'power_off',
      displayName: 'Stop Scenario',
      description: `Stop ${config.device_name}`,
      parameters: [],
      group: 'power',
      icon: this.iconResolver.selectIconForAction('power_off'),
      uiHints: { buttonStyle: 'secondary' }
    });

    // For each group that has a role mapping, inherit from source device (skip inputs)
    for (const [groupId, deviceId] of Object.entries(scenarioRoles)) {
      // Skip inputs group - it's for backend sequencing, not UI
      if (groupId === 'inputs') {
        console.log(`⏭️ [ScenarioDevice] Skipping '${groupId}' group (not shown in UI)`);
        continue;
      }
      
      try {
        console.log(`🔄 [ScenarioDevice] Inheriting group '${groupId}' from device '${deviceId}'`);
        const inheritedActions = await this.inheritGroupFromDevice(groupId, deviceId);
        actions.push(...inheritedActions);
        console.log(`✅ [ScenarioDevice] Inherited ${inheritedActions.length} actions from '${deviceId}' for group '${groupId}'`);
      } catch (error) {
        console.error(`❌ [ScenarioDevice] Failed to inherit group '${groupId}' from device '${deviceId}':`, error);
        // Fall back to processing from config
        this.processGroupFromConfig(config, groupId, actions);
      }
    }

    // Process any remaining commands from config that don't have role mappings
    Object.entries(config.commands || {}).forEach(([commandKey, command]) => {
      // Skip power commands and commands that were already inherited
      if (commandKey === 'power_on' || commandKey === 'power_off') {
        return;
      }
      
      const groupId = command.group || 'controls';
      if (!scenarioRoles[groupId]) {
        // This group doesn't have a role mapping, process as-is
        actions.push({
          actionName: commandKey,
          displayName: command.description || commandKey,
          description: command.description || `Control: ${commandKey}`,
          parameters: this.convertParamsToParameters(command.params || []),
          group: groupId,
          icon: this.getIconForScenarioAction(commandKey, groupId, command.location),
          uiHints: { hasParameters: !!(command.params && command.params.length > 0) }
        });
      }
    });

    console.log(`📊 [ScenarioDevice] Processed ${actions.length} total scenario device actions`);
    return actions;
  }

  private async inheritGroupFromDevice(groupId: string, deviceId: string): Promise<ProcessedAction[]> {
    try {
      // Read source device configuration directly from files
      const sourceConfig = await this.readDeviceConfigFile(deviceId);
      
      console.log(`📡 [ScenarioDevice] Read config for source device '${deviceId}', class: ${sourceConfig.device_class}`);

      // Get the appropriate device handler for the source device
      const sourceHandler = this.deviceHandlers.get(sourceConfig.device_class);
      if (!sourceHandler) {
        throw new Error(`No handler found for device class: ${sourceConfig.device_class}`);
      }

      console.log(`🔧 [ScenarioDevice] Using ${sourceConfig.device_class} handler for inheritance`);

      // Find commands in the source device that belong to the target group
      const groupCommands = Object.entries(sourceConfig.commands || {})
        .filter(([_, command]) => command.group === groupId)
        .map(([commandName, command]) => ({ commandName, command }));

      console.log(`🔍 [ScenarioDevice] Found ${groupCommands.length} commands in '${groupId}' group from ${deviceId}`);

      if (groupCommands.length === 0) {
        console.log(`⚠️ [ScenarioDevice] No commands found in group '${groupId}' for device '${deviceId}'`);
        return [];
      }

      // Convert device commands to ProcessedActions using the device handler's logic
      const actions: ProcessedAction[] = [];
      
      for (const { commandName, command } of groupCommands) {
        // Create a ProcessedAction from the device command
        const action: ProcessedAction = {
          actionName: commandName,
          displayName: command.description || commandName,
          description: command.description || `${commandName} control`,
          parameters: this.convertParamsToParameters(command.params || []),
          group: groupId,
          icon: this.iconResolver.selectIconForAction(commandName),
          uiHints: { 
            hasParameters: !!(command.params && command.params.length > 0),
            buttonSize: 'medium',
            buttonStyle: 'secondary'
          }
        };
        
        actions.push(action);
        console.log(`✅ [ScenarioDevice] Inherited command '${commandName}' from ${deviceId}`);
      }

      return actions;
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      console.error(`❌ [ScenarioDevice] Failed to inherit group '${groupId}' from device '${deviceId}': ${errorMessage}`);
      throw error;
    }
  }

  /**
   * Check if zone content suggests it contains actions for the target group
   */
  private zoneContainsGroup(content: any, groupId: string): boolean {
    if (!content) return false;
    
    // Check for common content patterns that suggest the zone contains our target group
    const groupPatterns: Record<string, string[]> = {
      'volume': ['volumeButtons', 'volumeSlider'],
      'playback': ['playbackSection', 'playbackButtons'],
      'tracks': ['tracksSection', 'trackButtons'],
      'navigation': ['navigationCluster', 'navButtons'],
      'menu': ['navigationCluster', 'menuButtons'],
      'apps': ['appsDropdown', 'appButtons'],
      'screen': ['screenActions', 'screenButtons'],
      'pointer': ['pointerPad']
    };
    
    const patterns = groupPatterns[groupId] || [groupId];
    return patterns.some(pattern => content[pattern]);
  }

  /**
   * Extract actions from a zone for a specific group
   */
  private extractActionsFromZone(zone: any, groupId: string): ProcessedAction[] {
    const actions: ProcessedAction[] = [];
    
    if (!zone.content) {
      console.log(`⚠️ [ScenarioDevice] Zone '${zone.zoneId}' has no content to extract actions from`);
      return actions;
    }

    // Extract actions from all content sections that have actions
    Object.entries(zone.content).forEach(([contentKey, contentValue]: [string, any]) => {
      
      if (contentValue && typeof contentValue === 'object') {
        // Extract direct actions array (for playbackSection, tracksSection)
        if (contentValue.actions && Array.isArray(contentValue.actions)) {
          actions.push(...contentValue.actions.map((action: any) => ({
            ...action,
            group: groupId // Ensure group is set correctly for inheritance
          })));
        }
        
        // Extract actions from volumeButtons array
        if (contentKey === 'volumeButtons' && Array.isArray(contentValue)) {
          contentValue.forEach((volumeButton: any, index: number) => {
            ['upAction', 'downAction', 'muteAction'].forEach(actionKey => {
              if (volumeButton[actionKey]) {
                actions.push({
                  ...volumeButton[actionKey],
                  group: groupId
                });
              }
            });
          });
        }
        
        // Extract actions from volumeSlider
        if (contentKey === 'volumeSlider' && contentValue.action) {
          actions.push({
            ...contentValue.action,
            group: groupId
          });
          if (contentValue.muteAction) {
            actions.push({
              ...contentValue.muteAction,
              group: groupId
            });
          }
        }
        
        // Extract actions from navigation clusters
        if (contentKey.includes('navigation') || contentKey.includes('nav')) {
          ['upAction', 'downAction', 'leftAction', 'rightAction', 'okAction', 'backAction', 'homeAction', 'menuAction', 'exitAction'].forEach(actionKey => {
            if (contentValue[actionKey]) {
              actions.push({
                ...contentValue[actionKey],
                group: groupId
              });
            }
          });
        }
        
        // Extract actions from dropdown options (like apps)
        if (contentValue.options && Array.isArray(contentValue.options)) {
          contentValue.options.forEach((option: any) => {
            actions.push({
              actionName: option.id || option.actionName,
              displayName: option.displayName || option.name,
              description: option.description || option.displayName || option.name,
              parameters: option.parameters || [],
              group: groupId,
              icon: option.icon || { iconLibrary: 'material', iconName: 'Apps', iconVariant: 'outlined', fallbackIcon: 'apps', confidence: 0.8 },
              uiHints: option.uiHints || { buttonSize: 'medium', buttonStyle: 'secondary' }
            });
          });
        }
        
        // Handle any nested actions in sub-objects
        if (contentValue.action) {
          actions.push({
            ...contentValue.action,
            group: groupId
          });
        }
      }
    });

    return actions;
  }

  private processGroupFromConfig(config: DeviceConfig, groupId: string, actions: ProcessedAction[]): void {
    // Fallback processing for groups without role mappings
    Object.entries(config.commands || {}).forEach(([commandKey, command]) => {
      if (command.group === groupId) {
        actions.push({
          actionName: commandKey,
          displayName: command.description || commandKey,
          description: command.description || `Control: ${commandKey}`,
          parameters: this.convertParamsToParameters(command.params || []),
          group: groupId,
          icon: this.getIconForScenarioAction(commandKey, groupId, command.location),
          uiHints: { hasParameters: !!(command.params && command.params.length > 0) }
        });
      }
    });
  }

  private async restoreInheritedZoneContent(remoteZones: any[], scenarioRoles: Record<string, string>): Promise<void> {
    console.log(`🔄 [ScenarioDevice] Restoring inherited zone content for roles:`, scenarioRoles);
    
    // Since inheritance now works through proper device handler zone structures,
    // this method primarily ensures zone content is preserved after zone detection
    for (const [groupId, sourceDeviceId] of Object.entries(scenarioRoles)) {
      // Skip inputs group as it's not shown in UI
      if (groupId === 'inputs') {
        continue;
      }
      
      try {
        console.log(`🔄 [ScenarioDevice] Ensuring ${groupId} zone content from ${sourceDeviceId}`);
        
        // Find the zone for this group in the scenario structure
        let targetZone = remoteZones.find(zone => zone.zoneId === groupId);
        if (!targetZone && (groupId === 'playback' || groupId === 'tracks')) {
          targetZone = remoteZones.find(zone => zone.zoneId === 'media-stack');
        }
        
        if (!targetZone) {
          console.log(`⚠️  [ScenarioDevice] No ${groupId} zone found to restore`);
          continue;
        }

        // If the zone already has content from inheritance, we're good
        if (targetZone.content && Object.keys(targetZone.content).length > 0) {
          console.log(`✅ [ScenarioDevice] Zone '${groupId}' already has content from inheritance`);
          continue;
        }

        // If zone is missing content, regenerate it from the source device
        const sourceConfig = await this.readDeviceConfigFile(sourceDeviceId);
        const { deriveGroupsFromConfig } = await import('../../types/DeviceConfig');
        const sourceGroups = deriveGroupsFromConfig(sourceConfig);
        
        const sourceHandler = this.deviceHandlers.get(sourceConfig.device_class);
        if (!sourceHandler) {
          console.warn(`⚠️  [ScenarioDevice] No handler found for device class: ${sourceConfig.device_class}`);
          continue;
        }

        const sourceStructure = sourceHandler.analyzeStructure(sourceConfig, sourceGroups);
        
        // Find the source zone and copy its content
        let sourceZone = sourceStructure.remoteZones.find((zone: any) => zone.zoneId === groupId);
        if (!sourceZone && (groupId === 'playback' || groupId === 'tracks')) {
          sourceZone = sourceStructure.remoteZones.find((zone: any) => zone.zoneId === 'media-stack');
        }

        if (sourceZone?.content) {
          targetZone.content = { ...sourceZone.content };
          console.log(`✅ [ScenarioDevice] Restored content for ${groupId} zone`);
        } else {
          console.log(`⚠️  [ScenarioDevice] No source content found for ${groupId}`);
        }

      } catch (error) {
        console.error(`❌ [ScenarioDevice] Error restoring ${groupId} zone content:`, error);
      }
    }
  }

  private applyInheritanceBasedEnablement(remoteZones: any[], scenarioRoles: Record<string, string>): void {
    console.log(`🔧 [ScenarioDevice] Applying inheritance-based enablement for roles:`, scenarioRoles);
    
    remoteZones.forEach(zone => {
      if (zone.zoneId === 'power') {
        // Power zone always enabled for scenarios
        zone.enabled = true;
        console.log(`✅ [ScenarioDevice] Power zone enabled`);
      } else if (zone.zoneId === 'media-stack') {
        // Media-stack zone enabled if playback or tracks are inherited
        zone.enabled = !!(scenarioRoles['playback'] || scenarioRoles['tracks']);
        const status = zone.enabled ? '✅' : '❌';
        console.log(`${status} [ScenarioDevice] Media-stack zone ${zone.enabled ? 'enabled' : 'disabled'} (playback: ${scenarioRoles['playback']}, tracks: ${scenarioRoles['tracks']})`);
      } else if (zone.zoneId === 'menu') {
        // Menu zone enabled if navigation or menu is inherited
        zone.enabled = !!(scenarioRoles['navigation'] || scenarioRoles['menu']);
        const status = zone.enabled ? '✅' : '❌';
        console.log(`${status} [ScenarioDevice] Menu zone ${zone.enabled ? 'enabled' : 'disabled'} (navigation: ${scenarioRoles['navigation']}, menu: ${scenarioRoles['menu']})`);
      } else {
        // All other zones enabled if corresponding group is inherited (except inputs)
        zone.enabled = !!scenarioRoles[zone.zoneId] && zone.zoneId !== 'inputs';
        const status = zone.enabled ? '✅' : '❌';
        console.log(`${status} [ScenarioDevice] Zone '${zone.zoneId}' ${zone.enabled ? 'enabled' : 'disabled'} (inherited from: ${scenarioRoles[zone.zoneId] || 'none'})`);
      }
    });
  }

  private getIconForScenarioAction(actionName: string, group: string, sourceDevice?: string): ActionIcon {
    // Use IconResolver for the action first (this handles device-specific mappings)
    let icon = this.iconResolver.selectIconForAction(actionName);
    
    // If IconResolver doesn't have a good match (low confidence), use device-specific logic
    if (icon.confidence < 0.7) {
      icon = this.getDeviceSpecificIcon(actionName, group, sourceDevice);
    }
    
    return icon;
  }

  private getDeviceSpecificIcon(actionName: string, group: string, sourceDevice?: string): ActionIcon {
    // Device-specific icon mappings based on source device type
    // This mimics what each device handler would do for the same action
    
    const cleanName = actionName.toLowerCase();
    
    // TV-specific actions (LG TV, etc.)
    if (sourceDevice?.includes('tv')) {
      if (cleanName.includes('input')) return { iconLibrary: 'material', iconName: 'Input', iconVariant: 'outlined', fallbackIcon: 'input', confidence: 0.9 };
      if (cleanName.includes('channel')) return { iconLibrary: 'material', iconName: 'Tag', iconVariant: 'outlined', fallbackIcon: 'channel', confidence: 0.9 };
      if (cleanName.includes('aspect')) return { iconLibrary: 'custom', iconName: 'aspect-ratio', iconVariant: 'outlined', fallbackIcon: 'aspect-ratio', confidence: 0.9 };
    }
    
    // Apple TV specific actions
    if (sourceDevice?.includes('appletv')) {
      if (cleanName.includes('siri')) return { iconLibrary: 'material', iconName: 'Mic', iconVariant: 'outlined', fallbackIcon: 'microphone', confidence: 0.9 };
      if (cleanName.includes('airplay')) return { iconLibrary: 'material', iconName: 'Cast', iconVariant: 'outlined', fallbackIcon: 'wifi', confidence: 0.9 };
      if (cleanName.includes('app')) return { iconLibrary: 'material', iconName: 'Apps', iconVariant: 'outlined', fallbackIcon: 'apps', confidence: 0.9 };
    }
    
    // Audio device specific actions (amplifier, streamer, etc.)
    if (sourceDevice?.includes('amplifier') || sourceDevice?.includes('streamer')) {
      if (cleanName.includes('input')) return { iconLibrary: 'material', iconName: 'Input', iconVariant: 'outlined', fallbackIcon: 'input', confidence: 0.9 };
      if (cleanName.includes('preset')) return { iconLibrary: 'material', iconName: 'Bookmark', iconVariant: 'outlined', fallbackIcon: 'preset', confidence: 0.9 };
      if (cleanName.includes('filter')) return { iconLibrary: 'material', iconName: 'FilterList', iconVariant: 'outlined', fallbackIcon: 'filter', confidence: 0.9 };
    }
    
    // Fall back to group-based mapping with proper IconResolver usage
    return this.getIconForGroup(group);
  }

  private getIconForGroup(group: string): ActionIcon {
    // Use IconResolver for consistent group-based mapping
    const groupActions: Record<string, string> = {
      'power': 'power',
      'volume': 'volume_up', 
      'playback': 'play',
      'navigation': 'up',
      'tracks': 'next',
      'menu': 'menu',
      'screen': 'input',
      'controls': 'settings'
    };
    
    const actionName = groupActions[group] || 'settings';
    return this.iconResolver.selectIconForAction(actionName);
  }

  private createScenarioActionHandlers(config: DeviceConfig): ActionHandler[] {
    return [{
      actionName: 'scenario_activate',
      handlerCode: `executeDeviceAction(${JSON.stringify(config.device_id)}, 'scenario_activate')`,
      dependencies: ['executeDeviceAction']
    }];
  }

  private createDeviceGroupsFromActions(actions: ProcessedAction[]): DeviceGroups {
    const groupsMap: Record<string, DeviceGroup> = {};
    
    actions.forEach(action => {
      if (!groupsMap[action.group]) {
        groupsMap[action.group] = {
          group_id: action.group,
          group_name: action.group,
          actions: [],
          status: 'active'
        };
      }
      groupsMap[action.group].actions.push({
        name: action.actionName,
        description: action.description,
        params: action.parameters
          .filter(p => ['string', 'range', 'integer'].includes(p.type))
          .map(p => ({
            name: p.name,
            type: p.type as 'string' | 'range' | 'integer',
            required: p.required,
            default: p.default,
            min: p.min ?? null,
            max: p.max ?? null,
            description: p.description
          }))
      });
    });
    
    return {
      device_id: 'scenario_virtual_device',
      groups: Object.values(groupsMap)
    };
  }


  private convertParamsToParameters(params: any[]): any[] {
    return params.map(param => ({
      name: param.name || 'value',
      type: param.type || 'string',
      required: param.required || false,
      default: param.default,
      min: param.min,
      max: param.max,
      description: param.description || `Parameter: ${param.name}`
    }));
  }

  private mapCommandToComponent(command: any): 'button' | 'slider' | 'input' {
    if (command.params && command.params.length > 0) {
      const param = command.params[0];
      switch (param.type) {
        case 'range':
        case 'integer':
          return 'slider';
        case 'string':
          return 'input';
        default:
          return 'button';
      }
    }
    return 'button';
  }

  private extractScenarioControlActions(config: DeviceConfig): any[] {
    const actions: any[] = [];
    
    // Add standard scenario control actions
    actions.push({
      id: 'scenario_activate',
      name: 'Activate Scenario',
      description: 'Activate this virtual scenario',
      type: 'button',
      group: 'scenario-control',
      params: {},
      className: 'scenario-activate-btn',
      variant: 'default'
    });

    actions.push({
      id: 'scenario_deactivate',
      name: 'Deactivate Scenario',
      description: 'Deactivate this virtual scenario',
      type: 'button',
      group: 'scenario-control',
      params: {},
      className: 'scenario-deactivate-btn',
      variant: 'outline'
    });

    // Extract any scenario-specific commands from config
    Object.entries(config.commands || {}).forEach(([commandKey, command]) => {
      if (this.isScenarioControlCommand(commandKey, command)) {
        actions.push({
          id: commandKey,
          name: command.description || commandKey,
          description: command.description || `Virtual scenario command: ${commandKey}`,
          type: 'button',
          group: 'scenario-control',
          params: command.params || {},
          className: 'scenario-command-btn'
        });
      }
    });

    return actions;
  }

  private extractVirtualCommandActions(config: DeviceConfig): any[] {
    const actions: any[] = [];

    Object.entries(config.commands || {}).forEach(([commandKey, command]) => {
      if (this.isVirtualCommand(commandKey, command)) {
        actions.push({
          id: commandKey,
          name: command.description || commandKey,
          description: command.description || `Virtual command: ${commandKey}`,
          type: this.mapCommandType(command),
          group: 'virtual-commands',
          params: command.params || {},
          className: 'virtual-command-control'
        });
      }
    });

    return actions;
  }

  private extractStatusActions(config: DeviceConfig): any[] {
    const actions: any[] = [];

    // Add virtual device status display
    actions.push({
      id: 'scenario_status',
      name: 'Scenario Status',
      description: 'Current scenario activation status',
      type: 'display',
      group: 'status',
      params: {},
      className: 'scenario-status-display'
    });

    actions.push({
      id: 'virtual_controls_status',
      name: 'Virtual Controls Status',
      description: 'Status of virtual WB controls',
      type: 'display',
      group: 'status',
      params: {},
      className: 'virtual-controls-status-display'
    });

    // Extract status-related commands
    Object.entries(config.commands || {}).forEach(([commandKey, command]) => {
      if (this.isStatusCommand(commandKey, command)) {
        actions.push({
          id: commandKey,
          name: command.description || commandKey,
          description: command.description || `Status: ${commandKey}`,
          type: 'display',
          group: 'status',
          params: command.params || {},
          className: 'status-display-item'
        });
      }
    });

    return actions;
  }

  private hasVirtualCommands(config: DeviceConfig): boolean {
    return Object.entries(config.commands || {}).some(([key, command]) => 
      this.isVirtualCommand(key, command)
    );
  }

  private isScenarioControlCommand(key: string, command: any): boolean {
    const scenarioKeywords = ['scenario', 'activate', 'deactivate', 'switch', 'startup', 'shutdown'];
    const keyLower = key.toLowerCase();
    
    return scenarioKeywords.some(keyword => 
      keyLower.includes(keyword) || 
      (command.description && command.description.toLowerCase().includes(keyword))
    );
  }

  private isVirtualCommand(key: string, command: any): boolean {
    const virtualKeywords = ['virtual', 'wb_', 'control', 'set_', 'get_'];
    const keyLower = key.toLowerCase();
    
    return virtualKeywords.some(keyword => 
      keyLower.includes(keyword) || 
      (command.description && command.description.toLowerCase().includes(keyword))
    ) && !this.isScenarioControlCommand(key, command) && !this.isStatusCommand(key, command);
  }

  private isStatusCommand(key: string, command: any): boolean {
    const statusKeywords = ['status', 'state', 'get_', 'read_', 'check_'];
    const keyLower = key.toLowerCase();
    
    return statusKeywords.some(keyword => 
      keyLower.includes(keyword) || 
      (command.description && command.description.toLowerCase().includes(keyword))
    );
  }

  private mapCommandType(command: any): string {
    // Map command properties to UI component types
    if (command.params && command.params.length > 0) {
      const param = command.params[0];
      
      switch (param.type) {
        case 'range':
        case 'integer':
          return 'slider';
        case 'string':
          return 'input';
        default:
          return 'button';
      }
    }
    
    return 'button';
  }
} 