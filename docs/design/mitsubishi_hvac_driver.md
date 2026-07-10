# MitsubishiHvac — a dedicated driver for the mitsubishi2wb HVAC modules (DRV-27 design)

**Status: DESIGN AGREED 2026-07-10, rev. 2 (first cut reviewed and revised the same day — the
single-`climate` capability and the derive-topics-from-one-field config were both rejected in
review; this revision records the agreed shape).** Implementation = **DRV-28**; enum-value icons =
**UI-16** (separate). Successor to the generic-passthrough treatment of the three HVACs; the
VWB-11-anticipated migration — renamed, since the modules are **ESP8266 (Wemos D1 Mini)** and the
contract is the *firmware's*, not a chip's.

## 1. Why a dedicated driver

The 2026-07-09 retained-wipe incident (journal) exposed the mismatch: HVACs are commanded-state
equipment with a real protocol vocabulary, modeled as dumb passthrough mirrors. What the generic
driver cannot provide:

- **Restore-at-boot** — passthrough's dynamic fields deliberately don't restore (DRV-25), so a
  broker wipe leaves the bridge blind until each value changes on the device.
- **Offline detection** — the firmware has no LWT and no per-control `meta/error`.
- A home for the firmware-specific vocabulary and semantics (the BroadlinkKitchenHood precedent:
  bespoke drivers encode one device family's contract).

Constraints honored: **mosquitto persistence stays OFF** (user decision, WB community advice);
**the firmware stays untouched for now** (the REST rewrite is separate research, bench-twin-gated
— §8).

## 2. The firmware contract (source of truth: `mitsubishi2wb.ino`)

Verified 2026-07-09 in `hpSettingsChanged()` / `mqttCallback()` / `mqttConnect()`:

- **Topics**: `/devices/N/controls/{power,mode,fan,vane,widevane,temperature,room_temperature}`
  (values, retained, published **on change only**) and `…/{control}/on` (commands; no
  `room_temperature/on`). `N` = the firmware's WB device name (`hvac_children`, …).
- **Wire vocabulary**: numeric index strings (the DRV-26 tables): mode 0=auto…4=fan_only; fan
  0=auto 1=quiet 2..5=speed_1..4; vane 0=auto 1=swing 2..6=pos_1..5; widevane 0=swing
  1..5=far_left..far_right 6=split; power `1`/`0`; temperatures floats.
- **Commands**: exact numeric strings only; anything else **silently ignored** (`else return`).
- **On MQTT reconnect**: `meta` only — values are never republished (the wipe fragility).
- **`room_temperature` publishes every 45 s unconditionally** — the only periodic signal: **a
  heartbeat**.
- No LWT, no `meta/error`.

## 3. Decisions (all user-pinned)

### D1 — Naming: `MitsubishiHvac`

`MitsubishiHvac` / `MitsubishiHvacConfig` / `MitsubishiHvacState`; capability map at
`config/capabilities/classes/MitsubishiHvac.json`. The driver docstring records that the actual
contract is the mitsubishi2wb firmware dialect (§2).

### D2 — Capability map: SIX per-domain capabilities (rev. 2 — replaces the single `climate`)

The AV shape (LgTv / kitchen hood / eMotiva): one capability per controllable domain, each owning
its actions, `state_field`, and readable fields. 1:1 with the firmware's controls:

| capability | actions | state_field | fields |
|---|---|---|---|
| `power` | `on`, `off` | `power` | `power` |
| `mode` | `set` | `mode` | `mode` (enum, 0..4 table) |
| `fan` | `set` | `fan` | `fan` (enum, 0..5 table) |
| `vane` | `set` | `vane` | `vane` (enum, 0..6 table) |
| `widevane` | `set` | `widevane` | `widevane` (enum, 0..6 table) |
| `temperature` | `set` | `setpoint` | `setpoint` (float, °C), `room_temperature` (float, °C, readonly) |

All: `kind: stateful`, `feedback: true`, `reconcile: false` (explicit — scenarios don't own HVAC;
the model default is true). The map lives in `classes/MitsubishiHvac.json`; **`profiles/hvac.json`
dies** (no other users — `heating_loop`, the floors' profile, keeps its own `climate` capability
and is untouched).

**Canonical param convention: `{value}`** on every enum `set` — one shape for "set an enum from a
closed table", matching the VWB-19 select-form convention (`input.set {value}`):
`mode.set {value: "cool"}` → `param_map {value: mode}` → native `set_mode`. `temperature.set`
keeps a float param (`{value: 22.5}` → `param_map {value: temp}`).

**Consequence, owned deliberately:** the canonical vocabulary changes (`climate.on` → `power.on`,
`climate.set_mode {mode}` → `mode.set {value}`, …). The golden changes (riding this arc's single
re-pin) and **`HvacPanel.tsx` is reworked** in DRV-28 (it dispatches `climate.*` today). Kitchen
hood already owns the `fan` domain with an int param — coexists fine; params are per-device
catalog surface.

### D3 — Wire tables live in the class map ONLY

The driver translates via its **attached capability map** (`fields[].values`, the shared
`ValueLabel` machinery — DRV-26-corrected values). No code constants, no per-config duplication;
the catalog carries the tables for free. Ordering note for DRV-28: `attach_capability_maps` runs
before MQTT echoes arrive — verify and pin with a test.

### D4 — Device configs: explicit MQTT topics per action, at `config/devices/` root (rev. 2)

The 3 configs **move out of `wb-devices/`** (that folder is the passthrough fleet; bespoke devices
live at the root beside `kitchen_hood.json`, `emotiva_xmc2.json`). Shape = **today's proven
schema** — explicit topics per action, hot-fixable, nothing derived:

```json
{ "device_id": "children_room_hvac",
  "names": { "ru": "Кондиционер", "en": "Air Conditioner", "de": "Klimaanlage" },
  "room": "children_room", "device_category": "appliance",
  "device_class": "MitsubishiHvac", "config_class": "MitsubishiHvacConfig",
  "commands": {
    "power_on":     { "topic": "/devices/hvac_children/controls/power/on", "value": "1" },
    "power_off":    { "topic": "/devices/hvac_children/controls/power/on", "value": "0" },
    "set_mode":     { "topic": "/devices/hvac_children/controls/mode/on",     "params": [ … ] },
    "set_fan":      { "topic": "/devices/hvac_children/controls/fan/on",      "params": [ … ] },
    "set_vane":     { "topic": "/devices/hvac_children/controls/vane/on",     "params": [ … ] },
    "set_widevane": { "topic": "/devices/hvac_children/controls/widevane/on", "params": [ … ] },
    "set_setpoint": { "topic": "/devices/hvac_children/controls/temperature/on", "params": [ … ] }
  },
  "state_topics": {
    "power": "/devices/hvac_children/controls/power",
    "mode": "/devices/hvac_children/controls/mode",
    "fan": "/devices/hvac_children/controls/fan",
    "vane": "/devices/hvac_children/controls/vane",
    "widevane": "/devices/hvac_children/controls/widevane",
    "setpoint": "/devices/hvac_children/controls/temperature",
    "room_temperature": "/devices/hvac_children/controls/room_temperature"
  } }
```

`state_topics` are **bare** (D3: types + value tables come from the class map via the existing
DRV-25 loader enrichment, which works for class maps exactly as for profiles). The driver
**validates completeness at load** — the full expected command + state-field set must be present;
a gap is a loud config error, not silent degradation. Note the field rename `temperature` →
`setpoint` (the state field follows the capability model; the MQTT topic keeps the firmware's
`temperature` name).

### D5 — Typed state, restore-at-boot, heartbeat reachability

`MitsubishiHvacState(BaseDeviceState)`: `mode/fan/vane/widevane: Optional[str]` (canonical),
`setpoint: Optional[float]`, `room_temperature: Optional[float]`, `reachable: bool = True`; the
base `power` field carries `"on"`/`"off"`. Declared fields ride the existing **VWB-18
restore-at-boot** — after a reboot + broker wipe the bridge (and voice, and the UI) still knows
the last commanded state; live retained echoes overwrite the snapshot at setup as usual.

**Reachability = the heartbeat**: a watchdog flips `reachable = False` when no `room_temperature`
arrives for ~3 intervals (≈ 2.5 min), back on any message. The first honest offline detection
these units have ever had. All state writes ride the `update_state` chokepoint.

### D6 — Command path

Canonical `power.on/off`, `{mode,fan,vane,widevane,temperature}.set {value}` expand (VWB-17) to
the native commands; the driver translates canonical → numeric wire via the class map and
publishes to the config's explicit command topic (non-retained). Idempotence: desired vs the typed
state field, via the standard **`idempotence_skip`** chokepoint honoring the reserved
`force`/`assume_state` params (the DRV-5 AV pattern). Echo-wait semantics unchanged (`no_op`
short-circuits; the firmware echoes value topics on real change).

### D7 — No bridge-owned WB card

The WB UI keeps the firmware's own raw card ("fine like it is"); humans use the bridge UI + voice.
The bridge never publishes into another device's topic namespace.

### D8 — Enum-value icons = the AV mechanism → UI-16

AV button icons resolve UI-side by name via the renderer's `IconResolver` (the manifest
`ActionIcon` is a placeholder hint — `ui_backend_contract.md` "Icons"). UI-16 extends the resolver
to canonical enum values and replaces `HvacPanel`'s hardcoded glyphs. No contract change.

