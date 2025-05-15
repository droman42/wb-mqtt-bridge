# EMotivaXMC2 Module Migration Plan

## Overview

This document outlines the detailed implementation plan for migrating the `EMotivaXMC2` device module to utilize the new refactored architecture of the `pymotivaxmc2` library. The migration will be performed as a single comprehensive update without maintaining backward compatibility.

## Architectural Changes

### Current Architecture

The current implementation uses a monolithic `Emotiva` client from the `pymotivaxmc2` library:

```python
from pymotivaxmc2 import Emotiva, EmotivaConfig as PyEmotivaConfig

self.client = Emotiva(PyEmotivaConfig(
    ip=host,
    **{k: v for k, v in emotiva_options.items() if v is not None}
))
```

Key characteristics:
- Single client class handling all operations
- Direct method calls for commands
- Callback-based notification system
- Manual state tracking
- Direct socket and protocol management

### New Architecture

The new architecture separates concerns into distinct modules:

```python
from pymotivaxmc2 import EmotivaController
from pymotivaxmc2.config import EmotivaConfig
from pymotivaxmc2.protocol import CommandFormatter, ResponseParser
from pymotivaxmc2.network import SocketManager, EmotivaNetworkDiscovery
from pymotivaxmc2.notifier import NotificationRegistry, NotificationDispatcher
from pymotivaxmc2.state import DeviceState, PropertyCache

self.client = EmotivaController(
    config=EmotivaConfig(
        ip=host,
        **{k: v for k, v in emotiva_options.items() if v is not None}
    )
)
```

Key improvements:
- Facade controller with specialized components
- Protocol-specific operations isolated
- Network operations decoupled
- Observer pattern for notifications
- Dedicated state management
- Clear command execution with error handling

## Detailed Migration Steps

### 1. Update Import Structure

#### Current Imports:
```python
import logging
import json
from typing import Dict, Any, List, Optional, Union, Callable, Awaitable, Tuple, TypeVar, cast, Coroutine, Literal, Protocol
from pymotivaxmc2 import Emotiva, EmotivaConfig as PyEmotivaConfig
from datetime import datetime
import asyncio
from enum import Enum, auto

from devices.base_device import BaseDevice
from app.schemas import EmotivaXMC2State, LastCommand, EmotivaConfig, EmotivaXMC2DeviceConfig, StandardCommandConfig, CommandParameterDefinition
from app.types import StateT, CommandResult, CommandResponse, ActionHandler
```

#### New Imports:
```python
import logging
import json
from typing import Dict, Any, List, Optional, Union, Callable, Awaitable, Tuple, TypeVar, cast, Coroutine, Literal, Protocol
from pymotivaxmc2 import EmotivaController
from pymotivaxmc2.config import EmotivaConfig as PyEmotivaConfig
from pymotivaxmc2.protocol import CommandFormatter, ResponseParser
from pymotivaxmc2.network import SocketManager, EmotivaNetworkDiscovery
from pymotivaxmc2.notifier import NotificationRegistry, NotificationListener, EmotivaNotification
from pymotivaxmc2.state import DeviceState, PropertyChangeEvent
from datetime import datetime
import asyncio
from enum import Enum, auto

from devices.base_device import BaseDevice
from app.schemas import EmotivaXMC2State, LastCommand, EmotivaConfig, EmotivaXMC2DeviceConfig, StandardCommandConfig, CommandParameterDefinition
from app.types import StateT, CommandResult, CommandResponse, ActionHandler
```

### 2. Implement NotificationListener Interface

The current notification handling uses a callback function:

#### Current Approach:
```python
# Setup
self.client.set_callback(self._handle_notification)

# Handler
def _handle_notification(self, notification_data: Dict[str, Any]) -> None:
    # Process raw dictionary of notification data
    # ...
```

