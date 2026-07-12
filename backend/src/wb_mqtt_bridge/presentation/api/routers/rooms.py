import asyncio
import logging
from typing import Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from wb_mqtt_bridge.domain.rooms.groups import (
    FANOUT_ALLOWED_GROUPS,
    GroupMember,
    resolve_members,
)
from wb_mqtt_bridge.presentation.api.routers.devices import dispatch_device_canonical
from wb_mqtt_bridge.presentation.api.schemas import (
    CanonicalActionRequest,
    CanonicalError,
    CanonicalErrorCode,
    GroupMemberResult,
    RoomCanonicalRequest,
    RoomCanonicalResponse,
)

logger = logging.getLogger(__name__)

# Create router with appropriate prefix and tags
router = APIRouter(
    tags=["Rooms"]
)

# Global references that will be set during initialization
room_manager = None
device_manager = None

def initialize(room_mgr, device_mgr=None):
    """Initialize global references needed by router endpoints."""
    global room_manager, device_manager
    room_manager = room_mgr
    device_manager = device_mgr

class RoomDefinitionResponse(BaseModel):
    """Response model for room definitions."""
    room_id: str
    names: Dict[str, str]
    description: str
    devices: List[str]
    default_scenario: Optional[str] = None
    group_defaults: Optional[Dict[str, str]] = None

@router.get("/room/list", response_model=List[RoomDefinitionResponse])
async def list_rooms():
    """
    Get a list of all room definitions.

    Returns:
        List[RoomDefinitionResponse]: List of room definitions

    Raises:
        HTTPException: If service not initialized
    """
    if not room_manager:
        raise HTTPException(status_code=503, detail="Service not fully initialized")

    return room_manager.list()

@router.get("/room/{room_id}", response_model=RoomDefinitionResponse)
async def get_room(room_id: str):
    """
    Get a specific room definition.

    Args:
        room_id: The ID of the room to retrieve

    Returns:
        RoomDefinitionResponse: The room definition

    Raises:
        HTTPException: If room not found or service not initialized
    """
    if not room_manager:
        raise HTTPException(status_code=503, detail="Service not fully initialized")

    room = room_manager.get(room_id)
    if not room:
        raise HTTPException(status_code=404, detail=f"Room '{room_id}' not found")

    return room


# ---- POST /rooms/{room_id}/canonical (VWB-23, canonical_first.md §10) -------------

def _err(room_id: str, payload: RoomCanonicalRequest,
         code: CanonicalErrorCode, message: str) -> RoomCanonicalResponse:
    return RoomCanonicalResponse(
        success=False, room_id=room_id, group=payload.group, action=payload.action,
        error=CanonicalError(code=code, message=message),
    )


async def _dispatch_member(member: GroupMember, payload: RoomCanonicalRequest) -> GroupMemberResult:
    """Run the group action against ONE member through the identical per-device
    canonical path (§10.1: the group verb names the intent, each member keeps its
    native grammar). Maps the device endpoint's outcomes onto the §10.4 statuses:
    `action_not_supported` -> skipped (reported, never an error); other failures ->
    failed with the member's error message; `no_op` flag -> no_op."""
    request = CanonicalActionRequest(
        capability=member.capability, action=payload.action,
        params=payload.params, wait=payload.wait,
    )
    try:
        resp = await dispatch_device_canonical(member.device_id, request)
    except HTTPException as e:
        detail = e.detail if isinstance(e.detail, dict) else {}
        error = detail.get("error") or {}
        code = error.get("code")
        message = error.get("message") or str(e.detail)
        if code == CanonicalErrorCode.ACTION_NOT_SUPPORTED.value:
            return GroupMemberResult(
                device_id=member.device_id, capability=member.capability,
                status="skipped", detail=message,
            )
        return GroupMemberResult(
            device_id=member.device_id, capability=member.capability,
            status="failed", detail=message,
        )
    except Exception as e:  # a member crashing must not sink the whole fan-out
        logger.error(f"Group dispatch to {member.device_id} raised: {e}")
        return GroupMemberResult(
            device_id=member.device_id, capability=member.capability,
            status="failed", detail=str(e),
        )
    return GroupMemberResult(
        device_id=member.device_id, capability=member.capability,
        status="no_op" if resp.no_op else "executed",
    )


