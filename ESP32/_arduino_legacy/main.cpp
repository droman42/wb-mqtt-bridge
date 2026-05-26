// main.cpp — SHARED CORE for all four bridge boxes (~95% of the firmware).
// Handles: Wi-Fi + light-sleep, MQTT (Wirenboard convention), OTA, command
// dispatch, record-arming. Knows nothing deck-specific — it only calls the
// active DeviceDriver's begin()/doCommand()/poll().
//
// ONE binary runs on all four boxes; each box's identity is stored in NVS.
#include <Arduino.h>
#include <WiFi.h>
#include <ArduinoOTA.h>
#include <PubSubClient.h>
#include <Preferences.h>
#include "config.h"
#include "device_driver.h"
#include "wb_mqtt.h"

WiFiClient   net;
PubSubClient mqtt(net);

static const DeviceDriver* drv = nullptr;
static Preferences prefs;
static char g_device_id[32] = {0};

// ---------- record-safety arming ----------
static uint32_t s_arm_until = 0;
bool record_is_armed()   { return millis() < s_arm_until; }
void record_consume_arm(){ s_arm_until = 0; }
static void record_arm() { s_arm_until = millis() + RECORD_ARM_WINDOW_MS; }

// ---------- identity (NVS) ----------
// Set once per box. Easiest: temporarily hardcode DEFAULT_ID for first flash of
// each box, OR send a retained MQTT msg to /provision/<mac> = "<device_id>".
// Here we read NVS; if empty, fall back to a compile-time default you can override.
#ifndef DEFAULT_ID
#define DEFAULT_ID ""   // leave empty in the shared image
#endif

static void loadIdentity() {
  prefs.begin("bridge", true);
  String id = prefs.getString("device_id", DEFAULT_ID);
  prefs.end();
  strncpy(g_device_id, id.c_str(), sizeof(g_device_id) - 1);
}

// Call this (e.g. from a serial command or provisioning topic) to set identity.
static void saveIdentity(const char* id) {
  prefs.begin("bridge", false);
  prefs.putString("device_id", id);
  prefs.end();
}

// ---------- MQTT callback ----------
static void onMqtt(char* topic, byte* payload, unsigned int len) {
  // build payload string
  String p; p.reserve(len);
  for (unsigned i = 0; i < len; i++) p += (char)payload[i];

  // provisioning: /provision sets identity then reboots
  if (strcmp(topic, "/provision") == 0 && p.length() && p.length() < 32) {
    saveIdentity(p.c_str());
    delay(100); ESP.restart();
    return;
  }

  const char* name = wb_match_command(topic);
  if (!name) return;
  if (p != "1") return;                 // act on "1" (button press / switch on)

  // find the control
  for (uint8_t i = 0; i < drv->n_controls; i++) {
    const Control& c = drv->controls[i];
    if (strcmp(c.name, name) != 0) continue;

    // record arming: an "arm" control (if the device defines one) sets the window.
    // Convention: a pushbutton named "arm_record" arms; record itself checks it.
    if (strcmp(name, "arm_record") == 0) { record_arm(); wb_publish_value("arm_record","1",true); return; }

    bool ok = drv->doCommand(name);     // <-- THE PER-DEVICE 5%
    // echo state: pushbuttons re-publish 0 (momentary); switches reflect requested state
    if (c.type == CT_SWITCH) wb_publish_value(name, ok ? "1" : "0", true);
    else                     wb_publish_value(name, "0", true);
    return;
  }
}

// ---------- Wi-Fi ----------
static void wifiConnect() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PSK);
  uint32_t t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < 20000) delay(200);
#if USE_WIFI_LIGHT_SLEEP
  WiFi.setSleep(true);     // automatic modem/light-sleep; DTIM wakes for buffered packets
#endif
}

// ---------- OTA ----------
static void otaSetup() {
  String host = String(OTA_HOSTNAME_PREFIX) + g_device_id;
  ArduinoOTA.setHostname(host.c_str());
  ArduinoOTA.setPassword(OTA_PASSWORD);
  // dual-partition + rollback is handled by the ESP32 OTA subsystem; a failed
  // image that doesn't mark itself valid is rolled back on next boot.
  ArduinoOTA.onStart([](){ /* could pause driver activity here */ });
  ArduinoOTA.begin();
}

// ---------- MQTT connect ----------
static void mqttConnect() {
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setKeepalive(MQTT_KEEPALIVE);
  mqtt.setBufferSize(MQTT_BUFFER);
  mqtt.setCallback(onMqtt);
  String cid = String("wbbridge-") + g_device_id;
  String lwt = String("/devices/") + g_device_id + "/meta/online";
  while (!mqtt.connected()) {
    bool ok = mqtt.connect(cid.c_str(), MQTT_USER, MQTT_PASS,
                           lwt.c_str(), 0, true, "0");   // last-will: online=0
    if (ok) break;
    delay(1000);
    if (WiFi.status() != WL_CONNECTED) wifiConnect();
  }
  mqtt.subscribe("/provision");
  wb_announce(drv);
}

// ---------- setup / loop ----------
void setup() {
  Serial.begin(115200);
  loadIdentity();

  if (g_device_id[0] == 0) {
    // No identity yet. Park safely: bring up Wi-Fi + OTA + provisioning only,
    // so you can set identity over MQTT (/provision) without a cable.
    wifiConnect();
    // minimal MQTT just for provisioning:
    mqtt.setServer(MQTT_HOST, MQTT_PORT);
    mqtt.setCallback(onMqtt);
    mqtt.setBufferSize(MQTT_BUFFER);
    mqtt.connect("wbbridge-unprovisioned");
    mqtt.subscribe("/provision");
    otaSetup();
    Serial.println("UNPROVISIONED: publish device id (retained) to topic /provision");
    return;
  }

  drv = driver_for(g_device_id);
  if (!drv) { Serial.printf("Unknown device id '%s'\n", g_device_id); }
  wb_init(g_device_id);
  if (drv && drv->begin) drv->begin();

  wifiConnect();
  otaSetup();
  mqttConnect();
}

void loop() {
  ArduinoOTA.handle();
  if (!mqtt.connected()) {
    if (WiFi.status() != WL_CONNECTED) wifiConnect();
    if (drv) mqttConnect();
  }
  mqtt.loop();
  if (drv && drv->poll) drv->poll();    // motion interlock / status read-back
  // No manual sleep: WiFi.setSleep(true) handles light-sleep between activity.
}
