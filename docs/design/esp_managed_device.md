# EspManagedDevice — the descriptor-native driver (DRV-36 design)

**Status: DESIGN AGREED 2026-07-12** (design-only session; implementation deliberately NOT
started — owner decision: it waits for the first real device on the satellite side).
Consumes the **device-integration convention v1**
([`device_integration_convention.md`](device_integration_convention.md),
`contracts/device-integration/`, tag `device-integration-v1`). Implementation = **DRV-37**
(filed with this design, BLOCKED on the satellite's first conforming descriptor); the
descriptor-pin conformance test (VWB-39) activates with it. Supersedes the parked
`ESP32ManagedDevice` concept in name and shape (HK-4; annotation at the old decision text).

## 1. What it is

One driver class for **every Locveil-built satellite device**, present and future: a driven
adapter (`infrastructure/devices/esp_managed/`, class
`EspManagedDevice(BaseDevice[EspManagedDeviceState])`, entry point `esp_managed`) whose
entire per-device knowledge arrives from the device's **descriptor** — the satellite-authored
JSON conforming to `device-descriptor.schema.json`. A new satellite device means: pin its
descriptor, add a thin device config. **No new driver, no hand-authored class map, no code.**
That is the "descriptors up" half of HK-4 made real bridge-side.

Like `MitsubishiHvac`, it **never creates a WB virtual device** — the firmware owns its WB
card (it publishes the full announce sequence itself); enforced the same two ways
(inherited `enable_wb_emulation=False` + no emulation call, test-pinned).

## 2. Config & the descriptor pin

- **Thin device config** `config/devices/<id>.json`: `device_class: EspManagedDevice`,
  device id, room, and a `descriptor` field naming the pinned copy. Everything else — names,
  controls, capabilities, timing — comes from the descriptor; the config model
  (`EspManagedDeviceConfig`) rejects attempts to restate it (one source of truth).
- **Pinned descriptor** at `config/descriptors/<device_id>.json` — a **byte-identical mirror
  of the satellite's descriptor** (they own it; we pin one-way, the exact inverse of how they
  pin our convention — the HK-4 mirrored-pins discipline). Re-pin on their descriptor bump;
  never hand-edit.
- **Load-time validation, loud:** the pinned descriptor is validated against the repo's
  pinned convention schema (the VWB-39 pin). Schema nonconformance, an unknown `profile`,
  or a `convention` major that doesn't match the pinned convention version → the config
  **refuses to load** (the VWB-35 fail-fast precedent). v1 accepts exactly
  `profile: "wb-mqtt-v1"`; a future ha-mqtt profile is a new translation, same driver shell.

## 3. Capability map — translated, not authored

The capability loader today has two map sources (class default `classes/<class>.json`,
per-instance `capability_profile`). The descriptor becomes the **third, per-instance
source**: at load, the descriptor's `capabilities` block is mechanically translated into the
class-map dialect the whole pipeline already speaks —

- action `control` → the map's `command` (the driver's command vocabulary IS the control
  set),
- the static `timing.confirm_latency_ms` → `gate.poll_timeout_ms` on every
  `feedback: true` capability (the promise is worst-case, used directly; the gate object
  never appears in a descriptor — it stays bridge-internal, re-tunable only by convention
  bump),
- `fields` with `{wire, canonical, labels}` tables pass through unchanged (same triplet
  form).

Downstream — catalog projection, param derivation, value tables, the canonical endpoint's
gate honoring (`poll_timeout_ms`, the DRV-29 mechanism) — is **unchanged code**. The
translation is a pure function with its own unit tests; no loader fork.

## 4. State & the wire

`EspManagedDeviceState(BaseDeviceState)`:

- **dynamic canonical fields** (dict keyed by the descriptor's field names — the passthrough
  precedent for open field sets),
- `reachable: bool` — driven by the retained `meta/online` LWT topic. This device family
  finally has an honest last will (unlike mitsubishi2wb), so **no heartbeat watchdog is
  needed** — the broker itself reports the death. DRV-27's workaround is explicitly not
  copied.
