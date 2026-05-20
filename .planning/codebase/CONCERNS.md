# Codebase Concerns

**Analysis Date:** 2026-05-20

## Tech Debt

**Excessive DEBUG logging in production code:**
- Issue: Multiple device drivers (`emotiva_xmc2/driver.py`, `mqtt/client.py`) contain profuse `[DEBUG]` prefixed log statements hardcoded throughout callbacks, state updates, and command execution. These are detailed enough for live troubleshooting but clutter the codebase and hurt maintainability.
- Files: `src/wb_mqtt_bridge/infrastructure/devices/emotiva_xmc2/driver.py`, `src/wb_mqtt_bridge/infrastructure/mqtt/client.py`
- Impact: Code readability; debugging-era instrumentation never cleaned up; makes it harder to spot real logic errors vs. instrumentation
- Fix approach: Extract debug logging into a separate debug module or debug decorator; make it opt-in via environment variable. Clean up the emotiva driver and mqtt client to use standard logger.debug() calls instead of inline strings.

**TODO comment in service cleanup:**
- Issue: Placeholder TODO in `RoomManager` at `src/wb_mqtt_bridge/domain/rooms/service.py:203` ("Add any cleanup operations if needed in the future") indicates incomplete lifecycle management.
- Files: `src/wb_mqtt_bridge/domain/rooms/service.py:203`
- Impact: Potential resource leaks if rooms manage stateful resources later
- Fix approach: Either implement the cleanup or remove the placeholder with a documented decision

**Complex device drivers without module-level documentation:**
- Issue: `LgTv` (2556 LoC), `AppleTVDevice` (1849 LoC), `EmotivaXMC2` (1548 LoC), and `AuralicDevice` (1334 LoC) are large, complex state machines. Little inline documentation explains the state transitions, reconnection logic, or error recovery flows.
- Files: `src/wb_mqtt_bridge/infrastructure/devices/lg_tv/driver.py`, `src/wb_mqtt_bridge/infrastructure/devices/apple_tv/driver.py`, `src/wb_mqtt_bridge/infrastructure/devices/emotiva_xmc2/driver.py`, `src/wb_mqtt_bridge/infrastructure/devices/auralic/driver.py`
- Impact: Difficult to reason about edge cases; high probability of bugs on code changes; onboarding friction
- Fix approach: Add module-level docstrings with state machine diagrams or flowcharts; annotate complex methods with intent and assumptions

**Bare `except Exception` blocks:**
- Issue: Error handlers throughout device base and specific implementations catch `Exception` generically and log/return without recovery strategy
- Files: `src/wb_mqtt_bridge/infrastructure/devices/base.py` (multiple occurrences)
- Impact: Swallows unexpected errors (e.g., `KeyboardInterrupt` might be caught); makes debugging harder; no distinction between recoverable and fatal errors
- Fix approach: Catch specific exception types; re-raise or handle `BaseException` subclasses like `SystemExit` and `KeyboardInterrupt` separately

---

## Known Bugs & Functional Gaps

