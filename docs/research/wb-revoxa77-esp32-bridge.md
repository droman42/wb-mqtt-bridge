# Revox A77 MK4 → Wirenboard via REMOTE CONTROL DIN — Option B Build & Handoff

**Goal:** Control a Revox A77 MK4 reel-to-reel from a Wirenboard PLC using a small
ESP32 that emulates the A77's momentary **remote-control contacts**, publishing
**Wirenboard-conformant MQTT** over Wi-Fi. Plus a **firmware rewind-safety interlock**
that prevents engaging Play until the reels have stopped. Fully external/reversible —
no cutting into the deck's vintage logic.

**Companion document:** [`wb-revoxb215-esp32-bridge.md`](./wb-revoxb215-esp32-bridge.md) (the B215 build).
Much of the MQTT/casing/firmware-scaffolding is shared; this doc only details what's
different for the A77.

**Status:** design locked. Exact DIN pin numbers must be **read from the A77 service
manual** (the user opted to lean on the manual, not ring out an original remote).
Treat pin assignments as TO-CONFIRM until verified against the manual + a continuity check.

---

## 0. How to resume this with Claude later

Paste this file back and say "continue the Revox A77 Option B build." Outstanding items:

1. **Read the exact REMOTE CONTROL DIN pinout** from the A77 service manual
   (manual 10.18.1611; rear-panel item **25 = remote control plug**; section **7.1
   Remote Control**; **Diagram 3 = Switch Board 1.077.435**; drive logic in **5.9**).
   Fill the pin map in §4.
2. **Confirm what the dummy plug shorts** (deck won't run without either the remote or
   the dummy bridging certain pins — §1).
3. **Pick the reel-motion sensor** and mounting point (§6), then tune the stop-detect
   debounce and post-stop delay (~0.5 s, B77-style).
4. Bench-confirm the REC = PLAY+REC interlock behaviour on your actual MK4.

Then Claude can finalise the firmware (contact map + interlock constants) and a
confirmed wiring diagram.

---

## 1. How the A77 remote actually works (confirmed facts)

- The A77 (late-60s/70s) has **no microcontroller, no IR, no serial bus**. The transport
  is **relay logic**: ~4 relays + roller/brake solenoids. (Service manual 5.9; the deck
  was explicitly designed for momentary-contact wired remote of all functions.)
- The rear **REMOTE CONTROL** connector (rear-panel item 25) brings the front-panel
  momentary switches out to a plug. The original remote is just a box of momentary
  buttons in parallel with the front panel.
- **A dummy plug must be inserted when no remote is used** — it bridges certain terminals
  so the deck operates normally. Removing the remote without the dummy (or vice-versa)
  can disable functions. **Replicate whatever the dummy shorts** in your adapter, or keep
  the dummy's bridge in your wiring.
- **Switches are momentary / non-latching**, both on the machine and the remote.
- **Contact electrical behaviour (confirmed from A77/B77 remote schematic discussion):**
  - Except REC, **each switch connects the ~24 V supply directly to that function's
    output line**. (So you are *switching 24 V*, not grounding — design the output stage
    accordingly.)
  - **REC is interlocked:** the REC switch only receives 24 V *after* the PLAY switch is
    closed, and only then passes 24 V to the REC output. A diode (D3) prevents REC
    activating on PLAY-only. **Net: Record requires PLAY + REC asserted together.**
    Preserve this — don't defeat it.
- **Auto-reverse:** none. Manual reel machine. No direction command.
- **Power:** A77 has a hard mechanical power switch; **no soft standby**. Mains power is
  NOT automated here (would be a separate, properly-rated relay-on-mains subproject).
- **No tape-motion sensor exists** in the A77 — this is the root cause of the
  "wait for rewind to stop before Play" hazard (see §7).

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
| Control | ITT serial bitstream on one open-collector data line | **momentary dry contacts** switching ~24 V |
| Output device | one open-collector / opto pulling a data pin low | **floating dry contact per function**: relay or **opto-MOSFET (AQY212 / TLP222 / G3VM-61A1)** |
| Why | deck idles line high, pulls low to signal | deck switches its own 24 V through the contact; an open-collector-to-ground would be wrong/destructive |

