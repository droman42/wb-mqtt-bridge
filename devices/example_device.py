import json
import logging
import asyncio
from typing import Dict, Any, List, Optional
from devices.base_device import BaseDevice
from app.schemas import ExampleDeviceState

logger = logging.getLogger(__name__)

class ExampleDevice(BaseDevice):
    """Example device implementation."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._state_schema = ExampleDeviceState
        self.state = {
            "power": "off",
            "last_reading": None,
            "update_interval": self.config.get("parameters", {}).get("update_interval", 60),
            "threshold": self.config.get("parameters", {}).get("threshold", 25.5),
            "temperature": 21,
            "brightness": 50
        }
        
        # Define action handlers for the parameter-based approach
        self._action_handlers = {
            "power_on": self.handle_power_on,
            "power_off": self.handle_power_off,
            "set_temperature": self.handle_set_temperature,
            "set_brightness": self.handle_set_brightness,
            "getData": self.handle_get_data
        }
    
    async def setup(self) -> bool:
        """Initialize the device."""
        try:
            logger.info(f"Initializing device: {self.get_name()}")
            logger.info(f"Example device {self.get_name()} initialized")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize device {self.get_name()}: {str(e)}")
            self.state["error"] = str(e)
            return False
    
    async def shutdown(self) -> bool:
        """Cleanup device resources."""
        try:
            # Perform any necessary cleanup
            logger.info(f"Example device {self.device_name} shutdown complete")
            return True
        except Exception as e:
            logger.error(f"Error during device shutdown: {str(e)}")
            return False
    
    def subscribe_topics(self) -> List[str]:
        """Define the MQTT topics this device should subscribe to."""
        if 'mqtt_topics' in self.config:
            topics: List[str] = self.config['mqtt_topics']
            return topics
        else:
            return [
                f"home/{self.device_name}/status",
                f"home/{self.device_name}/command"
            ]
    
    async def handle_message(self, topic: str, payload: str):
        """Handle incoming MQTT messages for this device."""
        logger.debug(f"Example device received message on {topic}: {payload}")
        
        try:
            data = json.loads(payload)
            
            if topic.endswith('/status'):
                await self.process_status_update(data)
            elif topic.endswith('/command'):
                await self.process_command(data)
            else:
                logger.warning(f"Unhandled topic for example device: {topic}")
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON payload: {payload}")
        except Exception as e:
            logger.error(f"Error handling message: {str(e)}")
    
    async def process_status_update(self, data: Dict[str, Any]):
        """Process a status update from the device."""
        logger.info(f"Device status update: {data}")
        self.update_state({"last_reading": data})
    
    async def process_command(self, data: Dict[str, Any]):
        """Process a command for the device."""
        logger.info(f"Received command: {data}")
        
        command = data.get('command')
        if not command:
            logger.warning("Command message missing 'command' field")
            return
        
        params = data.get('params', {})
        
        if command == 'turnOn':
            await self.execute_action('power_on', params)
        elif command == 'turnOff':
            await self.execute_action('power_off', params)
        elif command == 'getData':
            logger.info("Getting device data")
            return await self.execute_action('getData', params)
        else:
            logger.warning(f"Unknown command: {command}")
    
    def get_current_state(self) -> ExampleDeviceState:
        """Return the current state of the device."""
        return ExampleDeviceState(
            device_id=self.device_id,
            device_name=self.device_name,
            power=self.state.get("power", "off"),
            last_reading=self.state.get("last_reading"),
            update_interval=self.state.get("update_interval", 60),
            threshold=self.state.get("threshold", 25.5),
            last_command=self.state.get("last_command"),
            error=self.state.get("error")
        )
    
    # Handler methods for the parameter-based approach
    async def handle_power_on(self, cmd_config: Dict[str, Any], params: Dict[str, Any]):
        """Turn the device on with optional delay."""
        delay = params.get("delay", 0)
        
        if delay > 0:
            logger.info(f"Turning device ON after {delay}s delay")
            await asyncio.sleep(delay)
        
        self.update_state({"power": "on"})
        logger.info("Device turned ON")
        return True
    
    async def handle_power_off(self, cmd_config: Dict[str, Any], params: Dict[str, Any]):
        """Turn the device off with optional delay."""
        delay = params.get("delay", 0)
        
        if delay > 0:
            logger.info(f"Turning device OFF after {delay}s delay")
            await asyncio.sleep(delay)
        
        self.update_state({"power": "off"})
        logger.info("Device turned OFF")
        return True
    
    async def handle_set_temperature(self, cmd_config: Dict[str, Any], params: Dict[str, Any]):
        """Set the device temperature."""
        temperature = params.get("temperature")
        mode = params.get("mode", "auto")
        
        if temperature is None:
            logger.error("No temperature provided")
            return False
        
        self.update_state({"temperature": temperature, "mode": mode})
        logger.info(f"Temperature set to {temperature}°C in {mode} mode")
        return True
    
    async def handle_set_brightness(self, cmd_config: Dict[str, Any], params: Dict[str, Any]):
        """Set the device brightness."""
        level = params.get("level")
        transition = params.get("transition", 0)
        
        if level is None:
            logger.error("No brightness level provided")
            return False
        
        if transition > 0:
            current = self.state.get("brightness", 0)
            logger.info(f"Transitioning brightness from {current} to {level} over {transition}s")
            
            # Simplified transition simulation
            step = (level - current) / transition
            for i in range(1, transition + 1):
                interim_level = current + step * i
                self.update_state({"brightness": round(interim_level)})
                await asyncio.sleep(1)
        else:
            self.update_state({"brightness": level})
            
        logger.info(f"Brightness set to {level}%")
        return True
    
    async def handle_get_data(self, cmd_config: Dict[str, Any], params: Dict[str, Any]):
        """Get device data with optional filter."""
        filter_str = params.get("filter")
        
        data = {
            "power": self.state.get("power"),
            "temperature": self.state.get("temperature"),
            "brightness": self.state.get("brightness"),
            "last_reading": self.state.get("last_reading"),
            "update_interval": self.state.get("update_interval"),
            "threshold": self.state.get("threshold")
        }
        
        if filter_str:
            filtered_data = {}
            filter_keys = filter_str.split(',')
            for key in filter_keys:
                if key in data:
                    filtered_data[key] = data[key]
            return filtered_data
        
        return data 