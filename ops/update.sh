#!/usr/bin/env bash
# ops/update.sh — sync config + compose into the runtime tree, pull latest
# backend + UI images from GHCR, (re)start. Replaces the ~1000-line
# manage_docker.sh + the GitHub PAT + the artifact download dance. Idempotent.
# Cleans up dangling images afterwards — the WB has limited flash and repeated
# pulls of :latest leave the previous image untagged on disk.
#
# The SD-card clone is needed ONLY while this script runs (git pull + sources
# of truth). Everything the service needs at BOOT — compose file, .env, config,
# state — lives in the runtime tree on /mnt/data, so a reboot never depends on
# the lazily-mounted SD card.
#
# Usage on the Wirenboard:
#   cd /mnt/sdcard/locveil-bridge
#   git pull                 # config + compose + this script
#   ./ops/update.sh          # sync + pull images + restart + prune
set -euo pipefail

cd "$(dirname "$0")"
RUNTIME=/mnt/data/locveil-bridge-config

# Mirror the config source of truth into the runtime tree.
echo ">>> rsync config -> $RUNTIME/config"
mkdir -p "$RUNTIME/config"
rsync -a --delete "$(cd ../backend/config && pwd)/" "$RUNTIME/config/"

# The compose file also deploys into the runtime tree (the systemd unit runs
# compose from there — boot must not depend on the SD card). The .env next to
# it (reports token, user-created) is deliberately left alone.
echo ">>> deploy docker-compose.yml -> $RUNTIME"
cp docker-compose.yml "$RUNTIME/docker-compose.yml"

# The container runs non-root as uid 1000 (`USER locveil` in the Dockerfiles), but
# this script runs as root on the controller. The writable bind mounts must be
# owned by 1000 or the container hits EACCES (state DB, reports spool, logs). The
# :ro config mount is left alone — it is world-readable straight from the rsync.
# uid 1000 is unassigned on a stock Wirenboard; on an existing box this migrates
# the tree's prior ownership. Runs before `up` so the new image starts on 1000-owned dirs.
echo ">>> chown runtime data+logs -> 1000:1000 (non-root container user)"
mkdir -p "$RUNTIME/data" "$RUNTIME/logs"
chown -R 1000:1000 "$RUNTIME/data" "$RUNTIME/logs" 2>/dev/null || true

cd "$RUNTIME"
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
