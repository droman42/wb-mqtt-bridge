# UI

The UI consumes the backend through two contracts and nothing else. At **build
time** it generates TypeScript types from `backend/openapi.json` — no Python in the
build, no AST parsing of Pydantic classes. At **runtime** it fetches a
**layout manifest** per device or scenario and renders it through a single generic
component. Placement, ordering, parameters, icons — every visual decision is
data-driven; there is no hand-coded device page.

(Appliances are the deliberate exception — see the bottom of this page.)

## The two contracts

![UI architecture](../images/ui-architecture.png)

### Build-time — types, and only types

The UI build has one codegen step: `npm run gen:api-types` runs
`openapi-typescript` against `backend/openapi.json` to produce
`ui/src/types/api.gen.ts`. Every REST route and every DTO — including the
discriminated union of per-device state models that `_install_openapi_with_state_models`
injects into `/openapi.json` — lands in this one file. The UI imports its types
from `api.gen.ts` and from nothing else that originates on the backend.

This is what the rest of the architecture buys: no `pip install -e ./backend`
anywhere in the UI Dockerfile, no `python3 -c "ast.parse(...)"` subprocess, no
silent breakage when a Pydantic field is renamed. A backend type change either
shows up in the next `gen:api-types` run as a TypeScript diff or doesn't show up
at all (and then it's a backend bug — the model isn't reaching OpenAPI).

### Runtime — one fetch, one renderer

For every device and every scenario, the UI calls `GET /devices/{id}/layout`
or `GET /scenario/{id}/layout`. The backend's `layout_engine.py` composes a
`LayoutManifest` from the device's capability map, its config commands, and any
per-action `placement` hints; the response is typed in OpenAPI like every other
endpoint. The UI then:

1. Fetches the manifest in `RuntimeDevicePage.tsx` (or `RuntimeScenarioPage.tsx`).
2. Subscribes to `GET /events/devices` (or `/events/scenarios`) for live state.
3. Adapts the manifest via `layoutManifestAdapter.ts` into the
   `RemoteDeviceStructure` the renderer expects.
4. Renders through `RemoteControlLayout.tsx` — *the same component for every
   device*. No per-device React.

Add a new IR device, add an `inputs` value to its config — the next `/devices/{id}/layout`
response is what changes; the UI bundle does not.

## Two device categories, two UI shapes

`device_category` on a device config picks the UI shape:

| Category | Examples | UI |
|---|---|---|
| **`device`** | TV, AVR, Apple TV, streamer, IR fleet, reel-to-reel | **Harmony-style remote** — the layout manifest pattern above. |
| **`appliance`** | kitchen hood, future Roborock | **Hand-written bespoke page** in `ui/src/pages/appliances/`. The manifest endpoint is not consumed. |

The split is deliberate. A remote-style layout works for the canonical AV stack
(power, source, channel-up, volume, menu, transport, apps, pointer) — there's a
well-defined vocabulary, and a manifest captures it. An appliance has the
opposite problem: a kitchen hood is a few sliders and a light, a vacuum is a map
and a room picker, an oven is a temperature + timer + cycle. Forcing them through
the remote vocabulary would constrain expression; giving each its own page makes
it cheap to author one and ignore the others.

Today the **kitchen hood** is the only shipped appliance; the appliance page
slot (`ui/src/pages/appliances/`) and the `/appliance/:id` route are still in
design — see [the planned doc](../planned/appliance-pages.md).

## Anatomy of a layout manifest

![Layout manifest zones](../images/layout-manifest.png)

A manifest is a frozen Pydantic model (`presentation/api/layout_manifest.py`)
mirrored as a TypeScript type (camelCase JSON, snake_case in Python). At the
top it carries metadata — `entityKind` (`device` / `scenario`), `deviceCategory`,
`deviceClass`, `stateSchema` (the JSON-Schema fragment the UI uses to type
live-state payloads). Under that, **seven remote zones** plus a **scenario-only
bottom panel**. Each is optional.

### The seven remote zones

