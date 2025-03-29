import json
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

def subscribe_topics(config: Dict[str, Any]) -> List[str]:
    """Define the MQTT topics this device should subscribe to."""
    # Get topics from config, or use defaults
    if 'mqtt_topics' in config:
        return config['mqtt_topics']
    else:
        # Default topics if not specified in config
        device_name = config.get('device_name', 'example_device')
        return [
            f"home/{device_name}/status",
            f"home/{device_name}/command"
        ]

async def handle_message(topic: str, payload: str):
    """Handle incoming MQTT messages for this device."""
    logger.debug(f"Example device received message on {topic}: {payload}")
    
    try:
        # Try to parse JSON payload
        data = json.loads(payload)
        
        # Handle different topics
        if topic.endswith('/status'):
            process_status_update(data)
        elif topic.endswith('/command'):
            await process_command(data)
        else:
            logger.warning(f"Unhandled topic for example device: {topic}")
    except json.JSONDecodeError:
        logger.warning(f"Invalid JSON payload: {payload}")
    except Exception as e:
        logger.error(f"Error handling message: {str(e)}")

def process_status_update(data: Dict[str, Any]):
    """Process a status update from the device."""
    logger.info(f"Device status update: {data}")
    
    # Here you would implement logic to handle the status update
    # For example, updating a database or triggering other actions

async def process_command(data: Dict[str, Any]):
    """Process a command for the device."""
    logger.info(f"Received command: {data}")
    
    command = data.get('command')
    if not command:
        logger.warning("Command message missing 'command' field")
        return
    
    # Handle different commands
    if command == 'turnOn':
        # Logic to turn on the device
        logger.info("Turning device ON")
        # You might publish a message to another topic here
    elif command == 'turnOff':
        # Logic to turn off the device
        logger.info("Turning device OFF")
    elif command == 'getData':
        # Logic to get data from the device
        logger.info("Getting data from device")
    else:
        logger.warning(f"Unknown command: {command}") 