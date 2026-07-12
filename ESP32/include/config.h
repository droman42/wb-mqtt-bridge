// config.h — site config + per-box identity.
//
// ╔═══════════════════════════════════════════════════════════════════════════╗
// ║ This is a TEMPLATE (config.h.example, committed). Copy to config.h and    ║
// ║ fill in your real credentials — that copy is .gitignored:                 ║
// ║     cp include/config.h.example include/config.h                          ║
// ║ Then edit include/config.h. Never commit real creds.                      ║
// ╚═══════════════════════════════════════════════════════════════════════════╝
//
// Wi-Fi/MQTT/OTA are the same for all four boxes (one OTA image).
// The per-box DEVICE IDENTITY is stored in NVS (flash) so the SAME binary
// runs on every box; you set it once at first boot (see main.cpp setIdentity()).
#pragma once

// ---- Wi-Fi ----
#define WIFI_SSID      "YOUR_SSID"
#define WIFI_PSK       "YOUR_PSK"

// ---- MQTT (Wirenboard Mosquitto broker) ----
#define MQTT_HOST      "192.168.1.10"   // the Wirenboard controller
#define MQTT_PORT      1883
#define MQTT_USER      ""               // set if your broker requires auth
#define MQTT_PASS      ""
#define MQTT_KEEPALIVE 45               // s; comfortably > DTIM wake cycle
#define MQTT_BUFFER    1024             // PubSubClient default (256) is too small for meta topics

// ---- OTA (network update — MANDATORY per build docs) ----
// First flash is over serial; thereafter ALL updates are OTA. No USB after that.
#define OTA_HOSTNAME_PREFIX "wbbridge-" // + device_id
#define OTA_PASSWORD        "CHANGE_ME_OTA"

// ---- Light-sleep ----
// We use automatic Wi-Fi modem/light-sleep (WiFi.setSleep(true)). DTIM beacons
// wake the radio to receive buffered MQTT commands. DO NOT hand-call
// esp_light_sleep_start() in loop() — it would suspend the stack's beacon handling.
#define USE_WIFI_LIGHT_SLEEP 1

// ---- Record safety ----
#define RECORD_ARM_WINDOW_MS 8000       // after an "arm", record allowed for this long

// ---- Valid device ids (must match a driver in drivers.cpp) ----
// Set per box once: see main.cpp — call over serial or via a retained MQTT
// provisioning topic /devices/<id>/identity. Stored in NVS namespace "bridge".
