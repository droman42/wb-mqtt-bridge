import React from 'react';
import { useDataSync } from '../hooks/useDataSync';
import { useRoomStore } from '../stores/useRoomStore';
import { useLogStore } from '../stores/useLogStore';

function HomePage() {
  const { isLoading, errors } = useDataSync();
  const { 
    selectedRoomId, 
    selectedDeviceId, 
    selectedScenarioId, 
    rooms, 
    devices, 
    scenarios,
    getFilteredDevices,
    getFilteredScenarios
  } = useRoomStore();
  const { addLog } = useLogStore();

  const filteredDevices = getFilteredDevices();
  const filteredScenarios = getFilteredScenarios();
  const selectedRoom = rooms.find(r => r.id === selectedRoomId);

  React.useEffect(() => {
    addLog({
      level: 'info',
      message: 'Smart Home UI v2 initialized',
    });
  }, [addLog]);

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="text-center mb-8">
        <h1 className="text-4xl font-bold mb-4">Smart Home Remote UI v2</h1>
        <p className="text-muted-foreground">
          Control your smart home devices with intuitive interfaces generated from prompt files.
        </p>
      </div>

      {/* Debug Information */}
      <div className="mb-8 p-4 bg-muted rounded-lg">
        <h3 className="text-lg font-semibold mb-2">Debug Information</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
          <div>
            <h4 className="font-medium">API Status:</h4>
            <p>Loading: {isLoading ? 'Yes' : 'No'}</p>
            <p>API Base URL: {import.meta.env.VITE_API_BASE_URL || 'http://192.168.110.250:8000'}</p>
          </div>
          <div>
            <h4 className="font-medium">Data Counts:</h4>
            <p>Rooms: {rooms.length}</p>
            <p>Devices: {devices.length} (filtered: {filteredDevices.length})</p>
            <p>Scenarios: {scenarios.length} (filtered: {filteredScenarios.length})</p>
            {selectedRoom && <p>Selected Room: {selectedRoom.name.en}</p>}
          </div>
          <div>
            <h4 className="font-medium">Errors:</h4>
            <p>Rooms: {errors.rooms ? '❌' : '✅'}</p>
            <p>Devices: {errors.devices ? '❌' : '✅'}</p>
            <p>Scenarios: {errors.scenarios ? '❌' : '✅'}</p>
          </div>
        </div>
        {(errors.rooms || errors.devices || errors.scenarios) && (
          <div className="mt-4">
            <h4 className="font-medium text-red-600">Error Details:</h4>
            <pre className="text-xs bg-red-50 p-2 rounded mt-2 overflow-auto">
              {JSON.stringify(errors, null, 2)}
            </pre>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {/* Getting Started */}
        <div className="bg-card p-6 rounded-lg border">
          <h2 className="text-2xl font-semibold mb-4">Getting Started</h2>
          <p className="text-muted-foreground mb-4">
            Select a device or scenario from the navigation bar to begin controlling your smart home.
          </p>
          <ul className="space-y-2 text-sm">
            <li>• Use the Room dropdown to filter devices by location</li>
            <li>• Select a Device to access its control interface</li>
            <li>• Choose a Scenario to run automated sequences</li>
            <li>• Toggle the state panel to view device information</li>
            <li>• Check the log panel for system messages</li>
          </ul>
        </div>

        {/* Current Status */}
        <div className="bg-card p-6 rounded-lg border">
          <h2 className="text-2xl font-semibold mb-4">Current Status</h2>
          <div className="space-y-3">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Selected Device:</span>
              <span>{selectedDeviceId || 'None'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Selected Scenario:</span>
              <span>{selectedScenarioId || 'None'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">System Status:</span>
              <span className="text-green-600">Ready</span>
            </div>
          </div>
        </div>
      </div>

      {/* Features */}
      <div className="mt-12">
        <h2 className="text-3xl font-semibold text-center mb-8">Features</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          <div className="text-center">
            <h3 className="text-xl font-semibold mb-3">Device Control</h3>
            <p className="text-muted-foreground">
              Control smart home devices with intuitive interfaces generated from prompt files.
            </p>
          </div>
          <div className="text-center">
            <h3 className="text-xl font-semibold mb-3">Scenario Management</h3>
            <p className="text-muted-foreground">
              Execute complex automation scenarios with a single tap.
            </p>
          </div>
          <div className="text-center">
            <h3 className="text-xl font-semibold mb-3">Real-time Updates</h3>
            <p className="text-muted-foreground">
              Monitor device states and system logs in real-time.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default HomePage; 