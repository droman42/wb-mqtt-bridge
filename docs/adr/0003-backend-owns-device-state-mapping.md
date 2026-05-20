# ADR 0003 — Backend owns `device-state-mapping.json` (directory-relative paths)

- **Status:** Accepted
- **Date:** 2026-05-20

## Context

`device-state-mapping.json` (device class → state model + device config files) lived in
the **UI** repo, in two divergent variants: a package/CI form with `wb-mqtt-bridge/...`
path prefixes and a `*.local.json` with absolute paths. The file is metadata *about
backend models*; keeping it (and its backend paths) in the UI was historical accident,
and the dual variants were a maintenance hazard.

## Decision

Move the mapping into the **backend** repo at `config/device-state-mapping.json`. Make all
paths inside it **relative to the mapping file's own directory** (e.g. `devices/x.json`,
`scenarios`). The UI's configuration client resolves them against that directory, so the
**same file works in both layouts** (local sibling `../wb-mqtt-bridge/...` and CI/Docker
`./wb-mqtt-bridge/...`). The `*.local.json` variant is retired.

## Consequences

- The backend owns its own metadata; one mapping file, no variants.
- The UI build references `--mapping-file=wb-mqtt-bridge/config/device-state-mapping.json`
  and resolves config paths relative to it. The UI's duplicate mapping loaders were
  removed in favor of the shared, path-resolving client.
- `stateClassImport` keeps the `module:ClassName` shape, but only `ClassName` is used now
  (looked up in `openapi.json`); the module path is vestigial.
