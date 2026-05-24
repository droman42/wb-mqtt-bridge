// Runtime configuration served by /runtime-config.js, overwritten by the container
// at startup from environment variables (see docker-entrypoint.sh). Lets the MQTT
// URL be set per-deployment instead of being baked into the bundle at build time
// (action_plan P1 #4). Falls back to the Vite build-time env, then a localhost
// default, so local `vite dev` still works.
declare global {
  interface Window {
    RUNTIME_CONFIG?: {
      API_BASE_URL?: string;
      MQTT_URL?: string;
      VERSION?: string;
      RUNTIME_LAYOUT_DEVICES?: string;
    };
  }
}

const runtimeOverrides = (typeof window !== 'undefined' && window.RUNTIME_CONFIG) || {};

// Helper function to get API base URL
const getApiBaseUrl = () => {
  const envURL = import.meta.env.VITE_API_BASE_URL;
  if (envURL === undefined || envURL === null) {
    return 'http://localhost:8000'; // Development fallback
  }
  return envURL === '' ? '/api' : envURL; // Empty string means use nginx proxy
};

// Helper function to get SSE base URL
const getSSEBaseUrl = () => {
  const envURL = import.meta.env.VITE_SSE_BASE_URL;
  if (envURL === undefined || envURL === null) {
    return 'http://localhost:8000'; // Development: bypass proxy, use direct backend
  }
  return envURL === '' ? '' : envURL; // Empty string means use relative URLs
};

export const runtimeConfig = {
  statePollIntervalSec: 5,
  apiBaseUrl: getApiBaseUrl(),
  mqttUrl: runtimeOverrides.MQTT_URL || import.meta.env.VITE_MQTT_URL || 'ws://localhost:9001',
  
  // SSE Configuration
  sseBaseUrl: getSSEBaseUrl(),
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
