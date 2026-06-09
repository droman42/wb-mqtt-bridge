# Roborock S7 vacuum cleaner — design doc

> **Status: DRAFT, WORK IN PROGRESS (started 2026-06-09).** Captures the
> discussion state with the user; open questions flagged inline. Not yet a
> committed plan — implementation gated on the user signing off on the open
> questions + adding §P3.7-style numbered tasks to `docs/action_plan.md`.
>
> See also: [[plan_status]] for where this fits in the broader roadmap
> (currently NOT yet listed as a numbered task; will be added when the design
> is locked).

## 1. Scope

The Roborock S7 is the first **interactive-map appliance** in the bridge.
Unlike the AV gear (state + remote layout) and the WB-passthrough lights/
covers/HVACs (state + commands), it adds three new concerns:

1. A **2D map of the apartment** that the UI must render + pan/zoom + overlay
   live robot position.
2. **User-defined named zones** (CRUD) that are voice-addressable and
   trigger zone-scoped cleaning runs.
3. **Voice-announced status events** (the strings the vacuum normally
   speaks) that must be translated for the voice bridge + drive UI display.

It's a fourth class of device alongside `device` (AV remote — Layer-3
manifest), `appliance` (bespoke page — kitchen hood, HVAC), and
WB-passthrough (config-driven). It will be modelled as `device_category:
appliance` and route to a bespoke React page (matches the existing
`KitchenHoodPage` / `HvacPanel` pattern in `ui/src/pages/appliances/`).

### v1 feature scope (this design)

