"""WB Virtual Device Service - Config-driven abstraction for WB virtual device operations."""

import json
import logging
import re
from typing import Any, Callable, Dict, List, Optional, Tuple, Union, Awaitable

from wb_mqtt_bridge.domain.ports import MessageBusPort
from wb_mqtt_bridge.infrastructure.config.models import BaseDeviceConfig

logger = logging.getLogger(__name__)

# Type alias for command executor callback
CommandExecutor = Callable[[str, str, Dict[str, Any]], Awaitable[Any]]


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
        entity_name: Optional[str] = None     # Virtual entity abstraction (Phase 3 enhancement)
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
        try:
            # Extract device identity from config
            if isinstance(config, dict):
                config_device_id = config["device_id"]
                config_device_name = config["device_name"]
                enable_wb = config.get("enable_wb_emulation", True)
            else:
                config_device_id = config.device_id
                config_device_name = config.device_name
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
                "device_type": device_type or (config.device_class if hasattr(config, 'device_class') else 'device'),
                "device_name": wb_device_name,  # Store the virtual device name
                "wb_device_id": wb_device_id,   # Store virtual WB device ID for MQTT operations
                "config_device_id": config_device_id  # Store original config device ID for reference
            }
            self._command_executors[tracking_device_id] = command_executor
            
            # Publish device metadata (use virtual WB identifiers)
            await self._publish_wb_device_meta(wb_device_id, wb_device_name, driver_name, device_type)
            
            # Publish control metadata and initial states (use virtual WB device ID)
            await self._publish_wb_control_metas(wb_device_id, config)
            
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
        entity_id: Optional[str] = None
    ) -> List[str]:
        """Get MQTT subscription topics from config.
        
        Args:
            config: Device configuration
            entity_id: Virtual entity ID override (for scenarios, uses scenario_id instead of device_id)
        """
        topics = []
        
        try:
            # Extract device identity and commands
            if isinstance(config, dict):
                config_device_id = config["device_id"]
                commands = config.get("commands", {})
                enable_wb = config.get("enable_wb_emulation", True)
            else:
                config_device_id = config.device_id
                commands = config.commands
                enable_wb = getattr(config, 'enable_wb_emulation', True)
            
            # Apply virtual entity override for WB operations
            wb_device_id = entity_id if entity_id is not None else config_device_id
            
            if not enable_wb:
                return topics
            
            # UI-only groups that should not generate MQTT topics
            excluded_groups = {"pointer", "gestures", "noops", "media"}
            
            # Generate WB command topics for all commands (use virtual WB device ID)
            for cmd_name, cmd_config in commands.items():
                # Extract group from command config
                group = None
                if hasattr(cmd_config, 'group'):
                    group = cmd_config.group
                elif isinstance(cmd_config, dict):
                    group = cmd_config.get('group')
                
                # Skip commands in excluded groups
                if group and group.lower() in excluded_groups:
                    logger.debug(f"Skipping MQTT topic generation for UI-only command: {cmd_name} (group: {group})")
                    continue
                
                # Only add WB command topics for commands that have actions
                if hasattr(cmd_config, 'action') and cmd_config.action:
                    command_topic = f"/devices/{wb_device_id}/controls/{cmd_name}/on"
                    topics.append(command_topic)
                elif isinstance(cmd_config, dict) and cmd_config.get('action'):
                    command_topic = f"/devices/{wb_device_id}/controls/{cmd_name}/on"
                    topics.append(command_topic)
            
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
            
            # Execute the command via callback (use tracking device ID)
            executor = self._command_executors[tracking_device_id]
            await executor(control_name, payload, params)
            
            # Update WB control state to reflect the command (use virtual WB device ID)
            await self._update_wb_control_state(wb_device_id, control_name, payload)
            
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
    
    async def _publish_wb_control_metas(self, device_id: str, config: Union[BaseDeviceConfig, Dict[str, Any]]):
        """Publish WB control metadata for configured commands only."""
        try:
            # Extract commands from config
            if isinstance(config, dict):
                commands = config.get("commands", {})
            else:
                commands = config.commands
            
            # UI-only groups that should not generate MQTT topics or controls
            excluded_groups = {"pointer", "gestures", "noops", "media"}
            
            for cmd_name, cmd_config in commands.items():
                # Extract group from command config
                group = None
                if hasattr(cmd_config, 'group'):
                    group = cmd_config.group
                elif isinstance(cmd_config, dict):
                    group = cmd_config.get('group')
                
                # Skip commands in excluded groups
                if group and group.lower() in excluded_groups:
                    logger.debug(f"Skipping WB control metadata for UI-only command: {cmd_name} (group: {group})")
                    continue
                
                # Only create WB controls for commands that have actions
                action = None
                if hasattr(cmd_config, 'action'):
                    action = cmd_config.action
                elif isinstance(cmd_config, dict):
                    action = cmd_config.get('action')
                
                if action:
                    control_meta = self._generate_wb_control_meta_from_config(cmd_name, cmd_config, config)
                    
                    # Use command name as control name for WB topics
                    control_name = cmd_name
                    
                    # Publish control metadata
                    meta_topic = f"/devices/{device_id}/controls/{control_name}/meta"
                    await self.message_bus.publish(meta_topic, json.dumps(control_meta), retain=True, qos=1)
                    
                    # Publish initial control state
                    initial_state = self._get_initial_wb_control_state_from_config(cmd_name, cmd_config)
                    state_topic = f"/devices/{device_id}/controls/{control_name}"
                    await self.message_bus.publish(state_topic, str(initial_state), retain=True, qos=1)
                    
                    logger.debug(f"Published WB control meta for {device_id}/{control_name}")
        
        except Exception as e:
            logger.error(f"Error publishing WB control metas for {device_id}: {str(e)}")
    
    def _generate_wb_control_meta_from_config(self, cmd_name: str, cmd_config, config: Union[BaseDeviceConfig, Dict[str, Any]]) -> Dict[str, Any]:
        """Generate WB control metadata from command configuration."""
        
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
            "order": self._get_control_order_from_config(cmd_config)
        }
        
        # Determine control type based on parameters and group
        control_type = self._determine_wb_control_type_from_config(cmd_config)
        meta["type"] = control_type
        
        # Extract parameter-specific metadata
        param_metadata = self._extract_parameter_metadata_from_config(cmd_config)
        meta.update(param_metadata)
        
        return meta
    
    def _determine_wb_control_type_from_config(self, cmd_config) -> str:
        """Determine WB control type from command configuration."""
        
        # Extract group and parameters from command config
        group = None
        params = None
        
        if hasattr(cmd_config, 'group'):
            group = cmd_config.group
        elif isinstance(cmd_config, dict):
            group = cmd_config.get('group')
            
        if hasattr(cmd_config, 'params'):
            params = cmd_config.params
        elif isinstance(cmd_config, dict):
            params = cmd_config.get('params')
        
        # PRIORITY FIX: Parameter-based type detection takes precedence
        if params:
            return self._get_control_type_from_parameters(params)
        
        # Group-based overrides for parameterless commands only
        if group:
            group_type = self._get_control_type_from_group(group, cmd_config)
            if group_type:
                return group_type
        
        # No parameters and no group override - default to pushbutton
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
        
        if hasattr(first_param, 'min'):
            param_min = first_param.min
        elif isinstance(first_param, dict):
            param_min = first_param.get('min')
        
        if hasattr(first_param, 'max'):
            param_max = first_param.max
        elif isinstance(first_param, dict):
            param_max = first_param.get('max')
        
        if hasattr(first_param, 'units'):
            param_units = first_param.units
        elif isinstance(first_param, dict):
            param_units = first_param.get('units')
        
        # Add to metadata
        if param_min is not None:
            metadata["min"] = param_min
        if param_max is not None:
            metadata["max"] = param_max
        if param_units:
            metadata["units"] = param_units
        
        return metadata
    
    def _get_control_order_from_config(self, cmd_config) -> int:
        """Get control order from command configuration."""
        # Extract group and action for ordering
        group = None
        action = None
        
        if hasattr(cmd_config, 'group'):
            group = cmd_config.group
        elif isinstance(cmd_config, dict):
            group = cmd_config.get('group')
        
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
    
    def _get_initial_wb_control_state_from_config(self, cmd_name: str, cmd_config) -> str:
        """Get initial state value for WB control from configuration."""
        # First check for explicit default in command config
        if hasattr(cmd_config, 'params') and cmd_config.params:
            first_param = cmd_config.params[0]
            if hasattr(first_param, 'default') and first_param.default is not None:
                return str(first_param.default)
        elif isinstance(cmd_config, dict) and cmd_config.get('params'):
            first_param = cmd_config['params'][0]
            if isinstance(first_param, dict) and first_param.get('default') is not None:
                return str(first_param['default'])
        
        # Fallback to name-based defaults
        cmd_lower = cmd_name.lower()
        
        # Switch controls (0 = off, 1 = on)
        if any(x in cmd_lower for x in ['mute', 'unmute']):
            return "0"  # Not muted
        
        # Range controls with appropriate defaults
        elif any(x in cmd_lower for x in ['volume', 'vol']):
            return "50"  # 50% volume
        elif any(x in cmd_lower for x in ['speed', 'fan']):
            return "0"  # Fan/speed off
        elif any(x in cmd_lower for x in ['brightness', 'contrast']):
            return "75"  # 75% brightness/contrast
        elif 'level' in cmd_lower:
            return "50"  # 50% level
        elif any(x in cmd_lower for x in ['temp', 'temperature']):
            return "22"  # 22°C default temperature
        elif 'set_' in cmd_lower:
            return "0"  # Generic setter default
        
        # Text controls - empty or status strings
        elif any(x in cmd_lower for x in ['input', 'source', 'channel']):
            return ""  # No input selected
        elif any(x in cmd_lower for x in ['app', 'application']):
            return ""  # No app selected
        elif any(x in cmd_lower for x in ['status', 'state']):
            return "unknown"  # Unknown status
        elif any(x in cmd_lower for x in ['get_', 'list_', 'available']):
            return ""  # Empty list/info
        
        # Pushbutton controls (always 0 for non-pressed state)
        else:
            return "0"  # Not pressed
    
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
            await self.message_bus.publish(state_topic, payload, retain=True, qos=1)
            logger.debug(f"Updated WB control state for {device_id}/{control_name}: {payload}")
        except Exception as e:
            logger.error(f"Error updating WB control state for {device_id}/{control_name}: {str(e)}")
    
    def _validate_wb_configuration_from_config(self, config: Union[BaseDeviceConfig, Dict[str, Any]]) -> Tuple[bool, Dict[str, Any]]:
        """Validate WB configuration from config object."""
        validation_results = {
            'wb_controls_errors': {},
            'wb_state_mappings_errors': [],
            'warnings': []
        }
        
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
                action = None
                if hasattr(cmd_config, 'action'):
                    action = cmd_config.action
                elif isinstance(cmd_config, dict):
                    action = cmd_config.get('action')
                
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