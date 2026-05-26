// device_driver.h — the contract every per-device driver implements.
// The shared core (main.cpp) knows ONLY this interface; all deck-specific
// behaviour lives behind it. ~95% of the firmware is the core; a driver is the ~5%.
#pragma once
#include <Arduino.h>

// Wirenboard control type
enum CtrlType { CT_PUSHBUTTON, CT_SWITCH };

struct Control {
  const char* name;     // e.g. "play"  -> topic /devices/<id>/controls/play
  CtrlType    type;     // pushbutton (momentary) or switch (stateful)
  bool        is_record; // record-safety gating applies (arm/confirm)
};

struct DeviceDriver {
  const char*    device_id;     // MQTT device id, e.g. "revox_b215"
  const char*    display_name;  // meta/name, e.g. "Revox B215"
  const Control* controls;
  uint8_t        n_controls;

  void (*begin)();                          // init GPIO / sensors
  bool (*doCommand)(const char* name);      // deliver command to deck.
                                            //   return false if blocked (e.g. interlock/disarmed)
  void (*poll)();                           // periodic: motion interlock, status read-back (may be null)

  // Optional: a driver can publish extra read-only value topics by calling
  // wb_publish_value() from its poll(); the core exposes that helper.
};

// Provided by drivers.cpp: returns the driver matching a stored device id, or nullptr.
const DeviceDriver* driver_for(const char* device_id);

// Helpers the core exposes TO drivers (defined in main.cpp / wb_mqtt.cpp):
void wb_publish_value(const char* control, const char* value, bool retained = true);
bool record_is_armed();          // drivers gate record on this
void record_consume_arm();       // call after a successful record to re-disarm
