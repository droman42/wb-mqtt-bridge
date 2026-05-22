# Deployment Guide

## Overview

Automated Docker build and deployment for `wb-mqtt-ui` on ARM v7 devices
(Wirenboard 7). The build is **Node-only** — device pages and TypeScript types are
generated from the backend's committed `openapi.json` contract, so no Python /
`pip install` is involved.

## Architecture

- **Two-stage Docker build**: Node.js builder → `nginx:alpine` production stage.
- **Contract-driven generation**: device pages + types from `wb-mqtt-bridge`'s
  `openapi.json` (+ `config/device-state-mapping.json` + `config/devices/*.json`),
  read from the sibling checkout copied into the build context.
- **GitHub Actions**: builds the ARM image and uploads it as an artifact.
- **Runtime configuration**: backend proxy target and MQTT URL are set per-deployment
  via environment variables (no IPs baked into the image).
- **Port 3000**: avoids conflicts with system nginx on port 80.

## GitHub Actions workflow

`.github/workflows/build-arm.yml`:

1. Checks out the frontend repo + `wb-mqtt-bridge` (as `./wb-mqtt-bridge`).
2. Sets up Node.js (no Python step).
3. `npm ci`.
4. Generates pages/types: `npm run gen:device-pages -- --batch --mode=package
   --mapping-file=wb-mqtt-bridge/config/device-state-mapping.json --generate-router`.
5. Validates: `typecheck:all`, `lint`, `validate:generated-code`, `validate:components`.
6. Builds the ARM v7 image and uploads the compressed artifact.

Triggered on push / PR to `main`.

## Device-state mapping

The mapping is owned by the **backend** repo
(`wb-mqtt-bridge/config/device-state-mapping.json`) and uses
`stateClassImport` + `deviceConfigs` (and `scenarioConfigPath` for scenarios), with
paths relative to the mapping file's directory. The UI build references it via
`--mapping-file=wb-mqtt-bridge/config/device-state-mapping.json`. See the repo
`README.md` for the format.

## Deployment process

### 1. Download the artifact

```bash
gh auth login   # one-time
gh run download --repo <owner>/wb-mqtt-ui --name wb-mqtt-ui-image
```

### 2. Load the image

```bash
gunzip wb-mqtt-ui.tar.gz
docker load < wb-mqtt-ui.tar
```

### 3. Run the container

Point it at your backend and MQTT broker via env vars (defaults shown):

```bash
docker stop wb-ui 2>/dev/null || true; docker rm wb-ui 2>/dev/null || true
docker run -d \
  --name wb-ui \
  --restart unless-stopped \
  -p 3000:3000 \
  -e BACKEND_HOST=192.168.110.250 \
  -e BACKEND_PORT=8000 \
  -e MQTT_URL=ws://192.168.110.250:9001 \
  wb-mqtt-ui:latest
```

`docker-entrypoint.sh` renders `nginx.conf` from the template (substituting
`BACKEND_HOST`/`BACKEND_PORT`) and writes `/runtime-config.js` (from `MQTT_URL`)
before starting nginx. If you omit the env vars, the defaults above apply.

### 4. Verify

```bash
docker ps | grep wb-ui
docker logs wb-ui            # should print the configured backend + MQTT_URL
curl http://localhost:3000/  # then open http://<wirenboard-ip>:3000
```

## Container features

- **~30 MB** final image (`nginx:alpine`); no Node.js runtime in production.
- **Health check** built in (`docker inspect wb-ui | grep -A5 Health`).
- **nginx** serves static assets with long cache headers, SPA routing, and proxies
  `/api/*` + `/events/*` to the backend (`proxy_buffering off` for SSE).

## Troubleshooting

**Build fails at generation** — ensure the `wb-mqtt-bridge` checkout is present in the
build context and contains `openapi.json` + `config/device-state-mapping.json`.
Reproduce locally:

```bash
# with a sibling ../wb-mqtt-bridge checkout
npm ci
npm run gen:device-pages -- --batch --mode=local \
  --mapping-file=../wb-mqtt-bridge/config/device-state-mapping.json --generate-router
npm run typecheck:all && npm run lint
```

**Container starts but can't reach the backend** — check the rendered config:
`docker exec wb-ui cat /etc/nginx/nginx.conf | grep proxy_pass` and confirm
`BACKEND_HOST`/`BACKEND_PORT`. For MQTT, `docker exec wb-ui cat
/usr/share/nginx/html/runtime-config.js`.

**Port already in use** — `docker run ... -p 3001:3000 ...`.

## Update process

Push to `main` → GitHub Actions rebuilds the ARM image → download and redeploy:

```bash
gh run download --repo <owner>/wb-mqtt-ui --name wb-mqtt-ui-image
gunzip wb-mqtt-ui.tar.gz && docker load < wb-mqtt-ui.tar
docker stop wb-ui && docker rm wb-ui
docker run -d --name wb-ui --restart unless-stopped -p 3000:3000 \
  -e BACKEND_HOST=... -e BACKEND_PORT=... -e MQTT_URL=... wb-mqtt-ui:latest
```

## Security considerations

- The `wb-mqtt-bridge` repo must be reachable by GitHub Actions (public, or a token).
- Device configurations should not contain secrets.
- Only port 3000 is exposed; the backend is reached via the nginx proxy.
