export interface LastCommand {
  action: string;
  source: string;
  timestamp: string;
  params?: { [key: string]: any } | null;
}

export interface BaseDeviceState {
  deviceId: string;
  deviceName: string;
  lastCommand?: LastCommand | null;
  error?: string | null;
  isConnected: boolean;
  lastUpdated: Date | null;
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