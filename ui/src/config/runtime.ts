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

// Layer 3 (Step 2/3): devices whose page is rendered at RUNTIME from
// GET /devices/{id}/layout instead of the build-time .gen.tsx. Comma-separated
// allowlist; "*" enables all. Override via VITE_RUNTIME_LAYOUT_DEVICES (build) or
// window.RUNTIME_CONFIG.RUNTIME_LAYOUT_DEVICES (deploy); "" or "none" disables it.
// Step 3 rollout (device_ids, not config file names) — ALL device-category devices are now on the
// runtime renderer. WirenboardIR (commands/buttons): mf_amplifier, ld_player, video, vhs_player,
// upscaler; Revox reel_to_reel (playback). eMotiva (`processor`) + LG (`living_room_tv`,
// `children_room_tv`) + AppleTV (`appletv_living`, `appletv_children`) + Auralic (`streamer`) —
// api/slider devices (fixed-params flow + api-select param B5 incl. apps + slider valueField/valueParam).
// Only `kitchen_hood` (the sole device_category=appliance) is excluded — bespoke appliance pages are
// out of Layer-3-v1.
const RUNTIME_LAYOUT_DEFAULT = [
  // devices (device_ids) — all device_category devices; only kitchen_hood (appliance) excluded
  'mf_amplifier', 'ld_player', 'video', 'vhs_player', 'upscaler', 'reel_to_reel',
  'processor', 'living_room_tv', 'children_room_tv', 'appletv_living', 'appletv_children', 'streamer',
  // scenarios (scenario_ids) — Step 3 scenario rollout
  'movie_appletv', 'movie_ld', 'movie_vhs', 'movie_zappiti',
];
const parseLayoutDevices = (raw: string | undefined): Set<string> => {
  if (raw === undefined) return new Set(RUNTIME_LAYOUT_DEFAULT);
  const v = raw.trim();
  if (v === '' || v.toLowerCase() === 'none') return new Set();
  return new Set(v.split(',').map((s) => s.trim()).filter(Boolean));
};

export const runtimeLayoutDevices = parseLayoutDevices(
  runtimeOverrides.RUNTIME_LAYOUT_DEVICES ?? import.meta.env.VITE_RUNTIME_LAYOUT_DEVICES
);

export const isRuntimeLayoutEnabled = (deviceId: string): boolean =>
  runtimeLayoutDevices.has('*') || runtimeLayoutDevices.has(deviceId);
