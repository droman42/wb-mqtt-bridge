export interface DeviceConfig {
  device_id: string;
  device_name: string;
  device_class: string;
  config_class: string;
  commands: Record<string, DeviceCommand>;
}

export interface DeviceCommand {
  action: string;
  topic: string;
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