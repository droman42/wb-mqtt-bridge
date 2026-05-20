# Synthesis Summary

Entry point for `gsd-roadmapper`. Produced by `gsd-doc-synthesizer` from per-doc
classifications in `.planning/intel/classifications/`. Mode: **new** (net-new bootstrap;
no existing PROJECT/ROADMAP/REQUIREMENTS).

## Doc counts by type

- ADR: 5
- SPEC: 1
- PRD: 2
- DOC: 2
- Total: 10 (all high-confidence; all manifest type-overrides; 0 UNKNOWN/low-confidence)

Precedence applied: ADR(0) > SPEC(1) > PRD(2) > DOC(3) (per-doc integers from manifest).

## Decisions (LOCKED: 5 of 5)

All five ADRs are Accepted + LOCKED (precedence 0), orthogonal scopes, no contradictions:
- docs/adr/0001-contract-based-ui-backend-coupling.md
- docs/adr/0002-openapi-additive-state-model-injection.md
- docs/adr/0003-backend-owns-device-state-mapping.md
- docs/adr/0004-runtime-url-configuration.md
- docs/adr/0005-prune-miele-spruthub-delegate-voice.md

See `.planning/intel/decisions.md` (DEC-* entries).

## Requirements extracted (11 + carried open questions)

From docs/project.md (vision/scope) and docs/action_plan.md (roadmap):
- REQ-bridge-foreign-devices-to-wb
- REQ-category-specific-control-ui
- REQ-fix-scenario-layer  *(OPEN — top functional priority)*
- REQ-shipping-device-drivers
- REQ-planned-features  *(OPEN)*
- REQ-contract-based-button-placement  *(OPEN — design first)*
- REQ-ci-runs-tests-and-quality-gates  *(PARTIAL)*
- REQ-ops-image-distribution  *(OPEN — deferred P3)*
- REQ-arm64-image-for-wb8  *(OPEN — revisit at WB8+ migration)*
- REQ-adopt-gsd-workflow  *(IN PROGRESS — Step D)*

Plus 8 unresolved open questions carried from the PRDs (repo structure, deploy target,
device_category behavior, runtime-driven UI, productization, WB8+ timing, etc.).
See `.planning/intel/requirements.md`. Note: action_plan.md DONE items recorded as
completed context, not open work.

## Constraints (7; type breakdown)

From docs/ui_backend_contract.md (SPEC):
- api-contract: 2 (CON-contract-artifact-openapi-json, CON-runtime-rest-sse-mqtt)
- schema: 2 (CON-contract-artifact-device-state-mapping, CON-contract-artifact-device-configs)
- protocol: 2 (CON-build-time-codegen, CON-explicitly-not-in-contract)
- nfr: 1 (CON-cross-repo-invariants)

See `.planning/intel/constraints.md`. SPEC agrees with ADRs 0001–0004 (cross-linked).

## Context topics (13)

From docs/architecture.md and docs/conventions.md: system overview, hexagonal layering,
ports, device model, key flows, scenario system, configuration, bootstrap/lifecycle,
git/workflow conventions, formatting/typing/tests, adding-a-driver checklist, UI
conventions, docs conventions, project trajectory & non-goals.
See `.planning/intel/context.md`.

## Conflicts

- Blockers: 0
- Competing variants: 0
- Auto-resolved: 0
- Info: 4 (precedence chain applied with no overrides; SPEC restates ADRs in agreement;
  benign citation cycles; DONE items flagged as completed context)

Detail: `.planning/INGEST-CONFLICTS.md`

## Per-type intel files

- `.planning/intel/decisions.md` — ADR decisions (DEC-*)
- `.planning/intel/requirements.md` — PRD requirements (REQ-*) + open questions
- `.planning/intel/constraints.md` — SPEC constraints (CON-*)
- `.planning/intel/context.md` — DOC running notes by topic

## Status

READY — no blockers, no competing variants. Safe to route to gsd-roadmapper.
