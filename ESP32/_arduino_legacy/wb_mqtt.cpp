// wb_mqtt.cpp — Wirenboard topic conventions.
#include "wb_mqtt.h"
#include <PubSubClient.h>

extern PubSubClient mqtt;   // owned by main.cpp

static char s_prefix[64];   // "/devices/<id>"

void wb_init(const char* device_id) {
  snprintf(s_prefix, sizeof(s_prefix), "/devices/%s", device_id);
}

static void pub(const String& topic, const String& payload, bool retained) {
  mqtt.publish(topic.c_str(), payload.c_str(), retained);
}

void wb_announce(const DeviceDriver* drv) {
  // device display name
  pub(String(s_prefix) + "/meta/name", drv->display_name, true);

  for (uint8_t i = 0; i < drv->n_controls; i++) {
    const Control& c = drv->controls[i];
    String base = String(s_prefix) + "/controls/" + c.name;
    pub(base + "/meta/type", c.type == CT_SWITCH ? "switch" : "pushbutton", true);
    // initial value 0
    pub(base, "0", true);
    // subscribe to the command topic
    String onTopic = base + "/on";
    mqtt.subscribe(onTopic.c_str());
  }
  // a small "online" indicator
  pub(String(s_prefix) + "/meta/online", "1", true);
}

void wb_publish_value(const char* control, const char* value, bool retained) {
  pub(String(s_prefix) + "/controls/" + control, value, retained);
}

// If topic == "/devices/<id>/controls/<name>/on", return pointer to <name>
// (in a static buffer); else nullptr.
const char* wb_match_command(const char* topic) {
  static char name[32];
  String pfx = String(s_prefix) + "/controls/";
  if (strncmp(topic, pfx.c_str(), pfx.length()) != 0) return nullptr;
  const char* rest = topic + pfx.length();           // "<name>/on"
  const char* slash = strchr(rest, '/');
  if (!slash || strcmp(slash, "/on") != 0) return nullptr;
  size_t len = slash - rest;
  if (len >= sizeof(name)) return nullptr;
  memcpy(name, rest, len); name[len] = 0;
  return name;
}
