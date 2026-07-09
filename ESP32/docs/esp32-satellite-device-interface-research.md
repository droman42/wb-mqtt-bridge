# ESP32 Wi-Fi Satellite — Per-Device Interface & Power Research

**Purpose:** design reference for a family of ESP32 "satellite" boards, one per vintage device, each of which:
1. receives commands over Wi-Fi (with OTA firmware updates after install), and
2. controls the host device via **either its remote/control connector or by injection at the IR receiver/controller**, and
3. draws power **from the host device itself** — no external supply.

**Reliability convention used throughout:** every claim is tagged
`[CONFIRMED]` (stated in a service manual / multiple independent sources),
`[INFERRED]` (strong engineering inference from architecture, not explicitly documented), or
`[VERIFY]` (must be measured on the bench or read from the service manual before committing copper).
Treat anything OCR-extracted from a scanned manual as `[VERIFY]` until eyeballed against the page image — a smudged digit reads as a confident wrong value.

---

## Cross-cutting design: the common satellite core

All four boards share one core; only the **front-end** (control driver + power conditioning) changes per device.

**Core (common to all four):**
- ESP32 module (Wi-Fi), 3.3 V logic.
- Local energy reservoir: bulk cap (hundreds of µF to a few thousand) sized so Wi-Fi TX bursts (300–500 mA spikes) and the **sustained OTA load** come from the cap/local regulator, not the host rail.
- Decoupling from the host rail: ideal-diode or series element so transients stay local and never sag the host's supply.
- Power posture: modem-sleep / low-DTIM so the board stays *associated and pingable* (needed to receive an OTA push) while keeping average draw low. Note the tension: "reachable for OTA" costs more average current than "wake only to inject" — size the tap for the reachable-idle case, not the deep-sleep case.
- **Dual-bank (A/B) OTA with verify-before-swap**, so a power dip mid-flash rolls back to the known-good image instead of bricking a board you can only reach over Wi-Fi.

**Front-end matrix (what differs per device):**

| Device | Control path | Control electrical driver | Power source | Isolation of that source |
|---|---|---|---|---|
| Revox A77 Mk4 | Remote DIN (switch-closure) | Opto/relay contact-closure across button lines | **Pin 7 of remote DIN, +27 V @ 150 mA** | Isolated linear secondary `[CONFIRMED-ish]` |
| Pioneer CLD-D925 | SR control jack **or** IR-demod injection | Opto open-drain pull-low (IR node) / buffered drive (jack) | Internal +5 V logic secondary | Isolated SMPS secondary `[CONFIRMED]` (PCB marks PRIMARY/SECONDARY) |
| Revox B215 | Serial link socket **or** IR | Level-shift **or** RS-232 transceiver — TBD | Internal +5 V logic rail | Isolated linear secondary `[INFERRED]` |
| Panasonic NV-FS90 | IR-demod injection (control terminal unconfirmed) | Opto open-drain pull-low | Internal syscon 5 V secondary | **`[VERIFY]` — dominant risk** |

**The single rule that governs safety:** pick ONE ground domain per board and commit. If the board is powered from the host's internal secondary, the whole board floats in that domain — then the control driver into that same domain needn't be isolated, but *any other external connection must be*. Your OTA-after-install workflow resolves this cleanly: the only bench-time earth-referenced connection (USB programmer) exists **before** install and never coexists with the board being wired into the host. Wi-Fi is galvanically isolated by nature (radio), so once installed there is no second ground path.

---

## 1. Revox A77 Mk4 (reel-to-reel, ~1967–1977)

**Architecture:** solid-state, **electromechanical relay logic** — no microcontroller, no IR receiver, no command bus. `[CONFIRMED]`

### Control interface — remote DIN, switch closure
- Rear socket #25: **10-pin Hirschmann WIST 10** DIN (90° DIN plug). `[CONFIRMED]`
- **All transport push-button functions are available via this socket.** `[CONFIRMED]`
- It is a **contact-closure** interface: the remote/dummy plug **shorts pins 1 & 2** to satisfy the STOP line; if that short is absent the relay logic behaves as if STOP is held down. `[CONFIRMED]`
- Implication: you emulate button presses by **momentarily closing the relevant pin to the switch common** — via small-signal relays or opto-MOSFETs on the ESP32 board. No serial protocol, no timing-critical carrier.
- `[VERIFY]` exact pin→function mapping (which pins are Play/FF/Rew/Stop/Record) from the service manual remote-control schematic (fig. 7.1-86) and the Obsolete-Media "A77 Remote Control Plug" pinout page.

