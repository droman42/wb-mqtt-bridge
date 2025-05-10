import logging
import asyncio
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from app.schemas import (
    SystemConfig,
    SystemInfo,
    ServiceInfo,
    ReloadResponse
)
from app.mqtt_client import MQTTClient

# Create router with appropriate prefix and tags
router = APIRouter(
    prefix="",
    tags=["System"]
)

# Global references that will be set during initialization
config_manager = None
device_manager = None
mqtt_client = None
state_store = None  # Keep reference to state_store

def initialize(cfg_manager, dev_manager, mqt_client, state_st=None):
    """Initialize global references needed by router endpoints."""
    global config_manager, device_manager, mqtt_client, state_store
    config_manager = cfg_manager
    device_manager = dev_manager
    mqtt_client = mqt_client
    state_store = state_st  # Set the state_store reference

@router.get("/", response_model=ServiceInfo)
async def root():
    """Root endpoint - service information."""
    return ServiceInfo(
        service="MQTT Web Service",
        version="1.0.0",
        status="running"
    )

@router.get("/system", response_model=SystemInfo)
async def get_system_info():
    """Get system information."""
    if not config_manager or not device_manager:
        raise HTTPException(status_code=503, detail="Service not fully initialized")
    
    return SystemInfo(
        version="1.0.0",
        mqtt_broker=config_manager.get_mqtt_broker_config(),
        devices=device_manager.get_all_devices()
    )

@router.get("/config/system", response_model=SystemConfig)
async def get_system_config():
    """Get system configuration."""
    if not config_manager:
        raise HTTPException(status_code=503, detail="Service not fully initialized")
    
    try:
        system_config = config_manager.get_system_config()
        return system_config
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error retrieving system config: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/reload", response_model=ReloadResponse)
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
        if mqtt_client:
            await mqtt_client.stop()
        
        # Reload configs and device modules
        if config_manager:
            config_manager.reload_configs()
        
        if device_manager:
            await device_manager.load_device_modules()
        
        # Reconfigure MQTT client
        if config_manager:
            mqtt_broker_config = config_manager.get_mqtt_broker_config()
            new_mqtt_client = MQTTClient({
                'host': mqtt_broker_config.host,
                'port': mqtt_broker_config.port,
                'client_id': mqtt_broker_config.client_id,
                'keepalive': mqtt_broker_config.keepalive,
                'auth': mqtt_broker_config.auth
            })
            
            # Start the MQTT client first, then initialize devices
            mqtt_client = new_mqtt_client
            
            # Initialize devices with clean start
            if device_manager and config_manager:
                # Shutdown any existing devices
                await device_manager.shutdown_devices()
                
                # Initialize devices with typed configs
                device_manager.config_manager = config_manager
                await device_manager.initialize_devices(config_manager.get_all_device_configs())
                
                # Update MQTT client for each device
                for device_id, device in device_manager.devices.items():
                    device.mqtt_client = mqtt_client
                
                # Create topic to handler mapping
                topic_handlers = {}
                for device_id, device in device_manager.devices.items():
                    # Get message handler for this device
                    handler = device_manager.get_message_handler(device_id)
                    if handler:
                        # Add topic-handler mappings for this device's topics
                        for topic in device.subscribe_topics():
                            topic_handlers[topic] = handler
                
                # Connect to MQTT broker with topics and handlers
                if topic_handlers:
                    await mqtt_client.connect_and_subscribe(topic_handlers)
                else:
                    # Connect without topics if no handlers available
                    await mqtt_client.connect()
                
            logger.info("System reload completed successfully")
    except Exception as e:
        logger.error(f"Error during system reload: {str(e)}")
        import traceback
        logger.error(traceback.format_exc()) 