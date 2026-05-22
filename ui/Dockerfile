# Stage 1: Build Stage (Node.js 20 — no Python)
FROM node:20 AS builder

WORKDIR /app

# Copy package files first for better caching
COPY package*.json ./
RUN npm ci

# Copy the sibling backend repo (in the build context). Used at codegen time for
# device configs (config/devices/*.json) and the API contract (openapi.json).
# No Python / pip is needed: device-state types come from openapi.json, not from
# importing the package and AST-parsing Pydantic classes (action_plan P1 #3.5).
COPY wb-mqtt-bridge/ ./wb-mqtt-bridge/

# Copy frontend source code
COPY . .

# Set environment variables for production build.
# Use relative URLs so the nginx proxy handles API/SSE routing. The MQTT URL is
# NOT baked in here — it is provided at container start via runtime-config.js
# (action_plan P1 #4), so the same image works on any network.
ENV VITE_API_BASE_URL=""
ENV VITE_SSE_BASE_URL=""

# Verify all paths are accessible
RUN echo "Verifying config structure:" && \
    ls -la wb-mqtt-bridge/config/devices/ && \
    ls -la wb-mqtt-bridge/ && \
    echo "Found $(ls wb-mqtt-bridge/config/devices/*.json | wc -l) device configs"

# Generate device pages using package-based imports
RUN npm run gen:device-pages -- \
    --batch \
    --mode=package \
    --mapping-file=wb-mqtt-bridge/config/device-state-mapping.json \
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