### Power tap — trivial, on the same socket
- **Pin 7 = +27 Vdc, 150 mA max.** `[CONFIRMED]` (documented as a slide-projector supply). Fed by the 27 V rail (violet DF1) that also drives the transport board.
- Budget check: ESP32 + Wi-Fi peak ≈ 1.7 W ≈ ~65 mA drawn at 27 V through a buck → comfortably inside 150 mA. Reservoir cap still advisable for TX spikes, but headroom is generous.
- **No internal soldering required** — both control and power are on the rear DIN. This is the only one of the four you can do entirely from the back panel.

### Isolation / safety
- Linear mains-transformer supply, rails ~**21 V and 27 V**. `[CONFIRMED]`
- DC ground is **not** the chassis (service community explicitly warns "don't use the chassis" as a measurement reference) → isolated secondary. `[CONFIRMED-ish / VERIFY on your unit]`
- No primary-side hazard at the remote socket; still confirm secondary-gnd vs. earth on your unit before tying to anything.

### PCB front-end for the A77
- 27 V → 3.3 V **buck** (not linear — 27→3.3 linear wastes ~88%).
- N contact-closure drivers (opto-MOSFET or reed/relay) across the mapped button pins, sharing the switch common.
- Everything floats in the A77 secondary domain; program on the bench before installing.

### Sources & community links
- Service manual, full-text (searchable, remote-plug fig. 7.1-86, +27 V pin-7 note): https://archive.org/stream/studer_Revox_A77_Serv/Revox_A77_Serv_djvu.txt
- Service manual (ManualsLib, browsable): https://www.manualslib.com/manual/899158/Revox-A77.html — index of all 10 A77 manuals: https://www.manualslib.com/products/Revox-A77-3742846.html
- Service manual (Manualzz, rear-panel connector list): https://manualzz.com/doc/23698898/revox-a-77-service-manual-2
- siber-sonic A77 repair tips (dummy-plug pins 1&2, +21 V, links out to the Obsolete-Media "A77 Remote Control Plug Schematic" pinout page): https://siber-sonic.com/broadcast/RevoxA77tips.html
- HiFi Engine (manual + owner comments on the dummy plug / Hirschmann connector): https://www.hifiengine.com/manual_library/revox/a77.shtml
- Tapeheads — A77 PSU thread (21 V / 27 V rails, "don't use chassis as reference"): https://www.tapeheads.net/threads/revox-a77-power-supply.68340/ · page 3 (DF1 violet → transport + remote pin 7): https://www.tapeheads.net/threads/revox-a77-power-supply.68340/page-3
- Tapeheads — A77 MK1 PSU thread: https://www.tapeheads.net/threads/revox-a77-mk1-power-supply.77697/
- Tapeheads — A77 board/pin letter-code meanings (G = remote socket, etc.): https://www.tapeheads.net/threads/revox-a77-manual-board-pins-codes-meaning.108200/

---

## 2. Pioneer CLD-D925 (CD/CDV/LD player, 1996)

**Architecture:** SMPS with **transformer-isolated secondary** (PCB explicitly marks PRIMARY / SECONDARY regions). Mode-control IC **PD3337A = IC101 (FLKY assy)**. `[CONFIRMED, from service manual]`

### Control option A — rear CONTROL jack (SR bus)
- Rear **CONTROL IN/OUT** 3.5 mm minijacks: **JA3/JA4, part RKN1004** ("REMOTE CONTROL JACK"). `[CONFIRMED]`
- Carries Pioneer's SR-style **demodulated** control stream between stacked components. `[INFERRED]`
- Non-invasive (back-panel only), sits on the isolated secondary → safe low-voltage node.
- `[VERIFY]` the waveform: level, idle polarity, framing. Scope CONTROL OUT while pressing a real remote button to capture the format CONTROL IN expects. The manual confirms the jack exists but does not specify its electrical protocol.

