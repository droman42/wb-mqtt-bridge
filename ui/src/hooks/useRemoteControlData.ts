import { useState, useEffect, useCallback, useMemo } from 'react';
import { useExecuteDeviceAction, useDeviceState as useDeviceStateQuery } from './useApi';
import type { DropdownOption, RemoteDeviceStructure } from '../types/RemoteControlLayout';

// NOTE: This file uses optimized dependency arrays to prevent infinite re-renders.
// ESLint warnings are disabled where the patterns are intentionally used and verified to work correctly.
/* eslint-disable react-hooks/exhaustive-deps */

// Layer-3 static-vs-fetch is decided by the manifest's `populationMethod` (the renderer is
// class-agnostic — no deviceClass branching):
//   "commands" -> options are inline in the manifest; selecting executes `option.id` directly.
//   "api"      -> fetch the list at runtime via the dropdown's `apiAction`; select via the manifest's
//                 `setAction`, sending the value under the manifest's `setParam`.

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
 * Hook for fetching available inputs for a device.
 * "commands" dropdowns use the inline options; "api" dropdowns fetch via the manifest's apiAction.
 */
export function useInputsData(deviceStructure: RemoteDeviceStructure): UseInputsDataResult {
  const [inputs, setInputs] = useState<DropdownOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const executeActionQuery = useExecuteDeviceAction();

  // Decide static-vs-fetch from the manifest's populationMethod (class-agnostic). For scenarios the
  // dropdown's sourceDeviceId is the role device to fetch/gate against (else this device).
  const { hasInputsCapability, isCommands, commandOptions, apiAction, targetDeviceId } = useMemo(() => {
    const dd = deviceStructure.remoteZones.find(zone => zone.zoneId === 'media-stack')?.content?.inputsDropdown;
    return {
      hasInputsCapability: dd != null,
      isCommands: dd?.populationMethod === 'commands',
      commandOptions: dd?.options ?? [],
      apiAction: dd?.apiAction ?? null,
      // No dropdown → no device to gate against (empty id disables the query). Without a dropdown a
      // scenario would otherwise fall back to its own id and fetch /devices/{scenario}/state → 404.
      targetDeviceId: dd ? (dd.sourceDeviceId ?? deviceStructure.deviceId) : '',
    };
  }, [JSON.stringify(deviceStructure.remoteZones), deviceStructure.deviceId]);

  // Live state of the device we fetch/gate against (the role device for scenarios)
  const { data: deviceState } = useDeviceStateQuery(targetDeviceId);

  // Extract only the specific state fields that matter for inputs logic
  const { devicePower, deviceConnected, hasDeviceState } = useMemo(() => {
    return {
      devicePower: (deviceState as any)?.power,
      deviceConnected: (deviceState as any)?.connected,
      hasDeviceState: !!deviceState,
    };
  }, [(deviceState as any)?.power, (deviceState as any)?.connected, !!deviceState]);

  // Stabilize executeAction with useCallback to prevent dependency changes
  const executeAction = useCallback(
    (params: { deviceId: string; action: { action: string; params: Record<string, unknown> } }) =>
      executeActionQuery.mutateAsync(params),
    [executeActionQuery.mutateAsync]
  );

  const fetchInputs = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      // ✋ GUARD: device has no inputs zone
      if (!hasInputsCapability) {
        setInputs([]);
        setLoading(false);
        return;
      }

      // "commands": options are inline in the manifest — no device call.
      if (isCommands) {
        setInputs(commandOptions);
        setLoading(false);
        return;
      }

      // "api": fetch the list from the device (only when powered on + connected).
      const powerStateKnown = devicePower !== undefined;
      const isPoweredOn = devicePower === 'on';
      const isConnected = deviceConnected === true;

      if (!hasDeviceState) {
        setInputs([]);
        setError('Loading device state...');
        setLoading(false);
        return;
      }
      if (powerStateKnown && (!isPoweredOn || !isConnected)) {
        setInputs([]);
        setError(!isPoweredOn ? 'Device is powered off' : 'Device is disconnected');
        setLoading(false);
        return;
      }

      const response = await executeAction({
        deviceId: targetDeviceId,
        action: { action: apiAction ?? 'get_available_inputs', params: {} },
      });

      if (response.success && Array.isArray(response.data)) {
        const inputOptions: DropdownOption[] = response.data.map((input: any) => ({
          id: input.input_id,
          displayName: input.input_name,
          description: input.input_name,
        }));
        setInputs(inputOptions);
      } else {
        setError(response.error || 'Failed to fetch inputs');
        setInputs([]);
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      setError(`Failed to fetch inputs: ${errorMessage}`);
      setInputs([]);
    } finally {
      setLoading(false);
    }
  }, [
    targetDeviceId,
    hasInputsCapability,
    isCommands,
    JSON.stringify(commandOptions),
    apiAction,
    executeAction,
    devicePower,
    deviceConnected,
    hasDeviceState,
  ]);

  const refetch = useCallback(() => {
    void fetchInputs();
  }, [fetchInputs]);

  useEffect(() => {
    void fetchInputs();
  }, [fetchInputs]);

  return { inputs, loading, error, refetch };
}

