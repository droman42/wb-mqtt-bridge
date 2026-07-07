# Action Plan — Journal

**Status:** Living dated record of work done on the wb-mqtt-bridge monorepo. Extracted from
`docs/action_plan.md` §6 on 2026-06-06 — the plan was growing too quickly and the dated
history is intrinsically append-only, so it lives on its own from here. **Newest entries on
top.** References elsewhere in the plan ("see §6 (2026-05-25)" etc.) remain valid and now
point at the dated entry below.

`docs/action_plan.md` stays the master driving document (forward work + an index of recent
journal entries in §6). This file is the long tail.

**Archive pointer:** entries older than 2026-06-09 are frozen in
[`docs/archive/journal/2026-05-23_2026-06-08.md`](archive/journal/2026-05-23_2026-06-08.md)
(first rotation 2026-07-06, per the `one-active-journal` high-water rule; append-only, grep
when a `task-start-reconciliation` trail points there).

---

**Note on IDs (2026-06-30):** the ledger was re-IDed to the `PREFIX-N` workstream scheme (DOC-9). This
journal's **earlier dated entries keep their original positional refs** (`§P3.7 #19`, `§5.1 #7`, `P4 #7`,
etc.) — they are historical and resolve via [`action_plan_aliases.md`](action_plan_aliases.md). New
entries use the new IDs.

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

- **2026-07-04 (executed + closed: VWB-21 — the alias vocabulary, 3 rooms + 34 devices)** — The
  interactive session ran in 5 rounds with a new shape: inventory presented room-by-room WITH
  candidate synonyms to react to (lower recall burden than blank-slate); terse positional answers.
  Rooms: зал, сынарник (the family word for детская — unfindable by any model), квартира. Devices:
  the cross-room staples (телек/кондей/радиаторы/эппл per room), усилок/катушечник/видик/сервант/
  фартук/жалюзи/треки/полки/тумбочки/шторы, ночники (the SCONCES — user corrected the guess), «пол»
  generalized to all 5 heated floors on explicit confirmation. Collectives placed on every member
  (шторы/жалюзи/треки) — disambiguation is Irene's concern, the catalog records the truth. Open
  tails in the authoring log §6: bedroom tulle left un-aliased, гардеробная + global masters
  unconfirmed candidates for a later iteration. Golden `7a1149c7657a2f7f`; suite 522; drift guard
  green. **The VWB-15 promise "names + aliases" is now fully delivered; the voice side's resolver
  has real household surfaces.** Remaining voice-side bridge work: VWB-16 (crossover fixtures) +
  VWB-13 (live sweep).

- **2026-07-04 (filed + executed + closed: SCN-8 — the flat scenario `name` dropped, `names` is the one surface)** —
  User asked "why do we need `name` at all?" right after VWB-20 gave scenarios localized `names` —
  and the answer was: we don't. Only two consumers existed, both better served: the scenario
  manifest title (now `names.ru`, matching device manifests) and the UI's `useDataSync`, which had
  been FAKING localization from the flat string with the comment "API doesn't seem to have
  translations yet" — now consuming real ru/en, so the navbar finally shows «Кино с Apple TV» to
  the Russian-speaking household. Done the same day `names` was born, so no third naming dialect
  ever shipped (the device `device_name` → `names` migration precedent, followed to the letter).
  9 configs dropped `name`; ~12 test fixture sites swept; golden catalog content UNCHANGED (labels
  already flowed from `names`); openapi + pin + UI types regenerated. Suite 522; pyright 0;
  contracts 3/3; UI green.

- **2026-07-04 (executed + closed: VWB-20 — contract patch v1.1, PRE-PIN; voice may pin)** — Landed
  hours after filing, inside the shape-change window. **G1:** typed `CatalogParam`
  (…/`unit`/`values`/`options_from`) replaces the schema-free dicts; both producers unified (the §6
  projection emits the full shape; the hand-built `scenario.set` constructs the model explicitly).
  **G3:** `ScenarioDefinition.names` (LocalizedName; flat `name` = en fallback) + ru names
  auto-translated for all 9 scenarios («Кино с Apple TV», «ТВ через колонки», …) — user corrects
  wording at leisure, the drift guard forces re-dumps; the scenario enum labels now ru+en. **G4
  root-caused deeper than the review:** `CommandParameterDefinition` had NO `units` field — authored
  units were silently dropped at typed-config parse; field added, **28 params authored** (°C ×9,
  % ×13, dB, min), `_spec_dict` projects `unit`; bonus: the eMotiva WB `set_volume` control meta now
  carries `units: dB` (oracle re-captured; single-line diff verified before accepting). **G5
  corrected:** `options_from: "apps"` hint at SCN-7's options endpoint — the open-set pattern
  documented in `contracts/README.md` §Param semantics. **G2 schema half:** `aliases` on config +
  contract models, projected when authored (null until VWB-21). **Minor:** empty capability husks
  suppressed (locked by test; reappear with VWB-19). 4 new contract-semantics tests; suite **522**;
  pyright 0; contracts 3/3; golden v `31660f66f000d2ea` + STAMP + openapi + pin + UI types
  regenerated; UI green. **TEST-17 may pin now.** Next: VWB-21 (alias vocabulary, interactive).

