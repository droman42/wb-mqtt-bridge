#!/usr/bin/env python3
"""Back up the IR ROM banks of a WB-MSW v3 blaster to CSV, before a firmware upgrade wipes them.

WHY: upgrading a WB-MSW v3 firmware WIPES its learned IR ROM banks. This dumps every ROM bank that
HAS CONTENT (and optionally a chosen subset) to CSV (codes base64) so they survive the upgrade and
can be written back with ir_restore.py.

GENERAL PURPOSE: this scans the device itself -- it backs up every non-empty bank regardless of
what (if anything) references it. It has no knowledge of any A/V system, device config, or
scenario. See ir_common.py for the shared register map and the modbus_client wrapper.

RUNS ON THE WB CONTROLLER. It drives the controller-native `modbus_client` CLI (no Python deps) and
needs exclusive bus access, so by default it stops `wb-mqtt-serial` for the duration and restarts
it after.

MECHANISM (per bank N; verified on live hardware -- see ir_common.py for the full register map):
    1. read input reg (5399 + N) -> "ROM<N> size" in bytes (0 = empty bank, skipped).
    2. write holding 5501 = N    -> "BANK -> RAM": copies ROM bank N into the RAM buffer.
    3. read holding 2000..       -> the code: uint16 durations, big-endian, 10 us quanta,
       terminated by repeated 0x0000. Chunked at the 125-reg Modbus read ceiling.
  This is read-only to ROM (load + read only). DANGER: never write coil 5000 (erases all banks);
  this tool never does.

Usage (via the ir.py wrapper; `python3 ir_backup.py ...` works the same):
    # quick inventory -- which banks have content, sizes only, no code dump:
    sudo python3 ir.py backup wb-msw-v3_207 --port /dev/ttyRS485-2 --sizes-only

    # full backup of every non-empty bank (one service-stop window for all blasters):
    sudo python3 ir.py backup wb-msw-v3_207 wb-msw-v3_218 wb-msw-v3_220 --port /dev/ttyRS485-2

    # restrict to specific banks:
    sudo python3 ir.py backup wb-msw-v3_207 --banks 5,6,65-70 --port /dev/ttyRS485-2
"""
from __future__ import annotations

import argparse
import csv
import math
import re
import sys
from pathlib import Path

import ir_common as ir


def derive_slave_address(blaster: str) -> int:
    """WB auto-names modules `wb-msw-v3_<modbus-address>`; the numeric suffix IS the slave addr."""
    m = re.search(r"_(\d+)$", blaster)
    if not m:
        raise SystemExit(f"Cannot derive Modbus address from blaster name {blaster!r} "
                         f"(expected a trailing _<number>, e.g. wb-msw-v3_207).")
    return int(m.group(1))


CSV_FIELDS = ["blaster", "modbus_address", "rom", "code_size_bytes", "code_base64", "status"]


def backup_blaster(blaster: str, banks: list[int], call, out_dir: Path, sizes_only: bool) -> Path | None:
    slave = derive_slave_address(blaster)
    rows = []
    for bank in banks:
        try:
            size = ir.read_size(call, bank)
        except Exception as e:  # one bad bank shouldn't abort the whole backup
            print(f"  ROM{bank:<3} SIZE-ERROR: {e}", file=sys.stderr)
            continue
        if size == 0:
            continue  # empty/unused bank -- nothing to back up
        if sizes_only:
            print(f"  ROM{bank:<3} {size:>4} bytes")
            rows.append({"blaster": blaster, "modbus_address": slave, "rom": bank,
                         "code_size_bytes": size, "code_base64": "", "status": "size-only"})
            continue
        try:
            vals = ir.read_bank(call, bank, math.ceil(size / 2))
            b64 = ir.regs_to_b64(vals, size)
            status = "ok" if b64 else "EMPTY"
            print(f"  ROM{bank:<3} {status:5} {size:>4} bytes")
        except Exception as e:
            b64, status = "", f"ERROR: {e}"
            print(f"  ROM{bank:<3} {status}", file=sys.stderr)
        rows.append({"blaster": blaster, "modbus_address": slave, "rom": bank,
                     "code_size_bytes": size, "code_base64": b64, "status": status})

    if not rows:
        print(f"  (no non-empty banks on {blaster})")
        return None
    out = out_dir / f"ir_backup_{blaster}.csv"
    with out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        w.writeheader()
        w.writerows(rows)
    ok = sum(1 for r in rows if r["status"] == "ok")
    captured = "inventoried" if sizes_only else f"{ok}/{len(rows)} captured"
    print(f"  -> {out}  ({len(rows)} non-empty bank(s); {captured})")
    return out


def add_arguments(parser) -> None:
    parser.add_argument("blasters", nargs="+",
                        help="blaster name(s), e.g. wb-msw-v3_207 (suffix = Modbus slave)")
    parser.add_argument("--out-dir", type=Path, default=Path.cwd(),
                        help="dir for ir_backup_<blaster>.csv files (default: cwd)")
    ir.add_bus_args(parser)
    parser.add_argument("--banks", help=f"banks to scan, comma/range (e.g. 5,6,65-70); "
                                        f"default all {ir.BANK_MIN}-{ir.BANK_MAX}")
    parser.add_argument("--sizes-only", action="store_true",
                        help="inventory only: report which banks have content + sizes, do not dump codes")
    ir.add_service_arg(parser)


def run(args) -> int:
    banks = sorted(ir.parse_banks(args.banks)) if args.banks else list(range(ir.BANK_MIN, ir.BANK_MAX + 1))
    if not args.out_dir.is_dir():
        raise SystemExit(f"--out-dir not found: {args.out_dir}")

    for blaster in args.blasters:
        print(f"{blaster}: Modbus slave {derive_slave_address(blaster)}; "
              f"scanning banks {banks[0]}-{banks[-1]} ({len(banks)} bank(s))")

    with ir.bus_window(not args.no_toggle_service):
        for blaster in args.blasters:
            print(f"--- {blaster} ---")
            call = ir.caller_for(args, derive_slave_address(blaster))
            backup_blaster(blaster, banks, call, args.out_dir, args.sizes_only)
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_arguments(ap)
    raise SystemExit(run(ap.parse_args()))
