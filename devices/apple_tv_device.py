import asyncio
import json
import logging
import os
from typing import Dict, List, Any, Optional

import pyatv
from pyatv import scan, connect
from pyatv.const import Protocol as ProtocolType
from pyatv.interface import DeviceListener

from devices.base_device import BaseDevice
from app.schemas import AppleTVConfig, AppleTVState
from app.mqtt_client import MQTTClient

class AppleTVDevice(BaseDevice):
    """Apple TV device integration for wb-mqtt-bridge.
    
    This device class enables control of Apple TV devices via MQTT.
    It supports power status, media playback control, and device information.
    """
    
    def __init__(self, config: Dict[str, Any], mqtt_client: Optional[MQTTClient] = None):
        """Initialize the Apple TV device.
        
        Args:
            config: Device configuration
            mqtt_client: MQTT client instance
        """
        super().__init__(config, mqtt_client)
        
        # Apple TV specific configuration
        if not isinstance(config, dict) or "apple_tv" not in config:
            self.log.error("No Apple TV configuration section found")
            raise ValueError("No Apple TV configuration section found")
            
        self.apple_tv_config = AppleTVConfig(**config["apple_tv"])
        
        self.loop = None
        self.device = None
        self.config = None  # pyatv config
        
        # Set up MQTT topics
        self.topics = {
            "state": f"{self.base_topic}/state",
            "command": f"{self.base_topic}/command",
            "power": f"{self.base_topic}/power",
            "playback": f"{self.base_topic}/playback",
            "app": f"{self.base_topic}/app",
            "volume": f"{self.base_topic}/volume"
        }
        
        # Initialize device state
        self.state = {
            "connected": False,
            "power": "unknown",
            "app": None,
            "playback_state": None,
            "media_type": None,
            "title": None,
            "artist": None,
            "album": None,
            "position": None,
            "total_time": None,
            "volume": None,
            "error": None,
            "ip_address": self.apple_tv_config.ip_address
        }
        
        # Define available commands
        self.commands = {
            "connect": self.connect_to_device,
            "disconnect": self.disconnect_from_device,
            "turn_on": self.turn_on,
            "turn_off": self.turn_off,
            "play": self.play,
            "pause": self.pause,
            "stop": self.stop,
            "next": self.next_track,
            "previous": self.previous_track,
            "set_volume": self.set_volume,
            "volume_up": self.volume_up,
            "volume_down": self.volume_down,
            "launch_app": self.launch_app,
            "refresh_status": self.refresh_status
        }
        
        # Action groups
        self.action_groups = {
            "power": ["connect", "disconnect", "turn_on", "turn_off"],
            "playback": ["play", "pause", "stop", "next", "previous"],
            "volume": ["set_volume", "volume_up", "volume_down"],
            "apps": ["launch_app"],
            "system": ["refresh_status"]
        }
    
    async def setup(self) -> bool:
        """Set up the Apple TV device."""
        self.loop = asyncio.get_event_loop()
        
        try:
            # Extract IP address from config
            ip_address = self.apple_tv_config.ip_address
            self.log.info(f"Scanning for Apple TV at {ip_address}")
            
            # Scan for the device first to get its current configuration
            atvs = await scan(hosts=[ip_address], loop=self.loop)
            
            if not atvs:
                self.log.error(f"No Apple TV found at {ip_address}")
                self.state["error"] = f"No Apple TV found at {ip_address}"
                return False
            
            self.config = atvs[0]
            self.log.info(f"Found Apple TV: {self.config.name}")
            
            # Check if scanned name matches configured name (if provided)
            if self.apple_tv_config.name and self.config.name != self.apple_tv_config.name:
                self.log.warning(f"Found Apple TV name '{self.config.name}' doesn't match configured name '{self.apple_tv_config.name}'")
            
            # Load credentials from configuration
            if self.apple_tv_config.protocols:
                for protocol_name, protocol_config in self.apple_tv_config.protocols.items():
                    try:
                        protocol = ProtocolType[protocol_name]
                        self.config.set_credentials(
                            protocol,
                            protocol_config.credentials
                        )
                        self.log.info(f"Loaded credentials for {protocol_name}")
                    except (KeyError, ValueError) as e:
                        self.log.error(f"Error loading credentials for {protocol_name}: {e}")
            
            # Try to connect
            await self.connect_to_device()
            return True
            
        except Exception as e:
            self.log.error(f"Error setting up Apple TV device: {e}")
            self.state["error"] = str(e)
            return False
    
    async def shutdown(self) -> bool:
        """Shut down the Apple TV device."""
        try:
            if self.device:
                await self.disconnect_from_device()
            return True
        except Exception as e:
            self.log.error(f"Error shutting down Apple TV device: {e}")
            return False
    
    def subscribe_topics(self) -> List[str]:
        """Return the MQTT topics to subscribe to."""
        return [self.topics["command"]]
    
    async def handle_message(self, topic: str, payload: str):
        """Handle incoming MQTT messages."""
        try:
            if topic == self.topics["command"]:
                message = json.loads(payload)
                command = message.get("command")
                params = message.get("params", {})
                
                if command in self.commands:
                    self.log.info(f"Executing command: {command} with params: {params}")
                    await self.commands[command](**params)
                else:
                    self.log.warning(f"Unknown command: {command}")
        except json.JSONDecodeError:
            self.log.error(f"Invalid JSON in message: {payload}")
        except Exception as e:
            self.log.error(f"Error handling message: {e}")
    
    async def publish_state(self):
        """Publish the current device state to MQTT."""
        await self.mqtt_client.publish(self.topics["state"], json.dumps(self.state))
        
        # Also publish individual state components to dedicated topics
        if self.state.get("power"):
            await self.mqtt_client.publish(self.topics["power"], self.state["power"])
        
        if self.state.get("playback_state"):
            playback_state = {
                "state": self.state["playback_state"],
                "title": self.state.get("title"),
                "artist": self.state.get("artist"),
                "album": self.state.get("album"),
                "position": self.state.get("position"),
                "total_time": self.state.get("total_time")
            }
            await self.mqtt_client.publish(self.topics["playback"], json.dumps(playback_state))
        
        if self.state.get("app"):
            await self.mqtt_client.publish(self.topics["app"], self.state["app"])
        
        if self.state.get("volume") is not None:
            await self.mqtt_client.publish(self.topics["volume"], str(self.state["volume"]))
    
    async def connect_to_device(self):
        """Connect to the Apple TV device."""
        if self.device:
            self.log.info("Already connected to Apple TV, disconnecting first")
            await self.disconnect_from_device()
        
        try:
            self.log.info(f"Connecting to Apple TV at {self.apple_tv_config.ip_address}")
            self.device = await connect(self.config, loop=self.loop)
            self.state["connected"] = True
            self.log.info(f"Connected to {self.device.device_info.name}")
            
            # Start listening for updates
            self.device.listener = PyATVDeviceListener(self)
            
            # Refresh status immediately
            await self.refresh_status()
            
        except Exception as e:
            self.log.error(f"Failed to connect to Apple TV: {e}")
            self.state["connected"] = False
            self.state["error"] = str(e)
            self.device = None
        
        # Publish updated state
        await self.publish_state()
    
    async def disconnect_from_device(self):
        """Disconnect from the Apple TV device."""
        if self.device:
            try:
                # Simply call close and catch exceptions
                # Don't try to await the result as it might not be awaitable
                self.device.close()
                self.log.info("Disconnected from Apple TV")
            except Exception as e:
                self.log.error(f"Error disconnecting from Apple TV: {e}")
            finally:
                self.device = None
                self.state["connected"] = False
                await self.publish_state()
    
    async def refresh_status(self):
        """Refresh the device status."""
        if not self.device:
            self.log.warning("Cannot refresh status: not connected to Apple TV")
            return
        
        try:
            # Update power state based on connection status
            self.state["power"] = "on" if self.state["connected"] else "off"
            
            # Get current app
            app = await self.device.apps.current_app()
            if app:
                self.state["app"] = app.name
            
            # Get playback state
            playing = await self.device.metadata.playing()
            if playing:
                self.state["playback_state"] = playing.device_state.name.lower()
                self.state["media_type"] = playing.media_type.name.lower() if playing.media_type else None
                self.state["title"] = playing.title
                self.state["artist"] = playing.artist
                self.state["album"] = playing.album
                self.state["position"] = playing.position
                self.state["total_time"] = playing.total_time
            
            # Get volume if available
            if hasattr(self.device, "audio"):
                try:
                    # In newer pyatv versions, volume is a property
                    volume = self.device.audio.volume
                    if volume is not None:
                        self.state["volume"] = int(volume * 100)
                except Exception as e:
                    self.log.warning(f"Could not get volume: {e}")
            
            self.log.info(f"Status refreshed for {self.config.name}")
            await self.publish_state()
            
        except Exception as e:
            self.log.error(f"Error refreshing Apple TV status: {e}")
            self.state["error"] = str(e)
            await self.publish_state()
    
    async def turn_on(self):
        """Turn on the Apple TV."""
        if not self.device:
            await self.connect_to_device()
            return
        
        try:
            # Apple TV doesn't have a direct power on command, 
            # but we can send a key press to wake it
            await self.device.remote_control.menu()
            self.state["power"] = "on"
            await self.publish_state()
        except Exception as e:
            self.log.error(f"Error turning on Apple TV: {e}")
            self.state["error"] = str(e)
            await self.publish_state()
    
    async def turn_off(self):
        """Turn off the Apple TV."""
        if not self.device:
            self.log.warning("Cannot turn off: not connected to Apple TV")
            return
        
        try:
            # Use press of home button to sleep
            await self.device.remote_control.home()
            self.state["power"] = "off"
            await self.publish_state()
        except Exception as e:
            self.log.error(f"Error turning off Apple TV: {e}")
            self.state["error"] = str(e)
            await self.publish_state()
    
    async def play(self):
        """Play media on the Apple TV."""
        if not self.device:
            self.log.warning("Cannot play: not connected to Apple TV")
            return
        
        try:
            await self.device.remote_control.play()
            await self.refresh_status()
        except Exception as e:
            self.log.error(f"Error playing media: {e}")
            self.state["error"] = str(e)
            await self.publish_state()
    
    async def pause(self):
        """Pause media playback on the Apple TV."""
        if not self.device:
            self.log.warning("Cannot pause: not connected to Apple TV")
            return
        
        try:
            await self.device.remote_control.pause()
            await self.refresh_status()
        except Exception as e:
            self.log.error(f"Error pausing media: {e}")
            self.state["error"] = str(e)
            await self.publish_state()
    
    async def stop(self):
        """Stop media playback on the Apple TV."""
        if not self.device:
            self.log.warning("Cannot stop: not connected to Apple TV")
            return
        
        try:
            await self.device.remote_control.stop()
            await self.refresh_status()
        except Exception as e:
            self.log.error(f"Error stopping media: {e}")
            self.state["error"] = str(e)
            await self.publish_state()
    
    async def next_track(self):
        """Skip to the next track on the Apple TV."""
        if not self.device:
            self.log.warning("Cannot skip to next: not connected to Apple TV")
            return
        
        try:
            await self.device.remote_control.next()
            await self.refresh_status()
        except Exception as e:
            self.log.error(f"Error skipping to next track: {e}")
            self.state["error"] = str(e)
            await self.publish_state()
    
    async def previous_track(self):
        """Skip to the previous track on the Apple TV."""
        if not self.device:
            self.log.warning("Cannot skip to previous: not connected to Apple TV")
            return
        
        try:
            await self.device.remote_control.previous()
            await self.refresh_status()
        except Exception as e:
            self.log.error(f"Error skipping to previous track: {e}")
            self.state["error"] = str(e)
            await self.publish_state()
    
    async def set_volume(self, level: int):
        """Set the volume level on the Apple TV.
        
        Args:
            level: Volume level (0-100)
        """
        if not self.device:
            self.log.warning("Cannot set volume: not connected to Apple TV")
            return
        
        try:
            # Ensure volume is within range
            level = max(0, min(100, level))
            
            # Apple TV uses 0.0-1.0 for volume
            normalized_level = level / 100.0
            
            await self.device.audio.set_volume(normalized_level)
            self.state["volume"] = level
            await self.publish_state()
        except Exception as e:
            self.log.error(f"Error setting volume: {e}")
            self.state["error"] = str(e)
            await self.publish_state()
    
    async def volume_up(self):
        """Increase the volume on the Apple TV."""
        if not self.device:
            self.log.warning("Cannot increase volume: not connected to Apple TV")
            return
        
        try:
            await self.device.remote_control.volume_up()
            # Update volume after a brief delay to allow the device to respond
            await asyncio.sleep(0.5)
            if hasattr(self.device, "audio"):
                try:
                    # In newer pyatv versions, volume is a property
                    volume = self.device.audio.volume
                    if volume is not None:
                        self.state["volume"] = int(volume * 100)
                except Exception as e:
                    self.log.warning(f"Could not get volume after increase: {e}")
            await self.publish_state()
        except Exception as e:
            self.log.error(f"Error increasing volume: {e}")
            self.state["error"] = str(e)
            await self.publish_state()
    
    async def volume_down(self):
        """Decrease the volume on the Apple TV."""
        if not self.device:
            self.log.warning("Cannot decrease volume: not connected to Apple TV")
            return
        
        try:
            await self.device.remote_control.volume_down()
            # Update volume after a brief delay to allow the device to respond
            await asyncio.sleep(0.5)
            if hasattr(self.device, "audio"):
                try:
                    # In newer pyatv versions, volume is a property
                    volume = self.device.audio.volume
                    if volume is not None:
                        self.state["volume"] = int(volume * 100)
                except Exception as e:
                    self.log.warning(f"Could not get volume after decrease: {e}")
            await self.publish_state()
        except Exception as e:
            self.log.error(f"Error decreasing volume: {e}")
            self.state["error"] = str(e)
            await self.publish_state()
    
    async def launch_app(self, app_id: str):
        """Launch an app on the Apple TV.
        
        Args:
            app_id: App identifier to launch
        """
        if not self.device:
            self.log.warning("Cannot launch app: not connected to Apple TV")
            return
        
        try:
            await self.device.apps.launch_app(app_id)
            await self.refresh_status()
        except Exception as e:
            self.log.error(f"Error launching app {app_id}: {e}")
            self.state["error"] = str(e)
            await self.publish_state()


