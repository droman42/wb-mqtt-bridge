#!/usr/bin/env python3
"""contract-guard — the Locveil contract-coherence checker (HK-5 / PROD-16).

Layer-1 enforcement from process/contracts.md §4: verifies what is GENERIC and LOCAL
about a repo's contract surfaces — layout, registry, STAMP/PIN shape, hashes of local
pinned copies, version-string consistency. It never checks semantics (that is the
per-repo conformance tests' job, §4 layer 2) and never reaches across repos (pin==tag
bytes is checked at re-pin time by the re-pin flow, not here).

Layout it enforces (process/contracts.md §2, owner ruling: uniform, immediate):

    contracts/
      README.md            the registry: every owned surface + every consumed pin,
                           direction-labeled
      <name>/              OWNED:    README.md + STAMP.json (+ artifacts)
      pins/<name>/         CONSUMED: artifact copies + PIN.json (+ owner STAMP verbatim)

STAMP.json core: {contract, version, tag, date, owner_repo}; tag == "<contract>-v<version>".
PIN.json core:   {contract, version, tag, owner_repo, owner_commit, pinned_by, pin_date,
                  files: {<relpath>: <sha256>}, conformance}.

Legacy tolerance: a PIN.json without a "files" map (pre-convention pin) or a pin folder
without PIN.json degrades to WARNINGS — the strict shape becomes mandatory at the pin's
next re-pin. Everything structural (loose files, unregistered folders, missing owned
STAMP/README, hash mismatches on strict pins) FAILS.

Distribution: locveil-contract-guard, single stdlib file, tags contract-guard-vN,
vendored per consumer at a pinned tag (the scope-guard consumption model). --check only:
this tool never mutates the tree.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

__version__ = "1.1.0"

STAMP_CORE = ("contract", "version", "tag", "date", "owner_repo")
PIN_CORE = ("contract", "version", "tag", "owner_repo", "pin_date")
PIN_RECOMMENDED = ("owner_commit", "pinned_by", "conformance")
META_FILES = {"PIN.json", "README.md"}  # never hash-listed in a pin's files map
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")


class Report:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.warnings: list[str] = []

    def fail(self, msg: str) -> None:
        self.failures.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)


def _load_json(path: Path, rep: Report) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - report, don't crash
        rep.fail(f"UNPARSEABLE: {path} — {exc}")
        return None
    if not isinstance(data, dict):
        rep.fail(f"UNPARSEABLE: {path} — top level must be an object")
        return None
    return data


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _check_version_tag(kind: str, where: str, meta: dict, rep: Report, strict: bool) -> None:
    contract, version, tag = meta.get("contract"), meta.get("version"), meta.get("tag")
    if contract is None or version is None or tag is None:
        return  # missing-core is reported separately
    expected = f"{contract}-v{version}"
    if str(tag) != expected:
        msg = f"VERSION-MISMATCH: {where} — {kind} tag {tag!r} != '{expected}' (contract+version)"
        rep.fail(msg) if strict else rep.warn(msg + " [legacy pin — fix at next re-pin]")


def _local_tag_exists(root: Path, tag: str) -> bool | None:
    """True/False if determinable; None when not a git repo / git unavailable."""
    try:
        out = subprocess.run(["git", "-C", str(root), "tag", "-l", tag],
                             capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    return tag in out.stdout.split()


def check_owned(folder: Path, registry_text: str, rep: Report, root: Path) -> None:
    name = folder.name
    if name not in registry_text:
        rep.fail(f"UNREGISTERED: owned contract '{name}' not mentioned in contracts/README.md")
    if not (folder / "README.md").is_file():
        rep.fail(f"OWNED-NO-README: contracts/{name}/README.md missing (the normative guide)")
    stamp_path = folder / "STAMP.json"
    if not stamp_path.is_file():
        rep.fail(f"OWNED-NO-STAMP: contracts/{name}/STAMP.json missing")
        return
    stamp = _load_json(stamp_path, rep)
    if stamp is None:
        return
    missing = [k for k in STAMP_CORE if k not in stamp]
    if missing:
        rep.fail(f"STAMP-CORE: contracts/{name}/STAMP.json missing {missing}")
    if stamp.get("contract") not in (None, name):
        rep.fail(f"STAMP-NAME: contracts/{name}/STAMP.json says contract={stamp['contract']!r}")
    if "date" in stamp and not DATE_RE.match(str(stamp["date"])):
        rep.fail(f"STAMP-DATE: contracts/{name}/STAMP.json date {stamp['date']!r} not ISO (YYYY-MM-DD…)")
    _check_version_tag("STAMP", f"contracts/{name}/STAMP.json", stamp, rep, strict=True)
    # PROD-22: a STAMP naming a tag that was never created is a false green — the
    # consumer re-pins AGAINST the tag. Local tag object is the bar (remote push is
    # out of scope; a guard can't see the remote).
    tag = stamp.get("tag")
    if tag:
        exists = _local_tag_exists(root, str(tag))
        if exists is False:
            rep.fail(f"TAG-MISSING: contracts/{name}/STAMP.json names '{tag}' but no such "
                     "git tag exists — create the tag in the same change as the STAMP bump")
        elif exists is None:
            rep.warn(f"TAG-UNCHECKED: could not resolve git tags for contracts/{name} "
                     "(not a git repo or git unavailable)")


def check_pin(folder: Path, registry_text: str, rep: Report) -> None:
    name = folder.name
    where = f"contracts/pins/{name}"
    if name not in registry_text:
        rep.fail(f"UNREGISTERED: consumed pin '{name}' not mentioned in contracts/README.md")
    pin_path = folder / "PIN.json"
    if not pin_path.is_file():
        rep.warn(f"PIN-PENDING: {where}/PIN.json missing — legacy/co-owned pin; "
                 "strict PIN.json becomes mandatory at the next re-pin")
        return
    pin = _load_json(pin_path, rep)
    if pin is None:
        return
    strict = isinstance(pin.get("files"), dict)
    missing = [k for k in PIN_CORE if k not in pin]
    if missing:
        msg = f"PIN-CORE: {where}/PIN.json missing {missing}"
        rep.fail(msg) if strict else rep.warn(msg + " [legacy pin — fix at next re-pin]")
    if pin.get("contract") not in (None, name):
        rep.fail(f"PIN-NAME: {where}/PIN.json says contract={pin['contract']!r}")
    _check_version_tag("PIN", f"{where}/PIN.json", pin, rep, strict=strict)
    if not strict:
        rep.warn(f"PIN-LEGACY: {where}/PIN.json has no 'files' hash map — upgrade at next re-pin")
        return
    for rec in PIN_RECOMMENDED:
        if rec not in pin:
            rep.warn(f"PIN-RECOMMENDED: {where}/PIN.json lacks '{rec}'")
    listed = pin["files"]
    for rel, want in listed.items():
        target = folder / rel
        if not target.is_file():
            rep.fail(f"MISSING-PINNED-FILE: {where}/{rel} listed in PIN.json but absent")
            continue
        got = _sha256(target)
        if got != want:
            rep.fail(f"HASH-MISMATCH: {where}/{rel} — sha256 {got[:12]}… != PIN.json {str(want)[:12]}…")
    for child in sorted(folder.iterdir()):
        if child.is_file() and child.name not in META_FILES and child.name not in listed:
            rep.warn(f"UNLISTED-FILE: {where}/{child.name} not covered by PIN.json files map")


def run_check(root: Path) -> Report:
    rep = Report()
    contracts = root / "contracts"
    if not contracts.is_dir():
        return rep  # nothing to guard — a repo without contract surfaces is fine
    registry = contracts / "README.md"
    if not registry.is_file():
        rep.fail("NO-REGISTRY: contracts/README.md missing (the direction-labeled index)")
        registry_text = ""
    else:
        registry_text = registry.read_text(encoding="utf-8")

    for child in sorted(contracts.iterdir()):
        if child.is_file():
            if child.name != "README.md":
                rep.fail(f"LOOSE-FILE: contracts/{child.name} — everything lives in "
                         "contracts/<name>/ or contracts/pins/<name>/ (process/contracts.md §2)")
        elif child.name == "pins":
            for pin_child in sorted(child.iterdir()):
                if pin_child.is_file():
                    rep.fail(f"LOOSE-FILE: contracts/pins/{pin_child.name} — pins live in "
                             "contracts/pins/<name>/ subfolders")
                else:
                    check_pin(pin_child, registry_text, rep)
        else:
            check_owned(child, registry_text, rep, root)
    return rep


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path.cwd(),
                        help="repo root (default: cwd)")
    parser.add_argument("--check", action="store_true",
                        help="run the check (the default and only action)")
    parser.add_argument("--version", action="version",
                        version=f"contract-guard {__version__}")
    args = parser.parse_args(argv)

    rep = run_check(args.root.resolve())
    print(f"== contract-guard {__version__} · root {args.root.resolve()} ==")
    for w in rep.warnings:
        print(f"  WARN  {w}")
    for f in rep.failures:
        print(f"  FAIL  {f}")
    if rep.failures:
        print(f"\nFAIL: {len(rep.failures)} contract-coherence violation(s)"
              f" ({len(rep.warnings)} warning(s)).")
        return 1
    print(f"\nOK: contract coherence holds ({len(rep.warnings)} warning(s)).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
