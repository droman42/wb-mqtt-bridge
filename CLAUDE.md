# wb-mqtt-bridge — agent notes

## Development process — invariants (apply to EVERY task)

The always-on working discipline for development in this monorepo (the action plan drives the current
effort, but these rules apply to any task). **Single source of truth** — they live here in `CLAUDE.md`
because it's always in context = always enforced; a second copy anywhere would drift. Referenced by
**name** (stable slug), never by number — names survive adding/removing/reordering, so references from the
plan/journal/review docs never break. (Mirrors `../wb-mqtt-voice/CLAUDE.md` — same rules, bridge's dialect.)

- **`work-on-main`** — Work on `main`; small, focused commits with detailed bodies pushed straight to main
  (no PRs). Branch only when explicitly asked.
- **`config-master-canonical`** — The live **`backend/config/` JSON tree** is the canonical config
  reference: `system.json`, `rooms.json`, `topology.json`, `devices/*.json`, `scenarios/*.json`. Their
  schema is the Pydantic config models (surfaced via `backend/openapi.json`). There is no single
  `config-master` file and no shipped `config-example*` — a release-time example is a later story.
- **`hexagonal-architecture`** — Architecture target = Hexagonal (ports & adapters). **Every dependency
  points inward, across a port:** `domain/` (entities, managers, and the ports in `domain/ports.py`)
  depends on nothing outward; `infrastructure/` (driven adapters: device drivers, MQTT client, SQLite
  store) and `presentation/`+`cli/` (driving adapters) depend inward; `app/` wires them. Don't add
  backwards/cross-layer imports — enforced by the **import-linter** contracts in `backend/pyproject.toml`
  (`lint-imports` from `backend/`). The one documented exception (system router → `mqtt.client` for
  `POST /reload`) is recorded there and in `docs/architecture/overview.md`; don't add new ones. _This is
  the standing LAW: verify imports before every commit._
- **`config-ui-stays-functional`** — `ui/` is a first-class consumer of backend contracts (it imports no
  Python — it consumes the **OpenAPI contract** `backend/openapi.json` + the device/scenario configs; see
  `docs/design/ui_backend_contract.md`). Any task that changes one of these **must update `ui/` in the
  same change and leave it building/type-checking clean**:
  - **REST API endpoints / parameter schemas** → `src/utils/apiClient.ts`, `src/types/openapi.gen.ts`
    (regenerate via `npm run gen:api-types`), the affected components.
  - **Device state models** (the discriminated union behind `/devices/{id}/persisted_state`) or the
    **Layer-3 layout** (`/devices/{id}/layout` → `LayoutManifest`, consumed by `RuntimeDevicePage`) →
    the runtime renderer + `src/types/*`.
  - **Config schema** (`CoreConfig` / `system.json` / `rooms.json` / `topology.json`) → the config
    sections + `src/types/*`.
  - Definition-of-done addendum: `cd ui && npm run check && npm run build` passes (`check` = typecheck +
    strict ESLint + orphan check). _Pairs with `user-facing-docs-are-done` — `ui/` is the user-facing **app**._
- **`read-at-start-record-at-completion`** — AFFIRMATIVE & NON-NEGOTIABLE.
  - **At task START:** read **not only the action-plan item but also its related design/review doc(s)**
    (per the plan's document map) — the plan entry is a spine entry; the design/review doc holds the
    evidence, file:line refs, detail.
  - **At task COMPLETION:** flip status in `docs/action_plan.md` and add a dated entry to
    `docs/action_plan_journal.md` (newest on top) — **in the same change.** Do **not** re-edit a review
    doc's status (frozen evidence with a one-time `→ tracked as <ID>` pointer); the only reason to edit a
    review doc is if a *finding itself* is wrong/obsolete (annotate, don't flip status).
- **`single-task-ledger`** — `docs/action_plan.md` is the only source of scope + status (the master
  driving doc per its §0 document-map convention). Every task has **exactly one ID** (the existing
  §/number scheme — `#3.5`, `§P3.7`, §5.1 rows); design/review docs may *surface findings* but **a finding
  is not scope until it has a plan ID**.
  - **Two-file split (rule defined, not yet applied):** when `docs/action_plan.md` grows large, completed
    tasks move to a frozen `docs/action_plan_DONE.md` (by section) — one ledger, every ID in exactly one
    file, a task **moves** active → done on completion (same change as the journal entry). Until the split,
    completed tasks stay marked `DONE` in place.
  - A machine-checkable scope-drift guard (orphan findings, dead evidence links, contradictory status) is
    a deferred follow-up — see §5.1 in the plan.
- **`every-task-in-the-ledger`** — No work happens without an action-plan entry, **regardless of where the
  task came from** — a chat request, a GitHub issue, a code-review finding, a TODO spotted mid-task. The
  first action on any new piece of work is to file it: give it an ID *before* starting. External sources
  merely *surface* work; it is not scope until it lives in the plan (the intake door `single-task-ledger`
  guards).
- **`design-then-implement`** — A task that **adds a feature or redesigns** an existing one is a **design
  task**: its deliverable is a **design document** — a new file under `docs/design/`, or an edit to the
  existing design for a redesign — referenced from the plan entry. Completing it means *the design is done
  and recorded*, **not** that code shipped. On completion, **file the implementation follow-up task(s)** in
  the plan. Keep design and implementation as separate tasks — so the design is reviewable before any code
  is built. _Mirror of `review-then-remediate`._
- **`review-then-remediate`** — A **review** — requested in chat (name what to review) or run via the
  `/code-review` skill — is itself a **review task** in the plan. Its deliverable is a **review document**
  (frozen evidence under `docs/review/`, carrying the one-time `→ tracked as <ID>` pointers per
  `read-at-start-record-at-completion`). On completion, **file new plan tasks** for the findings worth
  acting on — a finding isn't scope until it has an ID (`single-task-ledger`). _Mirror of
  `design-then-implement`: the review produces the document; the fixes are fresh tasks._
- **`one-active-journal`** — `docs/action_plan_journal.md` is the only **active** chronological log
  (newest entries on top; the single place new entries are added). No competing live logs anywhere else.
  Entries reference task IDs but never assert status.
  - **Archival (rule defined, not yet applied):** older entries are **frozen** into dated files under
    `docs/archive/journal/` (append-only, never re-edited, greppable, **outside the default-read path**).
    Only the active journal is read at task start; an archive is consulted when a
    `task-start-reconciliation` grep points to it. Leave a pointer at the top of the active journal to the
    newest archive.
  - **When to rotate:** when the active journal exceeds **~1500 lines / ~40k tokens** (high-water), freeze
    the **oldest whole dated sections** (never split a day — here, the *bottom* sections, since newest is
    on top) into the newest `docs/archive/journal/` file until it is back under **~1000 lines / ~25k
    tokens** (low-water), then update the pointer.
- **`task-start-reconciliation`** — no stale, redundant, or mis-scoped work. Before starting **any** task,
  reconcile it against current reality — not just the plan/design/review doc
  (`read-at-start-record-at-completion`), but also `docs/action_plan_journal.md` (what actually landed)
  **and the code itself** (does the problem still exist where the task assumes?). Classify: (a) **valid** →
  proceed; (b) **partially addressed** → narrow; (c) **already addressed** → close obsolete; (d) **scope
  drifted** → redefine. **For (b)/(c)/(d): STOP and consult the user** before doing the work or editing the
  plan. _Pairs with `read-at-start-record-at-completion`: that one loads the context; this one verifies the
  task is still the right task._
- **`no-type-checking`** — No `if TYPE_CHECKING:` import guards. Imports are honest: if a type can be
  imported at runtime, import it at module top and annotate with the real symbol. A `TYPE_CHECKING` block
  is a band-aid for an import cycle, and a cycle is an architecture smell (dependencies not pointing inward
  — `hexagonal-architecture`). The fix is to **break the cycle** (move the shared type to a lower layer /
  use a port), not hide it from the runtime. When touching a file that has such a block, remove it.
  _(`backend/` is currently clean — keep new code compliant from the start.)_
- **`user-facing-docs-are-done`** — The user-facing docs — `docs/architecture/*`, `docs/guides/*`, and
  top-level `README*` — are narrative explanations for a reader who does **not** know the codebase or the
  action plan. **A non-root `README*`** (e.g. `eval/README.md`, `ui/README.md`) is also in scope, **but
  only when the task touches code in that README's directory/subsystem** (the local README documents the
  local code; don't audit every README on every task). For **every** task, before completion check whether
  the change alters behavior any in-scope doc describes; if so, update them **in the same change**, matching
  the document's voice — **no internal tracking language** (task IDs, plan/journal refs, file:line, raw
  internal symbols/config keys) unless the doc already teaches them as user-facing names. **Diagrams are
  docs too:** update the source (`docs/images/*.dot`) and regenerate the PNG in the existing visual style.
  _Pairs with `config-ui-stays-functional` (the user-facing **app**; this is the user-facing **docs**)._

## Testing & evaluation

Declarative tests (CLI contracts now; MQTT system tests pending a broker) live in
**[`eval/`](eval/README.md) — read that README before touching anything test-related.**

Key things it establishes (don't rediscover the hard way):
- All test *execution logic* (providers, scorers) lives in the sibling repo **`../eval-commons`** —
  this repo carries only YAML + a thin `eval/Makefile`. Change behavior there, not here.
- Run tests via `make` from `eval/` (it wires the **backend** `uv` venv + global `promptfoo`):
  `make cli` (no prerequisites), `make mqtt TARGET=local|wb7`.
- Code root is `backend/`: the CLI provider uses `cwd: ../backend` and the venv is
  `../backend/.venv` (not the repo-root `.venv`).
- Tests parameterize over the **TARGET** axis (local vs WB7 controller) via `eval/profiles/*.env` —
  never bake a broker host into a test case. promptfoo env refs are `{{env.VAR}}`, not `${VAR}`.

Status: `make cli` passes (wb-openapi, broadlink-cli over a real kitchen_hood code); the MQTT
suite is pending a running broker + bridge (see `eval/README.md` → Notes/TODO).
