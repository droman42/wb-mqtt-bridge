# Scenario Redesign — Implementation Progress & Session Notes

- **Status:** Phase 1 (backend) implemented; **partial hardware verification done** (clean boot
  on the live system + amp control on both entry points). Full scenario reconciler run on
  hardware still pending.
- **Branch:** `feat/scenario-redesign` (not merged to `main`). Full test suite: **274 pass**.
- **Last updated:** 2026-05-22.
- **Design contracts:** `docs/design/scenarios/scenario_system_redesign.md` (Layers 0/1/2/R),
  `docs/design/ui_backend_contract.md` → "Layout Manifest & Runtime Rendering" (Layer 3),
  `docs/archive/monorepo_migration_plan.md` (Phase 2).

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

## 1a. Hardware-verification session (2026-05-22)

First real-hardware run of the redesign. **The backend now boots clean on the live system** (all
13 devices initialize, 4 thin scenarios load, topology + capability maps attach, "System startup
complete"), and **amp control is verified end-to-end on both entry points** (FastAPI *and*
WB-UI/MQTT). Normal SIGTERM shutdown exits cleanly in ~2 s.

**Lifecycle-robustness cluster** (so the bridge survives real-world device states):
- **Bug 2 — `load_scenarios` is non-fatal** (`e697e8f`): a scenario referencing an offline device
  (or a malformed file) is logged + skipped, not `SystemExit`. One eMotiva in standby used to
  brick startup.
- **Keep failed-setup devices registered** (`9018254`): an off/unreachable/hung device stays
  registered (disconnected) instead of being dropped — scenarios still load, it stays controllable.
- **Hardware-transparent shutdown + correct assumed-state persistence** (`b77bafa`): split
  `ScenarioManager.deactivate()` (explicit power-off) from `shutdown()` (process stop — leaves the
  gear as-is, so a bridge restart never powers down the AV system); stop persisting teardown
  states (they corrupted the optimistic assumed state); the old sync-persist-on-shutdown (which
  always raised "event loop is already running") is gone.
- Remaining lifecycle tails (defensive startup cleanup, teardown noise, device auto-reconnect,
  AppleTV driver hygiene) parked in `docs/action_plan.md` P4.

**Three IR-driver bugs — found ONLY on hardware, missed by the mock tests** (the amp test):
1. `result.success` on a `CommandResult` *dict* (`e3e1cf6`): the IR fired but the command reported
   failure and the optimistic `power` state was never updated — would mislead the reconciler.
2. **Double IR blast on the API path** (`1717032`): the driver published the IR directly *and*
   returned it as `mqtt_command`, which the action router (`devices.py`) re-published.
3. **WB-UI/MQTT control silently dead** (`7f82915`): `WirenboardIRDevice` overrode `handle_message`
   with a legacy version that matched the topic *without* `/on` and only *returned* `mqtt_command`
   instead of executing — shadowing the working `BaseDevice.handle_message → wb_service` path.
   Removed the override; the IR device now uses the base path like every other device.

**Other findings:**
- The **kitchen_hood** Broadlink timeout was a **hung device** (power-cycle fixed it), not a code
  or VPN/network regression — broadlink lib unchanged (0.19.0), device reachable, ARP MAC matched.
- **AppleTV / pyatv 0.17.0** (`eaecb7c`): the dependency pass bumped pyatv, which added the
  abstract `AudioListener.volume_device_update` — now implemented; both Apple TVs connect.

**Key lesson (testing strategy):** the mock-based reconciler/scenario tests verify plan / order /
translation but **do not exercise real device-driver handlers**, so driver bugs (the three above)
only surface on hardware. Added **real-driver tests** that drive `execute_action(...)` for the IR
device (power toggle flips state, single publish, no `mqtt_command`) — prefer these for any driver.

### Commits this session
```
7f82915 wirenboard_ir: remove broken handle_message override (WB-control path)
1717032 wirenboard_ir: stop double-publishing IR on the API action path
e3e1cf6 wirenboard_ir: power handlers use dict access on CommandResult
928e296 action_plan: park lifecycle-robustness leftovers in P4
b77bafa lifecycle: hardware-transparent shutdown + correct assumed-state persistence (#3)
9018254 devices: keep failed-setup devices registered (don't drop)
e697e8f scenarios: load_scenarios is non-fatal — skip, don't SystemExit (Bug 2)
eaecb7c apple_tv: implement AudioListener.volume_device_update (pyatv 0.17.0)
```

**Still pending:** the **full scenario reconciler test on hardware** (activate a scenario with
`WB_SCENARIO_RECONCILER=1` — drives the whole AV chain: TV + eMotiva + source + amp, with topology
ordering + manual steps). NOTE: the amp's optimistic `power` state is currently **drifted** (the
earlier buggy run left it stale) — resync before/at that test.

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

**Then (per the plan):** merge to `main` → monorepo (Phase 2, `docs/archive/monorepo_migration_plan.md`)
→ Layer 3 runtime rendering.

**Deferred design items:** transition-aware manual notes (13.2); Apple TV "Who's watching?" tvOS
screen research (redesign §15); cross-device volume-scale normalization (latent; volume role = amp).

---

## 3. Caveats / things to watch

- **Partly hardware-verified (2026-05-22): clean boot + amp control on both paths** (see §1a). The
  **full scenario reconciler run** (power-on, input routing, gating delays, the manual Dodocus
  prompt, HDMI-ARC ordering) is still only **mock-verified** — that's the remaining hardware test.
  The mock tests prove plan/order/translation but not real IR/HDMI behavior or driver handlers.
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
