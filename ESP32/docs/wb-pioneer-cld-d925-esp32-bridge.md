# Pioneer CLD-D925 → Wirenboard via CONTROL IN (Pioneer SR) — Build & Handoff

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
>   slot). ~15 mA avg is easy on a logic rail; **meter once** under load to confirm. (Pioneer
>   can alternatively carry that 5 V on a **stereo CONTROL IN jack** — ring=+5 V — for a
>   single-cable box; see \u00a74 Power.)
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



**Goal:** Control a Pioneer CLD-D925 LaserDisc/CD player from a Wirenboard PLC by feeding
the player's rear **CONTROL IN** (Pioneer "SR" / System Remote) minijack with a small
ESP32 that publishes/subscribes **Wirenboard-conformant MQTT**. The unreliable external IR
blaster is replaced by a clean wired connection. **This is the easiest of the four-deck set**
— no opening the unit, no protocol reverse-engineering.

**Primary design:** wired-Ethernet ESP32 (WT32-ETH01) → 3.5 mm plug into CONTROL IN →
emit the player's own remote codes as a **baseband (carrier-stripped) waveform** on the tip.
Same MQTT/architecture as the Revox builds. Wi-Fi is an option (this box can be powered by
deck +5 V tap; see §4 Power. No USB/PoE.).

**Companion documents:**
[`wb-revoxb215-esp32-bridge.md`](./wb-revoxb215-esp32-bridge.md),
[`wb-revoxa77-esp32-bridge.md`](./wb-revoxa77-esp32-bridge.md).
Shared MQTT / casing / firmware scaffolding; this doc details what's CLD-D925-specific.

**Status:** CONTROL IN electrical interface and protocol CONFIRMED from a detailed
reverse-engineering writeup (idle ~5 V, open-collector, ~100 kΩ pull-up, baseband IR copy,
sleeve NOT grounded, plugging in disables internal IR). Outstanding: capture the CLD-D925
remote's codes and confirm idle/polarity on your unit with a scope.

---

## 0. How to resume this with Claude later

Paste this file back and say "continue the Pioneer CLD-D925 build." Outstanding:

1. **Scope the CONTROL IN jack** on your unit: confirm ~5 V idle on tip, that a remote
   press produces active-low baseband pulses, and that the sleeve is NOT grounded (§8).
2. **Capture the CLD-D925 remote's codes** (you have the remote) — both the raw IR for
   reference and the baseband bitstream you'll replay (§5/§8).
3. Decide control scope (Play/Pause/Stop/Chapter±/Scan±/Display/Power, etc.) and map to
   MQTT controls (§2).

Then Claude can finalise the code table and the emit routine.

---

## 1. How Pioneer SR "CONTROL IN" works (CONFIRMED)

Pioneer's **SR (System Remote)** is, in effect, **a wired IR repeater built into the gear**.
A controlling unit's CONTROL OUT carries the **demodulated (carrier-stripped) version of
whatever IR its receiver saw**, and a controlled unit's CONTROL IN accepts that same baseband
signal *instead of* its built-in IR sensor. Confirmed electrical facts (from scope analysis
of Pioneer SR jacks):

- **Connector:** 3.5 mm **mono** jack (tip = signal, sleeve = "ground" — but see below).
- **Idle level:** tip sits at about **+5 V** when idle.
- **Output/Input type:** **open-collector with an internal pull-up** — like a Sharp/Vishay
  IR receiver module's output. The CONTROL IN internal pull-up measured ~**100 kΩ**
  (CONTROL OUT ~10 kΩ). You **pull the tip low** to signal; release to let it return high.
- **Protocol:** the tip signal is a **baseband (no 38 kHz carrier) copy of the IR remote
  waveform**. Scope comparison showed the CONTROL OUT tip and a demodulating IR receiver's
  output carrying the *identical* signal. It also repeats **any** remote's codes, not just
  Pioneer's — i.e. it's protocol-agnostic at the waveform level.
- **Plugging in disables the internal IR sensor** (Pioneer's jack behaves as "RC-IX": Input +
  disables-internal-receiver). Good — no double-triggering.
