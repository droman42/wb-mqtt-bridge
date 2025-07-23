# Phase 2 Deployment Guide

## Overview

This guide covers the automated Docker build and deployment process for wb-mqtt-ui on ARM v7 devices (Wirenboard 7) using the new package-based wb-mqtt-bridge integration.

## Architecture

- **Two-stage Docker build**: Node.js + Python build stage → nginx production stage
- **Package-based imports**: Uses installed wb-mqtt-bridge Python package
- **GitHub Actions**: Automated ARM builds with Python package installation
- **Artifacts**: Compressed Docker images stored as GitHub artifacts
- **Port 3000**: Avoids conflicts with system nginx on port 80
- **TypeScript validation**: Ensures type safety during build

## GitHub Actions Workflow

The workflow (`.github/workflows/build-arm.yml`) automatically:

1. **Checks out repositories**: Frontend repo + wb-mqtt-bridge config repo
2. **Sets up Python environment**: Installs Python 3.11 with package caching
3. **Installs wb-mqtt-bridge package**: In development mode for type generation
4. **Validates imports**: Tests package installation and model imports
5. **Sets up Node.js**: With npm dependency caching
6. **Generates TypeScript types**: From Python models using package imports
7. **Validates TypeScript**: Ensures type safety before Docker build
8. **Builds ARM image**: Two-stage build with package-based type generation
9. **Publishes artifacts**: Compressed Docker image for download

### Triggered on:
- Push to `main` or `develop` branches
- Pull requests to `main` branch

## Configuration Requirements

### Update GitHub Actions Workflow

Before using, update the repository reference in `.github/workflows/build-arm.yml`:

```yaml
- name: Checkout config repo (public)
  uses: actions/checkout@v4
  with:
    repository: YOUR_USERNAME/wb-mqtt-bridge  # ← Update this
    path: wb-mqtt-bridge
    ref: main
```

### Device Configuration Mapping

The build uses `config/device-state-mapping.json` with package-based imports:

```json
{
  "WirenboardIRDevice": {
    "stateClassImport": "wb_mqtt_bridge.domain.devices.models:WirenboardIRState",
    "deviceConfigs": [
      "wb-mqtt-bridge/config/devices/ld_player.json",
      "wb-mqtt-bridge/config/devices/mf_amplifier.json"
    ],
    "description": "IR-controlled devices via Wirenboard"
  },
  "ScenarioDevice": {
    "stateClassImport": "wb_mqtt_bridge.infrastructure.scenarios.models:ScenarioWBConfig",
    "scenarioConfigs": ["wb-mqtt-bridge/config/scenarios/*.json"],
    "description": "Virtual WB device configurations for scenarios"
  }
}
```

### Legacy Fallback Support

During transition, both import methods are supported:

```json
{
  "WirenboardIRDevice": {
    "stateClassImport": "wb_mqtt_bridge.domain.devices.models:WirenboardIRState",
    "deviceConfigs": ["wb-mqtt-bridge/config/devices/ld_player.json"],
    
    // Legacy fallback (will be removed in future versions)
    "stateFile": "wb-mqtt-bridge/app/schemas.py",
    "stateClass": "WirenboardIRState"
  }
}
```

## Deployment Process

### 1. Download GitHub Artifact

```bash
# Install GitHub CLI if not available
# wget https://github.com/cli/cli/releases/latest/download/gh_*_linux_armv7.tar.gz

# Authenticate (one-time setup)
gh auth login

# Download latest build artifact
gh run download --repo YOUR_USERNAME/wb-mqtt-ui --name wb-mqtt-ui-image
```

### 2. Load Docker Image

```bash
# Extract compressed image
gunzip wb-mqtt-ui.tar.gz

# Load into Docker
docker load < wb-mqtt-ui.tar
```

### 3. Deploy Container

```bash
# Stop existing container (if any)
docker stop wb-ui || true
docker rm wb-ui || true

# Run new container
docker run -d \
  --name wb-ui \
  --restart unless-stopped \
  -p 3000:3000 \
  wb-mqtt-ui:latest
```

### 4. Verify Deployment

```bash
# Check container status
docker ps | grep wb-ui

# Check container logs
docker logs wb-ui

# Test HTTP response
curl http://localhost:3000/

# Access UI in browser
# http://YOUR_WIRENBOARD_IP:3000
```

## Container Features

### Health Checks
Built-in health monitoring:
```bash
# Check health status
docker inspect wb-ui | grep -A5 Health
```

### Resource Optimization
- **~30MB final image size** (nginx:alpine base)
- **No Node.js runtime** in production
- **Static file serving** with aggressive caching
- **SPA routing support** for React Router

### Network Configuration
- **Port 3000**: Avoids system nginx conflicts
- **API proxy**: Routes `/api/*` to backend on port 8000
- **Static asset caching**: 1-year cache headers for assets

