# Panasonic NV-FS90 → Wirenboard via added CONTROL IN jack — Build & Handoff

**Goal.** Control a Panasonic NV-FS90 S-VHS VCR from a Wirenboard PLC. The FS90 has
**no factory wired-control port** (AV1/AV2 SCART + IR only), so we **add one**: tap
the deck's internal IR-receiver output and bring it to a new rear 3.5 mm jack —
recreating the Pioneer "CONTROL IN" interface. An ESP32 then injects the FS90
remote's own codes as a **baseband (carrier-stripped) waveform**, replacing the
unreliable external IR blaster.

**Status.** Architecture confirmed (Panasonic VCR of this era: IR receiver module
→ baseband output → input port on syscon IC6001, a 5 V-logic Panasonic MN153xx
micro; front panel is a scanned key matrix — which is why we tap the IR output,
not the matrix). **Outstanding: a 60-second meter/scope check on YOUR unit to
identify the IR receiver's OUT pin** before soldering (§11). The exact pin is not
quoted from the manual on purpose — verify it on the board, don't trust a number
for something you solder to.

**Chosen approach: Option 2 — parallel tap, NO CUT.** Solder a wire onto the IR
receiver's output pin (sharing it with the existing syscon connection) and run it
to a rear jack. The internal IR receiver stays connected and live; your injected
open-collector signal simply wire-ORs with it. Fully reversible (remove the wire).
Trade-off: the internal IR sensor stays active, so a stray remote / strong ambient
IR can still reach the deck — accepted here.

**Once the jack exists, this is the SAME build as the Pioneer CLD-D925** —
identical output stage, firmware (`src/driver_ir.cpp`), and MQTT. See
[`wb-pioneer-cld-d925-esp32-bridge.md`](./wb-pioneer-cld-d925-esp32-bridge.md).

**Companion documents:**
[`wb-revoxb215-esp32-bridge.md`](./wb-revoxb215-esp32-bridge.md),
[`wb-revoxa77-esp32-bridge.md`](./wb-revoxa77-esp32-bridge.md),
[`wb-pioneer-cld-d925-esp32-bridge.md`](./wb-pioneer-cld-d925-esp32-bridge.md).

---

## 1. Design summary

All four ESP32 bridges share one canonical design — applied here to the NV-FS90:

- **Board:** ESP32 WROOM-32 (Wi-Fi), in a plastic enclosure with the PCB antenna
  near a case edge. No WT32-ETH01, no Ethernet, no RJ45.
- **Power: deck-derived only — no plugs, no USB, no PoE.** The NV-FS90 tap =
  **internal +5 V rail** (Pana­sonic NV-VP60 service manual confirms IC6001 pin 37
  is the 5 V rail — establishes 5 V-logic compatibility for this generation).
  Since you're already adding a rear jack for signal, the tidiest install is a
  **3-conductor TRS jack** carrying signal + 5 V + GND on the same cable — see §4.
  The 2-wire "pigtail through a separate hole" works too. Meter the chosen rail
  once under load to confirm headroom.
- **Wi-Fi runs in light-sleep** (DTIM-driven), avg ~15 mA, with commands still
  arriving instantly. Light-sleep + reservoir cap are a pair.
- **Reservoir cap network on the 5 V tap:**
  - **1000 µF low-ESR** across the 5 V tap,
  - **100 µF + 0.1 µF** decoupling at the board,
  - **2.2–10 Ω inrush resistor** in series with the big cap so the deck rail
    doesn't see the cap-fill surge at power-up.
- **OTA is mandatory.** First flash goes over a 3.3 V USB-serial header (the only
  time a cable touches the box); all subsequent updates ship over Wi-Fi via
  `esp_https_ota` with dual-OTA-partition rollback safety (see `partitions.csv`).

This is the single source of truth for the design; the sections below specify the
NV-FS90-specific hardware (parallel tap on the IR-receiver output, new rear jack,
BOM, bring-up) — they do not relitigate the design.

---

## 2. Why the FS90 needs a jack added (and why the IR-output tap is the right one)

- The NV-FS90 is a PAL S-VHS deck with **AV1/AV2 SCART + IR remote only**. There
  is **no edit/Control-S/wired-remote jack** (those were pro AG-series features,
  not this consumer deck). So unlike the Pioneer (which hands you CONTROL IN) and
  the Revoxes (documented remote ports), here you must **create** the wired input.
