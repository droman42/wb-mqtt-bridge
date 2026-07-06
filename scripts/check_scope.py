#!/usr/bin/env python3
"""
check_scope.py — ledger scope-drift guard (invariant `single-task-ledger`).

The task ledger is the single source of scope + status. It lives in two files
(`single-task-ledger`): `docs/action_plan.md` (active: open + partial tasks) and
`docs/action_plan_DONE.md` (frozen: completed tasks), every task ID in exactly one.
Tasks use the stable `PREFIX-N` workstream scheme (DOC-9); old positional IDs resolve
via `docs/action_plan_aliases.md`. Design/review docs *surface* findings but a finding
is not scope until it has a plan ID. This script proves nothing has drifted.

Fails the build (exit 1) on:
  1. DUPLICATE id        — a task ID declared more than once across the two ledger files
                           (violates "every ID in exactly one file / assigned once").
  2. MISPLACED status    — a `[x]` (done) task still in the active file, or a non-done
                           task in the frozen DONE file (the "contradictory status" check).
  3. ORPHAN finding      — a `PREFIX-N` id referenced in docs/design|docs/review but NOT
                           known to the ledger (scope hiding in a design/review doc).
  4. DEAD evidence link  — the ledger points at a docs/design|docs/review file that is
                           missing on disk.
  5. ALIAS phantom       — action_plan_aliases.md maps an old id to a new id that the
                           ledger does not declare.
  6. MISFILED task       — a task's ID prefix does not match its enclosing workstream
                           section header, in either file (an insert placed before the
                           NEXT section header lands in the PRECEDING section — the
                           classic slip; ported from wb-mqtt-voice, DOC-12).
  7. OUT-OF-ORDER id     — entries must ascend by ID number within each workstream
                           section, both files: completions are INSERTED at sorted
                           position, never appended (ported from wb-mqtt-voice, DOC-12).

Informational (never fails): per-workstream open/done/partial summary.

Usage:  python3 scripts/check_scope.py        (from anywhere; paths are repo-root-relative)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ACTIVE = ROOT / "docs" / "action_plan.md"
DONE = ROOT / "docs" / "action_plan_DONE.md"
ALIASES = ROOT / "docs" / "action_plan_aliases.md"
FINDING_DIRS = [ROOT / "docs" / "design", ROOT / "docs" / "review"]

PREFIXES = ("DRV", "SCN", "VWB", "UI", "OPS", "CORE", "DOC", "REL")
_PFX = "|".join(PREFIXES)

# A task DECLARATION line:  - [ ] **DRV-1** …  /  - [x] **VWB-6** …  /  - [~] **X-2** …
DECL_RE = re.compile(rf"^- \[([ x~])\] \*\*((?:{_PFX})-\d+)\*\*")
# A TOMBSTONE line (folded/retired id kept for provenance):  - ~~**DOC-7**~~ …
TOMB_RE = re.compile(rf"^- ~~\*\*((?:{_PFX})-\d+)\*\*~~")
# Any id reference (in prose / design docs).
ID_RE = re.compile(rf"\b((?:{_PFX})-\d+)\b")
# A repo-relative docs/design|docs/review markdown path. The negative lookbehind keeps it from
# matching a sibling-repo path like `wb-mqtt-voice/docs/design/mqtt_integration.md` (that file is
# outside this repo and is expected to be absent here).
EVID_RE = re.compile(r"(?<![\w/-])docs/(?:design|review)/[\w./-]+\.md")
# Alias-table row:  | DRV-1 | §5.1 #7 | … |
ALIAS_ROW_RE = re.compile(rf"^\|\s*((?:{_PFX})-\d+)\s*\|")
# A workstream SECTION header:  `### VWB — …` (active) / `## VWB — …` (DONE archive).
# A header at the same-or-higher level ends the section; DEEPER headers (e.g. a `####`
# runbook inside a `##` section) keep it — task rows may follow narrative sub-headers.
SECTION_RE = re.compile(r"^(#{2,4})\s+([A-Z]+)\s+—")
HEADER_RE = re.compile(r"^(#+)\s")


def declarations(path: Path) -> list[tuple[str, str]]:
    """[(id, status_char)] for every declaration line in a ledger file."""
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = DECL_RE.match(line)
        if m:
            out.append((m.group(2), m.group(1)))
    return out


def tombstones(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {m.group(1) for line in path.read_text(encoding="utf-8").splitlines()
            if (m := TOMB_RE.match(line))}


def main() -> int:
    if not ACTIVE.exists():
        print(f"FATAL: ledger not found at {ACTIVE}", file=sys.stderr)
        return 2

    active_decls = declarations(ACTIVE)
    done_decls = declarations(DONE)
    all_decls = active_decls + done_decls

    known_ids = {i for i, _ in all_decls} | tombstones(ACTIVE) | tombstones(DONE)

    errors: list[str] = []

    # 1. DUPLICATE id (declared more than once across both files)
    seen: dict[str, int] = {}
    for i, _ in all_decls:
        seen[i] = seen.get(i, 0) + 1
    dupes = sorted(i for i, n in seen.items() if n > 1)
    for i in dupes:
        errors.append(f"DUPLICATE id: {i} is declared {seen[i]}× (must be exactly one file/place)")

    # 2. MISPLACED status
    for i, s in active_decls:
        if s == "x":
            errors.append(f"MISPLACED status: {i} is done [x] but still in the ACTIVE ledger (move it to DONE)")
    for i, s in done_decls:
        if s != "x":
            errors.append(f"MISPLACED status: {i} is in the DONE archive but not [x] (status '{s}')")

    # 3 + 4. scan design/review docs for orphans; collect evidence-link targets
    orphans: dict[str, set[str]] = {}
    finding_files = sorted(p for d in FINDING_DIRS if d.exists() for p in d.rglob("*.md"))
    for p in finding_files:
        rel = p.relative_to(ROOT).as_posix()
        text = p.read_text(encoding="utf-8")
        for tid in set(ID_RE.findall(text)):
            if tid not in known_ids:
                orphans.setdefault(tid, set()).add(rel)
    for tid, files in sorted(orphans.items()):
        errors.append(f"ORPHAN finding: {tid} referenced in {', '.join(sorted(files))} but not in the ledger")

    # 4. DEAD evidence links: docs/design|docs/review paths named in the ledger that don't exist
    ledger_text = ACTIVE.read_text(encoding="utf-8") + "\n" + (DONE.read_text(encoding="utf-8") if DONE.exists() else "")
    for path_str in sorted(set(EVID_RE.findall(ledger_text))):
        if not (ROOT / path_str).exists():
            errors.append(f"DEAD evidence link: ledger references {path_str} which is missing on disk")

    # 5. ALIAS phantom: alias maps old -> new where new isn't a known id
    if ALIASES.exists():
        for line in ALIASES.read_text(encoding="utf-8").splitlines():
            m = ALIAS_ROW_RE.match(line)
            if m and m.group(1) not in known_ids:
                errors.append(f"ALIAS phantom: alias target {m.group(1)} is not declared in the ledger")

    # 6 + 7. MISFILED + OUT-OF-ORDER (ledger-discipline triad, ported from wb-mqtt-voice —
    # DOC-12). Walk each file tracking the enclosing workstream section: a declaration's
    # prefix must match the section, and IDs must ascend within it (sorted insert, not append).
    def section_walk(path: Path, which: str) -> None:
        if not path.exists():
            return
        section: str | None = None
        level = 0  # header level of the current workstream section
        prev: int | None = None
        for line in path.read_text(encoding="utf-8").splitlines():
            h = SECTION_RE.match(line)
            if h and h.group(2) in PREFIXES:
                section, level, prev = h.group(2), len(h.group(1)), None
                continue
            hh = HEADER_RE.match(line)
            if hh and section is not None and len(hh.group(1)) <= level:
                section, prev = None, None  # same-or-higher header ends the section
                continue
            m = DECL_RE.match(line)
            if not m:
                continue
            pfx, num = m.group(2).split("-")
            if section is None:
                errors.append(f"MISFILED task: {m.group(2)} sits outside any workstream section [{which}]")
                continue
            if pfx != section:
                errors.append(f"MISFILED task: {m.group(2)} sits under the {section} section [{which}]")
                continue
            n = int(num)
            if prev is not None and n < prev:
                errors.append(
                    f"OUT-OF-ORDER id: {m.group(2)} appears after {pfx}-{prev} in the {section} section "
                    f"[{which}] (insert at sorted position, don't append)"
                )
            prev = max(prev, n) if prev is not None else n

    section_walk(ACTIVE, "active")
    section_walk(DONE, "done")

    # ---- report ----
    print("== check_scope: ledger scope-drift guard ==\n")
    if errors:
        for e in errors:
            print(f"  ✗ {e}")
        print()

    # informational per-workstream summary
    by_ws: dict[str, list[int]] = {p: [0, 0, 0] for p in PREFIXES}  # [open, done, partial]
    for i, s in all_decls:
        pfx = i.split("-")[0]
        by_ws[pfx][{" ": 0, "x": 1, "~": 2}[s]] += 1
    print("Ledger by workstream (open · done · partial):")
    for p in PREFIXES:
        o, d, pa = by_ws[p]
        if o or d or pa:
            print(f"  {p:5} {o:>2} · {d:>2} · {pa:>2}")
    tot = len(all_decls)
    done_n = sum(1 for _, s in all_decls if s == "x")
    print(f"  total {tot} tasks — {done_n} done · {tot - done_n} not-done.\n")

    if errors:
        print(f"FAIL: {len(errors)} scope-drift issue(s). Reconcile the ledger.")
        return 1
    print("OK: no scope drift (ids unique + correctly placed, no orphan findings, no dead links).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
