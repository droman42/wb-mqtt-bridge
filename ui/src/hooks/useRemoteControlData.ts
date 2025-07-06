import { useState, useEffect, useCallback, useMemo } from 'react';
import { useExecuteDeviceAction } from './useApi';
import type { DropdownOption, RemoteDeviceStructure } from '../types/RemoteControlLayout';

// NOTE: This file uses optimized dependency arrays to prevent infinite re-renders.
// Some dependency arrays intentionally use JSON.stringify() for stability.

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
 * WirenboardIR uses static command lists, other devices use API calls
 */
export function useInputsData(deviceStructure: RemoteDeviceStructure): UseInputsDataResult {
  const [inputs, setInputs] = useState<DropdownOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const executeActionQuery = useExecuteDeviceAction();

  // Extract ONLY primitive values from deviceStructure to avoid infinite re-renders
  const deviceId = deviceStructure.deviceId;
  const deviceClass = deviceStructure.deviceClass;
  
  // Stabilize complex objects with JSON.stringify for useMemo
  const remoteZonesJSON = JSON.stringify(deviceStructure.remoteZones);
  const specialCasesJSON = JSON.stringify(deviceStructure.specialCases);
  
  // Memoize complex derivations with stable dependencies
  const { hasInputsCapability, isWirenboardIR, usesCommands, inputsFromCommands } = useMemo(() => {
    const remoteZones = JSON.parse(remoteZonesJSON);
    const specialCases = JSON.parse(specialCasesJSON);
    
    const mediaStackZone = remoteZones.find((zone: any) => zone.zoneId === 'media-stack');
    const hasInputsCapability = mediaStackZone?.content?.inputsDropdown !== undefined;
    const isWirenboardIR = deviceClass === 'WirenboardIRDevice';
    const usesCommands = specialCases?.some(
      (sc: any) => sc.caseType === 'wirenboard-ir-commands' && sc.configuration.inputsFromCommands
    );
    const inputsFromCommands = (isWirenboardIR && usesCommands) 
      ? (mediaStackZone?.content?.inputsDropdown?.options || [])
      : [];
    
    return { hasInputsCapability, isWirenboardIR, usesCommands, inputsFromCommands };
  }, [
    remoteZonesJSON,
    specialCasesJSON,
    deviceClass
  ]);

  // Stabilize executeAction with useCallback to prevent dependency changes
  const executeAction = useCallback(
    (params: { deviceId: string; action: { action: string; params: {} } }) => 
      executeActionQuery.mutateAsync(params),
    [executeActionQuery]
  );

  const fetchInputs = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      if (isWirenboardIR && usesCommands) {
        // For WirenboardIR: Use static command lists (DON'T TOUCH THIS LOGIC)
        console.log(`📺 [WirenboardIR] Using ${inputsFromCommands.length} inputs from commands`);
        setInputs(inputsFromCommands);
      } else if (hasInputsCapability) {
        // For all other devices: Simple API call - just wait for response
        console.log(`[${deviceId}] Calling get_available_inputs API`);
        const response = await executeAction({
          deviceId,
          action: { action: 'get_available_inputs', params: {} }
        });

        if (response.success && Array.isArray(response.data)) {
          const inputOptions: DropdownOption[] = response.data.map((input: any) => ({
            id: input.input_id,
            displayName: input.input_name,
            description: input.input_name
          }));
          
          console.log(`✅ [${deviceId}] Successfully fetched ${inputOptions.length} inputs`);
          setInputs(inputOptions);
        } else {
          const errorMsg = response.error || 'Failed to fetch inputs';
          console.error(`❌ [${deviceId}] Inputs API failed:`, errorMsg);
          setError(errorMsg);
          setInputs([]);
        }
      } else {
        // No inputs capability
        setInputs([]);
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      console.error(`❌ [${deviceId}] Error in fetchInputs:`, errorMessage);
      setError(`Failed to fetch inputs: ${errorMessage}`);
      setInputs([]);
    } finally {
      setLoading(false);
    }
  }, [
    deviceId,
    hasInputsCapability,
    isWirenboardIR,
    usesCommands,
    inputsFromCommands,
    executeAction
  ]);

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
 * Simple API call - just wait for response, no power state logic
 */
