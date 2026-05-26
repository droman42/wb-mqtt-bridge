# Deploying wb-mqtt-bridge on the Wirenboard

Standard Docker tooling — **not** WB's native `docker_manager`. Trade-offs:
- ✅ No GitHub PAT, no GitHub-API artifact dance, plain `docker pull`.
- ✅ ~10-line `update.sh` instead of a 1000-line `manage_docker.sh`.
- ✅ Standard compose / systemd / Docker workflow — transferable knowledge.
- ⚠ Containers won't appear in WB's admin UI as "managed apps" (they're just
  regular `docker ps` containers).
- ⚠ WB firmware updates: behaviour unknown (state at `/mnt/data/` should
  persist; Docker state may or may not). If wiped, the recovery is the
  "First install" section below — about 5 commands.

---

## First install (one-time, takes ~5 min)

Prereqs: WB has Docker installed (it does, via WB's own setup). You have shell
access to the WB.

### 1. Stop and disable the docker_manager flow for these containers

```bash
# Stop the running containers (no-op if they're not running)
sudo docker stop wb-mqtt-bridge wb-mqtt-ui 2>/dev/null || true
sudo docker rm   wb-mqtt-bridge wb-mqtt-ui 2>/dev/null || true

# If docker_manager is set up to auto-start them, remove these entries from
# its config (e.g., /etc/docker_manager_config.json or similar — depends on
# how you installed it). Leave docker_manager running for OTHER WB apps.
```

### 2. Preserve existing runtime state (if any)

The current docker_manager flow keeps state at `/mnt/data/mqtt-bridge-config/{data,logs}`.
Move it aside so the `git clone` step below has a clean target:

```bash
sudo mv /mnt/data/mqtt-bridge-config /mnt/data/mqtt-bridge-config.bak
```

### 3. Clone the repo at the install path

```bash
cd /mnt/data
sudo git clone https://github.com/droman42/wb-mqtt-bridge mqtt-bridge-config
sudo mkdir -p mqtt-bridge-config/.state
```

### 4. Restore preserved state (skip on a fresh install)

```bash
sudo mv /mnt/data/mqtt-bridge-config.bak/data /mnt/data/mqtt-bridge-config/.state/data
sudo mv /mnt/data/mqtt-bridge-config.bak/logs /mnt/data/mqtt-bridge-config/.state/logs
sudo rm -rf /mnt/data/mqtt-bridge-config.bak  # contains the old `config/` dir we no longer need
```

The state DB (`/mnt/data/mqtt-bridge-config/.state/data/state.db`) holds your
devices' last-good assumed state — preserve it across upgrades.

### 5. Install the systemd unit

```bash
sudo cp /mnt/data/mqtt-bridge-config/ops/wb-mqtt-bridge.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable wb-mqtt-bridge.service
```

### 6. First start

```bash
cd /mnt/data/mqtt-bridge-config/ops
sudo docker compose pull
sudo systemctl start wb-mqtt-bridge.service
sudo systemctl status wb-mqtt-bridge.service   # should be active (exited)
sudo docker compose ps                          # both containers Up
sudo docker compose logs -f                     # watch boot
```

Verify reachable:

```bash
curl http://localhost:8000/openapi.json | head
curl http://localhost:80/                       # UI nginx
```

---

## Update flow (no cable, no PAT)

```bash
cd /mnt/data/mqtt-bridge-config
sudo git pull                  # config changes
sudo ./ops/update.sh           # pulls latest images + restarts
```

Or to update just the images (no repo changes):

```bash
cd /mnt/data/mqtt-bridge-config/ops
sudo docker compose pull
sudo docker compose up -d
```

---

## Making the GHCR packages public (one-time, on first CI push)

The first time the CI workflow pushes images to `ghcr.io/droman42/wb-mqtt-bridge`
and `ghcr.io/droman42/wb-mqtt-ui`, they're created **private** by default. To
let the WB pull them anonymously (no PAT):

1. Go to https://github.com/users/droman42/packages and find each package.
2. Package settings → Danger Zone → "Change visibility" → Public.

Do this once per package; future pushes inherit the visibility.

---

## Recovery after a WB firmware upgrade

If the upgrade wipes Docker state but preserves `/mnt/data/`:

```bash
sudo systemctl daemon-reload                            # systemd unit survived
sudo docker compose -f /mnt/data/mqtt-bridge-config/ops/docker-compose.yml pull
sudo systemctl start wb-mqtt-bridge.service
```

If the upgrade wipes `/mnt/data/` too: re-do steps 3-6 of First install. State
DB is gone in that scenario — devices will rebuild assumed state on next use.

---

## Rolling back to a specific image

The CI tags every build with `latest`, `sha-<short>`, and `vYYYYMMDD-<short>`.
To pin to a known-good build, edit `ops/docker-compose.yml`:

```yaml
backend:
  image: ghcr.io/droman42/wb-mqtt-bridge:v20260526-abc1234
```

Then `sudo systemctl restart wb-mqtt-bridge.service`. To return to live updates,
restore `:latest` and `update.sh` again.

---

## What replaced what

| Old (docker_manager flow) | New (compose flow) |
|---|---|
| `ops/manage_docker.sh` (1081 lines) | `ops/update.sh` (~10 lines) |
| `ops/docker_manager_config.json` (with GitHub PAT) | `ops/docker-compose.yml` (no secrets) |
| GitHub Actions artifact + `wb-mqtt-bridge-config.tar.gz` | Cloned repo on WB; `git pull` updates config |
| `docker run …` per container with per-container args | `docker compose up -d` |
| docker_manager lifecycle | `wb-mqtt-bridge.service` systemd unit |