class PyATVDeviceListener(DeviceListener):
    """Listener for Apple TV device updates."""
    
    def __init__(self, device: AppleTVDevice):
        """Initialize the device listener.
        
        Args:
            device: AppleTVDevice instance
        """
        self.device = device
    
    def connection_lost(self, exception):
        """Called when connection is lost to the Apple TV."""
        self.device.log.warning(f"Connection lost to Apple TV: {exception}")
        self.device.state["connected"] = False
        self.device.state["power"] = "off"
        self.device.state["error"] = str(exception) if exception else "Connection lost"
        
        # Run asynchronous task in a non-async method
        asyncio.run_coroutine_threadsafe(
            self.device.publish_state(),
            asyncio.get_event_loop()
        )
    
    def connection_closed(self):
        """Called when connection was closed properly."""
        self.device.log.info("Connection closed to Apple TV")
        self.device.state["connected"] = False
        self.device.state["power"] = "off"
        
        # Run asynchronous task in a non-async method
        asyncio.run_coroutine_threadsafe(
            self.device.publish_state(),
            asyncio.get_event_loop()
        )
    
    def update_available(self, update):
        """Called when new metadata is available."""
        self.device.log.debug(f"Received update: {update}")
        
        # Run asynchronous task in a non-async method
        asyncio.run_coroutine_threadsafe(
            self.device.refresh_status(),
            asyncio.get_event_loop()
        ) 