#### New Approach:
```python
# Add NotificationListener to class definition
class EMotivaXMC2(BaseDevice[EmotivaXMC2State], NotificationListener):

    # Implement required methods from the interface
    async def on_notification(self, notification: EmotivaNotification) -> None:
        """Process notifications from the eMotiva device."""
        logger.debug(f"Received notification from eMotiva device: {notification}")
        
        # Create a background task for publishing
        notification_data = notification.to_dict()
        asyncio.create_task(self.publish_progress(json.dumps(notification_data)))
        
        try:
            updates: Dict[str, Any] = {}
            
            # Process based on notification type
            if notification.type == "power":
                power_state_value = notification.value
                power_state = PowerState.ON if power_state_value == "on" else PowerState.OFF if power_state_value == "off" else PowerState.UNKNOWN
                updates["power"] = power_state
                logger.info(f"Power state updated: {power_state}")
            
            # Continue with other notification types...
            
            # Update device state
            if updates:
                self.clear_error()
                self.update_state(**updates)
        except Exception as e:
            logger.error(f"Error processing notification: {str(e)}")
```

### 3. Update Device Initialization

#### Current Setup Method:
```python
async def setup(self) -> bool:
    try:
        # Get emotiva configuration
        emotiva_config: EmotivaConfig = self.config.emotiva
        
        # Get the host IP address
        host = emotiva_config.host
        if not host:
            logger.error(f"Missing 'host' in emotiva configuration for device: {self.get_name()}")
            self.set_error("Missing host configuration")
            return False
        
        # Create client instance
        self.client = Emotiva(PyEmotivaConfig(
            ip=host,
            **{k: v for k, v in emotiva_options.items() if v is not None}
        ))
        
        # Attempt discovery
        discovery_result = await self.client.discover()
        
        # Set up notification handling
        self.client.set_callback(self._handle_notification)
        
        # Subscribe to notifications
        subscription_result = await self.client.subscribe_to_notifications(default_notifications)
        
        # Query initial device status
        power_status = await self.client.get_power()
        # ...
```

#### New Setup Method:
```python
async def setup(self) -> bool:
    try:
        # Get emotiva configuration
        emotiva_config: EmotivaConfig = self.config.emotiva
        
        # Get the host IP address
        host = emotiva_config.host
        if not host:
            logger.error(f"Missing 'host' in emotiva configuration for device: {self.get_name()}")
            self.set_error("Missing host configuration")
            return False
        
        # Prepare configuration options
        emotiva_options = {
            "timeout": emotiva_config.timeout,
            "max_retries": emotiva_config.max_retries,
            "retry_delay": emotiva_config.retry_delay,
            "keepalive_interval": emotiva_config.update_interval
        }
        
        # Create EmotivaController with proper configuration
        config = PyEmotivaConfig(
            ip=host,
            **{k: v for k, v in emotiva_options.items() if v is not None}
        )
        
        self.client = EmotivaController(config=config)
        
        # Configure state listener for automatic state updates
        self.client.state.add_property_listener(self._handle_property_change)
        
        # Register as notification listener
        self.client.notifier.register_listener(self)
        
        # Attempt to discover the device using the discovery component
        logger.info(f"Attempting to discover eMotiva device at {host}")
        discovery_result = await self.client.discovery.discover_devices(
            timeout=emotiva_config.timeout or 5.0
        )
        
        # Check discovery result
        if discovery_result and discovery_result.status == "success":
            logger.info(f"Successfully discovered eMotiva device: {discovery_result}")
            
            # Subscribe to notification topics
            default_notifications = [
                "power", "zone2_power", "volume", "input", 
                "audio_input", "video_input", "audio_bitstream",
                "mute", "mode"
            ]
            
            subscription_result = await self.client.notifier.subscribe(default_notifications)
            logger.info(f"Notification subscription result: {subscription_result}")
            
            # Query initial device status through command executor
            try:
                logger.info(f"Querying initial power status for {self.get_name()}")
                power_response = await self.client.command_executor.execute_command(
                    device=self.client,
                    command="get_power"
                )
                
                if power_response.is_successful:
                    power_value = power_response.value
                    power_state = PowerState.ON if power_value == "on" else PowerState.OFF if power_value == "off" else PowerState.UNKNOWN
                    self.update_state(power=power_state)
                    logger.info(f"Initial power state: {power_state}")
                else:
                    logger.warning(f"Failed to get initial power state: {power_response.error}")
            except Exception as e:
                logger.warning(f"Error getting power status: {str(e)}")
            
            # Continue with other status queries...
```

