#!/usr/bin/env python3
"""Restore WB-MSW v3 IR ROM banks from an ir_backup_*.csv, after a firmware upgrade wiped them.

*** THIS WRITES THE DEVICE'S FLASH. *** It is the reverse of ir_backup.py. It reads the CSV(s)
produced by ir_backup.py, decodes each bank's base64 code back into IR durations, and writes it
into the corresponding ROM bank, then reads it back and verifies byte-for-byte.

RUNS ON THE WB CONTROLLER. Drives the controller-native `modbus_client` CLI (no Python deps) and
needs exclusive bus access, so by default it stops `wb-mqtt-serial` for the duration.

SAFETY:
  * It is a DRY RUN unless you pass --confirm. Without --confirm it only parses the CSV, decodes
    every code, and prints the plan -- it touches no hardware.
  * Every bank is read back and compared after writing; on a mismatch it STOPS (unless --keep-going).
  * Intended to run on banks that the firmware upgrade has emptied. Writing over an existing code
    is still safe (the device delimits a code by its 0x0000 0x0000 terminator), but verify-on-write
    is your guarantee either way.

MECHANISM (verified on live WB-MSW v3 hardware; same per-bank edit coil for ALL banks 1-80, even
though the wb-mqtt-serial template only exposes coils 5200-5231):
  For ROM bank N:
    1. write coil (5199 + N) = 1   -> enter edit mode (copies the current ROM bank into RAM)
    2. wait --settle seconds        (let the ROM->RAM copy settle; the official WB script uses 20)
    3. write holding regs 2000+     -> the code: uint16 durations, big-endian, 10us quanta,
       terminated by 0x0000 0x0000. Written in <=121-reg chunks (Modbus 0x10 limit is 123).
    4. write coil (5199 + N) = 0   -> COMMITS RAM->ROM (persists the bank).
  Read-back for verification uses the non-committing BANK->RAM loader (holding 5501 = N) + reads.
  DANGER: never write coil 5000 ("Reset all ROM" -- erases every bank). This script never does.

Usage:
    # dry run -- decode + show the plan, no hardware (safe anywhere):
    python3 ir_restore.py ir_backup_wb-msw-v3_220.csv

    # real restore on the WB controller (writes flash):
    sudo python3 ir_restore.py ir_backup_wb-msw-v3_220.csv --port /dev/ttyRS485-2 --confirm

    # restrict to specific banks:
    sudo python3 ir_restore.py ir_backup_wb-msw-v3_207.csv --only-rom 5,6 --confirm
"""
from __future__ import annotations

import argparse
import base64
import csv
import re
import struct
import subprocess
import sys
import time
from pathlib import Path

REG_RAM_BASE = 2000          # holding: the code buffer
REG_BANK_TO_RAM = 5501       # holding: write N -> load bank N into RAM (non-committing; for verify)
COIL_EDIT_BASE = 5199        # coil 5199+N: write 1 = enter edit (ROM->RAM), write 0 = COMMIT RAM->ROM
MAX_WRITE_REGS = 121         # write-multiple (0x10) chunk; Modbus caps at 123
MAX_READ_REGS = 125          # read (0x03) chunk; Modbus caps at 125

_PARITY = {"N": "none", "E": "even", "O": "odd"}
_DATA_RE = re.compile(r"0x[0-9a-fA-F]+")


def make_modbus_caller(port, slave, baud, parity, stopbits):
    base = ["modbus_client", "-mrtu", f"-b{baud}", f"-p{_PARITY[parity]}", f"-s{stopbits}",
            "-o", "2000", port, f"-a{slave}"]

    def call(func, addr, count=None, write_vals=None):
        cmd = base + [f"-t{func}", f"-r{addr}"]
        if count is not None:
            cmd.append(f"-c{count}")
        if write_vals is not None:
            cmd += [str(v) for v in write_vals]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return res.stdout + res.stderr

    return call


def _ok(out: str) -> bool:
    return ("written" in out) or ("SUCCESS" in out)


def _parse_regs(out: str) -> list[int] | None:
    m = re.search(r"Data:\s*(.*)", out)
    if not m:
        return None
    return [int(tok, 16) for tok in _DATA_RE.findall(m.group(1))]


def decode_code(b64: str) -> list[int]:
    """base64 -> bytes -> uint16 big-endian duration registers."""
    raw = base64.b64decode(b64)
    if len(raw) % 2:
        raw += b"\x00"  # pad an odd byte count to a whole register
    return [struct.unpack(">H", raw[i:i + 2])[0] for i in range(0, len(raw), 2)]


def write_buffer(regs: list[int]) -> list[int]:
    """The buffer to write: the code, guaranteed to end with a 0x0000 0x0000 terminator."""
    buf = list(regs)
    if buf[-2:] != [0, 0]:
        buf += [0, 0]
    return buf


def code_part(vals: list[int]) -> list[int]:
    """The meaningful code: up to and including the first 0x0000 0x0000 terminator."""
    out: list[int] = []
    for k, v in enumerate(vals):
        out.append(v)
        if k >= 1 and v == 0 and vals[k - 1] == 0:
            break
    return out