export function useAppsData(deviceStructure: RemoteDeviceStructure): UseAppsDataResult {
  const [apps, setApps] = useState<DropdownOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const executeActionQuery = useExecuteDeviceAction();

  // Extract ONLY primitive values from deviceStructure to avoid infinite re-renders
  const deviceId = deviceStructure.deviceId;
  
  // Stabilize complex objects with JSON.stringify for useMemo
  const remoteZonesJSON = JSON.stringify(deviceStructure.remoteZones);
  
  // Memoize complex derivations with stable dependencies
  const { hasAppsCapability } = useMemo(() => {
    const remoteZones = JSON.parse(remoteZonesJSON);
    const appsZone = remoteZones.find((zone: any) => zone.zoneId === 'apps');
    const hasAppsCapability = appsZone?.content?.appsDropdown !== undefined;
    
    return { hasAppsCapability };
  }, [
    remoteZonesJSON
  ]);

  // Stabilize executeAction with useCallback to prevent dependency changes
  const executeAction = useCallback(
    (params: { deviceId: string; action: { action: string; params: {} } }) => 
      executeActionQuery.mutateAsync(params),
    [executeActionQuery]
  );

  const fetchApps = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      if (hasAppsCapability) {
        // Simple API call - just wait for response, no other logic
        console.log(`[${deviceId}] Calling get_available_apps API`);
        const response = await executeAction({
          deviceId,
          action: { action: 'get_available_apps', params: {} }
        });

        if (response.success && Array.isArray(response.data)) {
          const appOptions: DropdownOption[] = response.data.map((app: any) => ({
            id: app.app_id,
            displayName: app.app_name,
            description: app.app_name
          }));
          
          console.log(`✅ [${deviceId}] Successfully fetched ${appOptions.length} apps`);
          setApps(appOptions);
        } else {
          const errorMsg = response.error || 'Failed to fetch apps';
          console.error(`❌ [${deviceId}] Apps API failed:`, errorMsg);
          setError(errorMsg);
          setApps([]);
        }
      } else {
        // No apps capability
        setApps([]);
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      console.error(`❌ [${deviceId}] Error in fetchApps:`, errorMessage);
      setError(`Failed to fetch apps: ${errorMessage}`);
      setApps([]);
    } finally {
      setLoading(false);
    }
  }, [
    deviceId,
    hasAppsCapability,
    executeAction
  ]);

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
  const executeActionQuery = useExecuteDeviceAction();

  // Extract stable values
  const deviceId = deviceStructure.deviceId;
  const deviceClass = deviceStructure.deviceClass;

  // Stabilize executeAction
  const executeAction = useCallback(
    (params: { deviceId: string; action: { action: string; params: any } }) => 
      executeActionQuery.mutateAsync(params),
    [executeActionQuery]
  );

  const selectInput = useCallback(async (inputId: string) => {
    setSelectedInput(inputId);
    
    try {
      const isWirenboardIR = deviceClass === 'WirenboardIRDevice';

      if (isWirenboardIR) {
        // For WirenboardIR: Execute the specific input command directly
        await executeAction({
          deviceId,
          action: { action: inputId, params: {} }
        });
      } else {
        // For other device classes: Use set_input action
        await executeAction({
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
  }, [deviceId, deviceClass, executeAction]);

  return { selectedInput, selectInput, setSelectedInput };
}

/**
 * Hook for handling app launching
 */
export function useAppLaunching(deviceStructure: RemoteDeviceStructure) {
  const [selectedApp, setSelectedApp] = useState<string>('');
  const executeActionQuery = useExecuteDeviceAction();

  // Extract stable values
  const deviceId = deviceStructure.deviceId;

  // Stabilize executeAction
  const executeAction = useCallback(
    (params: { deviceId: string; action: { action: string; params: any } }) => 
      executeActionQuery.mutateAsync(params),
    [executeActionQuery]
  );

  const launchApp = useCallback(async (appId: string) => {
    setSelectedApp(appId);
    
    try {
      // Use launch_app action for all device classes
      await executeAction({
        deviceId,
        action: { action: 'launch_app', params: { app_name: appId } }
      });
    } catch (err) {
      console.error('Failed to launch app:', err);
      // Optionally reset selection on error
      setSelectedApp('');
      throw err;
    }
  }, [deviceId, executeAction]);

  return { selectedApp, launchApp, setSelectedApp };
} 