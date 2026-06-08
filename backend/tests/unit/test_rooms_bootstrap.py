"""§P3.7 #21 — pin the on-disk rooms.json after the bootstrap.

These tests intentionally hit the REAL `backend/config/rooms.json` (not a mock), so the
authored room set surfaces in tests as soon as it diverges from what voice + the catalog
were promised. The full WB-UI room sweep (10 dashboards + `global`) lands here; the
device-side onboarding (each room's `devices` list filling in) lands in §P3.7 #22+#23.
"""
from __future__ import annotations

import json
from pathlib import Path

from wb_mqtt_bridge.domain.scenarios.models import RoomDefinition

ROOMS_JSON = Path(__file__).resolve().parents[2] / "config" / "rooms.json"

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


def test_global_room_present_and_empty_for_aggregate_devices():
    """`global` is where whole-house aggregate devices live (§P3.7 #22). It seeds empty:
    the aggregate device configs are added in #22 and they bring themselves in via the
    standard device → room membership flow."""
    raw = _load()
    g = raw["global"]
    assert g["names"]["ru"] == "Весь дом"
    assert g["names"]["en"] == "Whole House"
    assert g["devices"] == [], (
        "global must start empty; aggregate devices are added in §P3.7 #22"
    )


def test_legacy_rooms_preserve_existing_device_membership():
    """Renaming-by-stealth check: the bootstrap MUST NOT drop devices from the rooms that
    already had members (`living_room`, `children_room`, `kitchen`, `cabinet`). If a device
    is missing here it'll silently fall out of every catalog/scenario reference."""
    raw = _load()
    assert "living_room_tv" in raw["living_room"]["devices"]
    assert "processor" in raw["living_room"]["devices"]
    assert "children_room_tv" in raw["children_room"]["devices"]
    assert "kitchen_hood" in raw["kitchen"]["devices"]
    assert "cabinet_spots" in raw["cabinet"]["devices"]


def test_global_room_stays_empty_until_aggregate_devices_land():
    """`global` is the only room that should still be empty after #23 completes -- it's
    reserved for whole-house aggregate devices (#22) which are deferred until the voice
    command set requires them. All physical rooms are onboarded by the end of #23.

    Trajectory:
    - #21 bootstrap: 6 new rooms + global all started empty
    - #23: every physical room got at least one device; global stays untouched

    Today's still-empty set: global only (#22 fills it when voice command set requires)."""
    raw = _load()
    assert raw["global"]["devices"] == [], (
        "global should stay empty until §P3.7 #22 ships the aggregate devices"
    )


def test_rooms_json_devices_match_wb_passthrough_configs():
    """Drift guard (§P3.7 #23): every WB-passthrough device config under
    `wb-devices/<room>/` MUST also appear in rooms.json's `devices` list for that room.
    The catalog's room → devices projection reads from RoomManager (rooms.json), so a
    device declared with `room: foo` but missing from `foo.devices` is invisible to
    voice/UI even though it exists. Catches the kind of drift surfaced mid-children_room
    session on 2026-06-08 where 19 devices had piled up missing from rooms.json."""
    import sys as _sys
    _sys.path.insert(0, "src")
    from wb_mqtt_bridge.infrastructure.config.models import WbPassthroughDeviceConfig

    wb_devices_dir = ROOMS_JSON.parent / "devices" / "wb-devices"
    by_room: dict[str, set[str]] = {}
    for p in wb_devices_dir.rglob("*.json"):
        cfg = WbPassthroughDeviceConfig(**json.loads(p.read_text()))
        by_room.setdefault(cfg.room or "<missing>", set()).add(cfg.device_id)

    rooms = _load()
    missing: list[str] = []
    for room_id, devs in by_room.items():
        listed = set(rooms.get(room_id, {}).get("devices", []))
        for dev in devs:
            if dev not in listed:
                missing.append(f"{dev!r} (room={room_id!r})")
    assert not missing, (
        "rooms.json `devices` list is out of sync with WB-passthrough configs — "
        "the following devices declare a room but aren't listed in that room's `devices`:\n  "
        + "\n  ".join(sorted(missing))
        + "\nEither add them to rooms.json or drop the `room` field from the device config."
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
