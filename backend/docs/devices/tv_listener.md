# TV Listener Implementation Guide

This guide shows how to implement a real-time listener for WebOS TV power and volume changes using AsyncWebOSTV's subscription functionality.

## Overview

AsyncWebOSTV provides real-time event subscriptions that allow you to monitor TV state changes without polling. This guide focuses on implementing listeners for:

- **Volume Changes** - Monitor volume level and mute status changes
- **Power State Changes** - Monitor TV power on/off and standby states

## Prerequisites

- Python 3.8+
- AsyncWebOSTV library installed
- WebOS TV on the same network
- TV client key (obtained during first connection)

## Basic Setup

### 1. Install Dependencies

```bash
pip install asyncwebostv
```

### 2. Basic Connection Setup

```python
import asyncio
import logging
from asyncwebostv.connection import WebOSClient
from asyncwebostv.controls import MediaControl, SystemControl

# Configure logging to see subscription events
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TVListener:
    def __init__(self, tv_ip: str, client_key: str = None):
        """Initialize TV listener.

        Args:
            tv_ip: IP address of your WebOS TV
            client_key: Optional client key for authentication
        """
        self.tv_ip = tv_ip
        self.client_key = client_key
        self.client = None
        self.media_control = None
        self.system_control = None

    async def connect(self):
        """Connect to the TV and set up controls."""
        self.client = WebOSClient(self.tv_ip, client_key=self.client_key)
        await self.client.connect()

        # Register if needed
        if not self.client.client_key:
            logger.info("Registering with TV - please accept the connection request on your TV")
            store = {}
            async for status in self.client.register(store):
                if status == WebOSClient.PROMPTED:
                    logger.info("Please accept the connection request on your TV...")
                elif status == WebOSClient.REGISTERED:
                    logger.info("Registration successful!")
                    self.client_key = store.get("client_key")
                    break

        # Initialize control interfaces
        self.media_control = MediaControl(self.client)
        self.system_control = SystemControl(self.client)
        logger.info("Connected to TV successfully")
```

## Volume Change Listener

### Implementation

```python
async def volume_callback(self, success: bool, payload: dict):
    """Handle volume change events.

    Args:
        success: True if event is valid, False if error occurred
        payload: Event data containing volume info or error message
    """
    if success:
        volume = payload.get("volume", 0)
        muted = payload.get("muted", False)

        # Log the volume change
        status = "🔇 MUTED" if muted else f"🔊 {volume}%"
        logger.info(f"Volume changed: {status}")

        # Custom logic here - examples:
        # - Save volume state to database
        # - Send notification to mobile app
        # - Adjust smart home lighting based on volume
        # - Log volume changes for analytics

        await self.on_volume_changed(volume, muted)
    else:
        logger.error(f"Volume subscription error: {payload}")

async def setup_volume_listener(self):
    """Set up volume change monitoring."""
    try:
        await self.media_control.subscribe_get_volume(self.volume_callback)
        logger.info("✅ Volume listener activated")
    except ValueError as e:
        if "Already subscribed" in str(e):
            logger.warning("Volume listener already active")
        else:
            raise e

async def on_volume_changed(self, volume: int, muted: bool):
    """Custom handler for volume changes - override this method.

    Args:
        volume: Current volume level (0-100)
        muted: Whether audio is muted
    """
    # Override this method in your implementation
    print(f"Volume: {volume}%, Muted: {muted}")
```

### Volume Event Triggers

Volume events are triggered by:

- User changes volume via remote control
- App calls `set_volume()` or `volume_up()`/`volume_down()`
- User toggles mute via remote or `set_mute()`
- Smart home integrations changing volume

## Power State Listener

### Implementation

```python
async def power_callback(self, success: bool, payload: dict):
    """Handle power state change events.

    Args:
        success: True if event is valid, False if error occurred
        payload: Event data containing power state info or error message
    """
    if success:
        state = payload.get("state", "unknown")
        processing = payload.get("processing", False)
        power_on_reason = payload.get("powerOnReason", "")

        # Log the power state change
        status = f"⚡ {state}"
        if processing:
            status += " (processing...)"
        logger.info(f"Power state changed: {status}")

        # Custom logic here - examples:
        # - Update smart home automation
        # - Log TV usage patterns
        # - Send notifications when TV turns on/off
        # - Adjust room lighting based on TV state

        await self.on_power_changed(state, processing, power_on_reason)
    else:
        logger.error(f"Power state subscription error: {payload}")

async def setup_power_listener(self):
    """Set up power state change monitoring."""
    try:
        await self.system_control.subscribe_power_state(self.power_callback)
        logger.info("✅ Power state listener activated")
    except ValueError as e:
        if "Already subscribed" in str(e):
            logger.warning("Power state listener already active")
        else:
            raise e

async def on_power_changed(self, state: str, processing: bool, power_on_reason: str):
    """Custom handler for power state changes - override this method.

    Args:
        state: Current power state (Active, Off, Suspend, etc.)
        processing: Whether power operation is in progress
        power_on_reason: Reason for last power on event
    """
    # Override this method in your implementation
    print(f"Power State: {state}, Processing: {processing}")
    if power_on_reason:
        print(f"Power On Reason: {power_on_reason}")
```

