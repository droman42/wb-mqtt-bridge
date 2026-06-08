# WB device authoring — live log (§P3.7 #23)

**Purpose.** Capture the actual interactive workflow we use to author WB-passthrough
device configs, per-device Q&A, accumulated cross-room decisions, friction observations,
and automation opportunities. The intent is to feed a later analysis on whether (and how)
this work can be packaged for other Wirenboard owners.

This file is **living** — extended room-by-room as #23 progresses. It is not the action
plan (that's `docs/action_plan.md`) and not the contract (that's
`docs/voice_integration_contract_draft.md`). It is the **workflow log**.

---

## 0. Methodology

**Trigger.** User invoked an interactive #23 session: "ask me about each device, you plan
to do; this will be an interactive session room-by-room, device-by-device."

**Inputs available.**
- §P3.7 A2 findings in `docs/action_plan.md` (high-level WB-UI dashboard digest from a
  prior pass over `/etc/wb-webui.conf`).
- Earlier slice work: `cabinet_spots.json` as the shape reference.
- The 6 capability profiles authored in #19.
- The 11-room `rooms.json` from #21.

**Inputs NOT directly available to the assistant.**
- The live `/etc/wb-webui.conf` (only on the controller; assistant has no SSH).
- The actual Modbus/MQTT topology beyond what A2 digested.
- The user's mental model of which physical fixture maps to which WB slave/channel.

**Per-device flow.**
1. Assistant proposes a complete draft config based on A2 + slice reference.
2. Assistant surfaces the open decisions tightly (device_id, ru/en/de names, WB topics,
   profile choice, edge cases like state mirroring).
3. User confirms or corrects, often very terse.
4. Assistant writes the file (`backend/config/devices/wb-devices/<room>/<device_id>.json`),
   smoke-tests parse + capability resolution, reports outcome.
5. Move to next device.

**Pause / checkpoint cadence.** User-driven. After a room finishes (or partially finishes),
the user calls `commit and push`; assistant pauses until `continue` arrives.

---

## 1. Per-device session log

### 1.1 Cabinet (room id `cabinet`, WB dashboard `cabinet`)

#### 1.1.0 `cabinet_spots` — pre-existing slice device (reference)

Authored before #23 as part of slice #14. Included here as the shape reference for the
rest of the room.

| Attribute | Value |
|---|---|
| device_id | `cabinet_spots` |
| profile | `light_switch` |
| WB control | `wb-mr6c_51/K4` |
| ru/en | `Споты` / `Spots` (no de at slice time) |
| state mirroring | `power` (bare string, for internal no_op) |

---

#### 1.1.1 `cabinet_backlight` — paired switch+brightness on wb-mrgbw-d-fw3_238

Assistant's source: A2 mentioned "cabinet Подсветка = wb-mrgbw-d-fw3_238/Channel 2 (R) +
Channel 2 (R) Brightness" — paired switch+brightness, single-color (the wb-mrgbw-d-fw3
is an RGB controller, here used for one channel).

**Assistant proposed.** device_id=`cabinet_accent`, ru=`Подсветка`, en=`Accent Light`,
de=`Akzentbeleuchtung`. Profile=`dimmable_light`. State mirrors both `power` (bare
string, for no_op) and `level` (typed int %).

**User response.** `cabinet_backlight, en stays, de Hintergrundbeleuchtung, confirm
controls, yes mirror power`

**Resolved.**
| Attribute | Value |
|---|---|
| device_id | `cabinet_backlight` (user override) |
| ru/en/de | `Подсветка` / `Accent Light` / `Hintergrundbeleuchtung` (user changed de only) |
| profile | `dimmable_light` |
| WB controls | `wb-mrgbw-d-fw3_238/Channel 2 (R)` + `Channel 2 (R) Brightness` (verbatim, with spaces and parens) |
| state mirroring | `power` (bare string), `level` (int %) |

**Observations.** User accepted en + control topics as-is; tweaked device_id (likely to
match a Russian-transliteration convention `<room>_<feature>` they have in mind) and
swapped de to `Hintergrundbeleuchtung` (more idiomatic for accent/backlighting in German
than `Akzentbeleuchtung`).

