# REL-5 — Pre-tag code review (frozen evidence)

**Task:** REL-5 (`review-then-remediate`). **Date:** 2026-07-09. **Method:** multi-agent review — 7 reviewers over the release-critical backend + UI subsystems (canonical dispatch, scenarios/reconciler, device drivers, reports/secrets, ops/bootstrap/MQTT/state, UI runtime rendering, UI api/hooks), weighing correctness/actuation, security, hexagonal conformance, and simplification/test-coverage. **Every finding was adversarially verified** by an independent agent that re-read the code and tried to refute it; only survivors appear here.

**Result:** 20 raw findings → **19 survived** (1 refuted). By severity: **P0 2, P1 5, P2 12**. (Findings #4/#5 below are the same defect — broker password logged at `mqtt/client.py:18` — surfaced independently by two reviewers; remediate once.)

> **This document is frozen evidence.** Per `review-then-remediate`, the findings worth acting on are filed as fresh plan tasks; each carries a one-time `→ tracked as <ID>` pointer once assigned. The only reason to edit a finding here is if the finding itself is wrong/obsolete (annotate, don't flip).

---

## P0 — must fix before tag

### 1. [P0] MQTT broker credentials served unredacted via GET /config/system and /system (password also committed in system.json)

- **Where:** `backend/src/wb_mqtt_bridge/presentation/api/routers/system.py:89`
- **Subsystem / dimension:** canonical-dispatch / security
- **Verifier verdict:** CONFIRMED

**What:** SystemConfigResponse.mqtt_broker.auth (MQTTBrokerConfigResponse.auth: Dict[str,str]) passes the broker username+password straight through, and /system returns the full broker config dict; there is no auth middleware on the app, and the cleartext password is committed in backend/config/system.json.

**Failure scenario:** Any host on the LAN issues `GET /config/system` (or `GET /system`) with no credentials and receives `{..."mqtt_broker":{..."auth":{"username":"admin","password":"t6uxESDN"}}}`. The redaction module (domain/reports/redaction.py) explicitly exists to mask this exact value ('the MQTT broker password in system.json is the known hot item') for the reports evidence bundle, but the same credential flows unmasked through the config REST surface. Additionally the password is checked into the repo at backend/config/system.json:14, violating the 'credentials MUST NOT appear in config JSON or the repo' invariant regardless of the HTTP path.

**Evidence:** system.py:89 `SystemConfigResponse.model_validate(config_manager.get_system_config())`; schemas.py:21 `auth: Optional[Dict[str,str]]`; system.py:71-77 SystemInfo(mqtt_broker=config_manager.get_mqtt_broker_config()); backend/config/system.json:14 `"password": "t6uxESDN"` (git-tracked, not gitignored); no Depends/HTTPBearer/middleware in the router or main.

**Suggested fix:** Rotate the exposed broker password immediately; move it to the env-var path (manager.py already reads MQTT_PASSWORD) and drop `auth` from system.json. On the presentation DTOs, exclude or mask `auth` in MQTTBrokerConfigResponse / SystemInfo (reuse redact_mapping) so /config/system and /system never emit the credential.

**Verifier reasoning:** Every claim reproduces in the actual code. schemas.py:16-21 defines `MQTTBrokerConfigResponse` with `auth: Optional[Dict[str, str]] = None` and `model_config = ConfigDict(from_attributes=True)`; SystemConfigResponse.mqtt_broker (schemas.py:55) nests it, so `SystemConfigResponse.model_validate(config_manager.get_system_config())` at system.py:89 pulls `auth` straight off the infra config. `get_mqtt_broker_config()` (manager.py:268-270) returns the raw `system_config.mqtt_broker` including `auth`, and `_apply_environment_variables` (manager.py:298-301) only overrides auth when MQTT_USERNAME/MQTT_PASSWORD are set — otherwise the committed value survives. GET /system (system.py:71-77) hands that same broker config to `SystemInfo`. I confirmed config/system.json:12-15 carries cleartext `"username":"admin","password":"t6uxESDN"`, that the file is git-tracked (`git ls-files --error-unmatch` succeeded) and not gitignored (`git check-ignore` exit 1), committed as recently as 78673b3 (2026-07-08). There is no authentication anywhere: the only middleware in bootstrap.py is CORSMiddleware (line 619), no HTTPBearer/Depends/APIKey in the router or app. The redaction module (domain/reports/redaction.py) exists and its docstring literally names "the broker password in system.json is the known hot item," yet that masking is applied only to the reports evidence bundle, not to these config endpoints. This directly violates the Secrets invariant (broker credentials must not appear in config JSON, the repo, or over the wire) on a live LAN-exposed smart-home controller — P0 is correct.

> **Tracked as CORE-8** (filed 2026-07-09).

### 2. [P0] MQTT reconnect counter never resets — bridge permanently loses MQTT after 5 lifetime disconnects

- **Where:** `backend/src/wb_mqtt_bridge/infrastructure/mqtt/client.py:189`
- **Subsystem / dimension:** ops-bootstrap-mqtt-state / correctness
- **Verifier verdict:** CONFIRMED

**What:** In _run_mqtt_client, retry_count is initialized once before the while loop and incremented on every MqttError, but is never reset to 0 after a successful (re)connection, so the counter accumulates across the whole process lifetime rather than per disconnect episode.

**Failure scenario:** The bridge runs on the WB7 controller for weeks. The broker restarts / WiFi blips 5 separate times over that span (each a transient, self-healing drop). The first four times the loop reconnects fine but retry_count climbs 1→2→3→4. On the 5th transient drop retry_count reaches max_retries=5, the loop logs 'Max retries reached. Giving up MQTT connection' and exits _run_mqtt_client. The listener task completes, nothing supervises or restarts it, and the entire house becomes uncontrollable via MQTT with WB virtual-device state silently desyncing — until a manual process restart. Normal transient reconnects are a normal-path event over a live controller's lifetime.

**Evidence:** retry_count=0 at line 185; incremented at 306 and 322; compared at 189/307/323; no assignment back to 0 anywhere inside the successful-connection branch (lines 207-296).

**Suggested fix:** Reset retry_count = 0 immediately after a successful connection is established (right after self.connected = True / self._connection_event.set() inside the `async with Client(...)` block), so max_retries bounds retries per disconnect episode, not per process lifetime. Consider an unbounded/backoff reconnect for a live controller.

**Verifier reasoning:** Independently reproduced in backend/src/wb_mqtt_bridge/infrastructure/mqtt/client.py. retry_count is initialized to 0 at line 185 before the `while retry_count < max_retries:` loop (max_retries=5, line 189); it is incremented in the MqttError handler at line 306 (and the generic-exception handler at 322) but there is NO assignment resetting it to 0 anywhere in the successful-connection branch (lines 207-296, `async with Client(...)` → subscribe → `async for message in client.messages`). A live disconnect raises MqttError, exits the message loop, and increments the counter; on the 5th cumulative transient drop the loop condition fails, the code logs "Max retries reached. Giving up MQTT connection" (line 312) and `_run_mqtt_client` returns for good. Nothing restarts it: the listener task is only created (lines 123, 493) and appended to self.tasks, which is iterated solely to cancel tasks on shutdown (lines 337-341) — no supervisor/watchdog. Thus the counter accumulates over the whole process lifetime rather than per disconnect episode, and 5 inevitable transient reconnects over a live WB7 controller's uptime permanently kill MQTT (whole-house control loss + silent WB virtual-device state desync) until manual restart, with the HTTP-only container healthcheck unable to detect it. Defect, failure scenario, evidence lines, and P0 severity all hold.

> **Tracked as CORE-9** (filed 2026-07-09).

## P1 — must fix before tag

### 3. [P1] Canonical select-form `set` silently drops the reserved `force`/`assume_state` params — the force escape hatch is dead for input capabilities

- **Where:** `backend/src/wb_mqtt_bridge/presentation/api/routers/devices.py:454`
- **Subsystem / dimension:** canonical-dispatch / correctness
- **Verifier verdict:** CONFIRMED

**What:** For `input.set` the dispatcher extracts only `params.value` and calls `cap.select.expand(value)`; every other key in payload.params (including the reserved `force` and `assume_state`) is discarded, so the idempotence guard can never be bypassed on select-form capabilities.

**Failure scenario:** Emotiva/LG/Auralic `input` is modelled as select-form (config: `input.select = {command: set_input}`, no `set` action). User speaks/taps `input.set {value: source3}` while optimistic state already says input_source==source3 (e.g. it was changed by the physical remote). set_input's `idempotence_skip(params, self.state.input_source==token)` fires -> response carries skipped_reason='idempotence', UI arms its re-tap-to-force affordance. Re-tap sends `input.set {value: source3, force: true}`; dispatch_device_canonical does `value = payload.params.get('value')` then `cap.select.expand(value)` — `force` is never forwarded, CapabilitySelect.expand() only ever builds `{native_param: value, **fixed}`. Driver's idempotence_skip sees no `force`, skips again. The user can never recover an input desync through the UI; the actions-form path (line 438, `cap.actions[action].expand(payload.params)`) forwards force fine, so the bug is select-form only.

**Evidence:** devices.py:444-454 passes only `value`; models.py CapabilitySelect.expand (98-119) and CapabilityAction.expand() called with no args (114) never see incoming params; emotiva_xmc2/driver.py:1160 and lg_tv/driver.py:1199 read `force` via idempotence_skip(params,...); config shows Emotiva/LG/Auralic `input` are select-form with command set_input/set_input_source.

**Suggested fix:** After expanding select-form steps, overlay the reserved cross-cutting params onto each step: e.g. carry `force`/`assume_state` from payload.params into the NativeStep params (or pass them into CapabilitySelect.expand and have it merge them), mirroring how _resolve_and_validate_params preserves them downstream.

**Verifier reasoning:** I reproduced the defect end-to-end in code. (1) Config: the `input` capability for EMotivaXMC2, LgTv, and AuralicDevice (backend/config/capabilities/classes/*.json) is select-form (`select: {command: set_input[_source], param_map?}`) with NO `set` action, so `input.set` routes into the `elif payload.action == "set" and cap.select is not None` branch at devices.py:439 and calls `cap.select.expand(value)` at line 454 with only the value. (2) `CapabilitySelect.expand(value)` (models.py:98-119) takes a bare `value`; the parametric form builds `{native_param: value, **self.params}` and the by_value form calls `act.expand()` with no args — in neither case does any other payload param (force/assume_state) reach the NativeStep. (3) The dispatch loop (devices.py:489-493) passes `step.params` straight to `perform_action` with no force overlay. (4) The set_input handlers (emotiva driver.py:1160, lg driver.py:1199) call `idempotence_skip(params, self.state.input_source==token, ...)`, and base.py:278 only bypasses the guard when `(params or {}).get("force")` is truthy — which it never is, so a re-tap with force is silently dropped and skips again. The asymmetry is real: the actions-form path (devices.py:438) uses `CapabilityAction.expand(payload.params)` which passes ALL incoming params through unchanged (models.py:60, `param_map.get(k,k)` leaves `force` as `force`), so force works there. Decisively, the scenario reconciler's `_input_action` (reconciler.py:303-305) calls the very same `sel.expand()` and then MANUALLY re-injects `params["force"]=True` afterward with the comment "bypass driver idempotence guards" — proving the maintainers already know `select.expand` drops force and worked around it in the reconciler, but the canonical dispatch endpoint never got the equivalent overlay. Severity P1 is correct: this is a genuine correctness bug that deadens the documented UI re-tap-to-force escape hatch for input desync on all AV input devices, but it under-actuates (refuses a resend) rather than physically mis-actuating, and a scenario force_reconcile workaround exists, so it is not P0.

> **Tracked as DRV-21** (filed 2026-07-09).

### 4. [P1] MQTT broker password written to service.log / console in plaintext at client init

- **Where:** `backend/src/wb_mqtt_bridge/infrastructure/mqtt/client.py:18`
- **Subsystem / dimension:** ops-bootstrap-mqtt-state / security
- **Verifier verdict:** CONFIRMED

**What:** MQTTClient.__init__ logs the entire broker_config dict at INFO, and that dict includes the `auth` sub-dict carrying the broker username and password (system.json's MQTTBrokerConfig.auth is Dict[str,str] with a `password` key).

**Failure scenario:** On every startup, bootstrap constructs MQTTClient with {'host':..,'auth': mqtt_broker_config.auth}. Line 18 emits `Initializing MQTT client with broker config: {... 'auth': {'username': 'u', 'password': '<secret>'}}` to the on-disk service.log and the console handler. Anyone reading the controller's log file (or a shipped log) obtains the live broker password in cleartext. This directly violates the invariant that broker credentials must not appear in logs — the redaction module's own docstring names the broker password as the 'known hot item', yet this write bypasses it (the report-bundle redact_text is a separate, later pass; the primary log file on the box is already leaked).

**Evidence:** client.py:18 logs broker_config verbatim; client.py:39-41 shows auth carries password; config/models.py:23 `auth: Optional[Dict[str, str]]`; redaction.py docstring: 'the MQTT broker password in system.json is the known hot item'.

**Suggested fix:** Do not log the raw broker_config. Log only non-secret fields (host, port, client_id, keepalive, whether auth is present), or pass the dict through redact_mapping before logging.

**Verifier reasoning:** I independently reproduced the defect. `client.py:18` executes `logger.info(f"Initializing MQTT client with broker config: {broker_config}")` before any redaction, emitting the raw dict verbatim. `bootstrap.py:280-286` constructs `MQTTClient({... 'auth': mqtt_broker_config.auth})`, and `client.py:39-41` shows `auth` carries `username`/`password`. `config/models.py:23` types `auth: Optional[Dict[str, str]]`, and the live `backend/config/system.json` actually contains `auth.password: "t6uxESDN"` — a real cleartext broker password. So on every startup (including the system-router `POST /reload` path at `system.py:151` and the CLI path at `device_test.py:55`) the plaintext broker password is written to service.log/console. `redaction.py:4` explicitly names the broker password in system.json as the "known hot item," and that redaction is a separate report-bundle pass that does not cover this primary INFO log line — the leak bypasses it. This directly violates the secrets invariant (broker credentials must not appear in logs). P1 is the correct severity: a genuine credential-in-logs leak, but a local-disk exposure rather than a P0 remote/physical-actuation defect.

> **Tracked as CORE-8** (filed 2026-07-09).

### 5. [P1] MQTT broker password written in plaintext to service.log on every startup

- **Where:** `backend/src/wb_mqtt_bridge/infrastructure/mqtt/client.py:18`
- **Subsystem / dimension:** reports-security / security
- **Verifier verdict:** CONFIRMED

**What:** MQTTClient.__init__ logs the raw broker_config dict — including auth.password — at INFO, writing the broker credential in cleartext into logs/service.log, which is exactly the file the report collector ingests and serves.

**Failure scenario:** On boot, broker_config = {'host': '192.168.110.250', ..., 'auth': {'username': 'admin', 'password': 't6uxESDN'}, ...} is logged verbatim. logs/service.log now holds the broker password in cleartext at rest. ReportService._collect_logs() reads that file for the always-on GET /reports/evidence and every filed bundle. Redaction happens to mask this particular line only because redact_text keys off the adjacent 'password': substring (verified) — a single reformat of that log line, or any wrapping that separates the value from the keyword, would push the live broker credential straight into the (unauthenticated) evidence endpoint. The secret should never be logged in the first place.

**Evidence:** client.py:18 `logger.info(f"Initializing MQTT client with broker config: {broker_config}")`; config/system.json has mqtt_broker.auth.password='t6uxESDN'. Verified: redact_text currently masks the dict-repr form, but the log file itself stores it in cleartext.

**Suggested fix:** Log only non-secret fields (host, port, client_id, keepalive) or a copy with auth masked; never emit the whole broker_config.

**Verifier reasoning:** Independently confirmed the whole chain. client.py:18 is verbatim `logger.info(f"Initializing MQTT client with broker config: {broker_config}")`. bootstrap.py:280-286 constructs that dict with `'auth': mqtt_broker_config.auth`, and models.py:23 types auth as `Optional[Dict[str, str]]`, so the passed dict literally contains `{'auth': {'username': 'admin', 'password': 't6uxESDN'}}` (matching config/system.json). bootstrap.py:114/227 wires a TimedRotatingFileHandler to `logs/service.log`, so the INFO line lands in that file in cleartext at rest on every startup. This directly violates the project invariant "broker credentials MUST NOT appear in ... logs." The read-time mitigation is real but exactly as fragile as the finding says: service.py:166 applies redact_text to the file contents before the evidence endpoint serves them, and redaction.py:18-19's `_SECRET_TEXT_RE` masks the current dict-repr form only because it keys off `password': <value>` at end-of-line; any reflow that separates the keyword from its value would push the live credential to the unauthenticated GET /reports/evidence. The defect (a secret written to disk in the first place) exists precisely as described. P1 is appropriate: a real credential is persisted cleartext at rest, defended only by a brittle regex on the one exfil path.

> **Tracked as CORE-8** (filed 2026-07-09).

### 6. [P1] Teardown ignores reconcile:false — the reconciler drives a capability it is contractually forbidden to touch

- **Where:** `backend/src/wb_mqtt_bridge/domain/scenarios/reconciler.py:278`
- **Subsystem / dimension:** scenarios-reconciler / correctness
- **Verifier verdict:** CONFIRMED

**What:** build_power_off_plan emits power-off for any device with a power capability, without the reconcile-flag guard every other reconciler site applies, so a reconcile:false device (the upscaler) gets an explicit power_off on scenario deactivate/graceful-switch.

**Failure scenario:** movie_ld/movie_vhs route audio/video through `upscaler`, whose power capability is declared `"reconcile": false` (backend/config/capabilities/devices/upscaler.json — 'auto-powers with the LD') with an explicit `power_off` IR action. build_plan (line 406) correctly SKIPS powering it on. But on POST /scenario/shutdown -> deactivate() (service.py:538) or a graceful switch (service.py:297), the upscaler is in `involved`, so build_power_off_plan (no reconcile check at line 275-278) calls _power_off_actions and emits an IR `power_off` to it. The reconciler thus drives a capability whose entire contract is 'exposed on the page/WB/HTTP but skipped by the reconciler'. For the upscaler the end-state is benign (it ends up off either way), but it is an unwanted, racing IR emission and the guard is simply missing — any future reconcile:false power device (e.g. an always-on or toggle-power sink) would be actively mis-driven on teardown.

**Evidence:** Activation build_plan line 406 `if power_cap is not None and power_cap.reconcile:`; forced plan line 494; preview line 547 — all guard on reconcile. build_power_off_plan lines 275-278 have no such guard: `power_cap = cap_map.get('power')` then unconditionally `plan.actions.extend(_power_off_actions(...))`. upscaler.json line 3: `"reconcile": false ... actions: { off: { command: power_off } }`. topology.json places upscaler on the video path, so it is in resolve_targets' involved set.

**Suggested fix:** In build_power_off_plan, skip capabilities where reconcile is False, mirroring build_plan: `if power_cap is None or not power_cap.reconcile: continue`.

**Verifier reasoning:** Independently reproduced. build_power_off_plan (reconciler.py:274-278) fetches power_cap and unconditionally calls _power_off_actions with no reconcile guard, whereas the activation path build_plan (line 406) gates on `power_cap is not None and power_cap.reconcile`. The reconcile field docstring (domain/capabilities/models.py:201-206) defines False as "skipped by the reconciler (e.g. ... the upscaler)" — and build_power_off_plan is part of the reconciler, so this violates the field's own contract. upscaler.json carries `"reconcile": false` on power with an explicit power_off IR action; topology.json puts upscaler on the video path (lines 42/49/55/171-179) so resolve_targets()[2] includes it. Both callers — _switch_via_reconciler (service.py:297) and deactivate (service.py:538) — pass the full involved set into build_power_off_plan, so an IR power_off is emitted to the upscaler on teardown/graceful-switch, a device the reconciler is forbidden to drive. Severity P1, not P0: for the upscaler the end-state is benign (teardown wants it off, it has a real power_off, ends up off either way) so no current wrong-direction actuation, only an unwanted racing IR emission — but the guard is genuinely missing and any future reconcile:false power device would be actively mis-driven.

> **Tracked as SCN-12** (filed 2026-07-09).

### 7. [P1] SSE connection dies permanently after maxRetries with no recovery — live device state goes silently stale

- **Where:** `ui/src/hooks/useEventSource.ts:136`
- **Subsystem / dimension:** ui-api-hooks / correctness
- **Verifier verdict:** CONFIRMED

**What:** Once reconnectAttemptsRef reaches maxRetries (10), es.onerror stops scheduling reconnects and the EventSource is never reopened while url/enabled are unchanged; the ref is only reset on a successful onopen, which can no longer happen.

**Failure scenario:** The dashboard is left open on a wall panel (the normal deployment). A network blip / Wi-Fi drop / bridge restart lasts longer than the 10-retry backoff window (retryRef grows 5s×1.5 capped at 30s, so ~10 attempts span only a few minutes). After the 10th failure `reconnectAttemptsRef.current < maxRetries` is false, so no setTimeout is scheduled and es stays closed. When the network returns there is nothing to trigger a reconnect (the effect deps [url, enabled, maxRetries, retryInterval, withCredentials] are unchanged), so /events/devices is dead until a full page reload. Meanwhile useDeviceState intentionally does not poll ('only fetch on mount and after actions'), so Layout's state_change→setQueryData path (Layout.tsx:84) is the only liveness source. Result: the UI keeps showing the last-known power/volume/input for every device indefinitely. A user acting on that stale display (e.g. sees a device 'off' that is actually on) double-actuates or powers the wrong gear in a live house.

**Evidence:** useEventSource.ts:136 `if (!cancelledRef.current && reconnectAttemptsRef.current < maxRetries)` with no else-branch/backstop; counters reset only at onopen (line 80) which cannot fire once retries are exhausted.

**Suggested fix:** After exhausting maxRetries, keep a slow keepalive reconnect (e.g. retry every 60s indefinitely) rather than giving up, or surface a hard 'disconnected — reload' banner on every page (not just the DeviceStatePanel badge) so stale state can never be mistaken for live.

**Verifier reasoning:** Independently reproduced in code. useEventSource.ts:136 guards reconnect with `reconnectAttemptsRef.current < maxRetries` (maxRetries=10, line 29) and has no else/backstop; onerror (line 128) closes the ES (line 133) and schedules nothing once exhausted. The counter resets only in onopen (line 80) and onmessage (line 106), both of which require a live connection that can no longer exist, so recovery is impossible. Effect deps [url, enabled, maxRetries, retryInterval, withCredentials] (line 177) are stable for a wall-panel session so the effect never rebuilds the connection, and I confirmed there is no visibilitychange/online/focus reconnect listener anywhere in src/ (only error/unhandledrejection telemetry). Backoff (5s ×1.5 cap 30s) exhausts 10 attempts in ~3-4 min, so any longer outage permanently kills the stream. Liveness is SSE-only: Layout.tsx:22 useDeviceSSE + the state_change→setQueryData handler (lines 76-84) is the sole live-state path, and device-state queries have no refetchInterval (no polling fallback); the only disconnect cue is a red dot in DeviceStatePanel not shown on every page. On a live controller this freezes displayed device state indefinitely and invites physical mis-actuation — P1 is correct.

> **Tracked as UI-13** (filed 2026-07-09).

## P2 — file, fix opportunistically (not tag-blocking)

### 8. [P2] Handler availability failures mis-surface as internal_error(500) instead of device_unreachable(503) to voice

- **Where:** `backend/src/wb_mqtt_bridge/presentation/api/routers/devices.py:503`
- **Subsystem / dimension:** canonical-dispatch / correctness
- **Verifier verdict:** CONFIRMED

**What:** When a native step fails, the canonical dispatcher classifies the error solely by keyword-sniffing for param-shaped words; any non-param failure (including reachability/availability failures raised inside handlers) is bucketed as INTERNAL_ERROR/500, so voice never hears a speakable 'device unreachable'.

**Failure scenario:** Emotiva set_input runs while `self.client is None` and returns `error='Not connected to processor'` (emotiva_xmc2/driver.py:1169). dispatch_device_canonical sees err_text without 'param/missing/required/invalid', maps to INTERNAL_ERROR -> HTTP 500. The device is actually unreachable, but Irene speaks 'internal error' rather than the 'device unreachable' phrase the 503/DEVICE_UNREACHABLE path is designed to give (the timeout branch at line 557 already produces that code for the echo-wait case, so availability failures are surfaced inconsistently depending on where they arise).

**Evidence:** devices.py:500-508 keyword sniff -> only PARAM_INVALID else INTERNAL_ERROR; emotiva_xmc2/driver.py:1168-1169 returns 'Not connected to processor'; contrast the timeout branch devices.py:556-562 which correctly emits DEVICE_UNREACHABLE.

**Suggested fix:** Extend the classifier to recognize availability/reachability wording ('not connected', 'unreachable', 'no client', 'offline') -> DEVICE_UNREACHABLE/503, or have handlers return a structured error code the dispatcher maps, so pre-echo availability failures surface as 503 like the timeout path.

**Verifier reasoning:** Independently verified all code refs. devices.py:502-508 classifies native-step failures purely by lowercase keyword-sniff ("param"/"missing"/"required"/"invalid" → PARAM_INVALID/400; else INTERNAL_ERROR/500). emotiva_xmc2/driver.py:1168-1169 returns error="Not connected to processor" when self.client is None — that string matches none of the four keywords, so it buckets to INTERNAL_ERROR/500. Meanwhile the echo-timeout branch (556-562) and the state.reachable-False branch (566-573) correctly emit DEVICE_UNREACHABLE/503. So a genuine reachability/availability failure raised inside a handler pre-dispatch is surfaced as 500 while the same class of failure during the echo wait is surfaced as 503 — a real, reproducible inconsistency in the error code voice hears. No earlier availability guard intercepts it; the only reachability check for this path is inside the handler. The code comment at 499-501 explicitly documents this as a known stopgap. This is a semantic/UX error-labeling defect, not a physical mis-actuation, so P2 is the correct severity.

> **Tracked as VWB-31** (filed 2026-07-09).

### 9. [P2] LG TV WebOS client_key (device credential) logged in cleartext at INFO

- **Where:** `backend/src/wb_mqtt_bridge/infrastructure/devices/lg_tv/driver.py:904`
- **Subsystem / dimension:** device-drivers / security
- **Verifier verdict:** CONFIRMED

**What:** The WebOS pairing secret self.client_key is written to the log at INFO level in three places, leaking a reusable device-control credential into persistent logs.

**Failure scenario:** On first pairing (or any re-pairing) the TV returns a new client_key. connect() at line 904 logs `Obtained new client key for future use: {self.client_key}`; the insecure path logs it at line 967 and the post-WoL path at line 1013. The client_key grants full ssap control of the TV. It is now in the controller's rotating logs (and any bundle captured by the problem-report pipeline that ships logs off-box to droman42/wb-user-reports), crossing the LAN trust boundary the credential is scoped to. Anyone with the leaked key can command the TV.

**Evidence:** Lines 904, 967, 1013 all f-string the raw self.client_key into logger.info(). The invariant explicitly forbids credential-shaped values appearing in logs; a WebOS client_key is exactly such a value.

**Suggested fix:** Log only that a new key was obtained (and optionally a short fingerprint like client_key[:4]+'…'), never the full value. Apply to all three sites.

**Verifier reasoning:** I read driver.py directly and reproduced the defect exactly as described. Lines 903-904, 966-967, and 1012-1013 each assign `self.client_key = self.client.client_key` from a fresh WebOS pairing and then `logger.info(f"...{self.client_key}")` the full value at INFO level (the three sites: "Obtained new client key for future use", "...from insecure connection", "...after WoL"). `client_key` (initialized at line 118 from `self.tv_config.client_key` and passed into `WebOSTV(..., client_key=...)` at lines 197/204/2043/2087) is the WebOS ssap pairing token — a reusable device-control credential; a holder can command the TV over the LAN without re-triggering the on-TV pairing prompt. Logging it at INFO puts it into the controller's persistent rotating logs, which can be shipped off-box in problem-report bundles, so the credentials-must-not-appear-in-logs invariant is genuinely violated and the failure scenario reproduces on any (re)pairing. The finding's quotes and file:line refs are all accurate — no guard, caller, or test prevents it. The only adjustment is severity: the blast radius is a single TV's control over the LAN and exploitation requires access to the logs (not the broker password or a GitHub PAT, the "hot" P1 secrets), so this reads as P2 rather than P1 — a real credential leak, but lower impact than a house-control or broker-credential exposure. The suggested fix (log a short fingerprint like `client_key[:4]+'…'` instead of the raw value at all three sites) is correct.

> **Tracked as CORE-8** (filed 2026-07-09).

### 10. [P2] IR device last_command details (command_topic/command_payload) are immediately overwritten by the base chokepoint

- **Where:** `backend/src/wb_mqtt_bridge/infrastructure/devices/wirenboard_ir_device/driver.py:319`
- **Subsystem / dimension:** device-drivers / simplification
- **Verifier verdict:** CONFIRMED

**What:** record_last_command() writes a LastCommand carrying the IR topic/payload, but _execute_single_action in base overwrites last_command right after the handler returns, so the IR-specific bookkeeping is dead/lost.

**Failure scenario:** Any IR command executed through the normal dispatch path: the handler calls _execute_ir_command -> record_last_command (base.py-style update_state with source='mqtt' and params containing command_topic/command_payload). The handler returns, then BaseDevice._execute_single_action line 648 calls update_state(last_command=LastCommand(action, source, ...)) with the plain params and source='unknown' (handle_message passes no source), replacing the just-written record. The IR command_topic/command_payload the driver intended to persist never survives; source is also downgraded to 'unknown'. The intermediate value only flickers out via one transient SSE event before being clobbered.

**Evidence:** wirenboard_ir_device/driver.py:319 record_last_command inside _execute_ir_command; base.py:648 unconditionally re-writes last_command after the handler. Both target the same field via the chokepoint, second write wins.

**Suggested fix:** Drop the record_last_command call from the IR driver (rely on the base chokepoint's last_command), or move the IR-specific topic/payload into the CommandResult/data rather than last_command so it isn't clobbered.

**Verifier reasoning:** Verified independently. record_last_command (driver.py:166-198) writes last_command with source="mqtt" and params carrying command_topic/command_payload; it is only reachable via _execute_ir_command (driver.py:319/402), which is only called from the IR action handlers (driver.py:220/255/289). Those handlers are exactly the callable awaited at base.py:641, and base.py:648 then unconditionally rewrites last_command via update_state with the plain params (no command_topic/command_payload) and the caller's source, replacing the just-written record since update_state replaces the whole field. Every IR dispatch path goes through _execute_single_action, so there is no path where the IR record survives. A repo-wide grep shows no consumer reads last_command.params.command_topic/command_payload. Thus the IR-specific bookkeeping is redundant/dead — persisted last_command never keeps it, only a transient SSE flicker. P2/simplification is correct: this is metadata bookkeeping, not actuation, so no physical mis-actuation risk; cost is a redundant update_state write. The finding's "source downgraded to unknown" is accurate only on the handle_message path (base.py:412 passes no source); the execute_action path passes a real source — a minor imprecision that does not affect the core defect.

> **Tracked as DRV-22** (filed 2026-07-09).

### 11. [P2] Startup-failure cleanup omits WB-card offline marking, leaving retained available=1 (asymmetric with normal shutdown)

- **Where:** `backend/src/wb_mqtt_bridge/app/bootstrap.py:184`
- **Subsystem / dimension:** ops-bootstrap-mqtt-state / correctness
- **Verifier verdict:** CONFIRMED

**What:** _release_partial_startup tears down devices, disconnects MQTT and closes the store, but — unlike the normal shutdown path (lines 566-574) — never calls cleanup_wb_device_state() to publish meta/available=0 / meta/error=offline for the device WB cards while MQTT is still connected.

**Failure scenario:** Startup progresses past WB emulation setup (bootstrap lines 385-391 publish retained meta/available=1 for each device card) and then an unexpected error is raised later in the lifespan try-block (e.g. scenario manager init, report service wiring). The except-block calls _release_partial_startup, which disconnects MQTT without first marking the cards offline. The retained available=1 stays on the broker forever, so the Wirenboard UI shows every device card as live even though the bridge failed to start and is down — the exact false-liveness bug OPS-8 fixed for the normal shutdown path, re-opened on the failure path.

**Evidence:** bootstrap.py:176-192 (partial cleanup: no cleanup_wb_device_state); contrast bootstrap.py:566-574 normal path which does it explicitly with the comment about retained available=1.

**Suggested fix:** Before mqtt_client.disconnect() in _release_partial_startup, iterate device_manager.devices and best-effort await cleanup_wb_device_state() on each (guarded per-device), mirroring the normal shutdown ordering: mark WB cards offline BEFORE disconnecting MQTT.

**Verifier reasoning:** Independently verified in bootstrap.py: _release_partial_startup (lines 160-192) cleans up in order cancel-task / shutdown_devices (180) / mqtt disconnect (185) / state close (190) and never calls cleanup_wb_device_state(). The normal shutdown path (566-574) explicitly loops device_manager.devices calling cleanup_wb_device_state() BEFORE mqtt disconnect (578), with the OPS-8 comment noting device cards otherwise keep retained available=1 forever, looking live with the bridge down. The except block (501-514) wraps the whole startup, including WB emulation setup at 384-391 (which publishes retained available=1 for each card) and later steps that can raise (scenario_manager.initialize() at 403, report/state wiring at 495-497). A failure after 391 thus runs _release_partial_startup post-publish, disconnecting MQTT without marking cards offline — the exact false-liveness bug OPS-8 fixed for the normal path, re-opened on the failure path. cleanup_wb_device_state (base.py:161-178) is self-guarded/best-effort, so the suggested fix is safe. shutdown_devices() at 180 is not a substitute — the normal path runs it separately (582) from the offline-marking loop. P2 is correct: broker-metadata-only false liveness, hardware-transparent, only on the rare unexpected-startup-failure path.

> **Tracked as OPS-18** (filed 2026-07-09).

### 12. [P2] ConfigManager._apply_environment_variables is dead code — MQTT_BROKER_HOST/USERNAME/PASSWORD env overrides never take effect

- **Where:** `backend/src/wb_mqtt_bridge/infrastructure/config/manager.py:289`
- **Subsystem / dimension:** ops-bootstrap-mqtt-state / simplification
- **Verifier verdict:** CONFIRMED

**What:** _apply_environment_variables (which would apply MQTT_BROKER_HOST, MQTT_BROKER_PORT, MQTT_USERNAME, MQTT_PASSWORD onto the broker config) is defined but never invoked anywhere in the codebase.

**Failure scenario:** An operator, following the usual 12-factor expectation, sets MQTT_PASSWORD / MQTT_BROKER_HOST in the container environment to override system.json (e.g. to keep the broker password out of the committed config per the secrets invariant). Because __init__ never calls _apply_environment_variables and nothing else does, the env vars are silently ignored and the bridge connects with whatever is baked into system.json — the override that would let credentials live in the environment instead of committed JSON simply does not work.

**Evidence:** grep across src shows _apply_environment_variables only at its definition (manager.py:289) with no call site; contrast with the invariant that broker credentials must not appear in config JSON.

**Suggested fix:** Either call self._apply_environment_variables() at the end of _load_system_config()/__init__ so env overrides are honored (helpful for keeping the broker password out of committed JSON), or delete the dead method and its tests to avoid the false impression that env overrides are supported.

**Verifier reasoning:** Independently reproduced: a repo-wide grep for `_apply_environment_variables` across all .py files returns only the definition at manager.py:289 — no call site anywhere. I read `__init__` (lines 27-54), which calls only `_load_system_config()` and `_discover_and_load_device_configs()`; `_load_system_config()` (56-81) builds SystemConfig from system.json and returns without reading env vars; `reload_configs()` (282-287) calls only those same two loaders. The MQTT_BROKER_HOST/PORT/USERNAME/PASSWORD env vars are read nowhere else in the backend except inside this dead method (the only other hit, tests/debug.py:21, just prints MQTT_BROKER_HOST, it does not invoke the method), and no test exercises it. Therefore the failure scenario is accurate: env-var overrides for the MQTT broker (including MQTT_PASSWORD to keep the secret out of committed JSON) are silently ignored. This is genuine dead code / a false affordance. P2 is correct — it is a latent inconsistency, not an active mis-actuation, and the finding honestly offers both wire-it-up and delete-it remedies.

> **Tracked as (unfiled)** (filed 2026-07-09).

### 13. [P2] redact_mapping skips masking when a credential-shaped key holds a container

- **Where:** `backend/src/wb_mqtt_bridge/domain/reports/redaction.py:32`
- **Subsystem / dimension:** reports-security / security
- **Verifier verdict:** CONFIRMED

**What:** The mask branch only fires for SCALAR values; a credential-shaped key whose value is a dict/list is recursed into, so nested leaves that are not themselves credential-keyed pass through unmasked.

**Failure scenario:** redact_mapping({'api_keys': {'cloud': 'sk-SECRET'}, 'tokens': ['tok-SECRET']}) returns the input unchanged (verified): 'api_keys'/'tokens' match the secret-key regex but their values are containers, so the code recurses and the inner scalars — keyed 'cloud' / positional list element — are never masked. Today no shipped config has this exact shape (broker auth, Apple TV credentials, LG client_key are all scalar-keyed and correctly masked), but the redaction primitive is the last line of defense for the always-on unauthenticated /reports/evidence, and any future config or ui_evidence blob with a plural/grouped credential container leaks in full.

**Evidence:** redaction.py:30-34 — `redact_mapping(v) if isinstance(v,(dict,list,tuple)) or not _SECRET_KEY_RE.search(str(k)) else MASK`. Verified C: `{'api_keys':{'cloud':'sk-SECRET'},'tokens':['tok-SECRET']}` round-trips unmasked. No test covers the secret-keyed-container case (test_reports.py:59).

**Suggested fix:** When the key matches the secret regex, mask the whole value regardless of type (or recurse but mask every scalar leaf under a secret-keyed subtree).

**Verifier reasoning:** I read redaction.py:24-39 and the quote is accurate: line 32's conditional is `redact_mapping(v) if isinstance(v,(dict,list,tuple)) or not _SECRET_KEY_RE.search(str(k)) else MASK`, so the `else MASK` branch fires ONLY when the value is a scalar AND the key matches the secret regex. A secret-keyed key whose value is a container takes the recurse branch instead, and inside that container any leaf that isn't itself secret-keyed (a plural sub-key like 'cloud', or a positional list element) is returned unchanged. I reproduced it live: `redact_mapping({'api_keys':{'cloud':'sk-SECRET'},'tokens':['tok-SECRET'],'password':'p','auth':{'user':'u','password':'p2'}})` returned `api_keys`/`tokens` values verbatim while correctly masking the scalar-keyed `password` and nested `auth.password`. The module docstring even documents the recurse-on-container behavior as intentional ("only the credential leaves get masked"), but that design silently assumes every credential leaf is itself secret-keyed, which is false for grouped/plural containers. The unit test at test_reports.py:59 only covers scalar-keyed keys (including `token_env`), so nothing guards the container case. Severity P2 is correct, not higher: I grepped config/ and every shipped credential is scalar-keyed (system.json broker `password`, LG `client_key`) and thus masked today — the leak is latent defense-in-depth erosion on the unauthenticated /reports/evidence endpoint, not an active leak or a house-actuation bug.

> **Tracked as VWB-30** (filed 2026-07-09).

### 14. [P2] redact_text only masks key=value assignments; bare/URL-embedded secrets pass through

- **Where:** `backend/src/wb_mqtt_bridge/domain/reports/redaction.py:19`
- **Subsystem / dimension:** reports-security / security
- **Verifier verdict:** CONFIRMED

**What:** _SECRET_TEXT_RE requires a credential keyword immediately followed by a separator and value on the same line; a secret embedded in URL userinfo or otherwise not adjacent to a keyword is not masked in collected logs.

**Failure scenario:** A log line 'connecting to mqtt://admin:t6uxESDN@192.168.110.250:1883' or 'auth failed for user admin using t6uxESDN' is returned UNMASKED by redact_text (verified B/E). Any device driver or third-party library (aiohttp/pyatv/webostv/upnp) that logs a connection URL with userinfo or a bare token would leak that secret verbatim into every report bundle and the always-on evidence endpoint. The redactor's coverage is narrower than the 'mask credentials in log excerpts' contract it advertises.

**Evidence:** redaction.py:18-21 pattern anchors on `(authorization|token|passw|secret|credential|api_key)\S*\s*[=:]\s*`. Verified: URL-userinfo and keyword-non-adjacent forms are not masked. No test covers these (test_redact_text_masks_assignments only checks `key=value`).

**Suggested fix:** Add a userinfo pattern (scheme://user:PASS@host) and consider masking high-entropy bare tokens near credential keywords; add tests for both forms.

**Verifier reasoning:** I read redaction.py directly and reproduced the regex behavior. `_SECRET_TEXT_RE` (lines 18-21) requires a credential keyword immediately followed by a `[=:]` separator and value on the same line; running it confirms `mqtt://admin:t6uxESDN@192.168.110.250:1883` and `auth failed for user admin using t6uxESDN` are returned UNMASKED, while `password=hunter2` and `Authorization: Bearer xyz` are masked. `redact_text` is applied to the collected log file (service.py:166) and UI free-text that populate the report bundle / always-on evidence endpoint, so URL-userinfo or bare-token secrets logged by any dependency would leak. The only test (test_reports.py:74) covers just the key=value form, confirming no coverage of these cases. This is a genuine coverage gap in a redactor advertised to strip credentials from log excerpts. Severity is correctly P2 (defense-in-depth): the specifically-protected broker password is NOT reachable via this path — MQTTClient uses aiomqtt with separate host/username/password kwargs and never builds an mqtt:// URL with userinfo (client.py:41,107-111), so the finding's headline broker-URL example does not occur in this codebase. The leak is real but speculative (depends on a third-party library emitting a credential-bearing URL/bare token into the log), and does not touch the named hot item, so it is a hardening gap rather than a confirmed active leak.

> **Tracked as VWB-30** (filed 2026-07-09).

### 15. [P2] report_id has only second granularity — collisions cause permanently-undeliverable spool and spool-file overwrite

- **Where:** `backend/src/wb_mqtt_bridge/domain/reports/service.py:202`
- **Subsystem / dimension:** reports-security / correctness
- **Verifier verdict:** CONFIRMED

**What:** report_id = '{%Y%m%dT%H%M%SZ}-bridge-ui-{room}' has no uniqueness component; two reports for the same room in the same UTC second collide on both the GitHub content path and the spool filename.

**Failure scenario:** Two POST /reports for the same room within one second produce identical report_id. The GitHub sink PUTs reports/{report_id}/bundle.tar.gz (github_sink.py:43); the second PUT hits an existing path and GitHub returns HTTP 422 (missing sha) -> RuntimeError -> caught -> the report is spooled. retry_spooled re-runs _deliver against the same path -> 422 again forever -> the report is never delivered (silent data loss of a user report). Separately, _spool writes {report_id}.json, so a colliding spool entry overwrites the earlier one. The client-side rate limit (3/hour) makes this unlikely but not impossible (two users, same room, same second).

**Evidence:** service.py:200-202 builds ts at second resolution and report_id; github_sink.py:43 bundle_path derived solely from report_id; github_sink.py:101 spool filename is `{report_id}.json`.

**Suggested fix:** Append a short random/uuid suffix (or a monotonic counter) to report_id so the GitHub path and spool filename are unique.

**Verifier reasoning:** I independently read service.py:200-202 and confirmed report_id = f"{ts}-bridge-ui-{room}" where ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") — second-resolution, with no PID/uuid/counter/microsecond component (grep for uuid/urandom/token_hex/%f/microsecond in service.py returned nothing; models.py stores report_id as a plain str). github_sink.py:43 derives bundle_path = f"reports/{filing.report_id}/{filing.bundle_name}" solely from report_id, and _spool (line 101) writes {filing.report_id}.json — both quotes are exact. The GitHub "create or update file contents" PUT (lines 45-53) is called without a `sha`, so a PUT to an already-existing path returns HTTP 422 (sha not supplied), which is not in (200,201) → RuntimeError → caught in file_report (line 73) → spooled. retry_spooled (line 87) re-runs _deliver against the identical existing path → 422 again indefinitely, so a colliding second report is permanently undeliverable, and its spool file overwrites any same-second collision. The failure genuinely reproduces for two reports of the same room within one UTC second. It is real silent data-loss of a user problem report. Severity P2 is appropriate: the mechanism is real and the loss is silent, but the trigger is narrow (same room, same second, and the global 3/hour rate limit further gates it), and it degrades only the problem-report feature — it cannot mis-actuate the house.

> **Tracked as VWB-30** (filed 2026-07-09).

### 16. [P2] Shipped 'TEMPORARY DEBUG' default branch spams the progress UI for every unrecognized device SSE event

- **Where:** `ui/src/app/Layout.tsx:94`
- **Subsystem / dimension:** ui-api-hooks / simplification
- **Verifier verdict:** CONFIRMED

**What:** The device-SSE switch default case, explicitly labelled temporary debug, sets shouldAddToProgress=true for any event type not in the known set, pushing noise into the user-visible progress store on a release build.

**Failure scenario:** The backend adds or emits any device event type other than action_success/action_error/action_progress/state_change/test (e.g. a future 'connected'/'availability' event, or any typo) that still carries device_id+device_name. It falls into the default branch (Layout.tsx:93-97) which logs `[Layout] Unknown device event type` and, because the debug line flipped shouldAddToProgress from false to true, injects a `${eventType}: ...` message into the progress toast area for the end user. This is committed debug scaffolding ('🐛 TEMPORARY DEBUG', '🐛 Changed from false to true for debugging') going out in a tagged release.

**Evidence:** Layout.tsx:94-97 comments `// 🐛 TEMPORARY DEBUG` and `shouldAddToProgress = true; // 🐛 Changed from false to true for debugging`.

**Suggested fix:** Restore shouldAddToProgress=false in the default branch (silently ignore unknown event types, keep only the console.log) before tagging.

**Verifier reasoning:** I independently read ui/src/app/Layout.tsx:52-108 and the finding's quotes are accurate to the character. The device-SSE handler enters the block at line 52 only when eventType && device_id && device_name are all present. The switch (lines 57-98) has real cases only for action_success/action_error/action_progress/state_change (the 'test' type is handled earlier and early-returns at line 48). The default branch (lines 93-98) is committed debug scaffolding: it logs `[Layout] Unknown device event type` and, crucially, sets `shouldAddToProgress = true` with the inline comment `// 🐛 Changed from false to true for debugging`. Because of that flag, lines 100-108 call addMessage(), injecting a `${eventType}: ${message}` entry into the user-visible progress store. So any backend device event of an unrecognized type that still carries device_id+device_name (a future 'connected'/'availability' event, a typo, etc.) will spam the end-user progress UI. The failure scenario reproduces exactly as described, and the emoji-tagged TEMPORARY DEBUG markers confirm this is scaffolding not meant for a tagged release. Severity P2 is correct: this is cosmetic UI noise / cleanup, not a correctness bug — it cannot mis-actuate hardware (the state_change device-actuation path at 76-91 is untouched and correctly sets shouldAddToProgress=false), so it does not warrant escalation, but it is a genuine shipped-debug-code defect, not plausible-only.

> **Tracked as VWB-30** (filed 2026-07-09).

### 17. [P2] Problem-report actionLog captures the OLDEST 200 log entries, dropping the most recent (bug-relevant) ~800

- **Where:** `ui/src/lib/reportEvidence.ts:91`
- **Subsystem / dimension:** ui-api-hooks / correctness
- **Verifier verdict:** CONFIRMED

**What:** collectUiEvidence() uses entries.slice(-RING_MAX) on a newest-first array, so it returns the oldest entries instead of the newest.

**Failure scenario:** useLogStore.addLog() unshifts new entries to index 0 and caps the store at runtimeConfig.maxLogEntries = 1000 (useLogStore.ts:26,29). So entries[] is ordered newest-first. When a user hits a bug and presses the navbar bug button after ~1000 actions have accumulated, collectUiEvidence does entries.slice(-200), which returns the array TAIL = the 200 OLDEST log lines and silently drops the ~800 most recent — i.e. exactly the actions leading up to the failure the report is about. The ui_evidence.actionLog attached to POST /reports is therefore stale/irrelevant for any long-lived session, defeating the evidence ring's purpose.

**Evidence:** reportEvidence.ts:91 `actionLog: useLogStore.getState().entries.slice(-RING_MAX)` vs useLogStore.ts:26 `state.entries.unshift(newEntry)` (newest-first) and runtime.ts:49 `maxLogEntries: 1000` (> RING_MAX=200).

**Suggested fix:** Take the newest slice: `entries.slice(0, RING_MAX)` (entries are newest-first).

**Verifier reasoning:** Independently confirmed. useLogStore.ts:26 uses state.entries.unshift(newEntry), so the store is newest-first, and lines 29-30 cap it at runtimeConfig.maxLogEntries = 1000 (runtime.ts:49). In reportEvidence.ts:91, collectUiEvidence does useLogStore.getState().entries.slice(-RING_MAX) with RING_MAX=200 (line 8). slice(-200) on a newest-first array returns the array TAIL = the 200 OLDEST entries, dropping up to ~800 most recent ones — the actions immediately preceding the reported bug. The finding's quotes and mechanism are accurate, and the failure reproduces for any session exceeding 200 log entries. The suggested fix slice(0, RING_MAX) is correct. Contrast: the file's own consoleRing/apiRing use push()+splice(0,...) keeping the newest tail, so only the entries slice direction is wrong. P2 is appropriate — this corrupts problem-report evidence quality, not physical device actuation.

> **Tracked as UI-14** (filed 2026-07-09).

### 18. [P2] ForceReconcileDialog.close() resets expanded/results but not `pending`, stranding the dialog on quick reopen during an in-flight force

- **Where:** `ui/src/components/ForceReconcileDialog.tsx:53`
- **Subsystem / dimension:** ui-runtime / correctness
- **Verifier verdict:** CONFIRMED

**What:** close() clears `expanded` and `results` but leaves `pending` set; a force that is still in flight when the dialog is dismissed keeps `pending !== null`, which disables every row and every Confirm button on the next open until the old request resolves.

**Failure scenario:** User taps 'Send anyway' on a device row (setPending(deviceId), await force.mutateAsync — which can legitimately take several seconds since it runs the full gated chain incl. a poll timeout server-side). Before it resolves the user clicks the backdrop / Close. close() runs but does not reset pending. The user immediately reopens the dialog: renderRow computes tappable = row.reconcilable && !pending -> false for ALL rows (no row can expand), and Confirm buttons are disabled via `pending !== null`. The dialog is unusable until the earlier mutateAsync resolves. Additionally, when that stale request finally resolves it calls setResults on the freshly-cleared results map, surfacing a result message from the previous session.

**Evidence:** ForceReconcileDialog.tsx:53-57 close() sets expanded=null and results={} but omits pending; renderRow (line 84) tappable=row.reconcilable && !pending and confirm button disabled={isPending || pending !== null} (line 141).

**Suggested fix:** Reset pending in close() (setPending(null)), or clear pending/results in a useEffect keyed on `open` so each dialog open starts from a clean interaction state.

**Verifier reasoning:** Independently confirmed. The dialog is always mounted — RuntimeScenarioPage.tsx:169-173 renders it unconditionally with open={reconcileOpen}, and ForceReconcileDialog's `if (!open) return null` (line 51) returns null without unmounting, so useState `pending` (line 48) persists across close/reopen. close() (lines 53-57) resets expanded and results but omits setPending(null); pending is only cleared at line 77 after `await force.mutateAsync`. If the user clicks Close/backdrop during an in-flight force (which runs the full server-side gated chain incl. poll timeout, taking seconds — nothing blocks closing), pending stays set to the deviceId. On reopen, `tappable = row.reconcilable && !pending` (line 84) is false for ALL rows because pending is a truthy string, so no row can expand, and Confirm is disabled via `pending !== null` (line 141) — the dialog is unusable until the stale request resolves. The stale-result leak (setResults at line 66 writing into the cleared map) is also real. It self-heals when the old request resolves, and it violates no state-sync/idempotence/force invariant and causes no physical mis-actuation, so P2 (UI-only, temporary) is the correct severity.

> **Tracked as UI-15** (filed 2026-07-09).

### 19. [P2] Force re-tap arms for non-power controls (e.g. eMotiva set_volume) but only PowerZone buttons show the armed pulse

- **Where:** `ui/src/components/RemoteControlLayout.tsx:1128`
- **Subsystem / dimension:** ui-runtime / correctness
- **Verifier verdict:** PLAUSIBLE

**What:** handleAction arms the force offer on ANY idempotence skip, but the armed-pulse affordance (forceOfferAction) is passed only to PowerZone, so a skipped non-power control shows the banner with no indicated re-tap target.

**Failure scenario:** On an eMotiva device page the user drags the volume slider to the value the bridge already believes is set. The backend handle_set_volume (driver.py:1274) returns skipped_reason='idempotence'; RuntimeDevicePage.handleAction (line 113) calls armForceOffer('set_volume', deviceId). The amber '⚡ tap again to send anyway' banner appears, but VolumeZone never receives forceOfferAction (only PowerZone gets it at RemoteControlLayout.tsx:1128), so no slider/mute control pulses. The user sees the prompt but nothing indicates WHICH control to re-tap to force — the DRV-5 escape hatch is undiscoverable for every idempotence-guarded control outside the power zone.

**Evidence:** RemoteControlLayout.tsx:1128 passes forceOfferAction only to PowerZone; VolumeZone/MediaStackZone/ScreenZone/MenuZone get no such prop. Backend idempotence_skip fires on set_volume (emotiva driver.py:1274) which is dispatched through handleAction, not the dropdown path.

**Suggested fix:** Thread forceOffer?.actionName into every zone that renders idempotence-guardable controls (at minimum VolumeZone for mute/set_volume) and apply the same armedClass pulse, or scope armForceOffer to only arm for controls that can display the affordance.

**Verifier reasoning:** The mechanical claim is accurate and reproduces in code: RuntimeDevicePage.handleAction (lines 111-116) arms the force offer on ANY idempotence skip including VolumeZone's set_volume/mute (VolumeZone dispatches via the same onAction→handleAction at RemoteControlLayout.tsx:522), the amber banner renders globally (line 1107), yet the armedClass pulse and forceOfferAction prop exist only in PowerZone (lines 93-95, 1128) — VolumeZone/MediaStackZone/ScreenZone/MenuZone/PointerZone never receive it. So a non-power idempotence skip shows the banner without any control pulsing. However, the finding overstates the impact by labeling it a correctness bug and calling the escape hatch 'undiscoverable': the global banner explicitly instructs 'Tap again to send anyway' (line 55), the user just pressed the control so the target is not ambiguous, and the functional re-tap-to-force path (handleAction forced check, lines 104-109, keyed on forceOffer.actionName === action) works for every zone regardless of the missing pulse. Nothing mis-actuates and no state desyncs — this is a real but low-priority UX affordance-consistency gap (power zone glows, other zones don't), not a correctness defect, so PLAUSIBLE at P2 rather than a confirmed correctness bug.

> **Tracked as UI-14** (filed 2026-07-09).

---

## Refuted (kept for transparency)

- **[P2] scenarios-reconciler: Forced-toggle assume_state uses raw on_value — a non-string on_value silently defeats the claim-the-target correction** — The finding's three code quotes are all accurate: reconciler.py:212 sets `params["assume_state"] = cap.on_value` on the toggle path, models.py:146/208 type `on_value: str | bool | int`, and driver.py:214 only honors `assume_state in ("on","off")` else blind-flips. However, the failure scenario cannot occur in any valid configuration. The `assume_state` param is consumed exclusively by the WirenboardIR `power_toggle_handler`, whose power state field is always a string (`self.state.power` is set to the strings "on"/"off" at driver.py:217/224). If such a device declared a bool `on_value`, the normal reconcile diff at reconciler.py:201 (`_state_value(state, cap.state_field) == cap.on_value`) would compare a string power state against `True` and never match — the device would be re-actuated on every reconcile regardless of force, i.e. a globally broken config, not an SCN-11-specific defect. The sole shipped bool-`on_value` device is Auralic (state_field `connected: true`), which is a network device with explicit `on`/`off` actions, so `is_toggle` is false and `assume_state` is never emitted, and it does not route through the WB IR toggle handler at all. Every real toggle-power device (vhs_player, ld_player, mf_amplifier, video, EMotivaXMC2 zone2) carries `on_value: "on"`. Thus the described desync-mirror is unreachable; the residual concern is only a missing type validator (a latent hardening item the finding itself grades P2/latent), not a reproducible correctness bug that can misactuate the house.

---

## Remediation task map

| Finding(s) | Sev | Task | Milestone |
|---|---|---|---|
| #2 MQTT reconnect never resets | P0 | **CORE-9** | `[release]` (fixed 2026-07-09) |
| #3 select-form drops force | P1 | **DRV-21** | `[release]` |
| #6 teardown ignores reconcile:false | P1 | **SCN-12** | `[release]` |
| #7 SSE dies after maxRetries | P1 | **UI-13** | `[release]` |
| #13/#14/#15/#16 reports evidence hardening | P2 | **VWB-30** | `[release]` (pulled forward) |
| #17/#19 UI runtime nits | P2 | **UI-14** | `[release]` (pulled forward) |
| #1/#4/#5/#9/#12 broker & device secret handling | P0/P1/P2 | **CORE-8** | `[deferred]` (productization; user call 2026-07-09) |
| #8 avail→503 mapping | P2 | **VWB-31** | `[deferred]` |
| #10 IR last_command overwrite | P2 | **DRV-22** | `[deferred]` |
| #11 startup-cleanup WB-offline symmetry | P2 | **OPS-18** | `[deferred]` |
| #18 re-tap non-power pulse (PLAUSIBLE) | P2 | **UI-15** | `[deferred]` (fold feel-check into REL-3) |

**Note on #1 (P0 severity, deferred milestone):** the broker-credential exposure is a genuine P0 finding, but the owner scoped its remediation to productization (proper secrets management + optional API auth) on 2026-07-09 — the release ships on a trusted home LAN. Rotating the currently-committed password is a separate near-term user op.
