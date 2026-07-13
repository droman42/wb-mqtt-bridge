# Voice integration — agreed contract (bridge ↔ Irene)

**Status:** AGREED 2026-06-06; **amended 2026-06-15** to fold in the value-label translation layer
(§P3.7 #26, implemented 2026-06-09 — see "Value-labels for controllable enum fields" in §B). Reconciled
in the bridge session with the user. Originated as a draft from the **Irene voice-assistant** design
session (sister repo `locveil-voice`, task ARCH-7); see prior revision in git history for the
open-question form. This is the contract Irene's ARCH-8 implementation builds against
(`locveil-voice/docs/design/mqtt_integration.md` §10 — blocked on it).

> Same author, two projects. The strategic decision is:
> **locveil-bridge becomes the single authoritative device catalog + actuation backend for the
> whole house — native Wirenboard gear *and* the AV devices it already bridges — and Irene
> talks only to the bridge.** Irene owns voice; the bridge owns devices and all
> MQTT/home-automation conventions. wb-rules retains all rule/automation logic on the
> controller (unchanged); the bridge MIRRORS native control state by subscribing to MQTT value
> topics. Two writers (bridge + wb-rules), one truth (the broker).

---

## 0. Why this lands on the bridge

The real deployment is one Wirenboard 7 controller that is both the MQTT broker and the home.
Its broker carries the whole house under `/devices/{dev}/controls/{ctrl}`:

- **Native WB gear** (managed by `wb-mqtt-serial` + `wb-rules`, *not* in this bridge today):
  lights & dimmers (`wb-mr6c`, `wb-mdm3`, `wb-mrgbw-d`), curtains (`dooya`), HVAC, room
  multi-sensors (`wb-msw-v3`), metering, leak.
- **This bridge's virtual devices** (AV gear without native WB support): TVs, Apple TVs,
  eMotiva.

The voice assistant rejected talking to the raw broker directly (it would re-implement the
device/capability/room model this bridge already has, against a semantically poor topic tree).
Instead it consumes **this bridge** as the one normalized, capability-mapped, room-aware
authority. That makes the voice side thin and convention-agnostic.

## The contract, in three pillars

- **A. Canonical action endpoint** — callers speak `capability.action(params)`, not native
  command names. The capability→native translation already exists internally (the reconciler);
  this exposes it on the input path.
- **B. Voice-friendly catalog read surface** — devices + rooms + per-device capabilities +
  param schemas, **all locales**, pullable at startup with an MQTT dirty-nudge for refresh.
- **C. Onboard the native WB devices** — the bulk of the work; this bridge currently only
  models the AV gear. Includes a generic WB-passthrough driver, capability adapters for
  composite controls, and the wb-rules / bridge mirror boundary.

---

## A. Canonical action endpoint

**Path & DTO** — mirrors the existing `POST /devices/{id}/action` shape, swapping native
command name for canonical `(capability, action)`:

```
POST /devices/{device_id}/canonical
  body: { "capability": "volume", "action": "set", "params": { "level": 50 } }
  200:  { "success": true,
          "device_id": "lg_tv", "capability": "volume", "action": "set",
          "state": { ... },        // post-action device state
          "error": null }
  4xx/5xx: { "success": false, "device_id": "lg_tv",
             "error": { "code": "param_invalid", "message": "...",
                        "field": "level", "reason": "out_of_range" } }
```

Implementation: thin façade over `perform_action`. Resolve `(capability, action)` through the
existing capability map → native command + `param_map` rename → the current action path.

**Error code enum.** Body always carries `error.code`; HTTP status mirrors it:

| Code | HTTP | Meaning |
|---|---|---|
| `device_not_found` | 404 | `device_id` unknown to the bridge |
| `capability_not_supported` | 404 | device doesn't expose this capability |
| `action_not_supported` | 404 | capability exists but not this action |
| `param_invalid` | 400 | with `field` + `reason` (missing / out_of_range / wrong_type / unknown_choice) |
| `device_unreachable` | 503 | transient; Irene can say "try again" |
| `internal_error` | 500 | catch-all |

**Write semantics — synchronous with timeout.** After the bridge publishes the underlying
command, it waits for the device's value-topic echo (default **500 ms**, configurable per
driver) before returning. The response contains the post-action state. On timeout →
`device_unreachable`. `wb-mqtt-serial`'s per-control `…/meta/error` topics are the
deterministic complement: subscribing to them makes "device offline" detection immediate
rather than timeout-bound (verified A3 — payload is combinable single chars `r` / `w` / `p`,
retained when present, absent when healthy). Long-running actions (covers / curtains take seconds) can declare a larger
timeout at the driver level.

