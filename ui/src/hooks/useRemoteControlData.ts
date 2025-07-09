import { useState, useEffect, useCallback, useMemo } from 'react';
import { useExecuteDeviceAction, useDeviceState as useDeviceStateQuery } from './useApi';
import type { DropdownOption, RemoteDeviceStructure } from '../types/RemoteControlLayout';

// NOTE: This file uses optimized dependency arrays to prevent infinite re-renders.
// ESLint warnings are disabled where the patterns are intentionally used and verified to work correctly.
/* eslint-disable react-hooks/exhaustive-deps */

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
 * Handles both WirenboardIR (commands) and other device classes (API actions with power state checking)
 */
export function useInputsData(deviceStructure: RemoteDeviceStructure): UseInputsDataResult {
  const [inputs, setInputs] = useState<DropdownOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const executeActionQuery = useExecuteDeviceAction();
  
  // Get device state for power checking (for non-WirenboardIR devices)
  const { data: deviceState } = useDeviceStateQuery(deviceStructure.deviceId);

  // Extract ONLY primitive values from deviceStructure to avoid infinite re-renders
  const deviceId = deviceStructure.deviceId;
  const deviceClass = deviceStructure.deviceClass;
  
  // Memoize complex derivations with stable dependencies
  const { hasInputsCapability, isWirenboardIR, usesCommands, inputsFromCommands } = useMemo(() => {
    const mediaStackZone = deviceStructure.remoteZones.find(zone => zone.zoneId === 'media-stack');
    const hasInputsCapability = mediaStackZone?.content?.inputsDropdown !== undefined;
    const isWirenboardIR = deviceClass === 'WirenboardIRDevice';
    const usesCommands = deviceStructure.specialCases?.some(
      sc => sc.caseType === 'wirenboard-ir-commands' && sc.configuration.inputsFromCommands
    );
    const inputsFromCommands = (isWirenboardIR && usesCommands) 
      ? (mediaStackZone?.content?.inputsDropdown?.options || [])
      : [];
    
    return { hasInputsCapability, isWirenboardIR, usesCommands, inputsFromCommands };
  }, [
    // Only depend on JSON strings of arrays to ensure stability
    // eslint-disable-next-line react-hooks/exhaustive-deps
    JSON.stringify(deviceStructure.remoteZones),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    JSON.stringify(deviceStructure.specialCases),
    deviceClass
  ]);

  // Extract only the specific state fields that matter for inputs logic
  // Use memoization to prevent re-renders when irrelevant fields like last_command change
  const { devicePower, deviceConnected, hasDeviceState } = useMemo(() => {
    // eslint-disable-next-line react-hooks/exhaustive-deps
    return {
      devicePower: (deviceState as any)?.power,
      deviceConnected: (deviceState as any)?.connected,
      hasDeviceState: !!deviceState
    };
  }, [
    (deviceState as any)?.power, 
    (deviceState as any)?.connected, 
    !!deviceState
  ]);

  // Power state checking is working correctly

  // Stabilize executeAction with useCallback to prevent dependency changes
  const executeAction = useCallback(
    (params: { deviceId: string; action: { action: string; params: {} } }) => 
      executeActionQuery.mutateAsync(params),
    [executeActionQuery.mutateAsync]
  );

  const fetchInputs = useCallback(async () => {
    // Check device power state before making API calls

    setLoading(true);
    setError(null);

    try {
      if (isWirenboardIR && usesCommands) {
        // For WirenboardIR: Extract inputs from device commands
        console.log(`📺 [WirenboardIR] Using ${inputsFromCommands.length} inputs from commands`);
        setInputs(inputsFromCommands);
      } else {
        // ✋ GUARD: Early exit if device has no inputs functionality
        if (!hasInputsCapability) {
          console.log(`⚠️  [${deviceId}] No inputs capability detected - skipping inputs API calls`);
          setInputs([]);
          setLoading(false);
          return;
        }

        // 🔌 POWER STATE CHECK: For network-connected devices, check power state before API calls
        const powerStateKnown = devicePower !== undefined;
        const isPoweredOn = devicePower === 'on';
        const isConnected = deviceConnected === true;

        // 🛡️ CRITICAL FIX: Never call APIs if we don't have device state yet
        if (!hasDeviceState) {
          console.log(`[${deviceId}] Waiting for device state before calling inputs API`);
          setInputs([]);
          setError("Loading device state...");
          setLoading(false);
          return;
        }

        // ⚡ SHOW APPROPRIATE MESSAGE: If device is off or disconnected, show message but keep inputs section visible
        if (powerStateKnown && (!isPoweredOn || !isConnected)) {
          const reason = !isPoweredOn ? 'Device is powered off' : 'Device is disconnected';
          console.log(`[${deviceId}] Device is ${!isPoweredOn ? 'powered off' : 'disconnected'} - showing message instead of API call`);
          setInputs([]);
          setError(reason);
          setLoading(false);
          return;
        }

        // 📺 Execute get_available_inputs API call (only for powered-on devices)
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
    // Only depend on primitive values and stable functions
    deviceId,
    hasInputsCapability,
    isWirenboardIR,
    usesCommands,
    inputsFromCommands,
    executeAction,
    devicePower,
    deviceConnected,
    hasDeviceState
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
 * Handles both device capability checking and power state validation for network devices
 */
export function useAppsData(deviceStructure: RemoteDeviceStructure): UseAppsDataResult {
  const [apps, setApps] = useState<DropdownOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const executeActionQuery = useExecuteDeviceAction();
  
  // Get device state for power checking (for network-connected devices)
  const { data: deviceState } = useDeviceStateQuery(deviceStructure.deviceId);

  // Extract ONLY primitive values from deviceStructure to avoid infinite re-renders
  const deviceId = deviceStructure.deviceId;
  
  // Memoize complex derivations with stable dependencies
  const { hasAppsCapability, usesAppsAPI } = useMemo(() => {
    const appsZone = deviceStructure.remoteZones.find(zone => zone.zoneId === 'apps');
    const hasAppsCapability = appsZone?.content?.appsDropdown !== undefined;
    const usesAppsAPI = deviceStructure.specialCases?.some(
      sc => sc.configuration?.usesAppsAPI === true
    );
    
    return { hasAppsCapability, usesAppsAPI };
  }, [
    // Only depend on JSON strings of arrays to ensure stability
    // eslint-disable-next-line react-hooks/exhaustive-deps
    JSON.stringify(deviceStructure.remoteZones),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    JSON.stringify(deviceStructure.specialCases)
  ]);

  // Extract only the specific state fields that matter for apps logic
  // Use memoization to prevent re-renders when irrelevant fields like last_command change
  const { devicePower: appDevicePower, deviceConnected: appDeviceConnected, hasDeviceState: appHasDeviceState } = useMemo(() => {
    // eslint-disable-next-line react-hooks/exhaustive-deps
    return {
      devicePower: (deviceState as any)?.power,
      deviceConnected: (deviceState as any)?.connected,
      hasDeviceState: !!deviceState
    };
  }, [(deviceState as any)?.power, (deviceState as any)?.connected, !!deviceState]);

  // Power state checking is working correctly

  // Stabilize executeAction with useCallback to prevent dependency changes
  const executeAction = useCallback(
    (params: { deviceId: string; action: { action: string; params: {} } }) => 
      executeActionQuery.mutateAsync(params),
    [executeActionQuery.mutateAsync]
  );

  const fetchApps = useCallback(async () => {
    // Check device power state before making API calls

    setLoading(true);
    setError(null);

    try {
      // 🔌 POWER STATE CHECK: For network-connected devices, check power state before API calls
      const powerStateKnown = appDevicePower !== undefined;
      const isPoweredOn = appDevicePower === 'on';
      const isConnected = appDeviceConnected === true;

      // Power state validation logic

      // 🛡️ CRITICAL FIX: Never call APIs if we don't have device state yet
      if (!appHasDeviceState) {
        console.log(`[${deviceId}] Waiting for device state before calling apps API`);
        setApps([]);
        setError(null);
        setLoading(false);
        return;
      }

      // ⚡ CRITICAL FIX: Skip API call if device is known to be off or disconnected
      // These APIs should only be called AFTER successful power_on, not during page load
      if (powerStateKnown && (!isPoweredOn || !isConnected)) {
        const reason = !isPoweredOn ? 'powered off' : 'disconnected';
        console.log(`[${deviceId}] Device is ${reason} - skipping apps API call`);
        setApps([]);
        setError(null); // Don't show error for expected behavior
        setLoading(false);
        return;
      }

      // ✋ GUARD: Early exit if device has no apps functionality
      if (!hasAppsCapability) {
        console.log(`⚠️  [${deviceId}] No apps capability detected - skipping apps API calls`);
        setApps([]);
        setLoading(false);
        return;
      }

      // 📱 Execute get_available_apps API call (only for powered-on devices)
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
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      console.error(`❌ [${deviceId}] Error in fetchApps:`, errorMessage);
      setError(`Failed to fetch apps: ${errorMessage}`);
      setApps([]);
    } finally {
      setLoading(false);
    }
  }, [
    // Only depend on primitive values and stable functions
    deviceId,
    hasAppsCapability,
    usesAppsAPI,
    executeAction,
    appDevicePower,
    appDeviceConnected,
    appHasDeviceState
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

  // Stabilize executeAction
  const executeAction = useCallback(
    (params: { deviceId: string; action: { action: string; params: any } }) => 
      executeActionQuery.mutateAsync(params),
    [executeActionQuery.mutateAsync]
  );

  const selectInput = useCallback(async (inputId: string) => {
    setSelectedInput(inputId);
    
    try {
      const { deviceId, deviceClass } = deviceStructure;
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
  }, [deviceStructure.deviceId, deviceStructure.deviceClass, executeAction]);

  return { selectedInput, selectInput, setSelectedInput };
}

/**
 * Hook for handling app launching
 */
export function useAppLaunching(deviceStructure: RemoteDeviceStructure) {
  const [selectedApp, setSelectedApp] = useState<string>('');
  const executeActionQuery = useExecuteDeviceAction();

  // Stabilize executeAction
  const executeAction = useCallback(
    (params: { deviceId: string; action: { action: string; params: any } }) => 
      executeActionQuery.mutateAsync(params),
    [executeActionQuery.mutateAsync]
  );

  const launchApp = useCallback(async (appId: string) => {
    setSelectedApp(appId);
    
    try {
      const { deviceId } = deviceStructure;
      
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
  }, [deviceStructure.deviceId, executeAction]);

  return { selectedApp, launchApp, setSelectedApp };
} 