import { useCallback, useEffect, useState } from 'react';

interface ProgressMessage {
  id: string;
  deviceId?: string;
  deviceName?: string;
  scenarioId?: string;
  scenarioName?: string;
  message: string;
  timestamp: string;
  eventType: string;
  type: 'device' | 'scenario';
}

interface ProgressStore {
  messages: ProgressMessage[];
  addMessage: (message: Omit<ProgressMessage, 'id' | 'timestamp'>) => void;
  getDeviceMessages: (deviceId: string) => ProgressMessage[];
  getScenarioMessages: (scenarioId: string) => ProgressMessage[];
  clearMessages: (deviceId?: string, scenarioId?: string) => void;
  getLatestDeviceMessage: (deviceId: string) => ProgressMessage | null;
  getLatestScenarioMessage: (scenarioId: string) => ProgressMessage | null;
}

// Simple progress store for managing progress messages
let progressMessages: ProgressMessage[] = [];
let progressListeners: (() => void)[] = [];

const notifyProgressListeners = () => {
  progressListeners.forEach(listener => listener());
};

export const useProgressStore = (): ProgressStore => {
  const [, forceUpdate] = useState({});
  
  useEffect(() => {
    const updateHandler = () => forceUpdate({});
    progressListeners.push(updateHandler);
    
    return () => {
      const index = progressListeners.indexOf(updateHandler);
      if (index > -1) {
        progressListeners.splice(index, 1);
      }
    };
  }, []);

  const addMessage = useCallback((message: Omit<ProgressMessage, 'id' | 'timestamp'>) => {
    const newMessage: ProgressMessage = {
      ...message,
      id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      timestamp: new Date().toISOString()
    };
    
    progressMessages = [...progressMessages, newMessage];
    
    // Keep only last 50 messages per type
    const deviceMessages = progressMessages.filter(m => m.type === 'device').slice(-25);
    const scenarioMessages = progressMessages.filter(m => m.type === 'scenario').slice(-25);
    progressMessages = [...deviceMessages, ...scenarioMessages];
    
    notifyProgressListeners();
  }, []);

  const getDeviceMessages = useCallback((deviceId: string) => {
    return progressMessages
      .filter(m => m.type === 'device' && m.deviceId === deviceId)
      .slice(-3); // Keep only last 3 messages
  }, []);

  const getScenarioMessages = useCallback((scenarioId: string) => {
    return progressMessages
      .filter(m => m.type === 'scenario' && m.scenarioId === scenarioId)
      .slice(-3); // Keep only last 3 messages
  }, []);

  const getLatestDeviceMessage = useCallback((deviceId: string) => {
    const messages = progressMessages
      .filter(m => m.type === 'device' && m.deviceId === deviceId);
    return messages.length > 0 ? messages[messages.length - 1] : null;
  }, []);

  const getLatestScenarioMessage = useCallback((scenarioId: string) => {
    const messages = progressMessages
      .filter(m => m.type === 'scenario' && m.scenarioId === scenarioId);
    return messages.length > 0 ? messages[messages.length - 1] : null;
  }, []);

  const clearMessages = useCallback((deviceId?: string, scenarioId?: string) => {
    if (deviceId) {
      progressMessages = progressMessages.filter(m => !(m.type === 'device' && m.deviceId === deviceId));
    } else if (scenarioId) {
      progressMessages = progressMessages.filter(m => !(m.type === 'scenario' && m.scenarioId === scenarioId));
    } else {
      progressMessages = [];
    }
    notifyProgressListeners();
  }, []);

  return {
    messages: progressMessages,
    addMessage,
    getDeviceMessages,
    getScenarioMessages,
    getLatestDeviceMessage,
    getLatestScenarioMessage,
    clearMessages
  };
}; 