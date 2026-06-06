# Voice integration — contract draft (from the Irene side)

**Status:** DRAFT, written 2026-06-06 from the **Irene voice-assistant** design session (sister repo
`wb-mqtt-voice`, task ARCH-7). This is a **request for discussion**, not a spec — it states what the
voice assistant needs *from* wb-mqtt-bridge, so the bridge session can decide feasibility, placement,
and shape. The Irene-side design is in `wb-mqtt-voice/docs/design/mqtt_integration.md`.

> Same author, two projects. The strategic decision (made on the Irene side, with the user) is:
> **wb-mqtt-bridge becomes the single authoritative device catalog + actuation backend for the whole
> house — native Wirenboard gear *and* the AV devices it already bridges — and Irene talks only to the
> bridge.** Irene owns voice; the bridge owns devices and all MQTT/home-automation conventions.

---

## 0. Why this lands on the bridge

The real deployment is one Wirenboard 7 controller that is both the MQTT broker and the home. Its
broker carries the whole house under `/devices/{dev}/controls/{ctrl}`:

- **Native WB gear** (managed by `wb-mqtt-serial` + `wb-rules`, *not* in this bridge today): lights &
  dimmers (`wb-mr6c`, `wb-mdm3`, `wb-mrgbw-d`), curtains (`dooya`), HVAC, room multi-sensors
  (`wb-msw-v3`), metering, leak.
- **This bridge's virtual devices** (AV gear without native WB support): TVs, Apple TVs, eMotiva.

The voice assistant rejected talking to the raw broker directly (it would re-implement the
device/capability/room model this bridge already has, against a semantically poor topic tree). Instead
it consumes **this bridge** as the one normalized, capability-mapped, room-aware authority. That makes
the voice side thin and convention-agnostic — but it asks three things of the bridge.

## The ask, in one list

- **A. A canonical action endpoint** — so callers speak `capability.action(params)`, not native
  command names (the capability→native translation already exists internally; expose it on the input
  path).
- **B. A voice-friendly catalog read surface** — devices + rooms (with ru names) + per-device
  capabilities + param schemas, pullable at startup.
- **C. Onboard the native WB devices** — the bulk of the work; this bridge currently only models the
  AV gear.

---

## A. Canonical action endpoint (new)

**Today:** `POST /devices/{device_id}/action {action, params}` takes a **native** command name
(`set_volume`, `power_on`, …). The capability map (`config/capabilities/…`, canonical
`volume.set` → native `set_volume`) is **internal-only** — used for UI/scenario rendering, not exposed
on the action input path.

**Why voice wants canonical:** "сделай громче" should map the *same way* for a TV, a processor, and an
Apple TV — to `volume.up` — regardless of each device's native command name. A canonical vocabulary
(`power`, `volume`, `input`, `playback`, `menu`, …) keeps the voice NLU per-**capability** (uniform)
instead of per-device. The bridge already owns canonical↔native (the reconciler); voice just needs it
on the wire.

**Proposed shape** (illustrative — the bridge session decides the real path/DTO):

```
POST /devices/{device_id}/capability/{capability}/{action}
  body: { "params": { "level": 50 } }
  200:  { "success": true, "device_id": "...", "capability": "volume",
          "action": "set", "state": { ... }, "error": null }
```

Internally: resolve `(device, capability, action)` through the existing capability map → native
command + param rename (`param_map`) → the current action path. Essentially a thin canonical façade
over `perform_action`.

**Error semantics matter for spoken feedback.** Irene speaks the result, so it needs to distinguish:
device/capability/action unknown · param out of range/missing · device unreachable · success. A
structured `error` (code + message) beats a bare 500.

Open: device-vs-room addressing (does voice always resolve to a `device_id` first, or is there a
room-scoped command like "turn off the living room"?). Irene can resolve room→device itself from the
catalog (B), so a per-device endpoint is sufficient for v1; room/group actions could come later.

## B. Catalog read surface for voice

Irene pulls a catalog on startup and builds an in-memory device/room/capability model that drives NLU,
entity resolution, and parameter clarification. It needs, per the **capability** view (to match the
canonical write side):

- **device list** — id, display name, class/type, which **room** it's in.
- **rooms** — `GET /room/list` already gives `{room_id, names:{ru,en,de}, devices:[…]}`. The **ru
  name is the resolution key** ("в гостиной" → `Гостиная` → `living_room`). Confirm this is the
  intended matching key.
