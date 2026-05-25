# Revox A77 MK4 → Wirenboard via REMOTE CONTROL DIN — Option B Build & Handoff

**Goal:** Control a Revox A77 MK4 reel-to-reel from a Wirenboard PLC using a small
ESP32 that emulates the A77's momentary **remote-control contacts**, publishing
**Wirenboard-conformant MQTT** over Wi-Fi. Plus a **firmware rewind-safety interlock**
that prevents engaging Play until the reels have stopped. Fully external/reversible —
no cutting into the deck's vintage logic.

**Companion document:** [`wb-revoxb215-esp32-bridge.md`](./wb-revoxb215-esp32-bridge.md) (the B215 build).
Much of the MQTT/casing/firmware-scaffolding is shared; this doc only details what's
different for the A77.

**Status:** ✅ **Pinout, contact logic, dummy-plug bridge and power pin CONFIRMED from the
A77 service manual (10.18.1611, §7.1 Fig. 7.1‑86 and §5.9 Table 5.9‑44).** Remaining open
items are bench-tuning + sensor selection only (see §0). Do a 30‑second continuity check
of the socket before connecting, but the schematic is authoritative.

---

## 0. How to resume this with Claude later

Paste this file back and say "continue the Revox A77 Option B build." Outstanding items
(all the manual-derived facts are now filled in):

1. ✅ ~~Read the exact REMOTE CONTROL DIN pinout~~ — **DONE, see §4.**
2. ✅ ~~Confirm what the dummy plug shorts~~ — **DONE: shorts pins 1 & 2 (STOP pair), see §1/§4.**
3. **Pick the reel-motion sensor** and mounting point (§5), then tune the stop-detect
   debounce and post-stop delay (~0.5 s, B77-style).
4. Bench-confirm the REC = PLAY+REC interlock behaviour on your actual MK4 (logic confirmed
   in §1; just verify on the unit).

Then Claude can finalise the firmware (interlock constants) and the wiring harness.

---

## 1. How the A77 remote actually works (CONFIRMED from manual §7.1 + §5.9)

- The A77 (late-60s/70s) has **no microcontroller, no IR, no serial bus**. The transport
  is **relay logic**: 3 relays (A, B, C) + a Record Relay + roller/brake solenoids
  (manual §5.9). The deck was explicitly designed for momentary-contact wired remote of
  all functions.
- The rear connector is a **Hirschmann WIST 10 (10-pin DIN)**, labelled REMOTE CONTROL
  (rear-panel item 25). The original remote is just a box of momentary buttons that
  **parallel the front-panel switches** — the manual states remote-control contacts
  **F3…F10** are simply paralleled onto the deck's own button contacts, and "to have a
  minimum of relays, their control is locked by diodes."
- **Each button connects a PAIR of connector pins** (it's a simple SPST closure between
  two pins, not a switch to a single common rail). See the exact pairs in §4.
- **Dummy plug:** the manual says verbatim that the dummy connector **"must be inserted
  for operation without the REMOTE CONTROL unit"** and that it **shorts terminals 1 & 2**
  (the STOP pair). Keep that bridge present in your adapter.
- **Switches are momentary / non-latching**, both on the machine and the remote.
- **Pin 7 (vio) = +27 Vdc out**, intended for slide projectors, **150 mA max**. This is
  the only power available on the connector. (Correction to earlier drafts: it is **27 V,
  not 5 V** — do **not** feed an ESP32 from it directly; see §4.)
- **REC interlock — confirmed by the relay truth table (Table 5.9‑44):** REC energizes
  **relays A *and* B plus the Record Relay**. Relay A is the PLAY relay. So **Record
  depends on the PLAY path**; in the remote wiring REC is steered via diodes so pressing
  REC alone does nothing. **Net: Record requires PLAY + REC asserted together.** Preserve
  this — don't defeat it.
- **Auto-reverse:** none. Manual reel machine. No direction command.
- **Power:** A77 has a hard mechanical power switch; **no soft standby**. Mains power is
  NOT automated here (would be a separate, properly-rated relay-on-mains subproject).
- **No tape-motion sensor exists** in the A77 — the §5.9 transport schematic shows only
  the **photoelectric end-of-tape switch** (LDR + lamp). This absence is the root cause of
  the "wait for rewind to stop before Play" hazard (see §7), and is why the interlock
  needs an *added* sensor.

### Remote control schematic (manual Fig. 7.1‑86)