### Power State Values

- `"Active"` - TV is on and fully operational
- `"Off"` - TV is completely powered off
- `"Suspend"` - TV is in standby/sleep mode
- `"Screen Off"` - Display off but system running
- `"Power Saving"` - Low power mode

### Power Event Triggers

Power events are triggered by:

- User powers TV on/off via remote
- App calls `power_off()` or `power_on()`
- Sleep timer activation
- Energy saving mode changes
- Wake-on-LAN events

## Complete TV Listener Implementation

### Full Example

```python
import asyncio
import logging
import signal
from typing import Optional
from asyncwebostv.connection import WebOSClient
from asyncwebostv.controls import MediaControl, SystemControl

class CompleteTVListener:
    """Complete TV listener for power and volume changes."""

    def __init__(self, tv_ip: str, client_key: Optional[str] = None):
        self.tv_ip = tv_ip
        self.client_key = client_key
        self.client = None
        self.media_control = None
        self.system_control = None
        self.running = False

        # Set up logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    async def connect(self):
        """Connect to TV and set up controls."""
        self.client = WebOSClient(self.tv_ip, client_key=self.client_key)
        await self.client.connect()

        # Register if needed
        if not self.client.client_key:
            self.logger.info("Registering with TV...")
            store = {}
            async for status in self.client.register(store):
                if status == WebOSClient.PROMPTED:
                    self.logger.info("Please accept the connection request on your TV...")
                elif status == WebOSClient.REGISTERED:
                    self.logger.info("Registration successful!")
                    self.client_key = store.get("client_key")
                    break

        # Initialize controls
        self.media_control = MediaControl(self.client)
        self.system_control = SystemControl(self.client)

    async def volume_callback(self, success: bool, payload: dict):
        """Handle volume change events."""
        if success:
            volume = payload.get("volume", 0)
            muted = payload.get("muted", False)
            status = "🔇 MUTED" if muted else f"🔊 {volume}%"
            self.logger.info(f"Volume: {status}")

            # Call custom handler
            await self.on_volume_changed(volume, muted)
        else:
            self.logger.error(f"Volume error: {payload}")

    async def power_callback(self, success: bool, payload: dict):
        """Handle power state change events."""
        if success:
            state = payload.get("state", "unknown")
            processing = payload.get("processing", False)
            status = f"⚡ {state}"
            if processing:
                status += " (processing)"
            self.logger.info(f"Power: {status}")

            # Call custom handler
            await self.on_power_changed(state, processing)
        else:
            self.logger.error(f"Power error: {payload}")

    async def start_listening(self):
        """Start listening for TV events."""
        try:
            # Set up subscriptions
            await self.media_control.subscribe_get_volume(self.volume_callback)
            await self.system_control.subscribe_power_state(self.power_callback)

            self.logger.info("🎯 TV listener started - monitoring volume and power changes")
            self.running = True

            # Keep the listener running
            while self.running:
                await asyncio.sleep(1)

        except Exception as e:
            self.logger.error(f"Error starting listener: {e}")
            raise

    async def stop_listening(self):
        """Stop listening and clean up."""
        self.running = False

        try:
            # Unsubscribe from events
            await self.media_control.unsubscribe_get_volume()
            await self.system_control.unsubscribe_power_state()
            self.logger.info("✅ Unsubscribed from all events")
        except Exception as e:
            self.logger.warning(f"Error during unsubscribe: {e}")

        # Close connection
        if self.client:
            await self.client.close()
            self.logger.info("✅ Connection closed")

    # Override these methods in your implementation
    async def on_volume_changed(self, volume: int, muted: bool):
        """Override this method to handle volume changes."""
        pass

    async def on_power_changed(self, state: str, processing: bool):
        """Override this method to handle power changes."""
        pass

# Example usage
async def main():
    """Example usage of TV listener."""

    # Create custom listener class
    class MyTVListener(CompleteTVListener):
        async def on_volume_changed(self, volume: int, muted: bool):
            """Custom volume change handler."""
            if muted:
                print("🔇 TV was muted")
            elif volume > 50:
                print(f"🔊 TV volume is high: {volume}%")
            elif volume < 10:
                print(f"🔉 TV volume is low: {volume}%")

        async def on_power_changed(self, state: str, processing: bool):
            """Custom power change handler."""
            if state == "Active":
                print("📺 TV turned ON")
            elif state == "Off":
                print("⏻ TV turned OFF")
            elif state == "Suspend":
                print("😴 TV went to sleep mode")

    # Set up signal handlers for graceful shutdown
    listener = None

    def signal_handler(signum, frame):
        if listener:
            asyncio.create_task(listener.stop_listening())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start listening
    listener = MyTVListener("192.168.1.100")  # Replace with your TV's IP

    try:
        await listener.connect()
        await listener.start_listening()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        if listener:
            await listener.stop_listening()

if __name__ == "__main__":
    asyncio.run(main())
```

