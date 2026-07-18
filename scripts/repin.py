#!/usr/bin/env python3
"""repin — consumed-contract re-pin + staleness check (HK-12/PROD-26).

The org-wide promotion of locveil-voice's BUILD-24 engine: each consumed contract family
declared in the repo's `.repin.toml` is fetched from its OWNER repo's committed artifacts
at a family-named tag (`<family>-vN`), copied verbatim into the pin folder(s), and stamped
with a strict `PIN.json` (core fields + `files` sha256 map + conformance pointer) that the
vendored contract-guard verifies on every commit.

    python3 repin.py <family> [--tag TAG]      re-pin (default: the owner's newest tag)
    python3 repin.py --check [--fail-on X]     staleness report; exit per severity

Severity (process/contracts.md §5, the HK-12 ladder) is the caller's choice of --fail-on:
    none   pre-commit warn stage — always exit 0
    major  ordinary CI — exit 1 only on a MAJOR-version gap or a never-pinned family
    any    release gates / touch-the-family workflows — exit 1 on any staleness
The config's `default_fail_on` applies when the flag is omitted.

Tag lookup is REMOTE-FIRST via tokenless `git ls-remote --tags <owner_url>` (the org repos
are public — recorded HK-12 assumption); on network failure it falls back to the on-disk
sibling's tags with a WARN carrying fetch age. Never network-required-to-commit. A family
with no tag yet: re-pin pins at the owner's `main` (tag/version null); `--check` does a
byte-drift check against the sibling when one is on disk, else skips with a warning.

Re-pinning WRITES and therefore requires the owner sibling on disk. Cross-repo dest
writes are legal ONLY into ../locveil-commons (co-owned ground — HK-12 ruling); a family
marked `check_only` (a pin another repo's re-pin flow stamps) is checked, never written.

`[[tool]]` entries are the vendored-tools manifest (HK-12, satellite's rule): the recorded
`pinned_tag` of a vendored script (scope-guard, contract-guard, repin itself) is checked
against the owner's newest family tag with the same severity ladder.

Distribution: locveil-repin, single stdlib file, tags repin-vN, vendored per consumer at a
pinned tag (the scope-guard consumption model) + a repo-local `.repin.toml`.
"""

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

import tomllib

__version__ = "1.0.0"

LS_REMOTE_TIMEOUT = 10  # seconds; a hook must stay fast even on a flaky network


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True, check=True).stdout.strip()


def _git_bytes(repo: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, check=True).stdout


def _version_of(family: str, tag: str) -> tuple[int, ...] | None:
    m = re.fullmatch(rf"{re.escape(family)}-v(\d+(?:\.\d+)*)", tag)
    return tuple(int(x) for x in m.group(1).split(".")) if m else None


def _newest(tags, family: str) -> str | None:
    versioned = [t for t in tags if _version_of(family, t)]
    return max(versioned, key=lambda t: _version_of(family, t)) if versioned else None


def _remote_tags(url: str) -> set[str] | None:
    try:
        out = subprocess.run(["git", "ls-remote", "--tags", url],
                             capture_output=True, text=True, check=True,
                             timeout=LS_REMOTE_TIMEOUT).stdout
    except (subprocess.SubprocessError, OSError):
        return None
    tags = set()
    for line in out.splitlines():
        ref = line.split("\t")[-1]
        if ref.startswith("refs/tags/"):
            tags.add(ref[len("refs/tags/"):].removesuffix("^{}"))
    return tags


def _fetch_age(repo: Path) -> str:
    fetch_head = repo / ".git" / "FETCH_HEAD"
    try:
        days = (time.time() - fetch_head.stat().st_mtime) / 86400
        return f"fetched ~{days:.0f}d ago"
    except OSError:
        return "fetch age unknown"


def _newest_tag(spec: dict, root: Path, family: str) -> tuple[str | None, str]:
    """Resolve the owner's newest family tag, remote-first.

    Returns (tag_or_None, source_note); source_note is "" for a clean remote answer,
    a WARN string when degraded (stale-clone fallback / no source at all).
    """
    url = spec.get("owner_url")
    if url:
        tags = _remote_tags(url)
        if tags is not None:
            return _newest(tags, family), ""
    owner_dir = spec.get("owner_dir")
    if owner_dir:
        owner = (root / owner_dir).resolve()
        if owner.is_dir():
            try:
                tags = set(_git(owner, "tag", "-l", f"{family}-v*").splitlines())
            except subprocess.CalledProcessError:
                return None, f"WARN: {family}: sibling {owner} is not a git repo"
            note = ("" if not url else
                    f"WARN: {family}: remote unreachable — using on-disk tags of {owner} "
                    f"({_fetch_age(owner)}); a stale clone under-reports")
            return _newest(tags, family), note
    return None, f"WARN: {family}: no tag source (remote unreachable, no sibling on disk)"


