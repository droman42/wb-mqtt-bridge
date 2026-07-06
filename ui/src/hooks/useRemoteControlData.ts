import { useState, useEffect, useCallback, useMemo } from 'react';
import { fetchDeviceOptions, useExecuteCanonicalAction, useDeviceState as useDeviceStateQuery } from './useApi';
import type { DropdownOption, RemoteDeviceStructure } from '../types/RemoteControlLayout';

// NOTE: This file uses optimized dependency arrays to prevent infinite re-renders.
// ESLint warnings are disabled where the patterns are intentionally used and verified to work correctly.
/* eslint-disable react-hooks/exhaustive-deps */

// Layer-3 static-vs-fetch is decided by the manifest's `populationMethod` (the renderer is
// class-agnostic — no deviceClass branching):
//   "commands" -> options are inline in the manifest (fixed set).
//   "api"      -> fetch the list at runtime via GET /devices/{id}/options/{inputs|apps} (SCN-7:
//                 option enumeration is a READ, not an action).
// Selection dispatches canonically either way (UI-9): the manifest's DropdownConfig carries the
// canonical (capability, action, param) tuple and option ids are canonical values, so the hook
// POSTs /devices/{target}/canonical {capability, action, params: {[param]: optionId}, wait:false}.

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
 * "commands" dropdowns use the inline options; "api" dropdowns fetch the options endpoint.
 */
export function useInputsData(deviceStructure: RemoteDeviceStructure): UseInputsDataResult {
  const [inputs, setInputs] = useState<DropdownOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Decide static-vs-fetch from the manifest's populationMethod (class-agnostic). For scenarios the
  // dropdown's sourceDeviceId is the role device to fetch/gate against (else this device).
  const { hasInputsCapability, isCommands, commandOptions, targetDeviceId } = useMemo(() => {
    const dd = deviceStructure.remoteZones.find(zone => zone.zoneId === 'media-stack')?.content?.inputsDropdown;
    return {
      hasInputsCapability: dd != null,
      isCommands: dd?.populationMethod === 'commands',
      commandOptions: dd?.options ?? [],
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

      // SCN-7: option enumeration rides the read surface (GET), not the action path.
      const response = await fetchDeviceOptions(targetDeviceId, 'inputs');

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
 * "commands" dropdowns use inline options; "api" dropdowns fetch the options endpoint.
 */
export function useAppsData(deviceStructure: RemoteDeviceStructure): UseAppsDataResult {
  const [apps, setApps] = useState<DropdownOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // For scenarios, the apps dropdown's sourceDeviceId is the role device to fetch/gate against.
  const { hasAppsCapability, isCommands, commandOptions, targetDeviceId } = useMemo(() => {
    const dd = deviceStructure.remoteZones.find(zone => zone.zoneId === 'apps')?.content?.appsDropdown;
    return {
      hasAppsCapability: dd != null,
      isCommands: dd?.populationMethod === 'commands',
      commandOptions: dd?.options ?? [],
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

      // SCN-7: option enumeration rides the read surface (GET), not the action path.
      const response = await fetchDeviceOptions(targetDeviceId, 'apps');

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
 * Hook for handling input selection. Canonical dispatch (UI-9): `input.set {value}` —
 * identical for api-populated (parametric) and inline (by_value) dropdowns.
 */
export function useInputSelection(deviceStructure: RemoteDeviceStructure) {
  const [selectedInput, setSelectedInput] = useState<string>('');
  const executeCanonicalQuery = useExecuteCanonicalAction();

  const executeCanonical = useCallback(
    (params: { deviceId: string; request: { capability: string; action: string; params: any; wait: boolean } }) =>
      executeCanonicalQuery.mutateAsync(params),
    [executeCanonicalQuery.mutateAsync]
  );

  const { capability, action, param, targetDeviceId } = useMemo(() => {
    const dd = deviceStructure.remoteZones.find(zone => zone.zoneId === 'media-stack')?.content?.inputsDropdown;
    return {
      capability: dd?.canonicalCapability ?? 'input',
      action: dd?.canonicalAction ?? 'set',
      param: dd?.canonicalParam ?? 'value',
      targetDeviceId: dd?.sourceDeviceId ?? deviceStructure.deviceId,  // role device for scenarios
    };
  }, [JSON.stringify(deviceStructure.remoteZones), deviceStructure.deviceId]);

  const selectInput = useCallback(async (inputId: string) => {
    setSelectedInput(inputId);

    try {
      // wait:false — fire-and-return, same as button dispatch; SSE delivers the post-switch state.
      await executeCanonical({
        deviceId: targetDeviceId,
        request: { capability, action, params: { [param]: inputId }, wait: false },
      });
    } catch (err) {
      console.error('Failed to select input:', err);
      setSelectedInput('');
      throw err;
    }
  }, [targetDeviceId, capability, action, param, executeCanonical]);

  return { selectedInput, selectInput, setSelectedInput };
}

/**
 * Hook for handling app launching. Canonical dispatch (UI-9): `apps.launch {app}` —
 * the bridge renames `app` to the native param via the capability's param_map.
 */
export function useAppLaunching(deviceStructure: RemoteDeviceStructure) {
  const [selectedApp, setSelectedApp] = useState<string>('');
  const executeCanonicalQuery = useExecuteCanonicalAction();

  const executeCanonical = useCallback(
    (params: { deviceId: string; request: { capability: string; action: string; params: any; wait: boolean } }) =>
      executeCanonicalQuery.mutateAsync(params),
    [executeCanonicalQuery.mutateAsync]
  );

  const { capability, action, param, targetDeviceId } = useMemo(() => {
    const dd = deviceStructure.remoteZones.find(zone => zone.zoneId === 'apps')?.content?.appsDropdown;
    return {
      capability: dd?.canonicalCapability ?? 'apps',
      action: dd?.canonicalAction ?? 'launch',
      param: dd?.canonicalParam ?? 'app',
      targetDeviceId: dd?.sourceDeviceId ?? deviceStructure.deviceId,  // role device for scenarios
    };
  }, [JSON.stringify(deviceStructure.remoteZones), deviceStructure.deviceId]);

  const launchApp = useCallback(async (appId: string) => {
    setSelectedApp(appId);

    try {
      await executeCanonical({
        deviceId: targetDeviceId,
        request: { capability, action, params: { [param]: appId }, wait: false },
      });
    } catch (err) {
      console.error('Failed to launch app:', err);
      setSelectedApp('');
      throw err;
    }
  }, [targetDeviceId, capability, action, param, executeCanonical]);

  return { selectedApp, launchApp, setSelectedApp };
}
