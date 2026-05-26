// wifi_setup.h — Wi-Fi station-mode bring-up with automatic modem-sleep.
//
// Event-driven: kicks off association in the background and returns. The MQTT
// client will see its IP-up event and connect/reconnect on its own. We do NOT
// manually call esp_light_sleep_start() — esp_wifi_set_ps(WIFI_PS_MAX_MODEM)
// drives DTIM-based wakeups for buffered MQTT (REQUIREMENTS.md NFR-1).
#pragma once

// Initialize esp_netif + the default event loop + Wi-Fi station; set
// hostname to "wbbridge-<device_id>" (or "wbbridge-unprovisioned" when
// device_id is empty/null); configure credentials from config.h; start.
// Returns once esp_wifi_start() has been called — connection happens async.
void wifi_start(const char* device_id);

// True once we have an IP (event WIFI_EVENT_STA_GOT_IP). Polled by MQTT
// startup if it wants to wait, but normally MQTT is fire-and-forget — its
// own reconnect loop handles initial wait.
bool wifi_connected();
