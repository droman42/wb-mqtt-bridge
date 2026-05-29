#!/usr/bin/env python3
"""Read-only: verify every captured bank in a backup CSV against what's stored on the device now.

A definitive post-restore check, independent of ir_restore.py's in-run verify. It is READ-ONLY --
it loads each bank via the non-committing BANK->RAM loader and reads it back; it never writes flash
and never touches an edit coil. General purpose: no A/V knowledge. See ir_common.py for the shared
register map and the modbus_client wrapper.

The compare is jitter-tolerant (--tol quanta). WB-MSW learns IR by *capturing* a remote's pulses,
and multi-repeat frames (long ld_player/vhs codes) carry per-repeat capture jitter of a few 10 us
quanta, so the stored copy can differ from the backup by +-~3 quanta without being corrupt. Each
bank is reported as EXACT, ~jitter (within tol), or MISMATCH; a mismatch prints a first-diff dump
to characterise it (transform vs corruption). Pass --tol 0 for a strict byte-exact verify.

RUNS ON THE WB CONTROLLER. Needs exclusive bus access, so by default it stops wb-mqtt-serial.

Usage (via the ir.py wrapper; `python3 ir_verify.py ...` works the same):
    sudo python3 ir.py verify ir_backup_wb-msw-v3_207.csv --port /dev/ttyRS485-2
    sudo python3 ir.py verify ir_backup_wb-msw-v3_207.csv --only-rom 65-70 --detail
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

import ir_common as ir

VERIFY_READ_TRIES = 6        # read-back right after a large-code commit can be transiently wrong


def load_rows(csv_paths: list[Path], only_rom: set[int] | None):
    plan = []
    for path in csv_paths:
        with path.open() as fh:
            for row in csv.DictReader(fh):
                if row["status"] != "ok" or not row["code_base64"]:
                    continue
                rom = int(row["rom"])
                if only_rom is not None and rom not in only_rom:
                    continue
                expected = ir.code_part(ir.with_terminator(ir.b64_to_regs(row["code_base64"])))
                plan.append({"blaster": row["blaster"], "slave": int(row["modbus_address"]),
                             "rom": rom, "expected": expected})
    return plan


def add_arguments(parser) -> None:
    parser.add_argument("csv", nargs="+", type=Path, help="ir_backup_<blaster>.csv file(s) to verify against")
    ir.add_bus_args(parser)
    parser.add_argument("--tol", type=int, default=ir.JITTER_TOL,
                        help=f"per-register tolerance in 10us quanta (default {ir.JITTER_TOL}; 0 = byte-exact)")
    parser.add_argument("--only-rom", help="restrict to these ROM numbers, comma/range (e.g. 65-70)")
    parser.add_argument("--detail", action="store_true", help="print a first-diff dump for every non-exact bank")
    ir.add_service_arg(parser)


def run(args) -> int:
    for p in args.csv:
        if not p.is_file():
            raise SystemExit(f"CSV not found: {p}")
    only_rom = ir.parse_banks(args.only_rom) if args.only_rom else None
    plan = load_rows(args.csv, only_rom)
    if not plan:
        print("Nothing to verify.")
        return 0

    exact = jitter = bad = 0
    with ir.bus_window(not args.no_toggle_service):
        for e in plan:
            call = ir.caller_for(args, e["slave"])
            rep = got = None
            for _ in range(VERIFY_READ_TRIES):
                got = ir.code_part(ir.read_bank(call, e["rom"], len(e["expected"]) + 8))
                rep = ir.compare(e["expected"], got, args.tol)
                if rep["match"]:
                    break
                time.sleep(3)
            if rep["exact"]:
                exact += 1
                print(f"  {e['blaster']} ROM{e['rom']:<3} EXACT    ({rep['exp_len']} regs)")
            elif rep["match"]:
                jitter += 1
                print(f"  {e['blaster']} ROM{e['rom']:<3} ~jitter  "
                      f"(maxdev={rep['max_dev']} <= tol {args.tol} over {rep['n_diff']} reg(s))")
                if args.detail:
                    print(ir.diff_detail(e["expected"], got))
            else:
                bad += 1
                print(f"  {e['blaster']} ROM{e['rom']:<3} MISMATCH "
                      f"(exp {rep['exp_len']} regs, got {rep['got_len']}, maxdev={rep['max_dev']} > tol {args.tol})",
                      file=sys.stderr)
                print(ir.diff_detail(e["expected"], got), file=sys.stderr)
    total = exact + jitter + bad
    print(f"\nVerified {exact + jitter}/{total} banks match the backup "
          f"({exact} exact, {jitter} within jitter tol {args.tol})"
          + (f"; {bad} MISMATCH" if bad else "") + ".")
    return 1 if bad else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_arguments(ap)
    raise SystemExit(run(ap.parse_args()))
