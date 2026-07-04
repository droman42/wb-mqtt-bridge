import logging

from fastapi import APIRouter, HTTPException, BackgroundTasks

from wb_mqtt_bridge.presentation.api.catalog import build_catalog
from wb_mqtt_bridge.presentation.api.schemas import (
    CatalogResponse,
    SystemConfigResponse,
    SystemInfo,
    ServiceInfo,
    ReloadResponse,
)
from wb_mqtt_bridge.infrastructure.mqtt.client import MQTTClient

# §P3.7 #17. Retained MQTT topic Irene subscribes to; the payload is the current
# `/system/catalog` version hash. Bumped on /reload (after configs + devices reload).
CATALOG_VERSION_TOPIC = "bridge/catalog/version"

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
scenario_proxy = None  # ScenarioProxy (SCN-6)

def initialize(cfg_manager, dev_manager, mqt_client, state_st=None, scenario_mgr=None, room_mgr=None, scenario_prx=None):
    """Initialize global references needed by router endpoints."""
    global config_manager, device_manager, mqtt_client, state_store, scenario_manager, room_manager, scenario_proxy
    config_manager = cfg_manager
    device_manager = dev_manager
    mqtt_client = mqt_client
    state_store = state_st  # Set the state_store reference
    scenario_manager = scenario_mgr
    room_manager = room_mgr
    scenario_proxy = scenario_prx

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

@router.get("/config/system", response_model=SystemConfigResponse)
async def get_system_config():
    """Get system configuration."""
    if not config_manager:
        raise HTTPException(status_code=503, detail="Service not fully initialized")

    try:
        # Adapt the infra SystemConfig to the presentation DTO so the wire shape isn't
        # a leak of internal config layout. from_attributes=True drives the conversion,
        # nested DTOs included.
        return SystemConfigResponse.model_validate(config_manager.get_system_config())
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error retrieving system config: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/system/catalog", response_model=CatalogResponse)
async def get_system_catalog():
    """Voice-friendly catalog of devices + rooms (§P3.7 voice-integration slice #17).

    Flat capability-shaped projection of the whole house for any non-UI consumer
    (Irene first). All locales for both rooms and devices. The response carries a
    `version` (short content hash) so callers can subscribe to retained
    `bridge/catalog/version` MQTT and only re-fetch when it differs from the last
    seen one. Stable independent of insertion order: rooms + devices are sorted by
    id before hashing so the same content always hashes to the same value.

    NOT the Layer-3 layout manifest -- that one is UI-shaped (panels, sliders,
    positions). The catalog is the contract for capability-aware callers.
    """
    if not device_manager or not room_manager:
        raise HTTPException(status_code=503, detail="Service not fully initialized")
    return build_catalog(device_manager, room_manager, scenario_proxy)


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
                
                # Initialize devices with typed configs. Wire the shared MQTT client BEFORE
                # `initialize_devices` so WB-passthrough devices' setup() can register their
                # state_topic + meta/error subscriptions on the right client (see §P3.7 #18
                # postmortem). Existing AV drivers don't use mqtt_client in setup() so this
                # is a no-op for them.
                device_manager.config_manager = config_manager
                device_manager.set_runtime_services(mqtt_client=mqtt_client)
                await device_manager.initialize_devices(config_manager.get_all_device_configs())

                # Safety-net assignment (already set in the constructor; idempotent).
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
                
            # §P3.7 #17: bump the retained catalog version so Irene's catalog consumer
            # refetches. Done at the END so we publish the post-reload catalog hash --
            # the broker carries it retained so late-joining subscribers still see it.
            if mqtt_client and device_manager and room_manager:
                try:
                    catalog = build_catalog(device_manager, room_manager, scenario_proxy)
                    await mqtt_client.publish(
                        CATALOG_VERSION_TOPIC, catalog.version, retain=True
                    )
                    logger.info(
                        f"Published catalog version {catalog.version!r} to "
                        f"{CATALOG_VERSION_TOPIC} (retained) -- catalog-aware "
                        f"subscribers can refetch."
                    )
                except Exception as e:  # never let the nudge mask a successful reload
                    logger.warning(f"Failed to bump catalog version on /reload: {e}")

            logger.info("System reload completed successfully")
    except Exception as e:
        logger.error(f"Error during system reload: {str(e)}")
        import traceback
        logger.error(traceback.format_exc()) 