### Control option B — IR-demod injection (best-understood)
- Internal IR receiver module **GP1U28X** on the PWSB assy, wired via **CN301 (9-pin, 1.25 mm FJ)**. `[CONFIRMED]`
- GP1U28X output: **idle HIGH at 5 V, pulses LOW during carrier** (active-low), 5 V logic domain. `[CONFIRMED — standard for this module family]`
- Remote stream lands at **PD3337A pin 28 ("SEL IR / Remote control input")**, 5 V CMOS domain (IC101 pin 1 = VCC = +5 V). `[CONFIRMED, from IC pin table]`
- Inject with **open-drain / wired-AND pull-low**: pull the node low to simulate a burst, float otherwise. Never drives high → no contention with the original receiver, front-panel remote keeps working.
- Firmware: RMT outputs just the **demodulated envelope** of the Pioneer CU-CLD115 code (mark = pull low, space = release) — **no 40 kHz carrier generation needed** (reuses your existing IR-project timings).

### Power tap
- **+5 V logic secondary rail** (feeds IC101, GP1U28X, etc.). `[CONFIRMED as isolated secondary]`
- Solder tap: +5 V and GND at a convenient secondary-side point (near IC101 / a logic connector).
- Do **not** hang the ESP32 raw on this rail — reservoir cap + decoupling so Wi-Fi/OTA transients don't glitch the mode-controller.
- `[VERIFY]` rail headroom: measure loaded/unloaded, and specifically against the **OTA sustained draw**, not just an injection burst.

### Isolation / safety
- Secondary is transformer-isolated; **never probe the SMPS primary** (mains-hot). `[CONFIRMED]`
- `[VERIFY]` secondary-gnd vs. earth on your unit.

