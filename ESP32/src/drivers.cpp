// drivers.cpp — registry mapping a stored device id to its driver.
// Adding a 5th deck later = write one driver + add one line here.
#include "device_driver.h"

extern const DeviceDriver DRIVER_B215;
extern const DeviceDriver DRIVER_A77;
extern const DeviceDriver DRIVER_PIONEER;
extern const DeviceDriver DRIVER_PANASONIC;

static const DeviceDriver* ALL[] = {
  &DRIVER_B215, &DRIVER_A77, &DRIVER_PIONEER, &DRIVER_PANASONIC,
};

const DeviceDriver* driver_for(const char* device_id) {
  for (auto d : ALL) if (!strcmp(d->device_id, device_id)) return d;
  return nullptr;
}
