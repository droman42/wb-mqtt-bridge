# Network Configuration for Deployment

## Problem

When deploying the application in Docker containers, network connectivity between the frontend and backend can fail if not configured properly. The common error is:

```
AxiosError: Network Error
baseURL: "http://localhost:8000"
```

This occurs when the frontend tries to connect to `localhost:8000` from within a container, where `localhost` refers to the container itself, not the host machine.

## Solution

The application now supports multiple deployment modes through environment variables:

### Development Mode

For local development with backend running on the same machine:

```bash
# .env file
VITE_API_BASE_URL=http://localhost:8000
VITE_SSE_BASE_URL=http://localhost:8000
VITE_MQTT_URL=ws://localhost:9001
```

### Development with Remote Backend

For development with backend running on a different machine:

```bash
# .env file
VITE_API_BASE_URL=http://192.168.110.250:8000
VITE_SSE_BASE_URL=http://192.168.110.250:8000
VITE_MQTT_URL=ws://192.168.110.250:9001
```

### Production Docker Deployment (Recommended)

For production deployment using Docker with nginx proxy:

```bash
# Environment variables in Dockerfile
ENV VITE_API_BASE_URL=""
ENV VITE_SSE_BASE_URL=""
ENV VITE_MQTT_URL="ws://192.168.110.250:9001"
```

When `VITE_API_BASE_URL` is an empty string, the application uses relative URLs (`/api`) that are handled by the nginx proxy.

## Docker Container Network Flow

```
Frontend (container:3000) 
  ↓ API requests to /api/* 
nginx proxy 
  ↓ proxy_pass to http://192.168.110.250:8000/
Backend (host:8000)
```

## Key Configuration Files

### 1. Dockerfile
Sets environment variables for production build:
```dockerfile
ENV VITE_API_BASE_URL=""
ENV VITE_SSE_BASE_URL=""
ENV VITE_MQTT_URL="ws://192.168.110.250:9001"
```

### 2. nginx.conf
Proxies API requests to the backend:
```nginx
location /api/ {
    proxy_pass http://192.168.110.250:8000/;
    # ... proxy headers
}

location /events/ {
    proxy_pass http://192.168.110.250:8000/events/;
    # ... SSE-specific configuration
}
```

### 3. Frontend Configuration (automatic)
The application automatically detects empty environment variables and uses appropriate URLs:
- Empty `VITE_API_BASE_URL` → uses `/api` (nginx proxy)
- Set `VITE_API_BASE_URL` → uses absolute URL (direct connection)

## Deployment Steps

1. **Build the Docker image:**
   ```bash
   docker build -t wb-mqtt-ui:latest .
   ```

2. **Run the container:**
   ```bash
   docker run -d --name wb-ui -p 3000:3000 wb-mqtt-ui:latest
   ```

3. **Verify connectivity:**
   - Frontend: http://192.168.110.250:3000
   - Backend should be accessible at: http://192.168.110.250:8000
   - API proxy test: http://192.168.110.250:3000/api/system

## Troubleshooting

### "Network Error" in browser console
- Check if backend is running on `192.168.110.250:8000`
- Verify nginx proxy configuration
- Test direct backend access: `curl http://192.168.110.250:8000/system`

### SSE connection issues
- Check `/events/` proxy configuration in nginx
- Verify SSE endpoint: `curl -H "Accept: text/event-stream" http://192.168.110.250:8000/events/devices`

### MQTT WebSocket issues
- Verify MQTT broker is running on port 9001
- Check WebSocket endpoint: `ws://192.168.110.250:9001`
- Ensure firewall allows WebSocket connections

## Network Architecture

```
┌─────────────────────────────────────────────────────┐
│ Host Machine (192.168.110.250)                     │
│                                                     │
│ ┌─────────────────┐    ┌────────────────────────┐   │
│ │ Docker Container│    │ Backend Services       │   │
│ │                 │    │                        │   │
│ │ Frontend + nginx│    │ API Server :8000       │   │
│ │ :3000           │────│ MQTT Broker :9001      │   │
│ │                 │    │                        │   │
│ └─────────────────┘    └────────────────────────┘   │
└─────────────────────────────────────────────────────┘
            │
            ▼
    User Browser Access
 http://192.168.110.250:3000
```

This configuration ensures reliable communication between all components while maintaining proper network isolation and security. 