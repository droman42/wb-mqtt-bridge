# Requirements (PRDs)

Synthesized from classified PRDs: `docs/project.md` (vision/scope, precedence 2) and
`docs/action_plan.md` (roadmap, precedence 2). One requirement per entry; acceptance
criteria preserved. No competing acceptance variants were detected across the two PRDs —
project.md sets the goals, action_plan.md sequences the work, and they agree.

Note for downstream (gsd-roadmapper): action_plan.md items marked **DONE** are recorded
here as completed context, not open work. The open requirements are the un-checked /
TBD items.

---

## REQ-bridge-foreign-devices-to-wb

- **source:** docs/project.md
- **scope:** mission, automation bridge, virtual devices
- **description:** Bridge devices Wirenboard doesn't natively support (A/V equipment +
  appliances) into Wirenboard's MQTT / virtual-device ecosystem so each device is
  (a) usable by `wb-rules` automation alongside native WB devices and
  (b) controllable through the appropriate UI for its kind. Every foreign device becomes
  a first-class Wirenboard citizen, exposed as a WB virtual device over MQTT.
- **acceptance:** Each device action works and each scenario runs end-to-end on real
  hardware ("it actually works"). Bar is functional completeness + reliability, not more
  features.

## REQ-category-specific-control-ui

- **source:** docs/project.md
- **scope:** UI, device_category, remote layout, appliance pages
- **description:** UI per device is chosen by `device_category`: A/V devices
  (`device`) get a Logitech-Harmony-style remote (inherits Harmony's idea, behaviour,
  visual appearance) plus one-touch scenarios; appliances get individual purpose-built
  pages (explicitly NOT the remote layout). iPad-portrait-first.
- **acceptance:** Harmony-faithful A/V remote + scenarios; purpose-built pages for
  appliances; both categories bridged to WB/MQTT regardless of UI.

## REQ-fix-scenario-layer