## B. Catalog read surface

**`GET /system/catalog`** — flat capability-shaped projection of the whole house. NOT the
Layer-3 layout manifest (which is UI-oriented: sliders, buttons, panels). The catalog is the
stable read contract for any non-UI consumer (Irene first, but HA / scenes / future
automations get the same view). Shape:

```json
{
  "version": "<content-hash>",
  "rooms": [
    {"id": "living_room", "names": {"ru": "Гостиная",  "en": "Living Room"},
     "devices": ["lg_tv", "appletv_living", "wb-mdm3_83"]},
    {"id": "global",      "names": {"ru": "Весь дом",  "en": "Whole House"},
     "devices": ["all_lights"]}
  ],
  "devices": [
    {"id": "all_lights", "names": {"ru": "Весь свет", "en": "All Lights"},
     "class": "WbScene", "room": "global",
     "capabilities": [ {"name": "power", "actions": [{"name": "on"}, {"name": "off"}]} ]},
    {"id": "lg_tv", "names": {"ru": "Телевизор LG", "en": "LG TV"},
     "class": "LgTv", "room": "living_room",
     "capabilities": [
       {"name": "power",  "actions": [{"name": "on"}, {"name": "off"}]},
       {"name": "volume", "actions": [
         {"name": "set",  "params": [{"name": "level", "type": "int",
                                      "min": 0, "max": 100, "required": true,
                                      "labels": {"ru": "уровень", "en": "level"}}]},
         {"name": "up"}, {"name": "down"}, {"name": "mute"}]}]},
    {"id": "wb-msw-v3_207", "names": {"ru": "Сенсоры гостиной", "en": "Living Room Sensors"},
     "class": "WbMswSensors", "room": "living_room",
     "capabilities": [
       {"name": "sensor",
        "fields": [
          {"name": "temperature", "type": "float", "unit": "°C",
           "labels": {"ru": "температура", "en": "temperature"}},
          {"name": "humidity",    "type": "float", "unit": "%"},
          {"name": "co2",         "type": "int",   "unit": "ppm"}]}]}
  ]
}
```

**All locales for both rooms and devices.** Irene knows the language of the incoming request
and picks the matching label. `device_name` (currently single string) widens to
`names: {ru, en, …}` — **one-shot migration of the existing AV configs** as part of this
work; no backwards-compat shim accepting both forms.

**Sensor capability shape: one `sensor` capability with read-only `fields`.** No actions.
Voice resolves "какая температура в гостиной" → room → device with `sensor` capability →
field `temperature` → read from the bridge's state cache.

**Value-labels for controllable enum fields** *(§P3.7 #26, added 2026-06-09 — postdates the original
2026-06-06 agreement; folded into the contract 2026-06-15).* A controllable enum/choice field projects
its `values` as a list of **`{wire, canonical, labels}`** triplets instead of bare strings, e.g. an
HVAC `mode` field:

```json
{"name": "mode",
 "values": [
   {"wire": "0", "canonical": "off",  "labels": {"ru": "выключено",  "en": "off"}},
   {"wire": "2", "canonical": "cool", "labels": {"ru": "охлаждение", "en": "cool"}},
   {"wire": "3", "canonical": "heat", "labels": {"ru": "обогрев",    "en": "heat"}}]}
```

- **`wire`** — the raw MQTT payload on the bus (authoritative there; informational to API consumers).
- **`canonical`** — the language-neutral action identifier + `state.mirrored` key. **Irene/UI post this**
  in the canonical command; the bridge driver translates `canonical`↔`wire` symmetrically.
- **`labels`** — localized surface strings. **Irene matches the utterance against `labels` in the active
  locale**; the UI renders them as dropdown options. The match → `canonical` → posted back.

Keeps Irene convention-blind (it never sees `wire`) and gives one autodiscoverable enum vocabulary for
both voice and UI. Implemented as `ValueLabel` (`domain/devices/config.py`); `CapabilityField.values`
widened `List[str]`→`List[ValueLabel]`, projected by `GET /system/catalog` as `CatalogValueLabel`.

