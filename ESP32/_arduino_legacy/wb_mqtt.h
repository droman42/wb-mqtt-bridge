// wb_mqtt.h — Wirenboard-convention helpers over PubSubClient.
#pragma once
#include <Arduino.h>
#include "device_driver.h"

// Called by the core once connected: announce the device + all its controls as
// retained meta topics, and subscribe to each control's /on command topic.
void wb_announce(const DeviceDriver* drv);

// Publish a control's current value (retained). Used to echo state + by drivers
// for read-only value topics (status read-back, reels_moving, etc.).
void wb_publish_value(const char* control, const char* value, bool retained);

// Build the command-topic suffix test: returns the control name if `topic` is
// "/devices/<id>/controls/<name>/on", else nullptr.
const char* wb_match_command(const char* topic);

// Init with the active device id (sets topic prefixes).
void wb_init(const char* device_id);