## 4. What changes / what doesn't

- **Changes**: canonical HVAC vocabulary (six capabilities), the golden, `HvacPanel.tsx`
  (capability-per-field dispatch), 3 config files (moved + reshaped), `profiles/hvac.json` deleted.
- **Unchanged**: the DRV-25 passthrough machinery (serves heating_loop/covers/dimmers/sensors);
  `heating_loop`'s `climate`; MQTT as the only transport (v1); rooms.json (device ids unchanged);
  HvacPanel routing (`device_id`-keyed).

## 5. Contract impact

`device_class`, capability names, and action/param shapes are catalog surface → **golden bumps**
(supersedes `a4a2b1aed5f86447`). **The voice side re-pins ONCE, after DRV-28 lands** (covers
DRV-25 + DRV-26 + DRV-28; the interim hashes were never pinned). Check at implementation whether
`MitsubishiHvacState` joins an explicit persisted-state union in openapi.

## 6. Migration & rollout

DRV-28 changes backend code → backend image rebuild + WB7 redeploy (`git pull` + `update.sh`; new
image → containers recreate). The persisted passthrough snapshots for the 3 device_ids degrade
gracefully on the class swap (`restore_state` applies declared fields only, VWB-18); first boot
re-seeds from retained topics + the heartbeat.

## 7. Tests (DRV-28, per the device-test recipe)

Real driver + real class map + real device config + mocked MQTT: config-load validation (missing
command/state field = loud error); inbound wire → canonical typed state (`mode '2'` → `'cool'`,
floats, the `setpoint` rename); outbound canonical → numeric wire (`mode.set {value: cool}` →
`'2'` on `…/mode/on`); idempotence + `force`/`assume_state`; heartbeat watchdog (flips on silence,
recovers on message); restore-at-boot round trip (declared fields restore; live retained wins);
catalog projection (six capabilities, tables from the class map, params advertise `{value}`);
attach-before-echo ordering pinned; the 3 migrated configs parse; `profiles/hvac.json` gone with
zero references.

## 8. Horizon (recorded, not scoped)

The REST-endpoints firmware rewrite (commands via `POST /api/control`, `GET /api/status` at boot
instead of restore-from-snapshot; MQTT stays for value sync) slots into THIS driver as a transport
swap — config gains `host`, the command path switches to HTTP, everything else stays. Gated on the
bench-twin OTA protocol (spare D1 Mini; USB reflashing of the soldered modules is unacceptable at
any cost). Unfiled until the user green-lights the firmware track.