### PCB front-end for the CLD-D925
- Opto open-drain injector into GP1U28X node (LED-on = pull low), giving level shift + isolation + pull-low-only in one block. (Or a buffered driver into the CONTROL jack once you've scoped its polarity.)
- 5 V → 3.3 V (LDO or small buck) + reservoir + decoupling.
- If board is powered from the +5 V secondary, it floats with the player; the injector then needn't be isolated, but keep the OTA-only, no-second-ground discipline.

### Sources & community links
- Uploaded CLD-D925 service manual, order no. RRV1546 (your local scan).
- ManualsLib HTML mirror — page 52 = PD0237A2 mechanism-control-IC pin table: https://www.manualslib.com/manual/3316462/Pioneer-Cld-D925.html?page=52 · manual root: https://www.manualslib.com/manual/911101/Pioneer-Cld-D925.html
- HiFi Engine (spec corroboration): https://www.hifiengine.com/manual_library/pioneer/cld-d925.shtml
- LaserDisc Database manual repository (scan source): https://manuals.lddb.com/LD_Players/Pioneer/CLD/CLD-D925/
- elektrotanya (SM download): https://elektrotanya.com/pioneer_cld-d925_rrv1546.pdf/download.html
- Tom's Guide forum thread (owner discussion, door/tray issues): https://forums.tomsguide.com/threads/pioneer-cld-d925-serivice-manual.246696/

---

## 3. Revox B215 (cassette deck, 1985–~1990)

**Architecture:** automation by **three Philips microcontrollers**, auto-calibration, non-volatile memory. Both a **serial link** and an **IR receiver** fitted as standard. `[CONFIRMED]`

### Control option A — serial link socket (preferred)
- Rear **"Serial Link Socket"**, documented in the operating manual **section 5, page 35**. `[CONFIRMED]`
- Explicitly framed as **remote control by a computer via its serial port**. `[CONFIRMED, review sources]`
- Rich command set: the B215 has **"hidden" functions reachable only via serial or IR**, with no button on the Revox handset — a strong reason to target serial over IR here. `[CONFIRMED, owner community]`
- `[VERIFY] — CRITICAL:` the **electrical layer is undetermined** in all web sources. "Serial port" colloquially suggests RS-232, but a Studer/Philips control bus of this era could be low-voltage TTL or a proprietary bus. This decides your entire front-end:
  - true RS-232 (±12 V) → needs a **MAX3232-class transceiver** (wiring ±12 V straight to a GPIO destroys it);
  - 5 V TTL → needs only a **level shift** (ESP32 RX is not 5 V tolerant).
  - Read page 35 for pinout + levels + baud/framing; cross-check against the enthusiast reverse-engineering community (revoxremotes.com and Revox forums have characterized this bus commercially); then meter the pins.

### Control option B — IR receiver
- Fallback if serial proves awkward; same open-drain pull-low injection pattern as the Pioneer. Loses access to the serial-only hidden functions.

### Power tap
- Linear mains-transformer supply → **isolated secondary**, +5 V logic rail for the microcontrollers. `[INFERRED]`
- `[VERIFY]` exact rail location, voltage, and spare current from the service manual (HiFi Engine hosts it) + meter.

### Isolation / safety
- Transformer-based linear supply → isolated secondary. `[INFERRED — verify secondary-gnd vs earth]`.

### PCB front-end for the B215
- **Populate-on-verify front-end:** footprint for *both* a MAX3232 transceiver and a plain level-shifter, populate whichever the page-35 spec dictates. This is the one board whose front-end you should lay out to accommodate either outcome, because the electrical layer is the biggest open question.
- 5 V → 3.3 V + reservoir + decoupling.
- Variant note: confirm your unit is B215 vs **B215S** — some functions/behaviors differ across revisions.

### Sources & community links
- Operating manual, ManualsLib — **page 35 = "Serial Link Socket"** (section 5, Remote Control): https://www.manualslib.com/manual/1999803/Revox-B215.html?page=35
- HiFi Engine (manual + owner comments): https://www.hifiengine.com/manual_library/revox/b215.shtml
- Hi-Fi Classic review (states "remote control by a computer using its serial port"): https://www.hifi-classic.net/review/revox-b215-240.html
- Reverb listing (same serial-port statement): https://reverb.com/item/4210149-revox-b215-vintage-cassette-deck-1990s
- Wikipedia (three Philips µCs, B215/B215S/A721 variants, history): https://en.wikipedia.org/wiki/Revox_B215 · HandWiki mirror: https://handwiki.org/wiki/Engineering:Revox_B215
- **AudioKarma — "hidden functions reachable only via serial or IR"** (B215 vs H1 thread): https://audiokarma.org/forums/threads/revox-b215-vs-revox-h1-cassette-tape-deck.589367/
- **revoxremotes.com — commercial B215 control/remote reverse-engineering** (confirms the interface is community-characterized; good lead for the serial command set): https://www.revoxremotes.com/Revox_B215.htm
- premium-hifi (serial link + IR fitted as standard; restoration notes): https://www.premium-hifi.com/en-gb/studer-revox-b215-tape-recorder-cassette-deck
- Revox official Classic product page (spec sheet): https://revox.com/en/classic/classic-products/173/b215-cassette-deck

---

## 4. Panasonic NV-FS90 (S-VHS Hi-Fi VCR, ~1990)

**Architecture:** mains VCR with syscon microcontroller + IR receiver. **This is the highest-risk device for the power-tap requirement and the one with the least confirmed data — treat every power/ground claim as `[VERIFY]`.**

### Control interface
- IR receiver + syscon µC present (standard for the class). `[INFERRED]`
- **IR-demod injection** is the reliable path: same open-drain pull-low into the demodulator-output node feeding syscon, same envelope-only firmware approach as the Pioneer.
- `[VERIFY]` from the service manual: the IR receiver module identity, its output node/polarity, and the syscon remote-input pin.
- `[VERIFY]` whether a rear **edit/control terminal** exists (high-end editing decks sometimes expose a 5-pin edit or Control-S style jack). Not confirmed in available sources — check the SM rear-panel/connector section. If present and on the isolated secondary, it may be a cleaner path than IR.

### Power tap — **the dominant open question**
- Panasonic S-VHS supplies of this era are transformer-based with multiple `UNREG_*V` secondaries → a syscon 5 V secondary rail almost certainly exists. `[INFERRED]`
- **`[VERIFY] — non-negotiable:` VCR grounding can be mixed.** Before tapping *anything*, meter the candidate rail's ground against mains earth and against chassis, power-off then power-on, to confirm the syscon secondary is genuinely isolated. A VCR is exactly the class of device where a non-isolated or "hot" section is plausible, and tying a Wi-Fi board (even OTA-only) to a non-isolated node is a genuine hazard.
- If the syscon rail proves **not** cleanly isolated: fall back to an **isolated DC-DC** from whatever rail is available, or (violating the "no external supply" goal only for this one deck) a small external supply + fully optoisolated injector. Do not force the power-from-device requirement onto a non-isolated rail.
- Solder tap location: TBD from the SM once the isolated 5 V rail is identified.

### Isolation / safety
- **Assume mains hazard until proven otherwise.** Never probe the primary side. The whole viability of "power from the device" here hinges on the isolation measurement above.

### PCB front-end for the NV-FS90
- Opto open-drain injector into the IR-demod node (isolation here is doubly valuable given the grounding uncertainty).
- Power stage designed to accept **either** a direct tap (if isolation confirmed) **or** an isolated DC-DC (if not) — lay out for both.

### Sources & community links
- Service manual (elektrotanya, SM download): https://elektrotanya.com/panasonic_nvfs90.pdf/download.html
- Service manual (Internet Archive, "NVFS90BEB SM PANASONIC GB"): https://archive.org/details/manual_NVFS90BEB_SM_PANASONIC_GB
- Service manual (eserviceinfo): https://www.eserviceinfo.com/downloadsm/98236/panasonic_hfe%20panasonic%20nv-fs90%20service.html · (Scribd copy): https://www.scribd.com/document/756995828/hfe-panasonic-nv-fs90-service-113810
- HiFi Engine (manual + owner repair comments, e.g. C2311 audio-dropout fix): https://www.hifiengine.com/manual_library/panasonic/nv-fs90.shtml
- User manual, HTML (petervis): https://www.petervis.com/manuals/panasonic-nv-fs90/nv-fs90.html
- Generic Panasonic S-VHS PSU topology (UNREG_*V secondaries) — digitalFAQ VCR-repair: https://www.digitalfaq.com/forum/vcr-repair/7056-panasonic-vhs-power.html · Tapeheads late-80s Panasonic PSU thread: https://www.tapeheads.net/threads/late-80s-panasonic-quasar-vcr-power-circuit-1000-series-help.90213/
- Replacement-remote listing (button set, for IR-command reference): https://remotes-world.com/products/panasonic-vcrdvr-nv---fs-90

**FS90-specific control/isolation detail still needs the service manual PDF read directly — this device is the least resolved by web research alone.**

---

## Consolidated "close-the-gaps" bench checklist

Per device, before committing a board layout:

1. **A77:** map remote-DIN pins to transport functions (SM fig. 7.1-86 / Obsolete-Media pinout); confirm pin-7 +27 V present on your unit; confirm secondary-gnd ≠ chassis. *(Lowest effort — mostly confirmation.)*
2. **CLD-D925:** scope CONTROL-OUT envelope (polarity/level) **or** confirm GP1U28X node idle-high/pull-low; measure +5 V rail headroom under **OTA** load; confirm secondary-gnd vs earth.
3. **B215:** read manual page 35 for serial pinout + **electrical level (RS-232 vs TTL) + baud/framing**; cross-check protocol against Revox enthusiast reverse-engineering; identify + measure the 5 V rail; confirm B215 vs B215S.
4. **NV-FS90:** from SM — IR module + syscon input pin, any rear edit terminal, isolated 5 V rail location; **then meter that rail's isolation from mains/earth before trusting it** (gating decision for the whole power approach on this deck).

## Where each device's docs live (non-PDF where possible)
- **Typeset layers** (specs, IC pin tables, connector sections): browsable HTML on **ManualsLib** (https://www.manualslib.com); corroborate specs on **HiFi Engine** (https://www.hifiengine.com/manual_library/). Treat ManualsLib text as OCR to verify, not ground truth.
- **Schematic sheets / hand-drawn detail:** only in the scanned PDFs — **elektrotanya** (https://elektrotanya.com), **Internet Archive** (https://archive.org), **HiFi Engine**, **LaserDisc Database manuals** (https://manuals.lddb.com). No reliable text transcription exists — that's diagram understanding, not OCR. Use scan + bench.

## Community hubs worth posting to (reverse-engineering / pinout help)
These are the forums where the switch-closure mappings, serial command sets, and isolation gotchas for these machines have already been discussed — search first, then ask with your specific gap:
- **Tapeheads** (Revox / reel-to-reel / cassette, deep transport + PSU knowledge): https://www.tapeheads.net
- **AudioKarma** (vintage hi-fi, Revox serial/IR hidden functions): https://audiokarma.org
- **digitalFAQ VCR Repair** (Panasonic S-VHS power/grounding): https://www.digitalfaq.com/forum/vcr-repair/
- **EEVblog Repair** (general vintage-supply/isolation questions): https://www.eevblog.com/forum/repair/
- **revoxremotes.com** (commercial Revox control adapters — evidence the B215/A77 interfaces are already characterized): https://www.revoxremotes.com
- **LaserDisc Database forums / lddb.com** (Pioneer LD players): https://www.lddb.com
- **Obsolete Media — "Tape Deck Remote Control Plugs"** subsite (A77 remote-plug pinout; reached via the siber-sonic tips page linked in §1).
