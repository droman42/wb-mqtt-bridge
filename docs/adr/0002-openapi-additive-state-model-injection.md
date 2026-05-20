# ADR 0002 — Expose device-state models via an additive `app.openapi()` override

- **Status:** Accepted
- **Date:** 2026-05-20
- **Relates to:** [ADR 0001](0001-contract-based-ui-backend-coupling.md)

## Context

For the UI to read device-state shapes from `openapi.json` (ADR 0001), the state models
(`LgTvState`, `EmotivaXMC2State`, …, `ScenarioWBConfig`) must appear in
`components.schemas`. They didn't: `/devices/{id}/persisted_state` returned
`Dict[str, Any]`, and `/devices/{id}/state` had no `response_model`. The obvious move —
typing those endpoints with a union/discriminated-union `response_model` — is risky:

- The endpoints return plain dicts (from the state store) or live instances; validating
  those through a union can **mis-coerce** to the wrong/most-permissive member.
- It would route serialization through FastAPI's response model, **bypassing the custom
  `model_dump` overrides** several state models rely on (enum→str, field completeness).

## Decision

Inject the state-model schemas **additively** via an `app.openapi()` override
(`bootstrap._install_openapi_with_state_models`): generate each model's JSON schema, lift
nested `$defs` (e.g. `LastCommand`) into `components.schemas`, and memoize. The set is the
explicit list `OPENAPI_EXTRA_MODELS`. **No endpoint's `response_model` or runtime
behavior changes.** A regression test (`tests/unit/test_openapi_schema.py`) asserts every
model is present.

## Consequences

- Zero runtime/serialization risk; custom `model_dump` overrides untouched.
- The models appear as standalone component schemas (no operation references them) — fine
  for `openapi-typescript` and for the UI's by-name lookup.
- New obligation: **adding/renaming a state model requires updating
  `OPENAPI_EXTRA_MODELS`** (the test enforces presence) and regenerating `openapi.json`.

## Alternatives considered

- *Discriminated union as `response_model`* — rejected: requires a `Literal` discriminator
  on every model (changes persisted shape) and breaks reading existing dicts.
- *Plain union as `response_model`* — rejected: smart-union coercion can pick the wrong
  member and bypasses `model_dump`.
