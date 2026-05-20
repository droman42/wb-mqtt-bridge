# Decisions (ADRs)

Synthesized from classified ADRs. Each entry preserved separately; precedence
ADR=0 (highest), all LOCKED. No decision was auto-overridden. Status reflects the
ADR's own header.

---

## DEC-contract-based-ui-backend-coupling

- **source:** docs/adr/0001-contract-based-ui-backend-coupling.md
- **title:** ADR 0001 — Contract-based UI↔backend coupling; no Python in the UI build
- **status:** Accepted / LOCKED
- **precedence:** 0
- **scope:** UI build, backend coupling, OpenAPI contract, Python imports, device-state types, REST surface, Docker image, CI

**Decision.** Couple `wb-mqtt-ui` and `wb-mqtt-bridge` through the backend's OpenAPI
contract instead of Python imports:
- Backend emits a committed `openapi.json` snapshot via the `wb-openapi` CLI carrying
  both the REST surface and the device-state model schemas.
- UI generates types from that snapshot: REST types via `openapi-typescript`
  (`src/types/api.gen.ts`); device-state types by reading `components.schemas` in
  `src/lib/StateTypeGenerator.ts`.
- Remove Python entirely from the UI build (Dockerfile + CI). The UI still consumes a
  sibling `wb-mqtt-bridge` checkout for device configs + `openapi.json`, but never
  imports the package.

**Consequence / obligation.** Backend renames now fail loudly (model missing from
contract). New obligation: regenerate + commit `openapi.json` when the API or a state
model changes.

---

## DEC-openapi-additive-state-model-injection

- **source:** docs/adr/0002-openapi-additive-state-model-injection.md
- **title:** ADR 0002 — Expose device-state models via an additive `app.openapi()` override
- **status:** Accepted / LOCKED
- **precedence:** 0
- **relates-to:** DEC-contract-based-ui-backend-coupling (ADR 0001)
- **scope:** device-state, OpenAPI, FastAPI, response_model, schema injection, state models, OPENAPI_EXTRA_MODELS

**Decision.** Inject device-state-model schemas additively via an `app.openapi()`
override (`bootstrap._install_openapi_with_state_models`): generate each model's JSON
schema, lift nested `$defs` (e.g. `LastCommand`) into `components.schemas`, memoize.
The set is the explicit list `OPENAPI_EXTRA_MODELS`. No endpoint's `response_model` or
runtime behavior changes. Regression test `tests/unit/test_openapi_schema.py` asserts
every model is present.

**Rejected alternatives.** Discriminated union as `response_model` (changes persisted
shape, breaks reading existing dicts); plain union as `response_model` (smart-union
coercion picks wrong member, bypasses `model_dump`).

**Consequence / obligation.** Adding/renaming a state model requires updating
`OPENAPI_EXTRA_MODELS` and regenerating `openapi.json`.

---

## DEC-backend-owns-device-state-mapping

- **source:** docs/adr/0003-backend-owns-device-state-mapping.md
- **title:** ADR 0003 — Backend owns `device-state-mapping.json` (directory-relative paths)
- **status:** Accepted / LOCKED
- **precedence:** 0
- **scope:** device-state-mapping.json, backend repository, UI repository, device configuration, state model mapping, path resolution

**Decision.** Move `device-state-mapping.json` into the backend repo at
`config/device-state-mapping.json`. Make all paths inside it relative to the mapping
file's own directory (e.g. `devices/x.json`, `scenarios`); the UI's configuration
client resolves them, so the same file works in both layouts (local sibling and
CI/Docker). The `*.local.json` variant is retired.

**Consequence.** Backend owns its own metadata; one mapping file, no variants.
`stateClassImport` keeps the `module:ClassName` shape but only `ClassName` is used now
(looked up in `openapi.json`); the module path is vestigial.

---

## DEC-runtime-url-configuration

- **source:** docs/adr/0004-runtime-url-configuration.md
- **title:** ADR 0004 — Configure backend/MQTT URLs at container runtime, not build time
- **status:** Accepted / LOCKED
- **precedence:** 0
- **scope:** backend configuration, nginx, MQTT URL, container runtime, environment variables, docker-entrypoint, UI deployment

**Decision.** Resolve backend and MQTT URLs at container start:
- nginx config rendered from `nginx.conf.template` by `docker-entrypoint.sh` using
  `envsubst` scoped to `${BACKEND_HOST}` / `${BACKEND_PORT}`.
- MQTT URL written to `/runtime-config.js` (`window.RUNTIME_CONFIG.MQTT_URL`) by the
  entrypoint from the `MQTT_URL` env var, read by `src/config/runtime.ts`.
- Defaults preserve previous values; existing deployments behave identically with no
  env vars. `VITE_*` remain as local-`vite dev` fallback only.

**Consequence.** One image runs against any backend/broker via
`-e BACKEND_HOST/BACKEND_PORT/MQTT_URL`.

---

## DEC-prune-miele-spruthub-delegate-voice

- **source:** docs/adr/0005-prune-miele-spruthub-delegate-voice.md
- **title:** ADR 0005 — Drop Miele and SprutHub; delegate voice to Wirenboard's Alisa bridge
- **status:** Accepted / LOCKED
- **precedence:** 0
- **scope:** Miele appliance support, SprutHub integration, voice control, Yandex Alisa, Wirenboard, asyncmiele dependency, documentation and scope

**Decision.**
- Remove Miele: drop `asyncmiele` from `pyproject.toml`, regenerate `uv.lock`, purge
  Miele from docs/README. (Roborock stays — it is a planned device, not a false claim.)
- Drop SprutHub and treat voice control as out of scope for this project. Rely on
  Wirenboard's future native Yandex Alisa bridge: because every foreign device is
  already exposed as a WB virtual device, those devices become voice-controllable for
  free once that bridge ships.

**Accepted risk.** If Wirenboard never ships an Alisa bridge, voice would need to be
reconsidered.
