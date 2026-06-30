# Layer-3 runtime rendering — rollout record (archived)

**Status:** FROZEN. The per-step / per-commit history of the Layer-3 runtime-rendering rollout, extracted
verbatim from `docs/design/ui_backend_contract.md` on 2026-06-30 (DOC-10). The rollout is **complete and
hardware-verified**; this is the as-it-happened ledger (incremental migration, Step-2 hardening, Step-3
device-by-device rollout, Step-4 cutover). The **living** contract — manifest shape, placement engine,
endpoints, backend-call inventory, scenarios-as-composite-remote, icons/appliances — stays in
`docs/design/ui_backend_contract.md` → "Layout Manifest & Runtime Rendering". Kept for provenance.

---

### Migration (incremental, app stays runnable)
1. Manifest Pydantic + `/layout` endpoints; placement engine reproducing one device's `.gen.tsx`.
2. UI generic runtime renderer behind a flag for that device; visual diff vs. today. **+ Step 2
   hardening (below) before rollout.**
3. Roll across device classes; then scenarios.
4. Delete build-time generators + UI scenario duplication; update Invariants + playbook here.

### Step 2 hardening — runtime-render gaps & clean-fix plan (found 2026-05-23, mf_amplifier visual check)
The first runtime render (mf_amplifier, behind the flag) surfaced **three gaps the structural oracle
missed**. Two are real bugs; one is a confirmed *non-bug*.

1. **`specialCases` — a hardcoded back-channel (bug).** The renderer decides inputs/apps
   static-vs-fetch from a hardcoded `specialCases[wirenboard-ir-commands]` constant + a literal
   `deviceClass === 'WirenboardIRDevice'` check, **ignoring `populationMethod`** — which the manifest
   already carries (derived from the capability: `by_value` → `"commands"` + inline options;
   parametric `select`+`list` → `"api"` + `apiAction`/`setAction`). Every handler emits a
   `specialCases` constant; only a couple are read; the rest are dead.
