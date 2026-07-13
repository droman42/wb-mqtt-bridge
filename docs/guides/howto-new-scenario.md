# How-to — define a new AV scenario

A scenario is the Logitech-Harmony idea: one tap brings up the right
combination of devices for an activity ("Watch movies on Apple TV"). On
this project, scenarios are **thin** — they declare *what* (which devices
fill which roles), and the reconciler derives *how* (the per-device
actions to fire) from the topology and the capability maps.

This guide assumes the participating devices already exist (configs +
capability maps) and the topology already wires them. If a device is
missing, do [How-to: add a device with an existing driver](howto-new-device.md)
or [How-to: add a new driver](howto-new-driver.md) first; if the wiring
isn't in `config/topology.json`, extend that file (the schema is in
**[Architecture: key concepts](../architecture/key-concepts.md)**).

## Three things you decide before writing the file

1. **The roles** — `source` (the device producing the content),
   `display` (the video sink, usually the TV), `audio` (the device that
   plays the sound). These are required for any thin scenario.
2. **The room** — `room_id` must match a `room_id` in
   `config/rooms.json`. **Every device named by the scenario must
   live in that same room** — the bridge hard-fails at load on mismatch.
3. **Any manual steps** — passive switches in the audio path (an RCA
   hub), tape decks, turntables, anything the user has to touch by hand.
   These come from the topology's manual nodes (resolved at activation
   time) and from your scenario's optional `manual_instructions` block
   (static notes shown on the scenario page).

## Worked example — Apple TV in the living room

File: `config/scenarios/movie_appletv.json`.

```json
{
  "scenario_id": "movie_appletv",
  "names": { "ru": "Кино с Apple TV", "en": "Watch movies on Apple TV" },
  "description": "Setup for watching movies with optimal audio and video settings",
  "room_id": "living_room",

  "source":  "appletv_living",
  "display": "living_room_tv",
  "audio":   "mf_amplifier",

  "roles": {
    "volume":   "mf_amplifier",
    "playback": "appletv_living",
    "tracks":   "appletv_living",
    "menu":     "appletv_living",
    "pointer":  "appletv_living",
    "apps":     "appletv_living",
    "inputs":   "processor"
  },

  "manual_instructions": {
    "startup": [
      "💡 Dim the living room lights if needed",
      "🎬 Make sure the projector screen is down"
    ],
    "shutdown": [
      "💡 Don't forget to turn the lights back on",
      "🎬 Raise the projector screen if you're done watching"
    ]
  }
}
```

What each block does:

