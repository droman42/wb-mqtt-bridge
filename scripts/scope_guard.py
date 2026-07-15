#!/usr/bin/env python3
"""
scope_guard.py — the Locveil ledger/journal discipline guard (HK-1 / PROD-13).

ONE config-driven tool superseding the per-repo check_scope.py scripts; the rule set is
the UNION of the historical voice + bridge checkers plus the HK-1 additions. Normative
convention: locveil-commons/process/ledger-discipline.md. Consumers VENDOR this single
stdlib-only file at a pinned `scope-vX` tag together with their own `.scope-guard.toml`;
behavior changes happen in locveil-commons, never in a consumer's copy.

Modes:
  --check  (default)  validate; never mutates the tree. Errors exit 1, warnings exit 0.
  --rotate [journal|done|all]   execute the rotation rule deterministically (its own
           commit). Hooks and CI must only ever run --check.

Failing rules (config-toggled where marked):
  DUPLICATE id · MISPLACED status (two-directional) · ORPHAN finding · DEAD evidence link
  (path-scan and/or voice-style `[x]` index) · ALIAS phantom [aliases] · MISFILED task
  [sections] · OUT-OF-ORDER id · MISSING required tag [required_tags] · ARCHIVE-POINTER
  broken [journal.archive_pointer] · NO-JOURNAL completion [journal.completion_crosscheck]
  · DELEGATION without write-back [board.delegation_writeback] · hard-ceiling overflow.
Warnings: UNINDEXED review [evidence.index] · journal/DONE over high-water.

Usage:  python3 scope_guard.py [--config .scope-guard.toml] [--root DIR] [--rotate all]
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
import tomllib
from pathlib import Path

__version__ = "1.3.0"  # scope-v6 — UNREFERENCED-evidence check (HK-10 / IMPL-2)


# ---------------------------------------------------------------- config

DEFAULTS = {
    "ledger": {
        "active": None, "done": None, "archive_dir": None, "aliases": None,
        "prefixes": [], "open_statuses": [" ", "~"],
        "require_sections": True, "sections_required_for_all": False,
        "required_tags": [], "tombstones": False,
        "high_water": 3000, "low_water": 2000, "hard_ceiling": 4000,
        "docs_verdict_since": "",
    },
    "evidence": {"dirs": [], "index": False, "link_scan": False, "unindexed": "warn",
                 "unreferenced": "warn"},
    "journal": {
        "active": None, "archive_dir": None,
        "high_water": 1500, "low_water": 1000, "hard_ceiling": 2000,
        "completion_crosscheck": False, "archive_pointer": True,
    },
    "board": {"delegation_writeback": False},
    "claude": {"file": None, "blocks": []},
}

# Pinned shared blocks in CLAUDE.md (process/claude-md.md §2-3):
#   <!-- locveil:begin <name> scope-vN -->  …  <!-- locveil:end <name> -->
def find_block(text: str, name: str) -> str | None:
    m = re.search(rf"<!-- locveil:begin {re.escape(name)}(?:\s[^>]*)? -->\n(.*?)\n?"
                  rf"<!-- locveil:end {re.escape(name)} -->", text, re.S)
    return m.group(1) if m else None


def block_hash(content: str) -> str:
    return hashlib.sha256(content.strip().encode("utf-8")).hexdigest()


def load_config(path: Path) -> dict:
    with path.open("rb") as f:
        raw = tomllib.load(f)
    cfg = {}
    for section, defaults in DEFAULTS.items():
        cfg[section] = dict(defaults)
        cfg[section].update(raw.get(section, {}))
    if not cfg["ledger"]["active"] or not cfg["ledger"]["prefixes"]:
        sys.exit(f"FATAL: {path}: [ledger] needs at least 'active' and 'prefixes'")
    return cfg


class Rules:
    """Compiled per-config patterns."""

    def __init__(self, cfg: dict):
        pfx = "|".join(re.escape(p) for p in cfg["ledger"]["prefixes"])
        st = re.escape("".join(cfg["ledger"]["open_statuses"])) + "x"
        # `\b` (not a closing `**`) so both `**DOC-12**` and the board's
        # `**PROD-1 — title**` declaration shapes match.
        self.decl = re.compile(rf"^- \[([{st}])\] \*\*((?:{pfx})-\d+)\b")
        self.tomb = re.compile(rf"^- ~~\*\*((?:{pfx})-\d+)\*\*~~")
        self.id = re.compile(rf"\b((?:{pfx})-\d+)\b")
        self.alias_row = re.compile(rf"^\|\s*((?:{pfx})-\d+)\s*\|")
        # Section headers, both house styles: `### VWB — …` and `### Architecture (ARCH)`.
        self.sec_dash = re.compile(rf"^(#{{2,4}})\s+({pfx})\s+—")
        self.sec_paren = re.compile(rf"^(#{{2,4}})\s+.*\(({pfx})\)\s*$")
        self.header = re.compile(r"^(#+)\s")
        # A repo-relative evidence path; the lookbehind keeps sibling-repo paths
        # (`locveil-voice/docs/design/x.md`) from matching.
        dirs = "|".join(re.escape(d) for d in cfg["evidence"]["dirs"]) or "docs/(?:design|review)"
        self.evid = re.compile(rf"(?<![\w/-])(?:{dirs})/[\w./-]+\.md")


# ---------------------------------------------------------------- helpers

def read(path: Path | None) -> str:
    return path.read_text(encoding="utf-8") if path and path.exists() else ""


def declarations(text: str, rules: Rules) -> list[tuple[str, str]]:
    """[(id, status_char)] for every declaration line."""
    return [(m.group(2), m.group(1)) for line in text.splitlines()
            if (m := rules.decl.match(line))]


def entry_blocks(text: str, rules: Rules) -> list[tuple[str, str, str]]:
    """[(id, status, block_text)] — a block runs from its declaration line to the next
    top-level `- ` bullet or header (continuation lines are indented)."""
    lines = text.splitlines()
    out, cur = [], None  # cur = [id, status, [lines]]
    for line in lines:
        m = rules.decl.match(line)
        if m:
            if cur:
                out.append((cur[0], cur[1], "\n".join(cur[2])))
            cur = [m.group(2), m.group(1), [line]]
        elif cur and (line.startswith("- ") or line.startswith("#")):
            out.append((cur[0], cur[1], "\n".join(cur[2])))
            cur = None
        elif cur:
            cur[2].append(line)
    if cur:
        out.append((cur[0], cur[1], "\n".join(cur[2])))
    return out


# A dated journal entry starts either as a heading (`## 2026-07-11 — …`, commons style)
# or a top-level bullet (`- **2026-07-11 — …**`, voice/bridge style).
DATED = re.compile(r"^(?:#{2,3}|- \*\*)(\d{4}-\d{2}-\d{2})")


def dated_sections(text: str) -> tuple[list[str], list[tuple[str, list[str]]]]:
    """Split a newest-on-top journal into (header_lines, [(date, day_lines)]).

    Consecutive entries sharing a date are grouped into ONE day unit — rotation moves
    whole days, never part of one."""
    lines = text.splitlines()
    header: list[str] = []
    sections: list[tuple[str, list[str]]] = []
    cur: list[str] | None = None
    for line in lines:
        m = DATED.match(line)
        if m:
            if sections and sections[-1][0] == m.group(1):
                cur = sections[-1][1]           # same day continues — never split it
                cur.append(line)
            else:
                cur = [line]
                sections.append((m.group(1), cur))
        elif cur is not None:
            cur.append(line)
        else:
            header.append(line)
    return header, sections


# ---------------------------------------------------------------- checks

class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)


def check(root: Path, cfg: dict, rules: Rules) -> Report:
    rep = Report()
    L, E, J, B = cfg["ledger"], cfg["evidence"], cfg["journal"], cfg["board"]

    active_p = root / L["active"]
    done_p = root / L["done"] if L["done"] else None
    if not active_p.exists():
        rep.error(f"FATAL: active ledger not found at {active_p}")
        return rep
    active = read(active_p)
    done = read(done_p)

    active_decls = declarations(active, rules)
    done_decls = declarations(done, rules)
    all_decls = active_decls + done_decls

    # Rotated ledger archives stay in the known-ID set (the HK-1 hard rule).
    archive_decls: list[tuple[str, str]] = []
    if L["archive_dir"] and (root / L["archive_dir"]).exists():
        for p in sorted((root / L["archive_dir"]).glob("*.md")):
            archive_decls += declarations(read(p), rules)

    tombs: set[str] = set()
    if L["tombstones"]:
        for text in (active, done):
            tombs |= {m.group(1) for line in text.splitlines()
                      if (m := rules.tomb.match(line))}
    known = {i for i, _ in all_decls + archive_decls} | tombs

    # DUPLICATE — across active + done (archives hold *moved* copies, not duplicates)
    seen: dict[str, int] = {}
    for i, _ in all_decls:
        seen[i] = seen.get(i, 0) + 1
    for i in sorted(k for k, n in seen.items() if n > 1):
        rep.error(f"DUPLICATE id: {i} declared {seen[i]}× (every ID in exactly one place)")
    for i, _ in archive_decls:
        if i in seen:
            rep.error(f"DUPLICATE id: {i} is in a ledger archive AND a live ledger file")

    # MISPLACED — two-directional
    for i, s in active_decls:
        if s == "x":
            rep.error(f"MISPLACED status: {i} is done [x] but still in the ACTIVE ledger (move it to DONE)")
    for i, s in done_decls:
        if s != "x":
            rep.error(f"MISPLACED status: {i} is in the DONE ledger but not [x] (status '{s}')")

    # ORPHAN + evidence-file inventory
    evid_files = sorted(p for d in E["dirs"] if (root / d).exists()
                        for p in (root / d).rglob("*.md"))
    orphans: dict[str, set[str]] = {}
    for p in evid_files:
        rel = p.relative_to(root).as_posix()
        for tid in set(rules.id.findall(read(p))):
            if tid not in known:
                orphans.setdefault(tid, set()).add(rel)
    for tid, files in sorted(orphans.items()):
        rep.error(f"ORPHAN finding: {tid} referenced in {', '.join(sorted(files))} but not in the ledger")

    # DEAD links — path-scan mode (bridge style)
    if E["link_scan"]:
        for path_str in sorted(set(rules.evid.findall(active + "\n" + done))):
            if not (root / path_str).exists():
                rep.error(f"DEAD evidence link: ledger references {path_str} which is missing on disk")

    # DEAD links + UNINDEXED — voice-style `[x]` exists-marker index (active file only)
    if E["index"]:
        indexed: dict[str, bool] = {}
        for line in active.splitlines():
            if line.startswith("|") and (m := re.search(r"`([\w./-]+\.md)`", line)):
                indexed[m.group(1)] = "`[x]`" in line
        on_disk = {p.name for p in evid_files}
        for f, exists_marked in indexed.items():
            # rows without `[x]` are planned docs produced later — not dead
            if exists_marked and Path(f).name not in on_disk:
                rep.error(f"DEAD evidence link: index marks {f} `[x]` but it is missing on disk")
        if E["unindexed"] != "off":
            idx_names = {Path(f).name for f in indexed}
            for p in evid_files:
                if p.name not in idx_names:
                    msg = f"UNINDEXED review doc: {p.relative_to(root).as_posix()} not in the ledger index"
                    rep.error(msg) if E["unindexed"] == "fail" else rep.warn(msg)

    # UNREFERENCED evidence — the fourth direction (HK-10 ruling 1, ledger-discipline §6):
    # a doc ON DISK that no ledger entry (active or DONE) references is forgotten scope.
    # Referenced = its repo-relative path OR its basename appears in active+DONE.
    if E["unreferenced"] != "off":
        ledgers = active + "\n" + done
        for p in evid_files:
            rel = p.relative_to(root).as_posix()
            if rel not in ledgers and p.name not in ledgers:
                msg = (f"UNREFERENCED evidence: {rel} is referenced by no ledger entry "
                       f"(HK-10 — anchor it with a task or completion entry)")
                rep.error(msg) if E["unreferenced"] == "error" else rep.warn(msg)

    # ALIAS phantom
    if L["aliases"]:
        for line in read(root / L["aliases"]).splitlines():
            m = rules.alias_row.match(line)
            if m and m.group(1) not in known:
                rep.error(f"ALIAS phantom: alias target {m.group(1)} is not declared in the ledger")

    # MISFILED + OUT-OF-ORDER
    def section_walk(text: str, which: str) -> None:
        section: str | None = None
        level = 0
        prev: int | None = None
        prev_by_pfx: dict[str, int] = {}
        for line in text.splitlines():
            h = rules.sec_dash.match(line) or rules.sec_paren.match(line)
            if h and L["require_sections"]:
                section, level, prev = h.group(2), len(h.group(1)), None
                continue
            hh = rules.header.match(line)
            if hh and section is not None and len(hh.group(1)) <= level:
                section, prev = None, None  # same-or-higher header ends the section
                continue
            m = rules.decl.match(line)
            if not m:
                continue
            pfx, num = m.group(2).rsplit("-", 1)
            n = int(num)
            if L["require_sections"]:
                if section is None:
                    if L["sections_required_for_all"]:
                        rep.error(f"MISFILED task: {m.group(2)} sits outside any workstream section [{which}]")
                    continue
                if pfx != section:
                    rep.error(f"MISFILED task: {m.group(2)} sits under the {section} section [{which}]")
                    continue
                if prev is not None and n < prev:
                    rep.error(f"OUT-OF-ORDER id: {m.group(2)} appears after {pfx}-{prev} in the "
                              f"{section} section [{which}] (insert at sorted position, don't append)")
                prev = max(prev, n) if prev is not None else n
            else:
                p = prev_by_pfx.get(pfx)
                if p is not None and n < p:
                    rep.error(f"OUT-OF-ORDER id: {m.group(2)} appears after {pfx}-{p} [{which}] "
                              f"(IDs ascend per prefix)")
                prev_by_pfx[pfx] = max(p, n) if p is not None else n

    section_walk(active, "active")
    if done:
        section_walk(done, "done")

    # required tags on every non-done entry (block-level: tags may sit past the ID line)
    if L["required_tags"]:
        for tid, s, block in entry_blocks(active, rules):
            if s != "x" and not any(t in block for t in L["required_tags"]):
                rep.error(f"MISSING required tag: {tid} carries none of {L['required_tags']}")

    # watermarks: journal + DONE ledger
    def watermark(path: Path | None, high: int, ceiling: int, what: str) -> None:
        if not path or not path.exists():
            return
        n = len(read(path).splitlines())
        if n > ceiling:
            rep.error(f"OVER hard ceiling: {what} at {n} lines (> {ceiling}) — run --rotate")
        elif n > high:
            rep.warn(f"over high-water: {what} at {n} lines (> {high}) — rotation due (--rotate)")

    journal_p = root / J["active"] if J["active"] else None
    watermark(journal_p, J["high_water"], J["hard_ceiling"], "journal")
    watermark(done_p, L["high_water"], L["hard_ceiling"], "DONE ledger")

    # archive-pointer integrity
    if J["archive_pointer"] and journal_p and J["archive_dir"]:
        jtext = read(journal_p)
        adir = root / J["archive_dir"]
        for m in re.finditer(rf"(?<![\w/-]){re.escape(J['archive_dir'])}/[\w./-]+\.md", jtext):
            if not (root / m.group(0)).exists():
                rep.error(f"ARCHIVE-POINTER broken: journal names {m.group(0)} which is missing on disk")
        if adir.exists():
            archives = sorted(adir.glob("*.md"))
            if archives and archives[-1].name not in jtext:
                rep.error(f"ARCHIVE-POINTER stale: newest archive {archives[-1].name} "
                          f"is not mentioned in the journal header")

    # completion-journal cross-check: every DONE id appears in the journal corpus
    if J["completion_crosscheck"] and journal_p:
        corpus = read(journal_p)
        if J["archive_dir"] and (root / J["archive_dir"]).exists():
            for p in sorted((root / J["archive_dir"]).glob("*.md")):
                corpus += "\n" + read(p)
        for tid, _ in done_decls:
            if tid not in corpus:
                rep.error(f"NO-JOURNAL completion: {tid} is in DONE but never mentioned in the journal")

    # board rule pack: closed entries with delegations must carry written-back IDs
    if B["delegation_writeback"]:
        for tid, s, block in entry_blocks(active + "\n" + done, rules):
            if s != "x":
                continue
            n_deleg = block.count("Delegation →")
            if n_deleg and len(re.findall(r"ID:\s*(?:\*\*|_)?[A-Z]+-\d+", block)) < n_deleg:
                rep.error(f"DELEGATION without write-back: closed entry {tid} has {n_deleg} "
                          f"delegation(s) but fewer written-back local IDs")

    # docs-verdict rule (HK-6, process/user-docs.md §3): every completion entry newer
    # than docs_verdict_since must record a docs verdict ("docs: <node-ids>" or
    # "docs: none — <why>"). Presence/syntax only — correctness stays judgment (the
    # per-repo manifest conformance test owns everything manifest-aware).
    since = L.get("docs_verdict_since") or ""
    if since:
        date_re = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
        verdict_re = re.compile(r"\bdocs:\s*\S")
        for tid, s, block in entry_blocks(done, rules):
            if s != "x":
                continue
            dates = date_re.findall(block)
            if dates and max(dates) >= since and not verdict_re.search(block):
                rep.error(f"DOCS-VERDICT missing: completion entry {tid} (dated >= "
                          f"{since}) records no docs verdict (process/user-docs.md §3)")

    # claudemd rule: pinned shared blocks present and byte-faithful (hash vs config pin).
    # Fully local — staleness vs commons is a re-pin concern, not a check concern.
    C = cfg["claude"]
    if C["file"] and C["blocks"]:
        ctext = read(root / C["file"])
        if not ctext:
            rep.error(f"CLAUDE-BLOCK: {C['file']} not found or empty")
        else:
            for b in C["blocks"]:
                name, want = b.get("name", "?"), b.get("sha256", "")
                content = find_block(ctext, name)
                if content is None:
                    rep.error(f"CLAUDE-BLOCK missing: no `locveil:begin {name}` … "
                              f"`locveil:end {name}` markers in {C['file']}")
                    continue
                got = block_hash(content)
                if got != want:
                    rep.error(f"CLAUDE-BLOCK drift: '{name}' hash {got[:12]}… != pinned "
                              f"{str(want)[:12]}… (edit in commons + re-pin; never edit in place)")

    # informational summary
    by_pfx: dict[str, list[int]] = {}
    for i, s in all_decls:
        row = by_pfx.setdefault(i.rsplit("-", 1)[0], [0, 0, 0])
        row[0 if s == " " else 1 if s == "x" else 2] += 1
    print("Ledger by prefix (open · done · other):")
    for p in cfg["ledger"]["prefixes"]:
        if p in by_pfx:
            o, d, x = by_pfx[p]
            print(f"  {p:5} {o:>3} · {d:>3} · {x:>3}")
    print(f"  total {len(all_decls)} live tasks (+{len(archive_decls)} archived, "
          f"{len(tombs)} tombstones)\n")
    return rep


# ---------------------------------------------------------------- rotation

def rotate_journal(root: Path, cfg: dict) -> bool:
    J = cfg["journal"]
    if not (J["active"] and J["archive_dir"]):
        print("journal rotation: not configured — skipped")
        return False
    path = root / J["active"]
    text = read(path)
    lines = text.splitlines()
    if len(lines) <= J["high_water"]:
        print(f"journal rotation: {len(lines)} lines <= high-water {J['high_water']} — nothing to do")
        return False
    header, sections = dated_sections(text)
    if len(sections) < 2:
        print("journal rotation: fewer than 2 dated sections — refusing to empty the journal")
        return False

    # freeze oldest WHOLE dated sections (bottom of a newest-on-top file, never split a
    # day) until at or under low-water — keep at least the newest section.
    kept, moved = list(sections), []
    def total(secs: list) -> int:
        return len(header) + sum(len(s[1]) for s in secs)
    while len(kept) > 1 and total(kept) > J["low_water"]:
        moved.insert(0, kept.pop())  # oldest is last; archive stays oldest-first? no —
    if not moved:
        print("journal rotation: nothing movable without splitting a day — skipped")
        return False
    # archive preserves the journal's newest-on-top order among the moved sections
    dates = sorted(d for d, _ in moved)
    adir = root / J["archive_dir"]
    adir.mkdir(parents=True, exist_ok=True)
    aname = f"{dates[0]}_{dates[-1]}.md"
    apath = adir / aname
    if apath.exists():
        print(f"journal rotation: {apath} already exists — refusing to overwrite")
        return False
    moved_sorted = sorted(moved, key=lambda s: s[0], reverse=True)
    body = "\n".join("\n".join(day).rstrip() + "\n" for _, day in moved_sorted)
    apath.write_text(
        f"# Journal archive {dates[0]} … {dates[-1]} (frozen — never re-edit)\n\n" + body,
        encoding="utf-8")

    pointer = f"> Older sections: {J['archive_dir']}/{aname}"
    new_header = list(header)
    insert_at = 1 if new_header and new_header[0].startswith("#") else 0
    new_header.insert(insert_at, pointer)
    new_text = "\n".join(new_header) + "\n" + "\n".join("\n".join(day) for _, day in kept) + "\n"
    path.write_text(new_text, encoding="utf-8")
    print(f"journal rotated: {len(moved)} section(s) → {apath.relative_to(root)}; "
          f"{len(new_text.splitlines())} lines remain")
    return True


def rotate_done(root: Path, cfg: dict, rules: Rules) -> bool:
    L = cfg["ledger"]
    if not (L["done"] and L["archive_dir"]):
        print("DONE rotation: not configured — skipped")
        return False
    path = root / L["done"]
    text = read(path)
    lines = text.splitlines()
    if len(lines) <= L["high_water"]:
        print(f"DONE rotation: {len(lines)} lines <= high-water {L['high_water']} — nothing to do")
        return False

    # move the lowest-numbered completed entries (per prefix) until under low-water;
    # archived declarations stay in the known-ID set via the archive_dir scan.
    blocks = entry_blocks(text, rules)
    order = sorted(blocks, key=lambda b: (b[0].rsplit("-", 1)[0], int(b[0].rsplit("-", 1)[1])))
    to_move: list[str] = []
    remaining = len(lines)
    for tid, _s, block in order:
        if remaining <= L["low_water"] or len(to_move) >= len(blocks) - 1:
            break
        to_move.append(tid)
        remaining -= block.count("\n") + 1
    if not to_move:
        print("DONE rotation: nothing movable — skipped")
        return False

    adir = root / L["archive_dir"]
    adir.mkdir(parents=True, exist_ok=True)
    seq = len(list(adir.glob("*.md"))) + 1
    apath = adir / f"{Path(L['done']).stem}_archive_{seq:03d}.md"
    moved_blocks = [b for b in blocks if b[0] in set(to_move)]
    apath.write_text(
        f"# DONE-ledger archive {seq:03d} (frozen — never re-edit; IDs stay resolvable "
        f"to scope-guard via this directory)\n\n"
        + "\n".join(block.rstrip() for _, _, block in moved_blocks) + "\n",
        encoding="utf-8")

    out_lines, skip = [], False
    move_set = set(to_move)
    for line in lines:
        m = rules.decl.match(line)
        if m:
            skip = m.group(2) in move_set
        elif skip and (line.startswith("- ") or line.startswith("#")):
            skip = False
        if not skip:
            out_lines.append(line)
    path.write_text("\n".join(out_lines).rstrip() + "\n", encoding="utf-8")
    print(f"DONE ledger rotated: {len(to_move)} entrie(s) → {apath.relative_to(root)}; "
          f"{len(out_lines)} lines remain")
    return True


# ---------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(description="Locveil ledger/journal discipline guard")
    ap.add_argument("--config", default=".scope-guard.toml")
    ap.add_argument("--root", default=None, help="repo root (default: config file's directory)")
    ap.add_argument("--check", action="store_true",
                    help="explicit read-only check (the default mode; what hooks and CI run)")
    ap.add_argument("--rotate", nargs="?", const="all", choices=["journal", "done", "all"],
                    help="execute rotation (default mode is a read-only check)")
    ap.add_argument("--hash-blocks", action="store_true",
                    help="print the current hash of every locveil block in [claude].file "
                         "(re-pin helper) and exit")
    ap.add_argument("--version", action="version", version=f"scope-guard {__version__}")
    args = ap.parse_args()
    if args.check and args.rotate:
        ap.error("--check and --rotate are mutually exclusive")

    cfg_path = Path(args.config).resolve()
    if not cfg_path.exists():
        sys.exit(f"FATAL: config not found: {cfg_path}")
    root = Path(args.root).resolve() if args.root else cfg_path.parent
    cfg = load_config(cfg_path)
    rules = Rules(cfg)

    if args.hash_blocks:
        text = read(root / (cfg["claude"]["file"] or "CLAUDE.md"))
        names = re.findall(r"<!-- locveil:begin ([\w-]+)", text)
        if not names:
            print("no locveil blocks found")
            return 1
        for n in names:
            print(f"{n}: {block_hash(find_block(text, n) or '')}")
        return 0

    print(f"== scope-guard {__version__} · root {root} ==\n")

    if args.rotate:
        did = False
        if args.rotate in ("journal", "all"):
            did |= rotate_journal(root, cfg)
        if args.rotate in ("done", "all"):
            did |= rotate_done(root, cfg, rules)
        print()

    rep = check(root, cfg, rules)
    for w in rep.warnings:
        print(f"  ⚠ {w}")
    for e in rep.errors:
        print(f"  ✗ {e}")
    if rep.errors:
        print(f"\nFAIL: {len(rep.errors)} issue(s)"
              + (f", {len(rep.warnings)} warning(s)" if rep.warnings else "")
              + ". Reconcile the ledger.")
        return 1
    print(("\nOK" if not rep.warnings else f"\nOK with {len(rep.warnings)} warning(s)")
          + ": ledger discipline holds.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
