# Ledger-format convergence — design

- **Status:** DESIGN — agreed 2026-06-30. Deliverable of plan task **§5.2 #1** (the design gate).
  Records the target ledger format + a complete migration mapping; **no re-ID executed yet** — that
  is §5.2 #5 (re-scoped below), gated on review of this doc.
- **Scope:** `docs/action_plan.md` + `docs/action_plan_DONE.md` + `docs/action_plan_journal.md`
  (the bridge's ledger), and the CLAUDE.md invariants that reference them. No code.
- **Why:** two 2026-06-30 analyses (chat-requested) — (1) this plan's positional `P0…P4 / #n / §5.1`
  numbering vs the sister repo's workstream-serial ledger (`../wb-mqtt-voice/docs/RELEASE_PLAN.md` +
  frozen `RELEASE_PLAN_DONE.md` + `scripts/check_scope.py`), and (2) the scenario/Layer-3 design docs
  that doubled as ledgers — both surfaced the same defect: the ledger's *identity* scheme is
  positional, so IDs encode priority/order and **renumber** when tasks move (this plan renumbered
  `#22→#23` on 2026-06-07 while CLAUDE.md says "reference by name, never number"), and the same `#n`
  is reused across sections (`#7`/`#8` exist in **both** P3 **and** §5.1 **and** P4 **and** §5.2 —
  four live collisions). The divergence from voice is *historical* (this plan began as an analysis
  report; voice's began as a release ledger), not deliberate; CLAUDE.md is already mirrored between
  the repos, so converging the ledger finishes a convergence that is most of the way done at the
  governance layer.

---

## 1. Decisions

### D1 — Identity is a stable workstream-prefixed serial

Every task gets one ID of the form **`PREFIX-N`** (e.g. `DRV-1`, `SCN-3`, `VWB-7`):

- **`PREFIX`** = the workstream (a stable *subsystem* bucket — §2). It never changes for a task.
- **`N`** = a monotonic serial within that workstream, **assigned once, never reused, never
  renumbered.** Adding/removing/reordering tasks does not touch any existing ID. A retired/folded
  task keeps its number forever (the number is a tombstone, like voice's gaps).
- The ID carries **no priority and no ordering meaning** — those are separate axes (D3, D4).

This is voice's scheme (`ARCH-8`, `QUAL-29`) with a bridge-native bucket vocabulary (§2). It is the
direct fix for the renumber-churn and the cross-section `#n` collisions, and it satisfies CLAUDE.md's
"reference by stable name, never by number" principle *inside* the ledger that principle governs.

### D2 — Buckets are subsystem-shaped (decided 2026-06-30)

The bridge is a device-integration project; its work clusters by **where it physically lives**, not
by kind-of-work (voice buckets by kind — ARCH/QUAL/BUG — because voice ran a big code-quality wave).
So the bridge buckets by subsystem. Full taxonomy in §2. **One addition beyond the six picked
2026-06-30: a `CORE` bucket** for cross-cutting backend work that belongs to no single subsystem
(the system-router adapter cleanup; the acceptance-gate dead-code sweep). Without it those tasks have
no honest home. **Confirmed 2026-06-30.** Expected to stay **thin** — the hexagonal architecture is
already in place and **enforced** (import-pure `domain/` since 2026-05-25; import-linter contracts
gate every commit — the standing LAW), so layering is an *invariant*, not a task source. CORE is the
not-mis-filing bucket, not evidence of a core backlog.

### D3 — Priority is a separate inline tag, not part of the ID

`P0` / `P1` / `P2` as an inline tag on the task line (voice's convention). The old `P0…P4` *bands*
are dissolved — they conflated priority, sequencing, **and** identity into one positional token.
Sequencing that genuinely matters (dependencies, "do X before Y") is expressed by an explicit
`blocks:`/`after:` note on the task, not by ID order.

### D4 — Milestone tags map the bridge's "done" to voice's `[release]`/`[deferred]`

Voice tags every task `[release]` (in the release gate) or `[deferred]`. The bridge's equivalent
milestone is its stated done-criterion — **"everything works in my home"** (the P4 final-acceptance
gate). So:

- **`[house]`** — required for the house-works milestone (the bridge's release gate).
- **`[later]`** — real but post-milestone; nice-to-have / backlog.
- **`[parked]`** — explicitly dormant, do not pull in without reactivation (e.g. the ESP32 scaffold).

The gate becomes: *every `[house]` task is `[x]`*. **Confirmed 2026-06-30** (`[house]`/`[later]`/
`[parked]`; semantics mirror voice 1:1).

### D5 — Status legend (mirrors voice + one bridge-specific marker)

`- [ ]` open · `- [x]` done · `- [~]` partial/paused. Inline annotations, with reason:
`DOING` · `BLOCKED <why>` · `DEFERRED` · `PARKED` · **`HW-GATED <what>`** (bridge-specific — a large
share of bridge work is gated on the user at the rack; making it a first-class marker stops
"HW-pending" from reading as "stalled"). Status lives **only** in the active plan; the DONE file and
the journal never assert status (CLAUDE.md `one-active-journal`).

### D6 — Two-file split, now organized by workstream

`action_plan.md` = **open + partial** tasks only; `action_plan_DONE.md` = completed, **by
workstream** (not by phase — the initial 2026-06-30 split was by P-phase as a stopgap; #5 reorganizes
it by workstream). One ledger, **every ID in exactly one file**; a task *moves* active→done on
completion (same change as its journal entry). This codifies what §5.2 #2 began.

---

## 2. Workstream taxonomy

| Prefix | Workstream | Scope |
|---|---|---|
| **DRV** | Device drivers | The 7 driver classes + the WB-passthrough driver; per-driver HW verification; driver-level features (IR learning, force flag, audio-output rework); IR ROM tooling; ESP32 transport-bridge firmware. |
| **SCN** | Scenarios / topology / reconciler | The Harmony-model scenario engine (Layers 0/1/2/R), topology, capability maps, manual-notes, the scenario↔WB rebuild. |
| **VWB** | Voice-integration + native WB onboarding | The P3.7 push: canonical endpoint, catalog, WB-passthrough onboarding, aggregate devices, value-label layer — the bridge-as-house-catalog work + the Irene contract. |
| **UI** | config-ui | The React UI, the OpenAPI/contract codegen seam, Layer-3 runtime rendering consumption, build-toolchain (vite). |
| **OPS** | Docker / CI-CD / deploy / ops | Image build + GHCR, compose/systemd, lifecycle/shutdown robustness, dependency refresh, the monorepo decision. |
| **CORE** | Backend core / architecture *(confirmed 2026-06-30)* | Cross-cutting backend work with no single subsystem home — the system-router adapter cleanup and the acceptance-gate dead-code sweep. **Expected to stay a thin bucket:** the hexagonal architecture is already in place and **enforced** (import-pure `domain/` since 2026-05-25, import-linter contracts gate every commit — the standing LAW), so layering is an *invariant*, not a task source. CORE exists so the rare genuinely-cross-cutting backend task isn't mis-filed, not because a backlog of core work is expected. |
| **DOC** | Docs / ledger / process | User-facing + design docs, the action-plan/ledger itself, the scope-drift guard, this convergence. |

**Not workstream tasks (kept as a gate, not dissolved into IDs):** the **P4 "Final acceptance &
cleanup"** checklist is the bridge's *Definition-of-done gate* (analogous to voice's
"Definition of release"), not units of work. Its cross-cutting completion criteria (all devices
migrated, all scenarios migrated, UI works everywhere, dead-code sweep, HW re-verify) stay as a
**`## Acceptance gate`** section that *references* the `[house]` workstream tasks. The two P4 items
that ARE real work-units re-ID into their workstreams (P4 #6 → `OPS`, P4 #7 → `SCN`).

---

## 3. Migration mapping (old → new) — the reviewable artifact for #5

Complete map of every existing task. Borderline bucket calls flagged `(±)`. Serials are assigned
roughly chronologically within each workstream (done/earliest first).

### Completed (currently in `action_plan_DONE.md`, by P-phase → re-home by workstream)

| Old | New | Task | Status |
|---|---|---|---|
| P0 #0a | **UI-1** | Ship appliance-category UI feature | `[x]` |
| P0 #0b | **OPS-1** | Delete stale branches | `[x]` |
| P0 #1 | **UI-2** (±CORE) | Backend half of the appliance feature | `[x]` |
| P0 #2 | **OPS-2** | Wire tests into CI (amd64; gate ARM) | `[x]` |
| P0.5 #12 | **SCN-1** | Scenario layer rebuild (Harmony/reconciler) | `[x]` |
| P1 #3 | **UI-3** | Generate OpenAPI types for the UI | `[x]` |
| P1 #3.5 | **UI-4** | Kill the Python-AST coupling in UI codegen | `[x]` |
| P1 #4 | **UI-5** | Parameterize nginx + MQTT URLs | `[x]` |
| P1 #4.5 | **UI-6** | Move `device-state-mapping.json` to backend | `[x]` |
| P2 #5 | **DOC-1** | Archive `TODO.md` → history | `[x]` |
| P2 #6 | **DOC-2** | Doc-accuracy pass | `[x]` |
| P2.5 #10 | **UI-7** | Placement contract (→ Layer-3 manifest) | `[x]` |
| P2.6 #11 | **DOC-3** | GSD workflow (adopted then dropped) | `[x]` |
| P3 #7 | **OPS-3** | GHCR image push | `[x]` |
| P3 #8 | **OPS-4** | compose / systemd / update.sh | `[x]` |
| P3 #9 | **OPS-5** | Monorepo decision (Phase 2) | `[x]` |

### In-flight — P3.7 (all → VWB)

| Old | New | Task | Status |
|---|---|---|---|
| §P3.7 #13 | **VWB-1** | Generic WB-passthrough driver | `[x]` |
| §P3.7 #14 | **VWB-2** | cabinet_spots config + `light_switch` profile | `[x]` |
| §P3.7 #15 | **VWB-3** | `POST /devices/{id}/canonical` | `[x]` |
| §P3.7 #16 | **VWB-4** | `device_name → names` bilingual migration | `[x]` |
| §P3.7 #17 | **VWB-5** | `GET /system/catalog` | `[x]` |
| §P3.7 #18 | **VWB-6** | Slice end-to-end HW validation | `[x]` |
| §P3.7 #19 | **VWB-7** | Capability profiles + driver enrichment (folded #20) | `[x]` |
| §P3.7 ~~#20~~ | **VWB-7** | *(folded into VWB-7 — tombstone)* | — |
| §P3.7 #21 | **VWB-8** | `rooms.json` bootstrap + `global` | `[x]` |
| §P3.7 #R | **VWB-9** (±SCN) | Room-architecture refactor | `[x]` |
| §P3.7 #22 | **VWB-10** | Aggregate devices in `global` (`all_lights`) | `[ ]` `[house]` |
| §P3.7 #23 | **VWB-11** | Bulk device configs (57 across 10 rooms) | `[x]` |
| §P3.7 #24 | **VWB-12** | `wb-msw-v3_*` sensor side | `[ ]` `[house]` |
| §P3.7 #25 | **VWB-13** | Catalog completeness + bulk e2e verification | `[ ]` `[house]` |
| §P3.7 #26 | **VWB-14** | Value-label translation layer | `[x]` |

*(P3.7 pre-work findings A1/A2/A3 are not tasks — they fold into VWB-1/-2/-3 context.)*

### In-flight — SCN / DRV / OPS / UI / CORE / DOC

| Old | New | Task | Status |
|---|---|---|---|
| §5.1 manual-notes baseline | **SCN-2** | Transition-aware manual notes — baseline | `[x]` |
| P3.6 | **SCN-3** | Round-2 music scenarios | `[~]` `HW-GATED` `[house]` |
| P4 #7 | **SCN-4** | Scenario↔WB rebuild (mandatory design) | `[ ]` `[house]` |
| §5.2 #6 | **SCN-5** | Transition-aware manual notes — activation-time half | `[ ]` `[house]` |
| §5.1 #7 | **DRV-1** | Per-driver HW verification pass | `[~]` `DOING` `[house]` |
| §5.1 AppleTV apps | **DRV-2** | Apple TV app launching | `[ ]` `[house]` |
| §5.1 IR-learn page | **DRV-3** (±UI) | IR-code learning page | `[ ]` `[later]` |
| §5.1 LG audio_output | **DRV-4** | LG TV `audio_output` rework + `watch_tv` | `[ ]` `[later]` |
| §5.1 force flag | **DRV-5** | Per-action `force` escape hatch | `[ ]` `[later]` |
| §5.1 IR ROM tooling | **DRV-6** | IR ROM backup/restore — remaining play-test | `[~]` `HW-GATED` `[later]` |
| §5.1 ESP32 scaffold | **DRV-7** | ESP32 transport-bridge firmware | `[ ]` `PARKED` `[parked]` |
| §5.1 #8 | **OPS-6** | Clean shutdown (SSE drain + pyatv teardown) | `[x]` |
| §5.1 dep refresh | **OPS-7** | Dependency / Dependabot refresh | `[ ]` `[later]` |
| P4 #6 | **OPS-8** | Lifecycle-robustness leftovers | `[ ]` `[later]` |
| P1 #3-cluster done? | *(see UI-3..6)* | — | — |
| §5.1 vite 5→6 | **UI-8** | Vite 5 → 6 migration | `[ ]` `[later]` |
| §5.1 system-router | **CORE-1** | System-router adapter cleanup (Item A) | `[ ]` `HW-GATED` `[later]` |
| §5.1 scope-drift guard | **DOC-4** | Machine-checkable scope-drift guard | `[ ]` `[later]` |
| §5.2 #1 | **DOC-5** | Ledger-format convergence design *(this doc)* | `[x]` |
| §5.2 #2 | **DOC-6** | Two-file split (initial) | `[x]` |
| §5.2 #3 | **DOC-7** | Adopt additive conventions | `[ ]` |
| §5.2 #4 | **DOC-8** | Extract narrative sections (plan → spine) | `[ ]` |
| §5.2 #5 | **DOC-9** | **Full re-ID execution** *(re-scoped — §5)* | `[ ]` |
| §5.2 #7 | **DOC-10** | Retire frozen scenario/Layer-3 ledgers | `[ ]` `blocks: needs SCN-5 filed` |

**Notable disambiguations the new scheme buys:** the four `#7`/`#8` collisions split cleanly —
`OPS-3`/`OPS-6` (old `#7`s), `OPS-4`/`OPS-8`/`SCN-4` (old `#8`/P4 `#7`s) — and every `§5.2 #n`
stops colliding with `P4 #n`.

---

## 4. Migration mechanics (the spec #5/DOC-9 executes)

Ordered, each step its own commit; **gated on review of this doc** (taxonomy + `CORE` + tag names):

1. **Restructure `action_plan.md`** from P-bands to workstream sections (`## DRV`, `## SCN`, … `##
   DOC`) holding **open + partial** tasks, each line `**PREFIX-N** [Pn] [house|later|parked] —
   <title>. <body>` with a D5 status marker. Add a **`## Acceptance gate`** section (ex-P4 #1–#5).
   Keep `## Open questions`, the journal index, and §7 Codegen (until DOC-8 extracts it).
2. **Reorganize `action_plan_DONE.md`** by workstream (it is currently by P-phase), applying the new
   IDs to completed tasks.
3. **Add a one-time alias map** — `docs/action_plan_aliases.md` (or a table atop the DONE file):
   every old ID → new ID (the §3 tables). This is what makes historical references resolve.
4. **Journal:** **do not rewrite** the ~990 lines of dated prose (rewriting back-refs is the exact
   churn we're eliminating). Prepend a one-line pointer to the alias map; the historical `"§P3.7
   #19"` refs resolve through it. New journal entries use new IDs from here on.
5. **CLAUDE.md:** update the `single-task-ledger` example (`"#3.5, §P3.7, §5.1 rows"` → the
   `PREFIX-N` scheme) and any `read-at-start-record-at-completion` ID examples; add the D4 milestone
   tags + D5 `HW-GATED` marker to the process vocabulary. Single source of truth — must stay honest.
6. **Downstream:** the scope-drift guard (**DOC-4**) is now writable against a regular grammar
   (`^[A-Z]+-\d+`), making `../wb-mqtt-voice/scripts/check_scope.py` a near-port rather than a rewrite.

**Boundary (what "full re-ID" does and does not touch):** it re-IDs the **live ledger** — the active
plan and the DONE file (CLAUDE.md calls these "completed tasks"). The **journal stays frozen** as
historical narrative with an alias map; re-IDing dated prose buys nothing and risks corruption. This
is "full re-ID" in the sense that matters: every *task identity* the ledger exposes is new and
stable; only the immutable history keeps its old words.

---

## 5. Effect on the rest of the §5.2 series

- **§5.2 #1 (this) → DONE** on writing this doc (design recorded; `design-then-implement`).
- **§5.2 #5 RE-SCOPED:** was "(deferred) lazy re-ID"; the 2026-06-30 decision is **full re-ID now**,
  so #5 becomes the execution of §4 above. No longer deferred.
- **§5.2 #3 (adopt conventions) → MERGED into #5** (confirmed 2026-06-30): the legend/priority-split/
  tags (D3/D4/D5) get applied *in* #5's structural rewrite — one pass, not two. #3 is a tombstone.
- **§5.2 #4 (extract narrative)** unchanged — still moves §1–3/§7 out so the plan is a spine.
- **§5.2 #7 (retire scenario docs)** unchanged; still blocked on SCN-5 (transition-aware notes) being
  filed before its source doc is archived.

## 6. Confirmations — RESOLVED 2026-06-30

1. **`CORE` 7th bucket** — ✅ accepted (kept thin; the hexagon is enforced, not a task source).
2. **Milestone tag names** — ✅ `[house]` / `[later]` / `[parked]`.
3. **`#3`+`#5` merge** — ✅ one pass; #3 folds into #5.
