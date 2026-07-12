# Action Plan — Journal
> Older sections: docs/archive/journal/2026-06-09_2026-07-04.md

**Status:** Living dated record of work done on the wb-mqtt-bridge monorepo. Extracted from
`docs/action_plan.md` §6 on 2026-06-06 — the plan was growing too quickly and the dated
history is intrinsically append-only, so it lives on its own from here. **Newest entries on
top.** References elsewhere in the plan ("see §6 (2026-05-25)" etc.) remain valid and now
point at the dated entry below.

`docs/action_plan.md` stays the master driving document (forward work + an index of recent
journal entries in §6). This file is the long tail.

**Archive pointer:** entries older than 2026-07-05 are frozen in
[`docs/archive/journal/`](archive/journal/) — newest archive
[`2026-06-09_2026-07-04.md`](archive/journal/2026-06-09_2026-07-04.md) (second rotation
2026-07-11, the first via `scope_guard.py --rotate`), oldest
[`2026-05-23_2026-06-08.md`](archive/journal/2026-05-23_2026-06-08.md) (first rotation
2026-07-06, manual). Per the `one-active-journal` high-water rule; append-only, grep when a
`task-start-reconciliation` trail points there.

---

**Note on IDs (2026-06-30):** the ledger was re-IDed to the `PREFIX-N` workstream scheme (DOC-9). This
journal's **earlier dated entries keep their original positional refs** (`§P3.7 #19`, `§5.1 #7`, `P4 #7`,
etc.) — they are historical and resolve via [`action_plan_aliases.md`](action_plan_aliases.md). New
entries use the new IDs.

- **2026-07-12 — PROD-15 bridge delegation pulled: satellite-boundary tasks filed (DRV-34/35/36 + VWB-38/39).**
  Board-as-outbox intake (council HK-4, locveil-satellite bootstrap; board entry PROD-15 in
  `../locveil-commons/board/BOARD.md`). All five delegation items verified against the repo at intake
  (`task-start-reconciliation`) — all valid: the `ESP32/` tree + DRV-7 + the ESP32ManagedDevice
  narrative + the `productization_bridge.md` §3 "no bridge work filed" note + the VWB-37 pin pattern
  are exactly as the delegation claims. Two reconciliation notes: the delegation's "§5.1 area" pointer
  is old positional numbering — the superseded text actually lives in the VWB context narrative (plus
  a stale "§5" back-pointer inside DRV-7); and the board says the HVACs run **ESP8266** while the plan
  says **ESP32** — discrepancy parked into DRV-34 to resolve at execution. Filed 1:1 with the
  delegation: **DRV-34** (HK-4 supersession doc pass — items 1a+5 folded, both dated-annotation work),
  **DRV-35** (DELETE `ESP32/` + retire DRV-7; BLOCKED on satellite import confirmation — item 1b),
  **DRV-36** (EspManagedDevice driver design — item 3), **VWB-38** (device-integration-convention
  design — item 2; owner: separate session), **VWB-39** (descriptor-pin conformance test, VWB-37
  pattern — item 4). Per-deck cutover tasks stay unfiled until satellite first-light, per the board.
  IDs written back into the PROD-15 board entry (commons commit).

- **2026-07-11 — VWB-35: reports-repo re-point complete — spool drained (trivially), the task closes.**
  Board-as-outbox delegation (PROD-14 phase 2 (1), council HK-3); implementation had landed
  (`0279ade` + `7f37dae`: slug sweep, explicit `reports.repo`, schema default dropped with the
  fail-fast validator, regen chain, guide re-truthed) with the completion held on the one owner
  check — the agent's SSH to the controller is permission-blocked by design. Owner verified:
  `/mnt/data/locveil-bridge-config/data/` has **no `reports/` subdirectory** — the spool dir is
  lazily created on first spool (`_spool` mkdir; `retry_spooled` handles absence), so nothing was
  ever spooled = trivially drained, consistent with the phase-1 live smoke delivering directly.
  All four scope items verified → completion triad. Suite 704, golden unchanged.

- **2026-07-11 — VWB-36: lens-bridge.md re-reviewed — triage now knows the protocol pin.**
  Board-as-outbox delegation (PROD-14 phase 2 (2); the VWB-26 co-ownership pattern; the board's
  pre-named VWB-30 was stale — serial already consumed — re-serialed at intake). All existing
  lens claims verified true against the live repo (test paths, gates, `$CROSS_REPO_TOKEN`,
  ping-pong guard; slugs already clean from the phase-0 sweep); one addition landed on the
  reports repo (`locveil-reports@6a5dc62`): §2 teaches the protocol-pinned filing surface
  (VWB-37's pin + conformance test — wire-surface changes start with a commons re-pin, never
  bridge-side) and the explicit no-default `reports.repo` (VWB-35). No bridge code touched.

