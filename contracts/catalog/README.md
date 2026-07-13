# The catalog contract — the Irene ↔ bridge artifacts

This directory is the **contract of record** between the bridge and its non-UI
consumers — first among them the `locveil-voice` assistant (Irene). The bridge is the
*generator and source of truth*: artifacts are committed **here** and never pushed
into a sibling repository. The voice side pins its own copy (into
`locveil-commons/contracts/pins/catalog/`) — a one-way, outward, version-stamped sync.
The [registry one level up](../README.md) indexes every contract this repo owns or
consumes; the org-wide rules live in the Locveil contract convention
(`locveil-commons/process/contracts.md`).

## Versioning

The contract is versioned by **family-named git tags** `catalog-vN.M` together with
`STAMP.json` — since **`catalog-v1.5`**, the first tag, those two are the
machine-readable version authority: no contract version exists that is not in a
stamp. The earlier v1.1–v1.4 lineage predates tagging and lives on as the prose
"since contract vX" notes throughout this document — frozen history, not
retro-tagged. v1.5 itself changed no contract surface: it is the convention cut that
gave the family its layout, stamp core, and first tag. v1.6 (additive) rewrote the
OpenAPI field descriptions reader-first — no structural change, no golden change —
and the STAMP now enumerates the artifact set (`artifacts`) so a consumer's pin can
be checked for completeness. v1.7 (additive) renamed the backend import package to
`locveil_bridge`: the module-qualified names of the two `ManualInstructions` schema
variants in `openapi.json` changed prefix accordingly — a schema-name rename, no
field or structural change, and the golden catalog is byte-identical. Additive changes bump the
minor version, breaking changes the major; the version is carried in code as the
catalog projection's `CONTRACT_VERSION` constant and flows into the STAMP at
regeneration. The golden's *content hash* is *not* a version — it moves whenever the
house config changes, with zero contract change.

## Files

| File | What it is |
|---|---|
| `catalog.golden.json` | The golden catalog sample — the full house as `GET /system/catalog` serves it: rooms, devices (including the `global` aggregates and the per-room `scenario_manager_*` entities), capabilities with action **param descriptors** (typed `CatalogParam`: name/type/required/default/min/max/`unit`/`values`/`options_from` — the schema of record for param parsing) and `{wire, canonical, labels}` enum value tables. Generated offline and deterministically from `backend/config/` — same projection code path as the live endpoint. |
| `openapi.json` | The pinned API schema of record — carries `CatalogResponse`, the canonical action request/response shapes, and (since contract v1.4) the problem-report surface: `EvidenceEnvelope`, the shape `GET /reports/evidence` returns — the bridge-side evidence a voice-filed problem report embeds when the smart home is involved. Byte-identical to `backend/openapi.json` (the UI-consumed copy). |
| `STAMP.json` | The version stamp: the contract core (`contract`, `version`, `tag`, `date`, `owner_repo` — since contract v1.5) plus the build record — which bridge commit + version last generated these artifacts, and the golden's content-hash. The content-hash tracks *config* drift (Irene re-fetches when the retained `bridge/catalog/version` topic changes); the commit stamp tracks the *code build* the voice side coded against. Neither substitutes for the other. The commit named is the build the artifacts were generated **from** (i.e. the parent of the commit that lands them). |

## Regeneration

From `backend/`:

```bash
uv run locveil-catalog --stamp ../contracts/catalog/STAMP.json
uv run locveil-openapi -o openapi.json && cp openapi.json ../contracts/catalog/openapi.json
```

`locveil-catalog` builds the catalog **offline** — typed configs + capability maps +
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

## Realism check

The bridge runs on the WB7 controller, and its live catalog has been verified a
byte-for-byte match against `catalog.golden.json` — so the *deployed* bridge serves
exactly what the repo says (no deployment drift). To re-check at any time, dump the
live catalog and diff it against the golden:

```bash
curl -s http://<wb7>:8000/system/catalog | diff - catalog.golden.json
```

An empty diff means the deployed bridge and the committed contract agree.
