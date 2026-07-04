# Canonical-first actuation & the scenario proxy

**Status:** DECIDED 2026-07-04 (interactive design session, SCN-4). This document is the
design deliverable of **SCN-4** ("Scenario ↔ Wirenboard integration — mandatory design
discussion → clean rebuild"). The discussion outgrew the original question — the decisions
below cover not just the scenario↔WB representation but the system's target actuation
architecture. Implementation is filed separately: **SCN-6** (phase 1), **SCN-7** (phase 2);
the param-schema derivation (§6) lands with **VWB-15**'s catalog work. **§10 (room-scoped
group addressing) is an addendum DECIDED 2026-07-05** — design deliverable of **VWB-22**,
implementation filed as **VWB-23**.

**Supersedes:** the deleted per-scenario WB virtual-device implementation
(`ScenarioWBAdapter` + `setup_wb_emulation_for_all_scenarios`, removed 2026-05-24,
`f519605`) — dormant, disliked, never clearly specified. This design starts from scratch,
as SCN-4 mandated.

**Related:** `docs/design/scenarios/scenario_system_redesign.md` (as-built scenario
architecture this builds on) · `docs/design/ui_backend_contract.md` (Layer-3 manifest
contract this revises in phase 1/2) · `../wb-mqtt-voice/docs/design/mqtt_integration.md`
§5/§13/§14 (the Irene↔bridge REST contract this extends additively).

---

## 1. Decision summary

1. **Scenarios get exactly one WB representation per scenario-bearing room:** a
   **Scenario Manager** virtual device («Сценарии …») with an enum select control —
   SCN-4's option (b), instantiated **per room** (amended 2026-07-04, same session: the
   living room and the future children room each carry their own scenario set and can be
   active **concurrently**). No per-scenario devices, no WB scenes.
2. **Scenario-inherited device commands** (volume/playback/menu/… of the active scenario's
   role-bound devices) are fired at the same Scenario Manager entity as **canonical
   commands**; the bridge resolves role → device **at fire time**.
3. **The proxy is universal:** the UI's scenario page dispatches through it too — same
   grammar, same code path as voice and the WB card. The Layer-3 manifest becomes a pure
   render projection; it no longer determines dispatch targets for scenario pages.
4. **Canonical-first is the target architecture:** device pages migrate to the canonical
   grammar in phase 2, converging the whole system on one client contract —
   catalog (read) · canonical (write) · state/SSE (read). `POST /devices/{id}/action`
   demotes to an internal/dev door; `/scenario/switch`+`/scenario/shutdown` become
   internal details behind the proxy's `scenario` capability.
5. **Param metadata has one source:** canonical action param descriptors (type, min/max,
   units, enum choices) are **derived** from the native config param specs through the
   capability layer's `param_map` — one projection function feeding both the catalog and
   the manifest. Nothing is authored twice.
6. **(Addendum 2026-07-05, §10)** Group utterances («включи свет», «закрой шторы») get a
   **third canonical address form**: room + semantic group + action. The voice side
   resolves only as deep as the utterance specifies; the **bridge** owns membership and
   default-vs-fan-out policy.

## 2. The two consumers that shaped the decision

**The Wirenboard ecosystem** — WB web UI cards, wb-rules, and the future WB-native Alisa
bridge. The project's declared Yandex-voice strategy is "everything exposed as a WB
virtual device becomes Alisa-controllable for free once WB ships their bridge". Devices
already qualify; scenarios only join if they exist as WB controls. A design without a WB
representation forfeits «Алиса, включи кино» via that path permanently.

**Irene (`wb-mqtt-voice`)** — actuates over REST canonical commands resolved against
`GET /system/catalog` (three interactions, all REST; see the voice repo's
`mqtt_integration.md` §5). The catalog today is `{version, rooms, devices}` — scenarios
are absent. The voice repo explicitly flags SCN-4 as able to "reshape what the catalog
exposes as actuation targets". This design's answer: scenarios arrive as **one more
device** — zero new contract concepts, zero new endpoints, fully additive to the VWB-15
artifact.

## 3. The Scenario Manager entities (one per scenario-bearing room)

One virtual entity **per room that has scenarios**, id scheme
**`scenario_manager_<room_id>`** (`scenario_manager_living_room` today;
`scenario_manager_children_room` when that round ships). Rooms are the concurrency
unit: each room's scenario is active/inactive independently; scenarios are already
room-pure by validation (`room_id` + the room-membership hard-fail), which is exactly
the invariant that makes this safe. Each entity is present in **both** external
surfaces:

- **In the catalog:** a `CatalogDevice` with **`room` set to its room** (this is what
  lets Irene disambiguate «включи кино в детской» — and «громче» when two rooms are
  active — through her existing room mechanics, no new concepts) carrying:
  - the **`scenario`** capability — stateful select, `by_value` over **that room's**
    scenario ids, each an enum `{wire, canonical, labels}` triplet (ru/en names from the
    scenario configs — the same value-label mechanism devices already use). Actions:
    `set(<scenario_id>)` (activate/switch — the reconciler's diff transition, exactly
    today's `switch_scenario` semantics, **diffed within the room only**) and `off`
    (deactivate — powers the room's involved devices down, today's `deactivate()`).
  - the **static union of inheritable domains** — `volume`, `playback`, `menu`, `tracks`,
    `screen` (the layout engine's existing role→domain table). Static = the catalog is
    byte-stable across scenario switches; no version churn. A command whose role is
    unbound *right now* fails at fire time (§4).
- **On Wirenboard:** one WB device card **per room** (N cards = N scenario-bearing
  rooms, not N scenarios — the clutter objection stays answered) with:
  - the `scenario` **enum control** (current scenario id or `none`; retained value topic —
    the *only* state the entity publishes). Writing a scenario id activates; writing
    `none` deactivates.
  - a **curated subset** of command pushbuttons — play/pause/stop + volume up/down
    (final list at implementation; a full menu D-pad does not belong on a WB card).
    Stateless pushbuttons; wired through the same proxy executor.

**State rule (write-proxy / read-direct):** the proxy publishes only the `scenario` enum
value. Inherited command domains stay **stateless** on the proxy — real device state
lives on the real devices (their WB cards, their SSE channels, their persisted state),
exactly as today. This split is deliberate; do not "fix" it by mirroring role-device
state onto the proxy.

## 4. Fire-time role resolution (the proxy seam)

Any canonical command at a manager entity other than the `scenario` capability is
resolved by the bridge at dispatch time, **scoped to the entity's room**:

```
{capability: volume, action: up}  at scenario_manager_living_room
  → active scenario OF THAT ROOM                (movie_appletv | none)
  → role for the domain (role→domain table)     (volume → mf_amplifier)
  → re-enter the normal per-device canonical dispatch
    (mf_amplifier's capability map: volume.up → native volume_up → IR burst
     → update_state chokepoint → persistence + WB echo + SSE)
```

Synchronous, speakable failures:

- no active scenario **in that room** → **409** `no_active_scenario`;
- active scenario has no binding for the domain's role → **409** naming the missing role;
- the bound device's capability lacks the action → the existing canonical 4xx unchanged.

The success response carries the resolved target (`executed_on: <device_id>` + the native
action), so Irene can confirm meaningfully and the UI/logs stay honest.

**Mid-transition rule:** resolution reads `current_scenario` as-is (it flips at the end
of a switch). Identical exposure window to today's UI behavior; no queueing, no locking.

All three clients hit this one seam:

```
UI scenario page ──┐
Irene (REST)     ──┼──▶ POST /devices/scenario_manager_<room>/canonical ─▶ fire-time resolution
WB card /on topic ─┘         (WB messages route to the same executor)
```

**Domain prerequisite (SCN-6 deliverable):** today's `ScenarioManager` holds a single
global `current_scenario` and one persisted `active_scenario` key — a second room's
activation would be treated as a cross-room *switch* and power the first room down.
Per-room concurrency requires: active-scenario tracking **per room** (map keyed by
room_id), per-room persistence keys (`active_scenario:<room_id>`, with a one-shot
migration read of the legacy `active_scenario` key), per-room `deactivate()`, and
transition diffs computed within a room only. Scoped and mechanical; it lands inside
SCN-6 because the proxy service is built against `ScenarioManager` anyway.

## 5. The UI under canonical-first

**Scenario page (phase 1).** The manifest remains the render source — zones, buttons,
icons, labels, state bindings, built per-scenario from the *actual* bound devices'
capabilities (so the page renders only what the current scenario truly supports). What
changes: inherited-zone buttons carry the canonical `(capability, action, params)` tuple
and dispatch to `scenario_manager`; the bound device id stays on the button as
*informational* metadata (tooltips, state binding) — not the dispatch target. The power
zone unifies onto the same grammar: activate/deactivate become `scenario.set` /
`scenario.off` at the proxy, retiring the page's bespoke `POST /scenario/switch` +
`/scenario/shutdown` calls. Fire-time resolution also removes the stale-manifest quirk
(a page rendered before a switch could target the previous scenario's device).

**Device pages (phase 2).** The exposure gate already made the device-page surface
identical to the capability surface (`exposed:false` is invisible on manifest/WB/HTTP;
every exposed command is capability-backed — the RC4 load check). The only UI↔voice
difference left is grammar (native `volume_up` vs canonical `volume.up`), so device pages
migrate to `POST /devices/{id}/canonical` as well. Requirements before/with phase 2:

- **VWB-17** (sequence-form actions through the canonical dispatcher) becomes phase 2's
  **gate** — today zero shipped capability actions are sequence-form (and the manifest
  builder skips them too, so parity holds), but one authored sequence would silently
  break a page button. Not voice-only future-proofing anymore.
- **Echo-wait mode:** the canonical endpoint deliberately waits for a value-topic echo
  (right for voice — Irene speaks the result; wrong for a user mashing volume-up). The
  request gains a `wait: false` mode (or momentary actions short-circuit).
- **List queries stay reads:** `get_available_inputs`/`get_available_apps` are reads
  wearing action clothes; they move to the read surface (catalog/state), keeping
  canonical purely imperative.

**Reads stay direct everywhere:** state indicators, SSE subscriptions, persisted-state
views bind to real devices in both phases. Only *writes* are proxied/canonicalized.

## 6. One metadata source: derived canonical param descriptors

The catalog's `CatalogAction.params` is stubbed (`schemas.py` — "param introspection …
owed work"), and the manifest currently reads slider min/max/units from native config
params. Decision: **derive, don't author**. Constraints are genuinely device-dependent
and already live where the driver enforces them — the native config param specs. The
canonical layer contributes what it already owns:

- the **`param_map`** (canonical↔native name correspondence), reversed at projection
  time; type/min/max/units/default ride along unchanged;
- the **value-label tables** supply enum choices (`{wire, canonical, labels}`), taking
  precedence over bare string typing;
- capability-**fixed** params (`fan.off` → `{level: 0}`) are *excluded* from the
  client-facing descriptor — they're implementation, not signature;
- multi-param actions (pointer `dx`/`dy`) list every client param.

Examples of the derived shape:

```
hood    fan.set     → [{name: level, type: range, min: 0, max: 4, required: true}]
eMotiva volume.set  → [{name: level, type: range, min: -96, max: 11, unit: dB}]
amp     input.set   → [{name: value, type: enum, values: [{wire,canonical,labels}…]}]
```

**One projection function** produces these descriptors and feeds **both** the catalog
(`CatalogAction.params` — discharging the owed §P3.7 #19 work, landing with **VWB-15**)
and the Layer-3 manifest (phase 2). "One metadata source" is thereby one code path, not a
synchronization discipline.

Rejected alternatives: authoring param schemas in the capability maps (duplicates
min/max/units across config + `wb_controls` + capability, and the drift-guard you'd need
is this derivation anyway); moving constraints into capability maps and stripping configs
(deep migration — WB control meta and driver validation both read config params — for no
observable gain; remains possible later); status-quo split with a CI consistency check
(institutionalizes the two-grammar problem).

## 7. Rejected scenario-representation options

- **(a) No WB representation** — Irene could ride a bespoke catalog section + REST, but
  that is *new* contract surface; the WB UI can't start movie night; the future Alisa
  path gets nothing.
- **(c) One WB device per scenario** — the deleted approach: WB clutter, and activation
  semantics across N sibling devices were never definable.
- **(d) WB native scenes/rules** — inverts the source of truth; WB scenes would call
  back into the bridge and scenario state would live in two places.
- **Voice-side role resolution** (Irene tracks the active scenario and targets real
  devices) — duplicates the bridge's role logic in every voice client and adds
  context-tracking; rejected in favor of the bridge-side proxy, which the UI then joined.

## 8. Phasing & tracked work

| Phase | Scope | Ledger |
|---|---|---|
| **1** | Proxy routing service (domain/app layer) · **per-room `ScenarioManager` state** (active map, per-room persistence keys + legacy-key migration, per-room deactivate, in-room diffs) · `scenario_manager_<room>` entities in catalog + canonical dispatch · WB card per room (enum + curated pushbuttons) · scenario-page manifest revision + dispatch switch · retained per-room active-scenario value topics | **SCN-6** |
| **2** | Device pages → canonical · echo `wait:false` mode · list-queries → read surface · manifest consumes the §6 projection | **SCN-7** (gated on **VWB-17**) |
| **3** | `/action` demotion/retirement decision · `/scenario/switch`+`shutdown` internalization | acceptance-gate item 4 (code-review half) |
| — | §6 param-descriptor projection → `CatalogAction.params` | rides **VWB-15** |
| — | §10 room-scoped group addressing (`/rooms/{id}/canonical`, `group` overlay, `group_defaults`, aggregate response) | **VWB-23** (design **VWB-22**, 2026-07-05) |

Contract-timing note (**revised 2026-07-04, user decision**): mechanically everything
here is additive — but the **first** VWB-15 golden dump deliberately **waits for the
scenario chain (SCN-6 → VWB-17 → SCN-7)**, so v1 of the pinned contract already carries
the `scenario_manager_<room>` entities and the final canonical-first grammar, and the
VWB-16 crossover fixtures cover scenario commands from day one. After the v1 pin,
additivity + the drift check govern subsequent changes as originally written.

Hexagonal placement: the resolution service is application/domain-layer (it composes
`ScenarioManager` + capability maps); REST router, WB message handler, and the manifest
builder stay thin adapters. No new inward-pointing violations.

## 9. Reference flows

**Today (UI, unchanged until phase 1)** — volume-up on the scenario page,
`mf_amplifier` bound to the volume role: manifest built at page load carries
`sourceDeviceId: mf_amplifier` → UI posts native `volume_up` to
`/devices/mf_amplifier/action` → exposure gate → IR driver publishes
`/devices/wb-msw-v3_207/controls/Play from ROM18/on` → blaster fires → `update_state`
chokepoint fans out (SQLite, WB echo, SSE). The scenario manager is not on the path —
"inheritance" is read-time composition.

**Target (voice and UI alike)** — «громче» / volume-up button:
`POST /devices/scenario_manager_living_room/canonical {capability: volume, action: up}`
→ fire-time resolution (that room's active `movie_appletv` → volume role →
`mf_amplifier`) → re-enters the per-device
canonical path → same IR burst, same chokepoint fan-out → `200 {executed_on:
mf_amplifier, …}`. The WB card's volume-up pushbutton takes the identical path via its
`/on` topic. Failure with nothing active: `409 no_active_scenario` (Irene: «сейчас нет
активного сценария»).

## 10. Room-scoped group addressing (the third address form) — addendum 2026-07-05

**Status:** DECIDED 2026-07-05 (discussion session, VWB-22 — surfaced by the voice side:
"what should the system do with «turn on the lights» / «close curtains»?"). Design
deliverable of **VWB-22**; implementation is **VWB-23**.

### 10.1 The decision

The canonical write door gains a **room-scoped** address alongside the device-level and
scenario-level forms:

```
1. device-level    POST /devices/{device_id}/canonical            (phase 2, shipped)
2. scenario-level  POST /devices/scenario_manager_<room>/canonical (§3–§4, shipped)
3. group-level     POST /rooms/{room_id}/canonical                 (this addendum)
```

The resolver (Irene) resolves **only as deep as the utterance specifies**: a named device
(«включи торшер») → form 1; a relative command inside an active scenario («громче») →
form 2; a bare capability noun («включи свет», «закрой шторы») → form 3, room from
context. Guessing a device out of «свет» would be the resolver inventing precision the
utterance doesn't carry — that guess moves into the bridge, where it is *policy*, not
heuristics. Form 2 is the precedent: caller names an intent, bridge picks the device.

Request shape (additive, mirrors the device-level grammar):

```
POST /rooms/{room_id}/canonical
{ group: "light", action: "on", params?: {…},
  scope?: "auto" | "all" | "one",     // default "auto"
  wait?: bool }                        // same echo semantics as the device endpoint
```

**Resolution policy (`scope`):**

- **`auto`** (default) — the room's configured default device for the group, if any
  (§10.3); otherwise fan-out to **all** members.
- **`all`** — force fan-out. The caller heard the plural / «весь» — the bridge didn't;
  this is how that signal survives. Without it, «выключи весь свет» would actuate one
  ceiling lamp and leave three sconces lit.
- **`one`** — force the default device; speakable `409 no_default_device` if the room has
  none configured.

### 10.2 Membership: the `group` overlay (why NOT the domain, and NOT re-profiling)

The obvious rule — "members = devices in the room whose capability map has the domain" —
**fails on the fleet as shipped**: all 36 light switches declare domain **`power`**
(`light_switch`/`dimmable_light`/`rgb_light` profiles); only the kitchen hood carries a
`light` domain. Domain-as-membership would sweep sockets and the oven-guard relay into
«включи свет». The domain taxonomy conflates *grammar of control* (on/off) with
*semantic class* (this is a lamp) — for WB passthroughs the semantics live in the
**profile name**, not the domain.

Decision: a capability entry carries an optional **`group`** tag — its semantic class.
**Default: the domain name itself** (so `cover`, `volume`, `playback` need nothing);
the three illumination profiles override their `power` capability with `group: "light"`.
The hood's `light` capability matches implicitly — «включи свет» in the kitchen includes
the hood light with zero authoring. Membership for `(room, group)` = devices with
`room_id == room` owning a capability whose group matches.

Execution per member re-enters the ordinary per-device canonical dispatch **against the
member's own capability** (a light switch executes its `power.on`, the hood its
`light.on`) — the group verb names the intent, each member keeps its native grammar, the
`no_op` short-circuit and the `update_state` chokepoint apply per member unchanged.

**Rejected: re-profiling illumination from `power` → `light`.** Semantically purer, but
the `power` domain is load-bearing infrastructure — the reconciler's entire power
management, the layout engine's power zone, the WB-device service grouping all key on it
— and the migration buys nothing the overlay doesn't. Revisitable later; the overlay is
forward-compatible with it (a migrated profile simply stops needing the tag).

**Rejected: per-room master switches by convention** (a "lights" alias per room) —
authoring burden, drift on every added light, and the master's state is undefined when
half the lights are on. `wb-rules/all_lights.js` stays what it is: the hand-authored
*global* physical master; form 3 is its per-room generalization on the REST side.

**Rejected: curated `groups.json`** — a whole new config concept to solve membership
errors we haven't observed. If a device must opt out of its natural group, that's a
per-capability `group: null` override, not a new file.

### 10.3 Room defaults & the singular/plural distinction

`rooms.json` gains an optional per-room **`group_defaults`** map:

```json
{ "room_id": "living_room", …, "group_defaults": { "light": "living_room_ceiling" } }
```

Validated at load: the device must be in the room and a member of the group. This is what
makes «включи свет» (singular intent, `scope: auto`) mean *the* main light where one is
declared, while «весь свет» (`scope: all`) always fans out. The default is a property of
the **room** — one place to look, no two-devices-both-claim-primary collisions a
per-device flag would invite.

### 10.4 Aggregate response — the honest confirmation

With policy in the bridge, the caller no longer knows what was touched, so the response
must say it:

```
200 { room_id, group, action, scope_applied: "default" | "fan_out",
      results: [ { device_id, status: executed | no_op | skipped | failed, detail? } … ] }
```

`skipped` = member lacks the action (reported, never an error); partial failures return
200 with per-member `failed` entries — the caller decides how to speak them («включила
весь свет, бра не ответило»). Empty membership is a speakable **`404 no_group_members`**
(the `no_active_scenario` pattern). `executed_on` semantics from §4 generalize to the
`results` list.

### 10.5 Safety rail: fan-out allow-list

Fan-out launches for **benign groups only — `light` and `cover`** (a static table in the
dispatch service, extended deliberately). For `power` and other consequential groups the
endpoint refuses fan-out with a speakable 409 — «выключи всё» must not be one mumbled
sentence away from the fridge and the NAS (the travel case is already owned, with curated
exclusions, by the `at_home` switch). Explicit device or scenario remains the only path
to consequential actuation.

### 10.6 Contract & catalog impact (additive)

- New endpoint `POST /rooms/{room_id}/canonical` (+ response shape above) in
  `openapi.json`.
- `CatalogDevice` capabilities expose their effective **`group`**; `CatalogRoom` exposes
  **`group_defaults`** — Irene's noun lexicon («свет» → `light`, «шторы» → `cover`) binds
  to catalog truth, not convention.
- `rooms.json` schema: optional `group_defaults` (config model + UI config section).
- All additive. If VWB-23 lands before the voice side pins the contract, v1 simply
  carries it; afterwards it's an ordinary additive rev under the drift guard.
- **Interim:** until VWB-23 ships, Irene *can* fan out client-side (the catalog already
  carries rooms + domains), accepting N round-trips and voice-side membership guesses —
  a stopgap, not the target.