**One device, one room** (`room: Optional[str]`). Whole-house / group controls are modeled as
**aggregate devices in the `global` room** (e.g. an `all_lights` device whose `power.off`
wb-rules maps to the real per-light fan-out). "Выключи свет везде" resolves to that aggregate
device and is a **single** canonical call — Irene does NOT iterate rooms or synthesize a group;
she relies on the aggregate device being present in the catalog. The bridge (with wb-rules)
owns the actual fan-out. See C.5.

**Refresh nudge**: retained `bridge/catalog/version` (content hash) bumped on `/reload` or
config change. Irene resubscribes when it sees a new version.

## C. Onboard the native Wirenboard devices

### C.1 Boundary: rules stay on the controller, bridge mirrors

wb-rules / wb-mqtt-serial keep all rule/automation logic. The bridge does not read or care
about rules. For each native control the bridge represents, it:

- **Writes** to `…/controls/{ctrl}/on` when the canonical endpoint is called.
- **Subscribes** to `…/controls/{ctrl}` (value topic) and to the matching per-control
  `…/controls/{ctrl}/meta/error` (Wirenboard MQTT convention; combinable single-char codes
  `r` / `w` / `p`, retained when present, absent when healthy — see action_plan §P3.7 A3 for
  the verified shape). Every value change — whether the bridge wrote it, wb-rules wrote it,
  HomeUI wrote it, or a physical switch flipped it — flows into `BaseDevice.update_state`
  (the existing state-sync chokepoint).

**Loop guard.** For bridge-OWNED virtual devices, `update_state` triggers a callback that
publishes back to the virtual-device value topic. For WB-passthrough devices the bridge is
NOT the owner — the chokepoint must NOT re-publish, or we feedback-loop with the real device.
The WB-passthrough driver registers only the persist + SSE/UI callbacks, not the WB-publish
one. This is the one structural change to the state-sync wiring; the chokepoint contract
itself is unchanged.

### C.2 Generic WB-passthrough driver

One driver class, fully data-driven. **Adding a WB device = a config file, not code.**
Per-command config declares the topic and param types explicitly — we deliberately do NOT
introspect `…/meta/type` at runtime (more boilerplate, never wrong, matches the existing AV
config style):

```json
{
  "device_id": "wb-mdm3_83",
  "device_class": "WbPassthroughDevice",
  "names": {"ru": "Свет в гостиной", "en": "Living Room Light"},
  "room": "living_room",
  "commands": {
    "power_on":       {"topic": "/devices/wb-mdm3_83/controls/Channel 1/on", "value": "1"},
    "power_off":      {"topic": "/devices/wb-mdm3_83/controls/Channel 1/on", "value": "0"},
    "set_brightness": {"topic": "/devices/wb-mdm3_83/controls/Channel 1/on",
                       "params": [{"name": "level", "type": "int",
                                   "min": 0, "max": 100, "required": true}]}
  },
  "state_topics": {
    "brightness": "/devices/wb-mdm3_83/controls/Channel 1",
    "power":      "/devices/wb-mdm3_83/controls/Channel 1"
  }
}
```

Placement per hexagonal LAW: `infrastructure/devices/wb_passthrough/`. Tests follow
`device_test_pattern` (real-driver `execute_action`, not mocks — see
`mock-tests-miss-driver-bugs`).

### C.3 Composition layer ABOVE the driver

Composite WB controls — RGB (one control encoded as `"R;G;B"`), HVAC (mode + setpoint + fan,
often across sub-devices) — are handled by a **capability-adapter layer above the driver**,
NOT inside the driver. One canonical action resolves to one or more driver-level command
invocations. The driver stays dumb: one config row = one WB control write.

This layer lives next to the existing reconciler; it's the natural extension of the
canonical→native resolution, just one-to-many instead of one-to-one. Per-capability adapters
sit in `infrastructure/capabilities/` (or alongside the reconciler — placement settled in
implementation).

### C.4 Canonical capability vocabulary

Current vocabulary is AV-flavoured (power / volume / input / playback / menu). Extending for
native:

- `power` — `on` / `off` (already exists)
- `brightness` — `set(level)` / `up` / `down`
- `color` — `set(rgb)` — composed (RGB string)
- `cover` — `open` / `close` / `stop` / `set_position(pct)`
- `climate` — `set_mode(mode)` / `set_setpoint(temp)` / `set_fan(speed)` — composed
- `sensor` — read-only `fields` (temperature / humidity / illuminance / co2 / leak / …)

We align with Home Assistant's capability namespace where it cleanly fits, but this bridge's
config is the source of truth — no automatic mapping to HA.

