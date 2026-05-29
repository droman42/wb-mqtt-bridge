#!/usr/bin/env python3
"""Shared primitives for the WB-MSW v3 IR ROM tools (backup / restore / verify).

GENERAL PURPOSE. This module knows only the WB-MSW v3 IR register map and the controller-native
`modbus_client` CLI. It has NO knowledge of any A/V system, device config, scenario, or topology --
it is a plain "dump / write back / compare IR ROM banks" toolkit for a WB-MSW v3 blaster.

RUNS ON THE WB CONTROLLER. The tools drive `modbus_client` (shipped on every Wiren Board
controller -- no Python deps) and need exclusive bus access.

WB-MSW v3 IR register map (0-based wire addresses; verified on live hardware against
/usr/share/wb-mqtt-serial/templates/config-wb-msw_v3.json and the WB support toolkit):

  * BANK -> RAM loader (non-committing):  holding 5501 = N   copies ROM bank N into the RAM buffer.
        Universal loader for every bank 1..80 (the per-bank ROM<N>->RAM coils only cover 1..32).
  * ROM<N> code size in bytes:            input  5399 + N   (= 5400 + (N-1)). Bank-indexed, static.
  * code buffer:                          holding 2000+     one uint16 duration per register,
        big-endian, 10 us quanta, terminated by a 0x0000 0x0000 pair.
  * per-bank EDIT coil:                   coil   5199 + N   write 1 = enter edit (ROM->RAM),
        write 0 = COMMIT RAM->ROM. The same coil works for ALL banks 1..80 (template exposes
        only 5200..5231). A bank left at 1 LOCKS the whole blaster's playback (every "Play from
        ROM" then returns Modbus exception 06 "Slave Device Busy").

  DANGER: never write coil 5000 ("Reset all ROM" -- erases every bank). No tool here does.

Modbus framing limits: a single read is capped at 125 regs/frame; a write-multiple (0x10) at 121.
"""
from __future__ import annotations

import base64
import contextlib
import re
import struct
import subprocess
import time

# --- WB-MSW v3 IR register map (0-based wire addresses) -------------------------------------
REG_RAM_BASE = 2000          # holding: the code buffer (one uint16 duration per register)
REG_BANK_TO_RAM = 5501       # holding: write N -> copy ROM bank N into RAM (non-committing)
REG_CODE_SIZE_BASE = 5400    # input:  ROM<N> size in bytes lives at 5400 + (N-1) = 5399 + N
COIL_EDIT_BASE = 5199        # coil 5199+N: 1 = enter edit (ROM->RAM), 0 = COMMIT RAM->ROM

MAX_READ_REGS = 125          # Modbus caps a single read at 125 registers
MAX_WRITE_REGS = 121         # write-multiple (0x10) chunk; Modbus caps at 123, keep margin

BANK_MIN = 1                 # WB-MSW v3 ROM banks are numbered 1..80
BANK_MAX = 80

DEFAULT_PORT = "/dev/ttyRS485-2"
JITTER_TOL = 8               # default per-register tolerance (10 us quanta) for the verify compare;
                             # learned multi-repeat IR frames carry inherent +-~3-quantum capture
                             # jitter, so an exact byte compare is the wrong bar (see codes_match)

_PARITY = {"N": "none", "E": "even", "O": "odd"}
_DATA_RE = re.compile(r"0x[0-9a-fA-F]+")


def parse_banks(spec: str) -> set[int]:
    """Parse a '5,6,10-14' bank spec into a set of ints. Used by --only-rom / --banks."""
    out: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo, hi = part.split("-", 1)
            out.update(range(int(lo), int(hi) + 1))
        else:
            out.add(int(part))
    return out


