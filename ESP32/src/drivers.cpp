// drivers.cpp — registry mapping a stored device id to its driver.
//
// PHASE 2 stub: no drivers registered yet. Phase 4 adds the real ones (a77 /
// b215 / pioneer + panasonic via driver_ir.cpp). Until then, the firmware
// boots, connects Wi-Fi/MQTT, subscribes to /provision — but driver_for()
// returns nullptr for every id, so the device sits in unprovisioned mode and
// no controls are announced. That exercises the whole core wiring.
#include "device_driver.h"
#include <cstring>

// Phase 4 will add: extern const DeviceDriver DRIVER_A77;
//                   extern const DeviceDriver DRIVER_B215;
//                   extern const DeviceDriver DRIVER_PIONEER;
//                   extern const DeviceDriver DRIVER_PANASONIC;

static const DeviceDriver* const ALL[] = {
    // populated in Phase 4
};
static const size_t N = sizeof(ALL) / sizeof(ALL[0]);

const DeviceDriver* driver_for(const char* device_id) {
    if (!device_id || !*device_id) return nullptr;
    for (size_t i = 0; i < N; i++) {
        if (std::strcmp(ALL[i]->device_id, device_id) == 0) return ALL[i];
    }
    return nullptr;
}
