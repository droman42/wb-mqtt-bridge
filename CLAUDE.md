# locveil-bridge — agent notes

## Development process — invariants (apply to EVERY task)

The always-on working discipline (the action plan drives the current effort, but these rules apply to
any task). **Two layers:** the *shared* Locveil process rules are normative in
`../locveil-commons/process/` and carried here as pinned digest blocks between `locveil:begin/end`
markers — hash-guarded by scope-guard, so **never edit a block in place** (edit in commons, re-pin);
the *bridge-local* LAW + dialect below the blocks is repo-owned and lives only here. Invariants are
referenced by **name** (stable slug), never by number — names survive adding/removing/reordering.
(`../locveil-voice/CLAUDE.md` carries the same shared blocks with its own dialect.)

<!-- locveil:begin shared-invariants scope-v3 -->
**Locveil shared process invariants** — digest; normative source: `../locveil-commons/process/`
(`ledger-discipline.md`, `claude-md.md`). On disagreement the process files win. Never edit
this block in place — edit in commons, then re-pin (`process/claude-md.md` §3).

- **ledger triad** — active ledger + DONE ledger + one rotating journal; completion MOVES
  the entry to DONE and journals it in the same change; rotation only via an explicit
  `scope_guard.py --rotate` in its own commit; watermarks + mechanics:
  `process/ledger-discipline.md`.
- **every-task-in-the-ledger** — no work without a ledger ID; a doc finding becomes scope
  only when a ledger task declares it.
- **task-start-reconciliation** — before executing any task, verify its claims against repo
  reality; narrow or redefine at intake rather than executing stale text.
- **design-then-implement** — non-trivial changes get a reviewed design doc before code.
- **review-then-remediate** — review findings become ledger tasks before they get fixed.
- **Enforcement** — vendored `scope_guard.py` at a pinned `scope-vX` tag + committed
  pre-commit hook + path-gated `ledger-guard` CI job; hooks and CI run `--check` only.
<!-- locveil:end shared-invariants -->

<!-- locveil:begin cross-repo-board scope-v4 -->
**Locveil cross-repo: the board.** The repos are SIBLINGS on disk — `../locveil-commons`
(umbrella: board, `process/`, shared packages), `../locveil-voice`, `../locveil-bridge`,
`../locveil-satellite`.
Cross-repo initiatives live at `../locveil-commons/board/BOARD.md` (`PROD-N`; council
topics `HK-N`; completed entries in `BOARD_DONE.md`). Delegations arrive as board-as-outbox
text committed inside a PROD entry: pull it, verify per `task-start-reconciliation`, file
it under a LOCAL task ID, execute locally, then write that ID back into the board entry.
The board never asserts a delegated task's status — this repo's ledger owns it. Direct
operational filings between product repos (bug reports, contract requests) stay
repo-to-repo and don't need the board. Cross-repo design sessions and the council run FROM
locveil-commons (convention: `../locveil-commons/process/council.md`); decisions land on
the board, never in chat.
<!-- locveil:end cross-repo-board -->

### Bridge dialect + repo-local LAW

- **`work-on-main`** — Work on `main`; small, focused commits with detailed bodies pushed straight to main
  (no PRs). Branch only when explicitly asked.
- **`config-master-tree`** (renamed from `config-master-canonical` by HK-2 — the voice repo's counterpart
  is `config-master-file`; no repo keeps the bare slug) — The live **`backend/config/` JSON tree** is the
  canonical config reference: `system.json`, `rooms.json`, `topology.json`, `devices/*.json`,
  `scenarios/*.json`. Their schema is the Pydantic config models (surfaced via `backend/openapi.json`).
  There is no single config-master file and no shipped `config-example*` — a release-time example is a
  later story.
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
- **`cross-repo-source-of-truth`** — for any artifact **shared with a sibling repo** (the Irene↔bridge
  catalog contract, eval fixtures, a schema pin), **this** repo is the *generator / source of truth*: it
  commits the reference copy **here** (e.g. `contracts/`) and **never writes into the sibling product
  repo** (`locveil-voice`) — `locveil-commons` is co-owned ground (board write-backs, shared-package
  fixes). Sync is **one-way, outward, version-stamped** — the sibling *pins its own copy* (the bridge
  does not push one). Mirror of the Testing-section rule from the other direction (test *execution
  logic* lives in `../locveil-commons/eval`, changed there not here). Cross-repo initiatives arrive as
  **board delegations** (see the `cross-repo-board` block); a direct operational filing from a sibling
  (a bug report, a contract request) is normal intake — verify its claims against live code, then it
  needs a local ID like any other work. Detail: `locveil-voice/docs/design/mqtt_integration.md` §14 +
  the `voice-bridge-catalog-contract` memory.
