# ESP32 bridge firmware — Requirements

Authoritative spec for the single PlatformIO/Arduino-ESP32 firmware image that
bridges four vintage AV transports (Revox A77, Revox B215, Pioneer CLD-D925,
Panasonic NV-FS90) to the Wirenboard MQTT broker.

Keywords (MUST / MUST NOT / SHOULD / MAY) per RFC 2119.

**Status:** scaffold complete; bench data (driver fill-ins below) and first-light
hardware verification deferred — see `action_plan.md §5.1`.

---

## 1. Purpose & scope

A single firmware binary that runs unchanged on **all four** bridge boxes; each
box's identity is selected at runtime and persisted, so the same image flashes
everywhere. Per-device behaviour lives behind a small driver contract (~5% of the
code); the remaining ~95% (Wi-Fi, MQTT, OTA, dispatch, identity, safety gates) is
shared.

Out of scope: device-specific signal capture, deck repair / restoration,
multi-broker support, voice control (delegated to a future Wirenboard-native
Alice bridge).

---

## 2. Functional requirements (FR)

### Identity & provisioning
- **FR-1 (single image).** The firmware MUST be a single binary supporting all 4
  target devices. There MUST NOT be a per-box compilation step.
- **FR-2 (NVS identity).** Per-box identity MUST be selected at runtime by reading
  a string from NVS (`bridge` namespace, `device_id` key). On empty/missing NVS,
  the box MUST come up in an **unprovisioned** mode (Wi-Fi + MQTT + OTA only,
  subscribed to the provisioning topic; no driver active).
- **FR-3 (over-MQTT provisioning).** Identity MUST be settable over MQTT (retained
  publish to topic `/provision`, payload = device id). On receipt the firmware
  MUST persist it to NVS and reboot. **No USB cable required after first flash.**
- **FR-4 (valid identities).** The set of acceptable identities is closed and
  matches the driver registry: `revox_b215`, `revox_a77`, `pioneer_cld_d925`,
  `panasonic_nv_fs90`. Unknown ids MUST log + remain unprovisioned.

### Wirenboard MQTT contract
- **FR-5 (announce).** On MQTT connect the firmware MUST publish (retained):
  - `meta/name` (display name)
  - per control: `meta/type` ∈ {`pushbutton`, `switch`}
  - per control: initial value `"0"`
  - `meta/online = "1"`
- **FR-6 (last will).** The MQTT session MUST set `meta/online = "0"` as last will.
- **FR-7 (subscribe).** The firmware MUST subscribe to
  `/devices/<id>/controls/<c>/on` for every declared control, and to `/provision`.
- **FR-8 (echo).** On a successful command, the firmware MUST republish the
  control value (retained): pushbutton → `"0"` (momentary); switch → `"1"`/`"0"`
  reflecting the requested state.

### Dispatch & per-device drivers
- **FR-9 (driver contract).** Each device MUST implement `DeviceDriver`
  (`include/device_driver.h`): `device_id`, `display_name`, control table,
  `begin()`, `doCommand(name) → bool`, optional `poll()`. The core MUST route
  commands solely through `doCommand`.
- **FR-10 (no core knowledge of devices).** The shared core MUST NOT contain any
  per-device branching. New device classes are added by writing one driver + adding
  one line to `src/drivers.cpp`.
- **FR-11 (command surface, per device):**

  | Device | Controls |
  |---|---|
  | `revox_b215` | `standby` (switch), `stop`, `play`, `ff`, `rewind`, `pause`, `arm_record`, `record` |
  | `revox_a77` | `stop`, `play`, `ff`, `rewind`, `arm_record`, `record` |
  | `pioneer_cld_d925` | `power` (switch), `play`, `pause`, `stop`, `scan_fwd`, `scan_rev`, `chapter_next`, `chapter_prev` |
  | `panasonic_nv_fs90` | `power` (switch), `play`, `stop`, `pause`, `ff`, `rewind`, `arm_record`, `record` |

