## Conflict Detection Report

Mode: new (net-new bootstrap; no existing PROJECT/ROADMAP/REQUIREMENTS to check against).
Inputs: 10 classified docs — 5 ADR (all LOCKED, precedence 0), 1 SPEC (precedence 1),
2 PRD (precedence 2), 2 DOC (precedence 3). All classifications high-confidence with
manifest type overrides; no UNKNOWN/low-confidence docs.

### BLOCKERS (0)

(none)

No LOCKED-vs-LOCKED ADR contradiction: the five locked ADRs address orthogonal scopes
(0001 UI↔backend coupling; 0002 OpenAPI additive injection; 0003 mapping ownership;
0004 runtime URLs; 0005 integration pruning) and do not contradict on any shared scope.
No UNKNOWN/low-confidence docs to re-tag. No synthesis-dependency cycle (see INFO below).

### WARNINGS (0)

(none)

No competing acceptance variants: the two PRDs are complementary, not overlapping.
  Found: docs/project.md states the vision/goals/scope; docs/action_plan.md sequences the
    work toward those goals.
  Found: both agree on the load-bearing facts — scenarios are broken and are the top
    functional priority (docs/project.md "scenario layer is currently broken";
    docs/action_plan.md P0.5 #12); Miele/SprutHub dropped and voice delegated to WB's
    Alisa bridge (both PRDs, consistent with docs/adr/0005-prune-miele-spruthub-delegate-voice.md);
    bounded "done = my house works" scope; WB8+/arm64 as future hardware.
  No requirement is defined twice with divergent acceptance criteria, so nothing was
  routed to competing-variants.

### INFO (4)

[INFO] Precedence chain applied, no overrides triggered
  Note: ordering ADR(0) > SPEC(1) > PRD(2) > DOC(3) per the manifest's per-doc precedence
    integers (sources: .planning/intel/ingest-manifest.yaml and each classification's
    `precedence` field). No content contradiction crossed a precedence boundary, so no
    auto-resolution was needed — nothing was overridden or dropped.

[INFO] SPEC restates ADR decisions; ADRs remain source of record
  Note: docs/ui_backend_contract.md (SPEC) describes the same mechanisms decided in the
    ADRs — `_install_openapi_with_state_models` / `OPENAPI_EXTRA_MODELS`
    (docs/adr/0002-openapi-additive-state-model-injection.md), directory-relative
    `device-state-mapping.json` (docs/adr/0003-backend-owns-device-state-mapping.md),
    runtime `BACKEND_HOST`/`BACKEND_PORT`/`MQTT_URL`
    (docs/adr/0004-runtime-url-configuration.md), and contract-not-import coupling
    (docs/adr/0001-contract-based-ui-backend-coupling.md). The SPEC agrees with each ADR
    (no contradiction), so these are recorded as agreement, not auto-resolved overrides.
    Synthesized constraints in .planning/intel/constraints.md cross-link to the owning ADR.

[INFO] Benign citation cycles in the cross-ref graph (not synthesis-dependency cycles)
  Found: mutual "see also"/"relates-to" references form citation loops —
    docs/adr/0001 <-> docs/adr/0002; docs/architecture.md <-> docs/conventions.md;
    docs/project.md <-> docs/action_plan.md; docs/architecture.md <-> docs/action_plan.md;
    docs/conventions.md <-> docs/action_plan.md; docs/ui_backend_contract.md <-> docs/action_plan.md.
  Note: these are bidirectional documentation citations, not dependency edges that drive
    synthesis. Synthesis here is type-bucketed extraction (each source is read once and
    emitted to its type file); it does not recursively traverse refs, so these cycles
    cannot produce synthesis loops. Max traversal depth well under the 50 cap. Not gated.

[INFO] action_plan.md items marked DONE recorded as completed context
  Note: docs/action_plan.md mixes shipped work (P0/P1/P2, many "DONE") with open work
    (P0.5 #12 scenarios, P2.5 #10 placement, P3 ops, arm64, GSD Step D). Synthesized
    requirements in .planning/intel/requirements.md flag status (OPEN / PARTIAL /
    IN PROGRESS / completed-context) so the roadmapper does not re-plan finished work.