- **The sleeve is NOT grounded.** Pioneer deliberately floats the ring/sleeve (avoids ground
  loops between chained units). **You must provide a ground reference separately** — typically
  via the shield of an audio/video RCA cable already linking the player, or a dedicated ground
  wire to chassis. Some Pioneer units won't respond until ground is supplied this way.

**Net:** to control the CLD-D925, drive its CONTROL IN tip with the **carrier-stripped
bitstream of its own remote codes**, pulling low (open-collector), referenced to a ground you
supply. No carrier generation needed — that's the whole point of SR.

---

## 2. Target command set

The CLD-D925 is a LaserDisc/CD/CDV player; useful controls (capture each from the remote):

| Function | Notes |
|---|---|
| Power (on/off) | confirm whether it's a discrete on/off or a toggle on the remote |
| Play | |
| Pause / Still | |
| Stop | |
| Scan / Search +/- | fast forward/reverse |
| Chapter / Track +/- | skip |
| Display / On-screen | optional |
| Open/Close (eject) | optional |
| Side change | LaserDisc-specific; confirm if remote exposes it |

MQTT controls of type `pushbutton`, plus optionally a `switch` for power. No status read-back
(SR CONTROL IN is one-way; the player gives no feedback on this jack — unlike the B215's
serial link). If status ever matters, that's a separate tap, out of scope here.

---

## 3. Why this is simpler than the Revox builds

| | B215 (serial) | A77 (contacts) | **CLD-D925 (SR CONTROL IN)** |
|---|---|---|---|
| Reverse-engineering | scope ITT frames | trace pin-pairs | **none — replay remote codes** |
| Open the unit? | no (rear DIN) | no (rear DIN) | **no (rear minijack)** |
| Output stage | open-collector opto on data | 5× opto-MOSFET dry contacts | **one open-collector onto the tip** |
| Carrier? | n/a | n/a | **none — baseband (SR strips it)** |
| Status back | yes | sensor-added | no (one-way jack) |
| Power from device? | 5 V/150 mA pin | 27 V pin | **none on the jack — deck-power via internal +5 V tap (§4)** |

The CLD-D925 is the cleanest: it's essentially "blast the remote, but over a wire that the
deck already accepts." Your existing remote-code captures are directly reusable.

---

## 4. Wiring

```
WT32-ETH01 (or any ESP32)
   IOxx (out) ──► open-collector stage ──► 3.5 mm TIP  → CONTROL IN
   board GND  ──────────────────────────► ground reference (see note)  → CONTROL IN sleeve / deck chassis
```

### Open-collector output stage onto the tip

The CONTROL IN already has its own ~100 kΩ pull-up to ~5 V. You only need to **pull the tip
low**. Two equivalent ways:

**(a) Transistor (simplest):**
```
ESP32 IOxx ──[1kΩ]──► base of NPN (BC547 / 2N3904)
                       collector ──► 3.5 mm TIP (CONTROL IN)
                       emitter   ──► ground reference
```
- IO high → transistor conducts → tip pulled low (asserted).
- IO low → transistor off → deck's 100 kΩ pull-up restores ~5 V (idle).

**(b) Optocoupler (cleaner isolation, recommended):**
```
ESP32 IOxx ──[1kΩ]──► PC817 LED ──► ESP32 GND
PC817 transistor collector ──► 3.5 mm TIP
PC817 transistor emitter   ──► ground reference
```
- Keeps your board's ground separate from the deck's floating reference — tidy, and avoids
  surprises since the sleeve isn't a real ground.

### Polarity (carrier-stripped IR is active-low here)

A demodulating IR receiver idles **high** and pulses **low** during bursts. The SR CONTROL
line behaves the same (idle ~5 V, active-low pulses). So your firmware emits the **inverted**
logic of the raw modulated IR: where the remote sends a 38 kHz burst, you pull the tip LOW;
the gaps are released HIGH. Set this with an `INVERT` flag after scoping (§8).

### Ground — the one quirk that matters

**The jack sleeve is NOT grounded.** You must tie your board's ground to the player's ground
by another path:
- easiest: ensure an **RCA audio/video cable** runs between the player and the rest of the
  system (its shield provides the common ground), **or**
