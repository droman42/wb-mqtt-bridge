# Action Plan — Journal

**Status:** Living dated record of work done on the wb-mqtt-bridge monorepo. Extracted from
`docs/action_plan.md` §6 on 2026-06-06 — the plan was growing too quickly and the dated
history is intrinsically append-only, so it lives on its own from here. **Newest entries on
top.** References elsewhere in the plan ("see §6 (2026-05-25)" etc.) remain valid and now
point at the dated entry below.

`docs/action_plan.md` stays the master driving document (forward work + an index of recent
journal entries in §6). This file is the long tail.

---

**Note on IDs (2026-06-30):** the ledger was re-IDed to the `PREFIX-N` workstream scheme (DOC-9). This
journal's **earlier dated entries keep their original positional refs** (`§P3.7 #19`, `§5.1 #7`, `P4 #7`,
etc.) — they are historical and resolve via [`action_plan_aliases.md`](action_plan_aliases.md). New
entries use the new IDs.

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

- **2026-06-08 (Invert flag extended to bool — heating switch inversions cleaned up)** —
  Architectural symmetry follow-up: the cover invert fix (just landed) made covers
  architecturally clean, but heating switches with inverted actuators (3 configs:
  living_room_heating, children_room_heating, bedroom_heating) still carried the
  band-aid value-swap workaround (`mode_on: "0"`, `mode_off: "1"` in each config) +
  bare-string state_topic that held raw wire `"0"`/`"1"` -- the inverted semantic was
  invisible from the state surface. Reading "is the heating on?" required out-of-band
  knowledge of which wb-gpio pin maps to which valve orientation.
  **Fix**: extended the existing `invert` flag to handle `type: "bool"` (toggle
  `True`↔`False`) in addition to the existing `int`/`float` (`100 - value`). New
  module-level helper `_toggle_bool_wire_form` preserves surface form (`"on"`↔`"off"`,
  `"1"`↔`"0"`) so wire bytes stay consistent. The 3 heating configs migrated:
    - state_topic mode: bare-string → `{topic, type: "bool", invert: true}`
    - mode_on / mode_off reverted to natural sense (`"1"` = on, `"0"` = off)
  **State.mirrored impact**: now carries typed `True`/`False` in natural sense, so any
  consumer reading mode gets "is the heating on?" directly without per-device knowledge.
  **No-op detection refactor (bug surfaced + fixed)**: the previous compare
  (`str(current) == natural_payload`) worked for int (`str(25) == "25"`) but failed for
  bool (`str(True) == "1"` is False). Replaced with type-aware compare: parse target
  payload to typed form via `_parse_value`, compare to mirror's typed value. Falls back
  to plain string compare when no spec is available. Fixes no_op short-circuit for
  bool-typed fields generally, not just the heating case.
  **Tests** (+8 in test_wb_passthrough.py): bool defaults, outbound toggle for mode_on
  and mode_off, inbound toggle for wire 0 and wire 1, end-to-end roundtrip with no_op,
  surface-form preservation in `_toggle_bool_wire_form` (incl. `"on"`/`"off"`/`"On"`/
  `"true"` variants + unknown-passthrough), regression guard for non-inverted bare-str
  fields. Full suite **502 passing** (was 495; +7 net).
  **Hexagon LAW clean** (verified via grep) -- change is presentation-internal driver
  wiring + per-config schema; no domain → infrastructure imports touched.
  **NOT touched in this commit (asked separately)**: cabinet_windowsill on
  wb-gpio/EXT3_R3A5 was authored as NOT inverted, but the cabinet "Обогрев" widget
  was never pasted -- if it actually has `"invert": true` in its `extra` map, the
  same migration applies (the file already uses the heating_loop profile; just needs
  the state_topic widened + value swap added). Pending user confirmation.
- **2026-06-08 (Cover `invert_position` flag — cabinet rollers fixed end-to-end)** —
  Follow-up on the deferred item from §P3.7 #23: cabinet's `dooya_dm35eq_x_*` motors
  publish wire 0=open / 100=closed (inverse of the other dooyas). Until now we'd
  hand-swapped the static `open`/`close` action values in the cabinet roller configs
  (open writing `"0"`, close writing `"100"`), but `set_position(pct)` passed `pct`
  raw and so silently misrouted any non-midpoint percentage: voice asking for "25%
  open" actually published `25` (= 75% open). State.mirrored also carried raw motor
  values, so consumers saw misleading natural-sense readings.
  **Fix**: added an `invert: bool = False` flag to `StateTopicSpec` (per-field, opt-in).
  Driver applies `100 - value` SYMMETRICALLY at the wire boundary:
    - **Outbound** (`_publish_command` + new `_invert_wire_payload`): natural-sense
      payload from `_resolve_payload` → inverted just before publish. Configs stay in
      natural sense.
    - **Inbound** (`_coerce_mirror` + new `_apply_inversion`): typed value from
      `_parse_value` → inverted before storing in `state.mirrored`. Mirror always
      carries natural sense.
  **No-op detection**: works correctly across the inversion because we now compare in
  natural-sense throughout (mirror is natural-sense; new param value is natural-sense
  via `_resolve_payload` BEFORE the wire-inversion step). The publish still happens
  (the `data.no_op` flag tells the canonical endpoint to short-circuit the echo
  wait).
  **Cabinet roller configs reverted** to natural-sense: open=100, close=0,
  set_position takes natural pct 0-100, with `invert: true` added to the position
  state_topic. The driver hides the device-family quirk; configs no longer carry the
  manual-swap workaround.
  **Tests** (+8 in `test_wb_passthrough.py`):
    - `test_state_topic_spec_invert_flag_defaults_false` / `_parses_true` — schema
    - `test_invert_outbound_static_open/close_publishes_inverted_*` — static values flip
    - `test_invert_outbound_set_position_25_publishes_75_wire_sense` — the core fix:
      `set_position(pct=25)` now publishes `75` (= 25% open), not the broken `25`.
    - `test_invert_outbound_set_position_midpoint_unchanged` — invariant: 50% is the
      same in either sense
    - `test_invert_inbound_mirror_stores_natural_sense` — echo `"75"` → mirrored 25
    - `test_invert_roundtrip_set_then_mirror_consistent` — end-to-end: publish, echo,
      mirror, repeat → no_op short-circuit works in inverted space
    - `test_invert_does_not_affect_non_inverted_field` — regression guard for the
      slice's cabinet_spots (no invert flag → behaviour unchanged)
  Full suite **495 passing** (was 486; +9 net = +8 new + 1 already-added defaults
  check). **Hexagon LAW clean** (verified via grep before commit) — change is
  presentation-internal driver wiring + schema field; no domain → infrastructure
  imports touched.
  **Still deferred** (logged in authoring log, separate session): ESP32ManagedDevice
  class introduction for the 3 HVAC configs.
