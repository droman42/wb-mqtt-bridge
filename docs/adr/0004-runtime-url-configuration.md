# ADR 0004 — Configure backend/MQTT URLs at container runtime, not build time

- **Status:** Accepted
- **Date:** 2026-05-20

## Context

The UI hardcoded the backend location: `nginx.conf` proxied to a literal
`192.168.110.250:8000`, and `VITE_MQTT_URL=ws://192.168.110.250:9001` was baked into the
JS bundle at build time. The same image could therefore only ever talk to one network —
bad for moving the backend, and a blocker for any future community release.

## Decision

Resolve both URLs **at container start**:

- nginx config is rendered from `nginx.conf.template` by `docker-entrypoint.sh` using
  `envsubst` scoped to `${BACKEND_HOST}` / `${BACKEND_PORT}` (so nginx's own `$host`,
  `$remote_addr`, … survive).
- The MQTT URL is written to `/runtime-config.js` (`window.RUNTIME_CONFIG.MQTT_URL`) by
  the entrypoint from the `MQTT_URL` env var, and read by `src/config/runtime.ts`.
- Defaults preserve the previous values, so existing deployments behave identically with
  no env vars set. `VITE_*` remain as the local-`vite dev` fallback only.

## Consequences

- One image runs against any backend/broker via `-e BACKEND_HOST/BACKEND_PORT/MQTT_URL`.
- Reuses the project's existing-but-unwired `window.RUNTIME_CONFIG` pattern.
- API/SSE were already relative URLs behind the nginx proxy, so only the proxy *target*
  and the MQTT URL needed parameterizing.
