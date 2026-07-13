"""Group membership resolution for room-scoped canonical addressing (VWB-23).

The third canonical address form (canonical_first.md §10): «включи свет» resolves to
``(room, group, action)`` and the *bridge* decides which devices that means. Membership
is never authored — it is derived here from what already exists: each device's room
(``DevicePort.get_room()``) and its capability map, where a capability's semantic group
defaults to its domain name and profiles override where domain ≠ semantics
(:meth:`Capability.effective_group`).

Pure domain logic: takes the ``{device_id: device}`` mapping duck-typed exactly like the
catalog projection does (``.get_room()`` / ``.config.room`` + ``.capabilities``), so the
offline dump's stand-ins and test fakes work unchanged.
"""

from typing import Any, List, Mapping, NamedTuple, Optional

from locveil_bridge.domain.capabilities.models import CapabilityMap

# §10.5 safety rail: groups whose members may be actuated as a fan-out. Consequential
# groups (`power` — sockets, the oven guard) refuse fan-out with a speakable 409: room-
# wide power-off must never be one mumbled sentence away from the fridge and the NAS
# (the travel case is owned, with curated exclusions, by the `at_home` switch). Extended
# deliberately, never dynamically.
FANOUT_ALLOWED_GROUPS = frozenset({"light", "cover"})


class GroupMember(NamedTuple):
    """One device matched into a room group: the device id plus WHICH capability
    (domain) matched — members execute the group action against their own capability
    (a light switch its `power.on`, the kitchen hood its `light.on`)."""

    device_id: str
    capability: str


def _device_room(device: Any) -> Optional[str]:
    get_room = getattr(device, "get_room", None)
    if callable(get_room):
        room = get_room()
    else:
        cfg = getattr(device, "config", None)
        room = getattr(cfg, "room", None) if cfg is not None else None
    return room if isinstance(room, str) else None


def resolve_members(
    devices: Mapping[str, Any], room_id: str, group: str
) -> List[GroupMember]:
    """Devices in ``room_id`` owning a capability whose effective group is ``group``.

    Sorted by device id for deterministic fan-out order and stable responses. A device
    contributes at most one member (the first matching domain in map order — maps don't
    declare the same semantic group twice in practice).
    """
    members: List[GroupMember] = []
    for device_id in sorted(devices):
        device = devices[device_id]
        if _device_room(device) != room_id:
            continue
        cap_map = getattr(device, "capabilities", None)
        if not isinstance(cap_map, CapabilityMap):
            continue
        for domain, cap in cap_map.root.items():
            if cap.effective_group(domain) == group:
                members.append(GroupMember(device_id=device_id, capability=domain))
                break
    return members
