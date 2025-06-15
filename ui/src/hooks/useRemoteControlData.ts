import { useState, useEffect, useCallback } from 'react';
import { useExecuteDeviceAction } from './useApi';
import type { DropdownOption, RemoteDeviceStructure } from '../types/RemoteControlLayout';

interface UseInputsDataResult {
  inputs: DropdownOption[];
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

interface UseAppsDataResult {
  apps: DropdownOption[];
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

/**
 * Hook for fetching available inputs for a device
 * Handles both WirenboardIR (commands) and other device classes (API actions)
 */
export function useInputsData(deviceStructure: RemoteDeviceStructure): UseInputsDataResult {
  const [inputs, setInputs] = useState<DropdownOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const executeAction = useExecuteDeviceAction();

  const fetchInputs = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const { deviceId, deviceClass, specialCases } = deviceStructure;
      
      // Check if this is a WirenboardIR device with special handling
      const isWirenboardIR = deviceClass === 'WirenboardIRDevice';
      const usesCommands = specialCases?.some(
        sc => sc.caseType === 'wirenboard-ir-commands' && sc.configuration.inputsFromCommands
      );

      if (isWirenboardIR && usesCommands) {
        // For WirenboardIR: Extract inputs from device commands
        // This would be populated during zone detection phase
        const inputsZone = deviceStructure.remoteZones.find(zone => zone.zoneId === 'media-stack');
        const inputsFromCommands = inputsZone?.content?.inputsDropdown?.options || [];
        setInputs(inputsFromCommands);
      } else {
        // For other device classes: Use get_available_inputs device action
        const response = await executeAction.mutateAsync({
          deviceId,
          action: { action: 'get_available_inputs', params: {} }
        });

        if (response && response.data) {
          // Expected format: [{ input_id: "hdmi1", input_name: "HDMI 1" }, ...]
          const inputOptions: DropdownOption[] = response.data.map((item: any) => ({
            id: item.input_id,
            displayName: item.input_name,
            description: item.description || item.input_name
          }));
          setInputs(inputOptions);
        } else {
          setInputs([]);
        }
      }
    } catch (err) {
      console.error('Failed to fetch inputs:', err);
      setError(err instanceof Error ? err.message : 'Failed to fetch inputs');
      setInputs([]);
    } finally {
      setLoading(false);
    }
  }, [deviceStructure, executeAction]);

  const refetch = useCallback(() => {
    fetchInputs();
  }, [fetchInputs]);

  useEffect(() => {
    fetchInputs();
  }, [fetchInputs]);

  return { inputs, loading, error, refetch };
}

/**
 * Hook for fetching available apps for a device
 * Uses get_available_apps device action for all device classes
 */
export function useAppsData(deviceStructure: RemoteDeviceStructure): UseAppsDataResult {
  const [apps, setApps] = useState<DropdownOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const executeAction = useExecuteDeviceAction();

  const fetchApps = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const { deviceId } = deviceStructure;
      
      // Use get_available_apps device action
      const response = await executeAction.mutateAsync({
        deviceId,
        action: { action: 'get_available_apps', params: {} }
      });

      if (response && response.data) {
        // Expected format: [{ app_id: "youtube.leanback.v4", app_name: "YouTube" }, ...]
        const appOptions: DropdownOption[] = response.data.map((item: any) => ({
          id: item.app_id,
          displayName: item.app_name,
          description: item.description || item.app_name
        }));
        setApps(appOptions);
      } else {
        setApps([]);
      }
    } catch (err) {
      console.error('Failed to fetch apps:', err);
      setError(err instanceof Error ? err.message : 'Failed to fetch apps');
      setApps([]);
    } finally {
      setLoading(false);
    }
  }, [deviceStructure, executeAction]);

  const refetch = useCallback(() => {
    fetchApps();
  }, [fetchApps]);

  useEffect(() => {
    fetchApps();
  }, [fetchApps]);

  return { apps, loading, error, refetch };
}

/**
 * Hook for handling input selection
 */
export function useInputSelection(deviceStructure: RemoteDeviceStructure) {
  const [selectedInput, setSelectedInput] = useState<string>('');
  const executeAction = useExecuteDeviceAction();

  const selectInput = async (inputId: string) => {
    setSelectedInput(inputId);
    
    try {
      const { deviceId, deviceClass } = deviceStructure;
      const isWirenboardIR = deviceClass === 'WirenboardIRDevice';

      if (isWirenboardIR) {
        // For WirenboardIR: Execute the specific input command directly
        await executeAction.mutateAsync({
          deviceId,
          action: { action: inputId, params: {} }
        });
      } else {
        // For other device classes: Use set_input action
        await executeAction.mutateAsync({
          deviceId,
          action: { action: 'set_input', params: { input: inputId } }
        });
      }
    } catch (err) {
      console.error('Failed to select input:', err);
      // Optionally reset selection on error
      setSelectedInput('');
      throw err;
    }
  };

  return { selectedInput, selectInput, setSelectedInput };
}

/**
 * Hook for handling app launching
 */
export function useAppLaunching(deviceStructure: RemoteDeviceStructure) {
  const [selectedApp, setSelectedApp] = useState<string>('');
  const executeAction = useExecuteDeviceAction();

  const launchApp = async (appId: string) => {
    setSelectedApp(appId);
    
    try {
      const { deviceId } = deviceStructure;
      
      // Use launch_app action for all device classes
      await executeAction.mutateAsync({
        deviceId,
        action: { action: 'launch_app', params: { app_name: appId } }
      });
    } catch (err) {
      console.error('Failed to launch app:', err);
      // Optionally reset selection on error
      setSelectedApp('');
      throw err;
    }
  };

  return { selectedApp, launchApp, setSelectedApp };
} 