---

#### 1.1.2 `cabinet_floor` + 1.1.3 `cabinet_windowsill` — heating loops

Assistant's source: A2 claimed cabinet had **three** heating loops: radiator, warm floor,
windowsill. Assistant assumed radiator was `wb-gpio/EXT3_R3A5`.

**Assistant proposed.** A `heating_loop`-profile template with mode actions + setpoint
slider + room temperature sensor. Asked for confirmation on: drop radiator?, setpoint
topics, room-temp topic, windowsill id, naming.

**User response (round 1).** `1. do it like for cabinet spots 2. cabinet_floor.
3. wb-mr6cu_31/K5 for the floor wb-gpio/EXT3_R3A5 - windowsill, 4. - reasonable`

Assistant had to infer: A2 was wrong about 3 loops (live home has 2), the
`wb-gpio/EXT3_R3A5` originally hypothesized for radiator is actually the windowsill,
floor's actuator is `wb-mr6cu_31/K5`. Setpoint and room-temp topics still unanswered.

**Assistant's follow-up.** Asked for setpoint topics, room temp topic, windowsill id
confirmation, and en/de names.

**User response (round 2).** `setpoints_floor/cabinet1_temp - setpoint floor,
setpoints_floor/cabinet2_temp - setpoint windowsill, wb-m1w2_56/External Sensor 1 -
floor temperature, wb-m1w2_56/External Sensor 2 - windowsill temperature, cabinet has
no radiator`

Important insight: the "temperature" topics for the heating loops are NOT the
wb-msw-v3_219 room sensor — they're per-loop 1-wire sensors on `wb-m1w2_56` (the
Wirenboard 1-wire master). Semantically the heating system regulates against the
loop's own feedback sensor (floor surface temp, windowsill heater temp), not the room
air temperature. The profile field is named `room_temperature` but the value mirrored
into it is the loop sensor's reading — soft semantic mismatch noted, not fixed (the
data is right; only the field name reads less precisely than it could).

**Resolved.**
| Attribute | `cabinet_floor` | `cabinet_windowsill` |
|---|---|---|
| ru/en/de | `Тёплый пол` / `Floor Heating` / `Fußbodenheizung` | `Подоконник` / `Windowsill Heater` / `Fensterbankheizung` |
| profile | `heating_loop` | `heating_loop` |
| actuator | `wb-mr6cu_31/K5` | `wb-gpio/EXT3_R3A5` |
| setpoint | `setpoints_floor/cabinet1_temp` | `setpoints_floor/cabinet2_temp` |
| loop temp | `wb-m1w2_56/External Sensor 1` | `wb-m1w2_56/External Sensor 2` |
| setpoint range | 5–30 °C | 5–30 °C |
| state mirroring | mode (bare string, for no_op) + setpoint (float °C) + room_temperature (float °C) | same |

**Cross-cutting decision triggered.** During this device's authoring the assistant
surfaced a profile-vs-wire mismatch (see §2.3 below). User chose option (c): make the
`heating_loop` profile mirror the `light_switch` pattern. Resulting profile edit:
removed `mode` from `fields[]` (kept `state_field` for reconciler use). Both heating
configs already had `mode` as bare-string state_topic, so no device-side change
needed.

---

#### 1.1.4 `cabinet_sensors` — wb-msw-v3_219 multi-sensor

**Status: deferred to a later session.** User said: "skip all sensors for now, I need
to dig into documentation (we'll do it together with global room)." Sensors require
WB-MSW firmware documentation review (some firmware variants ship subsets of the
declared sensor set; some have per-control naming quirks).

---

## 2. Accumulated decisions

Decisions taken during #23 that affect multiple devices/rooms or change the schema.

### 2.1 Trilingual ru/en/de for every device

Adopted at the start of #23: every device's `names` carries ru + en + de. ru is
WB-UI verbatim where available, en is natural-home translation, de is best-effort
idiomatic. Matches the trilingual room set from #21.

### 2.2 Mirror internal state (`power` / `mode`) even when the profile doesn't expose it

cabinet_spots's `state_topics["power"]` exists despite `light_switch` profile not
declaring `power` as a field. The mirrored value is used only by the driver's no_op
short-circuit on the canonical endpoint. Confirmed as the desired pattern for #23 (user
on cabinet_backlight: "yes mirror power"). Applies wherever a switch's persistent state
matters for idempotency but doesn't need a public catalog field.