| Zone | Shape | What it renders |
|---|---|---|
| ① `power` | `PowerButtonConfig[]` (left / middle / right) | Up to three power buttons (`power-off`, `power-on`, `power-toggle`, `zone2-power`). |
| ② `media-stack` | `inputs` (Dropdown) + `playback` (actions row) + `tracks` (actions row) | Source selection + transport. Dropdown is "by-api" (populated from a `list` call like LG's `get_apps`) or "by-commands" (one command per option, IR-style). |
| ③ `screen` | Vertical button stack | Menu, home, back, info — the buttons that live to the left of the D-pad. |
| ④ `menu` | Nav cluster | The D-pad + OK. Always rendered, even if all five slots are empty (it anchors the layout visually). |
| ⑤ `volume` | `VolumeSliderConfig` + optional `mute_action` | Vertical slider reading the device state's `valueField`; zone-aware (XMC-2 main / zone2). |
| ⑥ `apps` | Dropdown | App launching (Apple TV / LG webOS). |
| ⑦ `pointer` | 2D pad | The LG TV Magic Remote pointer. |

### The bottom panel — `manualInstructions` (scenario only)

A scenario's remote often needs to surface authored notes that cannot be
automated: "set the Dodocus RCA hub to the LD position", "power the Sugden
phono pre on". These live in the scenario config and ride on the manifest as
`manualInstructions`:

| Field | Shape | Purpose |
|---|---|---|
| `manualInstructions.startup` | `string[]` | Notes shown when the scenario is offered / activated — checked off by the user. |
| `manualInstructions.shutdown` | `string[]` | Notes shown on deactivation. |

The UI renders them as a section beneath the seven zones. The field is omitted
on device manifests.

**Don't confuse this with the runtime `manual_steps`.** The reconciler also
emits `manual_steps` *at activation time* when the resolved topology path
crosses a manual node (e.g. the Dodocus RCA hub mapped to its `ld` position).
Those land in the `POST /scenario/start` response, not on the manifest, and
the UI surfaces them as a toast / prompt during the activation flow. The
`manualInstructions` panel is *static* (always visible when the scenario page
is open); `manual_steps` is *dynamic* (one-shot, per-activation).

### The atom — `ProcessedAction`

Every renderable button is a `ProcessedAction`:

- `actionName` and `displayName` (the latter localised per device language).
- `parameters` — typed slider min/max/step, range/string/integer/boolean types,
  defaults. Validated on the way out.
- `icon` — material-icon name + variant, with a fallback string; resolved
  UI-side by `IconResolver.ts`.
- `uiHints` — button size, style (`primary` / `secondary` / `destructive`),
  whether the action takes parameters (drives a popover).
- `params` — *fixed* native params the UI must always send (e.g. the XMC-2's
  `power_off` always carries `{zone: 1}`; `set_volume` always carries
  `{zone: 2}`).
- `sourceDeviceId` — used only on **scenario** manifests; it points the action
  at the *role device*, not the scenario itself (see below).

## Scenario manifests — same shape, different routing

`GET /scenario/{id}/layout` returns the same `LayoutManifest` type, composed from
the scenario's role devices. The `source` device contributes the input-dropdown
and transport actions; the `display` device contributes the screen and menu
zones; the `audio` device contributes the volume slider. Every `ProcessedAction`
on a scenario manifest carries a non-null `sourceDeviceId` — the UI dispatches
the action against that device, not against the scenario id, so "volume up the
active activity's audio" reaches the AVR even though the user pressed it on
the scenario page.

This is what makes scenario pages feel like one Harmony activity: it's a remote
for the *whole stack*, assembled from the right pieces of each participating
device's manifest.

## Live state — SSE, not polling

`RuntimeDevicePage` opens one SSE connection per page (`GET /events/devices`),
filters events by `device_id`, and updates the React state. The renderer reads
the live state for slider values (`valueField`), toggle highlights (`power`),
and dropdown selections (the catalog reflects the device's `state.input`). The
manifest itself is fetched once per page load — it does not change between
renders.

System events (`/events/system`) and scenario events (`/events/scenarios`) feed
the navbar and the global toast lane.

## Build, deploy, configure

The UI ships as a static React/Vite bundle served by nginx. Two contract files
travel with the build: `backend/openapi.json` (for types) and
`backend/config/device-state-mapping.json` (a tiny lookup used by the codegen).
The build resolves them from `../backend` when run from `ui/`, or from
`backend/` when run inside a Docker build context that's the repo root.

Runtime configuration is **injected at container start** — `envsubst` on
`nginx.conf.template` parameterises the backend network location; a small
`runtime-config.js` shim does the same for the browser→MQTT WebSocket URL. The
defaults preserve `192.168.110.250` so existing deploys are unchanged.

## Appliance pages — the deliberate exception

Appliances *do not* call `/devices/{id}/layout`; instead, they consume the
backend's plain device endpoints (`/config/device/{id}`, `/devices/{id}/action`,
`/devices/{id}/state`, `/events/devices`) and render through a hand-authored
page. The intended structure (still in design):

- One file per appliance under `ui/src/pages/appliances/<DeviceName>Page.tsx`.
- An `index.ts` registry mapping `device_class` → page component.
- A single `/appliance/:id` route that looks up the page from the registry.

See **[Planned: appliance pages](../planned/appliance-pages.md)** for the
intended shape — what exists today is the kitchen hood as a one-off.

## Where to go next

- **[Interfaces](interfaces.md)** — the REST + SSE endpoints the UI consumes.
- **[Devices and scenarios](devices-and-scenarios.md)** — how the capability
  map feeds the layout engine.
- **[Planned: device setup](../planned/device-setup.md)** — the not-yet-built
  device admin UI.
- **[Planned: appliance pages](../planned/appliance-pages.md)** — the
  appliance UI shape.
