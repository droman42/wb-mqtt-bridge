# The Irene ↔ bridge contract artifacts

This directory is the **contract of record** between the bridge and its non-UI
consumers — first among them the `wb-mqtt-voice` assistant (Irene). The bridge is the
*generator and source of truth*: artifacts are committed **here** and never pushed
into a sibling repository. The voice side pins its own copy (into
`eval-commons/contracts/`) — a one-way, outward, version-stamped sync.

## Files

| File | What it is |
|---|---|
| `catalog.golden.json` | The golden catalog sample — the full house as `GET /system/catalog` serves it: rooms, devices (including the `global` aggregates and the per-room `scenario_manager_*` entities), capabilities with action **param descriptors** (typed `CatalogParam`: name/type/required/default/min/max/`unit`/`values`/`options_from` — the schema of record for param parsing) and `{wire, canonical, labels}` enum value tables. Generated offline and deterministically from `backend/config/` — same projection code path as the live endpoint. |
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

## Param semantics (since contract v1.1)

- **`unit`** on a param is the semantic unit of the value (`°C`, `%`, `dB`, `min`) —
  what a voice consumer needs to parse «поставь двадцать два градуса» against a
  °C-shaped target. Constraints (min/max/type) always come from the same native spec
  the driver enforces.
- **`values`** carries the `{wire, canonical, labels}` table when the choice set is
  **bridge-known and static** (e.g. the scenario enum — labels are localized, ru/en).
  Since contract v1.3 this includes action params whose choice set lives on a
  same-named read-side field (the HVAC `set_mode(mode)` / `set_fan(fan)` family):
  the param mirrors the field's table, so «кондиционер на охлаждение» validates
  against the same triplets the state reads back. The canonical param name always
  equals the field name — that correspondence is the rule, not a coincidence.
- **`options_from`** marks an **intentionally open set**: the choices are
  runtime-dynamic (installed apps change with every install) and enumerable via
  `GET /devices/{id}/options/<options_from>`. A param carries *either* `values` *or*
  `options_from`, never both — an open set frozen into the golden would drift.
- **Selection capabilities advertise `set`** (since contract v1.2): a capability
  that switches between options (`input` on TVs, amps, streamers) carries a `set`
  action with one required `value` param. Devices with a **closed** option set (one
  native command per input) embed it as static `values` — the consumer can validate
  «переключи на CD» without a round-trip; devices with a **runtime** set carry
  `options_from: "inputs"` instead. Same rule as above: either/or, never both.
- **No empty capability husks:** a capability with neither invocable actions nor
  readable fields is suppressed from the catalog. (The TVs' `input` was the one case
  — it carries a real `set` since contract v1.2 and is back in the catalog.)

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
