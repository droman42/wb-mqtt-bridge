export interface LastCommand {
  action: string;
  source: string;
  timestamp: string;
  params?: { [key: string]: any } | null;
}

export interface BaseDeviceState {
  device_id: string;
  device_name: string;
  last_command?: LastCommand | null;
  error?: string | null;
}

export interface DeviceStateUpdate<T = any> {
  [key: string]: T;
}

export interface StateSubscription {
  unsubscribe: () => void;
}

export type StateUpdateCallback<T extends BaseDeviceState = BaseDeviceState> = (
  newState: Partial<T>
) => void; 