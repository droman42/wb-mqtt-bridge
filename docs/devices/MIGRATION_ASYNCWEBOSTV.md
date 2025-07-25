# Migration from PyWebOSTV to AsyncWebOSTV

This document outlines the changes made to switch from the synchronous PyWebOSTV library to the asynchronous AsyncWebOSTV library in the WB-MQTT-Bridge project.

## Installation

The AsyncWebOSTV library needs to be installed as a local development dependency:

```bash
# Install the AsyncWebOSTV library
pip install -e ../asyncwebostv
```

## Required Code Changes

The migration from PyWebOSTV to AsyncWebOSTV involves the following key changes:

### 1. Import Statements

```python
# Old imports
from pywebostv.discovery import *
from pywebostv.connection import *
from pywebostv.controls import *

# New imports
from asyncwebostv.connection import WebOSClient
from asyncwebostv.controls import (
    MediaControl,
    SystemControl,
    ApplicationControl,
    TvControl,
    InputControl,
    SourceControl
)
```

### 2. Removing ThreadPoolExecutor

The AsyncWebOSTV library is fully asynchronous, so we no longer need `ThreadPoolExecutor` for making synchronous calls in an async context.

```python
# Old initialization with ThreadPoolExecutor
self.executor = ThreadPoolExecutor(max_workers=2)

# Old usage pattern
result = await asyncio.get_event_loop().run_in_executor(
    self.executor, sync_method_call
)

# New fully async approach
result = await async_method_call()
```

### 3. Connection and Registration

```python
# Old connection and registration (synchronous)
def connect_sync():
    client = WebOSClient(ip_address, secure=True)
    client.connect()
    registered = False
    for status in client.register(self.store):
        if status == WebOSClient.PROMPTED:
            # handle prompt
        elif status == WebOSClient.REGISTERED:
            registered = True
    return client

self.client = await asyncio.get_event_loop().run_in_executor(
    self.executor, connect_sync
)

# New connection and registration (asynchronous)
self.client = WebOSClient(ip_address, secure=secure_mode, client_key=self.client_key)
await self.client.connect()

# Registration (if needed)
if not self.client.client_key:
    store = {}
    async for status in self.client.register(store):
        if status == WebOSClient.PROMPTED:
            # handle prompt
        elif status == WebOSClient.REGISTERED:
            # handle registration
```

### 4. Method Calls

```python
# Old synchronous methods run in executor
def set_volume_sync():
    self.media.set_volume(volume)

await asyncio.get_event_loop().run_in_executor(self.executor, set_volume_sync)

# New direct async method calls
await self.media.set_volume(volume)
```

## Key API Differences

1. **Connect/Disconnect**: `await client.connect()` and `await client.close()`
2. **Registration**: `async for status in client.register(store)` 
3. **Control Methods**: All control methods are now awaitable (`await control.method()`)
4. **State Queries**: Methods like `get_volume()` and `list_apps()` are asynchronous

## Best Practices

1. Always check for None before calling methods: `if self.media: await self.media.set_volume(volume)`
2. Use try/except blocks around asynchronous calls that might fail
3. Keep track of connection state and reconnect as needed
4. Log failures clearly to help with debugging

## Dependencies

Update pyproject.toml to use the AsyncWebOSTV library:

```
# Remove or comment out PyWebOSTV
#pywebostv>=0.8.9

# Add AsyncWebOSTV (local development)
-e ../asyncwebostv
```

Also update pyproject.toml if used:

```toml
dependencies = [
    # Other dependencies...
    # Local dependency for AsyncWebOSTV
    "asyncwebostv @ file:///path/to/asyncwebostv"
]
``` 