#!/usr/bin/env python3
import sys
import os

# Add current directory to Python path
sys.path.append('.')

from app.config_manager import ConfigManager
from app.mqtt_client import MQTTClient

def main():
    # Initialize config manager
    config_manager = ConfigManager()
    
    # Get MQTT broker config
    mqtt_broker_config = config_manager.get_mqtt_broker_config()
    print(f"1. MQTT Broker Config from ConfigManager: {mqtt_broker_config}")
    
    # Check environment variables
    print(f"2. Environment variables:")
    print(f"   MQTT_BROKER_HOST = {os.getenv('MQTT_BROKER_HOST', 'not set')}")
    print(f"   MQTT_BROKER_PORT = {os.getenv('MQTT_BROKER_PORT', 'not set')}")
    print(f"   MQTT_USERNAME = {os.getenv('MQTT_USERNAME', 'not set')}")
    print(f"   MQTT_PASSWORD = {os.getenv('MQTT_PASSWORD', 'not set')}")
    
    # Initialize MQTT client with converted config
    mqtt_client = MQTTClient(mqtt_broker_config.model_dump())
    print(f"3. MQTT Client initialized with:")
    print(f"   host = {mqtt_client.host}")
    print(f"   port = {mqtt_client.port}")
    print(f"   client_id = {mqtt_client.client_id}")
    print(f"   username = {mqtt_client.username}")
    print(f"   password = {'*****' if mqtt_client.password else 'not set'}")
    
    # Check what happens when creating client args
    client_args = {
        'hostname': mqtt_client.host,
        'port': mqtt_client.port,
        'keepalive': mqtt_client.keepalive
    }
    
    if mqtt_client.username and mqtt_client.password:
        client_args.update({
            'username': mqtt_client.username,
            'password': mqtt_client.password
        })
    
    print(f"4. Client args that would be passed to aiomqtt.Client:")
    print(f"   {client_args}")

if __name__ == "__main__":
    main() 