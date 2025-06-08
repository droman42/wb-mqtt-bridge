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
- **Icons**: Heroicons 24 + Lucide React
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

### Build and Deploy to Wirenboard

```bash
# Set environment variables
export WIRENBOARD_HOST=192.168.1.100
export WIRENBOARD_USER=root

# Build and deploy
./docker/build_and_push.sh
```

### Manual Docker Build

```bash
# Build image
docker build -f docker/Dockerfile -t smart-home-ui-v2 .

# Run container
docker run -d -p 3000:80 smart-home-ui-v2
```

## Configuration

Runtime configuration is managed in `src/config/runtime.ts`:

```typescript
export const runtimeConfig = {
  statePollIntervalSec: 5,
  apiBaseUrl: '/api',
  mqttUrl: 'ws://localhost:9001',
  defaultLanguage: 'en',
  maxLogEntries: 1000,
  debounceDelaySec: 0.3,
};
```

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