- Internally, the remote path is the universal arrangement: **IR receiver module
  → baseband logic-level output (idle-high, active-low) → an input port on the
  system-control micro IC6001** (a Panasonic MN153xx-family, 5 V logic —
  confirmed by the related NV-VP60 service manual, which flags IC6001 pin 37 as
  the 5 V rail).
- The **front panel is a scanned key matrix** (read by the syscon / a counter
  micro). Injecting into a scanned matrix is hard (you must hit the right
  row/column at the right scan instant). **Tapping the IR-receiver output is far
  easier and is the recommended path** — you feed the syscon exactly the
  baseband bytes it already understands, using the deck's own decoder.
- That IR-output node behaves **identically to the Pioneer CONTROL IN**: idle
  ~5 V, open-collector-ish, baseband (carrier already stripped), active-low. So
  adding a jack there = giving the FS90 its own Pioneer-style CONTROL IN.

---

## 3. Target command set

Capture each from the FS90 remote (or reuse the WB-blaster codes — §9); expose as
MQTT `pushbutton` controls (+ `switch` for power):

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

**No status read-back** (the IR path is one-way). If you ever want transport
status, that's a separate tap (e.g. an FIP/syscon line) — out of scope.

---

## 4. Creating the CONTROL IN jack (Option 2 — parallel tap, no cut)

### The principle

The IR receiver's OUT pin and the syscon input are both happy to share the line:
the receiver output is open-collector with a pull-up, and your ESP32 output stage
is also open-collector. Two open-collector drivers on one node simply **wire-OR**
— whoever pulls low wins, neither damages the other. So you **add** your wire in
parallel; you do **not** cut anything.

### Signal install

1. **Identify the IR-receiver OUT pin** (§11.1) — do this first, with power on.
2. With the deck **unplugged**, solder a thin wire to that OUT pin (or the
   nearest convenient pad on the same net).
3. Run the wire to a **rear-panel 3.5 mm jack** (drill a hole — rear panel area
   is fine to drill; pick a spot clear of internal boards/shields).
4. Use a **switched (closed-circuit) panel-mount 3.5 mm jack**: wire only
   tip+sleeve for injection now, leaving the internal receiver permanently
   connected. You get a clean panel connector now, and if you ever want to
   upgrade to a cut/auto-mute install you just move one wire to the switch
   contact — no redo.

```
IR receiver module (behind front window)
   Vcc (~5V)  ── leave (this is the 5 V rail — tap here for box power, §"Power tap")
   GND        ──────────────► new jack SLEEVE   (and deck chassis)
   OUT (baseband, active-low) ─┬─► existing trace to IC6001 input  (LEAVE CONNECTED)
                               └─► new jack TIP   (your injected signal, parallel tap)
```

### Power tap (per §1) — single-cable TRS option

