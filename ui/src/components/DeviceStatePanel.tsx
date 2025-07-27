import React from 'react';
import { Icon } from './icons';
import { useRoomStore } from '../stores/useRoomStore';
import { useSettingsStore } from '../stores/useSettingsStore';
import { useDeviceState } from '../hooks/useDeviceState';
import { useScenarioState } from '../hooks/useScenarioState';
import { useExecuteDeviceAction } from '../hooks/useApi';
import { Button } from './ui/button';
import { CollapsibleSection } from './ui/collapsible-section';
import { ProgressReport } from './ProgressReport';
import { RemoteDeviceStructure } from '../types/RemoteControlLayout';

interface SSEConnectionState {
  connected: boolean;
  error: string | null;
  reconnectAttempts: number;
}

interface SharedSSEState {
  deviceSSE: SSEConnectionState;
  scenarioSSE: SSEConnectionState;
  systemSSE: SSEConnectionState;
}

interface DeviceStatePanelProps {
  isOpen: boolean;
  className?: string;
  sseState?: SharedSSEState;
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

function DeviceStatePanel({ isOpen, className, sseState }: DeviceStatePanelProps) {
  const { selectedDeviceId, selectedScenarioId } = useRoomStore();
  const { setStatePanelOpen } = useSettingsStore();

  // Use appropriate state hook based on selection
  const { state: deviceState, isLoading: deviceLoading, error: deviceError, isConnected: deviceConnected } = useDeviceState(selectedDeviceId || '');
  const { state: scenarioState, isLoading: scenarioLoading, error: scenarioError, isConnected: scenarioConnected } = useScenarioState(selectedScenarioId || '');
  
  // Determine which state to use
  const isScenario = !!selectedScenarioId;
  const state = isScenario ? scenarioState : deviceState;
  const isLoading = isScenario ? scenarioLoading : deviceLoading;
  const error = isScenario ? scenarioError : deviceError;
  const isConnected = isScenario ? scenarioConnected : deviceConnected;
  
  // Get device action status
  const executeAction = useExecuteDeviceAction();

  // Provide default SSE state if not provided
  const defaultSSEState: SharedSSEState = {
    deviceSSE: { connected: false, error: null, reconnectAttempts: 0 },
    scenarioSSE: { connected: false, error: null, reconnectAttempts: 0 },
    systemSSE: { connected: false, error: null, reconnectAttempts: 0 }
  };
  const currentSSEState = sseState || defaultSSEState;

  // Get device structure for state interface
  const deviceStructure = getDeviceStructure(selectedDeviceId || '');

  if (!isOpen) return null;

  const renderDeviceSpecificState = () => {
    if (!deviceStructure?.stateInterface?.fields || !state) {
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
      <CollapsibleSection title="Device State" defaultOpen={true}>
        {deviceSpecificFields.map((field) => {
          const value = (state as any)[field.name];
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
      </CollapsibleSection>
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
        ) : state ? (
          <div className="space-y-6">
            {/* Connection Status */}
            <CollapsibleSection title="Connection Status" defaultOpen={true}>
              <div className="flex items-center justify-between p-2 rounded-md bg-muted/30">
                <div className="flex items-center space-x-2">
                  <div className={`w-3 h-3 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
                  <span className="text-sm font-medium">Device Status</span>
                </div>
                <span className={`text-sm ${isConnected ? 'text-green-600' : 'text-red-600'}`}>
                  {isConnected ? 'Connected' : 'Disconnected'}
                </span>
              </div>
              
              <div className="flex items-center justify-between p-2 rounded-md bg-muted/30">
                <div className="flex items-center space-x-2">
                  <div className={`w-3 h-3 rounded-full ${currentSSEState.deviceSSE.connected ? 'bg-green-500' : 'bg-red-500'}`} />
                  <span className="text-sm font-medium">SSE Connection</span>
                </div>
                <span className={`text-sm ${currentSSEState.deviceSSE.connected ? 'text-green-600' : 'text-red-600'}`}>
                  {currentSSEState.deviceSSE.connected ? 'Connected' : 'Disconnected'}
                </span>
              </div>
            </CollapsibleSection>

            {/* Device Info Section */}
            <CollapsibleSection title="Device Info" defaultOpen={true}>
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
                <span className="text-sm font-mono text-foreground">{isScenario ? (state as any).scenario_id : (state as any).device_id}</span>
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
                <span className="text-sm text-foreground">{isScenario ? (selectedScenarioId || 'Unknown') : ((state as any).device_name || 'Unknown')}</span>
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
            </CollapsibleSection>

            {/* Action Status Section */}
            <CollapsibleSection title="Action Status" defaultOpen={true}>
              {executeAction.isPending && (
                <div className="flex items-center justify-between p-2 rounded-md bg-blue-50/50 border border-blue-200/50">
                  <div className="flex items-center space-x-2">
                    <Icon 
                      library="material" 
                      name="Refresh" 
                      size="sm" 
                      fallback="loading" 
                      className="h-4 w-4 text-blue-600 animate-spin" 
                    />
                    <span className="text-sm font-medium text-blue-800">Executing Action</span>
                  </div>
                  <span className="text-sm text-blue-600">
                    {executeAction.variables?.action.action || 'Unknown Action'}
                  </span>
                </div>
              )}
              
              {executeAction.isError && executeAction.error && (
                <div className="p-3 rounded-md bg-destructive/10 border border-destructive/20">
                  <div className="flex items-start space-x-2">
                    <Icon 
                      library="material" 
                      name="Error" 
                      size="sm" 
                      fallback="error" 
                      className="h-4 w-4 text-destructive mt-0.5" 
                    />
                    <div className="flex-1">
                      <p className="text-sm font-medium text-destructive">Action Failed</p>
                      <p className="text-xs text-destructive/80 mt-1">
                        {executeAction.error.message}
                      </p>
                      {executeAction.variables?.action.action && (
                        <p className="text-xs text-muted-foreground mt-1">
                          Action: {executeAction.variables.action.action}
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              )}
              
              {!executeAction.isPending && !executeAction.isError && executeAction.isSuccess && (
                <div className="flex items-center justify-between p-2 rounded-md bg-green-50/50 border border-green-200/50">
                  <div className="flex items-center space-x-2">
                    <Icon 
                      library="material" 
                      name="CheckCircle" 
                      size="sm" 
                      fallback="check" 
                      className="h-4 w-4 text-green-600" 
                    />
                    <span className="text-sm font-medium text-green-800">Action Completed</span>
                  </div>
                  <span className="text-sm text-green-600">Ready</span>
                </div>
              )}
              
              {!executeAction.isPending && !executeAction.isError && !executeAction.isSuccess && (
                <div className="text-sm text-muted-foreground text-center py-2">
                  No recent actions
                </div>
              )}
            </CollapsibleSection>

            {/* Device-Specific State */}
            {renderDeviceSpecificState()}

            {/* Last Command Section */}
                          {!isScenario && (state as any).last_command && (
              <CollapsibleSection title="Last Command" defaultOpen={false}>
                <div className="p-3 rounded-md bg-muted/30 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Action</span>
                    <span className="text-sm font-mono text-foreground">{(state as any).last_command.action}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Source</span>
                    <span className="text-sm text-foreground">{(state as any).last_command.source}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Time</span>
                    <span className="text-xs text-muted-foreground">
                      {new Date((state as any).last_command.timestamp).toLocaleString()}
                    </span>
                  </div>
                                      {(state as any).last_command.params && (
                    <div className="mt-2">
                      <span className="text-sm font-medium">Parameters</span>
                      <pre className="text-xs text-muted-foreground mt-1 p-2 bg-background rounded border">
                        {JSON.stringify((state as any).last_command.params, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              </CollapsibleSection>
            )}

            {/* Error Section */}
                          {!isScenario && (state as any).error && (
              <CollapsibleSection title="Error" defaultOpen={true}>
                <div className="p-3 rounded-md bg-destructive/10 border border-destructive/20">
                  <p className="text-sm text-destructive">{(state as any).error}</p>
                </div>
              </CollapsibleSection>
            )}

            {/* Progress Report Section - Always at the bottom */}
            <ProgressReport deviceId={selectedDeviceId || undefined} />
          </div>
        ) : null}
      </div>
    </div>
  );
}

export default DeviceStatePanel; 