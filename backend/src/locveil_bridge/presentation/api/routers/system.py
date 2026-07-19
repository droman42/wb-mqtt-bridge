import logging

from fastapi import APIRouter, HTTPException, BackgroundTasks

from locveil_bridge.presentation.api.catalog import build_catalog
from locveil_bridge.presentation.api.schemas import (
    CatalogResponse,
    SystemConfigResponse,
    SystemInfo,
    ServiceInfo,
    ReloadResponse,
)

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
# CORE-1: the /reload background work lives in the app layer
# (`app/reload_service.py`); this router only schedules it. Wired by the
# composition root via set_reload_service().
reload_service = None

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

def set_reload_service(service):
    """Wire the app-layer reload service (CORE-1). Separate from initialize()
    because the service is constructed after the routers are wired — it needs
    the composition root's rewire hook, which needs the routers importable."""
    global reload_service
    reload_service = service

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
    """Voice-friendly catalog of devices + rooms.

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
    if not config_manager or not device_manager or not reload_service:
        raise HTTPException(status_code=503, detail="Service not fully initialized")

    logger = logging.getLogger(__name__)
    logger.info("Reloading system configuration")

    # Reload in the background to not block the response (CORE-1: the sequence
    # itself lives in the app layer -- app/reload_service.py).
    background_tasks.add_task(reload_service.reload)

    return ReloadResponse(
        status="reload initiated",
        message="System reload has been initiated in the background"
    )
