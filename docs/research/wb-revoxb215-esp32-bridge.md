# Revox B215 → Wirenboard via SERIAL LINK — Option B Build & Handoff

**Goal:** Control a Revox B215 cassette deck from a Wirenboard PLC by driving the deck's
rear **SERIAL LINK** port directly with a small ESP32 that publishes/subscribes
**Wirenboard-conformant MQTT** over Wi-Fi. IR is bypassed entirely.

**Companion document:** [`wb-revoxa77-esp32-bridge.md`](./wb-revoxa77-esp32-bridge.md) (the A77
reel-to-reel build — shared MQTT / casing / firmware scaffolding).

**Status of this document:** design locked; pinout treated as confirmed per the
`0815simon` reference but **must be verified with a multimeter before connecting to pin 3**.
Command byte values are placeholders until captured from the user's B205 remote.

---

## 0. How to resume this with Claude later

Paste this file back in and say "continue the Revox B215 Option B build." The two
things still outstanding are:

1. **Multimeter / scope measurements** (see §8). Specifically: DIN pin count + layout,
   which pin is +5 V vs GND (deck powered, rear switch on), and scope captures of the
   B205 frames on pin 3 for the seven target functions.
2. **Filling the command table** (§5) with real captured frame values and setting
   `LINK_INVERT` after observing line polarity.

Once those exist, Claude can produce: final `sendLinkFrame()` timing constants, the
real command table, and a confirmed wiring diagram.

---

## 1. Confirmed facts about this deck & system

- **Deck:** Revox B215, serial 013773, Made in West Germany (Willi Studer GmbH,
  D-7827 Löffingen), 45 W. Genuine B215. Service-manual references (Regensdorf-edited
  "IR Remote Control Systems," order no. 10.30.0430) apply.
- **Rear panel confirmed from photo:** a panel labelled **SERIAL LINK** with a DIN
  socket, sub-labelled **REMOTE CONTROL**, plus a separate POWER panel with voltage
  selector + **hard mains rocker switch**, and an AUDIO panel (L/R in, L/R out RCA).
- **The SERIAL LINK is the chosen control path.** It is part of the Revox B200-series
  remote system; the deck addresses itself on this bus as **device identifier 04**.
- **Pinout (provisional, per `0815simon/revox-rc5-remote`, VERIFY BEFORE USE):**
  - DIN **pin 3 = DATA** (single bidirectional open-collector line)
  - DIN **pin 2 = GND**
  - DIN **pin 5 = +5 V**
  - Short **pins 1+2 and 4+5** to disable the internal IR receiver (optional).
- **Electrical nature:** NOT RS-232, NOT RS-485. A single bidirectional
  **open-collector** data line, idled high by the deck's internal pull-up, behind
  **optocoupler isolation** inside the deck. ITT/Nokia pulse-coded framing with
  ~15 µs-scale carrier features.
- **CRITICAL SAFETY RULE:** never drive pin 3 hard high. Assert a bit by pulling the
  line to GND; release it to let the deck's pull-up restore high. Use an
  **open-collector / open-drain (ideally opto-isolated) output stage**. Driving +5 V
  onto the line can damage the deck's output when it tries to pull low.
- **Power on/off behaviour:** "off" = **Standby** (deck logic stays powered; rear hard
  switch must remain ON permanently). "On" is best modelled as **wake-on-transport**:
  sending Play wakes the deck and acts. Whether Stop/Pause alone wake it is unconfirmed —
  on the test list. There is **no cold-start over serial** if the rear switch is off.
- **Auto-reverse:** direction is handled internally. There is **no direction command** —
  Play plays the current direction. Nothing extra to model.
- **Eject:** mechanical/front-panel; do **not** assume a serial eject exists. Verify.

---

## 2. Target command set (device identifier 04)

Seven functions in scope, mapped to the B215 drive-function enumeration:

