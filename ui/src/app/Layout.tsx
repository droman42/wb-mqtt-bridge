import React from 'react';
import { useSettingsStore } from '../stores/useSettingsStore';
import Navbar from '../components/Navbar';
import DeviceStatePanel from '../components/DeviceStatePanel';
import LogPanel from '../components/LogPanel';

interface LayoutProps {
  children: React.ReactNode;
}

function Layout({ children }: LayoutProps) {
  const { statePanelOpen, logPanelOpen } = useSettingsStore();

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