**Scenario execution is broken:**
- Issue: Per the action plan (§P0.5, #12), scenarios do not execute end-to-end on hardware. Confirmed by user 2026-05-20. Root cause not yet diagnosed — may be startup/shutdown sequencing, condition evaluation, role-action dispatch, WB-adapter integration, or state persistence.
- Files: `src/wb_mqtt_bridge/domain/scenarios/scenario.py`, `src/wb_mqtt_bridge/domain/scenarios/service.py`, `src/wb_mqtt_bridge/infrastructure/scenarios/wb_adapter.py`
- Trigger: Enable any scenario (e.g., `movie_appletv`) and attempt to invoke it via the API or WB virtual device
- Workaround: None; scenarios cannot be used currently
- Priority: **Critical — blocks the project's #1 success criterion ("my house works")**

**Auralic device subscription timeout (10-second hardcoded limit):**
- Issue: `src/wb_mqtt_bridge/infrastructure/devices/auralic/driver.py:382` has a comment flagging a known 10-second subscription timeout issue. The underlying cause (future.result(timeout=10) in line 332) is a hard timeout on UPnP subscription setup.
- Files: `src/wb_mqtt_bridge/infrastructure/devices/auralic/driver.py:260-332, 382`
- Impact: Auralic device may fail to initialize on slow networks or if discovery takes longer than 10 seconds
- Workaround: None
- Fix approach: Increase timeout or implement exponential backoff + retry

**LG TV SSL certificate verification always disabled by default:**
- Issue: `src/wb_mqtt_bridge/infrastructure/devices/lg_tv/driver.py:130-132` hardcodes `verify_ssl = False` for WebOS TV connections due to self-signed certificates. While documented and configurable, this defaults to insecure and may be overlooked.
- Files: `src/wb_mqtt_bridge/infrastructure/devices/lg_tv/driver.py:130-132, 592-595`
- Impact: MITM vulnerability on the local network if hostile actor is present
- Fix approach: Recommend certificate extraction as primary path; implement optional certificate pinning; document the security trade-off clearly

---

## Security Considerations

**No input validation on scenario conditions:**
- Risk: `ScenarioDefinition` conditions are stored as strings and evaluated via property lookups and string pattern matching. No schema validation or safe expression language — arbitrary property names could be injected.
- Files: `src/wb_mqtt_bridge/domain/scenarios/models.py`, `src/wb_mqtt_bridge/domain/scenarios/scenario.py:104-150`
- Current mitigation: Conditions are admin-configured (not user-supplied), so the attack surface is limited to the person running the server
- Recommendations: (1) Document that scenario configs must be treated as trusted admin input; (2) add explicit validation for condition field names against the known device state schema; (3) consider a safer expression DSL (e.g., JSON logic) if scenarios become user-facing

**GitHub PAT in plaintext on deployed Wirenboard:**
- Risk: `docker_manager_config.json` on the Wirenboard device contains a personal access token for GitHub API. If the device is compromised, the PAT can be exfiltrated to trigger arbitrary workflows.
- Files: `docker_manager_config.json` (user-specific, not in repo)
- Current mitigation: File is likely guarded by Wirenboard authentication and is not uploaded to version control
- Recommendations: (1) Use GitHub's fine-grained PATs with minimal scopes; (2) rotate PAT periodically; (3) consider using GitHub's OIDC token exchange instead of long-lived PATs; (4) document secure PAT setup in deployment guide

**Dependency pinning for critical git sources:**
- Risk: Two device libraries are git-pinned to specific branches or commits (`openhomedevice` to `remove-lxml-dependency`, `pyatv` to commit `f75e718...`). If those upstream repos are deleted, rebuilt, or force-pushed, the build becomes unrecoverable.
- Files: `pyproject.toml:51-53`
- Current mitigation: Both are actively maintained projects; low short-term risk
- Recommendations: (1) Vendor the git deps into a `vendor/` directory or sub-repository if upstream disappears; (2) or: push PRs upstream to get merged and switch to PyPI versions; (3) set up periodic CI checks to verify git sources are still available

---

## Performance Bottlenecks

**Synchronous UPnP discovery in Auralic device initialization:**
- Problem: `src/wb_mqtt_bridge/infrastructure/devices/auralic/driver.py:187` uses blocking `requests.get()` inside an async context during device discovery. While technically awaited, this blocks the event loop if the network is slow.
- Files: `src/wb_mqtt_bridge/infrastructure/devices/auralic/driver.py:184-191, 260-271`
- Cause: Legacy code from pre-async refactor; `requests` library is synchronous
- Improvement path: Replace `requests.get()` with `aiohttp` or `httpx` async methods for network calls during discovery

**Large device driver files with complex state machines:**
- Problem: `LgTv` (2556 LoC), `AppleTVDevice` (1849 LoC), and `EmotivaXMC2` (1548 LoC) are monolithic. Each combines connection management, callback registration, state synchronization, and command dispatch in one file.
- Files: `src/wb_mqtt_bridge/infrastructure/devices/lg_tv/driver.py`, `src/wb_mqtt_bridge/infrastructure/devices/apple_tv/driver.py`, `src/wb_mqtt_bridge/infrastructure/devices/emotiva_xmc2/driver.py`
- Cause: Incremental feature additions without refactoring boundaries
- Improvement path: Extract connection state machine, callback handler, and command dispatch into separate internal modules (e.g., `lg_tv/connection.py`, `lg_tv/command_handler.py`)

---

## Fragile Areas

**Emotiva device reconnection logic:**
- Files: `src/wb_mqtt_bridge/infrastructure/devices/emotiva_xmc2/driver.py:630-640, 793-805, 971-983, 1118-1130, 1258-1270`
- Why fragile: Each command method (`power_on`, `power_off`, `set_input`, `set_volume`, `mute_toggle`) contains almost identical reconnection logic with inline state checks. If a reconnection edge case is discovered, it must be fixed in five places simultaneously.
- Safe modification: Extract the reconnection check into a helper method; use it before every command
- Test coverage: Commands are tested individually but there is no integration test for the full reconnection-on-failure flow

**MQTT message dispatch with generic wildcards:**
- Files: `src/wb_mqtt_bridge/infrastructure/mqtt/client.py:235-275`
- Why fragile: The message handler routing uses wildcard pattern matching with a fallback for exact matches. The order of evaluation matters but is not clearly documented. A new wildcard subscription could silently intercept messages meant for more specific handlers.
- Safe modification: Document handler precedence explicitly; add tests for handler precedence conflicts
- Test coverage: Limited; no test for overlapping wildcard subscriptions

**State persistence without transaction boundaries:**
- Files: `src/wb_mqtt_bridge/infrastructure/persistence/sqlite.py:84-145`
- Why fragile: The SQLite state store uses simple get/set operations without transactions. If the process crashes between reading a device state and writing it back after a command, the state will be stale.
- Safe modification: Implement transactional read-modify-write semantics; or document that state persistence is best-effort
- Test coverage: Unit tests exist but do not cover crash scenarios or concurrent writes

---

## Scaling Limits

**No horizontal scaling for stateful device connections:**
- Current capacity: Single process, single MQTT connection, all devices connected to the same instance
- Limit: If the machine restarts or is replaced, all device connections drop and must be re-established. No active-active or active-passive failover.
- Scaling path: (1) Add device state replication to external state store (Redis); (2) implement device connection pooling or proxy; (3) research HA patterns for device integration (likely a future P4 task)

**Event streaming bandwidth not limited:**
- Current capacity: SSE streams to UI with no backpressure or rate limiting. If the UI is slow to consume, events queue in memory.
- Limit: A misbehaving or slow UI client could cause the backend to accumulate unbounded event buffers
- Scaling path: (1) Add event queue depth limits and drop old events if buffer fills; (2) implement client-side ack handshakes; (3) compress SSE payloads

---

## Dependencies at Risk

**Git-pinned dependencies without fallback:**
- Risk: `openhomedevice` and `pyatv` are both loaded from specific git branches/commits. If those upstream repos are deleted, moved, or force-pushed, builds will fail permanently.
- Impact: Build failures; impossible to deploy without manual intervention
- Migration plan: (1) Create a bot to periodically check git source availability and alert; (2) vendorize or mirror the sources if upstream becomes unreliable; (3) push any custom changes (e.g., the ARM lxml fix) upstream and switch to PyPI versions

**PyPI versions without upper bounds:**
- Risk: Dependencies like `fastapi>=0.103.0`, `pydantic>=2.11.0`, and `aiomqtt>=1.0.0` use lower-bound version constraints but no upper bounds. A breaking change in a minor release could silently break the app.
- Impact: Silent incompatibilities; hard-to-debug runtime errors
- Migration plan: (1) Add upper-bound constraints (e.g., `pydantic>=2.11.0,<3`); (2) set up dependabot or Renovate to detect and test upgrades; (3) pin to exact versions in production if stability is critical

---

## Missing Critical Features

**No scenario lifecycle state machine:**
- Problem: Scenarios do not track initialization state (booting, booted, running, shutdown). Commands can be dispatched to uninitialized scenarios. No guards prevent re-initialization or command dispatch during shutdown.
- Blocks: Robust scenario execution; safe scenario switching
- Scope: Needs explicit state machine in `src/wb_mqtt_bridge/domain/scenarios/scenario.py`

**No device command queuing or rate limiting:**
- Problem: Commands sent to a device in rapid succession may race or overload the device's command buffer. No backpressure mechanism.
- Blocks: Reliable execution of rapid multi-step scenarios (e.g., power on → wait → set input → set volume)
- Scope: Command queue in BaseDevice; rate limiting per device type

**No rollback or undo for scenario actions:**
- Problem: If a scenario startup succeeds partially (e.g., TV powers on but receiver fails), there is no automated way to revert the TV power change.
- Blocks: Atomic scenarios; safe scenario switching
- Scope: Transactional scenario execution with rollback

---

## Test Coverage Gaps

**No integration tests for device reconnection:**
- What's not tested: The full reconnection flow when a device becomes unreachable mid-command. Unit tests mock the library; integration tests with a real (or simulated) device going offline and coming back online are missing.
- Files: `tests/devices/` (existing device test files)
- Risk: Reconnection logic bugs are not caught until production; no confidence in recovery behavior
- Priority: High

**No scenario end-to-end tests:**
- What's not tested: Scenario initialization, condition evaluation, action dispatch, and shutdown end-to-end. Current tests cover components in isolation (Unit tests for `scenario.py` logic, mocked device calls).
- Files: `tests/unit/test_scenario.py` — covers the Scenario class directly but not real device execution
- Risk: The critical bug (scenarios don't work) was not caught by existing tests
- Priority: Critical

**No WB virtual device integration tests:**
- What's not tested: The full integration between a scenario and the Wirenboard emulation layer. Device state updates and scenario state-to-WB sync are not tested together.
- Files: `tests/unit/test_wb_virtual_device_service.py` — 31 unit tests, but no integration with actual device state changes
- Risk: WB virtual device may not reflect true device state or scenario state
- Priority: High

**No MQTT reconnection tests:**
- What's not tested: The MQTT client reconnection flow, message buffering during disconnection, and handler re-subscription after reconnect.
- Files: `tests/test_integration.py` — has basic MQTT setup tests but not disconnection/reconnection scenarios
- Risk: Message loss or handler deregistration during network glitches
- Priority: Medium

**No API concurrency tests:**
- What's not tested: Concurrent API requests (e.g., two scenario activations at the same time, device commands while state is being read). No race condition detection.
- Files: `tests/test_integration.py`, `tests/unit/test_scenario_manager.py`
- Risk: Deadlocks, state corruption, or lost updates under load
- Priority: Medium

---

## Architectural Concerns

**Unguarded global state in bootstrap:**
- Issue: `src/wb_mqtt_bridge/app/bootstrap.py:97-102` initializes module-level variables (`config_manager`, `device_manager`, `mqtt_client`, `state_store`) as `None`, then mutates them in the lifespan context. This relies on Python's GIL and implicit ordering; not thread-safe if the server ever becomes multi-threaded.
- Files: `src/wb_mqtt_bridge/app/bootstrap.py:97-150`
- Impact: If FastAPI is ever configured to use multiple worker processes, these globals will be inconsistent across workers
- Fix: Use dependency injection via FastAPI's dependency system or a singleton pattern with explicit locking

**Circular dependency potential in device→scenario:**
- Issue: Devices can execute scenario actions (via `src/wb_mqtt_bridge/domain/devices/service.py`), and scenarios execute device actions (via `src/wb_mqtt_bridge/domain/scenarios/scenario.py`). There's no guard against a scenario that executes an action that triggers a scenario action (A → B → A).
- Files: `src/wb_mqtt_bridge/domain/scenarios/scenario.py:52-83`, `src/wb_mqtt_bridge/domain/devices/service.py:150+`
- Impact: Stack overflow or deadlock if a scenario inadvertently creates a loop
- Fix: Add a depth counter or visited-set to detect cycles; document the anti-pattern

---

## Code Quality Issues

**Inconsistent error handling patterns:**
- Issue: Some modules raise custom exceptions (`ScenarioError`, `ScenarioExecutionError`), others return error dicts, others log and swallow. No unified error contract.
- Files: `src/wb_mqtt_bridge/domain/scenarios/scenario.py`, `src/wb_mqtt_bridge/infrastructure/devices/base.py`, `src/wb_mqtt_bridge/domain/devices/service.py`
- Impact: Callers must handle multiple error patterns; inconsistent recovery strategies
- Fix: Define a single error handling strategy (exception types or result enums); apply consistently

**DEBUG print statements in bootstrap:**
- Issue: `src/wb_mqtt_bridge/app/bootstrap.py:124, 133` use `print()` instead of logger. These bypass the logging system and appear on stderr, making them noisy and hard to filter.
- Files: `src/wb_mqtt_bridge/app/bootstrap.py:124, 133`
- Impact: Noise in logs; difficult to suppress in production; inconsistent with the rest of the codebase
- Fix: Replace with `logger.debug()` or `logger.info()`

---

*Concerns audit: 2026-05-20*
