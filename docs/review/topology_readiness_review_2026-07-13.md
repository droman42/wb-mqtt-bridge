# Topology-layer readiness review — DRV-38(b), 2026-07-13

**Frozen evidence.** Companion to `emotiva_wedge_20260712.md` (the incident). Three
read-only audit lanes ran in parallel (driver audit / executor mechanics / scenario
exposure map); synthesis and owner-reviewed conclusions below. Findings → tracked as
**SCN-16** (zone-aware power planning) and **SCN-17** (executor dispatch timeout);
the dispatch-seam fix itself landed as DRV-38(a) (`b4407bc`).

## Lane R1 — driver audit (all 9 drivers)

| Driver | Verdict | Post-power window | "Ready" defined as |
|---|---|---|---|
| emotiva_xmc2 | **HARD-RISK** (the reference case) | CEC/ARC handshake; firmware wedges | `_power_on_monotonic` window — since DRV-38(a) enforced at the dispatch seam for every command |
| lg_tv | SOFT-RISK | WoL boot (5–15 s waits exist) | `client and state.connected` + control object, per handler |
| apple_tv | SOFT-RISK | wake; 0.5 s stabilize in `_ensure_connected` | `atv and state.connected` |
| auralic | SOFT-RISK | boot ~15 s; ports move per transition | `openhome_device and state.connected` + deep-sleep flag |
| wirenboard_ir | SOFT-RISK | none defined — IR into a booting sink is silently dropped | undefined (optimistic power only) |
| broadlink_hood | SAFE | n/a (no power concept; one deliberate 0.5 s intra-command settle) | client presence |
| revox_a77 | SAFE | n/a (carries its own transport-reversal settle) | cosmetic |
| wb_passthrough | SAFE | n/a | `reachable` from WB error flags |
| mitsubishi_hvac | SAFE | n/a (firmware drops bad/unchanged payloads) | heartbeat-fresh `reachable` |

**Only the eMotiva can wedge.** The soft-risk drivers degrade to ignored/errored
commands behind per-handler connectivity guards. `BaseDevice` offers **no** generic
readiness hook — every driver rolls per-handler guards, which is precisely how the
eMotiva gap happened (one gated handler, seven ungated).

## Lane R2 — executor mechanics (`reconciler.py`)

- **Entry pacing has exactly one lever:** topology `ordering.delay_ms` →
  `pre_delay_ms`, slept before dispatch (`execute_plan`, reconciler.py:704). Nothing
  else delays a step's entry.
- **Steps are globally serialized** — one `for` loop, no concurrency; a hold on one
  device delays every later device's step.
- **SCN-14 gates are outcome-only** and return the instant the target satisfies:
  after the eMotiva main-power gate satisfied (~4 s), nothing in the executor could
  hold zone 2. Confirmed against the 19:50:40.938 dispatch.
- **A driver-side hold inside `execute_action` is honored transparently:** the
  executor awaits dispatch (reconciler.py:715) strictly before starting the gate
  (:731), so the gate's `poll_timeout_ms` clock starts AFTER the hold — a hold never
  eats the gate budget. This validates the DRV-38(a) seam as the architecturally
  correct layer (readiness is device knowledge; the hexagon wants it behind the port).
- **Residual:** no timeout wraps `device.execute_action` — a buggy, never-returning
  driver hold would hang the whole switch. DRV-38(a)'s hold is hard-capped at 15 s,
  so this is defense-in-depth → **SCN-17**.

## Lane R3 — scenario exposure map

Cold-start plan shapes derived from configs + `build_plan` (verified against the
2026-07-12 19:50 execution; full step tables in the session record):

- **`zone2_power_on` fires in all 5 AV scenarios, always BEFORE the gated
  `set_input`** (zone iteration order) — pre-fix, every AV start led with the
  unguarded command. DRV-38(a) closed all five at once.
- **The diff can remove the only protected step:** at 19:50 the input was already
  correct, so `set_input` fell out of the plan and zone-2 power became the eMotiva's
  last word. Plan shape is emergent; per-handler protection can never be sufficient.
- **Spurious zone 2:** `movie_ld` / `movie_vhs` power zone 2 although their audio
  path is Dodocus RCA → amp (`processor:zone2` unused). `_power_actions` emits every
  declared zone unconditionally whenever the device is involved → **SCN-16**.
- **Load-bearing blind delays:** `ld_player/vhs_player.power → upscaler.input`
  (4500 ms) is the upscaler's ONLY protection (its power is `reconcile: false`, no
  gate exists); `processor.input → video.power` (5000 ms) masks the Zappiti
  unrouted-sink quirk (replacement already tracked as SCN-10). Accepted as-is,
  recorded here; the amp's post-IR-power input selects ride the amp's own 4000 ms
  blind delay — SOFT (dropped IR at worst).
- **`tv_on_speakers`** stacks a second CEC interaction (eMotiva `set_input(arc)`
  power-cycles the processor right after the TV's own ARC move) — known territory,
  expected-fail until the DRV-32 bench.

## Conclusions (owner-reviewed 2026-07-13)

1. **Readiness lives driver-side behind `execute_action`** — DRV-38(a) is the
   pattern, not a patch. A first-class `BaseDevice` pre-dispatch hook waits for
   rule-of-two (no second driver needs it today; only the eMotiva is HARD-RISK).
2. **The planner should not power zones off the used audio path** → SCN-16 [P1].
3. **The executor should bound dispatch** → SCN-17 [P2].
4. The soft-risk IR-into-boot-window pattern stays masked by authored delays —
   accepted, with the upscaler delay flagged as the fragile one (no task; revisit if
   it ever misfires).
