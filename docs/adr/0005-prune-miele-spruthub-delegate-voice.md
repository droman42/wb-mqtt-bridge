# ADR 0005 — Drop Miele and SprutHub; delegate voice to Wirenboard's Alisa bridge

- **Status:** Accepted
- **Date:** 2026-05-20

## Context

Two integrations were carried as dead weight:

- **Miele** appliance support was declared (a `asyncmiele` dependency + doc/README
  mentions) but **never implemented** — no driver, config, or test ever existed, and
  repeated integration attempts against Miele appliances did not work.
- **SprutHub** was a stopgap to get scenarios/devices into **Yandex Alisa** voice control
  while waiting for Wirenboard to provide a native Alisa bridge.

## Decision

- **Remove Miele**: drop `asyncmiele` from `pyproject.toml`, regenerate `uv.lock`, and
  purge Miele from docs/README. (Roborock stays — it's a *planned* device, not a false
  claim.)
- **Drop SprutHub** and treat **voice control as out of scope for this project**. Rely on
  **Wirenboard's future native Yandex Alisa bridge**: because every foreign device is
  already exposed as a WB virtual device (the system's core job), those devices become
  voice-controllable for free once that bridge ships.

## Consequences

- Smaller dependency surface and honest docs/scope.
- No voice/Alisa code or SprutHub integration is maintained here; the related backlog
  items were retired.
- If Wirenboard never ships an Alisa bridge, voice would need to be reconsidered — an
  accepted risk, since SprutHub was unsatisfactory ("a nasty workaround").
