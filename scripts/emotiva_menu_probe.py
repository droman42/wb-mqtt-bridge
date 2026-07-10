#!/usr/bin/env python3
"""Read-only(ish) eMotiva OSD menu probe — walk the menu over UDP and dump every
screen, to read the HDMI CEC setting without touching the rack.

Usage:
  emotiva_menu_probe.py ping                 # discovery only (harmless)
  emotiva_menu_probe.py open                 # subscribe + open the menu, dump screen
  emotiva_menu_probe.py keys down down enter # send nav keys, dump screen after each
  emotiva_menu_probe.py close                # send 'menu' again to close the OSD

Only menu/up/down/left/right/enter are ever sent. Never sends input or ARC
commands (Command.ARC is rack-verified to hang the device).
"""
import socket
import sys
import time
from xml.etree import ElementTree as ET

HOST = "192.168.110.177"
PING = b'<?xml version="1.0" encoding="utf-8"?><emotivaPing protocol="3.1"/>'
CTRL_PORT = 7002
NOTIFY_PORT = 7003
MENU_PORT = 7005
ALLOWED_KEYS = {"menu", "up", "down", "left", "right", "enter"}


def cmd_xml(name: str) -> bytes:
    return (f'<?xml version="1.0" encoding="utf-8"?>'
            f'<emotivaControl><{name} value="0" ack="yes"/></emotivaControl>').encode()


def sub_xml(props) -> bytes:
    inner = "".join(f"<{p}/>" for p in props)
    return (f'<?xml version="1.0" encoding="utf-8"?>'
            f'<emotivaSubscription protocol="3.0">{inner}</emotivaSubscription>').encode()


def bind(port: int) -> socket.socket:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("", port))
    s.settimeout(0.5)
    return s


def drain(sock: socket.socket, seconds: float):
    """Collect packets for `seconds`; return list of parsed XML roots."""
    out = []
    end = time.time() + seconds
    while time.time() < end:
        try:
            data, _ = sock.recvfrom(65535)
        except socket.timeout:
            continue
        try:
            out.append(ET.fromstring(data.decode("utf-8", "replace")))
        except ET.ParseError:
            print(f"  [unparseable {len(data)}B] {data[:120]!r}")
    return out


def render_menu(xml_root):
    """Pretty-print an emotivaMenuNotify screen."""
    rows = []
    for row in xml_root.findall("row"):
        cols = []
        for col in row.findall("col"):
            v = col.get("value", "")
            if col.get("highlight") == "yes":
                v = f">>{v}<<"
            if col.get("arrow") not in (None, "no"):
                v += f"[{col.get('arrow')}]"
            cols.append(v)
        rows.append(" | ".join(c or "·" for c in cols))
    return "\n".join(f"  {r}" for r in rows if r.strip(" |·"))


def report(packets):
    screens = 0
    for p in packets:
        if p.tag == "emotivaMenuNotify":
            screens += 1
            print(f"--- menu screen (seq {p.get('sequence')}) ---")
            print(render_menu(p))
        elif p.tag == "emotivaNotify":
            props = [f"{c.tag if p.get('protocol') is None else c.get('name')}"
                     f"={c.get('value')}" for c in p]
            print(f"  [notify] {', '.join(props)}")
        elif p.tag in ("emotivaAck", "emotivaSubscription"):
            details = [f"{c.tag} {c.get('status', '?')}" for c in p]
            print(f"  [{p.tag}] {', '.join(details)}")
        else:
            print(f"  [{p.tag}] {ET.tostring(p, encoding='unicode')[:200]}")
    if screens == 0:
        print("  (no menu screens received)")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "ping"

    # discovery ping — confirms reachability + advertised ports
    ping_sock = bind(7001)
    tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    tx.sendto(PING, (HOST, 7000))
    try:
        data, addr = ping_sock.recvfrom(65535)
        root = ET.fromstring(data.decode())
        info = {c.tag: (c.text or "").strip() for c in root.iter() if c.text}
        print(f"[transponder] from {addr[0]}: model={info.get('model')} "
              f"name={info.get('name')} keepAlive={info.get('keepAlive')}ms")
    except socket.timeout:
        print("NO transponder response — device unreachable from this box")
        return 1
    finally:
        ping_sock.close()

    if mode == "ping":
        return 0

    ctrl = bind(CTRL_PORT)
    notify = bind(NOTIFY_PORT)
    menu_sock = bind(MENU_PORT)

    # register interest so menuNotify comes to *this* host
    ctrl.sendto(sub_xml(["menu", "menu_update"]), (HOST, CTRL_PORT))
    report(drain(ctrl, 1.0))

    keys = []
    if mode == "open":
        keys = ["menu"]
    elif mode == "close":
        keys = ["menu"]
    elif mode == "keys":
        keys = sys.argv[2:]
        bad = [k for k in keys if k not in ALLOWED_KEYS]
        if bad:
            print(f"refusing non-navigation keys: {bad}")
            return 1

    for k in keys:
        print(f"\n=== send: {k} ===")
        ctrl.sendto(cmd_xml(k), (HOST, CTRL_PORT))
        report(drain(ctrl, 0.8))
        report(drain(menu_sock, 2.5))
        report(drain(notify, 0.3))

    if mode == "open":
        # linger for slow redraws
        print("\n=== lingering 3s for menu updates ===")
        report(drain(menu_sock, 3.0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