def read_back(call, bank: int, nregs: int) -> list[int]:
    """Load bank via the non-committing BANK->RAM loader and read nregs from RAM."""
    if not _ok(call("0x06", REG_BANK_TO_RAM, write_vals=[bank])):
        raise RuntimeError(f"BANK->RAM (reg {REG_BANK_TO_RAM}={bank}) failed")
    vals: list[int] = []
    off = 0
    while off < nregs:
        chunk = min(MAX_READ_REGS, nregs - off)
        r = _parse_regs(call("0x03", REG_RAM_BASE + off, count=chunk))
        if r is None or len(r) < chunk:
            raise RuntimeError(f"read RAM at {REG_RAM_BASE + off} x{chunk} failed")
        vals.extend(r[:chunk])
        off += chunk
    return vals


def write_bank(call, bank: int, buf: list[int], settle: float) -> None:
    """enter edit (coil 5199+N=1) -> write RAM in chunks -> commit (coil 5199+N=0)."""
    coil = COIL_EDIT_BASE + bank
    if not _ok(call("0x05", coil, write_vals=[1])):
        raise RuntimeError(f"enter edit (coil {coil}=1) failed")
    time.sleep(settle)
    off = 0
    while off < len(buf):
        chunk = buf[off:off + MAX_WRITE_REGS]
        if not _ok(call("0x10", REG_RAM_BASE + off, write_vals=chunk)):
            raise RuntimeError(f"write RAM at {REG_RAM_BASE + off} x{len(chunk)} failed")
        off += len(chunk)
    if not _ok(call("0x05", coil, write_vals=[0])):
        raise RuntimeError(f"commit (coil {coil}=0) failed")
    time.sleep(2)


def load_rows(csv_paths: list[Path], only_rom: set[int] | None):
    """Yield (blaster, slave, rom, regs, expected_code, referenced_by) for restorable rows."""
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
                regs = decode_code(row["code_base64"])
                nbytes = int(row["code_size_bytes"])
                if len(regs) * 2 not in (nbytes, nbytes + 1):
                    print(f"  ! {row['blaster']} ROM{rom}: decoded {len(regs)*2}B != csv {nbytes}B",
                          file=sys.stderr)
                buf = write_buffer(regs)
                plan.append({
                    "blaster": row["blaster"], "slave": int(row["modbus_address"]),
                    "rom": rom, "buf": buf, "expected": code_part(buf), "nbytes": nbytes,
                    "referenced_by": row.get("referenced_by", ""),
                })
    return plan


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", nargs="+", type=Path, help="ir_backup_<blaster>.csv file(s) to restore from")
    ap.add_argument("--port", default="/dev/ttyRS485-2", help="serial port (default: /dev/ttyRS485-2)")
    ap.add_argument("--baud", type=int, default=9600)
    ap.add_argument("--parity", default="N", choices=["N", "E", "O"])
    ap.add_argument("--stopbits", type=int, default=2, choices=[1, 2])
    ap.add_argument("--settle", type=float, default=20.0,
                    help="seconds to wait after entering edit mode (official WB script uses 20)")
    ap.add_argument("--only-rom", help="restrict to these ROM numbers, comma-separated (e.g. 5,6)")
    ap.add_argument("--confirm", action="store_true",
                    help="actually WRITE FLASH. Without this the script is a dry run.")
    ap.add_argument("--keep-going", action="store_true",
                    help="continue to remaining banks after a verify mismatch (default: stop)")
    ap.add_argument("--no-toggle-service", action="store_true",
                    help="do NOT stop/start wb-mqtt-serial (use if you stopped it yourself)")
    args = ap.parse_args()

    for p in args.csv:
        if not p.is_file():
            raise SystemExit(f"CSV not found: {p}")
    only_rom = {int(x) for x in args.only_rom.split(",")} if args.only_rom else None

    print("Parsing + decoding CSV ...")
    plan = load_rows(args.csv, only_rom)
    if not plan:
        print("Nothing to restore.")
        return 0
    print(f"\n{len(plan)} bank(s) to restore:")
    for e in plan:
        print(f"  {e['blaster']} (slave {e['slave']}) ROM{e['rom']:<3} "
              f"{e['nbytes']:>4}B  <- {e['referenced_by']}")

    if not args.confirm:
        print("\nDRY RUN -- no hardware touched. Re-run with --confirm to write flash.")
        return 0

    toggled = False
    if not args.no_toggle_service:
        print("\nStopping wb-mqtt-serial for exclusive bus access...")
        subprocess.run(["systemctl", "stop", "wb-mqtt-serial"], check=True)
        toggled = True
    failures = 0
    try:
        time.sleep(2)
        for e in plan:
            call = make_modbus_caller(args.port, e["slave"], args.baud, args.parity, args.stopbits)
            try:
                write_bank(call, e["rom"], e["buf"], args.settle)
                got = code_part(read_back(call, e["rom"], len(e["expected"]) + 4))
                if got == e["expected"]:
                    print(f"  {e['blaster']} ROM{e['rom']:<3} OK   ({e['nbytes']}B verified)")
                else:
                    failures += 1
                    print(f"  {e['blaster']} ROM{e['rom']:<3} VERIFY MISMATCH "
                          f"(wrote {len(e['expected'])} regs, read {len(got)})", file=sys.stderr)
                    if not args.keep_going:
                        print("  stopping (use --keep-going to continue past mismatches)", file=sys.stderr)
                        break
            except Exception as ex:
                failures += 1
                print(f"  {e['blaster']} ROM{e['rom']:<3} ERROR: {ex}", file=sys.stderr)
                if not args.keep_going:
                    break
    finally:
        if toggled:
            print("Restarting wb-mqtt-serial...")
            subprocess.run(["systemctl", "start", "wb-mqtt-serial"], check=False)
    print(f"\nDone: {len(plan) - failures}/{len(plan)} bank(s) restored & verified.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
