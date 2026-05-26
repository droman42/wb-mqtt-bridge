# Revox B215 → Wirenboard via SERIAL LINK — Build & Handoff

> ## ⚑ FINAL POWER & CONNECTIVITY DECISION (supersedes power/connectivity text below)
>
> After working through USB / PoE / battery / wired-Ethernet options, the locked choice for
> **all four bridge boxes** is:
>
> - **NO power plugs.** Power is taken from the deck.
> - **Wi-Fi (ESP32 WROOM-32), NOT wired Ethernet.** Run **light-sleep** (avg ~15 mA) so the
>   deck rail only sees a small steady load. See §"Light-sleep + DTIM" below for how commands
>   still arrive instantly.
> - **Reservoir cap buffers the Wi-Fi TX spikes** so the deck rail only ever supplies the
>   ~15 mA average: **1000 µF low-ESR** across the 5 V tap + **100 µF + 0.1 µF** at the board
>   + **2.2–10 Ω inrush resistor** feeding the big cap. (Cap + light-sleep are a pair; a cap
>   with always-on Wi-Fi would just drain.)
> - **No RJ45 / no USB / no PoE** (the MikroTik's single passive-PoE port is irrelevant).
> - **Plastic case** (Wi-Fi antenna near a wall edge). See `cases/` (v5 STLs).
>
> **Power source per device:**
> - **B215:** SERIAL LINK **pin 5 (+5 V)** — now comfortable (~15 mA avg + cap removes the old
>   150 mA-rail spike worry).
> - **A77:** **pin 7 (+27 V)** → small buck → 5 V (ample headroom); cap on the buck output.
> - **Pioneer / Panasonic:** tap an **internal +5 V** rail (2 wires through the case grommet
>   slot). ~15 mA avg is easy on a logic rail; **meter once** under load to confirm.
>
> **What this supersedes below:** ignore wired-Ethernet/WT32-ETH01-primary, USB-supply, PoE,
> or battery passages — kept only as alternative-history reference. Firmware: keep the
> command/MQTT logic; transport = **Wi-Fi (`WiFi.begin()`)** in **light-sleep**; output stage
> and protocol/code capture unchanged.
>
> ---

## Firmware design rule — network update (OTA) is MANDATORY

The box is **deck-powered with no USB and no easy physical access** once installed, so the
firmware **must** support full **over-the-air update over the network**: upload a new image,
flash it, and reboot — with **no cable and no USB** ever needed after first flash.

- Use **ArduinoOTA** (or ESP-IDF `esp_https_ota`) so you can push builds from the IDE / a script
  over Wi-Fi. Implement: receive image -> verify -> write to the OTA partition -> reboot into it.
- Keep OTA reachable even in light-sleep: the device is associated and reachable (see
  "Light-sleep + DTIM"); an OTA push wakes it like any other connection.
- **Safety:** use the ESP32's dual-OTA partition scheme so a bad image **rolls back** to the
  previous one on boot-fail (never leave the box bricked behind a deck).
- Gate OTA behind a password/token; optionally only enable the OTA listener for a window after
  an MQTT "update-arm" command, so it isn't open permanently.
- First flash is the only wired step (3.3 V serial header on the WROOM-32). After that the USB
  serial adapter is **literally never needed again** — all updates go over the network.

---

## CURRENT BUILD — board, power & parts (OVERRIDES the BOM / shopping list below)

The BOM, shopping list, casing and "why wired" sections further down were written when the
plan was wired-Ethernet. The **locked build** (see banner) changes these specifics. Use this
list; treat the older tables as reference only:

**Board:** **ESP32 WROOM-32 (Wi-Fi)** — NOT the WT32-ETH01. (Antenna near a plastic wall edge.)
**Connectivity:** Wi-Fi light-sleep. **DROP** all of: WT32-ETH01, RJ45 jack/patch lead, PoE
splitter/injector, USB 5 V PSU, USB-C PSU, Schottky diode-OR fallback. None are used.
**First flash only:** a 3.3 V USB-serial adapter on the WROOM-32 header — needed once, then
never again (updates go OTA, see the OTA rule above). Most WROOM-32 dev boards have onboard
USB-serial, so even that may be unnecessary.

**Power = deck-derived, no plugs** (per banner), buffered by the reservoir cap:
- **1000 µF low-ESR** across the 5 V tap + **100 µF + 0.1 µF** at the board + **2.2–10 Ω**
  inrush resistor feeding the big cap.

**Keep from the lists below:** the optocoupler/opto-MOSFET output stage + its resistors, the
signal connector (DIN / WIST-10 / 3.5 mm jack), prototyping bits, hook-up wire, and (A77) the
27 V→5 V buck + fuse. **Enclosure: plastic** (Wi-Fi), per the `cases/` v5 files.

---



**Goal:** Control a Revox B215 cassette deck from a Wirenboard PLC by driving the deck's
rear **SERIAL LINK** port directly with a small ESP32 that publishes/subscribes
**Wirenboard-conformant MQTT**. IR is bypassed entirely.

**Primary design (this rewrite):** a **wired-Ethernet ESP32 (WT32-ETH01) powered from the
deck's own +5 V**, no battery, no Wi-Fi. This was chosen after working through the power
options — see §11. The earlier Wi-Fi and battery variants are kept as **Appendix A** for
reference.

**Companion documents** (the four-transport ESP32-bridge family — shared MQTT /
casing / firmware scaffolding; this doc covers the B215-specific SERIAL LINK protocol):
[`wb-revoxa77-esp32-bridge.md`](./wb-revoxa77-esp32-bridge.md) (Revox A77 reel-to-reel),
[`wb-pioneer-cld-d925-esp32-bridge.md`](./wb-pioneer-cld-d925-esp32-bridge.md) (Pioneer LD),
[`wb-panasonic-nv-fs90-esp32-bridge.md`](./wb-panasonic-nv-fs90-esp32-bridge.md) (Panasonic VHS).

**Status:** SERIAL LINK pinout CONFIRMED from the official B215 service manual (§1.4).
Electrical nature (bidirectional, opto-isolated, +5 V/150 mA) confirmed. Outstanding:
scope-capture of the B205 command/status frames (protocol bytes/timing) and `LINK_INVERT`
polarity.

---

## 0. How to resume this with Claude later

Paste this file back and say "continue the Revox B215 build." Outstanding:

1. DONE — DIN pinout, +5 V vs GND — **official pinout in §1.**
2. DONE — Power approach — **DECIDED: wired Ethernet + deck 5 V (§11).**
3. **Scope captures of the B205 frames on pin 3** for the seven functions (§8) — still
   needed for the command table + timing.
4. **Fill the command table** (§5) with captured frame values; set `LINK_INVERT`.

Then Claude can produce final `sendLinkFrame()` timing constants, the real command table,
and the finalized wiring harness.

> 30-second sanity check before connecting: meter pin 5 to pin 2 with the deck powered (rear
> switch on) and confirm ~+5 V **and that it holds under the board's load** (§8/§11). The
> manual pinout is authoritative, but the scan is old and a quick check is cheap insurance.

---

## 1. Confirmed facts about this deck & system

- **Deck:** Revox B215, serial 013773, Made in West Germany (Willi Studer GmbH,
  D-7827 Loffingen), 45 W. Genuine B215. Two manuals apply: the **B215 deck service
  manual** (transport/audio/schematics — source of the pinout below) and the separate
  **"IR Remote Control Systems"** manual (order no. 10.30.0430 — source of the serial-link
  *protocol*, device id 04, and the drive-function enumeration).
- **Rear panel** (confirmed from photo + manual §1.4): a panel labelled **SERIAL LINK /
  REMOTE CONTROL** with the DIN socket, a POWER panel with voltage selector + **hard mains
  rocker switch**, and an AUDIO panel (L/R in, L/R out RCA).

### Rear panel (manual §1.4)

![Revox B215 rear panel showing the AUDIO input/output RCAs, the POWER panel with voltage selector and AC inlet, and the SERIAL LINK / REMOTE CONTROL DIN socket at right](./img/rear-panel.png)

- **The SERIAL LINK is the chosen control path.** It is part of the Revox B200-series
  remote system; the deck addresses itself on this bus as **device identifier 04**.

### CONFIRMED pinout (B215 service manual §1.4 — "Occupation des poles de la fiche Serial Link")

![Revox B215 SERIAL LINK pin assignment from the service manual: pin 1 GND earth, pin 2 GND floating, pin 3 serial I/O, pin 4 +5V floating, pin 5 +5V max 150 mA, pin 6 n.c.](./img/serial-link-pinout.png)

| Pin | Manual definition | Use in this build |
|---|---|---|
| **1** | GND (earth / terre) | chassis earth — **do NOT use as the signal reference** |
| **2** | GND (**floating** / flottante) | **signal + opto reference ground** |
| **3** | **Serie I/O** (bidirectional serial data) | **DATA** — the line you drive/read |
| **4** | +5 V (floating) | spare floating rail (leave unused) |
| **5** | +5 V (**max. 150 mA**) | **powers the bridge** (wired-Ethernet design — see §11) |
| **6** | n.c. | unused |

**Key facts from the official pinout:**
- Pin 3 = data, pin 5 = +5 V (both as assumed in earlier drafts).
- **Two grounds**: pin 1 = **earth**, pin 2 = **floating GND**. Reference the opto stage to
  **pin 2**, not pin 1, to keep the deck's internal isolation intact.
- **Two +5 V pins**: pin 4 (floating) and pin 5 (the 150 mA-rated one). Use pin 5.
- Pin 6 is **n.c.**
- **IR-disable strap (1+2 / 4+5): hobbyist-sourced, NOT confirmed by the deck manual.**
  Per the official pinout, shorting 1+2 bonds floating GND to earth and 4+5 ties the two
  +5 V rails — possibly how the deck senses "external controller present," but **treat as
  unverified; scope/meter before applying.** Optional anyway (only suppresses stray IR).

- **Electrical nature:** NOT RS-232, NOT RS-485. A single **bidirectional** ("Serie I/O")
  **open-collector** data line, idled high by the deck's internal pull-up, behind
  **optocoupler isolation** inside the deck. ITT/Nokia pulse-coded framing with
  ~15 us-scale carrier features.
- **CRITICAL SAFETY RULE:** never drive pin 3 hard high. Assert a bit by pulling the
  line to GND (pin 2); release it to let the deck's pull-up restore high. Use an
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
| Rewind    | (Ruckspulen) |
| Record    | gate behind a confirm/arm step (safety) |
| Pause     | auxiliary function |

Optional extras if easy after captures: Loop/Positioning, cue, and **status read-back**
(play state + real-time mm:ss tape counter) — a genuine bonus of the serial path, and easy
here because the wired design has no battery/Wi-Fi power constraints.

---

## 3. Bill of materials — primary (wired Ethernet, deck-powered)

| Part | Qty | Notes |
|---|---|---|
| **WT32-ETH01** (ESP32 + LAN8720 + RJ45) | 1 | wired Ethernet; accepts 5 V on its dedicated 5V pin |
| 3.3 V USB-serial programmer (CP2102 **3V3**) | 1 | WT32-ETH01 has no USB — needed to flash it |
| PC817 optocoupler | 2 | control + status read-back; 6N137 if edges too soft |
| Resistor 1 kOhm | 1 | control opto LED series |
| Resistor 4.7 kOhm | 1 | status opto LED series |
| Resistor 4.7 kOhm | 0–1 | pin-3 pull-up ONLY if scope shows weak idle-high |
| DIN plug to mate SERIAL LINK socket | 1 | confirm pin count/layout vs your socket (see §3a) |
| Capacitor 470–1000 uF | 1 | reservoir on the 5 V rail (covers Ethernet link-up inrush) |
| Capacitor 0.1 uF | 1 | decoupling at board |
| RJ45 patch lead | 1 | deck location to LAN (reaches easily — confirmed) |
| 2x Schottky diode (BAT43) | 0–2 | only if adding the USB-C fallback diode-OR (§11) |
| Enclosure ~80x50x25 mm | 1 | metal OK now (no Wi-Fi) — but plastic is fine too |

> Note vs earlier drafts: a **metal enclosure is now acceptable** because there's no Wi-Fi
> antenna to detune. The 5 V USB PSU is no longer the primary supply — the deck's pin 5
> powers the board (§11). Keep a USB-C PSU only if you want the fallback.

---

## 3a. Precise shopping list — Amazon.de

Search terms / typical listings on **amazon.de**. Quantities assume one build + spares.
Prices indicative; verify at purchase.

| # | Item | amazon.de search term | Qty | ~EUR | Notes |
|---|---|---|---|---|---|
| 1 | WT32-ETH01 board | `WT32-ETH01 ESP32 Ethernet Modul` (AZDelivery/DWEII) | 1–2 | 10–14 ea | the core board; buy 2 for a spare |
| 2 | USB-serial programmer 3.3 V | `CP2102 USB UART 3,3V Programmer` | 1 | 5–7 | **must be 3.3 V TTL**, not 5 V; WT32-ETH01 has no USB |
| 3 | Optocoupler PC817 | `PC817 Optokoppler DIP` (10–20er-Set) | 1 set | 6–8 | control + status + spares |
| 4 | Optocoupler 6N137 (optional, faster) | `6N137 Optokoppler High Speed` | 0–2 | 5 | only if pin-3 edges look soft on the scope |
| 5 | Resistor kit | `Widerstand Sortiment 1/4W Metallschicht` (incl. 1 kOhm, 4.7 kOhm) | 1 kit | 8–11 | covers all values incl. ADC dividers etc. |
| 6 | DIN plug | `DIN Stecker 5-polig 180 Grad Lotversion` (metal shell) | 2 | 6–9 | buy 2; **confirm it mates your SERIAL LINK socket** |
| 7 | Electrolytic caps | `Elektrolytkondensator 470uF/1000uF 16V` (Sortiment) | a few | 5 | reservoir on 5 V rail |
| 8 | Ceramic caps | `Keramikkondensator 100nF Sortiment` | a few | 5 | decoupling |
| 9 | RJ45 patch lead | `Netzwerkkabel Cat6 0,5m` (length to suit) | 1 | 5 | deck to LAN |
| 10 | Enclosure | `Aluminium Gehause 80x50x25` or `Kunststoffgehause ABS` | 1 | 6–12 | metal OK (no Wi-Fi) |
| 11 | Perfboard / jumpers | `Lochrasterplatine Set` + `Jumper Kabel Dupont` | 1 each | 8–12 | prototyping |
| 12 | Hook-up wire | `Schaltlitze Set 0,25mm2 flexibel` | 1 | 8 | DIN harness |
| 13 | USB-C PSU (optional fallback) | `USB-C Netzteil 5V 2A` | 0–1 | 8 | only for the diode-OR fallback (§11) |

**Notes / gotchas for ordering:**
- **WT32-ETH01 needs a 3.3 V USB-serial adapter to flash** (item 2) — it has no onboard
  USB. A 5 V TTL adapter can damage it. To enter flashing: ground IO0 while toggling EN.
- **DIN plug (item 6):** the manual lists a 6-pin *assignment*, but Revox SERIAL LINK uses
  a standard DIN body — most builds use the 5-pin 180 degree plug. **Verify your socket** before
  ordering; if it's a 6-pin/DIN variant, get that from Reichelt/Conrad/Mouser DE.
- PC817 (item 3) is generic and cheap; a bag of 10–20 covers control + status + mistakes.
- The DIN plug is the one item worth checking Reichelt/Conrad/Mouser DE for if Amazon
  listings look dubious.

---

## 4. Wiring (primary: wired Ethernet, deck-powered)

```
LAN -- RJ45 -- WT32-ETH01 (ESP32 + LAN8720)
                  | 5V pin  <-- DIN pin 5 (+5 V)   [via 470-1000 uF reservoir]
                  | GND     <-- DIN pin 2 (GND floating)
                  | IOxx (out) --> control opto
                  | IO35 (in)  <-- status opto      [IO35/36/39 are input-only - ideal for status]
```

### Control output stage (MCU to deck)

```
ESP32 IOxx --[1kOhm]--> PC817 #1 LED anode
                        PC817 #1 LED cathode --> ESP32 GND

PC817 #1 transistor collector --> DIN pin 3 (DATA, Serie I/O)
PC817 #1 transistor emitter   --> DIN pin 2 (GND FLOATING - not pin 1 earth)
```

- IO high -> opto conducts -> pin 3 pulled to pin 2 (line low).
- IO low  -> opto off -> deck pull-up restores high (idle).
- This **inverts** sense (matches the protocol's noted inversion). Final polarity is
  resolved in firmware via `LINK_INVERT` after scoping.
- **Reference everything to pin 2 (floating GND), never pin 1 (earth)** — preserves the
  deck's internal optocoupler isolation.
- Pick a normal GPIO for the control output (NOT IO35/36/39 — those are input-only).

### Status read-back (deck to MCU)

```
DIN pin 3 --[4.7kOhm]--> PC817 #2 LED --> (ref. to pin 2)
PC817 #2 transistor --> ESP32 IO35 (input-only pin, fine for reads)
```

- Lets you parse the deck's return frames (play state, mm:ss tape counter) into MQTT value
  topics. Free to include here — no power constraint in the wired design.

### Power

- **DIN pin 5 (+5 V / 150 mA) powers the WT32-ETH01** via its dedicated 5V pin. A
  470–1000 uF reservoir cap covers Ethernet link-up inrush. See §11 for the budget (the
  board draws ~120 mA at 100M — fits the rail with thin headroom, so **measure**).
- Pin 4 (+5 V floating) — leave unused.
- **Optional USB-C fallback:** diode-OR pin 5 and a USB-C 5 V PSU into the board's 5V pin
  (2x Schottky) so you can power from USB if the rail proves marginal under load.

### IR disable (optional, UNVERIFIED — see §1)

- The hobbyist note "short DIN 1+2 and 4+5" is **not confirmed** by the deck manual and,
  per the official pinout, bonds floating-GND/earth and the two +5 V rails. Only attempt
  after scoping; merely suppresses stray IR and is not required for control.

---

## 5. Firmware

**Base repo:** `https://github.com/0815simon/revox-rc5-remote` — file `revox_web_remote.ino`.

**What to keep:** the **serial-link bit-banging routine** (frame to GPIO toggles).
**What to delete:** the RC5/IR receive code and the bundled webserver.
**What to add:** **Ethernet** (`ETH.begin()`) + MQTT (PubSubClient) + a clean command table.

> The repo is the author's self-described "hacky, trial-and-error" project. Lift and
> adapt the TX core; don't flash as-is.

**Wired vs Wi-Fi:** the only transport change from the Wi-Fi variant is `ETH.begin()`
instead of `WiFi.begin()` (the WT32-ETH01 Ethernet init, LAN8720, with its specific
`ETH_PHY_*` defines). MQTT, command table, opto logic, and the pin-2 reference rule are
identical. **Force 100M link speed** (see §11 — 10M draws *more* current on this PHY).

### Skeleton

```cpp
#include <ETH.h>

// ---- config ----
const char* MQTT_HOST = "192.168.x.x";   // Wirenboard broker (Mosquitto on the WB)
const uint16_t MQTT_PORT = 1883;
const char* DEVICE_ID = "revox_b215";

const int   PIN_LINK    = 14;            // control opto LED (any normal GPIO, NOT 35/36/39)
const int   PIN_STATUS  = 35;            // status opto in (input-only pin is fine)
const bool  LINK_INVERT = true;          // set after scoping line polarity

// ---- Ethernet bring-up (WT32-ETH01 / LAN8720) ----
// Use the board's documented ETH_PHY_* defines; force 100M.
void netUp() {
  ETH.begin();                  // WT32-ETH01 default LAN8720 config
  // optionally pin link to 100M full-duplex per board notes
}

// ---- ITT serial-link bit-banger (adapted from 0815simon) ----
// Sends one Revox frame: device id 04 + function code.
// Bit order (MSB/LSB) and bit timing come from YOUR scope captures.
void sendLinkFrame(uint16_t frame) {
  // assert = pull line low; idle = release (deck pull-up brings high)
  // honour LINK_INVERT
  // use delayMicroseconds() with measured bit widths (~15 us-scale features:
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
- For each control: `/devices/revox_b215/controls/<name>/meta/type` (retained)
  - momentary keys (stop, play, ff, rewind, record, pause) -> type `pushbutton`
  - standby -> type `switch` (stateful on/off) if desired
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

**Integration choice:** **broker-direct** — the ESP connects to the WB controller's
Mosquitto broker over the LAN. The deck appears as a native WB device; rules/scenes/UI work
with no extra glue.

---

## 7. Casing

- **Material:** metal is now fine (no Wi-Fi antenna to detune); ABS/PETG also fine. If
  printing, PETG handles warm-equipment proximity better than PLA.
- **Layout:** WT32-ETH01 on standoffs; opto + passives on a small perfboard daughter area.
  DIN pigtail exits one end via a grommet (strain relief); RJ45 exits the other.
- **Ventilation:** a few slots; the board runs warm (~120 mA); no fan needed.
- **Mounting:** VHB pad or keyhole tab to hang behind the rack. Keep away from the deck's
  transformer area.
- **Label** the DIN pigtail with the pinout (use the §1 confirmed map).

---

## 8. Measurements still required (before/at bring-up)

1. DONE — DIN pinout, +5 V vs GND — confirmed (§1). Still do the meter check: pin 5 to pin 2
   ~ +5 V, deck powered, rear switch on — **and confirm it holds ~5 V with the WT32-ETH01
   running and the Ethernet link up** (the worst moment is link negotiation; §11).
2. **B205 frame captures on pin 3** — deck only, scope pin 3 to **pin 2** while firing the
   **B205** at the front for each of: standby, stop, play, ff, rewind, record, pause.
   Record: idle level, logic swing, start-bit timing, 0/1 bit periods, frame length,
   repeat gap, bit order. These fill the command table and set timing.
3. **Polarity** — from the captures, set `LINK_INVERT`.
4. **Wake test** — put deck in standby, send Stop; does it wake? Repeat Pause, then Play.
   Note which wake it (settles the "power on" mapping).

---

## 9. Bring-up sequence

1. Flash the WT32-ETH01 (3.3 V USB-serial; IO0 low while toggling EN). Confirm it gets a
   DHCP lease and the MQTT topics appear in WB.
2. Scope the output stage into a dummy load: confirm pull-low/release; set `LINK_INVERT`.
3. Capture B205 frames on pin 3 (deck only) -> fill command table (§5).
4. Power the board from pin 5; **verify the rail holds under load with the link up** (§8.1).
5. Connect (reference to pin 2); send **stop** first; then play / pause / ff / rewind;
   **record last** (gated).
6. Add status-read opto; parse return frames into WB value topics.

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
- **Two grounds on the connector** — always reference to pin 2 (floating), never pin 1
  (earth), or you defeat the deck's isolation.
- **WT32-ETH01: force 100M Ethernet.** At 10M the LAN8720 draws *more* (~160 mA vs ~120 mA)
  due to its signal encoding — and 160 mA would exceed the deck's 150 mA rail.
- **WT32-ETH01 input-only pins:** IO35/36/39 cannot drive outputs — use them for the status
  read, not the control opto.

---

## 11. Power decision — why wired Ethernet + deck 5 V

We worked through every option; this is the rationale, kept so the choice is auditable.

**The core constraint:** deck pin 5 supplies **+5 V at 150 mA max** (manual §1.4).

| Connectivity / mode | Avg draw | Deck-5V rail? | Battery life (3000 mAh) |
|---|---|---|---|
| Wi-Fi, always-on | ~120 mA + 300–500 mA spikes | NO — spikes blow past 150 mA | ~20 h |
| Wi-Fi, light-sleep | ~5–15 mA | yes, with reservoir cap | ~1–3 weeks |
| **Ethernet (WT32-ETH01), 100M** | **~120 mA steady, no spikes** | **yes — fits (thin headroom)** | ~18–40 h |
| Ethernet + MCU sleep | ~50–90 mA | yes | ~1–2 days |

**Why wired wins for this install:**
- Ethernet draws a **steady** current with **no Wi-Fi TX spikes** — and the spikes were the
  specific thing that broke the 150 mA rail. So the deck's own 5 V becomes a viable supply.
- A **LAN cable reaches the deck location easily** (confirmed), so wired is no hardship.
- It **deletes the entire fragile subsystem**: no battery, no charger, no load-share, no
  charge-on-notification ritual, no `battery_*` topics. The box just lives on the deck.
- Same MQTT model; `ETH.begin()` replaces `WiFi.begin()`.

**The one caveat:** ~120 mA vs a 150 mA rail is **thin headroom**. Mitigations, in order:
1. **Force 100M** (10M draws ~160 mA — would exceed the rail).
2. **Reservoir cap** (470–1000 uF) on the 5 V rail to cover link-up inrush.
3. **Measure** pin 5 under load with the link up before trusting it (§8.1).
4. If it sags: **USB-C fallback via diode-OR** (parts in BOM), or power wholly from USB-C
   and use pin 5 only as reference.

---

## Appendix A — alternative designs (not chosen)

Kept for reference; the wired design above supersedes these.

### A.1 Wi-Fi + external USB power
The original plan: an ESP32 (WROOM-32) on Wi-Fi, powered from a **USB 5 V supply** (pin 5's
150 mA can't survive Wi-Fi spikes). Needs a **non-metal enclosure** (antenna). Same opto
stages and MQTT. Use only if running a LAN cable is undesirable. If used, prefer
**light-sleep** to cut average draw.

### A.2 Battery-powered, charge-on-notification
A self-contained battery box with **USB-C TP4056+DW01A charger + 18650 cell + load-share**,
running the ESP in **light-sleep** (~1–3 weeks/charge). Firmware publishes four topics —
`battery` (%), `hours_remaining` (live voltage-slope estimate), `battery_low` ("plug in",
<=3.40 V), `battery_full` ("unplug", from the TP4056 CHRG pin) — plus `charging`. The cell is
the source; USB-C only replenishes when notified. **Superseded** because wired Ethernet + deck
power removes the whole battery subsystem and its maintenance ritual. Runtime physics: an
always-on Wi-Fi ESP32 drains a 3000 mAh cell in ~a day; only light-sleep makes manual
charging practical.

### A.3 Option A — Wirenboard controller drives the link over 3 m
Drive the serial link directly from the WB controller's GPIO over the existing wall wiring.
Fails on Linux timing jitter + a 3 m unbuffered open-collector run; if ever attempted, buffer
+ opto-isolate at the deck end and make that end "B-ready" so an ESP can drop in.

---

## 12. Source references

- **B215 deck service manual (Studer Revox, trilingual DE/EN/FR)** — §1.4 rear-panel
  description: **SERIAL LINK pin assignment (pin 1 GND earth, 2 GND floating, 3 Serie I/O,
  4 +5 V floating, 5 +5 V max 150 mA, 6 n.c.)**; transport/audio/alignment/schematics.
- **Revox "IR Remote Control Systems" service manual** (order no. 10.30.0430): device
  identifier table (04 = B215), serial-link protocol, drive/aux function enumeration,
  B215 status string format. (archive.org: `studer_Revox_IR_Remote_System_Serv`)
- **WT32-ETH01** (Wireless-Tag): ESP32 + LAN8720A, RJ45, 3V3 **or** 5V supply pin; ~120 mA
  at 100M (more at 10M — LAN8720 encoding); no USB, flash via 3.3 V serial (IO0 low + EN);
  IO35/36/39 input-only. (datasheet V1.4 + egnor/wt32-eth01 notes + esp32.com current thread)
- `0815simon/revox-rc5-remote` (GitHub): working ESP8266 serial-link TX; DIN data/GND/+5V
  notes and the **unverified** IR-disable strap idea.
- Tapeheads.net "Info on Revox Serial Link protocol wanted": bidirectional single-wire
  warning, open-collector / opto recommendation, Nokia/ITT protocol family.
- IRMP discussion #80: native remote waveform timing (~15 us bursts; 150/300 us bit
  periods), TBA2800 preamp note.
- Wirenboard wiki: WB-MSW v3 is RS-485/Modbus IR module (IR-only actuator); WB controller
  has native RS-485 + Linux + Mosquitto broker; MQTT device convention.
- NEEO forum: B215 PLAY triggers power-on event (wake-on-transport evidence).
- Li-ion / TP4056 (Appendix A.2): TP4056+DW01A USB-C charger modules; ~37% C charge current
  via Rprog; DW01A over-discharge cutoff ~2.4 V / release ~3.0 V.
