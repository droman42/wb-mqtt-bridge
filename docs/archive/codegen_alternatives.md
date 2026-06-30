# Codegen alternatives — decision record (archived)

**Status:** FROZEN. The analysis behind the UI device-page codegen decision, extracted verbatim
from `action_plan.md` §7 on 2026-06-30 (§5.2 #4). **The decision is settled and the codegen
pipeline this describes was deleted** at the Layer-3 Step-4 cutover (2026-05-24): Option 1 (kill the
Python-AST step — old P1 #3.5 / UI-4) shipped first, then Option 2 (backend-owned runtime layout
manifest — Layer 3) replaced build-time page codegen entirely. Canonical current doc:
`docs/design/ui_backend_contract.md` → "Layout Manifest & Runtime Rendering". Kept for the option
analysis + industry-pattern survey.

---

## 7. Codegen Alternatives (reference)

This section captures the analysis behind P1 #3.5 and the related Open Question. Keep it for context when revisiting the decision.

### 7.1 How the current device-page codegen actually works

The UI generates a React page per device at **build time**, producing static artifacts that are committed to git:

- 17 × `wb-mqtt-ui/src/pages/devices/{deviceId}.gen.tsx`
- 8 × `wb-mqtt-ui/src/types/generated/{StateClass}.state.ts`
- 1 × `wb-mqtt-ui/src/pages/devices/index.gen.ts` (router manifest)

The running UI **never regenerates them**. It fires actions via `POST /devices/{id}/action` and consumes state updates via SSE. The `.gen.tsx` files only describe the *shape* of each device's control panel (zones, buttons, groups), delegating rendering to a shared `RemoteControlLayout` component.

The generator (`wb-mqtt-ui/src/scripts/generate-device-pages.ts`, 802 lines) needs three inputs:

| # | Input | How it's obtained today | Coupling cost |
|---|---|---|---|
| **A** | Device config (commands, params, groups, names) | Reads `wb-mqtt-bridge/config/devices/*.json` from sibling checkout | Just a path. Cheap. |
| **B** | State model field info (name, type, optional, default) | Spawns `python` subprocess that does `importlib.import_module(...)` + `ast.parse(inspect.getsource(cls))` to walk Pydantic class fields | **The expensive coupling.** Requires `pip install -e ./wb-mqtt-bridge` in UI build, Python in the UI builder image, and breaks silently on backend rename. |
| **C** | Mapping: `DeviceClass → stateClassImport + configs` | `wb-mqtt-ui/config/device-state-mapping.json` (in the UI repo) | Hand-maintained; doesn't auto-sync with backend changes. |

The three `--mode=` flags only swap how input A is obtained (`api` hits a running backend, `local`/`package` read JSON from disk). They do not affect the Python coupling for input B.

### 7.2 What FastAPI exposes today vs. what codegen needs

Already in `/openapi.json`:
- `BaseDeviceConfig` (covers ~all of input A)
- `CommandResponse`, `GroupedActionsResponse`, `SystemInfo`, etc.

**Not** in `/openapi.json`:
- Device state models (`LgTvState`, `EmotivaXMC2State`, …) — the very classes codegen imports via Python. The `/devices/{id}/persisted_state` endpoint returns `Dict[str, Any]` instead of a typed state.
- Per-action parameter classes (`SetVolumeParams`, `MoveCursorParams`, …).

**Key leverage point:** typing one endpoint with a discriminated union of state models exposes every state class via OpenAPI automatically — ~10 lines on the backend.

### 7.3 Industry patterns

| Project | Pattern |
|---|---|
| Home Assistant | Backend sends schema-like dict per "config flow"; UI renders dynamically. Entities have a `domain` and the frontend has hardcoded "more-info" components per domain. Strong runtime introspection. |
| ioBroker | "JSON Config" schema spec; adapter ships a JSON file describing its admin UI. |
| openHAB | "Items" with types; UI auto-picks widgets per item type. Sitemaps = declarative UI DSL. |
| Node-RED | Nodes declare HTML template + edit dialog spec; editor renders dynamically. |

**Common thread:** a small set of well-known control primitives (switch, slider, select, button) keyed by device/entity type, with backend-owned schema served at runtime. **Almost nobody does build-time codegen of per-device React pages from server-side Python AST parsing.** We are an outlier here.

Of the JSON-Schema → form tools, only `react-jsonschema-form` (rjsf) has meaningful adoption in this neighborhood. Vendor-extension UI hints (`x-ui-*` in OpenAPI) have never standardized. For pure OpenAPI → TS types, `openapi-typescript` + `openapi-fetch` is the minimum-tax choice.

### 7.4 Four alternatives, ranked least → most disruptive

#### Option 1 — Keep build-time codegen, kill the Python AST step (**recommended; this is P1 #3.5**)

**Mechanism.** Type `/devices/{id}/persisted_state` with a discriminated union of state models so they land in `/openapi.json`. Rewrite `StateTypeGenerator.ts` to consume the OpenAPI schema. Remove Python + `pip install -e` from the UI Dockerfile.

**What dies.** Python AST parsing. `pip install -e ./wb-mqtt-bridge` in UI build. Python in the UI builder image. Silent break on rename.

**What survives.** Build-time codegen, `.gen.tsx` files, `RemoteControlLayout`, the mapping file (now derivable but can stay hand-maintained).

**Effort.** ~1 day, mostly UI-side.

**Tradeoff.** Backend still owns the schema; UI build needs an OpenAPI snapshot (fetched from a running backend at codegen time, or committed as `openapi.json`). Same operational shape as today, but the coupling is contract-based instead of import-based.

#### Option 2 — Backend ships a device-manifest endpoint; UI renders dynamically at runtime

**Mechanism.** `GET /devices/{id}/manifest` returns everything needed to render that device's page (metadata, command groups, parameter schemas, state shape as JSON Schema). UI ships a handful of generic primitives plus the `RemoteControlLayout` shell, fetches the manifest at page load, and renders.

**What dies.** The entire codegen pipeline. `gen:device-pages`. `device-state-mapping.json`. Python in UI build. The mapping problem.

**What survives.** `RemoteControlLayout`, the zone/group taxonomy from `docs/remote_layout.md`, action execution, SSE state stream.

**Effort.** ~2–3 days. Manifest endpoint is straightforward; the work is on the UI side (manifest-driven page renderer).

**Tradeoff.** One extra fetch per device page (invisible at this scale). Harder static typing (rendering from a runtime schema is `unknown`-shaped TypeScript). New devices on the backend appear in the UI on next refresh. Backend renames break loudly with a 404 at runtime, not silently at build time.

This is the industry-pattern answer. Recommended as a *follow-on* to Option 1, when/if we feel pain that justifies the refactor.

> **As-built (Layer 3, 2026-05-24).** This is the option we implemented — but the "harder static typing / `unknown`-shaped TS" tradeoff was **avoided**: the manifest is itself an `openapi.json` schema (`LayoutManifest`), so `api.gen.ts` types the renderer's input. Net effect: only `gen:device-pages` dies at cutover; the **REST type contract (`openapi.json` + `api.gen.ts`) survives and becomes more central**. Canonical scope = `ui_backend_contract.md` → "Step 4 — cutover (canonical scope)".

#### Option 3 — Reverse direction: backend owns codegen, UI consumes static manifests

**Mechanism.** Backend grows a CLI subcommand (`wb-bridge generate-manifests`) that walks configured devices and writes `manifests/{device_id}.json`. UI reads those JSON manifests at build time. No Python ever touches the UI build.

**What dies.** Python in the UI builder. The TypeScript-spawning-Python pattern.

**Tradeoff.** Manifests need to live somewhere both repos can reach (UI repo? backend repo published as releases? third "contract" repo?). Operationally awkward across two repos; rhymes with the broader mono-vs-multi-repo question. **Defer until the repo structure is decided.**

#### Option 4 — Drop codegen entirely, fully runtime, with rjsf for parameter dialogs

Like Option 2 plus `react-jsonschema-form` for command-parameter input dialogs. Most commands today are pushbuttons or simple ranges, so rjsf's automation doesn't pay off at our scale. **Skip.**

### 7.5 Recommendation

Adopt **Option 1 now** (P1 #3.5). Re-evaluate **Option 2** after Option 1 ships — once state models are in `/openapi.json`, Option 2 becomes a pure UI-side refactor with no further backend work. Keep **Option 3** in mind only if/when we move to a monorepo. **Skip Option 4** entirely.
