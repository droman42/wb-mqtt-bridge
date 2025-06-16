import { useState, useEffect, useCallback, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { BaseDeviceState, StateUpdateCallback, StateSubscription } from '../types/BaseDeviceState';
import { useDeviceState as useDeviceStateQuery, useExecuteDeviceAction } from './useApi';
import { createDefaultDeviceState, mapBackendDataToState, createStateUpdate } from '../utils/stateUtils';

interface EnhancedDeviceStateHook {
  state: BaseDeviceState;
  isLoading: boolean;
  error: Error | null;
  isConnected: boolean;
  isDisabled: boolean;
  disabledReason?: DeviceError;
  isPoweringOn: boolean;
  subscribeToState: (callback: StateUpdateCallback) => StateSubscription;
  updateState: (updates: Partial<BaseDeviceState>) => void;
  executeAction: (action: string, params?: Record<string, any>) => Promise<void>;
  setDeviceDisabled: (disabled: boolean, reason?: DeviceError) => void;
  setPoweringOn: (powering: boolean) => void;
}

type DeviceError = 'power_on_failed' | 'inputs_fetch_failed' | 'apps_fetch_failed';

export function useDeviceState(deviceId: string): EnhancedDeviceStateHook {
  const queryClient = useQueryClient();
  const { data: backendState, isLoading, error: queryError } = useDeviceStateQuery(deviceId);
  const { mutateAsync: executeDeviceAction } = useExecuteDeviceAction();
  
  // Local state management
  const [localState, setLocalState] = useState<BaseDeviceState>(() => createDefaultDeviceState(deviceId));
  const [isConnected, setIsConnected] = useState(false);
  const [isDisabled, setIsDisabled] = useState(false);
  const [disabledReason, setDisabledReason] = useState<DeviceError | undefined>();
  const [isPoweringOn, setIsPoweringOn] = useState(false);
  const subscribersRef = useRef<Set<StateUpdateCallback>>(new Set());
  
  // Update local state when backend data changes
  useEffect(() => {
    if (backendState) {
      const mappedData = mapBackendDataToState(backendState);
      
      setLocalState(prevState => {
        const newState: BaseDeviceState = {
          ...prevState,
          ...mappedData,
        };
        
        // Notify subscribers of the update
        subscribersRef.current.forEach(callback => {
          callback(mappedData);
        });
        
        return newState;
      });
      
      setIsConnected(true);
    }
  }, [backendState]);
  
  // Handle connection status based on query state
  useEffect(() => {
    if (queryError) {
      setIsConnected(false);
      setLocalState(prevState => ({
        ...prevState,
        isConnected: false,
        error: queryError.message,
      }));
    } else if (!isLoading && backendState) {
      setIsConnected(true);
    }
  }, [queryError, isLoading, backendState]);
  
  // Update deviceId if it changes
  useEffect(() => {
    setLocalState(prevState => ({
      ...prevState,
      deviceId,
    }));
  }, [deviceId]);
  
  // Subscribe to state changes
  const subscribeToState = useCallback((callback: StateUpdateCallback): StateSubscription => {
    subscribersRef.current.add(callback);
    
    return {
      unsubscribe: () => {
        subscribersRef.current.delete(callback);
      },
    };
  }, []);
  
  // Update state locally and optionally sync to backend
  const updateState = useCallback((updates: Partial<BaseDeviceState>) => {
    setLocalState(prevState => {
      const newState = createStateUpdate(prevState, updates);
      
      // Notify subscribers
      subscribersRef.current.forEach(callback => {
        callback(updates);
      });
      
      return newState;
    });
    
    // Invalidate React Query cache to trigger refetch
    if (updates.device_id || updates.device_name || updates.last_command || updates.error) {
      queryClient.invalidateQueries({ queryKey: ['devices', deviceId, 'state'] });
    }
  }, [deviceId, queryClient]);
  
  // Execute device action and update state
  const executeAction = useCallback(async (action: string, params?: Record<string, any>) => {
    try {
      const result = await executeDeviceAction({
        deviceId,
        action: { action, params },
      });
      
             // Update local state with the result
       if (result.state) {
         const mappedData = mapBackendDataToState(result.state);
        updateState({
          ...mappedData,
          last_command: {
            action,
            source: 'frontend',
            timestamp: new Date().toISOString(),
            params: params || null,
          },
          error: result.error || null,
        });
      }
    } catch (error) {
      // Update state with error
      updateState({
        error: error instanceof Error ? error.message : 'Action execution failed',
        last_command: {
          action,
          source: 'frontend',
          timestamp: new Date().toISOString(),
          params: params || null,
        },
      });
      throw error;
    }
  }, [deviceId, executeDeviceAction, updateState]);
  
  // Helper methods for managing device state
  const setDeviceDisabled = useCallback((disabled: boolean, reason?: DeviceError) => {
    setIsDisabled(disabled);
    setDisabledReason(reason);
  }, []);

  const setPoweringOn = useCallback((powering: boolean) => {
    setIsPoweringOn(powering);
  }, []);

  return {
    state: localState,
    isLoading,
    error: queryError,
    isConnected,
    isDisabled,
    disabledReason,
    isPoweringOn,
    subscribeToState,
    updateState,
    executeAction,
    setDeviceDisabled,
    setPoweringOn,
  };
} 