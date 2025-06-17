# Device Page Generation - Local Configuration Mode

## Overview

This document outlines a two-phase approach to enable device page generation without REST API dependencies and automated ARM deployment. Both phases must produce **identical results** to the current API-based generation.

# Phase 1: Local Configuration Mode

## Overview

Phase 1 enables device page generation without REST API dependencies by using local device configuration files.

## Problem Statement

Currently, the device page generator (`generate-device-pages.ts`) requires a running backend API to fetch:
1. Device configuration via `/config/device/{deviceId}`
2. Device groups via `/devices/{deviceId}/groups`

This creates barriers for:
- Offline development
- CI/CD pipelines without backend dependencies
- Testing and iteration during development
- Reproducible builds

## Solution: Local Configuration Mode

### Key Discovery

Analysis of actual device configuration files reveals that **groups are embedded within device commands**, making the groups API call redundant:

```json
{
  "commands": {
    "power_on": {
      "action": "power_on",
      "topic": "/devices/children_room_tv/controls/power_on",
      "description": "Power On",
      "group": "power"  // ← Group information embedded here
    }
  }
}
```

This means:
- Only device configuration is needed (single data source)
- Groups can be derived programmatically from commands
- API call reduction: 2 calls → 1 call (or 0 in local mode)

### Approach: Dual Configuration Files Strategy

The solution uses **two mapping files** to support different environments:

1. **Main file** (`config/device-state-mapping.json`): Uses relative paths for CI/Docker builds
2. **Local file** (`config/device-state-mapping.local.json`): Uses absolute paths for local development

#### Main Configuration File (CI/Docker Builds)

```json
{
  "WirenboardIRDevice": {
    "stateFile": "wb-mqtt-bridge/app/schemas.py",
    "stateClass": "WirenboardIRState",
    "deviceConfigs": [
      "wb-mqtt-bridge/config/devices/ld_player.json",
      "wb-mqtt-bridge/config/devices/mf_amplifier.json",
      "wb-mqtt-bridge/config/devices/vhs_player.json",
      "wb-mqtt-bridge/config/devices/upscaler.json",
      "wb-mqtt-bridge/config/devices/video.json"
    ]
  }
}
```

#### Local Development Configuration File

```json
{
  "WirenboardIRDevice": {
    "stateFile": "/home/droman42/development/wb-mqtt-bridge/app/schemas.py",
    "stateClass": "WirenboardIRState",
    "deviceConfigs": [
      "/home/droman42/development/wb-mqtt-bridge/config/devices/ld_player.json",
      "/home/droman42/development/wb-mqtt-bridge/config/devices/mf_amplifier.json",
      "/home/droman42/development/wb-mqtt-bridge/config/devices/vhs_player.json",
      "/home/droman42/development/wb-mqtt-bridge/config/devices/upscaler.json",
      "/home/droman42/development/wb-mqtt-bridge/config/devices/video.json"
    ]
  },
  "LgTv": {
    "stateFile": "/home/development/wb-mqtt-bridge/app/schemas.py",
    "stateClass": "LgTvState",
    "deviceConfigs": [
      "/home/droman42/development/wb-mqtt-bridge/config/devices/lg_tv_children.json",
      "/home/droman42/development/wb-mqtt-bridge/config/devices/lg_tv_living.json"
    ]
  },
  "EMotivaXMC2": {
    "stateFile": "/home/development/wb-mqtt-bridge/app/schemas.py",
    "stateClass": "EmotivaXMC2State",
    "deviceConfigs": [
      "/home/droman42/development/wb-mqtt-bridge/config/devices/emotiva_xmc2.json"
    ]
  },
  "BroadlinkKitchenHood": {
    "stateFile": "/home/development/wb-mqtt-bridge/app/schemas.py",
    "stateClass": "KitchenHoodState",
    "deviceConfigs": [
      "/home/droman42/development/wb-mqtt-bridge/config/devices/kitchen_hood.json"
    ]
  },
  "AppleTVDevice": {
    "stateFile": "/home/development/wb-mqtt-bridge/app/schemas.py",
    "stateClass": "AppleTVState",
    "deviceConfigs": [
      "/home/droman42/development/wb-mqtt-bridge/config/devices/appletv_children.json",
      "/home/droman42/development/wb-mqtt-bridge/config/devices/appletv_living.json"
    ]
  },
  "AuralicDevice": {
    "stateFile": "/home/development/wb-mqtt-bridge/app/schemas.py",
    "stateClass": "AuralicDeviceState",
    "deviceConfigs": [
      "/home/droman42/development/wb-mqtt-bridge/config/devices/streamer.json"
    ]
  },
  "RevoxA77ReelToReel": {
    "stateFile": "/home/development/wb-mqtt-bridge/app/schemas.py",
    "stateClass": "RevoxA77ReelToReelState",
    "deviceConfigs": [
      "/home/droman42/development/wb-mqtt-bridge/config/devices/reel_to_reel.json"
    ]
  }
}
```

