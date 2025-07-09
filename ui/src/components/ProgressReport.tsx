import React from 'react';
import { Icon } from './icons';
import { useProgressStore } from '../hooks/useProgressStore';
import { formatTimestamp } from '../lib/utils';

interface ProgressReportProps {
  deviceId?: string;
  scenarioId?: string;
  className?: string;
}

// Helper function to get event type icon and color
function getEventTypeDisplay(eventType: string) {
  switch (eventType) {
    case 'device_setup':
      return { icon: 'Settings', color: 'text-blue-600' };
    case 'connection_attempt':
      return { icon: 'Sync', color: 'text-yellow-600' };
    case 'connection_success':
      return { icon: 'CheckCircle', color: 'text-green-600' };
    case 'device_progress':
      return { icon: 'Schedule', color: 'text-blue-600' };
    case 'scenario_start':
      return { icon: 'PlayArrow', color: 'text-green-600' };
    case 'scenario_progress':
      return { icon: 'Schedule', color: 'text-blue-600' };
    case 'scenario_complete':
      return { icon: 'CheckCircle', color: 'text-green-600' };
    case 'scenario_error':
      return { icon: 'Error', color: 'text-red-600' };
    default:
      return { icon: 'Info', color: 'text-gray-600' };
  }
}

export function ProgressReport({ deviceId, scenarioId, className = '' }: ProgressReportProps) {
  const { getDeviceMessages, getScenarioMessages, clearMessages } = useProgressStore();
  
  const messages = deviceId 
    ? getDeviceMessages(deviceId)
    : scenarioId 
    ? getScenarioMessages(scenarioId)
    : [];

  const handleClear = () => {
    if (deviceId) {
      clearMessages(deviceId);
    } else if (scenarioId) {
      clearMessages(undefined, scenarioId);
    }
  };

  if (messages.length === 0) {
    return (
      <div className={`space-y-3 ${className}`}>
        <div className="flex items-center justify-between">
          <h3 className="font-medium text-sm text-muted-foreground uppercase tracking-wider">
            Progress Report
          </h3>
        </div>
        <div className="h-16 flex items-center justify-center text-xs text-muted-foreground border border-dashed border-muted-foreground/30 rounded-md">
          No progress messages
        </div>
      </div>
    );
  }

  return (
    <div className={`space-y-3 ${className}`}>
      <div className="flex items-center justify-between">
        <h3 className="font-medium text-sm text-muted-foreground uppercase tracking-wider">
          Progress Report
        </h3>
        <button
          onClick={handleClear}
          className="text-xs text-muted-foreground hover:text-foreground transition-colors"
          title="Clear progress messages"
        >
          <Icon library="material" name="Clear" size="sm" fallback="clear" className="h-3 w-3" />
        </button>
      </div>
      
      {/* Scrollable container with fixed height (3 lines high) */}
      <div className="h-16 overflow-y-auto bg-muted/20 border border-muted/40 rounded-md p-2 space-y-1">
        {messages.map((message) => {
          const eventDisplay = getEventTypeDisplay(message.eventType);
          return (
            <div key={message.id} className="text-xs font-mono leading-tight">
              <div className="flex items-start space-x-2">
                <span className="text-muted-foreground text-[10px] mt-0.5 flex-shrink-0">
                  {formatTimestamp(new Date(message.timestamp).getTime())}
                </span>
                <Icon 
                  library="material" 
                  name={eventDisplay.icon} 
                  size="sm" 
                  fallback="info" 
                  className={`h-3 w-3 mt-0.5 flex-shrink-0 ${eventDisplay.color}`}
                />
                <div className="flex-1">
                  {(message.deviceName || message.scenarioName) && (
                    <div className="text-muted-foreground text-[10px] font-medium">
                      {message.deviceName || message.scenarioName}
                    </div>
                  )}
                  <span className="text-foreground">
                    {message.message}
                  </span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
      
      {messages.length > 0 && (
        <div className="text-xs text-muted-foreground text-center">
          {messages.length} message{messages.length !== 1 ? 's' : ''} 
          {messages.length >= 10 && ' (showing recent 10)'}
        </div>
      )}
    </div>
  );
} 