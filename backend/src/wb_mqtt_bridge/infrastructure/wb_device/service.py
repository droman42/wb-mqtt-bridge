"""WB Virtual Device Service - Config-driven abstraction for WB virtual device operations."""

import json
import logging
import re
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union, Awaitable

from wb_mqtt_bridge.domain.ports import MessageBusPort
from wb_mqtt_bridge.infrastructure.config.models import BaseDeviceConfig

# Type alias for the per-device state provider injected at WB setup. Lets WB-publish
# read the device's current state at callback time without holding a device reference.
StateProvider = Callable[[], Any]

logger = logging.getLogger(__name__)

# Type alias for command executor callback
CommandExecutor = Callable[[str, str, Dict[str, Any]], Awaitable[Any]]

# Capability domains that never get a WB control (UI-only). Layer-3 re-key: the old group exclusion
# was {pointer, gestures, noops, media}; gestures doesn't exist, and noops/media are now exposed:false
# (handled by the `exposed` check), leaving pointer as the only WB-excluded domain.
_WB_EXCLUDED_DOMAINS = {"pointer"}

# A few capability domain names differ from the legacy `group` strings the WB type/order heuristics
# key off. Alias the domain to the expected string so the re-key is byte-equivalent to the group path.
_DOMAIN_GROUP_ALIAS = {"input": "inputs"}


def _commands_by_domain(capabilities: Any) -> Dict[str, str]:
    """Map each native command name -> its capability domain. Walks actions / zones / select /
    by_value / list (incl. nested sequences). First domain wins on the rare shared command."""
    out: Dict[str, str] = {}
    if capabilities is None:
        return out

    def _walk(ca: Any, domain: str) -> None:
        if ca is None:
            return
        cmd = getattr(ca, "command", None)
        if cmd:
            out.setdefault(cmd, domain)
        for sub in (getattr(ca, "sequence", None) or []):
            _walk(sub, domain)

    root = getattr(capabilities, "root", None) or {}
    for domain, cap in root.items():
        for ca in (getattr(cap, "actions", None) or {}).values():
            _walk(ca, domain)
        sel = getattr(cap, "select", None)
        if sel is not None:
            if getattr(sel, "command", None):
                out.setdefault(sel.command, domain)
            for ca in (getattr(sel, "by_value", None) or {}).values():
                _walk(ca, domain)
        _walk(getattr(cap, "list", None), domain)
        for zone in (getattr(cap, "zones", None) or {}).values():
            for ca in (getattr(zone, "actions", None) or {}).values():
                _walk(ca, domain)
    return out


