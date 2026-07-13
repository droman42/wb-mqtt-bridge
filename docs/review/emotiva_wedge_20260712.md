# eMotiva XMC-2 wedge #2 — 2026-07-12 19:50, `movie_appletv` cold start

**Frozen evidence** (chat-session log forensics, 2026-07-13; source:
`service.log.20260712.log`, owner-copied from the WB7 — 138 101 lines / 20 MB, sits
beside the repo checkout, not committed). Findings → tracked as **DRV-38** (wedge +
topology-layer review) and **OPS-25** (log hygiene).

## Incident timeline (log line numbers from the source file)

| Time 2026-07-12 | Evidence | Event |
|---|---|---|
| 19:50:32.646 | l.113063 | `movie_appletv` start in living_room (outgoing=None). Plan: Apple TV power_on, amp IR power, eMotiva main power_on, eMotiva zone2 power_on, LG set_input_source. **No eMotiva set_input step** — believed input already `source2`, confirmed by the device at :37.14 (`source = HDMI 2`). TV already on (no TV power step) — the known-dangerous gesture. |
| 19:50:36.87–36.94 | l.~113180 | eMotiva `power_on {zone:1}` sent, **acked** attempt 1; full healthy property burst follows. |
| 19:50:38.595 | driver DEBUG | Uncommanded `source → HDMI ARC` notification — the TV grabs ARC; **the driver records `input_source: 'arc'` at :38.651**. The CEC/ARC handshake is live and bridge-visible. |
| 19:50:40.639 | socket_mgr | **Last packet ever received on notifyPort** (a keepAlive). |
| 19:50:40.938 | l.~113540 | `power_on {zone:2}` → `zone2_power_on` sent — 4.07 s after main power-on, **2.3 s into the visible ARC handshake**, ungated. |
| 19:50:41.040 | protocol | `zone2_power_on` **acked — the last thing the XMC-2 ever said.** |
| 19:50:41.658 | l.113560 | Scenario declared successfully switched. |
| 19:51:06.95 | l.113594 | DRV-30 watchdog: *"heartbeat lost after 26s of silence"* → unreachable. Every re-subscribe from 19:51:08 onward times out (controlPort dead); the 2 s/3 s/4.5 s retry ladder repeats for the rest of the log. |

## Finding 1 — the DRV-30 readiness gate guards ONE command path (the trigger is bridge-side)

`_await_input_ready` (`backend/src/wb_mqtt_bridge/infrastructure/devices/emotiva_xmc2/driver.py:505`)
is invoked from **exactly one call site: `handle_set_input` (driver.py:1377)**. The power
handlers — including `power_on {zone:2}` — never consult it. The driver's own state
carried `input_source == 'arc'` (the condition the gate's comment calls the known-fatal
window, driver.py:527-529) when it fired `zone2_power_on` into the handshake.

Coverage-gap provenance: REL-3 (2026-07-10) validated the fix on the `movie_zappiti`
path, whose post-power eMotiva step IS a `set_input` — gated, passed. `movie_appletv`
needs no input switch, so its post-power step is the ungated zone-2 power command; the
REL-3 findings record contains zero appletv mentions — this plan shape never ran live
after DRV-30. The wedge class was declared fixed on evidence from one command path.

**Not a config regression:** the `processor:zone2 → mf_amplifier:aux2` topology link and
the zone-2 capability predate the monorepo (`f187b96`); `movie_appletv.json` last changed
at the SCN-8 rename (2026-07-06, `4fc5895`). The firmware ARC-window vulnerability itself
stands (the 3.2-flash task DRV-31/32 keeps its full value; note: a wedge + wall-unplug
recovery resets the XMC-2's CEC config — re-check after recovery, per the REL-3 record).

## Finding 2 — the protection lives at the wrong layer (→ the topology-layer review)

The plan is derived from the topology; which command a device receives after power-on is
an emergent property of the diff (input already correct ⇒ the "next command" changes
identity). Guarding *one handler* can therefore never cover the window — the guard must
hold for **whatever** command the plan emits next. Today's layering:

- per-device fatal-window knowledge: inside one handler (`handle_set_input`);
- inter-step pacing: topology `ordering` edges with `delay_ms` (e.g. the 5 s
  `processor.input → video.power` settle, `3ae31eb`) — authored per edge, blind to
  runtime windows;
- step confirmation: SCN-14/SCN-15 gates — they confirm *outcomes*, they do not hold
  *entry* into a device's unready window.

None of these is a per-device "not ready for ANY command" concept. Review scope filed
under DRV-38: whether readiness belongs at the dispatch/executor layer as a first-class
device property, audit of other devices with post-power vulnerable windows, and whether
topology `delay_ms` settles are masking similar gaps elsewhere.

## Finding 3 — log volume (20 MB/day) is root-DEBUG × the DRV-30 keepAlive machinery

- `system.json` ships `log_level: "DEBUG"` (pre-monorepo, never production-tuned).
- Since DRV-30 subscribed the 7.5 s keepAlive, every beat emits ~9 DEBUG lines
  (`pymotivaxmc2` socket_mgr → xmlcodec → dispatcher ×2 + driver). Measured: 45 258
  lines mention keepAlive; `pymotivaxmc2` 68.5 k + eMotiva driver 22.8 k ≈ **two-thirds
  of the 138 k-line file is idle eMotiva chatter** (~5.5–6 k lines/hour, flat around the
  clock — background, not events). The `[EMOTIVA_DEBUG]`/`[MQTT_DEBUG]`/`[SCENARIO_DEBUG]`
  forensic tags from the REL-3 investigation are also still active. → OPS-25.