### 4. Add Property Change Listener

Add a new method to handle property changes from the device state:

```python
def _handle_property_change(self, event: PropertyChangeEvent) -> None:
    """Handle property change events from the device state.
    
    Args:
        event: Property change event containing property name, old value, and new value
    """
    property_name = event.property_name
    new_value = event.new_value
    logger.debug(f"Property change: {property_name} = {new_value}")
    
    # Map property changes to our state model
    updates = {}
    
    if property_name == "power":
        power_state = PowerState.ON if new_value == "on" else PowerState.OFF if new_value == "off" else PowerState.UNKNOWN
        updates["power"] = power_state
    elif property_name == "zone2_power":
        zone2_state = PowerState.ON if new_value == "on" else PowerState.OFF if new_value == "off" else PowerState.UNKNOWN
        updates["zone2_power"] = zone2_state
    elif property_name == "volume":
        updates["volume"] = float(new_value) if new_value is not None else 0
    elif property_name == "mute":
        updates["mute"] = bool(new_value)
    # Continue with other properties...
    
    # Apply state updates if any
    if updates:
        self.update_state(**updates)
```

### 5. Update Command Execution

#### Current Command Helper:
```python
async def _execute_device_command(self, 
                                action: str,
                                command_func: DeviceCommandFunc,
                                params: Dict[str, Any],
                                notification_topics: List[str] = None,
                                state_updates: Dict[str, Any] = None) -> CommandResult:
    try:
        if not self.client:
            logger.error(f"Client not initialized for action: {action}")
            return self.create_command_result(success=False, error="Client not initialized")
        
        # Subscribe to notifications if provided
        if notification_topics:
            try:
                await self.client.subscribe_to_notifications(notification_topics)
            except Exception as e:
                logger.warning(f"Could not subscribe to notifications for {action}: {str(e)}")
        
        # Execute the command
        try:
            result = await command_func()
        except asyncio.TimeoutError:
            logger.error(f"Timeout waiting for {action} response from {self.get_name()}")
            self.set_error("Command timeout")
            return self.create_command_result(success=False, error="Command timeout")
        # ...
```

#### New Command Helper:
```python
async def _execute_device_command(self, 
                                action: str,
                                command: str,
                                value: Any = None,
                                params: Dict[str, Any] = None,
                                notification_topics: List[str] = None,
                                state_updates: Dict[str, Any] = None) -> CommandResult:
    try:
        if not self.client:
            logger.error(f"Client not initialized for action: {action}")
            return self.create_command_result(success=False, error="Client not initialized")
        
        # Subscribe to notifications if provided
        if notification_topics:
            try:
                await self.client.notifier.subscribe(notification_topics)
            except Exception as e:
                logger.warning(f"Could not subscribe to notifications for {action}: {str(e)}")
        
        # Execute the command using the command executor
        try:
            # Prepare command execution options
            execute_options = {
                "command": command,
                "retries": self.config.emotiva.max_retries,
                "timeout": self.config.emotiva.timeout
            }
            
            # Add value if provided
            if value is not None:
                execute_options["value"] = value
                
            # Execute through the command executor
            response = await self.client.command_executor.execute_command(**execute_options)
            
            # Check response
            if response.is_successful:
                # Update state with provided updates
                if state_updates:
                    # Clear any previous errors
                    self.clear_error()
                    self.update_state(**state_updates)
                
                # Record last command
                self._update_last_command(action, params)
                
                # Create success message
                message = f"{action} command executed successfully"
                
                logger.info(f"Successfully executed {action} on eMotiva XMC2: {self.get_name()}")
                return self.create_command_result(success=True, message=message)
            else:
                # Get error from response
                error_message = response.error or f"Unknown error during {action}"
                logger.error(f"Failed to execute {action} on eMotiva XMC2: {error_message}")
                
                # Update the state with the error
                self.set_error(error_message)
                
                return self.create_command_result(success=False, error=error_message)
                
        except asyncio.TimeoutError:
            logger.error(f"Timeout waiting for {action} response from {self.get_name()}")
            self.set_error("Command timeout")
            return self.create_command_result(success=False, error="Command timeout")
        except Exception as e:
            logger.error(f"Error executing {action} on eMotiva XMC2: {str(e)}")
            self.set_error(str(e))
            return self.create_command_result(success=False, error=str(e))
    except Exception as e:
        # Catch any unexpected exceptions in the command execution process
        error_message = f"Unexpected error executing {action}: {str(e)}"
        logger.error(error_message)
        self.set_error(error_message)
        return self.create_command_result(success=False, error=error_message)
```

