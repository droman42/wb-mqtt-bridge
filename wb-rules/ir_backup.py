#!/usr/bin/env python3
"""Back up WB-MSW v3 IR ROM codes that wb-mqtt-bridge configs reference, before a firmware upgrade.

WHY: upgrading a WB-MSW v3 firmware WIPES its learned IR ROM banks (confirmed by Wiren Board docs:
"saving command banks before updating is recommended using a script"). This reads every ROM bank
any device config references for a given blaster and writes them to a CSV (codes base64-encoded),
so they survive the upgrade.

MECHANISM (per the WB-MSx Consumer IR Manual — Modbus):
  For ROM bank i on the module (Modbus slave = the numeric suffix of the blaster name):
    1. write coil  (5200 + i)  -> copy ROM bank i into the RAM buffer (NON-destructive to ROM)
    2. read input  (5400 + i)  -> code size in bytes
    3. read holding 2000..     -> the code: uint16 durations (10 us quanta), ends with two 0x0000
  ROM banks: 1..N (flash). RAM buffer: regs 2000-2509 (scratch).

This runs ON the WB controller and needs exclusive bus access, so by default it stops
`wb-mqtt-serial` for the duration of the read and restarts it after (same as the firmware updater).

RESTORE: writing arbitrary codes back INTO a ROM bank is NOT documented by Wiren Board (there is
no confirmed save-RAM->ROM coil; coil 5300+i only records from a physical remote). This script is
therefore BACKUP-ONLY. The CSV preserves every code (base64) so you can (a) re-learn from the
original remotes using the CSV as the checklist, or (b) restore programmatically later once the
save mechanism is confirmed with Wiren Board.

Usage:
    # dry run — just show which ROMs are referenced (no hardware access, safe anywhere):
    python3 ir_backup.py wb-msw-v3_207 --scan-only

    # full backup on the WB controller:
    sudo python3 ir_backup.py wb-msw-v3_207 --port /dev/ttyRS485-1 --baud 9600

Requires `pymodbus` for the hardware read (`pip3 install pymodbus`); --scan-only needs nothing.
"""
from __future__ import annotations

import argparse
import base64
import csv
import json
import math
import re
import struct
import subprocess
import sys
from pathlib import Path

# Modbus register/coil map (WB-MSx Consumer IR Manual), parameterised by ROM bank index i:
COIL_EDIT_ROM_TO_RAM = 5200   # write 1 -> copy ROM bank i into RAM (regs 2000..); non-destructive
REG_CODE_SIZE_BYTES = 5400    # input register: size of ROM bank i's code, in bytes
REG_RAM_BASE = 2000           # holding registers: the code lives at 2000.. (one uint16 per register)
RAM_MAX_REGS = 510            # RAM buffer is 2000-2509


def derive_slave_address(blaster: str) -> int:
    """WB auto-names modules `wb-msw-v3_<modbus-address>`; the numeric suffix IS the slave addr."""
    m = re.search(r"_(\d+)$", blaster)
    if not m:
        raise SystemExit(f"Cannot derive Modbus address from blaster name {blaster!r} "
                         f"(expected a trailing _<number>, e.g. wb-msw-v3_207).")
    return int(m.group(1))


def scan_configs(blaster: str, config_dir: Path) -> dict[int, list[str]]:
    """Find every ROM bank referenced for `blaster` across all device configs.

    Two reference patterns are used in this repo:
      A) WirenboardIRDevice commands: {"location": "<blaster>", "rom_position": "<i>"}
      B) full WB topics in sub-configs (Auralic/AppleTV ir_*_topic):
         "/devices/<blaster>/controls/Play from ROM<i>/on"
    Returns {rom_bank: [human-readable references]} sorted by bank.
    """
    topic_re = re.compile(rf"/devices/{re.escape(blaster)}/controls/Play from ROM(\d+)/on")
    refs: dict[int, list[str]] = {}

    def add(rom: int, ref: str) -> None:
        refs.setdefault(rom, [])
        if ref not in refs[rom]:
            refs[rom].append(ref)

    def walk_strings(obj, on_str):
        if isinstance(obj, dict):
            for v in obj.values():
                walk_strings(v, on_str)
        elif isinstance(obj, list):
            for v in obj:
                walk_strings(v, on_str)
        elif isinstance(obj, str):
            on_str(obj)

    for cfg_path in sorted(config_dir.glob("*.json")):
        try:
            cfg = json.loads(cfg_path.read_text())
        except (json.JSONDecodeError, OSError) as e:
            print(f"  ! skipping {cfg_path.name}: {e}", file=sys.stderr)
            continue
        device_id = cfg.get("device_id", cfg_path.stem)

        # Pattern A — per-command location + rom_position
        for cmd_name, cmd in (cfg.get("commands") or {}).items():
            if isinstance(cmd, dict) and cmd.get("location") == blaster and cmd.get("rom_position") is not None:
                rom = int(cmd["rom_position"])
                desc = cmd.get("description", "")
                add(rom, f"{device_id}:{cmd_name}" + (f" ({desc})" if desc else ""))

        # Pattern B — full "Play from ROM<i>" topic anywhere in the config (sub-configs)
        def on_str(s: str, _did=device_id):
            m = topic_re.search(s)
            if m:
                add(int(m.group(1)), f"{_did}:topic")
        walk_strings(cfg, on_str)

    return dict(sorted(refs.items()))


