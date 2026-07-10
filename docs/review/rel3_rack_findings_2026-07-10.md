# REL-3 rack sitting #1 — findings (2026-07-10)

**Status: FROZEN EVIDENCE.** First REL-3 rack pass (partial: 13 verified · 4 flagged · 14 not run)
plus the same-day live investigation of the flagged eMotiva incident. Findings carry one-time
`→ tracked as <ID>` pointers per `read-at-start-record-at-completion`; the tasks are scope, this
document is the evidence. All timestamps **UTC** (log time; local = UTC+3).

The rack pass itself continues in a second sitting once the P0 fixes land — REL-3 stays open.

---

## The incident (user report, 10:11–10:15)

START `movie_zappiti` from the scenario card, with the living-room TV already on (household in
use): the eMotiva XMC-2 froze hard — unresponsive to every subsequent network command, front
panel dead, required a wall-unplug. Both SWITCHes "worked" only because the processor was frozen
on the input the movie needed; END did nothing on the eMotiva and the Zappiti kept playing.

## Reconstructed timeline (container log, `docker logs wb-mqtt-bridge`)

```
10:11:23.0  switch_scenario movie_zappiti (room living_room, outgoing None)
10:11:27.8  processor power_on dispatched          (TV.power already satisfied → edge collapsed)
10:11:31.3  power_on returns OK (zones 1+2)
10:11:31.7  ← eMotiva notification: input_source = 'arc'   ARC HANDSHAKE IN FLIGHT
10:11:32.3  TV confirms HDMI2 (state 'HDMI_2')
10:11:34.9  gate timeout: living_room_tv.input never reads 'hdmi2' (3000 ms) → "optimistically"
10:11:35.0  processor set_input source1 → ACKED    ← fired 3.3 s into the ARC handshake
10:12:56    next eMotiva command (source2): NO ack ×3 — device wedged for good
10:14:59    teardown power_off zone1: no ack ×3 (9.3 s); zone2 same (9.2 s)
10:15:17.6  Zappiti IR power toggle dispatched, ROM fired, "success" — physically missed
```

## Root-cause chain

1. **No spacing between `processor.power` and `processor.input`.** The topology edges route that
   spacing through the TV steps (`TV.power → proc.power → TV.input → proc.input`); `_order`
   applies an edge only when both endpoints are in the plan, so a warm TV collapses the chain.
   The only spacing left was an accidental 3 s — itself a bug (finding 2).
2. **The driver watched the danger and drove through it.** `input_source='arc'` was in our state
   3.3 s before `set_input` fired. The XMC-2's ARC/HDMI handshake is documented fragile in the
   driver itself (`Command.ARC` rack-verified 2026-05-30 to hang the device;
   `_power_cycle_for_arc` exists because of it).
3. **Why ARC engaged at all:** the TV (CEC, Sound Out previously configured) claimed the audio
   system the moment it appeared. Five controlled power-ups later in the day pinned the enabling
   condition — see finding 6.

---

## Findings

### F1 — eMotiva firmware wedge: input switch during the ARC handshake `→ tracked as DRV-30`

Evidence above. The fix is driver-level and notification-driven (user requirement: no blind
delays — the device reports everything needed):

- **Post-power-on readiness gate**: after `power_on` (or an observed Off→On), `set_input` waits
  for **notification quiescence** before sending `source_N`. Measured baseline: a clean (non-ARC)
  power-up delivers the full property burst (power, source, audio_input, video_input,
  audio_bitstream, mode — twice) in **< 1 s** (3 samples: 10:57:29, 11:12:31, 11:19:38); the
  incident's ARC claim arrived at **+0.4 s** and was still in flight at **+3.3 s**. Quiescence
  window ~2 s of silence, hard cap ~15 s (safety valve; never deadlock a scenario).
