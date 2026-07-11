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

## On-controller layout (two trees, deliberately)

```
/mnt/sdcard/wb-mqtt-bridge/      <- this repo, cloned — needed ONLY at update time
/mnt/data/mqtt-bridge-config/    <- the RUNTIME tree: everything the service needs at boot
├── docker-compose.yml   deployed from the clone's ops/ by update.sh
├── .env                 reports token (user-created; update.sh never touches it)
├── config/              synced from the clone's backend/config by update.sh (:ro in container)
├── data/                SQLite state store — survives updates
└── logs/                service logs
```

Boot depends only on `/mnt/data` and Docker — deliberately **not** on the SD
card, which is lazily automounted and can be slow to appear after a reboot.
The card matters only when you run `update.sh`.

The runtime tree keeps the historical layout this Wirenboard has always used
(the pre-compose flow used the same three directories), so nothing about where
state and logs live changes across the migration. The repo clone is the config
**source of truth**: `git pull` + `update.sh` mirrors `backend/config` into the
runtime tree on every update.

Docker's image store stays at its existing location (`/mnt/data/.docker`): the
SD card is exFAT, which cannot host Docker's overlay filesystem, and the two
images are small enough for `/mnt/data` as long as `update.sh`'s prune step
keeps running (it removes each replaced `:latest` on every update). The SD card
holds only the repo clone — plain files, which exFAT handles fine.

Both containers run **non-root**, as uid 1000. The writable runtime directories
(`data/`, `logs/`) must therefore be owned by 1000 — `update.sh` chowns them on
every run, so this is automatic. `config/` is mounted read-only and stays as the
rsync leaves it. If you ever start the containers by hand without `update.sh`
first, chown those two directories yourself, or the backend can't write its state
DB and logs.

## First install (one-time, takes ~5 min)

Prereqs: WB has Docker installed (it does, via WB's own setup). You have shell
access to the WB.

### 1. Stop, remove containers AND old images from the docker_manager flow

```bash
# Stop + remove the running containers (no-op if they're not running)
sudo docker stop wb-mqtt-bridge wb-mqtt-ui 2>/dev/null || true
sudo docker rm   wb-mqtt-bridge wb-mqtt-ui 2>/dev/null || true

# Remove the docker_manager-installed images — they were sideloaded from
# tarballs, have no registry digest, and won't be reused. Critical: the WB
# has limited flash and these would otherwise sit dangling forever.
sudo docker rmi wb-mqtt-bridge:latest wb-mqtt-ui:latest 2>/dev/null || true

# If docker_manager is set up to auto-start them, remove these entries from
# its config (e.g., /etc/docker_manager_config.json or similar — depends on
# how you installed it). Leave docker_manager running for OTHER WB apps.
```

### 2. Clone the repo (on the SD card)

The clone is re-pullable "garbage" — it goes on the roomy SD card, keeping
`/mnt/data` (the small runtime partition) for state only:

```bash
cd /mnt/sdcard
sudo git clone https://github.com/droman42/wb-mqtt-bridge wb-mqtt-bridge
```

The existing `/mnt/data/mqtt-bridge-config/{config,data,logs}` tree stays exactly
where it is — it becomes the runtime tree. (Fresh install without one:
`sudo mkdir -p /mnt/data/mqtt-bridge-config/{config,data,logs}`.)

### 3. Initial sync into the runtime tree

`update.sh` does this on every update; run it once by hand so the first start
has current config and the compose file in place (config sync **replaces**
whatever the old flow left in `config/` — the repo is the source of truth).
Needs `rsync` (`sudo apt install rsync` if missing):

```bash
sudo rsync -a --delete /mnt/sdcard/wb-mqtt-bridge/backend/config/ /mnt/data/mqtt-bridge-config/config/
sudo cp /mnt/sdcard/wb-mqtt-bridge/ops/docker-compose.yml /mnt/data/mqtt-bridge-config/
```

The state DB (`/mnt/data/mqtt-bridge-config/data/state_store.sqlite`) holds your
devices' last-good assumed state — preserve it across upgrades.

### 4. Taking over from a bridge running elsewhere (cutover)

If another instance of the bridge has been serving the house from a different
machine (e.g. a development box), two things matter:

1. **Stop the other instance BEFORE starting this one.** Both use the same MQTT
   client id, and two live bridges on one broker fight over the connection and
   can double-actuate devices. Stop first, then start here — never overlap.
2. **Carry its state over (recommended).** The other instance's
   `backend/data/state_store.sqlite` holds the *current* assumed state of every
   device — much fresher than anything already in this Wirenboard's `data/`
   (which predates the other instance taking over). After stopping it, copy that
   file to `/mnt/data/mqtt-bridge-config/data/state_store.sqlite` here, so the
   takeover is seamless and no device gets re-commanded from stale assumptions.

### 5. Install the systemd unit

```bash
sudo cp /mnt/sdcard/wb-mqtt-bridge/ops/wb-mqtt-bridge.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable wb-mqtt-bridge.service
```

### 6. First start

```bash
cd /mnt/data/mqtt-bridge-config
sudo docker compose pull
sudo systemctl start wb-mqtt-bridge.service
sudo systemctl status wb-mqtt-bridge.service   # should be active (exited)
sudo docker compose ps                          # both containers Up
sudo docker compose logs -f                     # watch boot
```

Verify reachable:

```bash
curl http://localhost:8000/openapi.json | head
curl http://localhost:3000/                     # UI nginx (listens on 3000 —
                                                # port 80 belongs to the WB admin UI)
```

The web UI is then at `http://<wirenboard-ip>:3000/` from any browser on the LAN.

---

## Update flow (no cable, no PAT)

```bash
cd /mnt/sdcard/wb-mqtt-bridge
sudo git pull                  # config changes + scripts
sudo ./ops/update.sh           # syncs config into the runtime tree + pulls
                               # latest images + restarts + cleans dangling
```

`update.sh` first mirrors the clone's `backend/config` into
`/mnt/data/mqtt-bridge-config/config` and deploys `docker-compose.yml` next to
it (so a `git pull` is how both config and compose changes reach the runtime
tree), then runs `docker image prune -f` at the end, which removes the
**just-replaced** old `:latest` (now untagged) so the WB's flash doesn't
accumulate it. Tagged images you've pinned (e.g. `:vYYYYMMDD-<short>` for
rollback) are NOT touched.

