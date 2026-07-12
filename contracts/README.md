# locveil-bridge — contract registry

The direction-labeled index required by the Locveil contract convention
(`locveil-commons/process/contracts.md` §2). Every contract this repo OWNS and every
pin it CONSUMES, one line each; details live in the per-contract READMEs. Layout is
the uniform org shape: `contracts/<name>/` owned, `contracts/pins/<name>/` consumed.

## Owned

| Contract | Consumers | Version authority |
|---|---|---|
| [`catalog`](catalog/README.md) — the Irene ↔ bridge read contract: golden catalog + pinned OpenAPI schema | locveil-voice (pins into `locveil-commons/contracts/pins/catalog/`) | `catalog/STAMP.json` + tags `catalog-vN.M` (first: `catalog-v1.5`) |
| [`device-integration`](device-integration/README.md) — how Locveil-built devices integrate with the bridge: convention doc + descriptor schema | locveil-satellite (pins the convention, authors conforming descriptors) | `device-integration/STAMP.json` + tags `device-integration-vN` |

Cross-reference (a consumed process contract on the **block-pin lane**, not
relocated): the **scope kit** (`scope-vN`) — the pinned CLAUDE.md blocks and the
vendored `scripts/scope_guard.py`, enforced by the sha256 block rules in
`.scope-guard.toml`.

## Consumed (pins)

| Pin | Owner | Conformance guard |
|---|---|---|
| [`report-protocol`](pins/report-protocol/README.md) — the problem-report filing surface (labels, title prefix, report-id/bundle shape) | locveil-commons (tag `report-protocol-v1`) | `backend/tests/unit/test_report_protocol_pin.py` |

Layer-1 coherence (layout, stamps, pin hashes) is checked by the vendored
contract-guard; layer-2 conformance lives in the named tests above, inside the
normal backend suite.
