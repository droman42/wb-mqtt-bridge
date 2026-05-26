# Revox B215 → Wirenboard via SERIAL LINK — Build & Handoff

**Goal.** Control a Revox B215 cassette deck from a Wirenboard PLC by driving the deck's
rear **SERIAL LINK** port directly with a small ESP32 that publishes/subscribes
**Wirenboard-conformant MQTT**. IR is bypassed entirely.

**Status.** SERIAL LINK pinout CONFIRMED from the official B215 service manual (§1.4).
Electrical nature (bidirectional, opto-isolated, +5 V/150 mA) confirmed. Outstanding:
scope-capture of the B205 command/status frames (protocol bytes/timing) and `LINK_INVERT`
polarity — see §11.

**Companion documents** (the four-transport ESP32-bridge family — shared design,
shared firmware scaffolding; this doc covers the B215-specific SERIAL LINK protocol):
[`wb-revoxa77-esp32-bridge.md`](./wb-revoxa77-esp32-bridge.md) (Revox A77 reel-to-reel),
[`wb-pioneer-cld-d925-esp32-bridge.md`](./wb-pioneer-cld-d925-esp32-bridge.md) (Pioneer LD),
[`wb-panasonic-nv-fs90-esp32-bridge.md`](./wb-panasonic-nv-fs90-esp32-bridge.md) (Panasonic VHS).

---

## 1. Design summary

All four ESP32 bridges share one canonical design — applied here to the B215:

- **Board:** ESP32 WROOM-32 (Wi-Fi), in a plastic enclosure with the PCB antenna near
  a case edge. No WT32-ETH01, no Ethernet, no RJ45.
- **Power: deck-derived only — no plugs, no USB, no PoE.** B215 tap = **SERIAL LINK
  pin 5 (+5 V)**. The 150 mA-rail spike worry is gone: light-sleep + reservoir cap
  drop the steady draw to ~15 mA and absorb the Wi-Fi TX spikes locally so the rail
  only sees the average.
- **Wi-Fi runs in light-sleep** (DTIM-driven), avg ~15 mA, with commands still
  arriving instantly. Light-sleep + reservoir cap are a pair — an always-on Wi-Fi
  MCU would empty the cap.
- **Reservoir cap network on the 5 V tap:**
  - **1000 µF low-ESR** across the 5 V tap,
  - **100 µF + 0.1 µF** decoupling at the board,
  - **2.2–10 Ω inrush resistor** in series with the big cap so the deck rail doesn't
    see the cap-fill surge at power-up.
- **OTA is mandatory.** First flash goes over a 3.3 V USB-serial header (the only time
  a cable touches the box); all subsequent updates ship over Wi-Fi via
  `esp_https_ota` with dual-OTA-partition rollback safety (see `partitions.csv`).
  After first flash, the USB-serial adapter is **literally never needed again**.

This is the single source of truth for the design; the sections below specify the
B215-specific hardware (pinout, wiring, BOM, bring-up) — they do not relitigate the
design.

> 30-second sanity check before connecting: meter pin 5 to pin 2 with the deck powered
> (rear switch on) and confirm ~+5 V. The manual pinout is authoritative, but the scan
> is old and a quick check is cheap insurance.

---

## 2. How the SERIAL LINK works (CONFIRMED from B215 manual §1.4)

- **Deck:** Revox B215, serial 013773, Made in West Germany (Willi Studer GmbH,
  D-7827 Loffingen), 45 W. Genuine B215. Two manuals apply: the **B215 deck service
  manual** (transport/audio/schematics — source of the pinout below) and the separate
  **"IR Remote Control Systems"** manual (order no. 10.30.0430 — source of the
  serial-link *protocol*, device id 04, and the drive-function enumeration).
- **Rear panel** (confirmed from photo + manual §1.4): a panel labelled **SERIAL LINK /
  REMOTE CONTROL** with the DIN socket, a POWER panel with voltage selector + **hard
  mains rocker switch**, and an AUDIO panel (L/R in, L/R out RCA).
- **The SERIAL LINK is the chosen control path.** It is part of the Revox B200-series
  remote system; the deck addresses itself on this bus as **device identifier 04**.