| Function | Notes |
|---|---|
| Standby   | stateful on/off; "power" surfaces as this |
| Stop      | safe first test command |
| Play      | also serves as "wake / power on" |
| FF        | fast-forward (Vorspulen) |
| Rewind    | (Rückspulen) |
| Record    | gate behind a confirm/arm step (safety) |
| Pause     | auxiliary function |

Optional extras if easy after captures: Loop/Positioning, cue, and **status read-back**
(play state + real-time mm:ss tape counter) — a genuine bonus of the serial path.

---

## 3. Bill of materials (Option B)

| Part | Qty | Notes |
|---|---|---|
| ESP32 dev board (WROOM-32 DevKitC or similar) | 1 | Wi-Fi; choose one with a decent onboard regulator |
| PC817 optocoupler | 1 (control) +1 if adding status read-back | output stage; 6N137 if edges too soft |
| Resistor 1 kΩ | 1 | opto LED series |
| Resistor 220–470 Ω | 1 | only for status-direction opto LED, if used |
| Resistor 4.7 kΩ | 0–1 | pin-3 pull-up ONLY if scope shows weak idle-high |
| 5-pin 180° DIN plug + short cable | 1 | mates SERIAL LINK socket |
| Capacitor 470–1000 µF | 1 | local power reservoir |
| Capacitor 0.1 µF | 1 | decoupling at board |
| 3.3 V LDO | 0–1 | if powering from pin-5 5 V under spiky load |
| Small USB 5 V supply | 0–1 | fallback if pin-5 power proves marginal |
| ABS/PETG enclosure ~80×50×25 mm | 1 | NON-metal (Wi-Fi); see §7 |

---

## 4. Wiring

### Control output stage (MCU → deck)

```
ESP32 GPIO17 ──[1kΩ]──► PC817 LED anode
                        PC817 LED cathode ──► ESP32 GND

PC817 transistor collector ──► DIN pin 3 (DATA)
PC817 transistor emitter   ──► DIN pin 2 (GND, deck side)
```