- **source:** docs/action_plan.md (P0.5 #12), corroborated by docs/project.md ("scenario layer is currently broken")
- **scope:** scenarios, top functional priority
- **status:** OPEN — top functional priority
- **description:** Investigate and fix the scenario layer, currently broken (confirmed
  2026-05-20). Device actions mostly work; scenarios do not. Scope: reproduce failures,
  determine whether the cause is startup/shutdown sequencing, condition evaluation,
  role-action dispatch, WB-adapter, or state — then fix and verify on hardware.
- **acceptance:** Every scenario runs end-to-end on real Wirenboard hardware. This is
  the headline gap between today and "done = my house works".

## REQ-shipping-device-drivers

- **source:** docs/project.md, docs/architecture.md
- **scope:** device drivers, shipped inventory
- **description:** Ship the 7 device drivers (LgTv, EMotivaXMC2, AppleTVDevice,
  AuralicDevice, BroadlinkKitchenHood, WirenboardIRDevice, RevoxA77ReelToReel),
  scenarios, rooms, WB virtual-device emulation, SSE.
- **acceptance:** Each shipped driver's actions work on real hardware. Supported-device
  list is the home inventory ("supported" = "devices I own"), not an aspirational catalog.

## REQ-planned-features

- **source:** docs/project.md, docs/action_plan.md (§5.1 backlog)
- **scope:** planned devices/features
- **status:** OPEN — planned, not shipped
- **description:** Planned additions: Roborock; Apple TV app launching
  (`Запуск приложений на AppleTV`); IR-code learning page; appliance UI pages;
  contract-based button placement (action_plan #10); re-verify Revox reel-to-reel on
  hardware after the Wirenboard refactor.
- **acceptance:** Each item works on real hardware when implemented. (Miele dropped;
  SprutHub/voice delegated to WB Alisa bridge — see DEC-prune-miele-spruthub-delegate-voice.)

## REQ-contract-based-button-placement

- **source:** docs/action_plan.md (P2.5 #10), referenced by docs/ui_backend_contract.md invariant 4
- **scope:** UI, control placement, layout contract
- **status:** OPEN — design first, not yet scoped for implementation
- **description:** Replace the current implicit/undocumented within-zone control
  placement (slot zones by action-name substring matching; array-order zones by
  `config/devices/*.json` command key order) with an explicit placement contract.
  Candidate directions: (1) explicit per-action `slot`/`position`/`order` config fields;
  (2) a backend-owned layout manifest served/consumed as a contract; (3) command-level
  UI annotations (`x-ui-*`-style).
- **acceptance:** Placement is deterministic and reviewable; layout no longer depends on
  undocumented config-command ordering. Design agreed before implementation.

## REQ-ci-runs-tests-and-quality-gates

- **source:** docs/action_plan.md (P0 #2 DONE; rough edges #1, #2)
- **scope:** CI/CD, tests, lint/mypy
- **status:** PARTIAL — tests wired (DONE); lint/mypy in backend CI still open
- **description:** Run the test suite in CI (DONE: amd64, `pytest -m "not requires_device"`,
  225 pass / 0 skip / 0 fail). Remaining: backend CI has no lint/mypy/ruff; UI has
  typecheck/lint/validate but not `npm test` (jest preset misconfigured, no test files).
- **acceptance:** CI fails on test/type/lint regressions for the changed surface.

## REQ-ops-image-distribution

- **source:** docs/action_plan.md (P3 #7, #8)
- **scope:** Docker, GHCR, docker-compose, deployment
- **status:** OPEN — deferred (P3, optional/later)
- **description:** Push images to GHCR instead of ephemeral artifacts (removes GitHub-API
  + plaintext-PAT machinery in `manage_docker.sh`, gives durable image history); add a
  top-level `docker-compose.yml` wiring both GHCR images by service name (requires GHCR).
- **acceptance:** Deploys pull durable, versioned images; PAT-in-plaintext risk removed.

## REQ-arm64-image-for-wb8

- **source:** docs/project.md (constraints), docs/action_plan.md (out-of-scope note)
- **scope:** multi-arch build, Wirenboard 8+, arm64
- **status:** OPEN — time-limited out-of-scope; revisit when WB8+ migration is scheduled
- **description:** Today's deploy target is Wirenboard 7 (ARMv7/32-bit). Planned move to
  Wirenboard 8+ (ARM64/64-bit) will require an arm64 image alongside or replacing the
  ARMv7 one. amd64 stays CI/dev-only, not a deploy target.
- **acceptance:** An arm64 deployable image exists when WB8+ migration is scheduled.

## REQ-adopt-gsd-workflow

- **source:** docs/action_plan.md (P2.6 #11)
- **scope:** dev workflow, GSD, .planning bootstrap
- **status:** IN PROGRESS — Steps A/B/C done; Step D (install + map + ingest) in flight
- **description:** Adopt the get-shit-done workflow. Sequencing: (A) archive stale docs
  DONE; (B) fix living docs DONE; (C) author GSD-seed artifacts (PROJECT, ARCHITECTURE,
  CONTRACT, CONVENTIONS) + ADRs DONE; (D) install GSD, run map-codebase then ingest-docs
  to bootstrap `.planning/`. First real phase to tackle via GSD: fix broken scenarios
  (REQ-fix-scenario-layer).
- **acceptance:** `.planning/` bootstrapped; phase loop usable; decision on `.planning/`
  tracked vs gitignored made.

---

## Open questions carried from PRDs (not yet decided — downstream input)

- **source:** docs/action_plan.md §5, docs/project.md (Open questions)
- ARMv7/Wirenboard-exclusive vs an amd64 dev path? (affects test arch, GHCR tags, GSD)
- Is Wirenboard the only deployment target, or also a separate Linux box over MQTT?
  (affects urgency of runtime-URL items)
- Long-term one repo or two? (contract-based coupling makes either cheaper)
- Will `device_category` drive real behavior soon, and what differs device vs appliance?
- Move to runtime-driven UI rendering (Codegen Option 2)? (default: defer)
- How exactly to make button/action placement explicit (see REQ-contract-based-button-placement)?
- What does opening to the Wirenboard community ("productization") entail? (project.md)
- Timing/trigger for the WB8+/arm64 migration? (project.md)
