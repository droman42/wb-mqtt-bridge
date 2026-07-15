# eMotiva XMC-2 ARC/CEC wedge — community + vendor research

**Frozen evidence, 2026-07-15.** Deep-research sweep (Emotiva official + AVS/AVForums +
Emotiva Lounge + integrator projects), adversarially verified (3-vote refutation per
claim; 64/75 votes upheld, 11 refuted — the refuted ones are recorded below as
corrections so they are never re-cited). Supports **DRV-31/32** (firmware/CEC bench),
**DRV-39** (silence-while-busy), and the **LIB** batch. Confidence tags are the
verification pass's, not marketing.

## The headline finding — a second integrator hit our exact failure (HIGH confidence)

The official **openHAB Emotiva binding** documentation states, verbatim:

> "Emotiva processors have **limited processing power**, so if the binding **subscribes
> to all channels simultaneously the device might grind to a halt after a while,
> requiring a manual reboot** of the device."
> — https://www.openhab.org/addons/bindings/emotiva/ ("Dynamic channels…" section)

This is an independent integrator documenting **the same wedge class we hit**: too much
concurrent network-control load → the processor becomes unresponsive → physical reboot.
Their **remedy is load reduction**: dynamically enable/disable channels rather than
subscribing to everything, plus load-shedding flags (`activateFrontBar` / `activateOSDMenu`
/ `activateZone2`) that default **off**. Two design consequences for us:

1. Our driver subscribes to **all 9–10 properties at once**, and the `power_on` tail
   **re-subscribes to all of them again** mid-transition. Per this source that is a
   documented device-killer independent of the ARC window — it is *load*, and the unit
   has "limited processing power." This **corroborates DRV-39 from a second angle** and
   adds a new lever: **subscribe to fewer channels**, not just "don't send while busy."
2. The same binding uses a **7500 ms keepalive, 2-minute retry, → OFFLINE on keepalive
   loss** (HIGH confidence) — byte-for-byte our watchdog's design. openHAB is a sibling
   implementation of the same protocol and independently landed on the same numbers,
   which validates our keepalive/watchdog parameters as correct.

## The "ready/settled" signal — nobody documents one (HIGH confidence, by absence)

Across every source (Emotiva official, forums, the openHAB + pokowaka + uc-intg
integrator projects, Emotiva's own Control4 driver docs) **there is no documented
"processor is ready / has settled" indicator and no recommended post-power-on or
post-input command delay/pacing.** Multiple sources explicitly note the absence. So:

- Our plan to **watch `audio_bitstream` (and `audio_bits`/`video_format`/`video_space`)
  as a settle proxy would be novel** — the notification channels exist and reflect
  input/format state (HIGH confidence: the openHAB channel list confirms
  `audio-bitstream`, `video-format`, etc. as read-only state channels), but **no one
  documents using them as a readiness gate.** DRV-32 would be characterizing new ground,
  not copying a known recipe. Worth doing, but expect to derive the pattern ourselves.

## Firmware: 3.2 rewrote the HDMI layer, but efficacy for lockups is UNCONFIRMED

- **CONFIRMED (HIGH):** Emotiva v3.2 (released **2023-05-17**, not 05-11) ships "all new
  rewritten and improved HDMI firmware… Enhanced stability and reliability for HDMI
  switching… Improved consistency and reliability with HDMI-CEC and ARC support…
  Enhanced stability… when switching audio decoding formats." (emotiva.com 3.2 blog + the
  5/17/23 bulletin on device.report.) The audio-decoding-format line is directly relevant
  to the input/ARC-change window.
- **REFUTED / do not overclaim (the adversarial pass killed this):** framing 3.1 or 3.2
  as fixing *lockups / network unresponsiveness* "specifically." The release notes list
  HDMI-CEC as **one of ~5 stability categories**, and **never mention lockups, freezing,
  network unresponsiveness, or power-cycle recovery.** No owner report was found stating
  "3.2 fixed the lockups." → **Flash 3.2 (DRV-32) as a genuine improvement, but do NOT
  assume it resolves the wedge; the bridge-side fixes (DRV-39/LIB) carry the load.**
- **eARC is gated by an HDMI *board* generation, not firmware** (HIGH): a non-eARC board
  vs the eARC HDMI-2.0b board (units after ~Nov 2021, or a paid upgrade). v3.2 auto-enables
  eARC only on eARC-board units. So our unit's board generation determines eARC
  availability regardless of the flash.