### Rear panel (manual §1.4)

![Revox B215 rear panel showing the AUDIO input/output RCAs, the POWER panel with voltage selector and AC inlet, and the SERIAL LINK / REMOTE CONTROL DIN socket at right](./img/rear-panel.png)

### CONFIRMED pinout (manual §1.4 — "Occupation des poles de la fiche Serial Link")

![Revox B215 SERIAL LINK pin assignment from the service manual: pin 1 GND earth, pin 2 GND floating, pin 3 serial I/O, pin 4 +5V floating, pin 5 +5V max 150 mA, pin 6 n.c.](./img/serial-link-pinout.png)

| Pin | Manual definition | Use in this build |
|---|---|---|
| **1** | GND (earth / terre) | chassis earth — **do NOT use as the signal reference** |
| **2** | GND (**floating** / flottante) | **signal + opto reference ground** |
| **3** | **Serie I/O** (bidirectional serial data) | **DATA** — the line you drive/read |
| **4** | +5 V (floating) | spare floating rail (leave unused) |
| **5** | +5 V (**max. 150 mA**) | **powers the bridge** (§4 power tap) |
| **6** | n.c. | unused |

**Key facts:**
- Pin 3 = data, pin 5 = +5 V (as assumed in earlier drafts).
- **Two grounds**: pin 1 = **earth**, pin 2 = **floating GND**. Reference the opto
  stage to **pin 2**, not pin 1, to keep the deck's internal isolation intact.
- **Two +5 V pins**: pin 4 (floating) and pin 5 (the 150 mA-rated one). Use pin 5.
- Pin 6 is **n.c.**
- **IR-disable strap (1+2 / 4+5): hobbyist-sourced, NOT confirmed by the deck manual.**
  Per the official pinout, shorting 1+2 bonds floating GND to earth and 4+5 ties the
  two +5 V rails — possibly how the deck senses "external controller present," but
  **treat as unverified; scope/meter before applying.** Optional anyway (only
  suppresses stray IR).

**Electrical nature:** NOT RS-232, NOT RS-485. A single **bidirectional** ("Serie I/O")
**open-collector** data line, idled high by the deck's internal pull-up, behind
**optocoupler isolation** inside the deck. ITT/Nokia pulse-coded framing with
~15 µs-scale carrier features.

> **CRITICAL SAFETY RULE:** never drive pin 3 hard high. Assert a bit by pulling the
> line to GND (pin 2); release it to let the deck's pull-up restore high. Use an
> **open-collector / open-drain (ideally opto-isolated) output stage**. Driving +5 V
> onto the line can damage the deck's output when it tries to pull low.

**Power on/off behaviour:** "off" = **Standby** (deck logic stays powered; rear hard
switch must remain ON permanently). "On" is best modelled as **wake-on-transport**:
sending Play wakes the deck and acts. Whether Stop/Pause alone wake it is unconfirmed
— on the test list (§11).

**Auto-reverse:** direction is handled internally. There is **no direction command**.
**Eject:** mechanical/front-panel; do **not** assume a serial eject exists. Verify.

---

## 3. Target command set (device identifier 04)

Seven functions in scope, mapped to the B215 drive-function enumeration:

| Function | Notes |
|---|---|
| Standby | stateful on/off; "power" surfaces as this |
| Stop    | safe first test command |
| Play    | also serves as "wake / power on" |
| FF      | fast-forward (Vorspulen) |
| Rewind  | (Rückspulen) |
| Record  | gate behind a confirm/arm step (safety) |
| Pause   | auxiliary function |

Optional extras if easy after captures: Loop/Positioning, cue, and **status read-back**
(play state + real-time mm:ss tape counter) — a genuine bonus of the serial path.

---

## 4. Wiring

### Topology

```
DIN pin 5 (+5 V)  ─┬─[2.2–10 Ω]──┬── ESP32 WROOM-32 5 V rail
                   │              │     (100 µF + 0.1 µF decoupling at board)
                   │            1000 µF low-ESR  (reservoir; see §1)
                   │              │
DIN pin 2 (GND fl.) ──────────────┴── ESP32 GND
DIN pin 3 (DATA)   ──[control opto, see below]── GPIO out
                   ──[status opto,  see below]── GPIO in
```

