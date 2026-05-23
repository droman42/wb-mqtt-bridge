# Scenario System Redesign — Capability, Topology & Reconciliation Contract

- **Status:** IMPLEMENTED — Phase 1 landed on `main` (2026-05-22). Authored 2026-05-20. See
  `scenario_redesign_progress.md` for the as-built record.
- **Supersedes:** the old scenario specs, now archived under `docs/archive/scenarios/`.
- **Scope:** Backend (`wb-mqtt-bridge`). UI consumes the resulting contract; no UI design here beyond exposure notes.

This document is the agreed design from the redesign discussion. It defines **what** the
scenario system is and the **contracts** (file schemas + runtime behavior). It is implemented —
the reconciler, topology, and capability maps all exist in `src/`; full hardware verification of
the reconciler is the one remaining item (see the progress doc).

---

## 1. Why we are redesigning

The current scenario layer is functionally broken. Root causes (verified against code/configs):

- **RC1 — parameter/name drift.** Scenarios call device commands with names/params that don't
  match the device contract (`set_input_source` passes `input_source`, device wants `source`;
  `processor.power_off` needs `zone`, scenario passes none). Fails at runtime in **all four**
  scenarios.
- **RC2 — silent failure.** `execute_action()` never raises; sequence runners never check
  `success`. Broken steps are skipped invisibly.
- **RC3 — switch reimplements shutdown** as a hardcoded `power_off`, which toggle-only IR
  devices (`ld_player`, `vhs_player`) don't have, so they're left running on switch.
- **RC4 — dead validation.** `_validate_parameters` checks `.parameters` (field is `.params`),
  so param errors are never caught at load.
- **RC5 — condition type gaps** (`zone2_power != True` never short-circuits, etc.).

Deeper, three **conceptual** capabilities the project wants are missing:

- **(a) Inheritance** — a scenario should inherit device functions automatically.
- **(b) Translation** — a scenario should map its own symbolic actions to each device's real
  command + params (so callers/configs needn't know device-native vocabulary).
- **(c) Universal device** — a scenario should behave as one orchestration + translation device
  between any caller (frontend, FastAPI, wb-rules) and the underlying gear.

The redesign delivers (a)(b)(c) and eliminates RC1–RC5 as **consequences of the model**, not
patches.

---

## 2. North star: the Logitech Harmony model

The A/V system deliberately inherits Harmony's behavior. Harmony is **IR-first and
feedback-free**, yet works because it:

1. Keeps an **assumed (optimistic) state model** — it's the only controller, so it trusts what
   it last sent.
2. Switches activities by **delta** from assumed state → target state.
3. Uses **discrete** commands where they exist; falls back to **toggle + assumed-state**.
4. Pushes **per-device "how-to" + timing** into a device database.
5. Provides a **resync escape hatch** when reality drifts. Our version: the user opens the
   device's own UI page and brings it up to state manually (accepted limitation).

This makes a desired-state reconciler viable across a fleet that is mostly feedback-less IR.

---

## 3. Architecture: four layers

```
Layer 0  Topology        config/topology.json     — the physical wiring, declared once
Layer 1  Capability map  driver (+ config override)— each device self-describes how-to + timing
Layer 2  Activity        config/scenarios/*.json   — declarative desired-state (a thin selection)
Layer R  Reconciler      runtime engine            — diff assumed→target, order, gate, execute
Layer 3  Layout manifest backend endpoint          — runtime device+scenario page construction
```

**Layer 3 (runtime UI rendering)** is specified in `docs/ui_backend_contract.md` →
"Layout Manifest & Runtime Rendering". It replaces build-time `.gen.tsx` codegen: the backend
serves a layout manifest (fed by the capability map + reconciler-resolved roles + topology) and the
UI renders it with one generic `RemoteControlLayout`. This subsumes the placement contract
(P2.5 #10) and resolves the UI duplication described in §8.1.

- **Topology** = the fixed signal graph (who feeds whose input; ARC paths; ordering edges).
- **Capability map** = the translation layer (canonical action → native command/params/sequence)
  + timing + feedback flag. Roles are capability domains; scenarios inherit it at init.
- **Activity/Scenario** = a selection (`source`/`display`/`audio`) plus role bindings for live
  commands, optional manual instructions, and an optional explicit-sequence escape hatch.
- **Reconciler** = computes and runs the minimal ordered action plan; owns optimistic state.

---

## 4. Layer 0 — Topology contract (`config/topology.json`)

The **physical truth**, declared **once**. Scenarios reference it; they never restate wiring.

### 4.1 Schema (conceptual)

```jsonc
{
  "links": [
    {
      "from": "appletv_living:hdmi",     // <device_id>:<port>
      "to":   "processor:hdmi2",
      "carries": ["video", "audio"]      // signal kinds on this link
    },
    { "from": "upscaler:out",      "to": "processor:hdmi3",       "carries": ["video"] },
    { "from": "processor:hdmi_out","to": "living_room_tv:hdmi2",  "carries": ["video"] },
    { "from": "living_room_tv:arc","to": "processor:arc",         "carries": ["audio"] },
    { "from": "processor:zone1",   "to": "mf_amplifier:aux2",     "carries": ["audio"] }
  ],

  "ordering": [
    {
      "after":  "living_room_tv.input",   // <device_id>.<capability>
      "before": "processor.input",
      "reason": "HDMI-ARC: TV must settle its input before the processor routes"
    }
    // ... enumerate the remaining real dependencies here
  ]
}
```

### 4.2 Semantics

- **A link's destination port is the input value.** Routing through `processor:hdmi2` means the
  processor's `input` target is `hdmi2`; through `living_room_tv:hdmi2` means TV `input` =
  `hdmi2`; `mf_amplifier:aux2` means amp `input` = `aux2`. **This is how the engine derives
  input values** — scenarios don't list them.
- **`ordering`** is an explicit list of `X before Y` edges over `<device>.<capability>`. The
  reconciler topo-sorts the action plan to respect them. This captures the HDMI-ARC dependency
  and "the more" you'll enumerate.
- Ordering rules that are universal (e.g. *power before input on the same device*) are built into
  the reconciler, **not** declared here.

### 4.3 Validation (load-time)

- Every `device_id` in a link/ordering edge exists in the device registry.
- Ports are free-form strings but must be consistent (a referenced sink port should correspond to
  a value the device's `input.select` can produce — checked against the capability map where
  possible).
- The graph is acyclic for the purpose of ordering (cycles in `ordering` → fatal).

### 4.4 Pydantic model (to fill in via dialog)

```python
from typing import Dict, List, Literal
from pydantic import BaseModel, Field, ConfigDict

SignalKind = Literal["video", "audio", "arc"]

class ManualNode(BaseModel):
    """A signal-routing element switched by hand (no driver), e.g. an RCA hub."""
    kind: Literal["manual"] = "manual"
    name: str
    positions: Dict[str, str] = Field(
        default_factory=dict,
        description="position-id -> human instruction surfaced when that position is needed",
    )

class TopologyLink(BaseModel):
    # `from` is a Python keyword → aliased; JSON keeps the natural "from"/"to".
    model_config = ConfigDict(populate_by_name=True)
    from_: str = Field(..., alias="from", description="<node>:<port> source/output end")
    to:    str = Field(..., description="<node>:<port> sink end; dst port = the input value to select")
    carries: List[SignalKind] = Field(..., min_length=1)

class OrderingEdge(BaseModel):
    first: str = Field(..., description="<device>.<capability> that must complete first")
    then:  str = Field(..., description="<device>.<capability> that runs after `first`")
    delay_ms: int = Field(0, ge=0, description="extra wait after `first` before `then` (no-feedback waits)")
    reason: str = ""

class Topology(BaseModel):
    nodes:    Dict[str, ManualNode] = Field(
        default_factory=dict,
        description="special (e.g. manual) nodes; ordinary device nodes are implied by links",
    )
    links:    List[TopologyLink] = Field(default_factory=list)
    ordering: List[OrderingEdge]  = Field(default_factory=list)
```

The real wiring lives in `config/topology.json` (authored 2026-05-20 from the hardware interview).
Ordering uses unambiguous `first → then` (not "after/before"). `delay_ms` covers no-feedback waits
(e.g. the IR upscaler); feedback-capable steps are completion-polled instead.

---

## 5. Layer 1 — Device Capability contract

Each device self-describes its **canonical capabilities**. This is the translation layer and the
"device DB." It lives in the **driver** (authoritative default), with an optional **per-device
config override** (`config/devices/*.json`). Roles in scenarios are **capability domains**, so a
role binding inherits the device's whole map for that domain at init — no hardcoded
`role_group_mapping`.

### 5.1 Canonical taxonomy

Two classes of capability:

- **Stateful** — participate in desired-state reconciliation (have a target + are diffed).
- **Momentary** — fire-and-forget live commands (exposed on the universal device, never reconciled).

| Domain | Kind | Canonical actions | Notes |
|---|---|---|---|
| `power` | stateful | `on`, `off`, `toggle` | toggle = IR fallback; engine uses assumed state |
| `input` | stateful | `select(input)` | target value derived from topology |
| `volume` | momentary | `up`, `down`, `set(level)`, `mute_on`, `mute_off`, `mute_toggle` | role auto-binds to active audio device |
| `playback` | momentary | `play`, `pause`, `play_toggle`, `stop`, `next`, `previous`, `ff`, `rewind` | |
| `tracks` | momentary | `audio_next`, `subtitle_next`, … | device-specific |
| `menu` | momentary | `up`, `down`, `left`, `right`, `ok`, `back`, `home`, `menu`, `exit` | |
| `screen` | momentary | `aspect_4_3`, `aspect_16_9`, `letterbox`, … | device-specific |
| `apps` | momentary | `launch(app)`, `list` | |
| `pointer` | momentary | `move(dx,dy)`, `tap(x,y)`, `gesture`, `click` | |

(Only `power` and `input` are reconciled in v1. `volume` level is **not** part of activity
desired-state by default — it's live.)

### 5.2 Capability descriptor (per device)

```jsonc
{
  "capabilities": {
    "power": {
      "kind": "stateful",
      "feedback": true,                  // can we read real state?
      "state_field": "power",            // field on the device's state model
      "on_value": "on",                  // value meaning "on"
      "actions": {
        "on":  { "command": "power_on" },
        "off": { "command": "power_off" }
        // toggle-only IR device would instead declare: "toggle": { "command": "power" }
      },
      "delays": { "after_on_ms": 5000, "after_off_ms": 0 }
    },

    "input": {
      "kind": "stateful",
      "feedback": true,
      "state_field": "input_source",
      "select": {
        "command": "set_input_source",
        "param_map": { "input": "source" }   // canonical 'input' -> native 'source'  (kills RC1)
      },
      "delays": { "settle_ms": 1000 }
    },

    "volume": {
      "kind": "momentary",
      "actions": {
        "up":   { "command": "volume_up" },
        "down": { "command": "volume_down" },
        "set":  { "command": "set_volume", "param_map": { "level": "level" } },
        "mute_toggle": { "command": "mute" }
      }
    }
  }
}
```

Key fields:

- **`command`** — native command name. May instead be **`sequence`** (an ordered list of native
  steps with optional inter-step delays) for IR boxes that need stepping (e.g. *Input → Down →
  Down → OK*).
- **`param_map`** — canonical param name → native param name. The engine renames before calling
  `execute_action`. This is where `input` → `source`, etc. live.
- **`feedback`** — drives gating (see §7.4): `true` → completion-poll; `false` → fixed delay.
- **`state_field` / `on_value`** — how the reconciler reads assumed/actual state to diff and to
  decide toggles.
- **`delays`** — device-declared timing; scenarios don't carry magic delays anymore.

### 5.3 Toggle / no-feedback devices

- A device that has only a `power` toggle declares `actions.toggle` and `feedback: false`. The
  reconciler computes "need on" vs "assumed off" and **fires the toggle once**, then updates
  assumed state. No feedback poll; fixed delay only.
- Discrete on/off IR codes (where the physical remote has them, or via the planned IR-learning
  page) upgrade a device from `toggle` to `on`/`off` with no scenario changes — purely a
  capability-map edit.

### 5.4 Multi-zone devices (eMotiva)

The processor has zone1/zone2 power and a main input. **Decision (13.1): keep the current
model — zones are expressed via `params` on the power commands (`{zone: 1|2}`)**, matching the
existing device contract. We do **not** introduce a separate `power_zone2` capability. The
capability descriptor therefore declares `power.on`/`power.off` with a `zone` param, and the
reconciler/scenario supplies the zone.

---

## 6. Layer 2 — Activity / Scenario contract

A scenario becomes a **thin selection** over the topology + capabilities. Most of what is hand-
authored today is **derived**.

### 6.1 Schema (proposed)

```jsonc
{
  "scenario_id": "movie_appletv",
  "name": "Watch Apple TV",
  "room_id": "living_room",

  // --- the selection (drives desired-state derivation) ---
  "source":  "appletv_living",      // primary content source
  "display": "living_room_tv",      // primary video sink
  "audio":   "mf_amplifier",        // active speakers; binds volume/mute roles, powers audio path

  // --- live (momentary) role bindings for the universal device ---
  // Auto-derived where possible (volume<-audio, playback/tracks<-source); listed only to override.
  "roles": {
    "menu":    "appletv_living",
    "pointer": "appletv_living",
    "apps":    "appletv_living"
  },

  // --- human-in-the-loop notes ---
  "manual_instructions": {
    "startup":  ["💡 Dim the living-room lights", "🎬 Lower the screen"],
    "shutdown": ["💡 Lights back on"]
  },

  // --- ESCAPE HATCH (optional): explicit steps the graph can't express ---
  // When present, these run in addition to / instead of derived steps for the named devices.
  "startup_sequence":  [ /* CommandStep[] — device-native, as today */ ],
  "shutdown_sequence": [ /* CommandStep[] */ ]
}
```

### 6.2 What the engine derives (so the scenario doesn't state it)

- **Involved devices**: `source`, `display`, `audio`, and every device on the topology path(s)
  connecting them (e.g. the processor between Apple TV and TV).
- **Target power**: `on` for involved devices; `off` for devices that are on in assumed state but
  not involved (handled by the diff — see §7).
- **Target inputs**: from the destination ports of the links on the active path.
- **Volume/mute role binding**: → the `audio` device. (TV-as-speakers is just `audio: living_room_tv`.)
- **Ordering + delays**: from `topology.ordering` + per-device capability delays.

### 6.3 Roles and momentary commands

`roles` binds the universal device's **momentary** commands to a device. Auto-derivation:
`volume`/`mute` ← `audio`; `playback`/`tracks` ← `source`. `menu`/`pointer`/`apps`/`screen` are
listed explicitly when ambiguous. Live commands dispatch as canonical `role.action` → translated
to native via the bound device's capability map.

### 6.4 Manual instructions (baseline + transition-aware)

- **Baseline:** `manual_instructions.startup/shutdown` (static lists) — kept as-is.
- **Transition-aware (option):** a manual note may be attached to a **topology link** and surfaced
  **only when that link activates/deactivates** in the current transition (e.g. "set the RCA hub
  to the LD position" appears only when switching onto the analog path). Decision pending (§13).

### 6.5 Escape hatch

`startup_sequence` / `shutdown_sequence` (the current `CommandStep[]` shape) remain **optional**.
When present they run for the listed devices, letting us handle quirks the graph can't model
without ever being blocked. Default scenarios omit them entirely.

---

## 7. The Reconciler (runtime engine)

Replaces the imperative `execute_startup_sequence` / `execute_shutdown_sequence` and the hardcoded
`switch_scenario` power-off loop.

### 7.1 Assumed state

- **Assumed state = `device.state`** (already updated by every device action, including manual
  actions from the device's UI page) and is **persisted**. There is no separate state store to
  keep in sync; resync happens for free when the user fixes a device via its page.

### 7.2 Resolve target

From the activity selection + topology, build `target[device] = {power, input?}` for involved
devices. Uninvolved devices have no explicit target (the diff decides whether to power them off).

### 7.3 Diff & plan

For each device/capability, compare assumed state to target. Emit an action only where they
differ (this subsumes the old per-step `condition`s). Then **topo-sort** the actions by:

1. **Universal rule:** `power.on` before `input.select` on the same device.
2. **Topology `ordering` edges:** e.g. `living_room_tv.input` before `processor.input`.
3. **Phase grouping:** power-on phase → input-routing phase → (momentary app launch, if declared).

### 7.4 Execute & gate

For each stateful action:

- Translate canonical → native (`command`/`sequence` + `param_map`), call `execute_action`.
- **Check `success`** (kills RC2). On failure: if the step is critical, abort and report; else
  record and continue.
- **Gate before dependent steps:**
  - `feedback: true` → **poll** the device's `state_field` until it equals the target (or
    timeout). This replaces the blind delay for the LG/eMotiva/AppleTV/Auralic.
  - `feedback: false` → wait the device-declared fixed delay.
- Update assumed state.

### 7.5 Start / switch / shutdown — all one operation

- **Start** = reconcile from current assumed state (possibly all-off) to target.
- **Switch** = reconcile from outgoing activity's assumed state to incoming target → shared
  devices keep power, only inputs change; devices not in the incoming activity power off (RC3 gone).
- **Shutdown (complete)** = reconcile to all-involved-off.

### 7.6 Error reporting

Failures are returned to the caller and broadcast via SSE with a structured payload:
`{device, capability, action, error, hint: "open <device> page to correct"}`. This makes the
optimistic-state escape hatch discoverable.

---

## 8. Universal-device exposure (WB + REST)

The scenario remains a WB virtual device and a REST surface, now expressing canonical capabilities:

- **Power group:** `activate` (start) / `deactivate` (shutdown) / `switch`.
- **Momentary role commands:** `role.action` (e.g. `volume.set`, `playback.play`, `menu.up`) →
  live dispatch through the bound device's capability map.
- **Volume/mute** always target the active `audio` device; the caller never needs to know which
  physical device that is.
- REST keeps `/scenario/*`; `role_action` payloads use **canonical** action + params (translation
  happens server-side), so the frontend speaks one vocabulary regardless of device.

The capability map and the derived scenario command set are published in the OpenAPI contract so
the UI codegen and the (future) button-placement contract (P2.5 #10) consume one source of truth.

### 8.1 UI coupling & impact (verified 2026-05-20)

**Finding:** scenario inheritance is currently implemented **twice**. Besides the backend's
`ScenarioWBConfig`, the **UI re-derives scenario pages itself**: `ScenarioVirtualDeviceHandler`
(sibling repo) reads the scenario's `roles`, then for each role reads the bound device's config
file and inherits its commands by matching `command.group === role`. The UI does **not** consume
the backend's resolved scenario virtual config. (The UI also carries a second, partly-stale
hardcoded group→action taxonomy in `ScenarioVirtualDeviceResolver.createVirtualDeviceGroups`,
e.g. `navigation` vs `menu` and invented actions — a latent drift source.)

**Consequences for this redesign:**

- **Device pages are safe.** They're generated from device configs (`commands`/`group`/`params`).
  The capability map is **additive** — we keep the existing `commands` structure, so individual
  device pages are unaffected. *(Constraint: do not remove `commands`/`group` from device configs
  in v1.)*
- **Scenario pages depend on explicit `roles` in the scenario JSON.** Therefore **fully omitting
  `roles` (pure backend auto-derivation) would break scenario page generation.** Two ways to keep
  the UI working (decision 13.4):
  - **Path 1 (v1, no UI change):** the scenario config the UI reads must still **carry `roles`** —
    either authored, or **emitted by the backend** as a resolved file. Backend auto-derivation is
    allowed, but its output must materialize `roles` for the UI.
  - **Path 2 (follow-up):** refactor the UI to consume the **backend-resolved** scenario virtual
    config (single source of truth). This removes the duplicate inheritance **and** the stale UI
    taxonomy. Recommended, but scheduled as its own workstream (touches the UI repo).

**Net for 13.4:** auto-derivation is accepted **provided `roles` remain materialized** in what the
UI consumes (Path 1) until Path 2 lands. Device pages need no change.

**Update — Path 2 chosen.** The project is moving page construction to **runtime** (Layer 3, see
§3 and `docs/ui_backend_contract.md`). With the backend serving a resolved layout manifest, the UI
no longer re-derives scenarios from raw JSON, so the duplicate `ScenarioVirtualDeviceHandler` /
`ScenarioVirtualDeviceResolver` are deleted and roles can be fully auto-derived (no longer
materialized for the UI). The Path-1 constraint applies only to the interim build-time period.

---

## 9. Validation rules (load-time)

1. **Topology:** referenced devices exist; `ordering` is acyclic; sink ports resolve to
   `input.select` values where checkable.
2. **Capability:** every `param_map` target is a real native param of the named command (this is
   the **fixed** version of RC4 — it would have caught RC1 at load); declared `state_field`
   exists on the device's state model.
3. **Scenario:** `source`/`display`/`audio` exist and are reachable in the topology; a path
   exists from `source` to `display` (and to `audio`); every `role` binds to a device that
   advertises that domain; escape-hatch steps resolve to real device commands/params.
4. **Fail loudly** at load with aggregated, human-readable errors (no `SystemExit` swallow; no
   silent dead validation).

---

## 10. How this resolves the root causes & realizes the concepts

| Item | Resolution |
|---|---|
| RC1 param/name drift | Translation via capability `param_map`; load-time validation catches mismatches |
| RC2 silent failure | Reconciler checks `success`, gates, and reports via SSE |
| RC3 switch power-off | Switch = diff; teardown uses each device's real `power.off`/`toggle` |
| RC4 dead validation | Capability validation re-enabled and correct |
| RC5 condition gaps | Conditions replaced by typed state diff; no string/bool ambiguity |
| (a) inheritance | Roles = domains; scenario inherits the capability map at init |
| (b) translation | Capability map (canonical → native command/params/sequence) |
| (c) universal device | Canonical `role.action` over WB + REST; reconciler orchestrates |

---

## 11. Impact on current code

**New**
- `config/topology.json` + Pydantic model + loader (in `ConfigManager`).
- Capability descriptor model; `BaseDevice` exposes `get_capabilities()`; per-driver defaults;
  config override merge.
- `ScenarioReconciler` (new) owning resolve/diff/order/gate/execute.

**Changed**
- `ScenarioDefinition` (domain/scenarios/models.py): add `source`/`display`/`audio`; make
  `startup_sequence`/`shutdown_sequence` optional (escape hatch); keep `roles`,
  `manual_instructions`.
- `ScenarioManager.switch_scenario` → delegates to the reconciler (remove hardcoded `power_off`).
- `ScenarioWBConfig._generate_virtual_commands` / `_extract_role_commands` → drive off the
  capability map; delete `role_group_mapping`.
- `Scenario.validate_configuration` / `_validate_parameters` → corrected, capability-aware.

**Removed**
- Hardcoded `role_group_mapping`; hardcoded switch power-off; string-condition evaluator
  (replaced by typed diff); dead `DeviceState.output` (or wire it if topology needs it).

---

## 12. Migration plan (incremental, keeps system runnable)

1. **Capability maps for the 7 drivers** (driver defaults) + load-time validation. No behavior
   change yet; just self-description.
2. **Topology.json** authored from the real rack (needs your wiring + ordering edges).
3. **Reconciler** behind a flag; convert one scenario (`movie_appletv`) to the slim schema; keep
   the others on the escape-hatch (old sequences) until verified.
4. **Switch** routed through the reconciler; verify diff behavior on hardware.
5. Convert remaining scenarios; retire the imperative path.
6. Publish capability map in OpenAPI; wire UI.

Each step is independently shippable and testable (mock-level), with a hardware pass at 3–4.

### v1 scope (proposed)
- Reconciled capabilities: **`power`, `input`** only.
- Gating: completion-poll for LG/eMotiva/AppleTV/Auralic; fixed delay for IR.
- Momentary: all domains exposed but not reconciled.
- Transition-aware manual notes: **deferred** (baseline static notes in v1).

---

## 13. Decisions

Resolved 2026-05-20:

1. **Multi-zone (eMotiva)** — **RESOLVED:** keep the current model; zones via `params`
   (`{zone: 1|2}`) on the power commands. No separate capability. (See §5.4.)
2. **Transition-aware manual notes** — **RESOLVED:** **deferred** until the core scenario system
   works. v1 ships static `manual_instructions` only.
3. **Capability override location** — **RESOLVED:** **driver-default + optional
   `config/devices/*.json` override.**
4. **Role auto-derivation** — **RESOLVED (conditional):** allowed (`volume←audio`,
   `playback/tracks←source`, explicit override), **provided the UI doesn't break.** Per §8.1: in
   v1 the scenario config the UI reads must still **materialize `roles`** (authored or
   backend-emitted); full omission waits for the UI Path-2 refactor. Device pages unaffected.

Still open:

5. **Topology ordering rule** — explicit `ordering` edges only, or *also* a global default rule
   (e.g. "sink input settles before upstream source")? Pending your decision + the real dependency
   list. (Discussion notes provided separately.)

---

## 14. Status of inputs (updated 2026-05-20)

- **Wiring** — gathered via the hardware interview and written to `config/topology.json`.
- **Ordering edges** — captured (6 edges that reproduce the observed manual startup sequence); in
  `config/topology.json`. We proceeded with **explicit `ordering` edges only** (no global default
  rule) — resolves 13.5.
- **§13 decisions** — 13.1–13.4 resolved. Placement-derived (capability decision 5) is
  **tentative**, to be finalized during Layer 3 layout analysis.
- **Capability maps** — the four `movie_appletv` devices approved; recorded in §16.

## 15. Future research / known limitations

- **Apple TV "Who's watching?" startup screen (tvOS-version-dependent).** Recent tvOS versions
  show a profile-selection ("Who is watching?") screen on wake/startup that must be confirmed
  before the Apple TV is usable for playback. This can **block a scenario's startup** (the source
  isn't "ready" until the screen is dismissed). **Research later:** whether the Apple TV driver
  (pyatv) can auto-select a default profile / dismiss this screen and make that a step in the
  startup procedure. Feasibility and behavior depend on the **installed tvOS version**, so any
  solution likely needs to be conditional (detect the screen / version-gated). Affects the
  reconciler's "is the source ready" gating for Apple TV scenarios.

## 16. Capability maps — worked examples (approved 2026-05-20)

The four `movie_appletv` devices, against the §5 shape. These become **driver defaults**
(decision 13.3: driver default + optional `config/devices/*.json` override). Conventions:
`param_map` only for renames (identity omitted); `feedback:true` ⇒ completion-poll `state_field`
to target (`gate.poll_timeout_ms`), `feedback:false` ⇒ fixed `gate.delay_ms`; stateful caps are
reconciled, momentary caps are live-only.

### 16.1 LG TV (`living_room_tv`) — feedback, parametric input
```jsonc
{
  "power": { "kind":"stateful","feedback":true,"state_field":"power","on_value":"on",
    "actions": { "on":{"command":"power_on"}, "off":{"command":"power_off"} }, "gate":{"poll_timeout_ms":8000} },
  "input": { "kind":"stateful","feedback":true,"state_field":"input_source",
    "select": { "command":"set_input_source","param_map":{"input":"source"} },   // kills RC1
    "list":   { "command":"get_available_inputs" }, "gate":{"poll_timeout_ms":3000} },
  "volume": { "kind":"momentary","actions": {
    "up":{"command":"volume_up"},"down":{"command":"volume_down"},
    "set":{"command":"set_volume","param_map":{"level":"level"}},"mute_toggle":{"command":"mute"} } },
  "menu": { "kind":"momentary","actions": {
    "up":{"command":"up"},"down":{"command":"down"},"left":{"command":"left"},"right":{"command":"right"},
    "ok":{"command":"enter"},"back":{"command":"back"},"home":{"command":"home"},"menu":{"command":"menu"},"exit":{"command":"exit"} } },
  "playback": { "kind":"momentary","actions": {
    "play":{"command":"play"},"pause":{"command":"pause"},"stop":{"command":"stop"},
    "ff":{"command":"rewind_forward"},"rewind":{"command":"rewind_backward"} } },
  "apps": { "kind":"momentary","actions": {
    "launch":{"command":"launch_app","param_map":{"app":"app_name"}},"list":{"command":"get_available_apps"} } },
  "pointer": { "kind":"momentary","actions": {
    "move":{"command":"move_cursor","param_map":{"x":"x","y":"y"}},
    "move_rel":{"command":"move_cursor_relative","param_map":{"dx":"dx","dy":"dy"}},"click":{"command":"click"} } }
}
```

### 16.2 MF amp (`mf_amplifier`) — IR, toggle power, value-mapped input
```jsonc
{
  "power": { "kind":"stateful","feedback":false,"state_field":"power","on_value":"on",
    "actions": { "toggle":{"command":"power"} }, "gate":{"delay_ms":1000} },   // toggle from assumed state
  "input": { "kind":"stateful","feedback":false,"state_field":"input",         // requires the new optimistic input field (dec. 3)
    "select": { "by_value": {
      "cd":{"command":"input_cd"},"aux2":{"command":"input_aux2"},"usb":{"command":"input_usb"},
      "phono":{"command":"input_phono"},"tuner":{"command":"input_tuner"},
      "aux1":{"command":"input_aux1"},"balanced":{"command":"input_balanced"} } }, "gate":{"delay_ms":500} },
  "volume": { "kind":"momentary","actions": {
    "up":{"command":"volume_up"},"down":{"command":"volume_down"},"mute_toggle":{"command":"mute"} } }
}
```

### 16.3 eMotiva (`processor`) — multi-zone power, parametric input, feedback
```jsonc
{
  "power": { "kind":"stateful","feedback":true,"gate":{"poll_timeout_ms":6000},
    "zones": {     // 13.1: zones via params; "power on" = all declared zones on
      "1": { "state_field":"power",      "on_value":"on",
             "actions": { "on":{"command":"power_on","params":{"zone":1}},"off":{"command":"power_off","params":{"zone":1}} } },
      "2": { "state_field":"zone2_power", "on_value":"on",
             "actions": { "on":{"command":"power_on","params":{"zone":2}},"off":{"command":"power_off","params":{"zone":2}} } } } },
  "input": { "kind":"stateful","feedback":true,"state_field":"input_source",
    "select": { "command":"set_input" }, "list":{"command":"get_available_inputs"}, "gate":{"poll_timeout_ms":3000} },
  "volume": { "kind":"momentary","actions": {        // latent: volume role = amp in current scenarios; native level is dB (-96..0)
    "set":{"command":"set_volume","param_map":{"level":"level"},"params":{"zone":2}},
    "mute_toggle":{"command":"mute_toggle","params":{"zone":2}} } }
}
```

### 16.4 Apple TV (`appletv_living`) — feedback, no input (pure source)
```jsonc
{
  "power": { "kind":"stateful","feedback":true,"state_field":"power","on_value":"on",
    "actions": { "on":{"command":"power_on"},"off":{"command":"power_off"} }, "gate":{"poll_timeout_ms":5000} },
  "playback": { "kind":"momentary","actions": {
    "play":{"command":"play"},"pause":{"command":"pause"},"stop":{"command":"stop"},
    "next":{"command":"next"},"previous":{"command":"previous"} } },
  "menu": { "kind":"momentary","actions": {
    "up":{"command":"up"},"down":{"command":"down"},"left":{"command":"left"},"right":{"command":"right"},
    "ok":{"command":"select"},"menu":{"command":"menu"},"home":{"command":"home"} } },
  "apps": { "kind":"momentary","actions": {
    "launch":{"command":"launch_app"},"list":{"command":"get_available_apps"} } },
  "pointer": { "kind":"momentary","actions": {
    "move":{"command":"pointer_gesture","param_map":{"dx":"deltaX","dy":"deltaY"}},
    "tap":{"command":"touch_at_position","param_map":{"x":"x","y":"y"}} } },
  "volume": { "kind":"momentary","actions": {
    "up":{"command":"volume_up"},"down":{"command":"volume_down"},"set":{"command":"set_volume","param_map":{"level":"level"}} } }
  // device-specific extras (outside canonical domains): screensaver, home_hold; refresh_status = internal query
}
```

## 17. Groups → capabilities & command exposure (Layer 3 / Step 0)

**Decided 2026-05-23.** How the legacy device-config `group` concept relates to the Layer-1
capability model, and how driver-supported-but-dormant commands are handled. Inputs for Layer 3
Step 0.

### 17.1 Judgement — capabilities subsume groups
The per-command `group` string and the capability **domain** are near-isomorphic vocabularies, but a
group is a *loose label* while a domain is a *typed contract* (domain + kind + native mapping +
feedback + gating). They collapse ~1:1: `power→power, inputs→input, volume→volume, menu→menu,
playback→playback, tracks→tracks, apps→apps, screen→screen, pointer→pointer`. `gestures` is **dead**
(no config uses it; both AppleTV swipe and LG-TV cursor use the `pointer` group → `pointer` domain).
`noops`/`media` are **orphan actions** with no domain (see 17.2).

Every job `group` does today is absorbed by capabilities:
- **UI zoning** → Layer 3 placement derives zones from **domains** (replaces group/action name-matching).
- **Scenario composition** → already capabilities (the reconciler), not groups.
- **WB control exposure + ordering** (`excluded_groups`, group-priority in `wb_device/service.py`) →
  re-keyed off `domain` + `kind` + the `exposed` flag (17.2).
- `/groups` API + `system.json` display names → redundant after Layer 3 (labels become manifest
  zone names).

**Verdict:** capabilities are the single model; **`group` becomes a transitional fallback** for any
command/device not yet capability-mapped, retired once coverage is complete (17.3/17.4). Not "groups
vs capabilities."

### 17.2 Command exposure & dormant commands (`exposed`)
`execute_action` today dispatches **any** command in the config registry (`base.py:748` — no
group/capability gate), so a command is HTTP-actionable even when hidden from UI/WB. To model
"driver supports it but it's parked":
- **`"exposed": false`** (default `true`) on the **config command**. A dormant command keeps its
  handler but is invisible on **all three** surfaces (UI/manifest, WB/MQTT, HTTP). Today's `noops`
  (`screensaver`, `home_hold`) + `media` (streamer `track_info`, testing unfinished) become
  `exposed: false`; the dead `gestures` group is deleted.
- **Load-time validation (RC4-style):** every config command must be **either `exposed: false` OR
  backed by an exposed capability `domain.action`** — anything else is a load error (kills the
  silent "forgot to map → goes dark" footgun).
- **New FastAPI gate:** `execute_action` rejects non-exposed actions (`403/404`). **Sequencing:**
  flip this gate **only after capability coverage is complete** (else it breaks un-mapped intended
  commands); the `exposed: false` tagging can land immediately.
- **Sequence sub-commands** (native commands used only inside a capability `sequence`/macro): mark
  `exposed: false` — the sequence still invokes them internally.

### 17.3 Capability-coverage targets (Step 0 precondition for retiring groups)
Retiring `group` requires ~100% capability coverage of in-scope commands. Gaps today:
- **Un-mapped in-scope A/V devices:** `streamer` (Auralic), `reel_to_reel` (Revox) — need maps.
- **Orphans:** `screensaver`, `home_hold`, `track_info` → `exposed: false`.
- **Deferred:** `kitchen_hood` (the ONLY `device_category=appliance`; Roborock will be the 2nd) —
  appliance bespoke pages are out of Layer-3-v1 scope, so its coverage can wait.

### 17.4 Sequencing
1. **Layer 3:** derive zones from **domains**; keep `group` as the fallback for un-mapped commands.
2. Tag dormant commands `exposed: false` now; author the missing maps (streamer, reel_to_reel).
3. **Once coverage = 100%:** flip the FastAPI exposure gate; re-key WB exposure/ordering off
   `domain`+`kind`+`exposed`; move display labels to manifest zone names; **delete `group` +
   `gestures`**. Fold the formal retirement into the post-all-phases doc reconciliation.