# ---------------------------------------------------------------- config


def load_config(path: Path) -> dict:
    cfg = tomllib.loads(path.read_text(encoding="utf-8"))
    root = path.resolve().parent
    for fam in cfg.get("family", []):
        for key in ("name", "owner_repo", "files"):
            if key not in fam:
                raise SystemExit(f"config error: [[family]] missing '{key}'")
        for dest in fam.get("dest", []):
            p = dest.get("path", "")
            if p.startswith(".."):
                target = (root / p).resolve()
                commons = (root / "../locveil-commons").resolve()
                if not str(target).startswith(str(commons)):
                    raise SystemExit(
                        f"config error: family '{fam['name']}' dest '{p}' writes outside "
                        "this repo — cross-repo dest writes are legal ONLY into "
                        "../locveil-commons (HK-12)")
    for tool in cfg.get("tool", []):
        for key in ("name", "family", "pinned_tag"):
            if key not in tool:
                raise SystemExit(f"config error: [[tool]] missing '{key}'")
    return cfg


# ---------------------------------------------------------------- re-pin


def repin(cfg: dict, root: Path, family: str, tag: str | None) -> int:
    spec = next((f for f in cfg.get("family", []) if f["name"] == family), None)
    if spec is None:
        print(f"error: family '{family}' not in config")
        return 2
    if spec.get("check_only"):
        print(f"error: family '{family}' is check_only — its pin is stamped by "
              f"{spec.get('managed_by', 'another repo')}'s re-pin flow, never here")
        return 2
    owner_dir = spec.get("owner_dir")
    owner = (root / owner_dir).resolve() if owner_dir else None
    if owner is None or not owner.is_dir():
        print(f"error: re-pinning needs the owner sibling on disk ({owner_dir}) — "
              "repin writes bytes, ls-remote cannot")
        return 2

    tag = tag or _newest(set(_git(owner, "tag", "-l", f"{family}-v*").splitlines()), family)
    ref = tag or "main"
    if tag:
        version = ".".join(str(x) for x in _version_of(family, tag))
    else:
        version = None
        print(f"note: {spec['owner_repo']} has no {family}-v* tag yet — pinning at main "
              "(version/tag stay null until the owner stamps)")
    owner_commit = _git(owner, "rev-parse", f"{ref}^{{commit}}")

    blobs: dict[str, bytes] = {}
    files: dict[str, str] = {}
    mirrored: dict[str, object] = {}
    for path in spec["files"]:
        blob = _git_bytes(owner, "show", f"{ref}:{path}")
        name = path.rsplit("/", 1)[-1]
        blobs[name] = blob
        files[name] = hashlib.sha256(blob).hexdigest()
        if name == "STAMP.json" and spec.get("mirror"):
            stamp = json.loads(blob)
            mirrored = {k: stamp[k] for k in spec["mirror"] if k in stamp}
        print(f"  {name}  {files[name][:12]}…  ({spec['owner_repo']} @ {ref})")

    for dest_spec in spec.get("dest", []):
        dest = (root / dest_spec["path"]).resolve()
        dest.mkdir(parents=True, exist_ok=True)
        for name, blob in blobs.items():
            (dest / name).write_bytes(blob)
        pin = {"contract": family, "version": version, "tag": tag,
               "owner_repo": spec["owner_repo"], "owner_commit": owner_commit,
               "pinned_by": cfg.get("repin", {}).get("pinned_by", "repin.py"),
               "pin_date": date.today().isoformat(),
               **mirrored,
               "files": files, "conformance": dest_spec.get("conformance")}
        (dest / "PIN.json").write_text(json.dumps(pin, indent=2, ensure_ascii=False) + "\n",
                                       encoding="utf-8")
        print(f"pinned {family} @ {ref} → {dest}")
        if dest_spec.get("conformance"):
            print(f"  conformance: {dest_spec['conformance']}")
    return 0


# ---------------------------------------------------------------- check

# classification order of badness; MAJOR-level classes fail under --fail-on=major
_MAJOR_CLASSES = ("stale-major", "never-pinned")
_ANY_CLASSES = _MAJOR_CLASSES + ("stale-minor", "drifted", "unknown")


def _classify(family: str, pinned_tag: str | None, newest: str | None) -> str:
    if newest is None:
        return "ok"  # untagged family freshness handled separately (drift path)
    if pinned_tag is None:
        return "stale-minor"  # pinned-at-main while the owner has since tagged
    if pinned_tag == newest:
        return "ok"
    old, new = _version_of(family, pinned_tag), _version_of(family, newest)
    if old is None or new is None or old[0] != new[0]:
        return "stale-major"
    return "stale-minor"


