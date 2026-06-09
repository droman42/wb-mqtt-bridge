# wb-mqtt-bridge

A Wirenboard-side bridge that brings A/V equipment and other appliances into the
Wirenboard MQTT ecosystem, runs Logitech-Harmony-style **scenarios** across them,
and pairs with the [Irene](https://github.com/droman42/wb-mqtt-voice) voice assistant
as the home's single device catalog and actuation backend.

> **Status — pre-release, single home.** The hexagonal backend, the typed config + state
> models, and the scenario reconciler are settled and hardware-verified on a Wirenboard
> 7. The React UI ships an iPad-portrait Harmony-style remote with backend-served runtime
> layouts. Voice-assistant pairing and the per-device setup pages are in active
> development; appliance pages, the topology setup page, and the Wirenboard 8 / arm64
> image are planned. Today it runs one home, one user, LAN only.

## What it does

- **Logitech-Harmony-style A/V remote and scenarios.** One-touch activities ("watch
  Apple TV", "play LD") drive a whole AV chain — TV, AVR, source — through one
  reconciler that diffs intended state against assumed state, executes only what's
  changed, and respects topology ordering (power before input, ARC delays, RCA-hub
  manual steps).
- **WB-foreign devices become WB virtual devices.** Each non-Wirenboard device (TV,
  AVR, streamer, kitchen hood, reel-to-reel, IR gear) is mirrored as a virtual device
  on the MQTT broker, so `wb-rules` can orchestrate it alongside native WB gear.
- **Two UI shapes, by category.** A/V devices get the remote layout; appliances get
  purpose-built pages. Per-device layouts are *backend-served manifests* rendered at
  runtime — no UI rebuild on config change.
- **Native WB gear, addressed the same way.** A `wb-passthrough` driver turns existing
  Wirenboard controls (`wb-mr6c`, `wb-mdm3`, `wb-mrgbw-d`, `dooya`, `wb-gpio`,
  `hvac_*`, …) into first-class devices in the bridge's catalog — same API, same room
  + capability metadata, so the voice assistant addresses the whole house through one
  surface.
- **Strongly typed end-to-end.** Pydantic device configs, per-device state models, an
  OpenAPI contract the UI consumes by codegen. No dict-shaped state.
- **Hexagonal layering, enforced.** `domain/` is import-pure; infrastructure adapters
  (MQTT, SQLite, drivers) implement the ports.

## Documentation

- **[Architecture overview](docs/architecture/overview.md)** — the hexagon, its ports
  and seams, how the pieces fit.
  - **[Devices and scenarios](docs/architecture/devices-and-scenarios.md)** — drivers,
    the IR / native-library / WB-passthrough distinction, scenarios on top.
  - **[Key concepts](docs/architecture/key-concepts.md)** — topology, capabilities,
    configs, reconciler; declarative definitions; scenario inheritance, startup,
    switching.
  - **[Interfaces](docs/architecture/interfaces.md)** — REST + MQTT + virtual-device
    emulation; the seams the rest of the house sees.
  - **[Rooms](docs/architecture/rooms.md)** — the room concept and what it buys
    scenarios and the voice assistant.
  - **[UI](docs/architecture/ui.md)** — the Harmony-style remote, runtime layout
    manifests, build-time codegen.
- **Planned features** — designed-but-not-built admin surfaces:
  - **[Device setup](docs/planned/device-setup.md)** — WB-cell importer + IR-learning
    sub-page (with public IR-code database support).
  - **[Topology setup](docs/planned/topology-setup.md)** — graph editor for the signal
    topology, with path-preview + interactive validator.
  - **[Appliance + room pages](docs/planned/appliance-pages.md)** — per-class
    appliance UIs (HVAC, Roborock, …) + per-room iPad-portrait dashboards.
  - **[Voice setup](docs/planned/voice-setup.md)** — bridge-side readiness surface
    for the Irene pairing.
- **[Contributing](CONTRIBUTING.md)** — developer setup, conventions, the gates each
  commit must clear. How-tos: [add a device with an existing
  driver](docs/guides/howto-new-device.md), [add a new device driver with a native
  library](docs/guides/howto-new-driver.md), [define a new AV
  scenario](docs/guides/howto-new-scenario.md).

## Acknowledgements

- The A/V remote and scenarios are modelled on Logitech's discontinued **Harmony**
  remotes — the same idea of one-touch activities across many devices, brought into the
  Wirenboard environment.
- The voice side is **[Irene](https://github.com/droman42/wb-mqtt-voice)** (sister
  project, `wb-mqtt-voice`). Irene owns voice; this bridge owns devices and all WB /
  MQTT conventions.

## License

MIT (declared in `backend/pyproject.toml`).
