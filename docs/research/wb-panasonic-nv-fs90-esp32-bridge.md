# Panasonic NV-FS90 → Wirenboard via added CONTROL IN jack — Build & Handoff

**Goal:** Control a Panasonic NV-FS90 S-VHS VCR from a Wirenboard PLC. The FS90 has **no
factory wired-control port** (AV1/AV2 SCART + IR only), so we **add one**: tap the deck's
internal IR-receiver output and bring it to a new rear 3.5 mm jack — recreating the Pioneer
"CONTROL IN" interface. An ESP32 then injects the FS90 remote's own codes as a **baseband
(carrier-stripped) waveform**, replacing the unreliable external IR blaster.

**Chosen approach: Option 2 — parallel tap, NO CUT.** Solder a wire onto the IR receiver's
output pin (sharing it with the existing syscon connection) and run it to a rear jack. The
internal IR receiver stays connected and live; your injected open-collector signal simply
wire-ORs with it. Fully reversible (remove the wire). Trade-off: the internal IR sensor stays
active, so a stray remote / strong ambient IR can still reach the deck — accepted here.

**Once the jack exists, this is the SAME build as the Pioneer CLD-D925** — identical output
stage, firmware, and MQTT. See [`wb-pioneer-cld-d925-esp32-bridge.md`](./wb-pioneer-cld-d925-esp32-bridge.md).

**Companion documents:**
[`wb-revoxb215-esp32-bridge.md`](./wb-revoxb215-esp32-bridge.md),
[`wb-revoxa77-esp32-bridge.md`](./wb-revoxa77-esp32-bridge.md),
[`wb-pioneer-cld-d925-esp32-bridge.md`](./wb-pioneer-cld-d925-esp32-bridge.md).

**Status:** Architecture confirmed (Panasonic VCR of this era: IR receiver module → baseband
output → input port on syscon IC6001, a 5 V-logic Panasonic MN153xx micro; front panel is a
scanned key matrix — which is why we tap the IR output, not the matrix). **Outstanding: a
60-second meter/scope check on YOUR unit to identify the IR receiver's OUT pin** before
soldering (§8). The exact pin is not quoted from the manual on purpose — verify it on the
board, don't trust a number for something you solder to.

---

## 0. How to resume this with Claude later

Paste this file back and say "continue the Panasonic NV-FS90 build." Outstanding:

1. **Identify the IR-receiver OUT pin** on your board (§8.1): the 3-pin module behind the IR
   window — find GND (0 V), Vcc (~5 V), and OUT (idles near 5 V, pulses active-low on a
   remote press).
2. **Capture the FS90 remote's codes** (you have the remote) as raw mark/space timings (§5).
3. **Solder the parallel tap + fit the rear jack** (§4), then bring up exactly like the
   Pioneer (§9).

Then Claude can finalise the code table (shared format with the Pioneer doc).

---

## 1. Why the FS90 needs a jack added (and why the IR-output tap is the right one)

- The NV-FS90 is a PAL S-VHS deck with **AV1/AV2 SCART + IR remote only**. There is **no
  edit/Control-S/wired-remote jack** (those were pro AG-series features, not this consumer
  deck). So unlike the Pioneer (which hands you CONTROL IN) and the Revoxes (documented remote
  ports), here you must **create** the wired input.
- Internally, the remote path is the universal arrangement: **IR receiver module → baseband
  logic-level output (idle-high, active-low) → an input port on the system-control micro
  IC6001** (a Panasonic MN153xx-family, 5 V logic — confirmed by the related NV-VP60 service
  manual, which flags IC6001 pin 37 as the 5 V rail).
- The **front panel is a scanned key matrix** (read by the syscon / a counter micro). Injecting
  into a scanned matrix is hard (you must hit the right row/column at the right scan instant).
  **Tapping the IR-receiver output is far easier and is the recommended path** — you feed the
  syscon exactly the baseband bytes it already understands, using the deck's own decoder.
- That IR-output node behaves **identically to the Pioneer CONTROL IN**: idle ~5 V,
  open-collector-ish, baseband (carrier already stripped), active-low. So adding a jack there
  = giving the FS90 its own Pioneer-style CONTROL IN.

---

## 2. Target command set

Capture each from the FS90 remote; expose as MQTT `pushbutton` controls (+ `switch` for power):