![Revox A77 REMOTE CONTROL schematic, Fig. 7.1-86, showing the five momentary buttons (<<, >>, PLAY, STOP, REC), their RC/diode networks, the pin-to-colour mapping, and the Hirschmann WIST 10 connector pinout](./img/remote-schematic.png)

### Relay / solenoid truth table (manual Table 5.9‑44)

![Revox A77 Table 5.9-44: which relays (A, B, C), the Record Relay, and the Roller and Brake solenoids are energized for STOP, PLAY, >>, <<, and REC](./img/function-table.png)

| Mode | Relay A | Relay B | Relay C | Record Relay | Roller Sol. | Brake Sol. |
|---|:--:|:--:|:--:|:--:|:--:|:--:|
| STOP | – | – | – | – | – | – |
| PLAY | ✓ | – | – | – | ✓ | ✓ |
| `>>` FF | – | – | ✓ | – | – | ✓ |
| `<<` REW | – | ✓ | – | – | – | ✓ |
| REC | ✓ | ✓ | – | ✓ | ✓ | ✓ |

(REC = A+B+Record Relay confirms the PLAY-dependency of Record.)

---

## 2. Target command set

Five transport functions, all momentary-contact:

| Function | Emulation |
|---|---|
| Stop   | pulse STOP contact (~200 ms) — safe first test |
| Play   | pulse PLAY contact — **gated by motion interlock (§7)** |
| FF     | pulse FAST-FORWARD contact |
| Rewind | pulse REWIND contact |
| Record | assert PLAY + REC **together** (interlock) — gate behind confirm/arm |

No standby/power. Optionally publish reel-motion / end-of-tape state to MQTT (free
once the sensor exists).

---

## 3. Why the output stage differs from the B215

| | B215 (serial link) | **A77 (remote contacts)** |
|---|---|---|
| Control | ITT serial bitstream on one open-collector data line | **momentary dry contacts** bridging a pin-pair |
| Output device | one open-collector / opto pulling a data pin low | **floating dry contact per function**: opto-MOSFET (AQY212 / TLP222 / G3VM-61A1) or small relay |
| Why | deck idles line high, pulls low to signal | deck closes a contact between two of its own pins; a floating SSR replicates the button exactly |

**Use opto-MOSFET solid-state relays (preferred) or small signal relays** — one per
function, wired **across the pin-pair that the corresponding button closes** (see §4).
They're floating and polarity-agnostic, so they don't care which pin of the pair is which.
This matches what the commercial adapter and the Raspberry-Pi DIY build both do.

---

## 4. Wiring — CONFIRMED PIN MAP (manual Fig. 7.1‑86)

The connector is a **Hirschmann WIST 10**. Bottom-row pin/colour/function mapping read
directly from the schematic. Each button closes the pin-pair shown:

| Function | Closes pins | Wire colours | Notes |
|---|---|---|---|
| `<<` REWIND | **8 ↔ 9** | gry ↔ wht | plain closure |
| `>>` FAST-FWD | **10 ↔ 3** | blk ↔ org | has RC net (22 Ω + 10 k + 500 µF) + steering diode in remote |
| PLAY | **4 ↔ 5** | yel ↔ grn | plain closure (+ steering diode) |
| STOP | **1 ↔ 2** | brn ↔ red | has RC net; **this is the dummy-plug pair** |
| REC | **6 ↔ (PLAY)** | blu | fed via PLAY; assert with PLAY |
| **+27 V out** | **7** | vio | 150 mA max — NOT for ESP32 power directly |
| connector type | — | — | Hirschmann WIST 10, 10-pin DIN |

> Pin numbers on the connector drawing (from the manual): 1 brn, 2 red, 3 org, 4 yel,
> 5 grn, 6 blu, 7 vio, 8 gry, 9 wht, 10 blk; centre pin marked "sw" (chassis/screen).

**Dummy plug:** shorts **1 ↔ 2** (the STOP pair). The deck reads "stop pair closed" as its
rest condition for remote operation; keep this bridge in your adapter so the deck behaves
normally. Your STOP opto-MOSFET parallels this same pair.

### Per-function output stage

Each ESP32 GPIO drives one opto-MOSFET whose floating output is wired **across that
function's pin-pair**, exactly mimicking the button:

```
ESP32 GPIO ──[330Ω]──► opto-MOSFET LED (e.g. AQY212)
                        opto-MOSFET output ──► across the two pins of the pair
                                                (e.g. PLAY = pin 4 ↔ pin 5)
```

