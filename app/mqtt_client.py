import asyncio
import logging
from typing import Dict, Any, Callable, Optional, List
import json

from asyncio_mqtt import Client, MqttError
from asyncio.exceptions import CancelledError

logger = logging.getLogger(__name__)

class MQTTClient:
    """Asynchronous MQTT client for the web service."""
    
    def __init__(self, broker_config: Dict[str, Any]):
        self.host = broker_config.get('host', 'localhost')
        self.port = broker_config.get('port', 1883)
        self.client_id = broker_config.get('client_id', 'mqtt_web_service')
        self.keepalive = broker_config.get('keepalive', 60)
        
        # Authentication settings
        auth = broker_config.get('auth', {})
        self.username = auth.get('username')
        self.password = auth.get('password')
        
        # Message handlers
        self.message_handlers: Dict[str, Callable] = {}
        
        # MQTT client
        self.client = None
        self.connected = False
        self.tasks = []
    
    async def connect(self):
        """Connect to the MQTT broker."""
        try:
            self.client = Client(
                hostname=self.host,
                port=self.port,
                identifier=self.client_id,
                keepalive=self.keepalive,
                username=self.username,
                password=self.password
            )
            await self.client.connect()
            self.connected = True
            logger.info(f"Connected to MQTT broker at {self.host}:{self.port}")
            return True
        except MqttError as e:
            logger.error(f"Failed to connect to MQTT broker: {str(e)}")
            self.connected = False
            return False
    
    async def disconnect(self):
        """Disconnect from the MQTT broker."""
        try:
            if self.client:
                await self.client.disconnect()
                self.connected = False
                logger.info("Disconnected from MQTT broker")
            return True
        except Exception as e:
            logger.error(f"Error disconnecting from MQTT broker: {str(e)}")
            return False
    
    def register_handler(self, device_name: str, handler: Callable):
        """Register a message handler for a device."""
        self.message_handlers[device_name] = handler
        logger.info(f"Registered message handler for device: {device_name}")
    
    async def subscribe(self, device_name: str, topics: List[str]):
        """Subscribe to topics for a device."""
        if not self.connected or not self.client:
            logger.error("Cannot subscribe: Not connected to MQTT broker")
            return False
        
        for topic in topics:
            try:
                await self.client.subscribe(topic)
                logger.info(f"Subscribed to topic: {topic} for device: {device_name}")
            except MqttError as e:
                logger.error(f"Failed to subscribe to {topic}: {str(e)}")
                return False
        return True
    
    async def publish(self, topic: str, payload: Any, qos: int = 0, retain: bool = False):
        """Publish a message to a topic."""
        if not self.connected or not self.client:
            logger.error("Cannot publish: Not connected to MQTT broker")
            return False
        
        try:
            # Convert payload to JSON string if it's a dict
            if isinstance(payload, dict):
                payload = json.dumps(payload)
            
            await self.client.publish(topic, payload, qos=qos, retain=retain)
            logger.debug(f"Published to {topic}: {payload}")
            return True
        except MqttError as e:
            logger.error(f"Failed to publish to {topic}: {str(e)}")
            return False
    
    async def listen(self):
        """Listen for messages on subscribed topics."""
        if not self.connected or not self.client:
            logger.error("Cannot listen: Not connected to MQTT broker")
            return
        
        try:
            async with self.client.messages() as messages:
                async for message in messages:
                    topic = message.topic.value
                    payload = message.payload.decode()
                    
                    logger.debug(f"Received message on {topic}: {payload}")
                    
                    # Find the device handler for this topic
                    for device_name, handler in self.message_handlers.items():
                        try:
                            await handler(topic, payload)
                        except Exception as e:
                            logger.error(f"Error in handler for {device_name}: {str(e)}")
        
        except CancelledError:
            logger.info("MQTT listener was cancelled")
        except MqttError as e:
            logger.error(f"MQTT error while listening: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error in MQTT listener: {str(e)}")
    
    async def start(self, device_topics: Dict[str, List[str]]):
        """Start the MQTT client with all the required subscriptions."""
        if not await self.connect():
            logger.error("Failed to start MQTT client: Connection error")
            return False
        
        # Subscribe to topics for each device
        for device_name, topics in device_topics.items():
            await self.subscribe(device_name, topics)
        
        # Start listening for messages
        listener_task = asyncio.create_task(self.listen())
        self.tasks.append(listener_task)
        
        logger.info("MQTT client started successfully")
        return True
    
    async def stop(self):
        """Stop the MQTT client and cancel all tasks."""
        for task in self.tasks:
            if not task.done():
                task.cancel()
        
        self.tasks = []
        await self.disconnect()
        logger.info("MQTT client stopped") 