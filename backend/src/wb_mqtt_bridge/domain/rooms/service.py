from pathlib import Path
import json
import logging
from typing import Dict, List, Optional

from wb_mqtt_bridge.domain.scenarios.models import RoomDefinition
from wb_mqtt_bridge.domain.devices.service import DeviceManager

logger = logging.getLogger(__name__)

class RoomManager:
    """
    Manages room definitions and provides room-related functionality.
    
    The RoomManager loads room definitions from rooms.json, validates them,
    and provides methods to query room information. It acts as the single
    source of truth for room spatial metadata in the system.
    """
    
    def __init__(self, cfg_dir: Path, device_manager: DeviceManager):
        """
        Initialize the RoomManager.
        
        Args:
            cfg_dir: Path to the config directory containing rooms.json
            device_manager: Reference to the DeviceManager instance for device validation
        """
        self._dir = cfg_dir
        self._device_mgr = device_manager
        self.rooms: Dict[str, RoomDefinition] = {}
        
        # Load room definitions immediately
        self.reload()

    # ------------- Public API -------------
    
    def reload(self) -> None:
        """
        Load or reload room definitions from rooms.json + DERIVE per-room device
        membership from `DeviceManager`.

        Source of truth shift (room-refactor 2026-06-08): rooms.json now carries ONLY
        the spatial metadata (room_id, names, description, default_scenario). The
        per-room `devices` list is DERIVED at load time by iterating
        `DeviceManager.devices` and grouping by each device's `get_room()` (via
        `DevicePort`). Any `devices` field still present in rooms.json is ignored.

        This eliminates the duplicated source-of-truth that drifted silently during
        §P3.7 #23 -- now drift is impossible by construction (single declaration site
        per device: `device.config.room`).

        Bootstrap order is already correct: bootstrap.py constructs DeviceManager and
        populates `self._device_mgr.devices` before RoomManager is built. If a device
        declares `room: "X"` but `X` isn't in rooms.json, we log a warning (the device
        is still functional; it just won't appear in any room's catalog projection).
        """
        rooms_file = self._dir / "rooms.json"
        try:
            logger.info(f"Loading room definitions from {rooms_file}")
            raw = json.loads(rooms_file.read_text(encoding="utf-8"))

            # Clear existing rooms
            self.rooms.clear()

            # 1) Parse the metadata-only RoomDefinition for every entry. Any `devices`
            #    field present in the JSON is dropped before parsing -- the derived
            #    list overwrites it below regardless.
            for rid, spec in raw.items():
                try:
                    if "room_id" not in spec:
                        spec["room_id"] = rid
                    elif spec["room_id"] != rid:
                        logger.warning(
                            f"Room ID mismatch: key '{rid}' doesn't match room_id '{spec['room_id']}'. "
                            f"Using key '{rid}' as the canonical ID."
                        )
                        spec["room_id"] = rid
                    # Strip any legacy `devices` field so derived membership is the
                    # sole writer; keeps behaviour identical whether the JSON still
                    # carries the array (transitional) or has been cleaned (target).
                    spec.pop("devices", None)
                    self.rooms[rid] = RoomDefinition.model_validate(spec)
                except Exception as e:
                    logger.error(f"Error processing room '{rid}': {str(e)}")

            # 2) Walk DeviceManager and group devices into their declared rooms.
            self._populate_devices_from_device_manager()

            # 3) Validate authored group_defaults (canonical_first.md §10.3): each entry
            #    must name a device that is in the room AND a member of the group.
            #    Invalid entries are dropped (error-logged) so a stale default degrades
            #    to fan-out / no_default_device instead of misfiring at dispatch time.
            self._validate_group_defaults()

            logger.info(
                f"Successfully loaded {len(self.rooms)} rooms; populated devices via DeviceManager."
            )

        except FileNotFoundError:
            logger.warning(f"Room configuration file not found: {rooms_file}")
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing rooms.json: {str(e)}")
        except Exception as e:
            logger.error(f"Error loading rooms: {str(e)}")

    def _validate_group_defaults(self) -> None:
        """Drop `group_defaults` entries whose device isn't in the room or isn't a
        member of the group (membership = the §10 group overlay, resolved against the
        live capability maps via :func:`resolve_members`)."""
        from wb_mqtt_bridge.domain.rooms.groups import resolve_members

        devices = getattr(self._device_mgr, "devices", {}) or {}
        for room in self.rooms.values():
            if not room.group_defaults:
                continue
            valid: Dict[str, str] = {}
            for group, device_id in room.group_defaults.items():
                member_ids = {m.device_id for m in resolve_members(devices, room.room_id, group)}
                if device_id in member_ids:
                    valid[group] = device_id
                else:
                    logger.error(
                        f"rooms.json: group_defaults[{group!r}] = {device_id!r} in room "
                        f"'{room.room_id}' is not a member of that group in that room — "
                        f"entry dropped (will fan out / 409 instead)"
                    )
            room.group_defaults = valid or None

    def list(self) -> List[RoomDefinition]:
        """
        Return a list of all room definitions.
        
        Returns:
            List of all room definitions
        """
        return list(self.rooms.values())

    def get(self, room_id: str) -> Optional[RoomDefinition]:
        """
        Get a room definition by ID.
        
        Args:
            room_id: The ID of the room to retrieve
            
        Returns:
            The room definition or None if not found
        """
        return self.rooms.get(room_id)

    def contains_device(self, room_id: str, device_id: str) -> bool:
        """
        Check if a room contains a specific device.
        
        Args:
            room_id: The ID of the room to check
            device_id: The ID of the device to look for
            
        Returns:
            True if the device is in the room, False otherwise
        """
        room = self.rooms.get(room_id)
        return bool(room and device_id in room.devices)

    def default_scenario(self, room_id: str) -> Optional[str]:
        """
        Get the default scenario ID for a room.
        
        Args:
            room_id: The ID of the room
            
        Returns:
            The default scenario ID or None if not defined
        """
        room = self.rooms.get(room_id)
        return room.default_scenario if room else None
    
    def get_device_room(self, device_id: str) -> Optional[str]:
        """
        Find which room a device belongs to.
        
        Args:
            device_id: The ID of the device to locate
            
        Returns:
            The room ID containing the device or None if not found
        """
        for room_id, room in self.rooms.items():
            if device_id in room.devices:
                return room_id
        return None
    
    def get_devices_by_room(self) -> Dict[str, List[str]]:
        """
        Get a mapping of room IDs to lists of device IDs.
        
        Returns:
            Dict mapping room IDs to lists of device IDs contained in each room
        """
        return {room_id: list(room.devices) for room_id, room in self.rooms.items()}

    # ------------- Internal Methods -------------

    def _populate_devices_from_device_manager(self) -> None:
        """
        Walk DeviceManager and populate each room's `devices` list from the devices
        that declare it via `DevicePort.get_room()`. Devices whose `get_room()`
        returns a room_id not in `self.rooms` log a warning -- they remain functional
        but stay invisible to room-membership consumers (catalog, scenarios, voice).

        Direction inverted from the legacy `_validate_devices_exist`: previously
        rooms.json was authoritative and we checked that every listed device_id
        existed; now device configs are authoritative and we group them by their
        declared room.
        """
        if not self._device_mgr:
            logger.warning("No device manager available; rooms will have empty `devices`.")
            return

        devices_attr = getattr(self._device_mgr, "devices", None)
        if not devices_attr:
            logger.warning("Device manager has no `devices` attribute; rooms will be empty.")
            return

        # Reset every room to empty before populating (idempotent across reload()).
        for room in self.rooms.values():
            room.devices = []

        unknown_room_count = 0
        for device_id, device in devices_attr.items():
            room_id = device.get_room() if hasattr(device, "get_room") else None
            if room_id is None:
                continue  # device explicitly unassigned (None is legal)
            if room_id not in self.rooms:
                logger.warning(
                    f"Device {device_id!r} declares room {room_id!r} which is not in "
                    f"rooms.json — device will not appear in any room's catalog projection."
                )
                unknown_room_count += 1
                continue
            self.rooms[room_id].devices.append(device_id)

        # Keep deterministic order so the catalog hash stays stable across restarts.
        for room in self.rooms.values():
            room.devices.sort()

        for room_id, room in self.rooms.items():
            logger.debug(f"Room {room_id!r} populated with {len(room.devices)} devices.")
        if unknown_room_count:
            logger.warning(
                f"{unknown_room_count} device(s) reference room_ids unknown to rooms.json."
            )

    # PLACEHOLDER: Add proper implementation for resource cleanup
    async def shutdown(self) -> None:
        """
        Clean up resources and perform orderly shutdown.
        
        This method handles any necessary cleanup operations
        for the RoomManager before application shutdown.
        """
        logger = logging.getLogger(__name__)
        logger.info("Shutting down RoomManager")
        
        # Currently RoomManager has no persistent connections or background tasks
        # but this method is added for consistency and future extensions
        
        # TODO: Add any cleanup operations if needed in the future
        
        logger.info("RoomManager shutdown complete") 