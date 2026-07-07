"""Slice integration test for §P3.7 #14 — cabinet_spots.

Pins four things end-to-end against the actual committed slice configs:

1. The cabinet_spots.json device config under `backend/config/devices/wb-devices/cabinet/`
   parses into a WbPassthroughDeviceConfig (Pydantic) — the names+room+capability_profile+
   commands+state_topics shape is exactly what the driver expects.
2. The recursive config scanner (utils/validation.py, switched to glob `**/*.json` for the
   single-room directory convention) actually discovers a config in a wb-devices/<room>/
   subtree. A regression here would silently make the slice device invisible to ConfigManager.
3. The `light_switch` capability profile resolves through the loader for cabinet_spots and
   maps canonical `power.on/off` → native `power_on/power_off`, matching the device config's
   commands. (Profiles are §P3.7's scaling answer for the WB-passthrough family — many
   devices share one capability file.)
4. The rooms.json carries the cabinet entry with bilingual names + cabinet_spots membership.

These are pure file-load + schema tests — no MQTT, no FastAPI, no hardware. The
WB-passthrough driver unit tests (test_wb_passthrough.py) cover the behavioural side.
"""
import json
from pathlib import Path

import pytest

from wb_mqtt_bridge.infrastructure.capabilities.loader import load_capability_map
from wb_mqtt_bridge.infrastructure.config.models import WbPassthroughDeviceConfig
from wb_mqtt_bridge.infrastructure.config.validation import discover_config_files

REPO_ROOT = Path(__file__).resolve().parents[3]
DEVICE_CFG = REPO_ROOT / "backend" / "config" / "devices" / "wb-devices" / "cabinet" / "cabinet_spots.json"
CAPS_DIR = REPO_ROOT / "backend" / "config" / "capabilities"
ROOMS_JSON = REPO_ROOT / "backend" / "config" / "rooms.json"


def test_cabinet_spots_json_parses_as_wb_passthrough_config():
    raw = json.loads(DEVICE_CFG.read_text())
    cfg = WbPassthroughDeviceConfig(**raw)
    assert cfg.device_id == "cabinet_spots"
    assert cfg.device_class == "WbPassthroughDevice"
    assert cfg.config_class == "WbPassthroughDeviceConfig"
    assert cfg.names.ru == "Споты"
    assert cfg.names.en == "Spots"
    assert cfg.room == "cabinet"
    # The capability shape comes from the shared light_switch profile, NOT a per-device file.
    assert cfg.capability_profile == "light_switch"
    # Loop guard: passthrough never owns the underlying control.
    assert cfg.enable_wb_emulation is False
    # Commands point at the actual WB blaster slave + channel from §P3.7 A1.
    assert cfg.commands["power_on"].topic == "/devices/wb-mr6c_51/controls/K4/on"
    assert cfg.commands["power_on"].value == "1"
    assert cfg.commands["power_off"].value == "0"
    # State mirror picks the value-topic (without /on suffix), per the WB convention.
    # `state_topics` widened to typed StateTopicSpec in #19; the slice's bare-string form
    # normalises to `type="str"` with the same topic — round-trip pin.
    assert set(cfg.state_topics.keys()) == {"power"}
    assert cfg.state_topics["power"].topic == "/devices/wb-mr6c_51/controls/K4"
    assert cfg.state_topics["power"].type == "str"


def test_recursive_scanner_finds_config_under_wb_devices_room_subdir():
    """The §P3.7 directory convention puts WB-passthrough configs at
    `wb-devices/<room>/<device_id>.json`. The scanner MUST recurse, else the device is
    invisible to ConfigManager."""
    files = discover_config_files(str(REPO_ROOT / "backend" / "config" / "devices"))
    assert str(DEVICE_CFG) in files, (
        f"cabinet_spots.json under wb-devices/cabinet/ was not discovered. "
        f"Found {len(files)} configs; check utils/validation.discover_config_files is "
        f"using recursive glob."
    )
    # Existing flat AV configs MUST still be found (no regression).
    assert str(REPO_ROOT / "backend" / "config" / "devices" / "lg_tv_living.json") in files


def test_light_switch_profile_resolves_power_on_off_to_native_commands():
    """Canonical `power.on/off` must map onto the native command names the device config
    exposes — otherwise the canonical endpoint (#15) can't route. The map comes from the
    shared `light_switch` profile, resolved through the loader exactly the way bootstrap
    does it; no per-device override file is involved."""
    cap_map = load_capability_map(
        device_class="WbPassthroughDevice",
        device_id="cabinet_spots",
        capabilities_dir=CAPS_DIR,
        capability_profile="light_switch",
    )
    power = cap_map.root["power"]
    assert power.actions["on"].command == "power_on"
    assert power.actions["off"].command == "power_off"
    # Cross-check: those native command names exist on the device config.
    dev_cfg = json.loads(DEVICE_CFG.read_text())
    assert "power_on" in dev_cfg["commands"]
    assert "power_off" in dev_cfg["commands"]
    # No per-device override exists (and shouldn't, for a stock light_switch).
    assert not (CAPS_DIR / "devices" / "cabinet_spots.json").exists()


def test_rooms_json_carries_cabinet_with_bilingual_names():
    """Pin cabinet's spatial metadata in rooms.json. Per the room-refactor (2026-06-08)
    rooms.json no longer carries `devices` arrays -- per-room membership is derived from
    DeviceManager at load time via `DevicePort.get_room()`. The membership assertion
    that used to live here (`"cabinet_spots" in cab["devices"]`) was moved to the
    forward-direction check at the device-config side: cabinet_spots.json must declare
    `room: "cabinet"`, asserted below."""
    rooms = json.loads(ROOMS_JSON.read_text())
    assert "cabinet" in rooms, "cabinet room missing from rooms.json"
    cab = rooms["cabinet"]
    assert cab["names"]["ru"] == "Кабинет"
    assert cab["names"]["en"] == "Study"
    # Forward-direction membership check: cabinet_spots.json must declare room=cabinet.
    slice_cfg = json.loads(DEVICE_CFG.read_text())
    assert slice_cfg.get("room") == "cabinet", (
        "cabinet_spots.json should declare room=cabinet (forward-direction membership)"
    )
