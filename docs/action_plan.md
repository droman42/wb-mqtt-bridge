# Action Plan — locveil-bridge

**Status:** Living master plan. Updated 2026-07-06.
**Scope:** The `locveil-bridge` **monorepo** (`backend/` + `ui/` + `wb-rules/` + `ops/` + `docs/`). The
UI is no longer a separate repo — it was merged in during Phase 2.
**Target:** milestone — **scope-complete** (release 1 ships when every `[release]` task is `[x]`;
no calendar date; the gate is the ledger guard — `scripts/scope_guard.py` since OPS-22 — clean).

This document captures the project state and a prioritized action plan, revised as we work.

---

## Definition of release 1 (exit criteria) — **SIGNED OFF 2026-07-06 (REL-1, interactive)**

> **Scope gate (`single-task-ledger`):** release 1 ships only when **every task tagged `[release]`
> is `[x]`**. Every open task carries an explicit `[release]` or `[deferred]` tag (these replaced
> the `[house]`/`[later]`/`[parked]` milestone tags at the sign-off — `[house]` mapped to
> `[release]`, `[later]`+`[parked]` to `[deferred]`, then each row was verified individually).
> Run the ledger guard (`python3 scripts/scope_guard.py --config .scope-guard.toml`, OPS-22 — was
> `scripts/check_scope.py`) at each gate to prove nothing has drifted. The exit criteria below
> are the human-readable summary of that gate.
>
> **The release artifact** = a version tag + the **armv7** GHCR images (backend + UI) **deployed on
> the WB7 controller via the `ops/` compose stack, serving the house** (owned by **REL-2**).
> Release 1 targets armv7/WB7 exclusively; other platforms (arm64 next-gen WB, an amd64 image) are
> release-2 scope (OPS-11 et al.).

1. **Bridge lives on the controller** — compose cutover done, survives restart,
   `wb-rules/all_lights.js` deployed; the live `/system/catalog` realism dump matches `contracts/`
   → **REL-2**.
2. **Everything works on hardware** — the per-driver pass completes (**DRV-1**, incl. the
   mf_amplifier re-check), Apple TV app launching (**DRV-2**), the four music scenarios (**SCN-3**),
   plus the converged rack pass (**REL-3**: WB scenario cards, HVAC live pass, end-to-end
   re-verification — absorbs acceptance-gate item 5; the two-room drill rides SCN-13
   post-release with the second scenario set).
3. **Voice contract proven both ways** — `contracts/` pinned by the voice side (their TEST-17) +
   the crossover consumer test green (**VWB-16**); catalog completeness sweep (**VWB-13**).
4. **Operational quality** — the IR desync escape hatch (**DRV-5**); no shutdown hang / startup
   resource leak (**OPS-8**).
5. **Code-quality gate** — the "thorough code review" half of acceptance-gate item 4, run per
   `review-then-remediate` → **REL-5** (its own task, split out of REL-3 2026-07-09 — runnable off
   the rack; findings filed as fresh tasks, P0/P1 remediated before the tag).
