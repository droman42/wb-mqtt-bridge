export const runtimeConfig = {
  statePollIntervalSec: 5,
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
  mqttUrl: import.meta.env.VITE_MQTT_URL || 'ws://localhost:9001',
  
  // SSE Configuration
  sseBaseUrl: import.meta.env.VITE_SSE_BASE_URL || 'http://localhost:8000',
  sseDevicesPath: '/events/devices',
  sseScenariosPath: '/events/scenarios', 
  sseSystemPath: '/events/system',
  
  defaultLanguage: 'en',
  maxLogEntries: 1000,
  debounceDelaySec: 0.3,
} as const;

// Helper function to build full SSE URLs
export const getSSEUrl = (path: string): string => {
  return runtimeConfig.sseBaseUrl ? 
    `${runtimeConfig.sseBaseUrl}${path}` : 
    path; // Use relative URL for proxy
}; 