| Function | Notes |
|---|---|
| Power | confirm discrete on/off vs toggle on the remote |
| Play | |
| Stop | |
| Pause / Still | |
| FF / Rewind | (wind) |
| Record | gate behind a confirm/arm step (safety) — same as the Revox builds |
| Eject | mechanical; remote may or may not expose it — confirm |
| (optional) Channel ±, OSD, etc. | if you want them |

No status read-back (the IR path is one-way). If you ever want transport status, that's a
separate tap (e.g. an FIP/syscon line) — out of scope.

---

## 3. Why this is the same as the Pioneer once the jack exists

| | Pioneer CLD-D925 | **Panasonic NV-FS90** |
|---|---|---|
| Wired input | factory CONTROL IN jack | **add jack at IR-receiver output (Option 2, no cut)** |
| Signal | baseband IR, idle-high, active-low | **same** |
| Output stage | one open-collector onto tip | **same** |
| Firmware | replay raw remote timings, baseband | **same** |
| Power | USB/PoE (no jack power) | **same** |
| Status | one-way | **same** |
| Extra work | none (jack exists) | **drill + solder one tap wire** |

So: the only FS90-specific effort is **§4 (create the jack) + §8.1 (find the OUT pin)**.
Everything else is lifted from the Pioneer doc.

---

## 4. Creating the CONTROL IN jack (Option 2 — parallel tap, no cut)

### The principle
The IR receiver's OUT pin and the syscon input are both happy to share the line: the receiver
output is open-collector with a pull-up, and your ESP32 output stage is also open-collector.
Two open-collector drivers on one node simply **wire-OR** — whoever pulls low wins, neither
damages the other. So you **add** your wire in parallel; you do **not** cut anything.

### Steps
1. **Identify the IR-receiver OUT pin** (§8.1) — do this first, with power on.
2. With the deck **unplugged**, solder a thin wire to that OUT pin (or the nearest convenient
   pad on the same net).
