import os
import logging
import asyncio
import json
from devices.wirenboard_ir_device import WirenboardIRDevice
import uvicorn
from typing import Dict, Any, List, Optional, Union
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
    BaseDeviceConfig,
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
    MQTTPublishResponse,
    Group,
    ActionGroup,
    GroupedActionsResponse,
    GroupActionsResponse,
    BaseDeviceState,
    CommandResponse
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
    
    # Apply logger-specific configuration
    if system_config.loggers:
        for logger_name, logger_level in system_config.loggers.items():
            specific_logger = logging.getLogger(logger_name)
            specific_level = getattr(logging, logger_level.upper(), logging.INFO)
            specific_logger.setLevel(specific_level)
            logging.info(f"Set logger {logger_name} to level {logger_level}")
    
    logger = logging.getLogger(__name__)
    logger.info("Starting MQTT Web Service")
    
    # Initialize MQTT client first
    mqtt_broker_config = system_config.mqtt_broker
    mqtt_client = MQTTClient({
        'host': mqtt_broker_config.host,
        'port': mqtt_broker_config.port,
        'client_id': mqtt_broker_config.client_id,
        'keepalive': mqtt_broker_config.keepalive,
        'auth': mqtt_broker_config.auth
    })
    
    # Initialize device manager with null MQTT client initially
    device_manager = DeviceManager(mqtt_client=None, config_manager=config_manager)
    await device_manager.load_device_modules()
    
    # Log the number of typed configurations
    typed_configs = config_manager.get_all_typed_configs()
    if typed_configs:
        logger.info(f"Using {len(typed_configs)} typed device configurations")
    
    # Initialize devices using typed configurations only
    await device_manager.initialize_devices(config_manager.get_all_device_configs())
    
    # Now set the MQTT client for each initialized device
    for device_id, device in device_manager.devices.items():
        device.mqtt_client = mqtt_client
        logger.info(f"Device {device_id} initialized with typed configuration")
    
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
    
    logger.info("System startup complete")
    
    yield  # Service is running
    
    # Shutdown
    logger.info("System shutting down...")
    await mqtt_client.disconnect()
    await device_manager.shutdown_devices()
    logger.info("System shutdown complete")

