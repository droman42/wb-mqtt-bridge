#!/usr/bin/env bash
# ops/update.sh — pull latest backend + UI images from GHCR and (re)start.
# Replaces the ~1000-line manage_docker.sh + the GitHub PAT + the artifact
# download dance. Idempotent. Cleans up dangling images afterwards — the WB
# has limited flash and repeated pulls of :latest leave the previous image
# untagged on disk.
#
# Usage on the Wirenboard:
#   cd /mnt/data/mqtt-bridge-config
#   git pull                 # config + this script
#   ./ops/update.sh          # pull images + restart + clean up dangling
set -euo pipefail

cd "$(dirname "$0")"
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