@router.post(
    "/rooms/{room_id}/canonical",
    response_model=RoomCanonicalResponse,
    responses={
        404: {"model": RoomCanonicalResponse},
        409: {"model": RoomCanonicalResponse},
    },
)
async def execute_room_canonical_action(room_id: str, payload: RoomCanonicalRequest):
    """Room-scoped group actuation — the third canonical address form.
    For utterances that name a capability, not a device
    («включи свет», «закрой шторы»): the caller supplies room + group + action, the
    bridge owns membership (the `group` overlay on capability maps) and the
    default-vs-fan-out policy (`scope` + the room's `group_defaults`).

    Members execute concurrently through the SAME per-device canonical dispatch the
    device endpoint uses (per-member no_op short-circuit, echo wait, `update_state`
    chokepoint — all unchanged). 200 even with partial member failures; the per-member
    `results` list is what makes the caller's confirmation honest.

    Speakable errors:
      - `404 no_group_members` — nothing in this room belongs to the group;
      - `409 no_default_device` — scope=one but the room declares no default;
      - `409 fanout_not_allowed` — a fan-out would be required but the group is not on
        the allow-list (`light`, `cover`); consequential groups (`power`, …) need an
        explicit device or scenario.
    """
    if not room_manager or not device_manager:
        raise HTTPException(status_code=503, detail="Service not fully initialized")

    room = room_manager.get(room_id)
    if not room:
        raise HTTPException(status_code=404, detail=f"Room '{room_id}' not found")

    members = resolve_members(getattr(device_manager, "devices", {}) or {}, room_id, payload.group)
    if not members:
        resp = _err(room_id, payload, CanonicalErrorCode.NO_GROUP_MEMBERS,
                    f"No device in room {room_id!r} belongs to group {payload.group!r}")
        raise HTTPException(status_code=404, detail=resp.model_dump())

    # Scope policy (§10.1): which members actually actuate.
    default_id = (getattr(room, "group_defaults", None) or {}).get(payload.group)
    default_member = next((m for m in members if m.device_id == default_id), None)

    targets: List[GroupMember]
    scope_applied: Literal["default", "fan_out"]
    if payload.scope == "one":
        if default_member is None:
            resp = _err(room_id, payload, CanonicalErrorCode.NO_DEFAULT_DEVICE,
                        f"Room {room_id!r} declares no default device for group {payload.group!r}")
            raise HTTPException(status_code=409, detail=resp.model_dump())
        targets, scope_applied = [default_member], "default"
    elif payload.scope == "auto" and default_member is not None:
        targets, scope_applied = [default_member], "default"
    else:  # scope == "all", or auto without a configured default
        targets, scope_applied = members, "fan_out"

    # §10.5 safety rail: fan-out only for benign groups, REGARDLESS of member count —
    # a consequential group must never actuate as an unnamed plural.
    if scope_applied == "fan_out" and payload.group not in FANOUT_ALLOWED_GROUPS:
        resp = _err(room_id, payload, CanonicalErrorCode.FANOUT_NOT_ALLOWED,
                    f"Group {payload.group!r} does not allow fan-out; name a device "
                    f"(or configure a room default and use scope 'one'/'auto')")
        raise HTTPException(status_code=409, detail=resp.model_dump())

    results = list(await asyncio.gather(*(_dispatch_member(m, payload) for m in targets)))
    return RoomCanonicalResponse(
        success=any(r.status in ("executed", "no_op") for r in results),
        room_id=room_id, group=payload.group, action=payload.action,
        scope_applied=scope_applied, results=results, error=None,
    )
