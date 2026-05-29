#!/usr/bin/env python3
"""WB-MSW v3 IR ROM toolkit -- one CLI over backup / restore / verify.

  ir.py backup  <blaster>...   dump every non-empty ROM bank from the device to CSV
  ir.py restore <csv>...       write banks back from a backup CSV (dry run unless --confirm)
  ir.py verify  <csv>...       read-only jitter-tolerant check of stored banks vs a backup CSV

All three subcommands share the serial-bus flags (--port/--baud/--parity/--stopbits) and the
--no-toggle-service flag, and they all sit on the general-purpose core in ir_common.py (the
WB-MSW v3 register map + modbus_client wrapper + codec; NO A/V knowledge). Run on the WB
controller. `ir.py <cmd> -h` shows a subcommand's own help.

The individual modules remain runnable on their own (python3 ir_backup.py ...) -- this wrapper is
just the front door.
"""
from __future__ import annotations

import argparse

import ir_backup
import ir_restore
import ir_verify

COMMANDS = {"backup": ir_backup, "restore": ir_restore, "verify": ir_verify}


def main() -> int:
    ap = argparse.ArgumentParser(prog="ir.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True, metavar="{backup,restore,verify}")
    for name, mod in COMMANDS.items():
        sp = sub.add_parser(name, help=mod.__doc__.strip().splitlines()[0],
                            description=mod.__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
        mod.add_arguments(sp)
        sp.set_defaults(_run=mod.run)
    args = ap.parse_args()
    return args._run(args)


if __name__ == "__main__":
    raise SystemExit(main())
