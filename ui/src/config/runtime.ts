export const runtimeConfig = {
  statePollIntervalSec: 5,
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
  mqttUrl: import.meta.env.VITE_MQTT_URL || 'ws://localhost:9001',
  defaultLanguage: 'en',
  maxLogEntries: 1000,
  debounceDelaySec: 0.3,
} as const; 