# Create the FastAPI app with lifespan
app = FastAPI(
    title="MQTT Web Service",
    description="A web service that manages MQTT devices with typed configurations",
    version="1.1.0",
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

@app.get("/config/system", tags=["System"], response_model=SystemConfig)
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

@app.get("/config/device/{device_id}", tags=["Devices"], response_model=BaseDeviceConfig)
async def get_device_config(device_id: str):
    """Get full configuration for a specific device."""
    if not config_manager:
        raise HTTPException(status_code=503, detail="Service not fully initialized")
    
    try:
        device_config = config_manager.get_device_config(device_id)
        if not device_config:
            logger = logging.getLogger(__name__)
            logger.error(f"Configuration for device {device_id} not found")
            raise HTTPException(status_code=404, detail=f"Device configuration for {device_id} not found")
        
        return device_config
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error retrieving device config for {device_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/config/devices", tags=["Devices"], response_model=Dict[str, BaseDeviceConfig])
async def get_all_device_configs():
    """Get configurations for all devices."""
    if not config_manager:
        raise HTTPException(status_code=503, detail="Service not fully initialized")
    
    try:
        all_device_configs = config_manager.get_all_device_configs()
        return all_device_configs
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error retrieving all device configs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

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

@app.get("/devices/{device_id}", tags=["Devices"], response_model=BaseDeviceState)
async def get_device(device_id: str):
    """Get information about a specific device.
    
    Args:
        device_id: The ID of the device to retrieve
        
    Returns:
        BaseDeviceState: The device state with proper typing
        
    Raises:
        HTTPException: If device is not found or an error occurs
    """
    logger = logging.getLogger(__name__)
    if not device_manager:
        raise HTTPException(status_code=503, detail="Service not fully initialized")
    
    try:
        device = device_manager.get_device(device_id)
        if not device:
            raise HTTPException(status_code=404, detail=f"Device {device_id} not found")
            
        try:
            # Return the properly typed state directly
            return device.get_current_state()
        except Exception as e:
            logger.error(f"Error getting device state for {device_id}: {str(e)}")
            # Create a minimal BaseDeviceState with error information
            return BaseDeviceState(
                device_id=device_id,
                device_name=device.get_name(),
                error=str(e)
            )
    except Exception as e:
        logger.error(f"Error getting device {device_id}: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/devices/{device_id}/action", tags=["Devices"], response_model=CommandResponse)
async def execute_device_action(
    device_id: str, 
    action: DeviceAction,
    background_tasks: BackgroundTasks
):
    """Execute an action on a specific device.
    
    This endpoint allows executing various actions on devices. The available actions depend on the device type.
    For LG TVs, the following mouse control actions are supported:
    
    * **move_cursor** - Move cursor to absolute position x,y
      ```json
      {
        "action": "move_cursor",
        "params": {
          "x": 500,
          "y": 300,
          "drag": false
        }
      }
      ```
    
    * **move_cursor_relative** - Move cursor by dx,dy relative to current position
      ```json
      {
        "action": "move_cursor_relative",
        "params": {
          "dx": 100,
          "dy": -50,
          "drag": false
        }
      }
      ```
    
    * **click** - Click at position x,y
      ```json
      {
        "action": "click",
        "params": {
          "x": 500,
          "y": 300
        }
      }
      ```
    
    * **launch_app** - Launch an app by name
      ```json
      {
        "action": "launch_app",
        "params": {
          "app_name": "Netflix"
        }
      }
      ```
    
    * **wake_on_lan** - Wake the TV using Wake-on-LAN
      ```json
      {
        "action": "wake_on_lan",
        "params": {}
      }
      ```
    
    Other common actions include:
    * **power_on** - Turn the TV on
    * **power_off** - Turn the TV off
    * **set_volume** - Set TV volume (params: volume)
    * **set_mute** - Set TV mute state (params: mute)
    * **set_input_source** - Change input source (params: input_source)
    * **send_action** - Send remote control command (params: command)
    """
    logger = logging.getLogger(__name__)
    if not device_manager:
        raise HTTPException(status_code=503, detail="Service not fully initialized")
    
    device = device_manager.get_device(device_id)
    if not device:
        raise HTTPException(status_code=404, detail=f"Device {device_id} not found")
    
    # Execute the action
    logger.info(f"Executing action {action.action} for device {device_id} with params {action.params}")
    result = await device.execute_action(action.action, action.params or {})
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Unknown error"))
    
    # If there's an MQTT command to be published, do it in the background
    if "mqtt_command" in result and result["mqtt_command"] is not None and mqtt_client is not None:
        mqtt_cmd = result["mqtt_command"]
        background_tasks.add_task(
            mqtt_client.publish,
            mqtt_cmd["topic"],
            mqtt_cmd["payload"]
        )
    
    # Return the properly typed CommandResponse directly
    return result

@app.post("/publish", tags=["MQTT"], response_model=MQTTPublishResponse, responses={
    503: {"model": ErrorResponse, "description": "Service not fully initialized"},
    500: {"model": ErrorResponse, "description": "Internal server error"}
})
async def publish_message(message: MQTTMessage, background_tasks: BackgroundTasks):
    """Publish a message to an MQTT topic.
    
    This endpoint allows publishing messages to an MQTT topic with the following features:
    
    - **Optional payload**: If payload is not provided (null), it defaults to 1 (which will be sent as "1")
    - **Multiple payload types**: Payload can be a string, number, boolean, object, or array
    - **Type conversion**: 
        - Dict/object payloads are JSON serialized
        - Boolean payloads are converted to "true"/"false" strings
        - Numeric payloads are converted to strings
    
    ### Parameter-based Commands
    
    For devices with commands that accept parameters, the payload should be a JSON object
    with properties matching the parameter names defined in the device configuration:
    
    - **Set volume example**: For a command with a 'level' parameter
      ```json
      {
        "level": 50
      }
      ```
    
    - **Launch app example**: For a command with an 'app' parameter
      ```json
      {
        "app": "Netflix"
      }
      ```
    
    - **Multiple parameters example**: For commands with multiple parameters
      ```json
      {
        "temperature": 22.5,
        "mode": "heat"
      }
      ```
    
    The parameters will be validated according to their definitions in the device configuration.
    
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

# API endpoints for Action Groups
@app.get("/groups", tags=["Groups"], response_model=List[Group])
async def get_groups():
    """List all available function groups."""
    if not config_manager:
        raise HTTPException(status_code=503, detail="Service not fully initialized")
    
    try:
        groups = config_manager.get_groups()
        return [{"id": group_id, "name": display_name} for group_id, display_name in groups.items()]
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error retrieving groups: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/devices/{device_id}/groups/{group_id}/actions", tags=["Groups"], response_model=GroupActionsResponse)
async def get_actions_by_group(device_id: str, group_id: str):
    """List all actions in a group for a device, with status information."""
    logger = logging.getLogger(__name__)
    
    if not device_manager or not config_manager:
        raise HTTPException(status_code=503, detail="Service not fully initialized")
    
    try:
        # Check if device exists
        device = device_manager.get_device(device_id)
        if not device:
            raise HTTPException(status_code=404, detail=f"Device '{device_id}' not found")
            
        # Get group definitions
        groups = config_manager.get_groups()
        group_name = groups.get(group_id)
        
        # Case 1: Group is not defined in system.json and is not 'default'
        if not config_manager.is_valid_group(group_id):
            return GroupActionsResponse(
                device_id=device_id,
                group_id=group_id,
                status="invalid_group",
                message=f"Group '{group_id}' is not defined in system configuration"
            )
            
        # Case 2: Group is valid but device doesn't have it
        if group_id not in device.get_available_groups():
            if group_id == "default":
                # Special case for default group - it always exists but might be empty
                return GroupActionsResponse(
                    device_id=device_id,
                    group_id=group_id,
                    group_name="Default Group",
                    status="no_actions",
                    message=f"Device '{device_id}' has no actions in the 'default' group"
                )
            else:
                return GroupActionsResponse(
                    device_id=device_id,
                    group_id=group_id,
                    group_name=group_name,
                    status="unknown_group",
                    message=f"Device '{device_id}' does not support the '{group_id}' group"
                )
        
        # Case 3: Group exists but has no actions
        actions = device.get_actions_by_group(group_id)
        if not actions:
            return GroupActionsResponse(
                device_id=device_id,
                group_id=group_id,
                group_name=group_name,
                status="no_actions",
                message=f"Device '{device_id}' has no actions in the '{group_id}' group"
            )
            
        # Case 4: Success - group exists with actions
        return GroupActionsResponse(
            device_id=device_id,
            group_id=group_id,
            group_name=group_name,
            status="ok",
            actions=actions
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving actions for group '{group_id}' in device '{device_id}': {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/devices/{device_id}/groups", tags=["Groups"], response_model=GroupedActionsResponse)
async def get_device_actions_by_groups(device_id: str):
    """Get all actions for a device organized by groups, including empty groups."""
    logger = logging.getLogger(__name__)
    
    if not device_manager or not config_manager:
        raise HTTPException(status_code=503, detail="Service not fully initialized")
    
    try:
        device = device_manager.get_device(device_id)
        if not device:
            raise HTTPException(status_code=404, detail=f"Device '{device_id}' not found")
        
        group_definitions = config_manager.get_groups()
        groups = []
        default_included = False
        
        # Get all device groups
        device_groups = device.get_available_groups()
        
        # Process all groups defined for this device
        for group_id in device_groups:
            group_name = group_definitions.get(group_id, group_id.title())
            actions = device.get_actions_by_group(group_id)
            
            # Create ActionGroup object
            action_group = ActionGroup(
                group_id=group_id,
                group_name=group_name,
                actions=actions,
                status="ok" if actions else "no_actions"
            )
            
            groups.append(action_group)
            
            # Track if default group is included
            if group_id == "default":
                default_included = True
        
        # Always include default group if not already included
        if not default_included:
            groups.append(ActionGroup(
                group_id="default",
                group_name="Default Group",
                actions=[],
                status="no_actions"
            ))
            default_included = True
        
        return GroupedActionsResponse(
            device_id=device_id,
            groups=groups,
            default_included=default_included
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving grouped actions for device '{device_id}': {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
