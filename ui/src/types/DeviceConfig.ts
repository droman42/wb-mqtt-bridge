export interface DeviceConfig {
  device_id: string;
  device_name: string;
  device_class: string;
  config_class: string;
  commands: Record<string, DeviceCommand>;
}

export interface DeviceCommand {
  action: string;
  location: string;
  rom_position?: string;
  description: string;
  group: string | null;
  params: CommandParameter[] | null;
}

export interface CommandParameter {
  name: string;
  type: 'range' | 'string' | 'integer';
  required: boolean;
  default: any;
  min: number | null;
  max: number | null;
  description: string;
}

export interface DeviceGroups {
  device_id: string;
  groups: DeviceGroup[];
}

export interface DeviceGroup {
  group_id: string;
  group_name: string;
  actions: GroupAction[];
  status: string;
}

export interface GroupAction {
  name: string;
  description: string;
  params: CommandParameter[] | null;
}

// Phase 1: Local Configuration Mode Types
export interface DeviceStateMapping {
  [deviceClass: string]: {
    stateFile: string;
    stateClass: string;
    deviceConfigs: string[];
  };
}

/**
 * Derives DeviceGroups from DeviceConfig by extracting group information 
 * embedded within device commands. This eliminates the need for a separate
 * groups API call. Matches API behavior by always including a 'default' group.
 */
export function deriveGroupsFromConfig(config: DeviceConfig): DeviceGroups {
  const groupMap = new Map<string, GroupAction[]>();
  
  // Always add 'default' group first (matches API behavior)
  groupMap.set('default', []);
  
  // Extract groups from commands
  Object.values(config.commands).forEach(command => {
    if (command.group) {
      if (!groupMap.has(command.group)) {
        groupMap.set(command.group, []);
      }
      groupMap.get(command.group)!.push({
        name: command.action,
        description: command.description,
        params: command.params
      });
    } else {
      // Commands without groups go to 'default'
      groupMap.get('default')!.push({
        name: command.action,
        description: command.description,
        params: command.params
      });
    }
  });
  
  // Build DeviceGroups structure
  return {
    device_id: config.device_id,
    groups: Array.from(groupMap.entries()).map(([groupId, actions]) => ({
      group_id: groupId,
      group_name: groupId.charAt(0).toUpperCase() + groupId.slice(1),
      actions: actions,
      status: 'active'
    }))
  };
} 