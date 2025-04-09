import json
import logging
import asyncio
import os
from typing import Dict, Any, List, Optional
from socket import socket, AF_INET, SOCK_DGRAM, SOL_SOCKET, SO_BROADCAST
from concurrent.futures import ThreadPoolExecutor
from pywebostv.discovery import *
from pywebostv.connection import *
from pywebostv.controls import *
from devices.base_device import BaseDevice

logger = logging.getLogger(__name__)

class LgTv(BaseDevice):
    """Implementation of an LG TV controlled over the network using PyWebOSTV library."""
    
    async def setup(self) -> bool:
        """Initialize the device."""
        try:
            # Initialize device state
            self.state = {
                "power": "unknown",
                "volume": 0,
                "mute": False,
                "current_app": None,
                "input_source": None,
                "last_command": None,
                "connected": False
            }
            
            # Get TV configuration
            tv_config = self.config.get("tv", {})
            if not tv_config:
                logger.error(f"No TV configuration for device {self.get_name()}")
                return False
                
            self.state["ip_address"] = tv_config.get("ip_address")
            self.state["mac_address"] = tv_config.get("mac_address")

            # Get connection client key
            if tv_config.get("client_key") == "":
                logger.error(f"No Access Key configured for TV {self.get_name()}")
                return False
            self.store = {"client_key": tv_config.get("client_key")}

            if not self.state["ip_address"]:
                logger.error(f"No IP address configured for TV {self.get_name()}")
                return False
            
            # Set up executor for synchronous calls
            self.executor = ThreadPoolExecutor(max_workers=2)
            
            # Try to connect to TV
            try:
                await self._connect_to_tv()
            except Exception as e:
                logger.warning(f"Could not connect to TV during setup: {str(e)}")
                # Continue setup even if TV is off
            
            logger.info(f"LG TV {self.get_name()} initialized")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize LG TV {self.get_name()}: {str(e)}")
            return False
    
    async def shutdown(self) -> bool:
        """Cleanup device resources."""
        try:
            # Close down the executor
            self.executor.shutdown(wait=False)
            
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
        """Establish a connection to the TV using PyWebOSTV."""
        try:
            ip_address = self.state.get("ip_address")
            
            # Run in executor since PyWebOSTV uses blocking calls
            def connect_sync():
                # Check if store is valid
                if not self.store:
                    logger.error("Invalid store - cannot connect to TV")
                    return None
                
                # Create client
                if self.config.get("tv", {}).get("secure", True):
                    client = WebOSClient(ip_address, secure=True)
                else:
                    client = WebOSClient(ip_address)
                
                # Connect
                client.connect()
                
                # Register with the TV
                registered = False
                for status in client.register(self.store):
                    if status == WebOSClient.PROMPTED:
                        logger.info("Please accept the connection on the TV!")
                    elif status == WebOSClient.REGISTERED:
                        logger.info("Registration successful!")
                        registered = True
                
                if not registered:
                    logger.error("Failed to register with TV")
                    return None
                
                return client
            
            # Run the connection in a separate thread
            self.client = await asyncio.get_event_loop().run_in_executor(
                self.executor, connect_sync
            )
            
            # Initialize controls
            self.media = MediaControl(self.client)
            self.system = SystemControl(self.client)
            self.app = ApplicationControl(self.client)
            self.tv_control = TvControl(self.client)
            self.input_control = InputControl(self.client)
            self.source_control = SourceControl(self.client)
            
            # Get initial TV state
            await self._update_tv_state()
            
            self.state["connected"] = True
            logger.info(f"Successfully connected to LG TV at {ip_address}")
            
            return True
            
        except Exception as e:
            self.state["connected"] = False
            logger.error(f"Failed to connect to LG TV: {str(e)}")
            return False
    
    async def _update_tv_state(self):
        """Update the TV state information."""
        try:
            # Run in executor since PyWebOSTV uses blocking calls
            def get_state_sync():
                state_updates = {}
                
                try:
                    # Get volume info
                    volume_info = self.media.get_volume()
                    if volume_info:
                        state_updates["volume"] = volume_info.get("volume", 0)
                        state_updates["mute"] = volume_info.get("muted", False)
                except Exception as e:
                    logger.debug(f"Could not get volume info: {str(e)}")
                
                try:
                    # Get current app
                    foreground_app = self.app.get_current()
                    if foreground_app:
                        state_updates["current_app"] = foreground_app
                except Exception as e:
                    logger.debug(f"Could not get current app: {str(e)}")
                
                return state_updates
            
            # Run in a separate thread
            state_updates = await asyncio.get_event_loop().run_in_executor(
                self.executor, get_state_sync
            )
            
            # Update state
            if state_updates:
                self.update_state(state_updates)
                
        except Exception as e:
            logger.error(f"Failed to update TV state: {str(e)}")
    
    async def power_on(self):
        """Power on the TV using Wake-on-LAN."""
        try:
            mac = self.state.get("mac_address")
            if not mac:
                logger.error("No MAC address configured for TV")
                return False
                
            # Send magic packet
            mac_bytes = bytes.fromhex(mac.replace(':', ''))
            magic_packet = b'\xff' * 6 + mac_bytes * 16
            
            sock = socket(AF_INET, SOCK_DGRAM)
            sock.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)
            sock.sendto(magic_packet, ('255.255.255.255', 9))
            sock.close()
            
            self.update_state({"power": "on"})
            logger.info(f"Sent WOL packet to {mac}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send WOL packet: {str(e)}")
            return False
    
    async def power_off(self):
        """Power off the TV."""
        if not self.state.get("connected", False):
            await self._connect_to_tv()
        
        try:
            # Run in executor since PyWebOSTV uses blocking calls
            def power_off_sync():
                try:
                    self.system.power_off()
                    return True
                except Exception as e:
                    logger.error(f"Error powering off TV: {str(e)}")
                    return False
            
            result = await asyncio.get_event_loop().run_in_executor(
                self.executor, power_off_sync
            )
            
            if result:
                self.update_state({"power": "off", "connected": False})
                
            return result
            
        except Exception as e:
            logger.error(f"Failed to power off TV: {str(e)}")
            return False
    
    async def set_volume(self, volume):
        """Set the TV volume."""
        if not self.state.get("connected", False):
            await self._connect_to_tv()
        
        try:
            # Ensure volume is in valid range
            volume = max(0, min(100, int(volume)))
            
            # Run in executor since PyWebOSTV uses blocking calls
            def set_volume_sync():
                try:
                    self.media.set_volume(volume)
                    return True
                except Exception as e:
                    logger.error(f"Error setting volume: {str(e)}")
                    return False
            
            result = await asyncio.get_event_loop().run_in_executor(
                self.executor, set_volume_sync
            )
            
            if result:
                self.update_state({"volume": volume})
                
            return result
            
        except Exception as e:
            logger.error(f"Failed to set volume: {str(e)}")
            return False
    
    async def set_mute(self, mute):
        """Mute or unmute the TV."""
        if not self.state.get("connected", False):
            await self._connect_to_tv()
        
        try:
            # Convert to boolean
            mute_state = bool(mute)
            
            # Run in executor since PyWebOSTV uses blocking calls
            def set_mute_sync():
                try:
                    self.media.mute(mute_state)
                    return True
                except Exception as e:
                    logger.error(f"Error setting mute: {str(e)}")
                    return False
            
            result = await asyncio.get_event_loop().run_in_executor(
                self.executor, set_mute_sync
            )
            
            if result:
                self.update_state({"mute": mute_state})
                
            return result
            
        except Exception as e:
            logger.error(f"Failed to set mute: {str(e)}")
            return False
    
    async def launch_app(self, app_id):
        """Launch an app on the TV."""
        if not self.state.get("connected", False):
            await self._connect_to_tv()
        
        try:
            # Run in executor since PyWebOSTV uses blocking calls
            def launch_app_sync():
                try:
                    # Get all apps
                    apps = self.app.list_apps()
                    
                    # Find the app by ID
                    target_app = None
                    for app in apps:
                        if app["id"] == app_id:
                            target_app = app
                            break
                    
                    if target_app:
                        self.app.launch(target_app)
                        return True
                    else:
                        logger.warning(f"App {app_id} not found")
                        return False
                        
                except Exception as e:
                    logger.error(f"Error launching app: {str(e)}")
                    return False
            
            result = await asyncio.get_event_loop().run_in_executor(
                self.executor, launch_app_sync
            )
            
            if result:
                self.update_state({"current_app": app_id})
                
            return result
            
        except Exception as e:
            logger.error(f"Failed to launch app: {str(e)}")
            return False
    
    async def send_action(self, action):
        """Send an action press to the TV."""
        if not self.state.get("connected", False):
            await self._connect_to_tv()
        
        try:
            # Run in executor since PyWebOSTV uses blocking calls
            def send_action_sync():
                try:
                    # Create a separate input connection
                    self.input_control.connect_input()
                    
                    # Map action names to methods
                    action_methods = {
                        "UP": self.input_control.up,
                        "DOWN": self.input_control.down,
                        "LEFT": self.input_control.left,
                        "RIGHT": self.input_control.right,
                        "ENTER": self.input_control.ok,
                        "HOME": self.input_control.home,
                        "BACK": self.input_control.back,
                        "MENU": self.input_control.menu,
                        "VOLUMEUP": self.input_control.volume_up,
                        "VOLUMEDOWN": self.input_control.volume_down,
                        "MUTE": self.input_control.mute,
                        "CHANNELUP": self.input_control.channel_up,
                        "CHANNELDOWN": self.input_control.channel_down,
                        "PLAY": self.input_control.play,
                        "PAUSE": self.input_control.pause,
                        "STOP": self.input_control.stop,
                        "FASTFORWARD": self.input_control.fastforward,
                        "REWIND": self.input_control.rewind,
                        "EXIT": self.input_control.exit,
                        "RED": self.input_control.red,
                        "GREEN": self.input_control.green,
                        "YELLOW": self.input_control.yellow,
                        "BLUE": self.input_control.blue,
                        "NETFLIX": lambda: self.input_control.type("NETFLIX"),
                        "AMAZON": lambda: self.input_control.type("AMAZON"),
                        "YOUTUBE": lambda: self.input_control.type("YOUTUBE"),
                        "INFO": self.input_control.info,
                        "DASH": self.input_control.dash,
                        "ASTERISK": self.input_control.asterisk,
                        "CC": self.input_control.cc,
                        "0": lambda: self.input_control.num_0(),
                        "1": lambda: self.input_control.num_1(),
                        "2": lambda: self.input_control.num_2(),
                        "3": lambda: self.input_control.num_3(),
                        "4": lambda: self.input_control.num_4(),
                        "5": lambda: self.input_control.num_5(),
                        "6": lambda: self.input_control.num_6(),
                        "7": lambda: self.input_control.num_7(),
                        "8": lambda: self.input_control.num_8(),
                        "9": lambda: self.input_control.num_9(),
                        "POWER": lambda: self.system.power_off()
                    }
                    
                    # Call the appropriate method if it exists
                    if action in action_methods:
                        action_methods[action]()
                        result = True
                    else:
                        logger.warning(f"Unknown action: {action}")
                        result = False
                    
                    # Close the input connection
                    self.input_control.disconnect_input()
                    return result
                    
                except Exception as e:
                    logger.error(f"Error sending action: {str(e)}")
                    return False
            
            return await asyncio.get_event_loop().run_in_executor(
                self.executor, send_action_sync
            )
            
        except Exception as e:
            logger.error(f"Failed to send action: {str(e)}")
            return False
    
    async def set_input_source(self, input_source):
        """Set the input source on the TV."""
        if not self.state.get("connected", False):
            await self._connect_to_tv()
        
        try:
            # Run in executor since PyWebOSTV uses blocking calls
            def set_input_sync():
                try:
                    # Get all input sources
                    sources = self.source_control.list_sources()
                    
                    # Find the source by ID
                    target_source = None
                    for source in sources:
                        if source["id"] == input_source:
                            target_source = source
                            break
                    
                    if target_source:
                        self.source_control.set_source(target_source)
                        return True
                    else:
                        logger.warning(f"Input source {input_source} not found")
                        return False
                        
                except Exception as e:
                    logger.error(f"Error setting input source: {str(e)}")
                    return False
            
            result = await asyncio.get_event_loop().run_in_executor(
                self.executor, set_input_sync
            )
            
            if result:
                self.update_state({"input_source": input_source})
                
            return result
            
        except Exception as e:
            logger.error(f"Failed to set input source: {str(e)}")
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
                                "source": "mqtt"
                            }
                        })
                    break
            
        except Exception as e:
            logger.error(f"Error handling message for {self.get_name()}: {str(e)}")
    
    def get_current_state(self) -> Dict[str, Any]:
        """Return the current state of the TV."""
        return {
            "power": self.state.get("power", "unknown"),
            "volume": self.state.get("volume", 0),
            "mute": self.state.get("mute", False),
            "current_app": self.state.get("current_app"),
            "input_source": self.state.get("input_source"),
            "connected": self.state.get("connected", False),
            "last_command": self.state.get("last_command")
        } 