- **2026-07-04 (filed: VWB-20 + VWB-21 — the voice review's contract gaps, pre-pin patch + alias session)** —
  Hours after VWB-15 landed, the wb-mqtt-voice-side Claude reviewed `contracts/` and surfaced five
  gaps; all verified against live code at intake (`cross-repo-source-of-truth`): **G1** confirmed
  and worse than stated — `CatalogAction.params` is schema-free AND its two producers emit
  *different* dict shapes (the §6 projection vs the hand-built `scenario.set`); **G2** confirmed —
  no aliases anywhere, despite VWB-15's own task text promising them (honest miss); **G3**
  confirmed at the root — `ScenarioDefinition.name` is a single English string, so the flagship
  scenario feature has no Russian voice surface; **G4** confirmed both halves — `_spec_dict` drops
  `units` (data path exists — the WB service reads it) and the HVAC `temp`-param/`setpoint`-field
  join is broken; **G5** problem confirmed but the proposed static-enum remedy REJECTED — the app
  set is runtime-dynamic, the fix is documenting it open + an `options_from` hint at SCN-7's
  options endpoint; the **minor flag** (TVs' empty `input` capability husk) is VWB-19's select-form
  gap showing through the projection, annotated there. **Filed: VWB-20** `[P1][house]` — the
  contract patch (typed `CatalogParam` with unit+values, scenario localized names, G5 doc + hint,
  G2's schema half, the empty-husk decision) — **sequenced PRE-PIN**: land before voice's TEST-17
  pins its copy, the cheapest shape-change window there will ever be. **VWB-21** `[P1][house]` —
  the alias-vocabulary authoring session (interactive; the household's actual spoken names are
  user knowledge — cannot be done solo). Analysis only today; neither started.

- **2026-07-04 (executed + closed: VWB-15 — the catalog contract artifacts; the pre-catalog chain is COMPLETE)** —
  The voice unblock, landed the same day the chain was sequenced. Repo-root **`contracts/`** now
  carries the contract of record: `catalog.golden.json` (79 devices / 11 rooms — globals + the
  scenario manager entity with its 9-scenario enum), the pinned `openapi.json` (byte-identical to
  the UI copy), `STAMP.json` (commit + version + content-hash), and a README with the consumption
  rules (one-way outward sync — the voice side pins its own copy). New **`wb-catalog`** CLI builds
  the golden **offline and deterministically** (typed configs + capability maps + rooms + scenario
  definitions through lightweight stand-ins; no drivers, no network; byte-identical across runs) —
  the morning smoke run had already proven the controller isn't needed for this. **The §6 param
  projection went live in the catalog**: `CatalogAction.params` filled (canonical names via reversed
  `param_map`, native-spec constraints, fixed params excluded) — hood `fan.set level 0–4`, HVAC
  `set_setpoint temp 16–31 °C`, eMotiva `volume.set level −96…0 dB` — discharging the owed #19
  stub. **The drift guard is a test** (`test_contracts_golden.py`) inside the normal backend CI
  job, with `contracts/**` added to the CI backend path filter; CONTRIBUTING documents the regen
  commands. **Owed tail:** the real-WB7 deployment-drift dump waits on the ops compose cutover
  (recorded in the DONE row + contracts/README). Suite 518, pyright 0, contracts 3/3. **The ball
  is now in `wb-mqtt-voice`'s court: TEST-17 pins the artifacts and parses the golden.** Remaining
  bridge-side voice work: VWB-13 (live sweep, pairs with the WB7 dump session) and VWB-16 (the
  crossover-fixture consumer test, now unblocked by this artifact).

- **2026-07-04 (executed + closed: SCN-7 — canonical-first phase 2, device pages on the canonical grammar; filed VWB-19)** —
  Third link of the pre-catalog chain, closing the coding road to VWB-15. Device manifests now
  annotate every action-backed control with its canonical tuple (no `sourceDeviceId` — the target
  is the device itself); `RuntimeDevicePage` dispatches annotated controls canonically with the new
  **`wait: false`** mode (fire-and-return-current-state — preserves the pre-canonical `/action` UX
  exactly; voice keeps the default echo-wait; HvacPanel keeps `wait:true` for its cache merge; the
  scenario page's inherited controls also switched to `wait:false`). Option enumeration became a
  READ: `GET /devices/{id}/options/{inputs|apps}` resolves the capability's `list` query internally
  (`source="system"`); the UI dropdowns fetch it instead of POSTing `get_available_*`. The §6
  param projection landed as the shared `param_projection.py` — native view feeds the manifest's
  `ProcessedParameter` (capability-fixed params excluded from specs), canonical view (reversed
  `param_map`, sequence union) awaits the catalog in VWB-15: one code path, two views. **Finding →
  VWB-19 filed:** `select`-form capabilities (parametric + `by_value` input selection, app launch)
  are not canonically routable — the dispatcher walks `cap.actions` only; dropdown *selection*
  stays native and voice can't switch inputs canonically; `[P2] [later]` (v1 voice set needs no
  input switching; catalog advertises no select actions today, so the crossover fixtures are
  unaffected). Gates: suite 515, pyright 0, contracts 3/3, contract + UI types regenerated, UI
  check + build green. Docs: `ui_backend_contract.md` phase-2 section; `interfaces.md` canonical
  row (+`wait`) and the options-endpoint row. **The chain's coding legs are DONE — VWB-15 (the
  first golden dump) is next and unblocked.**

- **2026-07-04 (VWB-17 addendum: sequence actions in the user-facing docs)** — User ask right after
  the close: teach sequence-form actions in prose. `key-concepts.md` gained a "Sequence actions
  (macros)" subsection under the capability-map chapter — two theoretical worked examples (LD-player
  wake→tray with an inter-press gap; an amp's mode→confirm dance), the failure semantics ("names
  exactly which step broke"), and the callers-never-see-the-choreography framing. While there:
  `interfaces.md`'s devices REST table was missing the `/devices/{id}/canonical` row entirely —
  added (capability-language dispatch, sequence expansion, echo wait, the Scenario Manager seam).

- **2026-07-04 (executed + closed: VWB-17 — sequence-form actions through the canonical seam)** —
  Second link of the pre-catalog chain, same-day follow-through after SCN-6. Reconciliation surprise:
  the router docstring's "the reconciler path handles those" was false — **nothing executed
  `CapabilityAction.sequence` anywhere** (only the exposure walks read it), so this introduced
  sequence execution for the first time. Shipped as ONE shared translation point:
  `CapabilityAction.expand(params) → List[NativeStep]` on the domain model (command form = one step;
  sequence form = recursive flatten, each step applying its own `param_map`/fixed params to the same
  incoming params) + a new additive `delay_after_ms` step field (IR macros need inter-press gaps).
  The canonical endpoint's sequence-500 branch became a unified step loop (single command = one-step
  sequence; mid-sequence failure names `step i/N (<command>)`; `no_op` short-circuit restricted to
  single-step; echo-wait semantics unchanged — waiter before step 1, awaited after the last).
  `ScenarioProxy.execute` rides the same expansion, so WB-card pushbuttons backed by sequences work
  too. `openapi.json` verified byte-unchanged. 7 new tests (`test_canonical_sequence.py`); suite
  **509 passing**, contracts 3/3, pyright 0 (run locally per the new gate discipline). Ripples:
  VWB-16's sequence caveat RESOLVED, SCN-7's gate SATISFIED — **SCN-7 is next in the chain.**

- **2026-07-04 (executed + closed: SCN-6 — canonical-first phase 1, the per-room scenario proxy seam)** —
  Same-day implementation of the morning's SCN-4 design; three commits. **`17f2ded` per-room domain
  state:** the `current_scenario` singleton became `active: Dict[room, Scenario]` — two rooms now run
  scenarios concurrently; per-room persistence keys (`active_scenario:<room>`) with a one-shot legacy
  migration; room-scoped switch diffs and `deactivate(room)`; `room_id` now load-mandatory;
  `/scenario/state?room=`; SSE payloads carry `room_id`. **`168f820` the proxy seam:** pure-domain
  `ScenarioProxy` — `scenario_manager_<room>` entities with fire-time role→device resolution
  (409 `no_active_scenario`/`role_unbound`), `scenario.set/off` activation, config-static union
  advertisement; the canonical endpoint recognizes entities before device lookup and inherited
  domains fall through the existing echo-waiting dispatch with `executed_on` naming the real target;
  the catalog gains one entity per room (byte-stable across switches — locked by test); one WB
  «Сценарии» card per room (retained `scenario` value topic driven by the new `on_active_changed`
  observer + curated transport pushbuttons); bootstrap wires it all (the WB-re-key placeholder
  comment finally replaced by its clean successor). **UI cutover (this commit):** the scenario
  manifest carries `canonicalEntityId` + per-control canonical annotations; `RuntimeScenarioPage`
  dispatches everything through the entity (power zone → `scenario.set/off`; bridge resolves at
  fire time — the stale-manifest targeting quirk is gone); un-annotated controls (list queries)
  keep the per-device fallback until SCN-7. Contract regenerated; UI check + build green; suite
  502; contracts 3/3. Docs: key-concepts, devices-and-scenarios, interfaces, ui_backend_contract.
  **HW verification owed** (WB cards + two-room drill at the next rack session). Next link of the
  pre-catalog chain: **VWB-17**.

- **2026-07-04 (sequencing: the pre-catalog chain — SCN-6 → VWB-17 → SCN-7 → VWB-15)** — User
  directive: the scenario tasks designed today **finish before the first catalog dump**. SCN-7
  `[later]` → `[house]`, VWB-17 `[later]` → `[house]`; VWB-15's "additive, doesn't wait" sequencing
  note replaced with the deliberate chain (v1 of the pinned contract carries the
  `scenario_manager_<room>` entities + the final canonical-first grammar; VWB-16 fixtures cover
  scenario commands from day one; no post-pin churn). `canonical_first.md` §8 contract-timing note
  revised to match. Cost accepted knowingly: the voice repo's TEST-17 unblock now waits on the full
  chain. Mechanical additivity + the drift check still govern everything after the v1 pin.

- **2026-07-04 (deferred: VWB-12 — MSW sensor side → post-release, both repos)** — Pre-work analysis
  ran in chat, then the user deferred: `[P1] [house]` → `[P2] [later]`. The analysis stands recorded
  for the pickup: the MSW modules serve two roles — IR blaster (used today purely as transport:
  47/16/2 topic references to `wb-msw-v3_207/218/220` from AV configs, no bridge device) and
  multi-sensor (un-onboarded except the sauna's `wb-msw2_100`). Recommendation when resumed:
  **split entry** — per-room sensor passthrough devices on the `sensor_room` profile (partial
  mirrors, sauna precedent), IR stays plumbing (module-is-wiring precedent — relay modules host six
  lights without being devices); a module-level IR entity remains addable alongside if DRV-3's
  IR-learning page ever wants one. Standing warning kept: verify sensor control names per module
  firmware before authoring. Voice side defers its sensor state-query feature equally (their
  ledger, their entry).

- **2026-07-04 (executed + closed: VWB-10 — the global room: 8 devices, 5 profiles, all_lights rule drafted)** —
  Interactive session; the user redefined scope at start (not just aggregates — the existing global
  fleet too). **Hybrid process, both halves now recorded in `docs/wb_device_authoring_log.md` §6:**
  existing controller devices rode the classic paste flow (WB-UI widget JSON → terse Q&A → config +
  profile); the `all_lights` aggregate inverted it — the bridge config *defines* the contract
  (`/devices/all_lights/controls/power`, wb-rules virtual device to be deployed) and
  **`wb-rules/all_lights.js` was drafted** (virtual device + fan-out over all 36 true lights
  harvested from the light_switch/dimmable_light configs; deployment = user tech debt, now written
  down instead of owed). Onboarded: `all_lights`, `all_plugs`, `oven_power` (light_switch reuse),
  `cleaning_mode`, `heating_control`, `water_supply`, `seasonal_mode`, `home_mode` (new profiles for
  the last five; `presence.away` flagged as the highest-consequence future voice command).
  `all_blinds` not shipped — absent from the voice command set. Convention correction mid-session
  (now a memory + log rule): **passthrough capabilities are ALWAYS profiles**, even singletons;
  `capabilities/devices/` stays IR/AV-only. Suite 488 green after every device; ledger: VWB-10 →
  DONE. The `global` room is no longer conceptually empty — the VWB-13 catalog sweep and the VWB-15
  golden both get a real whole-house section now.

- **2026-07-04 (amendment: per-room Scenario Managers — `canonical_first.md` §3/§4, SCN-6 rescoped)** —
  User's note right after SCN-4 closed: there will be **two scenario sets** (living room now, children
  room in a future round) with **concurrently** active scenarios. The design's mechanisms generalize —
  the singleton becomes **one manager entity per scenario-bearing room** (`scenario_manager_<room_id>`,
  catalog `room` set → Irene's existing room disambiguation covers «включи кино в детской» and makes
  «громче» unambiguous with two rooms active; one WB card per room). The real gap was the domain layer:
  today's `ScenarioManager` holds a single global `current_scenario` + one persisted key, so a second
  room's activation would read as a cross-room switch and power the first room down. Folded into the
  doc (entities-per-room, room-scoped resolution, the domain prerequisite) and into **SCN-6**'s
  deliverables (per-room active map, `active_scenario:<room_id>` keys + one-shot legacy migration,
  per-room deactivate, in-room-only transition diffs). Room-purity was already enforced by the
  room-membership validator — that invariant is what makes per-room concurrency safe.

- **2026-07-04 (design decided + closed: SCN-4 → `docs/design/canonical_first.md`; filed SCN-6 + SCN-7)** —
  The mandatory scenario↔Wirenboard design discussion ran as an interactive session and **outgrew the
  original question into the target actuation architecture**. Reconciliation first narrowed SCN-4: its
  recorded tie-ins (Layer-3 rendering, manual-steps surfacing) had already shipped, leaving purely the
  representation question — which now has two consumers: the WB ecosystem (incl. the future WB-native
  Alisa bridge, the project's declared Yandex path) and Irene (REST canonical against the catalog; her
  repo explicitly flags SCN-4 as able to reshape catalog actuation targets). Decisions, each driven by
  a user call: **(1)** option (b) — one Scenario Manager WB device with an enum select over scenario
  ids; **(2)** inherited commands (громче/pause) fire at the same entity as canonical commands,
  resolved role→device **bridge-side at fire time** (static-union catalog advertisement keeps the
  catalog byte-stable; speakable 409s); **(3)** the user's unification: the UI scenario page rides the
  SAME proxy (manifest = pure render projection; the page's power zone becomes `scenario.set/off`;
  write-proxy/read-direct); **(4)** the user's second push — device pages too: the exposure gate had
  already made page surface ≡ capability surface, so **canonical-first** becomes the target — catalog
  (read) + canonical (write) + state/SSE (read) as the ONE client contract for UI, voice, WB card;
  `/action` demotes to internal; VWB-17 re-scoped from voice-only future-proofing to the gate of the
  device-page phase; **(5)** param metadata derived, not authored — native config param specs projected
  through the capability `param_map` (+ value-label enum tables), one projection function feeding both
  catalog and manifest; discharges the catalog's owed #19 param-introspection stub and rides VWB-15.
  Verified along the way: manifest buttons speak native today (`layout_engine.py` `_action`); zero
  sequence-form actions in all shipped maps (the manifest builder skips them too — parity exact);
  canonical grammar (`{capability, action, params}` + `param_map`) expressive enough for selects/
  params/zones. Ledger: SCN-4 → DONE (design deliverable per `design-then-implement`); **SCN-6**
  (phase 1: proxy seam) + **SCN-7** (phase 2: device pages, gated on VWB-17) filed; VWB-15 + VWB-17
  annotated; the design doc registered in the §0 document map. No code shipped — design only.

- **2026-07-04 (filed + executed + closed: DRV-9 — kitchen_hood capability map)** — Interactive
  session at the user's direction ("right now, don't want to wait for the entire DRV-1"); closes the
  coverage gap CORE-2 surfaced this afternoon. Three design decisions put to the user, all resolved
  to the recommended option: **(1)** domains `light` + `fan` (not `power`+fan — the appliance's power
  is neither function, so a generic power-off can never half-kill it); **(2)** fan as parametric
  `set(level 0–4)` + `off` shortcut (the `brightness.set` precedent, not enum-select); **(3)**
  `reconcile: false` on both (upscaler precedent — appliance-only, no topology path, reconciler
  hands off). Authored `config/capabilities/classes/BroadlinkKitchenHood.json` with the enum triplet
  (`on`/`off` + ru/en labels) on the mirrored `light` field and an int `speed` field for the catalog.
  WB output stays byte-identical (explicit `wb_controls` keep meta precedence — locked by the
  existing `test_wb_rekey` oracle row). New shape test; suite 488 passing, contracts 3/3.
  **Milestone:** every shipped device instance now resolves a capability map (5 AV classes + 5 IR
  device maps + 57 profiled passthroughs + hood) — acceptance-gate item 1 annotated satisfied for
  the current fleet. Stale "capability-less kitchen_hood" comments corrected in `wb_device/service.py`
  and `devices/base.py`.

- **2026-07-04 (executed + closed: CORE-2 — dead-code sweep)** — Same-day execution of the sweep
  filed this morning. **Removed:** the entire legacy imperative scenario path (`scenario.py` shrank
  ~330 lines: startup/shutdown executors, string-condition evaluator, `_validate_parameters` and its
  sequence/condition validator callers, `_is_power_command`), the `WB_SCENARIO_RECONCILER`
  kill-switch (`switch_scenario`/`deactivate` are reconciler-only; the already-active early return
  aligned to the reconciler result shape — no consumer read the legacy keys), the `CommandStep`
  model + the `startup_sequence`/`shutdown_sequence` escape-hatch fields (contract regenerated:
  `openapi.json` −76 lines; UI types regenerated + dead `CommandStep` alias dropped from
  `ui/src/types/api.ts`; `npm run check` + build green), the vestigial scenarios `DeviceState.output`
  field, and the Phase-B `log_migration_guidance()` shim. **New guard:** scenarios must declare a
  thin `source` — a sourceless scenario is rejected at load (Bug-2 non-fatal skip) since it could
  never activate. **Two filing-text corrections discovered mid-task:** (1) `DeviceState.output` was
  alive after all (the filing grepped only the devices models; the field lived in the *scenarios*
  models — now actually removed); (2) the "`group` transitional fallback" is a misnomer — the config
  `group` field is already extinct repo-wide; what exists is the capability-less WB classification
  path, which stays (live for `kitchen_hood`, which has no capability map — the gate-item-1 coverage
  gap, owned by the DRV-1 kitchen_hood row / VWB-13 — and for the state-field→control mapping that
  enumerates controls without capability context). Its lying "legacy config group" docstrings were
  corrected instead. **Tests:** legacy tests removed / rewritten to thin fixtures; manager tests now
  cover manager-level behavior only (transition content stays with the reconciler suite); suite 487
  passing (was 502 — delta = deleted legacy tests), import contracts 3/3. Architecture docs' legacy-
  path passages removed (`key-concepts.md`, `devices-and-scenarios.md`). Acceptance-gate item 4
  annotated: sweep half DONE, "thorough code review" half remains with the gate.

- **2026-07-04 (filed: CORE-2 — dead-code sweep, scoped against live code)** — Chat analysis of the
  deferred-removal markers scattered across the ledger + design docs, reconciled against the codebase.
  Key finding: the acceptance-gate item-4 list's recorded gates ("all scenarios thin", "Layer 3
  authoritative") are **both already satisfied** — all 9 scenario configs are thin, and the Layer-3
  oracle retirement (2026-06-09) already removed two of the list's entries (UI scenario-inheritance
  duplicates + build-time generators; `DeviceState.output` is likewise already gone). What remains
  alive and swept into CORE-2: the legacy imperative scenario path + string-condition evaluator +
  `_validate_parameters`, the `WB_SCENARIO_RECONCILER` kill-switch (guards a fallback thin scenarios
  can't execute), the `ScenarioDefinition` escape-hatch fields (contract-visible → UI regen in the
  same change), the `group` transitional fallback in `wb_device/service.py` (conditional on the
  gate-item-1 capability-coverage check), and the Phase-B `log_migration_guidance()` shim.
  Delegations recorded: `MQTTClient.stop()/start()` shims → CORE-1 (its `/reload` rewrite owns the
  one live caller); piwheels `pip.conf` → OPS-11. Real sequencing constraint is gate item 5
  (cleanups regress → sweep before/with the DRV-1/SCN-3 rack passes). Filed `[P1] [house]`;
  implementation not started.