- run a dedicated **ground wire** from your board to the player chassis (a rear screw) or an
  RCA shell.
Without this, the open-collector pull has no return and the player may not respond.

### Power (deck-derived, no plugs — see FINAL DECISION banner)

The CONTROL IN as shipped is a **mono** jack (tip + floating sleeve) — it carries **no power**,
and the tip's ~5 V idle is only a weak ~100 kΩ pull-up (microamps), not a usable supply. So to
power the box from the deck (no plugs) you tap an **internal +5 V rail** and route it to the
box. Two ways:

**Option B — power pigtail through the grommet slot (recommended, least invasive).**
Open the deck, solder 2 wires (5 V + GND) to an internal +5 V logic rail, run them straight to
the box through the case grommet slot. Leave the factory mono CONTROL IN jack completely
untouched. Result: two leads to the box (signal jack + power pigtail). Fewest modifications,
fully reversible.

**Option A — put +5 V on the jack by upgrading it to STEREO (one cable to the box).**
Since you're inside anyway, replace/rewire CONTROL IN as a **3-conductor (TRS) jack** and:
- **tip → signal** (unchanged),
- **ring → internal +5 V** rail (new internal wire),
- **sleeve → GND** (new internal wire — Pioneer left the sleeve floating, so you must ground it).
Now one 3.5 mm stereo cable carries signal + 5 V + GND to the box, like the Revoxes' powered
DIN. Tidier at the box, but 3 internal solder joints (5 V tap, ground, jack) and you must take
care not to disturb the signal behaviour you characterised. Use a TRS cable/jack, not mono.

**Either way** (and unchanged by the choice): find an internal rail that can spare the ESP's
**~15 mA light-sleep average** (trivial) and **meter it once under load**. The reservoir cap
(FINAL DECISION banner) handles the Wi-Fi spikes so the rail only sees the average.

> The earlier "USB / PoE, no deck-5V question" note here is superseded by the no-plugs decision.

---

## 5. Firmware

Reuse the shared scaffolding (Ethernet/Wi-Fi + PubSubClient + MQTT command table). The
CLD-D925-specific part is the **emit routine**, which replays a captured **baseband** code by
toggling the open-collector pin — no carrier, unlike a normal IR LED.

```cpp
#include <ETH.h>   // or WiFi.h for the Wi-Fi option

const char* MQTT_HOST = "192.168.x.x";
const char* DEVICE_ID = "pioneer_cld_d925";

const int   PIN_SR   = 14;     // drives the open-collector stage onto CONTROL IN tip
const bool  SR_INVERT = true;  // baseband IR is active-low; confirm by scope

// A captured command = the remote's pulse/space timings (carrier stripped).
// Capture with an IR receiver/IRremote on the bench; store raw timings (us).
struct Cmd { const char* name; const uint16_t* timings; uint8_t len; };
// e.g. play_timings[] = {9000,4500, 560,560, 560,1690, ...}; // mark,space pairs (us)

// Emit one baseband frame on the open-collector pin.
// "mark" (would-be carrier burst) => pull LOW; "space" => release HIGH.
void emitSR(const uint16_t* t, uint8_t len) {
  for (uint8_t i = 0; i < len; i++) {
    bool mark = (i % 2 == 0);
    bool level = SR_INVERT ? !mark : mark;   // mark => LOW when SR_INVERT
    digitalWrite(PIN_SR, level ? HIGH : LOW);
    delayMicroseconds(t[i]);
  }
  digitalWrite(PIN_SR, SR_INVERT ? HIGH : LOW); // return to idle (released = high)
}
```

- Capture each remote button as raw mark/space timings (IRremote `rawData`, or an IR receiver
  + logic analyser). The Pioneer remote is almost certainly **NEC-family or Pioneer's own
  variant** — you don't need to *decode* it, just replay the raw timing, which is protocol-
  agnostic and exactly what SR wants.
- Some Pioneer commands need to be **sent twice / with the standard repeat frame** to register
  reliably — replicate the remote's repeat behaviour if a single shot is flaky.

### MQTT (Wirenboard convention) — identical to the other builds