3. Run the wire to a **rear-panel 3.5 mm jack** (drill a hole — rear panel area is fine to
   drill; pick a spot clear of internal boards/shields).
   - **Tip → IR-OUT net** (your injected signal).
   - **Sleeve → deck GND** (a chassis screw or the IR module's GND pin). NOTE: unlike the
     Pioneer (whose sleeve floats), here **you control the jack, so DO ground the sleeve** to
     the deck — that gives your ESP32 box a proper return without needing a separate ground
     wire.
4. (Recommended, still "no cut") use a **switched (closed-circuit) 3.5 mm jack** but wire only
   tip+sleeve for injection, leaving the internal receiver permanently connected. You get a
   clean panel connector now, and if you ever want Option 1 (auto-mute internal IR on insert)
   you just move one wire to the switch contact — no redo.

```
IR receiver module (behind front window)
   Vcc (~5V)  ── leave
   GND        ──────────────► new jack SLEEVE  (and deck chassis)
   OUT (baseband, active-low) ─┬─► existing trace to IC6001 input  (LEAVE CONNECTED)
                               └─► new jack TIP   (your injected signal, parallel tap)
```

### Reversibility
Remove the tap wire and the jack; the deck is exactly stock. Nothing cut, nothing rerouted.

### The accepted trade-off
Internal IR sensor stays live → a stray remote press or strong ambient IR can still reach the
deck. Fine for this install. (If that ever becomes a nuisance, the switched jack lets you
upgrade to the cut version.)

---

## 5. Firmware (identical to the Pioneer build)

Reuse the shared scaffolding (Ethernet/Wi-Fi + PubSubClient + MQTT). The emit routine replays
a captured **baseband** code by toggling the open-collector pin — **no carrier**, **active-low**.

```cpp
#include <ETH.h>   // or WiFi.h

const char* MQTT_HOST = "192.168.x.x";
const char* DEVICE_ID = "panasonic_nv_fs90";

const int   PIN_SR    = 14;     // open-collector stage onto the jack tip (IR-OUT net)
const bool  SR_INVERT = true;   // baseband IR is active-low; confirm by scope (§8)

// Captured command = remote's raw mark/space timings (carrier stripped).
struct Cmd { const char* name; const uint16_t* timings; uint8_t len; };

// Emit one baseband frame: "mark" => pull LOW, "space" => release HIGH.
void emitSR(const uint16_t* t, uint8_t len) {
  for (uint8_t i = 0; i < len; i++) {
    bool mark  = (i % 2 == 0);
    bool level = SR_INVERT ? !mark : mark;
    digitalWrite(PIN_SR, level ? HIGH : LOW);
    delayMicroseconds(t[i]);
  }
  digitalWrite(PIN_SR, SR_INVERT ? HIGH : LOW); // idle = released high
}
```

- The FS90 remote is a Panasonic IR protocol (Kaseikyo/"Panasonic" 48-bit family is typical).
  You **don't need to decode it** — capture and replay the raw timings (IRremote `rawData`).
- Panasonic frames often expect the **standard repeat/spacing**; if a single shot is flaky,
  replay the remote's repeat behaviour or send twice.
- **Record safety:** gate `record` behind a confirm/arm MQTT topic — same as the Revox builds.

### MQTT (Wirenboard convention) — identical to all the other builds
- `/devices/panasonic_nv_fs90/meta/name` = `Panasonic NV-FS90` (retained)
- per control `/controls/<name>/meta/type` = `pushbutton` (or `switch` for power)
- value `/controls/<name>` (retained), command `/controls/<name>/on` (subscribe)
- broker-direct to the Wirenboard Mosquitto broker.

---

## 6. Bill of materials

| Part | Qty | Notes |
|---|---|---|
| WT32-ETH01 (wired) **or** ESP32 WROOM-32 (Wi-Fi) | 1 | same family as the other builds |
| 3.3 V USB-serial programmer | 0–1 | only if WT32-ETH01 |
| PC817 optocoupler **or** NPN (BC547/2N3904) | 1 | open-collector output stage |
| Resistor 1 kΩ | 1 | base/LED series |
| **Switched (closed-circuit) 3.5 mm mono jack, panel-mount** | 1 | the new rear CONTROL IN |
| Thin hook-up wire (tap) | — | to the IR-OUT pin |
| 5 V USB PSU | 1 | powers the box (no power on the tap) |
| Enclosure | 1 | metal OK if wired-Ethernet; plastic if Wi-Fi |

---

## 6a. Precise shopping list — Amazon.de

| # | Item | amazon.de search term | Qty | ~EUR | Notes |
|---|---|---|---|---|---|
| 1 | Board | `WT32-ETH01 ESP32 Ethernet Modul` or `ESP32 NodeMCU WROOM-32` | 1 | 10–14 | match the other builds |
| 2 | USB-serial 3.3 V | `CP2102 USB UART 3,3V Programmer` | 0–1 | 5–7 | only for WT32-ETH01 |
| 3 | Optocoupler / transistor | `PC817 Optokoppler DIP` or `BC547 Sortiment` | 1 set | 6 | output stage |
| 4 | Resistor kit | `Widerstand Sortiment 1/4W` (incl. 1 kΩ) | 1 | 8 | |
| 5 | Panel-mount switched 3.5 mm jack | `3,5mm Klinkenbuchse Einbau schaltend` | 2 | 5 | the new rear jack (buy a spare) |
| 6 | 3.5 mm mono cable | `3,5mm Klinkenkabel mono` | 1 | 4 | box ↔ jack |
| 7 | 5 V USB PSU | `USB Netzteil 5V 2A` + cable | 1 | 8 | powers the box |
| 8 | Enclosure | `Aluminium/Kunststoff Gehause 80x50x25` | 1 | 6–10 | metal OK if wired |
| 9 | Perfboard / jumpers / wire | `Lochrasterplatine`, `Jumper Dupont`, `Schaltlitze` | 1 each | 12 | prototyping + tap wire |

**Notes:** no scarce parts (cheapest build alongside the Pioneer). Get a panel-mount
**switched** jack so you retain the option to upgrade to a "cut" install later. A small step
drill / Stufenbohrer makes a clean hole in the rear panel.

---

## 7. Casing & mounting

- Box behind the rack; metal OK if wired-Ethernet, plastic if Wi-Fi.
- The new jack lives on the FS90's rear panel; a short 3.5 mm cable links it to your box.
- Drill the rear-panel hole in a clear area (avoid internal board edges, shields, the PSU, and
  the deck mechanism). Deburr; add a drop of hot glue as strain relief on the internal tap wire.

---

## 8. Measurement / bring-up plan

### 8.1 Identify the IR-receiver OUT pin (do FIRST, before soldering)
1. Power the deck. Locate the **3-pin IR receiver module** behind the front IR window
   (service manual — HiFi Engine / elektrotanya — helps locate it on the board).
2. With a meter: one pin = **GND** (0 V), one = **Vcc** (~5 V steady). The third is **OUT**.
3. Confirm OUT: it idles **near 5 V**; on a remote press, a meter on **AC volts** twitches, and
   a scope shows clean **active-low** baseband pulses (no 38 kHz carrier — the module already
   stripped it). That is your tap pin and confirms `SR_INVERT`.

### 8.2 Capture remote codes
- IR receiver + IRremote/IRMP on the bench: record **raw mark/space timings** for each target
  button (you replay timings, not decode).

### 8.3 Bench the output stage
- Drive a dummy load (pull-up to 5 V); scope the pin; confirm clean pull-low / release-high.

### 8.4 Install & first live test
1. Deck unplugged: solder the parallel tap to OUT; fit the rear jack (tip→OUT net,
   sleeve→deck GND). Leave the internal receiver connected.
2. Power up; confirm the deck **still responds to its own remote** (proves the parallel tap
   didn't disturb the node).
3. Plug in the ESP32 box; send **Play**. Then Stop/Pause/FF/Rewind; **Record last** (gated).
   If flaky, add the Panasonic repeat frame or send twice.
4. Map all working codes to MQTT controls; expose in Wirenboard.

---

## 9. Known facts / gotchas

- **No cut (Option 2):** internal IR sensor stays live — stray/ambient IR can still reach the
  deck. Accepted trade-off; switched jack lets you upgrade to a cut/auto-mute install later.
- **Verify the OUT pin on your board** — don't trust a quoted pin number for a solder point.
- **Baseband, active-low** — feed carrier-stripped, idle-high/assert-low signal, like the
  Pioneer. Do NOT send a 38 kHz-modulated waveform into this node.
- **Ground the jack sleeve to the deck** here (unlike Pioneer, you own this jack) for a clean
  return.
- **5 V logic** (IC6001 family) — your open-collector pull-low is fully compatible; never drive
  the node hard high, just pull low and release.
- **Front-panel matrix is NOT the tap** — that path is the hard one; the IR-OUT node is the easy
  one and is what this doc uses.

---

## 10. Relationship to the other builds

Shared: ESP32/WT32-ETH01 + Wirenboard MQTT; broker-direct; open-collector baseband output;
**firmware and output stage identical to the Pioneer CLD-D925** once the jack exists.

Different: the FS90 has **no factory wired port**, so you **add a Pioneer-style CONTROL IN** by
a **parallel (no-cut) tap on the internal IR-receiver output** brought to a drilled-in rear
jack. The only device of the four requiring opening the unit and soldering to an internal node
— but a single wire, reversible, and it cures the IR-blaster reliability problem.

---

## 11. Source references

- **NV-FS90 service manual** (HiFi Engine, elektrotanya, eserviceinfo): locates the IR receiver
  module and syscon on the board. (Connection docs confirm AV1/AV2 SCART + IR only — no wired
  remote port.)
- **Panasonic NV-VP60 service manual:** confirms this generation's syscon is **IC6001
  (MN153xx-family)** with a **5 V rail (pin 37)** — establishes 5 V logic compatibility.
- **Panasonic AG-500 service manual:** documents the standard Panasonic VCR control
  architecture — **scanned key matrix** read by syscon/counter micros — confirming the matrix
  is the hard path and the IR-output tap is the easy one.
- **"Hacking Wired Remote Control Jacks Into A/V Equipment"** (wiredremotecontrol.blogspot.com):
  the canonical recipe for adding a CONTROL-IN jack to a VCR by tapping the IR-receiver output
  (Mitsubishi VCR: series switched jack; JVC: parallel no-cut tap onto the sensor output) —
  Option 2 here follows the JVC parallel approach. IR-receiver output is open-collector,
  idle-high, baseband.
- **Pioneer SR analysis** (same blog): the CONTROL-IN electrical model (idle ~5 V, baseband,
  active-low) this jack recreates — see the Pioneer CLD-D925 doc.
