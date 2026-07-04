import os
import logging
import asyncio
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Any, Callable, cast

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from wb_mqtt_bridge.domain.devices.models import (
    BaseDeviceState,
    KitchenHoodState,
    LgTvState,
    WirenboardIRState,
    RevoxA77ReelToReelState,
    AppleTVState,
    AuralicDeviceState,
    EmotivaXMC2State,
)
from wb_mqtt_bridge.infrastructure.config.manager import ConfigManager
from wb_mqtt_bridge.domain.devices.service import DeviceManager
from wb_mqtt_bridge.infrastructure.mqtt.client import MQTTClient
from wb_mqtt_bridge.infrastructure.persistence.sqlite import SQLiteStateStore
from wb_mqtt_bridge.infrastructure.wb_device.service import WBVirtualDeviceService
from wb_mqtt_bridge.domain.rooms.service import RoomManager
from wb_mqtt_bridge.domain.scenarios.service import ScenarioManager
from wb_mqtt_bridge.domain.scenarios.proxy import ScenarioProxy
from wb_mqtt_bridge.infrastructure.scenarios.wb_adapter import ScenarioWBAdapter
from wb_mqtt_bridge.infrastructure.capabilities.loader import attach_capability_maps, validate_command_exposure
from wb_mqtt_bridge.infrastructure.maintenance.wirenboard_guard import WirenboardMaintenanceGuard

# Import routers
from wb_mqtt_bridge.presentation.api.routers import (
    system, devices, mqtt, scenarios, rooms, state, events
)
from wb_mqtt_bridge.presentation.api.sse_manager import sse_manager