## Implementation Strategy

### 1. Group Derivation Algorithm

Create function to derive `DeviceGroups` from `DeviceConfig`:

```typescript
function deriveGroupsFromConfig(config: DeviceConfig): DeviceGroups {
  const groupMap = new Map<string, GroupAction[]>();
  
  // Extract groups from commands
  Object.values(config.commands).forEach(command => {
    if (command.group) {
      if (!groupMap.has(command.group)) {
        groupMap.set(command.group, []);
      }
      groupMap.get(command.group)!.push({
        name: command.action,
        description: command.description,
        params: command.params
      });
    }
  });
  
  // Build DeviceGroups structure
  return {
    device_id: config.device_id,
    groups: Array.from(groupMap.entries()).map(([groupId, actions]) => ({
      group_id: groupId,
      group_name: groupId.charAt(0).toUpperCase() + groupId.slice(1),
      actions: actions,
      status: 'active'
    }))
  };
}
```

### 2. Local Device Configuration Client

Create `LocalDeviceConfigurationClient` class:

```typescript
export class LocalDeviceConfigurationClient {
  constructor(private mappingFile: string) {}
  
  async fetchDeviceConfig(deviceId: string): Promise<DeviceConfig> {
    const mapping = await this.loadMapping();
    const configPath = this.findConfigPathByDeviceId(mapping, deviceId);
    const data = await fs.readFile(configPath, 'utf8');
    return JSON.parse(data);
  }
  
  async fetchDeviceGroups(deviceId: string): Promise<DeviceGroups> {
    const config = await this.fetchDeviceConfig(deviceId);
    return deriveGroupsFromConfig(config);
  }
  
  async validateConnectivity(): Promise<boolean> {
    return true; // Always available in local mode
  }
  
  private async loadMapping(): Promise<DeviceStateMapping> {
    const data = await fs.readFile(this.mappingFile, 'utf8');
    return JSON.parse(data);
  }
  
  private findConfigPathByDeviceId(mapping: DeviceStateMapping, deviceId: string): string {
    // Search all deviceConfigs arrays for matching device_id
    for (const [deviceClass, classInfo] of Object.entries(mapping)) {
      for (const configPath of classInfo.deviceConfigs) {
        const configData = JSON.parse(fs.readFileSync(configPath, 'utf8'));
        if (configData.device_id === deviceId) {
          return configPath;
        }
      }
    }
    throw new Error(`Device config not found for device_id: ${deviceId}`);
  }
}
```

### 3. DevicePageGenerator Modifications

Add mode parameter to constructor:

```typescript
export class DevicePageGenerator {
  constructor(
    apiBaseUrl: string, 
    outputDir: string,
    options?: { 
      mode?: 'api' | 'local'; 
      mappingFile?: string;
    }
  ) {
    this.apiBaseUrl = apiBaseUrl;
    this.outputDir = outputDir;
    
    if (options?.mode === 'local') {
      this.client = new LocalDeviceConfigurationClient(
        options.mappingFile || 'config/device-state-mapping.json'
      );
    } else {
      this.client = new DeviceConfigurationClient(apiBaseUrl);
    }
    
    // ... rest of constructor unchanged
  }
}
```

