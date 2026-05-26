// wb_mqtt.h — esp_mqtt_client (IDF built-in) wired to the Wirenboard
// topic convention (`/devices/<id>/meta/...`, `/controls/<c>`, `/controls/<c>/on`).
//
// On CONNECTED: publish retained meta/name + per-control meta/type + initial
// value; subscribe to each control's /on topic; subscribe to /provision.
// On DATA: parse topic → dispatch via drv->doCommand (with record-arm gate),
// echo state. The /provision topic persists identity to NVS and reboots.
#pragma once
struct DeviceDriver;

// Start the MQTT client. drv may be nullptr (unprovisioned mode — still
// subscribes to /provision, but no controls announced/dispatched).
void mqtt_start(const char* device_id, const DeviceDriver* drv);

// Implementation of the wb_publish_value declared in device_driver.h —
// drivers reach this via that helper.
void mqtt_publish_value_internal(const char* control, const char* value, bool retained);