- **2026-06-08 (Room-architecture refactor — single source of truth for room membership)** —
  Architectural cleanup triggered by the rooms.json drift discovered mid-#23 (user
  asked: "did we update rooms.json with new registered devices?" — answer was no for
  19 devices). The fix at that time was a band-aid drift-guard test; this refactor
  removes the duplication entirely. **Single source of truth**: each device declares
  its room exactly once via `device.config.room`. `RoomManager` derives `room.devices`
  from `DeviceManager` at load time via `DevicePort.get_room()`. rooms.json carries
  only spatial metadata (room_id, names, description, default_scenario) — any legacy
  `devices` field is ignored.
  **Five phases in one commit**:
    - **A**: Backfilled `room` on 13 AV configs (appletv_children → children_room,
      kitchen_hood → kitchen, all other AV → living_room). Data-only, no code touched.
    - **B**: `RoomManager.reload()` strips JSON-side `devices` arrays and populates
      `room.devices` from `DeviceManager.devices` by calling `device.get_room()`. The
      legacy `_validate_devices_exist` (rooms.json → DeviceManager direction) was
      replaced with `_populate_devices_from_device_manager` (inverse direction): warns
      on orphan devices (devices whose `get_room()` returns a room_id not in
      rooms.json) but doesn't fail bootstrap.
    - **C**: `RoomDefinition.devices` widened to `default_factory=list` (no longer
      required field; the manager populates it). Dropped 19 `devices` arrays from
      rooms.json — every entry is now metadata-only. Removed drift-guard
      `test_rooms_json_devices_match_wb_passthrough_configs`; added forward-direction
      `test_every_device_config_declares_a_known_room` (catches device configs that
      reference unknown room_ids — typos, missing rooms.json entries, etc.).
    - **D**: Added abstract `get_room() -> Optional[str]` to `DevicePort` (domain
      contract). Added `self.room = config.room` flat attribute and `get_room()` impl
      to `BaseDevice` — mirrors the existing `get_id` / `get_name` flat-projection
      pattern. **This is the hexagonal-clean way**: domain managers (RoomManager,
      ScenarioManager) call `device.get_room()` through the port instead of reaching
      into the concrete `BaseDevice.config.room` (which would be a domain → infra
      leak).
    - **E**: Activated the long-dormant `ScenarioDefinition.room_id` invariant. The
      schema had carried `room_id: Optional[str]` with a docstring promising "All
      devices must be in this room" since the start of the scenario redesign, but the
      validation was never implemented. Added `ScenarioManager._validate_room_membership()`
      called from `initialize()` after `load_scenarios()`: walks every loaded
      scenario, for those that declare `room_id`, asserts every device in the union
      `devices ∪ {source, display, audio} ∪ roles.values()` reports the same room
      via `get_room()`. **Hard-fails bootstrap** (raises `ScenarioError`) on mismatch
      — catches typos, stale references, drift between scenario configs and device
      configs. All 9 existing scenarios pass (they all declare `room_id: "living_room"`
      and reference only living_room devices); zero existing scenarios broken by the
      activation.
  **Hexagon-clean throughout** (verified with grep before commit):
    - Phase A: data-only, no imports.
    - Phase B: RoomManager (domain) reads `DeviceManager.devices` (domain) and calls
      `device.get_room()` (port) — all domain → domain.
    - Phase C: schema cleanup in domain only.
    - Phase D: `get_room()` added to port (domain), implemented in BaseDevice
      (infrastructure). Direction: infrastructure implements domain abstraction — correct.
    - Phase E: ScenarioManager (domain) reads `DeviceManager.devices` (domain) and
      calls `device.get_room()` (port) — all domain → domain.
  **Tests**: removed 1 (drift-guard), added 3 (forward-direction device→room check,
  scenario validation positive + negative), updated several mocks (MockDevice gained
  `get_room()`, integration test configs gained `room` attribute). Full suite **486
  passing** (was 485 at #23 close; net +1).
  **What this gives us going forward**: drift between rooms.json and device configs
  is now structurally impossible (one place to declare, derived everywhere else).
  Scenario room-membership is enforced — bootstrap aborts loudly on drift. UI is
  already room-sensitive end-to-end (audit-confirmed in pre-implementation review);
  zero UI changes needed. The architectural debts that remained from this discussion
  (cover.set_position `invert_position` flag for inverted Dooyas; ESP32ManagedDevice
  class introduction for the 3 HVACs) are tracked separately in the authoring log
  and will land in their own focused sessions.
- **2026-06-08 (§P3.7 #23 DONE — 57 WB-passthrough device configs across all 10 physical rooms)** —
  Largest bulk task in the voice integration phase, completed in one extended interactive
  session. **Per-room counts**: bedroom 11, living_room 11, cabinet 6, children_room 6,
  shower 6, bathroom 5, kitchen 4, hall 3, entrance 3, wardrobe 2 = **57 total**. **Per-
  profile distribution**: light_switch × 23, dimmable_light × 13, heating_loop × 9,
  cover × 8, hvac × 3, sensor_room × 1 (the sauna's wb-msw2_100). Workflow was user
  pasting raw WB-UI widget JSONs from `/etc/wb-webui.conf`, assistant proposing complete
  device configs per category with terse Q&A, writing files + extending rooms.json
  incrementally; once profile shapes settled, additional rooms collapsed to
  copy-paste-with-topic-swap. **Profile changes accumulated during authoring**: (1)
  `cover.stop` dropped — Dooya position sliders have no native stop control; (2) `hvac`
  profile rewritten end-to-end after reading sister-firmware
  `/home/droman42/development/mitsubishi2wb` — dropped fictional enum fields for
  mode/fan/vane (wire is int codes, not named strings), added missing `set_widevane`
  action, corrected `temperature` field to BE the writable setpoint (not a separate
  read-only); (3) `heating_loop.mode` dropped from fields[] to mirror light_switch
  pattern; (4) `sensor_room` made effectively "1-to-5 fields" by introducing catalog-
  side filtering (next item). **Catalog enhancement**: `_project_capability_actions`
  gained `mirrored_field_names: Optional[set[str]]` parameter so a device using a
  profile with N fields but mirroring only K<N of them surfaces only the K mirrored
  fields in the catalog. Triggered by the sauna sensors widget that had only
  temperature + humidity from the sensor_room profile's 5 declared fields. AV devices
  (no state_topics attribute) pass `None` → filter disabled → backward-compatible.
  **rooms.json drift-guard test**: walks every WB-passthrough config and asserts its
  device_id is in the correct room's `devices` list. Caught the silent 19-device drift
  surfaced when user asked "did we update rooms.json?" mid-session 3; now prevents
  recurrence. **Cabinet roller cover semantic fix**: `dooya_dm35eq_x_*` motors invert
  position (0=open, 100=closed); open/close action values swapped for both cabinet
  rollers. `set_position(pct)` semantic gap on inverted devices documented as deferred
  follow-up. **Subfolder convention correction**: `wb-devices/<room>/` uses bridge
  room_id (matches rooms.json), NOT the WB-UI dashboard id where they differ; action_
  plan A1 paragraph rewritten mid-session 2 once the inconsistency surfaced. **Live
  authoring log** at `docs/wb_device_authoring_log.md` captures every per-device
  decision, 14 accumulated cross-room rules (naming conventions, ru-verbatim-vs-
  disambiguate pattern, profile-vs-wire mismatch handling, etc.), 7 friction
  observations (A2 incompleteness, stale doc paragraphs, terse-reply interpretation
  risk, etc.), and 9 automation opportunities (read /etc/wb-webui.conf directly,
  schema-aware linter, derive rooms.json from device configs, eliminate the
  duplicated source-of-truth, etc.) — explicit input for any future packaged version
  of this onboarding flow. **HVAC migration flagged**: three HVAC configs
  (living_room_hvac, children_room_hvac, bedroom_hvac) currently on
  `WbPassthroughDevice` class; will migrate to `ESP32ManagedDevice` when that class
  is introduced (per the 2026-06-08 lock-in decision; class to be added when ESP32-
  specific surfaces are needed). **Multi-sensor backlog**: most rooms' wb-msw-v3_*
  multi-sensors deferred to a focused future session for firmware-doc cross-
  reference; only the sauna's wb-msw2_100 (2 simple fields) included in #23. The
  sauna case is what proved out the catalog-filtering feature, paving the way for
  partial multi-sensor exposures later. **Test count**: 482 → **485** passing
  (+3 net: drift-guard test, catalog filter test, catalog filter-disabled regression
  guard; renames + content updates for several existing tests). **Hexagonal LAW
  clean** — catalog filter change is presentation-layer-internal, no domain imports
  touched. **Commits**: 913cbf9 (cabinet) + edc345f (living_room) + ecc5759 (drift
  fix + children_room) + 53ddde0 (bedroom + cover semantic) + b65630d (kitchen) +
  this commit (remaining 5 rooms + sauna sensors + catalog filter + #23 DONE).
  **Next**: #22 (aggregate devices in `global` — `all_lights` first) + #24 (the
  multi-sensor bulk that #23 deferred) + #25 (catalog completeness sweep + e2e).
- **2026-06-08 (§P3.7 #21 DONE — rooms.json full WB-UI sweep + global)** —
  Second task of the bulk phase. **All 10 WB-UI dashboards from A2 findings now have
  matching `rooms.json` entries**: existing `living_room` / `children_room` / `kitchen` /
  `cabinet` preserved with their legacy symbolic ids (per user direction — the WB
  dashboards `livingroom` / `children` map onto them via the importer in #23, not via a
  rename), plus 6 new rooms: `entrance`, `hall`, `shower` (the WB dashboard labelled `wc`
  is a shower room in the live home — symbolic id reflects the actual room), `bathroom`,
  `bedroom`, `wardrobe`. Plus **`global`** for the whole-house aggregate devices that #22
  will ship (`all_lights` first). The WB-dashboard → bridge-room mapping for the three
  cases where ids differ is documented in each entry's `description`; a structured
  `wb_dashboard_id` field can land alongside the actual config importer (#23) if needed.
  **Locale coverage**: all 11 rooms carry **trilingual `ru/en/de`** names (de added to
  the new rooms alongside the pre-slice rooms that already carried it; covers the §P3.7
  voice contract's "all locales" rule and keeps the catalog locale-symmetric). Authored
  by hand — 11 entries is small enough that a Python importer for the rooms specifically
  is unnecessary churn. The full WB-config importer (which #23 needs to author ~50–80
  device configs) is deferred until #23 starts. **Tests**: 8 new in
  `test_rooms_bootstrap.py` pinning the on-disk file (not a mock fixture, so drift surfaces
  immediately): full 11-room set, each entry validates as `RoomDefinition`, trilingual
  coverage, `global` starts empty (`devices: []`; #22 fills it), legacy room device
  memberships preserved, new rooms start empty, WB-dashboard ids documented for the mapped
  rooms. Full suite **482 pass** (was 474). **Hexagonal LAW clean** — no code paths touched
  outside `config/rooms.json` and the test file. **Next**: #22 (aggregate devices in
  `global`).
- **2026-06-08 (§P3.7 #19 DONE — capability vocab profiles + driver enrichment)** —
  First task of the bulk phase landed. **Six capability profiles authored** in
  `backend/config/capabilities/profiles/`: `dimmable_light` (wb-mdm3 switch+slider),
  `rgb_light` (wb-mrgbw-d), `cover` (Dooya), `heating_loop` (radiator/floor),
  `hvac` (full mitsubishi-style climate), `sensor_room` (wb-msw-v3 with 5 fields —
  motion intentionally dropped, no v1 voice use case per user direction). **Schema
  widening landed cleanly**: new `StateTopicSpec(topic, type, encoding?, values?, unit?)`
  Pydantic model + a `mode="before"` `field_validator` on `state_topics` that normalises
  the bare-string config form into `StateTopicSpec(topic=..., type="str")` — slice's
  `cabinet_spots.json` and its tests parse unchanged. New optional `payload_template` on
  `WbPassthroughCommandConfig` for composite payloads (RGB-style). New `CapabilityField`
  model + `fields: List[CapabilityField]` on `Capability` (domain layer); `_shape`
  validator widened to accept the pure-sensor shape (stateful + empty actions + non-empty
  fields). **Driver helpers in the WB-passthrough driver** (~70 LOC): `_compose_payload`
  uses `payload_template.format(**params)` for multi-param composite writes;
  `_parse_value` does scalar coerce / enum validate / template-inverse (`"R;G;B"` →
  `{r,g,b}` via the new module-level `_parse_template` regex); `_coerce_mirror` looks up
  field spec, parses, logs on failure WITHOUT touching `error_flags` (that surface is
  WB-protocol-only — `r`/`w`/`p` — so a parse failure must not falsely flip `reachable`).
  `WbPassthroughState.mirrored` widened from `Dict[str, str]` to `Dict[str, Any]` so typed
  values land directly (floats are floats, RGB is a dict, enums stay strings). **Catalog
  builder enhancement**: new `CatalogField` DTO mirrors `CapabilityField`;
  `_project_capability_actions` walks `cap.fields[]` and emits type/encoding/values/unit/
  labels. Version hash naturally bumps when a capability `fields[]` entry changes (Irene
  re-fetches when sensors become visible or a new encoding lands). **Footgun caught + fixed**:
  `Capability.fields = Field(default_factory=list, ...)` raised `'FieldInfo' object is not
  callable` because the prior `list: Optional[CapabilityAction] = Field(...)` declaration
  in the same class body shadowed the builtin `list` — so `default_factory=list` resolved
  to the FieldInfo, not the constructor. Switched to `default_factory=lambda: []` with an
  inline comment so the next reader doesn't trip on it. **Tests**: 7 new profile/loader
  tests (sensor 5 fields no motion + each profile's distinguishing shape), 9 new driver
  tests (template parse + inverse, RGB compose + mirror round-trip, scalar coerce,
  parse-failure log path that does NOT flag `error_flags`, slice bare-string back-compat
  regression), 4 new catalog tests (sensor fields surface with labels, RGB encoding
  surfaces, version bumps on field addition), 1 slice test pin update (typed `StateTopicSpec`
  not raw string). **474 passed** (was 453). **Hexagonal LAW clean** — `grep` confirmed
  zero `domain → infrastructure/presentation` imports (the new `CapabilityField` references
  `LocalizedName` from `domain/devices/config.py`, same layer). Also swept the
  `BaseDeviceConfig.room` docstring that still mentioned the deprecated "Irene iterates
  rooms" model — fixed to match the aggregate-device-in-`global` resolution (matches the
  2026-06-07 contract reconcile). **Next**: #21 (rooms.json bootstrap) + #22 (aggregate
  devices in `global`).
- **2026-06-08 (§P3.7 #20 collapse — composition folds into the driver; HVAC class locked)** —
  Follow-up discussion on the bulk plan. Re-examined yesterday's "the composition layer #20
  needs code that profiles can't carry" claim and found it overstated: the only items that
  genuinely needed code were RGB payload assembly + inverse parsing + type coercion on the
  mirror, and **all three live cleanly inside the WB-passthrough driver** when `state_topics`
  carries per-field `{type, encoding?, values?}` metadata. The driver gains three helpers
  (~50–100 LOC): `_compose_payload(template, params)`, `_parse_value(raw, type, encoding)`,
  `_coerce_mirror(field, raw)`. `state.mirrored` then carries typed values (floats, dicts,
  enums) instead of raw strings — `GET /devices/{id}/state` returns typed; catalog emits typed
  defaults; Irene and the UI both get coherent shapes without consumer-side parsing. **#20
  deleted** (struck through with "folded into #19" note for traceability); #19's scope widens
  accordingly to ~1.5 day; bulk total drops to ~7–9.5 dev days (from ~7.5–10.5). Updated the
  pillar-C summary, the A2 composite-shapes prose for heating loops + RGB (both no longer
  reference an adapter layer), and the bulk table header. **Decision locked**: the 3 HVAC
  units WILL be a new device class **`ESP32ManagedDevice`** (not "may eventually move" — the
  decision is taken). At v1 ship it's behaviourally identical to `WbPassthroughDevice` (same
  subscribe/publish/coerce path, same `hvac` profile drives both); the distinct class exists
  so HVAC has a stable identity to grow into — future versions expose ESP32-specific surfaces
  **to the UI** (provisioning state, OTA progress, NVS identity, sleep/wake telemetry,
  firmware version) that don't belong on a generic passthrough device. Aligns with the PARKED
  ESP32 firmware scaffold in §5. No code touched.
- **2026-06-07 (§P3.7 plan reconcile — aggregate-device model for `global`)** —
  Re-read of `docs/design/voice_integration_contract_draft.md` against `action_plan.md` §P3.7 surfaced
  one residual drift from the 2026-06-06 contract correction (commit `36b8fe6`): two places in
  the plan still described "выключи свет везде" as Irene-iterating-rooms, where the agreed
  model is a single canonical call against an aggregate device in `global` (e.g. `all_lights`).
  Fixed both lines (§P3.7 pillar-B summary + A1 findings cross-room paragraph). Bulk task list
  also missed the aggregate-device deliverable — inserted a new task **#22 (Aggregate devices
  in `global`)** between rooms.json bootstrap and the per-room config sweep, ~½ day; renumbered
  the three following tasks (22→23, 23→24, 24→25); updated the "bulk total" estimate to
  ~7.5–10.5 dev days; updated the "#19-#24" range reference in the post-slice journal entry to
  "#19-#25". Task #21 (rooms.json bootstrap) clarified to seed the `global` room as a top-level
  entry. **User-declared scope boundary**: the bridge-side aggregate-device configs are in
  scope for #22; the **controller-side wb-rules fan-out scenes that back each aggregate are
  user tech debt** (out of bridge scope; the bridge just registers each aggregate as a normal
  `WbPassthroughDevice` config whose `commands.power_*` topic points at the WB virtual control
  the wb-rules scene listens on). Slice (#13-#18) needed no code change — contract drift was
  entirely in the bulk-task description. No code touched.
- **2026-06-06 (§P3.7 #18 cold-start fix — retained-message opt-in per topic)** —
  Final follow-up surfaced by the user at the rack: after the AV-driver fix, the bridge
  booted clean but the FIRST `power_off` after restart 503'd whenever the relay was
  already off. Cause: `MqttClient`'s receive loop globally skips retained messages, so
  the broker's retained current value (`"0"` on `/devices/wb-mr6c_51/controls/K4`) was
  delivered on subscribe but never dispatched -- `state.mirrored` stayed empty, the
  no_op short-circuit couldn't detect "already at target," and the publish-then-wait
  path timed out because the device doesn't republish unchanged values. The global
  skip is safe behaviour (a retained `/on` command payload would otherwise replay a
  stale action), so removing it wholesale isn't right. **Fix**: opt-in per topic.
  `MqttClient.subscribe()` gained a `process_retained=False` kwarg; topics opted in are
  tracked in a new `_retained_allowed_topics: Set[str]`; the receive loop's retained-skip
  now also checks that set. `WbPassthroughDevice.setup()` passes `process_retained=True`
  for both the value topic AND the per-control `meta/error` topic so the broker's
  retained current-state and current-error payloads are seeded into state on connect.
  AV drivers and the WB virtual-device `/on` command subscriptions stay at the default
  (skip retained) -- behavioural change is bounded to WB-passthrough subscriptions.
  5 new tests covering: default opt-out, opt-in adds topic, opt-in coexists with
  default, default initial state, and a driver-level assertion that setup() passes
  `process_retained=True` for both value and meta/error subscriptions. Full suite 453
  passed (was 448, +5). With this fix the cold-start case in the test_publish_no_op
  driver test (mirror unseen → no_op=False → publish-wait → potential 503) gets reduced
  to "broker has no retained value for the control," which is the genuinely-rare path.
- **2026-06-06 (§P3.7 #18 follow-up #2 — AV-driver instantiation regression + fix + signature test)** —
  Previous bootstrap fix added `wb_service=self._wb_service` to the device-class
  constructor call in `DeviceManager.initialize_devices`. `BaseDevice.__init__` accepts
  `wb_service`, but all 7 AV driver subclasses override `__init__` with the narrower
  `(config, mqtt_client=None)` signature. Result: every AV device TypeError'd at
  instantiation; the bridge booted with **only `cabinet_spots`** registered (the
  WB-passthrough driver does accept it). The two test fakes I'd widened to match (with
  `wb_service=None`) masked the production breakage. **Fix**: removed `wb_service=` from
  the constructor call. AV drivers keep receiving `wb_service` via the existing
  attribute-setter loop in bootstrap (`device.wb_service = wb_service`);
  `WbPassthroughDevice` doesn't need it at construction (its
  `enable_wb_emulation=False` skips the BaseDevice path that uses it). **Regression
  test**: new `tests/unit/test_device_class_init_signatures.py` walks every driver
  registered via the `wb_mqtt_bridge.devices` entry-point group and asserts each accepts
  the kwargs `DeviceManager.initialize_devices` passes (currently
  `{"mqtt_client"}` -- one place to update when the call signature changes). Catches
  this whole class of regression at unit-test time instead of when the bridge boots with
  fewer devices than authored. Full suite 448 passed (was 447, +1).
- **2026-06-06 (§P3.7 #18 follow-up — idempotency: no_op short-circuit for repeat actions)** —
  Slice gate passed; user immediately exercised the obvious follow-up case (fire the same
  `power_on` twice). Second call 503'd because wb-mqtt-serial doesn't republish unchanged
  values, so no echo arrived and the canonical endpoint timed out. The trace was honest:
  before publishing, state already showed `mirrored={'power': '1'}` from the first call's
  echo. **Fix**: `WbPassthroughDevice._publish_command` now compares the resolved
  target payload against `state.mirrored[<matching state_field>]`. When they match the
  publish still goes out (cheap; keeps the WB layer informed), but the result carries
  `data.no_op = True`. The canonical endpoint checks the flag right after `perform_action`
  returns: if set, return success immediately with the current state, skipping the echo
  wait (which would 503-timeout). AV devices don't set the flag and stay on the existing
  wait path. `_state_field_for_command` derives the matching mirror field by stripping the
  `/on` suffix from the command topic and looking it up in `state_topics`. 3 new
  driver-level tests (mirror-matches → no_op True; real change → no_op False; cold-start
  unseen mirror → no_op False with documented limitation note) + 2 new canonical-endpoint
  tests (no_op short-circuits the wait; no_op=False still waits). Full suite 447 passed
  (was 442, +5). **Known cold-start edge case** (documented in the new test, not yet
  fixed): if the bridge restarts while the relay is already at the user's target value,
  the first request after restart still 503s because retained messages are skipped by
  the MQTT client's main loop, so we don't seed `mirrored` on subscribe and can't detect
  no_op. Addressed in a later pass (process-retained-on-this-subscription option, or a
  one-shot poll at setup).
- **2026-06-06 (§P3.7 slice #18 — DONE; voice integration slice physically validated)** —
  After the bootstrap/MQTT-framework fixes (previous journal entry), the user restarted
  the bridge and re-ran the rack test. **Full trace, in milliseconds**:
  `15:39:57.496 POST /devices/cabinet_spots/canonical {capability:"power", action:"on"}`
  → bridge publishes `1` to `/devices/wb-mr6c_51/controls/K4/on` →
  `15:39:57.501 echo `1` received on /devices/wb-mr6c_51/controls/K4` (round-trip
  publish→echo: **5 ms**, well under the 500 ms canonical-endpoint budget) →
  `15:39:57.502 update_state(mirrored={'power': '1'}, error_flags={}, reachable=True)` →
  state-change callback chain fires (persistence + the canonical endpoint's one-shot
  waiter) → `15:39:57.502 HTTP/1.1 200 OK`. Relay physically clicked; the user observed
  the cabinet spots come on. The full chain — voice contract → canonical endpoint → WB
  publish → wb-mqtt-serial → physical relay → value-topic echo → bridge subscription →
  update_state → callback chain → 200 OK with post-state — is end-to-end live. The
  chokepoint suppressed the `last_command`-only updates as designed (the inner
  `_publish_command` update and the outer `perform_action` wrap), so the waiter only
  fired on the meaningful `mirrored` echo. **§P3.7 slice #18 is DONE.** The voice
  integration vertical slice is feature-complete on the bridge side AND validated against
  real hardware — the slice gate is crossed. Irene ARCH-8 sign-off remains the only
  external dependency to close out the slice formally; once Irene is on the controller
  the same POST works against the live bridge with zero further changes here. **Slice
  totals**: 6 slice tasks (#13/#14/#15/#16/#17/#18) + 3 pre-work items
  (A1/A2/A3) + 2 mid-slice corrections (single-room model + capability-profile
  mechanism) + 2 bug fixes (the bootstrap/MQTT-subscribe wiring), all done in a single
  session. Suite stayed green at 442 throughout. Hexagonal LAW held end-to-end. Next
  major work: §P3.7 bulk (#19-#25), starting whenever the user is ready.
- **2026-06-06 (§P3.7 #18 first rack run -- two-prong subscription wiring bug + fix)** —
  User exercised the slice at the rack with the real WB-MR6c at slave 51 channel K4. The
  relay clicked on POST `/devices/cabinet_spots/canonical` (publish out worked) but the
  endpoint returned **503 device_unreachable**. Bridge log showed perform_action returning
  `success: True` and the inner `_publish_command` updating `last_command` -- but
  `mirrored` stayed `{}`. Two bugs surfaced (both latent until WB-passthrough became the
  first driver to register MQTT subscriptions during its `setup()`):
  - **Bootstrap ordering**: `DeviceManager.initialize_devices` instantiated devices with
    `mqtt_client=None`; only AFTER the loop did bootstrap assign `device.mqtt_client =
    mqtt_client`. So `WbPassthroughDevice.setup()` saw `None`, returned False with the
    documented warning, and never queued any subscription.
  - **MQTT-client framework**: `MqttClient._run_mqtt_client` only subscribed to topics
    explicitly passed via `connect_and_subscribe(topic_handlers)` -- it ignored any
    handlers queued via `subscribe()` before the broker came up. So even if setup() had
    queued our state_topic + meta/error handlers, the broker never sent us their
    messages.
  Fix: `DeviceManager` gained `set_runtime_services(mqtt_client, wb_service)`; bootstrap
  + /reload now wire those BEFORE `initialize_devices`, and the constructor receives both
  via the existing `mqtt_client=` / `wb_service=` kwargs. `_run_mqtt_client` now
  subscribes the **union** of `topics_to_subscribe` and `self.message_handlers.keys()` --
  so any pre-queued handler reaches the broker. Two test fakes that took only
  `mqtt_client=None` widened to accept the new `wb_service=None` kwarg.
  **Known follow-up (deferred)**: when the canonical endpoint fires the same value as the
  current `mirrored` (e.g. power_off when light is already off), `update_state` finds no
  change → no callback → 500 ms timeout → 503. Mitigate later by waking the waiter on
  ack-received rather than state-changed; for slice 1 the rack walk alternates values so
  every call really does change state. **Full suite 442 passed.**
- **2026-06-06 (§P3.7 slice #17 — `GET /system/catalog` DONE)** — The catalog Irene
  fetches on startup (and after a version bump). New endpoint in
  `presentation/api/routers/system.py`; builder in a new `presentation/api/catalog.py`
  module that walks `DeviceManager.devices` + `RoomManager.list()` and projects to the
  catalog DTOs (`CatalogResponse` / `CatalogRoom` / `CatalogDevice` /
  `CatalogCapability` / `CatalogAction` in `schemas.py`). Deliberately separate from the
  Layer-3 layout manifest (which is UI-shaped); the catalog is the contract for any
  non-UI consumer. Per-device capabilities walked from the attached `CapabilityMap`
  (so the resolution chain from class → profile → per-device override authored in #14
  flows through naturally). For slice 1 we surface action *names* only (no param
  descriptors; param introspection lands with #19 / vocab extension); sensor `fields`
  shape stubbed in the DTO but populated when sensor capability profiles arrive.
  Devices without `room` set (the current AV configs until bulk onboarding) surface as
  `room: null`. The `version` field is a 16-hex short SHA-256 over the canonical JSON
  of `{rooms, devices}`; rooms + devices are sorted by id before hashing so insertion
  order can't randomise the hash. **Retained `bridge/catalog/version` MQTT topic
  published at the end of `reload_system_task`** so Irene's catalog consumer can
  subscribe and only re-fetch when the hash differs from the last seen one --
  retained-flag set so late-joining subscribers still see it. The publish is
  best-effort: failure logs a warning but never masks a successful reload. 9 tests in
  `tests/unit/test_system_catalog.py` pinning the slice payload, all-locales for both
  rooms and devices, null-room AV devices, deterministic version, content-change ->
  hash-change, insertion-order-independence, the live FastAPI route, and the 503 path
  when managers aren't initialised. **Full suite: 442 passed, 0 failed** (was 433,
  +9). openapi.json + UI types regenerated; the catalog DTOs + `GET /system/catalog`
  + the catalog-version MQTT constant all surface in the OpenAPI doc. Hexagonal LAW
  preserved (presentation gained `catalog.py` importing only from `domain.capabilities`
  + presentation schemas; no new cross-layer additions). **Voice integration slice is
  now feature-complete on the bridge side -- #18 is the rack walk with the user at the
  cabinet.**
- **2026-06-06 (§P3.7 slice #15 — canonical action endpoint DONE)** — Irene's first
  live-integration unblock. `POST /devices/{device_id}/canonical` accepts
  `{capability, action, params?}` and resolves canonical → native via the device's
  capability map (using the class → profile → per-device override chain from #14). New
  DTOs in `presentation/api/schemas.py`: `CanonicalActionRequest`, `CanonicalActionResponse`,
  `CanonicalError`, and a `CanonicalErrorCode` enum with the six contract codes. The
  endpoint mirrors the codes to HTTP statuses (404 / 400 / 503 / 500 per the
  `_HTTP_FOR_CODE` map). Synchronous-with-timeout semantics implemented by a one-shot
  `register_state_change_callback` registered BEFORE `perform_action`: AV-style handlers
  update state synchronously inside `perform_action` (the event is already set by the
  time we await it); WB-passthrough handlers publish-and-return and the value-topic echo
  fires the callback when it lands via the MQTT subscription chain. After the wait, the
  endpoint checks `getattr(device.state, "reachable", True)` -- if a per-control
  `meta/error` `r` flag landed during the window (Wirenboard MQTT convention, A3),
  reachable goes False and the endpoint surfaces `device_unreachable` (503). The
  capability action's `param_map` renames canonical param names to native before
  `perform_action` sees them (e.g. `input` → `source` for an LG TV input-select) so
  voice can speak the canonical vocabulary while drivers keep their existing signatures.
  10 endpoint tests in `tests/unit/test_canonical_endpoint.py`: device_not_found,
  capability_not_supported, action_not_supported, param_invalid (matched via keyword
  on the handler's error text; refined later if/when handlers distinguish cleanly),
  device_unreachable on TIMEOUT, device_unreachable on `reachable=False` flip during the
  wait, internal_error, AV-sync happy path, WB-passthrough async-echo happy path,
  param_map rename. **Full suite: 433 passed, 0 failed** (was 423, +10). openapi.json
  + UI types regenerated; new schemas `CanonicalActionRequest` / `CanonicalActionResponse`
  / `CanonicalError` / `CanonicalErrorCode` + the new `/devices/{device_id}/canonical`
  path land in the OpenAPI doc. Hexagonal LAW preserved (presentation imports stay
  presentation → domain only; no new cross-layer additions). **Irene can now integration-
  test against the bridge: the canonical endpoint works against ANY AV device that has a
  capability map (LG TV, Apple TV, eMotiva, …) the moment they're connected -- no
  dependency on the WB-passthrough slice closing.**
- **2026-06-06 (§P3.7 — capability-profile mechanism + light_switch profile + cabinet_spots migration)** —
  User flagged that the per-device capability file authored for cabinet_spots in #14 wouldn't
  scale: ~50-80 WB-passthrough devices would each get a nearly-identical 6-line file.
  Introduced **capability profiles**: a shared map at
  `config/capabilities/profiles/<profile>.json`, referenced from the device config via a new
  `capability_profile: Optional[str]` field on `BaseDeviceConfig`. Resolver order is now
  class → profile → per-instance override (each step optional). **The AV path is unchanged**:
  AV devices don't set `capability_profile`, so the profile-lookup step is skipped and the
  existing class + per-instance behaviour is byte-for-byte preserved — locked by a regression
  test. Slice 1's `light_switch` profile (`power.on/off` → `power_on/power_off`) is
  authored; `cabinet_spots.json` declares `capability_profile: "light_switch"`; the per-device
  `capabilities/devices/cabinet_spots.json` was deleted. Profile catalog documented in §P3.7
  A1 (light_switch / dimmable_light / rgb_light / cover / heating_loop / hvac / sensor_room,
  ~7 files covering ~80 logical devices in bulk). **Side note**: the 3 HVAC units are ESP32-
  based — a dedicated `ESP32ManagedDevice` driver class may land alongside future ESP32 work;
  deferred until we approach HVAC bulk. **§P3.7 #19** (capability vocab extension) updated
  to reflect that the mechanism is now in: it becomes "author the remaining 6 profiles".
  Loader updated (`infrastructure/capabilities/loader.py`: signature gained
  `capability_profile=None`; `attach_capability_maps` passes it through). 2 new loader tests
  in `test_capabilities.py` covering both the profile path AND the AV-path-unchanged
  regression; slice test refined to call `load_capability_map` directly and verify the
  profile resolves correctly. **Full suite: 423 passed, 0 failed** (was 421; +2 from the
  loader tests). openapi.json + UI types regenerated; UI typecheck + lint clean. Hexagonal
  LAW: domain gained the `capability_profile` field (domain stays pure); infra loader change
  stays within infrastructure; no cross-layer additions.
- **2026-06-06 (§P3.7 slice #14 — cabinet_spots wired)** — Slice's first device authored
  per the §P3.7 directory convention. Three files: `backend/config/devices/wb-devices/cabinet/
  cabinet_spots.json` (WB-passthrough config: device_id `cabinet_spots`, bilingual names
  Споты/Spots, `room: "cabinet"`, two commands publishing `1`/`0` to
  `/devices/wb-mr6c_51/controls/K4/on`, state mirror on `/devices/wb-mr6c_51/controls/K4`);
  `backend/config/capabilities/devices/cabinet_spots.json` (canonical `power.on/off` →
  native `power_on/power_off` per the existing capability-map convention shape — `kind:
  "momentary"`, no `state_field` for slice 1); `backend/config/rooms.json` extended with the
  `cabinet` entry (ru "Кабинет", en "Study", de "Arbeitszimmer"; description tags it as
  the §P3.7 slice's test room; `devices: ["cabinet_spots"]`). The `wb_passthrough` entry
  point (added to backend/pyproject.toml during #13) needed `uv pip install -e .` to
  register — done. **New test file** `tests/unit/test_slice_cabinet_spots.py` (4 tests)
  pins the integration: the cabinet_spots.json parses cleanly into `WbPassthroughDeviceConfig`
  (locks the file's shape to the model); the recursive `discover_config_files` walks into
  the `wb-devices/cabinet/` subtree AND still finds the existing flat AV configs (regression
  guard for the convention); the capability map's native command names agree with the
  device config's `commands` keys (catches the easy mistake of renaming one side and not
  the other); the `rooms.json` carries cabinet with the bilingual names + cabinet_spots
  membership. **Full suite: 421 passed, 0 failed** (was 417 — +4 from this slice). Hexagonal
  layering preserved (the new files are config + tests; no code changes). Slice tasks
  remaining: #15 (canonical endpoint), #17 (minimum catalog), #18 (rack verification).
  #15 + #17 can run in parallel.
- **2026-06-06 (§P3.7 — single-room model + wb-devices/<room>/ directory convention)** —
  Contract correction made before #14: **a device belongs to exactly one room**, not a list.
  The earlier draft's multi-room schema (and the `global` room as an opt-in tag for
  "выключи всё") was reversed by the user. Now: `BaseDeviceConfig.room: Optional[str]`
  (was `rooms: List[str]`); `global` is a regular room for whole-house controls only (rare);
  cross-room actions like "выключи свет везде" are Irene's job -- she resolves them from the
  catalog by iterating rooms and firing the relevant capability on each device. Directory
  convention for WB-passthrough configs: `backend/config/devices/wb-devices/<room>/<device_id>.json`
  (one file per logical device, grouped by its room; room sub-directory names use the WB
  HomeUI dashboard ids — non-Cyrillic — `cabinet/livingroom/children/…`). Existing AV
  configs stay flat at `backend/config/devices/*.json`. Implementation: `utils/validation.py`
  config scan switched from `glob("*.json")` to `glob("**/*.json", recursive=True)` so the
  new subtree loads naturally and existing flat AV configs continue to work; #13 test
  fixtures updated (`rooms=["cabinet", "global"]` → `room="cabinet"`); §P3.7 A1 sub-section
  + the contract draft's pillar B + C.5 sections rewritten to match (catalog JSON example
  uses `"room": "living_room"`; the `global` room is illustrated as empty in the sample).
  417 backend tests pass; openapi.json + UI types regenerated; UI typecheck + lint clean.
- **2026-06-06 (§P3.7 slice #13 — generic WB-passthrough driver DONE)** — Foundation that
  #14 (first device config) and #18 (e2e verification) ride on. New
  `infrastructure/devices/wb_passthrough/driver.py` (~180 LoC) implements a fully
  data-driven Wirenboard passthrough: per-command publishing via `MqttClient.publish`,
  per-state-topic subscription via `MqttClient.subscribe`, automatic `<topic>/meta/error`
  companion subscription (Wiren Board MQTT convention from §P3.7 A3), and state mirroring
  through `BaseDevice.update_state` so persistence + SSE callbacks fire normally.
  **Loop guard** is structural and verified by the static chokepoint test:
  `WbPassthroughDeviceConfig.enable_wb_emulation` defaults to **False**, so BaseDevice's
  `_setup_wb_virtual_device` is skipped end-to-end -- without that callback in the chain,
  an incoming value-topic update can't trigger a republish back to the same topic. Payload
  resolution handles WB conventions: static `value` wins; otherwise the first declared
  param's value with int/bool/float coercion (so a range slider "75.0" publishes as
  "75" matching the WB UI). New types added: `WbPassthroughCommandConfig` (topic + value)
  and `WbPassthroughDeviceConfig` (commands dict + state_topics map) in
  `infrastructure/config/models.py`; `WbPassthroughState` (mirrored / reachable /
  error_flags) in `domain/devices/models.py`. `rooms: List[str]` field added to
  `BaseDeviceConfig` (default empty list) so the schema is ready for #14 +
  catalog/rooms work without further changes. Entry point wired in
  `backend/pyproject.toml` under `[project.entry-points."wb_mqtt_bridge.devices"]`.
  15 driver-pattern tests (handler registration, setup subscriptions, write paths
  static + param-derived + missing-param-fails-cleanly, mirror path, error path
  `r`/`rw`/`w`/cleared); the existing chokepoint static guard (now covering 8 device
  drivers including the new one) caught a stray `self.state.connected = ...` in
  shutdown and was promptly removed. Full backend suite: **417 passed, 0 failed**.
  Backend openapi.json + UI openapi.gen.ts regenerated; UI typecheck + lint clean.
  Next slice tasks: #14 (cabinet_spots.json + capability map + room) + #15 (canonical
  POST endpoint) — both can land now.
- **2026-06-06 (§P3.7 slice #16 — device_name → names bilingual migration DONE)** — First
  coding task of the voice-integration slice. Schema: new `LocalizedName` Pydantic model
  (`ru: str, en: str, extra="allow"`) on `domain/devices/config.py`, re-exported from
  `infrastructure/config/models.py`. `BaseDeviceConfig.device_name: str` replaced by
  `names: LocalizedName`. Wire DTOs deliberately kept compatible — `BaseDeviceState.device_name`
  and `LayoutManifest.device_name` stay flat strings projected from `config.names.ru`, so the
  UI's state/layout surfaces don't shift shape; only the *catalog* (Step 5, #17) will consume
  `names` directly. Code sites updated: `BaseDevice.__init__` (`self.names = config.names`,
  `self.device_name = self.names.ru` for back-compat with the existing logging + state init);
  5 driver inits (`apple_tv`, `auralic`, `emotiva_xmc2`, `lg_tv`, `wirenboard_ir_device`) reading
  `config.device_name` → `config.names.ru`; `WBVirtualDeviceService` reads `config.names.ru` for
  the WB virtual device's display (WB UI is ru-default); `layout_engine.py` projects
  `cfg.names.ru` into `LayoutManifest.device_name`; `utils/validation.py` REQUIRED_FIELDS swap.
  All 13 AV configs rewritten with the agreed bilingual pairs (Apple TV / Apple TV; Телевизор /
  TV; Процессор / AV Processor; Усилитель / Amplifier; Стример / Streamer; Медиаплеер /
  Media Player; Апскейлер / Upscaler; Лазердиск / LaserDisc; Видеомагнитофон / VHS;
  Магнитофон / Reel-to-Reel; Вытяжка / Kitchen Hood). 25 fixture replacements across the test
  tree plus 5 contextual fixes (mock-config `.names = SimpleNamespace(...)`; KitchenHoodState
  back to flat `device_name=`; one assertion update). **401 backend tests pass, 0 failed.**
  UI side: `backend/openapi.json` regenerated via `wb_mqtt_bridge.cli.dump_openapi` (new
  `LocalizedName` schema added; BaseDeviceConfig.names $ref'd; runtime DTOs unchanged shape),
  `ui/src/types/openapi.gen.ts` regenerated (95ms, +17 lines net), `useDataSync.ts` updated to
  read `config.names.ru/en` instead of the gone `config.device_name`. **UI typecheck + lint
  clean.** Slice task #16 marked DONE in §P3.7. Next slice task is #13 (WB-passthrough driver
  skeleton) -- the foundation for #14 + #18.
- **2026-06-06 (A3 — wb-mqtt-serial error topic convention nailed; all pre-work DONE)** —
  Closed the last pre-work item for §P3.7's slice. Verified on the live broker AND
  cross-checked against the Wirenboard MQTT-conventions spec
  (`github.com/wirenboard/conventions`): errors are **per-CONTROL**, not per-device as the
  contract initially assumed. Topic: `/devices/{dev}/controls/{ctrl}/meta/error`, retained
  when present, **absent when healthy**. Payload = combinable single-char codes — `r` = read
  error / device reports an error, `w` = write error, `p` = read period miss; compound
  payloads possible (`rw`, `rwp`). Three live `r` samples seen on the broker
  (`wb-msw2_100/Buzzer`, `dooya_0x0101/Position`, `dooya_0x0102/Position`); slice slave
  `wb-mr6c_51/K4` has no error topic at all = healthy. Clearing semantics per spec: after a
  successful read the `r` flag is removed BEFORE the new good value is published (value +
  flag stay consistent); the `w` flag clears only on a successful write. Device-level
  `/devices/{dev}/meta/error` is also defined by the convention but isn't populated on this
  controller from per-control errors — the per-control topic is the authoritative signal.
  **Bridge wiring tightened**: WB-passthrough driver derives error topics **automatically**
  from each `state_topic` (subscribes to `<state_topic>/meta/error`) and additionally to the
  device-level topic for each unique device id — no explicit `error_topic` field in the
  device config. A1's `cabinet_spots.json` example updated to drop the `error_topic`
  placeholder that was a stand-in pending A3. Contract draft tightened in two places (write
  semantics + pillar C.1 subscription rule) to say "per-control `meta/error`" with a
  reference to A3. Documented in §P3.7 as a "Pre-work findings — A3" sub-section.
  **All pre-work A1+A2+A3 done; #13 (WB-passthrough driver skeleton) can start.**
- **2026-06-06 (A1 — slice artifacts nailed for cabinet_spots)** — Concrete-ed Step A1 of
  the §P3.7 voice-onboarding pre-work. Test room: **cabinet** (where the user works —
  physical observation closes the slice verification loop). Three files locked for slice
  authoring: `backend/config/devices/cabinet_spots.json` (WB-passthrough config; explicit
  topics — write `/devices/wb-mr6c_51/controls/K4/on`, value mirror
  `/devices/wb-mr6c_51/controls/K4`, error `…/meta/error` placeholder pending A3),
  `backend/config/capabilities/devices/cabinet_spots.json` (canonical `power.on/off` →
  native `power_on/power_off`), and a `rooms.json` extension adding `cabinet` + `global`.
  **Names bilingual from day one** per the contract's all-locales rule: ru = WB-UI verbatim
  (Споты / Кабинет / Весь дом), en = natural home-context renderings (Spots / Study / Whole
  House). `cabinet_spots` opts into `global` from day one so the multi-room schema gets
  exercised on the slice. Slice voice command: «включи свет в кабинете» / «включи споты».
  Validation steps for #18 written into §P3.7 (5-step rack walk: canonical POST → 500 ms
  response → physical observation → value-echo subscription updates state without
  WB-publish-loop → reverse). Pre-work status: **A1 + A2 done; only A3 (verify
  `wb-mqtt-serial`'s actual per-device error topic shape on the live broker) remains**
  before #13 starts.
- **2026-06-06 (A2 — WB HomeUI config located + composite-control patterns documented)** —
  Resolved Step A2 of the §P3.7 voice-onboarding pre-work. Located the WB HomeUI dashboard
  config at `/etc/wb-webui.conf` → `/mnt/data/etc/wb-webui.conf` (860 KB JSON). 10 real rooms
  identified for the bootstrap importer (`entrance / hall / livingroom / kitchen / wc /
  bathroom / bedroom / children / wardrobe / cabinet`); SVG dashboards + 3 cross-cutting
  dashboards (`safe`, `power` = global scenarios, `av_teaching`) deliberately skipped.
  **Locked the modeling decision: one logical bridge device per cell, NOT per WB slave** —
  cross-room analysis of 40 unique slaves showed **15 (38%) span 2–5 rooms each** (worst
  cases: 3 relay modules + GPIO + `setpoints_floor` all serving 5 rooms; `setpoints_radiator`
  4; the dimmers + `setpoints_curtain` + more relays 3 each). A per-slave model can't answer
  `rooms: […]`, and even single-room slaves often host multiple distinct logical things.
  Expected bulk count: ~50–80 logical devices across 10 rooms. **Documented the
  composite-control shapes** the WB-passthrough driver + capability adapters must handle:
  (a) paired switch + brightness lights → one logical device with `power` + `brightness`
  capabilities (no cross-device composition; just two-capability mapping); (b) heating loops
  (actuator switch + setpoint slider + room-temp sensor, sometimes 3 per room as in cabinet)
  → one logical device per loop with `climate` capability, multi-cell write through the
  capability-adapter layer (#20); (c) RGB strips → `color.set(rgb)` adapter writes the
  `"R;G;B"` string; (d) covers → position slider only, `dooya_dm35eq_x_*/Position`; (e) HVAC
  `hvac_*/*` (7 cells) → single device, full `climate`. `*_permit_schedule` cells are
  wb-rules schedule flags and are skipped during import. **Slice device locked**:
  `wb-mr6c_51/K4 "Споты"` → logical id `cabinet_spots` in `cabinet` room; pure switch, no
  composition; physical observation closes the verification loop because the user works in
  the cabinet. Findings written into §P3.7 of the plan (Pre-work findings — A2 sub-section);
  implementation step list (#13–24) unchanged.
- **2026-06-06 (voice integration contract agreed + new §P3.7 HIGH-PRIORITY phase)** — Reconciled
  the bridge ↔ Irene voice integration contract in this session with the user. The draft from
  Irene's ARCH-7 (`docs/design/voice_integration_contract_draft.md`, originally written by a sister-repo
  agent) had eight open questions; all settled here. Status DRAFT → AGREED 2026-06-06 (same
  filename; commit `f40df01`). **Strategic shift recorded:** the bridge becomes the single
  authoritative device catalog + actuation backend for the whole house — native Wirenboard gear
  AND the AV devices it already bridges — and Irene talks only to the bridge. **wb-rules stays on
  the controller** (unchanged); the bridge MIRRORS native state by subscribing to value topics +
  `wb-mqtt-serial` per-device error topics. Two writers, one truth (the broker). Loop guard on the
  state-sync chokepoint: passthrough devices register persist + SSE callbacks but NOT the
  WB-publish callback (else we feedback-loop with the real device). Three pillars agreed:
  **A** `POST /devices/{id}/canonical` (façade over `perform_action`, 6-code error enum,
  synchronous with 500 ms default echo timeout); **B** dedicated `GET /system/catalog` (NOT the
  Layer-3 UI manifest — flat, capability-shaped, all locales for both rooms and devices, sensor as
  ONE capability with read-only `fields`, multi-room device membership, refresh nudge via retained
  `bridge/catalog/version`); **C** generic data-driven WB-passthrough driver, explicit param types
  (no `meta/type` introspection), composition (RGB / HVAC) in a capability-adapter layer ABOVE the
  driver, `global` room with **explicit membership** (fridge / HVAC / sensors / AV gear
  deliberately excluded from "выключи всё"). Schema changes: `device_name` (single string) widens
  to `names: {ru, en, …}`; **one-shot migration of the ~15 existing AV configs**, no
  backwards-compat shim. New **§P3.7** added to this plan (above) as HIGH PRIORITY — slice of 6
  tasks (~3-4 dev days + rack/Irene verification) for the vertical "включи свет в детской", then
  bulk of 6 tasks (~7-10 dev days) for the full house. Runs in parallel with the §5.1 rack pass
  (different surfaces); settles before §P4. Irene's ARCH-8 implementation plan
  (`wb-mqtt-voice/docs/design/mqtt_integration.md` §10) is **unblocked** by this. Memory
  unchanged (no new entries needed — the contract is in the doc, the priority is in this plan).
- **2026-05-30 (rack pass on eMotiva + 2 sibling-library handoffs + LG TV silent-WS-death fix + eMotiva cleanup + HDMI ARC scenario)** — Long afternoon/evening session. **eMotiva row of §5.1 #7 substantively closed at the rack:** power on/off both zones (independence verified in BOTH directions), zone-2 volume change (independent of zone 1), zone-2 mute (acked but no audible effect — empirically confirms the protocol §4.2 read-back gap is mirrored by an apparent write-side gap on the XMC-2; kept exposed per user direction). All driver findings flow correctly through the pymotivaxmc2 dispatcher → `_handle_property_change` chokepoint; the 2026-05-29 "intermittent No ack received" issue did NOT recur. **Side observation:** controller has no bridge running (`wb-mqtt-bridge.service` inactive, no Docker container; §P3 #8 INSTALL.md cutover still pending) — the live home was being served entirely by the dev-box backend (PID 121053). No client-id collision because production wasn't running. Worth flagging: the house is currently 100% dependent on the dev-box backend for MQTT bridging. **Two sibling-library handoffs round-trip (both shipped same day):** (a) `asyncwebostv` 0.3.4 → **0.3.5** — `_close_callbacks` now fire from `_handle_messages`'s `ConnectionClosed` branch (remote-side close), not just from the consumer's explicit `close()`. Same registry, two firing points, semantic now "the connection is gone by any means." Triggered by today's rack observation: LG TV WebSocket closed at 14:03:41 with no preceding subscription event, bridge state stayed `power:on / connected:true / current_app:ivi` for 15+ minutes until a manual API query exposed the lie. (b) `pymotivaxmc2` 0.6.8 → **0.6.9** — `subscribe()` now also dispatches initial property values through registered `@on(prop)` callbacks (the same path as ongoing notifications). Unifies subscribe-time + notification-time delivery under one channel. Library Claude also unified `EmotivaController.subscribe` onto the lower-level `Protocol.subscribe` (was returning None fire-and-forget; now waits for confirmation and returns the dict) — correctness improvement noted in handoff round-trip. **Three bridge commits.** `afe334f` **fix(lg_tv): detect silent WebSocket death + auto-recover via close callback + health loop** (closes #23). Wires the new asyncwebostv 0.3.5 callback. Adds `_on_websocket_close` (driver-side; flips `connected=False`, clears `_subscriptions_active`; no-op during `_shutting_down`; leaves `power` untouched — could be a transient hiccup), `_tcp_probe` (asyncio.open_connection to port 3001, no payload; read-only liveness signal that won't WoL the TV), and `_health_loop` (background task running every `reconnect_interval` seconds — default 30s; 4-state machine over connected×reachable). Time-to-truth on silent WS death drops from ∞ to ≤75s (45s WS-close timeout + 30s health tick) even when the power-state subscription event mysteriously doesn't fire (today's Bug A; separate investigation when reproducible). 11 regression tests covering callback semantics, TCP probe (success/timeout/OSError/no-IP), health-loop state machine all 4 quadrants + cancel + boot-with-TV-off. `02d11d4` **refactor(emotiva): single update path via notifications + drop verified-safe optimistic writes** (closes #21 + #22). Library bump to 0.6.9 lets `setup()` drop `_refresh_device_state()` — subscribe auto-dispatches initial values via callbacks. Dropped post-ack optimistic writes from `handle_set_volume` (both zones — notifications rack-verified to fire ~180ms after ack) and main-zone `handle_power_on` (existing post-command refresh covers state seeding). KEPT optimistic writes for power_off (both zones), zone2_power_on (push behaviour unverified for this specific command path), and mute (both zones — protocol-impossible read-back per §4.2). Each remaining optimistic write has a docstring explaining WHY it stays, to prevent cargo-cult removal. Dead-code removed: `status(Property.ZONE2_MUTE)` line in `_synchronize_state` (would AttributeError — Property.ZONE2_MUTE doesn't exist in pymotivaxmc2's enum, which correctly mirrors the protocol's command-vs-notification split); unreachable `mute` branches in `_handle_property_change` + `_process_property_value`. **Important framing from the discussion:** the library's enum split was always correct (Command has MUTE/ZONE2_MUTE; Property doesn't) — the "pretending mute is subscribable" was entirely bridge-side dead code, NOT a library issue. 12 regression tests covering the notification-driven path + guards against re-adding the dropped writes. `e5dffa4` **feat(scenarios): symmetric src_port mechanism + tv_on_speakers scenario (HDMI ARC)** (closes #24). Pre-investigation findings: HDMI ARC isn't bindable to an Input button on the XMC-2 (per-Input Setup menu's Audio Input override doesn't list ARC — user verified at rack); the protocol's `Command.ARC` is in the same family as raw HDMI connectors (`hdmi1-8`) and **hangs the device** when sent (user rack-verified — same family that caused the 2026-05-29 black-rectangle issue, fixed by migrating to `select_source(N)`); the reliable mechanism is the eMotiva's auto-engagement on power-up when CEC is on AND the TV is on internal mode (NOT HDMI). Implemented as a **clean reconciler extension** (instead of the legacy `startup_sequence` escape hatch): the reconciler now treats topology `src_port` symmetrically to `dst_port` — when a source device's `input` capability declares `source_modes`, the reconciler emits `set_input(src_port)` on the source. **LG TV opts in** with `source_modes: ["arc"]`; driver translates `set_input_source(arc)` → `handle_home` (no webOS API for "go to internal mode"; pressing Home satisfies the eMotiva's ARC precondition). **eMotiva `handle_set_input(arc)`** triggers `_power_cycle_for_arc` (off → 3s sleep → on, with already-satisfied short-circuit when state.input_source is already "arc"). `_source_token` maps the device's raw `"HDMI ARC"` → canonical `"arc"` token (needed for the already_satisfied check to work — without it the reconciler would power-cycle on every activation). **Topology unchanged** — existing link `living_room_tv:arc → processor:arc` + 3 ordering rules (lines 43-46) already encoded the design intent perfectly. Other source devices silently skipped — only LG TV opts in via `source_modes`. New scenario `config/scenarios/tv_on_speakers.json` — thin, reconciler-driven, no `startup_sequence`. **HW verification still owed** by the user at the next rack session (restart the bridge first to pick up all today's changes). 13 regression tests covering symmetric src_port behaviour, opt-in vs silent-skip (Auralic streamer's "out" src_port would otherwise trigger), ARC token mapping, power-cycle short-circuits, LG TV's home-button translation. **Day totals across both 2026-05-30 entries:** 7 commits (`63b2846` + `e7cbcb5` + `2ca40fa` + `afe334f` + `02d11d4` + `e5dffa4` + this one), 401 tests passing (was 365 at start of day; **+36 net**), 4 backlog tasks closed (#21/#22/#23/#24), 2 sibling-library bumps shipped same day (asyncwebostv 0.3.5, pymotivaxmc2 0.6.9), 1 new scenario, 1 new architectural primitive (symmetric src_port in reconciler — reusable for any future device with a source-side mode quirk). Hexagonal LAW clean across all commits.
- **2026-05-30 (state-management audit → 2 stale-scenario-state bugs fixed + snapshot retired + chokepoint static guard)** — User-prompted audit of "how does device + scenario state actually work, what gets updated when, does the reconciler see manual device-page fixes." Answer for **device state**: every action source (FastAPI / WB MQTT-in / driver subscription / driver polling) routes through the single `BaseDevice.update_state(**)` chokepoint (`infrastructure/devices/base.py:639`) → fan-out to `state.db` persistence + WB value-topic publish + SSE broadcast. Per-driver verification: LG TV (3 webOS subscriptions), Apple TV (5 pyatv listeners), Auralic (polling loop), eMotiva (9 property callbacks) all chokepoint-clean; zero direct `self.state.X = Y` runtime assignments (LG TV's 2 `__init__`-only ip/mac copies are the documented exception). The 2026-05-27 LG TV cleanup (33 violations → 0) held across all four feedback drivers. **IR-family drivers** (`WirenboardIRDevice` / `RevoxA77` / `BroadlinkKitchenHood`) have no inbound feedback channel — optimistic state is structurally fragile and **only the 2 Wirenboard IR power handlers (`:235` / `:270`) carry idempotence guards** (input/volume/transport always send: nothing to compare against); the toggle handler at `:206` always sends too. Filed **§5.1 backlog item — per-action `force` flag** (commit `63b2846`) as the precision escape hatch for IR desync, with explicit non-goal of a scenario-level force (would fire toggle-code devices the wrong way). Answer for **scenario state / reconciler**: reconciler reads fresh `device.get_current_state()` at every `switch_scenario` (`reconciler.py:341`, no cache); a manual fix on a device page IS picked up at the next activation. **BUT the audit surfaced 2 real bugs** in `/scenario/state`: **Bug 1** `GET /scenario/state` (no-args, `routers/state.py:155-158`) returned the stale `ScenarioManager.scenario_state` snapshot (set once at activation by `_refresh_state()`, never refreshed) — exactly the failure mode the docstring on `get_scenario_state(id)` at `service.py:469-472` explicitly warned against; **Bug 2** the live recompute path in `get_scenario_state(active_id)` silently dropped `manual_steps` (activation-scoped notes from the 2026-05-26 transition-aware-manual-notes work would have been invisible to the per-scenario endpoint). **Fixes + cleanup** (commit `e7cbcb5`): live recompute now threads `list(self._activation_manual_steps)` through; no-args endpoint routes through the live recompute; with `get_scenario_state()` feature-complete the snapshot + `_refresh_state()` + their 3 callers became redundant — deleted. The 3 SSE broadcasts (`scenario_switched` / `scenario_started` / `role_action_executed`) that embedded the snapshot in event payloads now build payloads from `get_scenario_state(current_scenario.scenario_id).model_dump()`. Truthiness checks moved to `current_scenario` (the real sentinel). Single source of truth = `device.get_current_state()` walked at query time, no frozen snapshot anywhere. Persistence + restore paths untouched (they only depend on `scenario_id` under key `"active_scenario"`). **New static regression test** `test_chokepoint_static.py` — AST-based, auto-discovers via `glob("*/driver.py")`, parametrizes per driver, asserts no `self.state.X = Y` outside `__init__` (allows the documented LG TV exception). Plus 2 functional regression tests on `ScenarioManager` (live recompute reflects post-activation device changes; manual_steps survive every query). 4 existing test files rewired to query via `get_scenario_state()` instead of the deleted snapshot. **365 passed**. Hexagonal LAW clean (domain scenarios service + presentation only).
- **2026-05-29 (Auralic streamer — research → robustness hardening pass; OpenHome is the RIGHT protocol)** — The `streamer` (Auralic Altair G1, `AuralicDevice` via `openhomedevice`) "never really worked." Broad web research (4 agents) + code review concluded the **protocol choice is correct and the only viable one**: Auralic is an **OpenHome device, not a standard UPnP-AV renderer** (no usable `AVTransport`), so DLNA/`async_upnp_client` DmrDevice would be *worse*; the failures are robustness + Auralic quirks. Implemented a hardening pass (mock-tested; **HW verification still owed by the user**, device is on **wired LAN**): (1) per-call timeouts via an `_op()` `wait_for` wrapper on every OpenHome call (a wedged/standby unit could hang the poll loop or an action); (2) `_update_device_state` does a fast liveness probe (`is_in_standby`) first and bails on failure instead of firing 5 more calls; (3) **auto-rediscovery** — the periodic loop now re-runs SSDP discovery every `reconnect_interval` (default 60s) when the connection goes stale (Auralic reassigns its HTTP port on every boot), instead of only recovering on an explicit IR power-on; (4) rate-limited connected↔unreachable transition logging (no per-interval traceback flood, openhomedevice #18); (5) **real bug fixed:** `handle_next` called `skip()` with no arg but the lib signature is `skip(offset)` → "next" always threw; now `skip(1)`, and `handle_previous` implemented as `skip(-1)` (was stubbed "unsupported"); (6) `None`-tolerant volume/mute (units without a Volume service return None → don't write into the non-optional state fields; mute reports a clean failure); (7) track-metadata parsing isolated so a garbled DIDL can't drop the device to disconnected; (8) **(a)** discovery rewritten async (aiohttp; SSDP callback only collects locations, classification fetched off-loop) — dropped the blocking `requests.get` and the thread-pool `asyncio.run` sync-wrapper. Config gained `op_timeout` (5.0) + `reconnect_interval` (60). **(b) decision — fork KEPT:** upstream `openhomedevice` 2.3.1 still hard-requires `lxml>=4.8.0` (confirmed via PyPI — the earlier "2.3.1 removed lxml" claim was wrong; the *fork* removed it). The fork = upstream 2.3.1 code minus lxml (stdlib ElementTree); the lean Docker final stage has no `libxml2`. So we kept the fork pin and instead **pinned `async_upnp_client>=0.40,<0.45`** as a direct dep (prevents the #23 DIDL-parse break from a transitive bump; `uv.lock` regenerated, 0.44.0 unchanged). Tests: Auralic suite 18→22 (skip offsets, None-volume, metadata-error-keeps-connected, liveness fast-fail, op_timeout, reconnect wiring); full suite **356 passed**. See [[auralic-streamer-openhome-direction]].
- **2026-05-29 (IR ROM tooling cleanup — general-purpose, all-banks backup, jitter-tolerant verify, `temp/` gone)** — Refactored the WB-MSW v3 IR ROM scripts per the user's direction: the backup/verify/restore code must be a **general-purpose tool with zero A/V knowledge**, and `wb-rules/temp/` must go. (1) New `wb-rules/ir_common.py` — the shared, single-source-of-truth core: the full WB-MSW v3 register map, the `modbus_client` caller, base64↔reg codec, `read_size`/`read_bank`, and a jitter-tolerant `compare(exp, got, tol)` (lengths must match exactly; each register within `tol` 10 µs quanta; `tol=0` ⇒ byte-exact). `JITTER_TOL` default 8 comfortably exceeds the observed ±~3-quantum learned-code jitter while still catching gross corruption. (2) `ir_backup.py` no longer scans device configs for `rom_position`/`Play from ROM` references — it iterates banks 1–80, reads each ROM's size (`5399+N`), and **dumps every bank that has content**. CSV schema changed: dropped the `referenced_by` column (now `blaster,modbus_address,rom,code_size_bytes,code_base64,status`); added `--sizes-only` inventory + `--banks` range. (3) `temp/verify_banks.py` **promoted** to `ir_verify.py`: read-only, jitter-tolerant, reports each bank as EXACT / ~jitter / MISMATCH and prints a first-diff dump on mismatch — which **folds in `diag_rom65.py` + `diag_chunk.py`** (both deleted). (4) `ir_restore.py` deduped onto `ir_common`; its in-run verify now uses the tolerant `compare` (so the 7 jittery 207 banks pass without `--keep-going`); stays tolerant of old-schema CSVs. (5) `wb-rules/temp/` deleted. (6) New `wb-rules/scp_ir_tools.sh` deploys the tools (+ any local CSVs) to `/tmp/ir-tools` on the controller, with an optional `pull` mode to fetch produced `ir_backup_*.csv` back into the repo (the old ad-hoc `scp … :/tmp/` flow is retired; `scp_wb_rules.sh` only ever deployed the rules-engine dir, not these). (7) New **`ir.py`** unified CLI fronts all three as subcommands (`ir.py backup|restore|verify …`) — each module exposes `add_arguments(parser)`+`run(args)`, the shared bus flags (`--port/--baud/--parity/--stopbits/--no-toggle-service`) come from `ir_common`, and the stop/start-`wb-mqtt-serial` window is now a single `ir_common.bus_window` context manager (was duplicated in all three); the modules stay standalone-runnable too. All five `py_compile` clean; `ir_common` unit-checked (parse_banks, codec round-trip, compare exact/within-tol/over-tol/length, tol=0 strict); both `ir.py restore …` and standalone dry-runs load the old-schema 220 CSV fine. **Not run end-to-end on hardware** (no need — the live fix already proved the mechanism); the only open IR item is the user's functional *play* test of the 7 large jittery banks.
- **2026-05-29 (mf_amplifier root-caused — an `ir_restore.py` edit-lock bug, NOT firmware — fixed live + tool hardened)** — The "mf_amplifier broken" symptom traced end-to-end to: **bank 65 (`ld_player:tray`) stuck in edit mode** on `wb-msw-v3_207` (coil `5199+65`=1). A bank left in edit mode makes the WB-MSW return **Modbus exception 06 "Slave Device Busy"** for *every* `Play from ROM N` — which is why the amp *and* the known-good ROM5 both failed. **Root cause = bug in `ir_restore.py:write_bank`:** it entered edit (coil=1) with **no try/finally**, and the commit (coil=0) can transiently fail with "busy" right after a large RAM write (`_ok` treats that as failure → raises) → the edit coil is left at 1. No reboot needed — the bug alone does it. Diagnosis: WB support AI (Play = holding `5500`, added fw 4.18.0; coil errata ERRWB-MSWv30012 fixed 4.31.5 — we're on **4.37.0**, so not that) + `modbus_client --debug` (raw exception **06**; crucially **ROM content AND ROM-Size `5399+N` match the backup exactly → the restore *content* is vindicated**; byte-verify simply can't see a *play* lock). **Fixed live** by reload-then-commit on bank 65 (`5501`=65 then coil `5264`=0) → amp responds; both the `5500` path and the coil-`5100+` path the bridge uses now succeed (**no template change needed**). **`ir_restore.py` hardened** (committed): `write_bank` guarantees edit-exit via try/finally (reload committed ROM→RAM + commit prior content on failure), retries busy-prone RAM/commit writes (`WRITE_RETRIES`), and a **preflight `clear_stuck_edit`** scans coils `5199+N` (banks 1–80) per slave and clears any stuck bank before restoring. Controller is stale (WB7 7.2.1, testing channel, 146 pending updates; `wb-mqtt-serial` 2.178.0 vs 2.248.1 candidate) but that was not the cause. **§5.1 #7 `WirenboardIRDevice`/mf_amplifier now works.**
- **2026-05-29 (§5.1 #7 — eMotiva input→logical-source clean cut committed + HW-verified; kitchen hood OK; mf_amplifier broken)** — Reworked the eMotiva input path from physical HDMI connectors to **logical sources**, after the rack proved selecting `hdmiN` does a raw-connector switch that bypasses the input's A/V profile (black-rectangle / wrong-source artifact). The whole stack now uses the canonical `sourceN` token: driver `set_input`→`select_source(N)`, `get_available_inputs`→visible Input-button names via `get_input_names()`, and device source-NAME→`sourceN` feedback translation (all device-specific mapping in the driver; **reconciler unchanged & device-agnostic — hexagonal preserved**); topology `processor:hdmi1/2/3`→`source1/2/3`; pymotivaxmc2 bumped 0.6.7→**0.6.8** (sibling lib gained `select_source`/`get_input_names`/configurable `ack_timeout` this session). Committed `24aad19`; 349 tests pass. **HW-verified:** source1 (ZAPPITI) + source2 (HDMI 2/AppleTV) switch cleanly, feedback converges, no no-ack. Remaining for the eMotiva row: zone1/zone2 power + independence, volume, scenario route (needs topology reload). **Other rows tested this session:** `BroadlinkKitchenHood` (kitchen_hood) **WORKS** (tested). `WirenboardIRDevice`/**mf_amplifier BROKEN** — IR commands report success (WB IR topic published) but the Musical Fidelity M6si doesn't respond; user suspects a firmware-update relation. Lead: mf_amplifier IR codes live on `wb-msw-v3_207` (which underwent the firmware-upgrade IR-ROM wipe + restore) — though its power/vol banks (ROM17/18, small) verified OK in that restore, so the cause may be elsewhere; relates to the §5.1 "IR ROM backup/restore — functional test" item. **eMotiva driver findings logged:** (#1) zone-2 mute read-back is protocol-impossible (mute is command-only — confirmed in lib + Emotiva protocol doc) → mute is optimistic-only, drop the dead `status(ZONE2_MUTE)` sync; (#2/#3) intermittent `No ack received` (lib: positional/uncorrelated acks + shared control-port queue; 0.6.8 makes `ack_timeout` configurable, correlation deferred); (#4) driver `shutdown()` should skip unsubscribe when never connected.
- **2026-05-28 (IR ROM backup/restore — HW verification + 207 diagnosis; WB-MRGBW-D firmware-recovery side-quest)** — Verified `ir_restore.py` against the three captured WB-MSW v3 blasters on the controller. **220** (2 banks) + **218** (14/14) restore clean once the verify read gets a 6× spaced retry (`f0213af`) — the earlier "mismatches" were transient post-commit reads, not bad writes. **207** has 7 persistent mismatches on its large learned `ld_player`/`vhs` codes (ROM65/66/68/69/70/78/79); diagnosed **stored-side, not corruption**: `diag_chunk.py` showed the first-diff index is invariant to read-chunk size, and the codes are multi-repeat frames already carrying per-repeat capture jitter (±~3 quanta) in the backup — the exact magnitude of the restore delta. Filed as a new §5.1 backlog item (continue-or-cleanup, gated on a functional IR test the user owns). Recovered the verification/diagnostic scripts into `wb-rules/temp/` (`34fd1ee`) after a dev-box reboot wiped `/tmp`. **Side-quest:** WB-MRGBW-D slave **238** was stuck in bootloader from an interrupted `wb-device-manager` update — completed it to fw **3.7.1** via `wb-mcu-fw-updater update-fw /dev/ttyRS485-1 -a 238 --version 3.7.1` (the `recover` subcommand only flashes *latest*; see [[wb-fw-update-recovery]]), confirmed `3.7.1` on-device (holding reg 250), and surgically cleared only the stale slave-238 entry from the retained `wb-device-manager/firmware_update/state` topic (read-modify-write, other devices preserved).
- **2026-05-28 (§5.1 #7 — AppleTVDevice row DONE on both units, tvOS 26.5)** — Long rack arc; the headline is a **tvOS-side discovery, not our code**. Symptoms at the rack: power read as off, empty app list, `set_volume` 5 s timeouts, pointer dead. Root cause (proven with a vanilla `atvremote` + `--debug` opack traces): **tvOS 26.4/26.5 silently drop Companion *query* commands** (`FetchAttentionState`→power, `FetchLaunchableApplicationsEvent`→app list) unless the client sends a `TVRCSessionStart` handshake at connect — fixed on pyatv master (#2855) but in no release. `companion/api.py` is byte-identical 0.16.1→0.17.0, and upstream issues #2845/#2856/#2823 confirm it's tvOS, unfixed by any release. **Pinned pyatv to master SHA `9177803`** (`37bd20e`; same immutable-SHA pattern as openhomedevice; dependency-pin guard tests updated; exit = move to the first release with #2855) → power + app-list verified working on the actual tvOS 26.5 units. **Volume is a separate, still-open tvOS gap** (#2524): the device never advertises the `_mcF` Volume flag (idle=0, playing=14, Volume bit `0x0100` never set) so the Companion volume event/`set_volume` channel is dead, and even HID VolumeUp is accepted-but-ignored — confirmed remote ATV volume is unsupported here (matches pyatv docs: HomePod/AirPlay = full, CEC = up/down, **IR = none**). Resolution: removed absolute `set_volume` (driver+configs+capability+`AppleTVState.volume`; volume UI → up/down buttons, mf_amplifier-style, no slider/mute — manifest-only, both oracles regen) (`54a014c`), then routed `volume_up`/`volume_down` through the **WB IR blaster** (Auralic-style `ir_volume_*_topic`: living `wb-msw-v3_207` ROM5/6 `ac8c19c`, children `wb-msw-v3_220` ROM1/2 `dff628d`) — IR volume change verified audible + clean in the log on both units. Also fixed along the way: **Apple TV driver review vs pyatv 0.17.0** (`0463480` — B1 weakref-listener strong-ref, B2/B3 volume contract, B4 push_updater, B5 `["success"]`, B6 PowerListener); **pointer pad** (`5175998` — UI sends `{dx,dy}` but handler read `deltaX/deltaY`; click→`touch_at_position` needed coords → remapped move param + click→`select`, dropped dead `touch_at_position`). Apple TV row is **fully closed** (power/app-list/nav/playback/pointer/volume all working on living + children). Next §5.1 #7 row: `EMotivaXMC2`.
- **2026-05-28 (pointer-flood fix + LG input fix + CI bump — adjacent to the ATV row)** — (1) **PointerPad flooded the action path**: `onMove` fired a backend command per native mouse/touch event (60-120/s) → service.log grew MB/min. Fixed UI-side with an accumulate-and-flush throttle (~16/s, lossless delta sum, tap stays click-only) (`a4c52a0`); backend-side, the state-change chokepoint now skips persist + WB-publish for `last_command`-only changes (`683a82b`, `_EPHEMERAL_STATE_FIELDS`; 7th chokepoint test), and `DeviceManager.perform_action`'s redundant per-action `_persist_state` was removed (`173589f`) — both confirmed at the rack (zero per-move SQLite writes). (2) **LG `set_input` never worked**: config/capability/reconciler all use action `set_input_source`/param `source`, but the driver registered `handle_set_input`/`params["input"]` AND called a non-existent `source_control.set_source_input` — fixed to `handle_set_input_source` + `input_control.set_input` (`5ed71d1`+`1d7807e`); HDMI2 switch verified live. Classic [[mock-tests-miss-driver-bugs]] (reconciler tests use mock devices). (3) **CI** actions `checkout`/`setup-python`/`setup-node` bumped `@v4`→`@v6` (Node 24) ahead of the 2026-06-02 deprecation cutoff (`02eccce`). One-off ARM image build dispatched + GHCR-pushed (both images green).
- **2026-05-28 (§5.1 #8 — clean shutdown DONE, HW-verified)** — Shipped the shutdown-hang fix and verified it fully clean at the rack on a **single Ctrl-C**. The 2026-05-27 diagnosis was correct but the fix grew to **4 commits** as each layer surfaced at the rack: **Part 1** `c3f0305` — SSE generators poll uvicorn's `Server.should_exit` (new `sse_manager._shutdown_signaled()` + `set_uvicorn_server()`; `app/main.py` switched from `uvicorn.run(...)` to low-level `Config`+`Server` so the live server reaches the SSE manager) → 1st Ctrl-C drains the long-lived SSE connections instead of hanging. **Part 2** `bfa9614` — discovered by introspection that pyatv's `AppleTV.close()` is **sync but returns `Set[asyncio.Task]`** (cleanup tasks the caller must await) — the driver was dropping it, orphaning 2 aiohttp ClientSessions per shutdown (the original "Unclosed client session" smoking gun). Now `asyncio.wait_for(asyncio.gather(*tasks), 2.0)` + cancel stragglers. **Part 3** `1ada043` — the lifespan teardown blanket-cancelled `asyncio.all_tasks()` minus current, which **includes uvicorn's own serve task** (parked in `lifespan.shutdown()` awaiting us); cancelling it surfaced a `CancelledError` traceback out of `asyncio.run` + an orphaned `_GatheringFuture`, and prematurely killed the MQTT task before the ordered disconnect. Block deleted — ordered teardown stops owned tasks, `asyncio.run` cancels stragglers after the lifespan returns. **Part 4** `607b544` — uvicorn's `Server.capture_signals` deliberately **re-raises the captured SIGINT** post-graceful-shutdown (server.py:326-330) so an embedder sees standard Ctrl-C semantics; the asyncio runner turns that into a `KeyboardInterrupt` out of `server.run()`. uvicorn's CLI relies on click catching it — our console_script `main()` now wraps `server.run()` in `try/except KeyboardInterrupt` for a quiet exit. **Rack result:** single Ctrl-C → full bootstrap sequence, both Apple TVs "pyatv cleanup tasks completed cleanly (2 task(s))", "System shutdown complete" → "Application shutdown complete." → "Finished server process", immediate prompt, zero unclosed-session / threading / traceback noise. 343 tests pass throughout; hexagonal LAW clean (composition-root + presentation only). **§5.1 #8 closed.** Next HW-gated work: §5.1 #7 `EMotivaXMC2` row.
- **2026-05-27 evening (§5.1 #8 — shutdown-hang root cause diagnosed + actionable item filed)** — After the LG TV HW pass, attempted to shut down the backend; reproduced the morning's "3 Ctrl-Cs + multi-minute hang" pattern AND captured the terminal tracebacks that morning's read of the log file couldn't show (asyncio's `KeyboardInterrupt` traceback goes to stderr, not the bridge's logger). **Full causal chain now confirmed end-to-end**, summarised in §5.1 #8: SSE generators don't respond to shutdown → 1st Ctrl-C hangs on SSE → 2nd Ctrl-C raises `KeyboardInterrupt` in `runners.py:157` → starlette lifespan is at `await receive()` waiting for `lifespan.shutdown` message that never arrives → lifespan generator gets `GeneratorExit` (not `CancelledError` — `bootstrap.py:359`'s try/except can't catch it) → after-`yield` block is structurally unreachable → `device_manager.shutdown_devices()` never runs → Apple TV's pyatv teardown never happens → Python's `threading._shutdown()` blocks indefinitely waiting for pyatv's non-daemon zeroconf threads → `Exception ignored in: <module 'threading'>` traceback on the 3rd Ctrl-C → GC dumps 2 `Unclosed client session` aiohttp warnings (one per AppleTV instance). This session's hang was 3 min 2 s (morning's was 50 s — varies with pyatv state); 3rd Ctrl-C was always required to fully terminate. **Original P4 #6 "Teardown noise" sub-item marked SUPERSEDED** — §5.1 #8 has the full diagnosis + concrete 2-part fix path (~40 LoC: (1) SSE generators respond to `Server.should_exit` so 1st Ctrl-C drains naturally; (2) Apple TV `shutdown()` wraps `pyatv.atv.close()` in `asyncio.wait_for(..., timeout=2.0)` to bound the teardown). **Not blocking** the per-driver HW pass — workaround at the rack remains `kill -TERM` or the 3-Ctrl-C dance (state preserved through chokepoint persistence). To be picked up at the next session start.
- **2026-05-27 (§5.1 #7 — LG TV row DONE on living-room OLED77G1RLA)** — End-to-end on-hardware verification pass of the LG TV driver against the LG OLED77G1RLA (webOS 6.x), exercising every path the audit + library cleanup touched. **All audit-flagged bugs verified fixed live:** (1) `subscribe_power_state` URI flip to `tvpower` works — the canonical canary test was the user pressing the physical TV-remote power button (`reason=remoteKey` captured in the subscription payload); driver state flipped to `power='off'` in ~0.5 s after the actual state transition (and ~45 s before the WebSocket finally closed — the whole pre-fix "TV-off invisible until socket dies" gap is closed). (2) `subscribe_get_volume` `volumeStatus` unwrap works — 4 physical-remote volume-up deltas (21→22→23→24) captured live. (3) `subscribe_get_current` foreground-app subscription works — home/launch_app/browser/power-off-empty-string transitions all delivered. (4) `current_app` + `input_source` coalesced via `app_id_to_input_id` helper — when on `com.webos.app.browser` (or any internal app), `input_source` correctly clears to `None` rather than fabricating a stale HDMI value (the spec-research answer to the "subtle question" from handoff #3). (5) Pointer pad: movement works end-to-end via library's pointer-socket plain-text protocol; click was UI-side broken (defined-but-never-passed `_handleClick`), fixed in `bf5347d` with tap-vs-pan detection in PointerPad — verified live with `Sending pointer command: type:click` lines in the log. **Chokepoint dedupe verified working** — webOS double-fires power-state events during the goodbye animation (3× `Active Standby` + 1× `Suspend` for one off press); only the first transition actually changed state, the rest were correctly suppressed by the `changed_fields` early-return; zero spurious persistence writes. **Bonus observation:** the subscription payload includes a `reason` field tagging the source of each state change (`remoteKey` / `homekit` / ...) — useful for diagnostics and potentially for source-attribution in scenarios. **Out-of-scope finding (not pursued):** HomeKit cascade — your HK integration reacts to the TV state and fires its own follow-on power-state requests (`reason: homekit`), captured here only as an environment observation. **Deferred (non-blocking):** `children_room_tv` (LG OLED55C6D) smoke pass — config-only difference, expected to mirror; reconnect-cycle test (TV power-cycle / unplug → reconnect to exercise asyncwebostv 0.3.4's close-callback registry + the "discard old controls" reconnect contract). Today's commits: `ec90bc4` (bump asyncwebostv 0.3.1→0.3.4) · `feb1c30` (pointer rewrite + drop absolute `move_cursor` action) · `295ff0a` (input_source via foreground_app + `app_id_to_input_id`) · `bf5347d` (PointerPad tap-vs-pan). LG TV row of §5.1 #7 is **substantively done**; next driver row to walk = `EMotivaXMC2` (the next-most load-bearing driver — every movie scenario routes through it).
- **2026-05-27 (CI Python pin — 3.11.12; broken since 6a61766)** — CI was failing on every push since 2026-05-26 (commit `6a61766`). Root cause was NOT in that commit's diff (which only touched the ARM-image build steps): the floating `python-version: '3.11'` in `actions/setup-python` drifted to 3.11.15 on the current Ubuntu-24.04 runner image, which enforces strict `asyncio.Future()` / `get_event_loop()` behaviour in sync fixture contexts. 13 tests in `test_revox_params.py` + `test_wirenboard_ir_params.py` raised `RuntimeError: There is no current event loop in thread 'MainThread'` at fixture setup — three sync fixtures were building `MagicMock(return_value=asyncio.Future())`. Two-pronged fix (`d1e91df`): (1) **pin** — new `backend/.python-version` = 3.11.12 (single source of truth; uv reads it locally; CI's `actions/setup-python` switched from `python-version: '3.11'` to `python-version-file: backend/.python-version`). Closes the long-standing §6 "Still pending" item from the 2026-05-22 wrap-up audit. (2) **rewrite the brittle pattern** — the 3 sync fixtures now use `AsyncMock(return_value=...)` instead of MagicMock-returning-a-Future. Same observable behaviour, no Future at fixture-build time, future Python bumps can't re-break us this way. CI verified green (1m35s). Suite: 343 passed locally (unchanged by the fixture rewrite).
- **2026-05-27 (LG TV listener audit → asyncwebostv 0.3.0 → 3 real-time subscriptions)** — Pre-flight audit before the §5.1 #7 LG TV row found the driver was pure polling at connect time (`_update_volume_state` / `_update_current_app` / `_update_input_source` called once, then never again; **zero `subscribe_*` calls**). Physical-remote actions (volume change, power-off via remote, app switch via launcher) were invisible until the next bridge-originated command. Written up a handoff note for the sibling library (`asyncwebostv` — also user-owned) at `~/development/asyncwebostv/docs/wb-mqtt-bridge-handoff-2026-05-27.md`: required fix (`WebOSClient.close()` must clear `waiters` + `subscribers`) + 7 other meaningful checks (callback-signature verification, `cancelSubscribe` protocol message, ping/pong rationale comment, foreground-app subscription marker, concurrent connect safety, reconnect-and-subscriptions contract, power-state value mapping). Library owner shipped **v0.3.0** the same day (asyncwebostv `3787638`): all required + recommended checks actioned, including production-verified power-state value mapping ("Active" / "Screen Off" / "Screen Saver" → ON; "Active Standby" / "Suspend" / "Power Off" / None → OFF) ported from `aiowebostv` + `aiopylgtv`. Driver work in two commits: (1) `5a382eb` bumps `asyncwebostv` 0.2.7 → 0.3.0 in `backend/pyproject.toml`; transitive deps `aiofiles`/`aiohttp-socks`/`aiohttp-sse-client` pruned by the library, verified none were imported directly by wb-mqtt-bridge. (2) `5a09fd1` adds 3 real-time subscriptions to `infrastructure/devices/lg_tv/driver.py`: `MediaControl.subscribe_get_volume` (volume + mute), `SystemControl.subscribe_power_state` (power transitions), `ApplicationControl.subscribe_get_current` (foreground app). All callbacks route through `self.update_state(...)` so the chokepoint chain (persistence + WB-publish; see entry below) runs automatically. Reconnect contract honoured (each `connect()` already creates a new WebOSTV → fresh control objects; `_subscriptions_active` flag tracks current generation). `_setup_subscriptions()` is called in `connect()` after `_initialize_control_interfaces()` + initial polling seed; `_teardown_subscriptions()` is called in `shutdown()` **before** `client.close()` so the protocol-level cancellation goes out while the WebSocket is alive. Power-state mapping locked in by 8 parametrized tests + `_lg_tv_is_on` helper. Suite: 334 → 343 passed. **HW watch-for during §5.1 #7:** webOS 4.x+ firmware may have moved the power-state endpoint to `com.webos.service.tvpower` (the library currently uses the legacy `com.webos.service.power` URI matching pywebostv; `aiowebostv` uses the new one). If power events silently never fire on the user's OLEDs, that's the first thing to check — file a small URI-flip task back with the library Claude. Hexagonal LAW ([[hexagonal-law-for-all-changes]]) verified clean at every commit.
- **2026-05-27 (state-sync chokepoint — Invariants A + B; unblocks §5.1 #7)** — Pre-flight audit before the per-driver HW pass surfaced TWO load-bearing bugs: **Invariant A (state persists to `state.db`)** was PARTIAL — only the HTTP path had a safety-net `_persist_state` call; MQTT-in + scenario paths relied entirely on driver hygiene. **Invariant B (WB virtual-device value topic in sync with state)** DID NOT HOLD AT ALL — the publish chokepoint `_update_wb_control_state` was never called from the action chain; `handle_wb_message` was echoing the INCOMING command payload (wrong whenever the driver settled on a different value). LG TV had 33 runtime sites doing direct `self.state.x = y` assignment instead of `update_state(x=y)` — entirely bypassed `_notify_state_change` → callback chain → persistence; other 6 drivers were already correct (earlier per-driver regex over-counted via matching `==` comparisons). Fixed across 4 commits, **architecturally**: (1) `cbb73c5` generalized `BaseDevice._state_change_callback` (single slot) to `_state_change_callbacks: List[Callable[[str, List[str]], Any]]` + tracked `changed_fields` in `update_state` so per-field-aware callbacks know what changed; (2) `5d289af` added `WBVirtualDeviceService.publish_device_state_changes(device_id, changed_fields)` — reads device state via injected `state_provider`, builds a `state_field → wb_control_name(s)` map (explicit `wb_state_mappings` config field overrides + by-name convention fallback; pushbuttons excluded), publishes each changed field's current value retained; `BaseDevice._setup_wb_virtual_device` registers it as a second callback alongside persistence; `handle_wb_message`'s incoming-payload echo dropped (chokepoint covers it correctly); (3) `386b544` rewrote LG TV's 33 runtime direct assignments → `update_state` (27 calls; coalesced multi-field updates so each logical event fires the callback chain once); kept 2 `__init__`-time direct assignments (pre-callback-registration). (4) `8b30781` added 6 regression tests in `test_state_change_chokepoint.py` covering payload conventions, explicit-vs-convention mapping precedence, pushbutton exclusion, the Invariant B end-to-end, and the dropped echo. 334 passed. **Hexagonal LAW** (issued 2026-05-27 by the user, memory: [[hexagonal-law-for-all-changes]]) verified at every commit: `domain/` imports zero infra/presentation; only the one documented `presentation → infra` residual remains (system-router `/reload` → `MQTTClient`). **A2 (safety-net persist for MQTT + scenario) explicitly skipped** — the chokepoint covers both invariants for any driver that calls `update_state`, and we verified all 7 drivers do. **§5.1 #7 is now unblocked**: WB UI will reflect real state after every action, every driver, every source.
- **2026-05-27 (§5.1 #7 added — per-driver HW verification pass)** — Methodology gate before P3.6 scenario HW verification. User asked whether a per-driver pass was planned (it wasn't, as a structured session — only piecemeal items existed: §5.1 #3 for A77, P4 #5 as the very-late whole-system pass, and the aiomqtt 2.0.1 HW verify as a library concern). Reasoning ([[mock-tests-miss-driver-bugs]]): scenarios are composites; verifying scenarios first masks driver bugs inside composite flows. So the new §5.1 #7 fans out the seven driver classes (`LgTv`/`EMotivaXMC2`/`AppleTVDevice`/`AuralicDevice`/`WirenboardIRDevice` × 6 instances/`RevoxA77ReelToReel`/`BroadlinkKitchenHood`) into a single checklist with the same shape per row: setup + action set + state read-back + error recovery. Side-effect: also covers the aiomqtt 2.0.1 HW verify (every IR-via-WB row exercises that stack). **Subsumes §5.1 #3 (A77 re-verify)** — A77 is now one row of #7; the standalone entry is struck through with a pointer. Backlog now ordered with #7 listed first as the next HW-gated task; the rest of §5.1 follows. **Gated on the user at the rack.** Doc-only change.
- **2026-05-26 (P3 #7 + #8 — GHCR + compose, retiring docker_manager)** — User pick: "WB-specific, want standard tooling" → committed to going off the WB-supported deploy path. **CI side** (`6a61766`): `.github/workflows/build-arm.yml` two slow ARM jobs now log in to ghcr.io with the workflow's built-in GITHUB_TOKEN (no separate PAT) and push backend + UI images to `ghcr.io/droman42/{wb-mqtt-bridge,wb-mqtt-ui}` with `:latest` / `:sha-<short>` / `:vYYYYMMDD-<short>` (`docker/metadata-action@v5`). Dropped the artifact uploads + the `wb-mqtt-bridge-config.tar.gz` config archive — config now travels with the cloned repo, single source of truth. Fast checks (backend-test + ui-validate) unchanged. **ops/ side** (`fd61c93`): new `docker-compose.yml` (two services, both `network_mode: host` for WB mosquitto on localhost:1883, mem/cpu limits, bind-mounts `../backend/config:ro` + `../.state/{data,logs}`), `wb-mqtt-bridge.service` (systemd, `docker compose up -d` on boot), `update.sh` (~10 lines), and `INSTALL.md` covering the one-time install, the cutover from docker_manager (preserve the `.state/data/state.db` for assumed-state continuity), the GHCR-package public flip, WB-firmware-upgrade recovery, and image-pinning for rollback. **Removed**: `manage_docker.sh` (1081 lines) + `docker_manager_config.sample.json`. Net: -1081 / +120 LoC. Standing trade-offs (accepted): containers no longer show in WB's admin UI as managed apps; firmware-update preservation of `/mnt/data/` Docker state is unconfirmed (recovery flow in INSTALL.md). **WB-side cutover gated on the user** — INSTALL.md is the runbook.
- **2026-05-26 (§5.1 system-router cleanup, Item B)** — **`/config/system` response DTO — DONE.** Closed the smaller of the two hexagonal-pass deferred residuals (Item B). New presentation DTOs `SystemConfigResponse` + nested `MQTTBrokerConfigResponse`/`PersistenceConfigResponse`/`MaintenanceConfigResponse` mirror the infra config shape via `from_attributes=True`; the handler returns `SystemConfigResponse.model_validate(infra_system_config)` so the wire contract decouples from internal config layout. Dropped the `SystemConfig` re-export from `presentation/api/schemas.py`. Wire shape **field-identical** to before (verified by openapi diff: same 10 top-level fields on the renamed schema). UI: regen `openapi.gen.ts`; `api.ts` renamed `SystemConfig` alias → `SystemConfigResponse`, dropped `MQTTBrokerConfig` + `PersistenceConfig` aliases (no longer referenced by any endpoint, were only transitive types); `useApi.useSystemConfig` repointed. Backend 328 + `npm run check` green. `73ee8d5`. **Item A (extract `reload_system_task` into an app-layer service) is still deferred** — touches the live MQTT-reconnect path, can't be HW-verified without the user. Architecture.md "Dependency rule" subsection updated: now ONE documented exception, not two.
- **2026-05-26 (§5.1 #1)** — **Transition-aware manual notes — DONE (mock-validated; HW verification pending).** Closed the load-bearing UX gap that left `movie_ld`/`movie_vhs` silently audio-less: the reconciler already emitted the Dodocus "set the hub to LD/VHS" note on every activation, and the SSE + `ScenarioResponse` carried it — but the UI's SSE handler dropped the payload. Refactored to a **single source of truth**: `ScenarioState.manual_steps` (new field, populated by `ScenarioManager` on activation, cleared on deactivate/shutdown), and dropped the redundant copies from `ScenarioResponse` + the three lifecycle SSE event payloads + the `_switch_via_reconciler` return dict. UI: regen `openapi.gen.ts` (new `ManualStep` schema; +`api.ts` alias); `RemoteControlLayout` gains a `manualSteps` prop rendered as a "For this activation" amber subsection above the static startup/shutdown notes, with the `<details>` auto-opening when transition steps are present; `RuntimeScenarioPage` threads `activeScenarioState.manual_steps`, guarded on `lifecycleActive` so inactive scenarios' pages don't show another scenario's prompts. New `test_transition_to_ld_surfaces_dodocus_note_on_switch_and_clears_on_deactivate` exercises the load-bearing transition (appletv → ld surfaces note; deactivate clears; next start is fresh). 328 passed; `npm run check` green. Backend `79c3588`, UI `bd80cc5`. **Phase-2 refinement** (only emit notes for *newly-activated* links — diff-based, not every-activation) intentionally **NOT done**: over-prompting on every activation is correct for load-bearing notes. Hardware verification still gated on the user (same as the P3.6 round-2 scenarios).
- **2026-05-25 (P3.6)** — **Round-2 music scenarios BUILT (mock-validated; hardware verification pending).** Wiring interview done → 4 thin audio-only scenarios: `music_auralic` (Auralic `streamer` → amp `balanced`), `music_reel` (Revox A77 `reel_to_reel` → Dodocus **Reel** → amp `cd`), `music_tape` (Revox B215, **passive**), `music_turntable` (Kuzma Stabi S → Sugden PA4 phono corrector, **passive**) — the latter two via Dodocus → amp `cd`. Dodocus is now the central analog selector (ld/vhs/reel/tape/phono). The two passive sources (no driver) are modelled as **manual topology nodes** + a one-line reconciler change: a manual-node `source` anchors the topology path so the amp input + the hub note resolve, but is never added to `involved` (nothing to control) — `f1455c6` (reconciler + test), `368fbcb` (topology nodes/positions/links), `59fb661` (scenario configs + reconciler/manifest tests). 326 passed. **Children's room deferred by the user** (skipped this round). **Remaining: hardware verification.** See §P3.6.
- **2026-05-25** — **Hexagonal-purity pass — `domain/` is now import-pure; the doc-vs-code drift is fixed.** External analysis (+ a local re-audit) confirmed **6 `domain→infrastructure`** imports violating the documented inward rule, plus **1 infra→presentation** back-edge and **3 presentation→infra** the tool missed. Fixed across 7 focused, behaviour-neutral commits (`b391591`→`5c7843e`; 320 passed throughout): (1) moved `topology` (models+loader) and (2) the scenario **reconciler** into `domain/` (pure logic/data misfiled under infra → clears 3 of 6). (3) replaced the **vestigial, wrong-shaped `DeviceBusPort`** with a real `DevicePort` — the rich device contract the domain actually uses; `DeviceManager`/`Scenario` hint the port, `BaseDevice` implements it (clears the BaseDevice sites). (4) moved the device-config base models to `domain/devices/config.py` (infra re-exports for compat) → clears the last domain→infra site **and** the presentation→infra config import. (5) moved the capability **schema** to `domain/capabilities/models.py` (loader stays infra) → clears the `layout_engine` presentation→infra. (6) added `EventPublisherPort` (`SSEManager` implements it, injected into devices at bootstrap) to **break the infra→presentation cycle** (`BaseDevice` no longer imports the SSE singleton). **Result: `domain/` imports zero infra/presentation; infra imports zero presentation.** Two presentation→infra couplings consciously **accepted + documented** (system router exposes infra `SystemConfig` as a `response_model`; its `/reload` constructs the infra `MQTTClient`) — clean fix (response DTO + reload app-service) deferred (live MQTT path); tracked in §5.1. `architecture.md` rewritten to match (ports table, directory map, new "Dependency rule — and its two documented exceptions").
- **2026-05-19** — Initial draft. Captures research from a deep survey of both repos plus WIP and CI/CD analysis.
- **2026-05-19** — Added §7 (Codegen Alternatives) after deep-dive into the device-page generation pipeline. Inserted P1 items #3.5 (eliminate Python AST coupling) and #4.5 (relocate `device-state-mapping.json`). Added a new Open Question about runtime-driven UI.
- **2026-05-19** — Branch audit. Confirmed `main` is the source of truth in both repos; all feature branches are fully merged. Discovered the UI repo has 8 modified + 3 untracked files, including a `generate-device-pages.ts` change paired with the backend `device_category` WIP. Added P0 items #0a (UI WIP triage) and #0b (delete stale branches). Revised P2 #6 — `wb-mqtt-ui/docs/appliances.md` is untracked rather than stale-committed; action is now "decide whether to commit at all."
- **2026-05-19** — Executed #0a, #1, #0b. Backend `ab5402d` + `b7aa246` (this doc) pushed to `origin/main`; UI `8ab2cfa` pushed to `origin/main`. Three stale branches deleted (local + origin): backend `code_structure`, backend `feature/wb-virtual-device-emulation`, UI `code_structure`. Both repos now have only `main`. `appliances.md` shipped as part of the paired feature, resolving P2 #6 as "commit as-is" (design doc reflects current code).
- **2026-05-19** — Executed #2 (wire tests into CI). Backend `36b54d8` + UI `5be5bd2` pushed. Discovered the test suite had significant pre-existing API drift (scenarios devices dict→list, ScenarioManager kwarg rename, execute_command→execute_action, validate()→validate_configuration() semantic change, ScenarioMockStateStore needing load/save). Fixed what was mechanical; marked 14 files + 18 individual tests as `pytest.mark.skip(reason=...)` for the rest. CI ships green; ~half the suite runs. **Follow-up needed**: incrementally repair the skipped tests in dedicated PRs.
- **2026-05-19** — Started repairing the skipped tests semantically (rewrite where production contracts moved, not just mechanical assertion patching). Pushed across 7 commits (`b05d6db`, `66c5018`, `939f2b9`, `4a9f6fa`, `864fa19`, `e18f9f7`). Final state: **151 passed / 58 skipped / 0 failed** (was 107 / 109 / 0). Recovered ~51 tests. Files fully repaired or consolidated: test_state_store, test_state_store_error_handling, test_config_manager, test_message_handling, test_scenario, test_scenario_manager, test_wb_virtual_device_service (individual skips), test_persistence_integration (complete rewrite), test_integration, test_kitchen_hood_parameters, test_wirenboard_ir_params, test_revox_params, test_scenario_state_persistence (consolidated). **Still skipped** (~58 tests across 6 files): test_emotiva_params.py (hangs at collection), test_lg_tv.py + test_lg_tv_params.py (collection / 17 failing fixture-drift), test_scenario_api_integration.py (~14 errors — FastAPI mocking), test_auralic_device.py + test_auralic_update_task.py (hang at collection — openhomedevice import-time side-effects). Each remaining file needs deeper rework; recommended as separate follow-up PRs to keep diff size sane.
- **2026-05-19** — Completed the remaining 6 files (rewritten as fresh tests against the post-hexagonal-refactor drivers, not mechanical fixes). Commits `c8c1b0e`, `7e2d7cd`, `9f6757f`, `7a50f6e`. **State: 199 passed / 0 skipped / 0 failed.** Approach for the device drivers: bypass setup() entirely (which connects to real hardware), inject AsyncMocks for the driver's external client (openhomedevice / pymotivaxmc2 EmotivaController / WebOS MediaControl / etc.), flip state.connected=True, then drive handle_X methods directly and assert delegation + state mutations. test_lg_tv.py contained CLI-tool helpers misnamed `test_*` — renamed to `_check_*`/`_run_*` so pytest stops trying to collect them. test_scenario_api_integration.py rewritten with correct state.initialize signature and updated response-envelope assertions.
- **2026-05-19** — Applied the same fresh-rewrite treatment to the device test files that had only received mechanical patches earlier (kitchen_hood, wirenboard_ir, revox, apple_tv). Commit `9501ff9`. **Final state: 225 passed / 0 skipped / 0 failed.** Every device-driver test file now follows the same hexagonal pattern: typed Pydantic config in the fixture, external dependency injected as an AsyncMock, setup() bypassed, handlers driven directly. Tests added cover compensation logic (kitchen_hood speed-after-light), sequence execution with configurable delay (revox), and full handler coverage (apple_tv remote control + audio + apps). Net +26 tests vs the previous round. All originally-skipped tests are now passing or have been replaced with meaningful equivalents under the new architecture.
- **2026-05-20** — Removed Miele appliance support (never implemented — no driver, config, or test ever existed; repeated integration attempts failed). Commit `5f63513`: dropped `asyncmiele==0.2.6` from `pyproject.toml`, regenerated `uv.lock`, removed the Miele bullet from `README.md` and the Miele task from the TODO. The Roborock bullet was **kept** — it is a planned future feature, not a false current claim (revises the original P2 #5 wording, which had called for deleting it).
- **2026-05-20** — Completed P2 #5. Archived `docs/TODO.md` → `docs/history/phase1-2.md` (history preserved via `git mv`, header note added). Its 5 still-open items were migrated to §5.1 (Backlog) so live work stays tracked rather than buried in an archive. **P2 is now fully done.**
- **2026-05-20** — Completed **all of P1** (#3, #3.5, #4, #4.5) in one session. The architectural prize — removing the UI build's dependency on the Python package — is shipped.
  - **#3** (backend `6bc30fc`, UI `312fa56`): backend exposes device-state models in `/openapi.json` via an additive `app.openapi()` override (`bootstrap._install_openapi_with_state_models`) — no endpoint signature change, so runtime serialization and the custom `model_dump` overrides are untouched. New `wb-openapi` CLI dumps a committed `openapi.json` snapshot (the contract). UI added `openapi-typescript` + `gen:api-types` → `src/types/api.gen.ts`. 4 new backend tests; suite 229 pass.
  - **#3.5** (backend in `6bc30fc`, UI `5a71929`): `StateTypeGenerator` reads state shapes from `components.schemas` instead of spawning `python3` + `ast.parse`. Discovered the prior `pip install -e` was already **dead** (state config was only loaded in `local` mode, never `package`/CI). Enabled state-gen in package mode too, then removed Python entirely from the UI Dockerfile + CI. Validated a clean package-mode build: 8 state classes, typecheck/lint/validate all green.
  - **#4.5** (backend `2e5674c`, UI `7c3f3a8`, +`9f7da0e` untracking an accidental `system.json`): mapping now lives in the backend with directory-relative paths; the UI client resolves them, retiring the `.local.json` duplicate and the scenario handler's duplicate loaders.
  - **#4** (UI `395e538`): nginx proxy IP via `envsubst` template + MQTT URL via the (newly-wired) `window.RUNTIME_CONFIG` runtime shim; defaults preserve current behavior. **P1 is now fully done — only P3 (ops, deferred) remains.**
- **2026-05-20** — Verified the P1 codegen changes did **not** alter the remote-control layout: regenerated all layout artifacts at the pre-change baseline (`5be5bd2`) vs HEAD — all 17 `.gen.tsx` files (13 device + 4 scenario) byte-identical; `index.gen.ts` identical apart from `generatedAt` timestamps. Traced the within-zone placement mechanism in code (slot-by-action-name for power/volume/nav/pointer; array-order for screen/playback/tracks, sourced from `config/devices/*.json` command key order). The alphabetized `openapi.json`/`*.state.ts` feeds only the `.hooks.ts` typing layer, never the layout. Added **P2.5 #10** (design a contract-based placement) + a matching §5 open question — the user dislikes layout depending on an implicit config-order convention and wants an explicit contract designed before any change.
- **2026-05-20** — **Decided to adopt GSD** (added **P2.6 #11**; removed it from "out of scope"). Re-studied the framework: solo-friendly, brownfield path, multi-repo via workspaces. Audited all documentation in both repos against current code (two subagents) and executed the doc-reconciliation prerequisites:
  - **Step A (archive):** moved 28 backend + 6 UI superseded design/implementation plans to `docs/archive/` with a "not current, don't ingest" header (backend `124ca55`, UI `8bb360b`). The live `docs/` surface is now 13 backend + 5 UI docs.
  - **Step B (fix living docs):** backend README de-stale'd + trimmed 1146→878 (`55ca7e6`); backend living-doc batch + emotiva (`db5c18b`, `0493df4`); UI README rewritten 299→121 for the Python-free contract build (`16b95dc`); UI deployment + network-config rewritten for runtime env-var config (`9d0745b`); remote_layout trimmed to the spec + accurate impl note, page_instructions + appliances corrected (`b8a15e9`).
  - **Step C DONE** (GSD-seed docs): ✅ **CONTRACT** (`docs/design/ui_backend_contract.md`, `50e94b0`; UI pointer `f4d0e7b`); ✅ **ARCHITECTURE** (`docs/archive/architecture.md`, `a2456bc`); ✅ **PROJECT vision** (`docs/project.md`, `ef4421e`); ✅ **CONVENTIONS** (`docs/conventions.md`, `b1f4543`); ✅ **ADRs 0001–0005** (`docs/adr/`, `531a5bb`). **Step D DONE** — see next entry.
- **2026-05-20** — Vision-gathering surfaced two items folded into the plan: **P0.5 #12** (scenarios are broken — top functional priority) and a revised "multi-arch" note (WB8+/arm64 is the planned hardware trajectory, so an arm64 image will be needed). SprutHub dropped; Yandex Alisa delegated to Wirenboard's future native bridge.
- **2026-05-20** — **Completed P2.6 #11 Step D — GSD is now bootstrapped** (`.planning/` tracked, backend-primary). Three commits:
  - **D.1 `/gsd-config`** (`b931430`): balanced profile, branching off, `commit_docs=true`, `auto_advance=false`. Found that `/gsd-config` can't create `.planning/` in this SDK version (`config-ensure-section`/`config-set` need a pre-existing file) — bootstrapped via `gsd-sdk query config-new-project`. The Step D runbook was corrected to note this ordering.
  - **D.2 `/gsd-map-codebase`** (`4223f39`): 4 parallel mapper agents wrote 7 docs to `.planning/codebase/` (STACK, INTEGRATIONS, ARCHITECTURE, STRUCTURE, CONVENTIONS, TESTING, CONCERNS; 1720 lines).
  - **D.3 `/gsd-ingest-docs`** (mode=new, `98664f3`): curated 10-doc manifest (5 ADR + ui_backend_contract SPEC + project/action_plan PRD + architecture/conventions DOC) → classifier×10 → synthesizer → roadmapper. 0 conflicts. Generated `.planning/{PROJECT,REQUIREMENTS,ROADMAP,STATE}.md` + `intel/`. ROADMAP = **6 phases (4 active + 2 deferred)**: 1 Fix Scenario Layer · 2 Button-Placement Contract · 3 CI Quality Gates · 4 Planned Device Features · 5 Ops/GHCR (deferred) · 6 arm64 for WB8+ (deferred). P1/P2 recorded as completed context, not phases. Subsystem specs (`docs/design/scenarios/*` etc.) deliberately not ingested.
- **2026-05-20** — **Shipped a dependency-reproducibility-hardening pass** (ran as GSD "Phase 1", inserted ahead of the scenario fix). Commits `6d75760`, `4282e2c`, `321e391`, `3461289`, `10c0c0c`, `6419b09`. The durable results (independent of GSD):
  - **`openhomedevice`**: kept the fork (`droman42/openhomedevice`) but moved the `[tool.uv.sources]` entry from the moving `branch=remove-lxml-dependency` to the immutable `rev=6e862a1022f59a21c57c501dcf040f81d12ebfaf`. Upstream dropped `lxml` on `main` but has **not** released it; PyPI `openhomedevice==2.3.1` still forces `lxml` → would break ARMv7. **Migration trigger:** switch to the official PyPI release once it ships lxml-free.
  - **`pyatv`**: migrated from a pinned git commit to PyPI `pyatv==0.17.0` (the protobuf-contradiction fix from the old commit shipped in 0.16.1; driver imports unchanged). Git source removed.
  - **Upper bounds** added to all 17 direct PyPI deps (`httpx`/`requests` were unconstrained). Side effect: `paho-mqtt<2` cascaded **aiomqtt 2.3.2 → 2.0.1** (paho 2.x→1.x). Full suite green (236 pass / 0 fail) — but the MQTT stack is now older; **verify on real Wirenboard hardware** when convenient.
  - Added `tests/test_dependency_pins.py` (7 pin-guard tests), `docs/maintenance/dependency-recovery.md`, and **ADR 0006** (dependency-pinning policy). `uv.lock` is the pin-of-record.
- **2026-05-20** — **Dropped GSD.** After completing the dependency pass via the full GSD loop (discuss→research→plan→plan-check→execute→verify), removed GSD: **too slow for the value on a solo project** — every phase spawns ~7 sub-agents and GSD had installed 10 global hooks that ran on *every* tool call in *every* Claude Code session. Kept all the deliverables above (they're plain code/docs). Removed `.planning/` (the GSD project state) and the global GSD install (hooks, skills, agents, `gsd-sdk` CLI). The roadmap intent survives in the P-sections of this doc; future work proceeds without GSD. **`docs/adr/0006` and `docs/maintenance/dependency-recovery.md` were authored during the GSD pass but are kept as normal project docs.**
- **2026-05-21** — **Scenario layer rebuilt (P0.5 #12)** on branch `feat/scenario-redesign` (10 commits, **not merged**; full suite 270). Designed and implemented the Harmony-model redesign end to end:
  - **Design docs:** `docs/design/scenarios/scenario_system_redesign.md` (Layers 0/1/2/R + §16 capability maps + §15 tvOS note), the "Layout Manifest & Runtime Rendering" section of `docs/design/ui_backend_contract.md` (Layer 3 — runtime page construction replaces build-time `.gen.tsx`; subsumes P2.5 #10 + Codegen Option 2), and `docs/archive/monorepo_migration_plan.md` (P3 #9, Phase 2).
  - **Build order decided = B:** backend scenario fix (current repos) → monorepo (Phase 2) → Layer 3 (Phase 3). Branching: one feature branch per phase, merged between phases (the monorepo step rewrites history, so no branch may straddle it).
  - **Implemented:** Layer 0 topology (`config/topology.json` + `infrastructure/topology/`); Layer 1 capability maps (hot-fixable JSON under `config/capabilities/{classes,devices}/` + `infrastructure/capabilities/`, attached at bootstrap); optimistic `WirenboardIRState.input`; Layer R reconciler (`infrastructure/scenarios/reconciler.py`: resolve→diff→translate→order→execute + teardown) wired into `ScenarioManager` behind `WB_SCENARIO_RECONCILER`. **All four scenarios migrated to thin** `source/display/audio`. Manual steps (Dodocus) surfaced via `ScenarioResponse.manual_steps` + SSE. Fixes RC1/RC2/RC3 (mock-verified). ~45 new tests.
  - **Remaining for P0.5 #12 = hardware verification only** (gating/delay tuning, ordering/ARC, Dodocus hub, tvOS who's-watching). UI follow-ups (display `manual_steps`; re-run scenario codegen against thin configs) land with Layer 3. Full as-built record + caveats: `docs/design/scenarios/scenario_redesign_progress.md`.
- **2026-05-22** — **Phase 1 hardware-verified + merged to `main`; Phase 2 (monorepo) executed end-to-end.**
  - **Hardware verification (Phase 1):** clean boot on the live system (all 13 devices, 4 thin scenarios, topology + capability maps). Fixed the AppleTV/pyatv 0.17.0 listener (`eaecb7c`); shipped a **lifecycle-robustness cluster** (non-fatal `load_scenarios` = Bug 2; keep failed-setup devices registered; hardware-transparent shutdown + correct optimistic-assumed-state persistence); fixed **four hardware-only IR / WB-virtual-device bugs** via the amp test (`result.success` on a dict; double IR blast on the API path; broken `handle_message` override that killed WB-UI control; empty-retained value hiding WB controls). Stopped publishing scenarios as WB devices (pending design — P4 #7). kitchen_hood failure diagnosed as a hung device, not a regression. Full record: `scenario_redesign_progress.md` §1a.
  - **Phase 1 merged to `main`** (fast-forward); `pre-monorepo` recovery tags pushed on both repos.
  - **Phase 2 monorepo COMPLETE** (increments 1-7, `monorepo_migration_plan.md` §4): backend → `backend/` (git mv, native history); UI grafted → `ui/` (git-filter-repo, full 83-commit history); top-level peers `wb-rules/` + `ops/`; cross-cutting `docs/` (+ consolidated `docs/archive/` from the staleness sweep + `docs/device_setup/`); **one unified CI** builds both ARM images **green**; deploy (`ops/manage_docker.sh` + a sample config) repointed so both images come from the single repo; old `droman42/wb-mqtt-ui` **archived** read-only.
  - **Interim CI gating:** the slow QEMU arm/v7 image builds (~14 min for the UI) are gated to **manual-only** (`workflow_dispatch`) for the heavy-iteration period; fast checks (backend tests + UI codegen/typecheck/lint) run on every push. Build images on demand: `gh workflow run "Build ARM Docker Images (backend + ui)"`. Revert = delete the two `if:` lines.
  - **Backlog noted:** UI image build is slow purely from arm/v7 *emulation* of the Node build (863s) → future fix = build the JS on amd64 + assemble only the arm nginx layer (or arm runners). Plus §3b (root README authoring; wb-rules GitHub→WB deploy) and a fuller `docs/archive/ui-docs/page_instructions.md` Python-residue cleanup.
  - **Post-monorepo doc-staleness — found + FIXED in the 2026-05-22 wrap-up audit:** rewrote `project.md`, `conventions.md`, `ui_backend_contract.md`, and `architecture.md` to the monorepo (UI reads `../backend`; one layout) and added dated monorepo-update notes to ADR-0001 + ADR-0003 (decisions unchanged). **Still pending:** pin a sqlite-capable Python (`backend/.python-version` = 3.11.12) — the local `/usr/local/python3.11.4` lacks `_sqlite3`.
  - **Remaining (Phase 3 / deferred):** Layer 3 runtime rendering; the deferred **full scenario-reconciler hardware test** (resync the amp's drifted optimistic state first); verify the aiomqtt 2.0.1 downgrade on real WB hardware. **Deploy host action:** set the WB's `docker_manager_config.json` ui repo → `droman42/wb-mqtt-bridge`.
- **2026-05-23** — **Phase 3 prep: groups-vs-capabilities judgement, dormant-command design, and Alisa-bridge research.**
  - **Groups → capabilities.** Analyzed the device-config `group` concept vs the Layer-1 capability **domains**. Judgement: **capabilities subsume groups** — `group` becomes a transitional fallback, retired once capability coverage is complete. Recorded in `scenario_system_redesign.md` **§17**: the group→domain map (9/11 collapse 1:1; `gestures` is dead; `noops`/`media` are orphan actions); **dormant-command design** — `exposed: false` on the config command (invisible to UI/WB/HTTP) + a load-time validation rule (every command is `exposed:false` OR capability-backed) + a NEW `execute_action` exposure gate (verified absent today — `base.py:748` dispatches any command), sequenced to flip AFTER full coverage; coverage targets (author maps for `streamer` + `reel_to_reel`; `kitchen_hood` is the only appliance → deferred). Cross-ref added in `ui_backend_contract.md` placement-engine section.
  - **Alisa-bridge research.** Background agent (web blocked in its sandbox) + a main-thread web-verification pass → `docs/review/wb-alice-bridge.md` (web-verified). Verdict: WB's native `wb-mqtt-alice` (release wb-2602) exposes only `on_off`/`color_setting`/`range` (+ `toggle`), has **no `mode`** (AV input switching not voice-expressible), **cannot use `pushbutton` controls**, uses a **manual configurator** (not auto-discovery), and is **cloud-dependent** — so `project.md`'s "voice-controllable *for free* via WB virtual devices" is **falsified**. The one clean win is **publishing scenarios as `switch` controls** ("Алиса, включи кино"), feeding the P4 #7 decision. **PARKED** — revisit only after the scenario migration is fully done, all devices hardware-tested, and the house works end-to-end. Flagged for later: correct the "for free" wording (`project.md` §"Non-goals", `action_plan` P-context) and decide the cloud-dependency vs LAN-only non-goal.

- **2026-05-23 (cont.)** — **Phase 3 (Layer 3) — Step 0 + Step-1 model batch executed.** **Step 0:** layout analysis (zone↔domain taxonomy; config `group` ↔ capability `domain` align 1:1 → groups-retirement safe) → `docs/design/scenarios/layer3_step0_layout_analysis.md`; authored capability maps for `reel_to_reel` (playback) + `streamer` (input/volume/playback, then power); froze the fidelity oracle → `docs/design/scenarios/layer3_oracle/*.json`. **Step-1 model batch:** added `Capability.reconcile` + widened `on_value` to `str|bool|int` + `BaseCommandConfig.exposed`; reconciler skips `reconcile:false`; completed `streamer` power (feedback on the bool `connected`) + `upscaler` power (`reconcile:false` — manual page power, reconciler still auto-powers it) + tagged 5 dormant commands `exposed:false`; added the `execute_action` exposure gate + load-time `validate_command_exposure` (drift guard = **0 violations** → full capability coverage of in-scope devices). 279 backend tests pass. **Next:** the `LayoutManifest` Pydantic + domain→zone placement engine + `GET /devices/{id}/layout` (reproduce the oracle), then Steps 2-4 (UI renderer → rollout → cutover).

- **2026-05-23 (cont. 2)** — **Phase 3 Step-1 manifest started.** Built the `LayoutManifest` Pydantic model (`presentation/api/layout_manifest.py` — mirrors the UI `RemoteDeviceStructure`, `extra=forbid`; all 13 frozen oracles parse) + the placement-engine **foundation** (`presentation/api/layout_engine.py` `build_device_manifest`: the domain→zone framework + the **power** and **playback** zone builders; `reel_to_reel` + `vhs_player` reproduce their oracle structurally). Ordered-zone control order follows **capability-declaration order** (retires the config-key convention), so the fidelity check compares control *sets* for ordered zones. Icons are placeholders (port the UI IconResolver vs keep UI-side = open). **Remaining (Step 1):** the volume/input/tracks/menu/apps/screen/pointer zone builders → all 13 devices, then `GET /devices/{id}/layout`. 295 backend tests pass.

- **2026-05-23 (cont. 3)** — **Placement engine: volume + input builders.** Added the volume (volumeSlider when the cap has a `set` action, else up/down volumeButtons) and input (api-populated dropdown for a parametric `select`; commands dropdown from `by_value`) zone builders. Engine now covers **4/9 domains** (power, playback, volume, input); **3/13 devices** reproduce their oracle (reel_to_reel, vhs_player, mf_amplifier — `tests/unit/test_layout_engine.py`). Fixed `_is_empty` (empty collections count as empty); the fidelity check compares control *sets* for ordered zones + dropdowns by type/populationMethod/count. **Remaining (Step 1):** tracks/menu/screen/apps/pointer builders + multi-zone power (emotiva special case) + icons decision + the `GET /devices/{id}/layout` endpoint. 296 backend tests pass.

- **2026-05-23 (cont. 4)** — **Phase 3 Step 1 COMPLETE.** Placement engine covers all 9 domains and all 13 devices: the 12 standard devices reproduce their frozen oracle (`backend/tests/unit/test_layout_engine.py`), plus **eMotiva multi-zone power** (zone 1 off/on + zone 2 native `zone2_power` toggle — added the config command + driver `handle_zone2_power_toggle` calling the lib's `power_toggle(ZONE2)` + a cap `toggle` action; the reconciler still drives zones via on/off). `GET /devices/{id}/layout` serves the `LayoutManifest` (in `openapi.json` + UI `api.gen.ts`). **Icons decided — resolved UI-side:** the manifest carries semantics (`actionName`+domain), the UI's `IconResolver` maps to glyphs at render → keeps the manifest **skin-agnostic** (UI can be reskinned with no backend change); the `icon` field is an optional override. So Step 1 = model + engine (13/13) + endpoint + icon decision, all done; full suite 306. **Next: Step 2** — the UI runtime renderer behind a flag (where icon resolution lands).

- **2026-05-24 (cont. 24)** — **PHASE 3 / LAYER 3 STEP-4 CUTOVER COMPLETE + HARDWARE-VERIFIED.** The runtime renderer is now the only path; the build-time page codegen and the `group` concept are gone; live WB output confirmed unchanged on the live system (no degradation). Canonical scope + per-step record: `ui_backend_contract.md` → "Step 4 — cutover (canonical scope)". Sequence:
  - **UI:** A0 status pane reads **live device state** generically, not the codegen `stateInterface` (`e26e513`); A1 runtime is the only A/V path — dropped `isRuntimeLayoutEnabled` + the App.tsx gate, and **appliances → hand-written bespoke pages** (`kitchen_hood` = light+fan, `src/pages/appliances/`) (`f5a64cf`); A2 removed the `.gen` fallback from the runtime pages + Navbar's `getDeviceRoute` (`243b030`); A3 **deleted the entire page generator** (scripts + StateTypeGenerator/Doc/Batch/Validator/etc. + `lib/{deviceHandlers,generators,integration,validation}` + the gitignored outputs) **and the dormant scenario↔WB cluster** (`ScenarioWBAdapter`/`ScenarioWBConfig`/`setup_wb_emulation_for_all_scenarios`) (`bb109c6`, `f519605`); A4 removed the inert `specialCases` (`5adb3f0`); A7 `api.gen.ts`→`openapi.gen.ts` (`ba51f2c`); A8 phase 1 deleted the dead hand-written `api.ts` types (`2226ebf`). `npm run check` green throughout.
  - **Backend (Phase B):** B2 dropped `special_cases`/`DeviceSpecialCase` from the manifest model (`14db293`); deleted the `/groups` router + dead UI hooks (`9b388ab`); retired the `/scenario/virtual_config` endpoints, keeping nothing of the scenario-WB scaffolding (`0af97e5`). **WB re-key (steps 1-4):** key WB exposure/type/order off the capability **domain+kind+exposed** (`8fb2fdc`, golden snapshot `test_wb_rekey.py`), delete the orphaned group machinery (`f57322c`), then **fully remove `group`** — model fields + 182 config command entries + `system.json` `groups` + every reader (incl. re-keying the WirenboardIR optimistic-input off the capability `input` by_value mapping) (`c4dfb57`). The `execute_action` exposure gate was already implemented + active. backend 320; openapi/api.gen regenerated on each API-surface change.
  - **HARDWARE PASS PASSED (`e2cec4e` doc):** WB works as before, no degradation → `group` fully retired, revert-insurance dropped. The hardware run surfaced + we fixed an **unrelated UI bug** — the status-pane **alias cross-device leak** (`ebe625e`): the enhanced `useDeviceState` merged new device data into the prior device's `localState`, so a WirenboardIR `alias` bled onto non-IR devices (exposed by A0's generic pane); fixed by rebuilding localState from a clean per-device default (Playwright-reproduced + regression-guarded).
  - **Remaining (NOT cutover):** (1) **scenario↔WB rebuild** — MANDATORY P4 design (P4 #7; the old impl was deleted, so there's currently no scenario representation on Wirenboard); (2) **A8 phase 2** — optional (fold the live `api.ts` duplicates onto `openapi.gen`; deferred for `any`→`unknown` churn + dual-named `ManualInstructions`); (3) **oracle retirement** — deferred (kept as the engine's structural regression snapshot). **Next build = P3.6** (topology + scenarios round 2).

- **2026-05-24 (cont. 23)** — **Scenario UI state-feedback polish DONE — SCENARIO UI COMPLETE** (`1afaf40`, `91ef534`). The three decided follow-ups from cont. 22, all validated end-to-end (Playwright/mock, both lifecycle states + device regression). (1) **SSE→cache liveness fix (both halves):** device `state_change` → `setQueryData(['devices',id,'state'])` (was received + dropped; backend emits the full `get_current_state()` snake_case snapshot matching the REST shape → merge safe) + scenario lifecycle events (`scenario_started/switched/shutdown`) → invalidate `['scenario','state']`+`['scenarios','state']`. One source of truth — a scenario control reads its role device via the *same* `['devices',roleId,'state']` key a device page reads, so device-page fixes propagate to the scenario page (the IR-optimism case). (2) **Lifecycle active-state coloring:** `RemoteControlLayout` optional `lifecycleActive` prop (scenarios only; undefined on device pages → unchanged); PowerZone colors lifecycle buttons by it — running→start green/stop red, stopped→start white/stop dimmed (both stay clickable; start-on-running = re-reconcile). `RuntimeScenarioPage` derives running iff global `/scenario/state`.`scenario_id === scenarioId` (404=nothing active). (3) **Volume role binding** (Option B fan-out): VolumeZone reads the slider/buttons' `sourceDeviceId` (role device) for value/mute. **Bonus:** stop fetching `/devices/{scenario}/state` (PowerZone disables its query for lifecycle zones; `useInputsData`/`useAppsData` no longer fall back to the page id when there's no dropdown) → no spurious 404s. Validated: running (start green/stop red, only role devices fetched), stopped (start white/stop dimmed, `/scenario/state` 404 handled), device regression (processor: own state, 3 power buttons, slider, no spurious fetches). `npm run check` green. **RESUME → Step 4 cutover** (delete build-time codegen, retire groups + re-key WB exposure/ordering, full `specialCases` removal B2/U3, retire frozen oracle). Real proof = hardware.

- **2026-05-24 (cont. 22)** — **Scenario UI core built** (`52b685d`). `RuntimeScenarioPage` renders the composite-remote manifest via `RemoteControlLayout`; `handleAction` routes power_on/off → start/shutdown, every other control → its **role device** (`targetDeviceId`=sourceDeviceId); guard: a non-lifecycle control with no role device warns + skips (never posts to `/devices/{scenario}`). `useScenarioLayout` hook; dropdown `sourceDeviceId` routing in `useInputsData`/`useAppsData`/`useInputSelection`/`useAppLaunching`; **manual-steps** collapsible section at the remote bottom (scenario-only); `App.tsx` flag-routes the 4 `movie_*` scenarios. **Latent bug fixed:** `RemoteControlLayout`'s internal `handleAction` wrapper dropped the `targetDeviceId` 3rd arg (harmless for devices = target is the device; broke scenarios → all controls fell back to `/devices/{scenario}`). Validated end-to-end (Playwright/mock): movie_appletv renders the composite remote; volume→`/devices/mf_amplifier/action`, menu/apps→`/devices/appletv_living/action`, Start/Stop→`/scenario/start`+`/shutdown`. typecheck+lint+`npm run check` green; backend 307. **Remaining scenario-UI polish (state feedback):** the device/scenario **SSE→cache liveness fix** (Layout.tsx:74-80 drops `state_change`), the **lifecycle active-state coloring** (power zone running/stopped from `/scenario/state`), and per-`sourceDeviceId` **volume-slider value** binding (slider scenarios). THEN Step 4 cutover.

- **2026-05-24 (cont. 21)** — **Scenario BACKEND built** (`0aca1d1`). `build_scenario_manifest(scenario_def, device_manager)` — composite remote assembled per role from the role-devices' capabilities (volume/playback/tracks/menu/screen/apps/pointer; **inputs role skipped** = reconciler-derived); every control tagged `sourceDeviceId` (apps/inputs dropdowns get `DropdownConfig.sourceDeviceId`); **power zone = lifecycle** (power_off/power_on, no sourceDeviceId → UI routes to /scenario/shutdown+start); `manual_instructions` carried (new `ManualInstructions` + `LayoutManifest.manualInstructions`, scenario-only); `entityKind="scenario"`. + `GET /scenario/{id}/layout` (exclude_none). **Consistency fix:** `get_scenario_state` now **recomputes** the active scenario's devices from live `device.get_current_state()` (was a frozen snapshot, service.py:542) → can't drift after a manual device-page fix. Regen openapi/api.gen.ts (33 paths). **Validation = conformance** (`tests/unit/test_scenario_layout.py`, not oracle-diff). Backend **307** + UI typecheck/lint green. **Next: scenario UI** (`RuntimeScenarioPage` + per-`sourceDeviceId` state binding + device/scenario SSE→cache liveness + manual-steps bottom section + lifecycle active-state coloring).

- **2026-05-24 (cont. 20)** — **Scenario lifecycle active-state DECIDED → all scenario design questions settled.** The lifecycle power zone reflects running/stopped: one global active scenario (`current_scenario`), so a scenario is "running" iff it's the active one; UI reads `/scenario/state` (existing `useScenarioState`), live via `/events/scenarios` + the SSE→cache fix — **no new backend**. State-aware button coloring; both buttons stay functional (start-on-running = re-reconcile; start-on-stopped = switch). Recorded in `ui_backend_contract.md` "Scenario lifecycle (power zone) active-state". **Scenario scoping COMPLETE** — all four open questions resolved (state binding, virtual_config, manual_instructions placement, lifecycle active-state). Ready to build: `build_scenario_manifest` + `GET /scenario/{id}/layout` + `RuntimeScenarioPage` (+ the `get_scenario_state` recompute, SSE→cache, manual-instructions section). No code yet.

- **2026-05-24 (cont. 19)** — **manual_instructions placement = Option B (in the remote, scenarios-only).** Refines cont. 18: baseline `manual_instructions` are **part of the remote layout**, not a side panel — so they **ride the scenario manifest** (new top-level `manualInstructions?: {startup[],shutdown[]}`; `build_scenario_manifest` copies from the def; **device manifests omit it**). The renderer shows a collapsible "Manual steps" section at the **bottom of `.remote-zones`** (inside the remote box) **only when present** → scenario-only, no space wasted on device pages. **Supersedes** cont. 18's "read from `/scenario/definition`, no manifest change." Recorded in `ui_backend_contract.md` "Manual instructions".

- **2026-05-24 (cont. 18)** — **Scenario design decisions recorded (state binding + manual_instructions); no code yet.** State binding: one source of truth = `device.state` (reconciler diffs live ✓; UI controls fan out per `sourceDeviceId` = Option B + lifecycle→`ScenarioState`; `get_scenario_state` must recompute `devices` from live state — today a frozen snapshot, service.py:542; + wire device/scenario SSE→query cache). virtual_config RESOLVED (web-UI fallback, retired once all scenarios have `/layout`; WB publication separate). **manual_instructions:** baseline static lists shipped with the scenario page from `/scenario/definition/{id}` (no manifest change, collapsible panel); **transition-aware notes (Dodocus RCA hub etc.) DEFERRED to the reconciler/activation work but flagged LOAD-BEARING** (LD/VHS have no audio without them) — tracked as an open checklist item + §13.2 strengthened so it isn't dropped. Recorded in `ui_backend_contract.md` ("Scenarios = composite remote" / "Scenario state binding" / "Manual instructions") + `scenario_system_redesign.md` §13.2. **Still open:** scenario active-state on the power zone (next).

- **2026-05-24 (cont. 17)** — **Step 3 — Auralic on runtime; ALL device pages migrated (12/13)** (`b00c938`). Last device: Auralic (`streamer`), which needed the **slider value-param** generalization — its set-volume native param is `volume` not `level`. `VolumeSliderConfig` gains `valueParam` (from the set action's param_map: Auralic `{level:volume}`→`volume`, else `level`); the slider sends `{[valueParam ?? 'level']: newVolume, ...action.params}`. Enabled `streamer`. **All device_category devices are now on the runtime renderer; only `kitchen_hood` (the sole appliance) is excluded** (bespoke appliance pages out of Layer-3-v1). Validated (Playwright/mock): Auralic power off/on, INPUTS populate + `set_input {input:hdmi1}`, playback, volume slider 0-100. Regen openapi/api.gen.ts; backend 306 + `npm run check` green. **Step 3 device rollout COMPLETE.** Remaining: **scenarios** (`/scenario/{id}/layout` + the ⚠ `/scenario/virtual_config` decision), then **Step 4 cutover** (delete codegen, retire groups, full `specialCases` removal).

- **2026-05-24 (cont. 16)** — **Step 3 — LG + Apple TV + reel_to_reel on runtime (apps B5)** (`fe9a8c1`). **11/13** devices now. Generalized B5 to the **apps domain**: `_apps_dropdown` emits `setParam` (from the launch param_map: LG `{app:app_name}`→`app_name`, else `app` for AppleTV); `useAppLaunching` sends `{[setParam]:appId}` (was hardcoded `app_name` — buggy for AppleTV, which wants `app`). Enabled `living_room_tv`, `children_room_tv`, `appletv_living`, `appletv_children` + `reel_to_reel` (Revox, playback-only, no new work). LG inputs already worked via the generic param_map derivation (`set_input_source`/`source`); both TVs' volume sliders use the U2 valueField. (DropdownConfig already had `setParam` from cont. 14, so no openapi change.) **Validated end-to-end** (Playwright/mock): LG inputs/playback/menu/volume-slider/apps + launch `{app_name:netflix}` + pointer; AppleTV playback/menu/volume/apps + launch `{app:netflix}` + pointer, no INPUTS (pure source); reel_to_reel playback. Backend 306 + `npm run check` green. **Remaining Step 3:** Auralic/streamer (slider value-param generalization — native `volume` not `level`), kitchen_hood (appliance, deferred); then scenarios; then Step 4.

- **2026-05-24 (cont. 15)** — **Fix: eMotiva zone-2 power showed "2" instead of the power glyph** (`9b5dcec`). Found validating eMotiva. Two causes: (1) **IconResolver digit-key bug** — number-pad mappings (`'1'..'9'`) are integer-like keys that JS iterates first, so the partial-substring match matched `'2'` inside `zone2powertoggle` before `'power'` (affected any digit-containing action: aux2, hdmi2, …); fixed by skipping numeric keys in the partial loop (they're exact-match only — a literal `"2"` still resolves via the direct match). (2) the zone-2 **yellow-when-off color** was keyed on buttonType `power-toggle`, but Step 1 changed it to `zone2-power`; `getIconColor` now handles both. The old codegen never hit this — it spread `power_on`'s icon onto the synthesized zone2 action. Validated in-browser (red/yellow/green power glyphs); UI-only, check green.

- **2026-05-24 (cont. 14)** — **Step 3 — eMotiva on runtime (fixed-params flow + B5 + U2)** (`6a2e95f`). Enabled `processor` (eMotiva), the first api/slider device — 6/13 now on the runtime renderer. Surfaced + fixed a **latent param-passing bug**: the renderer sent the param *spec array* (`action.parameters`) as the payload, not values — harmless for the 5 no-param devices already rolled, broken for eMotiva. Three changes: (1) **fixed-params flow** — `ProcessedAction.params` carries the capability action's fixed native params (zone:1 power, zone:2 volume/mute); the engine threads them through the power+volume builders; the renderer sends `action.params` (buttons) + `{ level, ...params }` (slider). (2) **B5** — `DropdownConfig.setParam` (the native value param, from `param_map`: eMotiva `input`, LG `source`); `selectInput` sends `{ [setParam]: value }`. (3) **U2** — slider reads `deviceState[valueField]` (eMotiva `zone2_volume`), deleting `deviceClass==='EMotivaXMC2'`. **Validated end-to-end** (Playwright/mock): power sends `{zone:1}`/`{}`/`{zone:1}`, api inputs populate via `get_available_inputs` + select sends `set_input {input:hdmi2}`, slider renders the dB scale; the 5 rolled devices unaffected. Regen openapi/api.gen.ts; backend 306 + `npm run check` green. **Remaining Step 3:** LG/AppleTV (apps `setParam` generalization) + Auralic (slider value-param, native `volume` not `level`) + reel_to_reel (easy, playback-only) + kitchen_hood (appliance, deferred); then scenarios; then Step 4.

- **2026-05-24 (cont. 13)** — **Phase 3 Step 3 started — runtime render rolled to the easy WirenboardIR devices** (`1ebd5d8`). Enabled the runtime layout flag for `ld_player`, `video`, `vhs_player`, `upscaler` (+ the mf_amplifier pilot) — all WirenboardIR, commands/buttons only, **no api dropdowns** (verified), so none of the deferred hardening (B5/U2) is needed. **Validated render-level** (Playwright, real manifests via the mock): video = two power buttons (off/on) + PLAYBACK (4) + TRACKS (2) + menu nav-cluster; upscaler = power off/on + INPUTS (commands, 2 by_value) + SCREEN (3 aspect buttons) + menu cluster — all the new zone types (playback/tracks/menu/screen) render correctly. typecheck + lint + `npm run check` green. **Remaining in Step 3:** the api/slider devices (eMotiva, LG, AppleTV) — each needs B5 (api-select param) + U2 (slider) before its flag flips — then scenarios (`/scenario/{id}/layout` + the ⚠ `/scenario/virtual_config` decision). Also (cont. 13): fixed **§17.3** in `scenario_system_redesign.md` (`a3fd8d2`) — capability coverage is now MET (streamer/reel_to_reel mapped; drift guard 0 violations), so it no longer gates groups-retirement; only rollout (Step 3) + cutover (Step 4) remain.

- **2026-05-23 (cont. 12)** — **Step-2 hardening commit 2 DONE + re-scoped to mf_amplifier** (`94dd612`). U1: inputs/apps static-vs-fetch now obey the manifest's `populationMethod` (deleted the `specialCases`/`isWirenboardIR`/`usesAppsAPI` reads + hardcoded `get_available_*`); `selectInput`/`launchApp` route by `populationMethod` + use the manifest's `setAction`. **Scope correction (user):** other devices + scenarios are **Step 3**, so the LG/AppleTV **api-select param** (B5) + **eMotiva slider** (U2) + **full `specialCases` removal** (B2/U3) moved there — done per-device as each migrates + is hardware-tested. (Found while scoping: the old api-select hardcodes were *buggy* — LG `set_input` doesn't exist (cap = `set_input_source`/`source`); AppleTV `launch_app` wants `app` not `app_name`. Flagged TODO in `useRemoteControlData.ts`.) **Validated** mf_amplifier via the render mock: INPUTS populate from commands, apps empty/no-fetch, Navigation correctly empty (capability-driven) — matches the build-time page. backend 306 + `npm run check` green. **Step 2 is functionally complete for mf_amplifier** (real-world proof at the next UI deploy — flag defaults to mf_amplifier).

- **2026-05-23 (cont. 11)** — **Step-2 hardening commit 1 DONE (backend contract)** (`d0ca91e`). B1: `GET /devices/{id}/layout` now serves `response_model_exclude_none=True` → empty content fields omitted (not `null`), fixing the spurious-fetch bug + matching the codegen "absent = not present" contract. B3: added `state_field` to the 4 slider devices' volume capability (eMotiva→`zone2_volume`, LG/Auralic/AppleTV→`volume`) + new `valueField` on `VolumeSliderConfig`, emitted by the engine — **snake_case**, because device state serializes snake_case (no camel alias); the old hardcode read camelCase `zone2Volume` so eMotiva's slider value was silently broken. B4: **no-op** — every slider device already declares its set-volume `range` (eMotiva −96..0, others 0..100), surfaced via the action params. Regenerated `openapi.json` + `api.gen.ts` (VolumeSliderConfig gained `valueField`). Backend 306 + UI typecheck/lint green. **Next:** commit 2 (UI declarative — U1/U2), commit 3 (atomic `specialCases` removal — B2/U3).

- **2026-05-23 (cont. 10)** — **Step 2 visual check found 3 gaps; clean-fix plan agreed (NOT yet executed).** Spun up the dev server (zero-dep mock serving the *real* generated manifest, to avoid colliding with the live system's MQTT `client_id`) + Playwright screenshots of mf_amplifier runtime vs build-time. **Correction to (cont. 9):** the "adapter MATCHES oracle" result was a **false positive** — the frozen `layer3_oracle/*.json` compares distilled structure only; the rendered pages diverged. **3 gaps** (full detail in `ui_backend_contract.md` "Step 2 hardening"): (1) **`specialCases`** — a hardcoded back-channel + literal `deviceClass==='WirenboardIRDevice'` drives inputs/apps static-vs-fetch, ignoring the manifest's `populationMethod`; (2) **null vs undefined** — the manifest emits `appsDropdown: null`, the renderer checks `!== undefined` → false-positive zone that fetches and errors; (3) **empty menu/zones** — *NOT a bug*: capability-driven empty rendering is correct/preferred (user: showing controls for absent functionality is misleading in low light); empty zones stay as labeled `(Empty)` placeholders. **Decided principle:** manifest = complete + declarative + **class-agnostic**; renderer never branches on `deviceClass`/`specialCases`; `populationMethod` is the law. **Clean-fix plan (ALL devices; runtime-render flag stays per-device):** Backend B1 `exclude_none` on `/layout`, B2 drop `special_cases`, B3 volume `state_field`→`valueField`, B4 set-volume `range` via manifest; UI U1 `populationMethod`-driven inputs/apps, U2 volume reads `valueField`+range, U3 remove `specialCases` + the 8 handler emissions; Validation = render-level diff (retire the frozen oracle). **Records updated, not executed** — paused for review.

- **2026-05-23 (cont. 9)** — **Phase 3 Step 2 STARTED — UI runtime renderer behind a flag (mf_amplifier pilot)** (commit `d1da2db`). First consumption of `GET /devices/{id}/layout`: a device page rendered at runtime from the backend manifest via the existing `RemoteControlLayout`, gated per-device. Built: `isRuntimeLayoutEnabled()` allowlist flag in `config/runtime.ts` (`VITE_RUNTIME_LAYOUT_DEVICES`/`window.RUNTIME_CONFIG`; `*`=all, `""`/`none`=off; default pilot = `mf_amplifier`); `useDeviceLayout()` hook (`useApi.ts`, staleTime Infinity); `lib/layoutManifestAdapter.ts` (manifest → `RemoteDeviceStructure`, **resolves icons UI-side** via `IconResolver` since the engine emits `fallback` placeholders — matches the codegen's `selectIconForActionWithLibrary(name,'material')`; clones to avoid mutating the query cache; stubs the unused `stateInterface`); `components/RuntimeDevicePage.tsx` (replicates the `.gen.tsx` scaffolding, **falls back to the generated page on fetch error**); `app/App.tsx` routes the flagged device to it. Live data flow unchanged (`/state` + `/action` + SSE). **Validated:** the adapter output structurally diffs **MATCH** vs the frozen oracle (`layer3_oracle/mf_amplifier.json`), incl. resolved icons (power→PowerSettingsNew, volume→VolumeUp/Down/Off) and empty-zone flags; typecheck + lint + `npm run check` green. **Remaining for Step 2:** in-browser visual confirm of mf_amplifier against the build-time page (needs a running backend+browser), then Step 3 (roll to more devices → scenarios).

- **2026-05-23 (cont. 8)** — **Doc↔backend sync pass ("backend is king").** Audited the design docs against the shipped capability model (`infrastructure/capabilities/models.py`), `config/capabilities/*`, `config/topology.json`, and `openapi.json`; fixed real drift. `scenario_system_redesign.md`: §4.1 topology example `processor:zone1`→`zone2` (matches config; zone 2 = amplified); §5.2 replaced the non-existent `delays:{after_on_ms,settle_ms}` field with the real `gate:{poll_timeout_ms,delay_ms}`, added `list` + `reconcile` to the example; §5 "Key fields" now documents `gate`, `reconcile`, widened `on_value` (`str|bool|int`), `list`, `zones`; §5.4 rewrote the eMotiva prose to the actual `zones` dict (`ZonePower` per zone) + the Step-1 native zone-2 `toggle`; §16.3 worked map gained the zone-2 `toggle` action. `ui_backend_contract.md`: REST list marks the groups endpoints LEGACY/dead + adds `/devices/{id}/layout`. `action_plan.md`: device-config count `Twelve`→`Thirteen` (+ the Zappiti `video`). Verified residual stale patterns = 0; eMotiva worked-map braces balanced. No code change.

- **2026-05-23 (cont. 7)** — **Verified the Layer-3 plan covers all backend calls (pre-Step-2 audit).** Cross-checked `openapi.json` (32 ops) × the UI client (`useApi.ts` + `useEventSource.ts`) × the plan. Findings + fixes in `ui_backend_contract.md` "Layout Manifest & Runtime Rendering": (1) the manifest sketch was **stale** (draft `entity_id/zones[]/zone_type/state_schema` vs shipped `deviceId/deviceName/deviceClass/remoteZones[]/entityKind/deviceCategory/stateInterface/actionHandlers/specialCases`) → rewrote it to the implemented model; (2) status updated to "Step 0+1 implemented, Step 2 next"; (3) `/scenario/{id}/layout` marked NOT-yet-built (Step 3); (4) added an explicit **backend-call inventory** table mapping every endpoint to its Layer-3 fate — runtime data/control calls (`/devices/{id}/state`, `/action`, SSE `/events/*`, `/config/*`, `/room/*`, `/scenario/*` runtime, `/system`, `/publish`, `/reload`) **KEEP**; `/layout` **ADD**; the **groups** endpoints (`/groups`, `/devices/{id}/groups`, `…/actions`) **RETIRE** (UI hooks are dead — defined, no runtime caller); `/` + `/events/stats` + `/events/test` are unused. (5) Flagged an **⚠ open decision** for Step 3: the scenario **runtime** WB virtual-device controls (`/scenario/virtual_config/*` → `useScenarioVirtualDevice` → `<ScenarioVirtualDeviceControls>`, rendered in `App.tsx`) — does `/scenario/{id}/layout` subsume them, or do they stay a separate widget? The plan only deleted the *build-time* resolver/handler, never addressed this runtime path. No code change.

- **2026-05-23 (cont. 6)** — **UI lint/typecheck tightened before Step 2** (commit `9e90139`). Closed the long-standing "passes locally, fails on GitHub" gap (ESLint wasn't type-aware and didn't extend the standard TS ruleset; `lint`/`typecheck` are separate scripts). Four changes: (A) new **`npm run check`** mirrors the CI ui-validate job exactly (gen → typecheck:all → lint → validate:*); (B) extend `@typescript-eslint/recommended`; (C) un-exclude `IconResolver.ts` + the 2 type files from `tsconfig.json` (the Step-2 icon path was typechecked by nothing; 0 errors when added); (D) **type-aware lint** (`recommended-type-checked` + `parserOptions.project`), scoped to shipped app code (codegen tooling ignored — still in `typecheck:scripts`, deleted at Step 4), keeping the async-correctness rules (no-floating/misused-promises) and disabling the `any`-driven no-unsafe-* noise. Fixed the 22 real issues it surfaced (15 un-awaited promises → `void`, 3 async handlers in JSX attrs → wrapped, 2 `{}`-types → `Record<string,unknown>`, 1 redundant assertion, 1 `.apply` → spread). `npm run check` green end-to-end. No backend change.

- **2026-05-23 (cont. 5)** — **Topology/scenario scope clarified → new P3.6.** User flagged that `config/topology.json` + the 4 `movie_*` scenarios cover the **living-room A/V chain only**; the audio sources (Auralic, Revox) and the children's room (lg_tv_children, appletv_children) have capability maps (device pages render) but **no topology links and no scenarios**. Confirmed this is *not* a Layer-3 dependency (Layer 3 renders off capability maps; topology only feeds the scenario reconciler) and was only implied by P4 acceptance, never scheduled. **Decision: defer to after Phase 3 (Layer 3)** so new scenario pages render at runtime, not via the soon-deleted codegen — captured as **§ P3.6**. Confirmed scope: Music Auralic→amp, Music Revox→amp, + "some more" (children's room likely; full list TBD). Blocked on a wiring interview (which amp input each source uses; children's-room routing). No code change this entry.

---

