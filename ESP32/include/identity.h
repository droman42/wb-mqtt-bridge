// identity.h — per-box identity persisted in NVS (namespace "bridge", key
// "device_id"). Set once at first boot via the MQTT `/provision` topic; the
// same firmware image runs on every box.
#pragma once
#include <cstddef>

// Initialize NVS subsystem. Must be called once at startup before any other
// identity_* / NVS API. Wraps nvs_flash_init() + the recover-on-corruption dance.
void identity_init_nvs();

// Load device_id from NVS into dst (zero-terminated). Returns true if a
// non-empty id was found; false if NVS is empty or the key is missing.
bool identity_load(char* dst, size_t cap);

// Persist device_id to NVS. Returns true on success.
bool identity_save(const char* device_id);
