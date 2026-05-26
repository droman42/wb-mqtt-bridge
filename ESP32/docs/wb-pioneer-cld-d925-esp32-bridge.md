# Pioneer CLD-D925 → Wirenboard via CONTROL IN (Pioneer SR) — Build & Handoff

**Goal.** Control a Pioneer CLD-D925 LaserDisc/CD player from a Wirenboard PLC by
feeding the player's rear **CONTROL IN** (Pioneer "SR" / System Remote) minijack
with a small ESP32 that publishes/subscribes **Wirenboard-conformant MQTT**. The
unreliable external IR blaster is replaced by a clean wired connection. **This is
the easiest of the four-deck set** — no opening the unit to inject signal, no
protocol reverse-engineering.

**Status.** CONTROL IN electrical interface and protocol CONFIRMED from a detailed
reverse-engineering writeup (idle ~5 V, open-collector, ~100 kΩ pull-up, baseband
IR copy, sleeve NOT grounded, plugging in disables internal IR). Outstanding:
confirm idle/polarity on your unit with a scope; capture (or reuse — §9) the
remote's codes. See §11.

**Companion documents:**
[`wb-revoxb215-esp32-bridge.md`](./wb-revoxb215-esp32-bridge.md),
[`wb-revoxa77-esp32-bridge.md`](./wb-revoxa77-esp32-bridge.md),
[`wb-panasonic-nv-fs90-esp32-bridge.md`](./wb-panasonic-nv-fs90-esp32-bridge.md).
Shared design + firmware scaffolding; this doc details what's CLD-D925-specific.

---

## 1. Design summary

All four ESP32 bridges share one canonical design — applied here to the CLD-D925:

- **Board:** ESP32 WROOM-32 (Wi-Fi), in a plastic enclosure with the PCB antenna
  near a case edge. No WT32-ETH01, no Ethernet, no RJ45.
- **Power: deck-derived only — no plugs, no USB, no PoE.** The CONTROL IN jack
  itself carries no usable supply (it's a mono jack with a weak ~100 kΩ pull-up).
  So the CLD-D925 tap = **internal +5 V rail**, either as a **pigtail through the
  case grommet** or carried on a **3-conductor stereo CONTROL IN jack** (ring =
  +5 V) — see §4 Power. Meter the chosen rail once under load to confirm headroom.
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
CLD-D925-specific hardware (signal injection on the SR tip, ground quirk, BOM,
bring-up) — they do not relitigate the design.

---

## 2. How Pioneer SR "CONTROL IN" works (CONFIRMED)

Pioneer's **SR (System Remote)** is, in effect, **a wired IR repeater built into
the gear**. A controlling unit's CONTROL OUT carries the **demodulated (carrier-
stripped) version of whatever IR its receiver saw**, and a controlled unit's
CONTROL IN accepts that same baseband signal *instead of* its built-in IR sensor.
Confirmed electrical facts (from scope analysis of Pioneer SR jacks):

- **Connector:** 3.5 mm **mono** jack (tip = signal, sleeve = "ground" — but see
  the ground quirk in §4).
- **Idle level:** tip sits at about **+5 V** when idle.
- **Output/Input type:** **open-collector with an internal pull-up** — like a
  Sharp/Vishay IR receiver module's output. The CONTROL IN internal pull-up
  measured ~**100 kΩ** (CONTROL OUT ~10 kΩ). You **pull the tip low** to signal;
  release to let it return high.
- **Protocol:** the tip signal is a **baseband (no 38 kHz carrier) copy of the IR
  remote waveform**. Scope comparison showed the CONTROL OUT tip and a
  demodulating IR receiver's output carrying the *identical* signal. It also
  repeats **any** remote's codes, not just Pioneer's — i.e. it's protocol-agnostic
  at the waveform level.
- **Plugging in disables the internal IR sensor** (Pioneer's jack behaves as
  "RC-IX": Input + disables-internal-receiver). Good — no double-triggering.
- **The sleeve is NOT grounded.** Pioneer deliberately floats the ring/sleeve
  (avoids ground loops between chained units). **You must provide a ground
  reference separately** (§4).

**Net:** to control the CLD-D925, drive its CONTROL IN tip with the **carrier-
stripped bitstream of its own remote codes**, pulling low (open-collector),
referenced to a ground you supply. No carrier generation needed — that's the
whole point of SR.

---

## 3. Target command set

The CLD-D925 is a LaserDisc/CD/CDV player; useful controls (capture each from the
remote, or reuse the WB-blaster codes per §9):