### 2.3 `heating_loop` profile — drop `mode` from `fields[]` (mirror `light_switch`)

**The problem.** WB switch controls publish `"0"` / `"1"` raw on the wire. The
`heating_loop` profile originally declared its `mode` field as `type: "enum",
values: ["off", "on"]`. The catalog promised consumers the value would be `"off"` or
`"on"`; the actual state surface would have returned `"1"` (the raw mirror) — a lie
in the contract.

**Three options offered.**
- (a) Profile `mode: str` — catalog drops the enum claim, says "string".
- (b) Profile `mode: bool` — semantic match (it IS a switch); device state_topic must
  also be `type: bool` so the driver coerces `"1"` → `True`.
- (c) Mirror the `light_switch` pattern: remove `mode` from `fields[]` entirely. The
  catalog stops claiming any typed `mode` field. State stays internal-only for no_op.

**User chose (c).** Applied to `heating_loop.json`. Implication for voice: cannot ask
"is the floor heating currently on?" via a catalog-described typed field; can only
fire `mode.on` / `mode.off` actions. Acceptable for a command-only interaction.

### 2.4 Cabinet has **2** heating loops, not 3

A2 claimed three (radiator, warm-floor, windowsill). User correction: cabinet has only
floor + windowsill. Radiator entry dropped before drafting. A2 findings are a
**starting hypothesis**, not the ground truth; the user's home knowledge is the
source of authority for each room.

### 2.5 Loop-feedback temperatures live on `wb-m1w2_56`, not the wb-msw room sensor

For heating loops, the temperature sensor we mirror is the per-loop 1-wire sensor on
`wb-m1w2_56` (External Sensor 1/2 for floor/windowsill respectively), NOT the room
air temperature from wb-msw-v3_219. The heating control regulates against the loop
sensor; that's the relevant "current temperature" for the device. Soft field-name
mismatch noted (`room_temperature` is a slight misnomer here); not fixed in this pass.

### 2.6 Aggregate-device authoring (#22) postponed

User skipped #22 to do #23 first. Implication: the `global` room exists in
`rooms.json` but stays empty until aggregates are authored later (after #23 or
deferred indefinitely depending on voice command coverage).

### 2.7 Cabinet sensors deferred to a global-room session

User explicitly batched all sensor authoring with the eventual global-room work.
Probable reason: sensor topic naming requires firmware-documentation cross-reference
that the user wants to do in one focused session, not interleaved with actuator
configs.

---

## 3. Friction observations

Things that slowed the authoring or required round-trips.

### 3.1 A2's per-room device inventory is incomplete and partially wrong

A2 captured the WB-UI dashboards at a high level (which slaves serve which rooms,
which composite shapes exist). But:
- It mis-counted cabinet's heating loops (3 vs actual 2).
- It didn't enumerate per-loop setpoint topic suffixes.
- It didn't identify per-loop feedback sensors (assumed room temp from wb-msw).

**Impact.** The assistant's first draft for the heating loops was wrong on actuator
mapping and incomplete on setpoint/temp topics. User had to provide the corrections
across two reply rounds.

### 3.2 User's responses are terse — interpretation risk

Replies like `wc->shower` (one symbolic-id remap) or `2. cabinet_floor.` (one device
id where three were asked about) require careful interpretation. Assistant has to
verify ("did you mean only ONE heating loop or are you skipping radiator?") rather
than assume.

**Mitigation.** When ambiguity surfaces, ask a tight clarifying question before
writing. Don't guess on identity.

### 3.3 The profile-vs-wire mismatch surfaced only at draft time

