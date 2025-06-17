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