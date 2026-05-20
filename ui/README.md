# Smart Home Remote UI v2

A modern, responsive web application for controlling smart home devices and
scenarios. Built with React 18, TypeScript, and Tailwind CSS. It renders a
remote-control-style page per device, generated at build time from the
`wb-mqtt-bridge` backend's OpenAPI contract.

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
documented in the backend repo at `wb-mqtt-bridge/docs/ui_backend_contract.md`. At
build time the UI reads, from a sibling `wb-mqtt-bridge` checkout:

- `wb-mqtt-bridge/openapi.json` — the committed OpenAPI snapshot (device-state model
  shapes live in `components.schemas`).
- `wb-mqtt-bridge/config/device-state-mapping.json` — maps each device class to its
  state model + device config files (owned by the backend repo).
- `wb-mqtt-bridge/config/devices/*.json` — device configurations.

Two generators:

- `npm run gen:api-types` → `src/types/api.gen.ts` (REST request/response types from
  `openapi.json`).
- `npm run gen:device-pages` → per-device `*.gen.tsx` pages, `*.hooks.ts`, and
  `src/types/generated/*.state.ts` (device-state types read from `components.schemas`).

> Generated artifacts (`src/pages/**/*.gen.tsx`, `*.hooks.ts`,
> `src/types/generated/*.state.ts`, `index.gen.ts`) are **gitignored** — they are
> built fresh in CI/Docker, not committed. `src/types/api.gen.ts` is committed.

## Quick Start

### Prerequisites

- Node.js 20+
- A sibling `wb-mqtt-bridge` checkout (for device configs + `openapi.json`) — **no
  Python required**

### Installation

```bash
# Clone both repos side by side
git clone <frontend-repository-url> wb-mqtt-ui
git clone https://github.com/droman42/wb-mqtt-bridge.git

cd wb-mqtt-ui
npm install

# Generate API types + device pages from the sibling backend's openapi.json + mapping
npm run gen:api-types
npm run gen:device-pages -- --batch --mode=local \
  --mapping-file=../wb-mqtt-bridge/config/device-state-mapping.json --generate-router

# Start the dev server
npm run dev
```

The application will be available at `http://localhost:3000`.

> If the backend's `openapi.json` changes, regenerate it on the backend side with
> `wb-openapi` (committed there), then re-run the generators above.

## Configuration

### Device-state mapping (owned by the backend)

The mapping lives in the **backend** repo at
`wb-mqtt-bridge/config/device-state-mapping.json`. Paths inside it are resolved
relative to the mapping file's own directory, so the same file works for both the
local sibling layout and the CI/Docker subdir layout. Format:

```json
{
  "WirenboardIRDevice": {
    "stateClassImport": "wb_mqtt_bridge.domain.devices.models:WirenboardIRState",
    "deviceConfigs": ["devices/ld_player.json"]
  },
  "ScenarioDevice": {
    "stateClassImport": "wb_mqtt_bridge.infrastructure.scenarios.models:ScenarioWBConfig",
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
- `npm run gen:device-pages` — generate device pages + state types (see Quick Start)
- `npm run lint` / `npm run lint:fix`
- `npm run typecheck` / `npm run typecheck:scripts` / `npm run typecheck:all`
- `npm run validate:generated-code` / `npm run validate:components` / `npm run validate:all`
- `npm run gen:favicon`

## Project Structure

```
src/
├── app/                # Entry point & root layout
├── components/         # Reusable UI components (NavCluster, SliderControl,
│                       #   PointerPad, RemoteControlLayout, DeviceStatePanel, ...)
├── lib/                # Generators + device handlers (StateTypeGenerator, ZoneDetection)
├── pages/              # Generated device/scenario pages (*.gen.tsx — gitignored)
├── scripts/            # Build-time generator entry (generate-device-pages.ts)
├── stores/             # Zustand state slices
├── hooks/              # Custom React hooks
├── config/             # Runtime configuration (runtime.ts)
└── types/              # TypeScript definitions (api.gen.ts, generated/*.state.ts)
```

## Docker Deployment

ARM v7 images are built via GitHub Actions for Wirenboard 7 (Node-only build, no
Python). See [docs/deployment.md](docs/deployment.md) and
[docs/deployment-network-config.md](docs/deployment-network-config.md).

```bash
# Download the latest build artifact and load it
gunzip wb-mqtt-ui.tar.gz && docker load < wb-mqtt-ui.tar

# Run, pointing at your backend + MQTT broker (defaults shown)
docker run -d --name wb-ui --restart unless-stopped -p 3000:3000 \
  -e BACKEND_HOST=192.168.110.250 -e BACKEND_PORT=8000 \
  -e MQTT_URL=ws://192.168.110.250:9001 \
  wb-mqtt-ui:latest
# Access at http://WIRENBOARD_IP:3000
```

For a local build, ensure a sibling `wb-mqtt-bridge` checkout is present (the
Dockerfile copies it into the build context), then `docker build -t wb-mqtt-ui:local .`.

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

1. Ensure a sibling `wb-mqtt-bridge` checkout is present (no `pip install` needed).
2. `npm install`
3. Generate: `npm run gen:api-types` and `npm run gen:device-pages` (see Quick Start)
4. `npm run dev`, then `npm run typecheck:all && npm run lint && npm run validate:all`
5. `npm run build`

## License

MIT
