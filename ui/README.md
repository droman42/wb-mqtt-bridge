# Smart Home Remote UI v2

A modern, responsive web application for controlling smart home devices and scenarios. Built with React 18, TypeScript, and Tailwind CSS.

## Features

- **Device Control**: Intuitive interfaces for smart home devices
- **Scenario Management**: Execute complex automation sequences
- **Real-time Updates**: Live device state monitoring and system logs
- **Responsive Design**: Works on desktop, tablet, and mobile devices
- **Build-time Generation**: Pages generated from YAML prompt files
- **Multi-transport**: Supports both REST API and MQTT communication
- **Internationalization**: English and Russian language support

## Technology Stack

- **Frontend**: React 18 + TypeScript + Vite 5
- **Styling**: Tailwind CSS v3 + shadcn/ui components
- **State Management**: Zustand + Immer
- **Data Fetching**: TanStack Query 5
- **Icons**: Material Design Icons (@mui/icons-material) + Custom SVG fallbacks
- **Testing**: Jest + React Testing Library
- **Deployment**: Docker + Nginx

## Quick Start

### Prerequisites

- Node.js 18+ 
- npm or pnpm

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd smart-home-ui-v2

# Install dependencies
npm install

# Generate pages from prompts
npm run gen

# Start development server
npm run dev
```

The application will be available at `http://localhost:3000`.

## Project Structure

```
src/
├── api/                # Swagger-generated clients
├── app/                # Entry point & root layout
├── components/         # Reusable UI components
│   ├── NavCluster.tsx
│   ├── SliderControl.tsx
│   ├── PointerPad.tsx
│   ├── DeviceStatePanel.tsx
│   └── LogPanel.tsx
├── pages/              # Generated React pages
├── prompts/            # Developer prompt sources
├── scripts/            # Build-time generators
├── stores/             # Zustand state slices
├── hooks/              # Custom React hooks
├── config/             # Runtime configuration
└── types/              # TypeScript definitions
```

## Creating Device Controls

Device control interfaces are generated from YAML prompt files:

```yaml
# src/prompts/my_device.prompt.yaml
id: my_device
title:
  en: My Device
  ru: Моё устройство

menu:
  up: navigate_up
  down: navigate_down
  ok: select

sliders:
  - id: volume
    min: 0
    max: 100
    icon: SpeakerWaveIcon
    transport: api

buttons:
  - id: power
    label:
      en: Power
      ru: Питание
    transport: mqtt
```

After creating a prompt file, run `npm run gen` to generate the React component.

## Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run gen` - Generate pages from prompts
- `npm run preview` - Preview production build
- `npm run test` - Run tests
- `npm run lint` - Lint code
- `npm run typecheck` - Type check

## Docker Deployment

### Automated ARM Builds (Phase 2)

The project now supports automated ARM v7 Docker builds via GitHub Actions for Wirenboard 7 deployment:

```bash
# Download latest build from GitHub Actions
gh run download --repo YOUR_USERNAME/wb-mqtt-ui --name wb-mqtt-ui-image

# Deploy to Wirenboard 7
gunzip wb-mqtt-ui.tar.gz
docker load < wb-mqtt-ui.tar
docker run -d --name wb-ui --restart unless-stopped -p 3000:3000 wb-mqtt-ui:latest

# Access at http://WIRENBOARD_IP:3000
```

**Key Features:**
- ✅ **ARM v7 optimized** for Wirenboard 7
- ✅ **GitHub artifacts** - no container registry needed
- ✅ **Two-stage builds** - ~30MB final image (nginx:alpine)
- ✅ **Port 3000** - avoids system nginx conflicts
- ✅ **Automated device page generation** during build

See [docs/deployment.md](docs/deployment.md) for complete deployment guide.

### Manual Docker Build

For local development and testing:

```bash
# Clone config repo
git clone https://github.com/YOUR_USERNAME/wb-mqtt-bridge.git

# Build image locally
docker build -t wb-mqtt-ui:local .

# Run locally
docker run -d --name wb-ui-local -p 3000:3000 wb-mqtt-ui:local
```

## Configuration

Runtime configuration is managed in `src/config/runtime.ts`:

```typescript
export const runtimeConfig = {
  statePollIntervalSec: 5,
  apiBaseUrl: '/api',
  mqttUrl: 'ws://localhost:9001',
  sseBaseUrl: '', // Environment-driven SSE configuration
  defaultLanguage: 'en',
  maxLogEntries: 1000,
  debounceDelaySec: 0.3,
};
```

### Environment Variables

Create a `.env` file in the project root to customize configuration:

```bash
# API Base URL for regular HTTP requests
VITE_API_BASE_URL=http://localhost:8000

# MQTT WebSocket URL  
VITE_MQTT_URL=ws://localhost:9001

# SSE (Server-Sent Events) Configuration
# Leave empty to use relative URLs (proxy mode - recommended)
VITE_SSE_BASE_URL=

# Alternative: Use absolute URL for direct backend connection
# VITE_SSE_BASE_URL=http://192.168.110.250:8000

# Alternative: For production with different backend
# VITE_SSE_BASE_URL=https://api.yourdomain.com
```

**SSE Behavior:**
- **Empty `VITE_SSE_BASE_URL`**: Uses relative URLs (`/events/devices`) → Works with Vite proxy (dev) or nginx proxy (production)
- **Set `VITE_SSE_BASE_URL`**: Uses absolute URLs (`http://backend:8000/events/devices`) → Direct backend connection

## Component Library

### Core Components

- **NavCluster**: 3x3 navigation matrix with directional controls
- **SliderControl**: Debounced slider with icon and tick marks
- **PointerPad**: Touch/mouse gesture input (relative/absolute modes)
- **DeviceStatePanel**: Collapsible device information panel
- **LogPanel**: Collapsible system log viewer

### Layout Components

- **Navbar**: Top navigation with dropdowns and controls
- **Layout**: Main application layout with panels

## State Management

The application uses Zustand for state management:

- **useRoomStore**: Room, device, and scenario selection
- **useLogStore**: System log entries
- **useSettingsStore**: Theme, language, and panel visibility

## API Integration

The application supports both REST API and MQTT transports:

- REST endpoints follow the pattern `/api/devices/{id}/state`
- MQTT topics are configurable per control
- Device state polling occurs every 5 seconds (configurable)

## Performance

- Initial bundle ≤ 300 kB gzipped
- Panel animations ≤ 200 ms
- Time-to-interactive ≤ 100 ms on LAN
- Optimized for ARMv7 (Wirenboard) devices

## Browser Support

- Chromium ≥ 110
- Firefox ≥ 110  
- iOS Safari ≥ 15

## Contributing

1. Create prompt files in `src/prompts/`
2. Run `npm run gen` to generate components
3. Test with `npm run dev`
4. Build with `npm run build`

## License

[Your License Here] 