Since you are **building this jack from scratch**, make it a **3-conductor (TRS)
jack** and carry power on it — exactly like the Pioneer stereo-jack option:
- **tip → IR-OUT net** (your injected baseband signal, parallel tap as above),
- **ring → internal +5 V rail** (the deck-power feed, instead of a separate
  pigtail — the IR receiver module's Vcc pin is a convenient tap point),
- **sleeve → GND** (deck chassis or the IR module's GND pin).

Then a single 3.5 mm stereo cable carries signal + 5 V + GND to the box. Apply
the §1 cap network at the box end (1000 µF + 2.2–10 Ω inrush + 100 µF + 0.1 µF).
**Meter the 5 V rail once under the bridge's load** before trusting it.

Pigtail-through-a-separate-hole works too (a second small grommet), but since
you're already drilling for the jack and the IR module gives you a clean 5 V tap
right there, the TRS install is tidier.

> NOTE — unlike the Pioneer (whose sleeve floats by design), here **you own this
> jack, so DO ground the sleeve** to the deck. That gives your ESP32 box a proper
> return without the "supply ground separately" quirk that the Pioneer install
> requires.

### Reversibility

Remove the tap wire and the jack; the deck is exactly stock. Nothing cut, nothing
rerouted.

### The accepted trade-off

Internal IR sensor stays live → a stray remote press or strong ambient IR can
still reach the deck. Fine for this install. (If it ever becomes a nuisance, the
switched jack lets you upgrade to a cut install later.)

---

## 5. Firmware notes

**Identical to the Pioneer build.** Both decks use the same IR-baseband driver
`src/driver_ir.cpp` behind the `DeviceDriver { begin, doCommand, poll }`
contract in `include/device_driver.h`. The shared core (Wi-Fi + light-sleep +
MQTT + identity + OTA + dispatch) lives in `src/main.cpp` / `wifi_setup.cpp` /
`wb_mqtt.cpp` / `identity.cpp` / `ota.cpp` — **no deck-specific code there.**

Driver responsibilities for Panasonic:
1. **Emit one baseband frame** per command — toggle the open-collector GPIO
   between LOW (asserted, would-be carrier burst) and HIGH (released, gap) for
   the captured mark/space timings (units = µs). No carrier; the IR module
   already stripped it.
2. **Polarity** — `SR_INVERT = true` for the FS90 (active-low; same as Pioneer).
3. **Protocol family.** The FS90 remote is the Panasonic IR protocol
   (Kaseikyo / "Panasonic" 48-bit family is typical). You **don't need to
   decode it** — capture and replay the raw timings. Panasonic frames often
   expect the **standard repeat/spacing**; if a single shot is flaky, replay
   the remote's repeat behaviour or send twice.
4. **Record safety:** gate `record` behind a confirm/arm MQTT topic — same as
   the Revox builds.
5. **Timing.** Use `esp_rom_delay_us()` (IDF); for very tight timing guard with
   `portDISABLE_INTERRUPTS()` / `portENABLE_INTERRUPTS()`.

For Panasonic codes specifically, see §9 (reuse the WB-blaster codes — no fresh
capture needed).

---

## 6. MQTT (Wirenboard convention)

Same convention as the other three bridges:

| Topic | Direction | Retained | Purpose |
|---|---|---|---|
| `/devices/<id>/meta/name` | publish | yes | device display name |
| `/devices/<id>/controls/<c>/meta/type` | publish | yes | `pushbutton` (or `switch` for power) |
| `/devices/<id>/controls/<c>` | publish | yes | current state |
| `/devices/<id>/controls/<c>/on` | **subscribe** | — | command in |

`<id>` here = `panasonic_nv_fs90`. Broker-direct to the WB Mosquitto broker over
Wi-Fi.

---

## 7. Bill of materials

| Part | Qty | Notes |
|---|---|---|
| ESP32 WROOM-32 dev board (Wi-Fi) | 1 | onboard USB-serial; PCB antenna |
| PC817 optocoupler *or* NPN (BC547/2N3904) | 1 | open-collector output stage |
| Resistor 1 kΩ | 1 | base/LED series |
| Resistor 2.2–10 Ω | 1 | inrush limiter on the 5 V tap (§1) |
| Capacitor 1000 µF low-ESR | 1 | reservoir on the 5 V tap (§1) |
| Capacitor 100 µF | 1 | decoupling at board |
| Capacitor 0.1 µF | 1 | decoupling at board |
| **Switched (closed-circuit) 3.5 mm panel-mount jack** | 1 | the new rear CONTROL IN |
| 3.5 mm **stereo TRS** cable | 1 | box ↔ jack (3 conductors for sig+5V+GND) |
| Thin hook-up wire (tap) | — | to the IR-OUT pin and to the +5 V tap |
| Plastic enclosure (~80×50×25 mm) | 1 | Wi-Fi antenna must NOT be inside metal — `cases/` v5 |

---

## 8. Shopping list — Amazon.de

| # | Item | amazon.de search term | Qty | ~EUR | Notes |
|---|---|---|---|---|---|
| 1 | ESP32 WROOM-32 dev board | `ESP32 NodeMCU WROOM-32` (3-pack) | 1 set | 18–22 | onboard USB-serial; pick PCB-antenna variant |
| 2 | Optocoupler / transistor | `PC817 Optokoppler DIP` or `BC547 Sortiment` | 1 set | 6 | output stage |
| 3 | Resistor kit | `Widerstand Sortiment 1/4W` (incl. 1 kΩ, 2.2–10 Ω) | 1 | 8 | |
| 4 | Reservoir cap 1000 µF low-ESR | `Elektrolytkondensator 1000uF 16V Low ESR` | 2 | 5 | the cap is load-bearing |
| 5 | Decoupling caps | `Elektrolytkondensator 100uF 16V` + `Keramikkondensator 100nF Sortiment` | a few | 5 | at-board decoupling |
| 6 | Panel-mount switched 3.5 mm jack | `3,5mm Klinkenbuchse Einbau schaltend` | 2 | 5 | the new rear jack (buy a spare) |
| 7 | 3.5 mm stereo TRS cable | `3,5mm Klinkenkabel stereo` | 1 | 4 | box ↔ jack — needs 3 conductors for sig+5V+GND |
| 8 | Plastic enclosure | `Kunststoffgehäuse ABS 80x50x25` | 1 | 6–10 | **must be non-metal** (Wi-Fi antenna) |
| 9 | Perfboard / jumpers / wire | `Lochrasterplatine`, `Jumper Dupont`, `Schaltlitze` | 1 each | 12 | prototyping + tap wires |

**Notes / gotchas:**
- No scarce parts (cheapest build alongside the Pioneer).
- Get a panel-mount **switched** jack so you retain the option to upgrade to a
  "cut" install later.
- Use a **stereo** cable (item 7) — you carry signal + 5 V + GND on three
  conductors via the TRS jack (§4). A mono cable can't do that.
- Reservoir cap (item 4): proper **low-ESR** electrolytic, not a generic.
- A small step drill (Stufenbohrer) makes a clean hole in the rear panel.

---

## 9. Reusing your existing Wirenboard IR-blaster codes (no re-capture needed)

You already have working IR codes for this deck in your Wirenboard IR blaster.
**Those are the same codes you need here** — reuse them directly; you can skip
capturing from scratch.

Why they're identical: an IR command = **data** (protocol + command bits) riding
on a **38 kHz carrier** (only needed for the through-air hop). The blaster sends
data+carrier through the air; this build injects the **same data with the carrier
stripped** (baseband) into the deck — and the deck's IR receiver strips the
carrier anyway, so the bits reaching the syscon are identical. You are just
delivering the same command one stage further downstream (over a wire), which is
what fixes the unreliable air path (especially the awkwardly-placed Panasonic).

How to reuse:
- **Export the codes from Wirenboard** — preferably the **decoded protocol + hex**
  (most robust; in firmware call the matching `ir_emit_*()` helper in
  `driver_ir.cpp` with carrier set to 0/off). Raw mark/space timings work too
  (replay them on the open-collector pin, carrier off).
- **The only change vs a blaster: carrier OFF.** You're driving a logic line, not
  an IR LED — no 38 kHz.
- **Repeat frames:** if a baseband command registers unreliably, replay it twice
  / include the protocol's repeat frame — the same behaviour your blaster
  already uses for held buttons.
- **Verify carrier-off** once on a scope (or by it simply working): a modulated
  signal fed into a baseband node may not decode.

This makes your proven, already-working codes the ground truth — better than
fresh captures.

---

## 10. Casing & mounting

- Plastic enclosure (ABS/PETG). Wi-Fi antenna must not be inside metal. Box lives
  behind the rack.
- ESP32 WROOM-32 with the **PCB antenna pointing toward a case edge**.
- The new jack lives on the FS90's rear panel; a short 3.5 mm **stereo** cable
  links it to your box.
- Drill the rear-panel hole in a clear area (avoid internal board edges, shields,
  the PSU, and the deck mechanism). Deburr; add a drop of hot glue as strain
  relief on the internal tap wires.
- See `cases/` for the v5 STL files.

---

## 11. Bring-up sequence

### 11.1 Identify the IR-receiver OUT pin (do FIRST, before soldering)

1. Power the deck. Locate the **3-pin IR receiver module** behind the front IR
   window (service manual — HiFi Engine / elektrotanya — helps locate it on the
   board).
2. With a meter: one pin = **GND** (0 V), one = **Vcc** (~5 V steady). The third
   is **OUT**. Note the Vcc pin too — that's your +5 V tap point for the box.
3. Confirm OUT: it idles **near 5 V**; on a remote press, a meter on **AC volts**
   twitches, and a scope shows clean **active-low** baseband pulses (no 38 kHz
   carrier — the module already stripped it). That is your tap pin and confirms
   `SR_INVERT`.

### 11.2 Capture (or import) remote codes

See §9 — reuse the WB-blaster codes. Otherwise: IR receiver + IRremote/IRMP on
the bench, record **raw mark/space timings** for each target button (you replay
timings, not decode).

### 11.3 Bench the output stage

Drive a dummy load (pull-up to 5 V); scope the pin; confirm clean pull-low /
release-high.

### 11.4 Install & first live test

1. Deck unplugged: solder the parallel signal tap to OUT and the power tap to
   Vcc; fit the switched rear jack (tip → OUT net, ring → +5 V, sleeve → deck
   GND). Leave the internal receiver connected.
2. Power up; confirm the deck **still responds to its own remote** (proves the
   parallel tap didn't disturb the node).
3. **First flash** the WROOM-32 over USB-serial; confirm Wi-Fi associates and
   MQTT topics appear in WB.
4. **Meter the +5 V tap rail** under the bridge's load (cap network in place) —
   confirm no sag.
5. Plug in the ESP32 box; send **Play**. Then Stop/Pause/FF/Rewind; **Record
   last** (gated). If flaky, add the Panasonic repeat frame or send twice.
6. Map all working codes to MQTT controls; expose in Wirenboard.

---

## 12. Open items

Paste this file back and say "continue the Panasonic NV-FS90 build."

1. **Identify the IR-receiver OUT pin** on your board (§11.1) — the 3-pin module
   behind the IR window.
2. **Solder the parallel tap + the +5 V tap; fit the rear TRS jack** (§4).
3. **First live test** with WB-blaster codes (§9) per the §11 sequence.

---

## 13. Known facts / gotchas

- **No cut (Option 2):** internal IR sensor stays live — stray/ambient IR can
  still reach the deck. Accepted trade-off; switched jack lets you upgrade to a
  cut/auto-mute install later.
- **Verify the OUT pin on your board** — don't trust a quoted pin number for a
  solder point.
- **Baseband, active-low** — feed carrier-stripped, idle-high/assert-low signal,
  like the Pioneer. Do NOT send a 38 kHz-modulated waveform into this node.
- **Ground the jack sleeve to the deck** here (unlike Pioneer, you own this
  jack) for a clean return.
- **5 V logic** (IC6001 family) — your open-collector pull-low is fully
  compatible; never drive the node hard high, just pull low and release.
- **Front-panel matrix is NOT the tap** — that path is the hard one; the IR-OUT
  node is the easy one and is what this doc uses.

---

## 14. Source references

- **NV-FS90 service manual** (HiFi Engine, elektrotanya, eserviceinfo): locates
  the IR receiver module and syscon on the board. (Connection docs confirm
  AV1/AV2 SCART + IR only — no wired remote port.)
- **Panasonic NV-VP60 service manual:** confirms this generation's syscon is
  **IC6001 (MN153xx-family)** with a **5 V rail (pin 37)** — establishes 5 V
  logic compatibility.
- **Panasonic AG-500 service manual:** documents the standard Panasonic VCR
  control architecture — **scanned key matrix** read by syscon/counter micros —
  confirming the matrix is the hard path and the IR-output tap is the easy one.
- **"Hacking Wired Remote Control Jacks Into A/V Equipment"**
  (wiredremotecontrol.blogspot.com): the canonical recipe for adding a CONTROL-
  IN jack to a VCR by tapping the IR-receiver output (Mitsubishi VCR: series
  switched jack; JVC: parallel no-cut tap onto the sensor output) — Option 2
  here follows the JVC parallel approach. IR-receiver output is open-collector,
  idle-high, baseband.
- **Pioneer SR analysis** (same blog): the CONTROL-IN electrical model (idle
  ~5 V, baseband, active-low) this jack recreates — see the Pioneer CLD-D925 doc.

---

## 15. Relationship to the other builds

Shared: ESP32 WROOM-32 + canonical design (§1); WB MQTT scaffolding; broker-
direct; open-collector baseband output; **firmware and output stage identical to
the Pioneer CLD-D925** once the jack exists (`src/driver_ir.cpp`).

Different: the FS90 has **no factory wired port**, so you **add a Pioneer-style
CONTROL IN** by a **parallel (no-cut) tap on the internal IR-receiver output**
brought to a drilled-in rear TRS jack — and you ground the sleeve to the deck
(unlike Pioneer, you own this jack). The only device of the four requiring
opening the unit and soldering to an internal node — but a single signal wire +
a single 5 V tap wire, reversible, and it cures the IR-blaster reliability
problem.