- Pulse = GPIO high for ~150–250 ms, then low (a momentary press). Tune on bench.
- **Record:** drive PLAY opto AND REC opto together for the press window
  (REC = pin 6 closure while PLAY 4↔5 is also closed).
- **STOP:** parallels pins 1↔2; leave the dummy bridge in place as well (harmless — both
  just close the same pair).

### Power

Power the ESP32 from its **own small 5 V USB supply** (recommended, simplest, isolated).

If you want a single-cable install you *may* derive logic power from **pin 7 (+27 V,
150 mA)** via a proper **27 V→5 V buck converter** — but never connect 27 V to the ESP32
directly, and budget the 150 mA limit against ESP32 Wi-Fi TX spikes (a buck + local
reservoir cap is mandatory if you go this route). The contact pins carry the deck's own
low-level signalling and are kept isolated from the ESP32 by the opto-MOSFETs regardless.

---

## 5. Reel-motion sensor (enables the interlock + tape feedback)

The A77 has no motion sensor (confirmed — §5.9 has only the photoelectric end-of-tape
switch), so you add one for the ESP32 to read. This is the whole basis of the firmware
interlock:

- **Pickup:** an optical/IR-reflective or Hall sensor watching a moving element — a reel
  hub, the brake-drum, or a toothed wheel on the counter/brake-drum path (this is exactly
  where the B77 and the factory ITAM-modified A77 put their motion pickups).
- **Output to ESP32:** pulses while reels turn; absence of pulses = stopped.
- Mount non-invasively (bracket/tape), no deck logic changes.
- Bonus: feed pulse count to MQTT as a tape-counter / movement indicator, and detect
  end-of-reel (motion stops unexpectedly).

A cheap IR-reflective sensor (TCRT5000 module) aimed at a reel hub with a contrasting mark,
or a Hall sensor + a small magnet on the brake-drum, both work. The Hall approach is more
robust to ambient light and tape dust.

---

## 6. Bill of materials (Option B, A77)

| Part | Qty | Notes |
|---|---|---|
| ESP32 dev board | 1 | Wi-Fi; non-metal enclosure |
| Opto-MOSFET SSR (AQY212 / TLP222 / G3VM-61A1) | 5 | one per function (STOP, PLAY, FF, REW, REC); small relays OK alternative |
| Resistor 330 Ω | 5 | opto-MOSFET LED series |
| Reel-motion sensor (IR reflective TCRT5000, or Hall + magnet) | 1 | §5 |
| Hirschmann **WIST 10** mating plug (10-pin DIN) | 1 | confirmed connector type |
| 5 V USB supply for ESP32 | 1 | do NOT power from pin 7 (27 V) without a buck converter |
| Optional 27 V→5 V buck converter | 0–1 | only if deriving power from pin 7 |
| ABS/PETG enclosure | 1 | NON-metal (Wi-Fi) |
| Dummy-plug bridge wiring | — | replicate the 1↔2 short |

---

## 6a. Precise shopping list — Amazon.de

Exact-ish search terms / typical listings on **amazon.de**. Quantities assume one build
plus spares. Prices indicative (2024–2025); verify at purchase.

