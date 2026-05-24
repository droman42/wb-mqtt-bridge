// Layer 3: renders a device page at RUNTIME from GET /devices/{id}/layout via the generic
// RemoteControlLayout — the only device-page path (App.tsx routes every device here). On fetch
// failure it still falls back to the build-time .gen.tsx page (removed at the Step-4 cutover, A2).
import { useEffect, useMemo } from 'react';
import { useLogStore } from '../stores/useLogStore';
import { useExecuteDeviceAction, useDeviceLayout } from '../hooks/useApi';
import { useSettingsStore } from '../stores/useSettingsStore';
import { useRoomStore } from '../stores/useRoomStore';
import { RemoteControlLayout } from './RemoteControlLayout';
import { manifestToDeviceStructure } from '../lib/layoutManifestAdapter';
import { getDeviceComponent } from '../pages/devices/index.gen';

export function RuntimeDevicePage({ deviceId }: { deviceId: string }) {
  const { addLog } = useLogStore();
  const executeAction = useExecuteDeviceAction();
  const { statePanelOpen } = useSettingsStore();
  const { selectDevice } = useRoomStore();
  const { data: manifest, isLoading, isError } = useDeviceLayout(deviceId);

  // Automatically select this device when the page loads (matches the generated page).
  useEffect(() => {
    selectDevice(deviceId);
  }, [deviceId, selectDevice]);

  const deviceStructure = useMemo(
    () => (manifest ? manifestToDeviceStructure(manifest) : null),
    [manifest]
  );

  const handleAction = (action: string, payload?: any, targetDeviceId?: string) => {
    const params =
      payload === undefined || payload === null || (Array.isArray(payload) && payload.length === 0)
        ? {}
        : payload;
    const target = targetDeviceId || deviceId;
    executeAction.mutate({ deviceId: target, action: { action, params } });
    addLog({ level: 'info', message: `Action: ${action} -> ${target}`, details: params });
  };

  if (isLoading) {
    return <div className="p-6 text-center text-muted-foreground">Loading layout…</div>;
  }

  if (isError || !deviceStructure) {
    // Graceful fallback to the build-time page so a manifest failure never breaks the device.
    const Fallback = getDeviceComponent(deviceId);
    if (Fallback) return <Fallback />;
    return (
      <div className="p-6 text-center">
        <h1 className="text-2xl font-bold mb-4">Layout unavailable</h1>
        <p className="text-muted-foreground">
          Could not load the runtime layout for "{deviceId}".
        </p>
      </div>
    );
  }

  return (
    <div className={`${statePanelOpen ? 'p-2' : 'p-4'}`}>
      <RemoteControlLayout
        deviceStructure={deviceStructure}
        onAction={handleAction}
        isActionPending={executeAction.isPending}
        actionError={executeAction.error}
        lastAction={executeAction.variables?.action.action}
        className="w-full"
      />
    </div>
  );
}

export default RuntimeDevicePage;
