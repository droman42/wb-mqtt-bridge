import React, { useState } from 'react';
import { Button } from './ui/button';
import { cn } from '../lib/utils';
import { useScenarioWBConfig, useExecuteDeviceAction } from '../hooks/useApi';
import { useLogStore } from '../stores/useLogStore';
import type { WBCommandDefinition } from '../types/api';

interface ScenarioVirtualDeviceControlsProps {
  scenarioId: string;
  className?: string;
}

interface WBControlProps {
  command: WBCommandDefinition;
  scenarioId: string;
  onExecute: (commandId: string, value?: any) => void;
  disabled?: boolean;
}

const WBControl: React.FC<WBControlProps> = ({ command, scenarioId, onExecute, disabled = false }) => {
  const [value, setValue] = useState<any>(null);

  const handleExecute = () => {
    onExecute(command.id, value);
  };

  switch (command.type) {
    case 'switch':
      return (
        <div className="flex items-center justify-between p-3 border rounded-lg">
          <span className="text-sm font-medium">{command.title}</span>
          <Button
            variant={value ? "default" : "outline"}
            size="sm"
            onClick={() => {
              const newValue = !value;
              setValue(newValue);
              onExecute(command.id, newValue);
            }}
            disabled={disabled}
          >
            {value ? 'ON' : 'OFF'}
          </Button>
        </div>
      );

    case 'pushbutton':
      return (
        <div className="flex items-center justify-between p-3 border rounded-lg">
          <span className="text-sm font-medium">{command.title}</span>
          <Button
            variant="outline"
            size="sm"
            onClick={handleExecute}
            disabled={disabled}
          >
            Execute
          </Button>
        </div>
      );

    case 'range': {
      const min = command.meta?.min || 0;
      const max = command.meta?.max || 100;
      const step = command.meta?.step || 1;
      
      return (
        <div className="p-3 border rounded-lg space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">{command.title}</span>
            <span className="text-sm text-muted-foreground">
              {value || min}{command.meta?.units || ''}
            </span>
          </div>
          <div className="flex items-center space-x-2">
            <input
              type="range"
              min={min}
              max={max}
              step={step}
              value={value || min}
              onChange={(e) => setValue(Number(e.target.value))}
              className="flex-1"
              disabled={disabled}
            />
            <Button
              variant="outline"
              size="sm"
              onClick={handleExecute}
              disabled={disabled}
            >
              Set
            </Button>
          </div>
        </div>
      );
    }

    case 'text':
      return (
        <div className="p-3 border rounded-lg space-y-2">
          <label className="text-sm font-medium">{command.title}</label>
          <div className="flex items-center space-x-2">
            <input
              type="text"
              value={value || ''}
              onChange={(e) => setValue(e.target.value)}
              className="flex-1 px-3 py-2 border rounded-md text-sm"
              placeholder="Enter value..."
              disabled={disabled}
            />
            <Button
              variant="outline"
              size="sm"
              onClick={handleExecute}
              disabled={disabled}
            >
              Send
            </Button>
          </div>
        </div>
      );

    case 'value':
      return (
        <div className="p-3 border rounded-lg">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">{command.title}</span>
            <span className="text-sm text-muted-foreground">
              {value || 'No value'}
            </span>
          </div>
        </div>
      );

    default:
      return (
        <div className="p-3 border rounded-lg">
          <span className="text-sm text-muted-foreground">
            Unsupported control type: {command.type}
          </span>
        </div>
      );
  }
};

export const ScenarioVirtualDeviceControls: React.FC<ScenarioVirtualDeviceControlsProps> = ({
  scenarioId,
  className
}) => {
  const { data: config, isLoading, error } = useScenarioWBConfig(scenarioId);
  const executeAction = useExecuteDeviceAction();
  const { addLog } = useLogStore();

  const handleCommandExecute = async (commandId: string, value?: any) => {
    if (!config) return;

    try {
      addLog({
        message: `Executing virtual command: ${commandId}`,
        level: 'info',
        source: 'VirtualDevice',
        category: 'action'
      });

      // Execute the command through the virtual device interface
      await executeAction.mutateAsync({
        deviceId: config.device_id,
        action: {
          action: commandId,
          params: value !== undefined ? { value } : undefined
        }
      });

      addLog({
        message: `Virtual command executed successfully: ${commandId}`,
        level: 'info',
        source: 'VirtualDevice',
        category: 'action'
      });

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      addLog({
        message: `Virtual command failed: ${commandId} - ${errorMessage}`,
        level: 'error',
        source: 'VirtualDevice',
        category: 'error'
      });
    }
  };

  if (isLoading) {
    return (
      <div className={cn("p-6 space-y-4", className)}>
        <div className="animate-pulse space-y-3">
          <div className="h-4 bg-gray-200 rounded w-1/4"></div>
          <div className="h-12 bg-gray-200 rounded"></div>
          <div className="h-12 bg-gray-200 rounded"></div>
          <div className="h-12 bg-gray-200 rounded"></div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={cn("p-6 text-center", className)}>
        <div className="text-destructive mb-2">
          Failed to load virtual device configuration
        </div>
        <div className="text-sm text-muted-foreground">
          {error.message}
        </div>
      </div>
    );
  }

  if (!config) {
    return (
      <div className={cn("p-6 text-center text-muted-foreground", className)}>
        No virtual device configuration available for scenario: {scenarioId}
      </div>
    );
  }

  // Sort commands by order if available
  const sortedCommands = [...config.commands].sort((a, b) => 
    (a.order || 0) - (b.order || 0)
  );

  return (
    <div className={cn("p-6 space-y-4", className)}>
      <div className="border-b pb-4">
        <h3 className="text-lg font-semibold">{config.device_name}</h3>
        <p className="text-sm text-muted-foreground">
          Virtual Device Controls for {config.scenario_id}
        </p>
      </div>

      <div className="space-y-3">
        {sortedCommands.map((command) => (
          <WBControl
            key={command.id}
            command={command}
            scenarioId={scenarioId}
            onExecute={handleCommandExecute}
            disabled={executeAction.isPending}
          />
        ))}
      </div>

      {config.controls && config.controls.length > 0 && (
        <div className="border-t pt-4">
          <h4 className="text-sm font-medium mb-3">Device Status</h4>
          <div className="space-y-2">
            {config.controls.map((control, index) => (
              <div key={index} className="flex items-center justify-between p-2 bg-gray-50 rounded">
                <span className="text-sm">{control.title}</span>
                <span className="text-sm font-mono">
                  {control.value !== undefined ? String(control.value) : 'N/A'}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {executeAction.isPending && (
        <div className="fixed inset-0 bg-black/20 flex items-center justify-center z-50">
          <div className="bg-white p-4 rounded-lg shadow-lg">
            <div className="flex items-center space-x-2">
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-primary"></div>
              <span className="text-sm">Executing command...</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}; 