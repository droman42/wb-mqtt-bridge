import os
import logging
import asyncio
import json
from devices.wirenboard_ir_device import WirenboardIRDevice
import uvicorn
from typing import Dict, Any, List, Optional
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

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
    """Configure the logging system with daily rotation."""
    try:
        # Create logs directory if it doesn't exist
        log_dir = os.path.dirname(log_file)
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        
        # Set up logging format
        log_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Create timed rotating file handler
        file_handler = TimedRotatingFileHandler(
            filename=log_file,
            when='midnight',  # Rotate at midnight
            interval=1,       # One day interval
            backupCount=30,   # Keep 30 days of logs
            encoding='utf-8'
        )
        
        # Set custom suffix for rotated files
        file_handler.suffix = "%Y%m%d.log"
        file_handler.setFormatter(log_formatter)
        
        # Create console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(log_formatter)
        
        # Get root logger
        root_logger = logging.getLogger()
        
        # Remove any existing handlers
        root_logger.handlers = []
        
        # Add our handlers
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)
        
        # Set log level
        numeric_level = getattr(logging, log_level.upper(), logging.INFO)
        root_logger.setLevel(numeric_level)
        
        logger = logging.getLogger(__name__)
        logger.info("Logging system initialized with daily rotation")
        
    except Exception as e:
        print(f"Error setting up logging: {str(e)}")
        raise

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
    
    # Setup logging with system config
    system_config = config_manager.get_system_config()
    log_file = system_config.get('log_file', 'logs/service.log')
    log_level = system_config.get('log_level', 'INFO')
    setup_logging(log_file, log_level)
    
    logger = logging.getLogger(__name__)
    logger.info("Starting MQTT Web Service")
    
    # Initialize device manager and load devices
    device_manager = DeviceManager()
    await device_manager.load_device_modules()
    await device_manager.initialize_devices(config_manager.get_all_device_configs())
    
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
    
    if device_manager:
        await device_manager.shutdown_devices()
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

class DeviceAction(BaseModel):
    """Model for device action requests."""
    button: str
    params: Optional[Dict[str, Any]] = None

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
        await device_manager.load_device_modules()
        
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
async def get_device(device_id: str):
    """Get information about a specific device."""
    if not device_manager:
        raise HTTPException(status_code=503, detail="Service not fully initialized")
    
    device = device_manager.get_device(device_id)
    if not device:
        raise HTTPException(status_code=404, detail=f"Device {device_id} not found")
    
    device_config = config_manager.get_device_config(device_id)
    return {
        "device_id": device_id,
        "device_name": device.get_name(),
        "device_class": device_config.get('device_class'),
        "config": device_config,
        "state": device.get_state()
    }

@app.post("/devices/{device_id}/action", tags=["Devices"])
async def execute_device_action(
    device_id: str, 
    action: DeviceAction,
    background_tasks: BackgroundTasks
):
    """Execute an action on a specific device."""
    if not device_manager:
        raise HTTPException(status_code=503, detail="Service not fully initialized")
    
    device = device_manager.get_device(device_id)
    if not device:
        raise HTTPException(status_code=404, detail=f"Device {device_id} not found")
    
    # Execute the action
    result = await device.execute_action(action.button, action.params)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    
    # If there's an MQTT command to be published, do it in the background
    if result.get("mqtt_command"):
        mqtt_cmd = result["mqtt_command"]
        background_tasks.add_task(
            mqtt_client.publish,
            mqtt_cmd["topic"],
            mqtt_cmd["payload"]
        )
    
    return {
        "device_id": device_id,
        "button": action.button,
        "state": result["state"],
        "message": "Action executed successfully"
    }

# Add endpoint to get available actions for a device
@app.get("/devices/{device_id}/actions", tags=["Devices"])
async def get_device_actions(device_id: str):
    """Get list of available actions for a device."""
    if not device_manager:
        raise HTTPException(status_code=503, detail="Service not fully initialized")
    
    device = device_manager.get_device(device_id)
    if not device:
        raise HTTPException(status_code=404, detail=f"Device {device_id} not found")
    
    # For WirenboardIRDevice, get commands from config
    if isinstance(device, WirenboardIRDevice):
        commands = device.get_available_commands()
        return {
            "device_id": device_id,
            "actions": [
                {
                    "button": cmd_config["button"],
                    "description": cmd_config.get("description", "No description")
                }
                for cmd_config in commands.values()
            ]
        }
    
    # For other devices, return empty list or device-specific actions
    return {
        "device_id": device_id,
        "actions": []
    }
