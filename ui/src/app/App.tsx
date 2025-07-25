import React from 'react';
import { Routes, Route, useParams } from 'react-router-dom';
import { useSettingsStore } from '../stores/useSettingsStore';
import { useRoomStore } from '../stores/useRoomStore';
import { useDataSync } from '../hooks/useDataSync';
import Layout from './Layout';
import HomePage from '../pages/HomePage';
import { getDeviceComponent } from '../pages/devices/index.gen';
import { getScenarioComponent } from '../pages/scenarios/index.gen';
import { ScenarioVirtualDeviceControls } from '../components/ScenarioVirtualDeviceControls';

// Component to handle device page routing using generated registry
function DevicePage() {
  const { deviceId } = useParams<{ deviceId: string }>();
  
  if (!deviceId) {
    return (
      <div className="p-6 text-center">
        <h1 className="text-2xl font-bold mb-4">Invalid Device</h1>
        <p className="text-muted-foreground">No device ID provided.</p>
      </div>
    );
  }
  
  const DeviceComponent = getDeviceComponent(deviceId);
  
  if (DeviceComponent) {
    return <DeviceComponent />;
  }
  
  return (
    <div className="p-6 text-center">
      <h1 className="text-2xl font-bold mb-4">Device Not Found</h1>
      <p className="text-muted-foreground">
        Device "{deviceId}" does not have a generated page yet.
      </p>
    </div>
  );
}



// Component to handle scenario page routing
function ScenarioPage() {
  const { scenarioId } = useParams<{ scenarioId: string }>();
  const { statePanelOpen } = useSettingsStore();
  const { selectScenario } = useRoomStore();
  
  // Automatically select this scenario when the page loads
  React.useEffect(() => {
    if (scenarioId) {
      selectScenario(scenarioId);
    }
  }, [scenarioId, selectScenario]);
  
  if (!scenarioId) {
    return (
      <div className="p-6 text-center">
        <h1 className="text-2xl font-bold mb-4">Invalid Scenario</h1>
        <p className="text-muted-foreground">No scenario ID provided.</p>
      </div>
    );
  }
  
  // Try to get generated scenario component first
  const ScenarioComponent = getScenarioComponent(scenarioId);
  
  if (ScenarioComponent) {
    return <ScenarioComponent />;
  }
  
  // Fall back to dynamic scenario controls if no generated component exists
  return (
    <div className={`${statePanelOpen ? 'p-2' : 'p-4'}`}>
      <ScenarioVirtualDeviceControls 
        scenarioId={scenarioId}
        className="w-full max-w-4xl mx-auto"
      />
    </div>
  );
}

function App() {
  const { theme } = useSettingsStore();
  
  // Initialize data synchronization between API and stores
  useDataSync();

  React.useEffect(() => {
    const root = window.document.documentElement;
    
    if (theme === 'dark') {
      root.classList.add('dark');
    } else if (theme === 'light') {
      root.classList.remove('dark');
    } else {
      // System theme
      const systemTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
      if (systemTheme === 'dark') {
        root.classList.add('dark');
      } else {
        root.classList.remove('dark');
      }
    }
  }, [theme]);

  return (
    <Layout>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/devices/:deviceId" element={<DevicePage />} />
        <Route path="/scenario/:scenarioId" element={<ScenarioPage />} />
      </Routes>
    </Layout>
  );
}

export default App; 