- the **stamp block** mirrored from retained `meta/locveil`: `fw_app`, `fw_version`,
  `descriptor_version`, `convention_version`, plus derived `stale_pin: bool` (stamp trails
  the pinned versions). **Monitor-only** — logged and surfaced in state, never branched on
  (the HK-4 design-time rule).

The class is added to `OPENAPI_EXTRA_MODELS` + `device-state-mapping.json` **once** — the
"one-time openapi bump" of HK-4; it never recurs per device.

**Subscriptions:** every state-mirrored control's value topic, `meta/online`,
`meta/locveil`. Inbound values translate wire→canonical through the descriptor's tables (the
shared `value_translation` module) and land via the `update_state` chokepoint (persistence
rides it; there is no WB-mirror leg since there is no emulated card).

**Commands:** canonical action → publish to `<control>/on` — static `payload` as given,
parametric via canonical→wire translation, pushbutton fires `"1"`. Confirmation is the
convention's **echo**: the value-topic update closes the gate within `confirm_latency_ms`.
No polling, no read-back requests.

**Guards (established conventions, inherited not reinvented):** unreachable → fail-fast
speakable error on every command, reserved `force` bypasses (DRV-30); stateful controls ride
the `idempotence_skip` chokepoint, momentary/pushbutton actions never skip (nothing to
compare against).

**Boot & broker-wipe posture:** retained value topics repopulate state on subscribe;
`meta/online` is retained; and on a broker restart the *firmware* reconnects and re-announces
everything (the convention's announce rule) — the device family self-heals the broker-wipe
by design. State-DB restore (VWB-18) remains the cold-boot fallback via the base class.

**Interlocks:** `requires_arm` stays **firmware-enforced, single enforcement point** — the
driver exposes `arm_record`/`record` as ordinary actions and adds no bridge-side gate (a
second enforcement point could only disagree with the first). A UI arm-flow affordance (and
whether interlocks project into the catalog — a contract change) is deliberately deferred to
the first device's UX pass, where it can be designed against something real.

## 5. Vocabulary — the deferred cut

The deck devices need canonical vocabulary that does not exist bridge-side (a transport
family: `play`/`stop`/`ff`/`rewind`/`record`/`arm_record`). Per the convention (§6 of its
design) and HK-4: the satellite files the vocabulary request repo-to-repo with their first
descriptor; the tokens land bridge-side as **one deliberate contract cut batched with
DRV-37** — capability vocabulary + catalog projection + golden bump + the single voice
re-pin (the OPS-16 tagging discipline). Nothing is added speculatively now; the golden
catalog is untouched by this design.

## 6. Plumbing (recorded so DRV-37 is mechanical)

- Package `infrastructure/devices/esp_managed/`; entry point
  `esp_managed = …driver:EspManagedDevice`; added to the import-linter **independence**
  contract list (drivers never cross-import; descriptor translation lives in the package or
  in the existing shared modules, nothing new crosses layers).
- Tests follow the established device-test recipe: config/descriptor validation (including
  the fail-fast refusals), translation golden cases, both translation directions on the
  wire, echo-gate confirmation, LWT flip + recover, stale-pin stamp handling, no-WB-emulation
  pin, catalog projection.
- No WB-rekey oracle row (no emulated card). UI: types regenerate with the openapi bump;
  the runtime device page works off the projected capabilities as-is.

## 7. Follow-ups (filed with this design)

- **DRV-37** — implement `EspManagedDevice` per this design. **BLOCKED on the satellite's
  first conforming descriptor** (their DES-4 output for the first real device) — the driver
  is not built against a hypothetical: the first descriptor is the fixture, the vocabulary
  request arrives with it, and VWB-39's conformance test activates alongside.
- Per-deck device configs + rack cutover stay **unfiled until satellite first-light**
  (HW-GATED, satellite-triggered — standing board instruction).
- Out of scope forever unless the owner reopens firmware: the HVACs
  (`device_integration_convention.md` §2 — the standing constraint).
