// main.cpp — PHASE 1 stub. Proves PIO + ESP-IDF toolchain works on this host.
//
// This is intentionally minimal: just app_main + a heartbeat log so we can
// verify the build chain end-to-end before investing the Phase 2-4 rewrite.
// Real shared core (Wi-Fi + light-sleep + MQTT + NVS identity + OTA + dispatch)
// arrives in Phase 2.

#include <stdio.h>
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char* TAG = "bridge";

extern "C" void app_main(void) {
    ESP_LOGI(TAG, "wb-mqtt-bridge ESP32 firmware — phase 1 stub (IDF toolchain OK)");
    while (true) {
        vTaskDelay(pdMS_TO_TICKS(10000));
        ESP_LOGI(TAG, "alive");
    }
}