### 4. CLI Enhancements

Add local mode flags:

```bash
# Local development (uses absolute paths)
npm run gen:device-pages -- --device-id=children_room_tv --mode=local --mapping-file=config/device-state-mapping.local.json

# Generate for all devices of a class using local configs
npm run gen:device-pages -- --device-class=LgTv --mode=local --mapping-file=config/device-state-mapping.local.json

# Generate for all devices in local mapping file
npm run gen:device-pages -- --batch --mode=local --mapping-file=config/device-state-mapping.local.json

# CI/Docker builds (uses relative paths)
npm run gen:device-pages -- --batch --mode=local --mapping-file=config/device-state-mapping.json

# Generate using specific config file (for testing)
npm run gen:device-pages -- --config-file=/path/to/config.json --mode=local

# API mode (fallback)
npm run gen:device-pages -- --device-id=children_room_tv --mode=api
```

## Ensuring Identical Results

### Validation Strategy

1. **Data Structure Validation**: Ensure `deriveGroupsFromConfig()` produces identical `DeviceGroups` structure to API response

2. **Side-by-Side Testing**: 
   ```bash
   # Generate using API
   npm run gen:device-pages -- --device-id=children_room_tv --output-dir=api_output
   
   # Generate using local config
   npm run gen:device-pages -- --device-id=children_room_tv --mode=local --output-dir=local_output
   
   # Compare outputs
   diff -r api_output/ local_output/
   ```

3. **Automated Testing**: Create test suite that verifies identical output for all device classes

4. **Group Derivation Verification**: Test that derived groups match API-returned groups exactly

### Critical Equivalence Points

- **Device structure**: Identical `RemoteDeviceStructure` generation
- **Group processing**: Same group detection and zone mapping  
- **Component generation**: Identical React component output
- **State interfaces**: Same TypeScript state generation
- **File naming**: Consistent output file names and paths

## Benefits

### Development Benefits
- **Offline Development**: No backend dependency
- **Faster Iteration**: No network latency
- **Reproducible Builds**: Same input always produces same output
- **Version Control**: Device configs can be committed and tracked

### Production Benefits
- **CI/CD Integration**: Generate pages in pipelines without backend
- **Testing**: Easy to create test scenarios with modified configs
- **Backup Strategy**: Local configs serve as API backup
- **Performance**: Eliminates API redundancy (2 calls → 1 call)

## Migration Strategy

### Step 1: Add Local Mode (Backwards Compatible)
1. Implement `LocalDeviceConfigurationClient`
2. Add `--mode=local` CLI flag
3. Extend `device-state-mapping.json` with `deviceConfigs`
4. Maintain existing API mode as default

### Step 2: Optimize API Mode
1. Remove redundant `fetchDeviceGroups()` API call
2. Use `deriveGroupsFromConfig()` in API mode too
3. Update API client to only fetch device config

### Step 3: Default to Local Mode
1. Change default mode to `local`
2. Require explicit `--mode=api` for API usage
3. Add warning when API mode is used

## File Structure

```
config/
├── device-state-mapping.json (relative paths for CI/Docker)
├── device-state-mapping.local.json (absolute paths for local dev)
└── (references external configs in wb-mqtt-bridge)

/home/droman42/development/wb-mqtt-bridge/config/devices/
├── lg_tv_children.json
├── lg_tv_living.json  
├── emotiva_xmc2.json
├── kitchen_hood.json
├── appletv_children.json
├── appletv_living.json
├── streamer.json
├── reel_to_reel.json
├── ld_player.json
├── mf_amplifier.json
├── vhs_player.json
├── upscaler.json
└── video.json
```

## Path Strategy Explanation

### Why Two Files?

**Local Development (`*.local.json`)**:
- Uses absolute paths pointing to your local wb-mqtt-bridge repository
- Allows immediate development without complex setup
- Works with existing directory structure
- Example: `/home/droman42/development/wb-mqtt-bridge/config/devices/lg_tv.json`

