# Research: Wiren Board native Yandex Alisa bridge (`wb-mqtt-alice`) — fit with this project

> **RETIRED 2026-07-15 (archived, owner decision).** The WB-native Alisa bridge is **not** the
> project's voice path — the shipped integration is the **Irene catalog contract** (bridge as the
> authoritative device catalog + canonical actuation backend; the decision is recorded where ADR
> 0005's voice half was verified-and-archived). This brief's own verdict pointed the same way:
> Alisa's capability model can't express the AV-heavy `pushbutton` device set, and the bridge is
> cloud-dependent (not LAN-only). Kept for historical reference; the parked "scenarios as
> voice-triggerable on/off" idea, if ever revisited, starts from git history, not from active scope.

**Status:** Research brief, 2026-05-23 (web-verified). **PARKED — do not act on this yet.** Revisit
only **after** the scenario migration is fully done, all devices are hardware-tested, and the house
works end-to-end ("everything works for my home"). At that point: decide on scenarios-as-`switch`
for voice + the cloud-dependency (LAN-only non-goal) question. Read-only investigation; no
code/config changed.

> ✅ **Verification update (2026-05-23) — web-confirmed.** The brief was first produced with web
> access denied; it has since been verified against primary sources in a follow-up main-thread run.
> The key WB-bridge claims are now **VERIFIED** — and they make the verdict *stronger*, not weaker:
> - **Supported Yandex capabilities: `on_off`, `color_setting`, `range`; properties: `float`,
>   `event`. NO `mode`** → AV **input/source selection is not expressible** today. (`toggle`
>   reportedly added in a recent GitHub release; not yet reflected on the wiki — would enable mute.)
> - **`pushbutton`-type MQTT controls CANNOT be used** — they lack the retained flag. This excludes
>   the bulk of our AV remotes (menu, D-pad, transport, IR `input_*`) outright.
> - **Manual per-device configurator, NOT auto-discovery** — "the client activates only when at
>   least one device is added via the web-UI configurator." So nothing is bridged "for free."
> - **Cloud-dependent** — client → Wiren Board gateway server → Yandex; a Yandex account + internet
>   are required (NOT LAN-only).
> - Sources: <https://github.com/wirenboard/wb-mqtt-alice>,
>   <https://wiki.wirenboard.com/wiki/Yandex-smart-home>, <https://wiki.wirenboard.com/wiki/Wb-2602>.
> The codebase-side analysis was already VERIFIED against this repo (file:line cites below). Still
> worth a later look: the exact WB-control-type→capability mapping table (the GitHub config schema)
> and whether `mode` / media device types arrive in a future `wb-mqtt-alice` version.

---

## (a) Executive summary + verdict

**What `wb-mqtt-alice` is (per seed, UNVERIFIED):** a Wiren Board–native cloud bridge that exposes
WB controller devices to **Yandex Alisa** ("Дом с Алисой"), shipped in firmware release **wb-2602**.
It is **Alisa-specific**, not a universal voice-assistant bridge. Topology: WB controller →
`wb-mqtt-alice` (on-controller client) → WB gateway server (cloud) → Yandex "Дом с Алисой" skill →
Alisa app/speakers. Bound via Yandex ID in the WB web UI (Интеграции → Яндекс Алиса); a hardware key
in the ATECCx08 secure element authenticates the controller.

**Verdict on "voice-controllable for free once they are WB virtual devices"
(the non-goal stated in `docs/project.md:84` and `docs/action_plan.md:316`):**

> **❌ The "for free" assumption does NOT hold for our AV-heavy device set, and is only
> *partially* true even for the simplest devices.** It should be downgraded from a stated fact to
> "voice control for simple on/off + range controls is plausibly low-effort; AV control (input/source
> selection, playback transport, IR pushbuttons, scenarios) is NOT free and is partly *not
> expressible* in Alisa today."

Two independent reasons, both robust to the Q1/Q2 uncertainty:

