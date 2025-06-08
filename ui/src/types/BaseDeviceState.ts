export interface BaseDeviceState {
  isConnected: boolean;
  lastUpdated: Date | null;
  deviceId: string;
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