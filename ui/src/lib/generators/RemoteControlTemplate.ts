// Remote Control Template - Phase 1
// Generates device pages using remote control layout instead of grid layout

import type { RemoteDeviceStructure } from '../../types/RemoteControlLayout';

export class RemoteControlTemplate {
  
  generateComponent(structure: RemoteDeviceStructure): string {
    const isScenarioDevice = structure.deviceClass === 'ScenarioDevice';
    
    return `
// Auto-generated from device config - Remote Control Layout - DO NOT EDIT
import React, { useMemo, useEffect } from 'react';
import { useLogStore } from '../../stores/useLogStore';
import { useExecuteDeviceAction${isScenarioDevice ? ', useStartScenario, useShutdownScenario' : ''} } from '../../hooks/useApi';
import { useSettingsStore } from '../../stores/useSettingsStore';
import { useRoomStore } from '../../stores/useRoomStore';
import { RemoteControlLayout } from '../../components/RemoteControlLayout';

function ${this.formatComponentName(structure.deviceId)}Page() {
  const { addLog } = useLogStore();
  const executeAction = useExecuteDeviceAction();${isScenarioDevice ? `
  const startScenario = useStartScenario();
  const shutdownScenario = useShutdownScenario();` : ''}
  const { statePanelOpen } = useSettingsStore();
  const { selectDevice } = useRoomStore();

  // Automatically select this device when the page loads
  useEffect(() => {
    selectDevice('${structure.deviceId}');
  }, [selectDevice]);

  const handleAction = (action: string, payload?: any, targetDeviceId?: string) => {
    // Convert payload to proper params format: ensure it's an object, not an array
    const params = payload === undefined || payload === null || Array.isArray(payload) && payload.length === 0 
      ? {} 
      : payload;
    
    // Use targetDeviceId if provided (for inherited scenario actions), otherwise use this device
    const deviceId = targetDeviceId || '${structure.deviceId}';
    
    ${isScenarioDevice ? `// For scenario devices, use dedicated scenario endpoints for power actions
    if (action === 'power_on') {
      startScenario.mutate(deviceId);
      addLog({
        level: 'info',
        message: \`Starting scenario: \${deviceId}\`,
        details: params
      });
      return;
    }
    
    if (action === 'power_off') {
      shutdownScenario.mutate({ scenarioId: deviceId, graceful: true });
      addLog({
        level: 'info',
        message: \`Shutting down scenario: \${deviceId}\`,
        details: params
      });
      return;
    }
    
    // For other actions, use the regular device action endpoint
    ` : ''}executeAction.mutate({ 
      deviceId: deviceId, 
      action: { action: action, params: params } 
    });
    addLog({
      level: 'info',
      message: \`Action: \${action} -> \${deviceId}\`,
      details: params
    });
  };

  // 🔧 CRITICAL FIX: Memoize deviceStructure to prevent infinite re-renders
  // This object was being recreated on every render, causing all child hooks to re-run
  const deviceStructure: import('../../types/RemoteControlLayout').RemoteDeviceStructure = useMemo(() => (
    ${JSON.stringify(structure, null, 2)}
  ), []); // Empty dependency array since this is static data

  return (
    <div className={\`\${statePanelOpen ? 'p-2' : 'p-4'}\`}>
      <RemoteControlLayout
        deviceStructure={deviceStructure}
        onAction={handleAction}
        isActionPending={executeAction.isPending${isScenarioDevice ? ' || startScenario.isPending || shutdownScenario.isPending' : ''}}
        actionError={executeAction.error${isScenarioDevice ? ' || startScenario.error || shutdownScenario.error' : ''}}
        lastAction={executeAction.variables?.action.action}
        className="w-full"
      />
    </div>
  );
}

export default ${this.formatComponentName(structure.deviceId)}Page;
    `.trim();
  }

  private formatComponentName(deviceId: string): string {
    return deviceId
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join('');
  }
} 