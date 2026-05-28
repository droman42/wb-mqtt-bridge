#!/usr/bin/env python3
"""Back up WB-MSW v3 IR ROM codes that wb-mqtt-bridge configs reference, before a firmware upgrade.

WHY: upgrading a WB-MSW v3 firmware WIPES its learned IR ROM banks. This reads every ROM bank
any device config references for the given blaster(s) and writes them to CSV (codes base64), so
they survive the upgrade.

RUNS ON THE WB CONTROLLER. It drives the `modbus_client` CLI (shipped on every Wiren Board
controller — no Python deps) and needs exclusive bus access, so by default it stops
`wb-mqtt-serial` for the duration and restarts it after.

MECHANISM (verified on a live WB-MSW v3 against /usr/share/wb-mqtt-serial/templates/config-wb-msw_v3.json):
  Modbus slave = the numeric suffix of the blaster name (wb-msw-v3_207 -> slave 207).
  Registers are 0-based (the address on the wire); pass them to modbus_client WITHOUT -0.
  For ROM bank N (the same N as a config's rom_position / "Play from ROM<N>"):
    1. write holding reg 5501 = N   -> "BANK -> RAM": copies ROM bank N into the RAM buffer.
       (Universal loader for all banks. The per-bank "ROM<N> -> RAM" coils 5199+N only cover
        banks 1-32; 5501 reaches every bank — verified up to ROM80.)
    2. read input reg  (5399 + N)   -> "ROM<N> size": the code size in bytes.
    3. read holding regs 2000..     -> the code: uint16 durations, big-endian, 10 us quanta,
       terminated by repeated 0x0000. Modbus caps a read at 125 regs/frame, so reads are chunked.
  Each duration register is one mark/space; e.g. a captured NEC code starts 0x038b 0x01c3
  (9.07 ms / 4.51 ms leader) then 0x003a / 0x00a9 bit timings.

RESTORE IS NOT SUPPORTED BY THE FIRMWARE. The WB-MSW v3 register map exposes only LOAD
(ROM->RAM / BANK->RAM), LEARN-from-a-physical-remote (coils 5300+N, holding 5502), and
ERASE (coil 5000 "Reset all ROM"). There is NO RAM->ROM "save" control, so codes cannot be
written back from this CSV programmatically. This CSV is therefore the safety net: after a
firmware upgrade, banks must be re-learned from the original remotes (CSV = the per-ROM
checklist). DANGER: never write coil 5000 (erases all banks).

Usage:
    # dry run -- list referenced ROMs only, no hardware (safe anywhere):
    python3 ir_backup.py wb-msw-v3_207 wb-msw-v3_218 wb-msw-v3_220 --scan-only

    # real backup on the WB controller (one service-stop window for all blasters):
    sudo python3 ir_backup.py wb-msw-v3_207 wb-msw-v3_218 wb-msw-v3_220 --port /dev/ttyRS485-2
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

# WB-MSW v3 IR register map (0-based wire addresses; verified on hardware):
REG_BANK_TO_RAM = 5501       # holding: write N -> copy ROM bank N into the RAM buffer
REG_CODE_SIZE_BASE = 5400    # input:  ROM<N> code size in bytes lives at 5400 + (N-1) = 5399 + N
REG_RAM_BASE = 2000          # holding: the loaded code, one uint16 duration per register
MAX_REGS_PER_READ = 125      # Modbus caps a single read at 125 registers


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

        # Pattern A -- per-command location + rom_position
        for cmd_name, cmd in (cfg.get("commands") or {}).items():
            if isinstance(cmd, dict) and cmd.get("location") == blaster and cmd.get("rom_position") is not None:
                rom = int(cmd["rom_position"])
                desc = cmd.get("description", "")
                add(rom, f"{device_id}:{cmd_name}" + (f" ({desc})" if desc else ""))

        # Pattern B -- full "Play from ROM<i>" topic anywhere in the config (sub-configs)
        def on_str(s: str, _did=device_id):
            m = topic_re.search(s)
            if m:
                add(int(m.group(1)), f"{_did}:topic")
        walk_strings(cfg, on_str)

    return dict(sorted(refs.items()))


_PARITY = {"N": "none", "E": "even", "O": "odd"}
_DATA_RE = re.compile(r"0x[0-9a-fA-F]+")


def make_modbus_caller(port, slave, baud, parity, stopbits):
    """Return call(func, addr, count=None, write=None) -> stdout+stderr from modbus_client."""
    base = ["modbus_client", "-mrtu", f"-a{slave}", f"-b{baud}", "-d8",
            f"-s{stopbits}", f"-p{_PARITY[parity]}"]

    def call(func, addr, count=None, write=None):
        cmd = base + [f"-t{func}", f"-r{addr}"]
        if count is not None:
            cmd.append(f"-c{count}")
        cmd.append(port)
        if write is not None:
            cmd.append(str(write))
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return res.stdout + res.stderr

    return call


def _parse_regs(output: str) -> list[int] | None:
    """Pull the register values out of a modbus_client 'Data: 0x.. 0x..' line."""
    m = re.search(r"Data:\s*(.*)", output)
    if not m:
        return None
    return [int(tok, 16) for tok in _DATA_RE.findall(m.group(1))]


def read_rom_code(call, rom: int) -> tuple[int, bytes]:
    """Return (size_bytes, raw_bytes) for ROM bank `rom`. Read-only to ROM (load + read only)."""
    # 1) copy ROM bank N -> RAM (non-destructive; universal loader for all banks)
    out = call("0x06", REG_BANK_TO_RAM, write=rom)
    if "written" not in out and "SUCCESS" not in out:
        raise RuntimeError(f"BANK->RAM (reg {REG_BANK_TO_RAM}={rom}) failed: {out.strip()}")
    # 2) code size in bytes
    out = call("0x04", REG_CODE_SIZE_BASE + rom - 1, count=1)
    regs = _parse_regs(out)
    if not regs:
        raise RuntimeError(f"size read (reg {REG_CODE_SIZE_BASE + rom - 1}) failed: {out.strip()}")
    size_bytes = regs[0]
    if size_bytes == 0:
        return 0, b""  # empty/unused bank
    n_regs = math.ceil(size_bytes / 2)
    # 3) the code from RAM, chunked at the 125-reg Modbus ceiling
    vals: list[int] = []
    off = 0
    while off < n_regs:
        chunk = min(MAX_REGS_PER_READ, n_regs - off)
        out = call("0x03", REG_RAM_BASE + off, count=chunk)
        r = _parse_regs(out)
        if r is None or len(r) < chunk:
            raise RuntimeError(f"RAM read at {REG_RAM_BASE + off} x{chunk} failed: {out.strip()}")
        vals.extend(r[:chunk])
        off += chunk
    raw = b"".join(struct.pack(">H", v) for v in vals)[:size_bytes]
    return size_bytes, raw


CSV_FIELDS = ["blaster", "modbus_address", "rom", "code_size_bytes",
              "code_base64", "referenced_by", "status"]


def backup_blaster(blaster: str, refs: dict[int, list[str]], call, out_dir: Path) -> Path:
    slave = derive_slave_address(blaster)
    print(f"--- {blaster} (slave {slave}): {len(refs)} bank(s) ---")
    rows = []
    for rom, who in refs.items():
        try:
            size, raw = read_rom_code(call, rom)
            b64 = base64.b64encode(raw).decode() if raw else ""
            status = "ok" if raw else "EMPTY"
            print(f"  ROM{rom:<3} {status:5} {size:>4} bytes")
        except Exception as e:  # one bad bank shouldn't abort the whole backup
            size, b64, status = 0, "", f"ERROR: {e}"
            print(f"  ROM{rom:<3} {status}", file=sys.stderr)
        rows.append({
            "blaster": blaster, "modbus_address": slave, "rom": rom,
            "code_size_bytes": size, "code_base64": b64,
            "referenced_by": "; ".join(who), "status": status,
        })
    out = out_dir / f"ir_backup_{blaster}.csv"
    with out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        w.writeheader()
        w.writerows(rows)
    ok = sum(1 for r in rows if r["status"] == "ok")
    print(f"  -> {out}  ({ok}/{len(rows)} banks captured)")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("blasters", nargs="+", help="blaster name(s), e.g. wb-msw-v3_207 (suffix = Modbus slave)")
    ap.add_argument("--config-dir", type=Path,
                    default=Path(__file__).resolve().parent.parent / "backend" / "config" / "devices",
                    help="device configs dir (default: ../backend/config/devices)")
    ap.add_argument("--out-dir", type=Path, default=Path.cwd(),
                    help="dir for ir_backup_<blaster>.csv files (default: cwd)")
    ap.add_argument("--port", default="/dev/ttyRS485-2", help="serial port (default: /dev/ttyRS485-2)")
    ap.add_argument("--baud", type=int, default=9600)
    ap.add_argument("--parity", default="N", choices=["N", "E", "O"])
    ap.add_argument("--stopbits", type=int, default=2, choices=[1, 2])
    ap.add_argument("--scan-only", action="store_true", help="just list referenced ROMs; no hardware")
    ap.add_argument("--no-toggle-service", action="store_true",
                    help="do NOT stop/start wb-mqtt-serial (use if you stopped it yourself)")
    args = ap.parse_args()

    if not args.config_dir.is_dir():
        raise SystemExit(f"config dir not found: {args.config_dir}")

    # Scan all blasters up front (cheap, no hardware).
    scanned = {}
    for blaster in args.blasters:
        refs = scan_configs(blaster, args.config_dir)
        scanned[blaster] = refs
        slave = derive_slave_address(blaster)
        print(f"{blaster}: Modbus slave {slave}; {len(refs)} ROM bank(s) referenced:")
        for rom, who in refs.items():
            print(f"  ROM{rom:<3} <- {', '.join(who)}")
        if not refs:
            print("  (nothing references this blaster)")

    if args.scan_only:
        return 0
    if not any(scanned.values()):
        print("Nothing to back up.")
        return 0
    if not args.out_dir.is_dir():
        raise SystemExit(f"--out-dir not found: {args.out_dir}")

    toggled = False
    if not args.no_toggle_service:
        print("Stopping wb-mqtt-serial for exclusive bus access...")
        subprocess.run(["systemctl", "stop", "wb-mqtt-serial"], check=True)
        toggled = True
    try:
        import time
        time.sleep(2)  # let the bus settle after the service releases it
        for blaster, refs in scanned.items():
            if not refs:
                continue
            call = make_modbus_caller(args.port, derive_slave_address(blaster),
                                      args.baud, args.parity, args.stopbits)
            backup_blaster(blaster, refs, call, args.out_dir)
    finally:
        if toggled:
            print("Restarting wb-mqtt-serial...")
            subprocess.run(["systemctl", "start", "wb-mqtt-serial"], check=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
