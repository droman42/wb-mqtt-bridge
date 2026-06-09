"""Build the flat capability-shaped catalog response for `GET /system/catalog`.

§P3.7 voice-integration slice #17. The catalog is the stable read contract any non-UI
consumer (Irene first) talks to — it's deliberately separate from the Layer-3 layout
manifest, which is UI-shaped (panels, slider widgets, positions).

Resolution:

- Rooms: read directly from `RoomManager.list()` (which reads `rooms.json`); the room's
  `devices` list IS the authored membership ("which devices live here"). Reused verbatim,
  so the catalog room shape matches the long-standing `/room/list` shape.
- Devices: iterate `DeviceManager.devices`, project each device's
  `config.{device_id, names, device_class, room}` and walk its attached `capabilities`
  (`CapabilityMap` — the class-default merged with the §P3.7 capability profile and any
  per-instance override; see #14). For each capability, surface the canonical action
  names only; param introspection lands with the vocab extension (#19).
- Version: short SHA-256 of the canonical JSON of {rooms, devices}, so Irene can
  subscribe to retained `bridge/catalog/version` and only re-fetch on a real change.

The builder takes the live managers as arguments (no global state, no hidden imports of
the FastAPI router state) so the tests can pin behaviour with simple fakes.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Mapping, Optional

from wb_mqtt_bridge.domain.capabilities.models import CapabilityMap
from wb_mqtt_bridge.presentation.api.schemas import (
    CatalogAction,
    CatalogCapability,
    CatalogDevice,
    CatalogField,
    CatalogResponse,
    CatalogRoom,
    CatalogValueLabel,
)


def _project_capability_actions(
    cap_map: Optional[CapabilityMap],
    mirrored_field_names: Optional[set[str]] = None,
) -> list[CatalogCapability]:
    """Walk a CapabilityMap and project to the catalog's capability shape — actions and
    (since §P3.7 #19) read-only fields. Param introspection per-action is still owed work
    and not yet surfaced.

    `mirrored_field_names` (§P3.7 #23 / sauna-sensor case): the set of field names the
    device actually mirrors via `state_topics`. When provided, profile fields[] are
    FILTERED to only the names in the set -- so a device with `sensor_room` profile that
    only mirrors `temperature` + `humidity` emits only those two in the catalog, not the
    full 5 the profile declares. When `None` (AV devices that don't have `state_topics`
    at all), no filtering happens and every profile-declared field is emitted as before.
    """
    out: list[CatalogCapability] = []
    if cap_map is None:
        return out
    for cap_name, cap in cap_map.root.items():
        actions: list[CatalogAction] = []
        for action_name in cap.actions:
            actions.append(CatalogAction(name=action_name, params=None))
        fields: list[CatalogField] = []
        for f in cap.fields:
            if mirrored_field_names is not None and f.name not in mirrored_field_names:
                continue
            projected_values: Optional[list[CatalogValueLabel]] = None
            if f.values is not None:
                projected_values = [
                    CatalogValueLabel(
                        wire=v.wire,
                        canonical=v.canonical,
                        labels=v.labels.model_dump() if v.labels is not None else None,
                    )
                    for v in f.values
                ]
            fields.append(CatalogField(
                name=f.name,
                type=f.type,
                encoding=f.encoding,
                values=projected_values,
                unit=f.unit,
                labels=f.labels.model_dump() if f.labels is not None else None,
            ))
        out.append(CatalogCapability(
            name=cap_name,
            actions=actions if actions else None,
            fields=fields if fields else None,
        ))
    return out


def _project_devices(devices_iterable: Iterable) -> list[CatalogDevice]:
    """Build a list of CatalogDevice from anything iterating to device objects with
    `.config` (carrying device_id, names, device_class, room) and `.capabilities`."""
    out: list[CatalogDevice] = []
    for device in devices_iterable:
        cfg = getattr(device, "config", None)
        if cfg is None:
            continue
        names = cfg.names
        # `names` may be a Pydantic LocalizedName or a dict-shaped fallback from a fake.
        if hasattr(names, "model_dump"):
            names_dict = names.model_dump()
        elif isinstance(names, Mapping):
            names_dict = dict(names)
        else:
            names_dict = dict(vars(names))
        # Field filtering by what the device actually mirrors (§P3.7 #23 sauna-sensor case).
        # WB-passthrough configs declare `state_topics`; AV configs don't have that attribute.
        # `None` = no filter (AV devices keep emitting every profile-declared field).
        state_topics = getattr(cfg, "state_topics", None)
        mirrored_field_names: Optional[set[str]] = (
            set(state_topics.keys()) if state_topics is not None else None
        )
        out.append(CatalogDevice(
            id=cfg.device_id,
            names=names_dict,
            device_class=cfg.device_class,
            room=getattr(cfg, "room", None),
            capabilities=_project_capability_actions(
                getattr(device, "capabilities", None), mirrored_field_names,
            ),
        ))
    out.sort(key=lambda d: d.id)  # stable order -> stable hash
    return out


def _project_rooms(rooms_iterable: Iterable) -> list[CatalogRoom]:
    """Build a list of CatalogRoom from anything iterating to room definitions with
    `.room_id`, `.names`, `.devices`."""
    out: list[CatalogRoom] = []
    for room in rooms_iterable:
        names = room.names if hasattr(room, "names") else {}
        names_dict = dict(names) if isinstance(names, Mapping) else dict(names)
        out.append(CatalogRoom(
            id=room.room_id,
            names=names_dict,
            devices=list(room.devices),
        ))
    out.sort(key=lambda r: r.id)
    return out


def _content_hash(rooms: list[CatalogRoom], devices: list[CatalogDevice]) -> str:
    """Deterministic short hash of the catalog content. Same content -> same value; any
    change to rooms or devices flips it. Truncated to 16 hex chars (64 bits) -- plenty
    for a "did anything change?" signal."""
    payload = {
        "rooms": [r.model_dump() for r in rooms],
        "devices": [d.model_dump() for d in devices],
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def build_catalog(device_manager: Any, room_manager: Any) -> CatalogResponse:
    """Build the full catalog response from live managers. `device_manager.devices` is a
    `{device_id: device}` dict (per DeviceManager); `room_manager.list()` returns
    RoomDefinitions (per RoomManager)."""
    rooms = _project_rooms(room_manager.list() if room_manager is not None else [])
    devices = _project_devices(
        (device_manager.devices.values() if device_manager is not None else [])
    )
    return CatalogResponse(
        version=_content_hash(rooms, devices),
        rooms=rooms,
        devices=devices,
    )
