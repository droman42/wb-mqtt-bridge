#!/usr/bin/env bash
# ops/update.sh — pull latest backend + UI images from GHCR and (re)start.
# Replaces the ~1000-line manage_docker.sh + the GitHub PAT + the artifact
# download dance. Idempotent.
#
# Usage on the Wirenboard:
#   cd /mnt/data/mqtt-bridge-config
#   git pull                 # config + this script
#   ./ops/update.sh          # pull images + restart
set -euo pipefail

cd "$(dirname "$0")"
echo ">>> docker compose pull"
docker compose pull
echo ">>> docker compose up -d --remove-orphans"
docker compose up -d --remove-orphans
echo ">>> docker compose ps"
docker compose ps