### Control output stage (MCU to deck)

```
ESP32 GPIOxx ──[1 kΩ]──► PC817 #1 LED anode
                          PC817 #1 LED cathode ──► ESP32 GND
PC817 #1 transistor collector ──► DIN pin 3 (Serie I/O)
PC817 #1 transistor emitter   ──► DIN pin 2 (floating GND — NOT pin 1 earth)
```

- GPIO high → opto conducts → pin 3 pulled to pin 2 (line low).
- GPIO low  → opto off → deck pull-up restores high (idle).
- This **inverts** sense (matches the protocol's noted inversion). Final polarity is
  resolved in firmware via `LINK_INVERT` after scoping.
- **Reference everything to pin 2 (floating GND), never pin 1 (earth)** — preserves
  the deck's internal optocoupler isolation.
- Pick a normal GPIO for the control output (NOT IO34–39 — those are input-only).

### Status read-back (deck to MCU)

```
DIN pin 3 ──[4.7 kΩ]──► PC817 #2 LED ──► (ref. to pin 2)
PC817 #2 transistor   ──► ESP32 IO35 (input-only is fine for reads)
```

Lets you parse the deck's return frames (play state, mm:ss tape counter) into MQTT
value topics.

### Power tap (per §1)

- **DIN pin 5 (+5 V)** powers the board via the reservoir-cap network in §1
  (1000 µF + 2.2–10 Ω inrush resistor on the tap; 100 µF + 0.1 µF at the board).
- DIN pin 2 (floating GND) is the return.
- Pin 4 (+5 V floating) — leave unused.

### IR disable (optional, UNVERIFIED — see §2)

The hobbyist note "short DIN 1+2 and 4+5" is **not confirmed** by the deck manual
and, per the official pinout, bonds floating-GND/earth and the two +5 V rails. Only
attempt after scoping; merely suppresses stray IR and is not required for control.

---

## 5. Firmware notes

The shared core (Wi-Fi + light-sleep + MQTT + identity + OTA + dispatch) lives in
`src/main.cpp` / `wifi_setup.cpp` / `wb_mqtt.cpp` / `identity.cpp` / `ota.cpp` —
**no deck-specific code there.** The B215-specific driver is
`src/driver_b215.cpp` behind the `DeviceDriver { begin, doCommand, poll }` contract
in `include/device_driver.h`.

**Reference for the bit-bang core:** `https://github.com/0815simon/revox-rc5-remote`
(`revox_web_remote.ino`). Lift and adapt the **serial-link bit-banging routine**
(frame → GPIO toggles). Discard the RC5/IR receive code and the bundled webserver
(transport here is Wi-Fi + MQTT, in IDF; not Arduino + webserver). The repo is the
author's self-described "hacky, trial-and-error" project — adapt the TX core, don't
flash as-is.

**Bit timing.** Use `esp_rom_delay_µs()` (microsecond-grain busy-wait, IDF) with
captured bit widths; guard the critical section with `portDISABLE_INTERRUPTS()` /
`portENABLE_INTERRUPTS()` if Wi-Fi coexistence jitter becomes a problem. The frame
shape (~15 µs-scale features, start/0/1/repeat-gap) comes from §11 captures.

**Command table.** Replace placeholder frame values with captured B205 frames for
each of: standby, stop, play, ff, rewind, record, pause. See `src/driver_b215.cpp`
for the table location.

**Polarity.** Set `LINK_INVERT` after scoping (§11). The line idles high; assert by
pulling low.

**Record safety.** Gate `record` behind a second confirming MQTT topic or a short
"armed" window so a stray message can't start a recording over a tape.

---

## 6. MQTT (Wirenboard convention)

Same convention `wb-mqtt-serial` uses:

| Topic | Direction | Retained | Purpose |
|---|---|---|---|
| `/devices/<id>/meta/name` | publish | yes | device display name |
| `/devices/<id>/controls/<c>/meta/type` | publish | yes | `pushbutton` / `switch` |
| `/devices/<id>/controls/<c>` | publish | yes | current value/state |
| `/devices/<id>/controls/<c>/on` | **subscribe** | — | command in (UI/rules write here) |

`<id>` here = `revox_b215`. **Integration choice:** broker-direct — the ESP connects
to the WB controller's Mosquitto broker over Wi-Fi. The deck appears as a native WB
device; rules/scenes/UI work with no extra glue. Per-control type: momentary
(`stop`/`play`/`ff`/`rewind`/`record`/`pause`) → `pushbutton`; `standby` → `switch`.

---

## 7. Bill of materials

| Part | Qty | Notes |
|---|---|---|
| ESP32 WROOM-32 dev board (Wi-Fi) | 1 | onboard USB-serial; PCB antenna |
| PC817 optocoupler | 2 | control + status read-back; 6N137 if edges too soft |
| Resistor 1 kΩ | 1 | control opto LED series |
| Resistor 4.7 kΩ | 1 | status opto LED series |
| Resistor 4.7 kΩ | 0–1 | pin-3 pull-up ONLY if scope shows weak idle-high |
| Resistor 2.2–10 Ω | 1 | inrush limiter on the 5 V tap (§1) |
| Capacitor 1000 µF low-ESR | 1 | reservoir cap on the 5 V tap (§1) |
| Capacitor 100 µF | 1 | decoupling at board |
| Capacitor 0.1 µF | 1 | decoupling at board |
| DIN plug to mate SERIAL LINK socket | 1 | confirm pin count/layout vs your socket (see §8) |
| Plastic enclosure (~80×50×25 mm) | 1 | Wi-Fi antenna must NOT be inside metal — `cases/` v5 |
| Hook-up wire | — | DIN harness |

---

## 8. Shopping list — Amazon.de

Search terms / typical listings on **amazon.de**. Quantities assume one build + spares.
Prices indicative; verify at purchase.

| # | Item | amazon.de search term | Qty | ~EUR | Notes |
|---|---|---|---|---|---|
| 1 | ESP32 WROOM-32 dev board | `ESP32 NodeMCU WROOM-32` (3-pack) | 1 set | 18–22 | onboard USB-serial; pick PCB-antenna variant |
| 2 | Optocoupler PC817 | `PC817 Optokoppler DIP` (10–20er-Set) | 1 set | 6–8 | control + status + spares |
| 3 | Optocoupler 6N137 (optional, faster) | `6N137 Optokoppler High Speed` | 0–2 | 5 | only if pin-3 edges look soft |
| 4 | Resistor kit | `Widerstand Sortiment 1/4W Metallschicht` (incl. 1 kΩ, 4.7 kΩ, 2.2–10 Ω) | 1 kit | 8–11 | covers all values |
| 5 | DIN plug | `DIN Stecker 5-polig 180 Grad Lötversion` (metal shell) | 2 | 6–9 | buy 2; **confirm it mates your SERIAL LINK socket** |
| 6 | Reservoir cap 1000 µF low-ESR | `Elektrolytkondensator 1000uF 16V Low ESR` | 2 | 5 | the cap is load-bearing — get a low-ESR type |
| 7 | Decoupling caps | `Elektrolytkondensator 100uF 16V` + `Keramikkondensator 100nF Sortiment` | a few | 5 | at-board decoupling |
| 8 | Plastic enclosure | `Kunststoffgehäuse ABS 80x50x25` | 1 | 6–10 | **must be non-metal** (Wi-Fi antenna) |
| 9 | Perfboard / jumpers | `Lochrasterplatine Set` + `Jumper Kabel Dupont` | 1 each | 8–12 | prototyping |
| 10 | Hook-up wire | `Schaltlitze Set 0,25mm² flexibel` | 1 | 8 | DIN harness |

**Notes / gotchas for ordering:**
- The reservoir cap is the load-bearing part of the power design — buy a proper
  **low-ESR** electrolytic, not a generic. ESR matters for soaking up Wi-Fi
  TX-current spikes.
- **DIN plug:** the manual lists a 6-pin *assignment*, but Revox SERIAL LINK uses a
  standard DIN body — most builds use the 5-pin 180° plug. **Verify your socket**
  before ordering; if it's a 6-pin variant, get that from Reichelt/Conrad/Mouser DE.
- PC817 is generic and cheap; a bag of 10–20 covers control + status + mistakes.

---

## 9. Casing

- **Material:** plastic (ABS/PETG). Wi-Fi antenna must not be inside a metal box. If
  printing, PETG handles warm-equipment proximity better than PLA.
- **Layout:** ESP32 WROOM-32 with the **PCB antenna pointing toward a case edge** —
  not over the deck's transformer area, not next to the reservoir cap.
- **DIN pigtail** exits one end via a grommet (strain relief). Label the pinout
  (use the §2 confirmed map).
- **Mounting:** VHB pad or keyhole tab to hang behind the rack. Keep away from the
  deck's transformer area (RF + thermal both).
- See `cases/` for the v5 STL files.

---

## 10. Bring-up sequence

1. **First flash** the WROOM-32 over the onboard USB-serial header — single wired
   step in the box's life. Confirm Wi-Fi associates, MQTT topics appear in WB.
2. **Bench the output stage** into a dummy load: confirm pull-low/release; set
   `LINK_INVERT`.
3. **Capture B205 frames on pin 3** (deck only, scope referenced to pin 2) → fill
   the §5 command table.
4. **Power the board from pin 5** via the §1 cap network; verify the 5 V rail at
   the board stays at 5 V during MQTT activity (cap absorbing TX spikes).
5. **Connect** (signal + GND, referenced to pin 2); send **stop** first; then
   play / pause / ff / rewind; **record last** (gated).
6. **Add status-read opto**; parse return frames into WB value topics.

---

## 11. Open items (bench captures + measurements)

Paste this file back and say "continue the Revox B215 build."

1. **Scope captures of the B205 frames on pin 3** for the seven functions (§3) —
   needed for the command table + timing. Record: idle level, logic swing,
   start-bit timing, 0/1 bit periods, frame length, repeat gap, bit order.
2. **Fill the command table** (§5 / `src/driver_b215.cpp`) with captured frame
   values; set `LINK_INVERT`.
3. **Wake test** — put deck in standby, send Stop; does it wake? Repeat Pause,
   then Play. Note which wake it (settles the "power on" mapping).
4. **Watchdog field note** — the B215 transport has been reported to auto-stop
   within ~4 s if control sequencing is unexpected (was a fault from a swapped
   microprocessor, not normal behaviour). If your first Play "bounces," suspect
   framing/timing, not wiring.
5. **B201 vs B205 capture** — don't capture frames from a B201 (it doesn't drive
   Play on the tape decks); use the B205.

