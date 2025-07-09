"""Router modules for the MQTT Web Service.

This package contains FastAPI router modules that organize API endpoints by functionality:

- system: System-level endpoints (/, /system, /config/system, /reload)
- devices: Device-specific endpoints (/config/device/*)
- mqtt: MQTT-related endpoints (/publish)
- groups: Action group endpoints (/groups, /devices/*/groups/*)
- scenarios: Scenario management endpoints (/scenario/definition/*, /scenario/switch, /scenario/role_action)
- rooms: Room management endpoints (/room/*)
- state: State-related endpoints (/devices/*/state, /devices/*/persisted_state, /devices/persisted_states, /scenario/state)
- events: Server-Sent Events endpoints (/events/devices, /events/scenarios, /events/system)
"""

from app.routers import system, devices, mqtt, groups, scenarios, rooms, state, events 