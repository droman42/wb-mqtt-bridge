import React from 'react';
import { Routes, Route } from 'react-router-dom';
import { useSettingsStore } from '../stores/useSettingsStore';
import { useDataSync } from '../hooks/useDataSync';
import Layout from './Layout';
import HomePage from '../pages/HomePage';

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
        <Route path="/device/:deviceId" element={<div>Device Page (Generated)</div>} />
        <Route path="/scenario/:scenarioId" element={<div>Scenario Page (Generated)</div>} />
      </Routes>
    </Layout>
  );
}

export default App; 