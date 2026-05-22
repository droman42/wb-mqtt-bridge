#!/bin/sh
# Container entrypoint: render per-deployment configuration from environment
# variables, then start nginx (action_plan P1 #4).
#
#   BACKEND_HOST / BACKEND_PORT  -> nginx /api and /events proxy target
#   MQTT_URL                     -> browser MQTT broker URL (runtime-config.js)
#
# Defaults preserve the previous hardcoded values, so behavior is unchanged when
# the env vars are not set.
set -eu

BACKEND_HOST="${BACKEND_HOST:-192.168.110.250}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
MQTT_URL="${MQTT_URL:-ws://192.168.110.250:9001}"
export BACKEND_HOST BACKEND_PORT

# Render nginx config from the template. Only substitute our two variables so
# nginx's own runtime variables ($host, $remote_addr, ...) are left intact.
envsubst '${BACKEND_HOST} ${BACKEND_PORT}' \
    < /etc/nginx/nginx.conf.template \
    > /etc/nginx/nginx.conf

# Render the browser-visible runtime config consumed by src/config/runtime.ts.
cat > /usr/share/nginx/html/runtime-config.js <<EOF
window.RUNTIME_CONFIG = {
  API_BASE_URL: "",
  MQTT_URL: "${MQTT_URL}",
  VERSION: "container"
};
EOF

echo "Configured: backend proxy -> ${BACKEND_HOST}:${BACKEND_PORT}, MQTT_URL -> ${MQTT_URL}"

exec nginx -g 'daemon off;'
