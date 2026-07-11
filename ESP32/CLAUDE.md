# ESP32/ — subproject guide for Claude (and future me)

This directory is a **separate subproject** inside the locveil-bridge monorepo.
Different language (C++), different toolchain (PlatformIO + ESP-IDF), different
operating constraints (embedded, no Python, no FastAPI). The action-plan's
main-project conventions don't apply here.

## What this subproject is

A single firmware image that bridges four vintage AV transports
(Revox A77, Revox B215, Pioneer CLD-D925, Panasonic NV-FS90) to the Wirenboard
MQTT broker. Each box's identity is set once via a retained MQTT publish to
`/provision` — the same binary runs on every box.

Architecture: ~95 % shared core (Wi-Fi + auto-light-sleep + MQTT + NVS identity
+ OTA + dispatch + record-arming) lives in `src/main.cpp`, `src/wifi_setup.cpp`,
`src/wb_mqtt.cpp`, `src/identity.cpp`, `src/ota.cpp`. The ~5 % per-device
behaviour sits behind a single contract (`include/device_driver.h`):
`begin / doCommand / poll` function pointers in a `DeviceDriver` struct,
registered in `src/drivers.cpp`. **The shared core knows zero about decks.**

The authoritative spec is **`REQUIREMENTS.md`** (RFC 2119 MUST/SHOULD keywords).
Per-device hardware docs are in **`docs/`** (with manual scans / pinouts).

## STATUS — PARKED

> **Do not pull this into the active workstream unless the user explicitly
> reactivates it.** Tracked in `../docs/action_plan.md §5.1`. The scaffold +
> design docs are complete; first-light hardware verification + the bench
> data fill-ins (IR codes, B215 frame values, GPIO/timing tuning) wait for the
> "everything works in my home" milestone.

## Conventions

- **C++17.** No Arduino. Espressif IDF native APIs only (`esp_wifi_*`,
  `esp_mqtt_client_*`, `nvs_*`, `gpio_*`, `esp_https_ota`, FreeRTOS,
  `esp_timer`, `esp_log`). The Arduino-flavoured scaffold from the original
  browser-Claude generation lived under `_arduino_legacy/` during the Phase 2-4
  rewrite and was removed once the IDF port was complete (commit history holds
  it: pre-rename in commit `c2e266b`).
- **`.clang-format` shipped** (LLVM base, 4-space indent, 100-col). Run
  `clang-format -i src/*.cpp include/*.h` before committing source changes.
- **`DeviceDriver` is a C-style struct with function pointers** — idiomatic for
  embedded; allocated `const` in flash; not a virtual class. The fact that
  C++ gives namespace-scope `const` *internal* linkage by default means each
  driver definition MUST be prefixed with `extern` so the registry can find it
  (see `src/driver_*.cpp` end-of-file).
- **Bit-banging timing-critical sections** use `portDISABLE_INTERRUPTS()` +
  `esp_rom_delay_us`. If Wi-Fi coexistence jitter ever becomes a problem,
  consider the RMT peripheral (not worth the complexity until proven).
- **Logging.** `ESP_LOGI(TAG, …)` with a short module TAG ("main", "mqtt",
  "wifi", "ota", "a77", "b215", "ir", "identity").
- **TODOs in code are data fill-ins** (bench captures, GPIO confirmations,
  timing tuning) — NOT incomplete logic. Each is marked `TODO …` with the
  source of the missing value. The code itself is complete.

## Layout

