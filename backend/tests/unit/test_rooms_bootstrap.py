"""§P3.7 #21 — pin the on-disk rooms.json after the bootstrap.

These tests intentionally hit the REAL `config/rooms.json` (not a mock), so the
authored room set surfaces in tests as soon as it diverges from what voice + the catalog
were promised. The full WB-UI room sweep (10 dashboards + `global`) lands here; the
device-side onboarding (each room's `devices` list filling in) lands in §P3.7 #22+#23.
"""
from __future__ import annotations

import json
from pathlib import Path

from locveil_bridge.domain.scenarios.models import RoomDefinition

ROOMS_JSON = Path(__file__).resolve().parents[3] / "config" / "rooms.json"

# The full WB-UI dashboard sweep (per A2 findings) plus `global` for whole-house
# aggregate devices (§P3.7 #22). `living_room` and `children_room` keep their
# legacy ids (the WB dashboards `livingroom` / `children` map onto them via the
# WB-bootstrap importer in #23, not via a rename). `shower` is the live home's
# semantics for the WB dashboard labelled `wc`.
EXPECTED_ROOM_IDS = {
    "living_room", "children_room", "kitchen", "cabinet",
    "entrance", "hall", "shower", "bathroom", "bedroom", "wardrobe",
    "global",
}


def _load() -> dict:
    return json.loads(ROOMS_JSON.read_text())


def test_rooms_json_contains_full_room_sweep():
    raw = _load()
    assert set(raw.keys()) == EXPECTED_ROOM_IDS, (
        f"rooms.json drift: missing {EXPECTED_ROOM_IDS - set(raw)}, "
        f"unexpected {set(raw) - EXPECTED_ROOM_IDS}"
    )


def test_every_room_validates_as_room_definition():
    """Schema pin: each entry must parse as a RoomDefinition (catches typos in any locale
    block, missing devices list, etc.)."""
    raw = _load()
    for room_id, payload in raw.items():
        rd = RoomDefinition.model_validate(payload)
        assert rd.room_id == room_id, f"room_id {rd.room_id!r} does not match key {room_id!r}"


def test_every_room_has_trilingual_ru_en_de_names():
    """Per the §P3.7 voice contract: every room carries names in every supported locale.
    ru + en + de all required (de added to the new rooms in #21 alongside the pre-slice
    rooms that already carried it)."""
    raw = _load()
    for room_id, payload in raw.items():
        names = payload["names"]
        assert "ru" in names and names["ru"], f"{room_id} missing/empty ru name"
        assert "en" in names and names["en"], f"{room_id} missing/empty en name"
        assert "de" in names and names["de"], f"{room_id} missing/empty de name"


def test_rooms_json_carries_no_devices_arrays():
    """Post room-refactor (2026-06-08): rooms.json carries ONLY spatial metadata
    (room_id + names + description + default_scenario). Per-room `devices` is DERIVED
    from `DeviceManager` at load time via `DevicePort.get_room()`. Any authored
    `devices` array would be ignored anyway; assert it's absent so we don't grow
    stale arrays again."""
    raw = _load()
    offenders = [rid for rid, r in raw.items() if "devices" in r]
    assert not offenders, (
        f"rooms.json entries should NOT carry a `devices` array (derived at load time): {offenders}"
    )


def test_global_room_metadata_present():
    """`global` is where whole-house aggregate devices live (§P3.7 #22). Stays declared
    in rooms.json with metadata only; the derived devices list will populate from
    DeviceManager once #22's aggregate device configs land."""
    raw = _load()
    g = raw["global"]
    assert g["names"]["ru"] == "Весь дом"
    assert g["names"]["en"] == "Whole House"


def test_every_device_config_declares_a_known_room():
    """Forward-direction drift guard (replaces the legacy reverse-direction one that
    walked rooms.json devices lists). Every device config in `config/devices/`
    -- WB-passthrough subtree AND flat AV configs -- must declare a `room` matching an
    entry in `rooms.json`. (`room: null` is allowed for genuinely unassigned devices,
    though after the §P3.7 #23 backfill there shouldn't be any.) Catches the situation
    where someone adds a device with `room: "kitchne"` typo or references a room that
    hasn't been authored yet."""
    raw = _load()
    valid_rooms = set(raw.keys())

    devices_dir = ROOMS_JSON.parent / "devices"
    bad: list[str] = []
    for p in devices_dir.rglob("*.json"):
        spec = json.loads(p.read_text())
        room = spec.get("room")
        if room is None:
            continue  # explicitly unassigned (allowed)
        if room not in valid_rooms:
            bad.append(f"{p.name} declares room={room!r} (not in rooms.json)")
    assert not bad, (
        "Device configs reference unknown room ids:\n  " + "\n  ".join(bad)
        + f"\nKnown rooms: {sorted(valid_rooms)}"
    )


def test_wb_dashboard_mapping_documented_in_description():
    """For the rooms whose symbolic id differs from the WB-UI dashboard id, the importer
    (#23) needs the dashboard hint somewhere. We carry it in the description for now (a
    structured `wb_dashboard_id` field can land alongside the importer if it turns out to
    be needed)."""
    raw = _load()
    assert "livingroom" in raw["living_room"]["description"]
    assert "children" in raw["children_room"]["description"]
    assert "wc" in raw["shower"]["description"]


def test_room_count_matches_wb_dashboards_plus_global():
    """10 WB dashboards (A2 findings) + 1 `global` = 11 rooms. If this trips, either the
    WB-UI added a dashboard we should onboard, or a room was removed in error."""
    raw = _load()
    assert len(raw) == 11
