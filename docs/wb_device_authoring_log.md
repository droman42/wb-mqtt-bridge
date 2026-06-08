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

### 1.10 Wardrobe (room id `wardrobe`, WB dashboard `wardrobe`)

2 light devices — smallest physical room.

| device_id | ru | en | de | profile | WB control(s) |
|---|---|---|---|---|---|
| `wardrobe_spots` | Споты | Spots | Spots | **`light_switch`** | `wb-mr6c_51/K5` |
| `wardrobe_shelves_light` | Подсветка полок | Shelves Accent | Regalbeleuchtung | `dimmable_light` | `wb-mrgbw-d-fw3_10/Channel 2 (R)` + `Brightness` |

**First non-dimmable Споты** across all rooms — wardrobe's spots are on a wb-mr6c
relay (no brightness control). All previous rooms' "Споты" were on wb-mdm3 dimmers.
The catalog naturally exposes the difference (no `set_brightness` action, no `level`
field) — voice/UI can render appropriately per-device.

**RGB controller exhaustion** — `wb-mrgbw-d-fw3_10` now uses all 3 RGB channels:
R (wardrobe shelves), G (bedroom window), B (bedroom shelves), driving 3 independent
single-color fixtures across 2 rooms.

**Slave fully used** — `wb-mr6c_51` now has all 6 channels mapped: K1 (hall), K2 +
K3 (children), K4 (cabinet), K5 (wardrobe), K6 (bedroom). 5 rooms.

### 1.9 Bathroom (room id `bathroom`, WB dashboard `bathroom`)

5 devices: 4 lights + floor heating. Both shelf lights needed name disambiguation
(Полка над ванной / Полка над унитазом) → device_ids follow layer-then-location
pattern (`bathroom_shelf_bath`, `bathroom_shelf_toilet`), en uses parenthetical form
(`Shelf (Bath)`, `Shelf (Toilet)`).

| device_id | profile | WB control(s) |
|---|---|---|
| `bathroom_spots` | `dimmable_light` | `wb-mdm3_95/K2` + `Channel 2` |
| `bathroom_mirror` | `light_switch` | `wb-mr6c_52/K2` |
| `bathroom_shelf_bath` | `light_switch` | `wb-mr6c_58/K6` |
| `bathroom_shelf_toilet` | `light_switch` | `wb-mr6c_58/K5` |
| `bathroom_floor` | `heating_loop` | `wb-mr6cu_31/K3` + setpoints_floor/wc2_temp + wb-m1w2_173 floor sensor |

**Slave fully used** — `wb-mr6c_58` now has all 6 channels mapped: K1 + K2 (living),
K3 + K4 (bedroom), K5 + K6 (bathroom). 3 rooms.

### 1.8 Shower (room id `shower`, WB dashboard `wc`)

6 devices: 4 lights + floor heating + sauna sensors (the ONE sensor exception to the
"sensors deferred" rule — see §2.14 for the catalog-filter design decision triggered).

| device_id | profile | notes |
|---|---|---|
| `shower_spots` | `dimmable_light` | `wb-mdm3_83/K2` + `Channel 2` |
| `shower_mirror` | `light_switch` | `wb-mr6c_47/K2` |
| `shower_sauna` | `dimmable_light` | `wb-mrgbw-d-fw3_238/Channel 1 (B)` — single-color RGB channel |
| `shower_service_closet` | `light_switch` | `wb-mr6c_52/K6` — Инженерный шкаф (utility cabinet) |
| `shower_floor` | `heating_loop` | `wb-mr6cu_31/K2` + setpoints_floor/wc1_temp + wb-m1w2_114 floor sensor (legacy `wc1_*` topic naming) |
| `shower_sauna_sensors` | `sensor_room` | wb-msw2_100 — only 2 of 5 profile fields (temperature + humidity); triggered catalog-filter feature §2.14 |

### 1.7 Hall (room id `hall`, WB dashboard `hall`)

3 light devices. Only category present.

| device_id | profile | WB control(s) |
|---|---|---|
| `hall_spots` | `dimmable_light` | `wb-mdm3_87/K2` + `Channel 2` |
| `hall_track_1` | `light_switch` | `wb-mr6c_51/K1` (Трек 1 = track light 1) |
| `hall_track_2` | `light_switch` | `wb-mr6c_52/K3` |

### 1.6 Entrance (room id `entrance`, WB dashboard `entrance`)

Smallest room so far. 2 devices authored; widget had 4 additional cells that the user
chose to skip — see new pattern note §2.13.

| device_id | ru | en | de | profile | WB control(s) |
|---|---|---|---|---|---|
| `entrance_spots` | Споты | Spots | Spots | `dimmable_light` | `wb-mdm3_83/K1` + `Channel 1` |
| `entrance_cabinet_accent` | Подсветка шкафа | Cabinet Accent | Schrankbeleuchtung | `light_switch` | `wb-mr6c_52/K5` |

Naming nuance: `Шкаф` here is the entrance coat/shoe cabinet (a piece of furniture in
the entryway), NOT the `wardrobe` ROOM (Гардеробная, walk-in closet). device_id
`entrance_cabinet_accent` avoids the conflict; `entrance_wardrobe` would have read
ambiguously against the wardrobe room id.

**User response.** `approve all 2` — bulk approval.

---

### 1.5 Kitchen (room id `kitchen`, WB dashboard `kitchen`)

Compact room: 4 WB-passthrough devices (no curtains, no HVAC, just lights + floor
heating). The pre-existing AV device `kitchen_hood` remains.

#### 1.5.1 Lighting widget (3 devices)

