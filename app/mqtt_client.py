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
    
    async def connect_and_subscribe(self, topic_handlers: Dict[str, Callable]):
        """
        Connect to MQTT broker and subscribe to topics with their respective handlers.
        
        Args:
            topic_handlers: Dictionary mapping topics to handler functions
            
        Returns:
            bool: True if connection was successful, False otherwise
        """
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
            
            # Store topic handlers
            for topic, handler in topic_handlers.items():
                logger.debug(f"Registered handler for topic: {topic}")
                self.message_handlers[topic] = handler
            
            # Start the MQTT client task
            listener_task = asyncio.create_task(self._run_mqtt_client(client_args, list(topic_handlers.keys())))
            self.tasks.append(listener_task)
            
            logger.info(f"MQTT client connecting to broker at {self.host}:{self.port}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start MQTT client: {str(e)}")
            return False
    
    async def _run_mqtt_client(self, client_args, topics_to_subscribe):
        """Run the MQTT client in an async context manager with the given topics."""
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
                    
                    # Subscribe to all topics
                    for topic in topics_to_subscribe:
                        await client.subscribe(topic)
                        logger.info(f"Subscribed to topic: {topic}")
                    
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
                        
                        # Find handler for this exact topic
                        handler = self.message_handlers.get(topic)
                        if handler:
                            try:
                                await handler(topic, payload)
                            except Exception as e:
                                logger.error(f"Error in message handler for topic {topic}: {str(e)}")
                        else:
                            # If no exact match, check for wildcard handlers
                            for subscribed_topic, subscribed_handler in self.message_handlers.items():
                                if self._topic_matches(subscribed_topic, topic):
                                    try:
                                        await subscribed_handler(topic, payload)
                                    except Exception as e:
                                        logger.error(f"Error in wildcard handler for topic {topic} (subscribed to {subscribed_topic}): {str(e)}")
                
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
            except CancelledError:
                logger.info("MQTT client task cancelled")
                break
            except Exception as e:
                logger.error(f"Unexpected error in MQTT client: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())
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
    
    async def disconnect(self):
        """Disconnect the MQTT client and cancel all tasks."""
        for task in self.tasks:
            if not task.done():
                task.cancel()
        
        self.tasks = []
        self.connected = False
        self.client = None
        logger.info("MQTT client disconnected")
    
    # For backward compatibility
    async def stop(self):
        """Stop the MQTT client (backward compatibility method)."""
        logger.warning("MQTTClient.stop() is deprecated, use disconnect() instead")
        await self.disconnect()
    
    # For backward compatibility
    async def start(self, device_topics: Dict[str, List[str]]):
        """Start the MQTT client with device topics (backward compatibility method)."""
        logger.warning("MQTTClient.start() is deprecated, use connect_and_subscribe() instead")
        
        topic_handlers = {}
        for device_name, topics in device_topics.items():
            handler = self.message_handlers.get(device_name)
            if handler:
                for topic in topics:
                    topic_handlers[topic] = handler
        
        return await self.connect_and_subscribe(topic_handlers)
    
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
            # Handle None payload by defaulting to 1
            if payload is None:
                payload = 1
            
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
        """Check if topic matches subscription pattern (with + and # wildcards)."""
        # Split subscription pattern into segments
        sub_segments = subscription.split('/')
        topic_segments = topic.split('/')
        
        # If subscription ends with #, it matches everything after
        if sub_segments[-1] == '#':
            # Check if all previous segments match
            return self._segments_match(sub_segments[:-1], topic_segments[:len(sub_segments)-1])
        
        # If segments count doesn't match and there's no # wildcard, can't match
        if len(sub_segments) != len(topic_segments):
            return False
            
        # Check segment by segment
        return self._segments_match(sub_segments, topic_segments)
    
    def _segments_match(self, sub_segments, topic_segments):
        """Helper method to check if topic segments match subscription segments."""
        if len(sub_segments) != len(topic_segments):
            return False
            
        for i in range(len(sub_segments)):
            # + matches any single segment
            if sub_segments[i] == '+':
                continue
            # Exact match required
            if sub_segments[i] != topic_segments[i]:
                return False
                
        return True 