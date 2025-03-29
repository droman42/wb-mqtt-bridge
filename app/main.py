import os
import logging
import asyncio
import json
import uvicorn
from typing import Dict, Any, List

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel

from app.config_manager import ConfigManager
from app.device_manager import DeviceManager
from app.mqtt_client import MQTTClient

# Create the FastAPI app
app = FastAPI(
    title="MQTT Web Service",
    description="A web service that manages MQTT devices",
    version="1.0.0"
)

# Setup logging
def setup_logging(log_file: str, log_level: str):
    """Configure the logging system."""
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )

# Global instances
config_manager = None
device_manager = None
mqtt_client = None

@app.on_event("startup")
async def startup_event():
    """Initialize the application on startup."""
    global config_manager, device_manager, mqtt_client
    
    # Initialize config manager
    config_manager = ConfigManager()
    
    # Setup logging
    system_config = config_manager.get_system_config()
    log_file = system_config.get('log_file', 'logs/service.log')
    log_level = system_config.get('log_level', 'INFO')
    setup_logging(log_file, log_level)
    
    logger = logging.getLogger(__name__)
    logger.info("Starting MQTT Web Service")
    
    # Initialize device manager
    device_manager = DeviceManager()
    device_manager.load_device_modules()
    
    # Initialize MQTT client
    mqtt_broker_config = config_manager.get_mqtt_broker_config()
    mqtt_client = MQTTClient(mqtt_broker_config)
    
    # Get topics for all devices
    device_topics = {}
    for device_name, device_config in config_manager.get_all_device_configs().items():
        # Register message handler
        handler = device_manager.get_message_handler(device_name)
        if handler:
            mqtt_client.register_handler(device_name, handler)
        
        # Get topics
        topics = device_manager.get_device_topics(device_name, device_config)
        if topics:
            device_topics[device_name] = topics
    
    # Start MQTT client
    await mqtt_client.start(device_topics)
    logger.info("MQTT Web Service started successfully")

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown."""
    logger = logging.getLogger(__name__)
    logger.info("Shutting down MQTT Web Service")
    
    if mqtt_client:
        await mqtt_client.stop()
    
    logger.info("MQTT Web Service shutdown complete")

# API models
class MQTTMessage(BaseModel):
    topic: str
    payload: Any
    qos: int = 0
    retain: bool = False

class SystemInfo(BaseModel):
    version: str = "1.0.0"
    mqtt_broker: Dict[str, Any]
    devices: List[str]

# API endpoints
@app.get("/", tags=["System"])
async def root():
    """Root endpoint - service information."""
    return {
        "service": "MQTT Web Service",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/system", tags=["System"], response_model=SystemInfo)
async def get_system_info():
    """Get system information."""
    if not config_manager or not device_manager:
        raise HTTPException(status_code=503, detail="Service not fully initialized")
    
    return {
        "version": "1.0.0",
        "mqtt_broker": config_manager.get_mqtt_broker_config(),
        "devices": device_manager.get_all_devices()
    }

@app.post("/reload", tags=["System"])
async def reload_system(background_tasks: BackgroundTasks):
    """Reload configurations and device modules."""
    if not config_manager or not device_manager or not mqtt_client:
        raise HTTPException(status_code=503, detail="Service not fully initialized")
    
    logger = logging.getLogger(__name__)
    logger.info("Reloading system configuration")
    
    # Reload in the background to not block the response
    background_tasks.add_task(reload_system_task)
    
    return {"status": "reload initiated"}

async def reload_system_task():
    """Background task to reload the system."""
    logger = logging.getLogger(__name__)
    
    try:
        # Stop MQTT client
        await mqtt_client.stop()
        
        # Reload configs and device modules
        config_manager.reload_configs()
        device_manager.reload_device_modules()
        
        # Reconfigure MQTT client
        mqtt_broker_config = config_manager.get_mqtt_broker_config()
        new_mqtt_client = MQTTClient(mqtt_broker_config)
        
        # Get topics for all devices
        device_topics = {}
        for device_name, device_config in config_manager.get_all_device_configs().items():
            # Register message handler
            handler = device_manager.get_message_handler(device_name)
            if handler:
                new_mqtt_client.register_handler(device_name, handler)
            
            # Get topics
            topics = device_manager.get_device_topics(device_name, device_config)
            if topics:
                device_topics[device_name] = topics
        
        # Start new MQTT client
        await new_mqtt_client.start(device_topics)
        
        # Replace old client with new one
        global mqtt_client
        mqtt_client = new_mqtt_client
        
        logger.info("System reload completed successfully")
    except Exception as e:
        logger.error(f"Error during system reload: {str(e)}")

@app.get("/devices", tags=["Devices"])
async def get_devices():
    """Get list of all devices."""
    if not device_manager:
        raise HTTPException(status_code=503, detail="Service not fully initialized")
    
    devices = []
    for device_name in device_manager.get_all_devices():
        config = config_manager.get_device_config(device_name)
        devices.append({
            "name": device_name,
            "config": config
        })
    
    return {"devices": devices}

@app.get("/devices/{device_name}", tags=["Devices"])
async def get_device(device_name: str):
    """Get information about a specific device."""
    if not config_manager:
        raise HTTPException(status_code=503, detail="Service not fully initialized")
    
    device_config = config_manager.get_device_config(device_name)
    if not device_config:
        raise HTTPException(status_code=404, detail=f"Device {device_name} not found")
    
    return {"device": device_name, "config": device_config}

@app.post("/publish", tags=["MQTT"])
async def publish_message(message: MQTTMessage):
    """Publish a message to an MQTT topic."""
    if not mqtt_client:
        raise HTTPException(status_code=503, detail="MQTT client not initialized")
    
    success = await mqtt_client.publish(
        message.topic,
        message.payload,
        qos=message.qos,
        retain=message.retain
    )
    
    if success:
        return {"status": "published", "topic": message.topic}
    else:
        raise HTTPException(status_code=500, detail="Failed to publish message")

# Start the application if running directly
if __name__ == "__main__":
    # Load config to get web service settings
    temp_config_manager = ConfigManager()
    system_config = temp_config_manager.get_system_config()
    web_config = system_config.get('web_service', {})
    
    host = web_config.get('host', '0.0.0.0')
    port = web_config.get('port', 8000)
    
    uvicorn.run("app.main:app", host=host, port=port, reload=True) 