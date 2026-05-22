# Stage 1: Build Stage (Node.js 20 — no Python)
FROM node:20 AS builder

WORKDIR /app

# Build context is the MONOREPO ROOT (this Dockerfile is ui/Dockerfile). Copy the UI package
# manifests first for better caching.
COPY ui/package*.json ./
RUN npm ci

# Copy only what codegen needs from the backend (same monorepo): device configs
# (backend/config/devices/*.json) + the API contract (backend/openapi.json). No Python / pip is
# needed: device-state types come from openapi.json, not from importing the package.
COPY backend/config ./backend/config
COPY backend/openapi.json ./backend/openapi.json

# Copy the UI source
COPY ui/ ./

# Set environment variables for production build.
# Use relative URLs so the nginx proxy handles API/SSE routing. The MQTT URL is
# NOT baked in here — it is provided at container start via runtime-config.js
# (action_plan P1 #4), so the same image works on any network.
ENV VITE_API_BASE_URL=""
ENV VITE_SSE_BASE_URL=""

# Verify all paths are accessible
RUN echo "Verifying config structure:" && \
    ls -la backend/config/devices/ && \
    ls -la backend/ && \
    echo "Found $(ls backend/config/devices/*.json | wc -l) device configs"

# Generate device pages using package-based imports
RUN npm run gen:device-pages -- \
    --batch \
    --mode=package \
    --mapping-file=backend/config/device-state-mapping.json \
    --generate-router

# Validate TypeScript compilation
RUN npm run typecheck:all

# Build static assets
RUN npm run build

# Stage 2: Production (nginx on port 3000)
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
# nginx config is rendered from this template at startup (BACKEND_HOST/BACKEND_PORT).
COPY nginx.conf.template /etc/nginx/nginx.conf.template
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:3000/ || exit 1

ENTRYPOINT ["/docker-entrypoint.sh"] 