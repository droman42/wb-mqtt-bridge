import React from 'react';
import { Routes, Route, useParams } from 'react-router-dom';
import { useSettingsStore } from '../stores/useSettingsStore';
import { useDataSync } from '../hooks/useDataSync';
import Layout from './Layout';
import HomePage from '../pages/HomePage';
import { RuntimeDevicePage } from '../components/RuntimeDevicePage';
import { RuntimeScenarioPage } from '../components/RuntimeScenarioPage';
import { getAppliancePage } from '../pages/appliances';

// Device page routing — Layer 3: A/V devices render from the backend layout manifest at runtime;
// appliances (no capability map) get a hand-written bespoke page.
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

  const AppliancePage = getAppliancePage(deviceId);
  if (AppliancePage) {
    return <AppliancePage />;
  }

  return <RuntimeDevicePage deviceId={deviceId} />;
}

// Scenario page routing — Layer 3: always render from the backend scenario layout manifest at
// runtime. (RuntimeScenarioPage selects the scenario in the room store on mount.)
function ScenarioPage() {
  const { scenarioId } = useParams<{ scenarioId: string }>();

  if (!scenarioId) {
    return (
      <div className="p-6 text-center">
        <h1 className="text-2xl font-bold mb-4">Invalid Scenario</h1>
        <p className="text-muted-foreground">No scenario ID provided.</p>
      </div>
    );
  }

  return <RuntimeScenarioPage scenarioId={scenarioId} />;
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