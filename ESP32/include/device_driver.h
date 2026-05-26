// device_driver.h — the contract every per-device driver implements.
//
// The shared core (main + wifi_setup + mqtt_client + identity) knows ONLY
// this interface; all deck-specific behaviour lives behind it. ~95% of the
// firmware is the core; a driver is the ~5%.
//
// IDF-clean: no Arduino, no Espressif platform headers — just <cstdint>.
#pragma once
#include <cstdint>

// Wirenboard control kind (drives the meta/type publish).
enum CtrlType { CT_PUSHBUTTON, CT_SWITCH };

struct Control {
    const char* name;       // e.g. "play"  → topic /devices/<id>/controls/play
    CtrlType    type;       // pushbutton (momentary) or switch (stateful)
    bool        is_record;  // record-safety gating applies (arm/confirm)
};

struct DeviceDriver {
    const char*    device_id;       // MQTT device id, e.g. "revox_b215"
    const char*    display_name;    // meta/name, e.g. "Revox B215"
    const Control* controls;
    uint8_t        n_controls;

    void (*begin)();                          // init GPIO / sensors
    bool (*doCommand)(const char* name);      // deliver command to the deck.
                                              //   returns false if blocked
                                              //   (interlock / disarmed)
    void (*poll)();                           // optional periodic — motion
                                              //   interlock, status read-back;
                                              //   may be nullptr
};

// Registered in drivers.cpp — returns the driver matching a stored device id,
// or nullptr.
const DeviceDriver* driver_for(const char* device_id);

// Helpers the core exposes TO drivers (implemented in mqtt_client.cpp +
// main.cpp respectively).
void wb_publish_value(const char* control, const char* value, bool retained = true);
bool record_is_armed();          // drivers gate `record` on this
void record_consume_arm();       // call after a successful record to disarm
