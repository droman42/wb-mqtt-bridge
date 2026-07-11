# Quickstart & Tester Guide

How to install the bridge, see what it exposes, and exercise it — aimed at a tester or a
new contributor doing a first pass.

> **Read this first.** The bridge is a **hardware actuation backend**: in normal operation
> it drives a real house — TVs, an AV processor, air conditioners, lights — over an MQTT
> broker. A safe first look **never points at a live house broker**. The steps below start
> with zero-risk, broker-free exploration; the one step that runs the full service is
> explicitly scoped to a *local* broker, with the reasons spelled out.

> **Run the backend commands from `backend/`.** All paths below are relative to it unless
> noted. Real deployment onto a Wirenboard controller is a separate story — see
> [`../ops/INSTALL.md`](../ops/INSTALL.md).

---

## 1. Install

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # if you don't have uv
cd backend
uv sync --extra dev                               # creates the venv + installs deps (incl. dev tools)
```

## 2. See what the bridge exposes — no broker, no risk

Two commands read the config and print the bridge's public surfaces without connecting to
anything. This is the fastest way to understand what the bridge *is* before running it.

```bash
uv run wb-catalog -o catalog.json    # the device catalog: every device, room, capability,
                                     # and value vocabulary — what the UI and the voice
                                     # assistant consume. Prints "N devices, M rooms, version …".

uv run wb-openapi -o openapi.json    # the full REST + SSE contract (the same file the UI
                                     # generates its TypeScript types from).
```

Open `catalog.json` to see the house as the bridge presents it — rooms, devices, and the
canonical actions each device answers. Open `openapi.json` (or paste it into any OpenAPI
viewer) to browse the endpoints.

## 3. Run the test suites

The suites exercise the bridge against scratch fixtures — safe to run anywhere, no house
broker involved.

```bash
# From backend/ — the unit + integration suite:
uv run pytest

# From eval/ — the declarative CLI-contract tests:
cd ../eval && make cli
```

`make cli` wires the backend venv and runs the CLI contracts (e.g. a catalog dump, a
Broadlink code round-trip). The MQTT system tests (`make mqtt`) need a running broker and
bridge and are covered in [`../eval/README.md`](../eval/README.md).

## 4. Run the full service locally — *local broker only*

If you want the live REST API and the runtime UI behaviour, run the service against a
**local** MQTT broker with a **scratch** config. Do **not** run it against the house.

> **Why the caution.** The committed `backend/config/` is the *real house* configuration —
> its `system.json` points at the production broker. Two bridges on one broker collide on
> the shared MQTT client id, and a second bridge carrying its own state database can
> *restore-actuate* real devices on startup. So a local run uses its own broker and its own
> config copy, and never the committed one as-is.

```bash
# A throwaway local broker (any mosquitto works; a non-standard port keeps it obviously separate):
mosquitto -p 1899 &

# A scratch config that targets THAT broker, not the house:
cp -r config /tmp/wb-scratch-config
#  → edit /tmp/wb-scratch-config/system.json:
#      set the MQTT broker host to 127.0.0.1 and port to 1899
#      set persistence.db_path to a throwaway path (e.g. /tmp/wb-scratch.sqlite)

# Run the service with the scratch config as its working config dir:
cd /tmp/wb-scratch-config/.. && ln -sfn wb-scratch-config config   # the app reads ./config
uv run --project /path/to/backend locveil-bridge
```

The API comes up on `http://localhost:8000` — try `http://localhost:8000/docs` (interactive
API), `GET /system/catalog`, and `GET /devices`. Real devices won't respond (they're not on
your local broker) — that's the point; you're exercising the API surface safely.

## 5. Deploy for real

Onto a Wirenboard 7 controller, via the `ops/` compose stack (armv7 images from GHCR):
**[`../ops/INSTALL.md`](../ops/INSTALL.md)**. That is the only supported production path.

## Where to go next

- **[Architecture overview](architecture/overview.md)** — the hexagon, the ports, how the
  pieces fit.
- **[Root README](../README.md)** — what the bridge is and how it pairs with the voice
  assistant.
- **How-tos** — [add a device](guides/howto-new-device.md),
  [add a driver](guides/howto-new-driver.md),
  [define a scenario](guides/howto-new-scenario.md).
