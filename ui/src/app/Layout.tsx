import React, { useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useSettingsStore } from '../stores/useSettingsStore';
import Navbar from '../components/Navbar';
import DeviceStatePanel from '../components/DeviceStatePanel';
import LogPanel from '../components/LogPanel';
import { useDeviceSSE, useScenarioSSE, useSystemSSE } from '../hooks/useEventSource';
import { useLogStore } from '../stores/useLogStore';
import { useProgressStore } from '../hooks/useProgressStore';

interface LayoutProps {
  children: React.ReactNode;
}

function Layout({ children }: LayoutProps) {
  const { statePanelOpen, logPanelOpen } = useSettingsStore();
  const { addLog } = useLogStore();
  const { addMessage } = useProgressStore();
  const queryClient = useQueryClient();

  // SSE connections
  const deviceSSE = useDeviceSSE(true);
  const scenarioSSE = useScenarioSSE(true);
  const systemSSE = useSystemSSE(true);

  // Handle device events - only handle specified event types per specification
  useEffect(() => {
    if (deviceSSE.data) {
      const { device_id, device_name, message, eventType, timestamp } = deviceSSE.data;
      
      // Skip logging for keepalive events to reduce console noise
      if (eventType !== 'keepalive') {
        console.log('[Layout] Device SSE data received:', deviceSSE.data);
      }
      
      // Handle test events which have a different structure
      if (eventType === 'test') {
        const testData = deviceSSE.data.data;
        if (testData && testData.device_id) {
          addMessage({
            type: 'device',
            deviceId: testData.device_id,
            deviceName: testData.device_name,
            message: testData.message,
            eventType: 'test'
          });
        }
        return; // Exit early for test events
      }
      
      // Handle real backend events: only the specified event types
      if (eventType && device_id && device_name) {
        // Process different backend event types per specification
        let progressMessage = message;
        let shouldAddToProgress = false;
        
        switch (eventType) {
          case 'action_success':
            // Show successful device actions in progress (green)
            progressMessage = message || `Action completed successfully`;
            shouldAddToProgress = true;
            break;
            
          case 'action_error':
            // Show failed device actions in progress (red)
            progressMessage = message || `Action failed`;
            shouldAddToProgress = true;
            break;
            
          case 'action_progress':
            // Show device action progress in progress (blue)
            progressMessage = message || `Action in progress`;
            shouldAddToProgress = true;
            break;
            
          case 'state_change': {
            // Live-update the device-state cache so every reader re-renders WITHOUT a refetch.
            // This is the single source of truth for live state (Layer-3 scenario binding): a
            // scenario's controls read their ROLE device via ['devices', roleDeviceId, 'state'],
            // the same key a device page reads — so a change made on a device page (or by the
            // reconciler) is reflected on the scenario page, and vice versa. No progress display.
            const state = deviceSSE.data.state;
            if (state && device_id) {
              queryClient.setQueryData(
                ['devices', device_id, 'state'],
                (prev: Record<string, unknown> | undefined) => ({ ...(prev ?? {}), ...state })
              );
            }
            shouldAddToProgress = false;
            break;
          }
            
          default:
            // UI-14 (#17): unknown event types are ignored, not surfaced in the progress
            // feed (a shipped TEMPORARY-DEBUG branch used to log + show every one).
            shouldAddToProgress = false;
        }
        
        if (shouldAddToProgress) {
          addMessage({
            type: 'device',
            deviceId: device_id,
            deviceName: device_name,
            message: progressMessage,
            eventType: eventType
          });
        }
      }
      
      // Log important device events to the log panel - only valid event types
      if (eventType === 'action_success') {
        addLog({
          level: 'info',
          message: `${device_name}: ${message}`,
          details: { device_id, timestamp, eventType }
        });
      } else if (eventType === 'action_error') {
        addLog({
          level: 'error',
          message: `${device_name}: ${message}`,
          details: { device_id, timestamp, eventType }
        });
      }
    }
  }, [deviceSSE.data, addMessage, addLog, queryClient]);

  // Handle scenario events
  useEffect(() => {
    if (scenarioSSE.data) {
      const { scenario_id, scenario_name, message, eventType } = scenarioSSE.data;

      // Only handle test events per specification
      if (eventType === 'test') {
        addMessage({
          type: 'scenario',
          scenarioId: scenario_id,
          scenarioName: scenario_name,
          message: message,
          eventType: eventType
        });
      }

      // The /events/scenarios half of the SSE→cache liveness fix (ui_backend_contract.md
      // "Scenario state binding"). A lifecycle transition driven by ANY client (or the
      // reconciler / WB-UI) changes which scenario is active and its devices' states — refresh
      // the scenario-state cache so the lifecycle active-state coloring and the per-device views
      // go live, not just on mount / after this client's own mutation. Prefix-invalidate both the
      // global ['scenario','state'] and the per-scenario ['scenarios','state', id] queries.
      if (
        eventType === 'scenario_started' ||
        eventType === 'scenario_switched' ||
        eventType === 'scenario_shutdown'
      ) {
        void queryClient.invalidateQueries({ queryKey: ['scenario', 'state'] });
        void queryClient.invalidateQueries({ queryKey: ['scenarios', 'state'] });
      }
    }
  }, [scenarioSSE.data, addMessage, queryClient]);

  // Handle system events - only test events per specification
  useEffect(() => {
    if (systemSSE.data) {
      const { message, level, eventType } = systemSSE.data;
      
      // Only handle test events per specification
      if (eventType === 'test') {
        addLog({
          level: level || 'info',
          message: message,
          details: { 
            eventType: eventType
          }
        });
      }
    }
  }, [systemSSE.data, addLog]);

  return (
    <div className="h-full flex flex-col bg-background">
      {/* Top Navbar */}
      <Navbar />
      
      {/* Main Content Area */}
      <div className="flex-1 flex relative overflow-hidden">
        {/* Main Content */}
        <main className="flex-1 overflow-auto">
          {children}
        </main>
        
        {/* Device State Panel - slides in from right */}
        <DeviceStatePanel 
          isOpen={statePanelOpen}
          className={`
            fixed right-0 top-16 bottom-0 w-80 z-40 transform transition-transform duration-200 ease-out
            ${statePanelOpen ? 'translate-x-0' : 'translate-x-full'}
          `}
          sseState={{
            deviceSSE: { 
              connected: deviceSSE.connected, 
              error: deviceSSE.error?.type || null, 
              reconnectAttempts: deviceSSE.reconnectAttempts 
            },
            scenarioSSE: { 
              connected: scenarioSSE.connected, 
              error: scenarioSSE.error?.type || null, 
              reconnectAttempts: scenarioSSE.reconnectAttempts 
            },
            systemSSE: { 
              connected: systemSSE.connected, 
              error: systemSSE.error?.type || null, 
              reconnectAttempts: systemSSE.reconnectAttempts 
            }
          }}
        />
      </div>
      
      {/* Log Panel - collapsible footer */}
      <LogPanel 
        isOpen={logPanelOpen}
        className={`
          transition-all duration-200 ease-out
          ${logPanelOpen ? 'h-64' : 'h-12'}
        `}
      />
    </div>
  );
}

export default Layout; 