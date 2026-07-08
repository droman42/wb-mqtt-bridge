#!/usr/bin/env bash
# ops/update.sh — sync config, pull latest backend + UI images from GHCR, (re)start.
# Replaces the ~1000-line manage_docker.sh + the GitHub PAT + the artifact
# download dance. Idempotent. Cleans up dangling images afterwards — the WB
# has limited flash and repeated pulls of :latest leave the previous image
# untagged on disk.
#
# Usage on the Wirenboard:
#   cd /mnt/sdcard/wb-mqtt-bridge
#   git pull                 # config + this script
#   ./ops/update.sh          # sync config + pull images + restart + prune
set -euo pipefail

cd "$(dirname "$0")"

# The containers mount the runtime tree at /mnt/data/mqtt-bridge-config (the
# historical layout — see docker-compose.yml header). The repo clone is the
# config source of truth; mirror it into the runtime tree on every update.
RUNTIME_CONFIG=/mnt/data/mqtt-bridge-config/config
REPO_CONFIG="$(cd ../backend/config && pwd)"
echo ">>> rsync config: $REPO_CONFIG -> $RUNTIME_CONFIG"
mkdir -p "$RUNTIME_CONFIG"
rsync -a --delete "$REPO_CONFIG/" "$RUNTIME_CONFIG/"

echo ">>> docker compose pull"
docker compose pull
echo ">>> docker compose up -d --remove-orphans"
docker compose up -d --remove-orphans
# Prune ONLY dangling (untagged) images — what was :latest before the pull
# became untagged when the new :latest replaced it. Tagged images (pinned
# rollback versions like :vYYYYMMDD-<sha>) are untouched. Safe every run.
echo ">>> docker image prune -f  (reclaim flash from old :latest)"
docker image prune -f
echo ">>> docker compose ps"
docker compose ps
