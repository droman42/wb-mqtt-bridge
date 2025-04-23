# AsyncWebOSTV Library Updates and LgTv Class Implementation Guide

This document outlines the changes made to the AsyncWebOSTV library and provides recommendations for updating the LgTv class to leverage these improvements.

## Table of Contents

1. [Overview of Updates](#overview-of-updates)
2. [Registration Process Improvements](#registration-process-improvements)
3. [New Control Methods](#new-control-methods)
4. [Implementation Guide for LgTv Class](#implementation-guide-for-lgtv-class)
5. [Example Implementations](#example-implementations)

## Overview of Updates

The AsyncWebOSTV library has been enhanced with a persistent callback pattern that improves reliability and functionality for multi-step operations like registration, power control, app launching, and input switching. These improvements resolve issues with premature callback removal and provide better status tracking for operations.

### Key Improvements:

1. **Reliable Registration Process**: Fixed an issue where the registration process would hang due to premature callback removal
2. **Enhanced Power Control**: Added methods for power on/off with status monitoring
3. **Improved Application Launching**: Added methods for launching apps with status monitoring
4. **Input Switching with Status**: Enhanced input switching with status monitoring
5. **Volume and Mute Control**: Added methods for volume and mute operations with status monitoring

## Registration Process Improvements

The registration process has been completely reworked to use a queue-based approach for collecting and processing all messages from the TV. This ensures that both the initial "PROMPT" message and the subsequent "registered" message are properly handled, preventing the registration process from hanging.

### Key Changes:

1. **Queue-Based Message Processing**: All registration-related messages are collected in a queue and processed sequentially
2. **Persistent Callbacks**: Callbacks remain active throughout the registration process
3. **Enhanced Error Handling**: Better timeout behavior and error reporting
4. **Improved Logging**: More detailed logging of the registration process

## New Control Methods

The library now includes enhanced versions of commonly used control methods that provide better status tracking and reliability.

### SystemControl

- `power_off_with_monitoring(timeout=10.0)`: Powers off the TV and monitors the process
- `power_on_with_monitoring(timeout=20.0)`: Powers on the TV and monitors the process

### ApplicationControl

- `launch_with_monitoring(app_id, params=None, timeout=30.0)`: Launches an app and monitors until it's fully loaded

### InputControl

- `list_inputs()`: Gets a list of available input sources
- `get_input()`: Gets the current input source
- `set_input(input_id)`: Switches to a different input source
- `set_input_with_monitoring(input_id, timeout=10.0)`: Switches input sources with status monitoring

### MediaControl

- `set_volume_with_monitoring(volume, timeout=5.0)`: Sets volume with status monitoring
- `set_mute_with_monitoring(mute, timeout=5.0)`: Sets mute state with status monitoring

## Implementation Guide for LgTv Class

The LgTv class currently uses direct message sending through `client.send_message()` for many operations. We recommend updating it to use the new enhanced methods for improved reliability.

### Power Control Updates

The `power_on()` and `power_off()` methods should be updated to use the new monitoring methods:

```python
async def power_on(self):
    """Power on the TV (if supported)."""
    try:
        logger.info(f"Attempting to power on TV {self.get_name()}")
        success = False

        # First try using WebOS API if we have an active connection
        if self.system and self.client:
            try:
                logger.info("Attempting to power on via WebOS API...")
                result = await self.system.power_on_with_monitoring(timeout=20.0)
                if result.get("returnValue", False) or result.get("status") == "powered_on":
                    self.state["power"] = "on"
                    self.state["last_command"] = "power_on"
                    success = True
                    logger.info("Power on via WebOS API successful")
            except Exception as e:
                logger.debug(f"WebOS API power on failed: {str(e)}")

        # If WebOS method failed or we don't have an active connection, try Wake-on-LAN
        if not success:
            # Wake-on-LAN logic (unchanged)
            # ...

        return success
    except Exception as e:
        logger.error(f"Error powering on TV: {str(e)}")
        self.state["last_command"] = "power_on_error"
        return False

async def power_off(self):
    """Power off the TV."""
    try:
        logger.info(f"Powering off TV {self.get_name()}")

        # Use system turnOff method with monitoring
        if self.system and self.client:
            result = await self.system.power_off_with_monitoring(timeout=10.0)
            if result.get("returnValue", False) or result.get("status") in ["succeeded", "powered_off"]:
                self.state["power"] = "off"
                self.state["last_command"] = "power_off"
                return True

        return False
    except Exception as e:
        logger.error(f"Error powering off TV: {str(e)}")
        return False
```

### Application Launching Updates

The `launch_app()` method should be updated to use the new monitoring method:

```python
async def launch_app(self, app_name):
    """Launch an application on the TV."""
    try:
        logger.info(f"Launching app {app_name} on TV {self.get_name()}")

        if not self.app or not self.client:
            logger.error("Cannot launch app: TV client not initialized")
            return False

        # Get a list of available apps to find the app_id
        apps = await self.app.list_apps()
        app_id = None

        # Find the app by name or ID
        for app in apps:
            if app.name.lower() == app_name.lower() or app.id.lower() == app_name.lower():
                app_id = app.id
                break

        if not app_id:
            logger.error(f"Could not find app: {app_name}")
            return False

        # Launch the app with monitoring
        result = await self.app.launch_with_monitoring(app_id, timeout=30.0)

        if result.get("returnValue", False) or result.get("status") in ["launched", "foreground"]:
            self.state["current_app"] = app_name
            self.state["last_command"] = f"launch_app_{app_name}"
            return True

        return False
    except Exception as e:
        logger.error(f"Error launching app {app_name}: {str(e)}")
        return False
```

### Input Switching Updates

The `set_input_source()` method should be updated to use the new monitoring method:

```python
async def set_input_source(self, input_source):
    """Switch to a different input source."""
    try:
        logger.info(f"Setting input source to {input_source} on TV {self.get_name()}")

        if not self.input_control or not self.client:
            logger.error("Cannot set input: TV client not initialized")
            return False

        # Get a list of available inputs
        inputs = await self.input_control.list_inputs()
        input_id = None

        # Find the input by name or ID
        for input_item in inputs.get("devices", []):
            if input_item.get("label", "").lower() == input_source.lower() or input_item.get("id", "").lower() == input_source.lower():
                input_id = input_item.get("id")
                break

        if not input_id:
            logger.error(f"Could not find input source: {input_source}")
            return False

        # Switch input with monitoring
        result = await self.input_control.set_input_with_monitoring(input_id, timeout=10.0)

        if result.get("returnValue", False) or result.get("status") in ["switching", "switched"]:
            self.state["input_source"] = input_source
            self.state["last_command"] = f"set_input_{input_source}"
            return True

        return False
    except Exception as e:
        logger.error(f"Error setting input source to {input_source}: {str(e)}")
        return False
```

### Volume and Mute Control Updates

The `set_volume()` and `set_mute()` methods should be updated to use the new monitoring methods:

```python
async def set_volume(self, volume):
    """Set the volume level."""
    try:
        volume = int(volume)
        logger.info(f"Setting TV {self.get_name()} volume to {volume}")

        if not self.media or not self.client:
            logger.error("Cannot set volume: TV client not initialized")
            return False

        # Set volume with monitoring
        result = await self.media.set_volume_with_monitoring(volume, timeout=5.0)

        if result.get("returnValue", False) or result.get("status") in ["changing", "changed"]:
            self.state["volume"] = volume
            self.state["last_command"] = f"set_volume_{volume}"
            return True

        return False
    except Exception as e:
        logger.error(f"Error setting volume: {str(e)}")
        return False

async def set_mute(self, mute=None):
    """Set mute state on TV."""
    try:
        # Convert string to bool if needed
        if isinstance(mute, str):
            mute = mute.lower() in ("yes", "true", "t", "1", "on")
        elif mute is None:
            # Toggle mute if no value provided
            current_status = await self.media.get_volume()
            mute = not current_status.get("muted", False)

        logger.info(f"Setting mute on TV {self.get_name()} to {mute}")

        if not self.media or not self.client:
            logger.error("Cannot set mute: TV client not initialized")
            return False

        # Set mute with monitoring
        result = await self.media.set_mute_with_monitoring(mute, timeout=5.0)

        if result.get("returnValue", False) or result.get("status") in ["changing", "changed"]:
            self.state["mute"] = mute
            self.state["last_command"] = f"set_mute_{mute}"
            return True

        return False
    except Exception as e:
        logger.error(f"Error setting mute: {str(e)}")
        return False
```

## Example Implementations

### Power On with Wake-on-LAN Fallback

```python
async def power_on_with_wol_fallback(self):
    """Power on the TV with Wake-on-LAN fallback."""
    # Try WebOS API first
    if self.system and self.client:
        try:
            result = await self.system.power_on_with_monitoring(timeout=10.0)
            if result.get("returnValue", False) or result.get("status") == "powered_on":
                return True
        except Exception:
            pass

    # Fall back to Wake-on-LAN
    mac_address = self.state.get("mac_address")
    if mac_address:
        wol_success = await self.send_wol_packet(mac_address)
        if wol_success:
            await asyncio.sleep(15)  # Wait for TV to boot
            return await self.connect()  # Try to reconnect

    return False
```

### Running an Action Sequence

```python
async def run_action_sequence(self, actions):
    """Run a sequence of actions on the TV."""
    results = []

    for action in actions:
        action_type = action.get("type")

        if action_type == "power_on":
            result = await self.power_on()
        elif action_type == "power_off":
            result = await self.power_off()
        elif action_type == "launch_app":
            result = await self.launch_app(action.get("app_name"))
        elif action_type == "set_input":
            result = await self.set_input_source(action.get("input_source"))
        elif action_type == "set_volume":
            result = await self.set_volume(action.get("volume"))
        elif action_type == "set_mute":
            result = await self.set_mute(action.get("mute"))
        elif action_type == "wait":
            await asyncio.sleep(action.get("seconds", 1))
            result = True
        else:
            result = False

        results.append({
            "action": action_type,
            "success": result
        })

        if not result and action.get("stop_on_failure", False):
            break

    return results
```

By implementing these changes, the LgTv class will benefit from the improved reliability and status tracking provided by the updated AsyncWebOSTV library.