def make_modbus_caller(port: str, slave: int, baud: int, parity: str, stopbits: int):
    """Return call(func, addr, count=None, write_vals=None) -> stdout+stderr from modbus_client.

    `func` is a modbus function code string ('0x01' coils, '0x03' holding, '0x04' input,
    '0x05' write-coil, '0x06' write-holding, '0x10' write-multiple). `write_vals` is a list.
    The 2000 ms response timeout (-o) matters: a commit can be slow right after a large write.
    """
    base = ["modbus_client", "-mrtu", f"-b{baud}", "-d8", f"-s{stopbits}",
            f"-p{_PARITY[parity]}", "-o", "2000", port, f"-a{slave}"]

    def call(func, addr, count=None, write_vals=None):
        cmd = base + [f"-t{func}", f"-r{addr}"]
        if count is not None:
            cmd.append(f"-c{count}")
        if write_vals is not None:
            cmd += [str(v) for v in write_vals]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return res.stdout + res.stderr

    return call


def add_bus_args(parser) -> None:
    """Add the serial-bus connection args shared by every tool (--port/--baud/--parity/--stopbits)."""
    parser.add_argument("--port", default=DEFAULT_PORT, help=f"serial port (default: {DEFAULT_PORT})")
    parser.add_argument("--baud", type=int, default=9600)
    parser.add_argument("--parity", default="N", choices=["N", "E", "O"])
    parser.add_argument("--stopbits", type=int, default=2, choices=[1, 2])


def add_service_arg(parser) -> None:
    """Add the shared --no-toggle-service flag (see bus_window)."""
    parser.add_argument("--no-toggle-service", action="store_true",
                        help="do NOT stop/start wb-mqtt-serial (use if you stopped it yourself)")


def caller_for(args, slave: int):
    """A modbus_client caller for `slave`, built from the standard bus args (see add_bus_args)."""
    return make_modbus_caller(args.port, slave, args.baud, args.parity, args.stopbits)


@contextlib.contextmanager
def bus_window(toggle: bool, settle: float = 2.0):
    """Exclusive-bus context: stop wb-mqtt-serial (if `toggle`), settle, restart on exit.

    wb-mqtt-serial owns the RS485 bus, so a tool needs it stopped for the duration. The restart
    runs in a finally, so the service comes back even if the body raises or breaks out early."""
    started = False
    if toggle:
        print("Stopping wb-mqtt-serial for exclusive bus access...")
        subprocess.run(["systemctl", "stop", "wb-mqtt-serial"], check=True)
        started = True
    try:
        time.sleep(settle)  # let the bus settle after the service releases it
        yield
    finally:
        if started:
            print("Restarting wb-mqtt-serial...")
            subprocess.run(["systemctl", "start", "wb-mqtt-serial"], check=False)


def ok(out: str) -> bool:
    """modbus_client prints 'written' / 'SUCCESS' on a good write; everything else is a failure."""
    return ("written" in out) or ("SUCCESS" in out)


def parse_regs(out: str) -> list[int] | None:
    """Pull register values out of a modbus_client 'Data: 0x.. 0x..' line."""
    m = re.search(r"Data:\s*(.*)", out)
    if not m:
        return None
    return [int(tok, 16) for tok in _DATA_RE.findall(m.group(1))]


def read_size(call, bank: int) -> int:
    """ROM<bank> code size in bytes (input reg 5399+bank). Bank-indexed and static, so it is
    readable without first loading the bank into RAM. Returns 0 for an empty/unused bank."""
    regs = parse_regs(call("0x04", REG_CODE_SIZE_BASE + bank - 1, count=1))
    if not regs:
        raise RuntimeError(f"size read (reg {REG_CODE_SIZE_BASE + bank - 1}) failed for bank {bank}")
    return regs[0]


def read_bank(call, bank: int, nregs: int) -> list[int]:
    """Load ROM bank into RAM via the non-committing BANK->RAM loader, then read nregs registers."""
    if not ok(call("0x06", REG_BANK_TO_RAM, write_vals=[bank])):
        raise RuntimeError(f"BANK->RAM (reg {REG_BANK_TO_RAM}={bank}) failed")
    vals: list[int] = []
    off = 0
    while off < nregs:
        chunk = min(MAX_READ_REGS, nregs - off)
        r = parse_regs(call("0x03", REG_RAM_BASE + off, count=chunk))
        if r is None or len(r) < chunk:
            raise RuntimeError(f"read RAM at {REG_RAM_BASE + off} x{chunk} failed")
        vals.extend(r[:chunk])
        off += chunk
    return vals