1. **Capability-shape mismatch (the deep reason).** Alisa's smart-home model is built around a small
   set of *semantic* capabilities (`on_off`, `range`, `toggle`, `mode`, `color_setting`) and
   *properties* (`float`, `event`) attached to typed devices. Our AV publication is dominated by
   **`pushbutton`** controls — every menu key, navigation key, playback transport key, every IR
   `input_*` button, and (because of how `_determine_wb_control_type_from_config` works) most
   power commands. A momentary pushbutton has **no clean Alisa capability**: Alisa wants *states*
   ("turn volume to 40", "switch input to HDMI2", "set mode to movie"), not *keypresses* ("press
   the right-arrow"). This is a modeling gap, not a config gap — no amount of auto-discovery fixes it.

2. **Either the bridge auto-discovers (and then mis-types our AV controls) OR it requires a manual
   per-control configurator (so it's literally not "free").** Q1 is unresolved, but **both branches
   defeat "for free":**
   - *If manual config:* you must hand-author an Alisa device/capability mapping per device — that is
     exactly the per-control effort "for free" denies.
   - *If auto-discovery:* it can only act on WB control *types* it understands (`switch`/`range`/maybe
     `rgb`/`value`). Our many `pushbutton` controls would be **silently dropped or rendered as
     meaningless toggles**, and a multi-input AV device exposed as a pile of momentary buttons does
     not become a usable Alisa "TV/receiver."

**Bottom line for planning:** treat Alisa voice control as a **deliberate, designed integration**,
not an automatic side-effect of WB virtual-device publication. The realistic near-term win is
**scenarios as voice-triggerable on/off devices** ("Алиса, включи кино") — see (e) — not granular
AV control by voice.

---

## (b) Bridge architecture + control-type→capability mapping

### Architecture (per seed dialog — **UNVERIFIED (needs primary source)**)

- Release: **wb-2602**; wiki page last edited ~2026-03-20. Source to verify:
  https://wiki.wirenboard.com/wiki/Wb-2602
- Service: **`wb-mqtt-alice`**, with sub-services `wb-mqtt-alice-config` and `wb-mqtt-alice-client`.
- Integration doc to verify: https://wiki.wirenboard.com/wiki/Yandex-smart-home (incl. a
  "Настройка устройств" / device-setup section) and the errata page
  https://wiki.wirenboard.com/wiki/Yandex-smart-home:_Errata
- **Most valuable primary source (could not be reached this session):** the GitHub repo
  **`github.com/wirenboard/wb-mqtt-alice`** — its README / CHANGELOG / **config JSON schema** is the
  authoritative control→capability mapping. *This is the single most important thing to fetch on a
  web-enabled run.*

### Q1 — auto-discovery vs manual mapping: **OPEN / UNVERIFIED**

The seed dialog does not state this conclusively, and it is the pivotal question. Three a-priori
possibilities; the GitHub config schema will disambiguate:
- **(i) Pure auto-discovery** of `/devices/<id>/...` MQTT controls into Alisa devices (least likely
  for AV — Alisa needs a *device type* and *capability semantics* that bare WB control types don't
  carry).
- **(ii) Configurator / explicit mapping** — a `wb-mqtt-alice-config` UI or JSON where you pick which
  WB device+control becomes which Alisa device + capability. The presence of a dedicated
  `wb-mqtt-alice-config` sub-service **strongly suggests this** (a pure auto-discoverer would not need
  a config service).
- **(iii) Hybrid** — auto-suggests from control types, manual override per capability.

**Working assumption (to confirm): (ii)/(iii) — there is a per-device/per-control mapping step.**
If so, the "for free" claim is already false on its face.

### Control-type → Alisa-capability mapping (**ALL ROWS UNVERIFIED — needs the GitHub schema**)

Reconstructed from the seed dialog + the Yandex capability model. Treat as a *hypothesis to verify*,
not as fact.

| WB MQTT control type | Plausible Alisa capability | Yandex spec name | Confidence | Notes |
|---|---|---|---|---|
| `switch` | on/off | `devices.capabilities.on_off` | seed says supported; **UNVERIFIED** | The one clean mapping. Our kitchen-hood light, mute-as-switch. |
| `range` | range (volume/brightness/level) | `devices.capabilities.range` | seed says supported; **UNVERIFIED** | Maps to numeric set ("set volume to 40"). Our `set_volume`, `set_speed`, brightness. |
| `value` (read-only sensor) | float property | `devices.properties.float` | seed says supported; **UNVERIFIED** | Read-only telemetry → an Alisa sensor property. |
| `rgb` | color | `devices.capabilities.color_setting` | seed says supported; **UNVERIFIED** | We emit no `rgb` controls today. |
| `pushbutton` | event property / toggle? | `devices.properties.event` and/or `toggle` | **UNCERTAIN / likely poor fit** | Momentary press has no native "set-state" capability. `toggle` (added v0.11.0, ~2026-05-20) gives a *binary* toggle, not a one-shot press. `event` property is read-*out* (button-was-pressed notifications), not command-*in*. **This is where our AV controls fall through.** |
| `text` | mode? | `devices.capabilities.mode` | **mode NOT confirmed in WB docs** | We emit `text` for `set_input`/`set_source`/`launch_app`. Alisa's input/source selection is `mode`. **If `wb-mqtt-alice` lacks `mode`, input/source by voice is impossible.** Verify against errata + CHANGELOG. |

**Q2 specifics to confirm against the GitHub repo / CHANGELOG / errata:**
- **`toggle`** — seed says **added in v0.11.0 (~2026-05-20)**. Verify version + that it maps to a WB
  control type we can emit. (Likely consumes a `switch`.)
- **`mode`** — seed says **NOT confirmed** in WB docs. **This is the critical gap for AV**: without
  `mode`, "switch the receiver to HDMI 2" / "switch TV input to Apple TV" cannot be voiced. Confirm
  yes/no explicitly.
- Whether `range` supports relative ("volume up") vs only absolute ("set volume to N").
- Whether `event` is command-in (we trigger) or notification-out (Alisa is told a button fired) — it
  is almost certainly **out** (a property, not a capability), which means `pushbutton` → `event`
  does **not** make our buttons voice-*triggerable*.

---

## (c) Alisa AV device-type capabilities (Yandex side)

**Source to verify (could not reach this session):**
https://yandex.ru/dev/dialogs/smart-home/doc/ru/concepts/device-types and the media subpages
(`device-type-media`, `device-type-media-tv`, `device-type-media-receiver`, `device-type-media-tv-box`).
The following is the **general, well-known shape** of the Yandex media device types — **treat as
UNVERIFIED in detail; confirm exact capability lists on the dev docs.**

Yandex media device types relevant to us:
- `devices.types.media_device` (generic media)
- `devices.types.media_device.tv` (TV)
- `devices.types.media_device.receiver` (AV receiver)
- `devices.types.media_device.tv_box` (set-top / streamer like Apple TV)

Capabilities these types typically expose (UNVERIFIED specifics):
- **Power** → `on_off` ✅ expressible.
- **Volume** → `range` (instance `volume`), absolute and/or relative ✅ expressible.
- **Mute** → `toggle` (instance `mute`) ✅ expressible (now that `toggle` exists, if WB maps it).
- **Channel** → `range` (instance `channel`) + `toggle`(instance `channel`) for up/down — TV-centric,
  not relevant to our HDMI-input world.
- **Input / source selection** → **`mode`** (instance `input_source`). ✅ expressible *to Alisa*, but
  **only if `wb-mqtt-alice` supports `mode`** — which the seed says is unconfirmed. **This is the
  pivotal AV gap.**
- **Pause/Play** → `toggle` (instance `pause`) — a *binary* pause/resume, **not** a full transport
  (no discrete stop, FF, rewind, next/previous, chapter, menu, D-pad).

**What AV control is NOT expressible in Alisa at all (regardless of the WB bridge):**
- **Transport beyond play/pause:** stop, fast-forward, rewind, next/previous track, skip — **no
  capability.** (Our `playback` group is mostly these.)
- **Navigation / menu / D-pad** (up/down/left/right/ok/back/home/exit) — **no capability.** (Our
  `menu` group.)
- **Pointer/gesture** (cursor move, touch, swipe) — **no capability.** (We already exclude these from
  MQTT anyway — see `service.py:172`.)
- **Arbitrary IR keypresses** (the `input_*` buttons on the MF amp, Revox transport) — no native
  representation beyond shoe-horning into `mode`/`toggle`.
- **App launching by name** as a first-class capability — at best a `mode` with custom instance, awkward.

So Alisa AV ≈ **power + volume + mute + (maybe) input-as-mode + (maybe) play/pause-as-toggle.**
Everything else on a real AV remote is out of scope for voice.

---

## (d) Per-device-class fit assessment + gaps (our 7 classes)

**Our publication model (VERIFIED):** `WBVirtualDeviceService` publishes each device as a WB virtual
device — device `/meta`, per-control `/meta` (`type`/`title`/`order`/`readonly`), a value topic, and a
`/on` command topic — gated by `enable_wb_emulation`
(`backend/src/wb_mqtt_bridge/infrastructure/wb_device/service.py:25-104`,
publish at `:326-388`). The **emitted WB control type** is decided by
`_determine_wb_control_type_from_config` (`service.py:431-459`):

- **Parameter-typed commands win first** (`service.py:497-522`): param `range`/`integer`/`float` →
  **`range`**; `boolean` → **`switch`**; `string` → **`text`**.
- **Parameterless commands fall to group rules** (`service.py:461-495`): `volume` setters → `range`,
  mute/unmute → `switch`; `power` → **`pushbutton`**; `playback`/`navigation`/`menu` → **`pushbutton`**;
  `inputs`/`apps` setter actions → `text`, else **`pushbutton`**.
- **Default: `pushbutton`** (`service.py:459`).
- UI-only groups `{pointer, gestures, noops, media}` emit **no MQTT control at all**
  (`service.py:172`, `:350`) — so they're invisible to any bridge.

Mapping each class to the closest Alisa media type and noting gaps (Alisa-side rows UNVERIFIED):

| Our class | Example config | WB types we emit | Closest Alisa type | Cleanly voiceable | Gaps / not expressible |
|---|---|---|---|---|---|
| **LgTv** | `lg_tv_living.json` | power=`pushbutton`; volume_up/down/mute=`pushbutton`/`switch`; `set_volume`=`range`; menu/playback=`pushbutton`; `set_input_source`/`launch_app`=`text` | `media_device.tv` | power(if exposed as switch), `set_volume`(range), mute | **Power is `pushbutton`, not `switch`** → no clean `on_off` without remodeling. All menu/D-pad/playback `pushbutton`s → none. Input via `text`→ needs `mode` (unconfirmed). App launch → no clean capability. |
| **EMotivaXMC2** | `emotiva_xmc2.json` | power_on/off=`range`(!! has `zone` integer param → param-type rule makes it **`range`**); `set_input`=`text`; `set_volume`=`range`; `mute_toggle`=`pushbutton`(parameterless w/ zone param→actually `range`) | `media_device.receiver` | `set_volume`(range) | **Power maps to `range` because of the `zone` integer param** (`service.py:515`) — semantically wrong for Alisa `on_off`. Input via `text` → needs `mode`. Dual-zone has no Alisa concept. mute_toggle mistyped. |
| **AppleTVDevice** | `appletv_living.json` | power=`pushbutton`; `set_volume`=`range`; playback/menu=`pushbutton`; `launch_app`=`text`; pointer/noops excluded | `media_device.tv_box` | `set_volume`(range) | Power `pushbutton`→ no `on_off`. play/pause/stop/next/prev all `pushbutton` → at best play/pause-as-`toggle` if remodeled. App launch → no clean capability. |
| **AuralicDevice** | `streamer.json` | power=`pushbutton`; `set_volume`=`range`; playback=`pushbutton`; mute=`pushbutton`; `set_input`=`text`; `media` group excluded | `media_device` (generic) | `set_volume`(range) | Power/playback/mute all `pushbutton`. Input via `text`→`mode`. Streamer has no natural Alisa type. |
| **BroadlinkKitchenHood** | `kitchen_hood.json` | **explicit `wb_controls`**: `set_light`=`switch`, `set_speed`=`range` (`kitchen_hood.json:55-69`) | **not media** — `devices.types.cooking.kettle`? more likely a generic `light`+`range` appliance, or `devices.types.other` | **light→`on_off` ✅, speed→`range` ✅** | **The ONE clean fit.** Both controls map to real Alisa capabilities. This is the only class that is genuinely "voice-controllable for nearly free." (Even so, the *device type* mapping needs deciding.) |
| **WirenboardIRDevice** | `mf_amplifier.json` | power=`pushbutton`; volume_up/down/mute=`pushbutton`; **every `input_*`=`pushbutton`** (parameterless, no setter verb → falls through to pushbutton, `service.py:489-494`) | `media_device.receiver` (aspirationally) | (almost nothing) | **Worst fit.** All controls are momentary IR `pushbutton`s. The 7 discrete `input_*` buttons can't become an Alisa `mode` without a different config shape (a single `set_input` with a string param + a custom map). No state feedback (IR is fire-and-forget / optimistic). |
| **RevoxA77ReelToReel** | `reel_to_reel.json` | play/stop/rewind_*=`pushbutton` (playback group) | `media_device` (poor) | none | **No fit.** Pure transport pushbuttons; Alisa has no FF/rewind/stop capability. Not a sensible Alisa device. |

**Cross-cutting gaps (VERIFIED about our side; Alisa side UNVERIFIED):**
1. **Power is usually a `pushbutton`, not a `switch`.** Alisa `on_off` wants a stateful switch. To make
   "Алиса, включи телевизор" work we'd need to publish a synthetic **`switch`** control backed by
   power_on/power_off (and ideally reflecting real power state), not two momentary buttons.
2. **eMotiva power becomes `range`** purely because the command carries a `zone` integer param — a
   concrete example of the param-type rule (`service.py:515`) producing an Alisa-hostile type.
3. **Input/source = `text`** in our model; Alisa needs **`mode`** (instance `input_source`). The WB
   bridge's `mode` support is **unconfirmed** and is the make-or-break for AV input control.
4. **IR `input_*` are discrete pushbuttons**, not a selectable mode — structurally wrong for `mode`.
5. **No transport, no menu/D-pad, no pointer** in Alisa — large parts of every AV remote are simply
   not voiceable, by Yandex's design.

---

## (e) Scenarios as voice triggers — recommendation

**Context (VERIFIED):** publishing scenarios as WB virtual devices is **currently disabled**
(`docs/action_plan.md:276-293` P4 #7; `docs/archive/architecture.md:122-128`; bootstrap no longer calls
`setup_wb_emulation_for_all_scenarios`). The disabled approach was *one WB device per scenario*
(`type=scenario`), which "clutters the WB device list" and "conflates a scenario with a device." The
infra still exists: `ScenarioWBAdapter` and `WBVirtualDeviceService.setup_wb_device_from_config(...)`
already accept `entity_id`/`entity_name` overrides to publish a scenario under its own WB id
(`service.py:31-32, 55-58`).

**Recommendation: YES — publishing scenarios for voice is the single highest-value Alisa win, and it
sidesteps every AV mapping gap above.** A scenario is an *activity* ("watch a movie"), which is
exactly the granularity Alisa handles well, and it only needs **one clean capability**.

**What a scenario needs to be voice-triggerable:**
- The cleanest, most portable mapping is a **WB `switch` control** per scenario (e.g. control
  `active` on the scenario's WB device), which the bridge can expose to Alisa as **`on_off`** on a
  `devices.types.other` (or a "scene"-like) device. "Алиса, включи кино" → switch on → activate;
  "выключи" → switch off → deactivate. `on_off` is the **one capability we already established maps
  cleanly** (a `switch`). **VERIFIED-on-our-side that we can emit a `switch`** (kitchen_hood proves
  it via explicit `wb_controls`); the Alisa side is the usual UNVERIFIED `switch`→`on_off`.
- A **Yandex "scenario/scene"** is a *different* Alisa concept (user-defined in the Alisa app,
  triggered by phrase). We likely **cannot** register Alisa-side scenes from the controller; what we
  *can* do is present each of our scenarios as an **`on_off` device** and let the user say
  "включи <name>". (Confirm against Yandex docs whether the WB skill surfaces anything scene-like.)

**Feed into the P4 #7 design decision (`action_plan.md:276-293`):** of the four options listed there,
**(b) a single "Scenario Manager" WB device with a selector + activate/deactivate** is the better fit
for the WB *UI*, but for **Alisa** the cleaner shape is one **`switch`-typed control per scenario**
(each becomes an independent voice-toggle "включи кино" / "включи музыку"). A single enum/selector
control is awkward for Alisa (it'd be a `mode`, which may be unsupported, and you can't say "включи
кино" against an enum value as naturally). **Suggested resolution:** option (b) for the WB device list
*plus* expose **one `switch` per scenario** (could be controls on the one manager device, or
lightweight per-scenario `on_off`) specifically for the Alisa surface. Decide the WB-UI clutter
tradeoff explicitly. This keeps scenarios out of the AV-mapping swamp entirely.

---

## (f) Concrete recommendations + open questions

### Recommendations for our publication approach
1. **Stop treating Alisa as "free."** Update the non-goal wording in `docs/project.md:79-86` and the
   backlog note in `docs/action_plan.md:316` to: *"Voice control is a designed integration via
   `wb-mqtt-alice`; only `switch`/`range` controls map cleanly. AV transport/menu/input and IR
   pushbuttons are largely not voice-expressible; scenarios-as-`switch` is the primary voice surface."*
2. **Prioritize scenarios-as-voice over per-device AV voice.** It's the high-value, low-mapping-risk
   path and it unblocks the disabled-publishing decision (P4 #7) with a concrete capability target
   (`switch`→`on_off`). See (e).
3. **If/when we want per-device voice, add synthetic stateful controls, don't voice the raw remote:**
   - A **`switch`-typed `power`** control per AV device (backed by power_on/off, reflecting real
     state) so `on_off` works — instead of the two momentary `pushbutton`s.
   - Reshape **input selection** to a single command with a constrained string param and a value list,
     and verify whether `wb-mqtt-alice` can turn `text`/enum into Alisa **`mode`**. If `mode` is
     unsupported, input-by-voice is dead until WB adds it.
   - Accept that **transport/menu/pointer stay UI-only** — never try to voice them.
4. **Do nothing irreversible yet.** Until the GitHub `wb-mqtt-alice` config schema is read, don't
   re-shape configs for Alisa — the right control types depend on whether the bridge auto-discovers or
   uses a configurator, and whether it supports `mode`.

### Open questions (must verify against primary sources — could not this session)
- **Q1 (pivotal):** Does `wb-mqtt-alice` **auto-discover** `/devices/<id>/...` controls, or require a
  **configurator** (`wb-mqtt-alice-config`)? → read the GitHub README + config schema.
- **Q2a (pivotal for AV):** Is **`mode`** supported? If no, input/source by voice is impossible. →
  CHANGELOG + errata.
- **Q2b:** What WB control type does **`toggle`** (v0.11.0) consume, and does it cover mute/play-pause?
- **Q2c:** Is **`range`** absolute-only or also relative (volume up/down)?
- **Q2d:** Is **`event`** strictly a read-out *property* (button-pressed notification) — confirming
  `pushbutton` is **not** voice-*triggerable* through it?
- **Q3:** Exact capability lists for `media_device{,.tv,.receiver,.tv_box}` on the Yandex dev docs —
  confirm play/pause-as-`toggle`, input-as-`mode`, and the absence of stop/FF/rewind/menu.
- **Q (scenarios):** Can the WB skill surface anything Alisa-*scene*-like, or are we limited to
  presenting scenarios as `on_off` devices?
- **Q (deps):** Does enabling `wb-mqtt-alice` require the cloud gateway + ATECCx08 key, i.e. does it
  break our **LAN-only / no-cloud** non-goal (`docs/project.md:81-85`)? It almost certainly introduces
  a **cloud dependency** — note this tension explicitly when deciding to adopt it.

### Primary sources to fetch on a web-enabled re-run (in priority order)
1. `github.com/wirenboard/wb-mqtt-alice` — README, CHANGELOG, **config JSON schema** (answers Q1, Q2).
2. https://wiki.wirenboard.com/wiki/Yandex-smart-home (+ "Настройка устройств") and
   https://wiki.wirenboard.com/wiki/Yandex-smart-home:_Errata
3. https://wiki.wirenboard.com/wiki/Wb-2602 (release confirmation).
4. https://yandex.ru/dev/dialogs/smart-home/doc/ru/concepts/device-types and the media subpages.
