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
        Load or reload room definitions from rooms.json.
        
        This method clears the current rooms and loads them from disk.
        It validates that all referenced devices exist in the device manager.
        """
        rooms_file = self._dir / "rooms.json"
        try:
            logger.info(f"Loading room definitions from {rooms_file}")
            raw = json.loads(rooms_file.read_text(encoding="utf-8"))
            
            # Clear existing rooms
            self.rooms.clear()
            
            # Process each room definition
            for rid, spec in raw.items():
                try:
                    # Normalize room_id to match key if not specified
                    if "room_id" not in spec:
                        spec["room_id"] = rid
                    elif spec["room_id"] != rid:
                        logger.warning(
                            f"Room ID mismatch: key '{rid}' doesn't match room_id '{spec['room_id']}'. "
                            f"Using key '{rid}' as the canonical ID."
                        )
                        spec["room_id"] = rid
                    
                    # Create and validate room definition
                    room = RoomDefinition.model_validate(spec)
                    self._validate_devices_exist(room)
                    
                    # Store valid room
                    self.rooms[rid] = room
                    logger.debug(f"Loaded room {rid} with {len(room.devices)} devices")
                    
                except Exception as e:
                    logger.error(f"Error processing room '{rid}': {str(e)}")
            
            logger.info(f"Successfully loaded {len(self.rooms)} rooms")
            
        except FileNotFoundError:
            logger.warning(f"Room configuration file not found: {rooms_file}")
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing rooms.json: {str(e)}")
        except Exception as e:
            logger.error(f"Error loading rooms: {str(e)}")

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
    
    def _validate_devices_exist(self, room: RoomDefinition) -> None:
        """
        Validate that all devices in a room definition exist in the system.
        
        Args:
            room: The room definition to validate
            
        Raises:
            ValueError: If a device doesn't exist in the device manager
        """
        # Check if a device manager was provided during initialization
        if not self._device_mgr:
            logger.warning(f"No device manager available for validating room '{room.room_id}'")
            return
            
        # Get attribute to handle different DeviceManager implementations
        devices_attr = getattr(self._device_mgr, "devices", None)
        
        if not devices_attr:
            logger.warning(f"Device manager doesn't have a 'devices' attribute - skipping validation for room '{room.room_id}'")
            return
            
        # Check each device in the room
        unknown_devices = [d for d in room.devices if d not in devices_attr]
        
        if unknown_devices:
            error_msg = f"Room '{room.room_id}' references unknown devices: {unknown_devices}"
            logger.error(error_msg)
            raise ValueError(error_msg)

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