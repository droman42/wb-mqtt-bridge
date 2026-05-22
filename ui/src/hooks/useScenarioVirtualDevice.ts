import { useState, useEffect, useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useScenarioWBConfig, useScenarioVirtualConfig, queryKeys } from './useApi';
import { useLogStore } from '../stores/useLogStore';
import type { ScenarioWBConfig, WBCommandDefinition } from '../types/api';

interface VirtualDeviceState {
  scenario_id: string;
  scenario_active: boolean;
  virtual_controls: Record<string, any>;
  last_command_result: string | null;
  startup_sequence_complete: boolean;
  shutdown_sequence_complete: boolean;
  [key: string]: any;
}

interface UseScenarioVirtualDeviceResult {
  // Configuration data
  config: ScenarioWBConfig | undefined;
  virtualConfig: any;
  isLoading: boolean;
  error: Error | null;
  
  // Virtual device state
  state: VirtualDeviceState;
  updateState: (updates: Partial<VirtualDeviceState>) => void;
  resetState: () => void;
  
  // Command execution
  executeCommand: (commandId: string, value?: any) => Promise<void>;
  isExecuting: boolean;
  
  // Utility functions
  getCommandValue: (commandId: string) => any;
  setCommandValue: (commandId: string, value: any) => void;
  isCommandReadonly: (commandId: string) => boolean;
}

export const useScenarioVirtualDevice = (scenarioId: string): UseScenarioVirtualDeviceResult => {
  const queryClient = useQueryClient();
  const { addLog } = useLogStore();

  // API hooks
  const { 
    data: config, 
    isLoading: configLoading, 
    error: configError 
  } = useScenarioWBConfig(scenarioId);
  
  const { 
    data: virtualConfig, 
    isLoading: virtualConfigLoading, 
    error: virtualConfigError 
  } = useScenarioVirtualConfig(scenarioId);

  // Local state
  const [state, setState] = useState<VirtualDeviceState>({
    scenario_id: scenarioId,
    scenario_active: false,
    virtual_controls: {},
    last_command_result: null,
    startup_sequence_complete: false,
    shutdown_sequence_complete: true
  });

  const [isExecuting, setIsExecuting] = useState(false);

  // Initialize state when config loads
  useEffect(() => {
    if (config && config.commands) {
      const initialControls: Record<string, any> = {};
      
      config.commands.forEach((command: WBCommandDefinition) => {
        // Set initial values based on command type and meta
        switch (command.type) {
          case 'switch':
            initialControls[command.id] = false;
            break;
          case 'range':
            initialControls[command.id] = command.meta?.min || 0;
            break;
          case 'text':
            initialControls[command.id] = '';
            break;
          case 'value':
            initialControls[command.id] = null;
            break;
          default:
            initialControls[command.id] = null;
        }
      });

      setState(prevState => ({
        ...prevState,
        scenario_id: scenarioId,
        virtual_controls: initialControls
      }));
    }
  }, [config, scenarioId]);

  // Update state function
  const updateState = useCallback((updates: Partial<VirtualDeviceState>) => {
    setState(prevState => ({ ...prevState, ...updates }));
    
    // Log state changes
    addLog({
      message: `Virtual device state updated for scenario: ${scenarioId}`,
      level: 'debug',
      source: 'VirtualDevice',
      category: 'state',
      deviceId: scenarioId,
      details: updates
    });
  }, [scenarioId, addLog]);

  // Reset state function
  const resetState = useCallback(() => {
    setState({
      scenario_id: scenarioId,
      scenario_active: false,
      virtual_controls: {},
      last_command_result: null,
      startup_sequence_complete: false,
      shutdown_sequence_complete: true
    });

    addLog({
      message: `Virtual device state reset for scenario: ${scenarioId}`,
      level: 'info',
      source: 'VirtualDevice',
      category: 'state',
      deviceId: scenarioId
    });
  }, [scenarioId, addLog]);

  // Command execution function
  const executeCommand = useCallback(async (commandId: string, value?: any) => {
    if (!config) {
      throw new Error('Configuration not loaded');
    }

    const command = config.commands.find(cmd => cmd.id === commandId);
    if (!command) {
      throw new Error(`Command not found: ${commandId}`);
    }

    setIsExecuting(true);

    try {
      addLog({
        message: `Executing virtual command: ${commandId} with value: ${value}`,
        level: 'info',
        source: 'VirtualDevice',
        category: 'action',
        deviceId: scenarioId,
        details: { commandId, value, command }
      });

      // Simulate command execution (in real implementation, this would call the backend)
      await new Promise(resolve => setTimeout(resolve, 100));

      // Update the virtual control state
      updateState({
        virtual_controls: {
          ...state.virtual_controls,
          [commandId]: value
        },
        last_command_result: `${commandId}: success`
      });

      // Invalidate related queries to trigger refresh
      queryClient.invalidateQueries({ 
        queryKey: queryKeys.scenarios.wbConfig(scenarioId) 
      });

      addLog({
        message: `Virtual command executed successfully: ${commandId}`,
        level: 'info',
        source: 'VirtualDevice',
        category: 'action',
        deviceId: scenarioId
      });

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      
      updateState({
        last_command_result: `${commandId}: error - ${errorMessage}`
      });

      addLog({
        message: `Virtual command failed: ${commandId} - ${errorMessage}`,
        level: 'error',
        source: 'VirtualDevice',
        category: 'error',
        deviceId: scenarioId
      });

      throw error;
    } finally {
      setIsExecuting(false);
    }
  }, [config, state.virtual_controls, updateState, queryClient, scenarioId, addLog]);

  // Utility functions
  const getCommandValue = useCallback((commandId: string) => {
    return state.virtual_controls[commandId];
  }, [state.virtual_controls]);

  const setCommandValue = useCallback((commandId: string, value: any) => {
    updateState({
      virtual_controls: {
        ...state.virtual_controls,
        [commandId]: value
      }
    });
  }, [state.virtual_controls, updateState]);

  const isCommandReadonly = useCallback((commandId: string) => {
    if (!config) return false;
    
    const command = config.commands.find(cmd => cmd.id === commandId);
    return command?.meta?.readonly || command?.type === 'value';
  }, [config]);

  // Combine loading and error states
  const isLoading = configLoading || virtualConfigLoading;
  const error = configError || virtualConfigError;

  return {
    // Configuration data
    config,
    virtualConfig,
    isLoading,
    error,
    
    // Virtual device state
    state,
    updateState,
    resetState,
    
    // Command execution
    executeCommand,
    isExecuting,
    
    // Utility functions
    getCommandValue,
    setCommandValue,
    isCommandReadonly
  };
}; 