def read_rom_code(client, slave: int, rom: int):
    """Return (size_bytes, raw_bytes) for ROM bank `rom`, or raise on failure. Read-only to ROM."""
    # 1) copy ROM bank -> RAM (non-destructive to the ROM bank itself)
    wr = client.write_coil(COIL_EDIT_ROM_TO_RAM + rom, True, slave=slave)
    if wr.isError():
        raise RuntimeError(f"edit(ROM{rom}->RAM) coil {COIL_EDIT_ROM_TO_RAM + rom} failed: {wr}")
    # 2) code size in bytes
    sz = client.read_input_registers(REG_CODE_SIZE_BYTES + rom, count=1, slave=slave)
    if sz.isError():
        raise RuntimeError(f"read size reg {REG_CODE_SIZE_BYTES + rom} failed: {sz}")
    size_bytes = sz.registers[0]
    if size_bytes == 0:
        return 0, b""  # empty/unused bank
    n_regs = min(math.ceil(size_bytes / 2), RAM_MAX_REGS)
    # 3) the code from RAM (one uint16 duration per register, big-endian)
    rd = client.read_holding_registers(REG_RAM_BASE, count=n_regs, slave=slave)
    if rd.isError():
        raise RuntimeError(f"read RAM regs {REG_RAM_BASE}..{REG_RAM_BASE + n_regs - 1} failed: {rd}")
    raw = b"".join(struct.pack(">H", r) for r in rd.registers)[:size_bytes]
    return size_bytes, raw


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("blaster", help="blaster name, e.g. wb-msw-v3_207 (suffix = Modbus slave addr)")
    ap.add_argument("--config-dir", type=Path,
                    default=Path(__file__).resolve().parent.parent / "backend" / "config" / "devices",
                    help="device configs dir (default: ../backend/config/devices)")
    ap.add_argument("--out", type=Path, help="CSV output (default: ./ir_backup_<blaster>.csv)")
    ap.add_argument("--port", help="serial port, e.g. /dev/ttyRS485-1 (required unless --scan-only)")
    ap.add_argument("--baud", type=int, default=9600)
    ap.add_argument("--parity", default="N", choices=["N", "E", "O"])
    ap.add_argument("--stopbits", type=int, default=2, choices=[1, 2])
    ap.add_argument("--scan-only", action="store_true", help="just list referenced ROMs; no hardware")
    ap.add_argument("--no-toggle-service", action="store_true",
                    help="do NOT stop/start wb-mqtt-serial (use if you stopped it yourself)")
    args = ap.parse_args()

    if not args.config_dir.is_dir():
        raise SystemExit(f"config dir not found: {args.config_dir}")

    slave = derive_slave_address(args.blaster)
    refs = scan_configs(args.blaster, args.config_dir)
    print(f"{args.blaster}: Modbus slave {slave}; {len(refs)} ROM bank(s) referenced:")
    for rom, who in refs.items():
        print(f"  ROM{rom:<3} <- {', '.join(who)}")
    if not refs:
        print("  (nothing references this blaster — nothing to back up)")
        return 0
    if args.scan_only:
        return 0

    if not args.port:
        raise SystemExit("--port is required for a real backup (or use --scan-only)")
    try:
        from pymodbus.client import ModbusSerialClient
    except ImportError:
        raise SystemExit("pymodbus not installed — run: pip3 install pymodbus  (or use --scan-only)")

    toggled = False
    if not args.no_toggle_service:
        print("Stopping wb-mqtt-serial for exclusive bus access...")
        subprocess.run(["systemctl", "stop", "wb-mqtt-serial"], check=True)
        toggled = True
    try:
        client = ModbusSerialClient(port=args.port, baudrate=args.baud, parity=args.parity,
                                    stopbits=args.stopbits, bytesize=8, timeout=2.0)
        if not client.connect():
            raise SystemExit(f"cannot open serial port {args.port}")
        out = args.out or Path.cwd() / f"ir_backup_{args.blaster}.csv"
        rows = []
        for rom, who in refs.items():
            try:
                size, raw = read_rom_code(client, slave, rom)
                b64 = base64.b64encode(raw).decode() if raw else ""
                status = "ok" if raw else "EMPTY"
                print(f"  ROM{rom:<3} {status:5} {size:>4} bytes")
            except Exception as e:  # one bad bank shouldn't abort the whole backup
                size, b64, status = 0, "", f"ERROR: {e}"
                print(f"  ROM{rom:<3} {status}", file=sys.stderr)
            rows.append({
                "blaster": args.blaster, "modbus_address": slave, "rom": rom,
                "code_size_bytes": size, "code_base64": b64,
                "referenced_by": "; ".join(who), "status": status,
            })
        client.close()
        with out.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["blaster", "modbus_address", "rom",
                                               "code_size_bytes", "code_base64", "referenced_by", "status"])
            w.writeheader()
            w.writerows(rows)
        ok = sum(1 for r in rows if r["status"] == "ok")
        print(f"Wrote {out}  ({ok}/{len(rows)} banks captured)")
    finally:
        if toggled:
            print("Restarting wb-mqtt-serial...")
            subprocess.run(["systemctl", "start", "wb-mqtt-serial"], check=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
