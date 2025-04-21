import json
import logging
import asyncio
import os
from typing import Dict, Any, List, Optional
from asyncwebostv.connection import WebOSClient
from asyncwebostv.controls import (
    MediaControl,
    SystemControl,
    ApplicationControl,
    TvControl,
    InputControl,
    SourceControl
)
from devices.base_device import BaseDevice
from app.schemas import LgTvState, LgTvConfig, LastCommand
from app.mqtt_client import MQTTClient
from datetime import datetime

logger = logging.getLogger(__name__)

class LgTv(BaseDevice):
    """Implementation of an LG TV controlled over the network using AsyncWebOSTV library."""
    
    def __init__(self, config: Dict[str, Any], mqtt_client: Optional[MQTTClient] = None):
        super().__init__(config, mqtt_client)
        self._state_schema = LgTvState
        self.state = {
            "power": "unknown",
            "volume": 0,
            "mute": False,
            "current_app": None,
            "input_source": None,
            "last_command": None,
            "connected": False,
            "ip_address": None,
            "mac_address": None
        }
        self.client = None
        self.system = None
        self.media = None
        self.app = None
        self.tv_control = None
        self.input_control = None
        self.source_control = None
    
    async def setup(self) -> bool:
        """Initialize the TV device."""
        try:
            # Get TV-specific configuration
            tv_dict = self.config.get("tv", {})
            if not tv_dict:
                logger.error(f"Missing 'tv' configuration for {self.get_name()}")
                self.state["error"] = "Missing TV configuration"
                return False
                
            # Validate TV configuration with pydantic model
            try:
                tv_config = LgTvConfig(**tv_dict)
            except Exception as e:
                logger.error(f"Invalid TV configuration for device: {self.get_name()}: {str(e)}")
                self.state["error"] = f"Invalid TV configuration: {str(e)}"
                return False
                
            # Update state with configuration values
            self.state["ip_address"] = tv_config.ip_address
            self.state["mac_address"] = tv_config.mac_address
            
            # Store client key for WebOS authentication
            self.client_key = tv_config.client_key
            
            # Initialize TV connection
            if await self._connect_to_tv():
                logger.info(f"Successfully connected to TV {self.get_name()}")
                self.state["connected"] = True
            else:
                logger.error(f"Failed to connect to TV {self.get_name()}")
                self.state["connected"] = False
                self.state["error"] = "Failed to connect to TV"
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize TV {self.get_name()}: {str(e)}")
            self.state["error"] = str(e)
            return False
    
    async def shutdown(self) -> bool:
        """Cleanup device resources."""
        try:
            if self.tv and self.tv.connection:
                await self.tv.close()
            
            logger.info(f"LG TV {self.get_name()} shutdown complete")
            return True
        except Exception as e:
            logger.error(f"Error during device shutdown: {str(e)}")
            return False
    
    def subscribe_topics(self) -> List[str]:
        """Define the MQTT topics this device should subscribe to."""
        topics = []
        
        # Add command topics from configuration
        for command in self.get_available_commands().values():
            topic = command.get("topic")
            if topic:
                topics.append(topic)
        
        # Add any additional control topics
        power_topic = self.config.get("power_topic")
        if power_topic:
            topics.append(power_topic)
            
        volume_topic = self.config.get("volume_topic")
        if volume_topic:
            topics.append(volume_topic)
            
        app_launch_topic = self.config.get("app_launch_topic")
        if app_launch_topic:
            topics.append(app_launch_topic)
            
        input_source_topic = self.config.get("input_source_topic")
        if input_source_topic:
            topics.append(input_source_topic)
        
        logger.debug(f"Device {self.get_name()} subscribing to topics: {topics}")
        return topics
    
    async def _connect_to_tv(self) -> bool:
        """Connect to the TV."""
        try:
            ip = self.state.get("ip_address")
            if not ip:
                logger.error("No IP address configured for TV")
                return False
                
            # Get TV-specific configuration
            tv_dict = self.config.get("tv", {})
            tv_config = LgTvConfig(**tv_dict)
            
            # Use secure WebSocket mode by default, can be disabled in config
            secure_mode = tv_config.secure
            
            # Create a new TV client
            self.tv = WebOSClient(ip, secure=secure_mode)
            
            # Connect to the TV
            await self.tv.connect()
            
            # Register with the TV if needed
            if not self.tv.client_key:
                logger.info("No client key found, registering with TV...")
                store = {}
                registered = False
                
                try:
                    async for status in self.tv.register(store):
                        if status == WebOSClient.PROMPTED:
                            logger.info("Please accept the connection on the TV!")
                        elif status == WebOSClient.REGISTERED:
                            registered = True
                            logger.info("TV registration successful!")
                            
                            # Save the client key for future use
                            if store.get("client_key"):
                                self.client_key = store["client_key"]
                                logger.info("Client key obtained and stored")
                            
                            break
                except Exception as e:
                    logger.error(f"Error during TV registration: {str(e)}")
                    return False
                
                if not registered:
                    logger.error("Failed to register with the TV")
                    return False
            
            # Initialize controls
            self.media = MediaControl(self.tv)
            self.system = SystemControl(self.tv)
            self.app = ApplicationControl(self.tv)
            self.tv_control = TvControl(self.tv)
            self.input_control = InputControl(self.tv)
            self.source_control = SourceControl(self.tv)
            
            # Get initial TV state
            await self._update_tv_state()
            
            self.state["connected"] = True
            logger.info(f"Successfully connected to LG TV at {ip}")
            
            return True
            
        except Exception as e:
            self.state["connected"] = False
            logger.error(f"Failed to connect to LG TV: {str(e)}")
            return False
    
    async def _update_tv_state(self):
        """Update the TV state information."""
        try:
            # Get volume info
            try:
                if self.media:
                    # Call get_volume without parameters to avoid linter errors
                    volume_info = await self.media.get_volume()  # type: ignore
                    if volume_info:
                        self.state["volume"] = volume_info.get("volume", 0)
                        self.state["mute"] = volume_info.get("muted", False)
            except Exception as e:
                logger.debug(f"Could not get volume info: {str(e)}")
            
            # Get current app
            # Note: We don't get the current app as the asyncwebostv library doesn't provide a direct method
            # This would require additional implementation
            
            # Get input source 
            # Note: We don't get the source info as the asyncwebostv library doesn't provide a direct method
            # This would require additional implementation
            
            return True
        except Exception as e:
            logger.error(f"Error updating TV state: {str(e)}")
            return False
    
    async def power_on(self):
        """Power on the TV (if supported)."""
        try:
            # Note: Power on might not be directly supported via WebOS API
            # Most TVs must be woken using Wake-on-LAN which requires MAC address
            logger.info(f"Attempting to power on TV {self.get_name()}")
            
            # Try to use system power method if available
            if self.system and self.tv:
                try:
                    # Send turn on message directly 
                    await self.tv.send_message('request', 'ssap://system/turnOn', {})
                    self.state["power"] = "on"
                    self.state["last_command"] = "power_on"
                    return True
                except Exception as e:
                    logger.debug(f"System power on failed: {str(e)}")
            
            self.state["last_command"] = "power_on"
            return False
        except Exception as e:
            logger.error(f"Error powering on TV: {str(e)}")
            return False
    
    async def power_off(self):
        """Power off the TV."""
        try:
            logger.info(f"Powering off TV {self.get_name()}")
            
            # Use system turnOff method
            if self.system and self.tv:
                # Send turn off message directly
                await self.tv.send_message('request', 'ssap://system/turnOff', {})
                self.state["power"] = "off"
                self.state["last_command"] = "power_off"
                return True
            
            return False
        except Exception as e:
            logger.error(f"Error powering off TV: {str(e)}")
            return False
    
    async def set_volume(self, volume):
        """Set the volume level."""
        try:
            volume = int(volume)
            logger.info(f"Setting TV {self.get_name()} volume to {volume}")
            
            if self.media and self.tv:
                # Send volume message directly
                await self.tv.send_message('request', 'ssap://audio/setVolume', {"volume": volume})
                self.state["volume"] = volume
                self.state["last_command"] = f"set_volume_{volume}"
                return True
            
            return False
        except Exception as e:
            logger.error(f"Error setting volume: {str(e)}")
            return False
    
    async def set_mute(self, mute=None):
        """Set mute state on TV."""
        try:
            # Convert "true"/"false" strings to bool if needed
            if isinstance(mute, str):
                mute = mute.lower() in ["true", "1", "yes"]
            
            logger.info(f"Setting mute to {mute} on TV {self.get_name()}")
            
            if not self.tv:
                logger.error("TV client not initialized")
                return False
                
            # Send mute command directly
            await self.tv.send_message('request', 'ssap://audio/setMute', {"mute": mute})
            
            # Update state
            self.state["mute"] = mute
            self.state["last_command"] = "mute_set"
            return True
            
        except Exception as e:
            logger.error(f"Error setting mute: {str(e)}")
            return False
    
    async def launch_app(self, app_name):
        """Launch an app by name or ID."""
        try:
            logger.info(f"Launching app {app_name} on TV {self.get_name()}")
            
            if not self.tv:
                logger.error("TV client not initialized")
                return False
            
            # First retrieve list of available apps directly
            apps_response = await self.tv.send_message('request', 'ssap://com.webos.applicationManager/listApps', {}, get_queue=True)  # type: ignore
            if not apps_response or not apps_response.get("payload") or not apps_response.get("payload").get("apps"):  # type: ignore
                logger.error("Could not retrieve list of apps")
                return False
            
            apps = apps_response.get("payload").get("apps", [])  # type: ignore
            
            # Try to find the app by name or ID
            target_app = None
            for app in apps:
                if app_name.lower() in app.get("title", "").lower() or app_name == app.get("id"):
                    target_app = app
                    break
            
            if not target_app:
                logger.error(f"App {app_name} not found on TV")
                return False
            
            # Launch the app directly
            await self.tv.send_message('request', 'ssap://system.launcher/launch', {"id": target_app["id"]})
            self.state["current_app"] = target_app["id"]
            self.state["last_command"] = f"launch_app_{app_name}"
            return True
            
        except Exception as e:
            logger.error(f"Error launching app: {str(e)}")
            return False
    
    async def send_action(self, action):
        """Send a control action to the TV."""
        try:
            action = action.lower()
            logger.info(f"Sending action {action} to TV {self.get_name()}")
            
            if not self.tv:
                logger.error("TV client not initialized")
                return False
                
            result = False
            
            # Media controls
            if action == "play":
                await self.tv.send_message('request', 'ssap://media.controls/play', {})
                result = True
            elif action == "pause":
                await self.tv.send_message('request', 'ssap://media.controls/pause', {})
                result = True
            elif action == "stop":
                await self.tv.send_message('request', 'ssap://media.controls/stop', {})
                result = True
            elif action == "rewind":
                await self.tv.send_message('request', 'ssap://media.controls/rewind', {})
                result = True
            elif action == "fast_forward":
                await self.tv.send_message('request', 'ssap://media.controls/fastForward', {})
                result = True
            elif action == "volume_up":
                await self.tv.send_message('request', 'ssap://audio/volumeUp', {})
                result = True
            elif action == "volume_down":
                await self.tv.send_message('request', 'ssap://audio/volumeDown', {})
                result = True
            elif action == "mute":
                result = await self.set_mute(True)
            elif action == "unmute":
                result = await self.set_mute(False)
                
            # TV navigation controls
            elif action == "channel_up":
                await self.tv.send_message('request', 'ssap://tv/channelUp', {})
                result = True
            elif action == "channel_down":
                await self.tv.send_message('request', 'ssap://tv/channelDown', {})
                result = True
            elif action in ["up", "down", "left", "right", "ok", "back", "home", 
                            "red", "green", "yellow", "blue", "menu", "exit", "guide"]:
                # These all use the networkinput service with button parameter
                await self.tv.send_message('request', 
                                           'ssap://com.webos.service.networkinput/getPointerInputSocket', 
                                           {"button": action.upper()})
                result = True
            elif action in ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]:
                # Number buttons also use networkinput
                await self.tv.send_message('request', 
                                           'ssap://com.webos.service.networkinput/getPointerInputSocket', 
                                           {"button": action})
                result = True
            else:
                logger.error(f"Unknown action: {action}")
                return False
            
            self.update_state({
                "last_command": LastCommand(
                    action=f"action_{action}",
                    source="api",
                    timestamp=datetime.now(),
                    position="button"
                ).dict()
            })
            return result
            
        except Exception as e:
            logger.error(f"Error sending action: {str(e)}")
            return False
    
    async def set_input_source(self, input_source):
        """Set the TV input source."""
        try:
            logger.info(f"Setting input source to {input_source} on TV {self.get_name()}")
            
            if not self.tv:
                logger.error("TV client not initialized")
                return False
            
            # First retrieve list of available sources using direct message
            try:
                sources_response = await self.tv.send_message('request', 'ssap://tv/getExternalInputList', {}, get_queue=True)  # type: ignore
                if not sources_response or not sources_response.get("payload"):  # type: ignore
                    logger.error("Could not retrieve list of sources")
                    return False
                
                sources = sources_response.get("payload", {}).get("devices", [])  # type: ignore
                if not sources:
                    logger.error("No input sources available")
                    return False
                
                # Try to find the source by name or ID
                target_source = None
                for source in sources:
                    if input_source.lower() in source.get("label", "").lower() or input_source == source.get("id"):
                        target_source = source
                        break
                
                if not target_source:
                    logger.error(f"Input source {input_source} not found on TV")
                    return False
                
                # Set the input source directly
                await self.tv.send_message('request', 'ssap://tv/switchInput', {"inputId": target_source["id"]})
                self.state["input_source"] = target_source["id"]
                self.update_state({
                    "last_command": LastCommand(
                        action=f"set_input_{input_source}",
                        source="api",
                        timestamp=datetime.now(),
                        position="input"
                    ).dict()
                })
                return True
            except Exception as e:
                logger.error(f"Error sending input source request: {str(e)}")
                return False
        except Exception as e:
            logger.error(f"Error setting input source: {str(e)}")
            return False
    
    async def handle_message(self, topic: str, payload: str):
        """Handle incoming MQTT messages for this device."""
        logger.debug(f"LG TV received message on {topic}: {payload}")
        
        try:
            # Handle power topic
            power_topic = self.config.get("power_topic")
            if topic == power_topic:
                if payload.lower() in ["on", "1", "true"]:
                    await self.power_on()
                elif payload.lower() in ["off", "0", "false"]:
                    await self.power_off()
                return
            
            # Handle volume topic
            volume_topic = self.config.get("volume_topic")
            if topic == volume_topic:
                try:
                    volume = int(payload)
                    await self.set_volume(volume)
                except ValueError:
                    logger.error(f"Invalid volume value: {payload}")
                return
                
            # Handle app launch topic
            app_launch_topic = self.config.get("app_launch_topic")
            if topic == app_launch_topic:
                # The payload can now be an app_id or a configured app name
                await self.launch_app(payload)
                return
                
            # Handle input source topic
            input_source_topic = self.config.get("input_source_topic")
            if topic == input_source_topic:
                await self.set_input_source(payload)
                return
            
            # Handle command topics from configuration
            for cmd_name, cmd_config in self.get_available_commands().items():
                if topic == cmd_config["topic"]:
                    if payload.lower() in ["1", "true", "on"]:
                        # Process command
                        action = cmd_config.get("action")
                        if action:
                            await self.send_action(action)
                            
                        # Update state based on command
                        self.update_state({
                            "last_command": {
                                "action": cmd_name,
                                "source": "mqtt",
                                "position": cmd_config.get("position")
                            }
                        })
                    break
            
        except Exception as e:
            logger.error(f"Error handling message for {self.get_name()}: {str(e)}")
    
    def get_current_state(self) -> LgTvState:
        """Return the current state of the TV."""
        return LgTvState(
            device_id=self.device_id,
            device_name=self.device_name,
            power=self.state.get("power", "unknown"),
            volume=self.state.get("volume", 0),
            mute=self.state.get("mute", False),
            current_app=self.state.get("current_app"),
            input_source=self.state.get("input_source"),
            connected=self.state.get("connected", False),
            ip_address=self.state.get("ip_address"),
            mac_address=self.state.get("mac_address"),
            last_command=self.state.get("last_command"),
            error=self.state.get("error")
        )
        
    def get_state(self) -> Dict[str, Any]:
        """Override BaseDevice get_state to ensure we safely return state."""
        if not hasattr(self, 'state') or self.state is None:
            return LgTvState(
                device_id=self.device_id,
                device_name=self.device_name,
                power="unknown",
                volume=0,
                mute=False,
                current_app=None,
                input_source=None,
                connected=False,
                ip_address=None,
                mac_address=None,
                error="Device state not properly initialized"
            ).model_dump()
        return super().get_state()

    # Get available apps on the TV
    async def get_available_apps(self):
        """Get a list of available apps on the TV."""
        try:
            if not self.app:
                logger.error("App control not initialized")
                return []

            # Simplest implementation - call list_apps() without any parameters
            # This method is defined in the ApplicationControl COMMANDS dictionary
            # and should work according to the library's implementation
            try:
                # type: ignore comment is needed to suppress linter errors
                # about missing callback parameter
                result = await self.app.list_apps()  # type: ignore
                return result
            except Exception as e:
                logger.error(f"Error getting available apps: {str(e)}")
                return []
            
        except Exception as e:
            logger.error(f"Error in get_available_apps: {str(e)}")
            return [] 