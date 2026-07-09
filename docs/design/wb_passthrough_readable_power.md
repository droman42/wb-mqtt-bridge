# WB-passthrough state → top-level fields, and readable `power` (DRV-24 design)

**Status: DESIGN AGREED 2026-07-09; revised 2026-07-09 after review.** Follow-on to DRV-23. The
first cut kept the `mirrored` bucket and *projected* it to the top level; review found that bucket is
a workaround, not a layer — so this design **converges the generic passthrough driver onto top-level
state fields** (the shape the bespoke AV drivers already use), which subsumes DRV-23's projection and
removes the `power` duplication the first cut would have introduced. Implementation = **DRV-25**.
Cross-repo: **golden *and* openapi change → the voice side re-pins and the UI types regenerate.**

## 1. Problem

DRV-23 got voice's *sensor* reads working by projecting mirrored feedback to top-level `state.<field>`
(the ARCH-8 contract, `mqtt_integration.md` §5c). Two things remained:

- **Switch `power` is stale/write-only.** On the 39 momentary-power WB-passthrough switch devices, the
  relay state sits raw in `state.mirrored['power']` (`'1'`/`'0'`) while top-level `state.power` stays
  the vestigial default `'off'`, and the catalog advertises `power` as non-readable. So it reports the
  *opposite* of reality, and voice — which reads only catalog-advertised top-level fields — can't query
  it. Needed by three queued voice features: "is the light on?", relative adjust (voice **QUAL-68**),
  and the **ARCH-39** force-confirm (reads believed state before offering to force).
- **The `mirrored` bucket itself is the smell** (§2).

## 2. Root cause: `mirrored` is a substitute for typed fields, not a real layer

`WbPassthroughState` is **one** Pydantic class shared by all 65 passthrough devices, each with a
different field set (a floor: `room_temperature`/`setpoint`; a dimmer: `level`; a cover: `position`; a
switch: `power`; an HVAC: `mode`/`fan`/`vane`/…). A typed model can't declare per-device fields, so
state was dropped into a generic `mirrored: Dict[str, Any]` bucket. But:

- **The driver never holds a logical value apart from the mirror** (verified: its only `update_state`
  calls are `last_command`, the mirror echo, and `error_flags` — it never sets `state.power`). So for
  passthrough the mirror **is** the entire state; the declared top-level fields are vestigial defaults.
- **Consumers read two different places**: voice reads top-level `state.<field>`; the UI's `HvacPanel`
  reads `state.mirrored.power === '1'` (raw wire). Same value, two access paths, two representations —
  the bug class, twice.
- DRV-23's `model_dump` projection and the first cut's "also set `state.power`" were both *compensations*
  for the value living in the bucket instead of where consumers look.

The bespoke AV drivers store state as **typed top-level attributes** (`LgTvState.volume`, `input_source`)
and need no bucket. The generic driver should do the same — just with **dynamic** fields.

## 3. Scope

Two nested scopes:

- **Mirror → top-level conversion (D3): all 65 WB-passthrough devices** (structural — they all use the
  bucket today).
- **`power` readable/authoritative (D1): the 39** momentary-power switch devices across three profiles —
  `light_switch` (24), `dimmable_light` (13), `power_switch` (2). All 39 have a `state_topics.power`
  (relay reads back), so all 39 can be authoritative.

Out of scope (verified 2026-07-09): `kitchen_hood` (Broadlink, one-way, different driver — already
top-level); HVAC on/off (its `mode` readable field, carried along by D3); AV (already typed top-level);
IR (one-way, no feedback).

## 4. Design

### D1 — Profiles: `power` becomes stateful, readable, reconcile-explicit

In `light_switch` / `dimmable_light` / `power_switch`, the `power` capability changes from
`kind: momentary` to a stateful, readable capability:

```jsonc
"power": {
  "kind": "stateful",
  "feedback": true,
  "state_field": "power",
  "reconcile": false,            // EXPLICIT — see below
  "group": "light",             // (power_switch: omit)
  "actions": { "on": {...}, "off": {...} },
  "fields": [
    { "name": "power", "type": "enum",
      "values": [ {"wire":"1","canonical":"on"}, {"wire":"0","canonical":"off"} ],
      "labels": { "ru": "питание", "en": "power" } }
  ]
}
```

The `fields[]` entry makes the catalog advertise `power` as readable with `on`/`off` vocab (same
mechanism HVAC uses for `mode`).

**`reconcile: false` is mandatory here, not optional.** `Capability.reconcile` defaults to `True` and
these profiles don't override it; today power is `momentary` with `state_field: None`, so the reconciler
has no believed value to diff. Making it `stateful` + `state_field` *gives* the reconciler a believed
value, so it would begin driving believed-vs-desired power diffs on all 39 devices — a behaviour change
beyond this fix. Setting `reconcile: false` explicitly keeps lights/plugs out of scenario reconciliation
exactly as today; the change here is purely "power is now readable."

### D2 — Value-table enrichment (profile → device `state_topic`)

