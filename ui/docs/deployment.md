# Phase 2 Deployment Guide

## Overview

This guide covers the automated Docker build and deployment process for wb-mqtt-ui on ARM v7 devices (Wirenboard 7).

## Architecture

- **Two-stage Docker build**: Node.js build stage → nginx production stage
- **GitHub Actions**: Automated ARM builds triggered on push
- **Artifacts**: Compressed Docker images stored as GitHub artifacts
- **Port 3000**: Avoids conflicts with system nginx on port 80

## GitHub Actions Workflow

The workflow (`.github/workflows/build-arm.yml`) automatically:

1. **Checks out repositories**: Frontend repo + wb-mqtt-bridge config repo
2. **Sets up Docker Buildx**: For cross-platform ARM builds
3. **Builds ARM image**: Two-stage build with device page generation
4. **Publishes artifacts**: Compressed Docker image for download

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

The build uses `config/device-state-mapping.json` with relative paths:

```json
{
  "WirenboardIRDevice": {
    "stateFile": "wb-mqtt-bridge/app/schemas.py",
    "stateClass": "WirenboardIRState",
    "deviceConfigs": [
      "wb-mqtt-bridge/config/devices/ld_player.json",
      "wb-mqtt-bridge/config/devices/mf_amplifier.json"
    ]
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

**Config repo not found:**
```bash
# Verify repository is public and accessible
curl -s https://api.github.com/repos/YOUR_USERNAME/wb-mqtt-bridge
```

**Device generation fails:**
```bash
# Check GitHub Actions logs for detailed errors
gh run list --repo YOUR_USERNAME/wb-mqtt-ui
gh run view RUN_ID --log
```

### Deployment Issues

**Container won't start:**
```bash
# Check Docker logs for startup errors
docker logs wb-ui

# Verify image loaded correctly
docker images | grep wb-mqtt-ui
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

## Manual Build (Development)

For local testing of the Docker build:

```bash
# Clone config repo locally
git clone https://github.com/YOUR_USERNAME/wb-mqtt-bridge.git

# Build Docker image
docker build -t wb-mqtt-ui:local .

# Run locally
docker run -d --name wb-ui-local -p 3000:3000 wb-mqtt-ui:local
```

## Update Process

### Automated Updates
1. Push changes to `main` branch
2. GitHub Actions builds new ARM image
3. Download and deploy new artifact

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

## Security Considerations

- **Public repositories**: Config repo must be public for GitHub Actions
- **No secrets in configs**: Device configurations should not contain sensitive data
- **Container isolation**: UI container runs with minimal privileges
- **Network security**: Only port 3000 exposed, API proxy for backend communication 