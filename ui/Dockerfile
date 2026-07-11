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

# Validate TypeScript compilation. The API types (src/types/api.gen.ts) are committed and Layer 3
# removed the build-time page generator, so the UI build no longer runs codegen or reads backend/.
RUN npm run typecheck:all

# Build static assets
RUN npm run build

# Stage 2: Production (nginx on port 3000)
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
# nginx config is rendered from this template at startup (BACKEND_HOST/BACKEND_PORT).
# Build context is the monorepo root, so these UI files live under ui/.
COPY ui/nginx.conf.template /etc/nginx/nginx.conf.template
COPY ui/docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Non-root by design (same rationale as the backend image — matches uid 1000 so
# the product runs under one identity). nginx as uid 1000 needs write access to
# the paths it touches at start/run: the entrypoint's envsubst renders
# /etc/nginx/nginx.conf and /usr/share/nginx/html/runtime-config.js, and nginx
# itself writes the temp/cache and error-log trees. The pid file is redirected to
# /tmp in nginx.conf.template. listen :3000 is >1024, so no root is needed to bind.
RUN adduser -D -u 1000 locveil && \
    chown -R locveil:locveil /var/cache/nginx /var/log/nginx /etc/nginx /usr/share/nginx/html
USER locveil

EXPOSE 3000

# 127.0.0.1 explicitly: busybox wget resolves `localhost` to ::1 first, and
# nginx listens on IPv4 only — the check refused forever (seen live on the WB7
# while real traffic worked fine).
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://127.0.0.1:3000/ || exit 1

ENTRYPOINT ["/docker-entrypoint.sh"] 