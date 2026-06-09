# Layer 3 — fidelity oracle (frozen 2026-05-23)

Frozen snapshots of the **current build-time** `RemoteDeviceStructure` for each device, extracted
from the generated `ui/src/pages/devices/*.gen.tsx`. This is the **regression oracle for Layer 3
Step 1**: the backend layout manifest + placement engine must reproduce each device's zones +
controls, zone-by-zone, before the runtime renderer replaces the static page.

- One JSON per device, named by its **page id** — note a few differ from the config filename:
  `living_room_tv` = `lg_tv_living`, `children_room_tv` = `lg_tv_children`, `processor` =
  `emotiva_xmc2`.
- Produced by the **to-be-replaced** pipeline (config `group` + name-matching zone-detection). Do
  **not** hand-edit — regenerate via `npm run gen:device-pages` (from `ui/`) + `/tmp/extract_oracle.py`
  if configs change.
- `kitchen_hood` = appliance → empty remote zones (out of Layer-3-v1 scope; bespoke page later).
- `streamer` + `upscaler` currently show **group-derived power buttons**; reproducing them in the
  manifest requires their power capabilities — `streamer` power is pending the `on_value` widening,
  `upscaler` power uses `reconcile:false` (see `../layer3_step0_layout_analysis.md` §8).