The `heating_loop.mode: enum ["off","on"]` declaration looked fine in isolation in
#19, but only became a problem when an actual WB switch control's wire format
(`"0"` / `"1"`) had to map onto it. A schema-aware authoring linter could surface
this proactively ("you declared this field as enum but the WB control publishes
booleans — pick a fix").

### 3.4 Per-loop temperature sensor on a separate 1-wire module wasn't predictable

Without seeing the live broker, the assistant couldn't know that floor heating
feedback comes from `wb-m1w2_56/External Sensor N` and not from the room's wb-msw.
Required user disclosure.

---

## 4. Automation opportunities

If we ever want to package this as a self-serve flow for other Wirenboard owners:

### 4.1 Read `/etc/wb-webui.conf` directly

The dashboards JSON has authoritative room → device-cell mappings. A bootstrap script
could:
- Enumerate dashboards and their widget cells.
- For each cell, infer the WB slave/control and the human label.
- Classify each cell by `cell.type` (`switch` → light_switch, `range` → covers a slider
  candidate, `temperature` → sensor or setpoint, `rgb` → rgb_light).
- Detect paired controls (`K2` next to `Channel 2 Brightness`, etc.) and propose a
  single `dimmable_light` device per pair.
- Group into per-room logical device proposals.

This would replace "A2 findings" with live ground truth and avoid the cabinet-radiator
type of mismatch entirely.

### 4.2 ru name verbatim from `cell.name`, en/de via translation table or LLM call

The WB-UI cells carry Russian labels. Reusing them removes the "what should the ru
name be?" round-trip. en/de can come from a small curated translation table (rooms +
common fixtures) plus LLM fallback for edge cases.

### 4.3 Profile suggestion based on cell topology

If a slave has K-channel switches + matching Brightness controls, propose
`dimmable_light` per pair. If a slave has R/G/B channels, propose `rgb_light`. If it
has a Position slider only, propose `cover`. The mappings are mostly mechanical.

### 4.4 Schema-aware authoring linter

When the user (or importer) declares a `state_topic` with a type that conflicts with
the profile's declared field type, surface the mismatch with the three resolutions
we discussed (str / bool / drop from fields[]). Decision-support, not auto-resolve.

### 4.5 Topology gaps the importer can't fill

Some details probably never live in `/etc/wb-webui.conf`:
- Which `setpoints_floor/cabinetN_temp` belongs to which physical loop.
- Which 1-wire `External Sensor N` corresponds to which heater.
- Per-loop setpoint min/max safe ranges.

These require user disclosure regardless. A staged UI could surface them as
"unresolved → please confirm" entries.

---

## 5. Open questions for later analysis

- **Sensor strategy.** wb-msw firmware variants ship subsets of the declared
  sensor_room fields. Should the profile declare ALL plausible fields, and per-device
  configs OMIT the ones their firmware doesn't carry? Or should the profile only
  declare fields universally present, with optional fields added via per-device
  overrides?
- **Naming convention for paired devices.** cabinet_backlight covers the
  `Channel 2 (R)` switch + its `Channel 2 (R) Brightness` slider. If a slave has
  three such pairs (one per RGB channel acting as separate single-color zones), how
  do we name them? `cabinet_backlight_r/g/b`? `cabinet_backlight_left/right/center`?
  Per-device choice, but a convention would speed authoring.
- **HVAC enum fields.** The `hvac` profile's `mode/fan/vane` are enums with
  multi-value vocab. We need to verify the actual wire payloads on
  `hvac_*/controls/mode` etc. — are they `"auto"` / `"cool"` (matching the profile)
  or numeric codes? If the latter, same `heating_loop.mode` resolution applies, but
  per field, three times per HVAC.
- **Aggregate devices in `global`.** Postponed to a later session. Worth a separate
  log entry when authored, including what aggregations the wb-rules side actually
  supports and what voice command set drives them.

---

## 6. Sessions log (timestamped checkpoints)

- **2026-06-08** — Session 1: cabinet (3 new devices + heating_loop profile fix).
  Committed `913cbf9`. 482 tests passing. Sensors deferred. User called `pause`;
  living_room next when `continue` arrives.