**CI/Docker Builds (`*.json`)**:
- Uses relative paths that work in build containers
- Config repo is checked out to `wb-mqtt-bridge/` in build context
- Portable across different build environments
- Example: `wb-mqtt-bridge/config/devices/lg_tv.json`

### Default Behavior

- **Local development**: Use `--mapping-file=config/device-state-mapping.local.json`
- **CI/Docker builds**: Use `--mapping-file=config/device-state-mapping.json`
- **API fallback**: Use `--mode=api` when config files are unavailable

## Phase 1 Implementation Checklist

- [ ] Create `LocalDeviceConfigurationClient` class
- [ ] Implement `deriveGroupsFromConfig()` function
- [ ] Add mode parameter to `DevicePageGenerator` constructor
- [ ] Update `device-state-mapping.json` with `deviceConfigs` arrays
- [ ] Add CLI flags: `--mode`, `--mapping-file`, `--config-file`
- [ ] Create validation tests for identical output
- [ ] Update batch processing to handle local mode
- [ ] Add error handling for missing config files
- [ ] Document CLI usage examples
- [ ] Create migration guide for existing workflows

---

# Phase 2: Docker Build for ARM Deployment

## Overview

This phase extends the local configuration mode to support **automated Docker builds** for ARM v7 deployment on Wirenboard 7. The approach creates lightweight, static-only containers using GitHub Actions workflows with cross-repository dependencies.

## Requirements

- **Target Platform**: ARM v7 (Wirenboard 7)  
- **Container Type**: Two-stage Docker build (static files only, no Node.js runtime)
- **Port**: 3000 (avoiding conflict with system nginx on port 80)
- **Dependencies**: Public GitHub repositories for configuration data
- **Build Environment**: GitHub Actions workflows only (no local Docker builds required)
- **Deployment**: GitHub artifacts (no container registry needed)

## Architecture

### Multi-Repository Structure

```
GitHub Organization:
├── wb-mqtt-ui (frontend repo)
│   ├── src/
│   ├── config/device-state-mapping.json  
│   ├── Dockerfile
│   └── .github/workflows/build-arm.yml
└── wb-mqtt-bridge (config repo)
    ├── app/schemas.py
    └── config/devices/
        ├── lg_tv_children.json
        ├── emotiva_xmc2.json
        └── ...
```

### Docker Build Strategy

1. **GitHub Actions**: Checkout both repositories
2. **Build Context**: Copy config repo into frontend build context  
3. **Two-Stage Build**: 
   - Stage 1: Node.js build environment with device page generation
   - Stage 2: nginx:alpine serving static files on port 3000
4. **Cross-Platform**: Build ARM v7 images using Docker Buildx
5. **Artifact Publishing**: Save Docker image as compressed GitHub artifact

## Implementation

### 1. Enhanced device-state-mapping.json (Relative Paths)

```json
{
  "WirenboardIRDevice": {
    "stateFile": "wb-mqtt-bridge/app/schemas.py",
    "stateClass": "WirenboardIRState",
    "deviceConfigs": [
      "wb-mqtt-bridge/config/devices/ld_player.json",
      "wb-mqtt-bridge/config/devices/mf_amplifier.json",
      "wb-mqtt-bridge/config/devices/vhs_player.json",
      "wb-mqtt-bridge/config/devices/upscaler.json",
      "wb-mqtt-bridge/config/devices/video.json"
    ]
  },
  "LgTv": {
    "stateFile": "wb-mqtt-bridge/app/schemas.py", 
    "stateClass": "LgTvState",
    "deviceConfigs": [
      "wb-mqtt-bridge/config/devices/lg_tv_children.json",
      "wb-mqtt-bridge/config/devices/lg_tv_living.json"
    ]
  },
  "EMotivaXMC2": {
    "stateFile": "wb-mqtt-bridge/app/schemas.py",
    "stateClass": "EmotivaXMC2State", 
    "deviceConfigs": [
      "wb-mqtt-bridge/config/devices/emotiva_xmc2.json"
    ]
  },
  "BroadlinkKitchenHood": {
    "stateFile": "wb-mqtt-bridge/app/schemas.py",
    "stateClass": "KitchenHoodState",
    "deviceConfigs": [
      "wb-mqtt-bridge/config/devices/kitchen_hood.json"
    ]
  },
  "AppleTVDevice": {
    "stateFile": "wb-mqtt-bridge/app/schemas.py",
    "stateClass": "AppleTVState",
    "deviceConfigs": [
      "wb-mqtt-bridge/config/devices/appletv_children.json", 
      "wb-mqtt-bridge/config/devices/appletv_living.json"
    ]
  },
  "AuralicDevice": {
    "stateFile": "wb-mqtt-bridge/app/schemas.py",
    "stateClass": "AuralicDeviceState",
    "deviceConfigs": [
      "wb-mqtt-bridge/config/devices/streamer.json"
    ]
  },
  "RevoxA77ReelToReel": {
    "stateFile": "wb-mqtt-bridge/app/schemas.py",
    "stateClass": "RevoxA77ReelToReelState",
    "deviceConfigs": [
      "wb-mqtt-bridge/config/devices/reel_to_reel.json"
    ]
  }
}
```

