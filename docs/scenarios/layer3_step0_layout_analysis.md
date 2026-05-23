# Layer 3 — Step 0: Layout analysis (zone ↔ domain taxonomy + per-device inventory)

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
  source). Its `power_on`/`power_off` IR commands are unmapped → see §8.
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

## 8. Open decisions (need sign-off before Step 1)

1. **Taxonomy (§1)** — confirm as the v1 domain→zone mapping.
2. **upscaler power** — the device auto-powers with its source, so the reconciler omits a power
   capability. Should the UI still show **manual power buttons** (→ add a `power` capability for the
   page even though the reconciler ignores it), or treat `power_on`/`power_off` as **`exposed:false`**
   (vestigial)?
3. **List vs internal (§5/§6)** — confirm `*.list` actions = dropdown sources (exposed), and
   `refresh_status`/`refresh_inputs` = `exposed:false`.

## 9. Step-0 remaining (after this analysis)

- Author the `streamer` + `reel_to_reel` capability maps (workstream #2).
- Tag the dormant commands `exposed: false` (workstream #3).
- Capture the current `.gen.tsx` per-device zone/control snapshots as the **fidelity oracle** for
  Step 1 (the backend manifest must reproduce them).
