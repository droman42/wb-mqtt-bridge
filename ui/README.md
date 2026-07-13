# Smart Home Remote UI v2

A modern, responsive web application for controlling smart home devices and
scenarios. Built with React 18, TypeScript, and Tailwind CSS. It renders a
remote-control-style page per device, generated at build time from the
`locveil-bridge` backend's OpenAPI contract.

## Features

- **Device Control**: Remote-control-style interfaces per device
- **Scenario Management**: Execute complex automation sequences
- **Real-time Updates**: Live device state via Server-Sent Events (SSE)
- **Responsive Design**: Optimized for iPad-portrait, works on desktop/tablet/mobile
- **Contract-driven generation**: Device pages + types generated from the backend's
  `openapi.json` (no Python in the build)
- **Internationalization**: English and Russian language support

## Technology Stack

- **Frontend**: React 18 + TypeScript + Vite 5
- **Styling**: Tailwind CSS v3 + shadcn/ui components
- **State Management**: Zustand + Immer
- **Data Fetching**: TanStack Query 5
- **Icons**: Material Design Icons (@mui/icons-material) + custom SVG fallbacks
- **Type generation**: `openapi-typescript` against the backend `openapi.json`
- **Deployment**: Docker + Nginx (ARMv7 for Wirenboard)

## How code generation works

The UI consumes the backend purely as a **contract** — there is no Python in the
build. The full cross-repo contract (artifacts, invariants, change playbook) is
documented in `docs/design/ui_backend_contract.md`. At build time the UI reads,
from the monorepo's `backend/` directory (`../backend` from here):

- `backend/openapi.json` — the committed OpenAPI snapshot (device-state model
  shapes live in `components.schemas`).
- `config/device-state-mapping.json` — maps each device class to its
  state model + device config files (owned by the backend).
- `config/devices/*.json` — device configurations.

One generator:

- `npm run gen:api-types` → `src/types/api.gen.ts` (REST request/response types from
  `openapi.json`, including the `LayoutManifest`). Committed.

> **Layer 3 (no more page codegen).** Device/scenario pages are no longer generated at build
> time — they render at **runtime** from the backend layout manifest (`GET /devices/{id}/layout`,
> `GET /scenario/{id}/layout`) via the generic `RemoteControlLayout`. Appliances use hand-written
> bespoke pages (`src/pages/appliances/`). See `docs/design/ui_backend_contract.md` → "Layout Manifest &
> Runtime Rendering".

## Quick Start

### Prerequisites

- Node.js 20+ — **no Python required** (the backend contract is the committed
  `../backend/openapi.json` in this monorepo)

### Installation

```bash
git clone https://github.com/locveil/locveil-bridge.git
cd locveil-bridge/ui
npm install

# Generate API types from the backend's openapi.json (pages render at runtime — no page codegen)
npm run gen:api-types

# Start the dev server
npm run dev
```

The application will be available at `http://localhost:3000`.

> If the backend's `openapi.json` changes, regenerate it on the backend side with
> `locveil-openapi` (committed there), then re-run the generators above.

## Configuration

### Device-state mapping (owned by the backend)

The mapping lives on the **backend** side at
`config/device-state-mapping.json`. Paths inside it are resolved
relative to the mapping file's own directory, so the same file works for both
the local monorepo layout and the CI/Docker build context. Format:

```json
{
  "WirenboardIRDevice": {
    "stateClassImport": "locveil_bridge.domain.devices.models:WirenboardIRState",
    "deviceConfigs": ["devices/ld_player.json"]
  },
  "ScenarioDevice": {
    "stateClassImport": "locveil_bridge.infrastructure.scenarios.models:ScenarioWBConfig",
    "scenarioConfigPath": "scenarios",
    "resolverType": "scenario_virtual_device"
  }
}
```

Only the `ClassName` segment of `stateClassImport` is used (looked up in
`openapi.json`); the module path is vestigial.

### Runtime configuration

Backend URLs are resolved at **container start**, not baked into the bundle:

- **API/SSE proxy target**: nginx is rendered from `nginx.conf.template` by
  `docker-entrypoint.sh`, substituting `BACKEND_HOST` / `BACKEND_PORT`
  (defaults `192.168.110.250` / `8000`).
