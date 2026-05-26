// drivers.cpp — registry mapping a stored device id to its driver.
// Adding a 5th deck later = write one driver file + add one line here.
#include "device_driver.h"
#include <cstring>

extern const DeviceDriver DRIVER_A77;
extern const DeviceDriver DRIVER_B215;
extern const DeviceDriver DRIVER_PIONEER;
extern const DeviceDriver DRIVER_PANASONIC;

static const DeviceDriver* const ALL[] = {
    &DRIVER_A77, &DRIVER_B215, &DRIVER_PIONEER, &DRIVER_PANASONIC,
};
static const size_t N = sizeof(ALL) / sizeof(ALL[0]);

const DeviceDriver* driver_for(const char* device_id) {
    if (!device_id || !*device_id) return nullptr;
    for (size_t i = 0; i < N; i++) {
        if (std::strcmp(ALL[i]->device_id, device_id) == 0) return ALL[i];
    }
    return nullptr;
}