---

## 12. Source references

- **B215 deck service manual (Studer Revox, trilingual DE/EN/FR)** — §1.4 rear-panel
  description: SERIAL LINK pin assignment (pin 1 GND earth, 2 GND floating, 3 Serie
  I/O, 4 +5 V floating, 5 +5 V max 150 mA, 6 n.c.); transport/audio/alignment/
  schematics.
- **Revox "IR Remote Control Systems" service manual** (order no. 10.30.0430):
  device identifier table (04 = B215), serial-link protocol, drive/aux function
  enumeration, B215 status string format. (archive.org:
  `studer_Revox_IR_Remote_System_Serv`)
- `0815simon/revox-rc5-remote` (GitHub): working ESP8266 serial-link TX; DIN data/
  GND/+5 V notes and the **unverified** IR-disable strap idea.
- Tapeheads.net "Info on Revox Serial Link protocol wanted": bidirectional
  single-wire warning, open-collector / opto recommendation, Nokia/ITT protocol
  family.
- IRMP discussion #80: native remote waveform timing (~15 µs bursts; 150/300 µs
  bit periods), TBA2800 preamp note.
- Wirenboard wiki: WB-MSW v3 is RS-485/Modbus IR module (IR-only actuator); WB
  controller has native RS-485 + Linux + Mosquitto broker; MQTT device convention.
- NEEO forum: B215 PLAY triggers power-on event (wake-on-transport evidence).