- GPIO high → opto conducts → pin 3 pulled to pin 2 (line low).
- GPIO low  → opto off → deck pull-up restores high (idle).
- This **inverts** sense (matches the protocol's noted inversion). Final polarity is
  resolved in firmware via `LINK_INVERT` after scoping.

### Power

- Pin 5 (+5 V) may power the ESP32 **only if** it can source Wi-Fi TX spikes
  (300–500 mA bursts) without sagging — **measure first** (load with a resistor, watch
  voltage). If marginal: power ESP32 from its own USB supply; use pin 5 as reference only.
- If using pin-5 power: add 470–1000 µF reservoir + 0.1 µF at the board; prefer feeding
  a 3.3 V LDO over leaning on the dev board regulator under spiky load.

### Optional status read-back (deck → MCU)

- pin 3 → series resistor (ref. deck 5 V/GND) → second PC817 LED → its transistor → ESP32 input pin.
- Lets you parse the deck's return frames into MQTT value topics.

### IR disable (optional)

- Short DIN **1+2** and **4+5** so the deck ignores stray IR and listens only to the link.

---

## 5. Firmware

**Base repo:** `https://github.com/0815simon/revox-rc5-remote` — file `revox_web_remote.ino`.

**What to keep:** the **serial-link bit-banging routine** (frame → GPIO toggles).
**What to delete:** the RC5/IR receive code and the bundled webserver.
**What to add:** Wi-Fi + MQTT (PubSubClient or AsyncMqttClient) + a clean command table.

> The repo is the author's self-described "hacky, trial-and-error" project. Lift and
> adapt the TX core; don't flash as-is.

### Skeleton

```cpp
// ---- config ----
const char* WIFI_SSID = "...";
const char* WIFI_PSK  = "...";
const char* MQTT_HOST = "192.168.x.x";   // Wirenboard broker (Mosquitto on the WB)
const uint16_t MQTT_PORT = 1883;
const char* DEVICE_ID = "revox_b215";

const int   PIN_LINK    = 17;            // to opto LED
const bool  LINK_INVERT = true;          // set after scoping line polarity

// ---- ITT serial-link bit-banger (adapted from 0815simon) ----
// Sends one Revox frame: device id 04 + function code.
// Bit order (MSB/LSB) and bit timing come from YOUR scope captures.
// Keep all timing in this one function so retuning is trivial.
void sendLinkFrame(uint16_t frame) {
  // assert = pull line low; idle = release (deck pull-up brings high)
  // honour LINK_INVERT
  // use delayMicroseconds() with measured bit widths (~15 µs-scale features:
  //   confirm start-bit, 0/1 bit periods, repeat gap from captures)
}

// ---- command table: REPLACE 0x0000 with captured B205 frame values ----
struct Cmd { const char* name; uint16_t frame; };
Cmd CMDS[] = {
  {"standby", 0x0000},
  {"stop",    0x0000},
  {"play",    0x0000},
  {"ff",      0x0000},
  {"rewind",  0x0000},
  {"record",  0x0000},
  {"pause",   0x0000},
};

// ---- MQTT command handler (Wirenboard convention) ----
void onMqtt(char* topic, byte* payload, unsigned int len) {
  String t(topic), p;
  for (unsigned i = 0; i < len; i++) p += (char)payload[i];
  // expected: /devices/revox_b215/controls/play/on   payload "1"
  for (auto &c : CMDS) {
    String want = String("/devices/") + DEVICE_ID + "/controls/" + c.name + "/on";
    if (t == want && p == "1") {
      // RECORD SAFETY: gate here behind an "armed" flag / confirm topic
      sendLinkFrame(c.frame);
      String fb = String("/devices/") + DEVICE_ID + "/controls/" + c.name;
      mqtt.publish(fb.c_str(), "1", true);   // echo state back
    }
  }
}
```

### On connect: publish retained meta topics (so WB sees a native device)

- `/devices/revox_b215/meta/name` = `Revox B215` (retained)
- For each control:
  `/devices/revox_b215/controls/<name>/meta/type` (retained)
  - momentary keys (stop, play, ff, rewind, record, pause) → type `pushbutton`
  - standby → type `switch` (stateful on/off) if desired
- Value topic `/devices/revox_b215/controls/<name>` — publish state (retained)
- Command topic `/devices/revox_b215/controls/<name>/on` — **subscribe**

### Record safety

Gate `record` behind a second confirming topic or a short "armed" window so a stray
MQTT message can't start a recording over a tape.

---

## 6. Wirenboard MQTT convention (reference)

Same convention `wb-mqtt-serial` uses:

| Topic | Direction | Retained | Purpose |
|---|---|---|---|
| `/devices/<id>/meta/name` | publish | yes | device display name |
| `/devices/<id>/controls/<c>/meta/type` | publish | yes | `pushbutton` / `switch` |
| `/devices/<id>/controls/<c>` | publish | yes | current value/state |
| `/devices/<id>/controls/<c>/on` | **subscribe** | — | command in (UI/rules write here) |

**Integration choice:** simplest is **broker-direct** — ESP connects to the WB
controller's Mosquitto broker over Wi-Fi (reachable on LAN by default on WB). The deck
then appears as a native WB device; rules/scenes/UI work with no extra glue.

---

## 7. Casing

- **Material:** ABS or PETG, ~80×50×25 mm. **Not metal** (would kill Wi-Fi). If printing,
  PETG handles warm-equipment proximity better than PLA. Keep the ESP32 PCB antenna near
  an edge, not buried.
- **Layout:** ESP32 on standoffs; opto + passives on a small perfboard daughter area.
  DIN pigtail exits one end via a grommet (strain relief); USB (if used) exits the other.
- **Ventilation:** a few slots; LDO/ESP run warm; no fan needed.
- **Mounting:** VHB pad or keyhole tab to hang behind the rack. Keep away from the deck's
  transformer area.
- **Label** the DIN pigtail with the pinout.
- Off-the-shelf alternative: Hammond 1551-series ABS box.

---

## 8. Measurements still required (do before connecting to pin 3)

1. **DIN pin count + layout** — look straight into the socket; confirm 5-pin 180°.
2. **+5 V vs GND** — deck powered, rear switch ON: meter which pin is ~+5 V relative to
   which is GND. Confirms pinout on THIS unit.
3. **Pin-5 current capability** — load pin 5 with a resistor; confirm it sources ESP32
   Wi-Fi TX spikes without the rail sagging. If marginal → power ESP32 from USB.
4. **B205 frame captures on pin 3** — deck only, scope pin 3 to GND while firing the
   **B205** at the front for each of: standby, stop, play, ff, rewind, record, pause.
   Record: idle level, logic swing, start-bit timing, 0/1 bit periods, frame length,
   repeat gap, bit order. These fill the command table and set timing.
5. **Polarity** — from the captures, set `LINK_INVERT`.
6. **Wake test** — put deck in standby, send Stop; does it wake? Repeat Pause, then Play.
   Note which wake it (settles the "power on" mapping).

---

## 9. Bring-up sequence (Option B)

1. Bench ESP **without** deck: confirm Wi-Fi, MQTT topics appear in WB, buttons publish.
2. Scope the output stage into a dummy load: confirm pull-low/release; set `LINK_INVERT`.
3. Capture B205 frames on pin 3 (deck only) → fill command table (§5).
4. Connect; send **stop** first; then play / pause / ff / rewind; **record last** (gated).
5. (Optional) add status-read opto; parse return frames into WB value topics.

---

## 10. Known field notes / gotchas

- The B215 transport has a **watchdog**: a faulty unit was reported to auto-stop within
  ~4 s unless control sequencing was as expected (that was a fault from a swapped
  microprocessor, not normal behaviour). If your first Play "bounces," suspect command
  framing/timing, not wiring.
- The B201 (non-CD) remote does **not** drive Play on the tape decks — irrelevant here
  since you have a **B205** (drives everything) and are going serial, but don't capture
  frames from a B201.
- Protocol sense is **inverted** in places — that's expected; handle in `LINK_INVERT`.

---

## 11. Why Option B (vs A)

- Timing-critical signal generation lives **clean and local** at the deck (no Linux
  scheduling jitter, no 3 m cable run on a fussy open-collector line).
- Wi-Fi keeps wiring trivial; deck appears as a native WB device via standard MQTT.
- Only real homework: confirm pin-5 power (or give it USB).
- Option A (controller-driven over 3 m) remains a fallback; if ever built, make its
  deck-end board B-ready so swapping in an ESP32 is a 10-minute upgrade.

---

## 12. Source references

- Revox "IR Remote Control Systems" service manual (Studer Revox, order no.
  10.30.0430): device identifier table (04 = B215), serial-link protocol, drive/aux
  function enumeration, B215 status string format. (archive.org:
  `studer_Revox_IR_Remote_System_Serv`)
- `0815simon/revox-rc5-remote` (GitHub): working ESP8266 serial-link TX; DIN pinout
  notes (data=3, GND=2, +5V=5; IR-disable strap 1+2 & 4+5).
- Tapeheads.net "Info on Revox Serial Link protocol wanted": bidirectional single-wire
  warning, open-collector / opto recommendation, Nokia/ITT protocol family.
- IRMP discussion #80: native remote waveform timing (~15 µs bursts; 150/300 µs bit
  periods), TBA2800 preamp note.
- Wirenboard wiki: WB-MSW v3 is RS-485/Modbus IR module (IR-only actuator); WB controller
  has native RS-485 + Linux + Mosquitto broker; MQTT device convention.
- NEEO forum: B215 PLAY triggers power-on event (wake-on-transport evidence).
