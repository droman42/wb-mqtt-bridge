import json
import logging
from typing import Dict, Any, List
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
            "threshold": self.config.get("parameters", {}).get("threshold", 25.5)
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
            return self.config['mqtt_topics']
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
        
        if command == 'turnOn':
            self.update_state({"power": "on"})
            logger.info("Turning device ON")
        elif command == 'turnOff':
            self.update_state({"power": "off"})
            logger.info("Turning device OFF")
        elif command == 'getData':
            logger.info("Getting device data")
            return self.get_state()
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
        
    def get_state(self) -> Dict[str, Any]:
        """Override BaseDevice get_state to ensure we safely return state."""
        if not hasattr(self, 'state') or self.state is None:
            return ExampleDeviceState(
                device_id=self.device_id,
                device_name=self.device_name,
                power="off",
                last_reading=None,
                update_interval=60,
                threshold=25.5,
                error="Device state not properly initialized"
            ).dict()
        return super().get_state() 