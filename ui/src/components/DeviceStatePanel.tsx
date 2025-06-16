import React from 'react';
import { Icon } from './icons';
import { useRoomStore } from '../stores/useRoomStore';
import { useSettingsStore } from '../stores/useSettingsStore';
import { useDeviceState } from '../hooks/useDeviceState';
import { Button } from './ui/button';
import { RemoteDeviceStructure } from '../types/RemoteControlLayout';

interface DeviceStatePanelProps {
  isOpen: boolean;
  className?: string;
}

// Helper function to get device structure from generated pages
const getDeviceStructure = (deviceId: string): RemoteDeviceStructure | null => {
  // This will be populated by checking the current page's device structure
  // For now, we'll extract it from the window context if available
  if (typeof window !== 'undefined' && (window as any).currentDeviceStructure) {
    return (window as any).currentDeviceStructure;
  }
  return null;
};

// Helper function to format state values
const formatStateValue = (value: any, fieldType: string): string => {
  if (value === null || value === undefined) {
    return 'N/A';
  }
  
  switch (fieldType) {
    case 'boolean':
      return value ? 'Yes' : 'No';
    case 'number':
      return typeof value === 'number' ? value.toFixed(1) : String(value);
    case 'string':
      return String(value);
    default:
      return String(value);
  }
};

// Helper function to get field icon
const getFieldIcon = (fieldName: string): string => {
  const iconMap: Record<string, string> = {
    power: 'PowerSettingsNew',
    volume: 'VolumeUp',
    mainVolume: 'VolumeUp',
    zone2Volume: 'VolumeUp',
    input: 'Input',
    mainInput: 'Input',
    zone2Input: 'Input',
    currentInput: 'Input',
    inputSource: 'Input',
    playbackState: 'PlayArrow',
    transportState: 'PlayArrow',
    currentApp: 'Apps',
    currentTrack: 'MusicNote',
    tapeSpeed: 'Speed',
    recordLevel: 'FiberManualRecord',
    playbackLevel: 'VolumeUp',
    biasAdjustment: 'Tune',
    eqSetting: 'Equalizer',
    tapePosition: 'Timer',
    sampleRate: 'Analytics',
    bitDepth: 'Analytics',
    streamingService: 'CloudQueue',
    fanSpeed: 'Air',
    lightLevel: 'Lightbulb',
    temperature: 'Thermostat',
    lastAction: 'History'
  };
  
  return iconMap[fieldName] || 'Info';
};