| # | Item | amazon.de search term | Qty | ~€ | Notes |
|---|---|---|---|---|---|
| 1 | ESP32 dev board | `ESP32 NodeMCU WROOM-32 Entwicklungsboard` (e.g. AZDelivery 3er-Set) | 1 (3-pack) | 12–18 | 3-pack gives spares; pick PCB-antenna version |
| 2 | Opto-MOSFET SSR | `Toshiba TLP222A` **or** `Panasonic AQY212` **or** `Omron G3VM-61A1` | 6 | 8–15 | buy 6 (5 + spare); DIP-through-hole easiest to breadboard |
| 3 | Resistor kit | `Widerstand Sortiment 1/4W Metallschicht` (incl. 330 Ω) | 1 kit | 8–11 | also covers sensor-side resistors |
| 4 | IR reflective sensor | `TCRT5000 Infrarot Reflexion Sensor Modul` (5er-Set) | 1 set | 6–8 | OR item 4b |
| 4b | Hall sensor + magnets (alt.) | `A3144 Hall Sensor Modul` + `Neodym Magnete 3mm` | 1 each | 7–10 | more robust to light/dust |
| 5 | Hirschmann WIST 10 plug | `Hirschmann WIST 10` (DIN 10-pol Stecker) | 1 | 12–25 | specialist part — may need Reichelt/Conrad if amazon.de stock thin |
| 6 | 5 V USB PSU | `USB Netzteil 5V 2A` + `Micro-USB Kabel` | 1 | 7–10 | clean ESP32 supply |
| 7 | Buck converter (optional) | `Step-Down Wandler 27V 5V einstellbar` (e.g. LM2596 module) | 0–1 | 6 (5-pack) | only if powering from pin 7 |
| 8 | Enclosure | `Kunststoffgehäuse ABS Gehäuse 100x60x25` | 1 | 7–10 | NON-metal for Wi-Fi |
| 9 | Perfboard / jumpers | `Lochrasterplatine Set` + `Jumper Kabel Dupont` | 1 each | 8–12 | prototyping |
| 10 | Hook-up wire | `Schaltlitze Set 0,25mm² flexibel` | 1 | 8 | DIN harness |
| 11 | Reservoir cap (if buck used) | `Elektrolytkondensator 470µF 16V` | a few | 5 | local ESP32 rail decoupling |

**Notes / gotchas for ordering:**
- **The Hirschmann WIST 10 (item 5) is the one risky part** — it's a specialist DIN
  connector. If amazon.de doesn't stock it reliably, get it from **Reichelt, Conrad, or
  Mouser DE**. Confirm the mating plug matches your deck's socket gender before ordering.
- Opto-MOSFETs: any of TLP222 / AQY212 / G3VM-61A1 work; they're floating SPST-NO solid
  state. Avoid "relay modules with JD-VCC" unless you specifically want mechanical relays.
- If you choose the **Hall** motion sensor (4b), you also need a way to fix a small magnet
  to a rotating part (brake-drum) — kapton tape or epoxy; keep it balanced.
- Buy the **3-pack ESP32** and **6× opto-MOSFETs** so a mistake during bring-up doesn't
  stall the build.

---

## 7. The rewind-safety interlock (firmware, the chosen approach)

**Problem:** pressing PLAY while reels still coast from a fast wind → pinch roller grabs
fast tape → spill/stretch. The A77 lacks the motion sensor that the **B77** added to
solve this. (Reference B77 behaviour: a motion-sense line reads "stopped" only ~0.5 s
after reels actually halt, and the logic blocks PLAY until then.)

**Chosen fix = firmware interlock in the ESP32** (reversible, no deck-logic surgery):

```
State: reels_moving = (motion pulses seen within last N ms)

On "play" (or "record") command:
  if reels_moving:
       assert STOP contact (if not already stopped)   // STOP = close pins 1↔2
       wait until reels_moving == false
       wait additional POST_STOP_DELAY (~500 ms, B77-style settle)
  assert PLAY contact (and REC if record)             // PLAY = close 4↔5 (+ REC = 6)
```

Constants to tune on the bench: motion debounce window `N`, `POST_STOP_DELAY` (~0.5 s),
press pulse width.

**Known limitation (by design):** firmware can only gate **its own** Play commands. A
human pressing the **front-panel** Play still bypasses it (that path doesn't go through
the ESP32). If front-panel protection is ever wanted, that requires putting the interlock
in the deck's own logic path (B77/ITAM-style hardware mod) — explicitly out of scope here.

