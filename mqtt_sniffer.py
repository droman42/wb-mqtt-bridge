#!/usr/bin/env python3

import argparse
import asyncio
import logging
from datetime import datetime
import os
import json
import re
from typing import Optional, Set

import paho.mqtt.client as mqtt

class MqttSniffer:
    def __init__(
        self, 
        broker_host: str = "localhost", 
        broker_port: int = 1883,
        username: Optional[str] = None,
        password: Optional[str] = None,
        log_file: str = "mqtt_sniffer.log",
        topic_filter: str = "#",
        filter_substring: Optional[str] = None,
        av_devices_only: bool = False,
        av_devices_file: str = "wb-rules/av_devices.js"
    ):
        """
        Initialize the MQTT sniffer.
        
        Args:
            broker_host: MQTT broker hostname or IP
            broker_port: MQTT broker port
            username: Optional broker username
            password: Optional broker password
            log_file: Path to the log file
            topic_filter: MQTT topic filter (default "#" subscribes to all topics)
            filter_substring: Only report topics containing this substring (None = report all)
            av_devices_only: If True, only report topics for devices configured in av_devices.js
            av_devices_file: Path to the av_devices.js file
        """
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.username = username
        self.password = password
        self.log_file = log_file
        self.topic_filter = topic_filter
        self.filter_substring = filter_substring
        self.av_devices_only = av_devices_only
        self.av_devices_file = av_devices_file
        self.av_device_names: Set[str] = set()
        
        # Set up logging first
        self.setup_logging()
        
        # Load AV device names if filtering is enabled
        if self.av_devices_only:
            self.av_device_names = self.load_av_devices()
        
        # Initialize MQTT client
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        
        # Set credentials if provided
        if username and password:
            self.client.username_pw_set(username, password)
            
        self.logger.info(f"MQTT Sniffer initialized - will connect to {broker_host}:{broker_port}")
        if self.av_devices_only:
            self.logger.info(f"Configured to only report AV devices: {', '.join(sorted(self.av_device_names))}")
        elif self.filter_substring:
            self.logger.info(f"Configured to only report topics containing '{self.filter_substring}'")
        else:
            self.logger.info("Configured to report all topics")
        
    def setup_logging(self):
        """Configure logging to both console and file."""
        self.logger = logging.getLogger("mqtt_sniffer")
        self.logger.setLevel(logging.INFO)
        
        # Create formatter
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        
        # Create console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # Create file handler
        file_handler = logging.FileHandler(self.log_file)
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        
    def on_connect(self, client, userdata, flags, rc):
        """Callback for when the client connects to the broker."""
        if rc == 0:
            self.logger.info(f"Connected to MQTT broker at {self.broker_host}:{self.broker_port}")
            # Subscribe to all topics
            client.subscribe(self.topic_filter)
            self.logger.info(f"Subscribed to topic filter: {self.topic_filter}")
        else:
            connection_errors = {
                1: "Incorrect protocol version",
                2: "Invalid client identifier", 
                3: "Server unavailable",
                4: "Bad username or password",
                5: "Not authorized"
            }
            error = connection_errors.get(rc, f"Unknown error ({rc})")
            self.logger.error(f"Failed to connect: {error}")
            
    def on_message(self, client, userdata, msg):
        """Callback for when a message is received from the broker."""
        # Skip retained messages
        if msg.retain:
            self.logger.debug(f"Skipping retained message on topic {msg.topic}")
            return
            
        # Apply AV devices filter if enabled
        if self.av_devices_only and not self.is_av_device_topic(msg.topic):
            return
            
        # Apply substring filter if specified
        if self.filter_substring and self.filter_substring not in msg.topic:
            return
            
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        try:
            payload = msg.payload.decode('utf-8')
        except UnicodeDecodeError:
            payload = f"<binary data: {msg.payload.hex()}>"
            
        message = f"Topic: {msg.topic} | Payload: {payload}"
        self.logger.info(message)
            
    def start(self):
        """Connect to the broker and start the MQTT loop."""
        try:
            self.client.connect(self.broker_host, self.broker_port, 60)
            self.client.loop_start()
            return True
        except Exception as e:
            self.logger.error(f"Error connecting to broker: {str(e)}")
            return False
            
    def stop(self):
        """Disconnect from the broker and stop the MQTT loop."""
        self.client.loop_stop()
        self.client.disconnect()
        self.logger.info("MQTT Sniffer stopped")

    def load_av_devices(self) -> Set[str]:
        """
        Parse the av_devices.js file to extract device names.
        
        Returns:
            Set of device names configured in the av_devices.js file
        """
        device_names = set()
        
        if not os.path.exists(self.av_devices_file):
            self.logger.warning(f"AV devices file not found: {self.av_devices_file}")
            return device_names
        
        try:
            with open(self.av_devices_file, 'r') as f:
                content = f.read()
                
            # Use regex to find defineVirtualDevice calls and extract device names
            # Pattern: defineVirtualDevice("device_name", {
            pattern = r'defineVirtualDevice\s*\(\s*["\']([^"\']+)["\']'
            matches = re.findall(pattern, content)
            
            device_names = set(matches)
            self.logger.info(f"Loaded {len(device_names)} AV devices from {self.av_devices_file}")
            
        except Exception as e:
            self.logger.error(f"Error reading AV devices file: {str(e)}")
            
        return device_names

    def is_av_device_topic(self, topic: str) -> bool:
        """
        Check if a topic belongs to one of the configured AV devices.
        
        Args:
            topic: MQTT topic to check
            
        Returns:
            True if topic belongs to a configured AV device, False otherwise
        """
        # Expected topic format: /devices/{device_name}/controls/{control_name}
        # or similar variations
        parts = topic.strip('/').split('/')
        
        if len(parts) >= 2 and parts[0] == 'devices':
            device_name = parts[1]
            return device_name in self.av_device_names
            
        return False

