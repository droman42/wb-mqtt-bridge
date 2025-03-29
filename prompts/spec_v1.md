# Project Specification: MQTT Web Service

## Overview
This project is a Python-based web service that acts as an MQTT client to manage multiple devices. The service will:
- Subscribe and publish to MQTT topics.
- Handle device-specific actions via individual Python modules.
- Use a plugin-based architecture for extendability.
- Store device configurations in JSON files.
- Run as an asynchronous service behind an Nginx reverse proxy.
- Log events and errors to a file.

## Architecture
- **Web Service**: Built with FastAPI.
- **MQTT Client**: Based on [`asyncio-mqtt`](https://github.com/AndreasHeine/asyncio-mqtt/tree/main).
- **Device Modules**: Each device has its own Python module that handles its specific functions.
- **Configuration Storage**: JSON files for each device.
- **Authentication**: MQTT broker requires username/password authentication.
- **Logging**: Logs are stored in a file.

## Components
### 1. Web Service (FastAPI)
- Serves a REST API to interact with the system (e.g., list devices, reload config).
- Runs asynchronously with `uvicorn`.
- Deployed behind an Nginx reverse proxy.

### 2. MQTT Client
- Uses `asyncio-mqtt` to:
  - Subscribe to device-specific topics.
  - Publish messages when required.
- Handles reconnections in case of failures.

### 3. Device Modules (Plugins)
- Each device has a separate Python module in a `devices/` directory.
- The module contains:
  - A `subscribe_topics()` function defining MQTT topics.
  - A `handle_message(topic, payload)` function processing messages.
- The service dynamically loads and registers these modules.

### 4. Configuration Management
- Each device has a JSON config file stored in `config/devices/{device_name}.json`.
- Config files define:
  ```json
  {
    "device_name": "sensor_1",
    "mqtt_topics": ["home/sensor1/data"],
    "auth": {"username": "user", "password": "pass"}
  }
  ```
- A system-wide config file (`config/system.json`) defines MQTT broker details.

### 5. Logging
- Logs stored in `logs/service.log`.
- Uses Python’s built-in `logging` module.

## Implementation Plan
1. **Set up FastAPI service**.
2. **Implement MQTT client** using `asyncio-mqtt`.
3. **Create plugin system** to dynamically load device modules.
4. **Handle JSON-based configuration**.
5. **Implement logging and error handling**.
6. **Deploy behind Nginx**.

## Future Enhancements
- Add a web UI for device management.
- Implement a database for storing device states.
- Extend security with OAuth2 authentication.

---
Let me know if you need modifications or additional features!

