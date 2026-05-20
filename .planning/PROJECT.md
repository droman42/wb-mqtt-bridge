# wb-mqtt-bridge (Wirenboard MQTT Bridge)

## What This Is

A Python/FastAPI async service that bridges devices Wirenboard doesn't natively
support — A/V gear (TVs, AVRs, Apple TV, streamers, IR equipment, a Revox tape deck)
and appliances (kitchen hood, Roborock) — into Wirenboard's MQTT / virtual-device
ecosystem. Each foreign device becomes a first-class WB virtual device, so it is both
(a) usable by Wirenboard's `wb-rules` automation alongside native WB devices and
(b) controllable through a category-appropriate UI (a Logitech-Harmony-style remote for
A/V; purpose-built pages for appliances). Built for one home; the supported-device list
*is* the author's house inventory.

## Core Value

**It actually works.** Every device action works and every scenario runs end-to-end on
real Wirenboard hardware. The bar is functional completeness and reliability — not more
features.

## Requirements

### Validated

<!-- Shipped and confirmed working through the 2026-05 hardening pass. -->

- ✓ Foreign devices bridged to WB virtual devices over MQTT — `wb-rules` can orchestrate them (e.g. a light switch driving kitchen lights + the non-WB kitchen hood)
- ✓ Seven device drivers ship with working per-device actions (LgTv, EMotivaXMC2, AppleTVDevice, AuralicDevice, BroadlinkKitchenHood, WirenboardIRDevice, RevoxA77ReelToReel)
- ✓ Category-specific UI: Harmony-style remote for A/V `device`, bespoke pages for `appliance` (driven by `device_category`)
- ✓ Contract-based UI↔backend coupling — UI generates types from committed `openapi.json`, no Python in the UI build (P1, ADRs 0001–0004)
- ✓ Runtime URL configuration — one image runs against any backend/broker via env vars (P1, ADR 0004)
- ✓ Backend owns `config/device-state-mapping.json` with directory-relative paths (P1, ADR 0003)
- ✓ Test suite repaired and wired into CI on amd64 — 225 pass / 0 skip / 0 fail (P2)
- ✓ Docs reconciled to reality; Miele and SprutHub pruned, voice delegated to WB's future Alisa bridge (P2, ADR 0005)

### Active

<!-- Open scope. Building toward these. Maps to roadmap phases. -->

- [ ] **DEP-01..03**: Put the build on a reproducible footing — immutable git pins, PyPI upper bounds, a documented recovery path if upstream disappears (Phase 1 — foundation, do first)
- [ ] **SCEN-01..04**: Fix the broken scenario layer so every scenario runs end-to-end on hardware (Phase 2 — top functional priority)
- [ ] **PLACE-01..02**: Design and adopt an explicit, contract-based button/action placement (Phase 3 — design first)
- [ ] **CI-01..02**: Add lint/mypy/ruff quality gates to backend CI; wire UI tests (Phase 4)
- [ ] **DEV-01..04**: Ship planned device features — Apple TV app launching, IR-code learning page, Revox hardware re-verify, Roborock + appliance pages (Phase 5)
- [ ] **OPS-01..02**: Distribute images via GHCR + a top-level docker-compose (Phase 6 — deferred)
- [ ] **ARCH-01**: Produce an arm64 deployable image for the WB8+ migration (Phase 7 — deferred, revisit at migration)

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- Home Assistant replacement — this is bounded to the home, not a general platform
- Cloud dependency — LAN-only by design
- Multi-home / multi-tenant — single home, single user (household usage is the aspiration, not multi-tenancy)
- Voice control built here — delegated to Wirenboard's future native Yandex Alisa bridge; foreign devices become voice-controllable for free once that ships (ADR 0005). Accepted risk: if WB never ships it, voice must be reconsidered
- Miele appliance support — repeated integration attempts failed; `asyncmiele` dropped (ADR 0005)
- SprutHub integration — was a voice stopgap; dropped (ADR 0005)
- amd64 as a deployment target — amd64 is CI/dev only; deployment is Wirenboard-exclusive
- Runtime-driven UI rendering (Codegen Option 2) — deferred until build-time codegen causes actual pain
- Multi-arch builds beyond the WB7→WB8 path — scope is bounded by the home's hardware

## Context

- **Hexagonal architecture** (ports & adapters): `domain/` (pure logic — DeviceManager, ScenarioManager, RoomManager, models), `infrastructure/` (drivers, MQTT client, SQLite store, config, WB emulation), `presentation/` (FastAPI routers, SSE, schemas), `app/` (wiring + lifespan), `cli/` (console tools). New external deps hide behind a port.
- **Ports**: `MessageBusPort` (MQTT), `DeviceBusPort` (drivers via `BaseDevice`), `StateRepositoryPort` (SQLite). Defined in `domain/ports.py`.
- **Strong typing end-to-end**: per-device Pydantic config (`BaseDeviceConfig`) + state model (`BaseDeviceState`). No dict-shaped configs/state. Every device JSON declares `device_class` + `config_class`.
- **The contract**: committed `openapi.json` (root) is the single source of truth for the REST surface AND device-state model shapes; UI codegen consumes it. `config/device-state-mapping.json` and `config/devices/*.json` are the other two contract artifacts. See `docs/ui_backend_contract.md`.
- **Two repos in lockstep**: `wb-mqtt-bridge` (backend, here) + `wb-mqtt-ui` (sibling). Backend-primary GSD setup; `.planning/` lives here. The UI build consumes a sibling backend checkout for configs + `openapi.json` but never imports Python.
- **Current honest state**: "unfinished, but mostly works." Device actions mostly work; **the scenario layer is broken** (confirmed 2026-05-20) — the headline gap to "done = my house works."
- **Known scenario-layer concerns** (from codebase audit): no scenario lifecycle state machine (`domain/scenarios/scenario.py`), no end-to-end scenario tests (the bug slipped through unit tests), circular-dependency risk device↔scenario, no scenario action rollback. These inform the Phase 2 fix.
- **Workflow**: solo dev, push directly to `main` on both repos, small focused commits with detailed bodies, no PR ceremony. Decisions tracked in `docs/action_plan.md` + `docs/adr/`. Adopting GSD (this bootstrap completes Step D).

