# Revox A77 MK4 → Wirenboard via REMOTE CONTROL DIN — Build & Handoff

**Goal.** Control a Revox A77 MK4 reel-to-reel from a Wirenboard PLC using a small
ESP32 that emulates the A77's momentary **remote-control contacts**, publishing
**Wirenboard-conformant MQTT**. Plus a **firmware rewind-safety interlock** that
prevents engaging Play until the reels have stopped. Fully external/reversible —
no cutting into the deck's vintage logic.

**Status.** Pinout, contact logic, dummy-plug bridge and power pin CONFIRMED from
the A77 service manual (10.18.1611, §7.1 Fig. 7.1-86 and §5.9 Table 5.9-44).
Outstanding: pick the reel-motion sensor and tune the interlock constants on the
bench (§11). Do a 30-second continuity check of the socket before connecting, but
the schematic is authoritative.

**Companion documents** (the four-transport ESP32-bridge family — shared design,
shared firmware scaffolding; this doc only details what's different for the A77):
[`wb-revoxb215-esp32-bridge.md`](./wb-revoxb215-esp32-bridge.md) (Revox B215 tape),
[`wb-pioneer-cld-d925-esp32-bridge.md`](./wb-pioneer-cld-d925-esp32-bridge.md) (Pioneer LD),
[`wb-panasonic-nv-fs90-esp32-bridge.md`](./wb-panasonic-nv-fs90-esp32-bridge.md) (Panasonic VHS).

---

## 1. Design summary

All four ESP32 bridges share one canonical design — applied here to the A77:

- **Board:** ESP32 WROOM-32 (Wi-Fi), in a plastic enclosure with the PCB antenna
  near a case edge. No WT32-ETH01, no Ethernet, no RJ45.
- **Power: deck-derived only — no plugs, no USB, no PoE.** A77 tap = **REMOTE
  CONTROL pin 7 (+27 V)** → **switching buck → 5 V**. The 27 V × 150 mA ≈ 4 W
  budget gives huge headroom for Wi-Fi after the buck; the buck output is the
  reservoir node (caps live there).
- **Wi-Fi runs in light-sleep** (DTIM-driven), avg ~15 mA, with commands still
  arriving instantly. Light-sleep + reservoir cap are a pair.
- **Reservoir cap network at the buck output (5 V):**
  - **1000 µF low-ESR** across the 5 V rail,
  - **100 µF + 0.1 µF** decoupling at the board,
  - **2.2–10 Ω inrush resistor** in series with the big cap so the buck doesn't
    see the cap-fill surge at power-up.
- **Fuse the pin-7 tap** with a 100–200 mA fuse — the deck rail is rated 150 mA;
  a fault upstream of the buck must not be able to overdraw it.
- **OTA is mandatory.** First flash goes over a 3.3 V USB-serial header (the only
  time a cable touches the box); all subsequent updates ship over Wi-Fi via
  `esp_https_ota` with dual-OTA-partition rollback safety (see `partitions.csv`).

This is the single source of truth for the design; the sections below specify the
A77-specific hardware (pin map, contact emulation, motion sensor, interlock, BOM,
bring-up) — they do not relitigate the design.

---

## 2. How the A77 remote actually works (CONFIRMED from manual §7.1 + §5.9)

- The A77 (late-60s/70s) has **no microcontroller, no IR, no serial bus**. The
  transport is **relay logic**: 3 relays (A, B, C) + a Record Relay + roller/brake
  solenoids (manual §5.9). The deck was explicitly designed for momentary-contact
  wired remote of all functions.
- The rear connector is a **Hirschmann WIST 10 (10-pin DIN)**, labelled REMOTE
  CONTROL (rear-panel item 25). The original remote is just a box of momentary
  buttons that **parallel the front-panel switches** — the manual states
  remote-control contacts **F3...F10** are simply paralleled onto the deck's own
  button contacts, and "to have a minimum of relays, their control is locked by
  diodes."
- **Each button connects a PAIR of connector pins** (a simple SPST closure between
  two pins, not a switch to a single common rail). See the exact pairs in §4.
- **Dummy plug:** the manual says verbatim that the dummy connector **"must be
  inserted for operation without the REMOTE CONTROL unit"** and that it **shorts
  terminals 1 & 2** (the STOP pair). Keep that bridge present in your adapter.
- **Switches are momentary / non-latching**, both on the machine and the remote.
- **Pin 7 (vio) = +27 Vdc out**, intended for slide projectors, **150 mA max**.
  This is the only power available on the connector — **27 V, not 5 V**. It powers
  the bridge via a buck converter (§4); never feed 27 V to an ESP32 directly.
- **REC interlock — confirmed by the relay truth table (Table 5.9-44):** REC
  energizes **relays A *and* B plus the Record Relay**. Relay A is the PLAY
  relay. So **Record depends on the PLAY path**; in the remote wiring REC is
  steered via diodes so pressing REC alone does nothing. **Net: Record requires
  PLAY + REC asserted together.** Preserve this — don't defeat it.
- **Auto-reverse:** none. Manual reel machine. No direction command.
- **Power:** A77 has a hard mechanical power switch; **no soft standby**. Mains
  is NOT automated here (that would be a separate, properly-rated relay-on-mains
  subproject).
- **No tape-motion sensor exists** in the A77 — the §5.9 transport schematic shows
  only the **photoelectric end-of-tape switch** (LDR + lamp). This absence is the
  root cause of the "wait for rewind to stop before Play" hazard (§8), and is why
  the interlock needs an *added* sensor.

### Remote control schematic (manual Fig. 7.1-86)

![Revox A77 REMOTE CONTROL schematic, Fig. 7.1-86, showing the five momentary buttons (<<, >>, PLAY, STOP, REC), their RC/diode networks, the pin-to-colour mapping, and the Hirschmann WIST 10 connector pinout](./img/remote-schematic.png)

### Relay / solenoid truth table (manual Table 5.9-44)

![Revox A77 Table 5.9-44: which relays (A, B, C), the Record Relay, and the Roller and Brake solenoids are energized for STOP, PLAY, >>, <<, and REC](./img/function-table.png)

| Mode | Relay A | Relay B | Relay C | Record Relay | Roller Sol. | Brake Sol. |
|---|:--:|:--:|:--:|:--:|:--:|:--:|
| STOP | – | – | – | – | – | – |
| PLAY | yes | – | – | – | yes | yes |
| `>>` FF | – | – | yes | – | – | yes |
| `<<` REW | – | yes | – | – | – | yes |
| REC | yes | yes | – | yes | yes | yes |

(REC = A+B+Record Relay confirms the PLAY-dependency of Record.)

---

## 3. Target command set

Five transport functions, all momentary-contact:

| Function | Emulation |
|---|---|
| Stop   | pulse STOP contact (~200 ms) — safe first test |
| Play   | pulse PLAY contact — **gated by motion interlock (§8)** |
| FF     | pulse FAST-FORWARD contact |
| Rewind | pulse REWIND contact |
| Record | assert PLAY + REC **together** (interlock) — gate behind confirm/arm |

No standby/power (no soft-power on the A77). Optionally publish reel-motion /
end-of-tape state to MQTT (free once the §5 sensor exists).

---

## 4. Wiring — CONFIRMED PIN MAP (manual Fig. 7.1-86)

The connector is a **Hirschmann WIST 10**. Bottom-row pin/colour/function mapping
read directly from the schematic. Each button closes the pin-pair shown:

| Function | Closes pins | Wire colours | Notes |
|---|---|---|---|
| `<<` REWIND   | **8 - 9**  | gry - wht | plain closure |
| `>>` FAST-FWD | **10 - 3** | blk - org | has RC net (22 Ω + 10 k + 500 µF) + steering diode in remote |
| PLAY | **4 - 5** | yel - grn | plain closure (+ steering diode) |
| STOP | **1 - 2** | brn - red | has RC net; **this is the dummy-plug pair** |
| REC  | **6 - (PLAY)** | blu | fed via PLAY; assert with PLAY |
| **+27 V out** | **7** | vio | 150 mA max — feeds the buck (NOT the ESP directly) |
| connector type | — | — | Hirschmann WIST 10, 10-pin DIN |

> Pin numbers on the connector drawing (from the manual): 1 brn, 2 red, 3 org,
> 4 yel, 5 grn, 6 blu, 7 vio, 8 gry, 9 wht, 10 blk; centre pin marked "sw"
> (chassis/screen).

**Dummy plug:** shorts **1 - 2** (the STOP pair). The deck reads "stop pair closed"
as its rest condition for remote operation; keep this bridge in your adapter so the
deck behaves normally. Your STOP opto-MOSFET parallels this same pair.

### Per-function output stage

Each ESP32 GPIO drives one opto-MOSFET whose floating output is wired **across that
function's pin-pair**, exactly mimicking the button:

```
GPIO ──[330 Ω]──► opto-MOSFET LED (e.g. AQY212)
                  opto-MOSFET output ──► across the two pins of the pair
                                          (e.g. PLAY = pin 4 - pin 5)
```

- Pulse = GPIO high for ~150–250 ms, then low (a momentary press). Tune on bench.
- **Record:** drive PLAY opto AND REC opto together for the press window
  (REC = pin 6 closure while PLAY 4-5 is also closed).
- **STOP:** parallels pins 1-2; leave the dummy bridge in place as well (harmless
  — both just close the same pair).

Use **opto-MOSFET solid-state relays** (AQY212 / TLP222 / G3VM-61A1) — floating,
polarity-agnostic SPST-NO. Small signal relays work but are noisier and bigger;
avoid "relay modules with JD-VCC" unless you specifically want mechanical relays.

### Power tap (per §1)

```
DIN pin 7 (+27 V)
  └─[fuse 100–200 mA]─► switching buck (5 V out, >=30 V in)
                            │
                       ─┬─[2.2–10 Ω]──┬── ESP32 5 V rail
                        │              │     (100 µF + 0.1 µF at board)
                        │           1000 µF low-ESR (reservoir; see §1)
                        │              │
DIN chassis/centre ─────┴──────────────┴── ESP32 GND  ──► buck GND
```

- **Use a switching buck**, set to 5 V, rated for ≥30 V input (27 V can rise a bit).
  A linear regulator dropping 27→5 V at ~100 mA would burn ~2 W as heat — avoid.
- **Fuse the pin-7 tap (100–200 mA)** — the rail is only 150 mA, a fault must not
  exceed that.
- The contact pins carry the deck's own low-level switching and are kept
  **isolated from the board by the opto-MOSFETs**, regardless of how the board is
  powered.

---

## 5. Reel-motion sensor (enables the interlock + tape feedback)

The A77 has no motion sensor (confirmed — §2 has only the photoelectric
end-of-tape switch), so you add one for the board to read. This is the whole basis
of the firmware interlock in §8:

- **Pickup:** an optical/IR-reflective or Hall sensor watching a moving element —
  a reel hub, the brake-drum, or a toothed wheel on the counter/brake-drum path
  (this is exactly where the B77 and the factory ITAM-modified A77 put their
  motion pickups).
- **Output to board:** pulses while reels turn; absence of pulses = stopped.
- **Mount non-invasively** (bracket/tape), no deck logic changes.
- **Bonus:** feed pulse count to MQTT as a tape-counter / movement indicator, and
  detect end-of-reel (motion stops unexpectedly).

A cheap IR-reflective sensor (TCRT5000 module) aimed at a reel hub with a
contrasting mark, or a Hall sensor + a small magnet on the brake-drum, both work.
The Hall approach is more robust to ambient light and tape dust. Route the sensor
to a free GPIO (input-only pins IO34–39 are fine for this; not for the opto outputs).

---

## 6. Firmware notes

The shared core (Wi-Fi + light-sleep + MQTT + identity + OTA + dispatch) lives in
`src/main.cpp` / `wifi_setup.cpp` / `wb_mqtt.cpp` / `identity.cpp` / `ota.cpp` —
**no deck-specific code there.** The A77-specific driver is `src/driver_a77.cpp`
behind the `DeviceDriver { begin, doCommand, poll }` contract in
`include/device_driver.h`.

A77-specific responsibilities of the driver:
1. **Pulse one of five opto-MOSFETs** per command — STOP, PLAY, FF, REWIND, REC.
2. **Record asserts PLAY+REC together** (per §2 truth table).
3. **Motion-sensor ISR** counts reel pulses; a software timer (`esp_timer`)
   maintains the "moving / stopped" boolean by debouncing the pulse stream.
4. **Wrap PLAY and RECORD in the §8 interlock** — assert STOP first if reels are
   still moving; wait for `reels_moving == false`; wait additional
   `POST_STOP_DELAY` (~500 ms, B77-style); only then close the PLAY contact.

Record safety: gate `record` behind a confirm/arm MQTT topic so a stray message
can't trigger a recording over a tape — same as B215.

---

## 7. MQTT (Wirenboard convention)

Same convention as the other three bridges:

| Topic | Direction | Retained | Purpose |
|---|---|---|---|
| `/devices/<id>/meta/name` | publish | yes | device display name |
| `/devices/<id>/controls/<c>/meta/type` | publish | yes | `pushbutton` |
| `/devices/<id>/controls/<c>` | publish | yes | current state |
| `/devices/<id>/controls/<c>/on` | **subscribe** | — | command in |

`<id>` here = `revox_a77`. Controls (type `pushbutton`): `stop`, `play`, `ff`,
`rewind`, `record`. Optional read-only value topics: `reels_moving`,
`tape_counter`, `end_of_tape` (all fed by the §5 sensor). Broker-direct to the
WB Mosquitto broker over Wi-Fi.

---

## 8. The rewind-safety interlock (firmware, the chosen approach)

**Problem:** pressing PLAY while reels still coast from a fast wind → pinch
roller grabs fast tape → spill/stretch. The A77 lacks the motion sensor that
the **B77** added to solve this. (Reference B77 behaviour: a motion-sense line
reads "stopped" only ~0.5 s after reels actually halt, and the logic blocks
PLAY until then.)

**Chosen fix = firmware interlock in the board** (reversible, no deck-logic
surgery). Pseudocode:

```
State: reels_moving = (motion pulses seen within last DEBOUNCE_MS)

On "play" (or "record") command:
  if reels_moving:
      assert STOP contact (if not already stopped)   // close pins 1-2
      wait until reels_moving == false
      wait additional POST_STOP_DELAY (~500 ms, B77-style settle)
  assert PLAY contact (and REC if record)            // close 4-5 (+ REC = 6)
```

Constants to tune on the bench: motion debounce window, `POST_STOP_DELAY`
(~0.5 s), press pulse width. Constants live next to the driver in
`src/driver_a77.cpp`.

**Known limitation (by design):** firmware can only gate **its own** Play
commands. A human pressing the **front-panel** Play still bypasses it (that path
doesn't go through the board). If front-panel protection is ever wanted, that
requires putting the interlock in the deck's own logic path (B77/ITAM-style
hardware mod) — explicitly out of scope here.

> A genuinely sluggish/failing end-of-tape auto-stop is usually the aged LDR R155
> / resistor R118 on the relay board — a separate repair, not this interlock.
> Manual §8.1 "Rewind" is a different mod again (R125 820 Ω → 1.2 kΩ 9 W on drive
> control 1.077.370 — fixes weak rewind torque with 18 cm reels). Don't conflate
> the three.

---

## 9. Bill of materials

| Part | Qty | Notes |
|---|---|---|
| ESP32 WROOM-32 dev board (Wi-Fi) | 1 | onboard USB-serial; PCB antenna |
| Opto-MOSFET SSR (AQY212 / TLP222 / G3VM-61A1) | 5 (+1 spare) | one per function |
| Resistor 330 Ω | 5 | opto-MOSFET LED series |
| **27 V → 5 V switching buck** | 1 | ≥30 V input; e.g. MP1584 / LM2596 module |
| **Fuse 100–200 mA + holder** | 1 | on the pin-7 tap |
| Resistor 2.2–10 Ω | 1 | inrush limiter at the buck output (§1) |
| Capacitor 1000 µF low-ESR | 1 | reservoir at the buck output |
| Capacitor 100 µF | 1 | decoupling at board |
| Capacitor 0.1 µF | 1 | decoupling at board |
| Reel-motion sensor (IR reflective TCRT5000, or Hall + magnet) | 1 | §5 |
| **Hirschmann WIST 10** mating plug *or* PCB-in-WIST10-footprint | 1 | see §10 — scarce part |
| Dummy-plug bridge wiring | — | replicate the 1-2 short |
| Plastic enclosure (~80×50×25 mm) | 1 | Wi-Fi antenna must NOT be inside metal — `cases/` v5 |

---

## 10. WIST 10 connector — sourcing & the PCB-in-footprint alternative

The **Hirschmann WIST 10** is the scarce, expensive part of the whole A77 project
— far more than the board or opto-MOSFETs. Three routes:

1. **Genuine WIST 10 plug.** Out of production for decades, but available from
   **Revox Service Villingen** (bagged, any quantity) and shops like **Klassik
   Audio (CH)** as a "Dummystecker" — note the ~EUR 25 minimum-order surcharge
   makes one connector pricey. Most robust; latches properly. Ask whether they
   have a *blank/unwired* WIST 10 (not just the sealed dummy) so you can build
   the adapter into it.
2. **PCB-in-WIST10-footprint (recommended for an ESP/SSR build).** A small PCB
   cut to the WIST 10 outline, with **1.4–1.5 mm pins** on the deck edge in the
   WIST 10 contact pattern and a **10-pin header** on the body for ribbon-cable
   wiring. Forum builder "hbose" (revoxforum.ch "WIST10 Stecker Ersatz") did
   exactly this for an A77 WLAN remote; cost him ~EUR 4 vs EUR 25+. Pin diameter
   1.4–1.5 mm is the hard constraint (1.5 mm² installation wire works; thinner
   pins give poor contact). Getting the contact *pattern* right is the one risk
   — measure your socket or ask hbose for his board file/dimensions
   (roehrenkramladen.de).
3. **One integrated PCB** carrying the WIST 10 pins + opto-MOSFETs + board — the
   tidiest end state; design it only after validating the contact geometry with
   route 2.

---

## 11. Shopping list — Amazon.de

| # | Item | amazon.de search term | Qty | ~EUR | Notes |
|---|---|---|---|---|---|
| 1 | ESP32 WROOM-32 dev board | `ESP32 NodeMCU WROOM-32` (3-pack) | 1 set | 18–22 | onboard USB-serial; pick PCB-antenna variant |
| 2 | Opto-MOSFET SSR | `Toshiba TLP222A` / `Panasonic AQY212` / `Omron G3VM-61A1` | 6 | 8–15 | 5 + spare; DIP through-hole easiest |
| 3 | 27 V → 5 V buck | `MP1584 Step-Down einstellbar` or `LM2596 Step-Down Modul` | 2 | 6 (set) | set to 5 V; ≥30 V input rating |
| 4 | Fuse + holder | `Feinsicherung 0,2A + Halter` | 1 | 4 | on pin-7 tap |
| 5 | Resistor kit | `Widerstand Sortiment 1/4W Metallschicht` (incl. 330 Ω, 2.2–10 Ω) | 1 kit | 8–11 | covers opto + inrush |
| 6 | IR reflective sensor | `TCRT5000 Infrarot Reflexion Sensor Modul` (5er-Set) | 1 set | 6–8 | OR item 6b |
| 6b | Hall sensor + magnets (alt.) | `A3144 Hall Sensor Modul` + `Neodym Magnete 3mm` | 1 each | 7–10 | robust to light/dust |
| 7 | WIST 10 plug *or* DIY PCB | `Hirschmann WIST 10` (DIN 10-pol) | 1 | 12–25 | **scarce — see §10** |
| 8 | Reservoir cap 1000 µF low-ESR | `Elektrolytkondensator 1000uF 16V Low ESR` | 2 | 5 | at the buck output |
| 9 | Decoupling caps | `Elektrolytkondensator 100uF 16V` + `Keramikkondensator 100nF Sortiment` | a few | 5 | at-board decoupling |
| 10 | Plastic enclosure | `Kunststoffgehäuse ABS 80x50x25` | 1 | 6–10 | **must be non-metal** (Wi-Fi antenna) |
| 11 | Perfboard / jumpers | `Lochrasterplatine Set` + `Jumper Kabel Dupont` | 1 each | 8–12 | prototyping |
| 12 | Hook-up wire | `Schaltlitze Set 0,25mm² flexibel` | 1 | 8 | DIN harness |

**Notes / gotchas for ordering:**
- **Buck (item 3):** must be a *switching* step-down set to 5 V, NOT a linear
  regulator (27 → 5 V linear at 100 mA ≈ 2 W of heat). Confirm ≥30 V input rating.
- Reservoir cap (item 8): proper **low-ESR** electrolytic, not a generic. ESR
  matters for soaking up Wi-Fi TX-current spikes downstream of the buck.
- Hall sensor (6b) needs a small magnet fixed to a rotating part (brake-drum) —
  kapton tape or epoxy; keep it balanced.

---

## 12. Casing

- **Material:** plastic (ABS/PETG). Wi-Fi antenna must not be inside a metal box.
  PETG handles warm-equipment proximity better than PLA.
- **Layout:** ESP32 WROOM-32 with the **PCB antenna pointing toward a case edge**.
  Buck + fuse on a small daughter perfboard area; opto-MOSFETs around the WIST 10
  pigtail entry point.
- **Strain-relieve** the DIN pigtail; ventilation slots (the buck runs warm); mount
  behind the deck **away from the transformer/motors**. Route the motion-sensor
  lead cleanly to its bracket.
- **Label** the DIN pigtail pinout (use the §4 map).
- See `cases/` for the v5 STL files.

---

## 13. Bring-up sequence

1. **Continuity check** (deck unpowered) — confirm each button closes the pin-pair
   in §4 against your actual socket.
2. **First flash** the WROOM-32 over USB-serial (single wired step in the box's
   life). Bench it **without** the deck: confirm Wi-Fi associates, MQTT topics
   appear in WB, each button pulses its GPIO/opto-MOSFET (meter the contact
   closing across the right pin-pair).
3. **Set the buck to 5 V on the bench BEFORE connecting to pin 7**; fuse the pin-7
   tap. **Measure pin 7 ≈ 27 V and that it holds under the buck's load.**
4. Install adapter on the WIST 10 socket (keep the 1-2 dummy bridge). Send
   **STOP** first.
5. Test **PLAY** (4-5), **FF** (10-3), **REWIND** (8-9). Then **RECORD** (PLAY
   4-5 + REC 6 together, gated).
6. Add the motion sensor; verify `reels_moving` tracks reality; tune debounce
   + post-stop delay.
7. Enable the §8 interlock; test PLAY-immediately-after-REWIND → confirm it
   waits for stop + settle before engaging. Confirm no tape spill.

---

## 14. Open items (bench tuning)

Paste this file back and say "continue the Revox A77 build."

1. **Pick the reel-motion sensor** (§5) and mounting point, then tune the
   stop-detect debounce and `POST_STOP_DELAY` (~0.5 s, B77-style) in
   `src/driver_a77.cpp`.
2. **Bench-confirm the REC = PLAY+REC interlock behaviour** on your actual MK4
   (logic confirmed in §2; just verify on the unit).
3. **Press pulse width** — bench-tune (~150–250 ms typical).

---

## 15. Source references

- **A77 service manual 10.18.1611 — §7.1 Remote Control, Fig. 7.1-86**: connector
  = Hirschmann WIST 10; button → pin-pair map (REW 8-9, FF 10-3, PLAY 4-5,
  STOP 1-2, REC 6); pin 7 = +27 V / 150 mA; **dummy plug shorts 1 & 2**. **§5.9
  Drive Control + Table 5.9-44**: relay/solenoid truth table (REC = A+B+Record
  Relay → PLAY-dependency); only a photoelectric end-of-tape switch, no motion
  sensor. **§8.1 Rewind**: R125 820 Ω → 1.2 kΩ torque mod (unrelated). End-of-
  tape LDR R155 / relay-board R118 = auto-stop sensitivity (separate repair).
- **revoxforum.ch "WIST10 Stecker Ersatz"** (hbose): PCB-in-WIST10-footprint
  adapter, 1.4–1.5 mm pins, 10-pin header, ~EUR 4; genuine plug available from
  Revox Service Villingen (~EUR 25 min-order). Site: roehrenkramladen.de.
- **Tapeheads "ReVox A77 WIFI Remote, I am making my own"**: A77 remote-socket
  wires desoldered to relay modules driven by a Raspberry Pi; thread recommends
  ESP/NodeMCU; relay-interface approach ports to Teac/Ampex transports too.
- **Tapeheads "Revox B77 (mk2) diy remote control advice"**: corroborates the
  contact logic — momentary switches, REC fed from PLAY, diode blocks REC-on-
  PLAY-only; some builders rewired to ground-closure to drop the dummy plug.
- **Commercial adapter (revoxremotes/teacremotes)**: Sony-IR adapter into the
  remote connector controlling Play/Record/Stop/FF/Rewind; needs dummy plug
  removed. Confirms contact-emulation is all that's required.
- **B77 transport behaviour (Tapeheads transport-problem thread)**: motion-sense
  point P4 = 5 V stopped, 0 while moving, returns to 5 V ~0.5 s after full stop —
  the model for the §8 interlock timing.
- **ITAM 3.77 (factory-modified A77)**: counter belt over a motion-sensor
  pulley/toothed wheel feeding an extra plug-in control board — precedent for
  adding motion sensing to an A77.

---

## 16. Relationship to the B215 project

Shared, reuse directly: board + Wirenboard MQTT scaffolding; record-safety
gating; broker-direct integration; "appears as native WB device" approach;
**deck-power architecture (with a 27 V→5 V buck inserted on the A77 side
because the rail is 27 V not 5 V)**.

Different from B215: **dry-contact opto-MOSFET outputs across pin-pairs** (not
open-collector serial); **no protocol/capture** (just pulse contacts);
**REC = PLAY + REC interlock**; **no soft power**; **+27 V rail via buck**;
**added reel-motion sensor + firmware rewind interlock**; **scarce WIST 10
connector** (see §10); no rich status bus (feedback is only what the added
sensor provides).