- **Correction (killed claim):** "XMC-2/RMC-1/RMC-1L HDMI *hardware* is essentially the
  same" — FALSE; the *firmware* is shared but there are two distinct HDMI board
  generations. (Firmware-shared → RMC-1 findings still transfer at equal firmware.)

## CEC/ARC config + interop (the physical bench inputs for DRV-32)

- **CONFIRMED (HIGH):** on the XMC-2, **ARC and CEC live on HDMI Output 2** (the primary
  output; it was Output 1 on the XMC-1). The ARC handshake is tied to that specific port.
- **CONFIRMED (central):** an **RMC-1L owner hit a CEC audio failure** (the unit stuck
  showing "CEC:Audio to TV" where the sound mode should be) that **required a physical
  power cycle**; the fix was to **disable HDMI/CEC in the Setup menu**. Directly parallels
  our incident (CEC hijack of audio, power-cycle recovery).
- **CONFIRMED (supporting):** correlated with an **LG TV's SIMPLINK** (LG's CEC); toggling
  SIMPLINK did not clear it without the power cycle. Matches our LG-driven ARC grab.
- **CONFIRMED (supporting):** community recommendation for XMC-2 + LG OLED is **CEC on +
  ARC on (XMC-2 HDMI out 2), CEC + ARC on the TV, eARC OFF.**
- **Community remedy when CEC misbehaves: turn CEC off** (whole or per-feature).
- **Correction (killed claim):** "HDMI/CEC defaults to ON" — NOT established; it rests on
  one hedged "I think" forum post and is contradicted by sources saying many CEC functions
  are **disabled by default and enabled individually.** Treat our unit's CEC state as
  **must-read-at-the-bench**, not assumed.
- **Correction (killed claim):** the "unplug both units, wait 15 min" power-outage ARC
  wedge — real quote but **misattributed: that owner runs an XMC-1, not an XMC-2.** Do not
  cite it as XMC-2 evidence.

## What the research did NOT find (honest gaps)

- **No source describes the precise failure mode we logged** — a *network UDP command
  sent during the ARC handshake* wedging the unit. The closest primary evidence is the
  openHAB "subscribe-to-all → grind to a halt" load warning (concurrent-load framing, not
  timing-during-handshake). Our log forensics remain the primary evidence for the
  timing-specific trigger; the community confirms the *ingredients* (limited CPU, CEC
  fragility, power-cycle recovery) but not that exact sequence.
- **No integrator command-pacing recipe** and **no readiness signal** — confirming the
  design work is ours to originate (DRV-39 + DRV-32), not to copy.

## Net effect on the tasks

- **DRV-39** gains a second, independent rationale (openHAB "limited processing power")
  and a new sub-lever: **reduce subscription breadth**, not only "stay silent while busy."
- **DRV-32** should read the CEC menu state at the bench (not assume defaults), confirm
  ARC/CEC on HDMI Output 2, set eARC per the board generation, and — since no one
  documents a settle signal — **characterize `audio_bitstream`/`video_format` transitions
  during ARC engagement ourselves** as the candidate readiness gate.
- **Firmware 3.2 stays worth flashing** but is **not** a guaranteed wedge fix — the
  bridge-side invariant is the load-bearing fix.

## Primary sources

openHAB Emotiva binding — https://www.openhab.org/addons/bindings/emotiva/ ·
Emotiva v3.2 notes — https://emotiva.com/blogs/news/rmc-1-rmc-1l-and-xmc-2-firmware-3-2-now-available ·
v3.1 notes — https://emotiva.com/blogs/news/rmc-1-rmc-1l-and-xmc-2-firmware-3-1-now-available ·
eARC board — https://emotiva.com/products/earc-hdmi-2-0b-upgrade-board ·
Emotiva Lounge HDMI-CEC/ARC — https://emotivalounge.proboards.com/thread/59749/hdmi-cec-arc ·
Emotiva Lounge ARC/XMC+LG — https://emotivalounge.proboards.com/thread/57133/arc-xmc-wit-lg-oled ·
AVForums RMC/XMC experiences — https://www.avforums.com/threads/emotiva-rmc-1-rmc-1l-xmc-2-discussion-help-experiences.2252463/ ·
AVS XMC-2 owners — https://www.avsforum.com/threads/the-official-emotiva-xmc-2-owners-thread.3090736/ ·
Network protocol spec (Lounge) — https://emotivalounge.proboards.com/thread/47166/emotiva-network-control-protocol-specification ·
integrator libs — github.com/pokowaka/xmc, github.com/mase1981/uc-intg-emotiva
