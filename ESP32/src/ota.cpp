// ota.cpp — esp_https_ota driver, kicked off from an MQTT message in wb_mqtt.
//
// HTTPS in the name; HTTP also works (the LAN-hosted .bin case). For real
// HTTPS pin a CA cert via cert_pem (CONFIG_ESP_TLS_USE_DS_PERIPHERAL etc).
#include "ota.h"
#include "esp_http_client.h"
#include "esp_https_ota.h"
#include "esp_log.h"
#include "esp_system.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <cstring>
#include <cstdlib>

static const char* TAG = "ota";

static void ota_task(void* arg) {
    char* url = static_cast<char*>(arg);
    ESP_LOGI(TAG, "OTA start: %s", url);

    esp_http_client_config_t http_cfg = {};
    http_cfg.url               = url;
    http_cfg.timeout_ms        = 30000;
    http_cfg.keep_alive_enable = true;

    esp_https_ota_config_t ota_cfg = {};
    ota_cfg.http_config = &http_cfg;

    esp_err_t err = esp_https_ota(&ota_cfg);
    if (err == ESP_OK) {
        ESP_LOGI(TAG, "OTA OK — restarting in 1 s");
        vTaskDelay(pdMS_TO_TICKS(1000));
        esp_restart();
        // unreachable
    } else {
        ESP_LOGE(TAG, "OTA failed: %s", esp_err_to_name(err));
    }

    free(url);
    vTaskDelete(nullptr);
}

void ota_trigger(const char* url) {
    if (!url || !*url) {
        ESP_LOGW(TAG, "ignored empty OTA url");
        return;
    }

    // Copy URL onto the heap — the task owns it and frees on exit. (The MQTT
    // event-handler frame goes away before the task gets scheduled.)
    char* dup = strdup(url);
    if (!dup) {
        ESP_LOGE(TAG, "strdup OOM");
        return;
    }

    // HTTPS + OTA + esp_event use a lot of stack; 8 KB is the IDF-suggested
    // minimum for the simple path.
    BaseType_t r = xTaskCreate(ota_task, "ota", 8192, dup, 5, nullptr);
    if (r != pdPASS) {
        ESP_LOGE(TAG, "xTaskCreate failed");
        free(dup);
    }
}
