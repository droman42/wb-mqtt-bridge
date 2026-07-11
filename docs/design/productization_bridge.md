# Productization — the bridge's side of the Domovoy umbrella

**Status: FILED AT INTAKE 2026-07-08 (joint productization session, run from `~/development`
acting as both repos' Claude; voice-side BUILD-20). UNCOMMITTED per `cross-repo-source-of-truth`
— the maintainer verifies against live code and accepts; the proposed task IDs below are
confirmed or re-assigned at acceptance. Deliberately the LAST filing to use this uncommitted
mechanism — its replacement (board-as-outbox) is decision D-5 of the shared design.**

The shared spec — product name **Domovoy**, one commons repo, ownership regimes, cross-repo
discipline, release model — is `../locveil-commons/docs/design/productization.md` (D-1..D-12,
user-approved; the `problem_reports.md` precedent: shared spec in one home, this document
holds only what is the bridge's own). It migrates to `locveil-commons/docs/design/` once the
commons restructuring lands. This document records the bridge-side consequences.

## 1. What the shared design settles that the bridge relies on

- **D-2/D-3 — eval-commons becomes `locveil-commons`** (name executed as Locveil 2026-07-11) (rename + restructure; voice-side
  BUILD-21 executes, since voice co-develops the framework). Bridge impact: the `eval/`
  `file://` refs and `pip install -e ../locveil-commons/eval` paths need a one-time re-point at
  intake of that change. Ownership regimes are unchanged for the bridge: it remains the
  **generator** of the catalog/openapi contract artifacts, committed HERE in `contracts/`;
  the commons holds only the voice-managed pin. Nothing about `cross-repo-source-of-truth`
  moves.
- **D-4/D-5 — cross-repo ideas run as PROD design tasks in the commons board**, sessions run
  from the commons repo, and **the board entry is the outbox**: delegations to this ledger
  arrive as committed commons-board entries; this repo's session pulls them, verifies per
  `task-start-reconciliation`, files a local ID, and writes the ID back. Uncommitted sibling
  filings retire once the board exists.
- **D-10/D-11 — the ledger system stays** (no GitHub Projects/Jira); releases are
  per-component semver plus calver **suite compatibility manifests** ("Domovoy 2026.xx" =
  bridge vX + voice vY + contract vZ …) in the commons, gated on the eval cross-suites.
- **D-12 — the converged ops pattern becomes a normative spec** in `locveil-commons/process/`
  — largely codifying what this repo already does (the REL-2 layout is the reference pattern:
  runtime tree `/mnt/data/<name>-config`, sdcard clone update-time-only, boot depends on
  /mnt/data only, 127.0.0.1 healthchecks, start-period > fleet boot, GHCR pull-not-build,
  prune after pull).

## 2. Proposed bridge tasks (verify + accept, then normal discipline)

- **VWB-29** `[P2]` `[deferred]` — **Contract release tagging + artifacts** (shared design
  D-11; pairs with voice BUILD-24, which is gated on this). Today the contract artifacts
  (`contracts/openapi.json`, `catalog.golden.json`, `STAMP.json`, content-hash version) are
  committed and CI-drift-checked here, but a "contract release" is just a commit the voice
  side learns about through session notes. Scope: on a deliberate contract change, tag
  `contract-vN` (the existing `v1.4`-style contract version made an explicit tag series) and
  attach the artifacts to a GitHub Release, so the voice side's scripted re-pin
  (`make repin CONTRACT=vN`) + staleness gate have a machine-readable upstream. Decide at
  task start: tag-on-every-golden-change vs deliberate cuts (recommend deliberate cuts —
  additive = minor, breaking = major).
- **CORE-7** `[P2]` `[deferred]` — **Adopt the shared dynamic code loader from
  `locveil-commons/packages/core-py`** (shared design D-8; the user wants voice's loader
  pattern for the bridge — driver/module loading). Gated on the voice-side extraction design
  (their ARCH-42) + the core-py package existing. At task start: reconcile against the
  bridge's actual loading needs (device driver classes are wired via config `class` names
  today) and verify the extracted surface fits the hexagon (loader = infrastructure concern
  behind a port; `hexagonal-architecture` applies — no new cross-layer imports).
- **OPS-14** `[P2]` `[deferred]` — **Adopt the shared logging package from core-py, replacing
  the OPS-12 local implementation** (shared design D-8). OPS-12's scheme (startup rollover
  `service.log.<stamp>.log`, midnight rotation, 30-day prune) was hand-ported to voice as
  their BUG-30 — two copies of the same code by design review. Once extracted to commons
  (voice ARCH-43 designs the surface; this repo's requirements — the VWB-28 evidence glob
  compatibility — are input to that design), swap the local implementation for the package.
- **OPS-15** `[P2]` `[deferred]` — **Ops-spec conformance pass** (shared design D-12; the
  bridge-side sibling of voice BUILD-18-as-narrowed). Once the normative ops spec exists in
  `locveil-commons/process/`: walk `ops/` (update.sh shape, INSTALL.md structure, unit file,
  retention constants, naming) against the conformance checklist; fix dialects or record
  deliberate deviations in the spec. Expected to be mostly a no-op — the REL-2 layout is the
  spec's reference pattern — but the *naming/structure* dialects are real.
- **OPS-16** `[P2]` `[deferred]` — **Shared CLAUDE.md invariant blocks + drift guard —
  bridge-side adoption** (shared design D-12). Fence the shared invariants between markers,
  keep bridge-local ones outside, adopt the drift-guard script beside `check_scope.py` in the
  `ledger-guard` CI job, and take the same-slug renames (`config-master-canonical` means the
  OPPOSITE here vs voice — it splits into two differently-named invariants; drift inventory:
  shared design §2).

## 3. Recorded for the maintainer (not tasks)

- The stale cross-repo note is CLOSED: voice's re-pin to golden `8159b4b0068d1c63` has
  landed (`locveil-commons/contracts/STAMP.json` matches, bridge commit `7206902`) — the
  "voice must RE-PIN" line in the plan-status memory was corrected at this session.
- The satellite becomes a third product repo (`locveil-satellite`, voice BUILD-22) — no
  bridge work filed; if the satellite ever grows a bridge-facing surface, the bridge is the
  generator on that boundary per regime 1.
- Future PROD design worth anticipating: **Home Assistant support in parallel to Wirenboard**
  (shared design D-4's stress test) — expected shape: a new driven adapter behind the
  existing ports + at most a contract minor bump; if it demands voice-side changes, the
  contract leaked WB-specifics.