| Block | What it does |
|---|---|
| `scenario_id`, `names`, `description` | Identity. `scenario_id` must match the filename; `names` is a localized `{ru, en}` object. |
| `room_id` | The room invariant — every device named below must live here. |
| `source` / `display` / `audio` | The thin selection — the reconciler derives membership, input values, and order by DFS-ing the topology from `source` → `display` → `audio`. |
| `roles` | Maps a UI / capability slot to the device that backs it on the scenario page. `volume` → the AVR (so the scenario's volume slider drives the amp, not the TV); `playback` → the source (transport keys belong to the Apple TV, not the AVR); etc. |
| `manual_instructions.startup` / `.shutdown` | Static notes the UI renders as a bottom panel on the scenario page. Distinct from the *runtime* `manual_steps` the reconciler emits when the topology crosses a manual node (e.g. "set the Dodocus to LD") — those appear in the activation response, not on the manifest. |

## A simpler example — Zappiti video player

`config/scenarios/movie_zappiti.json`:

```json
{
  "scenario_id": "movie_zappiti",
  "names": { "ru": "Кино с Zappiti", "en": "Watch movies on Zappiti" },
  "description": "Setup for watching movies with optimal audio and video settings",
  "room_id": "living_room",

  "source":  "video",
  "display": "living_room_tv",
  "audio":   "mf_amplifier",

  "roles": {
    "volume":   "mf_amplifier",
    "playback": "video",
    "tracks":   "video",
    "menu":     "video",
    "inputs":   "processor"
  },

  "manual_instructions": { ... }
}
```

Same structure; no `apps` (Zappiti has no app launcher) or `pointer`
(no Magic-Remote pointer). Drop the roles your source doesn't expose —
the manifest simply omits the corresponding zone.

## Where to put the file

`config/scenarios/<scenario_id>.json`. Flat directory — no
per-room subfolders. The filename must match `scenario_id` exactly.

## The required and optional roles

For thin scenarios:

| Role | Required? | What it's used for |
|---|---|---|
| `source` | yes | DFS root in `resolve_targets`; the content source. |
| `display` | yes | The video sink; the path's end node. |
| `audio` | yes | The audio device; binds the volume slider. |
| `roles.volume` | recommended | Which device the volume slider drives (usually `audio`). |
| `roles.playback` / `tracks` / `menu` / `pointer` / `apps` | optional | Per-zone routing on the scenario manifest — each control carries the canonical `(capability, action)` tuple it dispatches through the room's Scenario Manager entity, which resolves the role to the backing device at fire time. |
| `roles.inputs` | optional | Which device the input dropdown selects on. Usually the AVR, not the source. |

Omit a role and the corresponding manifest zone is empty. Don't list a
role that points at a device with no capability in that domain — it
won't error, but it'll render an empty zone.

## What the reconciler does with the scenario

When a caller hits `POST /scenario/start` (the scenario id in the request body):

1. **Resolve targets** — DFS `appletv_living` → `living_room_tv` →
   `mf_amplifier` over the topology, collecting each link's destination
   port as the input the sink must select.
2. **Diff vs assumed state** — for every device on the resolved path,
   read its `get_current_state()` and emit only the deltas. A device
   already in the right state contributes zero actions.
3. **Translate** — capability maps turn canonical actions
   (`turn_on`, `set_input(arc)`) into native commands.
4. **Order** — power-before-input by convention; topology `ordering`
   edges layer in (HDMI-ARC handshake, upscaler warm-up, …).
5. **Execute** — fire each action through `DevicePort.execute_action`;
   gate on the capability's `poll_timeout_ms` (feedback devices) or
   `delay_ms` (no-feedback IR).

The full pipeline is in
**[Architecture: devices and scenarios](../architecture/devices-and-scenarios.md)**.

## After writing — verify

1. **Parse + load**: `pytest tests/unit/test_scenario_manager.py` runs the
   typed loader and the room-membership invariant against every scenario
   in `config/scenarios/`. A mismatch (device in a different room than
   `room_id`) fails the suite — don't push past it.
2. **Manifest projection**: `curl localhost:8000/scenario/movie_appletv/layout`
   returns the composite `LayoutManifest`. Every zone you wired in `roles`
   should be populated — the controls carry the canonical `(capability,
   action)` tuple they dispatch through the room's Scenario Manager entity
   (the bridge resolves the role to a device at fire time).
3. **Catalog projection**: `curl localhost:8000/system/catalog` lists the
   scenario under its room.
4. **Hardware activation**: `POST /scenario/start` (id in the body) — devices
   power up in the right order, inputs route correctly, manual steps
   surface in the response if the path crosses a manual node.
5. **Switch + deactivate**: from `movie_appletv` to `movie_zappiti`
   should diff cleanly (shared display + AVR stay on; only the source
   changes). `POST /scenario/shutdown` (id in the body) powers off the
   scenario's involved devices.

## Common pitfalls

- **Room mismatch.** If `room_id = "living_room"` but
  `mf_amplifier.room = "cabinet"` (typo or stale config), bootstrap
  hard-fails. Fix the device's `room` field or the scenario's `room_id` —
  don't drop the invariant.
- **Source device exposes no capability for the role you wired.**
  Reconciler logs a warning in the plan; the action's manifest zone
  renders empty. Audit the capability map (class / profile / device
  override).
- **No topology path between `source` and `display`.** `resolve_targets`
  returns an empty set; the reconciler does nothing. Check
  `config/topology.json` for the missing link.
- **Confusing static `manual_instructions` with runtime `manual_steps`.**
  Static notes go on the scenario config (always visible on the scenario
  page); runtime steps come from the topology's manual nodes (one-shot
  prompts during activation). The
  [UI doc](../architecture/ui.md) covers the distinction.

## Commit

One commit per scenario; commit body lists the room, the role
assignments, any topology links the scenario newly depends on (if you
extended `topology.json` to support it), and any manual_instructions
content.

## Where to go next

- **[Architecture: devices and scenarios](../architecture/devices-and-scenarios.md)**
  — the reconciler in detail.
- **[Architecture: key concepts](../architecture/key-concepts.md)** —
  topology + capabilities + scenario lifecycle.
- **[Architecture: rooms](../architecture/rooms.md)** — the `room_id`
  invariant and how scenarios scope to a room.
- **[How-to: add a device with an existing driver](howto-new-device.md)**
  and **[a new driver](howto-new-driver.md)** — the prerequisites if the
  devices in your scenario don't exist yet.
