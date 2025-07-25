import asyncio
import logging
from typing import Dict, Any, Callable, Optional, List
import json

from aiomqtt import Client, MqttError, Will
from asyncio.exceptions import CancelledError

from wb_mqtt_bridge.infrastructure.maintenance.wirenboard_guard import SystemMaintenanceGuard
from wb_mqtt_bridge.domain.ports import MessageBusPort

logger = logging.getLogger(__name__)

class MQTTClient(MessageBusPort):
    """Asynchronous MQTT client for the web service."""
    
    def __init__(self, broker_config: Dict[str, Any], maintenance_guard: SystemMaintenanceGuard = None):
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

        self.guard = maintenance_guard
        
        # Last Will Testament configuration
        self._will_messages: List[Will] = []
        self._device_lwt_registry: Dict[str, List[str]] = {}  # device_id -> list of will topics
        
        # MQTT client
        self.client: Optional[Client] = None
        self.connected = False
        self.tasks: List[asyncio.Task] = []
        self._connection_event = asyncio.Event()
    
    async def wait_for_connection(self, timeout: float = 30.0) -> bool:
        """
        Wait for MQTT connection to be established.
        
        Args:
            timeout: Maximum time to wait for connection in seconds
            
        Returns:
            bool: True if connected within timeout, False otherwise
        """
        try:
            await asyncio.wait_for(self._connection_event.wait(), timeout=timeout)
            return self.connected
        except asyncio.TimeoutError:
            logger.error(f"MQTT connection timeout after {timeout} seconds")
            return False

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
    
    def add_will_message(self, device_id: str, topic: str, payload: str, qos: int = 0, retain: bool = True):
        """
        Add a Last Will Testament message for a device.
        
        Args:
            device_id: The device ID for tracking
            topic: The topic for the will message
            payload: The payload to send when connection is lost
            qos: Quality of Service level
            retain: Whether to retain the will message
        """
        will = Will(topic=topic, payload=payload, qos=qos, retain=retain)
        self._will_messages.append(will)
        
        # Track will topics per device for cleanup
        if device_id not in self._device_lwt_registry:
            self._device_lwt_registry[device_id] = []
        self._device_lwt_registry[device_id].append(topic)
        
        logger.debug(f"Added LWT for device {device_id}: {topic} -> '{payload}'")
    
    def remove_device_will_messages(self, device_id: str):
        """
        Remove all will messages for a specific device.
        
        Args:
            device_id: The device ID to remove will messages for
        """
        if device_id in self._device_lwt_registry:
            topics_to_remove = self._device_lwt_registry[device_id]
            
            # Remove will messages with matching topics
            self._will_messages = [
                will for will in self._will_messages 
                if will.topic not in topics_to_remove
            ]
            
            # Clear registry for this device
            del self._device_lwt_registry[device_id]
            
            logger.debug(f"Removed {len(topics_to_remove)} LWT messages for device {device_id}")
    
    def clear_all_will_messages(self):
        """Clear all Last Will Testament messages."""
        self._will_messages.clear()
        self._device_lwt_registry.clear()
        logger.debug("Cleared all LWT messages")
    
    async def _run_mqtt_client(self, client_args, topics_to_subscribe):
        """Run the MQTT client in an async context manager with the given topics."""
        max_retries = 5
        retry_delay = 5  # seconds
        retry_count = 0
        
        logger.info(f"Running MQTT client with args: {client_args}")
        
        while retry_count < max_retries:
            try:
                logger.info(f"Connecting to MQTT broker at {client_args.get('hostname', 'unknown')}:{client_args.get('port', 'unknown')} (attempt {retry_count + 1}/{max_retries})")
                
                # Add Last Will Testament messages to client args
                if self._will_messages:
                    # For aiomqtt, we can only set one will message per connection
                    # If multiple devices need LWT, we'll use a service-level LWT
                    # that signals overall service offline state
                    service_will = Will(
                        topic=f"/devices/{self.client_id}/meta/error",
                        payload="service_offline",
                        qos=1,
                        retain=True
                    )
                    client_args['will'] = service_will
                    logger.info(f"Set service-level LWT: {service_will.topic}")
                
                async with Client(**client_args) as client:
                    self.client = client
                    self.connected = True
                    self._connection_event.set()  # Signal that connection is established
                    logger.info(f"Connected to MQTT broker at {self.host}:{self.port}")
                    
                    # Subscribe to all topics
                    for topic in topics_to_subscribe:
                        await client.subscribe(topic)
                        logger.info(f"Subscribed to topic: {topic}")
                    
                    # Subscribe to guard topics
                    if self.guard is not None:
                        for topic in self.guard.subscription_topics():
                            await client.subscribe(topic)
                            logger.info(f"Subscribed to guard topic: {topic}")

                    # Process incoming messages
                    async for message in client.messages:
                        topic = message.topic.value
                        try:
                            # Check if the message is in the maintenance window
                            if self.guard is not None and self.guard.maintenance_started(topic):
                                logger.info(f"Skipping message on topic {topic} because it's in the maintenance window")
                                continue

                            # Skip processing of retained messages
                            if message.retain:
                                logger.debug(f"Skipping retained message on topic {topic}")
                                continue
                            
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
                        
                        # DEBUG: Enhanced logging for control topics (broader filtering)
                        if "controls" in topic or "processor" in topic or "tv" in topic or "soundbar" in topic:
                            logger.debug(f"[MQTT_DEBUG] Processing message: topic={topic}, payload='{payload}', timestamp={asyncio.get_event_loop().time()}")
                        
                        # Find handler for this exact topic
                        handler = self.message_handlers.get(topic)
                        if handler:
                            try:
                                # DEBUG: Log handler execution for control topics
                                if "controls" in topic or "processor" in topic or "tv" in topic or "soundbar" in topic:
                                    logger.debug(f"[MQTT_DEBUG] Executing exact topic handler for {topic} (payload='{payload}')")
                                await handler(topic, payload)
                            except Exception as e:
                                logger.error(f"Error in message handler for topic {topic}: {str(e)}")
                        else:
                            # If no exact match, check for wildcard handlers
                            for subscribed_topic, subscribed_handler in self.message_handlers.items():
                                if self._topic_matches(subscribed_topic, topic):
                                    try:
                                        # DEBUG: Log wildcard handler execution for control topics
                                        if "controls" in topic or "processor" in topic or "tv" in topic or "soundbar" in topic:
                                            logger.debug(f"[MQTT_DEBUG] Executing wildcard handler for {topic} (subscribed to {subscribed_topic}, payload='{payload}')")
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
                self._connection_event.clear()  # Clear connection event on MQTT error
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
                self._connection_event.clear()  # Clear connection event on unexpected error
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
                    self._connection_event.clear()  # Clear connection event on disconnect
    
    async def disconnect(self):
        """Disconnect the MQTT client and cancel all tasks."""
        for task in self.tasks:
            if not task.done():
                task.cancel()
        
        self.tasks = []
        self.connected = False
        self.client = None
        self._connection_event.clear()  # Clear connection event on disconnect
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

    async def subscribe(self, topic: str, callback: Callable[[str, str], None]) -> None:
        """Subscribe to a topic on the message bus.
        
        Args:
            topic: The topic pattern to subscribe to
            callback: Function to call when messages arrive (topic, payload)
        """
        # Register the callback for this topic
        self.message_handlers[topic] = callback
        
        # If we're already connected, subscribe to the topic
        if self.connected and self.client:
            try:
                await self.client.subscribe(topic)
                logger.debug(f"Subscribed to topic: {topic}")
            except MqttError as e:
                logger.error(f"Failed to subscribe to {topic}: {str(e)}")
        else:
            logger.debug(f"Queued subscription for topic: {topic} (not connected yet)")
    
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
    
    async def connect(self):
        """
        Connect to MQTT broker without subscribing to any topics.
        
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
            
            # Start the MQTT client task with no topics
            listener_task = asyncio.create_task(self._run_mqtt_client(client_args, []))
            self.tasks.append(listener_task)
            
            logger.info(f"MQTT client connecting to broker at {self.host}:{self.port}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start MQTT client: {str(e)}")
            return False 