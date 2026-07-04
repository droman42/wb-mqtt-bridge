# Action Plan — wb-mqtt-bridge

**Status:** Living master plan. Updated 2026-06-06.
**Scope:** The `wb-mqtt-bridge` **monorepo** (`backend/` + `ui/` + `wb-rules/` + `ops/` + `docs/`). The
UI is no longer a separate repo — it was merged in during Phase 2.

This document captures the project state and a prioritized action plan, revised as we work.

---

## 0. Document map — master-doc convention (recorded 2026-05-25)

**`docs/action_plan.md` (this file) is the master driving document** — the overarching plan plus an
index of the **revision-log journal**. The dated history itself lives in
[`docs/action_plan_journal.md`](action_plan_journal.md) (extracted 2026-06-06 to keep this plan
focused on forward work); completed phases are frozen in
[`docs/action_plan_DONE.md`](action_plan_DONE.md) (by workstream), with completed-task IDs aliased
from the old positional scheme in [`docs/action_plan_aliases.md`](action_plan_aliases.md) — one
ledger, every ID in exactly one file. **The ledger now uses stable `PREFIX-N` workstream IDs**
(`DRV/SCN/VWB/UI/OPS/CORE/DOC`); see "How to use this file" below. **Read the journal first** in
any session for context on recent work; everything else hangs off this file. As of 2026-05-25 the major redesign is delivered and hardware-verified
(scenario reconciler · monorepo · Layer-3 runtime rendering + the build-time-codegen cutover). What
remains, by workstream: **VWB** (voice integration + native WB onboarding — HIGH PRIORITY; the former
§P3.7), **SCN** (round-2 music scenarios + the mandatory scenario↔WB design; former §P3.6/§P4 #7),
**DRV** (the per-driver HW rack pass + driver features), the **Acceptance gate** (former §P4 #1–#5),
and the **DOC** ledger/doc-reconciliation series.

Roles of the other docs **now** (they were "driving" during the redesign; they've since settled):
- `docs/design/ui_backend_contract.md` — **LIVING reference**: the UI↔backend contract + the
  steady-state Layer-3 runtime-rendering contract. Consult it for how the UI consumes the backend. (The
  frozen per-step Layer-3 *rollout* record moved to `docs/archive/layer3_rollout_record.md`, DOC-10.)
- `docs/design/scenarios/scenario_system_redesign.md` — **IMPLEMENTED → as-built spec** for the scenario
  architecture (Layers 0/1/2/R + §17 groups→capabilities). Describes what was built; not driving.
- `docs/design/canonical_first.md` — **DECIDED design (SCN-4, 2026-07-04): target actuation
  architecture** — the scenario proxy (`scenario_manager`), canonical-first convergence (catalog/
  canonical/state as the one client contract for UI + voice + WB), derived param descriptors.
  **Drives SCN-6 / SCN-7**; its §6 projection rides VWB-15.
- `docs/archive/scenarios/scenario_redesign_progress.md` — **archived 2026-06-30 (DOC-10)**; frozen
  session log, superseded by the as-built spec above.
- `docs/archive/scenarios/layer3_step0_layout_analysis.md` — **archived 2026-06-30 (DOC-10)**; frozen
  Step-0 working artifact, now embodied in the as-built spec §17 + the placement engine.
- `docs/archive/monorepo_migration_plan.md` — DONE → historical.
- `project.md` / `architecture.md` / `conventions.md` / `docs/adr/*` — foundational project docs; the
  eventual master *set* once the plan is exhausted.

**Convention:** the project stays **plan-driven** (this file is master) until §P3.6 + §P4 land; then
it shifts to **architecture-driven** (`project.md` / `architecture.md` / `ui_backend_contract.md` as
the master set), the redesign specs fully retire to history, and a project-wide doc reconciliation
(tracked separately) formalizes the handover. **Until then: this file is master.**

**Development-process invariants live in [`CLAUDE.md`](../CLAUDE.md) → "Development process — invariants",
not here** (single source of truth — always in context = always enforced). This plan is the ledger those
invariants reference (`single-task-ledger`, `read-at-start-record-at-completion`, `one-active-journal`,
`task-start-reconciliation`); see CLAUDE.md for the rules, by stable slug name.

---

---

## How to use this file

**Identity.** Every task has a stable ID **`PREFIX-N`** (e.g. `DRV-3`, `VWB-10`) — assigned once,
never renumbered, never reused. The prefix is the workstream (below); the number is a serial with no
priority/order meaning. Old positional IDs (`#13`, `§5.1 #7`, `P4 #7`) resolve via
[`action_plan_aliases.md`](action_plan_aliases.md).

**Workstreams** (stable buckets): **DRV** device drivers · **SCN** scenarios/topology/reconciler ·
**VWB** voice-integration + native WB onboarding · **UI** config-ui · **OPS** docker/CI-CD/deploy/ops ·
**CORE** backend core/architecture · **DOC** docs/ledger/process.

**Status:** `- [ ]` open · `- [x]` done · `- [~]` partial/paused. Inline markers (with reason):
`DOING` · `BLOCKED` · `DEFERRED` · `PARKED` · `HW-GATED` (waiting on the user at the rack).
**Priority** is a separate tag `[P0]`/`[P1]`/`[P2]`. **Milestone** tag: `[house]` (required for the
house-works gate — see "Acceptance gate") · `[later]` (post-milestone) · `[parked]` (dormant).

**Two-file split:** this file holds **open + partial** tasks by workstream; completed tasks move to
[`action_plan_DONE.md`](action_plan_DONE.md) (by workstream) on completion, same change as the journal
entry. One ledger, **every ID in exactly one file**. The dated narrative lives in
[`action_plan_journal.md`](action_plan_journal.md) (frozen back-refs resolve via the alias map).

---

## Workstreams

### DRV — Device drivers

- [ ] **DRV-1** `[P0]` `[house]` `DOING` — **#7 — Per-driver HW verification pass, pre-P3.6 scenarios (IN PROGRESS — `LgTv` + `AppleTVDevice` DONE; `EMotivaXMC2` input redesign DONE + input HW-verified 2026-05-29 [power/volume/zones/scenario pending]; `BroadlinkKitchenHood` DONE 2026-05-29; `WirenboardIRDevice`/mf_amplifier BROKEN 2026-05-29).** Methodology gate added 2026-05-27 after the user's instinct (matches [[mock-tests-miss-driver-bugs]]): scenarios are composites; verifying scenarios first masks driver bugs inside composite flows and makes diagnosis confusing. So verify each of the seven driver classes on hardware **before** the P3.6 scenario pass. **Subsumes §5.1 #3 (A77 re-verify) — A77 is just one row of the pass.** Same shape per driver (and per config instance for the multi-instance ones):
  - **Setup.** Bridge starts cleanly; driver registers with no errors; the WB virtual device appears with `meta/available=1`; the device card shows in the WB UI.
  - **Action set.** Walk the concrete action list (below). State persists across a bridge restart (assumed-state DB does its job).
  - **State read-back.** Any value topic the driver publishes (`/devices/<id>/controls/<x>`) updates within ~1 s of the change.
  - **Error recovery.** Disconnect the device briefly (pull power, drop off Wi-Fi, etc.) → driver re-establishes cleanly on next attempt, no leaked tasks/sockets in the bridge log.

  | Driver | Instance(s) | Action set to walk |
  |---|---|---|
  | `LgTv` (asyncwebostv) | **LG living: DONE 2026-05-27** · LG children: deferred | DONE on the living-room OLED77G1RLA: power on (WoL → connect → 3 subscriptions register cleanly post-`tvpower` URI flip) · volume± + mute (subscription delivers physical-remote deltas via the `volumeStatus` unwrap) · foreground-app transitions (home / launch_app / browser) · `power_state` subscription delivers physical-remote off in ~0.5 s with `reason=remoteKey`, ~45 s before the WebSocket finally closes (audit canary closed) · `current_app` + `input_source` coalesced via `app_id_to_input_id` helper · pointer move + tap-click on the pointer socket. DEFERRED (non-blocking): `children_room_tv` smoke pass (config-only, identical driver — expected to mirror); reconnect-cycle test (TV unplug → reconnect, exercises asyncwebostv 0.3.4 close-callback registry + the discard-old-controls reconnect contract). See §6 entry 2026-05-27. |
  | `EMotivaXMC2` (pymotivaxmc2 0.6.8) | **input redesign DONE + input HW-verified 2026-05-29**; power/volume/zones + scenario pending | Input switched from physical HDMI connectors (`hdmiN`) to **logical sources** (`sourceN` via `select_source` + `get_input_names`) — `hdmiN` did a raw-connector switch (black-rectangle) at the rack; topology `processor:hdmiN`→`sourceN`, reconciler unchanged (data-driven). source1 (ZAPPITI) + source2 (AppleTV) verified clean. Remaining: zone1/zone2 power + independence, volume (+ the ack-reliability + protocol-impossible mute-read-back findings), scenario route. See §6 2026-05-29. |
  | `AppleTVDevice` (pyatv) | **living + children: DONE 2026-05-28** (tvOS 26.5) | DONE on both units: power on/off + clean connect (pyatv git-pinned to master SHA `9177803` for the `TVRCSessionStart` fix — tvOS 26.5 silently drops Companion *query* commands without it; see §6) · app list works · nav (up/down/left/right/select/menu/home) + playback (play/pause/stop/next/prev) via Companion HID · pointer pad: drag→directional gesture + tap→select (dx/dy param fix + capability `click`→`select`) · **volume±: absolute `set_volume` removed** (no `_mcF` Volume flag on tvOS 26.5 — Companion volume is dead), routed through the **WB IR blaster** (living `wb-msw-v3_207` ROM5/6; children `wb-msw-v3_220` ROM1/2); volume UI = up/down buttons, mf_amplifier-style (no slider/mute). app-launch-by-name works; dynamic-launch UX deferred to §5.1 #2. See §6 2026-05-28. |
  | `AuralicDevice` (openhomedevice + IR fallback) | Auralic Altair G1 (**wired LAN**) | **Robustness hardening pass DONE 2026-05-29** (mock-tested; **HW walk still owed**): per-call timeouts, liveness-probe-first poll, **auto-rediscovery** on stale connection (dynamic-port aware), quiet transition logging, `skip(1)`/`skip(-1)` bug fix, None-volume tolerance, isolated metadata, async SSDP discovery. OpenHome confirmed the correct protocol (Auralic has no usable UPnP-AV) — see §6 + [[auralic-streamer-openhome-direction]]. **Remaining (all gated on the HW walk at the rack; wired LAN):** (1) **bench-probe** the unit's real OpenHome services first — sources list, whether a Volume service is present, standby-vs-deep-sleep behaviour — to rule out a plain discovery/connectivity issue; (2) **action walk** — power on/off (IR), play/pause/stop, next (`skip(1)`) / previous (`skip(-1)`), volume±, mute, now-playing read-back; (3) **auto-reconnect cycle** (the headline fix to validate) — reboot or standby→wake the unit and confirm the periodic loop rediscovers the new HTTP port within `reconnect_interval` and state recovers, *without* an IR power-on; (4) **#7 setup/error-recovery** — clean start, WB virtual device `available=1`, state survives a bridge restart, brief disconnect → clean re-establish; (5) **follow-ups contingent on results** — `previous` now works (`skip(-1)`) but is **not exposed** in `streamer.json`/`AuralicDevice.json` (add a Previous button if wanted); if the unit has no Volume service, settle the volume UX; tune `op_timeout`/`reconnect_interval` to observed timings. Pass ⇒ streamer is ready for P3.6 `music_auralic` scenario verification (streamer → `mf_amplifier:balanced`). |
  | `WirenboardIRDevice` (aiomqtt → WB IR) | DVDO, Pioneer LD, Panasonic VHS, **MF amplifier: FIXED 2026-05-29**, Zappiti, Dodocus | per-instance: 2–3 representative actions from the device's configured action set; full coverage isn't needed if a sampled action proves the IR path. **mf_amplifier (Musical Fidelity M6si): root-caused + fixed** — IR was dead because `wb-msw-v3_207` bank 65 was stuck in edit mode (coil `5199+65`=1), which made the blaster return "Slave Device Busy" for *every* Play. Caused by an `ir_restore.py` bug (no edit-exit on a busy commit), **not** firmware. Cleared the lock live (amp responds) and hardened `ir_restore.py` (guaranteed edit-exit + busy-retry + preflight unstick). See §6 2026-05-29. |
  | `RevoxA77ReelToReel` (aiomqtt → WB IR) | A77 | stop / play / ff / rewind / record (gated); covers §5.1 #3 |
  | `BroadlinkKitchenHood` (RF, broadlink) | **kitchen_hood: DONE 2026-05-29 (tested working)** | hood power, fan speed, light on/off (orphan — no live scenario uses it, but verify the driver still works after the hexagonal pass) |

  **Also covered as a side-effect:** the aiomqtt 2.0.1 downgrade HW verify (every IR-via-WB driver row exercises the aiomqtt stack). Pass = ready to go into P3.6 scenario verification with isolated-driver confidence.

- [ ] **DRV-2** `[P0]` `[house]` — **Apple TV app launching** — `Запуск приложений на AppleTV`.

- [ ] **DRV-3** `[P2]` `[later]` — **IR-code learning page** — capture codes from physical remotes (`Сделать страничку для обучения IR кодам с пультов`).

- [ ] **DRV-4** `[P2]` `[later]` — **LG TV `audio_output` API — clean rework of the "press Home" hack + enable a true `watch_tv` (TV speakers only) scenario.** Discovered 2026-05-30: `asyncwebostv.controls.MediaControl` already exposes `set_audio_output(value)` (`ssap://audio/changeSoundOutput`) + subscribable `get_audio_output` (`ssap://audio/getSoundOutput`); valid values per library's `list_audio_output_sources` are `['tv_speaker', 'external_speaker', 'soundbar', 'bt_soundbar', 'tv_external_speaker']` (likely incomplete for newer webOS — `external_arc`, `external_optical`, `bt_headset`, `mobile`, `lineout` exist on some firmware; verify on OLED77G1RLA via `get_audio_output` first). **Architectural implication:** the TV's audio output is an INDEPENDENT axis from its video input — webOS lets you have HDMI 1 on screen while audio routes via ARC to the AVR. The current `tv_on_speakers` "press Home" mechanism (driver translates `set_input_source(arc)` → `handle_home`; commit `e5dffa4`) was correct for its PRIMARY video-side purpose (force TV out of HDMI input mode for the watch-TV-with-amp scenario) but uses the wrong axis. **Clean rework when next at LG TV:** (1) add `state.audio_output` field (subscribable); (2) add `handle_set_audio_output` action; (3) add `audio_output` capability domain with `source_modes` (reuses the symmetric src_port mechanism but on a different capability); (4) topology link's src_port becomes the audio-output value, translated in the driver to the webOS string (`arc` → `external_arc`, `tv_speaker` → `tv_speaker`, etc.). **Enables a clean `watch_tv` scenario** (TV speakers only, all other devices off — discarded today because the press-Home hack didn't fit). **HW verification gates before coding:** (a) exact webOS audio-output value for HDMI ARC on the OLED77G1RLA (call `get_audio_output` while on the current ARC-routing setup); (b) whether explicit ARC audio output is enough for eMotiva ARC engagement without forcing TV to internal mode (i.e., does the precondition observed today — "TV must be in TV mode" — go away if the TV is just explicitly broadcasting on ARC?); (c) whether the eMotiva still needs the power-cycle workaround for ARC engagement, or whether CEC + TV-broadcasting-on-ARC is sufficient; (d) subscription delivery reliability for `get_audio_output`. **No urgency** — current `tv_on_speakers` works for its purpose (still HW-pending anyway). File as a coherent LG-TV cleanup pass.

- [ ] **DRV-5** `[P1]` `[later]` — **Per-action `force` flag — UI escape hatch for optimistic-state desync.** Adds a reserved boolean param `force` honored by handlers that contain idempotence guards ("skip if state already at target"). The optimistic-state model is correct overall (see [[state-sync-chokepoint]] + Harmony approach in `docs/design/scenarios/scenario_system_redesign.md`), but for **IR/RF devices with no feedback channel** the guards can lock the user out of resyncing: if optimistic state says `power=on` but the device is actually off (e.g. someone pressed the physical remote), clicking Power-On on the device page hits the guard at `wirenboard_ir_device/driver.py:235` → returns "already on, skipped" → **no IR sent, no state update** → the desync is unfixable from the UI. **Verified guard inventory** (grepped 2026-05-30, 8 idempotence guards total across 3 drivers):
  | Driver | Guards | Channel | Force value |
  |---|---|---|---|
  | `WirenboardIRDevice` | `power_on` (`:235`), `power_off` (`:270`) | IR, one-way | **HIGH** — only escape from desync trap |
  | `EMotivaXMC2` | `power_on` (`:745`), `power_off` (`:890`, `:914`), `set_input` (`:1079`), `set_volume` (`:1186`) | WebSocket, feedback | LOW — useful when an ack is missed (logged eMotiva issue) |
  | `AuralicDevice` | `power_on` (`:643`) | UPnP, feedback | LOW — feedback re-syncs anyway |

  `Revox A77`, `Broadlink Kitchen Hood`, `LG TV`, `Apple TV` have **zero** idempotence guards. For IR drivers this is structural: input/volume/channel/transport always send (the driver can't probe), so there's nothing to guard against — **`force` is only meaningful for the 2 IR power guards** in practice. **Wiring** (~30 LoC backend, ~50 LoC UI, no protocol change): (1) each guarded handler reads `params.get("force", False)` and skips the guard when truthy — existing `update_state(...)` call afterwards is unchanged; (2) capability map declares `force` on actions that honor it, so the UI only renders the checkbox where it does something; (3) UI adds a transient "Force next command" checkbox on the device-action panel (auto-unchecks after one fire, visually distinct while armed); (4) one regression test per guarded handler asserting force bypasses the skip. **Critical distinction:** force bypasses **idempotence** guards, NEVER **availability** guards (e.g. Auralic `:728` `_deep_sleep_mode and not openhome_device` is a "device unreachable" check, NOT idempotence — must not be force-bypassed; same for any `if not self.client or not self.state.connected` pattern). Convention: a comment-marker or helper like `_should_skip_for_idempotence(...)` at each guard site to make the distinction visible. **Explicit non-goal — no scenario-level `force`.** Considered and rejected: a scenario-activation force flag (bypass `reconciler.py:148/162/228` `already_satisfied`) would fire commands at every device in the scenario, including toggle-code devices (Revox/Pioneer/Panasonic IR) that would flip the wrong way, and devices that were correctly in state that get commanded anyway. Per-action force at the device level is the precision tool; once optimistic state is corrected per-device, the next normal scenario activation works because the reconciler reads fresh `device.get_current_state()`. **What this does NOT fix:** (a) toggle-code IR power (no guard to bypass — the toggle handler at `wirenboard_ir_device/driver.py:206` always sends and just decides which state to claim afterwards; the deeper issue is the state claim, not the send); (b) the underlying optimistic-state fragility — `force` is a user-mediated escape hatch, not feedback. For toggle-code cases, a complementary "set state without acting" affordance (writes `update_state` directly, no IR) would help — separate proposal, not part of this item. Hexagonal-LAW clean (handler-local change + capability flag in infra; no domain touch).

- [ ] **DRV-6** `[P2]` `[later]` `HW-GATED` — **IR ROM backup/restore tooling — cleanup + remaining large-code functional check.** **UPDATE 2026-05-29:** the functional test happened via mf_amplifier (207 banks 17–25) and exposed a real `ir_restore.py` bug — a busy/interrupted commit could leave a bank **stuck in edit mode**, which locks the *whole* blaster's playback (bank 65 was stuck → Modbus exc 06 "Slave Device Busy" on every Play). **Fixed live + `ir_restore.py` hardened** (guaranteed edit-exit, busy-retry `WRITE_RETRIES`, preflight `clear_stuck_edit`; see §6 2026-05-29). Restore *content* is vindicated (ROM bytes + ROM-Size match the backup). **Tooling cleanup DONE 2026-05-29** (see §6) — only the functional *play* test the user owns remains. The toolset is now `wb-rules/{ir,ir_common,ir_backup,ir_restore,ir_verify}.py` + `scp_ir_tools.sh`, fronted by a unified CLI **`ir.py`** (`ir.py backup|restore|verify …`, shared bus flags via argparse subparsers; each module stays standalone-runnable): `ir_common.py` is the shared, **general-purpose** core (register map + `modbus_client` wrapper + codec + jitter-tolerant `compare` + the `bus_window` service-stop context, **no A/V knowledge**); `ir_backup.py` now dumps **every non-empty bank** read from the device itself (was: only banks an A/V config referenced — CSV schema dropped the `referenced_by` column); `ir_verify.py` (promoted out of the deleted `temp/`, folds the one-off `diag_*` scripts) does a read-only jitter-tolerant verify with a first-diff dump on mismatch; `scp_ir_tools.sh` deploys them to `/tmp/ir-tools` (push, optional `pull` of produced CSVs). They back up and re-write WB-MSW v3 IR ROM banks so a firmware upgrade can't lose learned codes — the AppleTV volume IR (`wb-msw-v3_207` ROM5/6 + `wb-msw-v3_220` ROM1/2, §5.1 #7 AppleTV row) rides on this. Restore is **HW-verified clean on 220** (2 banks) **and 218** (14/14) once the verify read gets a 6× spaced retry (`f0213af`; the earlier failures were transient post-commit reads). **207** has **7 persistent mismatches** on its large learned `ld_player`/`vhs` codes (ROM65/66/68/69/70/78/79): the stored copy differs from the backup at **capture-jitter magnitude** (±~3 quanta) and is **stored-side, not corruption** — `diag_chunk.py` proved the first-diff index is invariant to read-chunk size, and these are multi-repeat IR frames that already carry per-repeat jitter in the backup itself. **Decision gated on a functional IR test the user owns** (fire e.g. ROM65 `ld_player:tray` at the real device):
  - **If the functional test FAILS** → back to wb-rules: the jittery banks aren't reproducing usable codes → investigate write fidelity / an alternate write path / re-learn those banks.
  - **If it PASSES** → byte-exact verification is the wrong bar for learned multi-repeat codes → byte-exact was already replaced by the jitter-tolerant `--tol` compare in the cleanup (no further script work). **Cleanup itself is DONE regardless of the play result** (it was the right refactor either way); a *failing* play test would reopen the FAILS branch (write fidelity / re-learn), not the scripts. See [[wb-msw-ir-restore-supported]]; commits `a7d7e5f`/`f2dbfc8`/`b46a8f3`/`f0213af`/`34fd1ee`.

- [ ] **DRV-7** `[P2]` `[parked]` `PARKED` — **PARKED: ESP32 firmware scaffold for the 4 transport-source bridges** (Revox A77 + Revox B215 + Pioneer CLD-D925 + Panasonic NV-FS90). Lives at `ESP32/` (PIO layout: `include/` + `src/` + `docs/`) — single image, identity selected at runtime via NVS + MQTT `/provision`. ~95% shared core (Wi-Fi auto-light-sleep + Wirenboard MQTT + MQTT-triggered `esp_https_ota` + record-arming + reel-motion interlock); 3 drivers cover 4 decks (Pioneer + Panasonic share `driver_ir.cpp` as baseband IR). **2026-05-26: rewritten from the original Arduino scaffold to pure ESP-IDF (C++17, framework=espidf, no Arduino libs); custom dual-OTA partition table (1.5 MB app slots); builds clean end-to-end from `pio run -t fullclean`** (RAM 11.2%, Flash 59.6% of 1.5 MB). Authoritative spec: `ESP32/REQUIREMENTS.md`. Subproject conventions + setup gotchas: `ESP32/CLAUDE.md`. Per-device hardware handoffs: `ESP32/docs/`. Deferred: bench fill-ins (IR codes, B215 frame values, GPIO/timing tuning) and first-light hardware verification, until **"everything works in my home"**. **Not in the active workstream** — do not pull into pre-P4 unless the user reactivates it.

- [ ] **DRV-8** `[P2]` `[later]` — **Roborock S7 vacuum — review & finish the design (DESIGN task).** The
  bridge's first **interactive-map appliance** (live state *plus* an interactive map — unlike the AV gear's
  remote layout or the WB-passthrough lights). A substantial **draft** design already exists —
  [`docs/design/roborock_vacuum.md`](../design/roborock_vacuum.md) (started 2026-06-09) — but it is
  **WIP with open questions flagged inline** and had **no plan ID** until now (filed 2026-06-30 to close
  the `every-task-in-the-ledger` gap — the design work happened untracked). **Deliverable
  (`design-then-implement`):** review the draft with the user, resolve the inline open questions, and
  **lock the design** — completion means the design is *done and recorded*, **not** that code shipped.
  **On completion, file the implementation follow-ups** as their own DRV tasks (the `RoborockDevice`
  driver + the interactive-map UI page). No driver/page work starts before the design locks.

---


### SCN — Scenarios / topology / reconciler

- [ ] **SCN-3** `[P0]` `[house]` `HW-GATED` — **Round-2 music scenarios.**

**BUILT 2026-05-25 (mock-validated; pending hardware verification).** Wiring interview done; the four
round-2 **music** scenarios are authored + reconciler-driven (`f1455c6`, `368fbcb`, `59fb661`):

| Scenario | Source | Amp routing | Notes |
|---|---|---|---|
| `music_auralic` | `streamer` (Auralic) | direct → `mf_amplifier:balanced` | controllable; playback on the streamer |
| `music_reel` | `reel_to_reel` (Revox A77) | Dodocus **Reel** → `mf_amplifier:cd` | controllable (IR); Dodocus note auto-surfaces |
| `music_tape` | `b215` (Revox B215) | Dodocus **Tape** → `mf_amplifier:cd` | **passive** manual source; amp volume + "press Play" note |
| `music_turntable` | `kuzma` (Kuzma Stabi S) | → Sugden PA4 → Dodocus **Phono** → `mf_amplifier:cd` | **passive**; amp volume + manual notes (power on Sugden, set hub, cue the record) |

The Dodocus RCA hub is now the central analog selector (5 positions: ld/vhs/reel/tape/phono, all →
amp `cd`). The two passive sources (no driver) are modelled as **manual topology nodes** + a one-line
reconciler change (a manual-node `source` anchors the topology path so the amp input + the hub note
resolve, but isn't itself controlled) — see §6 (2026-05-25). `kitchen_hood` stays appliance-only.

**Remaining:** **hardware verification** of the four (amp powers + selects the right input; Dodocus
manual notes show; Auralic/A77 playback; passive ones show the right manual steps). The **children's
room** (children_room_tv + appletv_children) was **deferred by the user** (skipped this round) — a
possible round-3.


- [ ] **SCN-5** `[P0]` `[house]` — **Transition-aware manual notes (the activation-time half).** Surface a
  topology manual-node's instruction **only when its link activates** in a transition — e.g. the Dodocus
  RCA-hub "set to LD/VHS" prompt appears only when switching onto the analog path. **Load-bearing:**
  without it the LD/VHS scenarios have *no audio*. Activation-time work — the reconciler diffs which
  topology links activate and emits the bound note; rides the reconciler/activation path, not the scenario
  page. Baseline static notes already shipped (SCN-2, 2026-05-26); this is the deferred transition-aware
  half (redesign §13.2 — the design-doc record that DOC-10 archives, so this is its standing home now).


### VWB — Voice-integration + native WB onboarding

**Context (the P3.7 push — design narrative preserved from the former phase section):**

**Driving doc:** `docs/design/voice_integration_contract_draft.md` (AGREED bridge ↔ Irene contract).
Sister-project counterpart: `wb-mqtt-voice/docs/design/mqtt_integration.md` §10 (Irene's ARCH-8,
**blocked on this**).

**Strategic shift.** The bridge becomes the **single authoritative device catalog + actuation
backend for the whole house** — native Wirenboard gear *and* the AV devices it already bridges.
wb-rules retains all rule/automation logic on the controller (unchanged); the bridge MIRRORS
native control state by subscribing to MQTT value topics. Two writers (bridge + wb-rules), one
truth (the broker). The contract has three pillars:

- **A. Canonical action endpoint** — `POST /devices/{id}/canonical {capability, action, params}`,
  thin façade over `perform_action` via the existing capability map. 6-code structured error enum
  (HTTP-mirrored); synchronous with a **500 ms** default value-topic-echo timeout; subscribes to
  `wb-mqtt-serial`'s per-device error topic for deterministic offline detection.
- **B. Voice-friendly catalog read** — `GET /system/catalog` (neutral, not voice-specific), flat
  capability-shaped projection of devices + rooms; **all locales** for both rooms and devices;
  sensors as ONE `sensor` capability with read-only `fields`; **one device, one room** (whole-house
  controls like "выключи свет везде" resolved as a SINGLE canonical call against an aggregate
  device in `global` — e.g. `all_lights` — NOT by Irene iterating rooms; the bridge ships the
  aggregate devices the supported voice command set needs);
  refresh nudge via retained `bridge/catalog/version` (content hash).
- **C. Native WB onboarding** — generic **data-driven WB-passthrough driver** in
  `infrastructure/devices/wb_passthrough/`; explicit param types per command (no
  `meta/type` introspection); composite payloads (RGB, HVAC) handled **inside** the driver via
  typed `state_topics` metadata + `payload_template` (folded into #19; **no separate
  adapter layer**); `global` is a regular room holding whole-house aggregate devices; loop
  guard on the state-sync chokepoint (no WB-publish callback for passthrough devices).

**Vertical slice first** — prove the whole stack against one live voice command before bulk
onboarding:

Slice total: ~3-4 dev days + a rack/Irene verification pass.

**Bulk onboarding** (after the slice proves out):

Bulk total: ~9-11.5 dev days (was ~7-9.5; +2 for #26 value-label layer added 2026-06-09).

**Pre-work findings — A1 (2026-06-06)**

Slice concrete artifacts — ready for #13 (driver) / #14 (config) / #15 (canonical endpoint) to
consume. Test room: **cabinet** (where the user works; observation closes the loop).

Three files to author for the slice:
- `backend/config/devices/wb-devices/cabinet/cabinet_spots.json` — WB-passthrough device
  config (new directory convention, see below); declares `capability_profile: "light_switch"`
- `backend/config/capabilities/profiles/light_switch.json` — shared capability profile (the
  canonical→native map) — written **once** for every relay-light in the house
- `backend/config/rooms.json` — extend with `cabinet`

**Directory convention — `wb-devices/<room>/<device_id>.json`** (settled 2026-06-06;
naming rule refined 2026-06-08). Existing AV configs stay flat at
`backend/config/devices/*.json`. **WB-passthrough configs live in
`backend/config/devices/wb-devices/<room>/<device_id>.json`** — one config file per logical
device, grouped by its (single) room. **A device belongs to exactly one room.** Devices
with no physical room (whole-house aggregate devices — see #22) live in
`backend/config/devices/wb-devices/global/<device_id>.json` and use room id `global`.
**Sub-directory name = the bridge's room_id (matches `rooms.json` exactly), NOT the WB-UI
dashboard id where they differ.** Examples: `wb-devices/living_room/` (bridge id
`living_room`, WB dashboard `livingroom`); `wb-devices/children_room/` (bridge id
`children_room`, WB dashboard `children`); `wb-devices/shower/` (bridge id `shower`, WB
dashboard `wc`); `wb-devices/cabinet/` (both match). Earlier draft of this paragraph said
"use WB-UI dashboard ids" — corrected mid-#23 once the inconsistency surfaced (device_id
prefix, room_id, and subfolder all now use the SAME identifier). Sensors follow the same
layout (e.g. `wb-devices/living_room/living_room_sensors.json`); no separate `sensors/`
subtree. The config scanner (`utils/validation.py`) recurses into subdirectories, so flat
AV configs continue to load unchanged.

**`cabinet_spots.json`** (WB-passthrough driver consumes this):

```json
{
  "device_id": "cabinet_spots",
  "device_class": "WbPassthroughDevice",
  "config_class": "WbPassthroughDeviceConfig",
  "names": {"ru": "Споты", "en": "Spots"},
  "capability_profile": "light_switch",
  "room": "cabinet",
  "commands": {
    "power_on":  {"topic": "/devices/wb-mr6c_51/controls/K4/on", "value": "1"},
    "power_off": {"topic": "/devices/wb-mr6c_51/controls/K4/on", "value": "0"}
  },
  "state_topics": {
    "power": "/devices/wb-mr6c_51/controls/K4"
  }
}
```

No explicit error topic field: per A3 below, errors are per-CONTROL and the WB-passthrough
driver subscribes to `<state_topic>/meta/error` automatically for every state mirror.

**Capability profiles — shared maps for the WB-passthrough family.** A new directory
`config/capabilities/profiles/<profile>.json` holds capability maps shared by many devices
of the same fixture kind. The resolver order is class → **profile** → per-instance override
(profile loaded only when `capability_profile` is set; AV devices set it to `None` and the
path stays byte-for-byte unchanged). Slice 1 uses **`light_switch`** = `power.on/off` →
`power_on/power_off` (the only capability cabinet_spots needs). The catalog of profiles we'll
author over the slice + bulk (matches §P3.7 A2's composite-control shapes):

| Profile | Capabilities | Used by (approx) |
|---|---|---|
| `light_switch` | `power` | wb-mr6c relay channels — ~25 |
| `dimmable_light` | `power` + `brightness` | wb-mdm3 switch+slider pairs — ~10 |
| `rgb_light` | `power` + `brightness` + `color` | wb-mrgbw-d RGB strips — ~5 |
| `cover` | `cover` (open/close/set_position) | dooya curtains — ~10 |
| `heating_loop` | `climate` (mode + setpoint + room-temp) | radiator / floor loops — ~9 |
| `hvac` | full `climate` (mode/fan/vane/setpoint) | hvac_* — 3 |
| `sensor_room` | `sensor` with fields | wb-msw-v3 sensor sides — ~9 |

The 3 HVAC units run on ESP32 and **will** be modeled as **`ESP32ManagedDevice`** — a new
device class (alongside future ESP32 work in this project, see PARKED entry in §5 for the
firmware scaffold). **At v1 ship, `ESP32ManagedDevice` is behaviourally identical to
`WbPassthroughDevice`** (subscribes to value topics, publishes to `/on`, type-coerces via the
profile metadata) — the `hvac` profile drives both. The distinct class exists so the HVAC
units have a stable identity to grow into: future versions will expose **additional
ESP32-specific capabilities to the system, specifically to the UI** (e.g. provisioning state,
OTA progress, NVS-stored identity, sleep/wake telemetry, firmware version) that don't belong
on a generic WB-passthrough device. Decision locked 2026-06-08.

**`rooms.json` additions**:

```json
[
  {"id": "cabinet", "names": {"ru": "Кабинет", "en": "Study"},
   "devices": ["cabinet_spots"]}
]
```

`cabinet` gets a single entry for the slice device. The `global` room holds **aggregate
devices** (e.g. `all_lights`) — one per supported whole-house command; `cabinet_spots` does not
belong there. **Whole-house actions** ("выключи свет везде") are a SINGLE canonical call
against the matching aggregate device in `global`; Irene does NOT iterate rooms. The bridge
config ships each aggregate device; the controller-side wb-rules scene that fans the aggregate
out to the real lights is **user tech debt** (the bridge writes to the aggregate's `/on`
topic, wb-rules handles the per-light fan-out).

**Names: bilingual from day one** (`names: {ru, en}`), per the contract's all-locales rule.
Slice authoring uses ru = WB-UI verbatim, en = natural home-context renderings: `Споты` =
Spots, `Кабинет` = Study. Adjust before #16 (the AV-configs migration) if other en
preferences exist (Office / Spotlights / …).

**Voice command the slice proves**: «включи свет в кабинете» / «включи споты»
(en: "turn on the study lights" / "turn on the spots").

**Validation steps for #18 (e2e at the rack, user observes from the cabinet)**:

1. `POST /devices/cabinet_spots/canonical {capability:"power", action:"on"}` → 200 within
   500 ms with `state: {power: "on"}`.
2. Spots physically on (observable).
3. Bridge subscription receives the value-topic echo on
   `/devices/wb-mr6c_51/controls/K4` → `update_state` runs the persist + SSE callbacks but
   **NOT** the WB-publish callback (loop guard verified by checking the broker for no
   bridge-originated echo back to the same topic).
4. `POST … action:"off"` → reverse, same path.
5. Independent wb-rules write to `/devices/wb-mr6c_51/controls/K4/on` (or the user flipping
   the wall switch if wired) → bridge mirrors the new state without re-publishing.

**Pre-work A1 status: DONE.**

**Pre-work findings — A3 (2026-06-06)**

**WB convention verified on the live broker + against the Wirenboard MQTT-conventions spec
(github.com/wirenboard/conventions).** Errors are **per-control, not per-device**:

- **Topic**: `/devices/{dev}/controls/{ctrl}/meta/error` — retained when present, absent when
  healthy. The slice slave's `wb-mr6c_51/K4` has no `meta/error` topic at all → healthy.
- **Payload**: single-character codes that combine — `r` = read error / device reports an
  error, `w` = write error, `p` = read period miss. Compound payloads are possible (e.g.
  `rw`, `rwp`). Live samples observed: three controls currently flagged `r`
  (`wb-msw2_100/Buzzer`, `dooya_0x0101/Position`, `dooya_0x0102/Position`).
- **Clearing semantics** (per spec): after a successful read, the `r` flag is removed and
  THEN the new good value is published — value-topic and error-flag are kept consistent. The
  `w` flag is removed only after a successful write.
- A **device-level `/devices/{dev}/meta/error`** is also defined by the convention but isn't
  populated on this controller from per-control errors; the per-control topic is the
  authoritative signal we'll subscribe to. The driver subscribes to the device-level topic
  too as a cheap redundant signal.

**Bridge wiring** (refines the §P3.7 pillar-A bullet — same idea, sharper shape):

- The WB-passthrough driver **derives error topics from `state_topics` automatically** — for
  every `state_topic` `/devices/X/controls/Y` the driver subscribes to
  `/devices/X/controls/Y/meta/error`. **No explicit error field in the device config.**
- The driver also subscribes to `/devices/{dev}/meta/error` for each unique device id seen in
  `commands` or `state_topics`.
- Any non-empty payload on a capability's monitoring error topic marks that capability —
  and consequently the device — `device_unreachable` for canonical-endpoint purposes.

**Net config impact**: A1's `cabinet_spots.json` example (above) now drops the
`error_topic` field; the driver does the work.

**Pre-work A3 status: DONE.** All three pre-work items (A1 + A2 + A3) resolved; #13 can
start.

**Pre-work findings — A2 (2026-06-06)**

**WB HomeUI config located**: `/etc/wb-webui.conf` → `/mnt/data/etc/wb-webui.conf` (860 KB
JSON). Top-level keys: `dashboards` (room navigation), `widgets` (top-level widget pool keyed
by id), `defaultDashboardId`. Each dashboard has `id`, Russian `name`, and an array of
widget-id references. Each widget has `cells` — `cell.id = "<wb-device>/<control>"` (maps to
`/devices/<wb-device>/controls/<control>`), `cell.name` is the Russian label (sometimes blank
for the paired slider of a composite control), `cell.type` is the widget kind
(`switch`/`range`/`temperature`/`rgb`/…). Importable rooms (10): `entrance / hall / livingroom
/ kitchen / wc / bathroom / bedroom / children / wardrobe / cabinet`. **Skip** during import:
SVG dashboards (`isSvg: true`), the 3 cross-cutting dashboards (`safe`, `power` = global
scenarios, `av_teaching`), and `*_permit_schedule` cells (wb-rules schedule flags, not device
controls).

**Modeling decision — one logical bridge device per cell, NOT per WB slave.** Cross-room
analysis of 40 unique WB slaves: **15 (38%) serve multiple rooms** — the worst cases serve 5
(`wb-mr6c_51/52`, `wb-mr6cu_31`, `setpoints_floor`, `wb-gpio`), plus `setpoints_radiator` (4),
the dimmers `wb-mdm3_83/87` (3 each), `wb-mr6c_47/58` (3), `setpoints_curtain` (3), and the
RGB dimmers `wb-mrgbw-d-fw3_10/238` (2). This is the install pattern, not an outlier — one
relay module is fanned out to wherever channels are needed. With the **single-room model**
(`room: str`, settled 2026-06-06 — see A1), a per-slave config can't answer "which one room
am I in?" for these slaves. Even single-room slaves often host several distinct logical
things (a dimmer slave = K1 relay-light + Channel 1 dimmer-light; an RGB slave = two paired
Channel/Brightness composite lights). Expected bulk count: **~50–80 logical devices** across
10 rooms, mechanically generated by #21 from the cells (placed at
`backend/config/devices/wb-devices/<room>/<device_id>.json` per the directory convention).

**Composite-control shapes the WB-passthrough driver + capability adapters must handle.**

- **Light: switch + paired brightness slider** — many lights are TWO cells rendered together:
  `<slave>/K<N>` (switch, has the human label) + `<slave>/Channel <N>` (range, no label,
  paired beneath). Examples: children's Споты = `wb-mdm3_87/K3` + `Channel 3`; cabinet
  Подсветка = `wb-mrgbw-d-fw3_238/Channel 2 (R)` + `Channel 2 (R) Brightness`. **Combine into
  one logical device** with `power` (on/off) + `brightness` (range) capabilities — no
  cross-device composition needed; just two-capability mapping in a single config.

- **Heating loop: actuator switch + setpoint slider + room-temp sensor** — cabinet alone has
  THREE such loops (radiator, warm-floor, windowsill heater), each the same shape: e.g.
  radiator = `wb-gpio/EXT3_R3A5` (actuator switch, no label) +
  `setpoints_radiator/cabinet_temp` (setpoint range) + `wb-msw-v3_219/Temperature` (room
  temperature sensor) + `setpoints_radiator/cabinet_permit_schedule` (wb-rules flag —
  **skip**). **Combine into one logical device per loop** with a `climate` capability:
  `set_mode(on/off)` → write the actuator switch; `set_setpoint(t)` → write the setpoint
  range; reads `room_temperature` from the sensor + `current_setpoint` from the setpoint
  cell. Multi-cell write — handled by the WB-passthrough driver's per-command topics (one
  config command per cell, no separate adapter; see #19's `state_topics` typed schema). Three
  logical devices in cabinet Обогрев (radiator, floor1, floor2), not twelve.

- **RGB strip: one cell encoded `"R;G;B"`** — e.g. `wb-mrgbw-d-fw3_*/RGB Strip`. One logical
  device with `power` + `brightness` + `color`; `color.set(r,g,b)` resolves via the
  `rgb_light` profile to a single driver command with `payload_template: "{r};{g};{b}"`;
  incoming echoes parse back into a typed `{r,g,b}` dict via the same template. All
  data-driven, no adapter. (#19 scope.)

- **Cover: single position slider** — `dooya_dm35eq_x_*/Position` (range 0–100). One logical
  device with `cover` capability: `open = set 100`, `close = set 0`, `set_position(pct)`.
  Stop semantics TBD during slice 2 (no obvious WB control for it — re-writing the same
  position is the likely answer).

- **HVAC: many cells, one device** — `hvac_children/*` has 7 cells
  (power / mode / fan / vane / widevane / temperature / room_temperature). One logical
  device, full `climate` capability — the most complex composite; do during bulk after the
  simpler shapes settle.

**Slice device locked**: `wb-mr6c_51/K4 "Споты"` → logical id `cabinet_spots`, room
`cabinet`, capability `power` (on/off only). The user works in the cabinet, so physical
observation closes the verification loop on slice step #18.

**Sequencing.** P3.7 runs in **parallel with the §5.1 rack pass** (different surfaces, no
contention). Settles **before P4** (final acceptance), which then sweeps the larger surface.

**Hexagonal LAW preserved** (`hexagonal-law-for-all-changes`): WB-passthrough driver in
`infrastructure/devices/wb_passthrough/`; capability mappings in `config/capabilities/`; capability
adapters next to the existing reconciler. No domain imports of infrastructure.

**Deferred to v2** (the only thing the contract leaves open): additional whole-house aggregate
devices beyond the v1 set (#22 ships the aggregates the v1 voice command set needs — e.g.
`all_lights`; more group/scene aggregates like `all_blinds`, per-floor groups, named scenes are
added as the voice command set grows, each as another normal device entry in `global` — no new
endpoint).

- **Voice control (Yandex Alisa) — out of scope here.** SprutHub was a stopgap and is **dropped** (2026-05-20). The plan is to rely on **Wirenboard's future native Alisa bridge**; because this system already exposes every foreign device as a WB virtual device, those devices become voice-controllable for free once that bridge ships. (The two former SprutHub backlog items are retired.)

- [ ] **VWB-12** `[P2]` `[later]` — `wb-msw-v3_*` sensor side — decide unified config (IR + `sensor`) vs split entry; implement. **DEFERRED POST-RELEASE 2026-07-04 (user decision, both sides — the voice repo defers sensor state-queries equally).** Analysis done in chat (see journal 2026-07-04): recommendation = **split entry** — per-room sensor devices (`sensor_room` profile, partial mirrors per the sauna precedent), IR side stays transport plumbing referenced from AV configs (module-is-wiring precedent: `wb-mr6c_47` hosts 6 lights and is no device either); a module-level IR entity can be added *alongside* later if DRV-3 ever needs one, without touching the sensor devices. When picked up: classic paste session per room + **verify control names per module firmware** (the recorded firmware-doc cross-reference warning; MSW inventory today: `wb-msw-v3_207` living room, `218`, `220` children — all currently IR-only references).

- [ ] **VWB-13** `[P1]` `[house]` — Catalog completeness sweep + bulk end-to-end verification across rooms (including each `global` aggregate device's canonical call landing on the broker, even if its wb-rules backing is still owed).

- [ ] **VWB-16** `[P2]` `[house]` — **Consumer contract test — crafted canonical `DeviceCommand` → native/echo** (cross-project; the consumer half of the bidirectional contract, pairs with `wb-mqtt-voice` TEST-18's producer half). Drive the bridge from the shared **`{utterance → expected canonical command}` crossover fixtures** (using the canonical-command half only — the utterance is Irene's concern): feed each crafted canonical command and assert it dispatches the right native action / value-topic echo, resolved against the **same golden catalog** the voice side tests against (so device-ids/capabilities can't drift apart). Depends on VWB-15's committed artifact.
  - **Sequence-form caveat — RESOLVED 2026-07-04 (VWB-17 DONE):** the canonical endpoint now routes `sequence`-form actions (shared `CapabilityAction.expand()` — per-step param translation, inter-step `delay_after_ms`, mid-sequence failure naming the step). Crossover fixtures may cover sequence-form actions freely.
  - Spec: `wb-mqtt-voice/docs/design/mqtt_integration.md` §14.

- [ ] **VWB-19** `[P2]` `[later]` — **Route `select`-form capabilities through the canonical endpoint.** Surfaced during SCN-7 (filed 2026-07-04): the canonical dispatcher walks `cap.actions` only, so a capability whose invocation lives in **`select`** (parametric `command`+`param_map` like LG's `set_input_source`, or `by_value` like the IR amp's `input_cd`/`input_aux2`) is **not reachable canonically** — voice cannot switch inputs («переключи на CD»), and the UI's input/app dropdown *selection* stays on the native `/action` path (the enumeration half already moved to `GET /devices/{id}/options/*` in SCN-7). Design sketch: canonical `input.set {value}` resolves via `select` (parametric → rename+dispatch; `by_value` → value-table lookup, honoring canonical/wire translation); catalog then advertises `set` on select-capabilities (today it advertises none of them — that's why this never bit the crossover fixtures). Not house-gating: the v1 voice command set has no input switching, and the UI path works natively. Natural trigger: the first voice input-switching feature, or the `/action` demotion decision at the acceptance gate. **Related symptom (voice review G-minor, 2026-07-04):** TVs' `input` capability projects into the catalog as an **empty husk** (actions None, fields None) because only `cap.actions` is projected — VWB-20 decides whether to suppress empty capabilities until this task makes them real.

- [ ] **VWB-23** `[P1]` — **Room-scoped group addressing — implementation of `canonical_first.md` §10** (design = VWB-22, DECIDED 2026-07-05). The third canonical address form for group utterances («включи свет», «закрой шторы»): **`POST /rooms/{room_id}/canonical`** `{group, action, params?, scope: auto|all|one, wait?}`. Scope policy: `auto` = room's `group_defaults[group]` if configured else fan-out; `all` = forced fan-out (the plural/«весь» signal survives); `one` = default required (`409 no_default_device`). **Membership = the `group` overlay**: a capability's group defaults to its **domain name**; the three illumination profiles (`light_switch`/`dimmable_light`/`rgb_light`) override their `power` capability with `group: "light"` (the fleet's 36 lights declare domain `power` — domain-as-membership would sweep sockets/oven into «свет»; re-profiling `power→light` REJECTED, reconciler/layout/WB-service all key on `power`). Kitchen hood's `light` domain matches implicitly. **Prerequisite (user-confirmed 2026-07-05): split a `power_switch` profile out of `light_switch`** (identical shape, no group override → group `power`) and re-point the two non-lights wearing it today — `global/oven_power` + `global/all_plugs`; `global/all_lights` stays (genuine light master — «свет» in `global` resolving to it, wb-rule fanning out physically, is intended). Per-member execution re-enters ordinary per-device canonical dispatch against the member's own capability (`no_op` short-circuit intact); aggregate response `{scope_applied, results: [{device_id, status: executed|no_op|skipped|failed}]}`; speakable `404 no_group_members`. **Fan-out allow-list: `light` + `cover` only** — consequential groups (`power`…) refuse fan-out with a speakable 409. Config: optional **`group_defaults`** map in `rooms.json` (validated: device in room + member of group). Contract impact (all additive): new endpoint + response schemas in `openapi.json`, capability `group` + room `group_defaults` in the catalog DTOs, UI types regen + config section (`config-ui-stays-functional`), golden re-dump. Pre-pin preferred: if this lands before voice TEST-17 pins, v1 carries it.

### UI — config-ui

- [ ] **UI-8** `[P2]` `[later]` — **UI `vite` 5 → 6 migration (deferred — deliberate major upgrade).** Filed 2026-06-27. Closes the remaining build-toolchain Dependabot alerts that couldn't be cleared by the lockfile-only `npm audit fix` (see journal 2026-06-27): **vite #113/#154/#155** (path traversal / dev-server) and **esbuild #81** (esbuild 0.25 rides vite 6). Does **NOT** cover the other 2 residual alerts — `minimatch` #101 (pinned by `@typescript-eslint@6`) and `js-yaml` #152 (pinned by `jest@29`); those are separate toolchain-major tasks (eslint 6→9 / jest upgrade), file them if/when pursued.
  - **Scope.** Bump `vite ^5.4.21 → ^6.x` + `@vitejs/plugin-react ^4.0.3 → ^4.3.x` (vite-6-compatible) in `ui/package.json`; refresh the lockfile. No test-runner impact — `ui/` uses **jest**, not vitest.
  - **Low-risk by construction (already vite-6-ready):** config is ESM (`vite.config.ts` uses `import.meta.url`), `build.target` is explicitly `'esnext'`, Docker builder is **Node 20** + `engines.node >=18.0.0` — so vite 6's CJS-API removal, raised Node floor, and changed default target don't bite.
  - **Risk surface = the dev-server SSE proxy.** `server.proxy['/events'].configure()` hooks `proxy.on('proxyReq'|'proxyRes'|'error', …)` to force `text/event-stream` + disable buffering. Re-verify these `http-proxy` hooks against vite 6's proxy API. This is **dev-server-only** (`npm run dev`); the production nginx path is unaffected.
  - **Definition of done.** `cd ui && npm run check && npm run build` clean (`config-ui-stays-functional`); a `npm run dev` SSE smoke test (the `/events` proxy still streams against a running backend) since #113 + the SSE proxy both live on the dev server; Dependabot drops to the 2 eslint/jest residuals. Then journal it (`read-at-start-record-at-completion`).


### OPS — Docker / CI-CD / deploy / ops

- [ ] **OPS-11** `[P2]` `[later]` — **Multi-arch images: add `linux/arm64` (aarch64, next-gen Wirenboard) alongside `linux/arm/v7`.** Filed 2026-07-02 off a chat analysis (sister-repo prompt: `wb-mqtt-voice` builds armv7 + aarch64 + standalone). **Unlike the voice repo** (per-target Dockerfiles + arch-suffixed image names, forced by per-platform ML profiles), the bridge's images are identical on both arches → use buildx **multi-platform manifests**: `platforms: linux/arm/v7,linux/arm64` in both image jobs of `.github/workflows/build-arm.yml` yields ONE manifest list per existing tag — WB7 pulls armv7, WB8 pulls arm64 from the same `ghcr.io/...:latest`; `ops/` (compose / `update.sh` / INSTALL.md flow) unchanged. **Work items:** (1) workflow: extend `platforms`, **drop the `ARCH=arm32v7` build-arg** — the Dockerfile's `${ARCH:+$ARCH/}python` prefix predates platform-aware buildx and would force the arm32 base into the arm64 leg (Dockerfile itself needs no change; `ARG ARCH=` defaults empty); (2) `ui/Dockerfile`: stage 1 → `FROM --platform=$BUILDPLATFORM node:20 AS builder` — the `dist/` bundle is arch-independent, so the ~14-min QEMU node build runs natively on the amd64 runner once and only the small nginx stage builds per-arch (bonus: the *existing* armv7 UI build should drop to ~2-3 min); (3) docs: a sentence each in `ops/INSTALL.md` + the READMEs noting the images are multi-arch. **Notes:** piwheels extra-index is armv7-only but harmless on arm64 (PyPI aarch64 cp311 wheel coverage is good — likely a faster leg than armv7); that `/etc/pip/pip.conf` is probably vestigial anyway since the image installs via `uv`, which doesn't read pip config — verify/drop while in there. WB8's Cortex-A5x could in principle run the armv7 image via AArch32 compat, but native arm64 is the clean path at ~6 lines of diff. **Verification:** QEMU build smoke in CI; real run gated on actual WB8 hardware (hence `[later]`).

- [ ] **OPS-7** `[P2]` `[later]` — **Dependency refresh — clear the Dependabot noise (88 alerts as of 2026-05-31).** Lockfiles haven't been bumped since the 2025-07 pause; GitHub now reports 1 critical / 28 high / 41 medium / 18 low. Audit (2026-05-31, before the UI image build) showed the headline number is misleading for this deployment: most are transitive duplicates of a few root packages, and almost none are exploitable on a LAN-only Wirenboard with a trusted UI↔backend channel. **Triage breakdown:**
  - **UI lockfile (`ui/package-lock.json`) — bulk of alerts.** Dominated by `axios` (~14 across H/M/L: prototype-pollution gadgets, NO_PROXY bypasses, header injection, DoS) — all need attacker-controlled config merging or hostile proxy config, neither applies (axios calls go to a fixed `apiBaseUrl`). The build-chain cluster (`vite`/`rollup`/`esbuild`/`postcss`/`picomatch`/`yaml`/`js-yaml`/`glob`/`minimatch`/`flatted`/`lodash`/`fast-uri`/`follow-redirects`/`form-data`/`@remix-run/router`/`react-router`) is **build-time only**, never in the deployed container. The 1 critical (`form-data` unsafe-random boundary, CVE-2025-7783) only matters across an attacker boundary — not the case here.
  - **Backend lockfile (`backend/uv.lock`).** `aiohttp` (~13) covers inbound HTTP parsing DoS / header injection — but we use aiohttp as a **CLIENT** (openhomedevice/pyatv/pymotivaxmc2 outbound to LAN devices), not a server, so the inbound surface isn't exposed. `urllib3` (5) is redirect/decompression-bomb stuff — we don't follow cross-origin redirects to untrusted hosts. `starlette` FileResponse Range DoS — we don't serve FileResponse. `black`/`pytest`/`Pygments`/`playwright` are dev tooling. `cryptography`/`pyopenssl` are TLS-tail issues; we're an MQTT client on a private LAN, not a public TLS server.
  - **Net real-world risk for the home deployment: low.** Threat model is "someone on the home LAN behaves maliciously" — almost nobody. Noise, not danger.

  **Plan (one focused PR, no rush):**
  1. **UI side:** `cd ui && npm update axios react-router @remix-run/router` first (kills ~half the high count); then `npm audit fix` for the build-chain tail (verify no major-version breakage); then `npm run typecheck:all && npm run validate:generated-code` and a local `npm run dev` smoke against the rack backend.
  2. **Backend side:** `cd backend && uv lock --upgrade-package aiohttp urllib3 starlette cryptography pyopenssl requests` (the high-value targets); regenerate uv.lock; `pytest -x` for the existing 401 tests; verify openhomedevice/pyatv/pymotivaxmc2 still import cleanly (those are the actual aiohttp consumers).
  3. **Defer:** the build-chain UI deps (vite/rollup/esbuild) — bump only if a real CVE in our actual runtime path appears. Mass-bumping the toolchain risks Vite-major-version churn without security benefit on a LAN UI.
  4. **Hexagonal LAW:** no domain touch, no config touch — pure dep bumps.

  **Gate:** do this on a quiet day, NOT before a hardware verification session (dep bumps add a confounder to whatever you're actually trying to debug at the rack). Re-pull the Dependabot count after the PR to confirm the drop.

- [ ] **OPS-8** `[P1]` `[later]` — **Lifecycle-robustness leftovers (deferred from the 2026-05-22 hardware session).** The
   lifecycle cluster (Bug 2 non-fatal load · keep failed-setup devices registered · hardware-
   transparent shutdown + assumed-state persistence) shipped; these lower-value tails were
   deferred here:
   - **Defensive startup-failure cleanup.** The lifespan startup isn't wrapped, so a *rare/
     unexpected* error during startup (not the now-handled device/scenario cases) leaks partial
     resources (sockets/ports → a hung process). Wrap startup → best-effort release on failure +
     re-raise. (The common zombie cause — `load_scenarios` `SystemExit` — is already fixed.)
   - **Teardown noise → SUPERSEDED 2026-05-27 evening by §5.1 #8** (full root-cause diagnosis + 2-part fix path). Kept here for historical context; §5.1 #8 is the actionable item. Originally
     classified cosmetic (`Task was destroyed but it is pending` from pyatv `CompanionAPI.
     disconnect` not awaited to completion; `_GatheringFuture exception was never retrieved`
     from the 2 s cancel-gather). **Field-observed during the LG TV HW pass on 2026-05-27**
     while stopping the backend with Ctrl-C: user had to press Ctrl-C **three times**; the
     process hung for **~50 seconds** between the first cancel signal and the eventual force
     exit. Log analysis (`backend/logs/service.log`, 14:13:57 → 14:14:47) shows the **entire
     bootstrap lifespan shutdown phase (`bootstrap.py:285-357`, the code after `yield`) never
     executed** — none of its INFO lines (`"System shutting down..."`, `"Shutting down devices..."`,
     `"Disconnecting MQTT client..."`, `"System shutdown complete"`, etc.) appear. What logged
     instead: uvicorn's signal handler cancelling background tasks directly (SSE generators,
     pymotivaxmc2 dispatcher, MQTT client task), then 50 s silence, then **2 `Unclosed client
     session` aiohttp errors from GC** — almost certainly the 2 pyatv (Apple TV) instances
     whose `CompanionAPI.disconnect` doesn't drain on cancel. So the cluster of issues is:
     (a) lifespan shutdown phase is being **bypassed**, not just made noisy — uvicorn's
     SIGINT handler cancels the lifespan generator without resuming the after-`yield` block;
     (b) pyatv teardown keeps the loop alive for ~50 s before GC; (c) the orchestrated cleanup
     (state-store close, WB virtual-device offline marking, device.shutdown() per device,
     including the LG TV's `_teardown_subscriptions` added in `5a09fd1`) **is never reached**.
     **NOT caused by today's commits** — `_teardown_subscriptions` only runs from inside
     `LgTv.shutdown()` which only runs inside `shutdown_devices()` which is part of the
     bypassed lifespan phase. State integrity preserved (writes are transactional through
     the operating life of the process, not buffered until shutdown). **Workaround at the
     rack today:** `kill -TERM <pid>` (often handled differently by uvicorn) or accept the
     Ctrl-C-x3 dance — no data loss. **When fixing:** (1) register an explicit SIGINT/SIGTERM
     handler in the entry point that drives the lifespan shutdown explicitly before uvicorn's
     cancel cascade; (2) wrap `atv.disconnect()` in `asyncio.wait_for(..., timeout=2.0)` with
     per-device timeout logging; (3) investigate whether the FastAPI/uvicorn version we run
     has the lifespan-cancel-bypass regression that's been reported upstream in uvicorn 0.27+.
     Also tune the 2 s background-task cancellation if needed.
   - **Device auto-reconnect/retry** for devices that failed setup (kept registered as
     disconnected) — so an off-at-boot eMotiva becomes controllable once it powers on, without a
     restart. (Follow-up to keep-registered.)
   - **Apple TV driver hygiene:** dead `device_update` / `device_error` methods (not part of any
     registered pyatv listener); the app-list fetch logs at ERROR + writes `state.error` when the
     device is merely asleep — defer the fetch until the device is awake (ties to §15 tvOS
     "Who's watching?").
   - **WB virtual device offline on shutdown.** Only *scenario* WB devices are torn down at
     bootstrap shutdown; regular-device WB virtual devices keep `meta/available=1` on the broker
     after the bridge stops, so their cards look live in the WB UI. Wire regular-device WB cleanup
     (mark `available=0`) into bootstrap shutdown. (Deferred companion to the empty-retained-value
     fix, 2026-05-22.)


### CORE — Backend core / architecture

- [ ] **CORE-1** `[P2]` `[later]` `HW-GATED` — **System-router adapter cleanup — Item A only (Item B DONE 2026-05-26).** Item A: `POST /reload`'s `reload_system_task` constructs + drives a concrete `MQTTClient` inline; extract an application-layer reload service (e.g. `app/reload_service.py`) so the router stays a thin adapter. **Gated on hardware** — touches the live MQTT-reconnect path; can't be safely HW-verified without you at the rack. Item B (response DTO for `/config/system`) done in `73ee8d5` — new presentation `SystemConfigResponse` + nested DTOs; wire shape field-identical; `presentation/api/schemas.py` no longer imports the infra `SystemConfig`.


### DOC — Docs / ledger / process

**The ledger & documentation reconciliation series (DOC-4…DOC-10).** Filed 2026-06-30 from two
chat-requested analyses: (1) a comparison of this plan's former positional `P0…P4 / #n` numbering
against the sister repo's workstream-serial ledger (`../wb-mqtt-voice/docs/RELEASE_PLAN.md` + frozen
`RELEASE_PLAN_DONE.md`), and (2) a read of the four scenario/Layer-3 design docs that doubled as
ledgers. Both surfaced the same thing: design/planning docs accreted a *done* ledger half that
diluted their reference half. The series executes the **handover §0 promises** ("the redesign specs
fully retire to history… a project-wide doc reconciliation formalizes the handover"). **The series is
complete:** DOC-5 (design gate) · DOC-6 (two-file split) · DOC-8 (archive the survey) · DOC-9 (re-ID) ·
DOC-10 (retire the scenario/Layer-3 ledgers) · DOC-4 (the `scripts/check_scope.py` scope-drift guard) —
all done; DOC-7 folded into DOC-9.

- ~~**DOC-7**~~ — *adopt additive conventions; folded into DOC-9 (the legend/tags/priority-split land in the re-ID pass).*

---

## Acceptance gate (house-works completion checklist — ex-P4 #1–#5)

The scenario reconciler + monorepo + Layer 3 runtime rendering are being done **gradually**, so a
deliberate final pass is required once all phases are in. Gradual migration always leaves stale
code/models/config behind — budget real time for this; do not skip it.

1. **All devices migrated.** Capability maps exist for **every** driver class and device instance,
   not just the `movie_appletv` set + IR fleet built first — check `streamer` (Auralic),
   `reel_to_reel` (Revox), `kitchen_hood` (appliance), `children_room_tv`/`appletv_children`, etc.
   *Satisfied for the current fleet as of 2026-07-04 (DRV-9 mapped the last gap, `kitchen_hood`;
   verified: 5 AV classes + 5 IR device maps + all 57 WB-passthroughs carry profiles). Re-confirm
   at the gate pass in case the fleet grew.*
2. **All scenarios migrated.** Every scenario is thin (`source/display/audio`) and reconciler-driven —
   the legacy `startup_sequence`/`shutdown_sequence` format was **removed** (CORE-2, 2026-07-04);
   a scenario without a thin `source` is now rejected at load.
3. **UI works for everything.** Every device page **and** every scenario page renders and functions
   under the runtime model (Layer 3); `manual_steps` are displayed; nothing depends on the retired
   build-time codegen.
4. **Thorough code review + dead-code sweep.** *→ tracked as **CORE-2** — the dead-code-sweep half
   is **DONE 2026-07-04** (see `action_plan_DONE.md`); the "thorough code review" half remains part
   of this gate pass. The list below is kept as the historical record — every removable entry on it
   is now removed (the `group` fallback survives narrowed: the config field is extinct; the
   capability-less WB path stays, live for `kitchen_hood` until its capability map exists).*
   Remove what the gradual migration superseded —
   likely candidates: the legacy imperative path (`Scenario.execute_startup_sequence` /
   `execute_shutdown_sequence`, the old shared-device `switch_scenario` branch, the string-condition
   evaluator, the dead `_validate_parameters`, vestigial `DeviceState.output`); the UI's duplicate
   scenario inheritance (`ScenarioVirtualDeviceHandler`/`Resolver`) + build-time generators once
   Layer 3 is authoritative; the `WB_SCENARIO_RECONCILER` kill-switch once the reconciler is the only
   path; any unused escape-hatch model fields; and superseded docs. Confirm the contract is clean
   (`openapi.json` has no orphaned models/fields).
5. **Hardware re-verification** of the whole system end-to-end after the cleanup (cleanups regress).

---

## Open questions

*Use this section to capture decisions as we discuss. Each answered question will inform revisions above.*

- [ ] **Are we keeping the project on ARMv7 / Wirenboard exclusively, or do we want a dev path on amd64 too?** Affects #2 (test target arch), #7 (multi-arch GHCR tags), #11.
- [ ] **Is the Wirenboard the only deployment target, or do we want to deploy to a separate Linux box and talk to the WB controller over MQTT?** Affects the urgency of items #3, #4 (hardcoded IPs).
- [ ] **Is the long-term direction one repo or two?** If "one," do #3 anyway (OpenAPI contract) and then merge — much cheaper post-contract. If "two," do #3 for sure, and the contract is the *point*.
- [ ] **Are there device drivers planned that aren't shipped yet (Roborock, Apple TV app launching, IR learning UI from the old TODO)?** Affects whether the device list (`docs/architecture/devices-and-scenarios.md`) is the final list or a checkpoint. *(Miele dropped 2026-05-20 — repeated integration attempts failed, `asyncmiele` dependency removed. SprutHub dropped 2026-05-20 — see §5.1.)*
- [ ] **Is `device_category` going to drive real behavior soon?** If yes — what differs between `device` and `appliance`? If not — should we even ship the enum now, or wait until we know what it gates?
- [ ] **Do we also want to move to runtime-driven UI rendering (Codegen Alternatives — Option 2)?** Eliminates `.gen.tsx` codegen entirely; UI fetches a per-device manifest from the backend and renders dynamically. Strong industry-practice alignment (Home Assistant / ioBroker pattern). ~2–3 day refactor. Default position: defer until after #3.5 ships and we feel actual pain that justifies it.
- [ ] **How should button/action placement be made explicit/contract-based instead of relying on config command order?** See item #10. The current implicit convention works (verified unchanged by the P1 work) but the user explicitly dislikes layout depending on undocumented config ordering. Decide between: explicit per-action `slot`/`order` fields, a backend-owned layout manifest (couples naturally with Option 2 above), or command annotations. This question and the Option-2 question are related — a runtime layout manifest could subsume both.
- [ ] _Add others as we discuss._

---

## 6. Revision Log

The dated history lives in **[`docs/action_plan_journal.md`](action_plan_journal.md)** — extracted
2026-06-06 to keep this plan focused on forward work. References elsewhere in this plan
("see §6 (2026-XX-XX)") still resolve: they point at that file's dated entries.

**Recent entries** (newest first; full content + earlier entries in the journal):

- 2026-06-09 — **Layer-3 frozen oracle retired** — last open item from the Step 4 cutover. 14 JSONs moved to `docs/archive/layer3_oracle/`; `test_layout_manifest.py` deleted (it was producing a hard collection error on a stale path) and `test_engine_reproduces_oracle` removed from `test_layout_engine.py` (its 12 parametrize entries had been silently skipping via the same stale-path bug). The eMotiva multi-zone property test survives (never oracle-based). Validation surface is render-level diff via `/devices/{id}/layout` + `RuntimeDevicePage`, per the 2026-05-23 decision. Suite 495 pass / 0 skipped (was 12 false skips). `ui_backend_contract.md` updated.
- 2026-06-09 — **§P3.7 #26 DONE** — value-label translation layer end-to-end: `ValueLabel(wire/canonical/labels)` on `CapabilityField` + `StateTopicSpec` with back-compat for bare `["a","b"]`; driver `_translate_outbound`/`_translate_inbound` mirroring the `invert` shape (canonical ↔ wire); catalog emits `CatalogValueLabel` triplet with version-hash bumps on label-table changes; HVAC profile + 3 Mitsubishi configs gained firmware-vocabulary value tables (mode/fan/vane/widevane wire from `mitsubishi2wb` `html_pages.h`, trilingual labels); drift-guard test pins profile↔config wire/canonical agreement; native React `HvacPanel.tsx` with the firmware's Unicode glyphs reads catalog + posts canonical. **5 commits** (`bb8cca4`→`c6c8f67`→`1c55007`→`ebc5a07`→`05371c2`). Suite **495 pass** in subset; the pre-existing `test_layout_manifest.py` collection error (stale oracle path) is unrelated and present on the pre-#26 baseline. Heating_loop.mode left as-is (the "optionally" qualifier — type=bool/invert=true already works). HW verification deferred to next rack session.
- 2026-06-09 — **Proposal added: §P3.7 #26 value-label translation layer** — design discussion logged in the task table. Three-layer enum mapping (wire / canonical / labels) on existing `CapabilityField` + `StateTopicSpec`. Same shape as the `invert` flag — symmetric outbound/inbound translation in the driver, no derived class needed. Resolves the enum-vs-wire mismatch we'd shelved across heating_loop / hvac; enables a native React HvacPanel (replaces the deferred "embed firmware HTML" idea). ~2 dev days. **Not started — user thinking overnight, picking up tomorrow.**
- 2026-06-08 — **`invert` extended to bool type** — heating switch inversions (living/children/bedroom on wb-gpio/EXT3_R3A2-4) now use the same flag pattern as covers: configs in natural sense (`mode_on: "1"`), bool state_topic with `invert: true`, driver toggles at the wire. 8 new tests + no_op compare made type-aware (parses target to typed before compare). State.mirrored carries typed `True`/`False` natural-sense. **502 passing** (was 495)
- 2026-06-08 — **`invert` flag on StateTopicSpec** — fixes cabinet rollers' inverted position semantics end-to-end (cover.set_position(25) now correctly means "25% open" regardless of the dooya motor family); driver applies `100-value` symmetrically on outbound publish + inbound mirror; cabinet roller configs reverted to natural-sense open=100/close=0 plus `invert: true` on the position state_topic; 8 new driver tests cover static + param paths + roundtrip + uninverted regression; **495 passing** (was 486)
- 2026-06-08 — **Room-architecture refactor** — eliminated rooms.json `devices` duplication (single source of truth: `device.config.room` → `DevicePort.get_room()` → `RoomManager` derives at load); backfilled `room` on 13 AV configs; added `get_room()` to port + BaseDevice; activated long-dormant scenario room-membership invariant (`ScenarioManager._validate_room_membership` hard-fails on mismatch); all 9 existing scenarios pass; drift-guard replaced with forward-direction check; 486 passing
- 2026-06-08 — §P3.7 #23 DONE — **57 WB-passthrough device configs across all 10 physical rooms** authored interactively from WB-UI widget JSONs; 4 profile cleanups (cover.stop, hvac rewrite, heating_loop.mode, sauna sensor_room partial use); catalog gains state_topics-driven field filtering; drift-guard test catches stale rooms.json; live authoring log captures every decision + automation opportunities for any future packaged version; HVACs flagged for ESP32ManagedDevice migration; multi-sensor backlog deferred; **485 passing** (was 482)
- 2026-06-08 — §P3.7 #21 DONE — `rooms.json` full WB-UI sweep (6 new rooms inc. `shower` for WB `wc`) + `global` for aggregate devices (#22); trilingual `ru/en/de` across all 11 rooms; legacy `living_room`/`children_room` ids preserved per user direction; WB-dashboard mapping in each entry's description (importer deferred to #23); 8 new tests; **482 passing** (was 474)
- 2026-06-08 — §P3.7 #19 DONE — 6 capability profiles authored (motion dropped from sensor_room); typed `state_topics` + `payload_template` + capability `fields[]` schema landed; driver gains type-coerce/compose/inverse-parse helpers (~70 LOC); catalog emits typed field metadata; FieldInfo class-body shadow footgun fixed; **474 tests passing** (was 453); slice configs unchanged
- 2026-06-08 — §P3.7 #20 collapse — composition folds into the WB-passthrough driver via typed `state_topics` + `payload_template` (no separate adapter layer); HVAC class locked as `ESP32ManagedDevice` (v1: behaviourally WB-passthrough; grows UI-facing ESP32 surfaces later); #19 widens to ~1.5 day; bulk total ~7-9.5 days
- 2026-06-07 — §P3.7 plan reconcile — aggregate-device model for `global` (two stale lines fixed; new bulk task #22 for v1 aggregates like `all_lights`; renumber #22-#24→#23-#25; controller-side wb-rules scenes are user tech debt; no code touched)
- 2026-06-06 — §P3.7 #18 cold-start fix — retained-message opt-in per topic (broker's retained "current value" now seeds `state.mirrored` on connect; first `power_off` after restart works; 453 tests pass)
- 2026-06-06 — §P3.7 #18 follow-up #2 — AV-driver instantiation regression + fix + entry-point-signature test (drop `wb_service=` from `device_class(...)` call; 448 tests pass)
- 2026-06-06 — §P3.7 #18 follow-up — idempotency no_op short-circuit (repeat actions return 200, not 503; 447 tests pass)
- 2026-06-06 — §P3.7 slice #18 — DONE; voice integration slice physically validated (5 ms publish→echo round-trip, 200 OK; slice gate crossed)
- 2026-06-06 — §P3.7 #18 first rack run — two-prong subscription wiring bug + fix (bootstrap ordering + `_run_mqtt_client` union-of-handlers; 442 tests pass)
- 2026-06-06 — §P3.7 slice #17 — `GET /system/catalog` DONE (deterministic version hash, retained MQTT nudge on /reload, 9 tests; slice feature-complete on the bridge side)
- 2026-06-06 — §P3.7 slice #15 — canonical action endpoint DONE (6-code error enum, 500 ms echo timeout, 10 tests; Irene unblocked for AV)
- 2026-06-06 — §P3.7 — capability-profile mechanism + `light_switch` profile (cabinet_spots migrated; AV path unchanged; 423 tests pass)
- 2026-06-06 — §P3.7 slice #14 — cabinet_spots wired (device config + capability map + rooms.json entry; 421 tests pass)
- 2026-06-06 — §P3.7 — single-room model + `wb-devices/<room>/` directory convention (contract correction; recursive config scan)
- 2026-06-06 — §P3.7 slice #13 — generic WB-passthrough driver DONE (417 tests pass, loop guard verified)
- 2026-06-06 — §P3.7 slice #16 — device_name → names bilingual migration DONE (401 tests pass, UI clean)
- 2026-06-06 — A3 — wb-mqtt-serial error topic convention nailed (per-control, `r`/`w`/`p`); all pre-work DONE
- 2026-06-06 — A1 — slice artifacts nailed for cabinet_spots (room: cabinet)
- 2026-06-06 — A2 — WB HomeUI config located + composite-control patterns documented
- 2026-06-06 — voice integration contract agreed + new §P3.7 HIGH-PRIORITY phase
- 2026-05-30 — eMotiva rack pass + 2 sibling-library handoffs + LG TV silent-WS-death fix + HDMI ARC scenario
- 2026-05-30 — state-management audit → 2 stale-scenario-state bugs fixed + chokepoint static guard
- 2026-05-29 — Auralic streamer research → robustness hardening pass (OpenHome confirmed)
- 2026-05-29 — IR ROM tooling cleanup (unified `ir.py`, jitter-tolerant verify, `temp/` gone)
- 2026-05-29 — mf_amplifier root-caused (ir_restore.py edit-lock bug fixed live + tool hardened)
- 2026-05-29 — §5.1 #7 eMotiva input → logical-source clean cut + HW-verified
- 2026-05-28 — IR ROM backup/restore HW verification + 207 large-code diagnosis
- 2026-05-28 — §5.1 #7 AppleTVDevice DONE on both units (tvOS 26.5 Companion fix + WB IR for volume)
- 2026-05-28 — pointer-flood fix + LG input fix + CI bump
- 2026-05-28 — §5.1 #8 clean shutdown DONE, HW-verified
- 2026-05-27 — multi (LG TV row DONE, §5.1 #8 shutdown-hang diagnosis, chokepoint Invariants A+B, CI Python pin, asyncwebostv 0.3.0)
- 2026-05-26 — multi (P3 #7+#8 GHCR/compose retiring docker_manager, §5.1 system-router cleanup, §5.1 #1 manual notes)
- 2026-05-25 — P3.6 round-2 music scenarios BUILT (mock-validated)
- 2026-05-25 — Hexagonal-purity pass (`domain/` import-pure)
- Earlier entries (2026-05-19 → 2026-05-22) — initial draft, P0/P1/P2 execution, scenario layer rebuild — in the journal.