> Note: a genuinely sluggish/failing end-of-tape auto-stop is usually the aged LDR R155 /
> resistor R118 on the relay board — a separate repair, not this interlock. (Manual §8.1
> "Rewind" is a different mod again: it fixes weak rewind torque with 18 cm reels by
> replacing R125 820 Ω → 1.2 kΩ 9 W on drive control 1.077.370. Don't conflate the three.)

---

## 8. MQTT (Wirenboard-conformant) — same convention as B215

- Device id e.g. `revox_a77`.
- Controls (type `pushbutton`): `stop`, `play`, `ff`, `rewind`, `record`.
- Optional (read-only value topics): `reels_moving`, `tape_counter`, `end_of_tape`.
- Topic shape:
  - `/devices/revox_a77/meta/name` (retained)
  - `/devices/revox_a77/controls/<c>/meta/type` (retained)
  - `/devices/revox_a77/controls/<c>` (publish state, retained)
  - `/devices/revox_a77/controls/<c>/on` (subscribe; UI/rules write here)
- Connect to the Wirenboard Mosquitto broker over Wi-Fi (broker-direct, simplest).
- **Record safety:** gate behind a confirm/arm topic, same as B215.

Firmware scaffolding (WiFi + PubSubClient + command table + handler) is identical in
shape to the B215 sketch — reuse it. The only A77-specific logic is: (a) each command
pulses an opto-MOSFET across a pin-pair instead of calling `sendLinkFrame()`, (b) the §7
interlock wraps play/record, (c) Record asserts PLAY+REC together.

---

## 9. Casing

Same rules as B215: ABS/PETG (NON-metal for Wi-Fi), strain-relieved DIN pigtail,
ventilation slots, mount behind the deck away from the transformer/motors. Route the
motion-sensor lead cleanly to its bracket. Label the DIN pigtail pinout (use the §4 map).

---

## 10. Bring-up sequence (A77 Option B)

1. ✅ Pin map filled (§4). Still do a continuity check (deck unpowered) confirming each
   button closes the pin-pair in §4 against your actual socket.
2. Bench ESP **without** deck: confirm Wi-Fi, MQTT topics in WB, each button pulses its
   GPIO/opto-MOSFET (meter the contact closing across the right pin-pair).
3. Install adapter on the WIST 10 socket (keep the 1↔2 dummy bridge). Send **STOP** first.
4. Test PLAY (4↔5), FF (10↔3), REWIND (8↔9). Then **RECORD** (PLAY 4↔5 + REC 6 together, gated).
5. Add motion sensor; verify `reels_moving` tracks reality; tune debounce + post-stop delay.
6. Enable the §7 interlock; test PLAY-immediately-after-REWIND → confirm it waits for
   stop + settle before engaging. Confirm no tape spill.

---

## 11. Prior art / references

- **A77 service manual 10.18.1611 — §7.1 Remote Control, Fig. 7.1‑86**: connector =
  Hirschmann WIST 10; button→pin-pair map (REW 8↔9, FF 10↔3, PLAY 4↔5, STOP 1↔2, REC 6);
  pin 7 = +27 V / 150 mA; **dummy plug shorts 1 & 2**. **§5.9 Drive Control + Table 5.9‑44**:
  relay/solenoid truth table (REC = A+B+Record Relay → PLAY-dependency); only a
  photoelectric end-of-tape switch, no motion sensor. **§8.1 Rewind**: R125 820 Ω→1.2 kΩ
  torque mod (unrelated). end-of-tape LDR R155 / relay-board R118 = auto-stop sensitivity
  (separate repair).
- **Tapeheads "ReVox A77 WIFI Remote, I am making my own"**: A77 remote-socket wires
  desoldered to relay modules driven by a Raspberry Pi, web page controls all drive
  functions; thread recommends doing it with an ESP/NodeMCU instead (your exact plan);
  notes the relay-interface approach ports to Teac/Ampex transports too.
- **Tapeheads "Revox B77 (mk2) diy remote control advice"**: corroborates the contact
  logic — momentary switches, REC fed from PLAY, diode blocks REC-on-PLAY-only; some
  builders rewired to ground-closure to drop the dummy plug.
- **Commercial adapter (revoxremotes/teacremotes)**: Sony-IR adapter into the remote
  connector controlling Play/Record/Stop/FF/Rewind; needs dummy plug removed. Confirms
  contact-emulation is all that's required (this is the unit you want to replace visually).
- **B77 transport behaviour (Tapeheads transport-problem thread)**: motion-sense point P4
  = 5 V stopped, 0 while moving, returns to 5 V ~0.5 s after full stop — the model for the
  §7 interlock timing.
- **ITAM 3.77 (factory-modified A77)**: counter belt over a motion-sensor pulley/toothed
  wheel feeding an extra plug-in control board — precedent for adding motion sensing to
  an A77.

---

## 12. Relationship to the B215 project

Shared, reuse directly: ESP32 + Wi-Fi + Wirenboard MQTT scaffolding; non-metal casing;
record-safety gating; broker-direct integration; "appears as native WB device" approach.

Different from B215: **dry-contact opto-MOSFET outputs across pin-pairs** (not
open-collector serial); **no protocol/capture** (just pulse contacts); **REC=PLAY+REC
interlock**; **no soft power** (pin 7 is 27 V, not a logic rail); **added reel-motion
sensor + firmware rewind interlock**; no rich status bus (feedback is only what your added
sensor provides).
