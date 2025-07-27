import { useState, useEffect } from 'react';
import { useSpecificScenarioState } from './useApi';
import type { ScenarioState } from '../types/api';

export interface EnhancedScenarioStateHook {
  state: ScenarioState | null;
  isLoading: boolean;
  error: Error | null;
  isConnected: boolean;
}

export function useScenarioState(scenarioId: string): EnhancedScenarioStateHook {
  const { data: backendState, isLoading, error: queryError } = useSpecificScenarioState(scenarioId);
  
  // Local state management
  const [localState, setLocalState] = useState<ScenarioState | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  
  // Update local state when backend data changes
  useEffect(() => {
    if (backendState) {
      setLocalState(backendState);
      setIsConnected(true);
    }
  }, [backendState]);
  
  // Handle connection status based on query state
  useEffect(() => {
    if (queryError) {
      setIsConnected(false);
      setLocalState(null);
    } else if (!isLoading && backendState) {
      setIsConnected(true);
    }
  }, [queryError, isLoading, backendState]);
  
  return {
    state: localState,
    isLoading,
    error: queryError,
    isConnected,
  };
} 