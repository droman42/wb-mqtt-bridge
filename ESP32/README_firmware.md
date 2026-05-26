# Bridge firmware — shared core + per-device drivers (one image, four decks)

One PlatformIO/Arduino-ESP32 firmware runs on **all four** bridge boxes. ~95% is shared;
each deck contributes a thin driver (~5%). Same binary everywhere; each box's identity is
stored in flash (NVS) and set once **without a cable** (over MQTT).

## The 95 / 5 split
**Shared core (`main.cpp`, `wb_mqtt.*`)** — identical for all four:
- Wi-Fi + **automatic light-sleep** (`WiFi.setSleep(true)`; DTIM wakes for buffered MQTT).
- MQTT (PubSubClient): connect, last-will `meta/online=0`, reconnect, keepalive, big buffer.
- **Wirenboard convention**: retained `meta/name`, per-control `meta/type`
  (pushbutton/switch), value topics, subscribe `<ctrl>/on`, echo state.
- **OTA** (ArduinoOTA, password, ESP32 dual-partition rollback) — network update is mandatory.
- Command dispatch + **record-arming** (`arm_record` opens an 8 s window; `record` checks it).
- Runtime **device identity** via NVS + `/provision` topic.

**Per-device driver (the ~5%)** — implements `DeviceDriver` (`device_driver.h`):
| Driver | File | Primitive |
|---|---|---|
| B215 | `driver_b215.cpp` | ITT serial-link bit-bang on open-collector pin 3 (+ status read-back hook) |
| A77 | `driver_a77.cpp` | opto-MOSFET pin-pair pulses, REC=PLAY+REC, **reel-motion rewind interlock** |
| Pioneer + Panasonic | `driver_ir.cpp` | **baseband IR emit** (carrier-off) — SHARED by both |

So really **three drivers** for four decks (Pioneer and Panasonic are the same code, different
code tables). `drivers.cpp` maps device id -> driver.

## Per-box setup (no cable after first flash)
1. **First flash over USB-serial** (the only wired step), same image to every box:
   `pio run -e serial -t upload`
2. **Set identity over MQTT** (retained), no cable:
   `mosquitto_pub -h <broker> -t /provision -r -m revox_b215`
   (valid ids: `revox_b215`, `revox_a77`, `pioneer_cld_d925`, `panasonic_nv_fs90`)
   The box stores it in NVS, reboots, and comes up as that device.
3. **All later updates are OTA:** `pio run -e ota -t upload` (set `upload_port` to the box's
   `wbbridge-<id>.local` or IP). USB is never needed again.

## What you MUST fill in (bench data — left as clearly-marked TODOs)
- **driver_ir.cpp** — replace the placeholder timing arrays with **your exported Wirenboard
  blaster codes** (raw mark/space us, carrier OFF). Pioneer + Panasonic command tables.
- **driver_b215.cpp** — `LINK_INVERT`, bit-timing constants, and the per-function frame values
  from your B205 scope captures.
- **driver_a77.cpp** — confirm the GPIO->pin-pair mapping, tune `PRESS_MS`,
  `MOTION_WINDOW_MS`, `POST_STOP_DELAY`, and the motion-sensor pin.
- **config.h** — Wi-Fi/MQTT/OTA credentials, broker IP.
- **GPIO numbers** in each driver — set to your actual WROOM-32 wiring (avoid input-only
  GPIO 34–39 for outputs; they're used here only for inputs/status).

## Light-sleep + MQTT (why commands still arrive)
`WiFi.setSleep(true)` keeps the association + MQTT session alive while dozing (~15 mA avg);
the AP buffers a command and flags it on the next DTIM beacon; the radio wakes briefly, the
`onMqtt()` callback fires, the driver acts. Latency ~0.1–1 s — fine for transport control.
**Do not** hand-call `esp_light_sleep_start()` — let the Wi-Fi power-save manage DTIM.

## Files
```
platformio.ini          build + serial/OTA envs
include/device_driver.h  the DeviceDriver contract + Control type
include/config.h         site creds, OTA, timings
src/main.cpp             shared core (Wi-Fi/sleep/MQTT/OTA/dispatch/arming/identity)
src/wb_mqtt.{h,cpp}      Wirenboard topic helpers
src/driver_b215.cpp      B215 serial link (+status hook)
src/driver_a77.cpp       A77 contacts + interlock
src/driver_ir.cpp        Pioneer + Panasonic baseband IR (shared)
src/drivers.cpp          id -> driver registry
```

## Notes / honest caveats
- This compiles against Arduino-ESP32 + PubSubClient, but is a **scaffold**: the TODO timing/
  code tables are placeholders — it will build and connect, but won't drive a deck correctly
  until you fill in your captured codes/frames and verify pin polarity on a scope.
- `delayMicroseconds()` bit-banging inside `noInterrupts()` is fine for short IR/serial frames;
  if Wi-Fi coexistence ever jitters timing, consider the RMT peripheral for the IR/serial emit.
- Record safety: `record` is refused unless `arm_record` was pressed within the window. Keep
  this — it prevents a stray MQTT message recording over a tape.
