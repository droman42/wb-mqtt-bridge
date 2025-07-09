import React, { useEffect } from 'react';
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

  // Use the new SSE hooks
  const deviceSSE = useDeviceSSE(true);
  const scenarioSSE = useScenarioSSE(true);
  const systemSSE = useSystemSSE(true);

  // Handle device events - now includes setup, connection attempts, and progress
  useEffect(() => {
    if (deviceSSE.data) {
      const { device_id, device_name, message, eventType } = deviceSSE.data;
      
      // Handle different device event types
      if (eventType && ['device_setup', 'connection_attempt', 'connection_success', 'device_progress'].includes(eventType)) {
        addMessage({
          type: 'device',
          deviceId: device_id,
          deviceName: device_name,
          message: message,
          eventType: eventType
        });
      }
      
      // Log important device events
      if (eventType === 'connection_success') {
        addLog({
          level: 'info',
          message: `Device connected: ${device_name}`,
          details: { device_id, timestamp: deviceSSE.data.timestamp }
        });
      } else if (eventType === 'connection_failed') {
        addLog({
          level: 'error',
          message: `Device connection failed: ${device_name}`,
          details: { device_id, timestamp: deviceSSE.data.timestamp }
        });
      }
    }
  }, [deviceSSE.data, addMessage, addLog]);

  // Handle scenario events
  useEffect(() => {
    if (scenarioSSE.data) {
      const { scenario_id, scenario_name, message, eventType, progress } = scenarioSSE.data;
      
      // Handle different scenario event types
      if (eventType && ['scenario_start', 'scenario_progress', 'scenario_complete', 'scenario_error'].includes(eventType)) {
        addMessage({
          type: 'scenario',
          scenarioId: scenario_id,
          scenarioName: scenario_name,
          message: message,
          eventType: eventType
        });
      }
      
      // Log important scenario events
      if (eventType === 'scenario_complete') {
        addLog({
          level: 'info',
          message: `Scenario completed: ${scenario_name || scenario_id}`,
          details: { scenario_id, timestamp: scenarioSSE.data.timestamp, progress }
        });
      } else if (eventType === 'scenario_error') {
        addLog({
          level: 'error',
          message: `Scenario error: ${scenario_name || scenario_id}`,
          details: { scenario_id, timestamp: scenarioSSE.data.timestamp, message }
        });
      }
    }
  }, [scenarioSSE.data, addMessage, addLog]);

  // Handle system events - add to log panel
  useEffect(() => {
    if (systemSSE.data) {
      const { message, level, eventType, timestamp } = systemSSE.data;
      
      // Don't log keepalive events to reduce noise
      if (eventType !== 'keepalive') {
        addLog({
          level: level || 'info',
          message: message,
          details: { 
            timestamp: timestamp,
            eventType: eventType
          }
        });
      }
      
      // Special handling for connected event
      if (eventType === 'connected') {
        console.log('[Layout] System SSE connected');
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