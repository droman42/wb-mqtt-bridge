# Network Configuration for Deployment

## Problem

When the UI runs in a container, `localhost` refers to the container, not the host —
so a frontend pointed at `localhost:8000` fails with `AxiosError: Network Error`.
The UI solves this by talking to the backend through the nginx proxy, with the proxy
target and MQTT URL configured **at container start** (not baked into the bundle).

## How it works

- **API/SSE** use relative URLs (`/api/*`, `/events/*`) served by nginx, which proxies
  to the backend. The proxy target is `${BACKEND_HOST}:${BACKEND_PORT}`, substituted
  into `nginx.conf` from `nginx.conf.template` by `docker-entrypoint.sh` at startup.
- **MQTT** URL is written to `/runtime-config.js` (`window.RUNTIME_CONFIG.MQTT_URL`)
  by the entrypoint from the `MQTT_URL` env var, and read by `src/config/runtime.ts`.

Defaults (if env vars are unset): `BACKEND_HOST=192.168.110.250`, `BACKEND_PORT=8000`,
`MQTT_URL=ws://192.168.110.250:9001`.

## Local development (`vite dev`)

No container, so `src/config/runtime.ts` falls back to `VITE_*` build-time env:

```bash
# .env
VITE_API_BASE_URL=        # empty -> use the /api proxy (recommended)
VITE_SSE_BASE_URL=        # empty -> relative /events URLs
VITE_MQTT_URL=ws://localhost:9001
```

To develop against a remote backend, set the absolute URLs (e.g.
`VITE_API_BASE_URL=http://192.168.110.250:8000`).

## Production (Docker)

Set the backend/MQTT location with environment variables at `docker run` time —
nothing about the network is hardcoded in the image:

```bash
docker run -d --name wb-ui --restart unless-stopped -p 3000:3000 \
  -e BACKEND_HOST=192.168.110.250 \
  -e BACKEND_PORT=8000 \
  -e MQTT_URL=ws://192.168.110.250:9001 \
  wb-mqtt-ui:latest
```

### Container network flow

```
Browser → Frontend (container:3000)
            ├─ /api/*    → nginx → http://${BACKEND_HOST}:${BACKEND_PORT}/
            ├─ /events/* → nginx → http://${BACKEND_HOST}:${BACKEND_PORT}/events/  (SSE; proxy_buffering off)
            └─ MQTT (ws) → ${MQTT_URL}  (direct from the browser)
```

## Key files

- **`nginx.conf.template`** — `proxy_pass http://${BACKEND_HOST}:${BACKEND_PORT}/;`
  for `/api/` and `/events/`. Rendered to `/etc/nginx/nginx.conf` at startup.
- **`docker-entrypoint.sh`** — `envsubst` the template (only `BACKEND_HOST`/
  `BACKEND_PORT`, so nginx's own `$host` etc. survive) + writes `runtime-config.js`,
  then `exec nginx`.
- **`src/config/runtime.ts`** — reads `window.RUNTIME_CONFIG.MQTT_URL` first, then
  `VITE_MQTT_URL`, then a localhost default. API/SSE base URLs default to the proxy
  (relative) unless `VITE_*` overrides are set.

## Troubleshooting

**"Network Error" in the browser** — confirm the rendered proxy target:
`docker exec wb-ui cat /etc/nginx/nginx.conf | grep proxy_pass`, then test the
backend directly: `curl http://<backend-host>:8000/system`.

**SSE not streaming** — verify `/events/` has `proxy_buffering off` (it does in the
template) and the backend stream works:
`curl -H "Accept: text/event-stream" http://<backend-host>:8000/events/devices`.

**MQTT WebSocket issues** — check the resolved URL:
`docker exec wb-ui cat /usr/share/nginx/html/runtime-config.js`; verify the broker
listens on the WS port and the firewall allows it.