```
ESP32/
├── README.md               quick-start (build / flash / provision)
├── REQUIREMENTS.md         the authoritative spec
├── CLAUDE.md               this file
├── platformio.ini          serial + ota envs (esp32dev board, framework=espidf)
├── partitions.csv          custom dual-OTA, 1.5 MB app slots
├── sdkconfig.defaults      project-level IDF defaults (source of truth)
├── .clang-format           code style
├── .gitignore              .pio/, include/config.h, sdkconfig.*, dependencies.lock
├── include/
│   ├── config.h.example    site-config template (Wi-Fi/MQTT/OTA placeholders)
│   ├── device_driver.h     the DeviceDriver contract + Control type
│   ├── identity.h          NVS-backed device-id persistence
│   ├── wifi_setup.h        STA + auto-light-sleep
│   ├── wb_mqtt.h           esp_mqtt_client + Wirenboard topic conventions
│   └── ota.h               MQTT-triggered esp_https_ota
├── src/
│   ├── CMakeLists.txt      explicit REQUIRES (esp_wifi/mqtt/driver/etc.)
│   ├── main.cpp            app_main entry; init order; record-arm timer
│   ├── identity.cpp        nvs_flash_init + nvs_get_str / nvs_set_str
│   ├── wifi_setup.cpp      esp_wifi_init / set_ps(MAX_MODEM) / event handler
│   ├── wb_mqtt.cpp         esp_mqtt_client + announce + dispatch + /provision
│   ├── ota.cpp             ota_trigger → FreeRTOS task → esp_https_ota
│   ├── drivers.cpp         id → driver registry
│   ├── driver_a77.cpp      opto-MOSFET WIST-10 + motion ISR + interlock
│   ├── driver_b215.cpp     SERIAL LINK bit-bang + status read-back hook
│   └── driver_ir.cpp       baseband IR (Pioneer + Panasonic share)
└── docs/                   per-device hardware build handoffs + img/ manual scans
```

## Build & flash (quick-start, full detail in `README.md`)

```bash
# One-time site config (real creds — file is gitignored)
cp include/config.h.example include/config.h && $EDITOR include/config.h

# Build (compile only)
~/.platformio/penv/bin/pio run -e serial

# First flash per box (USB serial — the only wired step, ever)
~/.platformio/penv/bin/pio run -e serial -t upload

# Set the box's identity over MQTT, no cable
mosquitto_pub -h <broker> -t /provision -r -m revox_b215

# Later updates: publish OTA URL (no cable, no PIO upload)
mosquitto_pub -h <broker> -t /devices/revox_b215/ota -m http://wb-ip:8000/firmware.bin
```

## Known setup gotchas

1. **PIO's bundled `framework-espidf 6.0.1` ships the `mqtt` component empty**
   (24 KB stub — `esp-mqtt` is a git submodule the tarball install doesn't
   fetch). The build will fail with
   *"Failed to resolve component 'mqtt' required by component 'src'"*.
   Fix on first setup of this machine:
   ```bash
   cp -r ~/esp/v5.5/esp-idf/components/mqtt/{CMakeLists.txt,esp-mqtt} \
         ~/.platformio/packages/framework-espidf/components/mqtt/
   ```
   `esp-mqtt` is API-stable across IDF 5.5 ↔ 6.0.1; the cross-version
   transplant builds + links cleanly. Not committed to the repo (the patch is
   under `~/.platformio/`).

2. **PIO's venv is missing `intelhex`** — esptool.py needs it but PIO doesn't
   auto-install. Fix once:
   ```bash
   ~/.platformio/penv/bin/pip install intelhex
   ```

3. **Adding/removing a `.cpp` under `src/`** requires a CMake reconfigure
   because `idf_component_register`'s GLOB doesn't track at build time
   (IDF doesn't allow `CONFIGURE_DEPENDS` in its component-scan mode):
   ```bash
   ~/.platformio/penv/bin/pio run -e serial -t fullclean
   ~/.platformio/penv/bin/pio run -e serial
   ```

4. **`pio` isn't on PATH** by default — it lives at
   `~/.platformio/penv/bin/pio`. Either add to PATH in your shell rc or use
   the absolute path.

## When you (Claude or future-me) come back

- Read `REQUIREMENTS.md` first. The MUST/SHOULD spec is the contract — anything
  here is supporting material.
- `docs/wb-*-esp32-bridge.md` are the per-device hardware handoffs — pinouts,
  schematics, BOM, build steps. Open the matching one for whichever deck you're
  bringing up.
- The TODOs in the driver source are **data** fill-ins, not bug stubs. The code
  is structurally complete.
- Don't reintroduce Arduino. Don't `#include <Arduino.h>`. Don't add ArduinoOTA.
- A separate IDF v5.5 install lives at `~/esp/v5.5/esp-idf` — PIO uses its own
  bundled IDF 6.0.1 + the mqtt-patch above. The standalone IDF is for direct
  `idf.py` work on other projects; this subproject doesn't depend on it
  beyond the one-time setup transplant.