- `/devices/pioneer_cld_d925/meta/name` = `Pioneer CLD-D925` (retained)
- per control `/controls/<name>/meta/type` = `pushbutton` (or `switch` for power)
- value `/controls/<name>` (retained), command `/controls/<name>/on` (subscribe)
- broker-direct to the Wirenboard Mosquitto broker.

---

## 6. Bill of materials

| Part | Qty | Notes |
|---|---|---|
| WT32-ETH01 (wired) **or** ESP32 WROOM-32 (Wi-Fi) | 1 | same board family as the Revox builds |
| 3.3 V USB-serial programmer | 1 | only if WT32-ETH01 (no onboard USB) |
| PC817 optocoupler **or** NPN (BC547/2N3904) | 1 | open-collector output stage |
| Resistor 1 kΩ | 1 | base/LED series |
| 3.5 mm **mono** plug + cable | 1 | into CONTROL IN |
| Ground wire / spare RCA lead | 1 | supply the missing ground (§4) |
| 5 V USB PSU | 1 | powers the box (no power on the jack) |
| Enclosure | 1 | metal OK if wired-Ethernet; plastic if Wi-Fi |

---

## 6a. Precise shopping list — Amazon.de

| # | Item | amazon.de search term | Qty | ~EUR | Notes |
|---|---|---|---|---|---|
| 1 | Board | `WT32-ETH01 ESP32 Ethernet Modul` (wired) or `ESP32 NodeMCU WROOM-32` (Wi-Fi) | 1 | 10–14 | match the Revox builds |
| 2 | USB-serial 3.3 V | `CP2102 USB UART 3,3V Programmer` | 0–1 | 5–7 | only for WT32-ETH01 |
| 3 | Optocoupler / transistor | `PC817 Optokoppler DIP` or `BC547 Transistor Sortiment` | 1 set | 6 | output stage |
| 4 | Resistor kit | `Widerstand Sortiment 1/4W` (incl. 1 kΩ) | 1 | 8 | |
| 5 | 3.5 mm mono plug + cable | `3,5mm Klinkenstecker mono Lötversion` + `3,5mm Klinkenkabel mono` | 1 | 5 | **mono**, not stereo |
| 6 | 5 V USB PSU | `USB Netzteil 5V 2A` + cable | 1 | 8 | powers the box |
| 7 | Enclosure | `Aluminium/Kunststoff Gehause 80x50x25` | 1 | 6–10 | metal OK if wired |
| 8 | Perfboard / jumpers / wire | `Lochrasterplatine Set`, `Jumper Dupont`, `Schaltlitze` | 1 each | 12 | prototyping + ground wire |

**Notes / gotchas:**
- Use a **mono** 3.5 mm plug (tip + sleeve). A stereo plug works if you only use tip + sleeve,
  but mono avoids confusion.
