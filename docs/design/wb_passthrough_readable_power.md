# WB-passthrough switch power — authoritative, readable state (DRV-24 design)

**Status: DESIGN AGREED 2026-07-09.** Follow-on to DRV-23 (which fixed the read path for
sensor/climate fields). Implementation filed as **DRV-25**. Cross-repo: this is a **golden
catalog change** — the voice side re-pins on completion.

## 1. Problem

DRV-23 made WB-passthrough devices project their mirrored feedback onto the top-level
`state.<field>` that voice reads (ARCH-8 contract, `mqtt_integration.md` §5c). It deliberately
did **not** touch `power`: it's a declared base field, and the mirror held the raw wire value
(`'1'`/`'0'`) while the capability vocabulary is `'on'`/`'off'` — a mapping, not a copy.

The consequence, from the voice side's live WB7 re-test: on the **39** WB-passthrough
switch/relay devices the `power` capability is `kind: momentary` (write-only). The relay's real
state sits in `state.mirrored['power']` as raw `'1'`/`'0'`, but top-level `state.power` stays the
vestigial default `'off'`, and the catalog advertises `power` as **non-readable**. So `state.power`
reports the **opposite of reality** on every switched relay, and voice — which reads only what the
catalog advertises — can't query it.

Not blocking today (voice reads only temperature/humidity), but on the path of three queued voice
features: a spoken "is the light on?", relative adjustments (voice **QUAL-68**), and the **ARCH-39**
force-confirm (reads believed state before offering to force).

## 2. Scope (verified 2026-07-09)

**WB-passthrough `power` capability only** — 39 devices across three profiles:

| profile | devices | shape |
|---|--:|---|
| `light_switch` | 24 | `power` on/off |
| `dimmable_light` | 13 | `power` on/off + `brightness`/`level` (already readable via DRV-23) |
| `power_switch` | 2 | `power` on/off (plugs, oven) |

All 39 have a `state_topics.power` (the relay reads back), so all 39 **can** be authoritative.

Explicitly **out of scope** (verified): `kitchen_hood` (Broadlink, different driver, one-way — already
exposes optimistic `light`/`speed` top-level); HVAC (its on/off is the `mode` *readable field*, already
projected by DRV-23); AV network devices (already expose authoritative top-level `power`); IR devices
(one-way, no feedback to be authoritative about).

## 3. The three decisions

### D1 — Catalog readability (profile change)

In each of the three profiles, change the `power` capability from `kind: momentary` to a stateful,
readable capability:

```jsonc
"power": {
  "kind": "stateful",
  "feedback": true,
  "state_field": "power",
  "group": "light",              // (power_switch: no light group)
  "actions": { "on": {...}, "off": {...} },
  "fields": [
    { "name": "power", "type": "enum",
      "values": [ {"wire":"1","canonical":"on"}, {"wire":"0","canonical":"off"} ],
      "labels": { "ru": "питание", "en": "power" } }
  ]
}
```

The `fields[]` entry is what makes the catalog advertise `power` as a readable field with the
`on`/`off` vocabulary (same mechanism HVAC uses to advertise `mode`). `state_field: "power"` also
gives the reconciler a believed value (harmless — these profiles are `reconcile:false` by config
today, unchanged here).

### D2 — Where the wire→canonical `'1'↔'on'` mapping lives (the real decision)

The driver's `_coerce_mirror` translates a wire echo to canonical **only** from the *device's*
`state_topics[field].values` — and today's bare form (`"power": "topic"`) defaults `type:"str"` with
no value table, so the mirror keeps `'1'`. There is **no** profile→state_topic enrichment, so the
profile field's `values` (D1) never reach the driver.

**Chosen: add a load-time enrichment step** — when a device's `state_topics[field]` is left typeless
and its `capability_profile` declares a matching `fields[].{type,values}`, enrich the device's
`StateTopicSpec` from the profile field (device-level explicit values always win). Declares the value
table **once per profile**, keeps the 39 device configs terse, and **generalizes**: it also closes the
DRV-23 sibling where bare-`state_topic` enum fields (e.g. `heating_loop` `mode`) currently project as
raw `'0'` instead of the advertised vocab.

- *Rejected — 39 per-device value tables:* correct but verbose and drift-prone; the drift-guard would
  have to police 39 duplicates of one table.
- *Rejected — hard-code `power` as bool→on/off in the driver:* special-cases one field name, doesn't
  generalize to `mode`/other enums, and puts vocabulary in code instead of config.

### D3 — Projecting to the top level

With D2 in place, `_coerce_mirror` yields canonical `'on'`/`'off'`, so `state.mirrored['power'] ==
'on'`. The driver's `_on_value_message` then sets the **declared** top-level field directly when the
echoed state field is a declared attribute of the state model (i.e. `power`):

```python
typed = self._coerce_mirror(field, payload)
updates = {"mirrored": {**self.state.mirrored, field: typed}, ...}
if field in type(self.state).model_fields and field not in ("mirrored", "error_flags", "reachable"):
    updates[field] = typed          # DRV-24: authoritative top-level for declared fields (power)
self.update_state(**updates)
```

DRV-23's `model_dump` projection stays `setdefault` for the **non-declared** mirror keys (setpoint,
room_temperature, level, position, mode…); it no longer needs to fight `power`, which is now a real,
correctly-valued field. `power` is never left stale, and the collision guard from DRV-23 is moot
because the value is canonical, not raw.

## 4. Contract impact + cross-repo

`power` becomes a readable catalog field on 39 devices ⇒ the **golden catalog content-hash changes**.
On completion: bridge regenerates `contracts/` (`wb-catalog` + openapi), the drift guard re-pins, and
the **voice side re-pins** its copy (their scripted `make repin`). Sequence it as one landing so the
two pins move together. No new endpoint or REST-schema change (the readable-field advertisement rides
the existing catalog surface).

## 5. Test plan

- profile parse: the three profiles' `power` capability is stateful + carries the value table.
- enrichment: a device with a bare `state_topics.power` + `light_switch` profile ends up with the
  `'1'↔'on'` value table on its spec; an explicit device-level value table still wins.
- driver: `_coerce_mirror('power', '1')` → `'on'`; `_on_value_message` sets top-level `state.power`.
- catalog: a light_switch device advertises `power` with `values [on/off]`; golden regenerated.
- end-to-end: echo `'1'` on the relay topic → `GET /state` has top-level `power: "on"`.
- regression: DRV-23 sensor projection unaffected; idempotence (reads `state.mirrored`) unaffected.

## 6. Implementation follow-up

**DRV-25** — implement D1–D3 + the catalog regen/re-pin. Single landing (3 profiles, the loader
enrichment, the driver `_on_value_message` change, catalog + contracts regen, tests). The enrichment
also discharges the DRV-23 `mode` value-vocab sibling for `heating_loop`/similar.
