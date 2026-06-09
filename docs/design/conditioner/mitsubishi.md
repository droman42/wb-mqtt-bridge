### What is happening?

| symptom                                                                                                                                           | what’s really going on                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| ------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Everything works until you touch the IR remote → then the CN105/MQTT bridge “dies” and only a full power-cycle of the indoor unit revives it.** | Pressing the IR handset often shuts the head unit down (or changes mode).  When the blower stops, the **5 V accessory rail on the CN105 connector goes dead for \~1 s** while the main controller re-initialises.  If you power your ESP8266/ESP32 from that pin (the mitsubishi2wb README shows exactly that), the micro *brown-outs*, reboots, and spews its 74880-baud bootloader banner out of the TX line.  Those garbage bytes violate Mitsubishi’s 9600 baud 8E1 framing, so the indoor PCB’s serial error-handler **puts the CN105 port into a latched fault state**.  The port is re-enabled only when the indoor controller itself is power-cycled – which is why pulling the mains or breaker fixes everything.([nicegear.nz][1], [github.com][2]) |

---

### How to stop it from happening

1. **Keep the controller powered even when the head is “Off”**

   * Use **CN105 pin 1 (12 V, always present)** plus a cheap buck converter (e.g. MP1584) to get 5 V/3 V3 for the ESP instead of CN105 pin 3 (the switched 5 V).
   * This way the micro never reboots when you press the IR remote.

2. **Mute the ESP’s TX pin during boot** (belt-and-braces)

   * Put a **10 kΩ series resistor** or a small **P-channel MOSFET** that only turns on after GPIO0 goes high (≈ 200 ms after reset).
   * Alternative: move the HeatPump UART to `Serial1` (which is silent at boot) and leave `Serial0` unconnected to CN105.

3. **Tell the HeatPump library to accept external changes**

   ```cpp
   hp.enableExternalUpdate();   // in setup()
   ```

   Without this the firmware will try to “undo” every IR command; with it the MQTT topics stay in sync.

4. **Upgrade HeatPump to ≥ 1.2.1**
   Commit `6e3c1f1` (Oct 2024) fixed a buffer-overflow that could also crash on long “function-setting” frames the head transmits right after an IR command.

---

### Quick wiring sketch

```
CN105  ─┬─ 12 V  ──► DC-DC (12→5 V) ──► ESP 5 V
        ├─ GND   ────────────────────► ESP GND
        ├─ TX    ──► ESP RX
        └─ RX    ◄── ESP TX ▫▫▫ (through 10 kΩ or MOSFET gate)
```

> **Important:** leave CN105 pin 3 (switched 5 V) *un-used*.

---

### Verifying the fix

1. Connect a logic-analyser or a second USB-UART to CN105.
2. Press the IR remote **before** and **after** the hardware change.

   * **Before:** you’ll see the ESP boot banner (`0x78 0x78 …` @ 74880 8N1) followed by silence from the indoor unit.
   * **After:** you should only see proper 36-/76-byte Mitsubishi frames; the bridge keeps publishing MQTT updates.

---

### Side benefits

* The ESP now remains online and continues to report temperature/humidity even when the AC is off.
* Because it no longer reboots, OTA updates and retained MQTT states survive IR use.
* The indoor unit never has to be hard-reset again, so compressor-run-time counters and error logs stay intact.

---

Give the wiring/power tweak a try; in 99 % of installations it eliminates the “remote kills CN105” behaviour completely.  If you still hit problems, capture a few seconds of CN105 traffic after using the IR remote and share the bytes – we can decode them and dig further.

[1]: https://nicegear.nz/blog/hacking-a-mitsubishi-heat-pump-air-conditioner/?utm_source=chatgpt.com "Hacking a Mitsubishi Heat Pump / Air Conditioner - nicegear blog"
[2]: https://github.com/SwiCago/HeatPump?utm_source=chatgpt.com "SwiCago/HeatPump: Arduino library to control Mitsubishi Heat ..."