- Remember the **sleeve isn't ground** — plan the separate ground wire/RCA shield (§4).
- No exotic/scarce parts here (unlike the A77's WIST 10). This is the cheapest build.

---

## 7. Casing

- Wired Ethernet → metal OK. Wi-Fi → plastic. Small box behind the rack.
- The 3.5 mm signal lead to CONTROL IN + the deck +5 V power leads exit the box; strain-relieve. (No RJ45/USB — Wi-Fi + deck power.)
- Label the pigtail "SR CONTROL IN — tip=signal, separate GND".

---

## 8. Measurement / bring-up plan

1. **Scope CONTROL IN (deck powered):** confirm tip idles ~5 V; press a remote button AT the
   player and watch the tip — you should see active-low baseband pulses appear (the deck
   echoes nothing on IN, so instead scope CONTROL **OUT** if present, or scope the internal IR
   receiver output, to capture the baseband reference). Confirm sleeve is NOT at ground
   (meter sleeve→chassis: should NOT be 0 Ω).
2. **Capture remote codes:** with an IR receiver + IRremote/IRMP on the bench, record raw
   mark/space timings for each target button. (You're replaying timings, not decoding.)
3. **Bench the output stage:** drive a dummy 100 kΩ-pull-up-to-5V load, scope the pin, confirm
   you pull cleanly low and release high; set `SR_INVERT`.
4. **First live test:** plug into CONTROL IN, supply ground (RCA shield or wire), send **Play**.
   Then Pause/Stop/scan/skip. If a command is flaky, add the remote's **repeat frame** or send
   twice.
5. Map all working codes to MQTT controls; expose in Wirenboard.

---

## 9. Known facts / gotchas

- **Sleeve not grounded** — the #1 reason an SR control attempt "does nothing." Always supply
  ground separately.
- **Baseband, not modulated** — do NOT send a 38 kHz-modulated signal into CONTROL IN; SR
  wants the carrier already stripped. (If you ever drive an external IR LED instead, then you
  DO modulate — different output path.)
- **Active-low** — idle high (~5 V), assert low; handle with `SR_INVERT`.
- **One-way** — no status/feedback on this jack.
- **Protocol-agnostic** — SR repeats whatever remote it's fed, so you don't need to identify
  the exact Pioneer protocol; replay raw timings.
- **CONTROL OUT exists too** — if your unit has both IN and OUT, you could daisy-chain other
  Pioneer gear, but that's not needed here.

---

## 10. Relationship to the other builds

Shared: ESP32/WT32-ETH01 + Wirenboard MQTT scaffolding; broker-direct; "appears as native WB
device"; open-collector output philosophy.

Different: **wired IR (baseband) into a standard SR CONTROL IN jack** — no disassembly, no
protocol capture beyond recording the remote's raw timings, no device power tap (box is
deck-powered via internal +5 V tap), one-way (no status). **The simplest and lowest-cost of the four decks.**

---


## Reusing your existing Wirenboard IR-blaster codes (no re-capture needed)

You already have working IR codes for this deck in your Wirenboard IR blaster. **Those are the
same codes you need here** — reuse them directly; you can skip capturing from scratch.

Why they're identical: an IR command = **data** (protocol + command bits) riding on a **38 kHz
carrier** (only needed for the through-air hop). The blaster sends data+carrier through the air;
this build injects the **same data with the carrier stripped** (baseband) into the deck — and the
deck's IR receiver strips the carrier anyway, so the bits reaching the syscon are identical. You
are just delivering the same command one stage further downstream (over a wire), which is what
fixes the unreliable air path (especially the awkwardly-placed Panasonic).

How to reuse:
- **Export the codes from Wirenboard** — preferably the **decoded protocol + hex** (most robust;
  in firmware call the matching IRremote/IRMP *send* function with carrier set to 0/off). Raw
  mark/space timings work too (replay them on the open-collector pin, carrier off).
- **The only change vs a blaster: carrier OFF.** You're driving a logic line, not an IR LED — no
  38 kHz. Everything else (data, timing, repeat frames) is unchanged.
- **Repeat frames:** if a baseband command registers unreliably, replay it twice / include the
  protocol's repeat frame — the same behaviour your blaster already uses for held buttons.
- **Verify carrier-off** once on a scope (or by it simply working): a modulated signal fed into a
  baseband node may not decode.

This makes your proven, already-working codes the ground truth — better than fresh captures.

---

## 11. Source references

- **Pioneer CLD-D925 service manual** (cd/cdv/ld player) — available via ManualsLib /
  smpcshop; for the internal IR path if you ever choose demod-injection instead of the jack.
- **"Hacking Wired Remote Control Jacks Into A/V Equipment"** (wiredremotecontrol.blogspot.com,
  John Sevinsky): definitive SR analysis — 3.5 mm jacks, idle ~5 V, open-collector,
  CONTROL IN pull-up ~100 kΩ / OUT ~10 kΩ, **baseband copy of the IR signal**, repeats any
  remote, **sleeve not grounded** (supply ground via RCA shield), plugging in disables the
  internal IR sensor (RC-IX). Commenter "Rodders" confirms SR's intent: one IR injection point
  chained out→in across components.
- **Audiokarma / Steve Hoffman forums:** corroborate Pioneer "Control In/Out" jacks on LD/CD
  gear and using a Harmony/wired link in place of the original remote.
- Pioneer CU-series remotes (e.g. CU-CLD-family) are the original handsets to capture codes
  from if your CLD-D925 remote is missing.
