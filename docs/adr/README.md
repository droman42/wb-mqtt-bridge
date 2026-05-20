# Architecture Decision Records (ADRs)

Short records of significant decisions: the context, the decision, and its
consequences. Newest decisions supersede older ones explicitly. These are the
authoritative "why" behind choices that the code alone doesn't explain — and the
`--ingest` material for planning tools.

| ADR | Title | Status |
|---|---|---|
| [0001](0001-contract-based-ui-backend-coupling.md) | Contract-based UI↔backend coupling; no Python in the UI build | Accepted |
| [0002](0002-openapi-additive-state-model-injection.md) | Expose device-state models via an additive `app.openapi()` override | Accepted |
| [0003](0003-backend-owns-device-state-mapping.md) | Backend owns `device-state-mapping.json` (directory-relative paths) | Accepted |
| [0004](0004-runtime-url-configuration.md) | Configure backend/MQTT URLs at container runtime, not build time | Accepted |
| [0005](0005-prune-miele-spruthub-delegate-voice.md) | Drop Miele and SprutHub; delegate voice to Wirenboard's Alisa bridge | Accepted |

Format: each ADR has **Context**, **Decision**, **Consequences**, and (where useful)
**Alternatives considered**.
