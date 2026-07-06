---
name: inbox
description: Review the problem-report queue one item at a time — fix PRs on this repo and owner-escalated tickets from wb-user-reports (VWB-26). Invoke when the user asks to review reports, check the inbox, or triage the queue, or when a session-start reminder flags pending items.
---

# /inbox — problem-report owner review (bridge lens)

The interactive review loop for the problem-reporting system (the cross-repo design in
`wb-mqtt-voice/docs/design/problem_reports.md` §8; the bridge's participation is
`docs/design/problem_reports_bridge.md`). Reports land as tickets in the **private**
`droman42/wb-user-reports` repo; a GitHub-hosted Claude triages each one and leaves it in one of
two states that need the owner: a **fix PR open on this repo**, or an **escalated ticket**
(`needs-owner`). This skill walks that queue **one item at a time**, with the owner deciding each.

The reports repo is the source of truth for the queue — not this repo's PR list. Every actionable
item has a `wb-user-reports` ticket; a fix PR is linked from its ticket.

## 1. Gather the queue

Two buckets, bridge lens only (the voice twin is the voice repo's `/inbox`):

```bash
# fix PRs awaiting review (ticket carries the PR link)
gh issue list --repo droman42/wb-user-reports --label fix-pr-open --label lens:bridge \
  --state open --json number,title,url

# escalations awaiting an owner decision or reply
gh issue list --repo droman42/wb-user-reports --label needs-owner --label lens:bridge \
  --state open --json number,title,url
```

If both are empty: say the inbox is clear and stop. Otherwise report the count and start the walk.

## 2. Walk one item at a time

Never batch. For each ticket, present it, do the reading, recommend, then **wait for the owner's
decision before touching anything**. Move to the next only when the current one is resolved or the
owner says skip.

### A `fix-pr-open` ticket

1. Read the ticket + the triage comment (`gh issue view <n> --repo droman42/wb-user-reports --comments`).
   A handed-over ticket carries the voice lens's handover comment — what they already ruled out.
2. Open the linked PR here (`gh pr view <pr> --json title,body,files,additions,deletions`;
   `gh pr diff <pr>`).
3. **Verify the finding independently — do not trust the triage.** The cloud triage reasons from a
   bundle it cannot re-run against live hardware, and a report is often triggered by a transient or
   a dev-session artifact. Reproduce or refute: run the affected tests (from `backend/`:
   `uv run pytest tests/ -q`), check the catalog claim against `contracts/catalog.golden.json`,
   read the cited code. Hold the PR to this repo's gates: suite green, `uv run pyright` 0,
   `uv run lint-imports` clean (`hexagonal-architecture`), `cd ui && npm run check && npm run build`
   if `ui/` is touched, and the contract drift test if it changes the catalog/OpenAPI surface.
   A triage PR must NOT touch ledger/journal files — those are the owner's (see step 5).
4. Give a plain verdict: **merge / revise / reject**, with the one reason that decides it.
5. On the owner's call:
   - **merge** → `gh pr merge <pr> --squash --delete-branch` (removes the triage's remote branch;
     also delete any local review branch you created, e.g. `git branch -D pr-<n>-review`);
     close the ticket with a note (`gh issue close <n> --repo droman42/wb-user-reports --comment "..."`);
     then do the ledger's half yourself: the merged fix is work — file/complete it per
     `every-task-in-the-ledger` + `read-at-start-record-at-completion` (journal entry; DONE row at
     sorted position — the ledger-discipline triad applies).
   - **revise** → make the changes on the PR branch (or ask triage to, via a ticket comment), push,
     re-review.
   - **reject** → `gh pr close <pr> --delete-branch` + close the ticket explaining why (a false
     positive is a normal outcome; record it so the pattern is visible).

### A `needs-owner` ticket

1. Read the ticket + triage comment. Triage escalates for a decision OR because the reporter needs
   more information (v1 has no user registry, so unclear reports always come here — usually with a
   **drafted reply in the reporter's language** ready for approval).
2. If a reply is drafted: present it, let the owner approve/edit, then post it as a ticket comment.
   The reporter has no GitHub account — the reply is for the owner's own out-of-band relay.
3. If it's a decision (dedup, not-a-bug, needs-voice-handover): recommend, act on the owner's call
   (comment, relabel `lens:voice` for a handover — mind the ping-pong guard: one bounce each way
   maximum, then it stays `needs-owner` — or close), one line of reasoning.

## 3. Close out

After the walk, summarize what changed (merged / rejected / replied / handed over / skipped). Leave
anything the owner deferred in place — the queue is durable; it'll resurface next `/inbox`.

## Notes

- **Leak fence still applies here.** Ticket bundles carry household data (logs, rooms, configs,
  free text); this repo's PRs and commits must stay technical. Don't paste bundle contents into a
  public PR or commit message.
- **Read-only is safe.** Listing and reading (steps 1–2) touch nothing. Only merges, closes,
  comments, and pushes change state, and each waits for an explicit owner decision.
- **Never live-repro against the house**: verification is tests-only — don't start a second
  backend against the real broker (client-id collision + restore-actuation risk).
