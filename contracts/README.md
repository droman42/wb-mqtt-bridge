# The Irene ↔ bridge contract artifacts

This directory is the **contract of record** between the bridge and its non-UI
consumers — first among them the `wb-mqtt-voice` assistant (Irene). The bridge is the
*generator and source of truth*: artifacts are committed **here** and never pushed
into a sibling repository. The voice side pins its own copy (into
`eval-commons/contracts/`) — a one-way, outward, version-stamped sync.

## Files

| File | What it is |
|---|---|
| `catalog.golden.json` | The golden catalog sample — the full house as `GET /system/catalog` serves it: rooms, devices (including the `global` aggregates and the per-room `scenario_manager_*` entities), capabilities with action **param descriptors** (type/min/max/units, canonical names) and `{wire, canonical, labels}` enum value tables. Generated offline and deterministically from `backend/config/` — same projection code path as the live endpoint. |
| `openapi.json` | The pinned API schema of record — carries `CatalogResponse` and the canonical action request/response shapes under `components/schemas`. Byte-identical to `backend/openapi.json` (the UI-consumed copy). |
| `STAMP.json` | The build stamp: which bridge commit + version last generated these artifacts, and the golden's content-hash. The content-hash tracks *config* drift (Irene re-fetches when the retained `bridge/catalog/version` topic changes); the commit stamp tracks the *code build* the voice side coded against. Neither substitutes for the other. The commit named is the build the artifacts were generated **from** (i.e. the parent of the commit that lands them). |

## Regeneration

From `backend/`:

```bash
uv run wb-catalog -o ../contracts/catalog.golden.json --stamp ../contracts/STAMP.json
uv run wb-openapi -o openapi.json && cp openapi.json ../contracts/openapi.json
```

`wb-catalog` builds the catalog **offline** — typed configs + capability maps +
rooms + scenario definitions, no drivers, no network, no broker — so the dump is
deterministic (devices sorted by id; identical bytes across runs).

## Drift guard

`backend/tests/unit/test_contracts_golden.py` regenerates both artifacts inside the
normal backend test job and fails if the committed copies are stale — any config,
capability-map, or API change that alters the contract without a re-dump breaks CI
with the one-command fix above.

## Realism check (pending)

Once the bridge is deployed on the WB7 controller (the `ops/` compose cutover), a
live dump — `curl http://<wb7>:8000/system/catalog` — diffed against
`catalog.golden.json` verifies the *deployed* bridge serves what the repo says
(deployment drift, not config drift). Until the cutover, the golden alone is the
contract.