`_coerce_mirror` translates a wire echo to canonical only from the *device's* `state_topics[field].values`,
and today's bare form (`"power": "topic"`) defaults `type:"str"` with no table, so coercion keeps `'1'`.
There is no profile→state_topic enrichment, so the profile field's `values` (D1) never reach the driver.

**Add a load-time enrichment**: when a device's `state_topics[field]` is left typeless and its
`capability_profile` declares a matching `fields[].{type,values}`, enrich the device's `StateTopicSpec`
from the profile field (device-level explicit values always win). Declares the table **once per profile**,
keeps the 65 configs terse, and **generalizes** — it also closes the DRV-23 sibling where a bare-`state_topic`
enum field (e.g. `heating_loop` `mode`) currently surfaces as raw `'0'` instead of the advertised vocab.

*Rejected:* 39 per-device value tables (verbose, drift-prone); hard-coding `power` as bool→on/off in the
driver (special-cases one field, doesn't generalize, puts vocabulary in code).

### D3 — Retire `mirrored`; passthrough state lives at the top level (all 65)

This is the core of the revision.

- **`WbPassthroughState`**: drop the `mirrored` field; add `model_config = ConfigDict(extra="allow")`.
  Keep `reachable` + `error_flags` (per-field connectivity metadata, unchanged). Remove DRV-23's
  `model_dump` override — fields are real attributes now and serialize natively.
- **`_on_value_message`**: set the coerced value as a top-level attribute —
  `update_state(**{field: typed})` — instead of into a bucket. (`power` lands on the declared field; a
  dynamic field like `room_temperature` lands as an `extra` attribute.)
- **Idempotence guard** (`_publish_command`): read `getattr(self.state, state_field, None)` instead of
  `state.mirrored.get(state_field)`. The typed/canonical comparison logic is unchanged.
- **Collision guard**: at config load, reject (or warn + drop) a `state_topics` key that shadows a
  reserved base field — `device_id`, `device_name`, `last_command`, `error`, `reachable`, `error_flags`.
  `power` is the one intended overlap and is allowed. (The bucket namespaced these for free; `extra="allow"`
  needs the guard back.)

**Result:** echo `'1'` on the relay topic → `_coerce_mirror` (D2 table) → `'on'` → `state.power = 'on'`
(declared field). A floor echo → `state.room_temperature = 24.125` (dynamic field). One store, one
representation, every consumer reads top-level.

## 5. Fallout to handle

- **UI** — `HvacPanel.tsx` migrates from `state.mirrored.*` (raw `'1'`) to top-level canonical fields
  (`state.power`, `state.room_temperature`, …). `config-ui-stays-functional`.
- **Persistence** — dynamic fields persist via `extra="allow"`; `restore_state` applies declared fields
  only, so dynamic fields are skipped on restore and **re-seeded from the retained value topics at
  `setup()`** (correct — a persisted sensor reading is stale; the live retained value wins). `power`
  (declared) restores normally.
- **Contract** — `/state` and `persisted_state` change shape (`mirrored` gone, fields top-level), so
  **openapi changes, not just the golden catalog**. `WbPassthroughState` is part of the persisted-state
  discriminated union; `extra="allow"` surfaces as `additionalProperties`. Regenerate `contracts/`
  (openapi + golden + stamp) and `ui/src/types/*` (`gen:api-types`); **the voice side re-pins**. Land the
  two pins together.

## 6. Test plan

- profiles parse (stateful power + value table + `reconcile:false`); enrichment merges profile
  `type`/`values` into a bare device `state_topic`, device-explicit wins.
- `_coerce_mirror('power','1') → 'on'`; `_on_value_message` sets a **top-level** field (declared `power`
  and a dynamic `room_temperature`), not a bucket.
- idempotence reads top-level (`getattr`); a `power_off` after `power_on` still fires (mirror-behaviour
  preserved, now off the attribute).
- collision guard rejects a reserved-name `state_topic`.
- persistence: dynamic field skipped on restore, re-seeded at setup; `power` restores.
- catalog advertises `power` readable with `on`/`off`; golden + openapi regenerated; UI types regen.
- end-to-end: echo `'1'` → `GET /state` top-level `power:"on"`; `HvacPanel` reads top-level.

## 7. Relationship to DRV-23

This **supersedes DRV-23's projection mechanism** (the `model_dump` override is removed) while preserving
its external behaviour (readable top-level fields). DRV-23's two tests are rewritten from "appears via
serialization projection" to "stored as a top-level field." Net external read behaviour is identical; the
internals collapse to one representation.

## 8. Implementation = DRV-25 (revised scope)

One landing: **D1** (3 profiles) + **D2** (loader enrichment) + **D3** (state model `extra="allow"` +
remove `mirrored` + driver `_on_value_message` + idempotence read + collision guard + remove DRV-23's
projection) + **UI** `HvacPanel` migration + **contracts** openapi/golden/stamp regen + UI types regen +
tests. Bigger than the first cut, but the correct shape — and DRV-25 is `[P2] [deferred]`, so there is no
release-time pressure to take the incremental-but-duplicating path. Golden + openapi re-pin coordinated
with the voice side; picks up alongside the voice features that need it (QUAL-68 / ARCH-39).
