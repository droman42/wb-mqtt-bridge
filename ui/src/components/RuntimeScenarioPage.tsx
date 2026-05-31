// Layer 3: renders a scenario page at RUNTIME from GET /scenario/{id}/layout via the generic
// RemoteControlLayout — a composite remote whose controls route to their role device (sourceDeviceId),
// with the power zone driving the scenario lifecycle (start/shutdown). The only scenario-page path
// (App.tsx routes every scenario here); on a manifest fetch failure it shows an error (the build-time
// .gen fallback was removed at A2).
import { useEffect, useMemo } from 'react';
import { useLogStore } from '../stores/useLogStore';
import { useExecuteDeviceAction, useScenarioLayout, useScenarioState, useSwitchScenario, useShutdownScenario } from '../hooks/useApi';
import { useSettingsStore } from '../stores/useSettingsStore';
import { useRoomStore } from '../stores/useRoomStore';
import { RemoteControlLayout } from './RemoteControlLayout';
import { manifestToDeviceStructure } from '../lib/layoutManifestAdapter';

export function RuntimeScenarioPage({ scenarioId }: { scenarioId: string }) {
  const { addLog } = useLogStore();
  const executeAction = useExecuteDeviceAction();
  // Power-on routes through /scenario/switch (not /scenario/start) so it handles both cold-start
  // (no current scenario → outgoing=None branch) AND hand-off from an already-active scenario
  // via the reconciler delta path. /scenario/start 409s when anything is active.
  const switchScenario = useSwitchScenario();
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
      switchScenario.mutate({ id: scenarioId, graceful: true });
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
        isActionPending={executeAction.isPending || switchScenario.isPending || shutdownScenario.isPending}
        actionError={executeAction.error || switchScenario.error || shutdownScenario.error}
        lastAction={
          switchScenario.isPending ? 'power_on'
          : shutdownScenario.isPending ? 'power_off'
          : executeAction.variables?.action.action
        }
        className="w-full"
        lifecycleActive={lifecycleActive}
        // Transition-aware reconciler notes (§5.1 #1) — only when THIS scenario is the
        // active one (viewing an inactive scenario's page must NOT show another
        // scenario's prompts).
        manualSteps={lifecycleActive ? activeScenarioState?.manual_steps ?? [] : []}
      />
    </div>
  );
}

export default RuntimeScenarioPage;
