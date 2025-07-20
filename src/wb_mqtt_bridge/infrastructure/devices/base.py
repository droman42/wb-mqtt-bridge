from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, cast, Union, Generic, Tuple
import logging
import json
import re
from datetime import datetime
from enum import Enum
from socket import socket, AF_INET, SOCK_DGRAM, SOL_SOCKET, SO_BROADCAST
import psutil

from wb_mqtt_bridge.domain.devices.models import BaseDeviceState, LastCommand
from wb_mqtt_bridge.infrastructure.config.models import BaseDeviceConfig, BaseCommandConfig, CommandParameterDefinition
from wb_mqtt_bridge.infrastructure.mqtt.client import MQTTClient
from wb_mqtt_bridge.utils.types import StateT, CommandResult, CommandResponse, ActionHandler
from wb_mqtt_bridge.presentation.api.sse_manager import sse_manager, SSEChannel
from wb_mqtt_bridge.domain.ports import DeviceBusPort

logger = logging.getLogger(__name__)

class BaseDevice(DeviceBusPort, ABC, Generic[StateT]):
    """Base class for all device implementations."""
    
    def __init__(self, config: BaseDeviceConfig, mqtt_client: Optional["MQTTClient"] = None):
        self.config = config
        # Use typed config directly - no fallbacks to dictionary access
        self.device_id = config.device_id
        self.device_name = config.device_name
        
        # Initialize state with basic device identification
        self.state = BaseDeviceState(
            device_id=self.device_id,
            device_name=self.device_name
        )
        self._action_handlers: Dict[str, ActionHandler] = {}  # Cache for action handlers
        self._action_groups: Dict[str, List[Dict[str, Any]]] = {}  # Index of actions by group
        self.mqtt_client = mqtt_client
        self._state_change_callback = None  # Callback for state changes
        
        # Register action handlers
        self._register_handlers()
        
        # Build action group index
        self._build_action_groups_index()
        
        # Auto-register handlers based on naming convention
        self._auto_register_handlers()
    
    def should_publish_wb_virtual_device(self) -> bool:
        """Check if WB virtual device emulation should be enabled for this device."""
        # Check if MQTT client is available
        if not self.mqtt_client:
            return False
            
        # Check configuration flag (defaults to True)
        return getattr(self.config, 'enable_wb_emulation', True)
    
    async def _setup_wb_virtual_device(self):
        """Set up Wirenboard virtual device emulation with enhanced validation."""
        if not self.mqtt_client:
            logger.warning(f"Cannot setup WB virtual device for {self.device_id}: no MQTT client")
            return
        
        # Validate WB configuration before setup
        is_valid, validation_results = await self.validate_wb_configuration()
        if not is_valid:
            logger.error(f"WB configuration validation failed for {self.device_id}")
            logger.error(f"Validation results: {validation_results}")
            return
        
        # Log warnings even if configuration is valid
        if validation_results.get('warnings'):
            for warning in validation_results['warnings']:
                logger.warning(f"WB setup warning for {self.device_id}: {warning}")
        
        # Publish device metadata
        await self._publish_wb_device_meta()
        
        # Publish control metadata and initial states
        await self._publish_wb_control_metas()
        
        # Set up Last Will Testament for offline detection
        await self._setup_wb_last_will()
        
        logger.info(f"WB virtual device emulation enabled for {self.device_id}")
    
    async def _publish_wb_device_meta(self):
        """Publish WB device metadata."""
        device_meta = {
            "driver": "wb_mqtt_bridge",
            "title": {"en": self.device_name}
        }
        
        topic = f"/devices/{self.device_id}/meta"
        await self.mqtt_client.publish(topic, json.dumps(device_meta), retain=True)
        logger.debug(f"Published WB device meta for {self.device_id}")
    
    async def _publish_wb_control_metas(self):
        """Publish WB control metadata for configured commands only."""
        available_commands = self.get_available_commands()
        
        for cmd_name, cmd_config in available_commands.items():
            # Only create WB controls for commands that have handlers
            if cmd_config.action and cmd_config.action in self._action_handlers:
                control_meta = self._generate_wb_control_meta_from_config(cmd_name, cmd_config)
                
                # Use command name as control name for WB topics
                control_name = cmd_name
                
                # Publish control metadata
                meta_topic = f"/devices/{self.device_id}/controls/{control_name}/meta"
                await self.mqtt_client.publish(meta_topic, json.dumps(control_meta), retain=True)
                
                # Publish initial control state
                initial_state = self._get_initial_wb_control_state_from_config(cmd_name, cmd_config)
                state_topic = f"/devices/{self.device_id}/controls/{control_name}"
                await self.mqtt_client.publish(state_topic, str(initial_state), retain=True)
                
                logger.debug(f"Published WB control meta for {self.device_id}/{control_name}")
    
    def _generate_wb_control_meta_from_config(self, cmd_name: str, cmd_config) -> Dict[str, Any]:
        """Generate WB control metadata from command configuration."""
        
        # Check for explicit WB configuration in device config first
        if hasattr(self.config, 'wb_controls') and self.config.wb_controls and cmd_name in self.config.wb_controls:
            return self.config.wb_controls[cmd_name]
        
        # Generate control metadata from command configuration
        meta = {
            "title": {"en": cmd_config.description or self._generate_control_title(cmd_name)},
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
        
        # Group-based overrides take precedence
        if hasattr(cmd_config, 'group') and cmd_config.group:
            group_type = self._get_control_type_from_group(cmd_config.group, cmd_config.action)
            if group_type:
                return group_type
        
        # Parameter-based type detection
        if hasattr(cmd_config, 'params') and cmd_config.params:
            return self._get_control_type_from_parameters(cmd_config.params)
        
        # No parameters - default to pushbutton
        return "pushbutton"
    
    def _get_control_type_from_group(self, group: str, action: str) -> Optional[str]:
        """Get control type based on command group and action."""
        group_lower = group.lower()
        action_lower = action.lower()
        
        # Power commands are always pushbuttons
        if group_lower == "power":
            return "pushbutton"
        
        # Volume group - distinguish between discrete and continuous controls
        if group_lower == "volume":
            if action_lower in ["volume_up", "volume_down", "mute", "unmute", "mute_toggle"]:
                return "pushbutton"  # Discrete volume controls
            elif action_lower in ["set_volume"]:
                return None  # Let parameter detection decide (likely range)
        
        # Playback controls are always pushbuttons
        if group_lower in ["playback", "menu", "navigation"]:
            return "pushbutton"
        
        # Input/source selection
        if group_lower in ["inputs", "apps"]:
            return None  # Let parameter detection decide
        
        return None  # No group-based override
    
    def _get_control_type_from_parameters(self, params: List) -> str:
        """Get control type based on command parameters."""
        if not params:
            return "pushbutton"
        
        # Look at the first parameter to determine control type
        first_param = params[0]
        param_type = getattr(first_param, 'type', 'string')
        
        if param_type == "range":
            return "range"
        elif param_type == "boolean":
            return "switch"
        elif param_type == "string":
            return "text"
        elif param_type in ["integer", "float"]:
            return "range"  # Numeric inputs as ranges
        else:
            return "pushbutton"  # Fallback
    
    def _extract_parameter_metadata_from_config(self, cmd_config) -> Dict[str, Any]:
        """Extract parameter metadata for WB control."""
        metadata = {}
        
        if not hasattr(cmd_config, 'params') or not cmd_config.params:
            return metadata
        
        first_param = cmd_config.params[0]
        
        # Extract range metadata
        if getattr(first_param, 'type', None) in ["range", "integer", "float"]:
            if hasattr(first_param, 'min') and first_param.min is not None:
                metadata["min"] = first_param.min
            if hasattr(first_param, 'max') and first_param.max is not None:
                metadata["max"] = first_param.max
            
            # Infer units from parameter description or name
            param_desc = getattr(first_param, 'description', '') or ''
            param_name = getattr(first_param, 'name', '') or ''
            
            if "dB" in param_desc:
                metadata["units"] = "dB"
            elif "%" in param_desc or param_name.lower() in ["volume", "level", "percentage"]:
                metadata["units"] = "%"
            elif param_name.lower() in ["speed", "rpm"]:
                metadata["units"] = "rpm"
            elif param_name.lower() in ["temperature", "temp"]:
                metadata["units"] = "°C"
        
        return metadata
    
    def _get_control_order_from_config(self, cmd_config) -> int:
        """Generate control ordering based on command configuration."""
        
        # Group-based ordering
        if hasattr(cmd_config, 'group') and cmd_config.group:
            group_lower = cmd_config.group.lower()
            action_lower = getattr(cmd_config, 'action', '').lower()
            
            # Power controls first (1-10)
            if group_lower == "power":
                if "on" in action_lower:
                    return 1
                elif "off" in action_lower:
                    return 2
                else:
                    return 5
            
            # Volume controls (10-19)
            elif group_lower == "volume":
                if "set_volume" in action_lower:
                    return 10
                elif "volume_up" in action_lower:
                    return 11
                elif "volume_down" in action_lower:
                    return 12
                elif "mute" in action_lower:
                    return 13
                else:
                    return 15
            
            # Input/source controls (20-29)
            elif group_lower in ["inputs", "apps"]:
                return 20
            
            # Playback controls (30-39)
            elif group_lower == "playback":
                if "play" in action_lower:
                    return 30
                elif "pause" in action_lower:
                    return 31
                elif "stop" in action_lower:
                    return 32
                elif "next" in action_lower:
                    return 33
                elif "previous" in action_lower:
                    return 34
                else:
                    return 35
            
            # Menu/navigation controls (40-49)
            elif group_lower in ["menu", "navigation"]:
                return 40
        
        # Fallback ordering based on action name
        action_lower = getattr(cmd_config, 'action', '').lower()
        if any(x in action_lower for x in ['get_', 'list_', 'available']):
            return 80  # Information controls at end
        
        return 100  # Default order

    def _get_initial_wb_control_state_from_config(self, cmd_name: str, cmd_config) -> str:
        """Get initial state value for WB control from command configuration."""
        
        # If no parameters, it's a pushbutton (always 0)
        if not hasattr(cmd_config, 'params') or not cmd_config.params:
            return "0"
        
        first_param = cmd_config.params[0]
        param_type = getattr(first_param, 'type', 'string')
        
        # Use default value if specified
        if hasattr(first_param, 'default') and first_param.default is not None:
            if param_type == "boolean":
                return "1" if first_param.default else "0"
            else:
                return str(first_param.default)
        
        # Type-based defaults
        if param_type == "boolean":
            return "0"  # False
        elif param_type in ["range", "integer", "float"]:
            # Use minimum value or 0
            if hasattr(first_param, 'min') and first_param.min is not None:
                return str(first_param.min)
            else:
                return "0"
        elif param_type == "string":
            return ""  # Empty string
        else:
            return "0"  # Fallback

    def _generate_wb_control_meta(self, handler_name: str) -> Dict[str, Any]:
        """Generate WB control metadata with enhanced smart defaults."""
        
        # Check for explicit WB configuration in device config
        if hasattr(self.config, 'wb_controls') and self.config.wb_controls and handler_name in self.config.wb_controls:
            return self.config.wb_controls[handler_name]
        
        # Generate smart defaults based on handler name
        meta = {
            "title": {"en": self._generate_control_title(handler_name)},
            "readonly": False,
            "order": self._get_control_order(handler_name)
        }
        
        # Enhanced smart type detection based on naming patterns
        handler_lower = handler_name.lower()
        
        # Power controls - pushbuttons
        if any(x in handler_lower for x in ['power_on', 'power_off', 'turn_on', 'turn_off']):
            meta.update({
                "type": "pushbutton",
                "readonly": False
            })
        
        # Volume controls - range sliders
        elif any(x in handler_lower for x in ['set_volume', 'volume', 'vol']):
            meta.update({
                "type": "range",
                "min": 0,
                "max": 100,
                "units": "%",
                "readonly": False
            })
        
        # Mute controls - switches  
        elif any(x in handler_lower for x in ['mute', 'unmute', 'toggle_mute']):
            meta.update({
                "type": "switch",
                "readonly": False
            })
        
        # Input/source selection - text input or range
        elif any(x in handler_lower for x in ['set_input', 'input', 'source', 'channel']):
            if 'set_' in handler_lower:
                meta.update({
                    "type": "text",
                    "readonly": False
                })
            else:
                meta.update({
                    "type": "text", 
                    "readonly": True
                })
        
        # Playback controls - pushbuttons
        elif any(x in handler_lower for x in ['play', 'pause', 'stop', 'next', 'previous', 'forward', 'rewind']):
            meta.update({
                "type": "pushbutton",
                "readonly": False
            })
        
        # Navigation controls - pushbuttons
        elif any(x in handler_lower for x in ['home', 'back', 'menu', 'up', 'down', 'left', 'right', 'ok', 'select']):
            meta.update({
                "type": "pushbutton",
                "readonly": False
            })
        
        # App/application controls - text or pushbutton
        elif any(x in handler_lower for x in ['app', 'application', 'launch']):
            if 'launch' in handler_lower or 'open' in handler_lower:
                meta.update({
                    "type": "text",
                    "readonly": False
                })
            else:
                meta.update({
                    "type": "text",
                    "readonly": True
                })
        
        # Speed/level controls - range sliders
        elif any(x in handler_lower for x in ['speed', 'level', 'brightness', 'contrast']):
            meta.update({
                "type": "range",
                "min": 0,
                "max": 100,
                "readonly": False
            })
            
            # Add appropriate units
            if 'speed' in handler_lower:
                meta["units"] = "rpm" if 'fan' in handler_lower else ""
            elif any(x in handler_lower for x in ['brightness', 'contrast']):
                meta["units"] = "%"
        
        # Temperature controls - range with appropriate units
        elif any(x in handler_lower for x in ['temp', 'temperature']):
            meta.update({
                "type": "range",
                "min": 16,
                "max": 30,
                "units": "°C",
                "readonly": "set_" not in handler_lower
            })
        
        # Status/state getters - readonly text
        elif any(x in handler_lower for x in ['get_', 'status', 'state', 'current']):
            meta.update({
                "type": "text",
                "readonly": True
            })
        
        # List/available getters - readonly text  
        elif any(x in handler_lower for x in ['list_', 'available', 'supported']):
            meta.update({
                "type": "text",
                "readonly": True
            })
        
        # Generic setters - range sliders
        elif 'set_' in handler_lower:
            meta.update({
                "type": "range",
                "min": 0,
                "max": 100,
                "readonly": False
            })
        
        # Connection/setup controls - pushbuttons
        elif any(x in handler_lower for x in ['connect', 'disconnect', 'setup', 'reset', 'restart']):
            meta.update({
                "type": "pushbutton",
                "readonly": False
            })
        
        # Default fallback - pushbutton for actions
        else:
            meta.update({
                "type": "pushbutton",
                "readonly": False
            })
        
        return meta
    
    def _generate_control_title(self, handler_name: str) -> str:
        """Generate a human-readable title for a control."""
        # Handle common abbreviations and improve formatting
        title = handler_name.replace('_', ' ').title()
        
        # Improve common abbreviations and terms
        replacements = {
            'Tv': 'TV',
            'Ir': 'IR', 
            'Rf': 'RF',
            'App ': 'App ',
            'Vol': 'Volume',
            'Temp': 'Temperature',
            'Set ': '',  # Remove "Set" prefix
            'Get ': '',  # Remove "Get" prefix
            'Toggle ': '',  # Simplify toggle controls
        }
        
        for old, new in replacements.items():
            title = title.replace(old, new)
        
        # Clean up extra spaces
        title = ' '.join(title.split())
        
        return title
    
    def _get_control_order(self, handler_name: str) -> int:
        """Generate control ordering based on handler name patterns."""
        handler_lower = handler_name.lower()
        
        # Power controls first (1-5)
        if any(x in handler_lower for x in ['power_on', 'turn_on']):
            return 1
        elif any(x in handler_lower for x in ['power_off', 'turn_off']):
            return 2
        elif any(x in handler_lower for x in ['connect', 'setup']):
            return 3
        elif any(x in handler_lower for x in ['disconnect', 'reset', 'restart']):
            return 4
        
        # Audio controls (10-19)
        elif any(x in handler_lower for x in ['volume', 'vol']):
            return 10
        elif any(x in handler_lower for x in ['mute', 'unmute']):
            return 11
        
        # Input/source controls (20-24)
        elif any(x in handler_lower for x in ['input', 'source', 'channel']):
            return 20
        
        # Playback controls (25-35)
        elif 'play' in handler_lower:
            return 25
        elif 'pause' in handler_lower:
            return 26
        elif 'stop' in handler_lower:
            return 27
        elif any(x in handler_lower for x in ['next', 'forward']):
            return 28
        elif any(x in handler_lower for x in ['previous', 'rewind']):
            return 29
        
        # Navigation controls (40-50)
        elif 'home' in handler_lower:
            return 40
        elif 'back' in handler_lower:
            return 41
        elif 'menu' in handler_lower:
            return 42
        elif any(x in handler_lower for x in ['up', 'down', 'left', 'right']):
            return 43
        elif any(x in handler_lower for x in ['ok', 'select']):
            return 44
        
        # App/application controls (55-59)
        elif any(x in handler_lower for x in ['app', 'application', 'launch']):
            return 55
        
        # Environmental controls (60-70)
        elif any(x in handler_lower for x in ['temp', 'temperature']):
            return 60
        elif any(x in handler_lower for x in ['speed', 'fan']):
            return 61
        elif any(x in handler_lower for x in ['brightness', 'contrast']):
            return 62
        elif 'level' in handler_lower:
            return 63
        
        # Status/information controls (80-89)
        elif any(x in handler_lower for x in ['status', 'state', 'current']):
            return 80
        elif any(x in handler_lower for x in ['get_', 'list_', 'available']):
            return 85
        
        # Generic setters (90-95)
        elif 'set_' in handler_lower:
            return 90
        
        # Everything else (100+)
        else:
            return 100
    
    def _get_initial_wb_control_state(self, handler_name: str) -> str:
        """Get initial state value for WB control with enhanced defaults."""
        handler_lower = handler_name.lower()
        
        # Switch controls (0 = off, 1 = on)
        if any(x in handler_lower for x in ['mute', 'unmute']):
            return "0"  # Not muted
        
        # Range controls with appropriate defaults
        elif any(x in handler_lower for x in ['volume', 'vol']):
            return "50"  # 50% volume
        elif any(x in handler_lower for x in ['speed', 'fan']):
            return "0"  # Fan/speed off
        elif any(x in handler_lower for x in ['brightness', 'contrast']):
            return "75"  # 75% brightness/contrast
        elif 'level' in handler_lower:
            return "50"  # 50% level
        elif any(x in handler_lower for x in ['temp', 'temperature']):
            return "22"  # 22°C default temperature
        elif 'set_' in handler_lower:
            return "0"  # Generic setter default
        
        # Text controls - empty or status strings
        elif any(x in handler_lower for x in ['input', 'source', 'channel']):
            return ""  # No input selected
        elif any(x in handler_lower for x in ['app', 'application']):
            return ""  # No app selected
        elif any(x in handler_lower for x in ['status', 'state']):
            return "unknown"  # Unknown status
        elif any(x in handler_lower for x in ['get_', 'list_', 'available']):
            return ""  # Empty list/info
        
        # Pushbutton controls (always 0 for non-pressed state)
        elif any(x in handler_lower for x in [
            'power_on', 'power_off', 'turn_on', 'turn_off',
            'play', 'pause', 'stop', 'next', 'previous', 'forward', 'rewind',
            'home', 'back', 'menu', 'up', 'down', 'left', 'right', 'ok', 'select',
            'connect', 'disconnect', 'setup', 'reset', 'restart'
        ]):
            return "0"  # Not pressed
        
        # Default for any other controls
        else:
            return "0"
    
    async def _setup_wb_last_will(self):
        """Set up enhanced Last Will Testament for device offline detection with maintenance guard integration."""
        try:
            # Set error state when device goes offline
            error_topic = f"/devices/{self.device_id}/meta/error"
            availability_topic = f"/devices/{self.device_id}/meta/available"
            
            # Add Last Will Testament messages to MQTT client
            if hasattr(self.mqtt_client, 'add_will_message'):
                # Add device offline LWT messages
                self.mqtt_client.add_will_message(self.device_id, error_topic, "offline", qos=1, retain=True)
                self.mqtt_client.add_will_message(self.device_id, availability_topic, "0", qos=1, retain=True)
                
                logger.debug(f"Added LWT messages for device {self.device_id}")
            else:
                logger.warning(f"MQTT client does not support Last Will Testament for {self.device_id}")
            
            # Clear error state and mark device as available on successful setup
            await self.mqtt_client.publish(error_topic, "", retain=True)
            await self.mqtt_client.publish(availability_topic, "1", retain=True)
            
            # Integration with maintenance guard - if maintenance is active, 
            # delay LWT setup to avoid false positives during system restarts
            if hasattr(self.mqtt_client, 'guard') and self.mqtt_client.guard:
                # The maintenance guard will handle filtering during restart windows
                logger.debug(f"LWT setup with maintenance guard integration for {self.device_id}")
            
            logger.debug(f"Set up WB Last Will Testament for {self.device_id}")
            
        except Exception as e:
            logger.warning(f"Error setting up Last Will Testament for {self.device_id}: {str(e)}")
    
    async def cleanup_wb_device_state(self):
        """
        Clean up WB device state on shutdown.
        Marks device as offline and unavailable.
        """
        if not self.should_publish_wb_virtual_device() or not self.mqtt_client:
            return
            
        try:
            # Mark device as offline
            error_topic = f"/devices/{self.device_id}/meta/error"
            await self.mqtt_client.publish(error_topic, "offline", retain=True)
            
            # Mark device as unavailable
            availability_topic = f"/devices/{self.device_id}/meta/available"
            await self.mqtt_client.publish(availability_topic, "0", retain=True)
            
            logger.debug(f"Cleaned up WB device state for {self.device_id}")
            
        except Exception as e:
            logger.warning(f"Error cleaning up WB device state for {self.device_id}: {str(e)}")
    
    async def setup_wb_emulation_if_enabled(self):
        """
        Helper method for subclasses to call during their setup() method.
        Sets up WB virtual device emulation if enabled.
        """
        if self.should_publish_wb_virtual_device():
            await self._setup_wb_virtual_device()
    
    async def refresh_wb_control_states(self):
        """
        Refresh all WB control states by republishing current device state.
        Useful after MQTT reconnection to ensure state persistence.
        """
        if not self.should_publish_wb_virtual_device():
            return
            
        try:
            # Republish all current state values to WB controls
            current_state = self.state.dict(exclude_unset=True)
            await self._sync_state_to_wb_controls(current_state)
            
            # Also republish any handler-specific states that might not be in main state
            for handler_name in self._action_handlers:
                if not handler_name.startswith('_'):
                    # Check if we have a current state for this handler
                    if hasattr(self.state, handler_name):
                        value = getattr(self.state, handler_name)
                        wb_value = self._convert_state_to_wb_value(handler_name, value)
                        if wb_value is not None:
                            control_topic = f"/devices/{self.device_id}/controls/{handler_name}"
                            await self.mqtt_client.publish(control_topic, str(wb_value), retain=True)
            
            logger.debug(f"Refreshed WB control states for {self.device_id}")
            
        except Exception as e:
            logger.warning(f"Error refreshing WB control states for {self.device_id}: {str(e)}")
    
    async def handle_mqtt_reconnection(self):
        """
        Handle MQTT reconnection by republishing all WB device metadata and states.
        This ensures retained messages are restored after connection loss.
        """
        if not self.should_publish_wb_virtual_device():
            return
            
        try:
            logger.info(f"Handling MQTT reconnection for WB device {self.device_id}")
            
            # Republish device metadata
            await self._publish_wb_device_meta()
            
            # Republish control metadata
            await self._publish_wb_control_metas()
            
            # Refresh all control states
            await self.refresh_wb_control_states()
            
            # Re-setup Last Will Testament
            await self._setup_wb_last_will()
            
            logger.info(f"Successfully restored WB device state for {self.device_id}")
            
        except Exception as e:
            logger.error(f"Error handling MQTT reconnection for {self.device_id}: {str(e)}")

    def _register_handlers(self) -> None:
        """
        Register all action handlers for this device.
        
        This method should be overridden by all device subclasses to register
        their action handlers in a standardized way.
        
        Example:
            self._action_handlers.update({
                'power_on': self.handle_power_on,
                'power_off': self.handle_power_off,
            })
        """
        pass  # To be implemented by subclasses
    
    def create_command_result(
        self, 
        success: bool, 
        message: Optional[str] = None, 
        error: Optional[str] = None, 
        **extra_fields
    ) -> CommandResult:
        """
        Create a standardized CommandResult.
        
        Args:
            success: Whether the command was successful
            message: Optional success message
            error: Optional error message (only if success is False)
            **extra_fields: Additional fields to include in the result
            
        Returns:
            CommandResult: A standardized result dictionary
        """
        result: CommandResult = {
            "success": success
        }
        
        if message:
            result["message"] = message
            
        if not success and error:
            result["error"] = error
            
        # Add any additional fields
        for key, value in extra_fields.items():
            result[key] = value
            
        return result
        
    def set_error(self, error_message: str) -> None:
        """
        Set an error message in the device state.
        
        Args:
            error_message: The error message to set
        """
        self.update_state(error=error_message)
        
    def clear_error(self) -> None:
        """Clear any error message from the device state."""
        self.update_state(error=None)
    
    def _build_action_groups_index(self):
        """Build an index of actions organized by group."""
        self._action_groups = {"default": []}  # Default group for actions with no group specified
        
        for cmd_name, cmd in self.get_available_commands().items():
            # Get the group for this command
            group = cmd.group or "default"
            
            # Add group to index if it doesn't exist
            if group not in self._action_groups:
                self._action_groups[group] = []
            
            # Add command to the group
            action_info = {
                "name": cmd_name,
                "description": cmd.description or "",
                # Add other relevant properties from the command config
                # (excluding group and description which we've already handled)
                "params": cmd.params
            }
            self._action_groups[group].append(action_info)
    
    def get_available_groups(self) -> List[str]:
        """Get a list of all available action groups for this device."""
        return list(self._action_groups.keys())
    
    def get_actions_by_group(self, group: str) -> List[Dict[str, Any]]:
        """Get all actions in a specific group."""
        return self._action_groups.get(group, [])
    
    def get_actions(self) -> List[Dict[str, Any]]:
        """Return a list of supported actions for this device."""
        # Get all action handlers registered for this device
        actions = []
        for action_name in self._action_handlers:
            # Skip internal actions (starting with underscore)
            if action_name.startswith('_'):
                continue
                
            # Add action to the list
            actions.append({
                'name': action_name,
                'group': 'default'  # Default group for now
            })
            
        return actions
    
    def get_id(self) -> str:
        """Return the device ID."""
        return self.device_id
    
    def get_name(self) -> str:
        """Return the device name."""
        return self.device_name
    
    @abstractmethod
    async def setup(self) -> bool:
        """Initialize the device. Called when the service starts."""
        pass
    
    @abstractmethod
    async def shutdown(self) -> bool:
        """Cleanup device resources. Called when the service stops."""
        pass
    
    def subscribe_topics(self) -> List[str]:
        """Define the MQTT topics this device should subscribe to."""
        topics = []
        
        # For WB-enabled devices, subscribe ONLY to WB command topics (/on suffix)
        if self.should_publish_wb_virtual_device():
            available_commands = self.get_available_commands()
            for cmd_name, cmd_config in available_commands.items():
                # Only add WB command topics for commands that have handlers
                if cmd_config.action and cmd_config.action in self._action_handlers:
                    command_topic = f"/devices/{self.device_id}/controls/{cmd_name}/on"
                    topics.append(command_topic)
        else:
            # For non-WB devices, use legacy topic subscription for backward compatibility
            for cmd_name, cmd in self.get_available_commands().items():
                # Use the new get_command_topic method for backward compatibility
                topic = self.get_command_topic(cmd_name, cmd)
                if topic:
                    topics.append(topic)
        
        return topics
    
    def get_command_topic(self, handler_name: str, cmd_config: BaseCommandConfig) -> str:
        """Get auto-generated topic for command following WB conventions."""
        return f"/devices/{self.device_id}/controls/{handler_name}"
    
    async def handle_message(self, topic: str, payload: str):
        """Handle incoming MQTT messages for this device."""
        logger.debug(f"Device {self.get_name()} received message on {topic}: {payload}")
        
        # DEBUG: Enhanced logging for all device messages
        logger.debug(f"[BASE_DEVICE_DEBUG] handle_message for {self.device_id}: topic={topic}, payload='{payload}'")
        
        # Check if this is a WB command topic
        if self._is_wb_command_topic(topic):
            await self._handle_wb_command(topic, payload)
            return
        
        # Find matching command configuration based on topic
        matching_commands = []
        for cmd_name, cmd in self.get_available_commands().items():
            # Use get_command_topic for consistent topic resolution
            expected_topic = self.get_command_topic(cmd_name, cmd)
            if expected_topic == topic:
                # Add command to matches when topic matches
                matching_commands.append((cmd_name, cmd))
        
        if not matching_commands:
            logger.warning(f"No command configuration found for topic: {topic}")
            return
        
        # DEBUG: Log matching commands for all devices
        logger.debug(f"[BASE_DEVICE_DEBUG] Found {len(matching_commands)} matching commands for {self.device_id}: {[cmd[0] for cmd in matching_commands]}")
        
        # Process each matching command configuration found for the topic
        for cmd_name, cmd in matching_commands:
            # Process parameters if defined for this command
            params = {}
            if cmd.params:
                try:
                    # Try to parse payload for parameter processing
                    params = self._process_mqtt_payload(payload, cmd.params)
                except ValueError as e:
                    logger.warning(f"Parameter validation failed for {cmd_name}: {str(e)}")
                    continue  # Skip this command if parameters failed validation
            
            # Execute the command with parameters
            # DEBUG: Log command execution for all devices
            logger.debug(f"[BASE_DEVICE_DEBUG] Executing command '{cmd_name}' on {self.device_id} with params: {params}")
            
            logger.debug(f"Executing command '{cmd_name}' based on topic match.")
            await self._execute_single_action(cmd_name, cmd, params)
    
    async def send(self, command: str, params: Dict[str, Any]) -> Any:
        """Send a command to the device via MQTT (default implementation).
        
        This provides the default MQTT-based implementation for device communication.
        Devices using other protocols (HTTP, TCP, etc.) should override this method.
        
        Args:
            command: The command identifier
            params: Command parameters
            
        Returns:
            Command result or response
        """
        if not self.mqtt_client:
            logger.error(f"No MQTT client available for device {self.device_id}")
            return None
            
        # Find the command configuration
        available_commands = self.get_available_commands()
        if command not in available_commands:
            logger.error(f"Unknown command '{command}' for device {self.device_id}")
            return None
            
        cmd_config = available_commands[command]
        
        # Get the topic for this command
        topic = self.get_command_topic(command, cmd_config)
        if not topic:
            logger.error(f"No topic configured for command '{command}' on device {self.device_id}")
            return None
        
        # Prepare payload - for MQTT devices, this is typically the parameter value
        payload = "1"  # Default payload
        if params:
            # For simple commands with one parameter, use that value
            if len(params) == 1:
                payload = str(list(params.values())[0])
            else:
                # For complex commands, send JSON
                payload = json.dumps(params)
        
        try:
            # Publish the command via MQTT
            await self.mqtt_client.publish(topic, payload, qos=1)
            logger.debug(f"Sent MQTT command '{command}' to {topic}: {payload}")
            return {"success": True, "topic": topic, "payload": payload}
        except Exception as e:
            logger.error(f"Failed to send MQTT command '{command}' to device {self.device_id}: {e}")
            return {"success": False, "error": str(e)}
    
    def _is_wb_command_topic(self, topic: str) -> bool:
        """Check if topic is a WB command topic."""
        pattern = f"/devices/{re.escape(self.device_id)}/controls/(.+)/on"
        return bool(re.match(pattern, topic))

    async def _handle_wb_command(self, topic: str, payload: str):
        """Handle WB command topic messages."""
        # Extract control name (command name) from topic
        match = re.match(f"/devices/{re.escape(self.device_id)}/controls/(.+)/on", topic)
        if not match:
            return
        
        cmd_name = match.group(1)
        
        # Find corresponding command configuration
        available_commands = self.get_available_commands()
        if cmd_name not in available_commands:
            logger.warning(f"No command configuration found for WB control: {cmd_name}")
            return
        
        cmd_config = available_commands[cmd_name]
        
        # Check if command has a handler
        if not cmd_config.action or cmd_config.action not in self._action_handlers:
            logger.warning(f"No handler found for WB control: {cmd_name} (action: {cmd_config.action})")
            return
        
        # Process parameters from payload using command configuration
        params = self._process_wb_command_payload_from_config(cmd_name, cmd_config, payload)
        
        # Execute the handler using the action name
        await self._execute_single_action(cmd_config.action, cmd_config, params, source="wb_command")
        
        # Update WB control state to reflect the command
        await self._update_wb_control_state(cmd_name, payload)
    
    def _process_wb_command_payload_from_config(self, cmd_name: str, cmd_config, payload: str) -> Dict[str, Any]:
        """Process WB command payload into parameters using command configuration."""
        params = {}
        
        # If no parameters defined, it's a simple pushbutton
        if not hasattr(cmd_config, 'params') or not cmd_config.params:
            return params
        
        # Process the first parameter (WB controls typically map to one parameter)
        first_param = cmd_config.params[0]
        param_name = first_param.name
        param_type = getattr(first_param, 'type', 'string')
        
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
            if hasattr(first_param, 'default') and first_param.default is not None:
                params[param_name] = first_param.default
        
        return params

    def _process_wb_command_payload(self, control_name: str, payload: str) -> Dict[str, Any]:
        """Process WB command payload into parameters."""
        params = {}
        
        # For range controls, the payload is the value
        handler_lower = control_name.lower()
        if 'volume' in handler_lower or 'set_' in handler_lower:
            try:
                # Try to parse as numeric value
                value = float(payload)
                # Map volume to a generic parameter name
                if 'volume' in handler_lower:
                    params['volume'] = int(value)
                else:
                    params['value'] = value
            except ValueError:
                # If not numeric, treat as string
                params['value'] = payload
        
        return params
    
    async def _update_wb_control_state(self, control_name: str, payload: str):
        """Update WB control state topic with the new value."""
        if self.mqtt_client:
            state_topic = f"/devices/{self.device_id}/controls/{control_name}"
            await self.mqtt_client.publish(state_topic, payload, retain=True)
    
    async def _sync_state_to_wb_controls(self, state_updates: Dict[str, Any]):
        """Synchronize state changes to WB control topics with bidirectional mapping."""
        if not self.mqtt_client:
            return
        
        try:
            # Get state field to WB control mappings for this device
            control_mappings = self._get_wb_control_mappings()
            
            for state_field, value in state_updates.items():
                # Skip internal fields and non-relevant updates
                if state_field in ['last_command', 'device_id', 'device_name']:
                    continue
                
                # Check if this state field maps to any WB controls
                if state_field in control_mappings:
                    wb_controls = control_mappings[state_field]
                    if isinstance(wb_controls, str):
                        wb_controls = [wb_controls]
                    
                    # Update all mapped WB controls
                    for wb_control in wb_controls:
                        if wb_control in self._action_handlers:
                            wb_value = self._convert_state_to_wb_value(state_field, value)
                            if wb_value is not None:
                                control_topic = f"/devices/{self.device_id}/controls/{wb_control}"
                                await self.mqtt_client.publish(control_topic, str(wb_value), retain=True)
                                logger.debug(f"Synced {state_field}={value} to WB control {wb_control}={wb_value}")
                
                # Also check for direct handler name matches
                if state_field in self._action_handlers:
                    wb_value = self._convert_state_to_wb_value(state_field, value)
                    if wb_value is not None:
                        control_topic = f"/devices/{self.device_id}/controls/{state_field}"
                        await self.mqtt_client.publish(control_topic, str(wb_value), retain=True)
                        logger.debug(f"Synced direct {state_field}={value} to WB control {state_field}={wb_value}")
                        
        except Exception as e:
            logger.warning(f"Error syncing state to WB controls for {self.device_id}: {str(e)}")
    
    def _get_wb_control_mappings(self) -> Dict[str, Union[str, List[str]]]:
        """Get state field to WB control mappings for this device."""
        # Default mappings for common state fields
        mappings = {
            # Power state mappings
            'power': ['power_state', 'get_power', 'power_status'],
            'connected': ['connection_status', 'get_connection_status'],
            'connection_status': ['get_connection_status'],
            
            # Audio state mappings  
            'volume': ['set_volume', 'get_volume', 'volume_level'],
            'mute': ['mute', 'toggle_mute', 'get_mute'],
            
            # Input/source mappings
            'input_source': ['set_input', 'get_input', 'input'],
            'current_app': ['get_app', 'current_app'],
            'app': ['get_app', 'current_app'],
            
            # Playback state mappings
            'playback_state': ['get_playback_state', 'playback_status'],
            'media_type': ['get_media_type'],
            'title': ['get_title'],
            'artist': ['get_artist'],
            'album': ['get_album'],
            
            # Kitchen hood specific
            'light': ['light', 'set_light'],
            'speed': ['speed', 'set_speed', 'fan_speed'],
            
            # Environment specific
            'temperature': ['set_temperature', 'get_temperature'],
            'brightness': ['set_brightness', 'get_brightness'],
            'contrast': ['set_contrast', 'get_contrast'],
            
            # Network info
            'ip_address': ['get_ip_address'],
            'mac_address': ['get_mac_address'],
            
            # Error/status
            'error': ['get_error', 'error_status'],
        }
        
        # Allow devices to override mappings via configuration
        if hasattr(self.config, 'wb_state_mappings') and self.config.wb_state_mappings:
            mappings.update(self.config.wb_state_mappings)
        
        return mappings
    
    def _convert_state_to_wb_value(self, state_field: str, value: Any) -> Optional[str]:
        """Convert a device state value to a WB control value."""
        if value is None:
            return None
        
        # Handle boolean values
        if isinstance(value, bool):
            return "1" if value else "0"
        
        # Handle string values
        if isinstance(value, str):
            # Special handling for power states
            if state_field in ['power', 'connection_status'] and value.lower() in ['on', 'connected', 'true']:
                return "1"
            elif state_field in ['power', 'connection_status'] and value.lower() in ['off', 'disconnected', 'false']:
                return "0"
            else:
                return value
        
        # Handle numeric values
        if isinstance(value, (int, float)):
            # Volume, brightness, etc. should be in 0-100 range
            if state_field in ['volume', 'brightness', 'contrast'] and 0 <= value <= 100:
                return str(int(value))
            # Temperature values
            elif state_field in ['temperature'] and isinstance(value, (int, float)):
                return str(int(value))
            # Speed/level values
            elif state_field in ['speed', 'level']:
                return str(int(value))
            else:
                return str(value)
        
        # Handle enum values
        if hasattr(value, 'value'):
            return str(value.value)
        elif hasattr(value, 'name'):
            return str(value.name)
        
        # Fallback to string conversion
        return str(value)

    def _process_mqtt_payload(self, payload: str, param_defs: List[CommandParameterDefinition]) -> Dict[str, Any]:
        """
        Process an MQTT payload into a parameters dictionary based on parameter definitions.
        
        Args:
            payload: The MQTT payload string
            param_defs: List of parameter definitions
            
        Returns:
            Dict[str, Any]: Processed parameters dictionary
            
        Raises:
            ValueError: If parameter validation fails
        """
        # Default empty parameters
        provided_params = {}
        
        # Try to parse as JSON first
        try:
            json_params = json.loads(payload)
            if isinstance(json_params, dict):
                provided_params = json_params
            else:
                logger.debug(f"Payload parsed as JSON but is not an object: {payload}")
                # Handle simple JSON values (numbers, strings, booleans) when only one parameter is defined
                if len(param_defs) == 1:
                    param_def = param_defs[0]
                    param_name = param_def.name
                    param_type = param_def.type
                    
                    # Process the simple JSON value based on parameter type
                    try:
                        if param_type == "integer":
                            provided_params = {param_name: int(json_params)}
                        elif param_type == "float":
                            provided_params = {param_name: float(json_params)}
                        elif param_type == "boolean":
                            # Convert numeric values to boolean
                            if isinstance(json_params, (int, float)):
                                provided_params = {param_name: bool(json_params)}
                            elif isinstance(json_params, str):
                                provided_params = {param_name: json_params.lower() in ("1", "true", "yes", "on")}
                            else:
                                provided_params = {param_name: bool(json_params)}
                        else:  # string or any other type
                            provided_params = {param_name: str(json_params)}
                    except (ValueError, TypeError):
                        logger.error(f"Failed to convert JSON value '{json_params}' to type {param_type}")
                        raise ValueError(f"Failed to convert JSON value '{json_params}' to type {param_type}")
                else:
                    logger.error(f"Payload is a simple JSON value but command expects multiple parameters: {payload}")
                    raise ValueError("Simple value cannot be used with multiple parameters")
        except json.JSONDecodeError:
            # Handle single parameter commands with non-JSON payload
            if len(param_defs) == 1:
                param_def = param_defs[0]
                param_name = param_def.name
                param_type = param_def.type
                
                # Convert raw payload based on parameter type
                try:
                    if param_type == "integer":
                        provided_params = {param_name: int(payload)}
                    elif param_type == "float":
                        provided_params = {param_name: float(payload)}
                    elif param_type == "boolean":
                        provided_params = {param_name: payload.lower() in ("1", "true", "yes", "on")}
                    else:  # string or any other type
                        provided_params = {param_name: payload}
                except (ValueError, TypeError):
                    logger.error(f"Failed to convert payload '{payload}' to type {param_type}")
                    raise ValueError(f"Failed to convert payload '{payload}' to type {param_type}")
            else:
                logger.error(f"Payload is not valid JSON and command expects multiple parameters: {payload}")
                raise ValueError("Payload is not valid JSON and command expects multiple parameters")
        
        # Create and validate full parameter dictionary
        return self._resolve_and_validate_params(param_defs, provided_params)
    
    def _get_action_handler(self, action: str) -> Optional[ActionHandler]:
        """Get the handler function for the specified action."""
        # Convert to lower case for case-insensitive lookup
        action = action.lower()
        
        # DEBUG: Log handler lookup attempt
        logger.debug(f"[{self.device_name}] Looking up handler for action: '{action}'")
        logger.debug(f"[{self.device_name}] Available handlers: {list(self._action_handlers.keys())}")
        
        # Check if we have a handler for this action
        if handler := self._action_handlers.get(action):
            logger.debug(f"[{self.device_name}] Found direct handler for '{action}'")
            return handler
            
        # If no direct handler, look for handle_<action> method
        name = f"handle_{action}"
        if hasattr(self, name) and callable(getattr(self, name)):
            logger.debug(f"[{self.device_name}] Using implicit handler {name}")
            return getattr(self, name)
            
        # If not found, check if maybe it's in camelCase and we have a handler for snake_case
        if '_' not in action:
            # Convert camelCase to snake_case and try again
            snake_case = ''.join(['_' + c.lower() if c.isupper() else c for c in action]).lstrip('_')
            logger.debug(f"[{self.device_name}] Trying snake_case variant: '{snake_case}'")
            if handler := self._action_handlers.get(snake_case):
                logger.debug(f"[{self.device_name}] Found handler for snake_case variant '{snake_case}'")
                return handler
            
            # Try the implicit handler with snake_case
            name = f"handle_{snake_case}"
            if hasattr(self, name) and callable(getattr(self, name)):
                logger.debug(f"[{self.device_name}] Using implicit handler {name} for camelCase action")
                return getattr(self, name)
        
        logger.debug(f"[{self.device_name}] No handler found for action '{action}'")
        return None
    
    def _auto_register_handlers(self) -> None:
        """
        Automatically register handler methods based on naming convention.
        
        This method discovers all methods named handle_<action> and registers them 
        as action handlers for <action>. It will not override existing handlers.
        """
        for attr in dir(self):
            if attr.startswith("handle_"):
                action = attr.removeprefix("handle_").lower()
                # Only register if not already registered
                self._action_handlers.setdefault(action, getattr(self, attr))
                logger.debug(f"[{self.device_name}] Auto-registered handler for action '{action}'")
    
    async def _execute_single_action(
        self, 
        action_name: str, 
        cmd_config: BaseCommandConfig, 
        params: Dict[str, Any] = None,
        source: str = "unknown"
    ) -> Optional[CommandResult]:
        """
        Execute a single action with the provided configuration and parameters.
        
        Args:
            action_name: Name of the action to execute
            cmd_config: Command configuration
            params: Optional parameters for the action
            source: Source of the command call (e.g., "api", "mqtt", "system")
            
        Returns:
            Optional[CommandResult]: Result of the action execution
        """
        if params is None:
            params = {}
            
        try:
            # Get the action handler method from the instance
            handler = self._get_action_handler(action_name)
            if not handler:
                logger.warning(f"No action handler found for action: {action_name} in device {self.get_name()}")
                return self.create_command_result(
                    success=False, 
                    error=f"No handler found for action: {action_name}"
                )

            # Process parameters if not already provided
            if params is None:
                # Try to resolve parameters from cmd_config
                try:
                    params = self._resolve_and_validate_params(cmd_config.params or [], {})
                except ValueError as e:
                    # Parameter validation failed
                    error_msg = f"Parameter validation failed for {action_name}: {str(e)}"
                    logger.error(error_msg)
                    return self.create_command_result(success=False, error=error_msg)
            
            logger.debug(f"Executing action: {action_name} with handler: {handler}, params: {params}")
            
            # DEBUG: Enhanced logging for all device action execution
            logger.debug(f"[BASE_DEVICE_DEBUG] Calling handler for {action_name} on {self.device_id}: handler={handler.__name__ if hasattr(handler, '__name__') else str(handler)}")
            
            # Call the handler with the new parameter-based approach
            result = await handler(cmd_config=cmd_config, params=params)
            
            # DEBUG: Log result for all devices
            logger.debug(f"[BASE_DEVICE_DEBUG] Handler result for {action_name} on {self.device_id}: {result}")
            
            # Update state with information about the last command executed
            # Use the provided source parameter instead of flawed topic-based logic
            self.update_state(last_command=LastCommand(
                action=action_name,
                source=source,
                timestamp=datetime.now(),
                params=params
            ))
            
            # Return the result
            return result
                
        except Exception as e:
            error_msg = f"Error executing action {action_name}: {str(e)}"
            logger.error(error_msg)
            return self.create_command_result(success=False, error=error_msg)
    
    def get_current_state(self) -> StateT:
        """Return a copy of the current device state."""
        return cast(StateT, self.state)
    
    def _validate_state_updates(self, updates: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate that state updates contain only JSON serializable values.
        
        This validation helps catch serialization issues early, before they cause 
        problems when attempting to persist state.
        
        Args:
            updates: Dictionary of state updates to validate
            
        Returns:
            Tuple[bool, List[str]]: (is_valid, error_messages)
            Where is_valid is True if all updates are serializable
        """
        errors = []
        
        # Check each field being updated
        for field_name, field_value in updates.items():
            try:
                # Handle simple primitives that are always serializable
                if field_value is None or isinstance(field_value, (str, int, float, bool)):
                    continue
                    
                # Handle special types we know how to serialize
                if hasattr(field_value, 'model_dump') or hasattr(field_value, 'dict'):
                    continue
                    
                if isinstance(field_value, (datetime, Enum)):
                    continue
                    
                # For other types, test JSON serialization
                try:
                    json.dumps({field_name: field_value})
                except (TypeError, OverflowError) as e:
                    errors.append(f"Field '{field_name}' with type '{type(field_value).__name__}' is not JSON serializable: {str(e)}")
            except Exception as e:
                errors.append(f"Error validating field '{field_name}': {str(e)}")
                
        return len(errors) == 0, errors
    
    def update_state(self, **updates):
        """
        Update the device state using keyword arguments.
        Each keyword argument will update the corresponding attribute in the state.
        
        This method now includes validation to detect non-serializable fields early.
        Only triggers state change notification if the state actually changes.
        """
        # Skip empty updates
        if not updates:
            return
        
        # Validate updates for serializability
        is_valid, errors = self._validate_state_updates(updates)
        if not is_valid:
            # Log warnings for non-serializable fields
            for error in errors:
                logger.warning(f"Device {self.device_id}: {error}")
            
            # Log a summary warning
            logger.warning(f"Device {self.device_id}: Updating state with {len(errors)} potentially non-serializable fields")
        
        # Store current state for comparison
        previous_state = self.state.dict(exclude_unset=True)
        
        # Create a new state object with updated values
        updated_data = self.state.dict(exclude_unset=True)
        updated_data.update(updates)
        
        # Check if there are actual changes
        has_changes = False
        for key, value in updates.items():
            if key not in previous_state or previous_state[key] != value:
                has_changes = True
                break
        
        # If no changes, exit early
        if not has_changes:
            # logger.debug(f"No actual state changes for {self.device_name}")
            return
        
        # Preserve the concrete state type when updating
        state_cls = type(self.state)  # Get the actual class of the current state
        self.state = state_cls(**updated_data)  # Create a new instance of the same class
        
        # Validate complete state after update
        if hasattr(self.state, 'validate_serializable'):
            is_state_valid, state_errors = self.state.validate_serializable()
            if not is_state_valid:
                logger.warning(f"Device {self.device_id}: State contains non-serializable fields after update: {', '.join(state_errors)}")
        
        logger.debug(f"Updated state for {self.device_name}: {updates}")
        
        # Notify about state change only if there were actual changes
        self._notify_state_change()
    
    def _notify_state_change(self):
        """Notify the registered callback about state changes and emit SSE event."""
        # Notify persistence callback
        if self._state_change_callback:
            try:
                # DEBUG: Log all state change notifications
                logger.debug(f"[BASE_DEVICE_DEBUG] _notify_state_change called for {self.device_id}")
                
                self._state_change_callback(self.device_id)
            except Exception as e:
                logger.error(f"Error notifying state change for device {self.device_id}: {str(e)}")
        
        # Emit state change via SSE
        try:
            import asyncio
            
            # Get current state for broadcast
            current_state = self.get_current_state()
            
            # Prepare state event data
            state_event_data = {
                "device_id": self.device_id,
                "device_name": self.device_name,
                "state": current_state.dict() if hasattr(current_state, 'dict') else current_state,
                "timestamp": datetime.now().isoformat()
            }
            
            # Create task to broadcast state change
            asyncio.create_task(
                sse_manager.broadcast(
                    channel=SSEChannel.DEVICES,
                    event_type="state_change",
                    data=state_event_data
                )
            )
            
            logger.debug(f"State change SSE event queued for device {self.device_id}")
            
        except Exception as e:
            logger.error(f"Error emitting state change SSE event for device {self.device_id}: {str(e)}")
                
    def register_state_change_callback(self, callback):
        """Register a callback to be notified when state changes."""
        self._state_change_callback = callback
    
    async def execute_action(
        self, 
        action: str, 
        params: Optional[Dict[str, Any]] = None,
        source: str = "unknown"
    ) -> CommandResponse[StateT]:
        """Execute an action identified by action name.
        
        Args:
            action: The action name to execute
            params: Optional parameters for the action
            source: Source of the command call (e.g., "api", "mqtt", "system")
            
        Returns:
            CommandResponse: Response containing success status, device state, and any additional data
        """
        try:
            # Find the command configuration for this action
            cmd = None
            for cmd_name, command_config in self.get_available_commands().items():
                if cmd_name == action:
                    cmd = command_config
                    break
            
            if not cmd:
                error_msg = f"Action {action} not found in device configuration"
                return CommandResponse(
                    success=False,
                    device_id=self.device_id,
                    action=action,
                    state=self.state,  # Now properly typed
                    error=error_msg
                )
            
            # Validate parameters
            validated_params = {}
            if cmd.params:
                try:
                    # Validate and process parameters
                    validated_params = self._resolve_and_validate_params(cmd.params, params or {})
                except ValueError as e:
                    # Re-raise with more specific message
                    error_msg = f"Parameter validation failed for action '{action}': {str(e)}"
                    return CommandResponse(
                        success=False,
                        device_id=self.device_id,
                        action=action,
                        state=self.state,  # Now properly typed
                        error=error_msg
                    )
            elif params:
                # No parameters defined in config but params were provided
                validated_params = params
            
            # Execute the action with validated parameters and source
            result = await self._execute_single_action(action, cmd, validated_params, source)
            
            # Create the response based on the result
            success = result.get("success", True) if result else True
            response: CommandResponse[StateT] = CommandResponse(
                success=success,
                device_id=self.device_id,
                action=action,
                state=self.state  # Now properly typed
            )
            
            # Add error if present in result
            if not success and result and "error" in result:
                response["error"] = result["error"]
                
            # Add mqtt_command if present in result
            if result and "mqtt_command" in result:
                response["mqtt_command"] = result["mqtt_command"]
                
            # Add data if present in result
            if result and "data" in result:
                response["data"] = result["data"]
            
            if success:
                await self.emit_progress(f"Action {action} executed successfully", "action_success")
                
            return response
                
        except Exception as e:
            error_msg = f"Error executing action {action} for device {self.device_id}: {str(e)}"
            logger.error(error_msg)
            return CommandResponse(
                success=False,
                device_id=self.device_id,
                action=action,
                state=self.state,  # Now properly typed
                error=error_msg
            )
    
    def get_broadcast_ip(self) -> str:
        """
        Auto-detect the broadcast IP address for the local network.
        
        Prefers non-virtual, active network interfaces and filters out loopback.
        Detects Docker bridge networks and warns about their limitations.
        Falls back to global broadcast (255.255.255.255) if detection fails.
        
        Returns:
            str: The broadcast IP address to use for WOL packets
        """
        try:
            # Get network interface statistics to identify active interfaces
            net_stats = psutil.net_if_stats()
            
            # Collect potential broadcast addresses with priority scoring
            candidates = []
            docker_bridge_detected = False
            
            for iface_name, iface_addrs in psutil.net_if_addrs().items():
                # Skip loopback interfaces
                if iface_name.startswith(('lo', 'Loopback')):
                    continue
                
                # Check if interface is up and running
                iface_stat = net_stats.get(iface_name)
                if not iface_stat or not iface_stat.isup:
                    continue
                
                for addr in iface_addrs:
                    # Only process IPv4 addresses with broadcast capability
                    if addr.family == AF_INET and addr.broadcast:
                        # Calculate priority score (higher is better)
                        priority = 0
                        ip_addr = addr.address
                        
                        # Detect Docker bridge networks (common ranges: 172.17.x.x, 172.18.x.x, etc.)
                        is_docker_bridge = (
                            iface_name.startswith('eth') and 
                            ip_addr.startswith('172.') and 
                            any(ip_addr.startswith(f'172.{subnet}.') for subnet in range(16, 32))
                        )
                        
                        if is_docker_bridge:
                            docker_bridge_detected = True
                            # Significantly penalize Docker bridge networks
                            priority -= 20
                            logger.warning(f"Detected Docker bridge network on {iface_name} ({ip_addr}). "
                                         f"Broadcast to {addr.broadcast} may not reach devices outside the container. "
                                         f"Consider using host networking or specifying the host's broadcast IP.")
                        
                        # Prefer ethernet/wifi interfaces (but not if they're Docker bridges)
                        if any(keyword in iface_name.lower() for keyword in ['eth', 'en', 'wlan', 'wifi']) and not is_docker_bridge:
                            priority += 10
                        
                        # Penalize virtual/tunnel interfaces
                        if any(keyword in iface_name.lower() for keyword in ['tun', 'tap', 'vpn', 'vbox', 'vmware', 'docker']):
                            priority -= 5
                        
                        # Prefer interfaces with typical private network ranges (but not Docker bridges)
                        if ip_addr.startswith(('192.168.', '10.')) or (ip_addr.startswith('172.') and not is_docker_bridge):
                            priority += 5
                        
                        candidates.append((priority, addr.broadcast, iface_name, ip_addr))
            
            if candidates:
                # Sort by priority (highest first) and return the best broadcast address
                candidates.sort(key=lambda x: x[0], reverse=True)
                best_candidate = candidates[0]
                
                # Additional warning if we're using a Docker bridge despite detection
                if docker_bridge_detected and best_candidate[3].startswith('172.') and any(best_candidate[3].startswith(f'172.{subnet}.') for subnet in range(16, 32)):
                    logger.warning(f"Using Docker bridge broadcast IP {best_candidate[1]} - WOL packets may not reach external devices. "
                                 f"For WOL to work with external devices, use --network=host or provide the host's broadcast IP explicitly.")
                
                logger.debug(f"Auto-detected broadcast IP: {best_candidate[1]} from interface {best_candidate[2]} ({best_candidate[3]})")
                return best_candidate[1]
            
            # If no suitable interface found, log warning and fall back to global broadcast
            logger.warning("Could not detect a suitable broadcast IP address, using global broadcast 255.255.255.255")
            return "255.255.255.255"
            
        except Exception as e:
            logger.warning(f"Failed to auto-detect broadcast IP: {str(e)}, falling back to 255.255.255.255")
            return "255.255.255.255"

    async def send_wol_packet(self, mac_address: str, ip_address: str, port: int = 9) -> bool:
        """
        Send a Wake-on-LAN magic packet to the specified MAC address.
        
        Args:
            mac_address: MAC address of the target device (format: xx:xx:xx:xx:xx:xx)
            ip_address: Broadcast IP address (default: 255.255.255.255)
            port: UDP port to send the packet to (default: 9)
            
        Returns:
            bool: True if the packet was sent successfully, False otherwise
        """
        try:
            if not mac_address:
                logger.error("No MAC address provided for Wake-on-LAN")
                return False
                
            # Convert MAC address to bytes
            mac_bytes = bytes.fromhex(mac_address.replace(':', ''))
            
            # Create the magic packet (6 bytes of 0xFF followed by MAC address repeated 16 times)
            magic_packet = b'\xff' * 6 + mac_bytes * 16
            
            # Send the packet
            sock = socket(AF_INET, SOCK_DGRAM)
            sock.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)
            sock.sendto(magic_packet, (ip_address, port))
            sock.close()
            
            logger.info(f"Sent WOL packet to {mac_address}")
            await self.emit_progress(f"WOL packet sent to {mac_address}", "action_progress")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send WOL packet: {str(e)}")
            return False
    
    def get_available_commands(self) -> Dict[str, BaseCommandConfig]:
        """Return the list of available commands for this device."""
        return self.config.commands
    
    async def emit_progress(self, message: str, event_type: str = "progress") -> bool:
        """
        Emit a progress message via Server-Sent Events.
        
        Args:
            message: The message to emit
            event_type: The type of event (default: "progress")
            
        Returns:
            bool: True if the message was emitted successfully, False otherwise
        """
        try:
            if not message:
                logger.warning(f"Empty progress message not emitted for device {self.device_id}")
                return False
                
            # Prepare event data
            event_data = {
                "device_id": self.device_id,
                "device_name": self.device_name,
                "message": message,
                "timestamp": datetime.now().isoformat()
            }
            
            # Emit to devices channel via SSE
            await sse_manager.broadcast(
                channel=SSEChannel.DEVICES,
                event_type=event_type,
                data=event_data
            )
            
            logger.debug(f"Emitted {event_type} event for device {self.device_id}: {message}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to emit progress message: {str(e)}")
            return False
    
    def _resolve_and_validate_params(self, param_defs: List[CommandParameterDefinition], 
                                   provided_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resolves and validates command parameters against their definitions.
        
        Args:
            param_defs: List of parameter definitions
            provided_params: The parameters provided for this command execution
            
        Returns:
            Dict[str, Any]: The validated and resolved parameter dictionary
            
        Raises:
            ValueError: If required parameters are missing or validation fails
        """
        # Start with an empty result
        result = {}
        
        # If no parameters defined, return provided params as is
        if not param_defs:
            return provided_params
            
        # Process each parameter definition
        for param_def in param_defs:
            param_name = param_def.name
            param_type = param_def.type
            required = param_def.required
            default = param_def.default
            min_val = param_def.min
            max_val = param_def.max
            
            # Check if parameter is provided
            if param_name in provided_params:
                # Parameter is provided, validate it
                value = provided_params[param_name]
                
                # Type validation
                try:
                    if param_type == "integer":
                        value = int(value)
                    elif param_type == "float":
                        value = float(value)
                    elif param_type == "boolean":
                        if isinstance(value, str):
                            value = value.lower() in ("1", "true", "yes", "on")
                        else:
                            value = bool(value)
                    elif param_type == "range":
                        # Convert to float for range validation
                        value = float(value)
                        
                        # Validate range
                        if min_val is not None and value < min_val:
                            raise ValueError(f"Parameter '{param_name}' value {value} is below minimum {min_val}")
                        if max_val is not None and value > max_val:
                            raise ValueError(f"Parameter '{param_name}' value {value} is above maximum {max_val}")
                            
                        # Convert back to int if both min and max are integers
                        if (isinstance(min_val, int) or min_val is None) and (isinstance(max_val, int) or max_val is None):
                            value = int(value)
                    # String type doesn't need conversion
                except (ValueError, TypeError) as e:
                    raise ValueError(f"Parameter '{param_name}' has invalid type. Expected {param_type}: {str(e)}")
                    
                # Store validated value
                result[param_name] = value
                
            # Parameter not provided, handle based on whether it's required
            elif required:
                # Required parameter is missing
                raise ValueError(f"Required parameter '{param_name}' is missing")
            else:
                # Optional parameter, use default if available
                if default is not None:
                    result[param_name] = default
                    
        return result
    
    def create_mqtt_command_result(
        self, 
        success: bool, 
        mqtt_topic: str, 
        mqtt_payload: Any, 
        message: Optional[str] = None, 
        error: Optional[str] = None, 
        **extra_fields
    ) -> CommandResult:
        """
        Create a standardized CommandResult with MQTT command.
        
        Args:
            success: Whether the command was successful
            mqtt_topic: The MQTT topic to publish to
            mqtt_payload: The MQTT payload to publish (will be converted to string if not already)
            message: Optional success message
            error: Optional error message (only if success is False)
            **extra_fields: Additional fields to include in the result
            
        Returns:
            CommandResult: A standardized result dictionary with MQTT command
        """
        # Convert the payload to JSON string if it's a dict or list
        if isinstance(mqtt_payload, (dict, list)):
            mqtt_payload_str = json.dumps(mqtt_payload)
        else:
            mqtt_payload_str = str(mqtt_payload)
            
        # Create the MQTT command structure
        mqtt_command = {
            "topic": mqtt_topic,
            "payload": mqtt_payload_str
        }
        
        # Create the command result with the MQTT command
        result = self.create_command_result(
            success=success, 
            message=message, 
            error=error, 
            mqtt_command=mqtt_command,
            **extra_fields
        )
        
        return result
    
    def _validate_wb_controls_config(self) -> Dict[str, List[str]]:
        """
        Validate the wb_controls configuration and return any errors found.
        
        Returns:
            Dict[str, List[str]]: Dictionary mapping control names to lists of error messages
        """
        errors = {}
        
        if not hasattr(self.config, 'wb_controls') or not self.config.wb_controls:
            return errors  # No controls to validate
        
        valid_types = {'switch', 'range', 'value', 'text', 'pushbutton'}
        
        for control_name, control_config in self.config.wb_controls.items():
            control_errors = []
            
            # Validate control name
            if not control_name or not isinstance(control_name, str):
                control_errors.append("Control name must be a non-empty string")
            elif control_name.startswith('_'):
                control_errors.append("Control name cannot start with underscore")
            elif control_name not in self._action_handlers:
                control_errors.append(f"No handler found for control '{control_name}'")
            
            # Validate control config structure
            if not isinstance(control_config, dict):
                control_errors.append("Control configuration must be a dictionary")
                errors[control_name] = control_errors
                continue
            
            # Validate type field
            control_type = control_config.get('type')
            if not control_type:
                control_errors.append("Control type is required")
            elif control_type not in valid_types:
                control_errors.append(f"Invalid control type '{control_type}'. Valid types: {valid_types}")
            
            # Validate range-specific fields
            if control_type == 'range':
                min_val = control_config.get('min')
                max_val = control_config.get('max')
                
                if min_val is not None and not isinstance(min_val, (int, float)):
                    control_errors.append("'min' value must be a number")
                if max_val is not None and not isinstance(max_val, (int, float)):
                    control_errors.append("'max' value must be a number")
                if min_val is not None and max_val is not None and min_val >= max_val:
                    control_errors.append("'min' value must be less than 'max' value")
            
            # Validate title field
            title = control_config.get('title')
            if title is not None:
                if isinstance(title, dict):
                    if 'en' not in title:
                        control_errors.append("Title dictionary must contain 'en' key")
                    elif not isinstance(title['en'], str):
                        control_errors.append("Title 'en' value must be a string")
                elif not isinstance(title, str):
                    control_errors.append("Title must be a string or dictionary with 'en' key")
            
            # Validate order field
            order = control_config.get('order')
            if order is not None and not isinstance(order, int):
                control_errors.append("Order must be an integer")
            
            # Validate readonly field
            readonly = control_config.get('readonly')
            if readonly is not None and not isinstance(readonly, bool):
                control_errors.append("Readonly must be a boolean")
            
            if control_errors:
                errors[control_name] = control_errors
        
        return errors
    
    def _validate_wb_state_mappings(self) -> List[str]:
        """
        Validate the wb_state_mappings configuration and return any errors found.
        
        Returns:
            List[str]: List of error messages
        """
        errors = []
        
        if not hasattr(self.config, 'wb_state_mappings') or not self.config.wb_state_mappings:
            return errors  # No mappings to validate
        
        if not isinstance(self.config.wb_state_mappings, dict):
            errors.append("wb_state_mappings must be a dictionary")
            return errors
        
        for state_field, wb_controls in self.config.wb_state_mappings.items():
            # Validate state field name
            if not isinstance(state_field, str) or not state_field:
                errors.append(f"Invalid state field name: {state_field}")
                continue
            
            # Validate wb_controls value
            if isinstance(wb_controls, str):
                # Single control mapping
                if wb_controls not in self._action_handlers:
                    errors.append(f"State field '{state_field}' maps to unknown control '{wb_controls}'")
            elif isinstance(wb_controls, list):
                # Multiple control mapping
                for control in wb_controls:
                    if not isinstance(control, str):
                        errors.append(f"State field '{state_field}' contains non-string control name: {control}")
                    elif control not in self._action_handlers:
                        errors.append(f"State field '{state_field}' maps to unknown control '{control}'")
            else:
                errors.append(f"State field '{state_field}' mapping must be string or list of strings")
        
        return errors
    
    async def validate_wb_configuration(self) -> Tuple[bool, Dict[str, Any]]:
        """
        Comprehensive validation of WB emulation configuration.
        
        Returns:
            Tuple[bool, Dict[str, Any]]: (is_valid, validation_results)
        """
        validation_results = {
            'wb_controls_errors': {},
            'wb_state_mappings_errors': [],
            'handler_validation': {},
            'warnings': []
        }
        
        try:
            # Validate wb_controls configuration
            validation_results['wb_controls_errors'] = self._validate_wb_controls_config()
            
            # Validate wb_state_mappings configuration
            validation_results['wb_state_mappings_errors'] = self._validate_wb_state_mappings()
            
            # Validate that all handlers have reasonable WB control mappings
            for handler_name in self._action_handlers:
                if not handler_name.startswith('_'):
                    handler_validation = self._validate_handler_wb_compatibility(handler_name)
                    if handler_validation:
                        validation_results['handler_validation'][handler_name] = handler_validation
            
            # Check for potential issues
            warnings = []
            
            # Warn about missing MQTT client
            if not self.mqtt_client:
                warnings.append("MQTT client not available - WB emulation will be disabled")
            
            # Warn about disabled WB emulation
            if not self.should_publish_wb_virtual_device():
                warnings.append("WB emulation is disabled in configuration")
            
            # Warn about missing IR topics for devices that might need them
            if hasattr(self.config, 'auralic') and self.should_publish_wb_virtual_device():
                if not getattr(self.config.auralic, 'ir_power_on_topic', None):
                    warnings.append("IR power control not configured - power operations may be limited")
            
            validation_results['warnings'] = warnings
            
            # Determine if configuration is valid
            has_errors = (
                bool(validation_results['wb_controls_errors']) or
                bool(validation_results['wb_state_mappings_errors']) or
                bool(validation_results['handler_validation'])
            )
            
            is_valid = not has_errors
            
            # Log validation results
            if not is_valid:
                logger.warning(f"WB configuration validation failed for device {self.device_id}")
                for control, errors in validation_results['wb_controls_errors'].items():
                    for error in errors:
                        logger.warning(f"WB control '{control}': {error}")
                for error in validation_results['wb_state_mappings_errors']:
                    logger.warning(f"WB state mappings: {error}")
                for handler, issues in validation_results['handler_validation'].items():
                    for issue in issues:
                        logger.warning(f"Handler '{handler}': {issue}")
            
            if warnings:
                for warning in warnings:
                    logger.info(f"WB configuration warning for {self.device_id}: {warning}")
            
            return is_valid, validation_results
            
        except Exception as e:
            logger.error(f"Error during WB configuration validation for {self.device_id}: {str(e)}")
            validation_results['validation_error'] = str(e)
            return False, validation_results
    
    def _validate_handler_wb_compatibility(self, handler_name: str) -> List[str]:
        """
        Validate that a handler is compatible with WB control generation.
        
        Args:
            handler_name: Name of the handler to validate
            
        Returns:
            List[str]: List of compatibility issues
        """
        issues = []
        
        # Check if handler exists
        if handler_name not in self._action_handlers:
            issues.append("Handler method not found")
            return issues
        
        handler = self._action_handlers[handler_name]
        
        # Validate handler is callable
        if not callable(handler):
            issues.append("Handler is not callable")
        
        # Check if handler name suggests it needs parameters but no command config exists
        param_suggesting_names = ['set_', 'move_', 'launch_', 'click_']
        if any(handler_name.startswith(prefix) for prefix in param_suggesting_names):
            # Check if there's a command configuration for this handler
            command_configs = self.get_available_commands()
            if handler_name not in command_configs:
                issues.append("Handler suggests parameter usage but no command configuration found")
            else:
                cmd_config = command_configs[handler_name]
                if not hasattr(cmd_config, 'params') or not cmd_config.params:
                    issues.append("Handler suggests parameter usage but no parameters defined in configuration")
        
        return issues