**Use opto-MOSFET solid-state relays (preferred) or small signal relays** — one per
function. They're floating, polarity-agnostic dry contacts that simply replace each
momentary switch. This matches what the commercial adapter and the Raspberry-Pi DIY
build both do (relay modules across the remote contacts).

---

## 4. Wiring (PIN NUMBERS = TO CONFIRM FROM MANUAL)

Read these from A77 service manual section 7.1 + Diagram 3 (Switch Board 1.077.435),
then fill in:

```
REMOTE CONTROL DIN (rear item 25):
  pin ?  = common / +24 V supply
  pin ?  = STOP   output
  pin ?  = PLAY   output
  pin ?  = FF     output
  pin ?  = REWIND output
  pin ?  = REC    output (fed via PLAY per interlock)
  pin ?  = (dummy-plug bridge pins: ____ to ____)
```

Each ESP32 function output drives one opto-MOSFET whose floating contact is wired
**across the corresponding momentary switch** (i.e. between the 24 V common and that
function's output pin), exactly mimicking a button press:

```
ESP32 GPIO ──[330Ω]──► opto-MOSFET LED (e.g. AQY212)
                        opto-MOSFET output ──► across [24V common] and [function pin]
```

- Pulse = GPIO high for ~150–250 ms, then low (momentary press). Tune duration on bench.
- **Record:** drive PLAY opto AND REC opto together for the press window.
- **Dummy plug:** keep its bridge present in your adapter (replicate the short), or build
  the adapter so the deck still sees the required bridge when the original dummy is removed.

Power the ESP32 from its **own small 5 V USB supply** (recommended). Older Revox remote
sockets sometimes carry mains-derived voltage — do **not** assume the DIN is a safe
low-voltage power source; verify before tapping anything for power. The 24 V you switch
is for the contacts only, kept isolated from the ESP32 by the opto-MOSFETs.

---

## 5. Reel-motion sensor (enables the interlock + tape feedback)

The A77 has no motion sensor, so you add one for the ESP32 to read (this is the whole
basis of the firmware interlock):

- **Pickup:** an optical/IR-reflective or Hall sensor watching a moving element — a reel
  hub, the brake-drum, or a toothed wheel on the counter/brake-drum path (this is exactly
  where the B77 and the factory ITAM-modified A77 put their motion pickups).
- **Output to ESP32:** pulses while reels turn; absence of pulses = stopped.
- Mount non-invasively (bracket/tape), no deck logic changes.
- Bonus: feed pulse count to MQTT as a tape-counter / movement indicator, and detect
  end-of-reel (motion stops unexpectedly).

---

## 6. Bill of materials (Option B, A77)

| Part | Qty | Notes |
|---|---|---|
| ESP32 dev board | 1 | Wi-Fi; non-metal enclosure |
| Opto-MOSFET SSR (AQY212 / TLP222 / G3VM-61A1) | 5 | one per function (STOP, PLAY, FF, REW, REC); small relays OK alternative |
| Resistor 330 Ω | 5 | opto-MOSFET LED series |
| Reel-motion sensor (IR reflective e.g. TCRT5000, or Hall + magnet) | 1 | §5 |
| DIN plug matching REMOTE CONTROL socket | 1 | confirm pin count from manual |
| 5 V USB supply for ESP32 | 1 | do NOT rely on DIN for power unless verified safe |
| ABS/PETG enclosure | 1 | NON-metal (Wi-Fi) |
| Dummy-plug bridge wiring | — | replicate what the stock dummy shorts |

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
       assert STOP contact (if not already stopped)
       wait until reels_moving == false
       wait additional POST_STOP_DELAY (~500 ms, B77-style settle)
  assert PLAY contact (and REC if record)
```

Constants to tune on the bench: motion debounce window `N`, `POST_STOP_DELAY` (~0.5 s),
press pulse width.

**Known limitation (by design):** firmware can only gate **its own** Play commands. A
human pressing the **front-panel** Play still bypasses it (that path doesn't go through
the ESP32). If front-panel protection is ever wanted, that requires putting the interlock
in the deck's own logic path (B77/ITAM-style hardware mod) — explicitly out of scope here.

> Note: a genuinely sluggish/failing end-of-tape auto-stop is usually the aged LDR R155 /
> resistor R118 on the relay board — a separate repair, not this interlock. Don't conflate.

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
pulses an opto-MOSFET instead of calling `sendLinkFrame()`, (b) the §7 interlock wraps
play/record, (c) Record asserts PLAY+REC together.

---

## 9. Casing

Same rules as B215: ABS/PETG (NON-metal for Wi-Fi), strain-relieved DIN pigtail,
ventilation slots, mount behind the deck away from the transformer/motors. Route the
motion-sensor lead cleanly to its bracket. Label the DIN pigtail pinout.

---

## 10. Bring-up sequence (A77 Option B)

1. From the service manual, fill the §4 pin map and the dummy-plug bridge. Verify with a
   continuity meter (deck unpowered) against the front-panel switches.
2. Bench ESP **without** deck: confirm Wi-Fi, MQTT topics in WB, each button pulses its
   GPIO/opto-MOSFET (scope/meter the contact closing).
3. Install adapter on the REMOTE CONTROL DIN (keep dummy bridge). Send **STOP** first.
4. Test PLAY, FF, REWIND. Then **RECORD** (PLAY+REC together, gated).
5. Add motion sensor; verify `reels_moving` tracks reality; tune debounce + post-stop delay.
6. Enable the §7 interlock; test PLAY-immediately-after-REWIND → confirm it waits for
   stop + settle before engaging. Confirm no tape spill.

---

## 11. Prior art / references

- **Tapeheads "ReVox A77 WIFI Remote, I am making my own"**: A77 remote-socket wires
  desoldered to relay modules driven by a Raspberry Pi, web page controls all drive
  functions; thread recommends doing it with an ESP/NodeMCU instead (your exact plan);
  notes the relay-interface approach ports to Teac/Ampex transports too.
- **Tapeheads "Revox B77 (mk2) diy remote control advice"**: definitive contact logic —
  momentary switches, each switch passes 24 V to its output, REC fed from PLAY, D3 blocks
  REC-on-PLAY-only; some builders rewired to ground-closure to drop the dummy plug.
- **Commercial adapter (revoxremotes/teacremotes)**: Sony-IR adapter into the remote
  connector controlling Play/Record/Stop/FF/Rewind; needs dummy plug removed. Confirms
  contact-emulation is all that's required (this is the unit you want to replace visually).
- **B77 transport behaviour (Tapeheads transport-problem thread)**: motion-sense point P4
  = 5 V stopped, 0 while moving, returns to 5 V ~0.5 s after full stop — the model for the
  §7 interlock timing.
- **ITAM 3.77 (factory-modified A77)**: counter belt over a motion-sensor pulley/toothed
  wheel feeding an extra plug-in control board — precedent for adding motion sensing to
  an A77.
- **A77 service manual 10.18.1611**: rear item 25 = remote control plug; §7.1 Remote
  Control; §8.1 Rewind modification; §5.9 Drive Control (relay/solenoid function table);
  Diagram 3 Switch Board 1.077.435; end-of-tape LDR R155 / relay-board R118 (auto-stop
  sensitivity — separate from this project).

---

## 12. Relationship to the B215 project

Shared, reuse directly: ESP32 + Wi-Fi + Wirenboard MQTT scaffolding; non-metal casing;
record-safety gating; broker-direct integration; "appears as native WB device" approach.

Different from B215: **dry-contact opto-MOSFET outputs** (not open-collector serial);
**no protocol/capture** (just pulse contacts); **REC=PLAY+REC interlock**; **no soft
power**; **added reel-motion sensor + firmware rewind interlock**; no rich status bus
(feedback is only what your added sensor provides).
