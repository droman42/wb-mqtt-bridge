// main.cpp — shared core entry. Init NVS → load identity → start Wi-Fi & MQTT
// → drop into a polling loop that pumps the active driver's poll() and the
// record-arming timer.
//
// The actual work runs in IDF tasks (Wi-Fi, esp_event, mqtt_client). app_main
// only does init + the driver-poll heartbeat; OTA (Phase 3) plugs in here.

#include "config.h"
#include "device_driver.h"
#include "identity.h"
#include "wb_mqtt.h"
#include "wifi_setup.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <cstring>

static const char* TAG = "main";

// ---- record-safety arming -------------------------------------------------
// Drivers gate `record` on record_is_armed(); the MQTT layer calls record_arm()
// when it sees an "arm_record" press.
static int64_t s_arm_until_us = 0;
bool record_is_armed()    { return esp_timer_get_time() < s_arm_until_us; }
void record_consume_arm() { s_arm_until_us = 0; }
void record_arm()         { s_arm_until_us = esp_timer_get_time() + (int64_t)RECORD_ARM_WINDOW_MS * 1000LL; }

// ---- entry ----------------------------------------------------------------

extern "C" void app_main(void) {
    ESP_LOGI(TAG, "wb-mqtt-bridge ESP32 firmware boot");

    // 1) NVS subsystem (Wi-Fi creds storage also depends on this)
    identity_init_nvs();

    // 2) Load identity (may be empty on first boot of a virgin box)
    char device_id[32] = {0};
    identity_load(device_id, sizeof(device_id));

    // 3) Resolve driver — may be nullptr (unprovisioned, or unknown id)
    const DeviceDriver* drv = driver_for(device_id);
    if (device_id[0] == '\0') {
        ESP_LOGW(TAG, "UNPROVISIONED — publish identity (retained) to /provision, e.g.:");
        ESP_LOGW(TAG, "  mosquitto_pub -h <broker> -t /provision -r -m revox_b215");
    } else if (!drv) {
        ESP_LOGE(TAG, "identity '%s' is set but no matching driver — staying degraded", device_id);
    } else {
        ESP_LOGI(TAG, "identity=%s → driver %s", device_id, drv->display_name);
        if (drv->begin) drv->begin();
    }

    // 4) Wi-Fi + MQTT (both fire-and-forget; auto-reconnect internally)
    wifi_start(device_id);
    mqtt_start(device_id, drv);

    // 5) Heartbeat + driver poll (motion interlock / status read-back / etc.)
    const TickType_t poll_period = pdMS_TO_TICKS(100);
    uint32_t tick = 0;
    while (true) {
        if (drv && drv->poll) drv->poll();
        if ((++tick % 100) == 0) {  // ~every 10s
            ESP_LOGI(TAG, "alive (wifi=%d, identity=%s)",
                     (int)wifi_connected(),
                     device_id[0] ? device_id : "<unprovisioned>");
        }
        vTaskDelay(poll_period);
    }
}