### Safety gates (drivers)
- **FR-12 (record arming).** Any driver exposing `record` MUST require an
  `arm_record` press within the previous `RECORD_ARM_WINDOW_MS` (default 8000 ms);
  unarmed `record` MUST be rejected. The arm MUST be consumed on a successful
  record.
- **FR-13 (A77 reel-motion interlock).** The A77 driver MUST refuse `play` and
  `record` while the reels are moving. It MUST: (a) assert STOP if motion is
  detected, (b) wait until motion ceases (timeout configurable, default 8 s),
  (c) wait an additional settle delay (`POST_STOP_DELAY`, default 500 ms) before
  engaging. Refusal returns `false` from `doCommand`.
- **FR-14 (B215 SERIAL LINK safety).** The B215 driver MUST NOT drive the DATA
  line high. The output stage MUST be open-collector (pulls LOW to assert;
  releases to let the deck's pull-up restore HIGH).

### Connectivity & resilience
- **FR-15 (Wi-Fi connect).** On boot the firmware MUST connect to Wi-Fi using
  `WIFI_SSID`/`WIFI_PSK`, with a 20 s budget; on failure it MUST keep retrying in
  the main loop.
- **FR-16 (MQTT reconnect).** On MQTT disconnect the firmware MUST reconnect
  (with Wi-Fi reconnect if needed) and re-announce.
- **FR-17 (OTA mandatory — MQTT-triggered HTTPS pull).** The firmware MUST
  support OTA updates via an MQTT-triggered pull (not ArduinoOTA — incompatible
  with IDF). The flow:
  1. Publish the `.bin` URL (retained) to `/devices/<id>/ota`.
  2. The box receives the message and calls `esp_https_ota` against that URL,
     writing to the inactive partition.
  3. On success the box MUST restart; on failure it MUST log + remain on the
     current image.
  4. Bootloader-level rollback (`CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE`,
     wired up in `sdkconfig.defaults` at Phase 6) MUST roll a non-validated
     image back on next boot.
  5. mDNS hostname is `<OTA_HOSTNAME_PREFIX><device_id>` (default
     `wbbridge-<id>`) — useful for discovery but not part of the OTA flow.
  6. **Ops side**: a tiny HTTP server hosting the `.bin` (e.g.
     `python3 -m http.server` on the Wirenboard) is required. Plain HTTP is
     acceptable on a trusted LAN; real HTTPS requires a pinned CA cert in
     firmware (deferred).

---

## 3. Non-functional requirements (NFR)

- **NFR-1 (power).** The firmware MUST use Wi-Fi automatic light-sleep
  (`WiFi.setSleep(true)`; DTIM-driven wakes for buffered MQTT). Target average
  current ≈ 15 mA. The firmware MUST NOT manually invoke
  `esp_light_sleep_start()` (it would suspend the stack's beacon handling).
- **NFR-2 (latency).** Command latency (MQTT message arrival → physical effect on
  the deck) MUST be ≤ 1 s under nominal Wi-Fi conditions; ~0.1–1 s is acceptable
  for transport control.
- **NFR-3 (MQTT buffer).** PubSubClient buffer size MUST be ≥ 1024 bytes (the
  default 256 is insufficient for retained meta-topic batches).
- **NFR-4 (footprint).** MUST run on the generic `esp32dev` (WROOM-32) target
  with the PIO `default.csv` partition table (ships dual OTA slots).
- **NFR-5 (timing-critical sections).** Driver bit-banging MAY use
  `delayMicroseconds()` inside `noInterrupts()` for short IR/serial frames. If
  Wi-Fi coexistence jitter becomes a problem, the RMT peripheral SHOULD be the
  fallback (no code change in scope here).

---

## 4. Constraints (C)

- **C-1.** Target = PlatformIO + Arduino-ESP32 framework.
- **C-2.** MQTT client = `knolleary/PubSubClient` (`^2.8`).
- **C-3.** Wi-Fi / MQTT / OTA credentials are compile-time constants in
  `include/config.h` (copied from `include/config.h.example`; real file
  gitignored).
- **C-4.** Identity is NVS-stored under namespace `bridge`, key `device_id`.
- **C-5.** Wire protocol IS the Wirenboard MQTT topic convention
  (`/devices/<id>/...`) — no abstraction over it.
- **C-6.** First flash MUST be over USB-serial (PIO env `serial`); all later
  updates MUST be OTA (PIO env `ota`).
- **C-7.** Output GPIOs MUST avoid `GPIO 34–39` (input-only on ESP32). They MAY
  be used here for inputs/status only (e.g. A77 motion-sensor, B215 status
  read-back).

---

## 5. External interfaces

### Upstream
- **EI-1.** Wirenboard Mosquitto broker, MQTT 3.1.1, port 1883, optional auth
  (`MQTT_USER` / `MQTT_PASS`).

### Downstream (per device — full pinout / electrical detail in `docs/`)
- **EI-2 (B215).** Rear **SERIAL LINK** DIN. Open-collector data on pin 3,
  referenced to pin 2; +5 V on pin 5 (max 150 mA — not used to power the ESP32).
  See `docs/wb-revoxb215-esp32-bridge.md`.
- **EI-3 (A77).** Rear **REMOTE CONTROL** DIN (Hirschmann WIST-10) — opto-MOSFETs
  close momentary pin-pairs; REC = PLAY + REC asserted together; an external
  reel-motion sensor is added (the A77 has none). See
  `docs/wb-revoxa77-esp32-bridge.md`.
- **EI-4 (Pioneer).** Rear **CONTROL IN** 3.5 mm minijack — baseband (carrier-off)
  IR on an open-collector stage. See `docs/wb-pioneer-cld-d925-esp32-bridge.md`.
- **EI-5 (Panasonic).** **Added** CONTROL IN jack — parallel-tap of the deck's
  internal IR-receiver output. Build then identical to Pioneer. See
  `docs/wb-panasonic-nv-fs90-esp32-bridge.md`.

---

## 6. Deferred fill-ins (data only — code is complete)

These are bench-captured / site-specific values the firmware cannot supply
itself. Each is clearly marked `TODO` in the source.

| Where | What to fill |
|---|---|
| `include/config.h` | `WIFI_SSID`, `WIFI_PSK`, `MQTT_HOST` / `PORT` / `USER` / `PASS`, `OTA_PASSWORD` |
| `src/driver_ir.cpp` | Command tables (raw mark/space µs, **carrier off**) for Pioneer + Panasonic — lift from your Wirenboard IR-blaster captures |
| `src/driver_b215.cpp` | `LINK_INVERT`, bit-timing constants (`T_START` / `T_BIT0` / `T_BIT1` / `T_REPEAT`), per-function `frame` values from B205 scope captures |
| `src/driver_a77.cpp` | Confirm GPIO ↔ pin-pair mapping against your WIST-10 wiring; tune `PRESS_MS`, `MOTION_WINDOW_MS`, `POST_STOP_DELAY`; set `PIN_MOTION` to the actual motion-sensor GPIO |
| `platformio.ini` (`[env:ota]`) | `upload_port` = `wbbridge-<id>.local` (per box); `--auth=` OTA password |
| GPIO numbers throughout the drivers | Confirm against actual WROOM-32 wiring; do not use 34–39 for outputs |

---

## 7. Documentation

- `README.md` — quick-start (build, flash, provision).
- `REQUIREMENTS.md` — this file.
- `docs/wb-revoxb215-esp32-bridge.md` — SERIAL LINK protocol, confirmed §1.4 pinout, BOM.
- `docs/wb-revoxa77-esp32-bridge.md` — WIST-10 contact emulation + reel-motion interlock.
- `docs/wb-pioneer-cld-d925-esp32-bridge.md` — CONTROL IN baseband IR; the easiest of the four.
- `docs/wb-panasonic-nv-fs90-esp32-bridge.md` — adding a CONTROL IN jack to the FS90.
- `docs/img/` — manual scans + photos referenced from the device docs.
