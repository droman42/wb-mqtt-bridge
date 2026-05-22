import logging

from fastapi import APIRouter, HTTPException, BackgroundTasks

from wb_mqtt_bridge.presentation.api.schemas import (
    SystemConfig,
    SystemInfo,
    ServiceInfo,
    ReloadResponse
)
from wb_mqtt_bridge.infrastructure.mqtt.client import MQTTClient

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
scenario_manager = None
room_manager = None

def initialize(cfg_manager, dev_manager, mqt_client, state_st=None, scenario_mgr=None, room_mgr=None):
    """Initialize global references needed by router endpoints."""
    global config_manager, device_manager, mqtt_client, state_store, scenario_manager, room_manager
    config_manager = cfg_manager
    device_manager = dev_manager
    mqtt_client = mqt_client
    state_store = state_st  # Set the state_store reference
    scenario_manager = scenario_mgr
    room_manager = room_mgr

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
    
    # Get scenarios list
    scenarios = []
    if scenario_manager:
        scenarios = list(scenario_manager.scenario_definitions.keys())
    
    # Get rooms list  
    rooms = []
    if room_manager:
        room_definitions = room_manager.list()
        rooms = [room.room_id for room in room_definitions]
    
    return SystemInfo(
        version="1.0.0",
        mqtt_broker=config_manager.get_mqtt_broker_config(),
        devices=device_manager.get_all_devices(),
        scenarios=scenarios,
        rooms=rooms
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
                
                # Wait for MQTT connection to be fully established
                logger.info("Waiting for MQTT connection to be established after reload...")
                connection_success = await mqtt_client.wait_for_connection(timeout=30.0)
                if not connection_success:
                    logger.error("Failed to establish MQTT connection within timeout after reload - WB emulation will be skipped")
                else:
                    logger.info("MQTT connection established successfully after reload")
                    
                    # Now that MQTT is connected, set up Wirenboard virtual device emulation for all devices
                    logger.info("Setting up Wirenboard virtual device emulation after reload...")
                    for device_id, device in device_manager.devices.items():
                        try:
                            await device.setup_wb_emulation_if_enabled()
                            logger.debug(f"WB emulation setup completed for device {device_id} after reload")
                        except Exception as e:
                            logger.error(f"Failed to setup WB emulation for device {device_id} after reload: {str(e)}")
                
            logger.info("System reload completed successfully")
    except Exception as e:
        logger.error(f"Error during system reload: {str(e)}")
        import traceback
        logger.error(traceback.format_exc()) 