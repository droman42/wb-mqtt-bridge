// Layer 3: renders a device page at RUNTIME from GET /devices/{id}/layout via the generic
// RemoteControlLayout — the only device-page path (App.tsx routes every A/V device here). On a
// manifest fetch failure it shows an error (the build-time .gen fallback was removed at A2).
// SCN-7 (canonical-first phase 2): controls annotated with a canonical (capability, action)
// tuple dispatch POST /devices/{id}/canonical with wait:false (fire-and-return — button mashing
// must not serialize on echo waits; live state arrives via SSE as before). Un-annotated
// controls (select-form dropdowns, anything unmapped) keep the native /action path.
//
// Force re-tap (DRV-5): when a response carries skipped_reason='idempotence' — an
// optimistic-state guard swallowed the command without sending anything — the pressed
// control arms for a few seconds ("tap again to send anyway"); a re-tap of the SAME
// action re-dispatches with params.force=true, bypassing the guard. This is the only
// UI escape from a desync on feedback-less IR devices (state says "on", device is off).
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLogStore } from '../stores/useLogStore';
import { useExecuteCanonicalAction, useExecuteDeviceAction, useDeviceLayout } from '../hooks/useApi';
import { useSettingsStore } from '../stores/useSettingsStore';
import { useRoomStore } from '../stores/useRoomStore';
import { RemoteControlLayout } from './RemoteControlLayout';
import { manifestToDeviceStructure } from '../lib/layoutManifestAdapter';

// How long the re-tap offer stays armed. Long enough to read the hint, short
// enough that a forgotten offer can't fire a surprise forced command minutes later.
const FORCE_OFFER_MS = 8000;

export interface ForceOffer {
  actionName: string;
  targetDeviceId: string;
  message: string;
}

export function RuntimeDevicePage({ deviceId }: { deviceId: string }) {
  const { addLog } = useLogStore();
  const executeAction = useExecuteDeviceAction();
  const executeCanonical = useExecuteCanonicalAction();
  const { statePanelOpen } = useSettingsStore();
  const { selectDevice } = useRoomStore();
  const { data: manifest, isLoading, isError } = useDeviceLayout(deviceId);
  const [forceOffer, setForceOffer] = useState<ForceOffer | null>(null);
  const offerTimer = useRef<number | null>(null);

  const clearForceOffer = useCallback(() => {
    if (offerTimer.current !== null) {
      window.clearTimeout(offerTimer.current);
      offerTimer.current = null;
    }
    setForceOffer(null);
  }, []);

  const armForceOffer = useCallback((actionName: string, targetDeviceId: string) => {
    if (offerTimer.current !== null) window.clearTimeout(offerTimer.current);
    setForceOffer({
      actionName,
      targetDeviceId,
      message: 'Skipped — state says it’s already there. Tap again to send anyway.',
    });
    offerTimer.current = window.setTimeout(() => {
      offerTimer.current = null;
      setForceOffer(null);
    }, FORCE_OFFER_MS);
  }, []);

  // Don't leave a live timer behind on unmount / device switch.
  useEffect(() => clearForceOffer, [deviceId, clearForceOffer]);

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
    const baseParams =
      payload === undefined || payload === null || (Array.isArray(payload) && payload.length === 0)
        ? {}
        : payload;
    const target = targetDeviceId || deviceId;

    // Force re-tap (DRV-5): a second tap of the armed action re-sends with force=true.
    // Any other action consumes the offer — force is a deliberate, immediate gesture.
    const forced =
      forceOffer !== null &&
      forceOffer.actionName === action &&
      forceOffer.targetDeviceId === target;
    if (forceOffer) clearForceOffer();
    const params = forced ? { ...baseParams, force: true } : baseParams;

    const onSkip = (skippedReason: string | null | undefined) => {
      if (skippedReason === 'idempotence') {
        armForceOffer(action, target);
        addLog({ level: 'info', message: `Skipped by idempotence guard: ${action} -> ${target} (re-tap to force)` });
      }
    };

    // Canonical-first: annotated controls speak the same grammar voice does. Params pass
    // through by name (the endpoint renames only param_map hits); wait:false keeps rapid
    // presses from serializing on echo waits (SSE delivers the live state as before).
    const canonical = canonicalByAction.get(action);
    if (canonical) {
      executeCanonical.mutate(
        {
          deviceId: target,
          request: { capability: canonical.capability, action: canonical.action, params, wait: false },
        },
        { onSuccess: (resp) => onSkip(resp.skipped_reason) }
      );
      addLog({ level: 'info', message: `Canonical: ${canonical.capability}.${canonical.action} -> ${target}${forced ? ' (FORCED)' : ''}`, details: params });
      return;
    }

    executeAction.mutate(
      { deviceId: target, action: { action, params } },
      { onSuccess: (resp) => onSkip((resp.data as { skipped_reason?: string } | null | undefined)?.skipped_reason) }
    );
    addLog({ level: 'info', message: `Action: ${action} -> ${target}${forced ? ' (FORCED)' : ''}`, details: params });
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
        forceOffer={forceOffer}
        className="w-full"
      />
    </div>
  );
}

export default RuntimeDevicePage;
