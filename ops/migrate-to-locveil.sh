#!/bin/sh
# ONE-TIME controller migration: wb-mqtt-bridge -> locveil-bridge (OPS-21).
# Everything renames: the systemd unit, the runtime tree on /mnt/data, both
# images (backend + UI), both containers. The SQLite state store, logs and
# .env (reports token) move WITH the runtime tree.
#
# Run on the controller, as root, AFTER renaming the SD-card clone:
#
#   systemctl stop wb-mqtt-bridge 2>/dev/null || true
#   cd /mnt/sdcard && mv wb-mqtt-bridge locveil-bridge
#   cd locveil-bridge && git pull && sh ops/migrate-to-locveil.sh
#
# Prerequisite: the new images exist on GHCR and are PUBLIC
# (ghcr.io/locveil/locveil-bridge + ghcr.io/locveil/locveil-bridge-ui —
# first publish creates the packages private; flip them in the org package
# settings, same as the old ones).
set -eu
cd "$(dirname "$0")"

OLD_RUNTIME=/mnt/data/mqtt-bridge-config
NEW_RUNTIME=/mnt/data/locveil-bridge-config

# 1. Retire the old unit (its ExecStop downs the old stack from the old tree).
systemctl disable --now wb-mqtt-bridge 2>/dev/null || true
rm -f /etc/systemd/system/wb-mqtt-bridge.service
systemctl daemon-reload

# 2. Make sure the old stack is down, then rename the runtime tree.
#    (The compose project follows the directory name, so the old project must be
#    torn down from the OLD path before it disappears.)
if [ -d "$OLD_RUNTIME" ]; then
    (cd "$OLD_RUNTIME" && docker compose down --remove-orphans 2>/dev/null) || true
    if [ -e "$NEW_RUNTIME" ]; then
        echo "error: $NEW_RUNTIME already exists — resolve manually" >&2
        exit 2
    fi
    mv "$OLD_RUNTIME" "$NEW_RUNTIME"
    echo "runtime tree moved: $OLD_RUNTIME -> $NEW_RUNTIME (data/state/.env intact)"
fi

# 3. Normal update flow under the new identity: syncs config + compose into the
#    new tree, pulls ghcr.io/locveil/locveil-bridge{,-ui}, starts the stack.
./update.sh

# 4. Wire the new unit to boot (COPY, don't symlink — SD card is a lazy automount).
cp locveil-bridge.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable locveil-bridge

# 5. Drop the old-name images; keep the flash lean.
docker rmi $(docker images --format '{{.Repository}}:{{.Tag}}' | grep -E 'wb-mqtt-(bridge|ui)') 2>/dev/null || true
docker image prune -f

echo "migrated. unit=locveil-bridge.service runtime=$NEW_RUNTIME"
echo "verify:  curl -s http://localhost:8000/ && docker logs -f locveil-bridge"
