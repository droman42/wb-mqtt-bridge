// mqtt_client.cpp — esp_mqtt_client wired to the Wirenboard topic convention.
//
// Topics:
//   /provision                       (subscribed) — payload = device id; stored
//                                                   in NVS, then reboot.
//   /devices/<id>/meta/name          (retained pub on connect)
//   /devices/<id>/meta/online        (retained pub "1" on connect; LWT "0")
//   /devices/<id>/controls/<c>/meta/type   (retained pub on connect)
//   /devices/<id>/controls/<c>             (retained pub; state echo)
//   /devices/<id>/controls/<c>/on    (subscribed) — command in
//
// Drivers reach the publish helper via wb_publish_value (device_driver.h) →
// mqtt_publish_value_internal.
#include "wb_mqtt.h"
#include "device_driver.h"
#include "identity.h"
#include "ota.h"
#include "config.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_system.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <mqtt_client.h>            // IDF: esp_mqtt_client (esp_mqtt component)
#include <cstdio>
#include <cstring>

static const char* TAG = "mqtt";

static esp_mqtt_client_handle_t s_client = nullptr;
static const DeviceDriver*      s_drv    = nullptr;
static char                     s_device_id[32] = {0};
static char                     s_prefix[64]    = {0};  // "/devices/<id>"

// ---- small helpers --------------------------------------------------------

static void pub(const char* topic, const char* payload, int qos, bool retain) {
    esp_mqtt_client_publish(s_client, topic, payload, 0 /* len=auto */, qos, retain ? 1 : 0);
}

static void publish_meta_and_subscribe(const DeviceDriver* drv) {
    // device-level meta
    char t[160];
    std::snprintf(t, sizeof(t), "%s/meta/name", s_prefix);     pub(t, drv->display_name, 1, true);
    std::snprintf(t, sizeof(t), "%s/meta/online", s_prefix);   pub(t, "1", 1, true);

    // per-control meta + initial value + /on subscribe
    for (uint8_t i = 0; i < drv->n_controls; i++) {
        const Control& c = drv->controls[i];
        std::snprintf(t, sizeof(t), "%s/controls/%s/meta/type", s_prefix, c.name);
        pub(t, c.type == CT_SWITCH ? "switch" : "pushbutton", 1, true);

        std::snprintf(t, sizeof(t), "%s/controls/%s", s_prefix, c.name);
        pub(t, "0", 1, true);

        std::snprintf(t, sizeof(t), "%s/controls/%s/on", s_prefix, c.name);
        esp_mqtt_client_subscribe(s_client, t, 1);
    }
    ESP_LOGI(TAG, "announced %s (%u controls)", drv->device_id, drv->n_controls);
}

// Extract `<name>` from "<s_prefix>/controls/<name>/on", or nullptr if it
// doesn't match. Writes into a small static buffer.
static const char* match_command_topic(const char* topic, int topic_len) {
    static char name[32];
    int plen = std::strlen(s_prefix);
    const char* base = "/controls/";
    int blen = std::strlen(base);

    if (topic_len <= plen + blen + 4) return nullptr;
    if (std::strncmp(topic, s_prefix, plen) != 0) return nullptr;
    if (std::strncmp(topic + plen, base, blen) != 0) return nullptr;

    const char* rest = topic + plen + blen;       // "<name>/on"
    int rest_len = topic_len - (plen + blen);
    const char* slash = (const char*)std::memchr(rest, '/', rest_len);
    if (!slash || (rest_len - (slash - rest)) != 3 /* "/on" */) return nullptr;
    if (std::strncmp(slash, "/on", 3) != 0) return nullptr;

    size_t name_len = slash - rest;
    if (name_len >= sizeof(name)) return nullptr;
    std::memcpy(name, rest, name_len);
    name[name_len] = '\0';
    return name;
}

// ---- record-arming gate (definition lives in main.cpp) --------------------
extern bool record_is_armed();
extern void record_consume_arm();
extern void record_arm();

// ---- dispatch -------------------------------------------------------------

static void dispatch(const char* name, const char* payload, int payload_len) {
    // Only act on "1" (button press / switch-on). Stays consistent with the
    // Wirenboard convention.
    if (payload_len != 1 || payload[0] != '1') return;

    // record-arming control is core-handled (the driver only knows record).
    if (std::strcmp(name, "arm_record") == 0) {
        record_arm();
        char t[160];
        std::snprintf(t, sizeof(t), "%s/controls/arm_record", s_prefix);
        pub(t, "1", 1, true);
        return;
    }

    if (!s_drv) {
        ESP_LOGW(TAG, "dispatch '%s' but no driver active", name);
        return;
    }

    // locate the control + execute
    for (uint8_t i = 0; i < s_drv->n_controls; i++) {
        const Control& c = s_drv->controls[i];
        if (std::strcmp(c.name, name) != 0) continue;

        bool ok = s_drv->doCommand(name);
        char t[160];
        std::snprintf(t, sizeof(t), "%s/controls/%s", s_prefix, c.name);
        // pushbutton → republish "0" (momentary); switch → "1"/"0" per ok
        pub(t, c.type == CT_SWITCH ? (ok ? "1" : "0") : "0", 1, true);
        return;
    }
    ESP_LOGW(TAG, "no such control: '%s'", name);
}

