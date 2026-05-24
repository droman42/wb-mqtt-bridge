# Device Page Generation — RETIRED (Layer 3)

> **This document is obsolete.** The build-time device/scenario **page generator** described here was
> removed at the Layer-3 Step-4 cutover (`feat(layer3): A3 cutover — delete the build-time page
> generator`). There are no longer any `*.gen.tsx` pages, device handlers, or `gen:device-pages`
> script.

## What replaced it

Device and scenario pages now render at **runtime** from a backend-served **layout manifest**:

- `GET /devices/{id}/layout` and `GET /scenario/{id}/layout` return a `LayoutManifest`
  (a schema in `openapi.json`, typed in the UI as `LayoutManifest` from `src/types/api.gen.ts`).
- `src/lib/layoutManifestAdapter.ts` converts the manifest to `RemoteDeviceStructure`; icons are
  resolved UI-side by `src/lib/IconResolver.ts`.
- `src/components/RuntimeDevicePage.tsx` / `RuntimeScenarioPage.tsx` fetch the manifest and render it
  via the generic `src/components/RemoteControlLayout.tsx`. `App.tsx` routes every device/scenario
  there.
- **Appliances** (`device_category=appliance`, e.g. `kitchen_hood`) do not use the manifest — they
  have hand-written bespoke pages in `src/pages/appliances/` (registered in
  `src/pages/appliances/index.ts`).

The only remaining generator is `npm run gen:api-types` (`openapi.json` → `src/types/api.gen.ts`),
the REST type contract — see the UI `README.md`.

## Authoritative references

- `docs/ui_backend_contract.md` → "Layout Manifest & Runtime Rendering" — the design + the backend
  placement engine (`backend/.../presentation/api/layout_engine.py`).
- `docs/scenarios/scenario_system_redesign.md` — Layer 3 within the scenario redesign.