## Constraints

- **Tech stack**: Python 3.11 / FastAPI / aiomqtt (backend); React / TypeScript / Vite (UI). Strong typing (Pydantic, mypy). black + isort, line length 88.
- **Runtime target**: Wirenboard 7 controller — ARMv7 / 32-bit Linux, ~256 MB RAM / 0.5 CPU, Docker, LAN. Performance and memory matter on constrained hardware.
- **Deployment**: Wirenboard-exclusive. amd64 is CI/dev only, never a deploy target. Docker + GitHub-Actions ARM build; artifact deploy today (GHCR planned).
- **Hardware trajectory**: WB8+ (ARM64 / 64-bit) migration planned later → will require an arm64 image then.
- **Compatibility**: cross-repo invariants must stay in sync (state models in `openapi.json`; `device_class` matching across config/mapping/UI handler; regenerate + commit `openapi.json` on API/state changes; command order in device configs is load-bearing for layout). See `CON-cross-repo-invariants`.
- **Dependencies at risk**: two git-pinned libs (`openhomedevice` branch, `pyatv` commit) can disappear; PyPI deps lack upper bounds.
- **Verification**: success is measured on real Wirenboard hardware, not just CI. Tests marked `requires_device` don't run in CI.

## Key Decisions

<!-- LOCKED ADRs (decisions.md DEC-*) + roadmap framing decisions. -->

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| **ADR 0001** — Contract-based UI↔backend coupling; no Python in the UI build | Import coupling broke silently on backend rename; OpenAPI contract makes renames fail loudly | ✓ LOCKED (P1 shipped) |
| **ADR 0002** — Expose device-state models via an additive `app.openapi()` override | Discriminated/plain unions as `response_model` change persisted shape / mis-coerce; additive injection touches no runtime behavior | ✓ LOCKED (P1 shipped) |
| **ADR 0003** — Backend owns `device-state-mapping.json` with directory-relative paths | One mapping file works in both local-sibling and CI/Docker layouts; backend owns its metadata | ✓ LOCKED (P1 shipped) |
| **ADR 0004** — Configure backend/MQTT URLs at container runtime, not build time | One image runs against any backend/broker via env vars; no rebuild per deployment | ✓ LOCKED (P1 shipped) |
| **ADR 0005** — Drop Miele + SprutHub; delegate voice to WB's Alisa bridge | Miele never worked; voice is free once devices are WB virtual devices | ✓ LOCKED (P2 shipped) |
| Harden dependencies before functional work | Two libs are pinned to a moving git branch / bare commit and PyPI deps lack upper bounds; a reproducible build is the foundation for everything after | — Pending (Phase 1) |
| Fix the scenario layer first (after dep hardening) | It's the #1 success criterion ("my house works") and the headline gap; device actions already mostly work | — Pending (Phase 2) |
| Design button-placement contract before implementing | User dislikes layout depending on undocumented config-command order; design must be agreed first | — Pending (Phase 3) |
| Record P1/P2 + test-CI work as completed context, not open phases | The hardening pass is done; the roadmap should only phase OPEN work | ✓ Applied here |

## Open Questions

<!-- Carried from PRDs — surfaced as decisions/risks, not invented scope. -->

These are unresolved and feed into the phases noted; they are NOT scope until decided:

- **Repo structure** (one repo vs two long-term) — contract-based coupling makes either cheaper; defer (touches Phase 6 ops)
- **Deploy target** (Wirenboard only, or also a separate Linux box over MQTT) — affects urgency of runtime-URL work
- **ARMv7-exclusive vs amd64 dev path** — affects test arch, GHCR tags
- **`device_category` behavior** — will it drive real behavior soon, and what differs between `device` and `appliance`? (touches Phase 3/5)
- **Runtime-driven UI rendering** (Codegen Option 2) — default: defer (related to Phase 3 placement contract)
- **Button/action placement mechanism** — explicit per-action fields vs backend layout manifest vs `x-ui-*` annotations (Phase 3 decides this)
- **Productization** — what opening to the Wirenboard community entails (long-term, undefined)
- **WB8+ / arm64 timing** — trigger for the migration and its arm64 build (Phase 7 is gated on this)

---
*Last updated: 2026-05-20 — inserted Phase 1 (Dependency Reproducibility Hardening) before the scenario fix; phases renumbered 2–7*