- **2026-07-02 (filed: OPS-11 — multi-arch images for the next-gen Wirenboard, deferred)** — Analysed
  what aarch64 support takes, prompted by `wb-mqtt-voice`'s three-target build matrix. Key finding: the
  bridge doesn't need the voice repo's per-target Dockerfiles/image names (theirs are forced by
  per-platform ML profiles) — identical images on both arches mean buildx **multi-platform manifests**
  under the *existing* tags (WB7 pulls armv7, WB8 arm64; `ops/` untouched). ~6-line diff: `platforms`
  list + drop the now-harmful `ARCH=arm32v7` build-arg + `--platform=$BUILDPLATFORM` on the UI's node
  build stage (arch-independent `dist/` → node build runs natively once; existing armv7 UI build should
  drop from ~14 min to ~2-3 min as a bonus). Implementation deferred at the user's direction — no WB8
  hardware to verify against yet.

- **2026-07-02 (filed + executed: OPS-10 — path-filtered CI)** — Borrowed the `changes`-job pattern from
  `../stockvision/deploy.yaml` at the user's request: `build-arm.yml` now opens with a
  `dorny/paths-filter@v3` job whose `backend`/`ui`/`ledger` outputs gate the fast checks.
  `backend-test` ← `backend/**`; `ui-validate` ← `ui/**` + the consumed backend contract
  (`backend/openapi.json`, `backend/config/**`); the scope guard became a standalone `ledger-guard` job
  gated on `docs/**` + `scripts/check_scope.py` (it previously rode `backend-test`, which docs-only
  commits — exactly where drift lives — would now skip). Docs-only ledger commits drop from full
  pytest + UI build to the ~10 s guard. `workflow_dispatch` gained `build_backend`/`build_ui` toggles
  (defaults preserve the old both-images behavior) and forces the matching fast checks so the image
  builds' `needs` gates stay satisfiable; per-event concurrency cancellation added (pushes can't cancel
  a dispatched image build). CONTRIBUTING §CI + the CLAUDE.md scope-guard pointer updated. Verified on
  the landing push: workflow+docs changes → all three filters true → all fast jobs ran green.

