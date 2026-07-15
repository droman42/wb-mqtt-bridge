# eMotiva XMC-2 wedge #3 — 2026-07-14 08:07, startup restore of `movie_appletv`

**Frozen evidence** (investigation 2026-07-15: log forensics over `../logs/service.log*`
(owner-copied from the WB7), the pymotivaxmc2 0.7.0 source + Emotiva protocol doc in
`../pymotivaxmc2/`, and the driver git history). Findings → tracked as **DRV-39**
(power-on tail), **DRV-40** (probe backoff), **SCN-18** (boot-restore policy),
**LIB-1/LIB-2/LIB-3** (pymotivaxmc2 fixes — new LIB workstream), **OPS-29** (forensic
logging middle ground). The firmware task (DRV-31/32, the 3.2 flash) and the DRV-38
rack replay stand unchanged.

## Incident timeline (from `service.log`, the post-redeploy session)

| Time 2026-07-14 | Evidence | Event |
|---|---|---|
| ≤ 08:04:54 | 20260713/20260714 logs | Device healthy for days — keepAlive every 7.5 s through the clean shutdown (old code, DEBUG; 56 620 keepalive lines on Jul 13 alone). Zero pymotivaxmc2 warnings. |
| 08:06:20 | l.1 | Redeploy restart. New code confirmed in-image: `locveil_bridge` logger names, `pymotivaxmc2` pinned to WARNING (OPS-25), i.e. DRV-38(a) + SCN-16/17 were deployed. |
| 08:07:16 | l.88–90 | Fresh connect + subscribe **succeeded** — device responsive. |
| 08:07:44.3 | l.1053–1055 | **Boot-time scenario restore**: `movie_appletv` was persisted active → the bridge re-runs the cold-start plan unattended (Apple TV wake, eMotiva power…). |
| 08:07:44.481 | l.1060 | eMotiva **main-zone `power_on` sent** (gate-exempt by design — it *starts* the readiness window). |
| 08:07:47.780 | l.1187–1189 | First anomaly, **+3.3 s after power-on**: `Timeout waiting for data on port controlPort after 2.0 seconds` → `Missing properties {all 9} on attempt 1, retrying` — the power_on handler's **own** post-send status batch (`_refresh_device_state`) timing out and re-sending into the booting unit. |
| ~08:07:53 | (derived) | Last packet the device ever sent (watchdog counts 25 s of silence back from 08:08:18). |
| 08:08:18.095 | l.1295 | DRV-30 watchdog: `heartbeat lost after 25s of silence` — detection worked exactly as designed (3 × 7.5 s). |
| 08:08:18.121 | l.1296 | `Unexpected response tag: emotivaUpdate (expected 'emotivaSubscription')` — a late status-query reply dequeued by the subscribe probe: **the library's shared-queue cross-talk observed in production.** |
| 08:08–20:46 | counts | The re-subscribe probe loop runs **2 455 cycles** (~9.5 s each: 2 s/3 s/4.5 s attempts) for 12.5 h. 7 366 controlPort timeouts total. |
| 20:46:35.057 | l.18520 | `heartbeat recovered (re-subscribed after outage)` — **no bridge restart in between**; consistent with an external device power-cycle. The DRV-30 recovery path succeeded on its first post-recovery attempt. |

No zone-2 command was dispatched (SCN-16 was never exercised); no readiness-gate hold
appears (nothing needed holding — the killer ran inside the exempt command). No MQTT
correlation. The LG TV `set_input HDMI2` fired at 08:07:48.5, mid-window — possible CEC
traffic toward the waking processor, invisible at the new log levels (see Finding 5).

## Finding 1 — the `power_on` handler violates its own readiness window (the trigger)

DRV-38(a) gates every *dispatched* command at the `execute_action` seam, with main-zone
`power_on` correctly exempt. But the handler's internal tail
(`emotiva_xmc2/driver.py` — the post-send block at ~:1080–1094) then fires, inside the
window every other command is held out of:

1. a "defensive" `client.subscribe(PROPERTIES_TO_MONITOR)` immediately after the ack;
2. `asyncio.sleep(1.0)` then `_refresh_device_state()` (:893) → `client.status(*9
   properties)` (:927) — a full Update batch at ~+1.5 s, which the library **retries
   whole up to 3×** (2 s/3 s/4.5 s) when the booting unit is slow.