class WBVirtualDeviceService:
    """Infrastructure service for WB virtual device operations using existing config schemas."""
    
    def __init__(self, message_bus: MessageBusPort):
        self.message_bus = message_bus
        self._active_devices: Dict[str, Dict[str, Any]] = {}  # Track active WB devices
        self._command_executors: Dict[str, CommandExecutor] = {}  # Device ID -> executor mapping
    
    async def setup_wb_device_from_config(
        self,
        config: Union[BaseDeviceConfig, Dict[str, Any]],
        command_executor: CommandExecutor,
        driver_name: str = "wb_mqtt_bridge",
        device_type: Optional[str] = None,
        entity_id: Optional[str] = None,      # Virtual entity abstraction (Phase 3 enhancement)
        entity_name: Optional[str] = None,    # Virtual entity abstraction (Phase 3 enhancement)
        capabilities: Any = None,             # device capability map → WB exposure/type/order (Layer-3 re-key)
        state_provider: Optional[StateProvider] = None,  # zero-arg callable returning current device state — used by publish_device_state_changes
    ) -> bool:
        """Set up WB virtual device using existing config schema patterns.
        
        Args:
            config: Device configuration (BaseDeviceConfig or dict)
            command_executor: Callback for executing commands
            driver_name: WB driver name
            device_type: WB device type override
            entity_id: Virtual entity ID override (for scenarios, uses scenario_id instead of device_id)
            entity_name: Virtual entity name override (for scenarios, uses scenario name instead of device_name)
        """
        # Init defaults so the except clause + later code see them defined even
        # if the very first extraction line raises.
        config_device_id = "<unknown>"
        config_device_name = "<unknown>"
        enable_wb = True
        try:
            # Extract device identity from config. Bilingual names live under config.names
            # (LocalizedName); WB virtual device meta uses the Russian rendering since the
            # Wirenboard UI is ru-default in this deployment.
            if isinstance(config, dict):
                config_device_id = config["device_id"]
                config_device_name = config["names"]["ru"]
                enable_wb = config.get("enable_wb_emulation", True)
            else:
                config_device_id = config.device_id
                config_device_name = config.names.ru
                enable_wb = getattr(config, 'enable_wb_emulation', True)
            
            # Apply virtual entity overrides for WB operations (scenarios use scenario_id/name)
            wb_device_id = entity_id if entity_id is not None else config_device_id
            wb_device_name = entity_name if entity_name is not None else config_device_name
            
            # Use config device_id for internal tracking to avoid conflicts
            tracking_device_id = config_device_id
            
            # Check if WB emulation is enabled
            if not enable_wb:
                logger.debug(f"WB emulation disabled for device {config_device_id}")
                return False
            
            # Validate configuration before setup
            is_valid, validation_results = self._validate_wb_configuration_from_config(config)
            if not is_valid:
                logger.error(f"WB configuration validation failed for {config_device_id}")
                logger.error(f"Validation results: {validation_results}")
                return False
            
            # Log warnings even if configuration is valid
            if validation_results.get('warnings'):
                for warning in validation_results['warnings']:
                    logger.warning(f"WB setup warning for {config_device_id}: {warning}")
            
            # Store device info and executor (use tracking_device_id for internal state)
            self._active_devices[tracking_device_id] = {
                "config": config,
                "driver_name": driver_name,
                "device_type": device_type or (getattr(config, 'device_class', None) or 'device'),
                "device_name": wb_device_name,  # Store the virtual device name
                "wb_device_id": wb_device_id,   # Store virtual WB device ID for MQTT operations
                "config_device_id": config_device_id,  # Store original config device ID for reference
                "state_provider": state_provider,  # zero-arg callable → current device state (Invariant B chokepoint)
            }
            self._command_executors[tracking_device_id] = command_executor
            
            # Publish device metadata (use virtual WB identifiers)
            await self._publish_wb_device_meta(wb_device_id, wb_device_name, driver_name, device_type)
            
            # Publish control metadata and initial states (use virtual WB device ID)
            await self._publish_wb_control_metas(wb_device_id, config, capabilities)
            
            # Set up Last Will Testament for offline detection (use virtual WB device ID)
            await self._setup_wb_last_will(wb_device_id)
            
            logger.info(f"WB virtual device emulation enabled for {config_device_id} as WB device {wb_device_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting up WB device for {config_device_id}: {str(e)}")
            return False
    
    async def cleanup_wb_device(self, tracking_device_id: str) -> bool:
        """Clean up WB virtual device.
        
        Args:
            tracking_device_id: The internal tracking device ID (config device_id) 
        """
        try:
            if tracking_device_id not in self._active_devices:
                logger.warning(f"Device {tracking_device_id} not found in active devices")
                return False
            
            # Get virtual WB device ID for MQTT operations
            device_info = self._active_devices[tracking_device_id]
            wb_device_id = device_info.get('wb_device_id', tracking_device_id)  # Fallback to tracking ID
            
            # Mark device as offline (use virtual WB device ID)
            error_topic = f"/devices/{wb_device_id}/meta/error"
            await self.message_bus.publish(error_topic, "offline", retain=True, qos=1)
            
            # Mark device as unavailable (use virtual WB device ID)
            availability_topic = f"/devices/{wb_device_id}/meta/available"
            await self.message_bus.publish(availability_topic, "0", retain=True, qos=1)
            
            # Remove from active devices (use tracking device ID)
            del self._active_devices[tracking_device_id]
            if tracking_device_id in self._command_executors:
                del self._command_executors[tracking_device_id]
            
            logger.debug(f"Cleaned up WB device state for {tracking_device_id} (WB device: {wb_device_id})")
            return True
            
        except Exception as e:
            logger.error(f"Error cleaning up WB device {tracking_device_id}: {str(e)}")
            return False
    
    def get_subscription_topics_from_config(
        self,
        config: Union[BaseDeviceConfig, Dict[str, Any]],
        entity_id: Optional[str] = None,
        capabilities: Any = None,
    ) -> List[str]:
        """Get MQTT subscription topics from config.

        A command gets a ``…/on`` subscribe topic iff it gets a WB control — so this is derived
        directly from :meth:`build_wb_controls_from_config` (same exclusion/classification source),
        guaranteeing the subscribe set never diverges from the published controls.

        Args:
            config: Device configuration
            entity_id: Virtual entity ID override (for scenarios, uses scenario_id instead of device_id)
            capabilities: Device capability map (Layer-3 re-key; falls back to config group if None)
        """
        topics: List[str] = []
        try:
            if isinstance(config, dict):
                config_device_id = config["device_id"]
                enable_wb = config.get("enable_wb_emulation", True)
            else:
                config_device_id = config.device_id
                enable_wb = getattr(config, 'enable_wb_emulation', True)

            if not enable_wb:
                return topics

            wb_device_id = entity_id if entity_id is not None else config_device_id
            for cmd_name in self.build_wb_controls_from_config(config, capabilities):
                topics.append(f"/devices/{wb_device_id}/controls/{cmd_name}/on")

        except Exception as e:
            logger.error(f"Error getting subscription topics from config: {str(e)}")

        return topics
    
    def _find_tracking_device_id_by_wb_id(self, wb_device_id: str) -> Optional[str]:
        """Find tracking device ID from virtual WB device ID.
        
        Args:
            wb_device_id: Virtual WB device ID
            
        Returns:
            Tracking device ID if found, None otherwise
        """
        for tracking_id, device_info in self._active_devices.items():
            stored_wb_id = device_info.get('wb_device_id', tracking_id)
            if stored_wb_id == wb_device_id:
                return tracking_id
        return None
    
    async def handle_wb_message(self, topic: str, payload: str, wb_device_id: str) -> bool:
        """Handle WB command messages.
        
        Args:
            topic: MQTT topic
            payload: MQTT payload
            wb_device_id: Virtual WB device ID (extracted from topic)
        """
        try:
            # Find tracking device ID from virtual WB device ID
            tracking_device_id = self._find_tracking_device_id_by_wb_id(wb_device_id)
            if not tracking_device_id:
                logger.warning(f"Received WB message for unknown WB device {wb_device_id}")
                return False
            
            if tracking_device_id not in self._command_executors:
                logger.warning(f"No command executor found for device {tracking_device_id}")
                return False
            
            # Check if this is a WB command topic (use virtual WB device ID)
            if not self._is_wb_command_topic(topic, wb_device_id):
                logger.warning(f"Invalid WB command topic: {topic}")
                return False
            
            # Extract control name from topic (use virtual WB device ID)
            match = re.match(f"/devices/{re.escape(wb_device_id)}/controls/(.+)/on", topic)
            if not match:
                logger.warning(f"Could not extract control name from topic: {topic}")
                return False
            
            control_name = match.group(1)
            
            # Get device config and find command configuration (use tracking device ID)
            device_info = self._active_devices[tracking_device_id]
            config = device_info["config"]
            
            if isinstance(config, dict):
                commands = config.get("commands", {})
            else:
                commands = config.commands
            
            if control_name not in commands:
                logger.warning(f"No command configuration found for WB control: {control_name}")
                return False
            
            cmd_config = commands[control_name]
            
            # Process parameters from payload using command configuration
            params = self._process_wb_command_payload_from_config(control_name, cmd_config, payload)
            
            # Execute the command via callback (use tracking device ID).
            executor = self._command_executors[tracking_device_id]
            await executor(control_name, payload, params)

            # Note: we no longer echo the incoming payload back to the value topic here.
            # The driver's `update_state(...)` call inside its handler triggers the state-
            # change callback chain, which publishes the device's RESULTING state via
            # `publish_device_state_changes`. Echoing the incoming payload would be (a)
            # redundant in the happy path and (b) wrong when the driver settles on a value
            # different from what was sent (toggle, normalization, rejection). Drivers that
            # don't call `update_state` are bugs and are caught by the per-driver audit, not
            # papered over here.

            return True
            
        except Exception as e:
            logger.error(f"Error handling WB message for WB device {wb_device_id}: {str(e)}")
            return False
    
    async def update_control_state(self, device_id: str, control_name: str, value: str) -> bool:
        """Update WB control state."""
        try:
            if device_id not in self._active_devices:
                logger.warning(f"Device {device_id} not found in active devices")
                return False
            
            await self._update_wb_control_state(device_id, control_name, value)
            return True
            
        except Exception as e:
            logger.error(f"Error updating control state for {device_id}/{control_name}: {str(e)}")
            return False
    
    async def handle_mqtt_reconnection(self, device_id: str) -> bool:
        """Handle MQTT reconnection for a specific device."""
        try:
            if device_id not in self._active_devices:
                logger.warning(f"Device {device_id} not found in active devices")
                return False
            
            device_info = self._active_devices[device_id]
            config = device_info["config"]
            device_name = device_info["device_name"]
            driver_name = device_info["driver_name"]
            device_type = device_info["device_type"]
            
            logger.info(f"Handling MQTT reconnection for WB device {device_id}")
            
            # Republish device metadata
            await self._publish_wb_device_meta(device_id, device_name, driver_name, device_type)
            
            # Republish control metadata
            await self._publish_wb_control_metas(device_id, config)
            
            # Re-setup Last Will Testament
            await self._setup_wb_last_will(device_id)
            
            logger.info(f"Successfully restored WB device state for {device_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error handling MQTT reconnection for {device_id}: {str(e)}")
            return False
    
    # Private methods - extracted and adapted from BaseDevice
    
    async def _publish_wb_device_meta(self, device_id: str, device_name: str, driver_name: str, device_type: Optional[str]):
        """Publish WB device metadata."""
        device_meta = {
            "driver": driver_name,
            "title": {"en": device_name}
        }
        
        if device_type:
            device_meta["type"] = device_type
        
        topic = f"/devices/{device_id}/meta"
        await self.message_bus.publish(topic, json.dumps(device_meta), retain=True, qos=1)
        logger.debug(f"Published WB device meta for {device_id}")
    
    def build_wb_controls_from_config(
        self,
        config: Union[BaseDeviceConfig, Dict[str, Any]],
        capabilities: Any = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Compute the WB controls (meta + initial state) a config would publish, applying the
        WB-exclusion + has-action filter. **Pure** (no MQTT) — the single place that decides which
        commands become WB controls and how, so `_publish_wb_control_metas` and the re-key
        equivalence tests agree. Returns ``{control_name: {"meta": {...}, "initial_state": "..."}}``.

        Classification source (exposure / control-type / order):
        - **with ``capabilities``** (the normal device path): the capability **domain** + the
          command's ``exposed`` flag. A command is excluded iff it's ``exposed: false`` (dormant) or
          its domain is UI-only (``pointer``). The domain (aliased) feeds the type/order heuristics.
        - **without** (fallback): the legacy config ``group`` field — used by capability-less devices
          that still enable WB emulation (e.g. the ``kitchen_hood`` appliance).
        Both paths are byte-equivalent on real device configs (verified by ``test_wb_rekey``), since
        the config ``group`` was authored to equal the capability domain.
        """
        if isinstance(config, dict):
            commands = config.get("commands", {})
        else:
            commands = config.commands

        cmd_domain = _commands_by_domain(capabilities) if capabilities is not None else {}

        controls: Dict[str, Dict[str, Any]] = {}
        for cmd_name, cmd_config in commands.items():
            if capabilities is not None:
                # Re-keyed path: exposure + capability domain.
                exposed = getattr(cmd_config, 'exposed', True) if not isinstance(cmd_config, dict) else cmd_config.get('exposed', True)
                domain = cmd_domain.get(cmd_name)
                if not exposed or (domain in _WB_EXCLUDED_DOMAINS):
                    logger.debug(f"Skipping WB control: {cmd_name} (exposed={exposed}, domain={domain})")
                    continue
                # domain may be None for commands not in cmd_domain; alias-lookup
                # with None as key is a no-op (returns None default), then we fall
                # through to the "no domain to classify" path naturally.
                classification = _DOMAIN_GROUP_ALIAS.get(domain, domain) if domain is not None else None
            else:
                # Fallback path: a capability-less device that still enables WB (e.g. the kitchen_hood
                # appliance). No domain to classify by, so exclusion is `exposed` only and the control
                # type/order come from explicit `wb_controls` (or params); there is no `classification`.
                exposed = getattr(cmd_config, 'exposed', True) if not isinstance(cmd_config, dict) else cmd_config.get('exposed', True)
                if not exposed:
                    logger.debug(f"Skipping WB control: {cmd_name} (exposed=False)")
                    continue
                classification = None

            action = None
            if isinstance(cmd_config, dict):
                action = cmd_config.get('action')
            else:
                action = getattr(cmd_config, 'action', None)

            if not action:
                continue

            controls[cmd_name] = {
                "meta": self._generate_wb_control_meta_from_config(cmd_name, cmd_config, config, classification),
                "initial_state": self._get_initial_wb_control_state_from_config(cmd_name, cmd_config, classification),
            }
        return controls

    async def _publish_wb_control_metas(self, device_id: str, config: Union[BaseDeviceConfig, Dict[str, Any]], capabilities: Any = None):
        """Publish WB control metadata for configured commands only."""
        try:
            for control_name, control in self.build_wb_controls_from_config(config, capabilities).items():
                # Publish control metadata
                meta_topic = f"/devices/{device_id}/controls/{control_name}/meta"
                await self.message_bus.publish(meta_topic, json.dumps(control["meta"]), retain=True, qos=1)

                # Publish initial control state. Never publish an empty retained payload —
                # that clears the retained value and the WB UI won't render the control.
                state_topic = f"/devices/{device_id}/controls/{control_name}"
                await self.message_bus.publish(state_topic, str(control["initial_state"]) or "0", retain=True, qos=1)

                logger.debug(f"Published WB control meta for {device_id}/{control_name}")

        except Exception as e:
            logger.error(f"Error publishing WB control metas for {device_id}: {str(e)}")
    
    def _generate_wb_control_meta_from_config(self, cmd_name: str, cmd_config, config: Union[BaseDeviceConfig, Dict[str, Any]], classification: Optional[str] = None) -> Dict[str, Any]:
        """Generate WB control metadata from command configuration. ``classification`` is the
        capability domain (or legacy group) that drives parameterless control-type + ordering."""

        # Check for explicit WB configuration in device config first
        wb_controls = None
        if isinstance(config, dict):
            wb_controls = config.get('wb_controls')
        else:
            wb_controls = getattr(config, 'wb_controls', None)

        if wb_controls and cmd_name in wb_controls:
            return wb_controls[cmd_name]

        # Extract command configuration properties
        if hasattr(cmd_config, 'description'):
            description = cmd_config.description
        elif isinstance(cmd_config, dict):
            description = cmd_config.get('description')
        else:
            description = None

        # Generate control metadata from command configuration
        meta = {
            "title": {"en": description or self._generate_control_title(cmd_name)},
            "readonly": False,
            "order": self._get_control_order_from_config(cmd_config, classification)
        }

        # Determine control type based on parameters and the classification (domain/group)
        control_type = self._determine_wb_control_type_from_config(cmd_config, classification)
        meta["type"] = control_type
        
        # Extract parameter-specific metadata
        param_metadata = self._extract_parameter_metadata_from_config(cmd_config)
        meta.update(param_metadata)
        
        return meta
    
    def _determine_wb_control_type_from_config(self, cmd_config, classification: Optional[str] = None) -> str:
        """Determine WB control type. ``classification`` = the capability domain (or legacy group)
        used for parameterless control-type heuristics."""

        params = None
        if hasattr(cmd_config, 'params'):
            params = cmd_config.params
        elif isinstance(cmd_config, dict):
            params = cmd_config.get('params')

        # PRIORITY FIX: Parameter-based type detection takes precedence
        if params:
            return self._get_control_type_from_parameters(params)

        # Classification-based overrides for parameterless commands only
        if classification:
            group_type = self._get_control_type_from_group(classification, cmd_config)
            if group_type:
                return group_type

        # No parameters and no classification override - default to pushbutton
        return "pushbutton"
    
    def _get_control_type_from_group(self, group: str, cmd_config) -> Optional[str]:
        """Get control type based on command group."""
        if not group:
            return None
        
        group_lower = group.lower()
        
        # Extract action name for context
        action = None
        if hasattr(cmd_config, 'action'):
            action = cmd_config.action
        elif isinstance(cmd_config, dict):
            action = cmd_config.get('action')
        
        action_lower = action.lower() if action else ""
        
        # Group-based type detection (for parameterless commands only)
        if group_lower == "volume":
            # Only specific actions should be range - more precise matching
            if any(x in action_lower for x in ["set_volume", "set_level"]) and not any(x in action_lower for x in ["up", "down"]):
                return "range"
            elif any(x in action_lower for x in ["mute", "unmute"]):
                return "switch"
            # volume_up, volume_down should fall through to None -> pushbutton
        elif group_lower == "power":
            return "pushbutton"
        elif group_lower in ["playback", "navigation", "menu"]:
            return "pushbutton"
        elif group_lower in ["inputs", "apps"]:
            # Only explicit setter actions should be text
            if any(x in action_lower for x in ["set_input", "set_source", "launch_app"]):
                return "text"
            # input_cd, input_usb, get_available_* should fall through to None -> pushbutton
        
        return None
    
    def _get_control_type_from_parameters(self, params) -> str:
        """Get control type based on command parameters."""
        if not params:
            return "pushbutton"
        
        # Handle both list of parameter objects and list of dicts
        first_param = params[0] if params else None
        if not first_param:
            return "pushbutton"
        
        # Extract parameter type
        param_type = None
        if hasattr(first_param, 'type'):
            param_type = first_param.type
        elif isinstance(first_param, dict):
            param_type = first_param.get('type')
        
        if param_type:
            if param_type in ["range", "integer", "float"]:
                return "range"
            elif param_type == "boolean":
                return "switch"
            elif param_type == "string":
                return "text"
        
        return "pushbutton"
    
    def _extract_parameter_metadata_from_config(self, cmd_config) -> Dict[str, Any]:
        """Extract parameter-specific metadata from command configuration."""
        metadata = {}
        
        # Extract parameters
        params = None
        if hasattr(cmd_config, 'params'):
            params = cmd_config.params
        elif isinstance(cmd_config, dict):
            params = cmd_config.get('params')
        
        if not params:
            return metadata
        
        # Process first parameter (WB controls typically map to one parameter)
        first_param = params[0] if params else None
        if not first_param:
            return metadata
        
        # Extract parameter properties
        param_min = None
        param_max = None
        param_units = None
        
        if isinstance(first_param, dict):
            param_min = first_param.get('min')
            param_max = first_param.get('max')
            param_units = first_param.get('units')
        else:
            param_min = getattr(first_param, 'min', None)
            param_max = getattr(first_param, 'max', None)
            param_units = getattr(first_param, 'units', None)
        
        # Add to metadata
        if param_min is not None:
            metadata["min"] = param_min
        if param_max is not None:
            metadata["max"] = param_max
        if param_units:
            metadata["units"] = param_units
        
        return metadata
    
    def _get_control_order_from_config(self, cmd_config, classification: Optional[str] = None) -> int:
        """Get control order. ``classification`` = the capability domain (or legacy group)."""
        # Extract action for ordering; ``classification`` (domain/group) drives the base order.
        group = classification
        action = None

        if hasattr(cmd_config, 'action'):
            action = cmd_config.action
        elif isinstance(cmd_config, dict):
            action = cmd_config.get('action')

        # Order by group first, then by action type
        group_order = {
            "power": 1, "inputs": 2, "playback": 3, 
            "volume": 4, "menu": 5, "navigation": 6, "display": 7
        }
        
        action_order = {
            "on": 1, "off": 2, "play": 3, "pause": 4, "stop": 5,
            "mute": 6, "unmute": 7, "set_volume": 8, "set_level": 9
        }
        
        base_order = group_order.get(group.lower() if group else "", 10) * 100
        action_name = action.lower() if action else ""
        
        # Try to match action patterns
        action_offset = 50  # Default
        for pattern, order in action_order.items():
            if pattern in action_name:
                action_offset = order
                break
        
        return base_order + action_offset
    
    def _generate_control_title(self, cmd_name: str) -> str:
        """Generate control title from command name."""
        # Convert snake_case or camelCase to Title Case
        title = cmd_name.replace('_', ' ').replace('-', ' ')
        # Handle camelCase
        title = re.sub(r'([a-z])([A-Z])', r'\1 \2', title)
        return title.title()
    
    def _get_initial_wb_control_state_from_config(self, cmd_name: str, cmd_config, classification: Optional[str] = None) -> str:
        """Get the initial state value for a WB control from configuration.

        MUST be non-empty and matched to the control TYPE. Publishing an empty (zero-length)
        retained payload is the MQTT "clear retained" operation, so the value topic is never
        stored — and the WB UI then refuses to render the control (it needs *both* a /meta and
        a value). This is what previously hid all `input_*`/`set_input`/`launch_app`/
        `get_available_*` controls (they used to default to "").
        """
        # 1) Explicit default from the command's first parameter, if any.
        if hasattr(cmd_config, 'params') and cmd_config.params:
            first_param = cmd_config.params[0]
            if hasattr(first_param, 'default') and first_param.default is not None:
                return str(first_param.default)
        elif isinstance(cmd_config, dict) and cmd_config.get('params'):
            first_param = cmd_config['params'][0]
            if isinstance(first_param, dict) and first_param.get('default') is not None:
                return str(first_param['default'])

        # 2) Default by control TYPE (never empty).
        control_type = self._determine_wb_control_type_from_config(cmd_config, classification)
        cmd_lower = cmd_name.lower()

        if control_type == "range":
            if any(x in cmd_lower for x in ['brightness', 'contrast']):
                return "75"
            if any(x in cmd_lower for x in ['temp', 'temperature']):
                return "22"
            if any(x in cmd_lower for x in ['speed', 'fan']):
                return "0"
            return "50"  # volume / level / generic range
        if control_type == "text":
            return "unknown"  # non-empty placeholder so the control renders
        # switch / pushbutton / value / anything else: off / not-pressed
        return "0"
    
    async def _setup_wb_last_will(self, device_id: str):
        """Setup Last Will Testament for device offline detection."""
        try:
            # Set device as online
            online_topic = f"/devices/{device_id}/meta/online"
            await self.message_bus.publish(online_topic, "1", retain=True, qos=1)
            
            # Mark device as available
            availability_topic = f"/devices/{device_id}/meta/available"
            await self.message_bus.publish(availability_topic, "1", retain=True, qos=1)
            
            logger.debug(f"Set up WB Last Will Testament for {device_id}")
            
        except Exception as e:
            logger.warning(f"Error setting up WB Last Will Testament for {device_id}: {str(e)}")
    
    def _is_wb_command_topic(self, topic: str, device_id: str) -> bool:
        """Check if topic is a WB command topic for the given device."""
        pattern = f"/devices/{re.escape(device_id)}/controls/(.+)/on"
        return bool(re.match(pattern, topic))
    
    def _process_wb_command_payload_from_config(self, cmd_name: str, cmd_config, payload: str) -> Dict[str, Any]:
        """Process WB command payload into parameters using command configuration."""
        params = {}
        
        # Extract parameters from command config
        config_params = None
        if hasattr(cmd_config, 'params'):
            config_params = cmd_config.params
        elif isinstance(cmd_config, dict):
            config_params = cmd_config.get('params')
        
        # If no parameters defined, it's a simple pushbutton
        if not config_params:
            return params
        
        # Process the first parameter (WB controls typically map to one parameter)
        first_param = config_params[0]
        
        # Extract parameter properties
        param_name = None
        param_type = None
        param_default = None
        
        if hasattr(first_param, 'name'):
            param_name = first_param.name
            param_type = getattr(first_param, 'type', 'string')
            param_default = getattr(first_param, 'default', None)
        elif isinstance(first_param, dict):
            param_name = first_param.get('name')
            param_type = first_param.get('type', 'string')
            param_default = first_param.get('default')
        
        if not param_name:
            return params
        
        try:
            if param_type == "boolean":
                # Convert payload to boolean
                params[param_name] = payload.lower() in ["1", "true", "on", "yes"]
            elif param_type in ["range", "integer", "float"]:
                # Convert payload to numeric value
                if param_type == "integer":
                    params[param_name] = int(float(payload))  # Handle "1.0" -> 1
                elif param_type == "float" or param_type == "range":
                    params[param_name] = float(payload)
            elif param_type == "string":
                # Use payload as string
                params[param_name] = payload
            else:
                # Fallback to string
                params[param_name] = payload
                
        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to convert WB payload '{payload}' for parameter {param_name} (type: {param_type}): {e}")
            # Use default value if available
            if param_default is not None:
                params[param_name] = param_default
        
        return params
    
    async def _update_wb_control_state(self, device_id: str, control_name: str, payload: str):
        """Update WB control state topic with the new value."""
        try:
            state_topic = f"/devices/{device_id}/controls/{control_name}"
            # Never publish an empty retained payload — it clears the retained value and the
            # WB UI then drops the control. Substitute "0" for an empty/None state update.
            safe_payload = payload if (payload is not None and payload != "") else "0"
            await self.message_bus.publish(state_topic, safe_payload, retain=True, qos=1)
            logger.debug(f"Updated WB control state for {device_id}/{control_name}: {safe_payload}")
        except Exception as e:
            logger.error(f"Error updating WB control state for {device_id}/{control_name}: {str(e)}")

    # ------------------------------------------------------------------------
    # Invariant B chokepoint: republish WB control value topics after device state changes.
    # Registered as a state-change callback on every WB-enabled device by BaseDevice
    # (`_setup_wb_virtual_device` calls `register_state_change_callback(wb_service.publish_device_state_changes)`).
    # The callback chain dispatches `(device_id, changed_fields)` synchronously from
    # `BaseDevice._notify_state_change`; we schedule the actual MQTT publishes async via
    # `asyncio.create_task` to avoid blocking the caller (matches the persistence callback pattern).
    # ------------------------------------------------------------------------

    def publish_device_state_changes(self, device_id: str, changed_fields: List[str]) -> None:
        """Sync state-change callback that schedules WB value-topic publishes.

        Sync entry point + ``asyncio.create_task`` keeps this callable from ``BaseDevice.
        _notify_state_change`` regardless of whether the caller is sync or async — matches
        ``DeviceManager._persist_state_callback``.
        """
        if not changed_fields:
            return
        if device_id not in self._active_devices:
            # Device wasn't WB-enabled (no virtual device) — silent no-op, not an error
            return
        try:
            import asyncio
            asyncio.create_task(self._async_publish_state_changes(device_id, list(changed_fields)))
        except RuntimeError as e:
            logger.warning(f"Cannot schedule WB state publish for {device_id} (no event loop): {e}")

    async def _async_publish_state_changes(self, device_id: str, changed_fields: List[str]) -> None:
        """Read the device's current state and publish each changed field to its WB control(s)."""
        try:
            device_info = self._active_devices.get(device_id)
            if not device_info:
                return  # device was unregistered between schedule and run

            wb_device_id = device_info["wb_device_id"]
            state_provider = device_info.get("state_provider")
            if state_provider is None:
                # Older code path didn't inject a provider — nothing to publish. (Tests / mocks.)
                return

            # Read current state once for this batch
            state_obj = state_provider()
            if hasattr(state_obj, "dict"):
                state_dict = state_obj.dict()
            elif hasattr(state_obj, "__dict__"):
                state_dict = state_obj.__dict__
            else:
                logger.warning(f"Cannot extract state dict from {type(state_obj).__name__} for {device_id}")
                return

            config = device_info["config"]
            field_to_controls = self._build_state_field_to_control_map(config)

            for field in changed_fields:
                control_names = field_to_controls.get(field)
                if not control_names:
                    continue  # no WB control mapped for this state field — silent skip
                if field not in state_dict:
                    continue
                payload = self._wb_payload_for_value(state_dict[field])
                for control_name in control_names:
                    await self._update_wb_control_state(wb_device_id, control_name, payload)
        except Exception as e:
            logger.error(f"Error publishing WB state changes for {device_id}: {e}")

    def _build_state_field_to_control_map(self, config: Union[BaseDeviceConfig, Dict[str, Any]]) -> Dict[str, List[str]]:
        """Build ``{state_field_name: [wb_control_name, ...]}`` from a device config.

        Two sources, in this order:
        1. **Explicit** ``wb_state_mappings`` in the device config — for cases where the state
           field name doesn't match any WB control name (e.g. ``input_source`` → ``input``).
           Value may be a single string or a list (one state field → multiple WB controls).
        2. **By-name convention** fallback — for every WB control NOT already covered by an
           explicit mapping, assume there's a state field of the same name. This is the common
           case (``power`` command → ``power`` control → ``power`` state field).

        Pushbutton/momentary controls are **excluded** — they have no state to track.
        """
        result: Dict[str, List[str]] = {}

        # 1) Explicit mappings from config
        explicit = None
        if isinstance(config, dict):
            explicit = config.get('wb_state_mappings')
        else:
            explicit = getattr(config, 'wb_state_mappings', None)

        if explicit:
            for field, control_or_controls in explicit.items():
                if isinstance(control_or_controls, str):
                    result[field] = [control_or_controls]
                elif isinstance(control_or_controls, (list, tuple)):
                    result[field] = [c for c in control_or_controls if isinstance(c, str)]

        # 2) By-name convention fallback — any WB control not already mapped by an explicit
        #    entry maps from a state field of the same name. Pushbuttons skipped.
        try:
            wb_controls = self.build_wb_controls_from_config(config)
        except Exception as e:
            logger.debug(f"Could not enumerate WB controls for state mapping ({e}); using explicit map only")
            wb_controls = {}

        explicit_controls = {c for controls in result.values() for c in controls}
        for control_name, control_info in wb_controls.items():
            meta_type = (control_info.get("meta", {}) or {}).get("type")
            if meta_type == "pushbutton":
                continue  # momentary controls have no state
            if control_name in explicit_controls:
                continue  # already covered by an explicit mapping (from a possibly differently-named field)
            # Convention: WB control name == state field name
            result.setdefault(control_name, []).append(control_name)
            # Dedupe in case the same control_name happened to also appear via explicit map
            result[control_name] = list(dict.fromkeys(result[control_name]))

        return result

    @staticmethod
    def _wb_payload_for_value(value: Any) -> str:
        """Convert a Python state value to the WB MQTT payload string.

        WB conventions: bool → '0'/'1'; None → '0' (also avoids the empty-retained-payload
        bug that drops the control from the WB UI); Enum → its value; everything else → str().
        """
        if value is None:
            return "0"
        if isinstance(value, bool):
            return "1" if value else "0"
        if isinstance(value, Enum):
            return str(value.value)
        return str(value)
    
    def _validate_wb_configuration_from_config(self, config: Union[BaseDeviceConfig, Dict[str, Any]]) -> Tuple[bool, Dict[str, Any]]:
        """Validate WB configuration from config object."""
        validation_results: Dict[str, Any] = {
            'wb_controls_errors': {},
            'wb_state_mappings_errors': [],
            'warnings': []
        }
        # Pre-bind so the except-clause logger.error never reads an unbound name.
        device_id = "<unknown>"

        try:
            # Extract configuration properties
            if isinstance(config, dict):
                device_id = config.get("device_id", "unknown")
                wb_controls = config.get("wb_controls")
                commands = config.get("commands", {})
            else:
                device_id = config.device_id
                wb_controls = getattr(config, 'wb_controls', None)
                commands = config.commands
            
            # Validate wb_controls configuration
            if wb_controls:
                for control_name, control_config in wb_controls.items():
                    if not isinstance(control_config, dict):
                        validation_results['wb_controls_errors'][control_name] = "WB control config must be a dictionary"
                    elif 'type' not in control_config:
                        validation_results['wb_controls_errors'][control_name] = "WB control config missing 'type' field"
            
            # Check for commands without actions
            missing_actions = []
            for cmd_name, cmd_config in commands.items():
                if isinstance(cmd_config, dict):
                    action = cmd_config.get('action')
                else:
                    action = getattr(cmd_config, 'action', None)

                if not action:
                    missing_actions.append(cmd_name)
            
            if missing_actions:
                validation_results['warnings'].append(f"Commands without actions will not create WB controls: {missing_actions}")
            
            # Check for potential issues
            if not commands:
                validation_results['warnings'].append("No commands defined - no WB controls will be created")
            
            # Validation passes if no critical errors
            is_valid = len(validation_results['wb_controls_errors']) == 0
            
            return is_valid, validation_results
            
        except Exception as e:
            logger.error(f"Error validating WB configuration for {device_id}: {str(e)}")
            validation_results['warnings'].append(f"Configuration validation error: {str(e)}")
            return False, validation_results 