- **MQTT broker URL**: written to `/runtime-config.js` (`window.RUNTIME_CONFIG`) by
  the entrypoint from the `MQTT_URL` env var, consumed by `src/config/runtime.ts`.

For local `vite dev`, `src/config/runtime.ts` falls back to `VITE_*` build-time env:

```bash
# .env (local dev only)
VITE_API_BASE_URL=        # empty = use the /api proxy
VITE_MQTT_URL=ws://localhost:9001
VITE_SSE_BASE_URL=        # empty = relative URLs (proxy)
```

## Available Scripts

- `npm run dev` / `npm run build` / `npm run preview`
- `npm run gen:api-types` — generate `src/types/api.gen.ts` from `openapi.json`
- `npm run check` — typecheck + lint (CI parity)
- `npm run lint` / `npm run lint:fix`
- `npm run typecheck` / `npm run typecheck:all`
- `npm run gen:favicon`

## Project Structure

```
src/
├── app/                # Entry point & root layout
├── components/         # UI components — RemoteControlLayout (the runtime remote renderer),
│                       #   RuntimeDevicePage/RuntimeScenarioPage, DeviceStatePanel, ...
├── lib/                # Runtime libs — layoutManifestAdapter (manifest → structure), IconResolver
├── pages/              # HomePage + appliances/ (hand-written bespoke appliance pages)
├── stores/             # Zustand state slices
├── hooks/              # Custom React hooks (useApi, useDeviceState, useEventSource, ...)
├── config/             # Runtime configuration (runtime.ts)
└── types/              # TypeScript definitions (api.gen.ts = OpenAPI types; RemoteControlLayout.ts)
```

## Docker Deployment

ARM v7 images are built via GitHub Actions for Wirenboard 7 (Node-only build, no
Python) and pushed to `ghcr.io/locveil/locveil-bridge-ui` with `latest` / `sha-<short>`
/ `vYYYYMMDD-<short>` tags. On the Wirenboard the UI runs from
`ops/docker-compose.yml` alongside the backend — host network, nginx on port
3000, proxying to the backend over loopback. See
[`ops/INSTALL.md`](../ops/INSTALL.md) for the deployment runbook (first install,
updates via `ops/update.sh`, rollback to a pinned tag).

To run the image standalone (outside compose):

```bash
docker run -d --name wb-ui --restart unless-stopped -p 3000:3000 \
  -e BACKEND_HOST=192.168.110.250 -e BACKEND_PORT=8000 \
  -e MQTT_URL=ws://192.168.110.250:9001 \
  ghcr.io/locveil/locveil-bridge-ui:latest
# Access at http://localhost:3000
```

For a local build, run from the **monorepo root** (the Dockerfile is built with the repo
root as context; it copies only `ui/` — the committed API types mean the build reads
nothing outside it):

```bash
docker build -t locveil-bridge-ui:local -f docker/Dockerfile.ui .
```

## Component Library

- **RemoteControlLayout**: the remote-control container + 7-zone layout
- **NavCluster**: directional navigation cluster
- **SliderControl**: debounced slider with icon and tick marks
- **PointerPad**: touch/mouse gesture input (relative/absolute modes)
- **DeviceStatePanel**: collapsible device state readout
- **LogPanel**: collapsible system log viewer
- **Navbar** / **Layout**: navigation + main app layout with panels

## State Management

Zustand stores: `useRoomStore` (room/device/scenario selection), `useLogStore`
(system log entries), `useSettingsStore` (theme, language, panel visibility).

## API Integration

Both REST (via the nginx `/api` proxy) and SSE (`/events/*`) are used. Device state
arrives over SSE; actions are sent via `POST /devices/{id}/action`.

## Performance & Browser Support

- Initial bundle ≤ ~300 kB gzipped; optimized for ARMv7 (Wirenboard)
- Chromium ≥ 110, Firefox ≥ 110, iOS Safari ≥ 15

## Contributing

1. From the monorepo, the backend contract lives in `../backend` (no `pip install` needed).
2. `npm install`
3. `npm run gen:api-types` (regenerate `api.gen.ts` after a backend API change)
4. `npm run dev`, then `npm run check` (typecheck + lint)
5. `npm run build`

## License

MIT
