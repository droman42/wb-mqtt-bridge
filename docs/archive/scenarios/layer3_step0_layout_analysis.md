# Layer 3 — Step 0: Layout analysis (zone ↔ domain taxonomy + per-device inventory)

> **ARCHIVED 2026-06-30 (DOC-10) — FROZEN working artifact; do not read as current.** A Step-0
> empirical analysis that fed the placement engine. All of it is now embodied in
> `scenario_system_redesign.md` §17 + the shipped placement engine, and the fidelity oracle it
> references was itself archived 2026-06-09. Kept for provenance only.

**Status:** Step-0 working artifact, 2026-05-23. Feeds the placement engine (Step 1). Design +
sequencing live in `scenario_system_redesign.md` §17; this is the empirical per-device analysis.

## 1. Domain → zone taxonomy (the placement signal)

The 9 capability domains map onto the existing 7 remote zones as follows (zones from the current
`ZoneDetection`; the placement engine re-keys this off **domain** instead of name-matching):

| Domain | Zone | Kind | Slot / order rule |
|---|---|---|---|
| `power` | power | slot | `power.off`→left, `power.on`→right |
| `input` | media-stack (inputs) | slot | inputs dropdown (populated by `input.list`) |
| `playback` | media-stack (playback) | ordered | transport row, capability-declaration order |
| `tracks` | media-stack (tracks) | ordered | audio/subtitle row, declaration order |
| `volume` | volume | ordered | up/down/mute/slider |
| `menu` | menu | ordered + slots | D-pad core = slots (`up/down/left/right/ok`); extras (home/back/exit/menu/settings) need placement (§7) |
| `apps` | apps | slot | apps dropdown (populated by `apps.list`) |
| `screen` | screen | ordered | aspect/ratio actions, declaration order |
| `pointer` | pointer | slot | touch/cursor pad (LG cursor, AppleTV swipe) |

9 domains → 7 zones (input/playback/tracks share **media-stack**). This is the v1 taxonomy.

## 2. Key finding — `group` and `domain` align 1:1 (zero exceptions)

Across all capability-mapped commands in all devices, the config `group` and the capability
`domain` agree semantically every time (power↔power, inputs↔input, volume↔volume, menu↔menu,
playback↔playback, tracks↔tracks, apps↔apps, screen↔screen, pointer↔pointer). **Consequence:**
deriving zones from `domain` reproduces today's grouping with **no reshuffling** — and confirms the
groups-retirement (§17) is safe. `group` is a redundant label.

## 3. Per-device inventory (summary)

| Device | Class | #cmds | Cap map | Gaps |
|---|---|---|---|---|
| appletv_living / _children | AppleTVDevice | 24 | ✅ class | `refresh_status`, `screensaver`, `home_hold` unmapped |
| lg_tv_living / _children | LgTv | 27 | ✅ class | clean (all mapped) |
| emotiva_xmc2 | EMotivaXMC2 | 6 | ✅ class | clean |
| mf_amplifier | WirenboardIRDevice | 11 | ✅ device | clean |
| vhs_player | WirenboardIRDevice | 6 | ✅ device | clean |
| ld_player | WirenboardIRDevice | 8 | ✅ device | clean |
| video | WirenboardIRDevice | 16 | ✅ device | clean |
| upscaler | WirenboardIRDevice | 14 | ✅ device | `power_on`/`power_off` unmapped (auto-powers — DECISION §8) |
| **streamer** | **AuralicDevice** | 14 | ❌ **none** | **all 14 unmapped — author full map** |
| **reel_to_reel** | **RevoxA77ReelToReel** | 4 | ❌ **none** | **all 4 unmapped — author playback map** |
| kitchen_hood | BroadlinkKitchenHood | 2 | ❌ none | **appliance — deferred** (has explicit `wb_controls`) |

## 4. Capability-coverage gaps → Step-0 authoring targets

- **`streamer` (Auralic) — author full map:** `power` (power_on/off), `playback` (play/pause/stop/
  next), `volume` (set_volume/up/down/mute), `input` (set_input + `input.list`=get_available_inputs).
- **`reel_to_reel` (Revox) — author playback map:** play/stop/rewind_forward/rewind_backward
  (`playback`). (Pure transport; no power/input.)