### 2. GitHub Actions Workflow (Updated for Artifacts)

**.github/workflows/build-arm.yml:**
```yaml
name: Build ARM Docker Image

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  build:
    runs-on: ubuntu-latest

    steps:
    - name: Checkout frontend repo
      uses: actions/checkout@v4

    - name: Checkout config repo (public)
      uses: actions/checkout@v4
      with:
        repository: user/wb-mqtt-bridge  # Replace with actual public repo
        path: wb-mqtt-bridge
        ref: main

    - name: Verify directory structure
      run: |
        echo "Build context structure:"
        ls -la
        echo "Config files found:"
        ls -la wb-mqtt-bridge/config/devices/
        echo "Python schemas:"
        ls -la wb-mqtt-bridge/app/
        echo "Total config files: $(ls wb-mqtt-bridge/config/devices/*.json | wc -l)"

    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v3

    - name: Build ARM Docker image
      uses: docker/build-push-action@v5
      with:
        context: .
        platforms: linux/arm/v7
        tags: wb-mqtt-ui:latest
        outputs: type=docker,dest=/tmp/wb-mqtt-ui.tar

    - name: Compress Docker image
      run: |
        gzip /tmp/wb-mqtt-ui.tar

    - name: Upload Docker image artifact
      uses: actions/upload-artifact@v3
      with:
        name: wb-mqtt-ui-image
        path: /tmp/wb-mqtt-ui.tar.gz
        retention-days: 30
```

### 3. Two-Stage Dockerfile

```dockerfile
# Stage 1: Build Stage (latest Node.js for best performance, regular image for compatibility)
FROM node:24 as builder

WORKDIR /app

# Copy package files first for better caching
COPY package*.json ./
RUN npm ci

# Copy config repo (now in build context)
COPY wb-mqtt-bridge/ ./wb-mqtt-bridge/

# Copy frontend source code
COPY . .

# Verify all paths are accessible
RUN echo "Verifying config structure:" && \
    ls -la wb-mqtt-bridge/config/devices/ && \
    ls -la wb-mqtt-bridge/app/ && \
    echo "Found $(ls wb-mqtt-bridge/config/devices/*.json | wc -l) device configs"

# Generate device pages using local mode with relative paths
RUN npm run gen:device-pages -- \
    --batch \
    --mode=local \
    --mapping-file=config/device-state-mapping.json

# Build static assets
RUN npm run build

# Stage 2: Production (nginx on port 3000)
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:3000/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
```

### 4. nginx Configuration

**nginx.conf:**
```nginx
events {
    worker_connections 1024;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;
    
    sendfile        on;
    keepalive_timeout  65;
    
    # Disable access log for lighter footprint
    access_log off;
    error_log /var/log/nginx/error.log warn;
    
    server {
        listen       3000;
        server_name  localhost;
        root         /usr/share/nginx/html;
        index        index.html;
        
        # Handle SPA routing (React Router)
        location / {
            try_files $uri $uri/ /index.html;
        }
        
        # Cache static assets
        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
        
        # API proxy (if needed for backend communication)
        location /api/ {
            proxy_pass http://localhost:8000/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        }
    }
}
```