- **per-device capabilities + actions** — which canonical capabilities a device supports.
- **per-action param schema** — name, type, range/min/max, choices, required, and a **human (ideally
  ru) label/description** — used to ask "какую яркость?" and validate before publish.

**Question for the session:** does the existing **Layer-3 layout/capability manifest**
(`GET /devices/{id}/layout`) already expose enough (capabilities + param schema + labels) for voice,
or is a **dedicated, stable `/voice/catalog`** (or `/system/catalog`) endpoint cleaner — one call
returning the whole house in the shape voice wants, decoupled from UI-layout concerns? Irene prefers
one stable read contract it can depend on.

**Refresh (optional):** Irene pulls on startup. For live changes, an MQTT nudge it can subscribe to
(e.g. retained `irene/catalog/dirty` bumped on `POST /reload`/config change) lets it re-pull without
polling. Nice-to-have, not v1-blocking.

## C. Onboard the native Wirenboard devices

This is the largest piece and is entirely bridge-side. Today the bridge models only the AV gear; the
native WB devices (the bulk of the house) are absent. To become the single authority it must model
them. Observed native classes that need onboarding:

| Device class | Examples (live) | Capabilities needed |
|---|---|---|
| relay/light | `wb-mr6c_47/51/52/58` ('Light'), `wb-mr6cu_31` ('Heat') | `power` (on/off per channel) |
| dimmer | `wb-mdm3_83/87/95` | `power`, `brightness` (range) |
| RGB dimmer | `wb-mrgbw-d-fw3_10/11/238` ('Light') | `power`, `brightness`, `color` |
| curtain/blind | `dooya_0x0101…0108`, `dooya_dm35eq_x_…` | `cover` (open/close/stop/position) |
| HVAC | `hvac_livingroom/bedroom/children`, setpoint vdevs | `climate` (mode, setpoint) |
| sensor | `wb-msw-v3_*` (per room), `wb-w1`, `wb-map3e` | read-only state (for "is it warm?") |

**The gap:** the existing `WirenboardIRDevice` driver is IR-blaster-specific (ROM-slot topics). Native
WB controls are plain `/devices/{dev}/controls/{ctrl}` read/write topics. So this likely needs **a new
generic WB-passthrough driver class** (a device whose commands map directly to publishing on a native
WB control topic, with `meta/type`-derived param types), plus:

- a `config/devices/{id}.json` per native device (commands → native WB control topics);
- `config/capabilities/{classes|devices}/*.json` mapping those to canonical capabilities;
- room assignment in `config/rooms.json` (the native devices' room membership — the controller's
  HomeUI room grouping is the human source; it is **not** in the MQTT tree, so it must be authored
  here).

This is exactly the structured modeling the bridge is built for, but it's real work and the bottleneck
for end-to-end voice control. Scope it in `docs/action_plan.md`.

---

## What Irene will NOT ask of the bridge

To keep the boundary clean:

- No voice/NLU/intent logic in the bridge — Irene owns all of that.
- No Irene-specific endpoints beyond the generic canonical-action + catalog surfaces above (those are
  useful to any non-UI caller, e.g. HA, automations).
- Irene does not publish to raw WB control topics or hold native command names — it speaks canonical
  to the bridge only.

## Open questions for the bridge session

1. **A — canonical endpoint:** path/DTO; reuse of the capability reconciler on the input path;
   structured error codes for spoken feedback.
2. **B — catalog read:** is the Layer-3 layout manifest enough, or add a dedicated `/voice/catalog`?
   Is the `rooms.json` ru name the resolution key? Optional MQTT catalog-dirty nudge.
3. **C — native onboarding:** generic WB-passthrough driver design; capability maps for
   relay/dimmer/RGB/curtain/HVAC; room authoring source; sensor read-state exposure.
4. **Sequencing:** a thin vertical slice first (one room, one light, end-to-end) before bulk
   onboarding, so the contract is proven against a live voice command early.

---

_Reconcile this draft in the bridge session, then the agreed contract feeds Irene's ARCH-8
implementation (`wb-mqtt-voice/docs/design/mqtt_integration.md` §10) — which is blocked on it._
