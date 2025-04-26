import asyncio
import logging
from typing import Dict, Any, Callable, Optional, List, Awaitable
import json

from aiomqtt import Client, MqttError
from asyncio.exceptions import CancelledError

logger = logging.getLogger(__name__)

class MQTTClient:
    """Asynchronous MQTT client for the web service."""
    
    def __init__(self, broker_config: Dict[str, Any]):
        logger.info(f"Initializing MQTT client with broker config: {broker_config}")
        
        # Check if broker_config is a Pydantic model and convert it to dict if needed
        config_dict = broker_config
        try:
            if hasattr(broker_config, 'model_dump'):
                config_dict = broker_config.model_dump()  # type: ignore
            elif hasattr(broker_config, 'dict') and callable(getattr(broker_config, 'dict')):
                config_dict = broker_config.dict()  # type: ignore
        except AttributeError:
            # Already a dict, continue
            pass
            
        self.host = config_dict.get('host', 'localhost')
        logger.info(f"MQTT broker host set to: {self.host} (from config)")
        self.port = config_dict.get('port', 1883)
        logger.info(f"MQTT broker port set to: {self.port} (from config)")
        self.client_id = config_dict.get('client_id', 'mqtt_web_service')
        self.keepalive = config_dict.get('keepalive', 60)
        
        # Authentication settings
        auth = config_dict.get('auth', {})
        self.username = auth.get('username')
        self.password = auth.get('password')
        
        # Message handlers
        self.message_handlers: Dict[str, Callable] = {}
        # Map of topics to devices that have subscribed to them
        self.topic_subscribers: Dict[str, List[str]] = {}
        
        # MQTT client
        self.client: Optional[Client] = None
        self.connected = False
        self.tasks: List[asyncio.Task] = []
    
    async def start(self, device_topics: Dict[str, List[str]]):
        """Start the MQTT client with all the required subscriptions."""
        try:
            # Create client with or without authentication
            client_args = {
                'hostname': self.host,
                'port': self.port,
                'keepalive': self.keepalive
            }
            
            # Add authentication only if BOTH username AND password are provided and non-empty
            if self.username and self.password and len(self.username) > 0 and len(self.password) > 0:
                client_args.update({
                    'username': self.username,
                    'password': self.password
                })
                logger.info("Using MQTT authentication with provided credentials")
            else:
                logger.info("Using anonymous MQTT connection (no credentials provided)")
            
            # Initialize topic-device mapping
            self.topic_subscribers = {}
            
            # Create mapping of topics to devices
            for device_name, topics in device_topics.items():
                for topic in topics:
                    if topic not in self.topic_subscribers:
                        self.topic_subscribers[topic] = []
                    self.topic_subscribers[topic].append(device_name)
            
            # Create client and start it in a background task
            listener_task = asyncio.create_task(self._run_client(client_args, device_topics))
            self.tasks.append(listener_task)
            
            logger.info(f"Started MQTT client connecting to broker at {self.host}:{self.port}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start MQTT client: {str(e)}")
            return False
    
    async def _run_client(self, client_args, device_topics):
        """Run the MQTT client in an async context manager."""
        max_retries = 5
        retry_delay = 5  # seconds
        retry_count = 0
        
        logger.info(f"Running MQTT client with args: {client_args}")
        
        while retry_count < max_retries:
            try:
                logger.info(f"Connecting to MQTT broker at {client_args.get('hostname', 'unknown')}:{client_args.get('port', 'unknown')} (attempt {retry_count + 1}/{max_retries})")
                async with Client(**client_args) as client:
                    self.client = client
                    self.connected = True
                    logger.info(f"Connected to MQTT broker at {self.host}:{self.port}")
                    
                    # Subscribe to topics for each device
                    for device_name, topics in device_topics.items():
                        for topic in topics:
                            await client.subscribe(topic)
                            logger.info(f"Subscribed to topic: {topic} for device: {device_name}")
                    
                    # Process incoming messages
                    async for message in client.messages:
                        topic = message.topic.value
                        try:
                            # Try UTF-8 first, fall back to latin-1 if that fails
                            try:
                                payload = message.payload.decode('utf-8')  # type: ignore
                            except UnicodeDecodeError:
                                # If UTF-8 fails, try latin-1 which can handle any byte sequence
                                payload = message.payload.decode('latin-1')  # type: ignore
                                logger.warning(f"Received non-UTF-8 payload on topic {topic}, using latin-1 decoding")
                        
                        except Exception as e:
                            logger.error(f"Failed to decode payload on topic {topic}: {str(e)}")
                            continue
                        
                        logger.debug(f"Received message on {topic}: {payload}")
                        
                        # Find devices that have subscribed to this topic
                        # Use wildcard matching for MQTT topics
                        devices_to_notify = set()
                        for subscribed_topic, device_names in self.topic_subscribers.items():
                            # Simple wildcard matching (+ and #)
                            if self._topic_matches(subscribed_topic, topic):
                                devices_to_notify.update(device_names)
                        
                        # Only notify devices that have subscribed to this topic
                        for device_name in devices_to_notify:
                            handler = self.message_handlers.get(device_name)
                            if handler:
                                try:
                                    mqtt_command = await handler(topic, payload)
                                    # Check if the handler returned an MQTT command to publish
                                    if mqtt_command and isinstance(mqtt_command, dict) and "topic" in mqtt_command and "payload" in mqtt_command:
                                        logger.info(f"Device {device_name} returned MQTT command to publish: {mqtt_command}")
                                        # Publish the command
                                        publish_topic = mqtt_command["topic"]
                                        publish_payload = mqtt_command["payload"]
                                        logger.info(f"Publishing message - Topic: {publish_topic}, Payload: {publish_payload}, Type: {type(publish_payload).__name__}")
                                        
                                        # Try to convert numeric strings to integers for certain device types
                                        if device_name.startswith("wirenboard_") and isinstance(publish_payload, str) and publish_payload.isdigit():
                                            publish_payload = int(publish_payload)
                                            logger.info(f"Converted payload to integer: {publish_payload}")
                                            
                                        try:
                                            success = await self.publish(publish_topic, publish_payload)
                                            if success:
                                                logger.info(f"Successfully published to {publish_topic}")
                                            else:
                                                logger.error(f"Failed to publish to {publish_topic}")
                                        except Exception as e:
                                            logger.error(f"Error publishing to {publish_topic}: {str(e)}")
                                    else:
                                        logger.warning(f"Device {device_name} did not return a valid MQTT command to publish")
                                except Exception as e:
                                    logger.error(f"Error in handler for {device_name}: {str(e)}")
            
            except CancelledError:
                logger.info("MQTT client task was cancelled")
                break
            except MqttError as e:
                logger.error(f"MQTT error: {str(e)}")
                if "Connection refused" in str(e):
                    logger.error(f"Could not connect to MQTT broker at {self.host}:{self.port}. Please ensure the broker is running and accessible.")
                elif "Not authorized" in str(e):
                    logger.error("Authentication failed. Please check your MQTT username and password.")
                
                self.connected = False
                retry_count += 1
                if retry_count < max_retries:
                    wait_time = retry_delay * retry_count
                    logger.info(f"Retrying connection in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Max retries ({max_retries}) reached. Giving up MQTT connection.")
            except Exception as e:
                logger.error(f"Unexpected error in MQTT client: {str(e)}")
                self.connected = False
                retry_count += 1
                if retry_count < max_retries:
                    wait_time = retry_delay * retry_count
                    logger.info(f"Retrying connection in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Max retries ({max_retries}) reached. Giving up MQTT connection.")
            finally:
                if self.connected:  # Only reset if we were connected
                    self.connected = False
                    self.client = None
    
    async def stop(self):
        """Stop the MQTT client and cancel all tasks."""
        for task in self.tasks:
            if not task.done():
                task.cancel()
        
        self.tasks = []
        logger.info("MQTT client stopped")
    
    def register_handler(self, device_name: str, handler: Callable):
        """Register a message handler for a device."""
        self.message_handlers[device_name] = handler
        logger.info(f"Registered message handler for device: {device_name}")
    
    async def publish(self, topic: str, payload: Any, qos: int = 0, retain: bool = False):
        """Publish a message to a topic."""
        if not self.connected or not self.client:
            logger.error("Cannot publish: Not connected to MQTT broker")
            return False
        
        try:
            # Handle different payload types
            if isinstance(payload, dict):
                payload = json.dumps(payload)
            elif isinstance(payload, bool):
                payload = "true" if payload else "false"
            elif isinstance(payload, (int, float)):
                payload = str(payload)
                
            logger.debug(f"Publishing to {topic}: {payload} (type: {type(payload).__name__})")
            await self.client.publish(topic, payload, qos=qos, retain=retain)
            return True
        except MqttError as e:
            logger.error(f"Failed to publish to {topic}: {str(e)}")
            return False 

    def _topic_matches(self, subscription, topic):
        """Check if a topic matches a subscription pattern with MQTT wildcards."""
        # Direct match
        if subscription == topic:
            return True
            
        # Split into segments
        sub_parts = subscription.split('/')
        topic_parts = topic.split('/')
        
        # Single-level wildcard (+) and multi-level wildcard (#) handling
        for i, sub_part in enumerate(sub_parts):
            # Multi-level wildcard
            if sub_part == '#':
                return True
                
            # End of subscription pattern but not end of topic
            if i >= len(topic_parts):
                return False
                
            # Single-level wildcard or exact match
            if sub_part != '+' and sub_part != topic_parts[i]:
                return False
                
        # If we've processed all subscription parts and all topic parts
        return len(sub_parts) == len(topic_parts) 