## Deployment

### Wirenboard 7 Deployment

```bash
# Download and load ARM image from GitHub artifacts
# First, download the latest artifact
gh run download --repo user/wb-mqtt-ui --name wb-mqtt-ui-image

# Load the Docker image
gunzip wb-mqtt-ui.tar.gz
docker load < wb-mqtt-ui.tar

# Run on port 3000 (avoids conflict with system nginx on port 80)
docker run -d \
  --name wb-ui \
  --restart unless-stopped \
  -p 3000:3000 \
  wb-mqtt-ui:latest

# Access the UI at http://wirenboard-ip:3000
```

### Container Management

```bash
# View logs
docker logs wb-ui

# Update to latest
gh run download --repo user/wb-mqtt-ui --name wb-mqtt-ui-image
gunzip wb-mqtt-ui.tar.gz
docker load < wb-mqtt-ui.tar
docker stop wb-ui
docker rm wb-ui
docker run -d --name wb-ui --restart unless-stopped -p 3000:3000 wb-mqtt-ui:latest

# Health check
curl http://localhost:3000/
```

## Local Development Workflow

For local development, create a separate mapping file with local paths:

**config/device-state-mapping.local.json:**
```json
{
  "WirenboardIRDevice": {
    "stateFile": "../wb-mqtt-bridge/app/schemas.py",
    "stateClass": "WirenboardIRState",
    "deviceConfigs": [
      "../wb-mqtt-bridge/config/devices/ld_player.json",
      "../wb-mqtt-bridge/config/devices/mf_amplifier.json"
    ]
  }
}
```

**Local CLI usage:**
```bash
# Local development
npm run gen:device-pages -- --batch --mode=local --mapping-file=config/device-state-mapping.local.json

# Docker build uses the main mapping file automatically
```

## Benefits

### Development Benefits
- ✅ **No local Docker complexity**: Developers use `npm run dev` locally
- ✅ **GitHub Actions integration**: Automated ARM builds on push
- ✅ **Public repo simplicity**: No authentication tokens needed
- ✅ **Relative paths**: Portable configuration across environments

### Production Benefits
- ✅ **Lightweight containers**: ~30MB final image (no Node.js runtime)
- ✅ **ARM optimized**: Native ARM v7 builds for Wirenboard 7
- ✅ **Port flexibility**: Runs on port 3000, avoiding system conflicts
- ✅ **Static serving**: Fast nginx serving with SPA support
- ✅ **Automated updates**: GitHub artifacts trigger new container builds

### Operational Benefits
- ✅ **Self-contained**: No external dependencies at runtime
- ✅ **Health checks**: Built-in container health monitoring
- ✅ **Easy deployment**: Single `docker run` command
- ✅ **Version pinning**: Tag-based deployment for stability
- ✅ **Cache optimization**: Docker layer caching for faster builds

## Phase 2 Implementation Checklist

- [ ] Create GitHub Actions workflow for ARM builds
- [ ] Implement two-stage Dockerfile with nginx
- [ ] Configure nginx for port 3000 and SPA routing
- [ ] Update `device-state-mapping.json` with relative paths
- [ ] Test cross-repository checkout in GitHub Actions
- [ ] Verify ARM v7 container builds and runs correctly
- [ ] Create deployment documentation for Wirenboard 7
- [ ] Set up GitHub artifacts publishing (compressed Docker images)
- [ ] Add health checks and monitoring
- [ ] Test full end-to-end deployment workflow

---

# Phase 3: Integration with manage_docker.sh

## Overview

This phase integrates the wb-mqtt-ui container deployment with the existing `manage_docker.sh` script infrastructure. The script will be extended to support **GitHub artifacts workflow** for UI containers, maintaining consistency with the existing backend container management approach.

## Current manage_docker.sh Architecture

The existing script follows this pattern:
- Downloads GitHub artifacts (Docker image + config archives)
- Manages container lifecycle (start/stop/redeploy)
- Handles GitHub PAT authentication
- Supports multiple containers via parameters

