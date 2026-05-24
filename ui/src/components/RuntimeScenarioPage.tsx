// Layer 3 (Step 3): renders a scenario page at RUNTIME from GET /scenario/{id}/layout via the generic
// RemoteControlLayout — a composite remote whose controls route to their role device (sourceDeviceId),
// with the power zone driving the scenario lifecycle (start/shutdown). Gated by isRuntimeLayoutEnabled
// (see App.tsx); on fetch failure it falls back to the generated scenario page.
import { useEffect, useMemo } from 'react';
import { useLogStore } from '../stores/useLogStore';
import { useExecuteDeviceAction, useScenarioLayout, useScenarioState, useStartScenario, useShutdownScenario } from '../hooks/useApi';
import { useSettingsStore } from '../stores/useSettingsStore';
import { useRoomStore } from '../stores/useRoomStore';
import { RemoteControlLayout } from './RemoteControlLayout';
import { manifestToDeviceStructure } from '../lib/layoutManifestAdapter';
import { getScenarioComponent } from '../pages/scenarios/index.gen';

export function RuntimeScenarioPage({ scenarioId }: { scenarioId: string }) {
  const { addLog } = useLogStore();
  const executeAction = useExecuteDeviceAction();
  const startScenario = useStartScenario();
  const shutdownScenario = useShutdownScenario();
  const { statePanelOpen } = useSettingsStore();
  const { selectScenario } = useRoomStore();
  const { data: manifest, isLoading, isError } = useScenarioLayout(scenarioId);
  // There is one global active scenario (ScenarioManager.current_scenario), so this scenario is
  // "running" iff it is the active one. /scenario/state 404s when nothing is active (query errors,
  // data undefined → not running). Kept live by the /events/scenarios → cache invalidation in
  // Layout.tsx. See ui_backend_contract.md "Scenario lifecycle (power zone) active-state".
  const { data: activeScenarioState } = useScenarioState();
  const lifecycleActive = activeScenarioState?.scenario_id === scenarioId;

  useEffect(() => {
    selectScenario(scenarioId);
  }, [scenarioId, selectScenario]);

  const deviceStructure = useMemo(
    () => (manifest ? manifestToDeviceStructure(manifest) : null),
    [manifest]
  );

  const handleAction = (action: string, payload?: any, targetDeviceId?: string) => {
    const params =
      payload === undefined || payload === null || (Array.isArray(payload) && payload.length === 0)
        ? {}
        : payload;

    // The scenario power zone (no sourceDeviceId) drives the lifecycle, not a device action.
    if (action === 'power_on') {
      startScenario.mutate(scenarioId);
      addLog({ level: 'info', message: `Starting scenario: ${scenarioId}`, details: params });
      return;
    }
    if (action === 'power_off') {
      shutdownScenario.mutate({ scenarioId, graceful: true });
      addLog({ level: 'info', message: `Shutting down scenario: ${scenarioId}`, details: params });
      return;
    }

    // Every other control routes to its ROLE DEVICE (sourceDeviceId). A scenario is not a device, so
    // we must never post to /devices/{scenario}; if a control lacks a role device, that's a manifest
    // bug — warn and skip rather than hit a non-existent endpoint.
    if (!targetDeviceId) {
      console.warn(`[scenario ${scenarioId}] control "${action}" has no role device (sourceDeviceId) — skipping`);
      addLog({ level: 'error', message: `Scenario control "${action}" has no role device`, details: params });
      return;
    }
    executeAction.mutate({ deviceId: targetDeviceId, action: { action, params } });
    addLog({ level: 'info', message: `Action: ${action} -> ${targetDeviceId}`, details: params });
  };

  if (isLoading) {
    return <div className="p-6 text-center text-muted-foreground">Loading layout…</div>;
  }

  if (isError || !deviceStructure) {
    // Graceful fallback to the build-time scenario page so a manifest failure never breaks it.
    const Fallback = getScenarioComponent(scenarioId);
    if (Fallback) return <Fallback />;
    return (
      <div className="p-6 text-center">
        <h1 className="text-2xl font-bold mb-4">Layout unavailable</h1>
        <p className="text-muted-foreground">
          Could not load the runtime layout for scenario "{scenarioId}".
        </p>
      </div>
    );
  }

  return (
    <div className={`${statePanelOpen ? 'p-2' : 'p-4'}`}>
      <RemoteControlLayout
        deviceStructure={deviceStructure}
        onAction={handleAction}
        isActionPending={executeAction.isPending || startScenario.isPending || shutdownScenario.isPending}
        actionError={executeAction.error || startScenario.error || shutdownScenario.error}
        lastAction={executeAction.variables?.action.action}
        className="w-full"
        lifecycleActive={lifecycleActive}
      />
    </div>
  );
}

export default RuntimeScenarioPage;
