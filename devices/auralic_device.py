import logging
import asyncio
from typing import Dict, Any, List, Optional, cast
from datetime import datetime

from openhomedevice.device import Device as OpenHomeDevice

from devices.base_device import BaseDevice
from app.schemas import AuralicDeviceState, LastCommand, AuralicDeviceConfig, BaseCommandConfig
from app.mqtt_client import MQTTClient
from app.types import CommandResult, CommandResponse

logger = logging.getLogger(__name__)

class AuralicDevice(BaseDevice[AuralicDeviceState]):
    """Implementation of an Auralic device controlled through OpenHome UPnP."""
    
    def __init__(self, config: AuralicDeviceConfig, mqtt_client: Optional[MQTTClient] = None) -> None:
        # Initialize state with typed Pydantic model before super().__init__
        self.state = AuralicDeviceState(
            device_id=config.device_id,
            device_name=config.device_name,
            ip_address=config.auralic.ip_address
        )
        
        # Call the base class constructor - this will call _register_handlers() 
        # and _auto_register_handlers() automatically
        super().__init__(config, mqtt_client)
        
        # Store configuration and initialize instance variables
        self.config = cast(AuralicDeviceConfig, config)
        self.ip_address = self.config.auralic.ip_address
        self.update_interval = self.config.auralic.update_interval
        self.discovery_mode = self.config.auralic.discovery_mode
        self.device_url = self.config.auralic.device_url
        self.openhome_device = None
        self._update_task = None
    
    async def setup(self) -> bool:
        """Initialize the device."""
        try:
            # Initialize openhomedevice
            self.openhome_device = await self._create_openhome_device()
            if not self.openhome_device:
                logger.error(f"Failed to connect to Auralic device at {self.ip_address}")
                self.update_state(error=f"Failed to connect to device at {self.ip_address}", connected=False)
                return False

            # Start periodic state updates
            self._update_task = asyncio.create_task(self._update_state_periodically())
            
            # Update initial state
            await self._update_device_state()
            
            logger.info(f"Auralic device {self.get_name()} initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Auralic device {self.get_name()}: {str(e)}")
            self.update_state(error=str(e), connected=False)
            return False
    
    async def shutdown(self) -> bool:
        """Cleanup device resources."""
        try:
            if self._update_task:
                self._update_task.cancel()
                try:
                    await self._update_task
                except asyncio.CancelledError:
                    pass
            
            logger.info(f"Auralic device {self.get_name()} shutdown complete")
            self.update_state(connected=False)
            return True
        except Exception as e:
            logger.error(f"Error during device shutdown: {str(e)}")
            return False
    
    async def _create_openhome_device(self) -> Optional[OpenHomeDevice]:
        """Create and initialize openhomedevice connection."""
        try:
            if self.discovery_mode:
                # Use discovery to find the device by name
                logger.info(f"Using discovery mode to find Auralic device '{self.device_name}'")
                devices = await OpenHomeDevice.all()
                for device in devices:
                    device_name = await device.name()
                    logger.debug(f"Found OpenHome device: {device_name}")
                    if self.device_name.lower() in device_name.lower():
                        logger.info(f"Found matching Auralic device: {device_name}")
                        return device
                logger.error(f"No matching Auralic device found with name '{self.device_name}'")
                return None
            else:
                # Connect directly using IP address
                if self.device_url:
                    logger.info(f"Connecting to Auralic device using custom URL: {self.device_url}")
                    device_url = self.device_url
                else:
                    logger.info(f"Connecting to Auralic device at IP: {self.ip_address}")
                    device_url = f"http://{self.ip_address}:8080/DeviceDescription.xml"
                    
                device = OpenHomeDevice(device_url)
                await device.init()
                return device
                
        except Exception as e:
            logger.error(f"Error connecting to Auralic device: {str(e)}")
            return None
    
    async def _update_state_periodically(self) -> None:
        """Periodically update device state in background."""
        while True:
            try:
                await self._update_device_state()
                await asyncio.sleep(self.update_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error updating device state: {str(e)}")
                await asyncio.sleep(self.update_interval)
    
    async def _update_device_state(self) -> None:
        """Update current device state."""
        if not self.openhome_device:
            self.update_state(connected=False)
            return
        
        try:
            # Get transport state (playing, paused, etc)
            transport_state = await self.openhome_device.transport_state()
            
            # Get standby state
            in_standby = await self.openhome_device.is_in_standby()
            power_state = "off" if in_standby else "on"
            
            # Get current track info
            track_info = await self.openhome_device.track_info()
            
            # Get volume and mute status
            volume = await self.openhome_device.volume()
            mute = await self.openhome_device.is_muted()
            
            # Get current source
            sources = await self.openhome_device.sources()
            source_index = await self.openhome_device.source_index()
            current_source = sources[source_index]["name"] if 0 <= source_index < len(sources) else None
            
            # Update state
            self.update_state(
                connected=True,
                power=power_state,
                volume=volume,
                mute=mute,
                source=current_source,
                transport_state=transport_state,
                track_title=track_info.get("title"),
                track_artist=track_info.get("artist"),
                track_album=track_info.get("album")
            )
            
        except Exception as e:
            logger.error(f"Error updating device state: {str(e)}")
            self.update_state(connected=False, error=str(e))

    # Handler methods that will be automatically registered by _auto_register_handlers()
    
    async def handle_power_on(self, command_config: BaseCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """Handle power on command."""
        try:
            if not self.openhome_device:
                return self.create_command_result(
                    success=False,
                    error="Device not connected"
                )
                
            # Check if already on
            if not await self.openhome_device.is_in_standby():
                return self.create_command_result(
                    success=True,
                    message="Device already powered on"
                )
            
            # Power on
            await self.openhome_device.set_standby(False)
            
            # Update state
            await self._update_device_state()
            
            return self.create_command_result(
                success=True,
                message="Device powered on"
            )
        except Exception as e:
            logger.error(f"Error executing power on: {str(e)}")
            return self.create_command_result(
                success=False,
                error=f"Failed to power on: {str(e)}"
            )

    async def handle_power_off(self, command_config: BaseCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """Handle power off command."""
        try:
            if not self.openhome_device:
                return self.create_command_result(
                    success=False,
                    error="Device not connected"
                )
                
            # Check if already off
            if await self.openhome_device.is_in_standby():
                return self.create_command_result(
                    success=True,
                    message="Device already powered off"
                )
            
            # Power off
            await self.openhome_device.set_standby(True)
            
            # Update state
            await self._update_device_state()
            
            return self.create_command_result(
                success=True,
                message="Device powered off"
            )
        except Exception as e:
            logger.error(f"Error executing power off: {str(e)}")
            return self.create_command_result(
                success=False,
                error=f"Failed to power off: {str(e)}"
            )

    async def handle_power_toggle(self, command_config: BaseCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """Handle power toggle command."""
        try:
            if not self.openhome_device:
                return self.create_command_result(
                    success=False,
                    error="Device not connected"
                )
                
            # Get current state
            in_standby = await self.openhome_device.is_in_standby()
            
            # Toggle standby state
            await self.openhome_device.set_standby(not in_standby)
            
            # Update state
            await self._update_device_state()
            
            return self.create_command_result(
                success=True,
                message=f"Device powered {'on' if in_standby else 'off'}"
            )
        except Exception as e:
            logger.error(f"Error executing power toggle: {str(e)}")
            return self.create_command_result(
                success=False,
                error=f"Failed to toggle power: {str(e)}"
            )

    async def handle_play(self, command_config: BaseCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """Handle play command."""
        try:
            if not self.openhome_device:
                return self.create_command_result(
                    success=False,
                    error="Device not connected"
                )
                
            await self.openhome_device.play()
            await self._update_device_state()
            
            return self.create_command_result(
                success=True,
                message="Playback started"
            )
        except Exception as e:
            logger.error(f"Error executing play: {str(e)}")
            return self.create_command_result(
                success=False,
                error=f"Failed to start playback: {str(e)}"
            )

    async def handle_pause(self, command_config: BaseCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """Handle pause command."""
        try:
            if not self.openhome_device:
                return self.create_command_result(
                    success=False,
                    error="Device not connected"
                )
                
            await self.openhome_device.pause()
            await self._update_device_state()
            
            return self.create_command_result(
                success=True,
                message="Playback paused"
            )
        except Exception as e:
            logger.error(f"Error executing pause: {str(e)}")
            return self.create_command_result(
                success=False,
                error=f"Failed to pause playback: {str(e)}"
            )

    async def handle_stop(self, command_config: BaseCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """Handle stop command."""
        try:
            if not self.openhome_device:
                return self.create_command_result(
                    success=False,
                    error="Device not connected"
                )
                
            await self.openhome_device.stop()
            await self._update_device_state()
            
            return self.create_command_result(
                success=True,
                message="Playback stopped"
            )
        except Exception as e:
            logger.error(f"Error executing stop: {str(e)}")
            return self.create_command_result(
                success=False,
                error=f"Failed to stop playback: {str(e)}"
            )

    async def handle_next(self, command_config: BaseCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """Handle next track command."""
        try:
            if not self.openhome_device:
                return self.create_command_result(
                    success=False,
                    error="Device not connected"
                )
                
            await self.openhome_device.next()
            await self._update_device_state()
            
            return self.create_command_result(
                success=True,
                message="Skipped to next track"
            )
        except Exception as e:
            logger.error(f"Error executing next: {str(e)}")
            return self.create_command_result(
                success=False,
                error=f"Failed to skip to next track: {str(e)}"
            )

    async def handle_previous(self, command_config: BaseCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """Handle previous track command."""
        try:
            if not self.openhome_device:
                return self.create_command_result(
                    success=False,
                    error="Device not connected"
                )
                
            await self.openhome_device.previous()
            await self._update_device_state()
            
            return self.create_command_result(
                success=True,
                message="Skipped to previous track"
            )
        except Exception as e:
            logger.error(f"Error executing previous: {str(e)}")
            return self.create_command_result(
                success=False,
                error=f"Failed to skip to previous track: {str(e)}"
            )

    async def handle_set_volume(self, command_config: BaseCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """Handle set volume command."""
        try:
            if not self.openhome_device:
                return self.create_command_result(
                    success=False,
                    error="Device not connected"
                )
                
            volume = params.get("volume")
            if volume is None:
                return self.create_command_result(
                    success=False,
                    error="Volume parameter is required"
                )
            
            # Ensure volume is within range (0-100)
            volume = max(0, min(100, int(volume)))
            
            # Set volume
            await self.openhome_device.set_volume(volume)
            
            # Update state
            await self._update_device_state()
            
            return self.create_command_result(
                success=True,
                message=f"Volume set to {volume}"
            )
        except Exception as e:
            logger.error(f"Error setting volume: {str(e)}")
            return self.create_command_result(
                success=False,
                error=f"Failed to set volume: {str(e)}"
            )

    async def handle_volume_up(self, command_config: BaseCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """Handle volume up command."""
        try:
            if not self.openhome_device:
                return self.create_command_result(
                    success=False,
                    error="Device not connected"
                )
                
            await self.openhome_device.increase_volume()
            await self._update_device_state()
            
            return self.create_command_result(
                success=True,
                message="Volume increased"
            )
        except Exception as e:
            logger.error(f"Error increasing volume: {str(e)}")
            return self.create_command_result(
                success=False,
                error=f"Failed to increase volume: {str(e)}"
            )

    async def handle_volume_down(self, command_config: BaseCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """Handle volume down command."""
        try:
            if not self.openhome_device:
                return self.create_command_result(
                    success=False,
                    error="Device not connected"
                )
                
            await self.openhome_device.decrease_volume()
            await self._update_device_state()
            
            return self.create_command_result(
                success=True,
                message="Volume decreased"
            )
        except Exception as e:
            logger.error(f"Error decreasing volume: {str(e)}")
            return self.create_command_result(
                success=False,
                error=f"Failed to decrease volume: {str(e)}"
            )

    async def handle_mute(self, command_config: BaseCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """Handle mute toggle command."""
        try:
            if not self.openhome_device:
                return self.create_command_result(
                    success=False,
                    error="Device not connected"
                )
                
            # Get current mute state
            is_muted = await self.openhome_device.is_muted()
            
            # Toggle mute state
            await self.openhome_device.set_mute(not is_muted)
            
            # Update state
            await self._update_device_state()
            
            return self.create_command_result(
                success=True,
                message=f"Device {'unmuted' if is_muted else 'muted'}"
            )
        except Exception as e:
            logger.error(f"Error toggling mute: {str(e)}")
            return self.create_command_result(
                success=False,
                error=f"Failed to toggle mute: {str(e)}"
            )

    async def handle_set_source(self, command_config: BaseCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """Handle set source command."""
        try:
            if not self.openhome_device:
                return self.create_command_result(
                    success=False,
                    error="Device not connected"
                )
                
            source = params.get("source")
            if source is None:
                return self.create_command_result(
                    success=False,
                    error="Source parameter is required"
                )
            
            # Get list of sources
            sources = await self.openhome_device.sources()
            
            # If source is numeric, use as index
            if isinstance(source, (int, str)) and str(source).isdigit():
                source_index = int(source)
                if 0 <= source_index < len(sources):
                    await self.openhome_device.set_source(source_index)
                    source_name = sources[source_index]["name"]
                else:
                    return self.create_command_result(
                        success=False,
                        error=f"Invalid source index: {source_index}"
                    )
            # Otherwise find source by name
            else:
                source_name = str(source)
                source_index = None
                for i, s in enumerate(sources):
                    if source_name.lower() == s["name"].lower():
                        source_index = i
                        break
                
                if source_index is not None:
                    await self.openhome_device.set_source(source_index)
                else:
                    return self.create_command_result(
                        success=False,
                        error=f"Source not found: {source_name}"
                    )
            
            # Update state
            await self._update_device_state()
            
            return self.create_command_result(
                success=True,
                message=f"Source set to {source_name}"
            )
        except Exception as e:
            logger.error(f"Error setting source: {str(e)}")
            return self.create_command_result(
                success=False,
                error=f"Failed to set source: {str(e)}"
            )

    async def handle_track_info(self, command_config: BaseCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """Handle track info command."""
        try:
            if not self.openhome_device:
                return self.create_command_result(
                    success=False,
                    error="Device not connected"
                )
                
            # Get current track info
            track_info = await self.openhome_device.track_info()
            
            # Update state
            await self._update_device_state()
            
            return self.create_command_result(
                success=True,
                message="Track information retrieved",
                track_info=track_info
            )
        except Exception as e:
            logger.error(f"Error getting track info: {str(e)}")
            return self.create_command_result(
                success=False,
                error=f"Failed to get track info: {str(e)}"
            ) 