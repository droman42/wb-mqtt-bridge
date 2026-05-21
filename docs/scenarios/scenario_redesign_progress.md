# Scenario Redesign — Implementation Progress & Session Notes

- **Status:** Phase 1 (backend) implemented; **hardware verification pending**.
- **Branch:** `feat/scenario-redesign` (not merged to `main`). Full test suite: **270 pass**.
- **Last updated:** 2026-05-21.
- **Design contracts:** `docs/scenarios/scenario_system_redesign.md` (Layers 0/1/2/R),
  `docs/ui_backend_contract.md` → "Layout Manifest & Runtime Rendering" (Layer 3),
  `docs/monorepo_migration_plan.md` (Phase 2).

This is the as-built record of the redesign work. It complements the design docs (what we
*intend*) with what is *actually built*, what's open, and what to watch.

---

## 1. Accomplishments

The broken scenario layer (action_plan P0.5 #12) was rebuilt as a topology- and
capability-driven **reconciler**, adopting the Logitech Harmony model (optimistic state,
IR-first, manual resync via the device page). **All four scenarios** now run through it.

- **Layer 0 — Topology.** `config/topology.json` (the living-room wiring, declared once) +
  Pydantic model/loader (`infrastructure/topology/`). A link's destination port is the input
  value to select; explicit `first → then` ordering edges (with optional `delay_ms`) encode the
  HDMI-ARC + observed startup order; a manual `dodocus` node carries the RCA-hub instructions.
- **Layer 1 — Capability maps.** Hot-fixable JSON under `config/capabilities/` (no rebuild
  needed) + schema/loader (`infrastructure/capabilities/`), attached to every device at bootstrap.
  `classes/` holds per-driver-class defaults (LgTv, EMotivaXMC2, AppleTVDevice); `devices/` holds
  per-device maps for the generic IR fleet (mf_amplifier, ld_player, vhs_player, video, upscaler).
- **Optimistic IR input.** `WirenboardIRState` gained an `input` field; the IR driver records it
  on a successful `inputs`-group command — so IR input is diffable despite no feedback.
- **Layer R — Reconciler** (`infrastructure/scenarios/reconciler.py`): resolve (topology DFS) →
  diff (vs assumed `device.state`) → translate (param_map / value-map / multi-zone / toggle) →
  order (power-before-input + topology edges) → execute (gate: poll feedback / delay IR; **check
  success**). Plus diff-based teardown for switch/shutdown.
- **Wired into `ScenarioManager`** behind `WB_SCENARIO_RECONCILER` (default on): thin scenarios
  route through the reconciler; legacy scenarios keep the old sequence path. `switch_scenario`
  is diff-based; `shutdown` powers off involved devices.
- **All scenarios migrated to thin** (`source`/`display`/`audio`): movie_appletv, movie_ld,
  movie_vhs, movie_zappiti.
- **Manual steps surfaced**: `ScenarioResponse.manual_steps` + SSE `scenario_switched`/`started`.
- **Root causes fixed** (in code, mock-verified): RC1 translation (input→source etc.), RC2 silent
  failures (now surfaced), RC3 hardcoded switch power-off (now capability-aware diff/teardown).
  RC4/RC5 superseded (validation + typed diff replace the dead param check / string conditions).
- **~45 new tests**; `openapi.json` re-synced twice (WirenboardIRState.input, ScenarioResponse).

### Commits on the branch (10)
```
4c59e7e surface reconciler manual steps via the API
8a64be1 migrate LD/VHS/Zappiti to thin + IR capability maps
fc3ca3c wire reconciler into ScenarioManager (2b)
cd26203 reconciler executor + teardown (2a)
3b2847e reconciler resolve+plan (increment 1)
b263662 wire capability maps onto devices + optimistic IR input
bc9a0c6 topology Pydantic model + loader
1a5bb3c capability schema, loader, movie_appletv maps
5604874 capability maps doc + Apple TV tvOS note
d010b41 config/topology.json
```
(Design docs `c7a9352`/`912e52f`/`bf569c2` landed on `main` earlier the same day.)

---

## 2. Open items

**To finish Phase 1 — hardware verification (the only blocker to merge):**
- Run each scenario on the real Wirenboard: confirm power-on, input routing, and the manual
  Dodocus prompt actually work; tune the gating delays (`gate.delay_ms`, `poll_timeout_ms`) and
  the topology `delay_ms` (e.g. the 4.5 s upscaler settle) to real device timings.
- Verify the HDMI-ARC ordering and whether an `upscaler.input → processor.input` edge is needed
  for LD/VHS (deliberately omitted — see caveats).
- Verify the eMotiva still does HDMI video switching with both zones on (capability assumes so).

**UI follow-ups (UI repo; part of Layer 3):**
- The UI does not yet **display** the surfaced `manual_steps` (backend emits them via API + SSE).
- The UI scenario-page codegen was **not re-run** against the thin configs (it reads the retained
  `roles`, so it should still generate — unverified).

**Then (per the plan):** merge to `main` → monorepo (Phase 2, `docs/monorepo_migration_plan.md`)
→ Layer 3 runtime rendering.

**Deferred design items:** transition-aware manual notes (13.2); Apple TV "Who's watching?" tvOS
screen research (redesign §15); cross-device volume-scale normalization (latent; volume role = amp).

---

## 3. Caveats / things to watch

- **Everything is mock-verified, not hardware-verified.** The tests prove the *plan* and the
  *dispatch order/translation*; they do not prove real IR/HDMI behavior.
- **Optimistic gating.** Even "feedback" devices set state optimistically in `execute_action`, so
  the completion-poll usually returns immediately rather than waiting on real hardware. True
  completion-waiting needs a device-side "refresh from hardware" — a later refinement.
- **Upscaler power is not controlled** by the reconciler (it auto-powers with LD/VHS, per the
  hardware interview). If on hardware it does *not* auto-power, add a `power` capability to
  `config/capabilities/devices/upscaler.json`.
- **No `upscaler.input → processor.input` ordering edge** was added (not reported as needed). If
  LD/VHS show "no signal," that edge in `config/topology.json` is the first thing to try.
- **`WB_SCENARIO_RECONCILER=0`** falls back to the legacy path — but thin scenarios have no
  sequences, so they become no-ops when disabled. The flag is a kill-switch, not a dual path.
- Unrelated but open: the `aiomqtt 2.0.1` downgrade from the dependency pass is still unverified on
  real WB hardware; GitHub reports Dependabot alerts on the repo.

---

## 4. Quick reference (where things live)

| Concern | Path |
|---|---|
| Wiring | `config/topology.json` (+ `infrastructure/topology/`) |
| Capability maps | `config/capabilities/{classes,devices}/*.json` (+ `infrastructure/capabilities/`) |
| Reconciler | `infrastructure/scenarios/reconciler.py` |
| Wiring point | `domain/scenarios/service.py` (`_switch_via_reconciler`, `shutdown`) |
| Thin scenarios | `config/scenarios/movie_*.json` |
| Manual-step API | `presentation/api/routers/scenarios.py` (`ScenarioResponse.manual_steps`) |
| Tests | `tests/unit/test_{topology,capabilities,reconciler}.py`, `tests/test_scenario_switch_reconciler.py` |
