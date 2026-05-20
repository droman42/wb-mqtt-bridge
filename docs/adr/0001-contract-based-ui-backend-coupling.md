# ADR 0001 — Contract-based UI↔backend coupling; no Python in the UI build

- **Status:** Accepted
- **Date:** 2026-05-20

## Context

The `wb-mqtt-ui` build imported the backend as a Python package
(`pip install -e ./wb-mqtt-bridge`) and generated device-state TypeScript types by
spawning `python3` to `importlib`-import Pydantic classes and `ast.parse` them. This
forced Python + the backend package into the UI's Docker image and CI, and made a
backend rename **silently** break the UI build. The two repos are developed in lockstep
but were coupled by *imports*, not a *contract*.

## Decision

Couple the repos through the backend's **OpenAPI contract** instead of Python imports:

- The backend emits a committed `openapi.json` snapshot (via the new `wb-openapi` CLI)
  that carries both the REST surface and the device-state model schemas.
- The UI generates its types from that snapshot: REST types via `openapi-typescript`
  (`src/types/api.gen.ts`), device-state types by reading `components.schemas` in
  `src/lib/StateTypeGenerator.ts`.
- **Remove Python entirely from the UI build** (Dockerfile + CI). The UI still consumes
  a sibling `wb-mqtt-bridge` checkout for device configs + `openapi.json`, but never
  imports the package.

See [`../ui_backend_contract.md`](../ui_backend_contract.md) for the full contract.

## Consequences

- A backend rename now fails **loudly/visibly** (model missing from the contract) rather
  than silently; the contract is regenerated and committed deliberately.
- The UI image/CI are simpler and Python-free.
- New obligation: **regenerate + commit `openapi.json` when the API or a state model
  changes** (see ADR 0002 and the contract doc). Discovered during the work that the old
  Python path was, in fact, already dead in package/CI mode — so its removal had no
  runtime cost.

## Alternatives considered

- *Keep importing Python, just stabilize it* — rejected: keeps Python in the UI build and
  the silent-break failure mode.
- *Runtime-driven UI manifest (Codegen Option 2)* — deferred (see `action_plan.md` §7);
  larger refactor, can build on this contract later.
