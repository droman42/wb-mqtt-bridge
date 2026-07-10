# MitsubishiHvac — a dedicated driver for the mitsubishi2wb HVAC modules (DRV-27 design)

**Status: DESIGN AGREED 2026-07-10 (interactive session).** Implementation = **DRV-28**; the
enum-value icon mechanism = **UI-16** (separate). Successor to the generic-passthrough treatment
of the three HVACs; the VWB-11-anticipated "ESP32ManagedDevice migration" — renamed, since the
modules are **ESP8266 (Wemos D1 Mini)** and the contract is the *firmware's*, not a chip's.

## 1. Why a dedicated driver

The 2026-07-09 retained-wipe incident (journal) exposed the mismatch: HVACs are commanded-state
equipment with a real protocol vocabulary, modeled as dumb passthrough mirrors. Consequences the
generic driver cannot fix cleanly:

- **No restore-at-boot** — passthrough's dynamic fields deliberately don't restore (DRV-25), so a
  broker wipe leaves the bridge blind until each value changes on the device.
- **No offline detection** — the firmware has no LWT and no per-control `meta/error`; passthrough
  reachability machinery has nothing to hook onto.
- The wire↔canonical vocabulary, topic layout, and publish semantics are all properties of one
  specific firmware — [`mavlyutov/mitsubishi2wb`](https://github.com/mavlyutov/mitsubishi2wb) —
  which is what bespoke drivers exist to encode (the BroadlinkKitchenHood precedent).

Constraints this design honors: **mosquitto persistence stays OFF** (user decision, WB community
advice) and the **firmware stays untouched for now** (a REST-endpoints rewrite is separately under
research, gated on the bench-twin OTA protocol; this driver is transport-ready for it — §8).

## 2. The firmware contract (source of truth: `mitsubishi2wb.ino`)

Verified 2026-07-09 in `hpSettingsChanged()` / `mqttCallback()` / `mqttConnect()`:

- **Topics** (fixed layout, one variable — the WB device name `N`):
  `/devices/N/controls/{power,mode,fan,vane,widevane,temperature,room_temperature}` (values,
  retained, published **on change only**) and `…/{control}/on` (commands, except
  `room_temperature`).
- **Wire vocabulary**: numeric index strings (the DRV-26 tables): mode 0=auto…4=fan_only; fan
  0=auto 1=quiet 2..5=speed_1..4; vane 0=auto 1=swing 2..6=pos_1..5; widevane 0=swing
  1..5=far_left..far_right 6=split; power `1`/`0`; temperature/room_temperature floats.
- **Commands**: exact numeric strings only; anything else is **silently ignored** (`else return`).
- **On MQTT reconnect**: re-publishes `meta` only — never values (the wipe fragility).
- **`room_temperature` is published every 45 s unconditionally** (`SEND_ROOM_TEMP_INTERVAL_MS`)
  — the only periodic signal, i.e. **a heartbeat**.
- No LWT, no `meta/error`.

## 3. Decisions

### D1 — Naming: `MitsubishiHvac` (user decision)

`MitsubishiHvac` / `MitsubishiHvacConfig` / `MitsubishiHvacState`, capability map at
`config/capabilities/classes/MitsubishiHvac.json`. The driver docstring records that the actual
contract is the mitsubishi2wb firmware dialect (this file, §2).

### D2 — Capability map moves `profiles/hvac.json` → `classes/MitsubishiHvac.json`; the profile dies

Same `climate` capability content (actions, `state_field: "power"`, fields with the DRV-26 value
tables and trilingual labels), plus **`reconcile: false` explicit** (scenarios don't own HVAC; the
default is true). The `hvac` profile has no other users and is deleted — one source.

### D3 — Wire tables live in the class map ONLY (user decision; amends the filed premise)

The driver translates via its **attached capability map** (`self.capabilities` →
`fields[].values`, the shared `ValueLabel` machinery). No code constants, no duplication, and the
catalog carries the tables for free. Hexagonally clean (infrastructure reads domain models).
Ordering note for DRV-28: `attach_capability_maps` runs in bootstrap before MQTT subscriptions
deliver echoes — verify and pin with a test.

### D4 — Device configs shrink to identity + one topic variable

```json
{ "device_id": "children_room_hvac",
  "names": { "ru": "Кондиционер", "en": "Air Conditioner", "de": "Klimaanlage" },
  "room": "children_room", "device_category": "appliance",
  "device_class": "MitsubishiHvac", "config_class": "MitsubishiHvacConfig",
  "mqtt_device": "hvac_children" }
```

All topics derive from `mqtt_device` per §2. The ~60-line `commands`/`state_topics` blocks and
`capability_profile` are gone from all three configs. (Optional per-unit extras if ever needed:
`supports_heat`, setpoint min/max — not in v1; the firmware clamps anyway.)

### D5 — Typed state, restore-at-boot, heartbeat reachability

`MitsubishiHvacState(BaseDeviceState)`: `mode/fan/vane/widevane: Optional[str]` (canonical),
`setpoint: Optional[float]`, `room_temperature: Optional[float]`, `reachable: bool = True`; the
base `power` field carries `"on"`/`"off"`. Declared fields ride the **existing VWB-18
restore-at-boot** — after a reboot + broker wipe the bridge (and voice, and HvacPanel) still knows
the last commanded state; live retained echoes overwrite the snapshot at setup as usual.

**Reachability = the heartbeat**: an `asyncio` watchdog flips `reachable = False` when no
`room_temperature` arrives for ~3 intervals (≈ 2.5 min), back to `True` on any message. The first
honest offline detection these units have ever had (no LWT in the firmware). All state writes ride
the `update_state` chokepoint.

### D6 — Command path

Canonical `climate.*` actions expand (VWB-17 machinery) to native commands (`set_mode` etc.); the
driver translates canonical → numeric wire via the class map and publishes to `…/{control}/on`
(non-retained, as today). Idempotence: compare desired vs the typed state field; honor the
reserved `force`/`assume_state` params via the DRV-5 `idempotence_skip` chokepoint (the AV-driver
pattern — passthrough's ad-hoc `no_op` flag is replaced by the standard one). Echo-wait semantics
unchanged: the firmware echoes the value topic on a real change; `no_op` short-circuits the wait.

### D7 — No bridge-owned WB card (user decision: the ESP32's card "is fine like it is")

The WB UI keeps the firmware's own raw card; humans use the bridge UI + voice. One card per
actual device owner — the bridge never publishes into another device's namespace.

### D8 — Enum-value icons = the AV mechanism, filed as UI-16 (user decision: "same mechanism")

AV button icons are resolved **UI-side by name** through the renderer's `IconResolver` (the
manifest's `ActionIcon` is a placeholder hint — `ui_backend_contract.md` "Icons"). UI-16 extends
the same resolver to **canonical enum values** (`cool` → snowflake, `heat` → sun, …) and replaces
`HvacPanel`'s hardcoded `SECTION_GLYPHS`. No contract change, no emoji in config; canonical
identifiers are the stable keys.

## 4. What deliberately does NOT change

- Canonical vocabulary, field names, `climate` action names → **voice and HvacPanel logic
  unchanged** (the panel is routed by `device_id`).
- The DRV-25 passthrough machinery (top-level dynamic fields, loader enrichment) — stays, serving
  heating_loop / covers / dimmers / sensors.
- MQTT as the only transport (v1) — see §8.

## 5. Contract impact

`device_class` is catalog surface → **golden bumps** (supersedes `a4a2b1aed5f86447`). openapi:
`MitsubishiHvacState` joins the persisted-state union if the union is explicit — verify at
implementation; the `/state` endpoints themselves are schema-`{}`. **The voice side re-pins ONCE,
after DRV-28 lands** (covers DRV-25 + DRV-26 + DRV-28; they have not pinned the interim hashes).

## 6. Migration & rollout

Config-only rollout on the WB7 (`git pull` + `update.sh` + backend restart — no image change
beyond the code image itself; note DRV-28 *does* change backend code → backend image rebuild).
The persisted passthrough snapshots for the 3 device_ids are schema-mismatched after the class
swap — `restore_state` degrades gracefully (declared-fields-only, VWB-18); first boot re-seeds
from retained topics.

## 7. Tests (DRV-28, per the device-test recipe)

Real driver + real class map + mocked MQTT: topic derivation from `mqtt_device`; inbound wire →
canonical typed state (mode `'2'` → `'cool'`, floats); outbound canonical → numeric wire (`cool` →
`'2'` on `mode/on`); idempotence + `force`/`assume_state`; heartbeat watchdog (reachable flips on
silence, recovers on message); restore-at-boot round trip (snapshot → declared fields → live
retained wins); catalog projection (readable fields + tables from the class map); config-load
collision with the deleted profile (none — profile gone); the 3 migrated configs parse.

## 8. Horizon (recorded, not scoped)

The REST-endpoints firmware rewrite (commands via HTTP `POST /api/control`, `GET /api/status` at
boot instead of restore-from-snapshot; MQTT stays for value sync) slots into THIS driver as a
transport swap — config gains `host`, the command path switches to HTTP, everything else (state
model, tables, catalog, tests) stays. Gated on the bench-twin OTA protocol (a spare D1 Mini;
USB reflashing of the soldered modules is unacceptable at any cost). Unfiled until the user green-
lights the firmware track.