### 6. Update Individual Command Handlers

#### Current Command Handler:
```python
async def handle_power_on(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
    """
    Handle power on command.
    
    Args:
        cmd_config: Command configuration
        params: Parameters (unused)
        
    Returns:
        Command execution result
    """
    return await self._execute_device_command(
        "power_on",
        self.client.power_on,
        params,
        notification_topics=["power"],
        state_updates={"power": PowerState.ON}
    )
```

#### New Command Handler:
```python
async def handle_power_on(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
    """
    Handle power on command.
    
    Args:
        cmd_config: Command configuration
        params: Parameters (unused)
        
    Returns:
        Command execution result
    """
    return await self._execute_device_command(
        action="power_on",
        command="power",
        value="on",
        params=params,
        notification_topics=["power"],
        state_updates={"power": PowerState.ON}
    )
```

### 7. Update Volume Setting Command

#### Current Volume Handler:
```python
async def handle_set_volume(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
    """
    Handle volume setting command.
    
    Args:
        cmd_config: Command configuration
        params: Parameters containing volume level
        
    Returns:
        Command execution result
    """
    # Validate parameters
    if not params:
        return self.create_command_result(success=False, error="Missing volume parameters")
    
    # Get and validate volume parameter
    volume_param = cmd_config.get_parameter("volume")
    is_valid, volume, error_msg = self._validate_parameter(
        param_name="volume",
        param_value=params.get("volume"),
        param_type=volume_param.type if volume_param else "float",
        min_value=volume_param.min if volume_param else 0,
        max_value=volume_param.max if volume_param else 100,
        action="set_volume"
    )
    
    if not is_valid:
        return self.create_command_result(success=False, error=error_msg)
        
    # Define nested command function with captured volume parameter
    async def set_volume_with_level() -> Dict[str, Any]:
        return await self.client.set_volume(volume)
    
    # Execute the command
    return await self._execute_device_command(
        "set_volume",
        set_volume_with_level,
        params,
        notification_topics=["volume"],
        state_updates={"volume": volume}
    )
```

#### New Volume Handler:
```python
async def handle_set_volume(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
    """
    Handle volume setting command.
    
    Args:
        cmd_config: Command configuration
        params: Parameters containing volume level
        
    Returns:
        Command execution result
    """
    # Validate parameters
    if not params:
        return self.create_command_result(success=False, error="Missing volume parameters")
    
    # Get and validate volume parameter
    volume_param = cmd_config.get_parameter("volume")
    is_valid, volume, error_msg = self._validate_parameter(
        param_name="volume",
        param_value=params.get("volume"),
        param_type=volume_param.type if volume_param else "float",
        min_value=volume_param.min if volume_param else 0,
        max_value=volume_param.max if volume_param else 100,
        action="set_volume"
    )
    
    if not is_valid:
        return self.create_command_result(success=False, error=error_msg)
    
    # Execute the command with volume value
    return await self._execute_device_command(
        action="set_volume",
        command="volume",
        value=volume,
        params=params,
        notification_topics=["volume"],
        state_updates={"volume": volume}
    )
```

