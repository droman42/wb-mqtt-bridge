# docs-manifest (INTERNAL)

The stamp for this repo's **docs manifest** — the machine-readable index of every
user-facing document, kept at [`docs/manifest.json`](../../docs/manifest.json) where it
lives with what it describes (the pointer pattern for owned surfaces homed elsewhere).

This is a **repo-internal** contract: no sibling repo pins it, so no git tag is cut.
`STAMP.json` names the schema version (`docs-manifest-v1`, bumped only when the schema
itself is reshaped); `manifest.schema.json` is a verbatim copy of the org-wide schema
owned by `locveil-commons` (`process/user-docs/manifest.schema.json`), kept here so the
coherence test runs without reaching across repositories.

Guard: `backend/tests/unit/test_docs_manifest.py` — validates the manifest against the
schema and keeps it bijective with the documentation tree. The org convention behind all
of this: `locveil-commons/process/user-docs.md`.