6. **Docs accurate at release** — the project-wide doc reconciliation + master-doc convention
   handover (§0's recorded promise) → **REL-4** (DOC-11 folded in).
7. **CI green throughout** — backend suite + pyright 0 + import-linter + UI check/build + the
   ledger guard; standing, not a one-time check.

**Ordering — explicit gating between the `[release]` tasks (amended 2026-07-06):**

| Task | Gated by | Note |
|---|---|---|
| **REL-2** (cutover) | *(nothing)* | Root of the chain. Images already build in CI; user-at-rack. |
| **DRV-5**, **OPS-8** | *(nothing)* | Software-only; startable immediately, in any order. |
| **SCN-11** | **DRV-5** | Software-only; the scenario-page force-reconcile dialog, sequenced right after DRV-5 (added to release scope 2026-07-08, user decision). |
| **DRV-1**, **DRV-2**, **DRV-14**, **SCN-3**, **SCN-9** | rack session (user) | NOT gated on REL-2 — every HW pass so far ran against the dev-box bridge. Anything still open at cutover simply verifies on the WB7 bridge instead. SCN-3/SCN-9 additionally run after DRV-1 (drivers-before-composites gate). |
| **VWB-13** | **REL-2** | The sweep needs the bridge live on the WB7 broker. |
| **VWB-16** | voice **TEST-18** fixtures | The only cross-repo gate; lands whenever the fixtures do. |
| **REL-3** (rack pass) | **REL-2** + **DRV-1/2** + **DRV-14** + **SCN-3** + **SCN-9** + **DRV-5** + **SCN-11** + **OPS-8** + **VWB-13** | The HW convergence point: the end-to-end re-verification must run on the *deployed* bridge, after all code-touching `[release]` work has landed. |
| **REL-5** (code review) | *(nothing — all code-touching `[release]` work has landed)* | Split out of REL-3 2026-07-09. `review-then-remediate` — runnable off the rack **now**; findings filed as fresh tasks, P0/P1 remediation lands before REL-4/tag. |
| **REL-4** (docs pass) | **REL-3** + **REL-5** | Docs describe the final state — after both the rack pass and review remediation settle. Last task before the tag. |
| **the tag** | everything above + **VWB-16** | |

**Decisions recorded at sign-off (2026-07-06):** `POST /devices/{id}/action` ships in release 1 as
the documented internal/dev door (full demotion = **CORE-4**, deferred until the canonical HW passes
prove coverage) · DRV-3 / DRV-8 / children's-room round-3 / global-master aliases / VWB-12 sensors /
multi-arch images are all release-2 material · the survey-era "Open questions" section is closed
(answers recorded in place).

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
- `docs/design/zappiti-driver-spec.md` — **LIVING hardware/design contract (DRV-18, 2026-07-07):**
  the Zappiti Neo (Dune HD) IP-control contract (Part I) + the browser-native catalog & indexing
  design (Part II). **Drives DRV-19 / DRV-20.**
- `docs/archive/scenarios/scenario_redesign_progress.md` — **archived 2026-06-30 (DOC-10)**; frozen
  session log, superseded by the as-built spec above.
- `docs/archive/scenarios/layer3_step0_layout_analysis.md` — **archived 2026-06-30 (DOC-10)**; frozen
  Step-0 working artifact, now embodied in the as-built spec §17 + the placement engine.
- `docs/archive/monorepo_migration_plan.md` — DONE → historical.
- `project.md` / `architecture.md` / `conventions.md` / `docs/archive/adr/*` (frozen since DOC-15 — class retired by HK-6) — foundational project docs; the
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
**CORE** backend core/architecture · **LIB** pymotivaxmc2 library fixes (added 2026-07-15 off the
wedge-#3 review — tracked here, executed in the sibling `../pymotivaxmc2`, landing as pin bumps) ·
**DOC** docs/ledger/process · **REL** release (added 2026-07-06, mirrors the voice repo's REL series).

**Status:** `- [ ]` open · `- [x]` done · `- [~]` partial/paused. Inline markers (with reason):
`DOING` · `BLOCKED` · `DEFERRED` · `PARKED` · `HW-GATED` (waiting on the user at the rack).
**Priority** is a separate tag `[P0]`/`[P1]`/`[P2]`. **Milestone** tag (since 2026-07-06, REL-1):
`[release]` (required for release 1 — see "Definition of release 1" above) · `[deferred]`
(release-2+ material). The former `[house]`/`[later]`/`[parked]` tags mapped to
`[release]`/`[deferred]`/`[deferred]` at the sign-off; frozen docs still show the old tags.

**Two-file split:** this file holds **open + partial** tasks by workstream; completed tasks move to
[`action_plan_DONE.md`](action_plan_DONE.md) (by workstream) on completion, same change as the journal
entry. One ledger, **every ID in exactly one file**. The dated narrative lives in
[`action_plan_journal.md`](action_plan_journal.md) (frozen back-refs resolve via the alias map).

---

## Workstreams

### DRV — Device drivers

- [ ] **DRV-3** `[P2]` `[deferred]` — **IR-code learning page** — capture codes from physical remotes (`Сделать страничку для обучения IR кодам с пультов`).

- [ ] **DRV-4** `[P2]` `[deferred]` — **LG TV `audio_output` API — clean rework of the "press Home" hack + enable a true `watch_tv` (TV speakers only) scenario.** Discovered 2026-05-30: `asyncwebostv.controls.MediaControl` already exposes `set_audio_output(value)` (`ssap://audio/changeSoundOutput`) + subscribable `get_audio_output` (`ssap://audio/getSoundOutput`); valid values per library's `list_audio_output_sources` are `['tv_speaker', 'external_speaker', 'soundbar', 'bt_soundbar', 'tv_external_speaker']` (likely incomplete for newer webOS — `external_arc`, `external_optical`, `bt_headset`, `mobile`, `lineout` exist on some firmware; verify on OLED77G1RLA via `get_audio_output` first). **Architectural implication:** the TV's audio output is an INDEPENDENT axis from its video input — webOS lets you have HDMI 1 on screen while audio routes via ARC to the AVR. The current `tv_on_speakers` "press Home" mechanism (driver translates `set_input_source(arc)` → `handle_home`; commit `e5dffa4`) was correct for its PRIMARY video-side purpose (force TV out of HDMI input mode for the watch-TV-with-amp scenario) but uses the wrong axis. **Clean rework when next at LG TV:** (1) add `state.audio_output` field (subscribable); (2) add `handle_set_audio_output` action; (3) add `audio_output` capability domain with `source_modes` (reuses the symmetric src_port mechanism but on a different capability); (4) topology link's src_port becomes the audio-output value, translated in the driver to the webOS string (`arc` → `external_arc`, `tv_speaker` → `tv_speaker`, etc.). **Enables a clean `watch_tv` scenario** (TV speakers only, all other devices off — discarded today because the press-Home hack didn't fit). **HW verification gates before coding:** (a) exact webOS audio-output value for HDMI ARC on the OLED77G1RLA (call `get_audio_output` while on the current ARC-routing setup); (b) whether explicit ARC audio output is enough for eMotiva ARC engagement without forcing TV to internal mode (i.e., does the precondition observed today — "TV must be in TV mode" — go away if the TV is just explicitly broadcasting on ARC?); (c) whether the eMotiva still needs the power-cycle workaround for ARC engagement, or whether CEC + TV-broadcasting-on-ARC is sufficient; (d) subscription delivery reliability for `get_audio_output`. **No urgency** — current `tv_on_speakers` works for its purpose (still HW-pending anyway). File as a coherent LG-TV cleanup pass.

- [ ] **DRV-6** `[P2]` `[deferred]` `HW-GATED` — **IR ROM backup/restore tooling — cleanup + remaining large-code functional check.** **UPDATE 2026-05-29:** the functional test happened via mf_amplifier (207 banks 17–25) and exposed a real `ir_restore.py` bug — a busy/interrupted commit could leave a bank **stuck in edit mode**, which locks the *whole* blaster's playback (bank 65 was stuck → Modbus exc 06 "Slave Device Busy" on every Play). **Fixed live + `ir_restore.py` hardened** (guaranteed edit-exit, busy-retry `WRITE_RETRIES`, preflight `clear_stuck_edit`; see §6 2026-05-29). Restore *content* is vindicated (ROM bytes + ROM-Size match the backup). **Tooling cleanup DONE 2026-05-29** (see §6) — only the functional *play* test the user owns remains. The toolset is now `wb-rules/{ir,ir_common,ir_backup,ir_restore,ir_verify}.py` + `scp_ir_tools.sh`, fronted by a unified CLI **`ir.py`** (`ir.py backup|restore|verify …`, shared bus flags via argparse subparsers; each module stays standalone-runnable): `ir_common.py` is the shared, **general-purpose** core (register map + `modbus_client` wrapper + codec + jitter-tolerant `compare` + the `bus_window` service-stop context, **no A/V knowledge**); `ir_backup.py` now dumps **every non-empty bank** read from the device itself (was: only banks an A/V config referenced — CSV schema dropped the `referenced_by` column); `ir_verify.py` (promoted out of the deleted `temp/`, folds the one-off `diag_*` scripts) does a read-only jitter-tolerant verify with a first-diff dump on mismatch; `scp_ir_tools.sh` deploys them to `/tmp/ir-tools` (push, optional `pull` of produced CSVs). They back up and re-write WB-MSW v3 IR ROM banks so a firmware upgrade can't lose learned codes — the AppleTV volume IR (`wb-msw-v3_207` ROM5/6 + `wb-msw-v3_220` ROM1/2, §5.1 #7 AppleTV row) rides on this. Restore is **HW-verified clean on 220** (2 banks) **and 218** (14/14) once the verify read gets a 6× spaced retry (`f0213af`; the earlier failures were transient post-commit reads). **207** has **7 persistent mismatches** on its large learned `ld_player`/`vhs` codes (ROM65/66/68/69/70/78/79): the stored copy differs from the backup at **capture-jitter magnitude** (±~3 quanta) and is **stored-side, not corruption** — `diag_chunk.py` proved the first-diff index is invariant to read-chunk size, and these are multi-repeat IR frames that already carry per-repeat jitter in the backup itself. **Decision gated on a functional IR test the user owns** (fire e.g. ROM65 `ld_player:tray` at the real device):
  - **If the functional test FAILS** → back to wb-rules: the jittery banks aren't reproducing usable codes → investigate write fidelity / an alternate write path / re-learn those banks.
  - **If it PASSES** → byte-exact verification is the wrong bar for learned multi-repeat codes → byte-exact was already replaced by the jitter-tolerant `--tol` compare in the cleanup (no further script work). **Cleanup itself is DONE regardless of the play result** (it was the right refactor either way); a *failing* play test would reopen the FAILS branch (write fidelity / re-learn), not the scripts. See [[wb-msw-ir-restore-supported]]; commits `a7d7e5f`/`f2dbfc8`/`b46a8f3`/`f0213af`/`34fd1ee`.

- [ ] **DRV-8** `[P2]` `[deferred]` — **Roborock S7 vacuum — review & finish the design (DESIGN task).** The
  bridge's first **interactive-map appliance** (live state *plus* an interactive map — unlike the AV gear's
  remote layout or the WB-passthrough lights). A substantial **draft** design already exists —
  [`docs/design/roborock_vacuum.md`](../design/roborock_vacuum.md) (started 2026-06-09) — but it is
  **WIP with open questions flagged inline** and had **no plan ID** until now (filed 2026-06-30 to close
  the `every-task-in-the-ledger` gap — the design work happened untracked). **Deliverable
  (`design-then-implement`):** review the draft with the user, resolve the inline open questions, and
  **lock the design** — completion means the design is *done and recorded*, **not** that code shipped.
  **On completion, file the implementation follow-ups** as their own DRV tasks (the `RoborockDevice`
  driver + the interactive-map UI page). No driver/page work starts before the design locks.

- [ ] **DRV-15** `[P2]` `[deferred]` `HW-GATED` — **Revox A77 transport HW walk (moved out of DRV-1 /
  release scope, user decision 2026-07-07).** The last unwalked DRV-1 driver row, pulled out so DRV-1
  can complete without it: stop / play / ff / rewind / record (gated) on the A77 via the WB IR
  blaster, plus the common per-driver checklist (clean setup, `available=1`, state survives a bridge
  restart). Carries the old §5.1 #3 (A77 re-verify) lineage that DRV-1 had subsumed. Note: `music_reel`
  (SCN-3) drives the A77 — if the SCN-3 pass exercises it first, fold the result back here.


- [ ] **DRV-16** `[P2]` `[deferred]` `HW-GATED` — **LG TLS: actually verify against the configured
  certs + cert-capture tooling review.** Analysis 2026-07-07 (rack sitting, user noticed the
  warnings): both TV configs are correct (`secure: true`, valid `cert_file` PEMs in
  `config/devices/certs/`), but `_create_webos_tv` **hardcodes `verify_ssl=False`**
  ("Always … for WebOS TVs") and the library checks `verify_ssl` *before* `cert_file` — so the
  pinning branch (`load_verify_locations` + hostname-check off, the right pattern for LG
  self-signed certs) is never reached and every connect is **encrypted but unauthenticated**
  (the `SSL certificate verification disabled` warning on each attempt). **Fix:** driver default
  `verify_ssl = cert_file is not None` (keep the `ssl_options` override); on verification failure
  emit a clear "TV cert rotated — re-capture the PEM" error (LG regenerates certs on factory
  reset / some fw updates — the likely reason the False was hardcoded; pinning trades availability
  for authentication, so the failure message must say what to do). Rack re-test: both TVs
  connecting with verification ON. **Tooling half:** the capture tool lives in the LIBRARY —
  `asyncwebostv.SecureWebOSTV.get_certificate(save_path)` + standalone
  `extract_certificate(host, port=3001, output_file)` (`secure_connection.py:223`); the bridge has
  no wrapper. Review/update it there and expose a thin bridge-side entry (CLI now; the
  device-setup page flow consumes it post-release — `docs/planned/device-setup.md` is the home:
  pairing + cert capture belong in the same onboarding step).

- [ ] **DRV-17** `[P2]` `[deferred]` — **Auralic rich now-playing (cover art, progress, quality
  badge).** Filed off an EOD research question 2026-07-07. The bridge keeps **3** track fields
  (title/artist/album) out of **~27 the library already parses** from the same per-poll DIDL
  `Metadata` blob — discarded today: `albumArtwork` (albumArtURI — cover art), genre, year,
  track/disc numbers, the classical roles (composer/performer/conductor), channels/bitDepth/
  sampleRate/bitRate/duration/mimeType, etc. Beyond that, the unit offers (unwrapped by
  `openhomedevice`): **`Info.Details`** — the *stream truth*: actual bitrate/bitDepth/sampleRate,
  **lossless flag, codec name** (the "24/96 FLAC" badge data); **`Info.Metatext`** — live radio
  now-playing text; the **`Time` service** — position + duration (a working progress bar).
  **Scope:** (1) wrap Details/Metatext/Time in the `droman42/openhomedevice` fork (same style as
  the halt API; cross-repo: change there, pin here — batch with whatever PR #26 becomes);
  (2) extend `AuralicDeviceState` with the chosen fields — **contract change** (openapi + UI
  types regen, `config-ui-stays-functional` gates); (3) a now-playing panel on the streamer/
  scenario page (cover art via albumArtURI, progress from Time, quality badge from Details).
  Decide the field set at design time — don't ship all 27; pick what the panel renders.

- [ ] **DRV-19** `[P2]` `[deferred]` — **Zappiti Neo network driver (spec Part I).** Implement the
  Dune HD IP Control driver per [`docs/design/zappiti-driver-spec.md`](design/zappiti-driver-spec.md)
  §§1–8: HTTP-only driver class (fixed IP, router-pinned; no auth, no ADB), **discrete power**
  (`standby`/`main_screen` — replaces the `video` WirenboardIRDevice and retires its ROM toggle +
  the whole flaky-IR class; even remote-key fallbacks go over HTTP `ir_code`), **fire-then-poll
  launch verification** (§5.2 — `command_status=ok` only means "parsed"), slow steady-state status
  poll with transition-only logging (§5.3), track/subtitle/chapter control via `set_playback_state`.
  **Ripples (spec §7):** device + capability configs, `movie_zappiti` roles, catalog golden → voice
  re-pin; a status-reporting Neo lets the 5 s `processor.input→video.power` topology delay become a
  real feedback gate (pairs with SCN-10). **Pre-work gates (spec §8):** IP-Control persistence
  across a power-cycle, cold-launch wake from standby, mount-order stability with several shares.

- [ ] **DRV-20** `[P2]` `[deferred]` — **Zappiti catalog & indexing (spec Part II).** Per
  [`docs/design/zappiti-driver-spec.md`](design/zappiti-driver-spec.md) §§9–14: **browser-native
  indexer** in a catalog panel (mediainfo.js/WASM header probe, FilenameParser + TMDb matching
  ported to TS, match-resolution queue — TMDb-first with the contributor loop; OMDb only as a
  post-release optional module), bridge **ingest API + separate `catalog.sqlite`** (sole writer,
  plain SQL via the existing async persistence layer — no ORM), server-side `w500`/`w780` artwork
  on `/mnt/data`, browse/launch panel on the Zappiti device + movie scenario pages, series/season/
  episode modeling + mark-missing pruning. **First gate:** the §10.2 mediainfo.js↔ffprobe parity
  bench (fallback = the rejected container batch). Depends on DRV-19 (the launch path); expect a
  backend/UI split into subtasks when picked up (`config-ui-stays-functional` applies throughout).

- [ ] **DRV-22** `[P2]` `[deferred]` — **IR device `last_command` detail overwritten by the base chokepoint** (REL-5 #10). `wirenboard_ir_device/driver.py:319` sets `command_topic`/`command_payload` that `BaseDevice.update_state` immediately overwrites — cosmetic, no functional impact. Cleanup.


- [ ] **DRV-31** `[P2]` `[deferred]` — **Zappiti IR power toggle physically missed at scenario teardown** (REL-3 rack finding F5). 10:15:17 END: toggle dispatched, ROM fired, "success" — device kept playing (IR is fire-and-forget, `feedback:false`); subsequent manual toggles inverted believed-vs-physical parity. Hardware lane: re-learn ROM26 **holding the button** (the flaky single-frame-capture recipe), and investigate whether the Zappiti has **discrete on/off IR codes** to escape toggle parity entirely. DRV-5/SCN-11 remain the runtime escape hatch.

- [ ] **DRV-32** `[P2]` `[deferred]` `HW-GATED` — **eMotiva CEC restoration + ARC verification bench session** (REL-3 rack finding F6; owner decision 2026-07-10: post-release). The wedge+unplug **reset the XMC-2's CEC configuration** (Setup → HDMI CEC: `Enable` and `Audio to TV` found disabled via the remote menu probe `scripts/emotiva_menu_probe.py` + panel read) — ARC is structurally dead until re-enabled, `tv_on_speakers` expected-fail (honestly, once SCN-14 lands). Scope: (1) decide the granular CEC config as a *design choice* — `Enable · Audio to TV · Power On · Power Off · Volume · Input change`; `Input change` is the exact hijack vector of the incident, but disabling it may also break the designed `_power_cycle_for_arc` engagement — bench question; (2) re-enable per decision; (3) capture the **ARC-engagement notification choreography** (the stage-1 capture the 2026-07-10 session couldn't get with CEC dead) → feed the DRV-30 quiescence tuning; (4) the **stage-2 probe**: is switching away from *settled* ARC via `source_N` safe, or does leaving ARC need a choreographed exit; (5) verify `tv_on_speakers` end-to-end (sound physically moves). CEC config is volatile under crash — record the settings in the device notes so the next crash is a 2-minute restore. **Community/vendor research folded in** ([`docs/review/emotiva_arc_community_research_2026-07-15.md`](review/emotiva_arc_community_research_2026-07-15.md)): ARC/CEC live on **HDMI Output 2** (verify the cable is there); with the LG, community setup is CEC+ARC on both ends, **eARC OFF** (eARC needs the HDMI-2.0b board generation — check ours); **read the CEC menu state at the bench, don't assume defaults** (the "defaults ON" belief is unverified). Crucially, **no source documents any readiness/settle signal or command-pacing recipe** — step (3) is characterizing NEW ground, so capture the `audio_bitstream`/`audio_bits`/`video_format`/`video_space` transitions during ARC engagement as the candidate settle signal (these are real read-only notification channels; the plan is to watch `audio_bitstream` go from a no-lock value like `PCM 0.0` to a real format). Firmware 3.2 (DRV-31) rewrote the HDMI/CEC/ARC layer but **no owner report confirms it fixes lockups** — flash it as an improvement, not a cure.
  - **Evidence added 2026-07-11 — a SECOND wedge (spontaneous, no bridge involvement) + a firmware lead.** The eMotiva wedged again the evening of 2026-07-10 (~19:14, controller log `service.log.20260710.log`): it died **while idle in standby with ZERO bridge interaction** — no command, no `set_input`, no scenario; it was sending normal `keepAlive` heartbeats every ~7.5 s and simply stopped. **DRV-30 worked as designed** — the watchdog flagged `heartbeat lost` at 28 s, marked it unreachable, and probed re-subscribe (which can't revive a hard firmware wedge; it retried 19:14→23:59, never recovered). Network was fine (every other device healthy through 19:14). The death window (19:14:01–08) **overlaps the Apple-TV-power-on at 19:14:04** → prime suspect is **CEC one-touch-play** waking the AVR into the same HDMI/ARC fragility — IF CEC was re-enabled after the morning (owner to confirm). Confirms the XMC-2 also dies *unprompted*, not only on a bridge-triggered `set_input`.
  - **FIRMWARE LEAD (bench step 0, do BEFORE the CEC design work).** The unit is the **original XMC-2** (transponder model `XMC-2`, not `XMC-2+`), confirmed running **3.1 (`EmotivaUpdate-3_1-2022_11_14`)**. The latest downloadable firmware for the original XMC-2 (shared with RMC-1/RMC-1L) is **3.2 (2023-05-11)** — Emotiva's "CURRENT VERSION"; the `+`-model 5.x line does NOT apply. So the unit is **exactly one release behind — on the version immediately before the HDMI rewrite** (3.2's notes explicitly cite improvements "over v3.1"). Its changelog is exactly this failure's subsystem: a **completely rewritten HDMI firmware layer**, "better HDMI-CEC and ARC support reliability", "enhanced HDMI switching stability", "significant improvements in overall system stability" (+ eARC, needs an enabled board). **Recommendation: flash 3.2 as step 0** — it may resolve both the morning ARC-handshake wedge and the spontaneous standby death; only if it still wedges on 3.2 is this a hardware/RMA fault. Refs: `emotiva.com/pages/firmware-downloads`, `emotiva.com/blogs/news/rmc-1-rmc-1l-and-xmc-2-firmware-3-2-now-available`. No bridge change warranted either way — DRV-30 detection is the correct permanent posture.
    - **HDMI board generation (bench check, when powered on).** The wedging HDMI/CEC/ARC layer is a **discrete versioned board**: Menu → Information → **`HDMI Version`** reports it. `≥ 10.xx` = eARC-enabled board (eARC becomes usable once on 3.2); `< 10.xx` = no eARC board (a paid Emotiva hardware upgrade adds it). **NB the stability/CEC/ARC-reliability fixes in 3.2 are firmware and apply to ANY board** — a sub-10.xx reading is NOT a reason to skip 3.2. **Readable remotely via `scripts/emotiva_menu_probe.py`** — Information-menu rows render their values in `emotivaNotify` (unlike the blank leaf-editors), so `HDMI Version` can be captured without a panel visit when the unit is next on.
    - **3.2 install procedure (from the official 5/17/23 bulletin) — bridge-relevant bits.** USB FAT/FAT32 (exFAT ok; not NTFS/Apple), file in root, don't rename/unzip; the flash is **sandwiched between two Factory Resets** (before + after) + a mandatory TV AC power-cycle + Restore Settings — ~10–15 min flash, non-trivial. **(a) The double Factory Reset WIPES all config incl. CEC** → do the DRV-32 CEC-config decision fresh right here (the resets hand us a clean slate). **(b) After ANY power-off, wait a FULL 30 s before power-on** — the eMotiva's Ethernet port needs 30 s to reset or it returns with NO network (the bridge would then see it unreachable — DRV-30 would correctly report that; not a bridge bug). **(c)** config Restore may not survive the version jump → keep a written note of key settings. **(d)** new per-input **HDMI 1.4/2.0 compatibility** knob (bulletin note #8 flags HDMI-2.0↔1.4b generation mismatches as "many issues people face"). **CONCRETE for this rack (owner 2026-07-11):** the eMotiva bus mixes generations — **source1=Zappiti (4K/2.0)** + **source2=appletv_living (4K/2.0)** vs **source3=upscaler (HDMI 1.3 — older than the 1.4b cited)**. Set **source3 → HDMI 1.4-compat** (zero downside — the upscaler feeds LD/VHS, outputs ≤1080p, no 4K to lose), keep source1/source2 on **2.0**. Isolating the old 1.3 device on the compat mode is a strong, free candidate for the HDMI-subsystem instability behind both wedges — do it right after the 3.2 flash (which resets it anyway). No-downgrade-below-3.x (bricks). Refs in `contracts`-adjacent research: bulletin PDF `Official_RMC-1_RMC-1L_XMC-2_Firmware_v3.2_Bulletin_-_5_17_23.pdf` (Emotiva CDN).

- [ ] **DRV-37** `[P2]` `[deferred]` `BLOCKED` — **Implement `EspManagedDevice` per the DRV-36 design**
  ([`docs/design/esp_managed_device.md`](design/esp_managed_device.md)). **BLOCKED on the satellite's
  first conforming descriptor** (their DES-4 output for the first real device — the descriptor is the
  implementation fixture; do not build against a hypothetical). Scope when it unblocks: the
  `infrastructure/devices/esp_managed/` package (driver + `EspManagedDeviceConfig` + descriptor-pin
  loading with fail-fast validation against the convention pin + the descriptor→class-map translation
  as a tested pure function); `EspManagedDeviceState` into `OPENAPI_EXTRA_MODELS` +
  `device-state-mapping.json` (the one-time openapi bump); entry point + import-linter independence
  listing; the **deck vocabulary contract cut** (transport family per the satellite's repo-to-repo
  vocabulary request, batched: capability vocabulary + catalog projection + golden bump + the single
  voice re-pin); **VWB-39 activates alongside** (the descriptor-pin conformance test); UI types regen.
  Per-deck device configs + rack cutover stay UNFILED until satellite first-light (HW-GATED,
  satellite-triggered). The HVACs are out of scope permanently unless the owner reopens firmware
  (`device_integration_convention.md` §2).

- [~] **DRV-38** `[P1]` `HW-GATED` — **eMotiva wedge #2 (2026-07-12, `movie_appletv`): close the
  DRV-30 coverage gap + REVIEW the topology layer's protection model.** **(a) DONE 2026-07-13
  (`b4407bc`):** the readiness hold moved to the dispatch seam — `EMotivaXMC2.execute_action`
  override gates EVERY command (zone-aware exemption: `power_on` zone 1 exempt, zone 2 — the
  wedge command — gated; recovery paths exempt; `force` does NOT bypass); fresh-`arc` full-window
  hold now applies to any command; wedge-replay regression test through real dispatch; suite 719.
  **(b) DONE 2026-07-13:** the topology-layer review —
  [`docs/review/topology_readiness_review_2026-07-13.md`](review/topology_readiness_review_2026-07-13.md)
  (three lanes: only the eMotiva is HARD-RISK fleet-wide; the executor honors a driver-side hold
  and the gate clock starts after it; zone2 fired ungated in all 5 AV scenarios, spuriously in
  ld/vhs). Remediations filed: **SCN-16** (zone-aware power planning), **SCN-17** (executor
  dispatch bound). **REMAINING (the HW gate): the rack replay** — start `movie_appletv` with the
  TV on against the recovered eMotiva (expect the zone-2 hold in the log: "held power_on … after
  power-on (readiness gate)"), plus the DRV-32 CEC re-check (the wedge unplug likely reset it
  again). Original finding: Evidence (frozen):
  [`docs/review/emotiva_wedge_20260712.md`](review/emotiva_wedge_20260712.md) — the device's
  last-ever packet was its ack to an **ungated `zone2_power_on`** fired 2.3 s into a
  bridge-visible ARC handshake (`input_source` was already `'arc'` in the driver's own state);
  `_await_input_ready` has exactly one call site (`handle_set_input`), so any plan shape whose
  post-power step is NOT an input switch walks straight into the known-fatal window —
  `movie_appletv` (input already correct ⇒ next step is zone-2 power) was never exercised live
  after DRV-30 (zero appletv mentions in the REL-3 record). NOT a config regression (zone2
  topology link + scenario predate the monorepo); the firmware vulnerability itself stands —
  DRV-31/32 (the 3.2 flash + CEC bench) keep full value, and this wedge's unplug recovery has
  likely reset CEC again (re-check per DRV-32). **Scope: (a) the immediate fix** — hoist the
  ARC-window hold from `handle_set_input` to cover EVERY control-port command the device accepts
  post-power-on (zone2 power, volume, mode, …): gate at the driver's dispatch seam, not
  per-handler; regression test = the wedge plan shape (power_on → fresh-`arc` claim →
  zone2_power_on must HOLD). **(b) the topology-layer review** (`review-then-remediate`;
  deliverable = frozen evidence under `docs/review/`, remediations filed as fresh tasks): the
  plan's post-power command per device is an EMERGENT property of the topology diff, so
  per-handler guards can never cover a device's unready window — review whether per-device
  readiness belongs at the executor/dispatch layer as a first-class concept; audit every driver
  for post-power vulnerable windows (which devices define "ready"? who enforces it?); examine
  whether topology `ordering`/`delay_ms` settles are currently masking sibling gaps (they pace
  authored edges, blind to runtime windows) and whether SCN-14/15 outcome-gates are being
  mistaken for entry-gates. Live verification HW-GATED at the rack (and needs the eMotiva
  recovered first).

- [ ] **DRV-39** `[P1]` — **eMotiva `power_on` handler: quiet the post-send tail — it floods the
  fatal window the gate was built to protect** (wedge #3, 2026-07-14 08:07, startup restore of
  `movie_appletv`; evidence: [`docs/review/emotiva_wedge_20260714.md`](review/emotiva_wedge_20260714.md)
  Findings 1 + 4 + 4c). **This is the third wedge in a whack-a-mole chain, and the reason the
  per-command approach cannot converge** (Finding 4c): all five video scenarios share one shape —
  power processor, switch processor input, power zone-2 — and the wedge is *whichever control-port
  packet lands in the CEC/ARC window*. DRV-30 gated `set_input` → wedge #2 surfaced ungated
  `zone2_power_on` (appletv's `set_input` was diff-dropped, input already `source2`). DRV-38(a) gated
  every *dispatched* command → wedge #3 surfaced the residual: `handle_power_on`'s own tail, which
  runs inside the exempt `power_on` — a "defensive" `client.subscribe(9 props)` right after the ack +
  a `sleep(1.0)` → `_refresh_device_state()` full Update batch the library silently retries whole 3×
  (2 s/3 s/4.5 s), a dozen-plus control-port packets in the first seconds of the power-on transition;
  wedge #3's first anomaly is exactly this batch timing out at +3.3 s. Chasing the next command each
  time is why the invariant, not another gated handler, is the fix. **Fix shape —
  RESHAPED by the owner's silence-while-busy principle (2026-07-15 chat, review annotation #3):
  make *busy* a first-class driver state and the invariant "zero new traffic while busy".**
  (1) **Busy latch:** armed by ANY commanded transition (power AND input switches — anything that
  renegotiates HDMI/CEC; today only power-on anchors the window) and by uncommanded transition
  notifications (the `arc` grab, regardless of who started it); cleared by the completion
  notification + the existing 2 s quiescence. (2) **Silence while latched:** no commands, no
  queries, no handler tails — drop the defensive re-subscribe (subscriptions survive standby→on on
  fw 3.1, observed; mains cold boot is covered by the DRV-30 watchdog probe) and drop/defer the
  status batch (the burst arrives unbidden; per the protocol's own model — ack = receipt, the
  notification = completion). (3) **Cap fails CLOSED:** on the hold cap expiring, refuse the
  command with a speakable "still settling" error instead of releasing it into a possibly-live
  window (today's release-on-cap is "try while busy, delayed"; wedge cost ≫ failed-step cost);
  `force` stays the operator override — CONFIRM this flip at execution, it changes DRV-38(a)
  semantics. Regression test through real dispatch (the DRV-38 wedge-replay pattern); rack
  verification rides the DRV-38 replay session. LIB-2's retry=0 / `ack="no"` options are this
  invariant's library-side half (a retry into a busy device is new traffic too). **Second,
  independent rationale from research** ([`docs/review/emotiva_arc_community_research_2026-07-15.md`](review/emotiva_arc_community_research_2026-07-15.md)):
  the official openHAB Emotiva binding documents that "Emotiva processors have limited processing
  power, so if the binding subscribes to all channels simultaneously the device might grind to a
  halt… requiring a manual reboot" — a second integrator hitting our wedge as a *concurrent-load*
  problem, not just a timing one. Adds a lever beyond silence-while-busy: **reduce subscription
  breadth** — we subscribe to all 9–10 properties at once and the power-on tail re-subscribes to
  all again; evaluate trimming the monitored set to what the driver actually consumes. (openHAB
  independently uses the same 7.5 s keepalive / 2-min-retry / OFFLINE design — our watchdog
  parameters are validated.)

- [ ] **DRV-40** `[P2]` `[deferred]` — **Watchdog recovery probe needs backoff** (wedge #3 record:
  **2 455** re-subscribe cycles over 12.5 h, one every ~17 s, against a dead device —
  [`emotiva_wedge_20260714.md`](review/emotiva_wedge_20260714.md) timeline). Harmless but noisy
  (7 366 controlPort timeout warnings). Keep the first-probe latency (fast recovery detection),
  then back off exponentially to a cap (~60–120 s); reset on recovery. Pure driver change
  (`_watchdog_tick`); pairs with LIB-2's retry damping (each probe today is 3 library attempts).

### SCN — Scenarios / topology / reconciler

- [ ] **SCN-10** `[P2]` `[deferred]` — **Feedback-gated topology ordering edges (wait for the
  *reported* state, not just the ack).** Found live during the SCN-9 walk (2026-07-07, the
  movie_appletv → movie_zappiti switch-back): the `processor.input → video.power` ordering edge
  sequenced correctly but released the successor **4 ms after the eMotiva's ack** — the ack is
  instant while the physical HDMI re-route takes seconds, so the Zappiti booted into an unrouted
  sink and lost its HDMI output (known hardware quirk, needs repower). **Mitigated with
  `delay_ms: 5000`** on the edge (topology.json, same commit) — a blunt fixed wait. The proper
  mechanism: an ordering edge that releases the successor when the `first` device's **state
  reports the commanded value** (the eMotiva notifies `source` within ~0.5 s of the real switch;
  poll the device state with a bounded timeout, fall back to `delay_ms`). Feedback-capable
  domains only (`feedback: true` in the capability map). **Design note (user question answered
  2026-07-07): no new capability schema needed** — the vocabulary already exists end-to-end:
  `feedback` per domain (the "can it report" bit), `state_field` (where the report lands),
  `gate.poll_timeout_ms` (how long to wait — eMotiva input already declares 3000 ms), and the
  reconciler already threads all three into each `PlannedAction` for *within-device*
  confirmation. SCN-10 is therefore reconciler-only logic plus at most one optional
  topology-edge field (confirm-vs-delay semantics); `feedback: false` firsts fall back to
  `delay_ms`. Post-release: the 5 s settle serves the house fine.

- [ ] **SCN-13** `[P2]` `[deferred]` — **Second-room scenario set + the live two-room concurrency
  drill.** Filed 2026-07-10 when the drill was pulled out of REL-3: the SCN-6 per-room mechanism
  shipped and is mock-verified (14-test two-room proxy suite), but **every configured scenario is
  `living_room`** — the children-room set was declared "a future round" at the SCN-4/SCN-6
  amendment (journal 2026-07-04) and never became scope, so the drill has nothing to run against
  and cannot gate release 1. Scope when picked up: author the children-room scenarios (the room
  already carries `children_room_tv` + `appletv_children`), then the HW verification SCN-6 recorded
  as owed — both rooms' scenarios active concurrently, per-room Scenario Manager isolation (no
  cross-talk, both WB «Сценарии» cards correct, in-room-only transition diffs).

- [ ] **SCN-18** `[P1]` — **Boot-restore policy: a redeploy must not cold-start the rack unattended**
  (wedge #3 finding 6 — [`docs/review/emotiva_wedge_20260714.md`](review/emotiva_wedge_20260714.md)).
  On 2026-07-14 08:07 the bridge restart re-ran the full `movie_appletv` cold-start plan because the
  scenario was persisted active: a code deploy became a hardware-touching event, reproducing the
  known-dangerous cold-start gesture (eMotiva power-on with TV state unknown) with nobody watching —
  and it wedged the processor. **Decision-first (owner):** options — (a) restore *tracking only*
  (mark the scenario active, execute nothing; first user interaction reconciles), (b) reconcile-
  observe (compute the diff, publish it as pending, act only on confirmation), (c) keep executing
  but only within N minutes of the persisted timestamp (a deploy hours later restores tracking
  only), (d) status quo. Then implement per `design-then-implement`. Touches
  `domain/scenarios/service.py` restore path; no contract change expected.

### VWB — Voice-integration + native WB onboarding

**Context (the P3.7 push — design narrative preserved from the former phase section):**

**Driving doc:** `docs/design/voice_integration_contract_draft.md` (AGREED bridge ↔ Irene contract).
Sister-project counterpart: `locveil-voice/docs/design/mqtt_integration.md` §10 (Irene's ARCH-8,
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
subtree. The config scanner (`infrastructure/config/validation.py`) recurses into subdirectories, so flat
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
device class (alongside future ESP32 work in this project, see PARKED entry **DRV-7** for the
firmware scaffold — pointer fixed from the old positional "§5", DRV-34). **At v1 ship,
`ESP32ManagedDevice` is behaviourally identical to
`WbPassthroughDevice`** (subscribes to value topics, publishes to `/on`, type-coerces via the
profile metadata) — the `hvac` profile drives both. The distinct class exists so the HVAC
units have a stable identity to grow into: future versions will expose **additional
ESP32-specific capabilities to the system, specifically to the UI** (e.g. provisioning state,
OTA progress, NVS-stored identity, sleep/wake telemetry, firmware version) that don't belong
on a generic WB-passthrough device. Decision locked 2026-06-08.

> **SUPERSEDED 2026-07-12 (DRV-34; council HK-4 / board PROD-15) — preserved as the design
> narrative of its day; both halves of the paragraph above have since been overtaken:**
> **(1) The HVACs never became this class.** They run **ESP8266** (Wemos D1 Mini — the board's
> HK-4 text is right, this paragraph's "run on ESP32" was wrong; recorded at DRV-27 decision D1)
> and graduated 2026-07-10 to the bespoke **`MitsubishiHvac`** driver (design DRV-27
> rev. 2, live since DRV-28) — the contract is the *mitsubishi2wb firmware's*, not a chip's.
> HVAC drivers/configs stay bridge-side ALWAYS (HK-4 charter). **(2) The ESP-managed class
> arrives under a new name and shape:** **`EspManagedDevice`** (design task DRV-36) —
> descriptor-native, consuming the device-integration-convention descriptors (VWB-38) of
> satellite-managed devices (the `ESP32/` deck bridges move to `locveil-satellite`; DRV-35).
> The grow-into-UI-surfaces intent (provisioning state, OTA progress, firmware version …)
> carries over to that design.

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

- [ ] **VWB-12** `[P2]` `[deferred]` — `wb-msw-v3_*` sensor side — decide unified config (IR + `sensor`) vs split entry; implement. **DEFERRED POST-RELEASE 2026-07-04 (user decision, both sides — the voice repo defers sensor state-queries equally).** Analysis done in chat (see journal 2026-07-04): recommendation = **split entry** — per-room sensor devices (`sensor_room` profile, partial mirrors per the sauna precedent), IR side stays transport plumbing referenced from AV configs (module-is-wiring precedent: `wb-mr6c_47` hosts 6 lights and is no device either); a module-level IR entity can be added *alongside* later if DRV-3 ever needs one, without touching the sensor devices. When picked up: classic paste session per room + **verify control names per module firmware** (the recorded firmware-doc cross-reference warning; MSW inventory today: `wb-msw-v3_207` living room, `218`, `220` children — all currently IR-only references).

- [ ] **VWB-16** `[P2]` `[deferred]` — **Consumer contract test — crafted canonical `DeviceCommand` → native/echo** (cross-project; the consumer half of the bidirectional contract, pairs with `locveil-voice` TEST-18's producer half). **Re-tagged `[release]` → `[deferred]` 2026-07-10 (owner decision at the v0.6.0 cut):** it depends on the voice repo's TEST-18 crossover fixtures, which aren't ready — release 1 must not hang on a sibling repo. Lands whenever the fixtures do; the golden catalog it tests against (`5622ba7a1a78102a`) is stable, so no urgency. Drive the bridge from the shared **`{utterance → expected canonical command}` crossover fixtures** (using the canonical-command half only — the utterance is Irene's concern): feed each crafted canonical command and assert it dispatches the right native action / value-topic echo, resolved against the **same golden catalog** the voice side tests against (so device-ids/capabilities can't drift apart). Depends on VWB-15's committed artifact.
  - **Sequence-form caveat — RESOLVED 2026-07-04 (VWB-17 DONE):** the canonical endpoint now routes `sequence`-form actions (shared `CapabilityAction.expand()` — per-step param translation, inter-step `delay_after_ms`, mid-sequence failure naming the step). Crossover fixtures may cover sequence-form actions freely.
  - Spec: `locveil-voice/docs/design/mqtt_integration.md` §14.

- [ ] **VWB-31** `[P2]` `[deferred]` — **Canonical handler-availability failure mis-surfaces as `internal_error` (500) instead of `device_unreachable` (503) to voice** (REL-5 #8). `presentation/api/routers/devices.py:503`. Deferred — no live voice consumer yet; fix maps availability failures to a speakable 503.

- [ ] **VWB-33** `[P1]` `[deferred]` — **Harmonise language-data contribution across all devices/capabilities — design** (`design-then-implement`; filed 2026-07-10 off the chat analysis of how devices contribute language-specific data to voice). **Post-release, board-level cross-repo (owner decision 2026-07-10 — re-tagged out of `[release]`):** the convention is **half the voice side's** (the verbs-are-donations rule binds their repo too), so this is a **board-as-outbox cross-repo design session** — one of the first tasks *after* the Locveil board is established, alongside VWB-34 (both are board-delegated cross-repo designs; `locveil-commons/process/` is the candidate shared-spec home). NOT a release-1 gate. The analysis established the ownership split — **the bridge catalog contributes the NOUNS** (device `names` ru/en/de, device/room `aliases`, field `labels`, enum `{wire, canonical, labels}` value labels — the voice side's matching surfaces: it matches utterance words against `labels` in the active locale and posts `canonical`), **the voice donations contribute the VERBS** (phrases/lemmas per handler method; `CatalogAction` deliberately carries NO labels), and **group tokens** (`light`/`cover`/`fan`…) are unlocalized identifiers whose spoken words live in donation choice surfaces. Found inconsistencies to resolve by design: **(1)** uneven label-language coverage (kitchen hood field/value labels are ru/en only; HVAC carries full ru/en/de; some fleet fields carry no labels at all) — decide the required set (ru/en/de?) and whether a guard enforces it (`check`-style test or catalog-build warning); **(2)** no recorded CONVENTION for which surfaces must be localized vs must stay canonical tokens — write it down (candidate home: `contracts/README.md` in user-facing voice + the capability-map authoring guidance), including the verbs-are-donations rule so nobody adds action labels to the catalog; **(3)** `CatalogParam.description`/`unit` are English-only prose — decide: keep as developer-facing (documented as such) or localize; **(4)** device `aliases` coverage is sparse and ru-only — decide whether aliases become part of the authoring checklist for new devices; **(5)** audit the full fleet against the decided convention and file the implementation follow-up(s) with the gap list. Deliverable: the design/convention document + filed follow-ups (a finding is not scope until it has an ID). Coordinate with the voice side (the convention is half theirs — donations); candidate shared-spec home per the Domovoy arc (`locveil-commons/process/`) noted, not required for release 1.

- [ ] **VWB-34** `[P2]` `[deferred]` — **Publish confirmation-timing in the contract — design** (`design-then-implement`; filed 2026-07-10 off the DRV-29 post-mortem chat: "your HTTP timeout must exceed 15 s" is contract information currently delivered out-of-band in a handover note — the same coupling class DRV-29 fixed, one layer up: retune a gate to 30 s and voice's timeouts fire again with no signal in the pinned catalog). **Cross-repo** — intended for delegation to the board once board-as-outbox lands (Domovoy arc); the voice side co-owns the consumption design (example on the table: implement scenario startup as a *durable action* on the voice side). Three tiers established in the chat analysis, to be confirmed/refined by the design: **(1) capabilities** — publish a client-meaningful optional `confirm_timeout_ms` per capability (present only when gated), derived from but NOT exposing the internal `gate` object (the gate is implementation — reconciler polling cadence; the latency promise is contract — keeps internals re-tunable without a re-pin); consumers: voice sizes per-capability HTTP timeouts and can auto-choose `wait:false` + optimistic speech for slow capabilities instead of hardcoding device lists; the UI's HvacPanel shows an honest progress expectation; extends VWB-24's zero-round-trip philosophy (catalog says what's valid → now also what to expect). **(2) scenarios** — a static estimate would lie (switch duration is diff-dependent: warm shared devices ≈ seconds, cold start ≈ the critical path); the honest publishable fact is an **upper bound** `max_duration_ms`, mechanically derivable from the cold-start plan (step gates + IR delays along the critical path) — a ceiling for client timeouts, never exceeded, usually beaten; progress narration uses the existing SSE state stream, not a number. **(3) async composites** — the fully clean answer for long-running composites is the async-job pattern (`202 Accepted` + progress events + completion event, dissolving the timeout question; the durable-action idea lives here) — a real API redesign touching voice + UI both, deliberately the design's decision whether/when, NOT presumed. Contract cost when implemented: catalog model + derivation + golden/openapi re-pin + voice re-pin — batch with an adjacent deliberate contract cut (OPS-16 tagging discipline applies). Deliverable: design doc + filed implementation follow-up(s).

- [ ] **VWB-39** `[P2]` `[deferred]` — **Descriptor-pin conformance test (PROD-15 bridge delegation,
  item 4; the VWB-37 pattern).** VWB-38's versioned artifact EXISTS (`device-integration-v1`, DONE
  2026-07-12): pin it (the report-protocol pin recipe — byte-identical copy, tag-verified; org pin
  shape at `contracts/pins/<name>/` since VWB-40) and lock the bridge-side
  consuming surface to the pin with a unit test (`test_report_protocol_pin.py` shape). **Activates
  alongside DRV-37** (the implementation — DRV-36 was design-only; the consuming constants land in
  DRV-37), i.e. at the satellite's first conforming descriptor (the PROD-20 chain). *(Dep line
  re-anchored 2026-07-14, DOC-16 — the old text named done-VWB-38 as pending and "DRV-36's
  implementation".)*


### UI — config-ui


- [ ] **UI-10** `[P2]` `[deferred]` — **Inputs/apps dropdowns don't reflect the live selection.** Found
  at the 2026-07-07 rack sitting (living-room TV playing ivi; page shows "Select App…"): on every
  page mount the dropdowns render the placeholder even though device state knows the answer —
  `selectedInput`/`selectedApp` are plain local `useState('')` in `useRemoteControlData.ts`
  (`useInputSelection`/`useAppLaunching`), seeded from nothing and updated only by the user's own
  picks in that mount; they also never follow changes made elsewhere (physical remote, scenario,
  voice). Affects **every device/scenario page with an inputs or apps dropdown**. **Fix shape:**
  derive the selection from the live state (`current_app` / `input_source` via the existing
  `['devices', id, 'state']` query that SSE keeps fresh), keeping local state only as an optimistic
  overlay while a pick is in flight. **Mind the id/label mismatch per class:** app options key by
  app id (`ivi` — matches `current_app`), but LG `state.input_source` stores the *label* ("Emotiva
  XMC") while input options key by id (`HDMI_2`), and eMotiva state stores canonical `sourceN` —
  normalization per dropdown is the real work. `config-ui-stays-functional` gates apply.
  **Second facet (rack sitting, later same day):** the power gate that gray-outs the selector
  (`useRemoteControlData`: requires `power === 'on'` + `connected`) is **too strict per class** —
  an Auralic in standby is connected and its source list is likely readable (`Product.SourceXml`
  is served in standby); the streamer page showed a hard-disabled «device powered off» selector
  while the user stood next to a lit unit. Make the gate capability/class-informed (or allow
  opening with cached options + a standby hint); pairs with DRV-14's tri-state power semantics
  (on / standby / halted).

- [ ] **UI-11** `[P2]` `[deferred]` — **Same-name devices are indistinguishable on device pages.**
  Found at the 2026-07-07 rack sitting: both LG TVs are named «Телевизор»; the user opened the
  children's-room one believing it was the living room's and lost minutes to "why does it show
  powered off????". Nothing on the page (or the list it was picked from) names the room. **Fix
  shape:** room-qualify the device-page header («Телевизор — Детская»; room name is already in the
  catalog/rooms data the UI loads), and add the room label in whatever nav/list renders bare device
  names. Pure UI; no contract change expected.

- [ ] **UI-12** `[P2]` `[deferred]` — **Room lists miscategorize the whole WB-passthrough fleet as
  "devices".** Found at the 2026-07-07 rack sitting: every WB-passthrough instance (lights,
  curtains, heating, HVACs, sensors) shows in the room **device** list; the appliance list holds
  only `kitchen_hood` — ironically the one appliance that is NOT a passthrough. **Mechanism
  (investigated):** the split is `device_category` from each device config
  (`BaseDeviceConfig.device_category`, default `"device"`; UI filters on it via the layout
  manifest's `deviceCategory`). Only `kitchen_hood.json` sets `"appliance"` — even the 3 Mitsubishi
  HVACs (which HAVE bespoke `HvacPanel` appliance pages) default to `device`. **Fix shape:**
  backend categorization, not UI logic — either default `device_category = "appliance"` at the
  `WbPassthroughDeviceConfig` class level (one line, covers all 57+ instances incl. HVACs) or bulk
  per-config; **mind the side-effects:** `capabilities/loader.py` skips the exposed-command
  validation for appliance-category devices, and `device_category` rides the layout manifest +
  possibly the catalog → contract/golden regen check + `config-ui-stays-functional` gates apply.
  Routing is unaffected (appliance-list entries without a bespoke page fall through to the runtime
  layout as today). Decide during implementation whether pure-sensor instances belong in either
  list at all.


- [ ] **UI-15** `[P2]` `[deferred]` — **Force re-tap arms non-power controls but only PowerZone buttons show the armed pulse** (REL-5 #18, PLAUSIBLE). `ui/src/components/RemoteControlLayout.tsx:1128`. Deferred — minor UX; fold the visual feel-check into the REL-3 rack pass.

- [ ] **UI-18** `[P1]` — **Bridge Workbench plugin: package skeleton + the read-only v1 cut** (filed at
  UI-17 completion, `design-then-implement`; design:
  [`docs/design/ui/workbench_split.md`](design/ui/workbench_split.md) §2). New top-level
  `workbench-plugin/` (working name `@locveil/bridge-workbench-plugin`): vite-6 **library** build →
  ESM dist + types + embedded generated API types (own `gen:api-types`; no imports from `ui/`);
  eslint-9 flat config mirroring `ui/eslint.config.js`. Contract-v1 descriptor: id `bridge`, RU/EN
  i18n bundles, status slot fed from `GET /system` + the catalog version hash, `reportHook` → the
  live `POST /reports`. Pages in the v1 cut: **voice-readiness** as the first real page (existing
  read/action surfaces only — catalog version, `/canonical` test-utterance); device-setup +
  topology-setup as shells with their **config-writing verbs dormant under the named gate
  `PROD-4-auth`** (the deep features — WB-cell importer, graph editor — stay in their planned pages
  and file when pulled). **Gated on** the commons workbench shell existing to consume the built
  artifact (the shell + the first two plugins co-develop; PROD-10 rule); ui-kit restyle rides
  `ui-kit-v1`. `config-ui-stays-functional` applies to the plugin's own check/build gates.

### OPS — Docker / CI-CD / deploy / ops

- [ ] **OPS-11** `[P2]` `[deferred]` — **Multi-arch images: add `linux/arm64` (aarch64, next-gen Wirenboard) alongside `linux/arm/v7`.** Filed 2026-07-02 off a chat analysis (sister-repo prompt: `locveil-voice` builds armv7 + aarch64 + standalone). **Unlike the voice repo** (per-target Dockerfiles + arch-suffixed image names, forced by per-platform ML profiles), the bridge's images are identical on both arches → use buildx **multi-platform manifests**: `platforms: linux/arm/v7,linux/arm64` in both image jobs of `.github/workflows/build-arm.yml` yields ONE manifest list per existing tag — WB7 pulls armv7, WB8 pulls arm64 from the same `ghcr.io/...:latest`; `ops/` (compose / `update.sh` / INSTALL.md flow) unchanged. **Work items:** (1) workflow: extend `platforms`, **drop the `ARCH=arm32v7` build-arg** — the Dockerfile's `${ARCH:+$ARCH/}python` prefix predates platform-aware buildx and would force the arm32 base into the arm64 leg (Dockerfile itself needs no change; `ARG ARCH=` defaults empty); (2) `ui/Dockerfile`: stage 1 → `FROM --platform=$BUILDPLATFORM node:20 AS builder` — the `dist/` bundle is arch-independent, so the ~14-min QEMU node build runs natively on the amd64 runner once and only the small nginx stage builds per-arch (bonus: the *existing* armv7 UI build should drop to ~2-3 min); (3) docs: a sentence each in `ops/INSTALL.md` + the READMEs noting the images are multi-arch. **Notes:** piwheels extra-index is armv7-only but harmless on arm64 (PyPI aarch64 cp311 wheel coverage is good — likely a faster leg than armv7); that `/etc/pip/pip.conf` is probably vestigial anyway since the image installs via `uv`, which doesn't read pip config — verify/drop while in there. WB8's Cortex-A5x could in principle run the armv7 image via AArch32 compat, but native arm64 is the clean path at ~6 lines of diff. **Verification:** QEMU build smoke in CI; real run gated on actual WB8 hardware (hence `[later]`).


- [ ] **OPS-14** `[P2]` `[deferred]` — **Adopt the shared logging package from
  `locveil-commons/packages/core-py`, replacing the OPS-12 local implementation** (INTAKE — filed
  uncommitted 2026-07-08, joint productization session; verify before accepting). OPS-12's scheme
  (startup rollover `service.log.<stamp>.log`, midnight rotation, 30-day prune) was hand-ported to the
  voice repo as their BUG-30 — two copies by design review. The voice side designs the extracted
  surface (their ARCH-43; this repo's VWB-28 evidence-glob compatibility is input to that design);
  this task swaps the local implementation for the package. Gated on the commons restructuring (voice
  BUILD-21) + ARCH-43. Design: `docs/design/productization_bridge.md` §2, shared spec D-8.

- [ ] **OPS-15** `[P2]` `[deferred]` — **Ops-spec conformance pass** (INTAKE — filed uncommitted
  2026-07-08, joint productization session; verify before accepting). Once the normative ops spec
  exists in `locveil-commons/process/` (shared spec D-12 — largely codifying THIS repo's REL-2 layout
  as the reference pattern): walk `ops/` (update.sh shape, INSTALL.md structure, unit file, retention
  constants, naming) against the conformance checklist; fix dialects or record deliberate deviations
  in the spec. Sibling of the voice repo's narrowed BUILD-18. Design:
  `docs/design/productization_bridge.md` §2.

- [ ] **OPS-18** `[P2]` `[deferred]` — **Startup-failure cleanup omits WB-card offline marking (asymmetric with normal shutdown)** (REL-5 #11). `app/bootstrap.py:184` — `_release_partial_startup` doesn't call `cleanup_wb_device_state`, so a partial-startup failure leaves retained `available=1` on the WB cards. Edge path (only when startup fails midway); completes the OPS-8 shutdown-symmetry.

- [ ] **OPS-19** `[P2]` `[deferred]` — **`pyatv` git source is unmirrored — a dependency-policy Rule 2 compliance gap (policy home since DOC-15: `CONTRIBUTING.md` → Dependency policy; ex-ADR 0006, archived).** Surfaced by the REL-4 ADR review. `pyatv` is pinned to `git+https://github.com/postlund/pyatv@9177803…` — SHA-pinned (immutable, so the build is reproducible today) but **not** mirrored under the owner's account, which the policy's Rule 2 requires for repos the owner doesn't control; the old ADR's "only remaining git source" claim was already annotated false 2026-07-10. Residual risk: an upstream force-push/deletion of `postlund/pyatv` breaks recovery. **Decision + small op:** either mirror `postlund/pyatv` → `droman42/pyatv` and repoint the pin (comply), OR record an accepted exception in the CONTRIBUTING dependency-policy section with rationale. Not a release gate (reproducible now). Minor sibling: the dev-only `py-dev-gates@v0.1.1` is tag-pinned (owner-controlled) — fold in or leave.

- [ ] **OPS-28** `[P2]` `[deferred]` — **PROD-19 twin: public-issue intake posture — one door,
  locveil-reports** (filed at PROD-19 intake 2026-07-14; the board's HK-7 finding was that voice
  BUILD-14's "the bridge repo has the same question" claim had no bridge task behind it — this is
  that task). **Reconciled bridge reality (lighter than voice's):** the bridge carries NO pre-board
  intake machinery — no `.github/ISSUE_TEMPLATE/`, no triage workflow (`.github/workflows/` =
  `build-arm.yml` only), no docs pointing users at GitHub issues, zero issues ever filed — but the
  public repo's **Issues tab is enabled bare**: an unwatched side door, and (locveil-reports being
  private) the only intake channel a public visitor can see. **Scope:** decide the posture WITH
  voice BUILD-14 (one decision, two repos): (a) a forwarding workflow mirroring public issues into
  the reports-repo triage (leak fence: public→private mirroring is safe in that direction only) ·
  (b) lightweight issue templates that redirect, no automation · (c) disable the Issues tab. Apply
  the bridge side; any reports-repo workflow change is committed there (`cross-repo-source-of-truth`).
  Docs at execution: neither the README nor `docs/design/problem_reports_bridge.md` says anything
  about public intake today — record the chosen posture wherever it lands. Refs: board PROD-19,
  voice BUILD-14, `docs/design/problem_reports_bridge.md`.

- [ ] **OPS-29** `[P2]` — **Forensic logging middle ground: the load-bearing eMotiva transitions
  must survive INFO** (wedge #3 finding 5 —
  [`docs/review/emotiva_wedge_20260714.md`](review/emotiva_wedge_20260714.md)). OPS-25's hygiene is
  right, but it blinded the exact evidence the wedge forensics need: with `pymotivaxmc2` at WARNING
  and root at INFO, the uncommanded `source → arc` claim (the trigger condition the DRV-38 readiness
  gate keys on) and all property transitions are invisible. Scope: log **uncommanded source/input
  changes** and main/zone2 **power transitions** at INFO in the driver (rare events — a handful of
  lines per scenario, no volume risk; keepAlive stays silent); document the deliberate flip-on
  procedure for full UDP forensics (root DEBUG + unpin `pymotivaxmc2`) in the ops notes. Docs check
  at completion: manifest has no logging node — verify.

### CORE — Backend core / architecture

- [ ] **CORE-1** `[P2]` `[deferred]` `HW-GATED` — **System-router adapter cleanup — Item A only (Item B DONE 2026-05-26).** Item A: `POST /reload`'s `reload_system_task` constructs + drives a concrete `MQTTClient` inline; extract an application-layer reload service (e.g. `app/reload_service.py`) so the router stays a thin adapter. **Gated on hardware** — touches the live MQTT-reconnect path; can't be safely HW-verified without you at the rack. **Completion goal = 100% clean hexagon (explicit, added 2026-07-07):** this task owns the **only** `ignore_imports` exception in the import-linter config (`presentation.api.routers.system -> infrastructure.mqtt.client`, backend `pyproject.toml`); done means (1) the reload service extracted and the back-edge gone from the code, (2) the **`ignore_imports` entry deleted** — the contract set (6 since CORE-6) passes with **zero exceptions**, (3) the "one documented exception" passages updated in `docs/architecture/overview.md` + the contract name/comment in `pyproject.toml` + the [[hexagonal-layering]] memory, (4) HW-verified at the rack: `POST /reload` still reconnects cleanly against the live broker. Item B (response DTO for `/config/system`) done in `73ee8d5` — new presentation `SystemConfigResponse` + nested DTOs; wire shape field-identical; `presentation/api/schemas.py` no longer imports the infra `SystemConfig`.

- [ ] **CORE-4** `[P2]` `[deferred]` — **Full `POST /devices/{id}/action` demotion (release-2 candidate).** Decided at the release-1 sign-off (2026-07-06): `/action` ships in release 1 **as the documented internal/dev + UI-fallback door, untouched** — UI-9 removed its last first-party writer, but demoting it before the canonical hardware passes (REL-3, VWB-13) prove coverage would remove the safety net exactly when it might be needed. Post-release scope: strip the UI's un-annotated-control fallback dispatch paths, mark the endpoint internal in the OpenAPI docs (or move it under an internal prefix), and re-examine `/scenario/switch`+`/scenario/shutdown` internalization (the rest of `canonical_first.md` §8 phase 3) in the same pass.

- [ ] **CORE-5** `[P2]` `[deferred]` — **Resurrect the `device-test` CLI (stale ~1 year) + settle the
  `tests/device_test.py` squatter.** Reviewed 2026-07-07 on user request. The tool
  (`cli/device_test.py`, console script `device-test`, in the hexagon diagram) is the interactive
  per-device walk — exactly the DRV-1 shape: pick a device, fire actions, see state after each. It
  still imports clean and the entry point resolves, but it mirrors a **year-old bootstrap** (last real
  touch pre-monorepo `f187b96`; only mechanical typing/rename edits since). Verified gaps vs. the
  current composition root:
  (1) **no `StateRepositoryPort`** — `DeviceManager()` bare, so devices never re-hydrate persisted
  state before `setup()`; idempotence guards and assumed state behave unlike the real bridge, and the
  tool commands live gear from factory-default state;
  (2) **no `attach_capability_maps`** — capability-driven surfaces absent (DRV-5's `force` exposure
  won't render);
  (3) **private-attr wiring** — pokes `device_manager._mqtt_client` + casts `DevicePort`→`BaseDevice`,
  copying an old bootstrap shape instead of sharing it;
  (4) legacy disconnect→`connect_and_subscribe` re-connect dance;
  (5) result printing still handles the pre-`CommandResponse` nested-`result` shape.
  **Resurrection decision to make first:** (a) re-wire by **extracting a shared fleet-composition
  helper** from `app/bootstrap.py` (CLI and app can't drift again — hexagonally the cleanest), vs.
  (b) **retarget as a thin REST client of the running bridge** — which is what the *other* stale
  artifact already is: `backend/tests/device_test.py` (798 lines, drives a live service via
  REST/MQTT) squats in `tests/` matching pytest's `*_test.py` collection pattern (collects nothing,
  but misplaced) — fold or delete it in the same pass. Align with `eval/README.md`'s note that
  `device-test <id> <command>` is a wanted future eval CLI surface (needs MQTT). Post-release: the
  DRV-1/SCN rack passes run off the UI + eval suite; this tool is a developer convenience, not a gate.

- [ ] **CORE-7** `[P2]` `[deferred]` — **Adopt the shared dynamic code loader from
  `locveil-commons/packages/core-py`** (INTAKE — filed uncommitted 2026-07-08, joint productization
  session; verify before accepting). The user wants the voice repo's loader pattern for the bridge
  (driver/module loading). Gated on the voice-side extraction design (their ARCH-42) + the core-py
  package existing (voice BUILD-21). At task start: reconcile against the bridge's actual loading
  needs (driver classes are wired via config `class` names today) and verify the extracted surface
  fits the hexagon — loader = infrastructure concern behind a port, no new cross-layer imports
  (`hexagonal-architecture`). Design: `docs/design/productization_bridge.md` §2, shared spec D-8.

- [ ] **CORE-8** `[P1]` `[deferred]` — **Broker/device secret handling — out of config, off the wire, out of the logs** (REL-5 #1 (P0), #4/#5, #9, #12; `docs/review/rel5_pretag_review.md`). **Deferred to productization by user decision 2026-07-09** — proper secrets management + any API auth is product-shaped, and the house is on a trusted LAN. Scope: **(#1)** drop `auth` from `system.json` (env-only) and mask/drop `auth` in the `/config/system` + `/system` presentation DTOs (`system.py`, reuse `redact_mapping`) — today the broker password is served unauthenticated on the LAN; **(#12)** FIX the dead `_apply_environment_variables` (`config/manager.py:289` — `MQTT_BROKER_HOST/USERNAME/PASSWORD` overrides never take effect, which also unblocks the env-only path above); **(#4/#5)** stop logging the raw `broker_config` (`mqtt/client.py:18`); **(#9)** stop logging the LG WebOS `client_key` (`lg_tv/driver.py:904`). NB: rotating the currently-committed broker password is a separate near-term user op (the value is in git history) — recommended regardless of when this code work lands.

- [ ] **CORE-12** `[P1]` — **Staged-write API for repo-owned config — implementation** (filed at UI-17
  completion, `design-then-implement`; design:
  [`docs/design/ui/workbench_split.md`](design/ui/workbench_split.md) §3; write model normative home:
  board PROD-4 item 4). One envelope per target under `data/staged-config/` (`{target, base_sha256,
  content, staged_at, note}`); `GET /staged` · `GET/PUT/DELETE /staged/{target}`; **stage-time
  validation = overlay on the live tree + the existing load-time validation** (Pydantic models +
  topology/scenario structural checks, 422 on failure); stale base (`base_sha256` ≠ live) surfaces as
  conflict, never merges; self-cleaning when the live hash equals the proposal hash (promotion
  landed); promotion itself is a human commit + `update.sh`, no endpoint. Hexagonal placement: thin
  presentation router → app-layer staging service (bootstrap-wired) → infrastructure staged-store
  adapter; **zero new import-linter exceptions**. **HARD GATE (binding condition, board PROD-24/PROD-4):
  the endpoints must be unreachable until PROD-4's auth decision lands** — code may land behind a
  disabled feature flag, reachability may not. OpenAPI/`contracts/` regen + UI types ride whichever
  change first exposes the schema.

### LIB — pymotivaxmc2 library (sibling repo)

Fixes to the owner-maintained **`../pymotivaxmc2`** library (PyPI, pinned `==0.7.0` in
`backend/pyproject.toml`), filed off the wedge-#3 review
([`docs/review/emotiva_wedge_20260714.md`](review/emotiva_wedge_20260714.md) Finding 2). The bridge
ledger **tracks** these; the code lands in the sibling repo (its own commits/tests/release), and each
fix arrives here as a **pin bump** — a deliberate version decision, i.e. a normal task, not the
lockfile carve-out. Mirror-image of `cross-repo-source-of-truth`: here the bridge is the consumer.

- [ ] **LIB-1** `[P1]` — **controlPort reply correlation — kill the shared-queue cross-talk.** All
  control transactions read one unkeyed `asyncio.Queue` per port (`socket_mgr.py:106-113`) and acks
  are never matched to requests (`protocol.py:63`, tag-only check), while `Semaphore(5)`
  (`protocol.py:28`) permits 5 concurrent transactions: coroutines steal each other's replies →
  false timeouts → silent retries. **Observed in production** (wedge #3, 08:08:18.121: `Unexpected
  response tag: emotivaUpdate (expected 'emotivaSubscription')`). Fix shape: route replies to their
  transaction (match on tag + requested property set; or a dispatcher that fans control-port frames
  to per-transaction futures); a mismatched frame must never be consumed-and-dropped by the wrong
  waiter. Release + bridge pin bump.

- [ ] **LIB-2** `[P1]` — **Retry-storm damping + command pacing.** Every control call silently
  retries up to 3× (`send_command` `protocol.py:45-97`, `subscribe` `:218-296`,
  `request_properties_full` `:130-205` — the last re-sends the WHOLE property batch when any
  property is missing). The library's own `docs/emotiva_lib_fixes.md` names "device stuck under
  command floods" as this unit's failure mode — the retry machinery is the amplifier (wedge #3:
  the power-on status batch retried into the booting unit). Fix shape: make retries visible +
  configurable per call (callers like a readiness-sensitive driver need retry=0), re-request only
  the *missing* properties on batch retry, and offer an optional global min-inter-packet pacing
  knob. Also (owner Q&A 2026-07-15, review annotation #2): the library forces `ack="yes"` on every
  command (`xmlcodec.py:38-40`) though the spec makes it optional — expose `ack="no"` as a per-call
  option, since the always-awaited ack is the retry-ladder entry point exactly when the device is
  busy/fragile. Release + bridge pin bump; the driver's power-on tail (DRV-39) consumes the retry=0 option
  if it keeps any post-power-on query.

- [ ] **LIB-3** `[P2]` `[deferred]` — **API + hygiene batch.** (1) Public accessor for the
  transponder's `keepAlive` interval — parsed then dropped today (`discovery.py:147-149`); the
  bridge driver reads private `_info` via getattr. (2) Real unsubscribe on `disconnect()` — the
  current empty `<emotivaUnsubscribe>` (`controller.py:153`, `xmlcodec.py:80-92`) is a no-op per
  spec §2.1.5 ("each notification property must be unsubscribed explicitly"); requires tracking the
  subscribed set. (3) `SO_REUSEADDR` on the fixed 7002/7003 binds (`socket_mgr.py:64-67`) — rapid
  disconnect→connect risks `address already in use`. (4) Surface notification **sequence numbers**
  (spec §2.6, v2.0+) so consumers can detect missed notifications instead of blind full refreshes.
  One release; bridge pin bump + driver cleanup of the `_info` getattr.

**The ledger & documentation reconciliation series (DOC-4…DOC-10).** Filed 2026-06-30 from two
chat-requested analyses: (1) a comparison of this plan's former positional `P0…P4 / #n` numbering
against the sister repo's workstream-serial ledger (`../locveil-voice/docs/RELEASE_PLAN.md` + frozen
`RELEASE_PLAN_DONE.md`), and (2) a read of the four scenario/Layer-3 design docs that doubled as
ledgers. Both surfaced the same thing: design/planning docs accreted a *done* ledger half that
diluted their reference half. The series executes the **handover §0 promises** ("the redesign specs
fully retire to history… a project-wide doc reconciliation formalizes the handover"). **The series is
complete:** DOC-5 (design gate) · DOC-6 (two-file split) · DOC-8 (archive the survey) · DOC-9 (re-ID) ·
DOC-10 (retire the scenario/Layer-3 ledgers) · DOC-4 (the `scripts/check_scope.py` scope-drift guard) —
all done; DOC-7 folded into DOC-9.

- ~~**DOC-7**~~ — *adopt additive conventions; folded into DOC-9 (the legend/tags/priority-split land in the re-ID pass).*

### DOC — Docs / ledger / process

- ~~**DOC-11**~~ — *reconcile `docs/architecture/ui.md` with canonical-first dispatch; **folded into REL-4** at the release-1 sign-off (2026-07-06, DOC-7→DOC-9 precedent). The finding: the "Scenario manifests — same shape, different routing" section still describes pre-SCN-6 dispatch (controls posted at role devices; since SCN-6 they dispatch through the room's Scenario Manager entity) and claims the `source` device contributes an input-dropdown (scenario manifests deliberately render no inputs control); canonical dispatch as the UI's only write path is explained nowhere.*

- [ ] **DOC-17** `[P2]` `[deferred]` — **Planned-pages + diagram staleness reconcile** (discovered
  during UI-17's planned-docs pass 2026-07-14 — pre-existing, distinct from the UI-17 edits, filed
  per the discovered-staleness rule). The four `docs/planned/` pages carry status tables/prose that
  predate recent landings — spot-verified: voice-setup lists the value-label translation layer
  ("#26") as *Not built* (DONE 2026-06-09) and its §P3.7 tail statuses need a sweep; appliance-pages
  lists `HvacPanel.tsx` as *Not built* (shipped with DRV-28/UI-16). Sweep all four pages' "Where the
  parts already live in code" tables + status headers against the current tree. Fold in: every
  diagram title under `docs/images/*.dot` still says "wb-mqtt-bridge" (rename era) — retitle to
  `locveil-bridge` in one pass and regenerate the PNGs in the existing visual style. Pure docs; not
  release-gated.

### REL — Release

*(All `[release]` REL tasks complete — see `docs/action_plan_DONE.md`. The only open `[release]`
task anywhere is VWB-16, gated on voice TEST-18 fixtures, off the critical path.)*


---

## Acceptance gate (house-works completion checklist — ex-P4 #1–#5)

> **ABSORBED into the "Definition of release 1" (2026-07-06, REL-1):** items 1–3 are
> satisfied/rolling as annotated below; item 4's review half + item 5 ride **REL-3**; the list
> is kept as the detailed checklist REL-3's gate pass walks.

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

## Open questions — **CLOSED 2026-07-06 (REL-1 session; kept as the answered record)**

*All seven survey-era questions (2026-05-20) were resolved at the release-1 sign-off — six by
events, one by decision. New open questions go to the ledger as tasks, not here.*

- [x] **ARMv7/Wirenboard exclusively, or a dev path on amd64 too?** — **DECIDED (REL-1):** release 1 targets **armv7/WB7 exclusively**; amd64 stays a native-dev convenience (`uv run`, no image); other platforms (arm64 for next-gen WB, an amd64 image) are release-2 scope (OPS-11).
- [x] **WB-only deployment, or a separate Linux box over MQTT?** — **Answered by events:** the `ops/` compose cutover to the WB7 controller is the plan of record (`ops/INSTALL.md`, now REL-2); the dev box serving the house is a recorded debt, not a target.
- [x] **One repo or two?** — **Answered by events:** monorepo, merged 2026-06 (the old UI repo is archived); the OpenAPI contract survived as the internal seam (`config-ui-stays-functional`).
- [x] **Unshipped planned drivers?** — **Answered by events:** all carry ledger IDs — DRV-2 (Apple TV app launching, `[release]`), DRV-3 (IR learning page, `[deferred]`), DRV-8 (Roborock design, `[deferred]`); Miele + SprutHub dropped 2026-05-20.
- [x] **Will `device_category` drive real behavior?** — **Answered by events:** it already does — the UI splits devices vs appliances in navigation on it (`useRoomStore`, `HomePage`); the enum ships.
- [x] **Runtime-driven UI rendering (Option 2)?** — **Answered by events:** shipped as the Layer-3 backend layout manifest + `RuntimeDevicePage` (the 2026-05-24 cutover); build-time codegen is retired.
- [x] **Explicit placement contract?** — **Answered by events:** the backend-owned layout manifest IS the placement contract (subsumed UI-7); zones follow capability-declaration order, slot zones are engine-assigned.
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