## Error Handling

### Common Error Scenarios

#### 1. Double Subscription

```python
try:
    await media_control.subscribe_get_volume(callback)
except ValueError as e:
    if "Already subscribed" in str(e):
        logger.warning("Volume subscription already active")
    else:
        raise
```

#### 2. Connection Lost

```python
async def handle_connection_loss(self):
    """Handle WebSocket connection loss."""
    # All subscriptions are automatically cleaned up
    # Reconnect and re-subscribe
    try:
        await self.connect()
        await self.start_listening()
    except Exception as e:
        logger.error(f"Reconnection failed: {e}")
```

#### 3. TV Not Available

```python
try:
    await client.connect()
except Exception as e:
    logger.error(f"Cannot connect to TV: {e}")
    # Implement retry logic or fallback behavior
```

## Best Practices

### 1. Resource Management

```python
# Always clean up subscriptions
try:
    await media_control.unsubscribe_get_volume()
    await system_control.unsubscribe_power_state()
finally:
    await client.close()
```

### 2. Non-blocking Event Handlers

```python
async def volume_callback(self, success: bool, payload: dict):
    """Keep callbacks lightweight and non-blocking."""
    if success:
        # Process quickly
        volume = payload.get("volume", 0)

        # For heavy processing, use background tasks
        asyncio.create_task(self.heavy_processing(volume))
```

### 3. Graceful Shutdown

```python
import signal

def setup_signal_handlers(listener):
    """Set up graceful shutdown on signals."""
    def signal_handler(signum, frame):
        asyncio.create_task(listener.stop_listening())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
```

### 4. Persistent Client Key Storage

```python
import json

def save_client_key(client_key: str):
    """Save client key for future use."""
    with open("tv_client_key.json", "w") as f:
        json.dump({"client_key": client_key}, f)

def load_client_key() -> Optional[str]:
    """Load saved client key."""
    try:
        with open("tv_client_key.json", "r") as f:
            return json.load(f).get("client_key")
    except FileNotFoundError:
        return None
```

## Use Cases and Examples

### 1. Smart Home Integration

```python
async def on_power_changed(self, state: str, processing: bool):
    """Integrate with smart home systems."""
    if state == "Active":
        # Turn on ambient lighting
        await smart_home.set_scene("movie_time")
    elif state == "Off":
        # Turn off all entertainment area lights
        await smart_home.turn_off_zone("entertainment")

async def on_volume_changed(self, volume: int, muted: bool):
    """Adjust room acoustics based on volume."""
    if volume > 70:
        # Close automated blinds for better acoustics
        await smart_home.close_blinds("living_room")
```

### 2. Usage Analytics

```python
import sqlite3
from datetime import datetime

async def on_power_changed(self, state: str, processing: bool):
    """Log TV usage for analytics."""
    conn = sqlite3.connect("tv_usage.db")
    conn.execute(
        "INSERT INTO power_events (timestamp, state) VALUES (?, ?)",
        (datetime.now(), state)
    )
    conn.commit()
    conn.close()
```

### 3. Parental Controls

```python
async def on_volume_changed(self, volume: int, muted: bool):
    """Enforce volume limits."""
    if volume > 60 and is_quiet_hours():
        await self.media_control.set_volume(40)
        await self.system_control.notify("Volume reduced for quiet hours")
```

## Testing Your Listener

### 1. Test Volume Events

- Change volume using TV remote
- Press mute/unmute button
- Use voice commands (if supported)

### 2. Test Power Events

- Turn TV on/off with remote
- Enable/disable sleep timer
- Test standby mode

### 3. Validation Script

```python
async def test_listener():
    """Test script to validate listener functionality."""
    listener = CompleteTVListener("192.168.1.100")

    try:
        await listener.connect()
        print("✅ Connection successful")

        await listener.start_listening()
        print("✅ Subscriptions active")

        print("Test your TV remote - volume and power changes should appear here")
        await asyncio.sleep(30)  # Monitor for 30 seconds

    finally:
        await listener.stop_listening()
        print("✅ Cleanup complete")
```

## Troubleshooting

### Common Issues

1. **No events received**: Check TV network connectivity and firewall settings
2. **Connection timeouts**: Verify TV IP address and ensure TV is on
3. **Registration fails**: Make sure to accept the connection request on TV screen
4. **Subscription errors**: Ensure only one subscription per event type at a time

### Debug Mode

```python
import logging

# Enable debug logging to see all WebSocket traffic
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('asyncwebostv')
logger.setLevel(logging.DEBUG)
```

## Conclusion

This guide provides a complete foundation for implementing real-time TV listeners using AsyncWebOSTV subscriptions. The subscription system provides:

- ✅ **Real-time updates** with no polling overhead
- ✅ **Robust error handling** and automatic reconnection
- ✅ **Easy customization** for your specific use cases
- ✅ **Production-ready** patterns for reliable operation

Use this as a starting point and customize the event handlers for your specific application needs!