| # | Feature | Source |
|---|---|---|
| F1 | Basic commands: start cleaning, pause, stop, return to dock, locate | User input 2026-06-09 |
| F2 | Live map view: pan/zoom + robot icon as a moving overlay | User input 2026-06-09 |
| F3 | Predefined named zones — CRUD, voice-addressable, zone-scoped cleaning, active-zone overlay in semi-transparent colour | User input 2026-06-09 |
| F4 | Status messages (the vacuum's voice announcements) — translated dictionary for voice bridge + UI display reacts to status | User input 2026-06-09 |

### Out of scope for v1

- **Scenario integration.** The vacuum stays `device_category: appliance` (out of
  reconciler scope, same as kitchen hood); a future "Cleaning Bedtime" scenario
  is a separate decision.
- **Consumables tracking + alerts** (brush life, filter life). The library
  exposes the data via the `consumables` trait — UI display only in v1, no
  alerting.
- **Scheduling.** Time-of-day cleaning schedules are out of scope; user can
  still trigger via voice.
- **Multi-floor map management** (`MapsTrait.set_current_map(flag)`).
  Single-floor for v1 — flag a multi-floor future iteration if you ever add
  a second vacuum.
- **Remote control mode** (`APP_RC_MOVE`, joystick-style live driving). The
  library supports it; we don't need it for v1.
- **Pet patrol / Easter eggs / camera modes** (the S7 doesn't have them
  anyway, but the library has command enum entries for higher-end models).

## 2. Library choice — `python-roborock`

[python-roborock](https://github.com/Python-roborock/python-roborock) (currently
v5.14.2 on PyPI, 2026-06-04). Module structure (relevant subset):

```
roborock/
├── web_api.py                  ← cloud-auth bootstrap (RoborockApiClient)
├── devices/
│   ├── device.py               ← Device façade (device.v1_properties.*)
│   ├── device_manager.py       ← create_device_manager / UserParams
│   ├── transport/
│   │   ├── local_channel.py    ← PURE TCP, port 58867 (we use this)
│   │   └── mqtt_channel.py     ← cloud-control path (we DO NOT use this)
│   └── traits/v1/              ← (status, command, maps, map_content,
│                                  rooms, consumables, clean_summary, …)
├── protocols/
│   ├── v1_protocol.py          ← S7 = V1 protocol
│   ├── a01_protocol.py         ← (wet/dry vacuums — skip)
│   └── b01_*_protocol.py       ← (Q-series — skip)
├── map/
│   └── map_parser.py           ← wraps PiotrMachowski's parser (server-side
│                                  render path; CLIENT-SIDE RENDER PREFERRED —
│                                  see §6)
└── data/code_mappings.py       ← RoborockStateCode, RoborockErrorCode,
                                  RoborockDockErrorCode, RoborockFanPower, …
```

### What we use vs skip

| Path | Use? | Notes |
|---|---|---|
| `web_api.RoborockApiClient` | **bootstrap only** | `request_code(email)` → `code_login(code)` → `user_data`. One-shot CLI to extract `local_key`s; never runs at bridge runtime. See §3. |
| `devices.transport.local_channel.LocalChannel` | YES | `LocalChannel(host, local_key, device_uid)` — TCP port 58867, fully offline once `local_key` is cached. |
| `devices.transport.mqtt_channel` + `roborock.mqtt.*` | NO | Cloud-control MQTT session manager. Forbidden via `import-linter` (see §10). |
| `devices.traits.v1.command` | YES | Single `send(RoborockCommand, params)` method; we wrap the 5-10 commands we care about. |
| `devices.traits.v1.status` | YES | Push-driven via `update_from_dps(decoded_dps)` over the LocalChannel; gives state code, battery, errors, fan_power, etc. |
| `devices.traits.v1.maps` + `map_content` + `rooms` | YES | Map metadata + raw blob + per-room metadata. |
| `devices.traits.v1.consumables` | YES (read-only display) | Brush/filter wear-life. Read into state, surface in UI. |
| `roborock.map.MapParser` | NO (preferred) | Server-side renderer wrapping PiotrMachowski + Pillow. **We render in the browser** instead — see §6 for the reasoning. |
| `vacuum_map_parser_roborock` + `vacuum_map_parser_base` + `Pillow` | TBD | Pulled in as transitive deps of `python-roborock`. **Open question (§13.1):** install with `--no-deps` and vendor only the binary-decoding bits, OR accept the ~10 MB Pillow tax and lazy-import the map module. |

## 3. Authentication & connection model

### One-time bootstrap (off-runtime)

The Roborock account is the same whether registered via the iOS app, the
web, or Xiaomi Home — there's only one cloud backend per email. The user's
wife registered through the iOS Roborock app; **no separate web account
needed**, the same email-and-code flow works.

**Bootstrap CLI** (new console script alongside `wb-openapi`,
`mqtt-sniffer`, etc.):

```bash
wb-roborock-auth --email her-roborock-account@example.com
# → "Code sent to email. Enter code: ______"
# → on success: writes user_data → config/devices/<vacuum_id>.json
#                                  (or to a separate secrets path; TBD §13.2)
```

Internally:

```python
api = RoborockApiClient(username=email)
await api.request_code()              # Roborock emails 6-digit code
user_data = await api.code_login(code)
# user_data carries: per-device local_key, device_uid, rriot tokens, LAN IPs
```

**Account-discovery hints for the user** (one-time only, when she runs the
CLI):
- The email is shown in iOS Roborock app → `Profile` tab → tap avatar/name.
- If she used "Sign in with Apple" + "Hide My Email", the email on file
  is a `@privaterelay.appleid.com` address — codes still forward to her
  real inbox; she just needs to enter the relay address as the email.
- If 2FA is enabled on the Roborock account, the email-code path may
  return an error; fallback = disable 2FA for the bootstrap, re-enable
  after.

### Runtime (every bridge start)

```python
channel = LocalChannel(
    host=cfg.host,               # e.g. "192.168.110.42" (DHCP reservation)
    local_key=cfg.local_key,     # 16-char string from user_data
    device_uid=cfg.device_uid,   # also from user_data
)
# Pure TCP socket. 10s keep-alive pings. Auto-reconnect on drop.
# Pulls status pushes via update_from_dps() — no polling.
```

**No cloud at runtime.** Same model as the existing pyatv credentials
pattern: extract once, cache in config, refresh if/when the library
reports the key is invalid (rare — typically only after a factory reset
or revoking the session in the app's device-list page).

## 4. Backend architecture

### 4.1 Driver

`backend/src/wb_mqtt_bridge/infrastructure/devices/roborock_vacuum/driver.py`:

```python
class RoborockVacuum(BaseDevice[RoborockVacuumState]):
    config: RoborockVacuumConfig

    async def setup(self) -> bool:
        # Open LocalChannel, register status push callback.
        # Discover current map_flag + room mapping.
        # Seed state from status.refresh() once.

    async def shutdown(self) -> bool:
        # Close LocalChannel cleanly.

    # Action handlers (one per command capability)
    async def handle_start(...)        # APP_START
    async def handle_pause(...)        # APP_PAUSE
    async def handle_stop(...)         # APP_STOP
    async def handle_return_to_dock(...)  # APP_CHARGE
    async def handle_locate(...)       # locate beeper
    async def handle_clean_zones(...)  # APP_ZONED_CLEAN with zone coords
    async def handle_clean_rooms(...)  # APP_SEGMENT_CLEAN with segment IDs

    # Status push (registered against status trait)
    def _on_status_push(self, dps: dict) -> None:
        # decode → update_state(state=..., battery=..., error_code=..., ...)
        # ALWAYS goes through update_state (chokepoint per
        # [[state-sync-chokepoint]] — never self.state.x = y at runtime).
```

### 4.2 State model

`backend/src/wb_mqtt_bridge/domain/devices/models.py`:

```python
class RoborockVacuumState(BaseDeviceState):
    # Translated to canonical via [[value-label-translation]]
    status: str               # canonical: "idle"/"cleaning"/"returning"/...
    error: Optional[str]      # canonical error name, None when ok
    dock_error: Optional[str]

    battery: int              # 0-100
    fan_power: str            # canonical: "quiet"/"balanced"/"turbo"/"max"
    water_box_mode: Optional[str]
    mop_mode: Optional[str]

    # Position / map state
    position: Optional[Dict[str, float]]  # {x, y, angle} in mm
    map_version: str          # short hash; UI re-fetches map on bump

    # Active job
    active_zone_ids: List[str]    # ids referencing RoborockVacuumConfig.zones
    active_segment_ids: List[int] # if launched via room-clean
    clean_time_seconds: int
    clean_area_mm2: int

    # Consumables (display-only, v1)
    main_brush_wear_pct: int
    side_brush_wear_pct: int
    filter_wear_pct: int

    reachable: bool           # mirrors LocalChannel connection health
```

### 4.3 Config model

`backend/src/wb_mqtt_bridge/infrastructure/config/models.py`:

```python
class RoborockZone(BaseModel):
    """One user-defined cleaning zone (Feature F3)."""
    id: str                       # canonical identifier ("kitchen", "office")
    names: LocalizedName          # ru/en/de — voice + UI labels
    # Rectangle in vacuum map mm-space (NOT pixel-space — survives map rescale)
    rect_mm: Tuple[int, int, int, int]   # (x1, y1, x2, y2)
    repeats: int = 1              # APP_ZONED_CLEAN cleans N times


class RoborockVacuumConfig(BaseDeviceConfig):
    # Connection (from bootstrap CLI)
    host: str
    local_key: str
    device_uid: str

    # Optional: pin a specific map_flag (for multi-floor; None = use current)
    map_flag: Optional[int] = None

    # User-defined zones
    zones: List[RoborockZone] = Field(default_factory=list)
```

Cloud `user_data` (rriot tokens etc.) is NOT stored in the device config —
the bootstrap CLI writes it to a separate secrets path that the bridge
never reads at runtime (only needed for re-bootstrap). **TBD §13.2** —
exact secrets-path convention.

### 4.4 Capability profile

`backend/config/capabilities/profiles/vacuum_cleaner.json`:

```jsonc
{
  "cleaning": {
    "kind": "stateful", "feedback": true, "state_field": "status",
    "actions": {
      "start":   {"command": "start"},
      "pause":   {"command": "pause"},
      "stop":    {"command": "stop"},
      "dock":    {"command": "return_to_dock"},
      "locate":  {"command": "locate"},
      "clean_zones": {"command": "clean_zones",
                      "param_map": {"zone_ids": "zone_ids"}},
      "clean_rooms": {"command": "clean_rooms",
                      "param_map": {"room_ids": "room_ids"}}
    },
    "fields": [
      // §P3.7 #26 value-label triplet — wire from RoborockStateCode,
      // canonical short identifiers, ru/en/de labels for voice + UI.
      {"name": "status", "type": "enum",
       "labels": {"ru": "статус", "en": "status", "de": "Status"},
       "values": [
         {"wire": "1",  "canonical": "starting",  "labels": {...}},
         {"wire": "2",  "canonical": "charger_disconnected", "labels": {...}},
         {"wire": "3",  "canonical": "idle",      "labels": {"ru": "ожидание",      "en": "idle",       "de": "bereit"}},
         {"wire": "5",  "canonical": "cleaning",  "labels": {"ru": "уборка",        "en": "cleaning",   "de": "reinigt"}},
         {"wire": "6",  "canonical": "returning", "labels": {"ru": "возвращается",  "en": "returning",  "de": "kehrt zurück"}},
         {"wire": "8",  "canonical": "charging",  "labels": {"ru": "заряжается",    "en": "charging",   "de": "lädt"}},
         {"wire": "10", "canonical": "paused",    "labels": {"ru": "пауза",         "en": "paused",     "de": "pausiert"}},
         {"wire": "11", "canonical": "spot_cleaning", "labels": {...}},
         {"wire": "12", "canonical": "error",     "labels": {"ru": "ошибка",        "en": "error",      "de": "Fehler"}},
         {"wire": "15", "canonical": "docking",   "labels": {...}},
         {"wire": "16", "canonical": "going_to_target", "labels": {...}},
         {"wire": "17", "canonical": "zone_cleaning", "labels": {...}},
         {"wire": "18", "canonical": "segment_cleaning", "labels": {...}}
         // …complete table when we pull RoborockStateCode at impl time
       ]},
      {"name": "error", "type": "enum", "values": [...]},     // RoborockErrorCode
      {"name": "dock_error", "type": "enum", "values": [...]},// RoborockDockErrorCode
      {"name": "battery", "type": "int", "unit": "%"},
      {"name": "fan_power", "type": "enum", "values": [
         {"wire": "101", "canonical": "quiet",    "labels": {...}},
         {"wire": "102", "canonical": "balanced", "labels": {...}},
         {"wire": "103", "canonical": "turbo",    "labels": {...}},
         {"wire": "104", "canonical": "max",      "labels": {...}},
         {"wire": "105", "canonical": "off",      "labels": {...}}
       ]}
      // consumables fields TBD §13.3 (separate `maintenance` capability?)
    ]
  }
}
```

This **uses the §P3.7 #26 value-label translation layer end-to-end**
([[value-label-translation]]) — voice (Irene) reads the table from
`/system/catalog` and announces "Робот возвращается на базу" without any
new dispatch mechanism. Same shape as the HVAC mode/fan/vane/widevane
values we just shipped.

### 4.5 REST surface (new endpoints)

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/devices/{id}/map` | Returns `{ blob_b64: str, map_version: str, robot: {x,y,angle}, charger: {x,y}, rooms: [{id, name, segment_id}], no_go: [...], virtual_walls: [...] }`. Blob is the raw Roborock binary; UI parses + renders client-side. `map_version` is a short hash so the UI knows when to re-fetch the blob. |
| `GET/POST/PUT/DELETE` | `/devices/{id}/zones` + `/devices/{id}/zones/{zone_id}` | Zone CRUD. Writes update `RoborockVacuumConfig.zones` on disk (config-file mutation, same pattern as scenario edits — TBD §13.4 confirm the write-path is acceptable here). Triggers catalog version bump. |
| `POST` | `/devices/{id}/canonical {capability: "cleaning", action: ...}` | Existing endpoint — used for all commands (start/stop/dock/clean_zones/etc.). |

Also: catalog projects the `vacuum_cleaner` capability, including zone
labels (zones flow through the same `LocalizedName` → catalog locale
projection that rooms use). Voice asks "пропылесось кухню" → Irene matches
"кухня" against the zone's `labels.ru`, posts
`{capability: "cleaning", action: "clean_zones", params: {zone_ids:
["kitchen"]}}`, driver resolves to `APP_ZONED_CLEAN([rect_mm])`.

### 4.6 Hexagonal layering ([[hexagonal-law-for-all-changes]])

- `domain/devices/models.py::RoborockVacuumState` — pure data.
- `domain/devices/config.py::RoborockZone` — pure data (LocalizedName
  imported from same module, like ValueLabel).
- `infrastructure/devices/roborock_vacuum/driver.py` — imports python-
  roborock, holds the LocalChannel, owns the connection lifecycle.
- `infrastructure/config/models.py::RoborockVacuumConfig` — re-exports
  `RoborockZone` from domain.
- `presentation/api/routers/` — new `GET /devices/{id}/map` and
  `/zones` routes; both reach into the driver via `DeviceManager.get(id)`
  → typed driver instance (same pattern as the existing device endpoints).
- No new cross-layer edges. The `wb-roborock-auth` CLI lives in `cli/` and
  is the ONLY place allowed to import `roborock.web_api` —
  import-linter enforces (§10).

## 5. Status messages + voice integration (Feature F4)

Mapping:

| Source | Data | Sink |
|---|---|---|
| `StatusTrait.update_from_dps(decoded_dps)` push | int `state` code | Driver translates wire→canonical via the state-topic spec, stores `state.status = "returning"` via `update_state(...)`. |
| `state.status` field | canonical string | (a) Catalog/`/devices/{id}/state` → UI reads + reacts visually (e.g. "returning to dock" shows a dock-bound robot icon path, "error" shows red banner with the localised error label); (b) [[state-sync-chokepoint]] persists to `state.db` + fires SSE. |
| Catalog field's value table | canonical + ru/en/de labels | Voice (Irene) on status-change SSE: looks up the canonical in the catalog's value table, picks the locale label, announces. |
| `error` + `dock_error` fields | same triplet shape | "Bin full" / "stuck" / "no water" pronouncements localised the same way. |

**No new voice-bridge code needed** — the catalog autodiscovery + value-label
translation pattern shipped in §P3.7 #26 already covers this. Roborock is
exactly the kind of device the pattern was designed for (enum-encoded
state with multi-locale announcements).

UI display reactions per status (sketch):

| `status` canonical | UI reaction |
|---|---|
| `idle` / `charging` | Robot icon stationary at dock position; map fully visible. |
| `cleaning` / `zone_cleaning` / `segment_cleaning` | Robot icon updates ~1/s from position pushes; active-zone overlay rendered semi-transparent if `active_zone_ids` non-empty. |
| `returning` / `docking` | Robot icon shows directional bias toward charger position; "returning to dock" banner. |
| `paused` | Robot icon dimmed, "Paused" banner with Resume button. |
| `error` | Red banner with localised error label + retry/dismiss; robot icon stops updating. |

## 6. Map handling — **client-side rendering (primary)**

### 6.1 Rationale

The server-side render path (`roborock.map.MapParser` → `Pillow` →
`ParsedMapData(image_content: PNG bytes)`) is the obvious approach but
adds:
- `Pillow` + libjpeg/libpng/libtiff/libwebp/freetype on arm/v7 (~5-10 MB
  container + significant build time).
- Server-side CPU on every map refresh.
- Bandwidth: full PNG re-sent on every map version bump, even if only
  the robot moved.

**Browser-side rendering** is strictly better here:
- We ship the raw Roborock binary blob + structured non-pixel data (robot,
  rooms, no-go, walls, charger).
- UI parses + renders to canvas/SVG once per map-version bump.
- Live robot icon = absolutely-positioned overlay div with `transform:
  translate(x, y) rotate(angle)`, updated from SSE — no map re-render.
- Zoom/pan = CSS transform on the canvas container, no server round-trip.
- Saves Pillow + map parsers from the bridge container (~10 MB) and
  offloads pixel work to the device showing the pixels.

The HA `lovelace-xiaomi-vacuum-map-card` (same author as
`vacuum-map-parser-roborock`) does exactly this in TypeScript; we can
either port the relevant decoder pieces (MIT-licensed) or write our own
against the documented binary layout.

### 6.2 Map blob fetch cadence

- Initial fetch on driver setup.
- Re-fetch on status transitions that imply topology change: completed
  cleaning runs, manual "rebuild map" command, anything that bumps the
  Roborock-side `map_flag` revision.
- The driver computes a short hash of the blob → `state.map_version`.
  UI subscribes to state via SSE → on `map_version` change, fetches
  `/devices/{id}/map` and replaces the canvas.
- Manual "Refresh map" button in the UI for the rare edge case.

### 6.3 Open question — where does the binary parser live?

**TBD §13.5.** Two options:
- **A. UI ships its own TypeScript parser.** Maximum browser self-
  sufficiency; the bridge just proxies bytes. ~600-1000 LOC of new TS.
- **B. Bridge parses to structured data, ships parsed dict + raw bytes.**
  Saves the TS implementation but pulls in the binary-decoding side of
  `vacuum-map-parser-roborock` (skip the Pillow rendering pieces).
  Smaller container delta (~2-3 MB) than full Pillow.

Recommend Option A for full alignment with "render in the browser"
principle; revisit if TS implementation cost becomes prohibitive.

## 7. Zone management (Feature F3)

### 7.1 Storage

`RoborockVacuumConfig.zones: List[RoborockZone]` — persisted in the device
config JSON (`backend/config/devices/<vacuum_id>.json`). Same pattern as
existing config-side data (commands, state_topics, etc.).

Each zone:
- `id: str` — canonical identifier, voice-safe (`kitchen`, `office`).
- `names: LocalizedName` — `{ru, en, de}`. Voice matches user utterances
  against these via the catalog (same path as room names — [[plan_status]]
  §P3.7 §A1).
- `rect_mm: (x1, y1, x2, y2)` — coordinates in vacuum map mm-space.
  Stored in mm (not pixels) so a future map rescale doesn't invalidate
  zones. Origin = vacuum's own map origin.
- `repeats: int = 1` — `APP_ZONED_CLEAN`'s `count` parameter (how many
  times to clean the zone before moving on).

### 7.2 CRUD endpoints

| Method | Path | Body | Effect |
|---|---|---|---|
| `GET` | `/devices/{id}/zones` | — | Returns `List[RoborockZone]`. |
| `POST` | `/devices/{id}/zones` | `RoborockZone` (sans server-assigned fields) | Append. Persists to disk. Bumps catalog version. |
| `PUT` | `/devices/{id}/zones/{zone_id}` | `RoborockZone` | Replace. Persists + version bump. |
| `DELETE` | `/devices/{id}/zones/{zone_id}` | — | Remove. Persists + version bump. |

**Writes to a config file at runtime** — TBD §13.4 whether this needs a
new pattern (we don't write configs at runtime today except `state.db`).
Two options:
- **A. Mutate the device config JSON in place.** Atomic write (tmp + rename),
  reload via existing `/reload` mechanism. Risks: edits made while a
  scenario is loading could race.
- **B. Separate `zones.json` per device.** Smaller blast radius; never
  touches the canonical device config; loaded alongside it.

Recommend B for cleaner separation; revisit if it adds cognitive load.

### 7.3 Active-zone overlay

When a `cleaning.clean_zones` action lands, driver records
`state.active_zone_ids = [...]`. UI reads from state, draws each named
zone's `rect_mm` on the canvas as a semi-transparent fill (e.g. cyan @
30% opacity). Cleared when `status` transitions to `idle`/`charging`/
`returning`.

### 7.4 Voice flow

User: "пропылесось кухню"
Irene:
  1. Looks up `kitchen` in catalog → matches `zone.labels.ru = "кухня"`.
  2. Resolves to `POST /devices/livingroom_vacuum/canonical {capability:
     "cleaning", action: "clean_zones", params: {zone_ids: ["kitchen"]}}`.
Bridge driver:
  3. Resolves `zone_ids` → `cfg.zones[id=kitchen].rect_mm` → builds
     `APP_ZONED_CLEAN` params: `[[x1, y1, x2, y2, repeats]]`.
  4. Sends via LocalChannel; records `state.active_zone_ids = ["kitchen"]`.
UI:
  5. SSE delivers state update → overlay kitchen rect on map.
Voice:
  6. SSE delivers `state.status = "zone_cleaning"` → Irene announces
     "Начинаю уборку кухни" using the status value-label table.

## 8. UI architecture

### 8.1 Page registration

```ts
// ui/src/pages/appliances/index.ts (existing registry)
const APPLIANCE_PAGES: Record<string, ComponentType> = {
  kitchen_hood: KitchenHoodPage,
  bedroom_hvac: HvacPanel,
  living_room_hvac: HvacPanel,
  children_room_hvac: HvacPanel,
  // §P3.7 #26 / Roborock
  livingroom_vacuum: RoborockPage,  // single generic component, one entry
};
```

If multiple vacuums exist (future), all get the same `RoborockPage`
component (it reads `device_id` from the React-router param, exactly like
`HvacPanel`).

### 8.2 RoborockPage layout (sketch)

```
┌────────────────────────────────────────────────────────────┐
│ Header: device name + room + connection status            │
├────────────────────────────────────────────────────────────┤
│ Status banner (current localised status + battery %)      │
├────────────────────────────────────────────────────────────┤
│                                                            │
│              [interactive map canvas]                      │
│                  pan / zoom                                │
│           robot icon overlay (live position)               │
│         zone overlays (named + active highlight)           │
│                                                            │
├────────────────────────────────────────────────────────────┤
│ Action buttons:                                            │
│ [Start] [Pause] [Stop] [Return to dock] [Locate]          │
│ Fan power selector: [Quiet][Balanced][Turbo][Max]         │
├────────────────────────────────────────────────────────────┤
│ Zones (collapsible)                                        │
│ ▸ Kitchen   [▶ Clean]  [Edit]  [Delete]                   │
│ ▸ Office    [▶ Clean]  [Edit]  [Delete]                   │
│ [+ Add zone] (click-drag rectangle on the map above)       │
├────────────────────────────────────────────────────────────┤
│ Consumables (collapsible, read-only display, v1)          │
│ Main brush: 75%  Side brush: 60%  Filter: 40%             │
└────────────────────────────────────────────────────────────┘
```

### 8.3 New TypeScript pieces

- `ui/src/pages/appliances/RoborockPage.tsx` (~300-500 LOC).
- `ui/src/lib/roborockMapParser.ts` (binary blob → structured data;
  ~600-1000 LOC if we write it ourselves, less if we port from the
  Lovelace card).
- `ui/src/components/RoborockMapCanvas.tsx` (~200 LOC; canvas + pan/zoom +
  overlay layers).
- Zustand store slice for vacuum state (or just useDeviceState + local
  React state — TBD).

### 8.4 Hooks (new in `useApi.ts`)

```ts
useVacuumMap(deviceId)          // GET /devices/{id}/map, staleTime
                                // gated on state.map_version
useVacuumZones(deviceId)        // GET /devices/{id}/zones
useCreateVacuumZone(deviceId)   // POST mutation
useUpdateVacuumZone(deviceId)   // PUT mutation
useDeleteVacuumZone(deviceId)   // DELETE mutation
```

`useExecuteCanonicalAction` (already exists from §P3.7 #26 Phase 3) is
re-used for start/pause/stop/dock/clean_zones/etc.

## 9. Container footprint

Net new dependencies installed:

| Pkg | Size (arm/v7) | Notes |
|---|---|---|
| `python-roborock` | ~1-2 MB | Main library. |
| `pycryptodome` | ~1.5 MB | Local protocol encryption. |
| `protobuf` | ~1.5 MB | Wire format. |
| `construct` | ~500 KB | Binary structure parsing. |
| `pyrate-limiter` + `click-shell` | <500 KB | Library deps; library may import even for non-CLI use. |
| `vacuum-map-parser-roborock` + `base` | <500 KB | **Skipped if client-side parsing only.** |
| `Pillow` + system libs | 5-10 MB | **Skipped if client-side rendering only.** |
| `paho-mqtt` + `aiomqtt` | 0 (already in bridge) | |
| `aiohttp` | 0 (already in bridge) | |

**Best case (client-side parse + render, `python-roborock --no-deps` for
the map pieces):** ~5 MB added.
**Worst case (server-side render, accept full deps):** ~15 MB added.

WB7 has 8 GB eMMC + 1 GB RAM. Both options fit comfortably.

## 10. Layering + new contract entries

- New `import-linter` contract: `roborock.mqtt.*` and `roborock.web_api`
  are forbidden everywhere except `wb_mqtt_bridge.cli.roborock_auth`
  (the bootstrap CLI). Codified per [[hexagonal-law-for-all-changes]]
  workflow.
- `domain/` import-purity: `RoborockVacuumState` + `RoborockZone` are
  pure data; no python-roborock import in `domain/`.
- New REST endpoints in `presentation/api/routers/` follow the
  documented presentation→infra access pattern (via `DeviceManager`).
- `openapi.json` regenerated with the new endpoints + `RoborockVacuumState`
  in the discriminated union.
- UI `npm run gen:api-types` regenerates `openapi.gen.ts`.

## 11. Implementation phases (rough, to be refined when adding to action_plan)

| Phase | Surface | Output |
|---|---|---|
| 0 | Bootstrap CLI (`wb-roborock-auth`) + secrets-path convention | Working extraction of `user_data` from a real Roborock account; commit a sanitized fixture for tests. |
| 1 | Driver skeleton + connection + status push + commands (F1) | `RoborockVacuum` driver, capability profile, state model, basic commands flow end-to-end. Mock-tested. |
| 2 | Status value-label tables + voice integration (F4) | RoborockStateCode/ErrorCode tables authored into the profile with ru/en/de labels. Catalog projects them. Voice reads + announces (post-Irene-on-controller — won't HW-verify till then). |
| 3 | Map blob endpoint + TypeScript parser + canvas renderer (F2) | `GET /devices/{id}/map`, browser-side parse + render, live robot overlay via SSE. |
| 4 | Zone CRUD + UI editor + voice (F3) | Endpoints + persistence, zone definition UI (click-drag on map), active-zone overlay, voice-addressable zones. |
| 5 | HW verification at the rack | End-to-end: voice → command → wire publish → device acts → status echo → UI updates. |

**Total estimate (no HW):** ~5-7 dev days backend + ~3-5 dev days UI.
Voice integration HW pass deferred behind Irene on-controller.

## 12. Hexagonal LAW pre-commit checklist (template for each phase)

- [ ] `grep -RnE "from wb_mqtt_bridge\.(infrastructure|presentation)" backend/src/wb_mqtt_bridge/domain/` returns zero
- [ ] `grep -RnE "from wb_mqtt_bridge\.presentation" backend/src/wb_mqtt_bridge/infrastructure/` returns zero
- [ ] `grep -RnE "from roborock\.(mqtt|web_api)" backend/src/wb_mqtt_bridge/` returns only `cli/roborock_auth.py`
- [ ] `lint-imports` clean (3 contracts kept + the new roborock.* contract)
- [ ] `pyright` clean
- [ ] `check-no-type-checking src/wb_mqtt_bridge` clean
- [ ] No `self.state.X = Y` outside `__init__` (per [[state-sync-chokepoint]] static guard)
- [ ] Suite passes; new tests added per [[device_test_pattern]]

## 13. Open questions — please respond before locking the design

1. **Map decoder location (§6.3).** Browser-side TypeScript parser (full
   "render in the browser" alignment, ~600-1000 LOC of new TS) vs bridge-
   side parse-but-not-render (smaller TS, ~2-3 MB extra container)?
   **Recommendation: browser-side.**
2. **Bootstrap secrets path.** Where does the `user_data` blob from the
   bootstrap CLI go? Options: (a) inside the device config JSON
   (simple, but mixes data + secrets); (b) separate `backend/.secrets/
   roborock_<device_id>.json` gitignored (cleanest, but new convention);
   (c) env vars (hostile for multi-line JSON).
   **Recommendation: (b) — separate gitignored file.**
3. **Consumables surfacing.** Read-only display only (v1) vs full
   "schedule reminder when filter > 80% worn" capability with
   notification surface (v2+)? **Recommendation: read-only display in
   v1, defer alerting.**
4. **Zone-storage write path (§7.2).** Mutate device config JSON in place
   vs separate `zones.json` per vacuum? **Recommendation: separate
   `zones.json`.**
5. **§5.1 backlog `force` flag interaction.** Vacuum has idempotence
   guards (e.g. "already docked, skipping" makes sense). Should it
   participate in the same `force` flag mechanism as Wirenboard IR
   power? **Recommendation: yes, mark guarded handlers `force`-eligible
   when we author them; same shape as Wirenboard IR.**
6. **Persisted-state restore.** Always pull live from the device on
   start, vs seed from `state.db` and reconcile? Vacuum state changes
   fast (battery, position). **Recommendation: ignore `state.db` seed
   for fast-changing fields, always pull live; persist only for the
   `RoborockZone` list which is config-shaped.**
7. **Scenario integration scope.** Confirmed out-of-scope for v1
   (vacuum stays appliance). Want to revisit later for "Cleaning Bedtime
   → run vacuum in zones A+B"? **Recommendation: file as a future-
   consideration after v1 ships + has HW verification.**
8. **Single vacuum vs multiple architecture decisions.** Today: one
   S7 in living room. Design assumes generic + multi-capable from the
   start (Roborock has multiple unit families with shared V1 protocol).
   No additional decisions needed unless a second unit is imminent.
9. **What's the device's `room` value?** Vacuums roam — they're not
   "in" a single room the way a TV is. Options: (a) `room: null` (like
   un-onboarded AV gear); (b) `room: global` (whole-house aggregate
   pattern from §P3.7 #22); (c) `room: <where the dock is>`.
   **Recommendation: (c) — physically the dock lives in a room, semantically
   "the vacuum belongs to the living room" matches user intent.**

## 14. References

### External

- [python-roborock library](https://github.com/Python-roborock/python-roborock)
  — main driver-side library (v5.14.2 as of 2026-06-09).
- [vacuum-map-parser-roborock](https://github.com/PiotrMachowski/Python-package-vacuum-map-parser-roborock)
  — map blob parser + Pillow renderer (PiotrMachowski; MIT).
- [lovelace-xiaomi-vacuum-map-card](https://github.com/PiotrMachowski/lovelace-xiaomi-vacuum-map-card)
  — TypeScript map renderer (same author; client-side reference for
  Phase 3).
- [python-roborock readthedocs](https://python-roborock.readthedocs.io/en/latest/)
  — API reference (incomplete; library source-of-truth is GitHub).

### Internal

- [[hexagonal-law-for-all-changes]] — verify imports before every commit.
- [[state-sync-chokepoint]] — `BaseDevice.update_state` is the single
  chokepoint; never `self.state.x = y` at runtime.
- [[value-label-translation]] — wire/canonical/labels triplet pattern;
  status codes + fan_power use it.
- [[device_test_pattern]] — recipe for the driver test file.
- [[plan_status]] — where this fits in the broader roadmap.
- `docs/design/ui/appliances.md` — historical appliance-page architecture
  design (since superseded — the registry IS built, KitchenHoodPage +
  HvacPanel route through it).
- `docs/action_plan.md` §P3.7 — voice integration + value-label
  translation work this design plugs into.

---

**Next session pickup:**
1. User reviews + responds to the §13 open questions.
2. Pull verbatim `RoborockStateCode` + `RoborockErrorCode` +
   `RoborockDockErrorCode` tables from `python-roborock/roborock/data/
   code_mappings.py`; finish authoring the value-label tables with
   trilingual labels.
3. Lock the design; add §P3.7-style numbered tasks to
   `docs/action_plan.md` for Phases 0-5.
4. Start with Phase 0 (bootstrap CLI) — has no behavioural risk + lets
   the user run it at her convenience to extract the local_key from her
   wife's Roborock account.