## Troubleshooting

### Build Issues

**Python package import errors:**
```bash
# Check GitHub Actions logs for package installation
gh run list --repo YOUR_USERNAME/wb-mqtt-ui
gh run view RUN_ID --log

# Look for "Install wb-mqtt-bridge package" step
# Should show: "✅ Device models import successful"
```

**Type generation failures:**
```bash
# Check the "Validate type generation" step in GitHub Actions
# Should show: "✅ Type generation successful"

# For local debugging:
git clone https://github.com/YOUR_USERNAME/wb-mqtt-bridge.git
cd wb-mqtt-bridge
pip install -e .
cd ../wb-mqtt-ui
npm run gen:device-pages --mode=package
```

**Config repo not found:**
```bash
# Verify repository is public and accessible
curl -s https://api.github.com/repos/YOUR_USERNAME/wb-mqtt-bridge
```

**TypeScript validation errors:**
```bash
# Check "Run TypeScript validation" step
# Should show: "✅ TypeScript validation successful"

# For local debugging:
npm run typecheck:all
```

### Deployment Issues

**Container won't start:**
```bash
# Check Docker logs for startup errors
docker logs wb-ui

# Verify image loaded correctly
docker images | grep wb-mqtt-ui

# Check if image was built with package support
docker run --rm wb-mqtt-ui:latest cat /usr/share/nginx/html/index.html | grep -i "generated"
```

**Port already in use:**
```bash
# Check what's using port 3000
sudo netstat -tlnp | grep :3000

# Use different port if needed
docker run -d --name wb-ui -p 3001:3000 wb-mqtt-ui:latest
```

**UI not accessible:**
```bash
# Check container is running
docker ps | grep wb-ui

# Verify port binding
docker port wb-ui

# Test local connectivity
curl http://localhost:3000/
```

### Package-Related Issues

**Missing Python models:**
```bash
# Test package installation locally
python -c "from wb_mqtt_bridge.domain.devices.models import WirenboardIRState; print('✅ OK')"
python -c "from wb_mqtt_bridge.infrastructure.scenarios.models import ScenarioWBConfig; print('✅ OK')"
```

**Type generation with old config format:**
```bash
# Update config to use stateClassImport instead of stateFile/stateClass
# See "Device Configuration Mapping" section above
```

## Manual Build (Development)

For local testing of the Docker build with package support:

```bash
# Clone config repo locally
git clone https://github.com/YOUR_USERNAME/wb-mqtt-bridge.git

# Install package locally (for validation)
cd wb-mqtt-bridge
pip install -e .

# Test imports
python -c "from wb_mqtt_bridge.domain.devices.models import WirenboardIRState; print('✅ Package ready')"

# Return to frontend and build Docker image
cd ../wb-mqtt-ui
docker build -t wb-mqtt-ui:local .

# Run locally
docker run -d --name wb-ui-local -p 3000:3000 wb-mqtt-ui:local
```

## Update Process

### Automated Updates
1. Push changes to `main` branch
2. GitHub Actions installs wb-mqtt-bridge package
3. GitHub Actions generates types using package imports
4. GitHub Actions validates TypeScript compilation
5. GitHub Actions builds new ARM image
6. Download and deploy new artifact

### Manual Updates
```bash
# Download latest artifact
gh run download --repo YOUR_USERNAME/wb-mqtt-ui --name wb-mqtt-ui-image

# Deploy new version
gunzip wb-mqtt-ui.tar.gz
docker load < wb-mqtt-ui.tar
docker stop wb-ui && docker rm wb-ui
docker run -d --name wb-ui --restart unless-stopped -p 3000:3000 wb-mqtt-ui:latest
```

## Migration from File-Based to Package-Based

If migrating from an older version:

### 1. Update Configuration Format
```bash
# Replace stateFile/stateClass with stateClassImport
# Old format:
{
  "WirenboardIRDevice": {
    "stateFile": "wb-mqtt-bridge/app/schemas.py",
    "stateClass": "WirenboardIRState"
  }
}

# New format:
{
  "WirenboardIRDevice": {
    "stateClassImport": "wb_mqtt_bridge.domain.devices.models:WirenboardIRState"
  }
}
```

### 2. Test Locally
```bash
# Install package
pip install -e ../wb-mqtt-bridge

# Generate with new format
npm run gen:device-pages --mode=package

# Validate
npm run typecheck:all
```

### 3. Update GitHub Actions
Use the updated workflow from this guide that includes Python setup and package installation.

## Security Considerations

- **Public repositories**: Config repo must be public for GitHub Actions
- **No secrets in configs**: Device configurations should not contain sensitive data
- **Container isolation**: UI container runs with minimal privileges
- **Network security**: Only port 3000 exposed, API proxy for backend communication
- **Package integrity**: wb-mqtt-bridge package verified during build process 