def check(cfg: dict, root: Path, fail_on: str, only: str | None) -> int:
    findings: list[tuple[str, str]] = []  # (class, message)

    def note(cls: str, msg: str) -> None:
        findings.append((cls, msg))
        prefix = {"ok": "  ok   ", "unknown": "  WARN "}.get(cls, "  STALE")
        print(f"{prefix} {msg}")

    for spec in cfg.get("family", []):
        family = spec["name"]
        if only and family != only:
            continue
        newest, warn = _newest_tag(spec, root, family)
        if warn:
            print(f"  {warn}")
        for dest_spec in spec.get("dest", []):
            dest = (root / dest_spec["path"]).resolve()
            where = f"{family} ({dest_spec['path']})"
            pin_path = dest / "PIN.json"
            if not pin_path.is_file():
                note("never-pinned", f"{where}: no PIN.json — never pinned")
                continue
            pin = json.loads(pin_path.read_text(encoding="utf-8"))
            if newest is None and warn:
                note("unknown", f"{where}: freshness unknown — no tag source")
                continue
            if newest is None:
                # untagged family: byte-drift check against the sibling when present
                owner_dir = spec.get("owner_dir")
                owner = (root / owner_dir).resolve() if owner_dir else None
                if owner is None or not owner.is_dir():
                    note("unknown", f"{where}: untagged family, no sibling — skipped")
                    continue
                drifted = [p.rsplit("/", 1)[-1] for p in spec["files"]
                           if hashlib.sha256(_git_bytes(owner, "show", f"main:{p}")).hexdigest()
                           != pin.get("files", {}).get(p.rsplit("/", 1)[-1])]
                if drifted:
                    note("drifted", f"{where}: owner's committed {', '.join(drifted)} no "
                                    f"longer matches the pin — run repin.py {family}")
                else:
                    note("ok", f"{where}: untagged, bytes match owner main")
                continue
            cls = _classify(family, pin.get("tag"), newest)
            if cls == "ok":
                note("ok", f"{where}: {newest}")
            else:
                note(cls, f"{where}: pinned {pin.get('tag') or 'untagged'}, owner's newest "
                          f"is {newest} — run repin.py {family}")

    for tool in cfg.get("tool", []):
        family = tool["family"]
        if only and tool["name"] != only:
            continue
        newest, warn = _newest_tag(tool, root, family)
        if warn:
            print(f"  {warn}")
        where = f"tool {tool['name']} (vendored @ {tool['pinned_tag']})"
        if newest is None:
            note("unknown", f"{where}: freshness unknown — no tag source")
            continue
        cls = _classify(family, tool["pinned_tag"], newest)
        if cls == "ok":
            note("ok", f"{where}: current")
        else:
            note(cls, f"{where}: owner's newest is {newest} — re-vendor via a ledger task")

    bad_classes = {"none": (), "major": _MAJOR_CLASSES, "any": _ANY_CLASSES}[fail_on]
    bad = [m for cls, m in findings if cls in bad_classes]
    stale = [m for cls, m in findings if cls != "ok"]
    if bad:
        print(f"\nSTALE (fail-on={fail_on}): {len(bad)} finding(s). The fix is a "
              "deliberate re-pin ledger task, never an auto-fetch.")
        return 1
    if stale:
        print(f"\nOK under fail-on={fail_on} — {len(stale)} warning(s) above.")
        return 0
    print("\nOK: every pin and vendored tool is at its owner's newest version.")
    return 0


# ---------------------------------------------------------------- CLI


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[1])
    parser.add_argument("family", nargs="?", help="consumed contract family to re-pin")
    parser.add_argument("--tag", help="owner tag to pin (default: newest family tag)")
    parser.add_argument("--check", action="store_true",
                        help="staleness report; exit per --fail-on")
    parser.add_argument("--fail-on", choices=["none", "major", "any"],
                        help="severity gate (default: config default_fail_on, else 'any')")
    parser.add_argument("--family", dest="only", metavar="NAME",
                        help="with --check: restrict to one family/tool")
    parser.add_argument("--config", default=".repin.toml", type=Path,
                        help="config path (default: ./.repin.toml)")
    parser.add_argument("--version", action="version", version=f"repin {__version__}")
    args = parser.parse_args(argv)

    if not args.config.is_file():
        print(f"error: no config at {args.config}")
        return 2
    cfg = load_config(args.config)
    root = args.config.resolve().parent

    if args.check:
        if args.family or args.tag:
            parser.error("--check takes --family/--fail-on only")
        fail_on = args.fail_on or cfg.get("repin", {}).get("default_fail_on", "any")
        return check(cfg, root, fail_on, args.only)
    if not args.family:
        parser.error("give a family to re-pin, or --check")
    return repin(cfg, root, args.family, args.tag)


if __name__ == "__main__":
    sys.exit(main())
