import { useCallback } from 'react';
import { useExecuteDeviceAction, usePollDeviceState } from './useApi';
import { useDeviceState } from './useDeviceState';
import { useLogStore } from '../stores/useLogStore';
import type { RemoteDeviceStructure } from '../types/RemoteControlLayout';

interface PowerManagementHook {
  handlePowerOn: (deviceStructure: RemoteDeviceStructure) => Promise<void>;
  isControlDisabled: boolean;
}

export function usePowerManagement(deviceId: string): PowerManagementHook {
  const { setDeviceDisabled, setPoweringOn, isDisabled, isPoweringOn } = useDeviceState(deviceId);
  const executeDeviceAction = useExecuteDeviceAction();
  const pollDeviceState = usePollDeviceState();
  const { addLog } = useLogStore();

  const fetchInputsIfNeeded = useCallback(async (deviceStructure: RemoteDeviceStructure) => {
    const { deviceClass } = deviceStructure;
    
    // Skip WirenboardIR devices
    if (deviceClass === 'WirenboardIR') {
      console.log(`⏭️  [${deviceId}] Skipping inputs fetch for WirenboardIR device`);
      return;
    }

    // Check if device has inputs capability
    const mediaStackZone = deviceStructure.remoteZones.find(zone => zone.zoneId === 'media-stack');
    const hasInputsCapability = mediaStackZone?.content?.inputsDropdown !== undefined;

    if (!hasInputsCapability) {
      console.log(`⏭️  [${deviceId}] No inputs capability detected`);
      return;
    }

    try {
      console.log(`📺 [${deviceId}] Fetching available inputs after power-on`);
      const inputsResponse = await executeDeviceAction.mutateAsync({
        deviceId,
        action: { action: 'get_available_inputs', params: {} }
      });

      if (!inputsResponse || inputsResponse.error) {
        throw new Error(`Inputs fetch failed: ${inputsResponse?.error || 'Unknown error'}`);
      }

      console.log(`✅ [${deviceId}] Successfully fetched ${inputsResponse.data?.length || 0} inputs`);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      console.error(`❌ [${deviceId}] Failed to fetch inputs:`, errorMessage);

      addLog({
        level: 'error',
        message: `Device ${deviceId} inputs fetch failed: ${errorMessage}`,
        category: 'device'
      });

      throw new Error('inputs_fetch_failed');
    }
  }, [deviceId, executeDeviceAction, addLog]);

  const fetchAppsIfNeeded = useCallback(async (deviceStructure: RemoteDeviceStructure) => {
    const { deviceClass, specialCases } = deviceStructure;
    
    // Skip WirenboardIR devices
    if (deviceClass === 'WirenboardIR') {
      console.log(`⏭️  [${deviceId}] Skipping apps fetch for WirenboardIR device`);
      return;
    }

    // Check if device has apps capability
    const appsZone = deviceStructure.remoteZones.find(zone => zone.zoneId === 'apps');
    const hasAppsCapability = appsZone?.content?.appsDropdown !== undefined;

    // Check if device uses apps API
    const usesAppsAPI = specialCases?.some(
      sc => sc.configuration?.usesAppsAPI === true
    );

    if (!hasAppsCapability || !usesAppsAPI) {
      console.log(`⏭️  [${deviceId}] No apps capability or API usage detected`);
      return;
    }

    try {
      console.log(`📱 [${deviceId}] Fetching available apps after power-on`);
      const appsResponse = await executeDeviceAction.mutateAsync({
        deviceId,
        action: { action: 'get_available_apps', params: {} }
      });

      if (!appsResponse || appsResponse.error) {
        throw new Error(`Apps fetch failed: ${appsResponse?.error || 'Unknown error'}`);
      }

      console.log(`✅ [${deviceId}] Successfully fetched ${appsResponse.data?.length || 0} apps`);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      console.error(`❌ [${deviceId}] Failed to fetch apps:`, errorMessage);

      addLog({
        level: 'error', 
        message: `Device ${deviceId} apps fetch failed: ${errorMessage}`,
        category: 'device'
      });

      throw new Error('apps_fetch_failed');
    }
  }, [deviceId, executeDeviceAction, addLog]);

  const handlePowerOn = useCallback(async (deviceStructure: RemoteDeviceStructure) => {
    try {
      console.log(`🔋 [${deviceId}] Starting power-on sequence`);
      setPoweringOn(true);

      // Step 1: Send power command
      console.log(`🔋 [${deviceId}] Sending power command`);
      const powerResponse = await executeDeviceAction.mutateAsync({
        deviceId,
        action: { action: 'power_on', params: {} }
      });

      if (!powerResponse || powerResponse.error) {
        throw new Error(`Power command failed: ${powerResponse?.error || 'Unknown error'}`);
      }

      // Step 2: Poll device state to confirm power on
      console.log(`🔋 [${deviceId}] Polling device state to confirm power on`);
      const stateData = await pollDeviceState.mutateAsync(deviceId);
      
      if ((stateData as any)?.power !== 'on') {
        throw new Error('Device failed to power on - state check failed');
      }

      console.log(`✅ [${deviceId}] Device powered on successfully`);

      // Step 3: Fetch inputs if applicable
      await fetchInputsIfNeeded(deviceStructure);

      // Step 4: Fetch apps if applicable  
      await fetchAppsIfNeeded(deviceStructure);

      // Success - enable all controls
      setDeviceDisabled(false);
      console.log(`🎉 [${deviceId}] Power-on sequence completed successfully`);

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      console.error(`❌ [${deviceId}] Power-on sequence failed:`, errorMessage);

      // Log error for user visibility
      addLog({
        level: 'error',
        message: `Device ${deviceId} power-on failed: ${errorMessage}`,
        category: 'device'
      });

      // Disable all controls
      setDeviceDisabled(true, 'power_on_failed');
      
      throw error; // Re-throw for component handling
    } finally {
      setPoweringOn(false);
    }
  }, [deviceId, executeDeviceAction, pollDeviceState, setDeviceDisabled, setPoweringOn, addLog, fetchInputsIfNeeded, fetchAppsIfNeeded]);

  const isControlDisabled = isDisabled || isPoweringOn;

  return {
    handlePowerOn,
    isControlDisabled,
  };
} 