| Function | Notes |
|---|---|
| Power (on/off) | confirm whether discrete on/off or a toggle on the remote |
| Play | |
| Pause / Still | |
| Stop | |
| Scan / Search +/- | fast forward/reverse |
| Chapter / Track +/- | skip |
| Display / On-screen | optional |
| Open/Close (eject) | optional |
| Side change | LaserDisc-specific; confirm if remote exposes it |

MQTT controls of type `pushbutton`, plus optionally a `switch` for power. **No
status read-back** (SR CONTROL IN is one-way; the player gives no feedback on
this jack — unlike the B215's serial link). If status ever matters, that's a
separate tap, out of scope here.

---

## 4. Wiring

### Signal — open-collector drive onto the tip

```
ESP32 GPIOxx ──[1 kΩ]──► PC817 LED ──► ESP32 GND
PC817 transistor collector ──► 3.5 mm TIP   (→ CONTROL IN tip)
PC817 transistor emitter   ──► ground reference   (see "Ground quirk" below)
```

The CONTROL IN already has its own ~100 kΩ pull-up to ~5 V. You only need to
**pull the tip low**. The optocoupler keeps the ESP's ground separate from the
deck's floating reference (tidy, and avoids surprises since the sleeve isn't a
real ground). A bare NPN (BC547 / 2N3904) works too if you'd rather skip the opto.

**Polarity (carrier-stripped IR is active-low here).** A demodulating IR receiver
idles **high** and pulses **low** during bursts. The SR CONTROL line behaves the
same (idle ~5 V, active-low pulses). So firmware emits the **inverted** logic of
the raw modulated IR: where the remote sends a 38 kHz burst, you pull the tip
LOW; the gaps are released HIGH. Set this with `SR_INVERT` in `driver_ir.cpp`
after scoping (§10).

### Ground quirk — the one thing that matters

**The jack sleeve is NOT grounded.** You must tie your board's ground to the
player's ground by another path:
- easiest: ensure an **RCA audio/video cable** runs between the player and the
  rest of the system (its shield provides the common ground), **or**
- run a dedicated **ground wire** from your board to the player chassis (a rear
  screw) or an RCA shell.
Without this, the open-collector pull has no return and the player may not
respond. This is the #1 reason an SR control attempt "does nothing."

### Power tap (per §1)

The CONTROL IN jack carries **no usable supply** (tip's ~5 V idle is just the
weak ~100 kΩ pull-up, microamps). So tap an **internal +5 V rail** and route it
to the box. Two install styles — pick one:

**Option B — power pigtail through the grommet slot (recommended, least invasive).**
Open the deck, solder 2 wires (5 V + GND) to an internal +5 V logic rail, run them
straight to the box through the case grommet slot. Leave the factory mono CONTROL
IN jack completely untouched. Result: two leads to the box (signal jack + power
pigtail). Fewest modifications, fully reversible.

**Option A — put +5 V on the jack by upgrading it to STEREO (one cable to the box).**
Since you're inside anyway, replace/rewire CONTROL IN as a **3-conductor (TRS)
jack** and:
- **tip → signal** (unchanged),
- **ring → internal +5 V** rail (new internal wire),
- **sleeve → GND** (new internal wire — Pioneer left the sleeve floating, so you
  must ground it here).
Now one 3.5 mm stereo cable carries signal + 5 V + GND to the box, like the
Revoxes' powered DIN. Tidier at the box, but 3 internal solder joints (5 V tap,
ground, jack) and you must take care not to disturb the signal behaviour. Use a
TRS cable/jack, not mono.

**Either way:** apply the §1 cap network at the box end (1000 µF + 2.2–10 Ω
inrush + 100 µF + 0.1 µF) and **meter the tap rail once under the bridge's load**
to confirm it doesn't sag.

### Topology summary

```
ESP32 WROOM-32 (Wi-Fi)
   GPIOxx ──► open-collector stage ──► 3.5 mm TIP        → CONTROL IN tip
   GND    ─────────────────────────► ground reference    → RCA shield, chassis screw,
                                                            or TRS sleeve (Option A)
   5V     ◄── deck internal +5 V tap (via §1 cap network) → pigtail or TRS ring
```

---

## 5. Firmware notes

The shared core (Wi-Fi + light-sleep + MQTT + identity + OTA + dispatch) lives in
`src/main.cpp` / `wifi_setup.cpp` / `wb_mqtt.cpp` / `identity.cpp` / `ota.cpp` —
**no deck-specific code there.** The IR-baseband driver shared between Pioneer and
Panasonic is `src/driver_ir.cpp` behind the `DeviceDriver { begin, doCommand, poll }`
contract in `include/device_driver.h`.