// ---- provision handler ----------------------------------------------------

static void handle_provision(const char* payload, int payload_len) {
    if (payload_len <= 0 || payload_len >= 32) {
        ESP_LOGW(TAG, "ignored /provision payload of length %d", payload_len);
        return;
    }
    char id[32];
    std::memcpy(id, payload, payload_len);
    id[payload_len] = '\0';

    ESP_LOGI(TAG, "provision → device_id=%s; saving + reboot", id);
    if (identity_save(id)) {
        // small grace before restart so the broker can ack the publish
        vTaskDelay(pdMS_TO_TICKS(200));
        esp_restart();
    }
}

// ---- event handler --------------------------------------------------------

static void on_mqtt_event(void* arg, esp_event_base_t base, int32_t id, void* data) {
    auto* e = (esp_mqtt_event_handle_t)data;
    switch ((esp_mqtt_event_id_t)id) {
        case MQTT_EVENT_CONNECTED: {
            ESP_LOGI(TAG, "connected");
            // /provision is always subscribed (provisioned or not)
            esp_mqtt_client_subscribe(s_client, "/provision", 1);
            // /devices/<id>/ota — OTA URL trigger (always subscribed when
            // we have an identity; ignored in unprovisioned mode).
            if (s_device_id[0]) {
                char t[160];
                std::snprintf(t, sizeof(t), "%s/ota", s_prefix);
                esp_mqtt_client_subscribe(s_client, t, 1);
            }
            if (s_drv) publish_meta_and_subscribe(s_drv);
            break;
        }
        case MQTT_EVENT_DISCONNECTED:
            ESP_LOGW(TAG, "disconnected (will auto-reconnect)");
            break;
        case MQTT_EVENT_DATA: {
            // Topics + payloads are NOT zero-terminated in IDF events.
            if (e->topic_len == (int)std::strlen("/provision") &&
                std::strncmp(e->topic, "/provision", e->topic_len) == 0) {
                handle_provision(e->data, e->data_len);
                return;
            }
            // OTA trigger: /devices/<id>/ota with payload = .bin URL
            char ota_t[160];
            int ota_len = std::snprintf(ota_t, sizeof(ota_t), "%s/ota", s_prefix);
            if (e->topic_len == ota_len &&
                std::strncmp(e->topic, ota_t, ota_len) == 0) {
                // payload isn't zero-terminated; ota_trigger strdups it for us
                char url[256];
                int n = (e->data_len < (int)sizeof(url) - 1) ? e->data_len : (int)sizeof(url) - 1;
                std::memcpy(url, e->data, n); url[n] = '\0';
                ota_trigger(url);
                return;
            }
            const char* name = match_command_topic(e->topic, e->topic_len);
            if (!name) return;
            dispatch(name, e->data, e->data_len);
            break;
        }
        case MQTT_EVENT_ERROR:
            ESP_LOGE(TAG, "MQTT error");
            break;
        default: break;
    }
}

// ---- start ----------------------------------------------------------------

void mqtt_start(const char* device_id, const DeviceDriver* drv) {
    s_drv = drv;
    std::strncpy(s_device_id, device_id ? device_id : "unprovisioned", sizeof(s_device_id) - 1);
    std::snprintf(s_prefix, sizeof(s_prefix), "/devices/%s", s_device_id);

    char uri[64];
    std::snprintf(uri, sizeof(uri), "mqtt://%s:%d", MQTT_HOST, MQTT_PORT);

    char client_id[48];
    std::snprintf(client_id, sizeof(client_id), "wbbridge-%s", s_device_id);

    char lwt_topic[80];
    std::snprintf(lwt_topic, sizeof(lwt_topic), "/devices/%s/meta/online", s_device_id);

    esp_mqtt_client_config_t cfg = {};
    cfg.broker.address.uri               = uri;
    cfg.credentials.client_id            = client_id;
    cfg.credentials.username             = (MQTT_USER[0] ? MQTT_USER : nullptr);
    cfg.credentials.authentication.password = (MQTT_PASS[0] ? MQTT_PASS : nullptr);
    cfg.session.keepalive                = MQTT_KEEPALIVE;
    cfg.session.last_will.topic          = lwt_topic;
    cfg.session.last_will.msg            = "0";
    cfg.session.last_will.msg_len        = 1;
    cfg.session.last_will.qos            = 1;
    cfg.session.last_will.retain         = 1;

    s_client = esp_mqtt_client_init(&cfg);
    esp_mqtt_client_register_event(s_client, MQTT_EVENT_ANY, on_mqtt_event, nullptr);
    esp_mqtt_client_start(s_client);
    ESP_LOGI(TAG, "MQTT client started (broker=%s, id=%s)", uri, client_id);
}

void mqtt_publish_value_internal(const char* control, const char* value, bool retained) {
    if (!s_client) return;
    char t[160];
    std::snprintf(t, sizeof(t), "%s/controls/%s", s_prefix, control);
    pub(t, value, 1, retained);
}

// wb_publish_value (declared in device_driver.h) — provided here so drivers
// reach the MQTT client without including its header directly.
void wb_publish_value(const char* control, const char* value, bool retained) {
    mqtt_publish_value_internal(control, value, retained);
}
