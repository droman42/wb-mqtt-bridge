# Archived documentation

These are **superseded** design specs and completed implementation/migration plans,
kept for historical reference only. **They do not describe the current code** and
should not be treated as guidance.

They predate major changes and still describe removed architecture — e.g. the
prompt-based generator (`/prompts`, `generate-pages.mjs`), `DevicePageTemplate` /
`UISection`, Python-in-the-build codegen (`pip install -e`, `importlib`/`ast.parse`),
and the old `stateFile`/`stateClass` mapping format. The codebase now generates
device-state types from the backend's `openapi.json` contract with no Python in the
build. For current behavior see the live docs under `docs/` and the repo `README.md`.

> Excluded from documentation ingestion / onboarding tooling on purpose.