- **`upscaler`** — has a map (input/screen/menu) but **no `power`** by design (auto-powers with
  source). **Decision §8.2: author a `power` capability with `reconcile: false`** — manual power on
  the device page, reconciler skips it.
- **`kitchen_hood`** — appliance, **out of Layer-3-v1 scope** (bespoke page later); leave as-is.

## 5. Dormant commands → `exposed: false`

- **AppleTV:** `screensaver`, `home_hold` (the `noops` group) — parked driver actions.
- **AppleTV:** `refresh_status` — internal status poll, not a user control.
- **streamer:** `track_info` (the `media` group — testing unfinished) and `refresh_inputs`
  (internal). `get_available_inputs` is NOT dormant — it's the `input.list` data source (§6).

## 6. Non-button capability actions (list/query → dropdown sources)

`get_available_apps` (`apps.list`) and `get_available_inputs` (`input.list`) are **mapped**
capabilities but render as the **data source for the apps/inputs dropdowns**, not as buttons. The
placement engine must treat a domain's `list` action as populating that domain's dropdown, not as a
standalone control. (Distinct from `refresh_*` = internal → `exposed:false`.)

## 7. Placement-hint candidates (where the derive rule is ambiguous)

- **menu zone:** the D-pad core (`up/down/left/right/ok`) fills fixed slots; the extras
  (`home`, `back`, `exit`, `menu`, `settings`) have no slot → need explicit `placement` hints
  (e.g. a row above/below the D-pad). LG TV + video + upscaler all have such extras.
- **media-stack:** section order of inputs (dropdown) / playback (transport) / tracks (row).
- **ordered zones (playback, tracks, screen):** intra-zone order follows **capability declaration
  order** — so the *capability map* author controls button order (this retires the old
  config-key-order convention).

## 8. Decisions (resolved 2026-05-23)

1. **Taxonomy (§1)** — **CONFIRMED** as the v1 domain→zone mapping.
2. **upscaler power** — **RESOLVED: keep manual power on the upscaler's device page** (the user tunes
   the upscaler standalone, outside any scenario). Wrinkle: the reconciler powers *every `involved`
   device that has a `power` capability* (`reconciler.py build_plan:330-343`), and the upscaler is on
   the signal path (`involved`) — so a plain power capability would make scenarios power-cycle it,
   breaking the intended auto-power. **Mechanism: a new capability flag `reconcile: false`** (default
   `true`) — the capability is exposed (page/WB/HTTP) but the reconciler skips it. Author the
   upscaler `power` capability with `reconcile: false`. Needs a small reconciler change (skip a cap
   where `reconcile is False`) — Step-1 backend task. This makes the model carry an orthogonal pair:
   **`exposed`** (command-level — surfaced at all?) × **`reconcile`** (capability-level —
   scenario-driven?).
3. **List vs internal (§5/§6)** — **CONFIRMED**: `*.list` = dropdown sources (exposed);
   `refresh_status`/`refresh_inputs` = `exposed: false`.

## 9. Step-0 status (2026-05-23)

- ✅ **reel_to_reel** capability map (playback).
- ✅ **streamer** capability map (input/volume/playback). **streamer power deferred → Step-1**
  (Auralic power is the bool `connected`; capability `on_value` is string-only → widen to
  `str|bool|int`).
- ✅ **Fidelity oracle captured** — `docs/design/scenarios/layer3_oracle/*.json` (per-device
  `RemoteDeviceStructure`, frozen 2026-05-23).
- ✅ **Step-1 model batch DONE (2026-05-23):** `on_value` widened (`str|bool|int`) · `reconcile`
  flag · `exposed` flag · reconciler `reconcile`-skip · load-time validation + drift guard ·
  `execute_action` exposure gate. Completed streamer power (bool `connected` feedback), upscaler
  power (`reconcile:false`), and dormant tagging (5 commands `exposed:false`). **Full capability
  coverage achieved** (drift guard: 0 violations); 279 backend tests pass.

**Step 0 + the Step-1 model batch are complete.** Next (rest of Phase-3 Step 1): the
**`LayoutManifest`** Pydantic model (mirroring `ui/src/types/RemoteControlLayout.ts`) + the
**domain→zone placement engine** + `GET /devices/{id}/layout`, reproducing a device's oracle
(`layer3_oracle/*.json`) zone-by-zone. Then Steps 2-4 (UI renderer → rollout → cutover).