### 8. Update Device Shutdown

#### Current Shutdown Method:
```python
async def shutdown(self) -> bool:
    """Cleanup device resources and properly shut down connections."""
    if not self.client:
        logger.info(f"No client initialized for {self.get_name()}, nothing to shut down")
        return True
        
    logger.info(f"Starting shutdown for eMotiva XMC2 device: {self.get_name()}")
    
    # Track if we completed all cleanup steps
    all_cleanup_successful = True
    
    try:
        # Step 1: Unregister from notifications
        try:
            # Check if the client has a notification_registered attribute
            if hasattr(self.client, '_notification_registered') and self.client._notification_registered:
                logger.debug(f"Unregistering from notifications for {self.get_name()}")
                # This is normally handled by the close method, but we'll try explicitly
                if hasattr(self.client, '_notifier') and self.client._notifier:
                    # ...
        except Exception as e:
            # ...
        
        # Step 2: Clean up the notifier
        try:
            if hasattr(self.client, '_notifier') and self.client._notifier:
                # ...
        except Exception as e:
            # ...
        
        # Step 3: Close the client connection
        try:
            logger.debug(f"Closing client connection for {self.get_name()}")
            await asyncio.wait_for(
                self.client.close(),
                timeout=2.0
            )
            # ...
        except asyncio.TimeoutError:
            # ...
        
        # Final cleanup
        # ...
    except Exception as e:
        # ...
```

#### New Shutdown Method:
```python
async def shutdown(self) -> bool:
    """Cleanup device resources and properly shut down connections."""
    if not self.client:
        logger.info(f"No client initialized for {self.get_name()}, nothing to shut down")
        return True
        
    logger.info(f"Starting shutdown for eMotiva XMC2 device: {self.get_name()}")
    
    # Track if we completed all cleanup steps
    all_cleanup_successful = True
    
    try:
        # Step 1: Unregister from notifications
        try:
            logger.debug(f"Unregistering from notification listener for {self.get_name()}")
            # Unregister from notification registry
            if hasattr(self.client, 'notifier') and self.client.notifier:
                try:
                    # Give a short timeout for unregistering
                    await asyncio.wait_for(
                        self.client.notifier.unregister_listener(self),
                        timeout=1.0
                    )
                    logger.info(f"Successfully unregistered from notifications for {self.get_name()}")
                except asyncio.TimeoutError:
                    logger.warning(f"Notification unregister timed out for {self.get_name()}")
                except Exception as e:
                    logger.warning(f"Error unregistering from notifications for {self.get_name()}: {str(e)}")
                    all_cleanup_successful = False
        except Exception as e:
            logger.warning(f"Exception during notification unregistration: {str(e)}")
            all_cleanup_successful = False
        
        # Step 2: Remove state listeners
        try:
            logger.debug(f"Removing state listeners for {self.get_name()}")
            if hasattr(self.client, 'state') and self.client.state:
                self.client.state.remove_property_listener(self._handle_property_change)
                logger.info(f"Successfully removed state listeners for {self.get_name()}")
        except Exception as e:
            logger.warning(f"Exception during state listener removal: {str(e)}")
            all_cleanup_successful = False
        
        # Step 3: Close the client
        try:
            logger.debug(f"Closing controller for {self.get_name()}")
            await asyncio.wait_for(
                self.client.close(),
                timeout=2.0
            )
            logger.info(f"Successfully closed controller for {self.get_name()}")
        except asyncio.TimeoutError:
            logger.warning(f"Controller close timed out for {self.get_name()}")
            all_cleanup_successful = False
        except Exception as e:
            logger.warning(f"Error closing controller for {self.get_name()}: {str(e)}")
            all_cleanup_successful = False
        
        # Final cleanup - update the state regardless of success
        if all_cleanup_successful:
            self.clear_error()
        else:
            self.set_error("Partial shutdown completed with errors")
            
        self.update_state(
            connected=False,
            notifications=False
        )
        
        # Release client reference
        self.client = None
        
        logger.info(f"eMotiva XMC2 device {self.get_name()} shutdown {'' if all_cleanup_successful else 'partially '}complete")
        return True
    except Exception as e:
        logger.error(f"Unexpected error during {self.get_name()} shutdown: {str(e)}")
        
        # Still update the state as disconnected even after errors
        self.set_error(f"Shutdown error: {str(e)}")
        self.update_state(
            connected=False,
            notifications=False
        )
        
        # Release client reference
        self.client = None
        
        return False
```