- **2026-07-02 (filed + executed: OPS-9 — docker_manager leftovers retired)** — Answering deployment
  questions in chat surfaced three tails of the 2026-05-26 GHCR/compose migration (OPS-3/OPS-4): the
  untracked local `ops/docker_manager_config.json` still carried the live GitHub PAT (never committed —
  gitignored; deleting it produces no git diff), `backend/README.md` still walked the retired
  manage_docker/artifact flow at length (~460 lines, ~30 references), and `ui/README.md` described the
  artifact `gunzip`/`docker load` flow with two dead `ui/docs/deployment*.md` links plus stale
  pre-monorepo "sibling checkout" instructions. Filed OPS-9 and executed in the same session: local
  config file deleted, both READMEs rewritten to the current strategy (CI → GHCR tags
  `latest`/`sha-<short>`/`vYYYYMMDD-<short>`; WB deploy = `ops/docker-compose.yml` + systemd +
  `ops/update.sh`; runbook = `ops/INSTALL.md`), lean-image subsection kept, UI local-build instructions
  corrected to the monorepo-root context. `ops/INSTALL.md` untouched (its docker_manager mentions are the
  intentional cutover content). **Outstanding user action: revoke the orphaned GitHub PAT** (Settings →
  Developer settings → Personal access tokens) — nothing uses it anymore. Docs-only; scope guard clean.

