# ESP32 — bridge firmware for 4 vintage AV transports

A single PlatformIO / Arduino-ESP32 image that bridges the **Revox A77**,
**Revox B215**, **Pioneer CLD-D925** and **Panasonic NV-FS90** to the
Wirenboard MQTT broker. Each box's identity is set once over MQTT — same binary
on all four.

**Status:** scaffold + design docs. **Parked** until the "everything works in
my home" hardware-verification phase. Not yet bench-validated.

## Layout

| Path | Contents |
|---|---|
| `REQUIREMENTS.md` | What this firmware MUST do (the authoritative spec). |
| `platformio.ini` | Build config (envs: `serial`, `ota`). |
| `include/` | Shared headers (`device_driver.h`, `wb_mqtt.h`, `config.h.example`). |
| `src/` | Shared core + per-device drivers (3 drivers for 4 decks — Pioneer + Panasonic share `driver_ir.cpp`). |
| `docs/` | Per-device design + build handoffs (with manual scans). |
| `docs/img/` | Photos / scans referenced from the device docs. |

## Quick-start

```bash
# 1) Site config (real creds — file is gitignored)
cp include/config.h.example include/config.h
$EDITOR include/config.h

# 2) First flash per box (USB serial — the only wired step, ever)
pio run -e serial -t upload

# 3) Set the box's identity over MQTT, no cable:
mosquitto_pub -h <broker> -t /provision -r -m revox_b215
# Valid ids: revox_b215, revox_a77, pioneer_cld_d925, panasonic_nv_fs90
# The box stores it in NVS and reboots into that driver.

# 4) All later updates over OTA — set upload_port to wbbridge-<id>.local
pio run -e ota -t upload
```

See `REQUIREMENTS.md §FR-11` for the full command list per device, and the
files under `docs/` for the per-device hardware build.