That is a dozen-plus control-port packets in the first seconds of the power-on
transition — the window wedges #1 (set_input at +3.3 s) and #2 (zone2_power at +4 s)
proved fatal on firmware 3.1. This tail predates DRV-30 (old "sync state after
standby" logic) and was never audited by DRV-38, whose scope was the *next dispatched
command*. Wedge #3's first anomaly is this exact batch timing out at +3.3 s.

## Finding 2 — pymotivaxmc2 0.7.0 is a flood amplifier (verified: PyPI 0.7.0 == sibling tree)

- **Un-correlated shared reply queue**: all control transactions read one unkeyed
  queue per port (`socket_mgr.py:106-113`); acks are never matched to requests
  (`protocol.py:63`). Concurrent transactions steal each other's replies → false
  timeouts → retries. Observed at 08:08:18.121 (`emotivaUpdate` consumed by a
  subscribe). `Semaphore(5)` (`protocol.py:28`) permits the concurrency.
- **Silent 3× retries everywhere**: `send_command` (`protocol.py:45-97`), `subscribe`
  (`:218-296`), and `request_properties_full` (`:130-205`, re-sends the WHOLE batch on
  any missing property). One caller-level call → up to 3 packets; concurrency → more.
  The library's own `docs/emotiva_lib_fixes.md` documented "device stuck under command
  floods" as this unit's failure mode; the Phase-2 retry machinery added then is
  itself the multiplier now.
- **Hygiene gaps**: `disconnect()` sends an empty `<emotivaUnsubscribe>` — a no-op per
  spec §2.1.5 ("each notification property must be unsubscribed explicitly"); the
  transponder's keepAlive interval is parsed then dropped (`discovery.py:147-149`,
  never exposed — the driver reads private `_info`); fixed ports 7002/7003 bound
  without `SO_REUSEADDR` (`socket_mgr.py:64-67`); notification **sequence numbers**
  (protocol §2.6, v2.0+) are ignored — the proper missed-notification detector.

## Finding 3 — the keep-alive/watchdog work is CLEARED as the cause

Three counts: (a) wedge #1 (2026-07-10 morning, REL-3) predates DRV-30 (landed 15:07
that day) — the fragility is older than the subscription work; (b) on 07-14 the
watchdog fired 25 s *after* the device went silent — detection, not cause; (c) the
interval math is right (advertised 7500 ms == observed beats; 3-miss limit ≈ the
logged 25 s). Per the protocol doc there is **no client→device keepalive/ack
obligation** and "no penalty" for duplicate subscribes — no device-side subscriber
accumulation. Residual blemish only: the recovery probe re-subscribes every ~17 s
forever (2 455 cycles) — harmless against a dead unit, but it deserves backoff (DRV-40).

## Finding 4 — what the protocol doc says about subscription timing after power-on

(`../pymotivaxmc2/docs/Emotiva_Remote_Interface_Description.md`)

- **No timing constraints exist.** §2.1.4: *"Subscription packets may be sent to the
  Emotiva device at any time"*; §2.1.5: *"The remote device can re-subscribe at any
  time"*; §2.1.6: *"The remote device can request an Update at any time."* The words
  ready/busy/wait/pacing appear nowhere as protocol concepts — the spec offers **no
  device-readiness signal and no rate limit**; all pacing responsibility falls on the
  client, and aggressive pacing is undefined behavior.
- **But the transaction model names the resume point — and it is NOT the ack.**
  §2.1.2: *"The acknowledgement is of the receipt of the command. It does not
  acknowledge execution"*; §2.4: *"Completion is indicated by the transmission of a
  notification packet."* The spec-conformant power-on pattern is therefore: send
  `power_on` → **passively wait for the `power` notification and the property burst**
  (we are already subscribed — everything arrives unbidden) → only then transact.
  Our tail runs in the receipt→completion gap: legal per the letter, against the
  grain of the model.
  *(Annotation 2026-07-15, owner question at review: this model is stated in the
  spec's GENERIC command sections — §2.1.2 "Commands", §2.4 command packets — so it
  applies to ALL commands, not just power_on; power-on is merely the doc's worked
  example. The gap's practical width differs: instant commands (volume ±1, mute)
  complete in milliseconds and the spec's increment design assumes rapid repeats;
  state-machine transitions (power, HDMI/CEC-renegotiating input switches) gap for
  seconds and are where fw 3.1 is fragile — all three wedges fit that pattern. The
  executor's SCN-14 outcome gates already key on notifications (conformant at the
  right layer); the known residual ack-keyed spot is `zone2_power_on`'s optimistic
  state write.)*
- **The defensive re-subscribe guards a case the spec doesn't describe and
  observation contradicts.** The spec is silent on whether subscriptions survive
  power transitions; observed on fw 3.1: keepAlives flow in standby and the post-
  power-on burst arrives on the *existing* subscription — they survive standby→on.
  The one real loss case (mains cold boot) is announced by the v3.0/3.1 startup
  transponder broadcast (§2.3) and is already covered by the DRV-30 watchdog's
  re-subscribe probe.
- §2.4 also notes `power_on` *"will always execute a power-on regardless of the
  current state"* — redundant sends are spec-safe but re-enter the transition;
  worth knowing for the idempotence guard's `force` path.

## Finding 5 — OPS-25 blinded the forensics

With `pymotivaxmc2` at WARNING and root at INFO, the uncommanded `source → arc` claim
and all UDP-level traces are invisible — wedge #3 cannot be checked for a live ARC
handshake. The ARC/source-change claim is load-bearing evidence (it keys the
readiness gate's fatal-window rule) and belongs at INFO in the driver (OPS-29); the
hygiene itself stays right.

## Finding 6 — a redeploy cold-starts the rack unattended

Boot-time scenario restore re-ran the full `movie_appletv` cold-start plan at 08:07
because the scenario was persisted active — a code deploy became a hardware-touching
event, reproducing the known-dangerous cold-start gesture with nobody watching.
Whether restore should execute plans (vs restore tracking only, or reconcile-observe)
is an owner policy decision → SCN-18.