| device_id | ru | en | de | profile | WB control(s) |
|---|---|---|---|---|---|
| `kitchen_spots` | Споты | Spots | Spots | `dimmable_light` | `wb-mdm3_87/K1` + `Channel 1` |
| `kitchen_chandelier` | Люстра | Chandelier | Kronleuchter | `light_switch` | `wb-mr6c_47/K5` |
| `kitchen_backlight` | Подсветка | Accent Light | Hintergrundbeleuchtung | `light_switch` | `wb-mr6c_47/K6` |

Naming notes:
- `Подсветка` (no qualifier) → `kitchen_backlight` device_id, matching cabinet_backlight
  precedent for the un-qualified case (vs `_accent` for qualified `Подсветка <X>` like
  bedroom's window/shelves accents).
- Cross-room slave count: `wb-mr6c_47` now hosts living K3+K4 + kitchen K5+K6.

**User response.** `approve all 3` — bulk approval.

#### 1.5.2 Floor heating — `kitchen_floor`

First heating loop with TWO available temperature sensors: room air
(`wb-msw-v3_218/Temperature`) AND floor surface (`wb-m1w2_43/External Sensor 1`).
User chose to **drop the air sensor and keep only the floor sensor** for this device,
mapped to the existing `room_temperature` profile field name (same soft-mismatch
pattern as cabinet's loops — see §2.5).

Two notable departures from the other heating loops:
1. **Actuator NOT inverted** — no `invert: true` in the widget's `extra` map for
   `wb-mr6cu_31/K4`, so `mode_on` writes `"1"` (matches cabinet's loops; differs from
   living/children/bedroom whose wb-gpio actuators were inverted).
2. **wb-mr6cu_31** appears twice now: cabinet_floor on K5, kitchen_floor on K4. Same
   slave, different channels.

| device_id | ru | en | de | actuator | setpoint | temp |
|---|---|---|---|---|---|---|
| `kitchen_floor` | Теплый пол | Floor Heating | Fußbodenheizung | `wb-mr6cu_31/K4` (NOT inverted) | `setpoints_floor/kitchen_temp` | `wb-m1w2_43/External Sensor 1` |

### 1.5.3 Kitchen session summary

**4 devices** (no HVAC, no curtains, no sensors):

| Profile | Count | Devices |
|---|---|---|
| `light_switch` | 2 | chandelier, backlight |
| `dimmable_light` | 1 | spots |
| `heating_loop` | 1 | floor |

Zero profile-side changes. The smallest room so far — confirms that not every room
has every category.

---

### 1.4 Bedroom (room id `bedroom`, WB dashboard `bedroom`)

Largest single room so far (11 devices). Three categories authored: lights, HVAC,
heating, curtains. Sensors deferred.

#### 1.4.1 Lighting widget (7 devices in one round-trip)

Most complex lighting widget yet: 10 cells → 7 logical devices. Two patterns worth
flagging:

**Multiple paired switch+brightness cells on one RGB controller**: `wb-mrgbw-d-fw3_10`
has its `Channel 3 (G)` and `Channel 1 (B)` channels used as INDEPENDENT single-color
dimmable lights (window accent + shelves accent). Same shape as cabinet_backlight on
`wb-mrgbw-d-fw3_238/Channel 2 (R)`, but here two channels on the same controller drive
two different fixtures. The fw3 controller can drive 4 channels independently (R/G/B/W)
plus the all-channel "RGB Strip"; this room uses two of them.

**Cross-room slave use accumulating**: `wb-mr6c_51` now hosts cabinet K4 + children
K2/K3 + bedroom K6. `wb-mr6c_58` hosts living K1/K2 + bedroom K3/K4. Each device's
config references the slave path it cares about; no special handling needed.

| device_id | ru | en | de | profile | WB control(s) |
|---|---|---|---|---|---|
| `bedroom_spots` | Споты | Spots | Spots | `dimmable_light` | `wb-mdm3_95/K1` + `Channel 1` |
| `bedroom_window_light` | Подсветка окна | Window Accent | Fensterbeleuchtung | `dimmable_light` | `wb-mrgbw-d-fw3_10/Channel 3 (G)` + `Brightness` |
| `bedroom_shelves_light` | Подсветка полок | Shelves Accent | Regalbeleuchtung | `dimmable_light` | `wb-mrgbw-d-fw3_10/Channel 1 (B)` + `Brightness` |
| `bedroom_nightstand_right` | Тумбочка справа | Nightstand (Right) | Nachttisch rechts | `light_switch` | `wb-mr6c_58/K3` |
| `bedroom_nightstand_left` | Тумбочка слева | Nightstand (Left) | Nachttisch links | `light_switch` | `wb-mr6c_58/K4` |
| `bedroom_sconce_right` | Бра справа | Sconce (Right) | Wandleuchte rechts | `light_switch` | `wb-mr6c_51/K6` |
| `bedroom_sconce_left` | Бра слева | Sconce (Left) | Wandleuchte links | `light_switch` | `wb-mr6c_52/K1` |

**User response.** `approve all 7, ranges go from 0 to 100` — bulk approval +
range confirmation (which matched my draft).

**Adjacent fix triggered**: `test_new_rooms_start_with_empty_devices` was asserting
6 rooms still empty; bedroom no longer fits. Renamed test to
`test_rooms_not_yet_onboarded_are_still_empty` and dropped bedroom from the empty list
with a docstring tracking the trajectory ("rooms that #23 hasn't reached yet").
Pattern will repeat for kitchen + remaining 5 rooms.

#### 1.4.2 HVAC — `bedroom_hvac` (3rd Mitsubishi, mechanical clone)

Identical shape to `living_room_hvac` / `children_room_hvac`. Topic prefix
`hvac_bedroom`. Same ESP32ManagedDevice migration flag (§2.11). Written without Q&A;
user-implicit approval.

#### 1.4.3 Heating loop — `bedroom_heating` (mechanical clone)

Same shape as `living_room_heating` / `children_room_heating`: wb-gpio actuator with
`invert: true`, setpoints_radiator setpoint, wb-msw-v3 room sensor. Topics: actuator
`EXT3_R3A4`, setpoint `bedroom_temp`, sensor `wb-msw-v3_225`. Written without Q&A.

#### 1.4.4 Curtains — single rail (2 covers)

Bedroom has a single curtain rail with both heavy + sheer layers (vs. living_room's
TWO rails). Naming: no left/right qualifier needed → kept ru cells verbatim (`Штора`,
`Тюль`); device_ids just `bedroom_curtain` and `bedroom_tulle`. Same §2.10 "verbatim
when unambiguous" pattern that cabinet's rollers used.

| device_id | ru | en | de | WB control |
|---|---|---|---|---|
| `bedroom_curtain` | Штора | Curtain | Vorhang | `dooya_0x0108/Position` |
| `bedroom_tulle` | Тюль | Sheer | Gardine | `dooya_0x0107/Position` |

### 1.4.5 Bedroom session summary

**11 devices** (sensors deferred):

| Profile | Count | Devices |
|---|---|---|
| `light_switch` | 4 | nightstand_right/left, sconce_right/left |
| `dimmable_light` | 3 | spots, window_light, shelves_light |
| `cover` | 2 | curtain, tulle |
| `hvac` | 1 | hvac (ESP32ManagedDevice migration flagged) |
| `heating_loop` | 1 | heating |

Zero new profile-side changes. Drift-guard test happy throughout. The first three
rooms paid the design cost; bedroom (and from here on) is pure copy-paste-with-topic-swap.

---

### 1.3 Children's room (room id `children_room`, WB dashboard `children`)

#### 1.3.1 Lighting widget (4 devices in one round-trip)

User pasted the **Освещение** widget JSON. 5 cells → 4 logical devices (one paired
switch+brightness + 3 simple switches + 1 RGB strip used as on/off).

| device_id | ru | en | de | profile | WB control(s) |
|---|---|---|---|---|---|
| `children_room_spots` | Споты | Spots | Spots | `dimmable_light` | `wb-mdm3_87/K3` + `Channel 3` |
| `children_room_ceiling_accent` | Подсветка потолка | Ceiling Accent | Deckenbeleuchtung | `light_switch` | `wb-mrgbw-d-fw3_11/RGB Strip` |
| `children_room_behind_column` | За колонной | Behind Column | Hinter der Säule | `light_switch` | `wb-mr6c_51/K2` |
| `children_room_by_wardrobe` | У Гардероба | By Wardrobe | Beim Kleiderschrank | `light_switch` | `wb-mr6c_51/K3` |

**Notable shape**: an RGB strip cell exposed as just a `switch` in the widget (no
brightness/color slider companions). User confirmed (a) on/off-only — modeled as
`light_switch`, not `rgb_light`. The wb-mrgbw-d-fw3 controller can drive RGB but in this
room it's treated as a single fixed-color accent.

**Cross-room slave**: `wb-mr6c_51` already hosts `cabinet_spots` (K4) — it now also
hosts the children's room K2/K3. A2's "15 slaves serve multiple rooms" finding observed
in practice. No special handling needed — each device's config references the slave
path it cares about.

**User response.** `(a) light_switch only, all device_ids and translations approved` —
one-line approval.

**Resolved-in-one-pass.** Four files written. 482 tests still green.

#### 1.3.2 HVAC — `children_room_hvac` (clone of living_room_hvac)

Same Mitsubishi unit shape; topic prefix `hvac_children` instead of `hvac_livingroom`.
No new profile decisions — fully mechanical clone. Assistant skipped the Q&A round and
wrote directly; user-implicit approval via the bulk-children_room flow. Same
ESP32ManagedDevice migration flag applies (§2.11).

| device_id | ru/en/de | profile |
|---|---|---|
| `children_room_hvac` | Кондиционер / Air Conditioner / Klimaanlage | `hvac` |

#### 1.3.3 Heating loop — `children_room_heating` (clone of living_room_heating)

Same shape as `living_room_heating`: wb-gpio actuator with `invert: true` (so `mode_on`
writes `"0"`), setpoints_radiator setpoint, wb-msw-v3 room sensor. Different topics:
actuator `EXT3_R3A3`, setpoint `children_temp`, sensor `wb-msw-v3_220`. Cloned without
Q&A; user-implicit approval.

| device_id | ru/en/de | profile |
|---|---|---|
| `children_room_heating` | Обогрев / Heating / Heizung | `heating_loop` |

### 1.3.4 Children's room session summary

**6 devices, room complete** (sensors deferred):

| Profile | Count | Devices |
|---|---|---|
| `light_switch` | 3 | ceiling_accent, behind_column, by_wardrobe |
| `dimmable_light` | 1 | spots |
| `hvac` | 1 | hvac (ESP32ManagedDevice migration flagged) |
| `heating_loop` | 1 | heating |

No profile-side changes — children_room reused the shapes settled by living_room
authoring. Once we have a fully canonical shape per category, subsequent rooms become
mechanical clones with just the topic prefix swap. The first room of each category
pays the design cost; the rest are copy-paste.

---

### 1.2 Living room (room id `living_room`, WB dashboard `livingroom`)

#### 1.2.1 Lighting widget (5 devices in one round-trip)

User pasted the full **Освещение** widget JSON from `/etc/wb-webui.conf` verbatim. First
time we've worked from raw WB-UI JSON instead of A2-fragment summaries — qualitatively
different experience (see §3.5).

The widget contained 5 logical fixtures (one paired switch+brightness, four simple
switches):

| device_id | ru | en | de | profile | WB control(s) |
|---|---|---|---|---|---|
| `living_room_spots` | Споты | Spots | Spots | `dimmable_light` | `wb-mdm3_83/K3` + `Channel 3` |
| `living_room_window_light` | Подсветка окна | Window Accent | Fensterbeleuchtung | `light_switch` | `wb-mr6c_58/K1` |
| `living_room_floor_lamp` | Торшер | Floor Lamp | Stehlampe | `light_switch` | `wb-mr6c_47/K3` |
| `living_room_desk_lamp` | Настольная лампа | Desk Lamp | Tischlampe | `light_switch` | `wb-mr6c_47/K4` |
| `living_room_union_cabinet` | Тумба Юнион | Union Cabinet | Union-Sideboard | `light_switch` | `wb-mr6c_58/K2` |

**Workflow shift.** Because the input was raw WB-UI JSON, assistant could:
- Read the `cell.name` ru labels directly (no guessing).
- Detect the paired switch+brightness from `wb-mdm3_83/K3` + `wb-mdm3_83/Channel 3`
  topology and auto-propose `dimmable_light` for it.
- Detect simple switches from `wb-mr6c_*/K*` cells of `type: switch` (no paired slider)
  and propose `light_switch`.
- Render the 5 complete configs in a single response and ask 4 bulk questions instead
  of 5 round-trips.

**User response (one line).** `1. living_room_, 2. all ok, 3. yes, 4. yes` — all 5
configs approved as-drafted, device_id prefix confirmed, en/de translations accepted.

**Resolved-in-one-pass.** Five files written, all parsed cleanly, no further round-trips.

**Observations.**
- "Тумба Юнион" — assistant guessed "Union Cabinet" for en (Юнион ≈ Union brand
  transliteration); user accepted without correction. Worth confirming the actual
  meaning if it ever matters for voice intent matching ("turn on the Union" — what's
  Union?).
- "Канал 3" (the slider's cell label, literally "Channel 3") is a WB-UI naming
  fallback when no human-meaningful name is set; correctly ignored — the slider is
  the brightness companion of K3 "Споты", not its own fixture.
- en + de translations for room lighting were "all ok" first try — small enough surface
  that defaults landed cleanly.

#### 1.2.2 Curtain widgets (4 devices, 2 widgets)

User pasted both **Карниз Справа** (right rail) and **Карниз Слева** (left rail) widget
JSONs at once. Each rail has two layers: heavy curtain (`Штора`) and sheer (`Тюль`),
each on its own Dooya motor exposing a single `Position` slider (range 0-100).

| device_id | ru | en | de | profile | WB control |
|---|---|---|---|---|---|
| `living_room_curtain_right` | Штора справа | Curtain (Right) | Vorhang rechts | `cover` | `dooya_0x0101/Position` |
| `living_room_tulle_right` | Тюль справа | Sheer (Right) | Gardine rechts | `cover` | `dooya_0x0102/Position` |
| `living_room_curtain_left` | Штора слева | Curtain (Left) | Vorhang links | `cover` | `dooya_0x0103/Position` |
| `living_room_tulle_left` | Тюль слева | Sheer (Left) | Gardine links | `cover` | `dooya_0x0104/Position` |

**Disambiguation pattern.** The WB-UI cells are just `Штора` and `Тюль` — the rail
side (left/right) lives in the parent widget's name, not the cell. Cells with raw WB
labels would be ambiguous in voice ("open the curtain" — which?). Bridge device names
inject the side suffix (`Штора справа`) so voice resolution is unambiguous. User
chose option (a) — disambiguated names. Pattern likely applies anywhere multiple
identical fixtures live across widgets.

**device_id ordering**: user picked **layer-then-side** (`*_curtain_right`,
`*_tulle_left`). Pattern: most-specific-thing first, location modifier last.

**Cross-cutting decision triggered: `cover.stop` dropped from the profile** (see §2.9
below).

**User response.** `1. layer-then-side 2. (a) 3. (b)` — three numbered answers to the
three numbered questions (#4 and #5 implicit "no change to assistant's defaults").

**Resolved-in-one-pass.** Four files written + one profile edit + one test rename.
482 tests still green.

#### 1.2.3 HVAC — `living_room_hvac` (most complex device so far)

Most complex device shape yet. The `Кондиционер` widget JSON exposed 7 cells; my §P3.7 #19
hvac profile draft (authored without the firmware in front of me) had three concrete
errors that surfaced as soon as the live widget data + firmware source arrived:

| Cell | Type per WB JSON | What the profile claimed | Reality (from `mitsubishi2wb` firmware) |
|---|---|---|---|
| `power` | switch | on/off actions ✓ | matches |
| `mode` | **range** (NOT enum) | enum off/cool/heat/auto/fan/dry | int 0-4 (0=Auto, 1=Dry, 2=Cool, 3=Heat, 4=Fan) |
| `fan` | range | enum auto/low/medium/high | int 0-5 (0=Auto, 1=Quiet, 2=1, 3=2, 4=3, 5=4) |
| `vane` | range | enum auto/1-5/swing | int 0-6 (0=Auto, 1=Swing, 2..6 = pos 1..5) |
| `widevane` | range | **NOT IN PROFILE** | int 0-6 (Swing, <<, <, \|, >, >>, <>) |
| `temperature` | temperature | a separate read-only field | **writable — IS the setpoint** |
| `room_temperature` | temperature | matches | matches |

**The discovery method** — user pointed assistant at the sister project
`/home/droman42/development/mitsubishi2wb` (the ESP8266 firmware that bridges the
Mitsubishi unit to MQTT, written by `mavlyutov`). Reading the firmware README's value
mapping table (`### WB ac terms`) plus the `.ino` source for topic generation
(`mitsubishi2wb.ino` lines 121-127) + value publishing (lines 887-949) + setpoint
handler (lines 1064-1067) gave a complete, authoritative picture in one pass. The
README also defined the min/max setpoint range (defaults `min_temp = 16.0`, `max_temp
= 31.0` from `config.h`).

**Profile changes applied** (3 in one edit):
1. Drop `mode/fan/vane` enum fields from `fields[]` — mirror §2.3 / §2.9 pattern (raw
   int wire format → don't promise typed state with named values).
2. Add `set_widevane` action — was missing entirely.
3. Drop fictional `setpoint` and supply-`temperature` fields; replace with two real
   ones: `temperature` (the WB writable cell that's actually the setpoint, kept as
   field name to match the WB topic; the *label* says "setpoint") and `room_temperature`
   (the read-only sensor).

`state_field` also changed from `mode` to `power` (the actual switch that says "is the
unit on?"); `mode` is meaningful only when power is on, and the reconciler should track
power state to decide on/off.

**Action params** kept descriptive (`mode`, `speed`, `angle`, `direction`, `temp`) even
though the values are integer codes — reads cleanly in voice DSL. Voice consumer
(Irene) needs the firmware mapping table baked in to translate `"поставь охлаждение"`
→ `set_mode(mode=2)`. Schema extension for labelled enum codes proposed but **deferred**
(my lean, user accepted) — voice can carry the table client-side until the pain
recurs.

| device_id | ru | en | de | profile |
|---|---|---|---|---|
| `living_room_hvac` | Кондиционер | Air Conditioner | Klimaanlage | `hvac` |

**Cross-cutting reminder from user**: "we will address it again, as we will move HVACs
to the new class — ESP32ManagedDevice". For now `device_class: WbPassthroughDevice` per
the 2026-06-08 lock-in decision (ESP32ManagedDevice introduced when ESP32-specific
surfaces are needed, behaviourally identical until then). When the class lands, the
HVAC configs (this one + the future bedroom + children ones) all need `device_class:
ESP32ManagedDevice` + matching `config_class`. See §2.11 below.

**User response.** `accepted, but we will address it again, as we will move HVACs to
the new class - ESP32ManagedDevice`. One-line approval + scope reminder.

**Resolved-in-one-pass.** One file written + one profile rewrite + one test rewrite.
482 tests still green.

#### 1.2.4 Heating loop — `living_room_heating` (last one for the room)

Single heating loop from the **Обогрев** widget. Differs from cabinet's two loops in
two ways worth noting:

1. **Room temperature is the actual wb-msw sensor** (`wb-msw-v3_207/Temperature`), not
   a 1-wire loop-feedback sensor. The `room_temperature` field is now semantically
   accurate here (the soft mismatch flagged for cabinet's loops doesn't apply).

2. **Actuator has `"invert": true`** in the WB-UI cell's `extra` map. Likely a
   normally-closed valve where wire `"0"` = open (heating ON) and `"1"` = closed
   (heating OFF). My `mode_on` writes `"0"`, `mode_off` writes `"1"` — flipped from
   cabinet's loops. User confirmed.

| device_id | ru | en | de | profile | actuator | setpoint | room temp |
|---|---|---|---|---|---|---|---|
| `living_room_heating` | Обогрев | Heating | Heizung | `heating_loop` | `wb-gpio/EXT3_R3A2` (inverted) | `setpoints_radiator/livingroom_temp` | `wb-msw-v3_207/Temperature` |

**User response.** `Y on all` — one-line approval, no corrections.

**Resolved-in-one-pass.** One file written. 482 tests still green.

---

### 1.2.5 Living room session summary

**11 devices, room complete** (sensors deferred to global-room session):

| Profile | Count | Devices |
|---|---|---|
| `light_switch` | 4 | window_light, floor_lamp, desk_lamp, union_cabinet |
| `dimmable_light` | 1 | spots |
| `cover` | 4 | curtain_right, tulle_right, curtain_left, tulle_left |
| `hvac` | 1 | hvac (flagged for ESP32ManagedDevice migration) |
| `heating_loop` | 1 | heating |

Profile-side changes accumulated during living_room: cover.stop dropped (§2.9), hvac
profile rewritten to match firmware reality (§1.2.3).

---

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

#### 1.1.5 + 1.1.6 Cabinet covers (added retroactively during session 2)

User noticed mid-living-room session that we'd missed cabinet's covers in session 1.
Pasted the **Карниз** widget (cabinet curtain rail) JSON with 2 cells + a schedule cell
to ignore. Different Dooya motor model (`dooya_dm35eq_x_*` instead of `dooya_*` plain)
but exposes the same `Position` slider 0-100 — same `cover` profile applies. The cells
are roller blinds (`ролл`), not curtains — cabinet has rollers, living_room has
curtain+sheer pairs.

| device_id | ru | en | de | profile | WB control |
|---|---|---|---|---|---|
| `cabinet_roller_right` | Правый ролл | Roller (Right) | Rollo rechts | `cover` | `dooya_dm35eq_x_0x0105/Position` |
| `cabinet_roller_left` | Левый ролл | Roller (Left) | Rollo links | `cover` | `dooya_dm35eq_x_0x0106/Position` |

**Naming nuance.** WB cells were already disambiguated (`Правый ролл` / `Левый ролл`
with side baked in) so ru kept verbatim — no need to inject side suffix like the
living_room covers (where cells were bare `Штора` × 2 across 2 widgets and needed
disambiguation). Pattern that's emerging: if the WB cell name is already unique within
the room, keep it verbatim; if not, append the disambiguator. See §2.10 below.

**Schedule cell** (`setpoints_curtain/cabinet_permit_schedule`, type=switch) ignored
per user direction — that's a wb-rules schedule-permit flag, not a device control.
Same pattern as A2's broader "skip `*_permit_schedule` cells" rule.

**User response.** `all confirmed` — one-line approval, no corrections.

**Resolved-in-one-pass.** Two files written, cabinet now at **6 devices** total.

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

### 2.14 Catalog field projection is now FILTERED by what each device actually mirrors

**Surfaced during shower's sauna sensors (1.6.2 / shower_sauna_sensors).** The sauna
has only 2 of the `sensor_room` profile's 5 fields (temperature + humidity; no co2 /
illuminance / sound_level). User chose option (a) — use the existing profile — but
asked: "make all fields optional so that it can go from 1 to 5 fields".

**Implementation.** `_project_capability_actions` in `presentation/api/catalog.py` now
accepts a `mirrored_field_names: Optional[set[str]]` parameter. `_project_devices`
extracts the set from each device's `state_topics` keys and passes it. Fields whose
name isn't in the set are skipped. AV devices (no `state_topics` attribute at all)
pass `None`, which DISABLES filtering — they keep emitting every profile-declared
field unchanged. So:

| Device shape | `state_topics` | Filter behaviour | Catalog fields emitted |
|---|---|---|---|
| WB-passthrough, all fields mirrored | full dict | filtered, all present | all profile fields |
| WB-passthrough, partial mirror (sauna) | subset | filtered, partial | only mirrored fields |
| AV (no state_topics attribute) | absent | filter disabled | all profile fields |

**Why it matters.** Voice/UI consumers reading the catalog now see exactly what the
state endpoint will populate. No more promised fields with permanent nulls. Removes
the soft asymmetry that lived between catalog claims and state surface for sensor
devices that don't fit the canonical 5-field shape.

**Tests added** (2): `test_catalog_filters_profile_fields_to_what_device_actually_mirrors`
(sauna case — only 2 of 5 fields), `test_catalog_keeps_all_profile_fields_when_device_has_no_state_topics`
(AV regression guard). 483 → 485 passing.

### 2.13 WB-UI widgets often mix actuators with input sensors / counters / wall switches

Surfaced in entrance lighting widget (1.6.1). The widget had 7 cells:
- 2 actuator devices we authored (Споты dimmable + Подсветка шкафа switch)
- 1 motion sensor input (`wb-gpio/EXT2_IN1` "Движение")
- 1 door open sensor input (`wb-gpio/EXT2_IN4` "Открытие")
- 1 physical wall switch input (`wb-mdm3_83/Input 1` "Выключатель")
- 1 switch counter readout (`wb-mdm3_83/Input 1 counter` "Счетчик")

The 4 non-actuator cells are signals the WB UI displays for the user's awareness +
that wb-rules can react to, but they aren't things the bridge ACTUATES. User direction
this round was to skip them entirely: "but here we take only spots and Подсветка
шкафа".

**Pattern**: a WB-UI widget can mix actuators and input signals on the same panel. The
bridge's WB-passthrough configs are about ACTUATION — input signals belong in a
separate concept (perhaps a `sensor` profile for binary inputs + counters; perhaps
nothing at all, leaving wb-rules to handle them). For the importer-driven future
(§4.1), the rule of thumb is: cells whose value can change in response to a /on
publish are candidates for WB-passthrough configs; cells that only ever publish their
own state are skipped (or routed to a different model).

### 2.12 Dooya position semantics differ by motor model

**Surfaced retroactively during bedroom session.** User caught this watching the
authoring log: the cabinet uses `dooya_dm35eq_x_*` motors where `position=0` means
**fully open**, `position=100` means **fully closed**. The living_room and bedroom use
plain `dooya_0x01xx` motors with the OPPOSITE convention (`0=closed, 100=open`).

The 4 living_room covers and 2 bedroom covers were authored correctly (open writes
"100"). The 2 cabinet rollers were authored **wrong** (open writes "100" → actually
closes the roller). Fixed both: cabinet rollers now have `open: "0", close: "100"`.

Per-device wire semantics for `Position`:

| Motor family | `value=0` | `value=100` |
|---|---|---|
| `dooya_0x01XX` (living_room, bedroom) | fully closed | fully open |
| `dooya_dm35eq_x_*` (cabinet) | **fully open** | **fully closed** |

**Limitation NOT fixed** in this pass: the `set_position(pct)` action passes `pct`
straight through to the WB slider. For the inverted cabinet motors, voice asking "set
to 25%" intends "25% open" but publishing `25` to the cabinet's slider means "25% of
motor travel" = "75% open". `open` and `close` actions work because each device's
config maps them to the correct wire value; `set_position(50)` works *by coincidence*
because 50% is the midpoint either way. Any other percentage diverges. Documented as a
follow-up — see §4.9 for the structural fix path.

**Lesson.** The Dooya model family appears in the WB topic name (`dooya_0x01XX` vs
`dooya_dm35eq_x_*`). Future cover devices need a quick "which motor family is this?"
check before drafting open/close values. An importer reading
`/etc/wb-webui.conf` could look up the WB device's `meta` block (or a known
model→semantics table) and propose the right defaults automatically.

### 2.11 HVAC configs are flagged for `device_class` migration to `ESP32ManagedDevice`

Per the 2026-06-08 lock-in decision (see action_plan.md §P3.7 #19 and the journal entry
of that date): the 3 HVAC units in this house WILL be hosted on a new
`ESP32ManagedDevice` class, behaviourally identical to `WbPassthroughDevice` at v1 ship,
but designed to grow ESP32-specific surfaces (provisioning state, OTA progress, NVS
identity, sleep/wake telemetry, firmware version). That class doesn't exist yet — its
introduction was tied to "when HVAC bulk configs are written".

**Current state.** First HVAC config (`living_room_hvac`) authored with
`device_class: WbPassthroughDevice`. User flagged this for revisit during authoring.

**Migration owed.** When `ESP32ManagedDevice` is introduced as a code change:
- Add the class in `infrastructure/devices/esp32_managed/driver.py` (subclass of
  `WbPassthroughDevice` for v1, override-points reserved for ESP32-specific telemetry).
- Add the matching `ESP32ManagedDeviceConfig` model.
- Register the entry point.
- Update all HVAC device configs (`living_room_hvac`, future `bedroom_hvac`,
  `children_room_hvac`) — change `device_class` + `config_class` only; everything else
  stays.

Doing the migration in one pass (when all 3 HVAC configs exist) makes more sense than
introducing the class for a single device.

### 2.10 Naming pattern for ru: WB-verbatim when unambiguous, disambiguate when not

Living room had `Штора` × 2 + `Тюль` × 2 across two widgets — bare cell names
identical, side context lived only in widget name. Bridge had to inject side suffix
(`Штора справа` etc.) so the catalog/voice could distinguish them.

Cabinet had `Правый ролл` + `Левый ролл` in one widget — cells already disambiguated.
Bridge kept ru verbatim.

**Rule.** If `cell.name` is unique within the room's authoring scope, keep verbatim.
If multiple cells share a name (typically across widgets in the same room), append
the natural disambiguator (side, layer, slave-id, whatever the room's structure
provides). Encoded as a per-room judgment call — no rigid convention forced.

### 2.9 `cover.stop` dropped from the profile

**The problem.** The `cover` profile originally declared four actions: `open` / `close` /
`set_position` / `stop`. Dooya position sliders have NO native stop control — they
just move toward whatever position you write. There's a possible "fake stop"
implementation (re-publish the current mirrored position to halt motion mid-travel)
but no driver helper for it yet.

**Three options offered.**
- (a) Omit `stop` from device configs only; profile still claims it; voice gets
  `action_not_supported` if invoked. Soft contract lie.
- (b) Drop `stop` from the profile entirely. Truthful catalog.
- (c) Defer — implement `stop` later as "re-write mirrored position". Helper needed.

**User chose (b).** Cleanest contract: don't promise what we can't deliver. If voice
ever needs stop-mid-motion, switch to (c) (add the helper, restore profile entry).

Same shape as the §2.3 `heating_loop.mode` decision: keep the catalog truthful.

### 2.8 Subfolder name = bridge room_id (NOT WB-UI dashboard id)

**Surfaced mid-session 2.** The original action_plan A1 paragraph said
"sub-directory names are the WB UI dashboard ids" (e.g. `livingroom/`, `children/`).
This conflicts with §P3.7 #21's decision to KEEP legacy bridge room_ids (`living_room`,
`children_room`) and the user's broader pattern of using room_id as the prefix for
device_ids. Net result was three different names for the same concept:

- room_id: `living_room`
- subfolder I initially wrote: `livingroom` ← inconsistent
- device_id prefix: `living_room_`

**Fixed.** Subfolder renamed `livingroom/ → living_room/`. Action_plan paragraph
rewritten to read "Sub-directory name = the bridge's room_id (matches `rooms.json`
exactly), NOT the WB-UI dashboard id where they differ." The same rule will apply when
authoring `children_room/`, `shower/`, etc. Aggregate-device configs (when authored)
land in `wb-devices/global/`.

**Why it almost slipped through.** Assistant followed the older A1 paragraph
literally without cross-checking against the user's other naming decisions. User
caught it on the first room where the room_id ≠ WB-dashboard-id.

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

### 3.7 rooms.json `devices` list silently drifted from device configs

**Surfaced mid-children_room (session 3).** User asked "did we update rooms.json with new
registered devices?" — answer: no, not since the slice. **19 devices** had been authored
between slice and children_room without anyone updating rooms.json's per-room `devices`
field. The catalog's room → devices projection reads from RoomManager (rooms.json), so
all 19 would have been invisible to voice/UI as room members despite existing with
`room: <id>` set on the device configs.

**Compounding problem**: AV configs (the 13 pre-§P3.7 devices in
`backend/config/devices/*.json`) **have no `room` field set at all** — their room
membership lives ONLY in rooms.json. So today the system has TWO sources of truth:

- **WB-passthrough side**: `room` field on the device config (forward direction)
- **AV side**: membership only in rooms.json (reverse direction)

The two sources weren't kept in sync because no test enforced it. Added
`test_rooms_json_devices_match_wb_passthrough_configs` to `test_rooms_bootstrap.py`
that walks every WB-passthrough config and asserts its `device_id` appears in the
correct room's `devices` list. Fails loud the moment they drift. Test count 482 → 483.

**Architectural question logged for later** (see §4.8): should we make device-config
`room` the single source of truth and have RoomManager populate `devices` at load
time? Would eliminate the drift class entirely but requires backfilling `room` on
the 13 AV configs.

### 3.6 Stale doc paragraphs are a real footgun — cross-check before quoting

The A1 paragraph saying "subfolder = WB dashboard id" was authored 2026-06-06 and
became outdated 2026-06-08 when #21 settled on the legacy room_id preservation. The
assistant didn't reread #21's outcome against the A1 paragraph before writing the
first `livingroom/` config — it just followed the older line. User caught it. Lesson:
when about to follow a documented convention, sanity-check against later decisions in
the same document. (Or — better — keep one document as the source of truth and remove
the stale claim, which is what this fix did.)

### 3.5 Raw WB-UI JSON paste massively reduces friction (vs. A2-fragment summaries)

When the user pasted the living_room **Освещение** widget JSON directly from
`/etc/wb-webui.conf`, 5 lights authored in **one round-trip** (one assistant proposal,
one user line `1., 2. all ok, 3. yes, 4. yes`). Compare with cabinet's heating loops:
2 devices, 3 round-trips, multiple corrections, A2 had to be repaired mid-conversation.

The qualitative difference is striking: with raw JSON the assistant can read every
cell's `id` (= `slave/control`), `name` (ru label), and `type` (switch/range/...)
directly. Pairing detection (K3 + Channel 3 → dimmable_light) is mechanical. Profile
proposal is rule-based. The only judgment calls left are:
- en/de translations
- device_id naming convention (set once per room/session)
- edge-case naming ("is Юнион a brand?")

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

### 4.9 ~~Per-device `invert` flag for cover position~~ — **DONE 2026-06-08**

Landed as `StateTopicSpec.invert: bool` (per-field flag). Driver applies `100 - value`
symmetrically on outbound publish (just before MQTT publish, via
`_invert_wire_payload`) and inbound mirror (just after type coercion, via
`_apply_inversion`). Cabinet roller configs reverted to natural-sense
(`open: "100"`, `close: "0"`, set_position takes natural pct) plus `invert: true` on
the position state_topic. The driver hides the device-family quirk; configs + voice +
state surface all speak the natural "100 = open" convention. The hand-swapped
open/close workaround from §2.12 is gone — replaced by data, not code-side gymnastics.
See action_plan_journal.md "Cover `invert_position` flag" entry for full details.

### 4.8 ~~Eliminate the rooms.json `devices` duplication~~ — **DONE 2026-06-08**

Landed as a focused post-#23 refactor (5 phases A–E in one commit). Net result:
`device.config.room` is the single source of truth; `DevicePort.get_room()` is the
hexagon-clean domain contract; `RoomManager.reload()` derives `room.devices` at load
time. rooms.json carries only metadata. The drift-guard test (§3.7) was replaced by
forward-direction `test_every_device_config_declares_a_known_room`. The dormant
`ScenarioDefinition.room_id` invariant got activated too — `ScenarioManager` now
hard-fails bootstrap if any scenario's devices report a different room than the
scenario declares. See action_plan_journal.md "Room-architecture refactor" entry for
the full breakdown.

### 4.7 First room per category pays the design cost; rest are clones

Cabinet's heating loops surfaced the `heating_loop.mode` profile question. Living_room's
HVAC surfaced the bigger HVAC profile rewrite. Living_room's covers surfaced the
`cover.stop` question. ONCE each profile is settled, subsequent rooms with the same
category are mechanical clones — children_room reused all of living_room's settled
shapes with zero new Q&A. Implication for any future packaging: profile authoring is
a one-time cost per fixture kind; per-room device configs are the volume.

### 4.6 Reading sister-firmware code beats inferring from MQTT shape alone

The HVAC's `mitsubishi2wb.ino` documented the exact `int → meaning` mappings for
mode/fan/vane/widevane in its README, plus min/max temp defaults, plus the publish
semantics for every cell. Without that source the assistant would have guessed
(possibly wrong) at the value codes, the setpoint semantics (is `temperature` writable
or read-only?), and the safe range. Pattern: when authoring a device backed by a known
firmware source, READ THE FIRMWARE FIRST. Treat it as the authoritative wire-format
spec.

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

- **2026-06-08** — Sessions 4–7 (rapid pace): bedroom (11) + kitchen (4) + entrance (3)
  + hall (3) + shower (6 incl. sauna sensors) + bathroom (5) + wardrobe (2) =
  **34 devices added** across 7 rooms in one continuous run. Profile changes: cover
  drops `stop`, hvac rewritten end-to-end against firmware, heating_loop drops `mode`
  field. Catalog gains state_topics-driven field filtering (§2.14, triggered by the
  sauna's partial sensor_room mirror). Drift-guard added (§3.7). Per-device-class
  Dooya inversion fix for cabinet rollers (§2.12). 485 passing. **#23 COMPLETE**:
  57 devices across all 10 physical rooms. `global` (#22) and sensor backlog
  (most rooms' wb-msw multi-sensors) remain.
- **2026-06-08** — Session 3: children_room (6 devices: lights × 4 + hvac + heating).
  Mid-session user caught rooms.json drift (19 missing); fixed + added drift-guard
  test. Committed `ecc5759`. 483 passing.
- **2026-06-08** — Session 2: living_room. 11 devices (lights × 5 + covers × 4 +
  hvac + heating). HVAC profile reworked from sister-firmware
  `/home/droman42/development/mitsubishi2wb` (see §1.2.3 / §4.6). cover.stop dropped
  (§2.9). Subfolder convention `wb-devices/<room>/` correction (§2.8). Committed
  `edc345f`. 482 passing.
- **2026-06-08** — Session 1: cabinet (3 new devices + heating_loop profile fix).
  Committed `913cbf9`. 482 tests passing. Sensors deferred. User called `pause`;
  living_room next when `continue` arrives.