/**
 * Hook for fetching available apps for a device.
 * "commands" dropdowns use inline options; "api" dropdowns fetch via the manifest's apiAction.
 */
export function useAppsData(deviceStructure: RemoteDeviceStructure): UseAppsDataResult {
  const [apps, setApps] = useState<DropdownOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const executeActionQuery = useExecuteDeviceAction();

  // For scenarios, the apps dropdown's sourceDeviceId is the role device to fetch/gate against.
  const { hasAppsCapability, isCommands, commandOptions, apiAction, targetDeviceId } = useMemo(() => {
    const dd = deviceStructure.remoteZones.find(zone => zone.zoneId === 'apps')?.content?.appsDropdown;
    return {
      hasAppsCapability: dd != null,
      isCommands: dd?.populationMethod === 'commands',
      commandOptions: dd?.options ?? [],
      apiAction: dd?.apiAction ?? null,
      // No dropdown → no device to gate against (empty id disables the query). Without a dropdown a
      // scenario would otherwise fall back to its own id and fetch /devices/{scenario}/state → 404.
      targetDeviceId: dd ? (dd.sourceDeviceId ?? deviceStructure.deviceId) : '',
    };
  }, [JSON.stringify(deviceStructure.remoteZones), deviceStructure.deviceId]);

  const { data: deviceState } = useDeviceStateQuery(targetDeviceId);

  const { devicePower: appDevicePower, deviceConnected: appDeviceConnected, hasDeviceState: appHasDeviceState } = useMemo(() => {
    return {
      devicePower: (deviceState as any)?.power,
      deviceConnected: (deviceState as any)?.connected,
      hasDeviceState: !!deviceState,
    };
  }, [(deviceState as any)?.power, (deviceState as any)?.connected, !!deviceState]);

  const executeAction = useCallback(
    (params: { deviceId: string; action: { action: string; params: Record<string, unknown> } }) =>
      executeActionQuery.mutateAsync(params),
    [executeActionQuery.mutateAsync]
  );

  const fetchApps = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      if (!hasAppsCapability) {
        setApps([]);
        setLoading(false);
        return;
      }

      if (isCommands) {
        setApps(commandOptions);
        setLoading(false);
        return;
      }

      // "api": fetch installed apps (only when powered on + connected).
      const powerStateKnown = appDevicePower !== undefined;
      const isPoweredOn = appDevicePower === 'on';
      const isConnected = appDeviceConnected === true;

      if (!appHasDeviceState) {
        setApps([]);
        setError(null);
        setLoading(false);
        return;
      }
      if (powerStateKnown && (!isPoweredOn || !isConnected)) {
        setApps([]);
        setError(null); // expected when off/disconnected — not an error
        setLoading(false);
        return;
      }

      const response = await executeAction({
        deviceId: targetDeviceId,
        action: { action: apiAction ?? 'get_available_apps', params: {} },
      });

      if (response.success && Array.isArray(response.data)) {
        const appOptions: DropdownOption[] = response.data.map((app: any) => ({
          id: app.app_id,
          displayName: app.app_name,
          description: app.app_name,
        }));
        setApps(appOptions);
      } else {
        setError(response.error || 'Failed to fetch apps');
        setApps([]);
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      setError(`Failed to fetch apps: ${errorMessage}`);
      setApps([]);
    } finally {
      setLoading(false);
    }
  }, [
    targetDeviceId,
    hasAppsCapability,
    isCommands,
    JSON.stringify(commandOptions),
    apiAction,
    executeAction,
    appDevicePower,
    appDeviceConnected,
    appHasDeviceState,
  ]);

  const refetch = useCallback(() => {
    void fetchApps();
  }, [fetchApps]);

  useEffect(() => {
    void fetchApps();
  }, [fetchApps]);

  return { apps, loading, error, refetch };
}