Driver responsibilities for Pioneer:
1. **Emit one baseband frame** per command — toggle the open-collector GPIO
   between LOW (asserted, would-be carrier burst) and HIGH (released, gap) for
   the captured mark/space timings (units = µs). No carrier generation; the deck
   already has the carrier stripped.
2. **Polarity** — `SR_INVERT = true` for the CLD-D925 (active-low SR signal,
   like a demodulating IR receiver's output).
3. **Repeat behaviour** — some Pioneer commands need the standard repeat frame or
   a double-send to register reliably; replicate the remote's repeat behaviour
   if a single shot is flaky.
4. **Timing.** Use `esp_rom_delay_us()` (IDF, microsecond busy-wait); for very
   tight timing guard with `portDISABLE_INTERRUPTS()` / `portENABLE_INTERRUPTS()`.

A captured command = the remote's pulse/space timings (carrier stripped). Capture
with an IR receiver on the bench, store raw timings (µs) per command in
`src/driver_ir.cpp`. For Pioneer codes specifically, see §9 (reuse the WB-blaster
codes — no fresh capture needed).

---

## 6. MQTT (Wirenboard convention)

Same convention as the other three bridges:

| Topic | Direction | Retained | Purpose |
|---|---|---|---|
| `/devices/<id>/meta/name` | publish | yes | device display name |
| `/devices/<id>/controls/<c>/meta/type` | publish | yes | `pushbutton` (or `switch` for power) |
| `/devices/<id>/controls/<c>` | publish | yes | current state |
| `/devices/<id>/controls/<c>/on` | **subscribe** | — | command in |

`<id>` here = `pioneer_cld_d925`. Broker-direct to the WB Mosquitto broker over
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
| 3.5 mm mono plug + cable | 1 | into CONTROL IN (or stereo TRS for Option A) |
| Ground wire / spare RCA lead | 1 | supply the missing ground (§4) — unless using Option A TRS |
| Plastic enclosure (~80×50×25 mm) | 1 | Wi-Fi antenna must NOT be inside metal — `cases/` v5 |

---

## 8. Shopping list — Amazon.de

| # | Item | amazon.de search term | Qty | ~EUR | Notes |
|---|---|---|---|---|---|
| 1 | ESP32 WROOM-32 dev board | `ESP32 NodeMCU WROOM-32` (3-pack) | 1 set | 18–22 | onboard USB-serial; pick PCB-antenna variant |
| 2 | Optocoupler / transistor | `PC817 Optokoppler DIP` or `BC547 Transistor Sortiment` | 1 set | 6 | output stage |
| 3 | Resistor kit | `Widerstand Sortiment 1/4W` (incl. 1 kΩ, 2.2–10 Ω) | 1 | 8 | |
| 4 | Reservoir cap 1000 µF low-ESR | `Elektrolytkondensator 1000uF 16V Low ESR` | 2 | 5 | the cap is load-bearing |
| 5 | Decoupling caps | `Elektrolytkondensator 100uF 16V` + `Keramikkondensator 100nF Sortiment` | a few | 5 | at-board decoupling |
| 6 | 3.5 mm plug + cable | `3,5mm Klinkenstecker mono Lötversion` + `3,5mm Klinkenkabel mono` (or TRS for Option A) | 1 | 5 | mono = Option B; TRS = Option A |
| 7 | Plastic enclosure | `Kunststoffgehäuse ABS 80x50x25` | 1 | 6–10 | **must be non-metal** (Wi-Fi antenna) |
| 8 | Perfboard / jumpers / wire | `Lochrasterplatine Set`, `Jumper Dupont`, `Schaltlitze` | 1 each | 12 | prototyping + ground wire |

**Notes / gotchas:**
- For **Option A** (TRS jack on the deck side), use a **stereo** plug + cable, not
  mono. For **Option B** (pigtail), use a **mono** 3.5 mm plug — sleeve is
  signal-ground reference if you tie it that way, but the actual GND return is
  via the pigtail or RCA shield.
- Remember the **sleeve isn't ground on a stock CONTROL IN** — plan the separate
  ground wire / RCA shield (§4), unless you've gone Option A.
- Reservoir cap (item 4): proper **low-ESR** electrolytic, not a generic. ESR
  matters for soaking up Wi-Fi TX-current spikes.
- No exotic/scarce parts here (unlike the A77's WIST 10). Tied with the Panasonic
  for cheapest build.

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
what fixes the unreliable air path.

How to reuse:
- **Export the codes from Wirenboard** — preferably the **decoded protocol + hex**
  (most robust; in firmware call the matching `ir_emit_*()` helper in
  `driver_ir.cpp` with carrier set to 0/off). Raw mark/space timings work too
  (replay them on the open-collector pin, carrier off).
- **The only change vs a blaster: carrier OFF.** You're driving a logic line, not
  an IR LED — no 38 kHz. Everything else (data, timing, repeat frames) is
  unchanged.
- **Repeat frames:** if a baseband command registers unreliably, replay it twice /
  include the protocol's repeat frame — the same behaviour your blaster already
  uses for held buttons.
- **Verify carrier-off** once on a scope (or by it simply working): a modulated
  signal fed into a baseband node may not decode.

This makes your proven, already-working codes the ground truth — better than
fresh captures.

---

## 10. Casing

- Plastic enclosure (ABS/PETG). Wi-Fi antenna must not be inside metal.
- ESP32 WROOM-32 with the **PCB antenna pointing toward a case edge**.
- The 3.5 mm signal lead to CONTROL IN + the deck +5 V power leads exit the box;
  strain-relieve.
- Label the pigtail/cable: "SR CONTROL IN — tip=signal, GND via RCA shield" (or
  "TRS: tip=sig, ring=+5V, sleeve=GND" for Option A).
- See `cases/` for the v5 STL files.

---

## 11. Bring-up sequence

1. **Scope CONTROL IN (deck powered):** confirm tip idles ~5 V; press a remote
   button AT the player and watch the tip — you should see active-low baseband
   pulses appear (the deck echoes nothing on IN, so instead scope CONTROL **OUT**
   if present, or scope the internal IR receiver output, to capture the baseband
   reference). Confirm sleeve is NOT at ground (meter sleeve → chassis: should
   NOT be 0 Ω).
2. **Capture (or import) remote codes** — see §9; reuse the WB-blaster codes.
3. **Bench the output stage:** drive a dummy 100 kΩ-pull-up-to-5 V load, scope
   the pin, confirm clean pull-low / release-high; set `SR_INVERT`.
4. **Tap and meter the internal +5 V rail** under the bridge's load (light-sleep
   + cap network in place) — confirm no sag.
5. **First flash** the WROOM-32 over USB-serial; confirm Wi-Fi associates and
   MQTT topics appear in WB.
6. **First live test:** plug into CONTROL IN, supply ground (RCA shield or wire,
   or via Option A TRS sleeve), send **Play**. Then Pause/Stop/scan/skip. If a
   command is flaky, add the remote's **repeat frame** or send twice.
7. Map all working codes to MQTT controls; expose in Wirenboard.

---

## 12. Open items

Paste this file back and say "continue the Pioneer CLD-D925 build."

1. **Scope the CONTROL IN jack** on your unit: confirm ~5 V idle on tip, that a
   remote press produces active-low baseband pulses, and that the sleeve is NOT
   grounded (§11).
2. **Decide control scope** (Play/Pause/Stop/Chapter±/Scan±/Display/Power, etc.)
   and map to MQTT controls (§3).
3. **Decide Option A vs B** for power routing (§4) before opening the deck.

---

## 13. Source references

- **Pioneer CLD-D925 service manual** (CD/CDV/LD player) — available via
  ManualsLib / smpcshop; for the internal IR path if you ever choose demod-
  injection instead of the jack.
- **"Hacking Wired Remote Control Jacks Into A/V Equipment"**
  (wiredremotecontrol.blogspot.com, John Sevinsky): definitive SR analysis —
  3.5 mm jacks, idle ~5 V, open-collector, CONTROL IN pull-up ~100 kΩ /
  OUT ~10 kΩ, **baseband copy of the IR signal**, repeats any remote, **sleeve
  not grounded** (supply ground via RCA shield), plugging in disables the
  internal IR sensor (RC-IX). Commenter "Rodders" confirms SR's intent: one IR
  injection point chained out → in across components.
- **Audiokarma / Steve Hoffman forums:** corroborate Pioneer "Control In/Out"
  jacks on LD/CD gear and using a Harmony/wired link in place of the original
  remote.
- Pioneer CU-series remotes (e.g. CU-CLD-family) are the original handsets to
  capture codes from if your CLD-D925 remote is missing.

---

## 14. Relationship to the other builds

Shared: ESP32 WROOM-32 + canonical design (§1); WB MQTT scaffolding; broker-
direct; "appears as native WB device"; open-collector output philosophy; IR-
baseband driver shared with the Panasonic build (`src/driver_ir.cpp`).

Different: **wired IR (baseband) into a factory SR CONTROL IN jack** — no
protocol capture beyond importing the remote's raw timings (or reusing WB-blaster
codes — §9), one-way (no status), and a power-tap routing choice (pigtail vs TRS
jack — §4). **The simplest and lowest-cost of the four decks.**
