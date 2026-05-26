// wifi_setup.cpp — STA-mode bring-up + DTIM-driven modem-sleep.
//
// Uses the IDF event loop (default). On WIFI_EVENT_STA_START / DISCONNECTED we
// (re)issue esp_wifi_connect; on IP_EVENT_STA_GOT_IP we flip the connected
// flag. esp_wifi_set_ps(WIFI_PS_MAX_MODEM) drives the auto-light-sleep that
// keeps average current ≈15 mA (REQUIREMENTS.md NFR-1).
#include "wifi_setup.h"
#include "config.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "nvs_flash.h"
#include <cstring>
#include <cstdio>

static const char* TAG = "wifi";
static volatile bool s_connected = false;

static void on_wifi_event(void* arg, esp_event_base_t base, int32_t id, void* data) {
    if (base == WIFI_EVENT) {
        switch (id) {
            case WIFI_EVENT_STA_START:
                ESP_LOGI(TAG, "STA start → connect");
                esp_wifi_connect();
                break;
            case WIFI_EVENT_STA_DISCONNECTED:
                s_connected = false;
                ESP_LOGW(TAG, "disconnected → reconnect");
                esp_wifi_connect();
                break;
            default: break;
        }
    } else if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
        s_connected = true;
        ip_event_got_ip_t* e = (ip_event_got_ip_t*)data;
        ESP_LOGI(TAG, "got IP: " IPSTR, IP2STR(&e->ip_info.ip));
    }
}

void wifi_start(const char* device_id) {
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());

    esp_netif_t* netif = esp_netif_create_default_wifi_sta();

    // Hostname (for mDNS / DHCP) — "wbbridge-<id>" or "...-unprovisioned"
    char host[40];
    snprintf(host, sizeof(host), "%s%s",
             OTA_HOSTNAME_PREFIX,
             (device_id && *device_id) ? device_id : "unprovisioned");
    esp_netif_set_hostname(netif, host);

    wifi_init_config_t init_cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&init_cfg));

    ESP_ERROR_CHECK(esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, on_wifi_event, nullptr));
    ESP_ERROR_CHECK(esp_event_handler_register(IP_EVENT,   IP_EVENT_STA_GOT_IP, on_wifi_event, nullptr));

    wifi_config_t cfg = {};
    std::strncpy((char*)cfg.sta.ssid,     WIFI_SSID, sizeof(cfg.sta.ssid));
    std::strncpy((char*)cfg.sta.password, WIFI_PSK,  sizeof(cfg.sta.password));
    cfg.sta.threshold.authmode = WIFI_AUTH_WPA2_PSK;

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &cfg));
    ESP_ERROR_CHECK(esp_wifi_start());

#if USE_WIFI_LIGHT_SLEEP
    // Max-modem-sleep: radio off between DTIM beacons. AP buffers MQTT
    // packets and flags them on the next beacon; radio wakes briefly to
    // receive. Latency ~0.1–1 s — fine for transport control.
    ESP_ERROR_CHECK(esp_wifi_set_ps(WIFI_PS_MAX_MODEM));
#else
    ESP_ERROR_CHECK(esp_wifi_set_ps(WIFI_PS_NONE));
#endif

    ESP_LOGI(TAG, "Wi-Fi started (hostname=%s, SSID=%s)", host, WIFI_SSID);
}

bool wifi_connected() { return s_connected; }
