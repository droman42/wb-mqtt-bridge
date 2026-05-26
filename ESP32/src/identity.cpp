// identity.cpp — NVS-backed device-id persistence.
#include "identity.h"
#include "esp_log.h"
#include "nvs.h"
#include "nvs_flash.h"
#include <cstring>

static const char* TAG     = "identity";
static const char* NS      = "bridge";
static const char* KEY_ID  = "device_id";

void identity_init_nvs() {
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        // First boot on this chip / partition layout changed. Erase + re-init.
        ESP_ERROR_CHECK(nvs_flash_erase());
        err = nvs_flash_init();
    }
    ESP_ERROR_CHECK(err);
}

bool identity_load(char* dst, size_t cap) {
    if (!dst || cap == 0) return false;
    dst[0] = '\0';

    nvs_handle_t h;
    esp_err_t err = nvs_open(NS, NVS_READONLY, &h);
    if (err != ESP_OK) {
        ESP_LOGD(TAG, "nvs_open(%s) failed: %s", NS, esp_err_to_name(err));
        return false;
    }

    size_t len = cap;
    err = nvs_get_str(h, KEY_ID, dst, &len);
    nvs_close(h);

    if (err != ESP_OK || dst[0] == '\0') {
        ESP_LOGI(TAG, "no identity in NVS — unprovisioned");
        dst[0] = '\0';
        return false;
    }
    ESP_LOGI(TAG, "loaded identity: %s", dst);
    return true;
}

bool identity_save(const char* device_id) {
    if (!device_id || !*device_id) return false;

    nvs_handle_t h;
    esp_err_t err = nvs_open(NS, NVS_READWRITE, &h);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "nvs_open RW failed: %s", esp_err_to_name(err));
        return false;
    }

    err = nvs_set_str(h, KEY_ID, device_id);
    if (err == ESP_OK) err = nvs_commit(h);
    nvs_close(h);

    if (err != ESP_OK) {
        ESP_LOGE(TAG, "nvs_set_str/commit failed: %s", esp_err_to_name(err));
        return false;
    }
    ESP_LOGI(TAG, "saved identity: %s", device_id);
    return true;
}
