#!/usr/bin/env python3
"""Restore WB-MSW v3 IR ROM banks from an ir_backup_*.csv, after a firmware upgrade wiped them.

*** THIS WRITES THE DEVICE'S FLASH. *** It is the reverse of ir_backup.py. It reads the CSV(s)
produced by ir_backup.py, decodes each bank's base64 code back into IR durations, writes it into
the corresponding ROM bank, then reads it back and verifies. General purpose: no A/V knowledge.
See ir_common.py for the shared register map and the modbus_client wrapper.

RUNS ON THE WB CONTROLLER. Drives the controller-native `modbus_client` CLI (no Python deps) and
needs exclusive bus access, so by default it stops `wb-mqtt-serial` for the duration.

SAFETY:
  * It is a DRY RUN unless you pass --confirm. Without --confirm it only parses the CSV, decodes
    every code, and prints the plan -- it touches no hardware.
  * Every bank is read back and compared after writing; on a mismatch it STOPS (unless --keep-going).
  * Verify is jitter-tolerant (--tol quanta): learned multi-repeat codes carry per-repeat capture
    jitter, so an exact compare reports false mismatches (see ir_common.compare). Lengths must
    still match exactly; pass --tol 0 for a strict byte-exact verify.

MECHANISM (per bank N; verified on live hardware -- see ir_common.py for the full register map):
    1. write coil (5199 + N) = 1   -> enter edit mode (copies the current ROM bank into RAM)
    2. wait --settle seconds        (let the ROM->RAM copy settle; the official WB script uses 20)
    3. write holding 2000+          -> the code: uint16 durations, big-endian, terminated by
       0x0000 0x0000. Written in <=121-reg chunks.
    4. write coil (5199 + N) = 0   -> COMMITS RAM->ROM (persists the bank).
  Read-back for verification uses the non-committing BANK->RAM loader (holding 5501 = N).
  A bank left in edit mode LOCKS the whole blaster's playback, so write_bank GUARANTEES an
  edit-exit on failure and a preflight clears any bank a prior run left stuck (clear_stuck_edit).
  DANGER: never write coil 5000 ("Reset all ROM"). This tool never does.

Usage (via the ir.py wrapper; `python3 ir_restore.py ...` works the same):
    # dry run -- decode + show the plan, no hardware (safe anywhere):
    python3 ir.py restore ir_backup_wb-msw-v3_220.csv

    # real restore on the WB controller (writes flash):
    sudo python3 ir.py restore ir_backup_wb-msw-v3_220.csv --port /dev/ttyRS485-2 --confirm

    # restrict to specific banks:
    sudo python3 ir.py restore ir_backup_wb-msw-v3_207.csv --only-rom 5,6 --confirm
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

import ir_common as ir

VERIFY_READ_TRIES = 6        # read-back after a large-code commit can be transiently wrong; retry
WRITE_RETRIES = 4            # RAM/commit writes can transiently NAK ("Slave Device Busy") right
                             # after a large write; retry before giving up


def _write(call, func: str, addr: int, vals, tries: int = WRITE_RETRIES, delay: float = 0.5):
    """Write (coil/holding) with retry. The WB-MSW transiently returns 'Slave Device Busy'
    right after a large RAM write, so a single attempt at the commit can spuriously fail."""
    out = ""
    for _ in range(tries):
        out = call(func, addr, write_vals=vals)
        if ir.ok(out):
            return out
        time.sleep(delay)
    raise RuntimeError(f"{func} @ {addr} (={vals}) failed after {tries} tries: {out.strip()[:120]}")


def write_bank(call, bank: int, buf: list[int], settle: float) -> None:
    """enter edit (coil 5199+N=1) -> write RAM in chunks -> commit (coil 5199+N=0).

    A bank left in edit mode LOCKS the blaster's entire playback ('Play from ROM' then returns
    Slave Device Busy for *every* bank). So this guarantees the bank leaves edit mode even when a
    write fails: on error it reloads the committed ROM back into RAM and commits, exiting edit with
    the bank's *prior* content intact rather than persisting a partial write or leaving it locked.
    """
    coil = ir.COIL_EDIT_BASE + bank
    _write(call, "0x05", coil, [1])                 # enter edit (retried)
    committed = False
    try:
        time.sleep(settle)
        off = 0
        while off < len(buf):
            chunk = buf[off:off + ir.MAX_WRITE_REGS]
            _write(call, "0x10", ir.REG_RAM_BASE + off, chunk)
            off += len(chunk)
        time.sleep(1)                               # let the RAM write settle before committing
        _write(call, "0x05", coil, [0])             # commit RAM->ROM (retried; transient busy after big writes)
        committed = True
    finally:
        if not committed:
            # Never leave the bank locked in edit mode: reload committed ROM -> RAM, then commit,
            # so we exit edit with the prior content (best-effort; preflight clears any residue).
            for _ in range(WRITE_RETRIES):
                try:
                    call("0x06", ir.REG_BANK_TO_RAM, write_vals=[bank])
                    if ir.ok(call("0x05", coil, write_vals=[0])):
                        break
                except Exception:
                    pass
                time.sleep(0.5)
    time.sleep(2)


def clear_stuck_edit(call) -> list[int]:
    """Clear any bank left in edit mode (coil 5199+N=1) by a prior failed/interrupted run -- a
    single stuck edit coil locks the whole blaster's playback. Reads banks 1-80 in one frame, then
    for each stuck bank reloads the committed ROM and commits (exits edit, prior content intact).
    Returns the banks it cleared."""
    regs = ir.parse_regs(call("0x01", ir.COIL_EDIT_BASE + 1, count=ir.BANK_MAX)) or []
    cleared = []
    for i, v in enumerate(regs):
        if v == 1:
            bank = i + 1
            call("0x06", ir.REG_BANK_TO_RAM, write_vals=[bank])     # reload ROM->RAM
            call("0x05", ir.COIL_EDIT_BASE + bank, write_vals=[0])  # commit (exit edit)
            cleared.append(bank)
    return cleared


def load_rows(csv_paths: list[Path], only_rom: set[int] | None):
    """Yield restorable plan entries from the backup CSV(s)."""
    plan = []
    for path in csv_paths:
        with path.open() as fh:
            for row in csv.DictReader(fh):
                rom = int(row["rom"])
                if only_rom is not None and rom not in only_rom:
                    continue
                if row["status"] != "ok" or not row["code_base64"]:
                    print(f"  skip {row['blaster']} ROM{rom}: status={row['status']!r}")
                    continue
                regs = ir.b64_to_regs(row["code_base64"])
                nbytes = int(row["code_size_bytes"])
                if len(regs) * 2 not in (nbytes, nbytes + 1):
                    print(f"  ! {row['blaster']} ROM{rom}: decoded {len(regs)*2}B != csv {nbytes}B",
                          file=sys.stderr)
                buf = ir.with_terminator(regs)
                plan.append({
                    "blaster": row["blaster"], "slave": int(row["modbus_address"]),
                    "rom": rom, "buf": buf, "expected": ir.code_part(buf), "nbytes": nbytes,
                })
    return plan


def add_arguments(parser) -> None:
    parser.add_argument("csv", nargs="+", type=Path, help="ir_backup_<blaster>.csv file(s) to restore from")
    ir.add_bus_args(parser)
    parser.add_argument("--settle", type=float, default=20.0,
                        help="seconds to wait after entering edit mode (official WB script uses 20)")
    parser.add_argument("--tol", type=int, default=ir.JITTER_TOL,
                        help=f"per-register verify tolerance in 10us quanta (default {ir.JITTER_TOL}; "
                             f"0 = strict byte-exact)")
    parser.add_argument("--only-rom", help="restrict to these ROM numbers, comma/range (e.g. 5,6,65-70)")
    parser.add_argument("--confirm", action="store_true",
                        help="actually WRITE FLASH. Without this the script is a dry run.")
    parser.add_argument("--keep-going", action="store_true",
                        help="continue to remaining banks after a verify mismatch (default: stop)")
    ir.add_service_arg(parser)


def run(args) -> int:
    for p in args.csv:
        if not p.is_file():
            raise SystemExit(f"CSV not found: {p}")
    only_rom = ir.parse_banks(args.only_rom) if args.only_rom else None

    print("Parsing + decoding CSV ...")
    plan = load_rows(args.csv, only_rom)
    if not plan:
        print("Nothing to restore.")
        return 0
    print(f"\n{len(plan)} bank(s) to restore:")
    for e in plan:
        print(f"  {e['blaster']} (slave {e['slave']}) ROM{e['rom']:<3} {e['nbytes']:>4}B")

    if not args.confirm:
        print("\nDRY RUN -- no hardware touched. Re-run with --confirm to write flash.")
        return 0

    failures = 0
    restored = 0
    attempted = 0
    with ir.bus_window(not args.no_toggle_service):
        # Preflight: clear any bank left in edit mode by a prior failed/interrupted run -- a stuck
        # edit coil locks the blaster's entire playback (every Play -> Slave Device Busy).
        for slave in sorted({e["slave"] for e in plan}):
            stuck = clear_stuck_edit(ir.caller_for(args, slave))
            if stuck:
                print(f"  preflight: slave {slave} had bank(s) {stuck} stuck in edit mode -> cleared")
        for e in plan:
            attempted += 1
            call = ir.caller_for(args, e["slave"])
            try:
                write_bank(call, e["rom"], e["buf"], args.settle)
                # A read-back immediately after committing a LARGE code can return transient
                # garbage for several seconds (the commit is correct, but the next read or two come
                # back wrong). So retry the verify read, spaced out, before declaring a mismatch.
                rep = None
                for _ in range(VERIFY_READ_TRIES):
                    got = ir.code_part(ir.read_bank(call, e["rom"], len(e["expected"]) + 4))
                    rep = ir.compare(e["expected"], got, args.tol)
                    if rep["match"]:
                        break
                    time.sleep(3)
                if rep["match"]:
                    restored += 1
                    note = "exact" if rep["exact"] else f"~jitter maxdev={rep['max_dev']} over {rep['n_diff']} reg(s)"
                    print(f"  {e['blaster']} ROM{e['rom']:<3} OK   ({e['nbytes']}B verified, {note})")
                else:
                    failures += 1
                    print(f"  {e['blaster']} ROM{e['rom']:<3} VERIFY MISMATCH "
                          f"(exp {rep['exp_len']} regs, got {rep['got_len']}, "
                          f"maxdev={rep['max_dev']} > tol {args.tol})", file=sys.stderr)
                    if not args.keep_going:
                        print("  stopping (use --keep-going to continue past mismatches)", file=sys.stderr)
                        break
            except Exception as ex:
                failures += 1
                print(f"  {e['blaster']} ROM{e['rom']:<3} ERROR: {ex}", file=sys.stderr)
                if not args.keep_going:
                    break
    skipped = len(plan) - attempted
    print(f"\nDone: {restored}/{len(plan)} restored & verified"
          + (f"; {failures} FAILED" if failures else "")
          + (f"; {skipped} not attempted" if skipped else "") + ".")
    return 1 if failures else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_arguments(ap)
    raise SystemExit(run(ap.parse_args()))
