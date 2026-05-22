/**
 * Runtime configuration (development defaults).
 *
 * In a deployed container this file is overwritten by docker-entrypoint.sh with
 * values from environment variables (MQTT_URL, ...), so the MQTT broker URL is
 * configured per-deployment instead of being baked into the bundle at build time.
 * For local `vite dev` these defaults apply (and src/config/runtime.ts also falls
 * back to VITE_* build-time env when a key is empty).
 */
window.RUNTIME_CONFIG = {
  API_BASE_URL: "",
  MQTT_URL: "",
  VERSION: "development"
};