2. **`null` vs `undefined` (bug).** The manifest serializes empty content fields as explicit `null`
   (`appsDropdown: null`); the renderer checks `!== undefined`, so `null` reads as "present" → a
   false-positive zone that renders a dropdown and tries to fetch (the mf_amplifier "Error loading
   apps"). The codegen omitted absent keys (`undefined`), which the UI handles correctly.
3. **Empty `menu`/zones — NOT a bug (decided 2026-05-23).** mf_amplifier's runtime menu zone is
   empty because its capability map declares no `menu` domain; the old codegen surfaced
   *group*-derived nav. The **capability-driven empty rendering is correct and preferred** — showing
   controls for functionality a device lacks is misleading (esp. in poor room light). Empty zones
   render as **labeled `(Empty)` placeholders** (user decision). Mapping the amp's menu IR commands,
   if ever wanted, is a separate capability-*content* decision, not a rendering fix.

**Decided principle:** the manifest is **complete, declarative, and class-agnostic**; the renderer
obeys manifest fields and **never** branches on `deviceClass` or `specialCases`. `populationMethod` is
the law for dropdowns.

**Clean-fix plan — applies to ALL devices** (the manifest contract + engine + shared renderer are
global; only the *runtime-render flag* stays per-device during rollout):

- **Backend:** B1 serve `/layout` with `exclude_none` (omit absent fields → fixes #2, shrinks
  payload, matches the codegen contract); B2 drop `special_cases`/`DeviceSpecialCase` from model +
  engine; B3 add `state_field` to the volume capability → surface as `valueField` on the volume zone
  config — **snake_case** (eMotiva volume → `zone2_volume`, others → `volume`), because the device
  state serializes snake_case with no camel alias (the old hardcode read camelCase `zone2Volume`,
  which never matched → eMotiva's slider value was silently broken); B4 **no-op** — every slider
  device already declares its set-volume `range` (eMotiva −96..0, others 0..100) and the engine
  surfaces min/max, so the range is already manifest-driven. `populationMethod`/`apiAction`/`setAction`
  already emitted — no change.
- **UI (shared renderer):** U1 `useInputsData`/`useAppsData`/`selectInput` obey `populationMethod`
  (delete `specialCases`, `isWirenboardIR`, `usesAppsAPI`); U2 volume reads `valueField` + range
  (delete `deviceClass === 'EMotivaXMC2'`); U3 remove `specialCases` from the type + adapter + strip
  the dead emission from the 8 handlers.
- **Validation:** render-level diff (Playwright) runtime vs build-time for mf_amplifier + a slider
  device (eMotiva) + an api device (Apple TV); `typecheck`/`lint`/`npm run check` green. Frozen
  oracle retired 2026-06-09 (`docs/archive/layer3_oracle/`).

Status (2026-05-23) — **re-scoped to the mf_amplifier pilot** (per the user: other devices +
scenarios are **Step 3**, so the LG/AppleTV api-select + eMotiva slider cleanups go there, done as
each device migrates + is hardware-tested):
- **commit 1 DONE** (`d0ca91e`) — backend B1 `exclude_none` + B3 volume `valueField` (B4 no-op);
  openapi/api.gen.ts regenerated.
- **commit 2 DONE** (`94dd612`) — UI **U1**: inputs/apps static-vs-fetch now obey `populationMethod`
  (deleted `specialCases`/`isWirenboardIR`/`usesAppsAPI` reads + the hardcoded `get_available_*`);
  `selectInput`/`launchApp` route by `populationMethod` and use the manifest's `setAction`.
- **Validated:** mf_amplifier renders clean via the render mock (INPUTS populate from commands, apps
  empty/no-fetch, Navigation correctly empty), matching the build-time page; backend 306 +
  `npm run check` green. **Step 2 is functionally complete for mf_amplifier** (real-world proof at the
  next UI deploy, since the flag defaults to mf_amplifier).
### Step-3 rollout (runtime renderer per device)
- **Easy WirenboardIR set DONE** (`1ebd5d8`): ld_player, video, vhs_player, upscaler (commands/buttons,
  no api dropdowns) — render-validated.
- **eMotiva DONE** (`6a2e95f`) — the first api/slider device. Surfaced + fixed a **latent
  param-passing bug** (the renderer sent the param *spec array* as the payload, not values). Landed:
  - **Fixed-params flow** (new): `ProcessedAction.params` carries the capability action's fixed native
    params (zone:1 power, zone:2 volume/mute); the engine threads them; the renderer sends
    `action.params` (buttons) + `{ level, ...params }` (slider). This is what made `action.parameters`
    (specs) stop being mis-sent.
  - **B5 DONE**: `DropdownConfig.setParam` (native value param from `param_map`: eMotiva `input`, LG
    `source`); `selectInput` sends `{ [setParam]: value }`.
  - **U2 DONE**: slider reads `deviceState[valueField]` (eMotiva `zone2_volume`); `deviceClass==='EMotivaXMC2'`
    deleted.
  - Validated end-to-end (Playwright/mock): power→{zone:1}/{}/{zone:1}, inputs populate + select→
    `set_input {input:hdmi2}`, dB slider renders.
- **Remaining**: LG ×2 + AppleTV ×2 (need the **apps `setParam`** generalization — apps domain),
  Auralic/streamer (the **slider value-param** generalization — native `volume` not `level`),
  reel_to_reel (easy, playback-only), kitchen_hood (appliance, deferred). Then scenarios.
- **Deferred to Step 4 cutover**: **B2/U3** full `specialCases` removal (model + UI type + 8 handlers)
  + oracle-test retirement; delete the build-time codegen; retire groups (§17.4).

### Step 4 — cutover (canonical scope)
The remaining Phase-3 work, after the runtime renderer covers 12/13 devices + the 4 scenarios. **What
the cutover removes = the build-time *page* generator and the now-unreachable fallbacks; the REST type
contract (`openapi.json`/`api.gen.ts`) stays** (see the "Scope note" and "Two generators" notes above).

- **UI (large, mechanical, no live-system risk):**
  - ✅ **A2 DONE (`243b030`):** removed the `.gen` fallback from `RuntimeDevicePage`/`RuntimeScenarioPage`
    (manifest fetch failure now shows "Layout unavailable") and the last runtime dependency on the
    generated registry — `Navbar` no longer imports `getDeviceRoute` (navigates directly to
    `/devices/${id}`; also fixed a latent `/device/${id}` singular-route bug). **No shipped source now
    imports `index.gen` / `getDeviceComponent` / `getScenarioComponent` / `getDeviceRoute`** → A3 can
    delete the generator.
  - ✅ **A3 DONE (`bb109c6`):** deleted the entire build-time page generator subsystem —
    `scripts/generate-device-pages.ts`, the generated outputs (`*.gen.tsx`/`*.hooks.ts`/`index.gen.ts`/
    `*.state.ts`), and the generator support libs (`StateTypeGenerator`, `DocumentationGenerator`,
    `BatchProcessor`, `DataValidator`, `ErrorHandler`, `PerformanceMonitor`, `ZoneDetection`,
    `lib/{deviceHandlers,generators,integration,validation}/`). Tooling: removed the codegen npm
    scripts + `tsconfig.scripts.json`/`typecheck:scripts`; `npm run check` = `typecheck:all && lint`;
    the UI `Dockerfile` no longer runs codegen or reads `backend/` (api.gen.ts is committed); CI
    `ui-validate` now runs `npm run check`. **U3 done as a side effect** (the `specialCases` emission
    lived in the deleted `lib/deviceHandlers/*`); the only `specialCases` remnants left are the inert
    type field in `types/RemoteControlLayout.ts` + reads in `layoutManifestAdapter.ts`/
    `useRemoteControlData.ts` → tidy in A4.
  - ✅ **Scenario web fallback retired (UI side, A3 `bb109c6`):** A1 removed its last runtime use
    (`App.tsx`), and it was entangled with the generator via the device handlers, so it was deleted
    with A3 — `ScenarioVirtualDeviceControls.tsx`, `useScenarioVirtualDevice.ts`,
    `ScenarioVirtualDeviceResolver.ts`, `DeviceConfigurationClient.ts`, and the `virtual_config` hooks
    in `useApi`. **A5 is now backend-only** (retire the `/scenario/virtual_config` endpoints + the
    `wb_adapter` resolver; keep the WB publication).
  - ✅ **A4 DONE (`5adb3f0`):** removed the inert `specialCases` from `types/RemoteControlLayout.ts`
    (the field + `DeviceSpecialCase` interface), `layoutManifestAdapter.ts` (stopped copying it), and
    refreshed the stale comment + retired the done `TODO(Step 3)` B5 note in `useRemoteControlData.ts`.
    The `api.gen.ts` `DeviceSpecialCase` type is generated — it goes when backend **B2** drops
    `special_cases` and openapi/api.gen are regenerated.
  - ✅ **Oracle retired 2026-06-09** (after A3): the frozen `docs/design/scenarios/layer3_oracle/*`
    JSONs archived to `docs/archive/layer3_oracle/`; `test_layout_manifest.py` deleted and
    `test_engine_reproduces_oracle` removed from `test_layout_engine.py` (the eMotiva multi-zone
    property test remains — it was never oracle-based). The fidelity-target role the oracle
    played at the engine's birth was superseded by hardware-verified render-level diff once each
    device class rolled onto the runtime renderer; both oracle-dependent test surfaces had
    been silently skipping or collection-erroring on a stale path for some time before retirement.
  - ✅ **A1 DONE (`f5a64cf`):** dropped the per-id runtime flag (removed the flag block from
    `config/runtime.ts`; the file stays for `runtimeConfig`/`getSSEUrl`) and the `App.tsx` gate —
    runtime is now the only path for A/V devices + scenarios. (The `.gen` fallback still lives inside
    `RuntimeDevicePage`/`RuntimeScenarioPage` → removed in A2.)
  - ✅ **Appliances — bespoke pages (A1, `f5a64cf`).** `kitchen_hood` (the sole
    `device_category=appliance`, no capability map → runtime manifest would be empty; its generated
    page was already empty since the renderer stopped reading `specialCases`) now has a **hand-written
    `src/pages/appliances/KitchenHoodPage.tsx`** (light `set_light{state}` + fan speed
    `set_speed{level}`), routed via a tiny hand-maintained registry `src/pages/appliances/index.ts`
    (`getAppliancePage` by device_id, checked in `App.tsx` before `RuntimeDevicePage`). This is the
    "appliances → bespoke pages" model — appliances do NOT go through the A/V runtime renderer. So the
    page generator below can be fully deleted (the appliance does not depend on it).
  - ✅ **Dead groups hooks retired (`9b388ab`)** — `useGroups`/`useDeviceGroups`/`useGroupActions` +
    their type imports removed from `useApi` (with the backend `/groups` router deletion).
  - ✅ **A7 DONE (`ba51f2c`)** — renamed `src/types/api.gen.ts` → `src/types/openapi.gen.ts` (git mv,
    history preserved; useApi import + `gen:api-types` `-o` path updated). Kills the `.gen` ambiguity:
    it's the generated REST type contract from `openapi.json`, and it SURVIVES the cutover.
  - ✅ **A8 phase 1 DONE (`2226ebf`)** — deleted the **dead** hand-written types from `api.ts` (no
    importers, not internal deps): the retired scenario-WB/virtual-config cluster (`ScenarioWBConfig`
    + `WB*` + `ScenarioVirtualConfig*`) and the unused error/config/util types (`ServiceInfo`,
    `ErrorResponse`, `ValidationError(LocInner)`, `HTTPValidationError`, `BaseDeviceConfig`,
    `BaseCommandConfig`, `CommandParameterDefinition`). `api.ts` now holds only the **19 live** types
    (15 imported by `useApi`/`useScenarioState` + internal deps `ManualInstructions`/`CommandStep`/
    `MQTTBrokerConfig`/`PersistenceConfig`). Importer surface is just those **2 files**.
  - ✅ **A8 phase 2 DONE (`37da8af`)** — `api.ts` now exports **18 thin named aliases** over
    `components['schemas'][…]` (single source of truth; the backend schema can't silently drift again).
    The alias swap surfaced **zero** typecheck errors (no consumer relied on a drifted shape) — and it
    retyped fields that HAD drifted, e.g. `SystemInfo.mqttBroker`→`mqtt_broker` (consumers reading
    `.mqttBroker` were getting `undefined`); free-form objects are now `unknown` (gen) not `any`. The
    hand-written `ManualInstructions` was dropped (dual-named backend models → no clean alias; reached
    transitively via `ScenarioDefinition`; the UI's own copy stays in `RemoteControlLayout.ts`). The 2
    importers (`useApi`, `useScenarioState`) are unchanged. npm run check + vite build green.
  - ✅ **A0 RESOLVED (2026-05-24, `e26e513`):** the status pane (`DeviceStatePanel`) no longer depends
    on the generated `stateInterface` — it renders the per-device "Device State" section from the **live
    `state` object** (keys + inferred type), so deleting the generated state types is safe. (This also
    fixed an already-silent regression: the section was empty for the runtime-enabled devices.)
    `StateTypeGenerator` itself goes with the page generator above.
  - Docs: `ui/README.md`, `docs/archive/ui-docs/page_instructions.md`.
- **Backend (small; the WB re-key touched live MQTT/WB control → ✅ hardware-verified, no degradation):**
  - ✅ **B2 DONE (`14db293`)** — dropped `special_cases`/`DeviceSpecialCase` from
    `presentation/api/layout_manifest.py`; the oracle-parse test strips the retired key; regen.
  - ✅ **`/groups` router DELETED (`9b388ab`)** — `routers/groups.py` + its registration; UI hooks
    were dead. Removed GET `/groups`, `/devices/{id}/groups`, `…/groups/{gid}/actions`.
  - ✅ **`/scenario/virtual_config` endpoints RETIRED (`0af97e5`)** — the two HTTP endpoints +
    the unused `ScenarioWBConfig` import in `routers/scenarios.py`. **WB integration wiring KEPT**:
    the `scenario_wb_adapter` global/param stays (now unread by the router, annotated), and the adapter
    + its domain-service usage (Layer-R control) are untouched. (Scenario WB *publishing* is already
    disabled in bootstrap pending the scenario↔WB design.)
  - ✅ **WB re-key — step 1 of 4 DONE (golden-snapshot, `1a72a56`+`8fb2fdc`).** `wb_device/service.py`
    now keys WB exposure/type/order off the capability **domain+kind+exposed** on the **device path**
    (capabilities threaded from `base.py`); scenario path keeps the group fallback. Proven equivalent
    by `tests/unit/test_wb_rekey.py` (13-device golden snapshot): zero controls added, zero meta/order
    changes — byte-identical EXCEPT a correctness fix (3 `exposed:false` dormant commands —
    `streamer.refresh_inputs`, `appletv*.refresh_status` — no longer leak onto WB; they were dead, the
    exposure gate already rejected them). ✅ **HARDWARE PASS PASSED (2026-05-24)** — verified on the live
    system: WB works as before, no degradation. (The hardware run also surfaced an unrelated UI bug —
    the status-pane alias cross-device leak, `ebe625e` — now fixed.)
  - ✅ **WB re-key — step 2 DONE (`f57322c`)** — deleted the orphaned group machinery
    (`base._action_groups`/`_build_action_groups_index`/`get_available_groups`/`get_actions_by_group`,
    `config_manager._groups`/`get_groups`/`is_valid_group`); zero consumers after the `/groups`
    deletion. base.py no longer reads `cmd.group`. backend 320.
  - ✅ **WB re-key — step 3 DONE (`f519605`)** — DELETED the dormant scenario↔WB path
    (`ScenarioWBAdapter`, `ScenarioWBConfig`, `setup_wb_emulation_for_all_scenarios` + the MQTT-sub
    setup, bootstrap/router wiring), removing the last scenario-side `group` reader. It was dead
    (no caller, no tests; the `/scenario/virtual_config` consumer was already retired). The WB-service
    `group` **fallback is KEPT** — it serves capability-less devices that still enable WB (the
    `kitchen_hood` appliance). **A clean scenario↔WB replacement is now MANDATORY** (action_plan P4 #7);
    there is currently no scenario representation on Wirenboard at all.
  - ✅ **WB re-key — step 4 DONE (`c4dfb57`)** — purged `group` entirely (user accepted the revert
    risk): dropped `BaseCommandConfig.group` + `SystemConfig.groups`; removed `group` from all 182
    command entries + `system.json` `groups`; the WB fallback is now group-free (exclusion by
    `exposed`, type/order from `wb_controls`/params). Behaviour-neutral — the WB golden snapshot
    (13 devices) is unchanged. backend 320; openapi/api.gen regen. **`group` is fully gone from the
    backend** (the earlier kitchen_hood "blocker" was a false alarm — it's `wb_controls`-driven).
  - ✅ **Review follow-ups DONE (`864e61e`+`80ef918`):** (a) the WirenboardIR optimistic-input
    detection now keys off the **capability `input` domain's by_value mapping** (command→value), not a
    command-name convention; (b) removed the **dead UI group code** — `types/DeviceConfig.ts`
    (+`deriveGroupsFromConfig`, `DeviceClassHandler`), the `api.ts` groups types/fields,
    `RemoteControlLayout.ts` `ZoneDetectionConfig`/`DEFAULT_ZONE_DETECTION`, and the dead `useApi`
    queryKeys. Only the live manifest `ProcessedAction.group` + `media-stack-group` CSS remain.
    ✅ **WB re-key COMPLETE + HARDWARE-VERIFIED (steps 1-4, 2026-05-24)** — `group` is fully retired
    from the backend, the live WB output is confirmed unchanged (no degradation), so the revert-
    insurance no longer applies.
  - **NOT remaining:** the `execute_action` **exposure gate is already implemented + active**
    (`infrastructure/devices/base.py` — rejects `exposed:false` from external sources, allows
    scenario/system/cli) and coverage is MET (redesign §17.3). Nothing to "flip."
- **Shared:** the frozen-oracle retirement that this section originally planned was completed
  2026-06-09 (`docs/archive/layer3_oracle/` + oracle tests removed); **regenerate `openapi.json`
  + `api.gen.ts` — but only because the backend deletions change the API surface** (`/groups`,
  `/scenario/virtual_config`, the `LayoutManifest` schema losing `special_cases`). A UI-only
  step needs no regen.
- **Sequencing (as executed):** UI-first (render path proven, zero live-system risk), then the backend
  WB re-key as its own commits with a hardware pass — it was the only change that could disrupt real
  MQTT control of the house. ✅ All done + hardware-verified (no degradation).