To update just the images without `git pull`:

```bash
cd /mnt/data/mqtt-bridge-config
sudo docker compose pull
sudo docker compose up -d
sudo docker image prune -f     # don't forget — compose alone leaves dangling
```

### Reclaiming flash (periodic / when running low)

`update.sh`'s `image prune -f` only removes **untagged** images. If you've
been pinning multiple tagged versions over time and want to reclaim that
space:

```bash
sudo docker images                                            # see what's around
sudo docker rmi ghcr.io/locveil/wb-mqtt-bridge:vYYYYMMDD-<short>  # drop a specific tag
# OR — nuke everything not currently in use (containers/images/networks/build cache):
sudo docker system prune -a -f
```

`system prune -a -f` is safe on this WB: nothing else builds Docker images
here, and any image not referenced by a running container will be re-pullable
from GHCR.

---

## Enabling problem reports (optional, one-time)

The bridge can file problem reports (the UI's "Report a problem" button) as tickets
into a private GitHub repo. That needs a fine-grained GitHub PAT scoped to that one
repo (Issues + Contents read/write). The token reaches the container via an env
file next to the compose file — it is gitignored and never committed:

```bash
cat > /mnt/data/mqtt-bridge-config/.env <<'EOF'
WB_REPORTS_TOKEN=github_pat_XXXXXXXXXXXX
EOF
chmod 600 /mnt/data/mqtt-bridge-config/.env
```

Then set `"reports": {"enabled": true, ...}` in the repo's
`backend/config/system.json` (commit it — the repo is the config source of
truth), run `update.sh` (or restart:
`sudo systemctl restart wb-mqtt-bridge.service`). Both start paths — the systemd
unit and `update.sh` — read the same `.env` file, so the token survives updates.
Without the file, reporting simply stays disabled; nothing else is affected.

---

## Making the GHCR packages public (one-time, on first CI push)

The first time the CI workflow pushes images to `ghcr.io/locveil/wb-mqtt-bridge`
and `ghcr.io/locveil/wb-mqtt-ui`, they're created **private** by default. To
let the WB pull them anonymously (no PAT):

1. Go to https://github.com/users/droman42/packages and find each package.
2. Package settings → Danger Zone → "Change visibility" → Public.

Do this once per package; future pushes inherit the visibility.

---

## Recovery after a WB firmware upgrade

If the upgrade wipes Docker state but preserves `/mnt/data/`:

```bash
sudo systemctl daemon-reload                            # systemd unit survived
sudo docker compose -f /mnt/data/mqtt-bridge-config/docker-compose.yml pull
sudo systemctl start wb-mqtt-bridge.service
```

If the upgrade wipes `/mnt/data/` too: re-do steps 2-6 of First install. State
DB is gone in that scenario — devices will rebuild assumed state on next use.

---

## Rolling back to a specific image

The CI tags every build with `latest`, `sha-<short>`, and `vYYYYMMDD-<short>`.
To pin to a known-good build, edit `ops/docker-compose.yml`:

```yaml
backend:
  image: ghcr.io/locveil/wb-mqtt-bridge:v20260526-abc1234
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
