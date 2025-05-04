"""Router modules for the MQTT Web Service.

This package contains FastAPI router modules that organize API endpoints by functionality:

- system: System-level endpoints (/, /system, /config/system, /reload)
- devices: Device-specific endpoints (/devices/*, /config/device/*)
- mqtt: MQTT-related endpoints (/publish)
- groups: Action group endpoints (/groups, /devices/*/groups/*)
""" 