## Migration Testing Strategy

### 1. Unit Testing Individual Components

1. **Setup Testing**:
   - Test successful initialization with valid configuration
   - Test error handling with invalid configuration
   - Verify device discovery mechanisms

2. **Command Testing**:
   - Test each command handler individually
   - Verify proper parameter handling
   - Check error propagation and handling

3. **Notification Testing**:
   - Validate notification registration
   - Test notification message processing
   - Verify state updates from notifications

4. **Cleanup Testing**:
   - Ensure proper shutdown sequence
   - Verify resource release
   - Check error handling during shutdown

### 2. Integration Testing

1. **MQTT Integration**:
   - Verify command handling via MQTT messages
   - Test state updates published via MQTT
   - Test error reporting via MQTT

2. **Device Communication**:
   - Test end-to-end communication with real devices
   - Verify command response handling
   - Check notification processing from device events

3. **Error Recovery**:
   - Test behavior during network interruptions
   - Verify reconnection capabilities
   - Test error state recovery

### 3. Regression Testing

1. **Command Functionality**:
   - Verify all existing commands work with new implementation
   - Test with various parameter combinations
   - Compare responses with previous implementation

2. **State Management**:
   - Verify state tracking behavior matches previous version
   - Check state persistence during operations
   - Validate state visibility via MQTT topics

## Implementation Timeline

| Stage | Task | Duration |
|-------|------|----------|
| 1 | Update import structure and class definitions | 1 day |
| 2 | Implement `NotificationListener` interface | 1 day |
| 3 | Update device initialization code | 1 day |
| 4 | Implement property change handling | 1 day |
| 5 | Update command execution helper | 1 day |
| 6 | Update individual command handlers | 2 days |
| 7 | Update device shutdown procedure | 1 day |
| 8 | Testing and debugging | 3 days |
| 9 | Documentation updates | 1 day |

**Total Estimated Time**: 12 working days

## Risk Management

| Risk | Impact | Mitigation |
|------|--------|------------|
| API Incompatibility | Command functionality broken | Review API docs, test commands individually |
| Response Format Changes | Incorrect state updates | Update response parsing, add validation |
| Event Model Differences | Missed notifications | Test notification system thoroughly |
| Error Handling Gaps | Unhandled error cases | Add comprehensive try/except blocks |
| Performance Regression | Slower response times | Benchmark key operations |
| Resource Leaks | Memory usage growth | Verify cleanup procedures |

## Conclusion

This migration plan provides a comprehensive approach to updating the `EMotivaXMC2` device module to utilize the new refactored architecture of the `pymotivaxmc2` library. By following this detailed implementation plan, the migration can be executed efficiently while ensuring all functionality is preserved and improved.

The refactored implementation will benefit from:
- Cleaner code organization with separation of concerns
- Improved error handling and recovery
- More robust state management
- Enhanced notification processing
- Better testability of individual components

After completion, the module will leverage the full capabilities of the refactored library architecture while maintaining the same MQTT interface and device functionality. 