import logging

from fastapi import APIRouter, HTTPException, BackgroundTasks

from wb_mqtt_bridge.presentation.api.schemas import (
    MQTTMessage,
    MQTTPublishResponse,
    ErrorResponse
)

# Create router with appropriate tags
router = APIRouter(
    tags=["MQTT"]
)

# Global references that will be set during initialization
mqtt_client = None

def initialize(mqt_client):
    """Initialize global references needed by router endpoints."""
    global mqtt_client
    mqtt_client = mqt_client

@router.post("/publish", response_model=MQTTPublishResponse, responses={
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
      
    ### Device-Specific Command Examples
    
    #### LG TV Commands
    
    - **Move cursor to position**:
      ```json
      {
        "x": 500,
        "y": 300,
        "drag": false
      }
      ```
    
    - **Click at position**:
      ```json
      {
        "x": 500,
        "y": 300
      }
      ```
    
    #### Audio/Video Receiver Commands
    
    - **Set volume with zone selection**:
      ```json
      {
        "level": -35.5,
        "zone": 1
      }
      ```
    
    - **Change input source**:
      ```json
      {
        "input": "hdmi1"
      }
      ```
    
    #### Wirenboard IR Commands
    
    - **Send IR command with parameters**:
      ```json
      {
        "code": "POWER_ON",
        "repeat": 2
      }
      ```
    
    ### Alternative Format
    
    Some implementations may use a format that includes both action name and parameters:
    
    ```json
    {
      "action": "set_volume",
      "params": {
        "level": -35.5,
        "zone": 1
      }
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