- **`read-at-start-record-at-completion`** — AFFIRMATIVE & NON-NEGOTIABLE. At task START, read **not
  only the action-plan item but also its related design/review doc(s)** (per the plan's document map) —
  the plan entry is a spine entry; the design/review doc holds the evidence, file:line refs, detail.
  Completion follows the shared triad (move + journal, same change). Do **not** re-edit a review doc's
  status (frozen evidence with a one-time `→ tracked as <ID>` pointer); the only reason to edit a
  review doc is if a *finding itself* is wrong/obsolete (annotate, don't flip status).
- **`single-task-ledger`** (bridge dialect of the shared triad) — active ledger `docs/action_plan.md`
  (the master driving doc per its §0 document-map convention), completed `docs/action_plan_DONE.md`,
  archives `docs/archive/ledger/`. Every task has **exactly one ID** in the stable **`PREFIX-N`
  workstream-serial** scheme (prefix = workstream section, serial assigned once / never renumbered;
  rows ascend within their section in both files); priority is a separate `[P0]/[P1]/[P2]` tag,
  milestone `[release]/[deferred]` (since REL-1), plus a `HW-GATED` status marker — see the plan's
  "How to use this file". Old positional IDs (`#3.5`, `§P3.7 #13`) resolve via
  `docs/action_plan_aliases.md`. Guard invocation: `python3 scripts/scope_guard.py --config
  .scope-guard.toml` (run it BARE in commit chains — pipes swallow the failing exit).
- **`every-task-in-the-ledger`** (carve-out) — routine dependency housekeeping: a lockfile-only bump
  that does **not** change `package.json` / `pyproject.toml` intent (e.g. `npm audit fix`, a Dependabot
  lock refresh) needs no plan ID — it still gets a `one-active-journal` line on completion. A bump that
  *is* a deliberate version decision (new dep, major upgrade, pin change) is a normal task with an ID.
- **`design-then-implement`** (dialect) — the design deliverable is a file under `docs/design/` (or an
  edit to the existing design for a redesign), referenced from the plan entry; on completion, file the
  implementation follow-up task(s) so the design is reviewable before any code is built.
- **`review-then-remediate`** (dialect) — a review — requested in chat or via the `/code-review` skill —
  is itself a plan task; its deliverable is frozen evidence under `docs/review/`, carrying the one-time
  `→ tracked as <ID>` pointers; the fixes are fresh tasks.
- **`one-active-journal`** (dialect) — the active journal is `docs/action_plan_journal.md` (newest
  entries on top; the single place new entries are added; no competing live logs). Entries reference
  task IDs but never assert status. Frozen archives live in `docs/archive/journal/` — append-only,
  greppable, **outside the default-read path**; a pointer at the top of the journal names the newest.
- **`task-start-reconciliation`** (dialect) — reconcile against the plan/design/review doc, the journal
  (what actually landed), **and the code itself**. Classify: (a) **valid** → proceed; (b) **partially
  addressed** → narrow; (c) **already addressed** → close obsolete; (d) **scope drifted** → redefine.
  **For (b)/(c)/(d): STOP and consult the user** before doing the work or editing the plan.
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
- **`problem-report-inbox`** — problem reports land as tickets in the private
  `locveil/locveil-reports` repo (cross-repo design: `locveil-voice/docs/design/problem_reports.md`;
  the bridge side: `docs/design/problem_reports_bridge.md`); a cloud Claude triages each and leaves it
  needing the owner (a fix PR open on this repo, or a `needs-owner` escalation). **At the start of a new
  or resumed session, do a quick, non-blocking check** —
  `gh issue list --repo locveil/locveil-reports --label needs-owner --label lens:bridge --state open`
  plus the `fix-pr-open` variant — and if anything is waiting, **mention the count in one line** and
  offer `/inbox`. Never auto-enter the review; the owner decides when. (Skill: `.claude/skills/inbox/`.
  A `gh` failure — no network, no auth — is silently skipped; this check must never block or noise up a
  normal session.)

## Testing & evaluation

Declarative tests (CLI contracts now; MQTT system tests pending a broker) live in
**[`eval/`](eval/README.md) — read that README before touching anything test-related.**

Key things it establishes (don't rediscover the hard way):
- All test *execution logic* (providers, scorers) lives in the sibling repo **`../locveil-commons/eval`** —
  this repo carries only YAML + a thin `eval/Makefile`. Change behavior there, not here.
- Run tests via `make` from `eval/` (it wires the **backend** `uv` venv + global `promptfoo`):
  `make cli` (no prerequisites), `make mqtt TARGET=local|wb7`.
- Code root is `backend/`: the CLI provider uses `cwd: ../backend` and the venv is
  `../backend/.venv` (not the repo-root `.venv`).
- Tests parameterize over the **TARGET** axis (local vs WB7 controller) via `eval/profiles/*.env` —
  never bake a broker host into a test case. promptfoo env refs are `{{env.VAR}}`, not `${VAR}`.

Status: `make cli` passes (wb-openapi, broadlink-cli over a real kitchen_hood code); the MQTT
suite is pending a running broker + bridge (see `eval/README.md` → Notes/TODO).