- **2026-07-02 (accepted + executed: VWB-18 — restart-durability triad)** — The voice side filed
  VWB-18 off its QUAL-56 durability review (`wb-mqtt-voice/docs/review/faf_durable_execution_review.md`
  Part 2/F7, uncommitted for review). Intake verification confirmed all three claims against live code
  (line refs exact) and surfaced an **aggravation**: `initialize_devices()` persisted each set-up device's
  boot-default state *before* the old restore stub ran, so the last-good snapshot was clobbered at every
  boot — any restore at the stub's call site could never have worked. Accepted with finalizations
  (`[house]` tag; deactivate-vs-shutdown nuance pinned; decision recorded: implement restore, per
  `shutdown()`'s own assumed-state-continuity promise + the QUAL-56 "persist + restore + restart test
  together" rule) in `80424ba`, then executed: **(1)** `5d60999` — `deactivate()` deletes the persisted
  `active_scenario` atomically with the in-memory clear (first-ever `StateRepositoryPort.delete` caller);
  `shutdown()` untouched (still-active scenario deliberately survives a restart — test locks the
  asymmetry). **(2)+(3)** `6b1e9d8` — new `DevicePort.restore_state` seam + `BaseDevice` impl
  (declared-fields-only, identity/ephemeral/stale-error never restored, rides the `update_state`
  chokepoint); `DeviceManager` re-hydrates per device inside `initialize_devices()` **before** `setup()`
  (live sources win; post-setup persist now writes restored state back, not defaults); `initialize()`
  stub + bootstrap call removed; toggle-power inversion closed by restored assumed state (mf_amplifier
  real-capability regression test). Suite **502 passing** (was 495); import contracts 3/3 kept; docs
  (architecture overview, devices-and-scenarios, scenario redesign §7.1) updated with restore-at-startup
  + deactivate-clears-intent. VWB-18 moved to `action_plan_DONE.md`. Residual (inherent, accepted): a
  blind device flipped *while* the bridge is down still drifts — same exposure as pre-restart operation;
  the device-page manual resync remains the recovery path.

- **2026-07-01 (analysed + tightened: VWB-15/16 cross-project catalog-contract tasks; filed VWB-17)** —
  The voice side (`wb-mqtt-voice`) filed two bridge-side tasks off its ARCH-26 design session (uncommitted
  here for review): **VWB-15** (emit the Irene↔voice catalog contract artifact) and **VWB-16** (consumer
  contract test — crafted canonical `DeviceCommand` → native/echo). Analysed both against
  `wb-mqtt-voice/docs/design/mqtt_integration.md` §14 **and** the live bridge code; every technical claim
  verified (openapi carries `CatalogResponse` + `CanonicalActionRequest`; `GET /system/catalog` and
  `POST /devices/{id}/canonical` exist; `{wire,canonical,labels}` triplets + a content-hash version already
  emitted). Folded three findings into the task text: **(1)** VWB-15 — reuse the existing `wb-openapi`
  CLI (`cli/dump_openapi.py`) which already emits+commits `openapi.json`, don't rebuild it; the new work
  is the golden-sample `catalog dump`, WB7 dump, `contracts/` home + drift check. **(2)** VWB-15 —
  disambiguated the two "versions": keep the existing catalog content-hash (lazy re-pull) **and** add a
  build/commit stamp (which bridge build the voice side coded against). **(3)** VWB-16 — recorded the
  sequence-form endpoint caveat and pointed it at the new follow-up. Filed **VWB-17** `[P2]` `[later]` —
  route `sequence`-form actions through `POST /devices/{id}/canonical` (today it 500s on non-single-command
  bindings); unblocks full crossover-fixture coverage in VWB-16, not house-gating. Scope guard clean.

- **2026-06-30 (filed: DRV-8 — Roborock vacuum design, doc wired)** — Closed an
  `every-task-in-the-ledger` gap: the substantial Roborock S7 draft design (`docs/design/roborock_vacuum.md`,
  started 2026-06-09 — the bridge's first interactive-map appliance) had been written **untracked**, with no
  plan ID and referenced by nothing. Filed it as **DRV-8**, a **design task** (`design-then-implement`):
  deliverable = review the draft with the user, resolve the inline open questions, **lock** the design; on
  completion it files the implementation follow-ups (the `RoborockDevice` driver + interactive-map UI page).
  No driver/page work before the design locks. **Wired both ways** — DRV-8 → the doc, and the doc's header →
  DRV-8 (replacing its "NOT yet listed as a numbered task" note). Scope-drift guard stays green. Note: the
  guard didn't *catch* this (the orphan doc referenced no `PREFIX-N` id) — an "unwired design doc" check is
  a possible future addition to `check_scope.py`.

- **2026-06-30 (DOC-4 DONE — scope-drift guard built + wired into CI)** — `scripts/check_scope.py`, the
  machine-checkable `single-task-ledger` enforcement the invariant had only described until now.
  **Reconciled before building:** the filed spec said "adapted to this plan's freeform numbered-markdown-table
  format" — but DOC-9 had just replaced that with the `PREFIX-N` two-file model, which (as the convergence
  design predicted) makes the guard a near-port of `../wb-mqtt-voice/scripts/check_scope.py`. Five
  build-failing checks — duplicate id · misplaced status (`[x]` in active / non-`[x]` in DONE) · orphan
  finding (`PREFIX-N` id in a design/review doc not in the ledger) · dead `docs/design`|`docs/review` link
  (with a negative lookbehind so sibling-repo paths don't false-positive — caught one on first run) ·
  phantom alias — plus a per-workstream status summary. Wired as the first step of the `backend-test` CI
  gate. Verified clean on the live ledger (52 tasks: 34 done · 18 not-done) + positive tests for orphan +
  dead-link. CLAUDE.md `single-task-ledger` note updated "deferred follow-up" → implemented. **This closes
  the entire §5.2 ledger & documentation reconciliation series** (DOC-4/5/6/8/9/10 done, DOC-7 folded).

- **2026-06-30 (SCN-5 re-scope + DOC-10 DONE — scenario/Layer-3 ledgers retired)** — Two things. (1)
  Tidied a re-ID wrinkle: the former §5.2 #6 had collapsed into SCN-5 self-referentially ("file the
  task"); re-scoped SCN-5 to be the actual implementation task (activation-time transition-aware manual
  notes, load-bearing for LD/VHS audio) and cleared DOC-10's now-stale "blocked on SCN-5 filed" marker.
  (2) **DOC-10 done** — the four scenario/Layer-3 docs that doubled as ledgers reconciled:
  `scenario_redesign_progress.md` + `layer3_step0_layout_analysis.md` **archived** (git mv → `docs/archive/scenarios/`,
  FROZEN headers; the first's "branch not merged / 274 tests" status was years-stale); `scenario_system_redesign.md`
  **kept as the as-built spec** with a freeze-edit (planning sections §11/§12/§14/§17.4 marked historical;
  fixed the §13-vs-§14 "ordering rule" contradiction); `ui_backend_contract.md` **split** — the living
  seam contract stays, the per-commit Layer-3 rollout ledger (641→429 lines) moved verbatim to
  `docs/archive/layer3_rollout_record.md`. All inbound refs repointed. **This completes the §5.2 ledger &
  documentation reconciliation series** (DOC-5/6/8/9/10 done, DOC-7 folded; only the optional DOC-4
  scope-drift guard remains `[later]`). No code touched.

- **2026-06-30 (DOC-9 DONE — full ledger re-ID to `PREFIX-N`)** — Re-keyed the whole live ledger off the
  positional `P0…P4 / #n / §5.1` scheme onto stable workstream-serial IDs, per `ledger_format_convergence.md`
  (the former §5.2 #5). `action_plan.md` restructured from priority bands into **workstream sections**
  (DRV/SCN/VWB/UI/OPS/CORE/DOC) with a "How to use this file" legend (the folded DOC-7 conventions: status
  legend, `[P0/1/2]` priority tag, `[house]/[later]/[parked]` milestone tag, `HW-GATED` marker) + an
  **Acceptance gate** section (ex-P4 #1–#5). `action_plan_DONE.md` reorganized by workstream + re-IDed. New
  **`action_plan_aliases.md`** maps every old ID → new (~50 tasks) so historical refs resolve. The big
  P3.7 design narrative is preserved verbatim as VWB context; the four live `#7`/`#8` cross-section
  collisions are gone. Executed by a span-relocation builder (bodies sliced, never retyped) with a
  distinctive-substring check confirming every task survives byte-exact. CLAUDE.md `single-task-ledger`
  ID example updated; §0 document-map updated. Completes the §5.2 reconciliation series bar DOC-4
  (scope-drift guard) + DOC-10 (retire scenario ledgers, blocked on SCN-5). No code touched.

- **2026-06-30 (§5.2 #4 DONE — narrative sections archived, plan is a spine)** — Reconciliation
  before starting #4 found §1–§3 + §7 of `action_plan.md` were all **superseded 2026-05
  starting-survey analysis**, not live reference (paused-state snapshot, a long-committed WIP diff,
  the pre-P3 Docker/CI pipeline, and a codegen decision whose pipeline was deleted at the Layer-3
  cutover). Promoting them to architecture/design docs would have published stale content as current
  truth — the live equivalents already exist (`docs/architecture/*`, `ui_backend_contract.md`,
  `ops/`). Per `task-start-reconciliation` I stopped and consulted; user chose **archive all four**.
  So #4 re-scoped promote → archive: §1–3 → `docs/archive/initial_survey_2026-05.md`, §7 →
  `docs/archive/codegen_alternatives.md`, both verbatim (verified byte-identical) with FROZEN/superseded
  headers. Repointed §7's 3 inbound refs (DONE #3.5, DONE #10, `ui_backend_contract.md`) + the §1.2 ref.
  `action_plan.md` is now a true spine — §0 map, §4 tasks, §5 questions, §6 journal index — **900 → 681
  lines**. Next: #5 (full re-ID) operates on this clean spine. No code.

- **2026-06-30 (§5.2 #1 DONE — ledger-format convergence design)** — Wrote
  `docs/design/ledger_format_convergence.md` (the design gate; `design-then-implement` — design
  recorded, no re-ID executed). User picked **subsystem-shaped buckets** (DRV/SCN/VWB/UI/OPS/DOC,
  +proposed CORE) and **full re-ID now** (over lazy). Design: stable `PREFIX-N` identity assigned
  once / never renumbered (kills the `#22→#23` churn + the four live `#7`/`#8` cross-section
  collisions); priority a separate `P0/P1/P2` tag (P-bands dissolved); milestone tags
  `[house]/[later]/[parked]` mapping the bridge's "house works" gate to voice's `[release]/[deferred]`;
  status legend + a bridge-specific `HW-GATED` marker; two-file split reorganized by workstream; P4
  becomes an Acceptance-gate section, not workstream IDs. The doc carries the **complete old→new
  mapping** for ~50 tasks + the migration mechanics (journal stays frozen with an alias map — no
  back-ref rewrite). **§5.2 #5 re-scoped** deferred-lazy → **full re-ID execution**; #5 may absorb
  #3. **Confirmations resolved same day:** CORE accepted (kept thin — corrected a doc error that
  cited nonexistent "hexagonal follow-ups"; the hexagon is enforced, not a task source), tags
  `[house]/[later]/[parked]`, and **#3 folded into #5** (conventions applied within the re-ID pass,
  not separately). #5 is now unblocked. No code.

- **2026-06-30 (§5.2 #2 DONE — two-file split applied)** — Created the frozen
  `docs/action_plan_DONE.md` and moved the seven fully-complete early phase bands
  (P0, P0.5, P1, P2, P2.5, P2.6, P3) out of `action_plan.md` into it, organized by section.
  String-anchored move (start `### P0`, end `### Explicitly out of scope`) — verified the moved
  block is **byte-identical** to the original and every moved task ID is now in exactly one file;
  §4 carries a one-paragraph pointer in their place. **In-flight phases (P3.6, P3.7, P4) left
  whole** on purpose — how to represent a partially-done phase across the two files is §5.2 #1's
  design call, so their done rows move when the phase closes. Active plan 980 → 900 lines; DONE
  file 91 lines. Updated CLAUDE.md `single-task-ledger` ("rule defined, not yet applied" →
  "initial split applied 2026-06-30") and the §0 document-map (DONE file now indexed). No re-ID;
  no code touched.

- **2026-06-30 (filed: §5.2 ledger & documentation reconciliation)** — Filed a coherent
  7-task series (§5.2 #1–#7) from two chat-requested analyses: (1) comparing this plan's
  positional `P0…P4/#n/§5.1` numbering to the sister repo's workstream-serial ledger
  (`../wb-mqtt-voice` `RELEASE_PLAN.md` + frozen `RELEASE_PLAN_DONE.md`), and (2) reading the
  four scenario/Layer-3 design docs that doubled as ledgers. Finding: design/planning docs
  accreted a *done* ledger half that dilutes their reference half — the same disease one layer
  down from the plan itself. The series executes the doc-reconciliation handover §0 already
  promises. #1 = design gate (workstream taxonomy + stable-ID scheme + status legend + two-file
  split mechanics → `docs/design/ledger_format_convergence.md`); #2 apply the two-file split
  (`action_plan_DONE.md`); #3 adopt additive conventions; #4 extract the §1–3/§7 narrative to
  reference docs (plan → spine); #5 (deferred) lazy re-ID to stable serials; #6 file the
  load-bearing transition-aware manual notes (§13.2) as a real task (blocks #7); #7 retire the
  frozen scenario/Layer-3 ledgers (archive `scenario_redesign_progress.md` +
  `layer3_step0_layout_analysis.md`; freeze-edit `scenario_system_redesign.md`; split
  `ui_backend_contract.md` — keep the living seam reference, archive the rollout-ledger tail).
  `design-then-implement` + `every-task-in-the-ledger`. No docs moved yet — filing only.

- **2026-06-27 (filed: UI vite 5→6 migration task)** — Scoped the deferred vite major
  upgrade as a §5.1 ledger task (a deliberate version decision needs an ID, per the
  `every-task-in-the-ledger` carve-out). Closes the 4 vite/esbuild Dependabot alerts the
  lockfile-only fix couldn't reach; the 2 residual eslint/jest-pinned alerts (minimatch
  #101, js-yaml #152) are noted as separate toolchain-major tasks, not yet filed.

- **2026-06-27 (development-process invariants + UI dependency housekeeping)** — Two
  changes. (1) **Invariants port** (`7f8fbe1`): ported the 13 named development-process
  invariants from the sister repo `../wb-mqtt-voice` into `CLAUDE.md` → "Development process
  — invariants" (single source of truth, always in context; referenced by stable slug name,
  no number legend since the invariants are new here). Adapted to bridge's dialect:
  `backend/config/` JSON tree as `config-master-canonical`, import-linter-enforced
  `hexagonal-architecture`, `ui/` contract gate for `config-ui-stays-functional`,
  `docs/action_plan.md` + `docs/action_plan_journal.md` as the ledger. `action_plan.md` §0
  now points to CLAUDE.md for the invariants; filed the deferred scope-drift-guard task in
  §5.1. Slimmed two duplicate memories to pointers. (2) **UI deps fix** (`bc5aa84`):
  lockfile-only `npm audit fix` clearing the non-breaking ("Group A") Dependabot alerts —
  fast-uri/flatted/lodash/rollup/picomatch/yaml/@tootallnate-once/glob + the patchable
  minimatch/js-yaml copies. All are ui/ build/test toolchain (none ship to the browser, none
  touch the Python backend). Deferred ("Group B", breaking): vite 5→6 (#113) + esbuild (#81,
  dev-server-only, staying on v5 per `df2c09f`) and the minimatch/js-yaml copies pinned deep
  in `@typescript-eslint@6` / `jest`. Verified `cd ui && npm run check && npm run build` pass.
  _Process note: these two commits were authored before this journal entry — the bookkeeping
  (`read-at-start-record-at-completion`) was applied retroactively; the deps fix also drove a
  carve-out in `every-task-in-the-ledger` for routine no-`package.json` dependency bumps._

- **2026-06-09 (Layer-3 frozen oracle retired)** — Last open item from the Step 4 cutover.
  The structural fidelity oracle (`docs/design/scenarios/layer3_oracle/*.json`, 14 frozen
  snapshots extracted from the now-deleted `.gen.tsx`) had been kept as a deferred
  structural-regression snapshot since the Layer-3 cutover (2026-05-24 cont. 22:
  "kept as the engine's structural regression snapshot — retire deliberately later"). The
  question of "when" was answered today after discovering BOTH oracle-dependent test files
  had been silently non-operational on a stale path: `_oracle_dir()` walks for
  `docs/scenarios/layer3_oracle/` but the dir actually lives at
  `docs/design/scenarios/layer3_oracle/`. `test_layout_manifest.py` was producing a hard
  collection error on every pytest run; `test_layout_engine.py::test_engine_reproduces_oracle`
  was silently skipping its 12-device parametrize via `skipif(not ORACLE.is_dir())`. The
  pre-#26 commit `5212809` reproduced the same error, confirming this drift predates the
  recent ValueLabel work.

  Per the 2026-05-23 cont. 10 decision (`ui_backend_contract.md` "Fidelity strategy"):
  validation surface is render-level diff via the live `/devices/{id}/layout` consumed by
  `RuntimeDevicePage`, hardware-verified per device on each rollout — the structural oracle
  gave false MATCH for mf_amplifier while the actual page diverged. Two weeks of post-
  cutover stability + the silently-broken state confirm nothing actually depended on the
  oracle.

  **Surgery:** (1) `test_layout_manifest.py` deleted entirely (file was 100% oracle-bound
  + collection-erroring). (2) In `test_layout_engine.py`, removed the `ORACLE` constant,
  the `_name`/`_structure` helpers used only by the oracle diff, and the parametrized
  `test_engine_reproduces_oracle` (12 parametrize entries silently skipping); kept
  `_backend_root`/`_make_device` + `test_engine_emotiva_multizone_power` — the eMotiva
  multi-zone test was authored as a property assertion (multi-zone power intentionally
  diverged from the old codegen) and stays real. (3) The 14 oracle JSONs moved to
  `docs/archive/layer3_oracle/` via `git mv` per the project convention
  ("Superseded docs move to `docs/archive/`, never deleted"). (4) Docstrings in
  `layout_manifest.py` + `layout_engine.py` updated to drop oracle references; the
  build-time codegen fields (`stateInterface`/`actionHandlers`) stay optional for back-
  compat with cached UI builds. (5) `ui_backend_contract.md` updated: the "Fidelity
  strategy" blockquote now reads "retired" instead of "retire them", the Step 4 "Deferred"
  oracle entry marked DONE, the §A3 "Oracle (deferred)" sub-bullet flipped to "Oracle
  retired 2026-06-09".

  Suite **495 pass, ZERO skipped** (was 495 pass + 12 false skips — the parametrize
  entries that had been silently skipping). pyright + import-linter + AST gate clean.
  No source-level behavior changed; openapi.json unchanged.

  This closes the last loose end from the 2026-05-24 Step 4 cutover punch list.

- **2026-06-09 (§P3.7 #26 DONE — value-label translation layer, end-to-end)** —
  Three-layer enum mapping shipped across schema, driver, catalog, configs, and UI.
  Bus speaks wire (firmware-specific bytes); voice, UI, `state.mirrored`, and the catalog
  all speak canonical (short identifier-safe English names). The driver does the
  lookup-table flip at the boundaries — same shape as the existing `invert` flag, but
  for string-valued enums instead of numeric inversion.

  **5 commits, in order:**
  1. `bb8cca4` — schema (Phase 1a) + catalog DTOs (Phase 1c). New `ValueLabel(wire,
     canonical, labels?)` model in `domain/devices/config.py` next to `LocalizedName`,
     plus a shared `_normalise_value_labels` helper. `CapabilityField.values` and
     `StateTopicSpec.values` widened from `Optional[List[str]]` to
     `Optional[List[ValueLabel]]`, each with a `mode="before"` field validator that
     normalises bare `["a", "b"]` into `[{wire: "a", canonical: "a"}, ...]` — every
     existing profile / config / test parsed through unchanged. New `CatalogValueLabel`
     DTO in `presentation/api/schemas.py`; `CatalogField.values` widened similarly.
     `_project_capability_actions` emits the triplet per entry (labels projected via
     `model_dump`), so any label-table edit (new entry, new locale, renamed canonical)
     bumps the deterministic catalog `version` hash and Irene re-fetches. 8 new tests
     across `test_capabilities`, `test_wb_passthrough`, and `test_system_catalog`.
     `openapi.json` regenerated.
  2. `c6c8f67` — `backend/uv.lock` synced with the manifest (orphaned bumps:
     asyncwebostv 0.4.0, pymotivaxmc2 0.7.0, py-dev-gates v0.1.1 + pyright /
     import-linter / grimp / nodeenv dev-tree). Lock had drifted across three earlier
     commits; landed as a separate focused commit so the source diff stayed clean.
  3. `1c55007` — driver (Phase 1b). Two new helpers in `wb_passthrough/driver.py`:
     `_translate_outbound(payload, spec)` (canonical → wire for enum fields with a
     value table; identity otherwise; warn + pass-through on unknown canonical) and
     `_translate_inbound(value, spec)` (wire → canonical, identity otherwise).
     `_publish_command` now normalises the idempotency target into canonical space via
     `_translate_inbound` so wire-shaped requests still match `state.mirrored`, and the
     final publish pipeline runs translation → inversion → publish. `_coerce_mirror`
     ends with `_translate_inbound` so `state.mirrored` always holds canonical for
     enum-with-table fields. **Pre-existing bug fixed in passing**: `_parse_value`'s
     enum branch tested `raw in spec.values` — silently broken when `values` shape
     widened from `List[str]` to `List[ValueLabel]` in `bb8cca4`; now accepts either
     wire OR canonical against `spec.values`'s wires + canonicals. 8 new tests
     covering both directions, idempotency on canonical state, unknown canonical
     fallback (warn + bus-rejects-it), wire-pass-through accepted, bare-string back-
     compat as identity, no-table field unaffected.
  4. `ebc5a07` — HVAC profile + 3 Mitsubishi configs (Phase 2). Reverses the 2026-06-08
     decision to leave mode/fan/vane/widevane off the catalog ("raw int wire format
     would diverge from any enum claim") — with the value-label layer in place, the
     typed `enum` claim is now truthful. `hvac.json` `climate.fields[]` widened from
     2 to 6 entries; wire values from sister-firmware `mitsubishi2wb`'s
     `html_pages.h` L137-179 in dropdown order (AUTO/DRY/COOL/HEAT/FAN;
     AUTO/QUIET/1-4; AUTO/SWING/1-5; SWING/`<<`/`<`/`|`/`>`/`>>`/`<>`); canonical
     names short identifier-safe (`fan_only` for the mode-FAN entry to avoid
     colliding with the `fan` field name; directional `far_left`/`center`/`split` for
     widevane — clearer than the firmware's opaque "Position N" UI). Trilingual
     ru/en/de labels per entry. Each of the 3 device configs (`bedroom_hvac`,
     `living_room_hvac`, `children_room_hvac`) mirrored the same wire ↔ canonical
     pairs in its state_topics (labels live only in the profile to keep configs
     scannable). Command params for set_mode/set_fan/set_vane/set_widevane changed
     from `type: "range"` (0-N int placeholder) to `type: "string"` since canonical
     values are identifiers. **Drift-guard test** walks the 3 configs against the
     profile and asserts each config's state_topics wire ↔ canonical pairs match the
     profile's exactly — catches the silent failure where a wire drifts (voice would
     publish a canonical the firmware doesn't echo back). 3 new tests.
     **Heating_loop.mode left as-is** — the action-plan "optionally restore"
     qualifier; type=bool/invert=true already works and a 2-value bool doesn't
     benefit enough from per-value labels to justify the busywork.
  5. `05371c2` — native React HvacPanel (Phase 3). Two new hooks in
     `ui/src/hooks/useApi.ts`: `useSystemCatalog()` (infinite staleTime since the
     bridge bumps the retained version-hash topic on /reload) and
     `useExecuteCanonicalAction()` (merges post-state into the device-state cache on
     success — same pattern as `useExecuteDeviceAction`). New `HvacPanel.tsx` (~190
     LOC) at `ui/src/pages/appliances/`: sections for power on/off, setpoint number
     input (16-31°C, `defaultValue` keyed on the mirror echo so the input re-renders
     when the device confirms), and mode/fan/vane/widevane button grids. Each grid
     renders one button per `ValueLabel` entry with the firmware's exact Unicode
     entities inline (♻ AUTO, 💧 DRY, ❄️ COOL, ☀️ HEAT, ❃ FAN for mode; ⚟ SWING +
     ➟ POS-N for vane; literal `<<`/`<`/`|`/`>`/`>>`/`<>` for widevane — same bytes
     the firmware's `html_pages.h` ships) plus the locale-appropriate label.
     Settings store carries en/ru today; the panel falls back en→canonical when a
     locale label is absent so de strings (in the catalog) survive a future
     language-picker extension. Same generic component services all 3 HVAC
     instances; React-router device_id selects the catalog entry. Registered in
     `appliances/index.ts` next to `KitchenHoodPage` (the registry is keyed on
     device_id — comment updated to drop the implied device_category=appliance
     constraint). `openapi.gen.ts` regenerated; `npm run check` (typecheck + lint +
     orphan guard) + `npm run build` clean.

  **Backend gates at every commit:** import-linter 3 contracts kept, pyright 0
  errors, AST gate clean. **Suite 495 pass** during #26 work; the
  `test_layout_manifest.py` collection error that ran alongside was traced to a
  pre-#26 stale-oracle-path bug and retired separately in the same day's session
  (entry above).

  **Hardware verification deferred** to the next rack session. The end-to-end voice
  path is now wired: `POST /devices/bedroom_hvac/canonical {capability: "climate",
  action: "set_mode", params: {mode: "cool"}}` → driver publishes wire `"COOL"` to
  `/devices/hvac_bedroom/controls/mode/on` → echo lands canonical `"cool"` in
  `state.mirrored.mode` → the panel highlights the COOL button. Confirming the
  wire-level publishes match the firmware's expectations is the obvious next step.

  Total: ~1.5 day backend + ~½ day UI (action-plan estimate matched).

---

