import logging
import json
import asyncio
from datetime import datetime
from enum import Enum, auto
from typing import Dict, Any, List, Optional, Union, Callable, Awaitable, Tuple, TypeVar, cast

# Updated imports for new library
from pymotivaxmc2 import EmotivaController
from pymotivaxmc2.enums import Command, Property, Input, Zone

from devices.base_device import BaseDevice
from app.schemas import EmotivaXMC2State, LastCommand, EmotivaConfig as AppEmotivaConfig, EmotivaXMC2DeviceConfig, StandardCommandConfig, CommandParameterDefinition
from app.types import StateT, CommandResult, CommandResponse, ActionHandler

logger = logging.getLogger(__name__)

# Define enums for strongly typed states
class PowerState(str, Enum):
    """Power state enum for eMotiva device."""
    ON = "on"
    OFF = "off"
    UNKNOWN = "unknown"

class EMotivaXMC2(BaseDevice[EmotivaXMC2State]):
    """eMotiva XMC2 processor device implementation.
    
    This class implements control for the Emotiva XMC-2 processor using the pymotivaxmc2 library.
    
    Input Selection:
    - The device supports inputs like: hdmi1, hdmi2, coax1, optical1, tuner
    - These correspond to the values in the Input enum from pymotivaxmc2.enums
    
    State Management:
    - The device maintains state for power, volume, mute, inputs, etc.
    - Properties are automatically tracked via callbacks from the controller
    """
    
    # Define standard properties to monitor for consistent usage across methods
    PROPERTIES_TO_MONITOR = [
        Property.POWER,              # Main zone power
        Property.ZONE2_POWER,        # Zone 2 power
        Property.VOLUME,             # Main volume
        Property.ZONE2_VOLUME,       # Zone 2 volume
        Property.SOURCE,             # Current input
        Property.AUDIO_INPUT,        # Audio input
        Property.VIDEO_INPUT,        # Video input
        Property.AUDIO_BITSTREAM,    # Audio bitstream format
        Property.SELECTED_MODE       # Audio processing mode
    ]
    
    def __init__(self, config: EmotivaXMC2DeviceConfig, mqtt_client=None):
        """Initialize the EMotivaXMC2 device.
        
        Args:
            config: Device configuration
            mqtt_client: MQTT client for publishing messages
        """
        super().__init__(config, mqtt_client)
        
        self.client: Optional[EmotivaController] = None
        
        # Add a lock to protect setup from concurrent calls
        self._setup_lock = asyncio.Lock()
        
        # Initialize device state with Pydantic model
        self.state: EmotivaXMC2State = EmotivaXMC2State(
            device_id=self.config.device_id,
            device_name=self.config.device_name,
            power=None,
            zone2_power=None,
            input_source=None,
            video_input=None,
            audio_input=None,
            volume=None,
            mute=None,
            audio_mode=None,
            audio_bitstream=None,
            connected=False,
            ip_address=None,
            mac_address=None,
            startup_complete=False,
            notifications=False,
            last_command=None,
            error=None
        )
        
    async def setup(self) -> bool:
        """Initialize the device.
        
        Returns:
            bool: True if setup was successful, False otherwise
        """
        async with self._setup_lock:
            # Double-checked locking: if already connected, return early
            if self.client and self.state.connected:
                return True
            try:
                # Get emotiva configuration directly from config
                emotiva_config: AppEmotivaConfig = self.config.emotiva
                
                # Get the host IP address
                host = emotiva_config.host
                if not host:
                    logger.error(f"Missing 'host' in emotiva configuration for device: {self.get_name()}")
                    self.set_error("Missing host configuration")
                    return False
                
                # Store MAC address if available in config
                if emotiva_config.mac:
                    self.update_state(mac_address=emotiva_config.mac)
                    
                logger.info(f"Initializing eMotiva XMC2 device: {self.get_name()} at {host}")
                
                # Create and initialize controller with simplified constructor
                try:
                    self.client = EmotivaController(
                        host=host,
                        timeout=emotiva_config.timeout or 5.0,
                        protocol_max="3.1"  # Use the most recent protocol version
                    )
                    
                    # Update state with IP address at this point
                    self.update_state(ip_address=host)
                except Exception as e:
                    logger.error(f"Failed to create controller for {self.get_name()}: {str(e)}")
                    self.set_error(f"Controller initialization error: {str(e)}")
                    return False
                
                # Connect to the device with retry logic
                max_retries = emotiva_config.max_retries or 3
                retry_delay = emotiva_config.retry_delay or 2.0
                
                for attempt in range(1, max_retries + 1):
                    try:
                        await self.client.connect()
                        logger.info(f"Connected to device at {host} on attempt {attempt}")
                        break
                    except Exception as e:
                        if attempt < max_retries:
                            logger.warning(f"Connection attempt {attempt} failed: {str(e)}. Retrying in {retry_delay} seconds...")
                            await asyncio.sleep(retry_delay)
                        else:
                            logger.error(f"Failed to connect to device at {host} after {max_retries} attempts: {str(e)}")
                            self.set_error(f"Connection error: {str(e)}")
                            return False
                
                # Set up callbacks for property changes
                for prop in self.PROPERTIES_TO_MONITOR:
                    self._register_property_callback(prop)
                
                # Attempt to subscribe to properties
                try:
                    await self.client.subscribe(self.PROPERTIES_TO_MONITOR)
                    logger.info(f"Successfully subscribed to properties for {self.get_name()}")
                    
                    # Query initial state for key properties using _refresh_device_state
                    try:
                        # DEBUG: Log state refresh attempt
                        logger.debug(f"[EMOTIVA_DEBUG] Starting initial state refresh during setup (device={self.get_name()})")
                        
                        # Refresh all properties at once
                        updated_properties = await self._refresh_device_state()
                        
                        # DEBUG: Enhanced state logging
                        logger.debug(f"[EMOTIVA_DEBUG] Initial state refresh completed: {updated_properties} (device={self.get_name()})")
                        
                        # Log the initial power state which is most critical
                        if "power" in updated_properties:
                            logger.debug(f"Initial power state: {updated_properties['power']}")
                        
                        # Log other important properties if power is on
                        if self.state.power == PowerState.ON:
                            if "volume" in updated_properties:
                                logger.debug(f"Initial volume: {updated_properties['volume']}")
                            if "mute" in updated_properties:
                                logger.debug(f"Initial mute state: {updated_properties['mute']}")
                            if "source" in updated_properties:
                                logger.debug(f"Initial input source: {updated_properties['source']}")
                    except Exception as e:
                        # DEBUG: Log state refresh failure
                        logger.debug(f"[EMOTIVA_DEBUG] Initial state refresh failed: {str(e)} (device={self.get_name()})")
                        logger.warning(f"Failed to query initial state: {str(e)}")
                        # Continue setup even if initial state query fails
                    
                    # Update state with successful connection
                    self.clear_error()
                    self.update_state(
                        connected=True,
                        ip_address=host,
                        startup_complete=True,
                        notifications=True
                    )
                    
                    # Publish connection status
                    await self.publish_progress(f"Connected to {self.get_name()} at {host}")
                    
                    return True
                except Exception as e:
                    # Handle subscription failure
                    error_message = f"Error subscribing to properties: {str(e)}"
                    logger.error(error_message)
                    
                    # The device might be in standby mode if subscription fails
                    # Try to continue if force_connect is enabled
                    if emotiva_config.force_connect:
                        logger.warning(f"Force connect enabled, continuing with setup despite subscription failure")
                        
                        # Update state assuming standby mode
                        self.update_state(
                            connected=True,
                            ip_address=host,
                            startup_complete=True,
                            notifications=False,
                            power=PowerState.OFF  # Assume standby mode which is a valid state
                        )
                        
                        # Set error but don't fail setup
                        self.set_error(f"Subscription failed, using forced connection: {error_message}")
                        
                        # Publish connection status with warning
                        await self.publish_progress(f"Connected to {self.get_name()} at {host} in force connect mode (limited functionality)")
                        
                        return True
                    else:
                        self.set_error(error_message)
                        return False

            except Exception as e:
                logger.error(f"Failed to initialize eMotiva XMC2 device {self.get_name()}: {str(e)}")
                self.set_error(f"Initialization error: {str(e)}")
                return False

    async def shutdown(self) -> bool:
        """Cleanup device resources and properly shut down connections.
        
        Returns:
            bool: True if shutdown was successful, False otherwise
        """
        if not self.client:
            logger.info(f"No client initialized for {self.get_name()}, nothing to shut down")
            return True
            
        logger.info(f"Starting shutdown for eMotiva XMC2 device: {self.get_name()}")
        
        try:
            # Attempt to unsubscribe from notifications first
            try:
                await self.client.unsubscribe(self.PROPERTIES_TO_MONITOR)
                logger.debug(f"Successfully unsubscribed from properties for {self.get_name()}")
            except Exception as e:
                # Log but continue with shutdown even if unsubscribe fails
                logger.warning(f"Failed to unsubscribe from properties for {self.get_name()}: {str(e)}")
            
            # Let the library handle connection cleanup
            try:
                await self.client.disconnect()
                logger.info(f"Successfully disconnected {self.get_name()}")
            except Exception as e:
                logger.warning(f"Error during disconnect for {self.get_name()}: {str(e)}")
                # Continue with cleanup despite disconnect error
            
            # Update our state
            self.clear_error()
            self.update_state(
                connected=False,
                notifications=False
            )
            
            # Publish shutdown status
            await self.publish_progress(f"Disconnected from {self.get_name()}")
            
            # Release client reference
            self.client = None
            
            logger.info(f"eMotiva XMC2 device {self.get_name()} shutdown complete")
            return True
        except Exception as e:
            error_message = f"Failed to shutdown {self.get_name()}: {str(e)}"
            logger.error(error_message)
            self.set_error(str(e))
            
            # Still update state to reflect disconnection even if there was an error
            self.update_state(
                connected=False,
                notifications=False
            )
            
            # Release client reference even if there was an error
            self.client = None
            
            return False

    def _register_property_callback(self, property: Property):
        """Register a callback for a specific property change.
        
        Args:
            property: The property to monitor for changes
        """
        if not self.client:
            return
            
        # Use the new decorator pattern for callbacks
        @self.client.on(property)
        async def property_callback(value):
            # DEBUG: Enhanced callback logging
            logger.debug(f"[EMOTIVA_DEBUG] Hardware callback triggered: {property.value} = {value} (device={self.get_name()}, timestamp={datetime.now().isoformat()})")
            # Convert property enum value to lowercase for consistent handling
            property_name = property.value.lower()
            self._handle_property_change(property_name, None, value)
            
        # DEBUG: Log callback registration
        logger.debug(f"[EMOTIVA_DEBUG] Registering property callback for {property.value} (device={self.get_name()})")
        
    # Constants for valid properties
    VALID_PROPERTIES = {
        Property.POWER: "power",
        Property.ZONE2_POWER: "zone2_power",
        Property.VOLUME: "volume",
        Property.ZONE2_VOLUME: "zone2_volume",
        Property.SOURCE: "source",
        Property.AUDIO_INPUT: "audio_input",
        Property.VIDEO_INPUT: "video_input",
        Property.AUDIO_BITSTREAM: "audio_bitstream",
        Property.SELECTED_MODE: "selected_mode"
    }
    
    def _handle_property_change(self, property_name: str, old_value: Any, new_value: Any) -> None:
        """Handle property change events from the device state.
        
        Args:
            property_name: Name of the property that changed
            old_value: Previous value of the property
            new_value: New value of the property
        """
        # DEBUG: Enhanced property change logging
        logger.debug(f"[EMOTIVA_DEBUG] Property change callback: {property_name} = {old_value} -> {new_value} (device={self.get_name()}, connected={self.state.connected})")
        
        # Process the value with our helper
        processed_value = self._process_property_value(property_name, new_value)
        
        # Map property changes to our state model
        updates = {}
        
        if property_name == "power":
            updates["power"] = processed_value
        elif property_name == "zone2_power":
            updates["zone2_power"] = processed_value
        elif property_name == "volume":
            updates["volume"] = processed_value
        elif property_name == "zone2_volume":
            updates["zone2_volume"] = processed_value
        elif property_name == "mute":
            updates["mute"] = processed_value
        elif property_name == "source":  # Changed from "input"
            updates["input_source"] = new_value  # Use raw value for input_source
        elif property_name == "video_input":
            updates["video_input"] = new_value
        elif property_name == "audio_input":
            updates["audio_input"] = new_value
        elif property_name == "audio_bitstream":
            updates["audio_bitstream"] = new_value
        elif property_name == "selected_mode":  # Changed from "audio_mode"
            updates["audio_mode"] = new_value
            
        # Apply state updates if any
        if updates:
            # DEBUG: Log state updates triggered by property changes
            logger.debug(f"[EMOTIVA_DEBUG] Property change triggering state update: {updates} (device={self.get_name()})")
            self.update_state(**updates)
    
    def _process_property_value(self, property_name: str, value: Any) -> Any:
        """
        Process and convert property values to the correct type.
        
        Args:
            property_name: Name of the property
            value: Property value to convert
            
        Returns:
            Converted property value
        """
        if value is None:
            return None
            
        if property_name in ["power", "zone2_power"]:
            # Convert power values to our PowerState enum
            if isinstance(value, str):
                return PowerState.ON if value.lower() == "on" else PowerState.OFF if value.lower() == "off" else PowerState.UNKNOWN
            return value  # Already converted
        elif property_name in ["volume", "zone2_volume"]:
            # Convert volume to float
            try:
                return float(value)
            except (ValueError, TypeError):
                return 0.0
        elif property_name == "mute":
            # Convert mute to boolean
            if isinstance(value, str):
                return value.lower() in ("on", "true", "1", "yes")
            return bool(value)
        
        # For other properties, return as is
        return value

    async def publish_progress(self, message: str) -> None:
        """
        Publish a progress message to the MQTT progress topic for this device.
        
        Args:
            message: The message to publish
        """
        if not self.mqtt_client or not self.mqtt_progress_topic:
            return
            
        try:
            # Ensure the topic has proper prefix/suffix
            topic = self.mqtt_progress_topic
            if not topic.startswith('/'):
                topic = f'/{topic}'
                
            # Include device info in the progress message
            progress_data = {
                "device_id": self.device_id,
                "device_name": self.device_name,
                "timestamp": datetime.now().isoformat(),
                "message": message
            }
            
            # Publish to MQTT
            await self.mqtt_client.publish(topic, json.dumps(progress_data))
            logger.debug(f"Published progress message to {topic}: {message}")
        except Exception as e:
            logger.error(f"Error publishing progress message: {str(e)}")
            # Don't set error state for publishing issues as they might be transient
            # and not related to the device itself

    def update_state(self, **kwargs) -> None:
        """
        Update the device state with the provided values.
        
        Args:
            **kwargs: State values to update
        """
        # DEBUG: Log all state updates with current state context
        logger.debug(f"[EMOTIVA_DEBUG] State update requested: {kwargs} (device={self.get_name()}, current_power={self.state.power}, connected={self.state.connected})")
        
        # Convert string power states to enum values if needed
        if 'power' in kwargs and isinstance(kwargs['power'], str):
            power_value = kwargs['power'].lower()
            kwargs['power'] = PowerState.ON if power_value == 'on' else PowerState.OFF if power_value == 'off' else PowerState.UNKNOWN
            
        if 'zone2_power' in kwargs and isinstance(kwargs['zone2_power'], str):
            zone2_value = kwargs['zone2_power'].lower()
            kwargs['zone2_power'] = PowerState.ON if zone2_value == 'on' else PowerState.OFF if zone2_value == 'off' else PowerState.UNKNOWN
            
        # Call the parent update_state method
        super().update_state(**kwargs)

    def _update_last_command(self, action: str, params: Dict[str, Any] = None):
        """Update last command in the device state.
        
        Args:
            action: The action that was executed
            params: Parameters used for the action
        """
        # Create a LastCommand model with current information
        last_command = LastCommand(
            action=action,
            source="api",
            timestamp=datetime.now(),
            params=params
        )
        # Store the LastCommand model directly in the state
        self.update_state(last_command=last_command)
        
    def _validate_parameter(self, 
                           param_name: str, 
                           param_value: Any, 
                           param_type: str, 
                           required: bool = True, 
                           min_value: Optional[float] = None, 
                           max_value: Optional[float] = None, 
                           action: str = "") -> Tuple[bool, Any, Optional[str]]:
        """Validate a parameter against its definition and convert to correct type.
        
        Args:
            param_name: Name of the parameter
            param_value: Value of the parameter
            param_type: Expected type ('string', 'integer', 'float', 'boolean', 'range')
            required: Whether the parameter is required
            min_value: Minimum value (for numeric types)
            max_value: Maximum value (for numeric types)
            action: Action name for error messages
            
        Returns:
            Tuple of (is_valid, converted_value, error_message)
            where error_message is None if validation passed
        """
        # Check if parameter is required but missing
        if required and param_value is None:
            return False, None, f"Missing required '{param_name}' parameter"
            
        # Return early if parameter is not required and not provided
        if not required and param_value is None:
            return True, None, None
            
        converted_value = param_value
        
        # Convert value to the correct type
        try:
            if param_type == "integer":
                converted_value = int(param_value)
                
                # Check range constraints if specified
                if min_value is not None and converted_value < min_value:
                    return False, converted_value, f"{param_name} value {converted_value} is below minimum {min_value}"
                if max_value is not None and converted_value > max_value:
                    return False, converted_value, f"{param_name} value {converted_value} is above maximum {max_value}"
                    
            elif param_type in ("float", "range"):
                converted_value = float(param_value)
                
                # Check range constraints if specified
                if min_value is not None and converted_value < min_value:
                    return False, converted_value, f"{param_name} value {converted_value} is below minimum {min_value}"
                if max_value is not None and converted_value > max_value:
                    return False, converted_value, f"{param_name} value {converted_value} is above maximum {max_value}"
                    
            elif param_type == "boolean":
                if isinstance(param_value, str):
                    converted_value = param_value.lower() in ("yes", "true", "1", "on")
                else:
                    converted_value = bool(param_value)
                    
        except (ValueError, TypeError):
            error_msg = f"Invalid {param_name} value: {param_value}. Must be a {param_type} value."
            return False, param_value, error_msg
            
        return True, converted_value, None

    # Add zone-specific helpers
    def _get_zone(self, zone_id: Union[int, str] = 1) -> Zone:
        """Get the Zone enum corresponding to the zone ID.
        
        Args:
            zone_id: Zone ID (1 for main, 2 for zone2)
            
        Returns:
            Zone enum value
        """
        try:
            zone_id = int(zone_id)
            if zone_id == 1:
                return Zone.MAIN
            elif zone_id == 2:
                return Zone.ZONE2
            else:
                logger.warning(f"Invalid zone ID: {zone_id}, defaulting to main zone")
                return Zone.MAIN
        except (ValueError, TypeError):
            if str(zone_id).lower() == "main":
                return Zone.MAIN
            elif str(zone_id).lower() in ("zone2", "zone_2"):
                return Zone.ZONE2
            else:
                logger.warning(f"Invalid zone ID: {zone_id}, defaulting to main zone")
                return Zone.MAIN

    async def _refresh_device_state(self) -> Dict[str, Any]:
        """
        Refresh the full device state by querying all important properties.
        
        This is used after powering on from standby to ensure state is in sync.
        
        Returns:
            Dict[str, Any]: Dictionary of updated properties and their values
        """
        # DEBUG: Log state refresh start
        logger.debug(f"[EMOTIVA_DEBUG] _refresh_device_state called (device={self.get_name()}, connected={self.state.connected})")
        
        if not self.client:
            logger.warning("Cannot refresh device state: client not initialized")
            return {}
            
        try:
            # Query all properties we care about using the status API
            properties_to_query = [
                Property.POWER,              # Main zone power
                Property.ZONE2_POWER,        # Zone 2 power
                Property.VOLUME,             # Main volume
                Property.ZONE2_VOLUME,       # Zone 2 volume
                Property.SOURCE,             # Current input
                Property.AUDIO_INPUT,        # Audio input
                Property.VIDEO_INPUT,        # Video input
                Property.AUDIO_BITSTREAM,    # Audio bitstream format
                Property.SELECTED_MODE       # Audio processing mode
            ]
            
            # DEBUG: Log properties being queried
            logger.debug(f"[EMOTIVA_DEBUG] Querying properties: {[p.value for p in properties_to_query]} (device={self.get_name()})")
            
            # Use the status method to get all properties at once
            result = await self.client.status(*properties_to_query)
            
            # Process and update our state with the results
            updated_properties = {}
            for prop, value in result.items():
                # Convert property enum to string for our internal handling
                prop_name = prop.value.lower()
                
                # Process the value with our helper
                processed_value = self._process_property_value(prop_name, value)
                updated_properties[prop_name] = processed_value
                
                # Handle input property specially
                if prop == Property.SOURCE:
                    self.update_state(input_source=value)
                else:
                    self.update_state(**{self.VALID_PROPERTIES.get(prop, prop_name): processed_value})
                    
            logger.debug(f"Device state refresh completed for {self.get_name()} ({len(updated_properties)}/{len(properties_to_query)} properties)")
            return updated_properties
            
        except Exception as e:
            logger.warning(f"Error refreshing device state: {str(e)}")
            return {}

    async def handle_power_on(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """Handle power on command.
        
        Args:
            cmd_config: Command configuration
            params: Parameters (may include zone)
            
        Returns:
            Command execution result
        """
        # DEBUG: Log command start with full context
        logger.debug(f"[EMOTIVA_DEBUG] power_on command received: params={params}, connected={self.state.connected}, power={self.state.power} (device={self.get_name()})")
        
        # If client is not initialized or not connected, reconnect first
        if not self.client or not self.state.connected:
            # DEBUG: Log reconnection trigger
            logger.debug(f"[EMOTIVA_DEBUG] Triggering reconnection: client={self.client is not None}, connected={self.state.connected} (device={self.get_name()})")
            logger.info(f"Device {self.get_name()} not connected, attempting reconnection before power on")
            try:
                await self.setup()
            except Exception as e:
                logger.error(f"Failed to reconnect device {self.get_name()} before power on: {str(e)}")
                return self.create_command_result(
                    success=False,
                    error=f"Failed to connect to device: {str(e)}"
                )
        
        # Get zone parameter if specified
        zone_id = 1  # Default to main zone
        
        if params and "zone" in params:
            zone_param = cmd_config.get_parameter("zone")
            is_valid, zone_value, error_msg = self._validate_parameter(
                param_name="zone",
                param_value=params.get("zone"),
                param_type=zone_param.type if zone_param else "integer",
                required=False,
                action="power_on"
            )
            
            if not is_valid:
                return self.create_command_result(success=False, error=error_msg)
                
            if zone_value is not None:
                zone_id = zone_value
                
        # Get zone as enum
        zone = self._get_zone(zone_id)
        
        # Check current power state
        current_power = None
        if zone == Zone.MAIN:
            current_power = self.state.power
        elif zone == Zone.ZONE2:
            current_power = self.state.zone2_power
                
        # If state is unknown or stale, synchronize it
        if current_power is None or current_power == PowerState.UNKNOWN:
            try:
                # Synchronize state for this zone using _refresh_device_state for main zone
                # or _synchronize_state for zone2
                updated_properties = await self._synchronize_state(zone_id)
                
                # Get updated power state
                if zone == Zone.MAIN:
                    current_power = self.state.power
                elif zone == Zone.ZONE2:
                    current_power = self.state.zone2_power
                    
                logger.debug(f"Synchronized power state for zone {zone_id} before power on: {current_power}")
            except Exception as e:
                logger.warning(f"Failed to synchronize state for zone {zone_id}: {str(e)}")
                # Continue with power on attempt even if we couldn't verify state
        
        # Check if already powered on
        if current_power == PowerState.ON:
            logger.debug(f"Zone {zone_id} is already powered on, skipping command")
            return self.create_command_result(
                success=True,
                message=f"Zone {zone_id} is already powered on",
                zone=zone_id
            )
        
        try:
            # Power on the specified zone
            if zone == Zone.MAIN:
                await self.client.power_on(zone=zone)
                self.update_state(power=PowerState.ON)
                logger.info(f"Main zone powered on successfully")
            elif zone == Zone.ZONE2:
                await self.client.power_on(zone=zone)
                self.update_state(zone2_power=PowerState.ON)
                logger.info(f"Zone 2 powered on successfully")
            else:
                logger.warning(f"Unsupported zone: {zone}")
                return self.create_command_result(
                    success=False,
                    error=f"Unsupported zone: {zone_id}"
                )
            
            # Clear any errors
            self.clear_error()
            
            # Update the last command information
            self._update_last_command("power_on", {"zone": zone_id})
            
            # If main zone was powered on, ensure we're subscribed to all properties
            if zone == Zone.MAIN:
                try:
                    # Subscribe to all properties to ensure we get updates
                    await self.client.subscribe(self.PROPERTIES_TO_MONITOR)
                    
                    # Update our connected and notification status
                    self.update_state(
                        connected=True,
                        startup_complete=True,
                        notifications=True
                    )
                    
                    # Synchronize state after power on to get current values
                    await asyncio.sleep(1.0)  # Brief delay to allow device to stabilize
                    updated_properties = await self._refresh_device_state()
                    
                    # Publish progress message
                    await self.publish_progress(f"Zone {zone_id} powered on successfully")
                    
                    # Return success result with updated properties
                    return self.create_command_result(
                        success=True,
                        message=f"Zone {zone_id} powered on successfully",
                        power=PowerState.ON.value,
                        zone=zone_id,
                        updated_properties=list(updated_properties.keys()) if updated_properties else []
                    )
                except Exception as e:
                    logger.error(f"Error during post-power-on operations: {str(e)}")
                    # Still return success for the power-on, but include warning
                    return self.create_command_result(
                        success=True,
                        message=f"Zone {zone_id} powered on, but state synchronization had errors: {str(e)}",
                        power=PowerState.ON.value,
                        zone=zone_id,
                        warnings=["State synchronization incomplete, some state updates may be missing"]
                    )
            else:
                # For non-main zones, just return success
                await self.publish_progress(f"Zone {zone_id} powered on successfully")
                return self.create_command_result(
                    success=True,
                    message=f"Zone {zone_id} powered on successfully",
                    zone=zone_id,
                    zone2_power=PowerState.ON.value if zone == Zone.ZONE2 else None
                )
                
        except Exception as e:
            error_message = f"Failed to power on zone {zone_id}: {str(e)}"
            logger.error(error_message)
            self.set_error(error_message)
            await self.publish_progress(f"Failed to power on zone {zone_id}: {str(e)}")
            return self.create_command_result(
                success=False,
                error=error_message
            )

    async def handle_power_off(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """Handle power off command.
        
        Args:
            cmd_config: Command configuration
            params: Parameters (may include zone)
            
        Returns:
            Command execution result
        """
        # DEBUG: Log command start with full context
        logger.debug(f"[EMOTIVA_DEBUG] power_off command received: params={params}, connected={self.state.connected}, power={self.state.power} (device={self.get_name()})")
        
        # If client is not initialized or not connected, reconnect first
        if not self.client or not self.state.connected:
            # DEBUG: Log reconnection trigger
            logger.debug(f"[EMOTIVA_DEBUG] Triggering reconnection for power_off: client={self.client is not None}, connected={self.state.connected} (device={self.get_name()})")
            logger.info(f"Device {self.get_name()} not connected, attempting reconnection before power off")
            try:
                await self.setup()
            except Exception as e:
                logger.error(f"Failed to reconnect device {self.get_name()} before power off: {str(e)}")
                return self.create_command_result(
                    success=False,
                    error=f"Failed to connect to device: {str(e)}"
                )
        
        # Get zone parameter if specified
        zone_id = 1  # Default to main zone
        
        if params and "zone" in params:
            zone_param = cmd_config.get_parameter("zone")
            is_valid, zone_value, error_msg = self._validate_parameter(
                param_name="zone",
                param_value=params.get("zone"),
                param_type=zone_param.type if zone_param else "integer",
                required=False,
                action="power_off"
            )
            
            if not is_valid:
                return self.create_command_result(success=False, error=error_msg)
                
            if zone_value is not None:
                zone_id = zone_value
                
        # Get zone as enum
        zone = self._get_zone(zone_id)
        
        # Check current power state
        current_power = None
        if zone == Zone.MAIN:
            current_power = self.state.power
        elif zone == Zone.ZONE2:
            current_power = self.state.zone2_power
                
        if current_power == PowerState.OFF:
            logger.debug(f"Zone {zone_id} is already powered off, skipping command")
            return self.create_command_result(
                success=True,
                message=f"Zone {zone_id} is already powered off",
                zone=zone_id
            )
            
        # If state is unknown, request an update
        if current_power is None or current_power == PowerState.UNKNOWN:
            try:
                # Synchronize state for this zone using _synchronize_state
                updated_properties = await self._synchronize_state(zone_id)
                
                # Get updated power state
                if zone == Zone.MAIN:
                    current_power = self.state.power
                elif zone == Zone.ZONE2:
                    current_power = self.state.zone2_power
                    
                logger.debug(f"Synchronized power state for zone {zone_id} before power off: {current_power}")
                    
                # Check again if already off
                if current_power == PowerState.OFF:
                    logger.debug(f"Zone {zone_id} is already powered off (verified), skipping command")
                    return self.create_command_result(
                        success=True,
                        message=f"Zone {zone_id} is already powered off (verified)",
                        zone=zone_id
                    )
            except Exception as e:
                logger.warning(f"Failed to get current power state for zone {zone_id}: {str(e)}")
                # Continue with power off attempt even if we couldn't verify state
        
        try:
            # Power off the specified zone
            if zone == Zone.MAIN:
                await self.client.power_off(zone=zone)
                self.update_state(power=PowerState.OFF)
                logger.info(f"Main zone powered off successfully")
            elif zone == Zone.ZONE2:
                await self.client.power_off(zone=zone)
                self.update_state(zone2_power=PowerState.OFF)
                logger.info(f"Zone 2 powered off successfully")
            else:
                logger.warning(f"Unsupported zone: {zone}")
                return self.create_command_result(
                    success=False,
                    error=f"Unsupported zone: {zone_id}"
                )
            
            # Clear any errors
            self.clear_error()
            
            # Update the last command information
            self._update_last_command("power_off", {"zone": zone_id})
            
            if zone == Zone.MAIN:
                return self.create_command_result(
                    success=True,
                    message=f"Zone {zone_id} powered off successfully",
                    power=PowerState.OFF.value,
                    zone=zone_id
                )
            else:
                return self.create_command_result(
                    success=True,
                    message=f"Zone {zone_id} powered off successfully",
                    zone=zone_id,
                    zone2_power=PowerState.OFF.value if zone == Zone.ZONE2 else None
                )
                
        except Exception as e:
            error_message = f"Failed to power off zone {zone_id}: {str(e)}"
            logger.error(error_message)
            self.set_error(error_message)
            return self.create_command_result(
                success=False,
                error=error_message
            )
            
    async def _handle_command_error(self, action: str, error: Exception, context: Dict[str, Any] = None) -> CommandResult:
        """Handle command errors in a consistent way.
        
        This centralizes error handling logic for commands to ensure consistent behavior.
        
        Args:
            action: The action that was being performed
            error: The exception that occurred
            context: Additional context for the error
            
        Returns:
            CommandResult: Error result
        """
        error_message = f"Failed to {action}: {str(error)}"
        logger.error(error_message)
        self.set_error(error_message)
        
        # Publish error message to MQTT
        try:
            error_context = f" ({', '.join([f'{k}={v}' for k, v in context.items()])})" if context else ""
            await self.publish_progress(f"Error: {error_message}{error_context}")
        except Exception as e:
            logger.warning(f"Failed to publish error message: {str(e)}")
        
        # Create error result
        result = self.create_command_result(
            success=False,
            error=error_message
        )
        
        # Add context to result if provided
        if context:
            for key, value in context.items():
                if key not in result:
                    result[key] = value
                    
        return result
        
    async def handle_set_input(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """Handle setting input source by input ID.
        
        This method supports setting inputs using the format recognized by the Emotiva controller.
        Supported inputs include: hdmi1-hdmi8, coax1-coax4, optical1-optical4, tuner
        
        Args:
            cmd_config: Command configuration
            params: Parameters containing input ID
            
        Returns:
            Command execution result
        """
        # DEBUG: Log command start with full context
        logger.debug(f"[EMOTIVA_DEBUG] set_input command received: params={params}, connected={self.state.connected}, current_input={self.state.input_source} (device={self.get_name()})")
        
        # If client is not initialized or not connected, reconnect first
        if not self.client or not self.state.connected:
            # DEBUG: Log reconnection trigger
            logger.debug(f"[EMOTIVA_DEBUG] Triggering reconnection for set_input: client={self.client is not None}, connected={self.state.connected} (device={self.get_name()})")
            logger.info(f"Device {self.get_name()} not connected, attempting reconnection before setting input")
            try:
                await self.setup()
            except Exception as e:
                return await self._handle_command_error(
                    "reconnect device",
                    e,
                    {"action": "set_input"}
                )
        
        # Validate parameters
        if not params:
            return self.create_command_result(success=False, error="Missing input parameters")
        
        # Get and validate input parameter
        input_param = cmd_config.get_parameter("input")
        is_valid, input_id, error_msg = self._validate_parameter(
            param_name="input",
            param_value=params.get("input"),
            param_type=input_param.type if input_param else "string",
            action="set_input"
        )
        
        if not is_valid:
            return self.create_command_result(success=False, error=error_msg)
        
        try:
            # Normalize the input ID to lowercase
            normalized_input = input_id.lower()
            
            # Check if device is powered on - can't change input if off
            if self.state.power != PowerState.ON:
                # If power state is unknown, try to synchronize
                if self.state.power is None or self.state.power == PowerState.UNKNOWN:
                    try:
                        # Use _refresh_device_state to update multiple properties at once
                        await self._refresh_device_state()
                        logger.debug(f"Refreshed device state before set input, power={self.state.power}")
                    except Exception as e:
                        logger.warning(f"Failed to refresh state before set input: {str(e)}")
                
                # Check again after synchronization
                if self.state.power != PowerState.ON:
                    error_message = "Cannot set input while device is powered off"
                    logger.warning(error_message)
                    await self.publish_progress(error_message)
                    return self.create_command_result(
                        success=False,
                        error=error_message,
                        power=self.state.power.value if self.state.power else "unknown",
                        input=normalized_input
                    )
            
            # Check if this is already the current input
            if self.state.input_source == normalized_input:
                logger.debug(f"Input already set to {normalized_input}, skipping command")
                await self.publish_progress(f"Input already set to {normalized_input}")
                return self.create_command_result(
                    success=True,
                    message=f"Input already set to {normalized_input}",
                    input=normalized_input
                )
                
            # If input state is unknown, synchronize state
            if self.state.input_source is None:
                try:
                    # Use our _refresh_device_state method to efficiently query multiple properties
                    updated_properties = await self._refresh_device_state()
                    logger.debug(f"Refreshed device state before set input, current_input={self.state.input_source}")
                    
                    # Check again if already set to requested input
                    if self.state.input_source == normalized_input:
                        logger.debug(f"Input already set to {normalized_input} (verified), skipping command")
                        await self.publish_progress(f"Input already set to {normalized_input} (verified)")
                        return self.create_command_result(
                            success=True,
                            message=f"Input already set to {normalized_input} (verified)",
                            input=normalized_input,
                            updated_properties=list(updated_properties.keys()) if updated_properties else []
                        )
                except Exception as e:
                    logger.warning(f"Failed to refresh state: {str(e)}")
                    # Continue with input selection even if we couldn't verify state
            
            # Try to find the matching Input enum
            input_enum = None
            try:
                # First try to find the enum by name (uppercase, like HDMI1)
                input_enum = getattr(Input, normalized_input.upper())
            except (AttributeError, ValueError):
                # If not a direct match, try to find a close match
                for enum_value in Input:
                    if enum_value.value.lower() == normalized_input:
                        input_enum = enum_value
                        break
            
            if input_enum:
                # Use the enum directly
                await self.client.select_input(input_enum)
                logger.debug(f"Selected input using enum: {input_enum}")
            else:
                # Fall back to using string if enum not found
                logger.debug(f"No matching enum found for input '{normalized_input}', using string value")
                await self.client.select_input(normalized_input)
            
            # Update our internal state
            self.update_state(input_source=normalized_input)
            
            # Clear any errors
            self.clear_error()
            
            # Update the last command information
            self._update_last_command("set_input", {"input": normalized_input})
            
            # Publish success message
            await self.publish_progress(f"Input set to {normalized_input}")
            
            # Return success result
            return self.create_command_result(
                success=True,
                message=f"Input set to {normalized_input} successfully",
                input=normalized_input
            )
        except Exception as e:
            return await self._handle_command_error(
                f"set input to {input_id}",
                e,
                {"input": normalized_input}
            )
            
    async def handle_set_volume(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """Handle setting volume level.
        
        Args:
            cmd_config: Command configuration
            params: Parameters containing volume level
            
        Returns:
            Command execution result
        """
        # DEBUG: Log command start with full context  
        logger.debug(f"[EMOTIVA_DEBUG] set_volume command received: params={params}, connected={self.state.connected}, current_volume={self.state.volume} (device={self.get_name()})")
        
        # If client is not initialized or not connected, reconnect first
        if not self.client or not self.state.connected:
            # DEBUG: Log reconnection trigger
            logger.debug(f"[EMOTIVA_DEBUG] Triggering reconnection for set_volume: client={self.client is not None}, connected={self.state.connected} (device={self.get_name()})")
            logger.info(f"Device {self.get_name()} not connected, attempting reconnection before setting volume")
            try:
                await self.setup()
            except Exception as e:
                logger.error(f"Failed to reconnect device {self.get_name()} before setting volume: {str(e)}")
                return self.create_command_result(
                    success=False,
                    error=f"Failed to connect to device: {str(e)}"
                )
        
        # Validate parameters
        if not params:
            return self.create_command_result(success=False, error="Missing volume parameters")
        
        # Get and validate level parameter
        level_param = cmd_config.get_parameter("level")
        is_valid, level, error_msg = self._validate_parameter(
            param_name="level",
            param_value=params.get("level"),
            param_type=level_param.type if level_param else "range",
            min_value=level_param.min if level_param else -96.0,
            max_value=level_param.max if level_param else 0.0,
            action="set_volume"
        )
        
        if not is_valid:
            return self.create_command_result(success=False, error=error_msg)
            
        # Get zone parameter if specified
        zone_param = cmd_config.get_parameter("zone")
        zone_id = 1  # Default to main zone
        
        if zone_param and "zone" in params:
            is_valid, zone_value, error_msg = self._validate_parameter(
                param_name="zone",
                param_value=params.get("zone"),
                param_type=zone_param.type if zone_param else "integer",
                required=False,
                action="set_volume"
            )
            
            if not is_valid:
                return self.create_command_result(success=False, error=error_msg)
                
            if zone_value is not None:
                zone_id = zone_value
        
        # Get zone as enum
        zone = self._get_zone(zone_id)
        
        # Check current volume state - if it's unknown, refresh it
        current_volume = None
        if zone == Zone.MAIN:
            current_volume = self.state.volume
            if current_volume is None:
                try:
                    # Use _refresh_device_state for main zone to efficiently get all properties
                    await self._refresh_device_state()
                    current_volume = self.state.volume
                    logger.debug(f"Refreshed device state before set volume: volume={current_volume}")
                except Exception as e:
                    logger.warning(f"Failed to refresh volume state: {str(e)}")
                    # Continue with volume setting even if we couldn't verify state
        elif zone == Zone.ZONE2:
            current_volume = getattr(self.state, "zone2_volume", None)
            if current_volume is None:
                try:
                    # For Zone2, use _synchronize_state which is optimized for Zone2
                    await self._synchronize_state(zone_id=2)
                    current_volume = getattr(self.state, "zone2_volume", None)
                    logger.debug(f"Synchronized Zone2 volume state: {current_volume}")
                except Exception as e:
                    logger.warning(f"Failed to synchronize Zone2 volume: {str(e)}")
                    # Continue with volume setting even if we couldn't verify state
                
        # If volume is already at the requested level, skip setting it
        if current_volume is not None and abs(current_volume - level) < 0.1:  # Small tolerance for float comparison
            logger.debug(f"Volume for zone {zone_id} already at {level} dB, skipping command")
            return self.create_command_result(
                success=True,
                message=f"Volume for zone {zone_id} already at {level} dB",
                volume=level,
                zone=zone_id
            )
        
        try:
            # Set volume for the specified zone
            if zone == Zone.MAIN:
                await self.client.set_volume(level, zone=zone)
                self.update_state(volume=level)
                logger.debug(f"Set main zone volume to {level} dB")
            elif zone == Zone.ZONE2:
                await self.client.set_volume(level, zone=zone)
                self.update_state(zone2_volume=level)
                logger.debug(f"Set zone 2 volume to {level} dB")
            else:
                logger.warning(f"Unsupported zone: {zone}")
                return self.create_command_result(
                    success=False,
                    error=f"Unsupported zone: {zone_id}"
                )
            
            # Clear any errors
            self.clear_error()
            
            # Update the last command information
            self._update_last_command("set_volume", {"level": level, "zone": zone_id})
            
            return self.create_command_result(
                success=True,
                message=f"Volume for zone {zone_id} set to {level} dB successfully",
                volume=level,
                zone=zone_id
            )
        except Exception as e:
            error_message = f"Failed to set volume: {str(e)}"
            logger.error(error_message)
            self.set_error(error_message)
            return self.create_command_result(
                success=False,
                error=error_message
            )
            
    async def handle_mute_toggle(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """Handle toggling mute state.
        
        Args:
            cmd_config: Command configuration
            params: Parameters including optional zone
            
        Returns:
            Command execution result
        """
        # DEBUG: Log command start with full context
        logger.debug(f"[EMOTIVA_DEBUG] mute_toggle command received: params={params}, connected={self.state.connected}, current_mute={self.state.mute} (device={self.get_name()})")
        
        # If client is not initialized or not connected, reconnect first
        if not self.client or not self.state.connected:
            # DEBUG: Log reconnection trigger
            logger.debug(f"[EMOTIVA_DEBUG] Triggering reconnection for mute_toggle: client={self.client is not None}, connected={self.state.connected} (device={self.get_name()})")
            logger.info(f"Device {self.get_name()} not connected, attempting reconnection before toggling mute")
            try:
                await self.setup()
            except Exception as e:
                logger.error(f"Failed to reconnect device {self.get_name()} before toggling mute: {str(e)}")
                return self.create_command_result(
                    success=False,
                    error=f"Failed to connect to device: {str(e)}"
                )
        
        # Get zone parameter if specified
        zone_id = 1  # Default to main zone
        
        if params and "zone" in params:
            zone_param = cmd_config.get_parameter("zone")
            is_valid, zone_value, error_msg = self._validate_parameter(
                param_name="zone",
                param_value=params.get("zone"),
                param_type=zone_param.type if zone_param else "integer",
                required=False,
                action="mute_toggle"
            )
            
            if not is_valid:
                return self.create_command_result(success=False, error=error_msg)
                
            if zone_value is not None:
                zone_id = zone_value
        
        # Get zone as enum
        zone = self._get_zone(zone_id)
        
        try:
            # Toggle mute for the specified zone
            if zone == Zone.MAIN:
                # Get current mute state if unknown
                if self.state.mute is None:
                    try:
                        # Use _refresh_device_state for more efficient state retrieval
                        updated_properties = await self._refresh_device_state()
                        logger.debug(f"Refreshed device state before mute toggle: mute={self.state.mute}")
                    except Exception as e:
                        logger.warning(f"Failed to refresh mute state: {str(e)}")
                        # Continue with toggle even if we couldn't verify state
                
                # Toggle mute
                await self.client.mute(zone=zone)
                
                # Update state with the new mute value (invert current state)
                new_mute = not self.state.mute if self.state.mute is not None else True
                self.update_state(mute=new_mute)
                logger.debug(f"Toggled main zone mute to {new_mute}")
            elif zone == Zone.ZONE2:
                # Get current mute state if unknown
                current_mute = getattr(self.state, "zone2_mute", None)
                if current_mute is None:
                    try:
                        # Zone2 properties need to be queried individually
                        zone2_updated = await self._synchronize_state(zone_id=2)
                        current_mute = getattr(self.state, "zone2_mute", None)
                        logger.debug(f"Synchronized Zone2 state before mute toggle: zone2_mute={current_mute}")
                    except Exception as e:
                        logger.warning(f"Failed to get current zone 2 mute state: {str(e)}")
                        # Continue with toggle even if we couldn't verify state
                
                # Toggle mute
                await self.client.mute(zone=zone)
                
                # Update state with the new mute value (invert current state)
                new_mute = not current_mute if current_mute is not None else True
                self.update_state(zone2_mute=new_mute)
                logger.debug(f"Toggled zone 2 mute to {new_mute}")
            else:
                logger.warning(f"Unsupported zone: {zone}")
                return self.create_command_result(
                    success=False,
                    error=f"Unsupported zone: {zone_id}"
                )
            
            # Clear any errors
            self.clear_error()
            
            # Update the last command information
            self._update_last_command("mute_toggle", {"zone": zone_id})
            
            return self.create_command_result(
                success=True,
                message=f"Mute for zone {zone_id} toggled successfully",
                mute=new_mute,
                zone=zone_id
            )
        except Exception as e:
            error_message = f"Failed to toggle mute: {str(e)}"
            logger.error(error_message)
            self.set_error(error_message)
            return self.create_command_result(
                success=False,
                error=error_message
            )
            
    async def handle_reconnect(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """Handle reconnection request.
        
        Args:
            cmd_config: Command configuration
            params: Parameters (unused)
            
        Returns:
            Command execution result
        """
        logger.info(f"Reconnection requested for device: {self.get_name()}")
        
        try:
            # Disconnect if currently connected
            if self.client and self.state.connected:
                logger.info(f"Disconnecting before reconnection for: {self.get_name()}")
                
                # Let the library handle disconnection
                await self.client.disconnect()
                
                # Update state to reflect disconnection
                self.update_state(
                    connected=False,
                    notifications=False
                )
                
                logger.info(f"Successfully disconnected {self.get_name()} for reconnection")
            
            # Re-initialize - setup creates a new client and connects
            success = await self.setup()
            
            if success:
                self.clear_error()
                logger.info(f"Reconnection successful for: {self.get_name()}")
                return self.create_command_result(
                    success=True, 
                    message=f"Successfully reconnected to {self.get_name()}"
                )
            else:
                error_msg = f"Reconnection failed for: {self.get_name()}"
                logger.error(error_msg)
                return self.create_command_result(success=False, error=error_msg)
        except Exception as e:
            error_msg = f"Error during reconnection: {str(e)}"
            logger.error(error_msg)
            self.set_error(error_msg)
            return self.create_command_result(success=False, error=error_msg)

    async def _synchronize_state(self, zone_id: int = 1) -> Dict[str, Any]:
        """Synchronize device state by querying current values.
        
        This method queries the device for current state values and updates the local state.
        It's useful when the state might be out of sync or when we need to ensure we have
        the latest values.
        
        Args:
            zone_id: Zone ID (1 for main, 2 for zone2)
            
        Returns:
            Dict[str, Any]: Dictionary of updated properties
        """
        if not self.client or not self.state.connected:
            logger.warning(f"Cannot synchronize state for {self.get_name()}: not connected")
            return {}
        
        zone = self._get_zone(zone_id)
        
        # For main zone, use _refresh_device_state to get all properties at once
        if zone == Zone.MAIN:
            try:
                logger.debug(f"Synchronizing all properties for main zone")
                updated_properties = await self._refresh_device_state()
                return updated_properties
            except Exception as e:
                logger.error(f"Error synchronizing main zone state: {str(e)}")
                return {}
                
        # For Zone2, we need to handle it differently since _refresh_device_state focuses on main zone
        else:
            updated_properties = {}
            try:
                # Query zone2 power state
                try:
                    power_result = await self.client.status(Property.ZONE2_POWER)
                    power_value = power_result.get(Property.ZONE2_POWER)
                    self.update_state(zone2_power=power_value)
                    updated_properties["zone2_power"] = power_value
                    logger.debug(f"Synchronized Zone2 power state: {power_value}")
                except Exception as e:
                    logger.warning(f"Failed to synchronize Zone2 power state: {str(e)}")
                
                # Only query other Zone2 properties if powered on
                if self.state.zone2_power == PowerState.ON:
                    # Query Zone2 volume
                    try:
                        volume_result = await self.client.status(Property.ZONE2_VOLUME)
                        volume = volume_result.get(Property.ZONE2_VOLUME)
                        self.update_state(zone2_volume=volume)
                        updated_properties["zone2_volume"] = volume
                        logger.debug(f"Synchronized Zone2 volume: {volume}")
                    except Exception as e:
                        logger.warning(f"Failed to synchronize Zone2 volume: {str(e)}")
                        
                    # Query Zone2 mute state
                    try:
                        mute_result = await self.client.status(Property.ZONE2_MUTE)
                        mute = mute_result.get(Property.ZONE2_MUTE)
                        self.update_state(zone2_mute=mute)
                        updated_properties["zone2_mute"] = mute
                        logger.debug(f"Synchronized Zone2 mute state: {mute}")
                    except Exception as e:
                        logger.warning(f"Failed to synchronize Zone2 mute state: {str(e)}")
                
                return updated_properties
            except Exception as e:
                logger.error(f"Error synchronizing Zone2 state: {str(e)}")
                return updated_properties

    async def handle_get_available_inputs(
        self, 
        cmd_config: StandardCommandConfig, 
        params: Dict[str, Any]
    ) -> CommandResult:
        """Handle retrieving available input sources for the Emotiva XMC2.
        
        Returns a list of all available input sources as pairs of input_id and input_name.
        The Emotiva XMC2 has a fixed set of inputs defined by the hardware specification.
        
        Args:
            cmd_config: Command configuration
            params: Dictionary containing optional parameters (unused)
            
        Returns:
            CommandResult: Result of the command execution with a list of available inputs
        """
        try:
            logger.info("Retrieving available input sources for Emotiva XMC2")
            
            # Create mapping from Input enum values to human-readable names
            input_name_mapping = {
                Input.HDMI1: "HDMI 1",
                Input.HDMI2: "HDMI 2", 
                Input.HDMI3: "HDMI 3",
                Input.HDMI4: "HDMI 4",
                Input.HDMI5: "HDMI 5",
                Input.HDMI6: "HDMI 6",
                Input.HDMI7: "HDMI 7",
                Input.HDMI8: "HDMI 8",
                Input.COAX1: "Coaxial 1",
                Input.COAX2: "Coaxial 2", 
                Input.COAX3: "Coaxial 3",
                Input.COAX4: "Coaxial 4",
                Input.OPTICAL1: "Optical 1",
                Input.OPTICAL2: "Optical 2",
                Input.OPTICAL3: "Optical 3", 
                Input.OPTICAL4: "Optical 4",
                Input.TUNER: "FM/AM Tuner"
            }
            
            # Format the input sources as pairs of input_id and input_name
            formatted_inputs = []
            
            for input_enum, human_name in input_name_mapping.items():
                formatted_inputs.append({
                    "input_id": input_enum.value,  # e.g., "hdmi1", "coax1", "optical1", "tuner"
                    "input_name": human_name       # e.g., "HDMI 1", "Coaxial 1", "FM/AM Tuner"
                })
            
            logger.info(f"Found {len(formatted_inputs)} available input sources")
            
            # Update the last command information
            self._update_last_command("get_available_inputs", {})
            
            return self.create_command_result(
                success=True,
                message=f"Retrieved {len(formatted_inputs)} input sources",
                data=formatted_inputs
            )
            
        except Exception as e:
            error_msg = f"Error retrieving input sources: {str(e)}"
            logger.error(error_msg)
            return self.create_command_result(success=False, error=error_msg)

