// ota.h — MQTT-triggered, HTTPS-pull OTA update.
//
// Replaces ArduinoOTA (which is incompatible with IDF). The flow is:
//   1. Publish the firmware .bin URL (retained) to /devices/<id>/ota.
//   2. The box receives the MQTT message, calls ota_trigger(url).
//   3. ota_task pulls the image via esp_https_ota → writes to inactive
//      partition → on success, restarts.
//   4. Rollback semantics rely on the bootloader app-rollback config
//      (Phase 6 sdkconfig.defaults: CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE).
//
// Plain http:// works (the API is called esp_https_ota but supports HTTP too).
// For a LAN-hosted .bin that's enough; HTTPS would need a pinned CA cert.
#pragma once

// Kick off an OTA pull from `url`. Returns immediately; the work runs on a
// separate FreeRTOS task. On success the device restarts. On failure it logs
// + the running image is unaffected.
void ota_trigger(const char* url);