function DeviceStatePanel({ isOpen, className }: DeviceStatePanelProps) {
  const { selectedDeviceId } = useRoomStore();
  const { setStatePanelOpen } = useSettingsStore();

  // Use the enhanced device state hook
  const { state: deviceState, isLoading, error, isConnected } = useDeviceState(selectedDeviceId || '');
  
  // Get device structure for state interface
  const deviceStructure = getDeviceStructure(selectedDeviceId || '');

  if (!isOpen) return null;

  const renderDeviceSpecificState = () => {
    if (!deviceStructure?.stateInterface?.fields || !deviceState) {
      return null;
    }

    const stateFields = deviceStructure.stateInterface.fields;
    const deviceSpecificFields = stateFields.filter(field => 
      !['device_id', 'device_name', 'last_command', 'error'].includes(field.name)
    );

    if (deviceSpecificFields.length === 0) {
      return null;
    }

    return (
      <div className="space-y-3">
        <h3 className="font-medium text-sm text-muted-foreground uppercase tracking-wider">
          Device State
        </h3>
        <div className="space-y-2">
          {deviceSpecificFields.map((field) => {
            const value = (deviceState as any)[field.name];
            const formattedValue = formatStateValue(value, field.type);
            const iconName = getFieldIcon(field.name);
            
            return (
              <div key={field.name} className="flex items-center justify-between p-2 rounded-md bg-muted/30">
                <div className="flex items-center space-x-2">
                  <Icon 
                    library="material" 
                    name={iconName} 
                    size="sm" 
                    fallback="info" 
                    className="h-4 w-4 text-muted-foreground" 
                  />
                  <div>
                    <span className="text-sm font-medium">
                      {field.name.replace(/([A-Z])/g, ' $1').replace(/^./, str => str.toUpperCase())}
                    </span>
                    {field.description && (
                      <p className="text-xs text-muted-foreground">{field.description}</p>
                    )}
                  </div>
                </div>
                <span className={`text-sm font-mono ${
                  value === null || value === undefined 
                    ? 'text-muted-foreground' 
                    : field.type === 'boolean' 
                      ? value ? 'text-green-600' : 'text-red-600'
                      : 'text-foreground'
                }`}>
                  {formattedValue}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  return (
    <div className={`flex flex-col h-full ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-border">
        <h2 className="text-lg font-semibold">Device State</h2>
        <Button 
          variant="ghost" 
          size="icon"
          onClick={() => setStatePanelOpen(false)}
        >
          <Icon 
            library="material" 
            name="Close" 
            size="md" 
            fallback="close" 
            className="h-5 w-5" 
          />
        </Button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-4">
        {!selectedDeviceId ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <Icon 
              library="material" 
              name="DeviceHub" 
              size="lg" 
              fallback="device" 
              className="h-12 w-12 text-muted-foreground mb-4" 
            />
            <p className="text-muted-foreground">No device selected</p>
            <p className="text-xs text-muted-foreground mt-1">Select a device to view its state</p>
          </div>
        ) : isLoading ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <Icon 
              library="material" 
              name="Refresh" 
              size="lg" 
              fallback="loading" 
              className="h-12 w-12 text-muted-foreground mb-4 animate-spin" 
            />
            <p className="text-muted-foreground">Loading device state...</p>
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <Icon 
              library="material" 
              name="Error" 
              size="lg" 
              fallback="error" 
              className="h-12 w-12 text-destructive mb-4" 
            />
            <p className="text-destructive">Error loading device state</p>
            <p className="text-xs text-muted-foreground mt-1">{error.message}</p>
          </div>
        ) : deviceState ? (
          <div className="space-y-6">
            {/* Device Info Section */}
            <div className="space-y-3">
              <h3 className="font-medium text-sm text-muted-foreground uppercase tracking-wider">
                Device Info
              </h3>
              <div className="space-y-2">
                <div className="flex items-center justify-between p-2 rounded-md bg-muted/30">
                  <div className="flex items-center space-x-2">
                    <div className={`w-3 h-3 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
                    <span className="text-sm font-medium">Status</span>
                  </div>
                  <span className={`text-sm ${isConnected ? 'text-green-600' : 'text-red-600'}`}>
                    {isConnected ? 'Connected' : 'Disconnected'}
                  </span>
                </div>
                
                <div className="flex items-center justify-between p-2 rounded-md bg-muted/30">
                  <div className="flex items-center space-x-2">
                    <Icon 
                      library="material" 
                      name="Badge" 
                      size="sm" 
                      fallback="id" 
                      className="h-4 w-4 text-muted-foreground" 
                    />
                    <span className="text-sm font-medium">Device ID</span>
                  </div>
                  <span className="text-sm font-mono text-foreground">{deviceState.device_id}</span>
                </div>

                <div className="flex items-center justify-between p-2 rounded-md bg-muted/30">
                  <div className="flex items-center space-x-2">
                    <Icon 
                      library="material" 
                      name="Label" 
                      size="sm" 
                      fallback="name" 
                      className="h-4 w-4 text-muted-foreground" 
                    />
                    <span className="text-sm font-medium">Device Name</span>
                  </div>
                  <span className="text-sm text-foreground">{deviceState.device_name || 'Unknown'}</span>
                </div>

                {deviceStructure && (
                  <div className="flex items-center justify-between p-2 rounded-md bg-muted/30">
                    <div className="flex items-center space-x-2">
                      <Icon 
                        library="material" 
                        name="Category" 
                        size="sm" 
                        fallback="class" 
                        className="h-4 w-4 text-muted-foreground" 
                      />
                      <span className="text-sm font-medium">Device Class</span>
                    </div>
                    <span className="text-sm text-foreground">{deviceStructure.deviceClass}</span>
                  </div>
                )}
              </div>
            </div>

            {/* Device-Specific State */}
            {renderDeviceSpecificState()}

            {/* Last Command Section */}
            {deviceState.last_command && (
              <div className="space-y-3">
                <h3 className="font-medium text-sm text-muted-foreground uppercase tracking-wider">
                  Last Command
                </h3>
                <div className="p-3 rounded-md bg-muted/30 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Action</span>
                    <span className="text-sm font-mono text-foreground">{deviceState.last_command.action}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Source</span>
                    <span className="text-sm text-foreground">{deviceState.last_command.source}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Time</span>
                    <span className="text-xs text-muted-foreground">
                      {new Date(deviceState.last_command.timestamp).toLocaleString()}
                    </span>
                  </div>
                  {deviceState.last_command.params && (
                    <div className="mt-2">
                      <span className="text-sm font-medium">Parameters</span>
                      <pre className="text-xs text-muted-foreground mt-1 p-2 bg-background rounded border">
                        {JSON.stringify(deviceState.last_command.params, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Error Section */}
            {deviceState.error && (
              <div className="space-y-3">
                <h3 className="font-medium text-sm text-destructive uppercase tracking-wider">
                  Error
                </h3>
                <div className="p-3 rounded-md bg-destructive/10 border border-destructive/20">
                  <p className="text-sm text-destructive">{deviceState.error}</p>
                </div>
              </div>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
}

export default DeviceStatePanel; 