# Project Vision — wb-mqtt-bridge

**Status:** current (2026-05-22). The intent behind the project — the part the code
can't tell you. For *how* it's built see [`architecture.md`](architecture.md); for the
UI↔backend seam see [`ui_backend_contract.md`](ui_backend_contract.md).

## Mission

Bridge devices Wirenboard doesn't natively support — A/V equipment and other
appliances — into Wirenboard's MQTT / virtual-device ecosystem, so each device is
**(a)** usable by Wirenboard's `wb-rules` automation engine alongside native WB
devices, and **(b)** controllable through the *appropriate* UI for its kind.

## Two faces, one idea

The unifying idea: **every foreign device becomes a first-class Wirenboard citizen.**
That shows up two ways:

### 1. Automation bridge (the `wb-rules` face)
Each device is exposed as a **WB virtual device over MQTT**, so the existing `wb-rules`
engine can orchestrate it next to native WB devices. Concrete example already in use: a
`wb-rule` on a light switch drives **kitchen lights + the kitchen-hood light** together
— the bridge is what makes the (non-WB) hood reachable from that rule.

### 2. Control UI (category-specific)
The UI a device gets depends on its `device_category`:

| Category | Examples | UI treatment |
|---|---|---|
| **A/V device** | TV, AVR, Apple TV, streamer, IR gear, tape deck | **Logitech-Harmony-style remote** — inherits Harmony's idea, behaviour, and visual appearance — plus one-touch **scenarios** (activities) |
| **Appliance** | kitchen hood, Roborock, … | **Individual, purpose-built pages** — explicitly *not* the remote layout |

Both categories are bridged to WB/MQTT for automation regardless of UI.

## Why it exists

- Bring **Harmony-style A/V control** (one-touch activities across many devices) into
  the Wirenboard environment.
- Make **WB-unsupported devices** (A/V gear, appliances) controllable by Wirenboard's
  automation, so the home's `wb-rules` logic can include them.

## Who it's for — trajectory

1. **Today:** built **for me alone** — single user, single home, LAN.
2. **Ultimate goal:** **household usage** — family members use the remote UI / automations
   in-room. ("Works for non-technical users" is an aspiration, not yet a requirement.)
3. **Later:** open it to the **Wirenboard community**, once it's done and stable.
   *(Open: what "productization" entails — to be defined.)*

## Goals & success criteria

**Primary success criterion: it actually works.** Every device action works, and every
scenario runs end-to-end on real hardware. The bar is functional completeness and
reliability, not more features.

Supporting goals:
- Native Wirenboard integration: virtual devices + `wb-rules` usability.
- Harmony-faithful A/V remote (idea, behaviour, appearance) + scenarios; iPad-portrait-first.
- Purpose-built UI pages for appliances.
- Reliable on constrained Wirenboard hardware.

## Current state (honest)

"Unfinished, but mostly works." Individual **device actions mostly work**; the
**scenario layer is currently broken** — closing that gap is the top *functional*
priority (see `action_plan.md`). Architecture, typing, tests, the OpenAPI contract, and
docs were hardened in 2026-05; the remaining work is functional correctness.

## Scope

- **Bounded — "done" = my house works.** The supported-device list *is* my house
  inventory, not an aspirational catalog; "supported" = "devices I own."
- **Shipping:** the 7 device drivers (LgTv, EMotivaXMC2, AppleTVDevice, AuralicDevice,
  BroadlinkKitchenHood, WirenboardIRDevice, RevoxA77ReelToReel), scenarios, rooms, WB
  virtual-device emulation, SSE.
- **Planned (devices I'm adding / features):** Roborock; Apple TV app launching;
  IR-learning page; appliance UI pages; contract-based button placement (#10).

### Non-goals (deliberately *not* doing)
- Not a general-purpose **Home Assistant** replacement.
- **No cloud** dependency — LAN-only.
- **No multi-home / multi-tenant.**
- **Voice control is not built here** — delegated to Wirenboard's future native Yandex
  Alisa bridge (devices become voice-controllable for free once they are WB virtual
  devices; the SprutHub stopgap was dropped 2026-05-20).
- Not an ever-growing platform — scope is bounded by the home.

## Constraints & hardware trajectory

- **Wirenboard-exclusive** deployment. **Today: Wirenboard 7 (ARMv7 / 32-bit)**, ~256 MB
  / 0.5 CPU. **Planned: Wirenboard 8+ (ARM64 / 64-bit).** No amd64 *deployment* target
  (amd64 is CI/dev only). → A future **arm64** image will be needed for WB8+.
- Docker + GitHub-Actions ARM build (one unified workflow builds both images); artifact deploy
  today (GHCR planned).
- **Monorepo** — `backend/` (FastAPI + MQTT), `ui/` (React/Vite), `wb-rules/`, `ops/`, `docs/` in
  one repo (consolidated 2026-05-22 from the former two repos); backend = data/functionality
  truth, UI = visual truth.
- Stack: Python 3.11 / FastAPI / aiomqtt (backend); React / TypeScript / Vite (UI).

## Design values

- **Strong typing end-to-end** (Pydantic configs + per-device state models).
- **Hexagonal architecture** (ports & adapters) for testability and swappable transports.
- **Contract-based coupling** (OpenAPI) over import coupling across the `backend/`↔`ui/` seam.
- **Deterministic, reproducible builds** (committed `openapi.json`; generated UI
  artifacts gitignored and built fresh).
- **Solo-dev pragmatism** — small focused commits, push to `main`, decisions tracked in
  `action_plan.md` + ADRs.
- **Docs that match reality** — no aspirational/stale documentation.

## Open questions

- What does opening to the **Wirenboard community** ("productization") actually entail?
- Timing/trigger for the **WB8+ / arm64** migration (and the arm64 build it requires).