from wb_mqtt_bridge.__version__ import __version__


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


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    
    # Global instances
    config_manager = None
    device_manager = None
    mqtt_client = None
    state_store = None
    
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Lifespan context manager for FastAPI application."""
        # Startup
        nonlocal config_manager, device_manager, mqtt_client, state_store
        
        # Initialize config manager
        config_manager = ConfigManager()
        
        # Set app title from config
        service_name = config_manager.get_service_name()
        app.title = service_name
        
        # Setup logging with system config
        system_config = config_manager.get_system_config()
        log_file = system_config.log_file or 'logs/service.log'
        log_level = system_config.log_level
        setup_logging(log_file, log_level)
        
        # Diagnostic: Check what level was actually set
        root_logger = logging.getLogger()
        print(f"DEBUG: After setup_logging - Root logger level: {root_logger.level} (requested: {log_level})")
        
        # Check for log level override from environment
        override_log_level = os.getenv('OVERRIDE_LOG_LEVEL')
        if override_log_level:
            override_numeric_level = getattr(logging, override_log_level.upper(), None)
            if override_numeric_level is not None:
                root_logger = logging.getLogger()
                root_logger.setLevel(override_numeric_level)
                print(f"Log level overridden by environment variable: {override_log_level}")
            else:
                print(f"Warning: Invalid log level override '{override_log_level}', ignoring")
        
        # Apply logger-specific configuration
        if system_config.loggers:
            for logger_name, logger_level in system_config.loggers.items():
                specific_logger = logging.getLogger(logger_name)
                specific_level = getattr(logging, logger_level.upper(), logging.INFO)
                specific_logger.setLevel(specific_level)
                logging.info(f"Set logger {logger_name} to level {logger_level}")
        
        logger = logging.getLogger(__name__)
        logger.info("Starting MQTT Web Service")
        
        # Initialize state store after config but before device manager
        db_path = Path(system_config.persistence.db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        state_store = SQLiteStateStore(db_path=str(db_path))
        await state_store.initialize()
        logger.info(f"State persistence initialized with SQLite at {db_path}")
        
        # Initialize MQTT client first
        mqtt_broker_config = system_config.mqtt_broker
        
        # Check if maintenance is enabled and create guard if needed
        maintenance_guard = None
        if config_manager.is_maintenance_enabled():
            maintenance_config = config_manager.get_maintenance_config()
            assert maintenance_config is not None, "is_maintenance_enabled() implies non-None config"
            logger.info(f"Maintenance is enabled - creating WirenboardMaintenanceGuard with duration={maintenance_config.duration}s, topic={maintenance_config.topic}")
            maintenance_guard = WirenboardMaintenanceGuard(
                duration=maintenance_config.duration,
                topic=maintenance_config.topic
            )
        else:
            logger.info("Maintenance is disabled - no maintenance guard will be used")
            
        mqtt_client = MQTTClient({
            'host': mqtt_broker_config.host,
            'port': mqtt_broker_config.port,
            'client_id': mqtt_broker_config.client_id,
            'keepalive': mqtt_broker_config.keepalive,
            'auth': mqtt_broker_config.auth
        }, maintenance_guard=maintenance_guard)
        
        # Initialize device manager with state repository
        device_manager = DeviceManager(state_repository=state_store)
        await device_manager.load_device_modules()
        
        # Log the number of typed configurations
        typed_configs = config_manager.get_all_typed_configs()
        if typed_configs:
            logger.info(f"Using {len(typed_configs)} typed device configurations")
        
        # Create WB virtual device service BEFORE initializing devices so device
        # constructors receive it -- WB-passthrough devices' setup() needs both
        # `mqtt_client` (to subscribe to state_topic + meta/error) and the service to
        # decide whether to register the WB virtual device (which they skip via
        # `enable_wb_emulation=False`).
        wb_service = WBVirtualDeviceService(message_bus=mqtt_client)
        logger.info("Created WB virtual device service")
        device_manager.set_runtime_services(mqtt_client=mqtt_client, wb_service=wb_service)

        # Initialize devices using typed configurations only
        await device_manager.initialize_devices(config_manager.get_all_device_configs())

        # Wire the SSE event-publisher port + safety-net `mqtt_client` / `wb_service`
        # assignments (already set in the constructor; idempotent here).
        # device_manager.devices values are DevicePort by contract -- at runtime
        # every shipped impl is BaseDevice (which has these attributes). app/
        # is the composition root, allowed to know infrastructure types; cast
        # to BaseDevice so pyright sees the BaseDevice attribute surface.
        from wb_mqtt_bridge.infrastructure.devices.base import BaseDevice as _BaseDevice  # local: keep domain/ import-pure
        for device_id, port_device in device_manager.devices.items():
            device = cast(_BaseDevice, port_device)
            device.mqtt_client = mqtt_client
            device.wb_service = wb_service
            device.event_publisher = sse_manager  # SSE fan-out via EventPublisherPort
            logger.info(f"Device {device_id} initialized with typed configuration and WB service")

        # Attach Layer 1 capability maps from config/capabilities/ (hot-fixable JSON).
        attach_capability_maps(device_manager.devices, Path(config_manager.config_dir) / "capabilities")
        logger.info("Attached capability maps to devices")

        _exposure_violations = validate_command_exposure(device_manager.devices)
        if _exposure_violations:
            logger.warning(
                "Command-exposure check: %d command(s) are `exposed` but not capability-backed "
                "(they will be invisible in Layer-3 manifests — mark `exposed: false` or add a "
                "capability): %s",
                len(_exposure_violations), ", ".join(sorted(_exposure_violations)),
            )
        else:
            logger.info(
                "Command-exposure check: OK (every device command is exposed:false or capability-backed)"
            )

        # Persisted device state is restored inside initialize_devices(), per device BEFORE
        # its setup() — it must precede the post-setup initial persist, which would otherwise
        # clobber the last-good snapshot with boot defaults. (Replaces the old
        # device_manager.initialize() restore stub that ran here, too late.)

        # Get topics for all devices
        device_topics: dict[str, list[str]] = {}
        for device_id, device in device_manager.devices.items():
            topics = device.subscribe_topics()
            device_topics[device_id] = topics
            logger.info(f"Device {device_id} subscribed to topics: {topics}")

        # Connect MQTT client. Filter out any None handlers
        # (get_message_handler returns Optional; skip the missing ones rather
        # than passing them down).
        handler_map: dict[str, Callable[..., Any]] = {}
        for device_id, topics in device_topics.items():
            handler = device_manager.get_message_handler(device_id)
            if handler is None:
                continue
            for topic in topics:
                handler_map[topic] = handler
        await mqtt_client.connect_and_subscribe(handler_map)
        
        # Wait for MQTT connection to be fully established
        logger.info("Waiting for MQTT connection to be established...")
        connection_success = await mqtt_client.wait_for_connection(timeout=30.0)
        if not connection_success:
            logger.error("Failed to establish MQTT connection within timeout - WB emulation will be skipped")
        else:
            logger.info("MQTT connection established successfully")
            
            # Now that MQTT is connected, set up Wirenboard virtual device emulation for all devices
            logger.info("Setting up Wirenboard virtual device emulation...")
            for device_id, port_device in device_manager.devices.items():
                device = cast(_BaseDevice, port_device)
                try:
                    await device.setup_wb_emulation_if_enabled()
                    logger.debug(f"WB emulation setup completed for device {device_id}")
                except Exception as e:
                    logger.error(f"Failed to setup WB emulation for device {device_id}: {str(e)}")
        
        # Initialize room manager (after devices are loaded)
        room_manager = RoomManager(Path(config_manager.config_dir), device_manager)
        
        # Initialize scenario manager
        scenario_manager = ScenarioManager(
            device_manager=device_manager,
            room_manager=room_manager,
            state_repository=state_store,
            scenario_dir=Path(config_manager.config_dir) / "scenarios"
        )
        await scenario_manager.initialize()
        logger.info("Scenario manager initialized")

        # Scenario <-> Wirenboard integration (SCN-6, canonical_first.md §3-§4): one
        # Scenario Manager entity per scenario-bearing room. The domain proxy resolves
        # role -> device at fire time for REST/UI/WB alike; the WB adapter renders each
        # entity as a «Сценарии» card and keeps its value topic tracking the room slot.
        scenario_proxy = ScenarioProxy(scenario_manager, device_manager)
        scenario_wb_adapter = ScenarioWBAdapter(scenario_proxy, wb_service, mqtt_client)
        if connection_success:
            try:
                await scenario_wb_adapter.setup()
            except Exception as e:
                logger.error(f"Failed to set up scenario WB cards: {str(e)}")
        else:
            logger.warning("MQTT not connected - scenario WB cards skipped")

        # Initialize routers with dependencies
        system.initialize(config_manager, device_manager, mqtt_client, state_store, scenario_manager, room_manager, scenario_proxy)
        devices.initialize(config_manager, device_manager, mqtt_client, scenario_proxy)
        mqtt.initialize(mqtt_client)
        scenarios.initialize(scenario_manager, room_manager, mqtt_client)
        rooms.initialize(room_manager)
        state.initialize(config_manager, device_manager, state_store, scenario_manager)
        events.initialize()  # Initialize SSE events router
        
        logger.info("System startup complete")
        
        yield  # Service is running
        
        # Shutdown
        logger.info("System shutting down...")
        
        try:
            # Shutdown SSE connections first to prevent blocking
            logger.info("Shutting down SSE connections...")
            await sse_manager.shutdown()

            # NOTE: do NOT blanket-cancel asyncio.all_tasks() here. We run inside uvicorn's
            # lifespan task, and all_tasks() also contains uvicorn's own serve task — which is
            # parked in `lifespan.shutdown()` awaiting our completion. Cancelling it tears the
            # serve task out from under us (CancelledError out the top of asyncio.run) and
            # prematurely kills the MQTT task before the ordered disconnect below. The ordered
            # teardown that follows stops every task we own; asyncio.run() cancels any stragglers
            # after the lifespan returns cleanly. See action_plan.md §5.1 #8.

            # Flush in-flight (real) state writes BEFORE marking shutdown, so the last operating
            # state is persisted. After this, the persistence callback stops saving — device
            # teardown mutates state to disconnected/off, which must NOT overwrite the assumed state.
            logger.info("Flushing pending persistence before shutdown...")
            try:
                await device_manager.wait_for_persistence_tasks(timeout=2.0)
            except asyncio.CancelledError:
                logger.warning("Persistence flush interrupted by cancellation")

            # Prepare the device manager for shutdown (stops further persistence; teardown is
            # transparent to the hardware — the active scenario stays on the devices).
            logger.info("Preparing device manager for shutdown...")
            await device_manager.prepare_for_shutdown()

            # Shutdown scenario manager
            logger.info("Shutting down scenario manager...")
            await scenario_manager.shutdown()
            
            # Shutdown room manager
            logger.info("Shutting down room manager...")
            await room_manager.shutdown()
            
            # Disconnect MQTT to prevent incoming messages during shutdown
            logger.info("Disconnecting MQTT client...")
            await mqtt_client.disconnect()
            
            # Shutdown devices
            logger.info("Shutting down devices...")
            await device_manager.shutdown_devices()
            
            # No post-teardown persistence: device teardown mutates state to disconnected/off,
            # which must NOT overwrite the assumed state (already flushed above, pre-teardown).
            # This keeps a bridge restart transparent to the hardware.

            # Close state store after all persistence is done
            logger.info("Closing state persistence connection...")
            try:
                await state_store.close()
            except asyncio.CancelledError:
                logger.warning("State store close interrupted by cancellation")
            
            logger.info("System shutdown complete")
            
        except asyncio.CancelledError:
            logger.warning("Shutdown sequence interrupted by cancellation - performing emergency cleanup")
            
            # Emergency cleanup - fire and forget critical operations
            try:
                # Try to close state store without waiting
                await asyncio.wait_for(state_store.close(), timeout=0.5)
            except (asyncio.TimeoutError, asyncio.CancelledError, Exception) as e:
                logger.warning(f"Emergency state store close failed: {e}")
            
            # Re-raise the cancellation to let uvicorn handle it properly
            raise

    # Create the FastAPI app with lifespan
    app = FastAPI(
        title="MQTT Web Service",
        description="A web service that manages MQTT devices with typed configurations",
        version=__version__,
        lifespan=lifespan
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # For local network, allow all origins
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(system.router)
    app.include_router(devices.router)
    app.include_router(mqtt.router)
    app.include_router(scenarios.router)
    app.include_router(rooms.router)
    app.include_router(state.router)
    app.include_router(events.router)

    _install_openapi_with_state_models(app)

    return app


# Device-state models that must be present in /openapi.json so the UI's
# build-time codegen can read state shapes from the API contract instead of
# importing the Python package and AST-parsing these classes (action_plan P1 #3.5).
# These are runtime-typed states returned by /devices/{id}/state and persisted by
# the state store; the codegen maps each by class name via device-state-mapping.json.
OPENAPI_EXTRA_MODELS = [
    BaseDeviceState,
    KitchenHoodState,
    LgTvState,
    WirenboardIRState,
    RevoxA77ReelToReelState,
    AppleTVState,
    AuralicDeviceState,
    EmotivaXMC2State,
]


def _install_openapi_with_state_models(app: FastAPI) -> None:
    """Override app.openapi() to inject device-state model schemas.

    These models are not the response_model of any operation (the live endpoints
    return plain dicts / instances and keep their custom serialization), so they
    would not otherwise appear in components.schemas. We add them as standalone
    schemas — purely additive, no endpoint behavior changes — so both
    openapi-typescript (api.gen.ts) and the device-page StateTypeGenerator can
    consume them from the contract.
    """

    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema

        openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )

        schemas = openapi_schema.setdefault("components", {}).setdefault("schemas", {})
        for model in OPENAPI_EXTRA_MODELS:
            model_schema = model.model_json_schema(
                ref_template="#/components/schemas/{model}"
            )
            # Pydantic emits nested/referenced models under "$defs"; lift them to
            # components.schemas so the $ref pointers resolve.
            for dep_name, dep_schema in model_schema.pop("$defs", {}).items():
                schemas.setdefault(dep_name, dep_schema)
            schemas[model.__name__] = model_schema

        app.openapi_schema = openapi_schema
        return openapi_schema

    app.openapi = custom_openapi 