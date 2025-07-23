# Smart Home Remote UI v2

A modern, responsive web application for controlling smart home devices and scenarios. Built with React 18, TypeScript, and Tailwind CSS.

## Features

- **Device Control**: Intuitive interfaces for smart home devices
- **Scenario Management**: Execute complex automation sequences
- **Real-time Updates**: Live device state monitoring and system logs
- **Responsive Design**: Works on desktop, tablet, and mobile devices
- **Build-time Generation**: Pages generated from Python model imports
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
- **Type Generation**: Python package imports via wb-mqtt-bridge

## Quick Start

### Prerequisites

- Node.js 18+ 
- Python 3.9+
- npm or pnpm
- wb-mqtt-bridge package (backend)

### Installation

```bash
# Clone the repositories
git clone <frontend-repository-url>
cd wb-mqtt-ui

# Clone the backend (for local development)
git clone https://github.com/droman42/wb-mqtt-bridge.git

# Install backend package in development mode
cd wb-mqtt-bridge
pip install -e .

# Test backend installation
python -c "from wb_mqtt_bridge.domain.devices.models import WirenboardIRState; print('✅ Backend package installed successfully')"

# Return to frontend and install dependencies
cd ../wb-mqtt-ui
npm install

# Generate pages from Python models
npm run gen:device-pages

# Start development server
npm run dev
```

The application will be available at `http://localhost:3000`.

### Alternative Setup (Package-only)

If wb-mqtt-bridge is installed as a system package:

```bash
# Install wb-mqtt-bridge from package manager or pip
pip install wb-mqtt-bridge

# Clone frontend only
git clone <frontend-repository-url>
cd wb-mqtt-ui

# Install dependencies
npm install

# Generate pages using package imports
npm run gen:device-pages --mode=package

# Start development server
npm run dev
```

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
├── scripts/            # Build-time generators
├── stores/             # Zustand state slices
├── hooks/              # Custom React hooks
├── config/             # Runtime configuration
└── types/              # TypeScript definitions
```

## Development Workflow

### Type Generation

The application generates TypeScript interfaces from Python model classes using two methods:

#### 1. Package-based (Recommended)
Uses installed wb-mqtt-bridge package:

```bash
# Generate types from package imports
npm run gen:device-pages --mode=package

# Configuration uses stateClassImport field:
{
  "WirenboardIRDevice": {
    "stateClassImport": "wb_mqtt_bridge.domain.devices.models:WirenboardIRState",
    "deviceConfigs": ["config/devices/ld_player.json"]
  }
}
```

#### 2. Local Development (Fallback)
Uses local file paths for development:

```bash
# Generate types from local files
npm run gen:device-pages --mode=local

# Configuration uses legacy stateFile/stateClass fields:
{
  "WirenboardIRDevice": {
    "stateFile": "app/schemas.py",
    "stateClass": "WirenboardIRState"
  }
}
```

### Configuration Files

Device configurations are defined in `config/device-state-mapping.json`:

```json
{
  "WirenboardIRDevice": {
    "stateClassImport": "wb_mqtt_bridge.domain.devices.models:WirenboardIRState",
    "deviceConfigs": ["config/devices/ld_player.json"],
    "description": "IR-controlled devices via Wirenboard"
  },
  "ScenarioDevice": {
    "stateClassImport": "wb_mqtt_bridge.infrastructure.scenarios.models:ScenarioWBConfig",
    "scenarioConfigs": ["config/scenarios/*.json"],
    "description": "Virtual WB device configurations for scenarios"
  }
}
```

### Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run gen:device-pages` - Generate pages from Python models
- `npm run preview` - Preview production build
- `npm run test` - Run tests
- `npm run lint` - Lint code
- `npm run typecheck` - Type check frontend only
- `npm run typecheck:all` - Type check all TypeScript files
- `npm run validate:all` - Validate generated code and components
- `npm run gen:favicon` - Generate favicon assets

### Troubleshooting

#### Python Import Errors

**Error**: `ModuleNotFoundError: No module named 'wb_mqtt_bridge'`

**Solution**:
```bash
# Install the backend package
pip install -e ../wb-mqtt-bridge

# Or install from package manager
pip install wb-mqtt-bridge

# Verify installation
python -c "import wb_mqtt_bridge; print(wb_mqtt_bridge.__version__)"
```

#### Type Generation Failures

**Error**: Type generation fails with import errors

**Solutions**:
1. **Check Python environment**:
```bash
# Verify Python path and installed packages
python -c "import sys; print(sys.path)"
pip list | grep wb-mqtt-bridge
```

2. **Use fallback mode**:
```bash
# Generate using local files as fallback
npm run gen:device-pages --mode=local
```

3. **Check configuration format**:
```bash
# Validate configuration syntax
npm run validate:all
```

#### Missing Device Configurations

**Error**: Device configs not found

**Solution**:
```bash
# Check if wb-mqtt-bridge is properly cloned/installed
ls -la wb-mqtt-bridge/config/devices/

# Verify configuration file paths
cat config/device-state-mapping.json
```

#### Docker Build Issues

**Error**: Docker build fails during type generation

**Solution**:
```bash
# Build locally first to test
npm install
npm run gen:device-pages --mode=package
npm run build

# Check Docker build logs
docker build --no-cache -t wb-mqtt-ui:test .
```

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
- ✅ **Package-based imports** - uses wb-mqtt-bridge Python package
- ✅ **GitHub artifacts** - no container registry needed
- ✅ **Two-stage builds** - ~30MB final image (nginx:alpine)
- ✅ **Port 3000** - avoids system nginx conflicts
- ✅ **Automated device page generation** during build
- ✅ **TypeScript validation** - ensures type safety

See [docs/deployment.md](docs/deployment.md) for complete deployment guide.

### Manual Docker Build

For local development and testing:

```bash
# Ensure wb-mqtt-bridge is available
git clone https://github.com/droman42/wb-mqtt-bridge.git

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

1. Install wb-mqtt-bridge package: `pip install -e ../wb-mqtt-bridge`
2. Generate device pages: `npm run gen:device-pages`
3. Test with `npm run dev`
4. Validate: `npm run validate:all`
5. Build: `npm run build`

## License

[Your License Here] 