def regs_to_b64(vals: list[int], size_bytes: int) -> str:
    """Pack uint16 duration registers (big-endian) into `size_bytes` bytes and base64-encode."""
    raw = b"".join(struct.pack(">H", v) for v in vals)[:size_bytes]
    return base64.b64encode(raw).decode() if raw else ""


def b64_to_regs(b64: str) -> list[int]:
    """base64 -> bytes -> uint16 big-endian duration registers (odd trailing byte zero-padded)."""
    raw = base64.b64decode(b64)
    if len(raw) % 2:
        raw += b"\x00"
    return [struct.unpack(">H", raw[i:i + 2])[0] for i in range(0, len(raw), 2)]


def code_part(vals: list[int]) -> list[int]:
    """The meaningful code: up to and including the first 0x0000 0x0000 terminator."""
    out: list[int] = []
    for k, v in enumerate(vals):
        out.append(v)
        if k >= 1 and v == 0 and vals[k - 1] == 0:
            break
    return out


def with_terminator(regs: list[int]) -> list[int]:
    """A copy of `regs` guaranteed to end with a 0x0000 0x0000 terminator."""
    buf = list(regs)
    if buf[-2:] != [0, 0]:
        buf += [0, 0]
    return buf


def compare(expected: list[int], got: list[int], tol: int = JITTER_TOL) -> dict:
    """Compare two duration lists with a per-register jitter tolerance.

    WHY tolerant: WB-MSW learns IR by *capturing* the remote's pulses, and multi-repeat frames
    (long ld_player/vhs codes) carry per-repeat capture jitter of a few 10 us quanta. The stored
    copy can therefore differ from a backup by +-~3 quanta without being corrupt -- an exact byte
    compare reports a false mismatch. So: lengths must match exactly, and every register must be
    within `tol` quanta (tol=0 -> exact compare).

    Returns a report dict: {match, exact, len_ok, max_dev, n_diff, first_diff, exp_len, got_len}.
    """
    exp_len, got_len = len(expected), len(got)
    len_ok = exp_len == got_len
    n = min(exp_len, got_len)
    devs = [abs(expected[i] - got[i]) for i in range(n)]
    max_dev = max(devs) if devs else 0
    diffs = [i for i, d in enumerate(devs) if d > 0]
    over_tol = [i for i, d in enumerate(devs) if d > tol]
    return {
        "match": len_ok and not over_tol,
        "exact": len_ok and not diffs,
        "len_ok": len_ok,
        "max_dev": max_dev,
        "n_diff": len(diffs),
        "n_over_tol": len(over_tol),
        "first_diff": diffs[0] if diffs else None,
        "first_over_tol": over_tol[0] if over_tol else None,
        "exp_len": exp_len,
        "got_len": got_len,
    }


def diff_detail(expected: list[int], got: list[int], around: int = 3, after: int = 5) -> str:
    """A short human-readable diff around the first differing index (folds the old diag_* output)."""
    n = min(len(expected), len(got))
    diffs = [i for i in range(n) if expected[i] != got[i]]
    lines = [f"exp_len={len(expected)} got_len={len(got)} n_diff={len(diffs)}"]
    if diffs:
        i = diffs[0]
        lo, hi = max(0, i - around), i + after
        lines.append(f"  first diff at index {i}")
        lines.append(f"    exp[{lo}:{hi}] = {expected[lo:hi]}")
        lines.append(f"    got[{lo}:{hi}] = {got[lo:hi]}")
        lines.append(f"    last 8 exp   = {expected[-8:]}")
        lines.append(f"    last 8 got   = {got[-8:]}")
    return "\n".join(lines)
