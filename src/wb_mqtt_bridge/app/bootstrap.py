import os
import logging
import asyncio
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from wb_mqtt_bridge.infrastructure.config.manager import ConfigManager
from wb_mqtt_bridge.domain.devices.service import DeviceManager
from wb_mqtt_bridge.infrastructure.mqtt.client import MQTTClient
from wb_mqtt_bridge.infrastructure.persistence.sqlite import SQLiteStateStore
from wb_mqtt_bridge.infrastructure.wb_device.service import WBVirtualDeviceService
from wb_mqtt_bridge.domain.rooms.service import RoomManager
from wb_mqtt_bridge.domain.scenarios.service import ScenarioManager
from wb_mqtt_bridge.infrastructure.scenarios.wb_adapter import ScenarioWBAdapter
from wb_mqtt_bridge.infrastructure.maintenance.wirenboard_guard import WirenboardMaintenanceGuard

# Import routers
from wb_mqtt_bridge.presentation.api.routers import (
    system, devices, mqtt, groups, scenarios, rooms, state, events
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
        
        # Initialize devices using typed configurations only
        await device_manager.initialize_devices(config_manager.get_all_device_configs())
        
        # Create WB virtual device service
        wb_service = WBVirtualDeviceService(message_bus=mqtt_client)
        logger.info("Created WB virtual device service")
        
        # Now set the MQTT client and WB service for each initialized device
        for device_id, device in device_manager.devices.items():
            device.mqtt_client = mqtt_client
            device.wb_service = wb_service
            logger.info(f"Device {device_id} initialized with typed configuration and WB service")
        
        # Configuration Migration Phase B: Log migration guidance for deprecated topic usage
        config_manager.log_migration_guidance()
        
        # Initialize state from persistence layer
        await device_manager.initialize()
        logger.info("Device states initialized from persistence layer")
        
        # Get topics for all devices
        device_topics = {}
        for device_id, device in device_manager.devices.items():
            topics = device.subscribe_topics()
            device_topics[device_id] = topics
            logger.info(f"Device {device_id} subscribed to topics: {topics}")
        
        # Connect MQTT client
        await mqtt_client.connect_and_subscribe({
            # Add message handlers for all device topics
            **{topic: device_manager.get_message_handler(device_id) 
               for device_id, topics in device_topics.items()
               for topic in topics}
        })
        
        # Wait for MQTT connection to be fully established
        logger.info("Waiting for MQTT connection to be established...")
        connection_success = await mqtt_client.wait_for_connection(timeout=30.0)
        if not connection_success:
            logger.error("Failed to establish MQTT connection within timeout - WB emulation will be skipped")
        else:
            logger.info("MQTT connection established successfully")
            
            # Now that MQTT is connected, set up Wirenboard virtual device emulation for all devices
            logger.info("Setting up Wirenboard virtual device emulation...")
            for device_id, device in device_manager.devices.items():
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
        
        # Initialize scenario WB adapter with shared service
        scenario_wb_adapter = ScenarioWBAdapter(
            scenario_manager=scenario_manager,
            wb_service=wb_service,
            device_manager=device_manager
        )
        logger.info("Scenario WB adapter initialized")
        
        # Set up WB device for current scenario if any (after MQTT is connected)
        if scenario_manager.current_scenario and connection_success:
            try:
                logger.info(f"Setting up WB virtual device for active scenario: {scenario_manager.current_scenario.definition.scenario_id}")
                success = await scenario_wb_adapter.setup_wb_virtual_device_for_scenario(
                    scenario_manager.current_scenario
                )
                if success:
                    logger.info("Scenario WB virtual device setup completed")
                else:
                    logger.warning("Failed to setup scenario WB virtual device")
            except Exception as e:
                logger.error(f"Error setting up scenario WB virtual device: {str(e)}")
        
        # Initialize routers with dependencies
        system.initialize(config_manager, device_manager, mqtt_client, state_store, scenario_manager, room_manager)
        devices.initialize(config_manager, device_manager, mqtt_client)
        mqtt.initialize(mqtt_client)
        groups.initialize(config_manager, device_manager)
        scenarios.initialize(scenario_manager, room_manager, mqtt_client, scenario_wb_adapter)
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
            
            # Cancel any remaining background tasks that might prevent shutdown
            logger.info("Cancelling background tasks...")
            all_tasks = [task for task in asyncio.all_tasks() if not task.done()]
            current_task = asyncio.current_task()
            background_tasks = [task for task in all_tasks if task != current_task]
            
            if background_tasks:
                logger.info(f"Found {len(background_tasks)} background tasks to cancel")
                for task in background_tasks:
                    if not task.done():
                        task.cancel()
                
                # Wait briefly for tasks to cancel gracefully
                try:
                    await asyncio.wait_for(
                        asyncio.gather(*background_tasks, return_exceptions=True),
                        timeout=2.0  # Reduced timeout
                    )
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    logger.warning("Background task cancellation interrupted or timed out")
            
            # Prepare the device manager for shutdown 
            logger.info("Preparing device manager for shutdown...")
            await device_manager.prepare_for_shutdown()
            
            # Clean up scenario WB devices first
            logger.info("Cleaning up scenario WB devices...")
            if scenario_manager.current_scenario:
                try:
                    await scenario_wb_adapter.cleanup_scenario_wb_device(scenario_manager.current_scenario)
                    logger.info("Scenario WB virtual device cleanup completed")
                except Exception as e:
                    logger.error(f"Error cleaning up scenario WB virtual device: {str(e)}")
            
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
            
            # Wait for any in-flight persistence tasks to complete
            logger.info("Waiting for persistence tasks to complete...")
            try:
                await device_manager.wait_for_persistence_tasks(timeout=2.0)  # Reduced timeout
            except asyncio.CancelledError:
                logger.warning("Persistence task wait interrupted by cancellation")
            
            # Perform final state persistence for all devices
            logger.info("Performing final state persistence...")
            try:
                await device_manager.persist_all_device_states()
            except asyncio.CancelledError:
                logger.warning("Final state persistence interrupted by cancellation")
            
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
    app.include_router(groups.router)
    app.include_router(scenarios.router)
    app.include_router(rooms.router)
    app.include_router(state.router)
    app.include_router(events.router)

    return app 