/**
 * Hook for handling input selection. "commands" -> the option id IS the command; "api" -> setAction.
 */
export function useInputSelection(deviceStructure: RemoteDeviceStructure) {
  const [selectedInput, setSelectedInput] = useState<string>('');
  const executeActionQuery = useExecuteDeviceAction();

  const executeAction = useCallback(
    (params: { deviceId: string; action: { action: string; params: any } }) =>
      executeActionQuery.mutateAsync(params),
    [executeActionQuery.mutateAsync]
  );

  const { isCommands, setAction, setParam, targetDeviceId } = useMemo(() => {
    const dd = deviceStructure.remoteZones.find(zone => zone.zoneId === 'media-stack')?.content?.inputsDropdown;
    return {
      isCommands: dd?.populationMethod === 'commands',
      setAction: dd?.setAction ?? null,
      setParam: dd?.setParam ?? 'input',
      targetDeviceId: dd?.sourceDeviceId ?? deviceStructure.deviceId,  // role device for scenarios
    };
  }, [JSON.stringify(deviceStructure.remoteZones), deviceStructure.deviceId]);

  const selectInput = useCallback(async (inputId: string) => {
    setSelectedInput(inputId);

    try {
      if (isCommands) {
        // The option id IS the device command (e.g. "input_cd").
        await executeAction({ deviceId: targetDeviceId, action: { action: inputId, params: {} } });
      } else {
        // api: manifest-declared setAction + the value under the manifest-declared setParam
        // (B5: eMotiva set_input/input, LG set_input_source/source).
        await executeAction({ deviceId: targetDeviceId, action: { action: setAction ?? 'set_input', params: { [setParam]: inputId } } });
      }
    } catch (err) {
      console.error('Failed to select input:', err);
      setSelectedInput('');
      throw err;
    }
  }, [targetDeviceId, isCommands, setAction, setParam, executeAction]);

  return { selectedInput, selectInput, setSelectedInput };
}

/**
 * Hook for handling app launching. Uses the manifest-declared setAction.
 */
export function useAppLaunching(deviceStructure: RemoteDeviceStructure) {
  const [selectedApp, setSelectedApp] = useState<string>('');
  const executeActionQuery = useExecuteDeviceAction();

  const executeAction = useCallback(
    (params: { deviceId: string; action: { action: string; params: any } }) =>
      executeActionQuery.mutateAsync(params),
    [executeActionQuery.mutateAsync]
  );

  const { setAction, setParam, targetDeviceId } = useMemo(() => {
    const dd = deviceStructure.remoteZones.find(zone => zone.zoneId === 'apps')?.content?.appsDropdown;
    return {
      setAction: dd?.setAction ?? null,
      setParam: dd?.setParam ?? 'app_name',
      targetDeviceId: dd?.sourceDeviceId ?? deviceStructure.deviceId,  // role device for scenarios
    };
  }, [JSON.stringify(deviceStructure.remoteZones), deviceStructure.deviceId]);

  const launchApp = useCallback(async (appId: string) => {
    setSelectedApp(appId);

    try {
      // manifest-declared setAction + value under setParam (B5): LG launch_app/app_name,
      // AppleTV launch_app/app. Routed to the role device's sourceDeviceId for scenarios.
      await executeAction({ deviceId: targetDeviceId, action: { action: setAction ?? 'launch_app', params: { [setParam]: appId } } });
    } catch (err) {
      console.error('Failed to launch app:', err);
      setSelectedApp('');
      throw err;
    }
  }, [targetDeviceId, setAction, setParam, executeAction]);

  return { selectedApp, launchApp, setSelectedApp };
}