## UI Container Integration Strategy

### 1. Artifact Type Detection

Extend the script to handle two types of GitHub artifacts:
- **Backend containers**: Image + config archives (existing behavior)
- **UI containers**: Image-only artifacts (new behavior)

### 2. Configuration Changes

**Add UI container configuration:**

```bash
# UI container configuration
declare -A UI_CONTAINERS=(
    ["wb-mqtt-ui"]="user/wb-mqtt-ui"
)

declare -A UI_PORTS=(
    ["wb-mqtt-ui"]="3000:3000"
)

declare -A UI_NETWORKS=(
    ["wb-mqtt-ui"]="wb-network"
)
```

### 3. Enhanced Artifact Detection

**Modified artifact detection logic:**

```bash
detect_artifact_type() {
    local repo="$1"
    local run_id="$2"
    
    # Get artifact list for the run
    local artifacts=$(gh api "repos/$repo/actions/runs/$run_id/artifacts" --jq '.artifacts[].name')
    
    # Check if it's a UI container (image-only)
    if echo "$artifacts" | grep -q ".*-image$" && ! echo "$artifacts" | grep -q ".*-configs$"; then
        echo "ui"
    # Check if it's a backend container (image + configs)
    elif echo "$artifacts" | grep -q ".*-image$" && echo "$artifacts" | grep -q ".*-configs$"; then
        echo "backend"
    else
        echo "unknown"
        return 1
    fi
}
```

### 4. UI Container Deployment Function

**New deployment function for UI containers:**

```bash
deploy_ui_container() {
    local container_name="$1"
    local repo="${UI_CONTAINERS[$container_name]}"
    local port="${UI_PORTS[$container_name]}"
    local network="${UI_NETWORKS[$container_name]:-wb-network}"
    
    echo "Deploying UI container: $container_name"
    
    # Find latest successful run
    local run_id=$(get_latest_successful_run "$repo")
    if [[ -z "$run_id" ]]; then
        echo "❌ No successful runs found for $repo"
        return 1
    fi
    
    # Verify it's a UI container
    local artifact_type=$(detect_artifact_type "$repo" "$run_id")
    if [[ "$artifact_type" != "ui" ]]; then
        echo "❌ Repository $repo does not produce UI container artifacts"
        return 1
    fi
    
    # Download Docker image artifact
    local image_artifact="${container_name}-image"
    echo "📦 Downloading $image_artifact..."
    
    if ! gh run download "$run_id" --repo "$repo" --name "$image_artifact" --dir "/tmp/docker-deploy/"; then
        echo "❌ Failed to download $image_artifact"
        return 1
    fi
    
    # Load Docker image
    echo "🔄 Loading Docker image..."
    if [[ -f "/tmp/docker-deploy/${container_name}.tar.gz" ]]; then
        gunzip "/tmp/docker-deploy/${container_name}.tar.gz"
        if ! docker load < "/tmp/docker-deploy/${container_name}.tar"; then
            echo "❌ Failed to load Docker image"
            return 1
        fi
    else
        echo "❌ Docker image file not found"
        return 1
    fi
    
    # Stop existing container
    stop_container "$container_name"
    
    # Start new container
    echo "🚀 Starting container: $container_name"
    docker run -d \
        --name "$container_name" \
        --restart unless-stopped \
        --network "$network" \
        -p "$port" \
        "$container_name:latest"
    
    # Verify container is running
    if docker ps | grep -q "$container_name"; then
        echo "✅ Container $container_name deployed successfully"
        echo "🌐 Access at: http://localhost:${port%:*}"
    else
        echo "❌ Container failed to start"
        return 1
    fi
    
    # Cleanup
    rm -rf "/tmp/docker-deploy/"
}
```

### 5. Updated Main Script Logic

**Enhanced main function:**