- **2026-07-11 — VWB-37: report-protocol-v1 consumed — the filing surface is pin-validated now.**
  Board-as-outbox delegation (PROD-14 phase 2 (3) / PROD-6, council HK-3), filed + executed same
  session alongside VWB-35/36. The commons machine core pinned byte-identical at the repo root
  (`report-protocol.pin.json`, tag verified before copy — the reports repo's pin convention);
  the `service.py` filing hardcodes (labels, `[bridge-ui]` prefix, bundle name, id source token)
  retired into `REPORT_*` constants; `test_report_protocol_pin.py` (5 tests) locks constants → pin,
  including `system.json` `reports.repo` == `repos.reports` (chains the VWB-35 cutover value to the
  protocol; the emitted-value half was already locked by the envelope test). Suite 704, pyright 0,
  import-linter 6/6, no contract change. Protocol bumps: re-pin first, adjust until conformance
  passes.

- **2026-07-11 — OPS-16: CLAUDE.md harmonization — the shared process layer is pinned blocks now
  (scope-v3).** Third board-as-outbox delegation (PROD-5 / HK-2), pre-assigned this ID with a REDEFINE
  flag — reconciliation confirmed the old text stale on three counts (`check_scope.py` gone with
  OPS-22; the separate-drift-guard-script plan dead — HK-2 put a `claudemd` hash rule INSIDE
  scope-guard; the split-in-two rename superseded by rename-apart) — owner approved the redefine
  before execution. Landed: both digest blocks (`shared-invariants`, `cross-repo-board`) inserted
  byte-identical between `locveil:begin/end` markers; the ~55 lines of duplicated long-form
  ledger/rotation/guard mechanics they replace came out, shared invariants now carry dialect-only
  bullets — CLAUDE.md 175 → 164 lines (the HK-2 hard criterion: adoption must not grow the file).
  Preamble de-lied (the "single source of truth = this file" claim was false since HK-1); the retired
  uncommitted-intake clause in `cross-repo-source-of-truth` replaced with board-as-outbox vs
  direct-operational-filing (and commons acknowledged as co-owned ground — the old "never write into
  `locveil-commons`" wording contradicted the board convention). **`config-master-canonical` →
  `config-master-tree`** (HK-2 rename-apart; frozen design-doc mention annotated, not rewritten).
  Guard re-pinned at **scope-v3** (1.1.0): `[claude]` hashes match commons' pins exactly; tamper test
  fails correctly (CLAUDE-BLOCK drift, exit 1); CLAUDE.md added to the CI `ledger` paths-filter. The
  board block closes the "sessions search for the board process" gap HK-2 named. Consumption noted on
  the board journal; PROD-5 stays `[>]` until voice's BUILD-23 lands.

- **2026-07-11 — OPS-22: scope-guard cutover — the commons ledger guard is the law here now; found +
  fixed a v1 rotation bug upstream (scope-v2).** Second board-as-outbox delegation consumed (PROD-13 /
  HK-1, verified at intake: tool + starter config green on this tree, tag matched HEAD, retirement
  targets where claimed). Cutover: `scripts/scope_guard.py` vendored + `.scope-guard.toml` (aliases +
  tombstones ON), old `check_scope.py` deleted only after the vendored tool proved green, CI
  `ledger-guard` + paths-filter re-pointed, committed pre-commit hook live (`core.hooksPath hooks` —
  every commit in this session passed through it), CLAUDE.md invariants updated (scope-guard as
  enforcer; DONE-ledger rotation rule new: 3000/2000/4000). **The first real `--rotate journal` run
  caught a scope-v1 defect**: archives written character-per-line AND the kept journal silently
  truncated (`rotate_journal` double-indexed the day-lines list after tuple unpacking — `s[1]` on an
  already-unpacked list, so `join` iterated a string). No history lost (git restore). Fixed in commons
  per the convention (never patch the vendored copy), validated on a copy of this tree with a
  line-by-line diff (zero loss), tagged **scope-v2** = 1.0.1 — also adds the explicit `--check` flag
  the docs promised but v1 lacked. Re-pinned here at v2; rotation then executed for real as its own
  commit: 1625 → 990 lines, 6 day-sections (2026-06-09…07-04) frozen to `docs/archive/journal/`.
  Board: OPS-22 written back into PROD-13; both delegations re-pointed at scope-v2 — **voice must pin
  v2**, its own overdue rotation would have hit the identical bug. Guard fully green post-rotation.

- **2026-07-11 — OPS-21 controller cutover CONFIRMED on hardware.** Owner flipped the new GHCR packages
  public (org-policy fix: allow public package creation) and ran `ops/migrate-to-locveil.sh` on the WB7:
  migration successful — `locveil-bridge` + `locveil-bridge-ui` running from
  `/mnt/data/locveil-bridge-config` under `locveil-bridge.service`. No wb-mqtt naming left on the box
  (the WB system services `wb-mqtt-serial`/`wb-rules` are Wirenboard's own, not ours).

- **2026-07-11 — OPS-21: deployment identity renamed — after the migration script runs, nothing on the
  controller says wb-mqtt.** Second act of the rename day, coordinated with voice BUILD-29 (owner call:
  finish the re-pointing down to the metal). Images → `locveil-bridge` + `locveil-bridge-ui`, containers,
  unit (`locveil-bridge.service`), runtime tree (`/mnt/data/locveil-bridge-config`), clone path, INSTALL
  flow, and the Python distribution (`locveil-bridge`, alias script renamed, `wb-api` + import package
  kept). New `ops/migrate-to-locveil.sh` performs the one-time controller cutover (old unit out → tree mv
  with state/.env intact → update.sh under the new identity → new unit in → old images dropped).
  Sequencing for the owner: dispatch one CI publish, flip the two new GHCR packages public, THEN run the
  migration script on the WB7 (both repos' scripts, either order). Backend suite 698 on the renamed
  distribution; eval cli 4/4; check_scope green.

- **2026-07-11 — OPS-20: the repo is `locveil-bridge` now — first board-as-outbox delegation consumed;
  OPS-21 filed.** The Locveil productization arc reached this repo: name locked (**Locveil**), org
  `locveil`, all three repos + local dirs renamed, commons restructured (`locveil-commons@52126da`,
  board live). The delegation was pulled from `locveil-commons/board/BOARD.md` PROD-2 (the mechanism
  D-5 designed — this retires the uncommitted-filing pattern that VWB-29/CORE-7/OPS-14/15/16 used as
  its deliberate last case), verified against live code, filed as OPS-20, executed: eval re-point to
  `../../locveil-commons/eval` (cli 4/4), `backend/.venv` rebuilt (the dir rename had bricked every
  console-script shebang — the voice session hit the identical failure), operative name sweep,
  `domovoy`→`locveil` container user (inert until the next image rebuild), GHCR pull refs →
  `ghcr.io/locveil/*` (**owner: run one CI publish before the next controller `update.sh`**, or the
  compose pull 404s). Deployment identity (image basenames, container/unit names, controller paths,
  the `wb-mqtt-bridge` distribution name) deliberately unchanged → OPS-21, to be coordinated with
  voice BUILD-29. Backend suite 698 passed post-rebuild; `check_scope.py` green; OPS-20 written back
  to the board (PROD-2 closes).

- **2026-07-10 — RELEASE 1 CUT: v0.6.0. VWB-16 → `[deferred]`; every `[release]` task now closed.** —
  the owner's call at the tag: VWB-16 (the voice-crossover consumer contract test) waits on the voice
  repo's TEST-18 fixtures, so it moved `[release]` → `[deferred]` — release 1 doesn't hang on a sibling
  repo (it lands whenever the fixtures do; golden `5622ba7a` is stable). With that, **every `[release]`
  task is `[x]`** and the scope gate is clean. Version bumped **0.5.0 → 0.6.0** across all nine
  touch-points (pyproject, `__version__.py`, uv.lock, ui/package.json, README, openapi ×2, STAMP,
  ui types); golden catalog unchanged (version-independent → no voice re-pin). Annotated tag **`v0.6.0`
  — "the house runs on the controller"** cut on the release commit. Structure mirrors the voice repo
  (0.x pre-1.0, annotated descriptive tag). The bridge's first real release since the year-old,
  pre-transformation `v0.5.0` — 651 commits of hexagonal rebuild, canonical-first, scenarios, the
  HVAC driver, and WB7 production deployment.

- **2026-07-10 — REL-4 DONE (the release docs pass — the last critical-path gate before the tag)** —
  user-facing docs made true at the release version, in the voice project's spirit, and scrubbed of
  ALL internal tracking language. Scope reconciled with the owner mid-task: the master-doc/governance
  half descoped to the board (with VWB-33/34); `project.md` archived (not user-facing); `docs/planned/*`
  ruled not-user-facing (excluded, and user-facing docs no longer link into them). Method: a four-way
  parallel doc audit against reality (architecture/guides/READMEs/ADRs) — 8 accurate, 11 fixed. Fixed
  the driver count (8→9), canonical-first framing (`/canonical` public, `/action` internal), DOC-11
  (ui.md scenario-manifest → render-projection-over-Scenario-Manager), the deployed/HVAC/reports status
  in the READMEs, contracts realism-check; added `docs/QUICKSTART.md` (safe-by-construction tester
  guide); amended ADR 0006 + filed OPS-19 (unmirrored pyatv git source); regenerated the 2 stale
  diagrams (canonical write path). A hard lesson mid-pass, owner-flagged twice: **user-facing docs must
  NEVER carry task IDs / `§P3.7` refs / plan pointers** — I'd leaked three into ui.md; the final sweep
  verifies the whole set clean. No code, no contract change. Board: **only VWB-16 (voice fixtures,
  off critical path) now stands between here and the tag.**

- **2026-07-10 — VWB-33 re-tagged `[release]` → `[deferred]` (owner: doesn't belong in release 1)** —
  at the start of the VWB-33 design session (scope/plan explained; reconciliation confirmed the
  analysis — labels are en/ru fleet-wide except HVAC's de/en/ru, aliases ru-only 35/78, names carry
  de on 65/78), the owner stopped it: the language-data convention is **half the voice side's** (the
  verbs-are-donations rule binds their repo), so it's a **board-level cross-repo design session** —
  one of the first tasks after the Domovoy board is established, sibling to VWB-34. Not a release-1
  gate. Effect on the board: **REL-4 is now the SOLE remaining `[release]` gate before the tag**
  (VWB-16 waits on voice TEST-18 fixtures, off the critical path). Critical path collapses to
  **REL-4 → tag**.

- **2026-07-10 — REL-3 DONE (the converged rack pass — two sittings, one critical bug found and
  killed, house verified)** — closed on owner confirmation that the SCN-11 dialog reads in sync after
  the SCN-15 redeploy. Two sittings the same day: #1 flagged the eMotiva ARC-window wedge (the
  headline finding the whole mock-tested suite structurally couldn't reach) → DRV-30 + SCN-14 shipped;
  #2 proved the wedge gesture now passes and closed its lone flag with DRV-33 + SCN-15. Verified live:
  bridge healthy + non-root + golden `5622ba7a1a78102a` byte-match, the full scenario lifecycle on
  hardware, the HVAC live pass, force/reconcile, mf_amplifier mute, end-to-end after cleanup, CI green.
  Deferred-not-gating items enumerated in the DONE entry; `tv_on_speakers` expected-fail until DRV-32.
  Five fixes were born and shipped from this one pass (DRV-30, SCN-14, DRV-33, SCN-15 + the DRV-31/32
  filings) — the rack paid for itself many times over. Only REL-4 (+ VWB-33) now stands before the tag.

- **2026-07-10 — SCN-15 DONE (all comparison sites unified on `_satisfies` — the DRV-33 flag's tail)** —
  post-DRV-33 the SCN-11 dialog still called the TV "out of sync" (`'HDMI_2'` vs `'hdmi2'`, owner
  screenshot): SCN-14 had canonicalized only the execution gate; the build_plan diffs and the
  preview's `in_sync` still compared raw. One shared `_satisfies()` (exact → value table →
  normalized) now serves the gate, all five diff sites, and both preview comparisons — the dialog
  reads honest wire-form state as in-sync and plans stop emitting phantom TV-input steps at the
  source. Fresh logs confirmed zero gate timeouts since the DRV-33 redeploy (the execution side was
  already clean). +2 tests (the screenshot case; diff already-satisfied across vocabularies). Full
  tree 698, pyright 0, 6/6.

- **2026-07-10 — REL-3 sitting #2: 21 ok · 1 flag · 11 not run — THE WEDGE GESTURE PASSED; the one
  flag root-caused and fixed same hour (DRV-33)** — START `movie_zappiti` with the TV already ON
  (yesterday's rack-killer) ran clean end-to-end; both switches executed against a live eMotiva for
  the first time; END + restart-survival green; force/reconcile station mostly green. The single
  flag (SCN-11 force on the TV showing believed input `Emotiva XMC` + a gate timeout) decoded from
  logs: the LG driver's optimistic input write stored the user-assigned input LABEL while the webOS
  event path writes the ID — with the TV already on target there's no correcting event, so the label
  stuck, every switch re-dispatched the TV input as a phantom diff, and SCN-14's honest gate
  faithfully reported the pre-existing lie (actuation itself always worked). One-line fix
  (`input_id` in the optimistic write) + pinned-behavior test corrected + an already-on-target
  regression. Full tree 696, pyright 0, 6/6. Remaining not-run items ride sitting #3 / owner triage.

- **2026-07-10 — DRV-30 DONE (eMotiva hardening: readiness gate + keepAlive watchdog + re-subscribe
  on recovery)** — the wedge class is closed at the driver, notification-driven throughout:
  `set_input` holds inside the post-power-on window (2 s quiescence normally; the **ARC-exit case
  holds the full 15 s** — design sharpened mid-implementation: the incident wedged 3.3 s of silence
  AFTER the `'arc'` claim, so quiescence alone is provably insufficient); `Property.KEEPALIVE`
  subscribed with the device-advertised 7500 ms interval — 3 missed beats → `connected=False` +
  speakable fail-fast on all six handlers (`force` bypasses) instead of blind 9 s retry burns; the
  recovery probe IS a re-subscribe (device-side subscriptions die with the device — the F4 deafness),
  ack re-seeds state. No new state field — contracts byte-identical. +9 tests; suite 595, pyright 0,
  6/6. Pre-release mandate complete (with SCN-14): scenario startup is safe as-if-ARC-worked; the
  ARC bench itself rides DRV-32 post-release.

- **2026-07-10 — SCN-14 DONE (reconciler gates: canonical comparison + timeout = failed step)** — the
  gate now translates the device's reported state through the capability's value table (carried on
  `PlannedAction`) with a normalized-comparison fallback for tableless drivers — the LG's
  `'HDMI_2'`/`'HDMI2'` finally satisfy a `'hdmi2'` target instead of burning 3 s per activation
  (F2, the gate had NEVER confirmed); and a `feedback:true` gate timeout is a **failed step** in the
  result (dispatched-and-acked stays in `executed`, unconfirmed lands in `failures`) — no more
  `tv_on_speakers` false successes (F3). Feedback-less steps stay optimistic. +4 gate tests; the
  force-endpoint fakes now reflect commands into state (honest gates correctly fail static fakes).
  Suite 586, pyright 0, 6/6; contracts untouched. `tv_on_speakers` now honestly fails until DRV-32.

- **2026-07-10 — REL-3 sitting #1: the eMotiva ARC-window wedge — investigated live, findings frozen,
  DRV-30/SCN-14 (P0) + DRV-31/DRV-32 filed** — the first rack pass (13 ok · 4 flagged · 14 not run)
  flagged a critical: START `movie_zappiti` with the TV already on wedged the XMC-2 hard
  (wall-unplug). Same-day forensics (owner-copied container logs + five controlled power-ups + a
  remote OSD probe over the protocol's menu system, `scripts/emotiva_menu_probe.py`): the bridge
  fired `set_input` **3.3 s into a CEC/ARC handshake its own state already showed**
  (`input_source='arc'` at power-on +0.4 s); the safety spacing between `processor.power` and
  `processor.input` was only ever accidental (edges collapse on a warm TV + the TV gate burns a
  dead 3 s — the gate compares canonical `'hdmi2'` to wire `'HDMI_2'` and has NEVER confirmed);
  `tv_on_speakers` reported success twice while ARC never engaged (gate timeout is advisory);
  the wedge+unplug also wiped the device-side subscriptions (bridge deaf until restart) AND
  **reset the XMC-2's CEC config to disabled** (panel read: Enable + Audio to TV off) — the
  afternoon's "ARC is dead" mystery. Evidence: `docs/review/rel3_rack_findings_2026-07-10.md`.
  Filed: **DRV-30** (readiness gate + keepAlive 7500 ms watchdog + re-subscribe on recovery,
  P0 release), **SCN-14** (gate canonicalization + timeout→failed-step, P0 release), DRV-31
  (Zappiti IR toggle miss, deferred), DRV-32 (CEC restoration + ARC bench, deferred HW-GATED —
  owner decision: post-release). REL-3 sitting #2 after the P0s land.

- **2026-07-10 — SCN-13 FILED; the two-room drill leaves REL-3 (user catch on the checklist)** —
  the REL-3 checklist still carried the SCN-6-owed two-room concurrency drill, but second-room
  scenarios went post-release at the 2026-07-04 SCN-4/SCN-6 amendment ("a future round") and the
  move never propagated into REL-3's entry or the release-definition item 2 — and every configured
  scenario is `living_room`, so the drill has nothing to run against. Fixed all three places:
  REL-3 entry + definition item 2 now point at SCN-13 (`[P2]` `[deferred]`: author the
  children-room set, then the concurrency drill SCN-6 recorded as owed); the rack-checklist
  artifact dropped the station (same URL). REL-3's HVAC line also refreshed — the DRV-26/28/29
  driver arc superseded the old VWB-14/24 read-path watch.

- **2026-07-10 — VWB-34 FILED (publish confirmation-timing in the contract — design, post-release)** —
  off the DRV-29 post-mortem: "your HTTP timeout must exceed 15 s" is contract information delivered
  out-of-band in a handover note — retune a gate and voice breaks silently again. Filed `[P2]`
  `[deferred]`, cross-repo, intended for board delegation once board-as-outbox lands (voice co-owns
  consumption; scenario startup as a durable action on the voice side is on the table). Three tiers
  sketched: per-capability `confirm_timeout_ms` (the latency promise, not the internal gate), scenario
  `max_duration_ms` as a derivable upper bound (diff-dependent duration means an estimate would lie;
  progress belongs to SSE), and the async-job pattern for composites as the design's open call.

- **2026-07-10 — DRV-29 DONE (voice-filed; canonical echo window honors the capability gate)** — the
  first DRV-28 live smoke («выключи кондиционер в детской») worked but 503'd: the flat 500 ms
  `CANONICAL_ECHO_TIMEOUT_S` vs the firmware's multi-second confirm rotation (~7 s observed). Fix:
  the endpoint now waits `cap.gate.poll_timeout_ms` when set (the per-capability timing the
  reconciler always honored; LgTv 8000 benefits too), else the 500 ms relay default. The 15 s HVAC
  window is DERIVED from the firmware source (1 s packet gate + 6×2 s info rotation ≈ 13 s worst
  case), not guessed — user requirement. Gates set on all six MitsubishiHvac capabilities. NO
  contract change (gates aren't catalog surface — no re-pin). +2 endpoint tests; suite 682, pyright
  0, 6/6. Voice's wait:true now speaks truth ~7 s late (their client timeout must exceed 15 s) or
  they opt into wait:false — their call. Backend-only rebuild owed.

- **2026-07-10 — VWB-32 DONE (retained catalog-version published at startup + on reconnect)** — the
  topic was `/reload`-only, so the persistence-less broker's restarts left it missing (voice's
  staleness gate blind). New generic `on_connect_callbacks` seam on `MQTTClient` (fires after each
  (re)connect's subscriptions, failure-isolated — the reusable home for wipe-surviving retained
  state); bootstrap registers the catalog-version publish + calls it once at boot; `/reload` publish
  kept. +2 tests (fires on connect + reconnect; raising callback isolated). Suite 680, pyright 0,
  6/6. Rides the pending image rebuild.

- **2026-07-10 — UI-16 DONE (enum-value icons via the shared IconResolver) — closed through a
  three-iteration ARTIFACT review** — a live review page (per-icon approve/alternate/comment + a
  general-instructions field; the user's exported review drove each next iteration, same URL
  republished). All 27 HVAC values settled: Material 1:1s (AcUnit/WaterDrop/WbSunny/Nightlight/
  arrows/SyncAlt), the custom number ladder for speeds+positions, the AV remotes' power pair, and
  FOUR new custom SVGs from the review: `auto-recycle` (♻-faithful chasing arrows), `swing-v`/`swing-h`
  (DETACHED-ray fans — the user rejected the joined pivot, matching ⚟'s implied convergence;
  orientation-aware pair), `center-bar` (the "keyboard |"). Color rule pinned: dry/cool/heat carry
  fixed colors (#42A5F5/#4FC3F7/#FFB300), everything else theme ink (currentColor). Code:
  `IconResolver.valueIconMappings` + `resolveValueIcon()` (scoped `capability.value` → bare fallback),
  4 custom components registered, `HvacPanel` glyph maps deleted → `ValueIcon` component. UI-only;
  check+build green; rides the pending DRV-28 image rebuild.

- **2026-07-10 — DRV-28 DONE (the `MitsubishiHvac` driver) — the ACs are bespoke devices** — the
  DRV-27 rev. 2 design implemented in one sitting: typed state + VWB-18 restore-at-boot (the
  broker-wipe fix), heartbeat reachability off the firmware's 45 s room_temperature publish (no LWT
  exists), canonical→numeric-wire commands via the attached class map through `idempotence_skip`,
  and — the user's hard requirement, twice-enforced and test-pinned — **never creates a WB virtual
  device** (the firmware owns its card). Translation stack extracted to the shared
  `value_translation` module (passthrough delegates; the `independence` contract stays clean, the new
  package added to it). Configs moved to `config/devices/` root (explicit commands, bare
  state_topics, `temperature`→`setpoint`); `profiles/hvac.json` deleted; `classes/MitsubishiHvac.json`
  = six capabilities. Catalog derivation extended: `set {value}` params inherit the state-field table
  (VWB-24's zero-round-trip property preserved under the new convention). HvacPanel reworked;
  device-state-mapping + OPENAPI_EXTRA_MODELS registered (user catch). **Golden → `5622ba7a1a78102a`,
  openapi +1 schema — voice re-pins ONCE (DRV-25+26+28), and their intent mapping must follow the new
  six-capability vocabulary, not just the hash.** Suite 678, pyright 0, 6/6, UI green, eval cli 4/4.
  Docs: devices-and-scenarios (nine drivers), README, howto-new-device. Owed: image rebuild + WB7
  redeploy; HW check rides REL-3.

- **2026-07-10 — DRV-27 DONE again (design rev. 2: six capabilities + explicit topics)** — the
  reopened discussion settled all three forks (user-pinned): **six per-domain capabilities**
  (power/mode/fan/vane/widevane/temperature — the AV action-group shape, 1:1 with the firmware's
  controls; `reconcile:false` explicit); **`{value}` param convention** on every enum/float `set`
  (mirrors VWB-19 select-form — one shape for voice); **today's config schema kept** (explicit
  per-action `commands` + bare `state_topics`, tables in the class map via the DRV-25 enrichment),
  the 3 configs moving out of `wb-devices/` to `config/devices/` root, driver validates completeness
  at load. Owned consequences: canonical HVAC vocabulary changes (golden bump, single voice re-pin
  after DRV-28) + `HvacPanel.tsx` rework. Design doc rewritten (rev. 2); DRV-28 amended to match.

- **2026-07-10 — DRV-27 REOPENED (design review: decomposition + explicit topics)** — the user read the
  design doc and rejected (1) the single `climate` capability — must decompose into per-domain action
  groups like LgTv/kitchen-hood/eMotiva, and (2) topic derivation from one `mqtt_device` field — device
  configs must carry explicit MQTT topics per action, and the 3 HVAC configs move out of `wb-devices/`
  to `config/devices/` root (bespoke home). Settled decisions stand (name, class-map-only tables, no WB
  card, UI-16 icons, heartbeat, restore). Discussion continues; DRV-28 amended on re-close.

- **2026-07-10 — DRV-27 DONE (design: `MitsubishiHvac` dedicated driver) + DRV-28/UI-16 filed** —
  interactive design session (`docs/design/mitsubishi_hvac_driver.md`). User-pinned decisions: name
  **MitsubishiHvac** (not "ESP32ManagedDevice" — the modules are ESP8266 and the contract is the
  mitsubishi2wb firmware dialect); capability map `profiles/hvac.json` → `classes/MitsubishiHvac.json`
  (profile dies, `reconcile:false` explicit); **tables in the class map ONLY** (driver translates via
  its attached capability map — amends the tables-in-code premise); device configs shrink to identity +
  `mqtt_device`; typed state → VWB-18 restore-at-boot + **heartbeat reachability** (the firmware's
  unconditional 45 s room_temperature publish; no LWT exists); NO bridge-owned WB card (the ESP32's raw
  card "is fine like it is"); enum-value icons = the AV IconResolver mechanism → **UI-16**
  `[P2][deferred]`. **DRV-28** filed `[P1][release]` (user pulled the implementation into the release
  run; the voice golden re-pin consolidates on its landing). REST-firmware horizon recorded in §8
  (bench-twin-gated, unfiled). No code.

- **2026-07-10 — DRV-26 DONE (HVAC value tables → firmware numeric wire; control revived)** — the
  VWB-14 tables carried label strings as `wire`, but mitsubishi2wb speaks numeric indices and silently
  drops anything else — HVAC mode/fan/vane/widevane was dead in both directions. Fix: `wire =
  str(position)` (declaration order already equals the firmware index) in the `hvac` profile + the 3
  device configs; canonical vocab + labels unchanged. Drift-guard tests updated to the firmware truth
  (+ a generalized every-table-is-indices guard); 2 both-direction tests on the real children config
  (`'2'→'cool'` in, `cool→'2'` out). **Golden → `a4a2b1aed5f86447`** (openapi byte-identical) — voice
  re-pins ONCE to this (covers DRV-25 + DRV-26). Suite 664, pyright 0, 6/6. DRV-27's firmware premise
  amended (user reversed: REST-endpoints rewrite under research, bench-twin-gated, ESP8266 D1 Mini
  confirmed). Live set_mode check rides REL-3.

- **2026-07-09, night — the HVAC-cards incident: root cause pinned (bridge exonerated); DRV-26 + DRV-27
  + VWB-32 filed** — all three WB-UI «Кондиционер» cards showed valueless controls (sliders pegged at
  max, blank setpoint, red ⊗); initial suspicion fell on the day's DRV-23/25 deploys. Investigation
  (live broker forensics + container logs + the `../mitsubishi2wb` firmware source): **the controller
  rebooted at 14:37 MSK and mosquitto runs WITHOUT persistence → every retained message was wiped.**
  Everything that actively republishes recovered (wb-mqtt-serial poll, wb-rules, ESP32 `meta` + periodic
  `room_temperature`); the mitsubishi2wb ESP32s republish interactive control values **only on change**
  (`mqttConnect()` re-sends meta only — confirmed in source), so their cards stayed empty until poked
  (living room self-healed after voice's command; children via panel power-cycle; bedroom = the still-
  broken witness that proved it: meta intact, values absent). The bridge's total output to HVAC topics
  all day: ONE non-retained `power/on: 0`. **Decisions:** mosquitto persistence stays OFF (user, per WB
  community advice) → robustness moves above the broker. **Found en route, filed:** **DRV-26** `[P1]
  [release]` — the VWB-14 HVAC value tables have label-string wire values but the firmware speaks
  numeric indices AND silently drops non-numeric commands ⇒ HVAC mode/fan/vane/widevane control is
  currently DEAD both directions (definitive numeric tables extracted from `hpSettingsChanged()`);
  **DRV-27** `[P2] [deferred]` — dedicated ESP32-HVAC driver design (typed declared state → restore-at-
  boot covers the wipe; firmware tables in code; optional bridge-owned labeled WB card; the VWB-11-
  anticipated migration, user-directed); **VWB-32** `[P1] [release]` — `bridge/catalog/version` is only
  published from `/reload`, so the wipe left it MISSING on the live broker (voice's staleness gate reads
  it) — publish retained at startup + on reconnect. No code in this entry — investigation + filings.

- **2026-07-09 — DRV-25 DONE (WB-passthrough state → top-level fields; switch `power` readable)** —
  pulled forward from `[deferred]` (maintainer: a nasty bug that must not ship in release 1). Retired
  the `mirrored` bucket: `WbPassthroughState` is `extra="allow"`, `_on_value_message` sets each coerced
  value as a top-level field, `BaseDeviceState.model_dump` merges `__pydantic_extra__`, idempotence reads
  `getattr(state, field)`, + a collision guard. `light_switch`/`dimmable_light`/`power_switch` `power` →
  stateful+readable+`reconcile:false`+`'1'↔'on'` value table; a loader step enriches bare
  `state_topics[field]` from the profile field. `HvacPanel` migrated off `state.mirrored.*`. **Contract:
  golden `8159b4b0068d1c63` → `16eee0f2f7832995`** (power readable); openapi byte-identical (the `/state`
  endpoints aren't openapi-typed, so `WbPassthroughState` isn't in the schema) — only golden+stamp moved,
  **voice re-pins to `16eee0f2f7832995`.** Suite
  662, pyright 0, import-linter 6/6, UI check+build green. Doc: `devices-and-scenarios.md` (state
  surfaces top-level). Supersedes DRV-23's projection. Live re-verify owed to the redeploy.

- **2026-07-09 — DRV-24 design REVISED (converged: retire `mirrored`)** — maintainer review of the first
  cut ("why mirror stateful values — isn't it duplication?") landed: the `mirrored` bucket is the generic
  driver's substitute for typed fields, and the driver never holds a logical value apart from the mirror,
  so for passthrough the mirror *is* the state and the projection was a workaround. Revised D3 to **retire
  `mirrored`** — passthrough state moves to top-level dynamic fields (`extra="allow"`, the AV-driver shape),
  subsuming DRV-23's `model_dump` projection and dropping the `power` duplication. Now an openapi + golden
  change + a UI `HvacPanel` migration. `docs/design/wb_passthrough_readable_power.md` + the DRV-25 entry
  updated to the converged scope. No code (design only).

- **2026-07-09 — DRV-24 DONE (design) + DRV-25 filed — WB-passthrough readable/authoritative power** —
  follow-on to DRV-23 from the voice side's live re-test. Design (`docs/design/wb_passthrough_readable_power.md`)
  for making `state.power` authoritative + readable on the 39 momentary-power WB-passthrough switch devices
  (`light_switch`×24, `dimmable_light`×13, `power_switch`×2): (D1) profiles' power → stateful readable with a
  `'1'↔'on'` value table; (D2) load-time enrichment so a device's bare `state_topics[field]` inherits the
  profile field's type/values (declare once; also fixes the DRV-23 `mode` raw-`'0'` sibling); (D3)
  `_on_value_message` sets the declared top-level `power` from the coerced canonical value. Scope pinned to the
  WB-passthrough power capability only. Golden re-pin on implementation (cross-repo). Implementation = **DRV-25**
  (`[P2][deferred]`, picks up with the voice features that need it — no release-1 gate).

- **2026-07-09 — DRV-23 DONE (voice-filed; WB-passthrough state projected to top-level)** — filed by the
  voice repo per `cross-repo-source-of-truth`; verified against live code + the running WB7, reframed, and
  fixed same session. **Read path was genuinely broken:** WbPassthrough wrote feedback only into
  `state.mirrored`, so voice reading top-level `state.<field>` (ARCH-8 contract) got `None` — «какая
  температура в кабинете» failed though `room_temperature=24.125` sat in `mirrored`. **Write-path claim
  disproven** by a live on→off→off repro (`power.off` fired, `no_op:false`; idempotence already uses
  `mirrored`). **Scope: WbPassthrough-only, 39/65 devices** (live sweep; `mirrored` exists only on that
  state class; all other classes clean). **Fix:** `model_dump` override on `WbPassthroughState` lifts each
  mirrored value to a top-level key (serialized-view only — mirrored stays the source of truth, declared
  fields like `power` not shadowed). +2 tests, suite 662, pyright 0, contracts 6/6, OpenAPI byte-identical.
  Live re-verify owed to the redeploy.

- **2026-07-09 — VWB-30 DONE (REL-5 reports hardening #13/#14/#15/#16, pulled forward)** — reports is
  live on the WB7, so four gaps fixed: redaction now masks the whole value under a credential-shaped key
  (was leaking non-secret-keyed leaves), `redact_text` masks URL-embedded creds (`scheme://user:pass@`),
  `report_id` gained a uuid suffix (spool-filename collisions), and the browser `actionLog` takes the
  newest N not the oldest (`slice(0,N)` — the store unshifts). +3 backend tests; pyright 0, 6/6, UI green.

- **2026-07-09 — UI-13 DONE (REL-5 #7 P1 fix: SSE never gives up)** — `useEventSource` now falls back to a
  60 s keepalive reconnect after the fast back-off budget is spent (was dead-until-reload after ~10
  attempts, freezing wall-panel device state). UI check + build green.

- **2026-07-09 — UI-14 DONE (REL-5 #17/#19, pulled forward)** — removed the shipped TEMPORARY-DEBUG branch
  that surfaced every unknown SSE event into the progress feed; `ForceReconcileDialog.close()` now clears
  `pending` so a quick reopen during an in-flight force isn't stranded. UI check + build green.

- **2026-07-09 — SCN-12 DONE (REL-5 #6 P1 fix: teardown honours reconcile:false)** — `build_power_off_plan`
  gained the `reconcile` guard `build_plan` already had, so a graceful switch/shutdown no longer emits an
  IR `power_off` to a `reconcile:false` device (the upscaler). One-line fix + test (upscaler ON → empty
  power-off plan). pyright 0, import-linter 6/6.

- **2026-07-09 — DRV-21 DONE (REL-5 #3 P1 fix: select-form forwards force/assume_state)** — canonical
  select-form `set` dropped the reserved cross-cutting params (`CapabilitySelect.expand` takes only
  `value`), so the UI re-tap-to-force escape hatch was dead for AV inputs. New domain constant
  `RESERVED_PARAMS`; the dispatcher overlays force/assume_state onto each expanded select-form step
  (mirrors the actions-form path; step params win). 3 tests in `test_select_canonical.py`; pyright 0,
  import-linter 6/6 (presentation→domain only).

- **2026-07-09 — CORE-9 DONE (REL-5 #2 P0 fix: MQTT reconnect budget per-episode)** — `_run_mqtt_client`
  reset `retry_count = 0` on each successful connect, so `max_retries` bounds retries within one
  failed-to-connect episode instead of across the process lifetime (five lifetime blips no longer
  permanently kill MQTT). New `test_mqtt_reconnect.py` (connect-then-drop 8× > max_retries, asserts the
  loop keeps reconnecting). pyright 0, import-linter 6/6.

- **2026-07-09 — REL-5 DONE (pre-tag code review) + 11 remediation tasks filed** — the code-review
  half of the release gate, split out of REL-3 and run off the rack. A multi-agent review (7 subsystem
  reviewers × 4 dimensions, every finding adversarially re-verified — 27 agents, 0 errors) over the
  release-critical backend + UI. **20 raw → 19 confirmed (1 refuted): 2 P0, 5 P1, 12 P2.** Frozen
  evidence: `docs/review/rel5_pretag_review.md`. Two P0s stand out — the broker password committed in
  `system.json` and served unauthenticated on the LAN (#1), and the MQTT reconnect counter that never
  resets so the bridge permanently loses MQTT after 5 lifetime disconnects (#2). Findings triaged with
  the user and filed as fresh tasks: tag-blocking **CORE-9, DRV-21, SCN-12, UI-13** + pulled-forward
  `[release]` **VWB-30** (reports hardening), **UI-14** (UI nits); deferred **CORE-8** (broker/device
  secret handling — owner scoped it to productization, house on a trusted LAN; password rotation is a
  separate near-term op), **VWB-31, DRV-22, OPS-18, UI-15**. P0/P1 remediation lands before the tag.
  Board now: REL-3 (rack) ∥ {CORE-9/DRV-21/SCN-12/UI-13/VWB-30/UI-14 fixes} → REL-4 → tag.

- **2026-07-09 — OPS-17 DONE (both containers run non-root as uid 1000 `domovoy`)** — user-flagged
  from the voice deployment work ("we run the containers as root, which is wrong"); mirrors the voice
  repo's BUILD-15 uid fix. Backend `Dockerfile`: `useradd -m -u 1000 domovoy` + chown /app + `USER`
  (clean — deps already in `/opt/venv`). UI `Dockerfile` (`nginx:alpine`): `adduser -D -u 1000`
  (BusyBox, not Debian `useradd`) + chown the paths nginx writes at start/run + `USER`; pid redirected
  to `/tmp/nginx.pid` in `nginx.conf.template` (non-root can't write `/run/nginx.pid`). `update.sh`
  chowns the writable mounts (`data/`,`logs/`) to 1000 before `up` (it runs as root; container would
  else EACCES). Name is provisional (tracks the Domovoy decision); the UID is the real identity.
  Verified: a stage-2-only UI build booted nginx master+worker as `domovoy`, pid in `/tmp`, HTTP 200.
  Activation owed to the rack — inert until images rebuilt + `git pull && ./ops/update.sh` (chown and
  the new non-root images land together in that one command). `sh -n` + `compose config` clean; no
  Python change. Docs: `ops/INSTALL.md` non-root note.

- **2026-07-09 — VWB-13 DONE (catalog completeness sweep + bulk end-to-end, on the deployed WB7)**
  — closed on the user's spot-check evidence after reconciling the sweep's two halves against live
  controller reality (`task-start-reconciliation`; user-accepted "close as done now"). Half one
  (**catalog completeness**) was already proven at the REL-2 cutover 2026-07-08: the controller's
  live `/system/catalog` byte-matched golden `8159b4b0068d1c63` (79 devices / 11 rooms, incl. all 8
  `global` aggregates + `scenario_manager_living_room`) — zero deployment drift, every canonical
  action resolvable. Half two (**bulk end-to-end across rooms**) rode the user's controller
  spot-checks 2026-07-08–09: room devices exercised through the deployed bridge, behaving identically
  to the dev-box run (same binary + config tree — REL-2 removed the only variable). The 8 `global`
  aggregates accepted as covered-enough (bar = the canonical call *publishes to the broker*; the wired
  ones actuate the house and several still owe wb-rules backing, so an exhaustive fire-all was
  deliberately not run). Verification task — no code touched. **REL-3 is now unblocked** (its last
  non-done prerequisite). Board: REL-3 → REL-4 → tag; VWB-16 x-repo.

- **2026-07-08, evening — Domovoy productization intake accepted (VWB-29, CORE-7, OPS-14, OPS-15,
  OPS-16 filed)** — the joint productization session (run from `~/development` as both repos' Claude;
  voice-side BUILD-20, committed there `7214eb7`) left `docs/design/productization_bridge.md` + five
  proposed ledger entries **uncommitted** per `cross-repo-source-of-truth`. Verified against live code
  before accepting: contract artifacts + STAMP as described (`contracts/`, commit `7206902`); voice's
  re-pin to golden `8159b4b0068d1c63` confirmed landed (`eval-commons/contracts/STAMP.json` matches —
  the stale "voice must re-pin" note is closed); OPS-12/VWB-28 logging facts match their DONE entries;
  driver wiring is indeed config-name-based (`device_class`/`config_class` in `devices/*.json`);
  `ledger-guard` job present; `check_scope.py` green with the five in place (109 tasks). All five stay
  `[P2]` `[deferred]` — nothing enters the release-1 board. Umbrella product name: **Domovoy**. This
  was the deliberate last use of the uncommitted-filing mechanism — replaced by board-as-outbox once
  eval-commons becomes `domovoy-commons` (voice BUILD-21).

- **2026-07-08, the cutover (REL-2 DONE — the house is served from the WB7)** — the user drove
  the controller shell, Claude verified over SSH/HTTP from the dev box; the runbook was rebuilt
  in-flight three times as controller reality arrived: (1) the historical runtime tree
  `/mnt/data/mqtt-bridge-config/{config,data,logs}` KEPT (user decision; compose mounts went
  absolute; update.sh gained the config rsync), (2) the clone moved to the exFAT SD card — which
  also ruled out moving Docker's data-root there (overlay2 needs POSIX; stays at
  `/mnt/data/.docker`), (3) after reboot test #1 FAILED (`RequiresMountsFor=/mnt/sdcard` dragged
  the automount's mount+fsck into early boot before the card enumerated — oneshot, no retry),
  the user's structural call: **boot depends only on /mnt/data** — update.sh deploys the compose
  file into the runtime tree, the unit runs compose from there, the clone is update-time-only
  (`e88aa84`). Reboot test #2: PASSED, ~3.5 min to a serving bridge, zero hands. Realism dump
  **MATCH** (golden `8159b4b0068d1c63`, 79 devices); `all_lights.js` in; reports live end-to-end
  (token via runtime-tree `.env`, `enabled` flipped through the repo — `78673b3`, the user's own
  commit, the source-of-truth flow working as designed). Bonus finds: container healthchecks
  lied (UI `localhost`→`::1` vs IPv4-only nginx = unhealthy forever; backend start-period 20s <
  device-fleet boot) — fixed `cc6a94d`, images rebuilt. Ops lesson exported to the voice repo as
  a note (same sdcard-boot-dependency suspected there). **VWB-13 unblocked; REL-3 is next at the
  rack.** 104/79.

- **2026-07-08, night (OPS-7 DONE — Dependabot triage; alerts 88 → 5 → 0; OPS-13 filed)** —
  the May entry aged well in the best way: 83 of its 88 alerts dissolved via ordinary lockfile
  evolution (axios + the whole backend aiohttp/urllib3 set gone; backend lockfile fully clean),
  so the original bump plan was obsolete. The 5 survivors were all `scope: development`
  (vite ×3 / esbuild / minimatch — dev server + lint-time only, nothing in the shipped
  containers) and none fixable in-range (`npm audit fix` a no-op; minimatch pinned EXACTLY by
  typescript-estree 6.21; vite fix starts at 6.4.3). Per the entry's own standing rule, all 5
  **dismissed as tolerable_risk** with comments pointing at the newly filed **OPS-13**
  (post-release UI toolchain migration: eslint 9 flat config + @typescript-eslint 8 + vite
  current). Open alerts: **0** — the per-push banner is gone. No code/lockfile change.
  103 tasks / 78 done; the desk stays clear.

- **2026-07-08, evening (OPS-8 DONE — reconciled, narrowed, shipped; THE DESK IS CLEAR)** —
  the user's "might be greatly outdated" was right: of the five 2026-05-22 sub-items, the
  teardown-hang one was OPS-6 (done 2026-05-28) and auto-reconnect had been addressed piecewise
  by the drivers' own evolution (eMotiva on-command setup, Apple TV `_ensure_connected`, LG
  health loop + WoL, Auralic probe/halt). Narrowed interactively to items 1+5+4-lite and shipped:
  **(1)** lifespan startup wrapped — unexpected mid-startup failure now releases the acquired
  resources (`_release_partial_startup`, each step guarded, 3 tests) and re-raises instead of
  leaking a hung process; reindent verified pure-whitespace. **(5)** `cleanup_wb_device_state()`
  had ZERO callers — WB device cards kept retained `available=1` forever after a bridge stop
  (the "Last Will" is a misnomer, no actual will); now wired into bootstrap shutdown BEFORE the
  MQTT disconnect. **(4-lite)** Apple TV app-list failure demoted ERROR→WARNING, no more
  `state.error` for a box that's merely asleep. Suite **652**, pyright 0, contracts 6/6, no API
  change; overview.md lifecycle updated. Commit `ea9f1f8` + the ledger move. **With DRV-5,
  SCN-11 and OPS-8 all closed today, no software-only release task remains** — everything left
  (REL-2 → VWB-13 → REL-3 → REL-4 → tag, VWB-16 x-repo) starts at the rack.

- **2026-07-08, later (SCN-11 DONE — the scenario force-reconcile dialog, same desk session)** —
  filed in the morning, shipped by the same sitting. Domain: `build_forced_device_plan` (single-
  device forced plan; diff skipped, `force` injected, cross-device ordering edges drop out — the
  5 s zappiti settle is test-pinned present in the full plan and absent in the forced one) +
  `build_reconcile_preview` (believed-vs-desired rows; eMotiva power as per-zone dicts) +
  `ScenarioManager.reconcile_preview`/`force_reconcile_device` (active-only). The toggle sharp
  edge landed as designed: forced toggles carry **`assume_state` = the plan target** and the IR
  toggle handler claims it instead of blind-flipping (else the desync comes back mirrored);
  `assume_state` joined `force` as a reserved param. Endpoints: GET `reconcile_preview` (pure
  read, 404/409) + POST `force_reconcile` (gated chain server-side). UI: "Device states…" button
  under the active scenario's remote → `ForceReconcileDialog` (expand-then-confirm rows, per-row
  progress; in-sync rows calm but tappable — the inversion is the point). 13 new tests; suite
  **649**, pyright 0, contracts 6/6, UI clean, eval cli 4/4; OpenAPI 36/90 regenerated; contract
  + architecture docs updated. HW feel-check rides REL-3. Commit `43c504c` + the ledger move.
  **Release board: the desk half is now DRV-5 ✅ SCN-11 ✅ — OPS-8 is the last desk task.**

- **2026-07-08 (DRV-5 DONE + SCN-11 filed — the force escape hatch, UX pinned interactively)** —
  the desk session opened the release board's software half. UX discussion first (user-driven):
  the plan's arm-checkbox sketch lost to **reactive re-tap** — a guarded skip now returns a
  structured marker (`data={no_op, skipped_reason:"idempotence"}` via the new
  `BaseDevice.idempotence_skip(...)` chokepoint), the UI arms an 8 s "tap again to send anyway"
  offer (amber banner + button pulse), and the re-tap re-sends with the reserved `force` param —
  no manifest/capability-map coupling at all, the skip response is the signal. All 9 idempotence
  guard sites converted (IR power pair = the HIGH-value desync trap; eMotiva ×5 incl. the ARC
  power-cycle guard; Auralic; LG); `_resolve_and_validate_params` preserves `force` alongside
  declared params; `CanonicalActionResponse.skipped_reason` added and threaded through `wait:false`.
  **Bonus fix:** `wait:true` canonical on an already-at-target guarded device no longer 503s (the
  skips now set `no_op`, so the short-circuit fires — voice «включи» on an already-on IR device).
  Suite **636** (+13: per-guard regressions + 2 route tests), pyright 0, contracts 6/6, UI
  check+build, eval cli 4/4; OpenAPI + UI types regenerated; docs updated (`ui_backend_contract.md`
  force section; `devices-and-scenarios.md`/`ui.md` — the promised "manual resync button" is now
  real, described as shipped). **Also this session:** the user re-scoped the feature as primarily
  a *scenario* symptom → **SCN-11 filed `[P1] [release]`** (per-device force-reconcile dialog on
  the active scenario page: believed-vs-desired table from a pure `build_plan` preview,
  expand-then-confirm rows, single-device forced plan, `assume_state` toggle-claim correction) —
  next up, right after this. DRV-5's "no scenario-level force" non-goal amended: the blanket flag
  stays rejected, SCN-11 is the user-mediated precision variant. Commits `22dfa5e` (filing),
  `ab7eb6c` (implementation), + the ledger move.

- **2026-07-07 (DRV-18 DONE, DRV-19/20 filed — the Zappiti design, the night half)** — a browser
  design session produced `docs/design/zappiti-driver-spec.md`; verified per the cross-repo intake
  rule (all §14 reuse claims real in `zappiti_updater`; the "Peewee matches the bridge stack" claim
  false — bridge is aiosqlite, fixed) and reworked in-session: Part I gains the polling policy
  (launch burst vs slow transition-only steady state), the don't-wire volume note, the pinned-IP +
  multi-export §7 rows, the mount-order §8 item, and a Bridge-integration-impact block (replaces
  the `video` IR device; discrete power kills the toggle; golden → voice re-pin; the 5 s topology
  delay upgradeable to a SCN-10 feedback gate). Part II re-architected around the four decisions
  pinned live: **browser-native indexer** (mediainfo.js/WASM probe over laptop mounts — chosen over
  the Synology container for the zero-install productization story), bridge = sole SQLite writer
  behind an ingest API (no DB crossing at all), TMDb-first with the contributor loop (OMDb → a
  post-release optional module, voice-project spirit), catalog panel on the Zappiti device +
  scenario pages with `w500`/`w780` artwork; schema gains series/season/episode + mark-missing
  pruning (the "add a season later" gaps). Design task DRV-18 closed born-done; DRV-19 (driver) +
  DRV-20 (catalog) filed `[deferred]`. Release board unchanged.

- **2026-07-07 (SCN-3 DONE — all four music scenarios; the evening half of the rack sitting)** —
  turntable (amp 4 s gate → cd, volume, **mute on the fresh ROM20**, reworded notes);
  auralic (one-action switch; Lightning DS playback with full now-playing after three live fixes —
  DIDL list-artist flattening, SourceIndex current-source, the lib skip() Playlist fallback for
  units reporting an empty source type — plus Previous exposed end-to-end, golden →
  `8159b4b0068d1c63`); reel/tape back-and-forth at 13–21 ms, amp/A77 behaving. **Collateral:**
  the power-off gate bool-complement fix (a 25 s teardown stall that hung the UI spinner and ate
  the notes dialog), **lifecycle SSE moved to the domain chokepoint** (the canonical path — the
  UI's primary since UI-9 — emitted nothing; page went stale until reload; router duplicates
  removed, UI mutation belt-and-suspenders added), the quiet halted probe (GetHaltStatus on the
  stored handle instead of a 60 s M-SEARCH loop), and the manual-notes rework (user wording moved
  into topology position strings; scenario manual_instructions emptied pending re-authoring —
  Revox/Sugden power notes parked). Exit-criteria item 2 is now fully satisfied except REL-3
  itself; **no rack-testable release task remains** — the board is REL-2 (user) → VWB-13 → REL-3
  → REL-4, plus desk-work DRV-5/OPS-8 and cross-repo VWB-16.

- **2026-07-07 (SCN-9 DONE — the scenario lifecycle re-proven, same day it was filed)** — the
  movie-scenario walk delivered all four points: start (14:59, three step findings all fixed same
  hour — LG input dialect matcher, amp power gate 1→4 s, zappiti power re-learned + corrected to a
  TOGGLE with catalog golden → `d0536f643b783d8a`), switch both directions (diff-only; the
  switch-back exposed the ordering-edge settle gap — ack≠completed, `delay_ms: 5000` mitigation +
  SCN-10 filed for feedback-gated edges, with the design note that the capability schema already
  carries everything needed), end (15:43, five teardown actions, zero failures, room dark), and
  restart survival (15:19, active scenario restored, 2-action re-reconcile). Also: zappiti
  subtitles ROM38 carried ROM37's code — re-learned + verified; REL-3's re-learn list is down to
  the amp mute ROM20. **The scenario machinery itself needed zero fixes** — every finding was
  dialect, timing data, or stored IR. 5 s settle feel-check rides SCN-3's sitting.

- **2026-07-07 (DRV-1 DONE — the per-driver HW pass closes after ~6 weeks `DOING`)** — the user
  closed it at the sitting after the Apple TV pointer pad went green (living unit fully verified
  same day). All seven driver classes hardware-verified. Residuals re-homed at close:
  children-room LG smoke **waived** ("always worked — it was my development environment"); LG
  reconnect-cycle + mf_amplifier mute re-check (ROM20 re-learn, user-owned) → **REL-3**; eMotiva
  scenario route + Auralic playback-with-content → **SCN-3**; A77 → **DRV-15** (already moved).
  Release exit-criteria item 2's DRV-1 line is satisfied; the drivers-before-composites
  methodology gate is discharged — the SCN-3/SCN-9 scenario passes are now unblocked on their
  own terms. 96 tasks, 71 done.

- **2026-07-07 (DRV-2 DONE — Apple TV dropdown app launch; sitting continued)** — kitchen hood +
  living-room HVAC actuate from the UI (HVAC read-side enum warnings stay with REL-3's check);
  UI-12 filed off the sitting (WB-passthrough fleet miscategorized as "devices" — only
  `kitchen_hood` carries `device_category: appliance`); A77 transport walk moved out of release
  scope → DRV-15 (user decision; `music_reel`/SCN-3 may cover it first); PR #26 retitled+rewritten
  to cover both library changes. Then DRV-2: the dropdown sends the app **id**, the handler
  resolved display **names** only → dual matching (LG precedent), 2 regression tests, HW-verified
  live (ARD Mediathek launches; «works!!!»). Apple TV living unit otherwise re-verified green;
  pointer pad re-test noted on the DRV-1 row. Suite 614. Release gate: exit-criteria item 2's
  DRV-2 line is now satisfied.

- **2026-07-07 (DRV-14 DONE — Auralic all-network power shipped + HW-verified; the full arc)** —
  research → library → driver → three live-fire iterations, one sitting. Library: fork branch
  `hardware-config-halt` (PR bazwilliams/openhomedevice#26) — `is_halted`/`set_halt` + the
  `Visible` dialect fix (Linn `true` vs AURALiC `1`; the unit's 11 sources were all filtered out —
  found when the user's inputs dropdown enabled but came up empty). Driver: halted **detected**
  (Product absent), never guessed; `power_off` = stop+standby+halt with honest messaging;
  `_wake_from_halt` learned the hard way (first live ladder failed) that the halt transition moves
  the unit's ports — the wake now goes to a **freshly discovered handle** every attempt. Also
  fixed: options dialect (`input_id`/`input_name`) + **true device indices** (invisible sources
  occupy slots — filtered positions would have switched the wrong source), stale state
  `ip_address`. **Ladder HW-verified 13:18: off (standby+halt) → wake → on in 22 s; 11 sources in
  the UI.** IR power gone (`ROM62` toggle freed). DRV-1 Auralic row: bench-probe answered (Volume
  service present, sources enumerated, tri-state mapped), walk largely done — playback-with-content
  rides the `music_auralic` SCN-3 pass. Suite 612; pins advanced twice with the guard test.

- **2026-07-07 (DRV-14 FILED — Auralic all-network power research; IR disproven necessary)** —
  user asked "do we really need IR power for the Auralic?" before starting the action walk; live
  experiment answered it. Streamer connected cleanly post-DRV-13 (`.142`, renderer picked over
  server, **standby readable, Volume service present** — two bench-probe answers in). UI power_off
  took the IR "true power off" path and claimed `deep_sleep=True` — but probing showed the unit
  **network-alive**: SSDP + device.xml up on a fresh port with a reduced service set
  (`HardwareConfig`+`Volume`; `Product` deregistered). SCPD enumeration found
  `GetHaltStatus`/`SetHaltStatus`; SOAP `GetHaltStatus`→1 confirmed "halted", and
  **`SetHaltStatus(0)` woke it into standby** (full services back, `is_in_standby`→True). Power
  ladder fully network-controllable: on ⇄ standby (`SetStandby`), standby ⇄ halted
  (`SetHaltStatus`); no network-dead state short of the rear rocker. DRV-14 filed `[release]`
  (wrap HardwareConfig in the openhomedevice fork, truth-tell `power_off`, detect the halted state,
  retire the ROM62 IR toggle) and wired into the Ordering table ahead of the SCN passes. Also
  closed en route: the streamer's DHCP reservation is live at `.142` (router lease enabled by the
  user, config pinned).

- **2026-07-07 (DRV-13 DONE — Auralic SSDP discovery rebuilt on raw M-SEARCH; the IP-drift saga)** —
  post-DRV-12 restart: cadenced probes fired on schedule but discovery still failed. Layered
  diagnosis: (1) unit dead at the configured `.16` → SSDP sweep found it at `.11`
  (`streamer.json` updated, stale `device_url` nulled); (2) still zero candidates → reproduced
  standalone: `async_upnp_client` 0.44.0 `SsdpSearchListener` receives **nothing** on this
  network under any variant while a raw-socket M-SEARCH gets 16 answers — the May "async SSDP
  discovery" was mock-tested only, first hardware contact today. Replaced with `_msearch_sync`
  (executor) + pure `_extract_ssdp_locations`; classification pipeline unchanged; live-verified
  (2 candidates at target). 3 parsing tests; suite 601. Router lease plot twist (user screenshot):
  the unit's MAC maps to a `.142` "LivingRoom" lease while the woken unit squats on old `.11`
  without re-DHCPing — canonical-address decision left with the user (reservation to `.11` vs
  renew onto `.142` + one config flip).

- **2026-07-07 (DRV-12 DONE — Auralic asleep-at-boot never rediscovered; sitting continued)** —
  eMotiva row closed to "scenario route only" (zone2 power/independence + volume verified; main-zone
  volume **N/A by topology** — `processor:zone2 → mf_amplifier:aux2` is the only audio output; the
  source-switch ack quirk observed live and handled by pymotivaxmc2). The living_room_tv `volume=98`
  sighting explained: genuine webOS volumeStatus push on the eMotiva's ARC engagement (external-audio
  scale), reverted to 30 with the path — DRV-4's two-axis story, no bug. Two UX papercuts filed off
  the sitting (UI-10 dropdowns don't reflect live selection; UI-11 same-name devices
  indistinguishable — the «Телевизор»×2 confusion). Then the Auralic walk opened with a real find:
  physically woken streamer stayed invisible — boot-failure sets the deep-sleep *guess* and the old
  loop branch never probed (40 min, zero attempts). Fixed: `_periodic_tick` extraction + cadenced
  probe in the deep-sleep branch; 4 tests; suite 598. Walk continues post-restart.

- **2026-07-07 (DRV-11 DONE — XMC-2 space-padded negative volumes parsed as 0.0; rack sitting
  continued)** — post-restart re-verification of DRV-10 all green on hardware (cold WoL power-on;
  `set_volume` echo payload success + OSD moved; already-on no-op in 1 ms). IR fleet blessed via
  `mf_amplifier` (power/inputs/volume react; **mute publishes ROM20 cleanly but the amp ignores it**
  — stored code suspect, user to check the OEM remote / re-learn; volume stepping slow = one code
  per press, enhancement candidate). eMotiva zone-1 power-on clean in 3.6 s, ARC recognized
  (`HDMI ARC` → `arc`), and the **third sighting of `zone2_power=On`** turned out to carry a real
  driver bug: the device pads short negatives (`'- 3.0'`), `float()` raised, silent fallback showed
  **0 dB instead of −3.0 dB**. Fixed in the converter (space-strip + warning) and the raw zone2
  status-sync path now routes through it; 3 regression tests; suite 594. `pymotivaxmc2` not at
  fault (raw XML strings by design). Zone2-physically-on question still open at the rack.

- **2026-07-07 (DRV-10 DONE — LG false-negative classifiers fixed; already-on power churn killed;
  rack sitting log)** — the first live DRV-1 sitting of the day, backend observed via
  `logs/service.log` while the user drove the UI. **LG living row re-verified on hardware:** power
  on (already-on path), home, launch_app (ivi), pointer move + click (~50–60 ms cadence), nav
  cluster (menu/back/exit/enter), power off with subscription-confirmed standby in ~2.3 s.
  **Two live finds:** (1) `set_volume` false-negative → root-caused to the driver re-validating
  asyncwebostv's already-validated-and-stripped payload (the library pops `returnValue`, raises
  `IOError` on failure); fixed `_execute_media_command` + `launch_app` to trust the contract,
  `_execute_with_monitoring` audited correct as-is (raw monitoring dicts); (2) power-on-while-on →
  `turnOn` answers empty payload → old code WoL'd + slept 20 s + full-reconnected; fixed with an
  idempotence guard (connected + power=on ⇒ no-op; DRV-5 inventory updated LgTv 0→1 guard, LOW,
  must honor `force`). Startup init verified correct (subscriptions synced power='on' in 2 s).
  4 regression tests; suite 591. **OPS-12 validated live** (rollover + 31-day prune fired on this
  very startup). Also observed, pending decisions: eMotiva zone2=On-while-main-Off at connect;
  HVAC «Кондиционер» numeric wire values failing enum parse (fan '0', mode '2', vane '0',
  widevane '3') — REL-3's HVAC check will hit this; DEBUG log prints the broker password in the
  MQTT-init line. Process note: a `tail` pipe swallowed a failing guard exit on the DRV-10 filing
  commit (6 OUT-OF-ORDER errors pushed, fixed next commit) — run the guard bare, never piped.

- **2026-07-07 (OPS-12 DONE — voice-style startup log rollover; dead rotation cleanup fixed)** —
  user-requested at the rack, first item of the REL-2 sitting. Each startup now renames the live
  log aside (`service.log.<YYYYmmdd_HHMMSS>.log`) and starts fresh; daily rotation kept. The
  rename deliberately stays in the `service.log.*` family so VWB-28's `_collect_logs` glob needed
  no change. Analysis found `backupCount=30` had **never deleted anything** (custom
  `TimedRotatingFileHandler.suffix` without matching `extMatch`) — fixed, plus a startup prune of
  siblings past 30 days for the startup-renamed files the handler can't see. 4 new unit tests +
  a two-startup smoke run; suite 587, pyright 0, contracts 6/6, no contract/UI impact. Filing
  footnote: the first OPS-12 commit attempt was blocked by the DOC-12 guard catching an edit slip
  that swallowed the `### CORE` header — the day-old triad already paying rent.

- **2026-07-07 (CORE-6 DONE — import-linter parity with voice; `domain ⇄ utils` cycle broken)** —
  filed + executed same session off the chat-requested enforcement comparison. The gate machinery
  was already identical (`py-dev-gates@v0.1.1`); the gap was declared coverage — 3 contracts vs
  voice's 11 — and one live violation hiding in it: `utils/types.py` + `utils/validation.py`
  imported `domain.*` while `domain/` imported `utils`, a package cycle contradicting
  `overview.md`'s foundation claim. Moved `utils/types.py` → `domain/devices/types.py` (it was
  pure domain vocabulary: `CommandResult`/`CommandResponse`/`StateT`/`ActionHandler`) and
  `utils/validation.py` → `infrastructure/config/validation.py`; rewrote 14 import sites (incl.
  2 tests + the howto-new-driver guide). Contracts 3 → 6: infrastructure additionally forbidden
  from `app`/`cli`, presentation from `app`/`cli`, utils from everything upward (canary-verified
  to fire), plus driver-package `independence` across the 8 drivers. Non-goals recorded:
  seam-pinning (behavioral chokepoints, test-locked) + port-purity (domain rule has no ignores).
  Gates: 6/6 kept, suite 583, pyright 0, OpenAPI byte-identical.

- **2026-07-07 (CORE-5 FILED — `device-test` CLI reviewed stale, resurrection deferred post-release)** —
  user flagged the `device-test` CLI as ~1 year untouched; reviewed against the live core before
  filing (evidence in the CORE-5 row): imports clean, entry point resolves, but it mirrors a
  year-old bootstrap — no state-repository re-hydration (commands live gear from factory-default
  assumed state), no capability maps, private-attr wiring (`_mqtt_client`), legacy
  reconnect-to-subscribe dance, pre-`CommandResponse` result printing. Also surfaced a second
  stale artifact: `backend/tests/device_test.py` (798-line REST/MQTT driver script squatting in
  `tests/`, matches the `*_test.py` collection pattern) — folded into the same task. Key
  resurrection fork recorded: extract a shared fleet-composition helper from bootstrap vs.
  retarget as a thin REST client. Filed `[P2]` `[deferred]`.

- **2026-07-07 (SCN-9 FILED — scenario lifecycle regression re-verification)** — user-requested
  intake during the rack-queue survey: the core start/switch/end scenario loop was last
  hardware-verified 2026-05-22, before the hexagonal restructuring, canonical dispatch and the
  VWB-28 dispatch-ring wrapper — everything since is mock-tested only. Filed as `[P0]`
  `[release]` `HW-GATED` with a 4-point rack walk (start / switch / deactivate / restart
  survival), sequenced after DRV-1 and added to REL-3's gate list in the Ordering table.

- **2026-07-06 (VWB-28 DONE — «Report a problem» shipped end-to-end; contract v1.4)** —
  The whole B-1..B-12 design implemented in one pass, pulled forward from `[deferred]`.
  **Backend:** `domain/reports/` (rings — `DispatchRing` at a new record-and-return wrapper on
  the `execute_action` chokepoint, `MqttWindow` behind a new `traffic_observer` seam on the MQTT
  client; B-5 redaction; `ReportService` collector + B-6 rate limit + §5 filing);
  `ReportSinkPort` (domain) / `GitHubReportSink` (infra, contents+issues API, PAT from env) with
  the B-7 `data/reports/` spool retried at startup + hourly; `POST /reports` +
  **`GET /reports/evidence`** (B-11; `EvidenceEnvelope` = owned contract surface → openapi/
  `contracts/` pin, **v1.4**); `ReportsConfig` on `SystemConfig` (+DTO; canonical `system.json`
  gains `"reports": {"enabled": false}` — filing opt-in, evidence always on). **UI:** navbar
  `BugReport` button (B-12: far right, muted→amber, «Сообщить о проблеме») + minimal dialog with
  in-dialog confirmation (id / spooled / rate-limited variants); `lib/reportEvidence.ts` console/
  crash taps + axios API ring + SSE health (fed from `useEventSource`) + `useLogStore` dump +
  app context, collected only at send. **Two redaction bugs caught by the new tests** (an `auth`
  dict was masked wholesale losing its username; `Authorization: Bearer x` masked only the first
  token) — fixed: containers recurse, text masks to end-of-line. 12 new tests (rings, redaction,
  collector scoping/diffs, filing bundle round-trip, spool temp-dir e2e, endpoints 200/429/503 +
  evidence-always-on). Suite **583** · pyright 0 · contracts 3/3 · UI check+build green · openapi
  +2 paths, golden byte-unchanged. Docs: `interfaces.md` §Problem reports, `contracts/README.md`
  v1.4. **Activation owed to the rack:** controller PAT env + `reports.enabled` flip at/after
  REL-2 (not a release gate). The problem-reporting workstream on the bridge is now complete.
  *Amended same day (user review of VWB-28): (1) hexagon re-verified on request — all new-module
  imports point at `domain` only, contracts 3/3 KEPT, and the package-scoped import-linter
  contracts cover new subpackages automatically (no gate edit needed); (2) the owed user-facing
  docs added — `docs/guides/report-a-problem.md` (modeled on the voice guide), README feature
  bullet + guide link, `overview.md` port list corrected four→five (`ReportSinkPort` + its
  adapter row) — a `user-facing-docs-are-done` gap the review caught; (3) token-minting answered
  (fine-grained PAT, wb-user-reports only, Issues+Contents write → controller env).*

- **2026-07-06 (B-12 — report-button placement + look decided, pre-VWB-28)** — Short interactive
  round before implementation starts: the button is a **navbar far-right icon button** (the
  centered picker row leaves the edge free; FAB rejected — shadows dense remote corners), icon
  **Material `BugReport`** (top-down beetle — genuinely an insect per the user's requirement AND
  the universal bug-report pictogram; sole icon library `@mui/icons-material` ships it —
  `PestControl` roach and `EmojiNature` bee rejected on semantics), resting state **quiet**
  (muted like the pickers, amber on hover — the manual-notes accent; tooltip «Сообщить о
  проблеме»; no permanent accent, no text label). Recorded as **B-12** in
  `problem_reports_bridge.md` (+§2 concretized). VWB-28 now has zero open design questions.

- **2026-07-06 (VWB-26 DONE — bridge joins the problem-reporting loop: lens co-owned, `/inbox` live)** —
  Pulled forward hours after voice BUILD-12 unblocked it. **(1) Lens co-ownership review:**
  `wb-user-reports`' `.github/claude/lens-bridge.md` verified against this repo — its §2
  Reproduce named nonexistent test paths (`tests/test_capabilities.py` for what is
  `backend/tests/unit/...`) and missed the `backend/` cwd, the `uv sync --extra dev` dev-extras
  gotcha, the pyright/lint-imports/UI gates, the contract-regen rule, and a never-live-repro
  warning (repo configs point at the real house) — all corrected in a commit on the reports repo;
  the rest of the file (dedup, key bridge questions, four outcomes, ping-pong guard, leak fence,
  triage-PRs-don't-touch-the-ledger) verified accurate and kept. **(2) `/inbox` + invariant:**
  `.claude/skills/inbox/SKILL.md` mirrors voice ARCH-33 adapted to `lens:bridge` — reports repo
  as the queue's source of truth, one-item-at-a-time walk, "verify the finding independently —
  never trust the triage" with this repo's gates spelled out, and the merge path doing the
  owner's ledger half (`every-task-in-the-ledger` + the DOC-12 triad); CLAUDE.md gained the
  `problem-report-inbox` invariant (non-blocking session-start check, one-line mention, silent
  gh-failure skip). **Verified live** against the private repo: both bridge-lens queues answer
  (empty — ticket #2/PR #1 are voice-lens). En route, the new DOC-12 guard caught a real
  clobber-slip (the VWB-26 DONE row initially overwrote VWB-27's line start; DUPLICATE fired
  until the active row was removed) — the triad's first live save. check_scope: 83 tasks /
  61 done, green. No backend/UI code touched.

- **2026-07-06 (DOC-12 DONE — ledger-discipline triad ported from the voice repo; 7 real violations caught + resorted)** —
  Voice-side filing (their QUAL-72/73/74, canary-verified there) accepted at intake and implemented
  in the same session at the user's direction ("we just cleaned up the mess created over the last
  2 days"). **Intake correction:** the filing's check (1) — stranded `[x]` in the active plan —
  already existed here (DOC-4's MISPLACED-status check, both directions); the actual port =
  **MISFILED** (prefix ≠ enclosing section, both files) + **OUT-OF-ORDER** (IDs ascend per section;
  sorted insert, never append), adapted to this ledger's `PREFIX —` headers with level-aware
  section tracking (a `####` runbook inside the DONE file's DOC section must not reset it — found
  while porting). **The new checks instantly caught 7 real violations from the last two days'
  tempo:** active OPS (11,7,8) + CORE (4,1); DONE VWB-17/18/19 + DOC-4 appended out of order —
  exactly the mess. One-time mechanical resort (scripted block moves, zero-entry-loss asserted:
  identical line multisets + ID counts, 24+59 entries preserved). All three checks canary-verified
  both directions. CLAUDE.md: discipline triad stated in `single-task-ledger`; the stale
  "in-flight phase rows stay DONE in place" carve-out removed (contradicted move-not-flip; phases
  long retired). Both repos now run the same ledger discipline. check_scope: 83 tasks / 60 done,
  green.

- **2026-07-06 (intake: B-11 evidence read seam accepted into VWB-28; VWB-26/28 unblocked — voice BUILD-12 shipped)** —
  Voice-side amendment (their ARCH-34, `[deferred]` v1.1) arrived as an uncommitted note on the
  VWB-28 row: factor the report collector behind **`GET /reports/evidence`** — the bundle-shaped,
  B-5-redacted evidence WITHOUT filing a ticket — so the voice collector can fold bridge evidence
  into VOICE bundles at filing time when a report looks smart-home-related. Intake verification:
  ARCH-34 confirmed on their ledger (matching the note nearly verbatim, incl. the good details —
  bridge-unreachable IS evidence, over-attach freely, bridge owns the envelope + voice pins);
  **one claim corrected** — the "UI needs an evidence preview in the dialog (§2's spirit)"
  consumer contradicts our agreed §2 ("no draft state"); B-11 was accepted **on the voice
  consumer alone**, preview noted as possible later UX. Design doc gained **B-11** + §7 build
  order + the §8 CLI trigger demoted to residual-case-only (the common case now closes
  automatically at filing time). **Side finding at intake:** voice **BUILD-12 is DONE and
  live-smoked** (`../wb-user-reports` exists with both lens files; their smoke ran
  device→ticket #2→triage→auto-opened fix PR #1) — so VWB-26's and VWB-28's `BLOCKED` markers
  were stale; both cleared (tags stay `[deferred]`; release scope unchanged). VWB-26 is
  actionable now: `lens-bridge.md` awaits our co-ownership review. No code touched.

- **2026-07-06 (VWB-27 DONE — bridge report-button design AGREED; VWB-28 filed)** — "While
  we're waiting to get unblocked" (VWB-26/28 gate on voice BUILD-12), the user pulled the
  VWB-27 design session forward: what evidence does the bridge collect when the UI
  "Report a problem" button is pressed? → `docs/design/problem_reports_bridge.md`
  (AGREED, B-1..B-10; the shared triage machinery comes from the voice ARCH-30 design
  unchanged). Interactive decisions: **B-1** scope = page-context details (entity +
  topology-neighbor configs/capability-maps/persisted-vs-live diffs) + ALL live states +
  today's backend logs; **B-2** all three ring families in v1 (backend dispatch ring +
  filtered MQTT window + browser buffers); **B-3** one trigger — the UI button with fully
  automatic collection behind `POST /reports` (the owner-CLI attach-evidence trigger
  explicitly out of v1; its handover-evidence gap recorded in the doc's §8). Session finds:
  the UI's `useLogStore` action log already exists at every dispatch site (free Tier-C
  narrative); the persisted-vs-live state diff is the natural optimistic-desync detector
  (the DRV-5 bug class); the broker password in `system.json` is the redaction hot item.
  B-4..B-10 (browser evidence set, redaction, rate limits, spool, endpoint+PAT, tunables,
  hexagonal placement) accepted as proposed. **VWB-28 filed** (implementation, `[deferred]`
  `BLOCKED` on voice BUILD-12, `config-ui-stays-functional` flagged for the new endpoint +
  config section). No code touched.

- **2026-07-06 (intake: VWB-26 + VWB-27 — problem-reporting participation, filed by wb-mqtt-voice)** —
  Voice-side filing (ARCH-30, design AGREED same day: `problem_reports.md` — private
  `wb-user-reports` triage home, one-Claude-two-lenses, handover-by-label) arrived uncommitted
  under the ID "VWB-25"; intake verification per `cross-repo-source-of-truth` confirmed every
  claim against the design doc + the voice ledger (ARCH-31/32/33 + BUILD-12 all `[release]`
  there) but caught an **ID collision** — VWB-25 was assigned to the wardrobe-alias task hours
  earlier (`check_scope` failed on the duplicate; the filing was made from a stale ledger view).
  **Accepted with corrections (user-confirmed):** renumbered → **VWB-26** (`[deferred]`,
  `BLOCKED` on voice BUILD-12 — no repo/labels/lens-draft to act on yet; explicit
  pull-into-`[release]` candidate if the voice release lands while our gate is open); the folded
  "LATER" UI report-button item split out as **VWB-27** (design task per `design-then-implement`;
  bridge bundle specifics are out of ARCH-30 v1 by its §11). The voice repo's stale "VWB-25"
  back-reference in its doc map is theirs to fix (one-way sync). No code touched.

- **2026-07-06 (REL-1 DONE — release 1 defined + signed off; open questions closed; VWB-25; journal rotated)** —
  Interactive session (user-requested: "address open questions one-by-one and define release 1
  gates in the spirit of the voice project"). **The definition** now heads `action_plan.md`:
  scope gate = every `[release]` task `[x]` + `check_scope.py` clean; artifact = version tag +
  armv7 GHCR images deployed on WB7 via `ops/` compose serving the house; 7 exit criteria.
  **Tag migration:** `[release]`/`[deferred]` replaced `[house]`/`[later]`/`[parked]` (remap +
  per-row verification; DRV-5, OPS-8, VWB-16 individually pulled INTO release scope).
  **Questions walked (11 rounds):** the 7 survey-era "Open questions" all closed (6 by events —
  monorepo, WB7 target, Layer-3/manifest, drivers-have-IDs, `device_category` drives UI nav —
  1 by decision: armv7-only, platforms = release 2); `/action` stays the documented internal
  door (CORE-4 filed `[deferred]` for the full demotion); DRV-3/DRV-8/children's-round-3
  deferred; alias tails settled — bedroom «шторы» correct as-is, global masters deferred,
  **wardrobe gains «свет» → VWB-25 filed + executed** (`wardrobe_spots` aliases; golden
  re-dumped `acc1e18beb3f204a`); docs-accuracy IS a gate → **REL-4 filed** (DOC-11 folded in).
  **New rows:** REL-2 (WB7 cutover — the ID-less load-bearing debt is now scope-gate-visible),
  REL-3 (converged rack pass — SCN-6 cards + two-room drill + HVAC canonical check +
  acceptance-gate items 4½/5), REL-4, CORE-4, VWB-25 (done). Acceptance-gate section annotated
  as absorbed. **Journal rotated** (first archive: `docs/archive/journal/2026-05-23_2026-06-08.md`,
  1595 → ~810 active lines + pointer). check_scope after: 79 tasks / 58 done.
  *Amended same day (user question "are the REL tasks gated?"): the inter-task gating — previously
  prose inside the REL-3/REL-4 rows — made explicit as an **Ordering table** in the definition
  block (REL-2 = root; DRV-5/OPS-8 ungated; DRV-1/2 + SCN-3 rack-gated but NOT REL-2-gated;
  VWB-13 ← REL-2; VWB-16 ← voice TEST-18; REL-3 = convergence; REL-4 ← REL-3; tag ← all + VWB-16).*

- **2026-07-06 (UI-9 DONE — dropdown seam canonical; `/action` demotion decision unblocked; DOC-11 filed)** —
  Flipped the last first-party `/action` writer. `DropdownConfig` swapped the native trio
  (`set_action`/`set_param`/`api_action` — the last was dead since SCN-7's options endpoint) for the
  canonical tuple (`canonical_capability`/`canonical_action`/`canonical_param`); `_inputs_dropdown`
  emits `input.set {value}` for BOTH select forms (the VWB-19 route) with **by_value option ids now
  the table keys** (`cd`, not `input_cd`); `_apps_dropdown` emits `apps.launch {app}`.
  `useInputSelection`/`useAppLaunching` dispatch `POST /devices/{target}/canonical` with
  `wait:false` (button parity) — the "commands"-mode option-id-is-a-command special case is gone;
  scenario pages keep targeting the dropdown's `sourceDeviceId` (role device) since `apps` is not
  proxy-inheritable, matching the read side. openapi regenerated + contracts copy synced (golden
  byte-unchanged — manifests aren't catalog surface). 4 new layout-engine tests (tuples; by_value
  ids round-trip through `CapabilitySelect.expand`); suite **571**, pyright 0, contracts 3/3, UI
  check + build green. Docs: `canonical_first.md` §11.3 → SHIPPED (+header/§8 row),
  `ui_backend_contract.md` fate table + SCN-7 section, `ui.md` media-stack row. **Consequence: the
  §8 phase-3 `/action` demotion decision is unblocked** (acceptance-gate item 4 — decision still
  deliberately deferred to the gate pass). **Filed DOC-11**: ui.md's scenario-routing narrative
  still describes pre-SCN-6 dispatch (spotted in passing; user-facing pass, batched for later).

- **2026-07-06 (SCN-5 CLOSED OBSOLETE — task-start-reconciliation, no code)** — Picked up SCN-5
  ("transition-aware manual notes, the activation-time half — load-bearing for LD/VHS audio") and
  the start-of-task reconciliation showed **category (c): already addressed**. SCN-2 (DONE
  2026-05-26, `79c3588`+`e7cbcb5`, UI `bd80cc5`) already shipped the load-bearing behavior the row
  claimed was missing: reconciler emits path manual-node notes at activation
  (`reconciler.py` `resolve_targets`), `ScenarioManager` holds them per room and threads them
  through `get_scenario_state()` → `/scenario/state`, UI renders the amber "For this activation"
  section; `test_transition_to_ld_surfaces_dodocus_note_on_switch_and_clears_on_deactivate` locks
  the appletv→ld transition (5 manual-notes tests green at close). The row's only unshipped
  literal ("only when its link activates" — diff-based suppression) is the phase-2 refinement
  SCN-2 deliberately declined as UX-wrong for load-bearing notes, and near-vacuous in this fleet
  (analog↔analog transitions always change the Dodocus position → the note text always changes).
  Stale-row origin: the 2026-06-30 re-ID pass rebuilt the self-referential former §5.2 #6 into an
  implementation task without re-checking SCN-2's shipped scope. **User consulted per the
  invariant; confirmed close-as-obsolete.** Row moved to `action_plan_DONE.md` with the pointer;
  the P0 band is now fully closed on the software side — remaining P0s (SCN-3, DRV-2) are
  HW-gated. HW verification of the notes on the rack still rides SCN-3's verification pass.

- **2026-07-05 (intake + executed + closed: VWB-24 — HVAC action params typed, contract v1.3)** —
  Voice-side filing (QUAL-35 Slice 2) arrived uncommitted; intake verification per
  `cross-repo-source-of-truth` confirmed every claim against the golden + live code AND found the
  root cause deeper: `CommandParameterDefinition` has no `values` field (the G4 shape again), so
  the §6 projection had nothing to project — while the read-side fields carry full ru/en/de
  triplets and the driver already translates canonical→wire (actuation always worked; only
  catalog metadata was missing). Sweep: the disease = exactly the climate quartet ×3 HVACs.
  Fix per user decision (rename approach, not a `values_from` hint): catalog projection derives
  param `values` from the **same-named enum field's table** (single authored source — the field);
  hvac profile param_map renames canonical params to the field names (`{fan: speed}`,
  `{vane: angle}`, `{widevane: direction}`; natives keep the firmware vocabulary; the rename is
  free — voice deliberately hadn't wired these params). Vane/widevane typed for free.
  `HvacPanel`'s FIELD_TO_PARAM indirection collapsed to identity. Golden `a17a63b0c47fdb53`
  (pre-pin); openapi byte-unchanged; contracts/README values-bullet extended (scrub rule
  honored). Tests: +2 derivation (test_system_catalog), +1 contract-semantics (all 3 HVACs × 4
  actions mirror their field tables), param-map assertions updated. Suite 568; pyright 0;
  contracts 3/3; UI check+build green. Voice re-pins and wires «кондиционер на охлаждение».

- **2026-07-05 (executed + closed: VWB-19 — select-form canonical routing; filed open: UI-9 —
  dropdown seam flip)** — Pulled forward from `[later]` by user decision, off the chat question
  "which task enables app launch / input selection through canonical?". Reconciliation split the
  premise first: **app launch never needed anything** (`apps.launch` is an ordinary action, LG +
  Apple TV both, routable since SCN-7); only input selection lived in `select` and was
  unreachable. Shipped per the fresh **`canonical_first.md` §11** addendum (design + code, one
  change): `set` = the reserved canonical action for select-capabilities;
  **`CapabilitySelect.expand(value)`** as the single resolution site (mirror of VWB-17's
  `CapabilityAction.expand`), the reconciler's private `_input_action` logic replaced by it;
  dispatcher routes `set` through `cap.select` when no authored `set` exists (authored wins);
  unknown/missing value → speakable `400 param_invalid` naming the valid set. Fleet fact: all 4
  parametric selects carry `list`, both by_value selects don't — so `options/inputs` gained the
  **static by_value fallback** (404'd for the amp before) and the catalog advertises `set {value}`
  with **static `values` for by_value** (zero-round-trip validation for Irene) vs
  **`options_from: "inputs"`** for parametric. The VWB-20 TV-input husk is a real catalog entry
  again. `openapi.json` byte-unchanged; golden `dbfd2855dac52026` + STAMP (pre-pin — voice pins
  current); UI types regen no-op, check+build green. New `test_select_canonical.py` (16 tests);
  suite 565; pyright 0; contracts 3/3. **UI-9 filed:** flip the Layer-3 dropdown seam (manifest
  `DropdownConfig` + `RuntimeDevicePage`) from native `set_action`/`set_param` to canonical —
  the last first-party `/action` writer, gating the §8 phase-3 demotion decision. Voice can now
  do «переключи на CD» the moment a command set wants it. **Post-commit correction (user
  flag):** ledger IDs scrubbed from `contracts/README.md` (`user-facing-docs-are-done` — task
  IDs never appear in user-facing docs; the "(contract vX, TASK-ID)" framing was the leak, twice —
  incl. the pre-existing v1.1 header; replaced by "since contract vX").

- **2026-07-05 (executed + closed: VWB-23 — room-scoped group addressing shipped, same day as
  its design)** — §10 end-to-end: `Capability.group` overlay (+ explicit-null opt-out via
  `model_fields_set`), pure `domain/rooms/groups.py` resolver, `POST /rooms/{room_id}/canonical`
  with scope `auto|all|one`, concurrent per-member dispatch through the **extracted**
  `dispatch_device_canonical` core (the device endpoint now delegates to it — one path, no
  drift), per-member `executed|no_op|skipped|failed` results, speakable
  `no_group_members`/`no_default_device`/`fanout_not_allowed`, allow-list `{light, cover}`.
  Config: `power_switch` split (oven_power + all_plugs re-pointed; the other 23 light_switch
  users audited as genuine lights), 3 illumination profiles tagged `group: "light"`,
  **`group_defaults` authored per user decision — every room's `light` defaults to its
  `<room>_spots` (10/10 regular), `global` deliberately none** (its group resolves to the
  `all_lights` master). RoomManager validates defaults at load (drop + error-log). Catalog:
  always-explicit `CatalogCapability.group` + `CatalogRoom.group_defaults`; golden
  `91909b54bfb4b593` (pre-pin, v1 carries it); UI types regen, check+build green. New
  `test_room_canonical.py` (17 tests); suite 548; pyright 0 (after one duck-typing return-type
  fix); contracts 3/3. Docs: `interfaces.md` row + `rooms.md` voice-flow rewritten to bridge-side
  resolution (old text described a never-built client-side `default` lookup). Voice side can now
  fire «включи свет» as one call and speak an honest confirmation from the results list.

- **2026-07-05 (filed + closed: VWB-22 — group-addressing design; filed open: VWB-23 —
  implementation)** — The voice side's open question ("what should «включи свет» / «закрой шторы»
  do?") ran as a discussion session and settled into `canonical_first.md` **§10**: a third
  canonical address form `POST /rooms/{room_id}/canonical {group, action, scope}` — Irene resolves
  only as deep as the utterance specifies, the bridge owns membership + default-vs-fan-out policy
  (the ScenarioProxy precedent generalized). Key discovery during the session: the fleet's 36
  light switches declare domain **`power`** (only the hood has `light`), so the naive
  domain-as-membership rule would sweep sockets and the oven guard into «свет» — hence the
  **`group` overlay** (capability-level tag defaulting to the domain name; 3 illumination
  profiles override with `group: "light"`), chosen over a `power→light` re-profiling (rejected:
  reconciler/layout/WB-service all key on `power`). User-shaped middle ground: `scope: auto`
  prefers a room-configured default device (`group_defaults` in `rooms.json`) else fans out;
  `all` preserves the plural signal; fan-out allow-listed to `light`+`cover` only. Aggregate
  response lists per-member outcomes so voice confirmations stay honest. All contract impact
  additive; pre-pin landing preferred. Implementation = **VWB-23** [P1], filed per
  `design-then-implement`.

- **2026-07-05 (filed + executed + closed: CORE-3 — maintenance guard rebuilt against the real
  midnight burst)** — Started as a "not ledger-worthy yet" diagnosis request ("skips MQTT events
  around midnight... find out what is wrong"), promoted to CORE-3 once the user said fix it. The
  investigation went to the controller itself (SSH, user-granted): the midnight event is the
  user's **own root crontab** — `0 0 * * * systemctl restart wb-rules` (the classic hang
  workaround) — not logrotate; the journal-measured burst runs ~00:00:05 (driver ready,
  `meta/driver` republished) → 00:00:10+ (rule files loading one by one, every virtual device +
  value republished, side-effect writes trailing), so the old fixed 5s window closed mid-burst.
  Second defect, log-proven from 2026-06-06: the trigger topic is retained, so the broker's
  subscribe-time replay opened a bogus window at every bridge connect and ate startup topics.
  Third: the retained-skip can't cover any of this — live republishes arrive retain=0 per
  [MQTT-3.3.1-9]. Fix: retain flag plumbed into `maintenance_started`; live-only trigger;
  sliding quiet-time window (config `duration: 5` unchanged, new quiet-time semantics) with a
  60s hard cap so periodic publishers can't wedge it open. 9 new fake-clock tests; no
  OpenAPI/contract impact (DTO untouched). Controller cleanups left with the user by their own
  call: delete the broken `@reboot` rule (`enable_online_meta_for_wbrules` — wb-rules cron
  rejects `@reboot`, error spam on every load); telegram2wb curl-35 + IR_Trainer datatype warts
  flagged. Suite 531; pyright 0; contracts 3/3.