- **`keepAlive` watchdog**: protocol V3 heartbeat, interval **device-advertised = 7500 ms**
  (transponder packet; the library's discovery already parses it, `Property.KEEPALIVE` exists).
  Missed heartbeats → `reachable=False` + fail-fast speakable errors (the teardown burned
  2×9 s of blind retries against a wedged device).
- Switching away from a **settled** ARC via `source_N` is *unverified on hardware* (the incident
  only proves +3.3 s into the handshake is fatal) — the stage-2 probe rides DRV-32.

### F2 — reconciler gate compares canonical target to wire state: never confirms `→ tracked as SCN-14`

Every activation logged `gate timeout: living_room_tv.input did not reach 'hdmi2' within 3000ms`
— the LG driver stores `'HDMI2'`/`'HDMI_2'`, the gate polls for canonical `'hdmi2'`, no
translation in the comparison. The TV-input feedback gate is dead code in practice; every
scenario start burns its full 3 s. Same wire↔canonical disease as the DRV-26 HVAC arc, in the
reconciler's `_wait`.

### F3 — gate timeout is advisory: scenarios report success while failing `→ tracked as SCN-14`

`tv_on_speakers` ran twice (11:12, 11:19); both times the `processor.input → 'arc'` gate
**correctly detected** that ARC never engaged, logged "(proceeding optimistically)", and the
scenario reported **success** — with the sound still on the TV speakers. For a `feedback:true`
capability, a gate timeout is evidence of failure and must surface as a failed step in the
switch result (the same surface the `set_input` no-ack already uses).

### F4 — device-side subscriptions are volatile; the bridge goes permanently deaf `→ tracked as DRV-30`

Emotiva subscriptions live in the **device's** memory. The wall-unplug wiped them; the driver
subscribes once in `setup()` and never again — after the device's cold boot the bridge received
**zero** notifications (state frozen at the 10:11 values) with nothing detecting the silence.
Recovery today required a bridge restart. Fix: the keepAlive watchdog doubles as the recovery
trigger — heartbeat loss → on return (or periodically) re-subscribe + refresh state. Subscribing
against a device in *standby* works and survives standby→on (verified 10:56→10:57).

### F5 — Zappiti teardown: IR power toggle fired but physically missed `→ tracked as DRV-31`

Teardown failure-isolation worked (the wedged eMotiva did NOT block later steps); the Zappiti
toggle was dispatched at 10:15:17.6 and reported success — IR is fire-and-forget
(`feedback:false`) and the frame didn't take. Two manual toggles afterwards played parity games
with believed state. Hardware lane: re-learn ROM26 holding the button (known flaky-capture
recipe); investigate discrete on/off codes to escape toggle parity.

### F6 — the crash reset the eMotiva's CEC configuration; ARC dead until re-enabled `→ tracked as DRV-32`

After the wedge + unplug, ARC refused every path: manual power-on (10:57), the designed
power-cycle (11:12), TV restart + rerun (11:19), even TV Sound Out explicitly set to HDMI-ARC.
A remote OSD probe over the protocol's menu system (`emotivaMenuNotify`; script:
`scripts/emotiva_menu_probe.py`) walked to **Setup → HDMI CEC** and the owner read the panel:
**Enable = disabled, Audio to TV = disabled** — reset by the crash (ARC had engaged at 10:11,
so CEC was enabled before it). Consequences recorded:

- CEC config is **volatile under crash** — the bridge must never assume the ARC path exists
  (F3's honest gate failure is the guard).
- The XMC-2 exposes granular CEC toggles: `Enable · Audio to TV · Power On · Power Off ·
  Volume · Input change`. `Input change` is the exact vector of the 10:11 hijack — the
  re-enable decision is a *configuration design choice*, not just flipping everything on.
- Owner decision 2026-07-10: **CEC restoration is post-release**; `tv_on_speakers` is
  expected-fail (honestly, per SCN-14) until DRV-32.

### Observations (recorded, not filed)

- **Zone2 power toggle flap**: the 10:58:22 `zone2_power_toggle` produced On→Off→On within
  1.4 s in notifications before settling On. Ended correct; watch for recurrence.
- The XMC-2 menu protocol renders **leaf-editor values blank** in `emotivaMenuNotify` XML
  (branch rows carry values fine) — remote *reading* of a setting needs eyes on the panel;
  remote *navigation* works fully.
- Bridge-side protocol facts for reuse: transponder advertises ports + keepAlive; menu/
  menu_update are subscribable; commands ack receipt, not execution (the spec is explicit).

---

## Method note

Five controlled power-ups, three falsified hypotheses (remembered-input, CEC-active-broadcast,
TV-side CEC re-enumeration), one falsified config theory (TV Sound Out), until the menu probe +
panel read produced the config fact. The rack checklist's flag-notes → chat → log-forensics loop
worked; the `service.log` hand-copy path (owner copies `docker logs` output) is the sanctioned
production-read channel.
