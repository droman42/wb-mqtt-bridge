import os
import logging
import asyncio
import json
from devices.wirenboard_ir_device import WirenboardIRDevice
import uvicorn
from typing import Dict, Any, List, Optional
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel

from app.config_manager import ConfigManager
from app.device_manager import DeviceManager
from app.mqtt_client import MQTTClient
from app.schemas import (
    MQTTBrokerConfig,
    DeviceConfig,
    DeviceState,
    DeviceActionResponse,
    DeviceActionsResponse,
    SystemConfig,
    ErrorResponse,
    MQTTMessage,
    SystemInfo,
    ServiceInfo,
    DeviceAction,
    ReloadResponse,
    MQTTPublishResponse
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
        logger.info("Logging system initialized with daily rotation at level %s", log_level)
        
    except Exception as e:
        print(f"Error setting up logging: {str(e)}")
        raise

# Global instances
config_manager = None
device_manager = None
mqtt_client = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI application."""
    # Startup
    global config_manager, device_manager, mqtt_client
    
    # Initialize config manager
    config_manager = ConfigManager()
    
    # Setup logging with system config
    system_config = config_manager.get_system_config()
    log_file = system_config.log_file or 'logs/service.log'
    log_level = system_config.log_level
    setup_logging(log_file, log_level)
    
    logger = logging.getLogger(__name__)
    logger.info("Starting MQTT Web Service")
    
    # Initialize device manager and load devices
    device_manager = DeviceManager(mqtt_client=mqtt_client)
    await device_manager.load_device_modules()
    await device_manager.initialize_devices(config_manager.get_all_device_configs())
    
    # Initialize MQTT client
    mqtt_broker_config = system_config.mqtt_broker
    mqtt_client = MQTTClient({
        'host': mqtt_broker_config.host,
        'port': mqtt_broker_config.port,
        'client_id': mqtt_broker_config.client_id,
        'keepalive': mqtt_broker_config.keepalive,
        'auth': mqtt_broker_config.auth
    })
    
    # Get topics for all devices
    device_topics = {}
    for device_name, device_config in config_manager.get_all_device_configs().items():
        # Register message handler
        handler = device_manager.get_message_handler(device_name)
        if handler:
            mqtt_client.register_handler(device_name, handler)
        
        # Get topics
        topics = device_manager.get_device_topics(device_name)
        if topics:
            device_topics[device_name] = topics
    
    # Start MQTT client
    await mqtt_client.start(device_topics)
    logger.info("MQTT Web Service started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down MQTT Web Service")
    
    if device_manager:
        await device_manager.shutdown_devices()
    if mqtt_client:
        await mqtt_client.stop()
    
    logger.info("MQTT Web Service shutdown complete")

# Create the FastAPI app with lifespan
app = FastAPI(
    title="MQTT Web Service",
    description="A web service that manages MQTT devices",
    version="1.0.0",
    lifespan=lifespan
)

# API endpoints
@app.get("/", tags=["System"], response_model=ServiceInfo)
async def root():
    """Root endpoint - service information."""
    return ServiceInfo(
        service="MQTT Web Service",
        version="1.0.0",
        status="running"
    )

@app.get("/system", tags=["System"], response_model=SystemInfo)
async def get_system_info():
    """Get system information."""
    if not config_manager or not device_manager:
        raise HTTPException(status_code=503, detail="Service not fully initialized")
    
    return SystemInfo(
        version="1.0.0",
        mqtt_broker=config_manager.get_mqtt_broker_config(),
        devices=device_manager.get_all_devices()
    )

@app.post("/reload", tags=["System"], response_model=ReloadResponse)
async def reload_system(background_tasks: BackgroundTasks):
    """Reload configurations and device modules."""
    if not config_manager or not device_manager or not mqtt_client:
        raise HTTPException(status_code=503, detail="Service not fully initialized")
    
    logger = logging.getLogger(__name__)
    logger.info("Reloading system configuration")
    
    # Reload in the background to not block the response
    background_tasks.add_task(reload_system_task)
    
    return ReloadResponse(
        status="reload initiated",
        message="System reload has been initiated in the background"
    )

async def reload_system_task():
    """Background task to reload the system."""
    global mqtt_client
    logger = logging.getLogger(__name__)
    
    try:
        # Stop MQTT client
        await mqtt_client.disconnect()
        
        # Reload configs and device modules
        config_manager.reload_configs()
        await device_manager.load_device_modules()
        
        # Reconfigure MQTT client
        mqtt_broker_config = config_manager.get_mqtt_broker_config()
        new_mqtt_client = MQTTClient({
            'host': mqtt_broker_config.host,
            'port': mqtt_broker_config.port,
            'client_id': mqtt_broker_config.client_id,
            'keepalive': mqtt_broker_config.keepalive,
            'auth': mqtt_broker_config.auth
        })
        
        # Get topics for all devices
        device_topics = {}
        for device_name, device_config in config_manager.get_all_device_configs().items():
            # Register message handler
            handler = device_manager.get_message_handler(device_name)
            if handler:
                new_mqtt_client.register_handler(device_name, handler)
            
            # Get topics
            topics = device_manager.get_device_topics(device_name)
            if topics:
                device_topics[device_name] = topics
        
        # Start new MQTT client
        mqtt_client = new_mqtt_client
        await mqtt_client.connect()
        
        # Initialize devices
        await device_manager.initialize_devices()
        
        logger.info("System reload completed successfully")
    except Exception as e:
        logger.error(f"Error during system reload: {str(e)}")

@app.get("/devices/{device_id}", tags=["Devices"], response_model=DeviceState)
async def get_device(device_id: str):
    """Get information about a specific device."""
    logger = logging.getLogger(__name__)
    
    if not device_manager:
        raise HTTPException(status_code=503, detail="Service not fully initialized")
    
    try:
        device = device_manager.get_device(device_id)
        if not device:
            logger.error(f"Device {device_id} not found")
            raise HTTPException(status_code=404, detail=f"Device {device_id} not found")
        
        device_config = config_manager.get_device_config(device_id)
        
        if not device_config:
            logger.error(f"Configuration for device {device_id} not found")
            raise HTTPException(status_code=404, detail=f"Configuration for device {device_id} not found")
        
        # Safely get device name and state to handle potential errors
        try:
            device_name = device.get_name()
        except Exception as e:
            logger.warning(f"Error getting device name for {device_id}: {str(e)}")
            device_name = device_id
            
        try:
            device_state = device.get_state()
        except Exception as e:
            logger.warning(f"Error getting device state for {device_id}: {str(e)}")
            device_state = {"error": str(e)}
        
        return DeviceState(
            device_id=device_id,
            device_name=device_name,
            state=device_state,
            last_command=device_state.get("last_command"),
            error=device_state.get("error")
        )
    except Exception as e:
        logger.error(f"Error getting device {device_id}: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/devices/{device_id}/action", tags=["Devices"], response_model=DeviceActionResponse)
async def execute_device_action(
    device_id: str, 
    action: DeviceAction,
    background_tasks: BackgroundTasks
):
    """Execute an action on a specific device."""
    logger = logging.getLogger(__name__)
    if not device_manager:
        raise HTTPException(status_code=503, detail="Service not fully initialized")
    
    device = device_manager.get_device(device_id)
    if not device:
        raise HTTPException(status_code=404, detail=f"Device {device_id} not found")
    
    # Execute the action
    logger.info(f"Executing action {action.action} for device {device_id} with params {action.params}")
    result = await device.execute_action(action.action, action.params)
    
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
    
    return DeviceActionResponse(
        success=True,
        device_id=device_id,
        action=action.action,
        state=result["state"],
        message="Action executed successfully"
    )

# Add endpoint to get available actions for a device
@app.get("/devices/{device_id}/actions", tags=["Devices"], response_model=DeviceActionsResponse)
async def get_device_actions(device_id: str):
    """Get list of available actions for a device."""
    logger = logging.getLogger(__name__)
    if not device_manager:
        raise HTTPException(status_code=503, detail="Service not fully initialized")
    
    device = device_manager.get_device(device_id)
    if not device:
        raise HTTPException(status_code=404, detail=f"Device {device_id} not found")
    
    # Get device-specific actions
    try:
        actions = []
        if hasattr(device, 'get_available_commands') and callable(device.get_available_commands):
            commands = device.get_available_commands()
            logger.info(f"Retrieved {len(commands)} commands for device {device_id}")
            
            actions = [
                {"action": cmd_name, "description": cmd_config.get("description", "No description")}
                for cmd_name, cmd_config in commands.items()
            ]
        else:
            logger.warning(f"Device {device_id} does not implement get_available_commands method")
            
            # Try to get commands from device configuration if available
            if hasattr(device, 'config') and hasattr(device.config, 'commands'):
                commands = device.config.commands
                actions = [
                    {"action": cmd_name, "description": cmd_data.get("description", "No description")}
                    for cmd_name, cmd_data in commands.items()
                ]
        
        return DeviceActionsResponse(
            device_id=device_id,
            actions=actions
        )
    except Exception as e:
        logger.error(f"Error getting actions for device {device_id}: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/publish", tags=["MQTT"], response_model=MQTTPublishResponse, responses={
    503: {"model": ErrorResponse, "description": "Service not fully initialized"},
    500: {"model": ErrorResponse, "description": "Internal server error"}
})
async def publish_message(message: MQTTMessage, background_tasks: BackgroundTasks):
    """Publish a message to an MQTT topic.
    
    Args:
        message: The MQTT message to publish
        background_tasks: FastAPI background tasks manager
        
    Returns:
        MQTTPublishResponse with status of the operation
        
    Raises:
        HTTPException: If service is not initialized or an error occurs
    """
    logger = logging.getLogger(__name__)
    if not mqtt_client:
        raise HTTPException(
            status_code=503,
            detail="Service not fully initialized"
        )
    
    try:
        # Publish the message in the background
        background_tasks.add_task(
            mqtt_client.publish,
            message.topic,
            message.payload,
            message.qos,
            message.retain
        )
        
        return MQTTPublishResponse(
            success=True,
            message=f"Message queued for publishing to {message.topic}",
            topic=message.topic
        )
    except Exception as e:
        logger.error(f"Failed to publish message: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

async def start_service():
    """Start the web service and initialize all components."""
    try:
        global config_manager, device_manager, mqtt_client
        
        # Initialize configuration manager
        config_manager = ConfigManager()
        await config_manager.load_config()
        
        # Initialize MQTT client
        mqtt_client = MQTTClient({
            'host': config_manager.get_mqtt_broker_host(),
            'port': config_manager.get_mqtt_broker_port(),
            'client_id': config_manager.get_mqtt_client_id(),
            'keepalive': config_manager.get_mqtt_keepalive(),
            'auth': {
                'username': config_manager.get_mqtt_username(),
                'password': config_manager.get_mqtt_password()
            }
        })
        
        # Initialize device manager with MQTT client
        device_manager = DeviceManager(mqtt_client=mqtt_client)
        await device_manager.load_device_modules()
        
        # Get device configurations
        device_configs = config_manager.get_device_configs()
        await device_manager.initialize_devices(device_configs)
        
        # Register message handlers for each device
        for device_id, device in device_manager.devices.items():
            handler = device_manager.get_message_handler(device_id)
            if handler:
                mqtt_client.register_handler(device_id, handler)
        
        # Get all device topics
        device_topics = {}
        for device_id in device_manager.get_all_devices():
            topics = device_manager.get_device_topics(device_id)
            if topics:
                device_topics[device_id] = topics
        
        # Start MQTT client with device topics
        await mqtt_client.start(device_topics)
        
        logger.info("Service started successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to start service: {str(e)}")
        return False