def read_broker_config(config_path: str = "config/system.json") -> dict:
    """
    Read MQTT broker configuration from system.json file.
    
    Args:
        config_path: Path to the system.json configuration file
        
    Returns:
        Dictionary containing broker configuration parameters
    """
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
            broker_config = config.get('mqtt_broker', {})
            auth = broker_config.get('auth', {})
            
            return {
                'broker': broker_config.get('host', 'localhost'),
                'port': broker_config.get('port', 1883),
                'username': auth.get('username'),
                'password': auth.get('password')
            }
    except Exception as e:
        logging.error(f"Error reading config file: {str(e)}")
        return {}

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="MQTT Sniffer - Log all MQTT topic changes")
    parser.add_argument("-b", "--broker", default="localhost", 
                        help="MQTT broker address (default: localhost)")
    parser.add_argument("-p", "--port", type=int, default=1883,
                        help="MQTT broker port (default: 1883)")
    parser.add_argument("-u", "--username", help="MQTT broker username")
    parser.add_argument("-P", "--password", help="MQTT broker password")
    parser.add_argument("-l", "--log-file", default="mqtt_sniffer.log",
                        help="Path to log file (default: mqtt_sniffer.log)")
    parser.add_argument("-t", "--topic", default="#",
                        help="MQTT topic filter (default: # - all topics)")
    parser.add_argument("-f", "--filter-substring", 
                        help="Only report topics containing this substring")
    parser.add_argument("-c", "--config", action="store_true",
                        help="Use broker parameters from config/system.json")
    parser.add_argument("-d", "--av-devices-only", action="store_true",
                        help="Only report topics for devices configured in av_devices.js")
    parser.add_argument("-a", "--av-devices-file", default="wb-rules/av_devices.js",
                        help="Path to the av_devices.js file")
    return parser.parse_args()

async def main():
    """Main entry point for the MQTT sniffer."""
    args = parse_args()
    
    # If config flag is set, read parameters from config file
    if args.config:
        config = read_broker_config()
        if config:
            args.broker = config['broker']
            args.port = config['port']
            args.username = config['username']
            args.password = config['password']
            print("Using broker parameters from config/system.json")
    
    # Print parameter description if no parameters are specified
    if args.broker == "localhost" and args.port == 1883 and args.username is None and args.password is None and args.log_file == "mqtt_sniffer.log" and args.topic == "#":
        print("Using default parameters:")
        print(f"  Broker: {args.broker}")
        print(f"  Port: {args.port}")
        print(f"  Username: {args.username}")
        print(f"  Password: {'*****' if args.password else None}")
        print(f"  Log file: {args.log_file}")
        print(f"  Topic filter: {args.topic}")
        print(f"  Filter substring: {args.filter_substring}")
        print(f"  AV devices only: {args.av_devices_only}")
        print(f"  AV devices file: {args.av_devices_file}")
    
    sniffer = MqttSniffer(
        broker_host=args.broker,
        broker_port=args.port,
        username=args.username,
        password=args.password,
        log_file=args.log_file,
        topic_filter=args.topic,
        filter_substring=args.filter_substring,
        av_devices_only=args.av_devices_only,
        av_devices_file=args.av_devices_file
    )
    
    if sniffer.start():
        print(f"MQTT Sniffer running. Press Ctrl+C to stop. Logging to {args.log_file}")
        if args.filter_substring:
            print(f"Only topics containing '{args.filter_substring}' will be reported")
        elif args.av_devices_only:
            print(f"Only topics for devices: {', '.join(sorted(sniffer.av_device_names))}")
        else:
            print("All topics will be reported")
        try:
            # Keep the script running until interrupted
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("Stopping MQTT Sniffer...")
        finally:
            sniffer.stop()
    
if __name__ == "__main__":
    asyncio.run(main()) 