### C.5 Rooms

- **Authoring source**: bootstrap `rooms.json` by importing the WB HomeUI's room→device
  grouping (config file location identified during implementation; one-shot, not manual).
- **One device, one room** (`room: Optional[str]`) — a device belongs to exactly one room.
  Tightened from an earlier multi-room draft on 2026-06-06.
- **`global` is a regular room that holds whole-house AGGREGATE devices** (e.g. `all_lights`,
  `all_blinds`) — the bridge/wb-rules implements each aggregate's fan-out to the real devices.
  "Выключи свет везде" resolves to the `all_lights` aggregate device and is a **single**
  canonical call; Irene does NOT iterate rooms or synthesize a cross-room group. So whole-house
  group control is just normal per-device actuation against an aggregate device — the bridge
  must **provide** these aggregate devices in `global` for the group commands voice should support.
- **Directory layout** for WB-passthrough configs: `config/devices/wb-devices/<room>/<device_id>.json`
  (one config file per logical device, grouped by its room). Existing AV configs stay
  flat at `config/devices/*.json`. The config scanner recurses into subdirectories.

### C.6 Devices to onboard

| Class            | Live examples                            | Capabilities              |
|------------------|------------------------------------------|---------------------------|
| relay/light      | wb-mr6c_47/51/52/58, wb-mr6cu_31         | power                     |
| dimmer           | wb-mdm3_83/87/95                         | power, brightness         |
| RGB dimmer       | wb-mrgbw-d-fw3_10/11/238                 | power, brightness, color  |
| curtain/blind    | dooya_0x0101…0108, dooya_dm35eq_x_…      | cover                     |
| HVAC             | hvac_livingroom/bedroom/children + vdevs | climate                   |
| sensor           | wb-msw-v3_*, wb-w1, wb-map3e             | sensor (read-only)        |

The `wb-msw-v3_*` units are already modeled in this bridge as IR blasters
(`WirenboardIRDevice`). The sensor side becomes a separate device entry (or a unified config
that exposes both `sensor` and IR-driven capabilities) — settled during implementation.

---

## What Irene will NOT ask of the bridge

To keep the boundary clean:

- No voice / NLU / intent logic in the bridge — Irene owns all of that.
- No Irene-specific endpoints beyond the generic canonical-action + catalog surfaces — they're
  useful to any non-UI caller.
- Irene does not publish to raw WB control topics or hold native command names — it speaks
  canonical to the bridge only.

## Hexagonal layering

Per the standing LAW (`hexagonal-law-for-all-changes`), every piece of this work preserves
the layering:

- WB-passthrough driver → `infrastructure/devices/wb_passthrough/`
- Canonical endpoint → application / API layer (existing FastAPI), calling into the domain
  service via the existing `perform_action`.
- Catalog endpoint → application / API layer, reading the existing capability + config +
  rooms registry.
- Capability adapters (composition) → infrastructure capabilities layer, next to the
  reconciler.
- No domain imports of infrastructure; no config bleed-through into the domain.

## Sequencing

**Vertical slice first** — prove the whole stack against one live voice command before bulk
onboarding:

1. WB-passthrough driver skeleton (single `wb-mr6c` relay channel).
2. One device config + capability map + room entry (children's room).
3. Canonical endpoint live + minimal `/system/catalog` (just this device).
4. `device_name → names` migration (one-shot across existing AV configs).
5. Irene-side: "включи свет в детской" hits the canonical endpoint end-to-end and the light
   responds with the post-state echo arriving inside the 500 ms budget.

Then bulk-onboard the remaining native devices (per the table) + widen capability adapters
(RGB, HVAC) + populate the `global` room with the **aggregate devices** (`all_lights`, etc.,
each backed by a wb-rules scene/group) + import `rooms.json` from the WB HomeUI config.

## Deferred to v2

- **Additional whole-house aggregate devices**: v1 ships only the aggregate `global` devices
  the supported group commands need (e.g. `all_lights`). More group/scene aggregates (per-floor,
  `all_blinds`, scenes) are added as the voice command set grows — each is just another device
  in `global`, no new endpoint. (There is no client-side fan-out to optimize: every group control
  is a single canonical call against an aggregate device.)

---

_With the contract agreed, the action plan (`docs/action_plan.md`) is updated separately to
schedule the work. This document is the bridge ↔ Irene reference; Irene's ARCH-8
implementation plan (`locveil-voice/docs/design/mqtt_integration.md` §10) builds against it._
