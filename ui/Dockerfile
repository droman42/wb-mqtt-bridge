# Stage 1: Build Stage (Node.js 20 + Python for ARM compatibility)
FROM node:20 AS builder

WORKDIR /app

# Install Python 3.9 and pip for package-based imports
RUN apt-get update && \
    apt-get install -y python3 python3-pip python3-venv && \
    rm -rf /var/lib/apt/lists/*

# Copy package files first for better caching
COPY package*.json ./
RUN npm ci

# Copy config repo (now in build context)
COPY wb-mqtt-bridge/ ./wb-mqtt-bridge/

# Install wb-mqtt-bridge package
RUN cd wb-mqtt-bridge && \
    pip3 install -e . && \
    echo "Testing package imports..." && \
    python3 -c "from wb_mqtt_bridge.domain.devices.models import WirenboardIRState; print('✅ Device models import successful')" && \
    python3 -c "from wb_mqtt_bridge.infrastructure.scenarios.models import ScenarioWBConfig; print('✅ Scenario models import successful')" || echo "⚠️ Scenario models not available (optional)"

# Copy frontend source code
COPY . .

# Set environment variables for production build
# Use relative URLs so nginx proxy handles the routing
ENV VITE_API_BASE_URL=""
ENV VITE_SSE_BASE_URL=""
ENV VITE_MQTT_URL="ws://192.168.110.250:9001"

# Verify all paths are accessible
RUN echo "Verifying config structure:" && \
    ls -la wb-mqtt-bridge/config/devices/ && \
    ls -la wb-mqtt-bridge/app/ && \
    echo "Found $(ls wb-mqtt-bridge/config/devices/*.json | wc -l) device configs"

# Generate device pages using package-based imports
RUN npm run gen:device-pages -- \
    --batch \
    --mode=package \
    --mapping-file=config/device-state-mapping.json \
    --generate-router

# Validate TypeScript compilation
RUN npm run typecheck:all

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