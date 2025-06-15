import React from 'react';
import { Routes, Route, useParams } from 'react-router-dom';
import { useSettingsStore } from '../stores/useSettingsStore';
import { useDataSync } from '../hooks/useDataSync';
import Layout from './Layout';
import HomePage from '../pages/HomePage';
import { getDeviceComponent } from '../pages/devices/index.gen';

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
        <Route path="/scenario/:scenarioId" element={<div>Scenario Page (Generated)</div>} />
      </Routes>
    </Layout>
  );
}

export default App; 