```bash
main() {
    local action="$1"
    local container_name="$2"
    
    # Validate container name
    if [[ -n "$container_name" ]]; then
        if [[ -n "${CONTAINERS[$container_name]}" ]]; then
            container_type="backend"
        elif [[ -n "${UI_CONTAINERS[$container_name]}" ]]; then
            container_type="ui"
        else
            echo "❌ Unknown container: $container_name"
            echo "Available backend containers: ${!CONTAINERS[*]}"
            echo "Available UI containers: ${!UI_CONTAINERS[*]}"
            exit 1
        fi
    fi
    
    case "$action" in
        "deploy")
            if [[ -z "$container_name" ]]; then
                echo "Usage: $0 deploy <container_name>"
                exit 1
            fi
            
            if [[ "$container_type" == "backend" ]]; then
                deploy_container "$container_name"
            elif [[ "$container_type" == "ui" ]]; then
                deploy_ui_container "$container_name"
            fi
            ;;
        "start"|"stop"|"restart"|"logs")
            # These operations work the same for both types
            container_operation "$action" "$container_name"
            ;;
        "status")
            show_status "$container_name"
            ;;
        *)
            show_usage
            ;;
    esac
}
```

### 6. Usage Examples

**Deploy UI container:**
```bash
# Deploy wb-mqtt-ui container
./manage_docker.sh deploy wb-mqtt-ui

# Container lifecycle operations (same as backend)
./manage_docker.sh start wb-mqtt-ui
./manage_docker.sh stop wb-mqtt-ui
./manage_docker.sh restart wb-mqtt-ui
./manage_docker.sh logs wb-mqtt-ui
./manage_docker.sh status wb-mqtt-ui
```

**Mixed environment deployment:**
```bash
# Deploy backend services
./manage_docker.sh deploy wb-mqtt-bridge
./manage_docker.sh deploy wb-http-api

# Deploy UI
./manage_docker.sh deploy wb-mqtt-ui

# Check overall status
./manage_docker.sh status
```

## Benefits

### Consistency Benefits
- ✅ **Unified workflow**: Same script manages all containers
- ✅ **Consistent commands**: Identical operations for UI and backend
- ✅ **Single authentication**: Shared GitHub PAT for all artifacts
- ✅ **Same deployment pattern**: GitHub artifacts → Docker deployment

### Operational Benefits
- ✅ **Simplified management**: One script for entire stack
- ✅ **Automated updates**: Script handles image downloads and loading
- ✅ **Network integration**: UI containers join existing Docker networks
- ✅ **Health monitoring**: Consistent container status checking

### Development Benefits
- ✅ **No script proliferation**: Extend existing infrastructure
- ✅ **Familiar interface**: Developers already know the commands
- ✅ **Type safety**: Automatic detection of container types
- ✅ **Error handling**: Robust artifact validation and deployment

## Phase 3 Implementation Checklist

- [ ] Add UI container configuration arrays to manage_docker.sh
- [ ] Implement `detect_artifact_type()` function
- [ ] Create `deploy_ui_container()` function  
- [ ] Update main script logic to handle UI containers
- [ ] Test UI container deployment workflow
- [ ] Verify network connectivity between UI and backend containers
- [ ] Update script documentation and usage examples
- [ ] Test mixed deployment scenarios (backend + UI)
- [ ] Validate error handling for UI-specific failure modes
- [ ] Create integration tests for full deployment workflow

## Migration Path

### Phase 3.1: Script Extension (Week 1)
- Extend manage_docker.sh with UI container support
- Test deployment of wb-mqtt-ui via artifacts
- Validate network connectivity and port configuration

### Phase 3.2: Integration Testing (Week 2)  
- End-to-end testing of GitHub Actions → artifacts → deployment
- Performance testing of artifact download and container startup
- Documentation updates and team training

### Phase 3.3: Production Deployment (Week 3)
- Deploy to staging environment for validation
- Production deployment with monitoring
- Handover documentation and operational procedures

---

## Summary

This three-phase approach provides a complete path from local development to production deployment:

1. **Phase 1**: Local configuration mode eliminates API dependencies
2. **Phase 2**: GitHub Actions creates deployable ARM containers via artifacts  
3. **Phase 3**: Integration with existing deployment infrastructure

The result is a unified, artifact-based deployment strategy that maintains consistency with existing backend services while supporting the specific needs of static UI containers. 