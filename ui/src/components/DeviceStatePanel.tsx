import React from 'react';
import { XMarkIcon } from '@heroicons/react/24/solid';
import { useRoomStore } from '../stores/useRoomStore';
import { useSettingsStore } from '../stores/useSettingsStore';
import { useDeviceState } from '../hooks/useApi';
import { Button } from './ui/button';

interface DeviceStatePanelProps {
  isOpen: boolean;
  className?: string;
}

function DeviceStatePanel({ isOpen, className }: DeviceStatePanelProps) {
  const { selectedDeviceId } = useRoomStore();
  const { setStatePanelOpen } = useSettingsStore();

  // Use the shared device state hook with polling
  const { data: deviceState, isLoading, error } = useDeviceState(selectedDeviceId || '');

  if (!isOpen) return null;

  return (
    <div className={`bg-card border-l border-border ${className}`}>
      <div className="h-full flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-border">
          <h2 className="text-lg font-semibold">Device State</h2>
          <Button 
            variant="ghost" 
            size="icon"
            onClick={() => setStatePanelOpen(false)}
          >
            <XMarkIcon className="h-5 w-5" />
          </Button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-4">
          {!selectedDeviceId ? (
            <p className="text-muted-foreground">No device selected</p>
          ) : isLoading ? (
            <p className="text-muted-foreground">Loading device state...</p>
          ) : error ? (
            <p className="text-destructive">Error loading device state</p>
          ) : deviceState ? (
            <div className="space-y-4">
              <div className="flex items-center space-x-2">
                <div className={`w-3 h-3 rounded-full bg-green-500`} />
                <span className="font-medium">{deviceState.deviceName}</span>
              </div>
              
              {deviceState.lastCommand && (
                <div>
                  <span className="text-sm text-muted-foreground">Last command: </span>
                  <span className="text-sm">{deviceState.lastCommand.action}</span>
                </div>
              )}

              {deviceState.error && (
                <div className="text-destructive text-sm">
                  Error: {deviceState.error}
                </div>
              )}

              <div className="space-y-2">
                <h3 className="font-medium">Device Info</h3>
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">ID:</span>
                  <span>{deviceState.deviceId}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Name:</span>
                  <span>{deviceState.deviceName}</span>
                </div>
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

export default DeviceStatePanel; 