// Layer 3: renders a device page at RUNTIME from GET /devices/{id}/layout via the generic
// RemoteControlLayout — the only device-page path (App.tsx routes every A/V device here). On a
// manifest fetch failure it shows an error (the build-time .gen fallback was removed at A2).
// SCN-7 (canonical-first phase 2): controls annotated with a canonical (capability, action)
// tuple dispatch POST /devices/{id}/canonical with wait:false (fire-and-return — button mashing
// must not serialize on echo waits; live state arrives via SSE as before). Un-annotated
// controls (select-form dropdowns, anything unmapped) keep the native /action path.
import { useEffect, useMemo } from 'react';
import { useLogStore } from '../stores/useLogStore';
import { useExecuteCanonicalAction, useExecuteDeviceAction, useDeviceLayout } from '../hooks/useApi';
import { useSettingsStore } from '../stores/useSettingsStore';
import { useRoomStore } from '../stores/useRoomStore';
import { RemoteControlLayout } from './RemoteControlLayout';
import { manifestToDeviceStructure } from '../lib/layoutManifestAdapter';

export function RuntimeDevicePage({ deviceId }: { deviceId: string }) {
  const { addLog } = useLogStore();
  const executeAction = useExecuteDeviceAction();
  const executeCanonical = useExecuteCanonicalAction();
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

  // Canonical dispatch table from the raw manifest (device manifests carry no
  // sourceDeviceId — the target is this device — so the key is the action name).
  const canonicalByAction = useMemo(() => {
    const map = new Map<string, { capability: string; action: string }>();
    const walk = (node: any) => {
      if (!node || typeof node !== 'object') return;
      if (Array.isArray(node)) { node.forEach(walk); return; }
      if (node.actionName && node.canonicalCapability && node.canonicalAction) {
        map.set(node.actionName, {
          capability: node.canonicalCapability,
          action: node.canonicalAction,
        });
      }
      Object.values(node).forEach(walk);
    };
    walk(manifest?.remoteZones);
    return map;
  }, [manifest]);

  const handleAction = (action: string, payload?: any, targetDeviceId?: string) => {
    const params =
      payload === undefined || payload === null || (Array.isArray(payload) && payload.length === 0)
        ? {}
        : payload;
    const target = targetDeviceId || deviceId;

    // Canonical-first: annotated controls speak the same grammar voice does. Params pass
    // through by name (the endpoint renames only param_map hits); wait:false keeps rapid
    // presses from serializing on echo waits (SSE delivers the live state as before).
    const canonical = canonicalByAction.get(action);
    if (canonical) {
      executeCanonical.mutate({
        deviceId: target,
        request: { capability: canonical.capability, action: canonical.action, params, wait: false },
      });
      addLog({ level: 'info', message: `Canonical: ${canonical.capability}.${canonical.action} -> ${target}`, details: params });
      return;
    }

    executeAction.mutate({ deviceId: target, action: { action, params } });
    addLog({ level: 'info', message: `Action: ${action} -> ${target}`, details: params });
  };

  if (isLoading) {
    return <div className="p-6 text-center text-muted-foreground">Loading layout…</div>;
  }

  if (isError || !deviceStructure) {
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
        isActionPending={executeAction.isPending || executeCanonical.isPending}
        actionError={executeAction.error || executeCanonical.error}
        lastAction={executeAction.variables?.action.action}
        className="w-full"
      />
    </div>
  );
}

export default RuntimeDevicePage;
