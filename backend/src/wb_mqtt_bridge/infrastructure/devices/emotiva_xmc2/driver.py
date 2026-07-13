import logging
import asyncio
import time
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, Union, Tuple

# Updated imports for new library
from pymotivaxmc2 import EmotivaController
from pymotivaxmc2.enums import Property, Zone

from wb_mqtt_bridge.infrastructure.devices.base import BaseDevice
from wb_mqtt_bridge.domain.devices.models import EmotivaXMC2State, LastCommand
from wb_mqtt_bridge.infrastructure.config.models import EmotivaConfig as AppEmotivaConfig, EmotivaXMC2DeviceConfig, StandardCommandConfig, CommandParameterDefinition
from wb_mqtt_bridge.domain.devices.types import CommandResponse, CommandResult

logger = logging.getLogger(__name__)

# Define enums for strongly typed states
class PowerState(str, Enum):
    """Power state enum for eMotiva device."""
    ON = "on"
    OFF = "off"
    UNKNOWN = "unknown"

class EMotivaXMC2(BaseDevice[EmotivaXMC2State]):
    # Narrow self.config so pyright sees EmotivaXMC2DeviceConfig-shaped fields.
    config: EmotivaXMC2DeviceConfig

    """eMotiva XMC2 processor device implementation.
    
    This class implements control for the Emotiva XMC-2 processor using the pymotivaxmc2 library.
    
    Input Selection:
    - Inputs are the device's logical sources (Input buttons), addressed by the canonical
      'source1'..'source8' token.
    - The driver maps 'sourceN' to the device's select_source(N), and maps the device's
      reported source NAME ("ZAPPITI") back to 'sourceN' via get_input_names(). This
      device-specific translation lives here so the reconciler stays device-agnostic.
    
    State Management:
    - The device maintains state for power, volume, mute, inputs, etc.
    - Properties are automatically tracked via callbacks from the controller
    """
    
    # Define standard properties to monitor for consistent usage across methods
    PROPERTIES_TO_MONITOR = [
        Property.POWER,              # Main zone power
        Property.ZONE2_POWER,        # Zone 2 power
        Property.VOLUME,             # Main volume
        Property.ZONE2_VOLUME,       # Zone 2 volume
        Property.SOURCE,             # Current input
        Property.AUDIO_INPUT,        # Audio input
        Property.VIDEO_INPUT,        # Video input
        Property.AUDIO_BITSTREAM,    # Audio bitstream format
        Property.SELECTED_MODE,      # Audio processing mode
        Property.KEEPALIVE,          # DRV-30: protocol V3 heartbeat (wedge/reboot detection)
    ]

    # --- DRV-30 timing (REL-3 rack findings, docs/review/rel3_rack_findings_2026-07-10.md) ---
    # The transponder advertises the real keepAlive interval (7500 ms on the XMC-2);
    # this is only the fallback if discovery info is unavailable.
    KEEPALIVE_INTERVAL_FALLBACK_S = 7.5
    # Missed beats before the device counts as unreachable. The 2026-07-10 wedge burned
    # 2×9 s of blind command retries; three missed 7.5 s beats (~22 s) is the detection
    # bound that replaces them with a fail-fast, speakable error.
    KEEPALIVE_MISS_LIMIT = 3
    # Post-power-on readiness (DRV-38: held for EVERY control-port command at the
    # dispatch seam, not just input switches): a clean power-up delivers its full
    # property burst in < 1 s (3 hardware samples 2026-07-10); 2 s of silence = settled.
    INPUT_QUIESCENCE_S = 2.0
    # Hard cap on the readiness hold — a lost packet must never deadlock a scenario.
    # Also the FULL hold for the fresh-'arc' case: two incidents prove the handshake
    # window is fatal (set_input 3.3 s in, 2026-07-10; zone2_power_on 2.3 s after the
    # arc claim, 2026-07-12) and its CEC traffic is invisible to us, so ANY command
    # inside a fresh-'arc' window waits the whole cap. Tune at the DRV-32 bench.
    INPUT_READY_TIMEOUT_S = 15.0

    def __init__(self, config: EmotivaXMC2DeviceConfig, mqtt_client=None):
        """Initialize the EMotivaXMC2 device.
        
        Args:
            config: Device configuration
            mqtt_client: MQTT client for publishing messages
        """
        super().__init__(config, mqtt_client)
        
        self.client: Optional[EmotivaController] = None

        # Add a lock to protect setup from concurrent calls
        self._setup_lock = asyncio.Lock()

        # Logical-source (Input button) maps, pulled from the device via get_input_names().
        # index (1-8) -> {"name": str, "visible": bool}; normalized source name -> index.
        self._source_buttons: Dict[int, Dict[str, Any]] = {}
        self._source_index_by_name: Dict[str, int] = {}

        # --- DRV-30: heartbeat watchdog + post-power-on readiness bookkeeping ---
        # Monotonic timestamps: wall-clock jumps must not fake or mask a heartbeat.
        self._last_notification_monotonic: Optional[float] = None
        self._power_on_monotonic: Optional[float] = None
        self._keepalive_interval_s: float = self.KEEPALIVE_INTERVAL_FALLBACK_S
        self._keepalive_task: Optional[asyncio.Task] = None
        # True after the watchdog declares the device gone (wedge / wall-unplug).
        # Commands fail fast while set (force bypasses); the watchdog probes for
        # recovery by re-subscribing — device-side subscriptions die with the device.
        self._heartbeat_lost: bool = False
        
        # Initialize device state with Pydantic model
        self.state: EmotivaXMC2State = EmotivaXMC2State(
            device_id=self.config.device_id,
            device_name=self.config.names.ru,
            zone2_power=None,
            input_source=None,
            video_input=None,
            audio_input=None,
            volume=None,
            mute=None,
            audio_mode=None,
            audio_bitstream=None,
            connected=False,
            ip_address=None,
            mac_address=None,
            startup_complete=False,
            notifications=False,
            last_command=None,
            error=None
        )
        
    async def setup(self) -> bool:
        """Initialize the device.
        
        Returns:
            bool: True if setup was successful, False otherwise
        """
        async with self._setup_lock:
            # Double-checked locking: if already connected, return early
            if self.client and self.state.connected:
                return True
            try:
                # Get emotiva configuration directly from config
                emotiva_config: AppEmotivaConfig = self.config.emotiva
                
                # Get the host IP address
                host = emotiva_config.host
                if not host:
                    logger.error(f"Missing 'host' in emotiva configuration for device: {self.get_name()}")
                    self.set_error("Missing host configuration")
                    return False
                
                # Store MAC address if available in config
                if emotiva_config.mac:
                    self.update_state(mac_address=emotiva_config.mac)
                    
                logger.info(f"Initializing eMotiva XMC2 device: {self.get_name()} at {host}")
                
                # Create and initialize controller with simplified constructor
                try:
                    self.client = EmotivaController(
                        host=host,
                        timeout=emotiva_config.timeout or 5.0,
                        protocol_max="3.1"  # Use the most recent protocol version
                    )
                    
                    # Update state with IP address at this point
                    self.update_state(ip_address=host)
                except Exception as e:
                    logger.error(f"Failed to create controller for {self.get_name()}: {str(e)}")
                    self.set_error(f"Controller initialization error: {str(e)}")
                    return False
                
                # Connect to the device with retry logic
                max_retries = emotiva_config.max_retries or 3
                retry_delay = emotiva_config.retry_delay or 2.0
                
                for attempt in range(1, max_retries + 1):
                    try:
                        if self.client is not None:
                            await self.client.connect()
                        logger.info(f"Connected to device at {host} on attempt {attempt}")
                        break
                    except Exception as e:
                        if attempt < max_retries:
                            logger.warning(f"Connection attempt {attempt} failed: {str(e)}. Retrying in {retry_delay} seconds...")
                            await asyncio.sleep(retry_delay)
                        else:
                            logger.error(f"Failed to connect to device at {host} after {max_retries} attempts: {str(e)}")
                            self.set_error(f"Connection error: {str(e)}")
                            return False
                
                # Set up callbacks for property changes
                for prop in self.PROPERTIES_TO_MONITOR:
                    self._register_property_callback(prop)
                
                # Build the logical-source map first so SOURCE values dispatched by
                # subscribe() (or any later notification) resolve to a 'sourceN' token.
                try:
                    await self._refresh_source_map()
                except Exception as e:
                    logger.warning(f"Failed to load source map during setup: {str(e)}")

                # Attempt to subscribe to properties. pymotivaxmc2 0.6.9 dispatches the
                # subscribe response's initial values through the registered @on(prop)
                # callbacks (the same path as ongoing notifications). State is seeded
                # via _handle_property_change as a side-effect — no separate refresh needed.
                try:
                    await self.client.subscribe(self.PROPERTIES_TO_MONITOR)
                    logger.info(f"Successfully subscribed to properties for {self.get_name()}")

                    # Update state with successful connection
                    self.clear_error()
                    self.update_state(
                        connected=True,
                        ip_address=host,
                        startup_complete=True,
                        notifications=True
                    )

                    # DRV-30: start the heartbeat watchdog on the device-advertised
                    # keepAlive interval (transponder packet; the library keeps it in
                    # its discovery info — no public accessor yet, hence getattr).
                    info = getattr(self.client, "_info", None) or {}
                    ka_ms = info.get("keepAlive")
                    if ka_ms:
                        self._keepalive_interval_s = float(ka_ms) / 1000.0
                    self._heartbeat_lost = False
                    self._last_notification_monotonic = time.monotonic()
                    if self._keepalive_task is None or self._keepalive_task.done():
                        self._keepalive_task = asyncio.create_task(self._keepalive_watchdog())

                    # Publish connection status
                    await self.emit_progress(f"Connected to {self.get_name()} at {host}", "action_progress")

                    return True
                except Exception as e:
                    # Handle subscription failure
                    error_message = f"Error subscribing to properties: {str(e)}"
                    logger.error(error_message)
                    
                    # The device might be in standby mode if subscription fails
                    # Try to continue if force_connect is enabled
                    if emotiva_config.force_connect:
                        logger.warning("Force connect enabled, continuing with setup despite subscription failure")
                        
                        # Update state assuming standby mode
                        self.update_state(
                            connected=True,
                            ip_address=host,
                            startup_complete=True,
                            notifications=False,
                            power=PowerState.OFF  # Assume standby mode which is a valid state
                        )
                        
                        # Set error but don't fail setup
                        self.set_error(f"Subscription failed, using forced connection: {error_message}")
                        
                        # Publish connection status with warning
                        await self.emit_progress(f"Connected to {self.get_name()} at {host} in force connect mode (limited functionality)", "action_progress")
                        
                        return True
                    else:
                        self.set_error(error_message)
                        return False

            except Exception as e:
                logger.error(f"Failed to initialize eMotiva XMC2 device {self.get_name()}: {str(e)}")
                self.set_error(f"Initialization error: {str(e)}")
                return False

    async def shutdown(self) -> bool:
        """Cleanup device resources and properly shut down connections.
        
        Returns:
            bool: True if shutdown was successful, False otherwise
        """
        if not self.client:
            logger.info(f"No client initialized for {self.get_name()}, nothing to shut down")
            return True
            
        logger.info(f"Starting shutdown for eMotiva XMC2 device: {self.get_name()}")

        # DRV-30: stop the heartbeat watchdog before tearing the client down.
        if self._keepalive_task is not None:
            self._keepalive_task.cancel()
            self._keepalive_task = None

        try:
            # Attempt to unsubscribe from notifications first
            try:
                await self.client.unsubscribe(self.PROPERTIES_TO_MONITOR)
                logger.debug(f"Successfully unsubscribed from properties for {self.get_name()}")
            except Exception as e:
                # Log but continue with shutdown even if unsubscribe fails
                logger.warning(f"Failed to unsubscribe from properties for {self.get_name()}: {str(e)}")
            
            # Let the library handle connection cleanup
            try:
                await self.client.disconnect()
                logger.info(f"Successfully disconnected {self.get_name()}")
            except Exception as e:
                logger.warning(f"Error during disconnect for {self.get_name()}: {str(e)}")
                # Continue with cleanup despite disconnect error
            
            # Update our state
            self.clear_error()
            self.update_state(
                connected=False,
                notifications=False
            )
            
            # Publish shutdown status
            await self.emit_progress(f"Disconnected from {self.get_name()}", "action_progress")
            
            # Release client reference
            self.client = None
            
            logger.info(f"eMotiva XMC2 device {self.get_name()} shutdown complete")
            return True
        except Exception as e:
            error_message = f"Failed to shutdown {self.get_name()}: {str(e)}"
            logger.error(error_message)
            self.set_error(str(e))
            
            # Still update state to reflect disconnection even if there was an error
            self.update_state(
                connected=False,
                notifications=False
            )
            
            # Release client reference even if there was an error
            self.client = None
            
            return False

    def _register_property_callback(self, property: Property):
        """Register a callback for a specific property change.
        
        Args:
            property: The property to monitor for changes
        """
        if not self.client:
            return
            
        # Use the new decorator pattern for callbacks
        @self.client.on(property)
        async def property_callback(value):
            # DEBUG: Enhanced callback logging
            logger.debug(f"[EMOTIVA_DEBUG] Hardware callback triggered: {property.value} = {value} (device={self.get_name()}, timestamp={datetime.now().isoformat()})")
            # Convert property enum value to lowercase for consistent handling
            property_name = property.value.lower()
            self._handle_property_change(property_name, None, value)
            
        # DEBUG: Log callback registration
        logger.debug(f"[EMOTIVA_DEBUG] Registering property callback for {property.value} (device={self.get_name()})")
        
    # Constants for valid properties
    VALID_PROPERTIES = {
        Property.POWER: "power",
        Property.ZONE2_POWER: "zone2_power",
        Property.VOLUME: "volume",
        Property.ZONE2_VOLUME: "zone2_volume",
        Property.SOURCE: "source",
        Property.AUDIO_INPUT: "audio_input",
        Property.VIDEO_INPUT: "video_input",
        Property.AUDIO_BITSTREAM: "audio_bitstream",
        Property.SELECTED_MODE: "selected_mode"
    }
    
    def _handle_property_change(self, property_name: str, old_value: Any, new_value: Any) -> None:
        """Handle property change events from the device state.
        
        Args:
            property_name: Name of the property that changed
            old_value: Previous value of the property
            new_value: New value of the property
        """
        # DEBUG: Enhanced property change logging
        logger.debug(f"[EMOTIVA_DEBUG] Property change callback: {property_name} = {old_value} -> {new_value} (device={self.get_name()}, connected={self.state.connected})")

        # DRV-30: every notification is proof of life. Record it for the watchdog and
        # the post-power-on quiescence gate; a notification arriving while the device
        # is considered gone means it came back with subscriptions intact.
        self._last_notification_monotonic = time.monotonic()
        if self._heartbeat_lost:
            self._heartbeat_lost = False
            self.clear_error()
            self.update_state(connected=True, notifications=True)
            logger.info(f"{self.get_name()}: heartbeat recovered (notification received)")

        # keepAlive carries no device state — it exists purely as the heartbeat.
        if property_name == "keepalive":
            return

        # Process the value with our helper
        processed_value = self._process_property_value(property_name, new_value)

        # DRV-30: an Off→On transition (ours or external — front panel, CEC) anchors
        # the post-power-on readiness window for input switching.
        if (
            property_name == "power"
            and processed_value == PowerState.ON
            and self.state.power != PowerState.ON
        ):
            self._power_on_monotonic = time.monotonic()
        
        # Map property changes to our state model
        updates = {}
        
        if property_name == "power":
            updates["power"] = processed_value
        elif property_name == "zone2_power":
            updates["zone2_power"] = processed_value
        elif property_name == "volume":
            updates["volume"] = processed_value
        elif property_name == "zone2_volume":
            updates["zone2_volume"] = processed_value
        # No mute / zone2_mute branches — the device never pushes either (Emotiva protocol
        # §4.2 has no notification entry; pymotivaxmc2's Property enum omits them).
        # Mute is optimistic-only in handle_mute_toggle.
        elif property_name == "source":  # device reports the source NAME ("ZAPPITI")
            updates["input_source"] = self._source_token(new_value)
        elif property_name == "video_input":
            updates["video_input"] = new_value
        elif property_name == "audio_input":
            updates["audio_input"] = new_value
        elif property_name == "audio_bitstream":
            updates["audio_bitstream"] = new_value
        elif property_name == "selected_mode":  # Changed from "audio_mode"
            updates["audio_mode"] = new_value
            
        # Apply state updates if any
        if updates:
            # DEBUG: Log state updates triggered by property changes
            logger.debug(f"[EMOTIVA_DEBUG] Property change triggering state update: {updates} (device={self.get_name()})")
            self.update_state(**updates)
    
    # --- DRV-30: heartbeat watchdog + readiness gate ---------------------------------

    async def _watchdog_tick(self) -> None:
        """One watchdog evaluation: declare the device gone after KEEPALIVE_MISS_LIMIT
        silent intervals, and while gone, probe for recovery by re-subscribing.

        Re-subscribe IS the correct probe: Emotiva subscriptions live in the DEVICE's
        memory, so a wall-unplug/reboot orphans us silently (REL-3 finding F4 — the
        bridge stayed deaf until restarted). Subscribing is idempotent per the protocol
        spec ("no penalty for subscribing to the same notification multiple times"),
        its ack proves liveness, and the subscribe response re-seeds state through the
        registered callbacks."""
        last = self._last_notification_monotonic
        if last is None or self.client is None:
            return
        silent_s = time.monotonic() - last
        limit_s = self.KEEPALIVE_MISS_LIMIT * self._keepalive_interval_s

        if silent_s <= limit_s and not self._heartbeat_lost:
            return

        if not self._heartbeat_lost:
            self._heartbeat_lost = True
            self.update_state(connected=False, notifications=False)
            self.set_error(
                f"heartbeat lost: no notifications for {silent_s:.0f}s "
                f"(keepAlive interval {self._keepalive_interval_s:.1f}s) — "
                "device wedged, rebooted, or unplugged; probing for recovery"
            )
            logger.error(f"{self.get_name()}: heartbeat lost after {silent_s:.0f}s of silence")
            await self.emit_progress(
                f"{self.get_name()} is unreachable (heartbeat lost)", "action_error"
            )

        # Recovery probe (also re-establishes subscriptions after a device reboot).
        try:
            await self.client.subscribe(self.PROPERTIES_TO_MONITOR)
        except Exception:
            return  # still gone; next tick probes again
        self._heartbeat_lost = False
        self._last_notification_monotonic = time.monotonic()
        self.clear_error()
        self.update_state(connected=True, notifications=True)
        logger.info(f"{self.get_name()}: heartbeat recovered (re-subscribed after outage)")
        await self.emit_progress(f"{self.get_name()} is reachable again", "action_progress")

    async def _keepalive_watchdog(self) -> None:
        """Background heartbeat loop; one `_watchdog_tick` per keepAlive interval."""
        try:
            while True:
                await asyncio.sleep(self._keepalive_interval_s)
                try:
                    await self._watchdog_tick()
                except Exception as e:  # the watchdog itself must never die
                    logger.warning(f"{self.get_name()}: watchdog tick failed: {e}")
        except asyncio.CancelledError:
            pass

    def _heartbeat_guard(self, params: Optional[Dict[str, Any]]) -> Optional[CommandResult]:
        """Fail fast while the heartbeat is lost (the 2026-07-10 teardown burned 2×9 s
        of blind retries against a wedged device). The reserved `force` param bypasses
        — the DRV-5 escape-hatch convention."""
        if self._heartbeat_lost and not (params or {}).get("force"):
            return self.create_command_result(
                success=False,
                error=f"{self.get_name()} is unreachable (heartbeat lost; watchdog is probing)",
            )
        return None

    def _ready_gate_exempt(self, action: str, params: Optional[Dict[str, Any]]) -> bool:
        """Whether an action may bypass the post-power-on readiness hold.

        Exempt: MAIN-zone power_on (it *starts* the window) and the recovery paths
        (a held recovery could deadlock a wedged device forever). Everything else that
        reaches the control port waits — the 2026-07-12 wedge was `power_on {zone: 2}`,
        the SAME action name as the exempt main-zone form, so the zone check is
        load-bearing: an unparseable zone stays gated (the safe default)."""
        if action in ("reconnect", "mqtt_reconnection"):
            return True
        if action == "power_on":
            zone = (params or {}).get("zone", 1)
            try:
                return int(zone) == 1
            except (TypeError, ValueError):
                return False
        return False

    async def _await_device_ready(self, action: str, params: Optional[Dict[str, Any]]) -> None:
        """Hold ANY control-port command until the device is safely past its power-on
        transition. REL-3 finding F1: `set_input` fired 3.3 s into a CEC/ARC handshake
        and wedged the firmware; the 2026-07-12 wedge proved the window is fatal for
        OTHER commands too (`zone2_power_on`, acked and then silence — see
        docs/review/emotiva_wedge_20260712.md), so the hold lives at the dispatch seam
        (execute_action), not inside individual handlers.

        Notification-driven, no blind delays: outside the ARC case, proceed once the
        notification stream has been quiet for INPUT_QUIESCENCE_S (a clean power-up
        burst measures < 1 s). A fresh 'arc' claim inside the window means the CEC
        handshake is live and its traffic is invisible to us — that case holds the
        full INPUT_READY_TIMEOUT_S for every command (the one exception: set_input TO
        arc, which is the choreographed engagement path). The reserved `force` param
        does NOT bypass — this hold protects hardware, not beliefs. No power-on in
        sight → return immediately."""
        anchor = self._power_on_monotonic
        if anchor is None:
            return
        if time.monotonic() - anchor >= self.INPUT_READY_TIMEOUT_S:
            return

        # set_input's target matters for the arc rule: going TO arc is the engagement
        # choreography and must not be held by the arc case itself.
        input_target: Optional[str] = None
        if action == "set_input":
            raw = (params or {}).get("input")
            input_target = str(raw).strip().lower() if raw is not None else None

        held = False
        while True:
            now = time.monotonic()
            since_power = now - anchor
            if since_power >= self.INPUT_READY_TIMEOUT_S:
                break
            # Re-evaluated every loop: the 'arc' claim can land mid-hold.
            arc_window = self.state.input_source == "arc" and input_target != "arc"
            if not arc_window:
                last = self._last_notification_monotonic or anchor
                quiet = now - max(last, anchor)
                if quiet >= self.INPUT_QUIESCENCE_S:
                    break
            held = True
            await asyncio.sleep(0.2)
        if held:
            logger.info(
                f"{self.get_name()}: held {action} for "
                f"{time.monotonic() - anchor:.1f}s after power-on (readiness gate)"
            )

    async def execute_action(
        self,
        action: str,
        params: Optional[Dict[str, Any]] = None,
        source: str = "unknown",
    ) -> CommandResponse[EmotivaXMC2State]:
        """Single dispatch chokepoint, eMotiva flavor: every command from every source
        (scenario / canonical / API / WB MQTT) passes the post-power-on readiness hold
        BEFORE the base dispatch. Internal choreography (e.g. `_power_cycle_for_arc`
        calling helpers directly) deliberately bypasses — the hold guards the dispatch
        boundary. The executor awaits this coroutine per step, so the hold naturally
        paces a scenario plan; the step gate's poll clock starts only after dispatch
        returns, so the hold never eats the gate budget."""
        if not self._ready_gate_exempt(action, params):
            await self._await_device_ready(action, params)
        return await super().execute_action(action, params, source)

    def _process_property_value(self, property_name: str, value: Any) -> Any:
        """
        Process and convert property values to the correct type.
        
        Args:
            property_name: Name of the property
            value: Property value to convert
            
        Returns:
            Converted property value
        """
        if value is None:
            return None
            
        if property_name in ["power", "zone2_power"]:
            # Convert power values to our PowerState enum
            if isinstance(value, str):
                return PowerState.ON if value.lower() == "on" else PowerState.OFF
            return value  # Already converted
        elif property_name in ["volume", "zone2_volume"]:
            # Convert volume to float. The XMC-2 pads short negative values with a
            # space after the sign ('- 3.0' for -3.0 dB, verified at the rack
            # 2026-07-07) — plain float() rejects that and the old fallback
            # silently reported 0.0 (DRV-11).
            try:
                if isinstance(value, str):
                    value = value.replace(" ", "")
                return float(value)
            except (ValueError, TypeError):
                logger.warning(f"Unparseable {property_name} value from device: {value!r}")
                return 0.0

        # mute / zone2_mute are deliberately absent — Emotiva protocol §4.2 has no
        # notification for either; pymotivaxmc2's Property enum correctly omits them
        # too, so this method never receives a "mute" property_name. Mute is
        # optimistic-only in handle_mute_toggle.

        # For other properties, return as is
        return value

    @staticmethod
    def _norm_source_name(name: Any) -> str:
        """Normalize a source name for matching (the device pads names, e.g. 'ZAPPITI   ')."""
        return str(name).strip().casefold()

    @staticmethod
    def _source_index_from_token(value: Any) -> Optional[int]:
        """Parse the canonical 'sourceN' token (or a bare 1-8 index) to an int 1-8, else None."""
        s = str(value).strip().lower()
        if s.startswith("source"):
            s = s[len("source"):].lstrip("_")
        try:
            n = int(s)
        except (ValueError, TypeError):
            return None
        return n if 1 <= n <= 8 else None

    def _source_token(self, name: Any) -> Optional[str]:
        """Map the device's reported source name -> canonical token.

        - "HDMI ARC" → "arc" (special source: HDMI ARC is a peer to the configurable
          Input buttons but isn't bound to one — per protocol §4.2 + per-Input Setup
          menu's Audio Input options, ARC isn't selectable as a per-Input audio source
          on the XMC-2. The canonical "arc" token is what the topology + scenario
          reconciler use to refer to it. Engaged via _power_cycle_for_arc.)
        - Configured Input-button names → "sourceN" via the cached get_input_names() map
        - Unknown names → stripped raw string (fallback)
        """
        if name is None:
            return None
        name_str = str(name).strip()
        if name_str == "HDMI ARC":
            return "arc"
        idx = self._source_index_by_name.get(self._norm_source_name(name))
        return f"source{idx}" if idx is not None else name_str

    async def _power_cycle_for_arc(self, params: Optional[Dict[str, Any]] = None) -> CommandResult:
        """Power-cycle the eMotiva to force HDMI ARC re-engagement.

        HDMI ARC engages on power-up when CEC is enabled and the TV is broadcasting
        from its internal mode (NOT from any HDMI input). Command.ARC was rack-
        verified 2026-05-30 to hang the device, so this off→on cycle is the only
        reliable mechanism.

        PRECONDITION (orchestrated by topology ordering + the LG TV's own
        set_input_source(arc) → handle_home, scheduled before this via the topology
        ordering edges at config/topology.json:43-46): the TV must be on its internal
        mode. If the TV is on an HDMI input when this fires, ARC won't engage and the
        cycle becomes an off→on no-op for state.input_source — the user would see no
        audio change. The reconciler's symmetric src_port mechanism ensures the TV is
        sent set_input_source(arc) (which translates to handle_home in the LG driver)
        before this power-cycle is dispatched.
        """
        # Idempotence guard (honors `force` — DRV-5): ARC engagement is exactly the
        # kind of believed state that goes stale; force re-runs the off→on cycle.
        skip = self.idempotence_skip(
            params, self.state.input_source == "arc",
            "Input already set to arc (ARC engaged)", input="arc",
        )
        if skip is not None:
            await self.emit_progress("Input already set to arc (ARC engaged)", "action_progress")
            return skip
        if self.client is None:
            return self.create_command_result(success=False, error="Not connected to processor")
        logger.info(f"set_input(arc): power-cycling {self.get_name()} to engage HDMI ARC")
        try:
            if self.state.power == PowerState.ON:
                await self.client.power_off(zone=Zone.MAIN)
                self.update_state(power=PowerState.OFF)
                # Let the standby transition settle before powering back on. 3s is
                # comfortable for the eMotiva to release the HDMI handshake without
                # leaving the user waiting too long.
                await asyncio.sleep(3.0)
            await self.client.power_on(zone=Zone.MAIN)
            # state.power + state.input_source will populate via notifications:
            #   - Power notification → state.power = ON
            #   - SOURCE notification ("HDMI ARC") → state.input_source = "arc"
            #     (via _source_token's special mapping)
            self.clear_error()
            self._update_last_command("set_input", {"input": "arc"})
            await self.emit_progress(
                "Power-cycled processor to engage HDMI ARC", "action_success"
            )
            return self.create_command_result(
                success=True, message="Power-cycled for HDMI ARC engagement", input="arc"
            )
        except Exception as e:
            return await self._handle_command_error(
                "power-cycle for HDMI ARC", e, {"input": "arc"}
            )

    async def _refresh_source_map(self) -> None:
        """Pull Input-button names/visibility from the device and rebuild the source maps.
        All device-specific source translation is sourced here (infrastructure), keeping
        the reconciler device-agnostic."""
        if not self.client:
            return
        buttons = await self.client.get_input_names()
        self._source_buttons = buttons or {}
        self._source_index_by_name = {
            self._norm_source_name(info["name"]): idx
            for idx, info in self._source_buttons.items()
            if info.get("name")
        }

    def update_state(self, **kwargs) -> None:
        """
        Update the device state with the provided values.
        
        Args:
            **kwargs: State values to update
        """
        # DEBUG: Log all state updates with current state context
        logger.debug(f"[EMOTIVA_DEBUG] State update requested: {kwargs} (device={self.get_name()}, current_power={self.state.power}, connected={self.state.connected})")
        
        # Convert string power states to enum values if needed
        if 'power' in kwargs and isinstance(kwargs['power'], str):
            power_value = kwargs['power'].lower()
            kwargs['power'] = PowerState.ON if power_value == 'on' else PowerState.OFF
            
        if 'zone2_power' in kwargs and isinstance(kwargs['zone2_power'], str):
            zone2_value = kwargs['zone2_power'].lower()
            kwargs['zone2_power'] = PowerState.ON if zone2_value == 'on' else PowerState.OFF
            
        # Call the parent update_state method
        super().update_state(**kwargs)

    def _update_last_command(self, action: str, params: Optional[Dict[str, Any]] = None):
        """Update last command in the device state.
        
        Args:
            action: The action that was executed
            params: Parameters used for the action
        """
        # Create a LastCommand model with current information
        last_command = LastCommand(
            action=action,
            source="api",
            timestamp=datetime.now(),
            params=params
        )
        # Store the LastCommand model directly in the state
        self.update_state(last_command=last_command)
        
    def _get_parameter_definition(self, cmd_config: StandardCommandConfig, param_name: str) -> Optional[CommandParameterDefinition]:
        """
        Get parameter definition by name from command configuration.
        
        Args:
            cmd_config: Command configuration object
            param_name: Name of the parameter to find
            
        Returns:
            CommandParameterDefinition if found, None otherwise
        """
        if not cmd_config.params:
            return None
            
        for param_def in cmd_config.params:
            if param_def.name == param_name:
                return param_def
                
        return None

    def _validate_parameter(self, 
                           param_name: str, 
                           param_value: Any, 
                           param_type: str, 
                           required: bool = True, 
                           min_value: Optional[float] = None, 
                           max_value: Optional[float] = None, 
                           action: str = "") -> Tuple[bool, Any, Optional[str]]:
        """Validate a parameter against its definition and convert to correct type.
        
        Args:
            param_name: Name of the parameter
            param_value: Value of the parameter
            param_type: Expected type ('string', 'integer', 'float', 'boolean', 'range')
            required: Whether the parameter is required
            min_value: Minimum value (for numeric types)
            max_value: Maximum value (for numeric types)
            action: Action name for error messages
            
        Returns:
            Tuple of (is_valid, converted_value, error_message)
            where error_message is None if validation passed
        """
        # Check if parameter is required but missing
        if required and param_value is None:
            return False, None, f"Missing required '{param_name}' parameter"
            
        # Return early if parameter is not required and not provided
        if not required and param_value is None:
            return True, None, None
            
        converted_value = param_value
        
        # Convert value to the correct type
        try:
            if param_type == "integer":
                converted_value = int(param_value)
                
                # Check range constraints if specified
                if min_value is not None and converted_value < min_value:
                    return False, converted_value, f"{param_name} value {converted_value} is below minimum {min_value}"
                if max_value is not None and converted_value > max_value:
                    return False, converted_value, f"{param_name} value {converted_value} is above maximum {max_value}"
                    
            elif param_type in ("float", "range"):
                converted_value = float(param_value)
                
                # Check range constraints if specified
                if min_value is not None and converted_value < min_value:
                    return False, converted_value, f"{param_name} value {converted_value} is below minimum {min_value}"
                if max_value is not None and converted_value > max_value:
                    return False, converted_value, f"{param_name} value {converted_value} is above maximum {max_value}"
                    
            elif param_type == "boolean":
                if isinstance(param_value, str):
                    converted_value = param_value.lower() in ("yes", "true", "1", "on")
                else:
                    converted_value = bool(param_value)
                    
        except (ValueError, TypeError):
            error_msg = f"Invalid {param_name} value: {param_value}. Must be a {param_type} value."
            return False, param_value, error_msg
            
        return True, converted_value, None

    # Add zone-specific helpers
    def _get_zone(self, zone_id: Union[int, str] = 1) -> Zone:
        """Get the Zone enum corresponding to the zone ID.
        
        Args:
            zone_id: Zone ID (1 for main, 2 for zone2)
            
        Returns:
            Zone enum value
        """
        try:
            zone_id = int(zone_id)
            if zone_id == 1:
                return Zone.MAIN
            elif zone_id == 2:
                return Zone.ZONE2
            else:
                logger.warning(f"Invalid zone ID: {zone_id}, defaulting to main zone")
                return Zone.MAIN
        except (ValueError, TypeError):
            if str(zone_id).lower() == "main":
                return Zone.MAIN
            elif str(zone_id).lower() in ("zone2", "zone_2"):
                return Zone.ZONE2
            else:
                logger.warning(f"Invalid zone ID: {zone_id}, defaulting to main zone")
                return Zone.MAIN

    async def _refresh_device_state(self) -> Dict[str, Any]:
        """
        Refresh the full device state by querying all important properties.
        
        This is used after powering on from standby to ensure state is in sync.
        
        Returns:
            Dict[str, Any]: Dictionary of updated properties and their values
        """
        # DEBUG: Log state refresh start
        logger.debug(f"[EMOTIVA_DEBUG] _refresh_device_state called (device={self.get_name()}, connected={self.state.connected})")
        
        if not self.client:
            logger.warning("Cannot refresh device state: client not initialized")
            return {}
            
        try:
            # Query all properties we care about using the status API
            properties_to_query = [
                Property.POWER,              # Main zone power
                Property.ZONE2_POWER,        # Zone 2 power
                Property.VOLUME,             # Main volume
                Property.ZONE2_VOLUME,       # Zone 2 volume
                Property.SOURCE,             # Current input
                Property.AUDIO_INPUT,        # Audio input
                Property.VIDEO_INPUT,        # Video input
                Property.AUDIO_BITSTREAM,    # Audio bitstream format
                Property.SELECTED_MODE       # Audio processing mode
            ]
            
            # DEBUG: Log properties being queried
            logger.debug(f"[EMOTIVA_DEBUG] Querying properties: {[p.value for p in properties_to_query]} (device={self.get_name()})")
            
            # Use the status method to get all properties at once
            result = await self.client.status(*properties_to_query)
            
            # Process and update our state with the results
            updated_properties = {}
            for prop, value in result.items():
                # Convert property enum to string for our internal handling
                prop_name = prop.value.lower()
                
                # Process the value with our helper
                processed_value = self._process_property_value(prop_name, value)
                updated_properties[prop_name] = processed_value
                
                # Handle input property specially (device reports the source NAME)
                if prop == Property.SOURCE:
                    self.update_state(input_source=self._source_token(value))
                else:
                    self.update_state(**{self.VALID_PROPERTIES.get(prop, prop_name): processed_value})
                    
            logger.debug(f"Device state refresh completed for {self.get_name()} ({len(updated_properties)}/{len(properties_to_query)} properties)")
            return updated_properties
            
        except Exception as e:
            logger.warning(f"Error refreshing device state: {str(e)}")
            return {}

    async def handle_power_on(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """Handle power on command.
        
        Args:
            cmd_config: Command configuration
            params: Parameters (may include zone)
            
        Returns:
            Command execution result
        """
        # DEBUG: Log command start with full context
        logger.debug(f"[EMOTIVA_DEBUG] power_on command received: params={params}, connected={self.state.connected}, power={self.state.power} (device={self.get_name()})")

        # DRV-30: fail fast while the heartbeat is lost (force bypasses).
        unreachable = self._heartbeat_guard(params)
        if unreachable is not None:
            return unreachable

        
        # If client is not initialized or not connected, reconnect first
        if not self.client or not self.state.connected:
            # DEBUG: Log reconnection trigger
            logger.debug(f"[EMOTIVA_DEBUG] Triggering reconnection: client={self.client is not None}, connected={self.state.connected} (device={self.get_name()})")
            logger.info(f"Device {self.get_name()} not connected, attempting reconnection before power on")
            try:
                await self.setup()
            except Exception as e:
                logger.error(f"Failed to reconnect device {self.get_name()} before power on: {str(e)}")
                return self.create_command_result(
                    success=False,
                    error=f"Failed to connect to device: {str(e)}"
                )

        # Guard again -- setup() may have completed without creating self.client
        # (config-error path, repeated network failure). All downstream code
        # dereferences self.client, so a single narrow here covers them.
        if self.client is None:
            return self.create_command_result(success=False, error="No client after reconnect attempt")

        # Get zone parameter if specified
        zone_id = 1  # Default to main zone
        
        if params and "zone" in params:
            zone_param = self._get_parameter_definition(cmd_config, "zone")
            is_valid, zone_value, error_msg = self._validate_parameter(
                param_name="zone",
                param_value=params.get("zone"),
                param_type=zone_param.type if zone_param else "integer",
                required=False,
                action="power_on"
            )
            
            if not is_valid:
                return self.create_command_result(success=False, error=error_msg)
                
            if zone_value is not None:
                zone_id = zone_value
                
        # Get zone as enum
        zone = self._get_zone(zone_id)
        
        # Check current power state
        current_power = None
        if zone == Zone.MAIN:
            current_power = self.state.power
        elif zone == Zone.ZONE2:
            current_power = self.state.zone2_power
                
        # If state is None, synchronize it
        if current_power is None:
            try:
                # Synchronize state for this zone using _refresh_device_state for main zone
                # or _synchronize_state for zone2
                updated_properties = await self._synchronize_state(zone_id)
                
                # Get updated power state
                if zone == Zone.MAIN:
                    current_power = self.state.power
                elif zone == Zone.ZONE2:
                    current_power = self.state.zone2_power
                    
                logger.debug(f"Synchronized power state for zone {zone_id} before power on: {current_power}")
            except Exception as e:
                logger.warning(f"Failed to synchronize state for zone {zone_id}: {str(e)}")
                # Continue with power on attempt even if we couldn't verify state
        
        # Idempotence guard (honors `force` — DRV-5: useful when an ack was missed).
        skip = self.idempotence_skip(
            params, current_power == PowerState.ON,
            f"Zone {zone_id} is already powered on", zone=zone_id,
        )
        if skip is not None:
            logger.debug(f"Zone {zone_id} is already powered on, skipping command")
            return skip
        
        try:
            # Power on the specified zone.
            # Main zone: no optimistic write — state is seeded by the device's notifications
            # (dispatched through _handle_property_change) PLUS the defensive subscribe +
            # refresh path below, both of which fire after the command ack.
            # Zone 2: KEEP the optimistic write — until rack-verified that the explicit
            # zone2_power_on command (distinct from the zone2_power_toggle path that was
            # verified 2026-05-30) triggers the same zone2_power notification.
            if zone == Zone.MAIN:
                await self.client.power_on(zone=zone)
                # DRV-30: anchor the post-power-on readiness window here as well as on
                # the Off→On notification — the anchor must exist even if notifications
                # are broken (that failure mode is exactly what the watchdog handles).
                self._power_on_monotonic = time.monotonic()
                logger.info("Main zone power_on command sent")
            elif zone == Zone.ZONE2:
                await self.client.power_on(zone=zone)
                self.update_state(zone2_power=PowerState.ON)  # optimistic; see comment above
                logger.info("Zone 2 powered on successfully")
            else:
                logger.warning(f"Unsupported zone: {zone}")
                return self.create_command_result(
                    success=False,
                    error=f"Unsupported zone: {zone_id}"
                )
            
            # Clear any errors
            self.clear_error()
            
            # Update the last command information
            self._update_last_command("power_on", {"zone": zone_id})
            
            # If main zone was powered on, ensure we're subscribed to all properties
            if zone == Zone.MAIN:
                try:
                    # Subscribe to all properties to ensure we get updates
                    await self.client.subscribe(self.PROPERTIES_TO_MONITOR)
                    
                    # Update our connected and notification status
                    self.update_state(
                        connected=True,
                        startup_complete=True,
                        notifications=True
                    )
                    
                    # Synchronize state after power on to get current values
                    await asyncio.sleep(1.0)  # Brief delay to allow device to stabilize
                    updated_properties = await self._refresh_device_state()
                    
                    # Emit progress message
                    await self.emit_progress(f"Zone {zone_id} powered on successfully", "action_success")
                    
                    # Return success result with updated properties
                    return self.create_command_result(
                        success=True,
                        message=f"Zone {zone_id} powered on successfully",
                        power=PowerState.ON.value,
                        zone=zone_id,
                        updated_properties=list(updated_properties.keys()) if updated_properties else []
                    )
                except Exception as e:
                    logger.error(f"Error during post-power-on operations: {str(e)}")
                    # Still return success for the power-on, but include warning
                    return self.create_command_result(
                        success=True,
                        message=f"Zone {zone_id} powered on, but state synchronization had errors: {str(e)}",
                        power=PowerState.ON.value,
                        zone=zone_id,
                        warnings=["State synchronization incomplete, some state updates may be missing"]
                    )
            else:
                # For non-main zones, just return success
                await self.emit_progress(f"Zone {zone_id} powered on successfully", "action_success")
                return self.create_command_result(
                    success=True,
                    message=f"Zone {zone_id} powered on successfully",
                    zone=zone_id,
                    zone2_power=PowerState.ON.value if zone == Zone.ZONE2 else None
                )
                
        except Exception as e:
            error_message = f"Failed to power on zone {zone_id}: {str(e)}"
            logger.error(error_message)
            self.set_error(error_message)
            await self.emit_progress(f"Failed to power on zone {zone_id}: {str(e)}", "action_error")
            return self.create_command_result(
                success=False,
                error=error_message
            )

    async def handle_power_off(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """Handle power off command.
        
        Args:
            cmd_config: Command configuration
            params: Parameters (may include zone)
            
        Returns:
            Command execution result
        """
        # DEBUG: Log command start with full context
        logger.debug(f"[EMOTIVA_DEBUG] power_off command received: params={params}, connected={self.state.connected}, power={self.state.power} (device={self.get_name()})")

        # DRV-30: fail fast while the heartbeat is lost (force bypasses).
        unreachable = self._heartbeat_guard(params)
        if unreachable is not None:
            return unreachable

        
        # If client is not initialized or not connected, reconnect first
        if not self.client or not self.state.connected:
            # DEBUG: Log reconnection trigger
            logger.debug(f"[EMOTIVA_DEBUG] Triggering reconnection for power_off: client={self.client is not None}, connected={self.state.connected} (device={self.get_name()})")
            logger.info(f"Device {self.get_name()} not connected, attempting reconnection before power off")
            try:
                await self.setup()
            except Exception as e:
                logger.error(f"Failed to reconnect device {self.get_name()} before power off: {str(e)}")
                return self.create_command_result(
                    success=False,
                    error=f"Failed to connect to device: {str(e)}"
                )

        # Guard again after the optional reconnect (see handle_power_on).
        if self.client is None:
            return self.create_command_result(success=False, error="No client after reconnect attempt")

        # Get zone parameter if specified
        zone_id = 1  # Default to main zone
        
        if params and "zone" in params:
            zone_param = self._get_parameter_definition(cmd_config, "zone")
            is_valid, zone_value, error_msg = self._validate_parameter(
                param_name="zone",
                param_value=params.get("zone"),
                param_type=zone_param.type if zone_param else "integer",
                required=False,
                action="power_off"
            )
            
            if not is_valid:
                return self.create_command_result(success=False, error=error_msg)
                
            if zone_value is not None:
                zone_id = zone_value
                
        # Get zone as enum
        zone = self._get_zone(zone_id)
        
        # Check current power state
        current_power = None
        if zone == Zone.MAIN:
            current_power = self.state.power
        elif zone == Zone.ZONE2:
            current_power = self.state.zone2_power
                
        # Idempotence guard (honors `force` — DRV-5).
        skip = self.idempotence_skip(
            params, current_power == PowerState.OFF,
            f"Zone {zone_id} is already powered off", zone=zone_id,
        )
        if skip is not None:
            logger.debug(f"Zone {zone_id} is already powered off, skipping command")
            return skip
            
        # If state is None, request an update
        if current_power is None:
            try:
                # Synchronize state for this zone using _synchronize_state
                await self._synchronize_state(zone_id)
                
                # Get updated power state
                if zone == Zone.MAIN:
                    current_power = self.state.power
                elif zone == Zone.ZONE2:
                    current_power = self.state.zone2_power
                    
                logger.debug(f"Synchronized power state for zone {zone_id} before power off: {current_power}")
                    
                # Check again if already off (idempotence guard, honors `force` — DRV-5).
                skip = self.idempotence_skip(
                    params, current_power == PowerState.OFF,
                    f"Zone {zone_id} is already powered off (verified)", zone=zone_id,
                )
                if skip is not None:
                    logger.debug(f"Zone {zone_id} is already powered off (verified), skipping command")
                    return skip
            except Exception as e:
                logger.warning(f"Failed to get current power state for zone {zone_id}: {str(e)}")
                # Continue with power off attempt even if we couldn't verify state
        
        try:
            # Power off the specified zone
            if zone == Zone.MAIN:
                await self.client.power_off(zone=zone)
                self.update_state(power=PowerState.OFF)
                logger.info("Main zone powered off successfully")
            elif zone == Zone.ZONE2:
                await self.client.power_off(zone=zone)
                self.update_state(zone2_power=PowerState.OFF)
                logger.info("Zone 2 powered off successfully")
            else:
                logger.warning(f"Unsupported zone: {zone}")
                return self.create_command_result(
                    success=False,
                    error=f"Unsupported zone: {zone_id}"
                )
            
            # Clear any errors
            self.clear_error()
            
            # Update the last command information
            self._update_last_command("power_off", {"zone": zone_id})
            
            if zone == Zone.MAIN:
                return self.create_command_result(
                    success=True,
                    message=f"Zone {zone_id} powered off successfully",
                    power=PowerState.OFF.value,
                    zone=zone_id
                )
            else:
                return self.create_command_result(
                    success=True,
                    message=f"Zone {zone_id} powered off successfully",
                    zone=zone_id,
                    zone2_power=PowerState.OFF.value if zone == Zone.ZONE2 else None
                )
                
        except Exception as e:
            error_message = f"Failed to power off zone {zone_id}: {str(e)}"
            logger.error(error_message)
            self.set_error(error_message)
            return self.create_command_result(
                success=False,
                error=error_message
            )
            
    async def _handle_command_error(self, action: str, error: Exception, context: Optional[Dict[str, Any]] = None) -> CommandResult:
        """Handle command errors in a consistent way.
        
        This centralizes error handling logic for commands to ensure consistent behavior.
        
        Args:
            action: The action that was being performed
            error: The exception that occurred
            context: Additional context for the error
            
        Returns:
            CommandResult: Error result
        """
        error_message = f"Failed to {action}: {str(error)}"
        logger.error(error_message)
        self.set_error(error_message)
        
        # Emit error message via SSE
        try:
            error_context = f" ({', '.join([f'{k}={v}' for k, v in context.items()])})" if context else ""
            await self.emit_progress(f"Error: {error_message}{error_context}", "action_error")
        except Exception as e:
            logger.warning(f"Failed to emit error message: {str(e)}")
        
        # Create error result
        result = self.create_command_result(
            success=False,
            error=error_message
        )
        
        # Add context to result if provided
        if context:
            for key, value in context.items():
                if key not in result:
                    result[key] = value
                    
        return result
        
    async def handle_zone2_power_toggle(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """Toggle Zone 2 power via the native eMotiva ``zone2_power`` command (pymotivaxmc2
        ``power_toggle(zone=ZONE2)``). The resulting zone2_power state arrives asynchronously via the
        device's property notification, so it is not set optimistically here."""

        # DRV-30: fail fast while the heartbeat is lost (force bypasses).
        unreachable = self._heartbeat_guard(params)
        if unreachable is not None:
            return unreachable
        logger.debug(f"[EMOTIVA_DEBUG] zone2_power_toggle received: connected={self.state.connected}, zone2_power={self.state.zone2_power} (device={self.get_name()})")
        if not self.client or not self.state.connected:
            logger.info(f"Device {self.get_name()} not connected, reconnecting before zone2 power toggle")
            try:
                await self.setup()
            except Exception as e:
                return self.create_command_result(success=False, error=f"Failed to connect to device: {str(e)}")
        if self.client is None:
            return self.create_command_result(success=False, error="No client after reconnect attempt")
        try:
            await self.client.power_toggle(zone=Zone.ZONE2)
            self.clear_error()
            return self.create_command_result(success=True, message="Zone 2 power toggled", zone=2)
        except Exception as e:
            logger.error(f"Failed to toggle zone 2 power on {self.get_name()}: {str(e)}")
            return self.create_command_result(success=False, error=f"Failed to toggle zone 2 power: {str(e)}")

    async def handle_set_input(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """Select a logical source (Input button) via the device's ``source_N`` command.

        Accepts the canonical ``sourceN`` token (or a bare 1-8 index). The token<->index and
        device-name<->token translation lives here so the reconciler stays device-agnostic.
        """
        logger.debug(f"[EMOTIVA_DEBUG] set_input received: params={params}, connected={self.state.connected}, current_input={self.state.input_source} (device={self.get_name()})")

        # DRV-30: fail fast while the heartbeat is lost (force bypasses).
        unreachable = self._heartbeat_guard(params)
        if unreachable is not None:
            return unreachable


        if not self.client or not self.state.connected:
            try:
                await self.setup()
            except Exception as e:
                return await self._handle_command_error("reconnect device", e, {"action": "set_input"})

        if not params:
            return self.create_command_result(success=False, error="Missing input parameters")

        input_param = self._get_parameter_definition(cmd_config, "input")
        is_valid, raw_value, error_msg = self._validate_parameter(
            param_name="input",
            param_value=params.get("input"),
            param_type=input_param.type if input_param else "string",
            action="set_input",
        )
        if not is_valid:
            return self.create_command_result(success=False, error=error_msg)

        # "arc" branch: HDMI ARC can't be reached via select_source/Command.ARC
        # (Command.ARC rack-verified to hang the device 2026-05-30). The reliable
        # workaround is a power-cycle on the eMotiva — ARC auto-engages on power-up
        # when CEC is on and the TV is broadcasting from its internal mode. The TV
        # state is orchestrated upstream by topology ordering + the LG TV's own
        # set_input_source(arc) → handle_home.
        if str(raw_value).strip().lower() == "arc":
            return await self._power_cycle_for_arc(params)

        index = self._source_index_from_token(raw_value)
        if index is None:
            return self.create_command_result(
                success=False, error=f"Invalid source '{raw_value}' (expected source1-source8 or arc)"
            )
        token = f"source{index}"

        # Can't change input while powered off.
        if self.state.power != PowerState.ON:
            if self.state.power is None:
                try:
                    await self._refresh_device_state()
                except Exception as e:
                    logger.warning(f"Failed to refresh state before set input: {str(e)}")
            if self.state.power != PowerState.ON:
                error_message = "Cannot set input while device is powered off"
                logger.warning(error_message)
                await self.emit_progress(error_message, "action_error")
                return self.create_command_result(
                    success=False, error=error_message, input=token,
                    # PowerState is a str-Enum -- the stored value IS already the
                    # string form ("on" / "off"). No .value needed; BaseDeviceState
                    # types this field as `str`.
                    power=self.state.power if self.state.power else "off",
                )

        # Already on this source? (Idempotence guard, honors `force` — DRV-5.)
        skip = self.idempotence_skip(
            params, self.state.input_source == token,
            f"Input already set to {token}", input=token,
        )
        if skip is not None:
            await self.emit_progress(f"Input already set to {token}", "action_progress")
            return skip

        if self.client is None:
            return self.create_command_result(success=False, error="Not connected to processor")

        # Readiness is enforced at the dispatch seam (execute_action → _await_device_ready,
        # DRV-38) — no inline hold here; direct internal calls intentionally bypass.
        try:
            await self.client.select_source(index)
            self.update_state(input_source=token)  # optimistic; the SOURCE notification confirms
            self.clear_error()
            self._update_last_command("set_input", {"input": token})
            await self.emit_progress(f"Input set to {token}", "action_success")
            return self.create_command_result(success=True, message=f"Input set to {token} successfully", input=token)
        except Exception as e:
            return await self._handle_command_error(f"set input to {token}", e, {"input": token})
            
    async def handle_set_volume(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """Handle setting volume level.
        
        Args:
            cmd_config: Command configuration
            params: Parameters containing volume level
            
        Returns:
            Command execution result
        """

        # DRV-30: fail fast while the heartbeat is lost (force bypasses).
        unreachable = self._heartbeat_guard(params)
        if unreachable is not None:
            return unreachable
        # DEBUG: Log command start with full context  
        logger.debug(f"[EMOTIVA_DEBUG] set_volume command received: params={params}, connected={self.state.connected}, current_volume={self.state.volume} (device={self.get_name()})")
        
        # If client is not initialized or not connected, reconnect first
        if not self.client or not self.state.connected:
            # DEBUG: Log reconnection trigger
            logger.debug(f"[EMOTIVA_DEBUG] Triggering reconnection for set_volume: client={self.client is not None}, connected={self.state.connected} (device={self.get_name()})")
            logger.info(f"Device {self.get_name()} not connected, attempting reconnection before setting volume")
            try:
                await self.setup()
            except Exception as e:
                logger.error(f"Failed to reconnect device {self.get_name()} before setting volume: {str(e)}")
                return self.create_command_result(
                    success=False,
                    error=f"Failed to connect to device: {str(e)}"
                )
        
        # Validate parameters
        if not params:
            return self.create_command_result(success=False, error="Missing volume parameters")
        
        # Get and validate level parameter
        level_param = self._get_parameter_definition(cmd_config, "level")
        is_valid, level, error_msg = self._validate_parameter(
            param_name="level",
            param_value=params.get("level"),
            param_type=level_param.type if level_param else "range",
            min_value=level_param.min if level_param else -96.0,
            max_value=level_param.max if level_param else 0.0,
            action="set_volume"
        )
        
        if not is_valid:
            return self.create_command_result(success=False, error=error_msg)
            
        # Get zone parameter if specified
        zone_param = self._get_parameter_definition(cmd_config, "zone")
        zone_id = 1  # Default to main zone
        
        if zone_param and "zone" in params:
            is_valid, zone_value, error_msg = self._validate_parameter(
                param_name="zone",
                param_value=params.get("zone"),
                param_type=zone_param.type if zone_param else "integer",
                required=False,
                action="set_volume"
            )
            
            if not is_valid:
                return self.create_command_result(success=False, error=error_msg)
                
            if zone_value is not None:
                zone_id = zone_value
        
        # Get zone as enum
        zone = self._get_zone(zone_id)
        
        # Check current volume state - if it's unknown, refresh it
        current_volume = None
        if zone == Zone.MAIN:
            current_volume = self.state.volume
            if current_volume is None:
                try:
                    # Use _refresh_device_state for main zone to efficiently get all properties
                    await self._refresh_device_state()
                    current_volume = self.state.volume
                    logger.debug(f"Refreshed device state before set volume: volume={current_volume}")
                except Exception as e:
                    logger.warning(f"Failed to refresh volume state: {str(e)}")
                    # Continue with volume setting even if we couldn't verify state
        elif zone == Zone.ZONE2:
            current_volume = getattr(self.state, "zone2_volume", None)
            if current_volume is None:
                try:
                    # For Zone2, use _synchronize_state which is optimized for Zone2
                    await self._synchronize_state(zone_id=2)
                    current_volume = getattr(self.state, "zone2_volume", None)
                    logger.debug(f"Synchronized Zone2 volume state: {current_volume}")
                except Exception as e:
                    logger.warning(f"Failed to synchronize Zone2 volume: {str(e)}")
                    # Continue with volume setting even if we couldn't verify state
                
        # If volume is already at the requested level, skip setting it
        # (idempotence guard with float tolerance, honors `force` — DRV-5).
        skip = self.idempotence_skip(
            params,
            current_volume is not None and abs(current_volume - level) < 0.1,
            f"Volume for zone {zone_id} already at {level} dB",
            volume=level, zone=zone_id,
        )
        if skip is not None:
            logger.debug(f"Volume for zone {zone_id} already at {level} dB, skipping command")
            return skip
        
        if self.client is None:
            return self.create_command_result(success=False, error="Not connected to processor")
        try:
            # Set volume for the specified zone. Both main and zone-2 volume notifications
            # are rack-verified to fire ~180ms after ack (see action_plan §6 2026-05-30).
            # State is updated via _handle_property_change on that notification — no
            # optimistic write needed.
            if zone == Zone.MAIN:
                await self.client.set_volume(level, zone=zone)
                logger.debug(f"Set main zone volume command sent: {level} dB")
            elif zone == Zone.ZONE2:
                await self.client.set_volume(level, zone=zone)
                logger.debug(f"Set zone 2 volume command sent: {level} dB")
            else:
                logger.warning(f"Unsupported zone: {zone}")
                return self.create_command_result(
                    success=False,
                    error=f"Unsupported zone: {zone_id}"
                )
            
            # Clear any errors
            self.clear_error()
            
            # Update the last command information
            self._update_last_command("set_volume", {"level": level, "zone": zone_id})
            
            return self.create_command_result(
                success=True,
                message=f"Volume for zone {zone_id} set to {level} dB successfully",
                volume=level,
                zone=zone_id
            )
        except Exception as e:
            error_message = f"Failed to set volume: {str(e)}"
            logger.error(error_message)
            self.set_error(error_message)
            return self.create_command_result(
                success=False,
                error=error_message
            )
            
    async def handle_mute_toggle(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """Handle toggling mute state.
        
        Args:
            cmd_config: Command configuration
            params: Parameters including optional zone
            
        Returns:
            Command execution result
        """

        # DRV-30: fail fast while the heartbeat is lost (force bypasses).
        unreachable = self._heartbeat_guard(params)
        if unreachable is not None:
            return unreachable
        # DEBUG: Log command start with full context
        logger.debug(f"[EMOTIVA_DEBUG] mute_toggle command received: params={params}, connected={self.state.connected}, current_mute={self.state.mute} (device={self.get_name()})")
        
        # If client is not initialized or not connected, reconnect first
        if not self.client or not self.state.connected:
            # DEBUG: Log reconnection trigger
            logger.debug(f"[EMOTIVA_DEBUG] Triggering reconnection for mute_toggle: client={self.client is not None}, connected={self.state.connected} (device={self.get_name()})")
            logger.info(f"Device {self.get_name()} not connected, attempting reconnection before toggling mute")
            try:
                await self.setup()
            except Exception as e:
                logger.error(f"Failed to reconnect device {self.get_name()} before toggling mute: {str(e)}")
                return self.create_command_result(
                    success=False,
                    error=f"Failed to connect to device: {str(e)}"
                )
        
        # Get zone parameter if specified
        zone_id = 1  # Default to main zone
        
        if params and "zone" in params:
            zone_param = self._get_parameter_definition(cmd_config, "zone")
            is_valid, zone_value, error_msg = self._validate_parameter(
                param_name="zone",
                param_value=params.get("zone"),
                param_type=zone_param.type if zone_param else "integer",
                required=False,
                action="mute_toggle"
            )
            
            if not is_valid:
                return self.create_command_result(success=False, error=error_msg)
                
            if zone_value is not None:
                zone_id = zone_value
        
        # Get zone as enum
        zone = self._get_zone(zone_id)

        if self.client is None:
            return self.create_command_result(success=False, error="Not connected to processor")

        try:
            # Toggle mute for the specified zone
            if zone == Zone.MAIN:
                # Get current mute state if unknown
                if self.state.mute is None:
                    try:
                        # Use _refresh_device_state for more efficient state retrieval
                        await self._refresh_device_state()
                        logger.debug(f"Refreshed device state before mute toggle: mute={self.state.mute}")
                    except Exception as e:
                        logger.warning(f"Failed to refresh mute state: {str(e)}")
                        # Continue with toggle even if we couldn't verify state
                
                # Toggle mute
                await self.client.mute(zone=zone)
                
                # Update state with the new mute value (invert current state)
                new_mute = not self.state.mute if self.state.mute is not None else True
                self.update_state(mute=new_mute)
                logger.debug(f"Toggled main zone mute to {new_mute}")
            elif zone == Zone.ZONE2:
                # Get current mute state if unknown
                current_mute = getattr(self.state, "zone2_mute", None)
                if current_mute is None:
                    try:
                        # Zone2 properties need to be queried individually
                        await self._synchronize_state(zone_id=2)
                        current_mute = getattr(self.state, "zone2_mute", None)
                        logger.debug(f"Synchronized Zone2 state before mute toggle: zone2_mute={current_mute}")
                    except Exception as e:
                        logger.warning(f"Failed to get current zone 2 mute state: {str(e)}")
                        # Continue with toggle even if we couldn't verify state
                
                # Toggle mute
                await self.client.mute(zone=zone)
                
                # Update state with the new mute value (invert current state)
                new_mute = not current_mute if current_mute is not None else True
                self.update_state(zone2_mute=new_mute)
                logger.debug(f"Toggled zone 2 mute to {new_mute}")
            else:
                logger.warning(f"Unsupported zone: {zone}")
                return self.create_command_result(
                    success=False,
                    error=f"Unsupported zone: {zone_id}"
                )
            
            # Clear any errors
            self.clear_error()
            
            # Update the last command information
            self._update_last_command("mute_toggle", {"zone": zone_id})
            
            return self.create_command_result(
                success=True,
                message=f"Mute for zone {zone_id} toggled successfully",
                mute=new_mute,
                zone=zone_id
            )
        except Exception as e:
            error_message = f"Failed to toggle mute: {str(e)}"
            logger.error(error_message)
            self.set_error(error_message)
            return self.create_command_result(
                success=False,
                error=error_message
            )
            
    async def handle_reconnect(self, cmd_config: StandardCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """Handle reconnection request.
        
        Args:
            cmd_config: Command configuration
            params: Parameters (unused)
            
        Returns:
            Command execution result
        """
        logger.info(f"Reconnection requested for device: {self.get_name()}")
        
        try:
            # Disconnect if currently connected
            if self.client and self.state.connected:
                logger.info(f"Disconnecting before reconnection for: {self.get_name()}")
                
                # Let the library handle disconnection
                await self.client.disconnect()
                
                # Update state to reflect disconnection
                self.update_state(
                    connected=False,
                    notifications=False
                )
                
                logger.info(f"Successfully disconnected {self.get_name()} for reconnection")
            
            # Re-initialize - setup creates a new client and connects
            success = await self.setup()
            
            if success:
                self.clear_error()
                logger.info(f"Reconnection successful for: {self.get_name()}")
                return self.create_command_result(
                    success=True, 
                    message=f"Successfully reconnected to {self.get_name()}"
                )
            else:
                error_msg = f"Reconnection failed for: {self.get_name()}"
                logger.error(error_msg)
                return self.create_command_result(success=False, error=error_msg)
        except Exception as e:
            error_msg = f"Error during reconnection: {str(e)}"
            logger.error(error_msg)
            self.set_error(error_msg)
            return self.create_command_result(success=False, error=error_msg)

    async def _synchronize_state(self, zone_id: int = 1) -> Dict[str, Any]:
        """Synchronize device state by querying current values.
        
        This method queries the device for current state values and updates the local state.
        It's useful when the state might be out of sync or when we need to ensure we have
        the latest values.
        
        Args:
            zone_id: Zone ID (1 for main, 2 for zone2)
            
        Returns:
            Dict[str, Any]: Dictionary of updated properties
        """
        if not self.client or not self.state.connected:
            logger.warning(f"Cannot synchronize state for {self.get_name()}: not connected")
            return {}
        
        zone = self._get_zone(zone_id)
        
        # For main zone, use _refresh_device_state to get all properties at once
        if zone == Zone.MAIN:
            try:
                logger.debug("Synchronizing all properties for main zone")
                updated_properties = await self._refresh_device_state()
                return updated_properties
            except Exception as e:
                logger.error(f"Error synchronizing main zone state: {str(e)}")
                return {}
                
        # For Zone2, we need to handle it differently since _refresh_device_state focuses on main zone
        else:
            updated_properties = {}
            try:
                # Query zone2 power state
                try:
                    power_result = await self.client.status(Property.ZONE2_POWER)
                    power_value = power_result.get(Property.ZONE2_POWER)
                    self.update_state(zone2_power=power_value)
                    updated_properties["zone2_power"] = power_value
                    logger.debug(f"Synchronized Zone2 power state: {power_value}")
                except Exception as e:
                    logger.warning(f"Failed to synchronize Zone2 power state: {str(e)}")
                
                # Only query other Zone2 properties if powered on
                if self.state.zone2_power == PowerState.ON:
                    # Query Zone2 volume
                    try:
                        volume_result = await self.client.status(Property.ZONE2_VOLUME)
                        # Route through the converter — the device may answer with the
                        # space-padded form ('- 3.0') this raw path used to store verbatim.
                        volume = self._process_property_value(
                            "zone2_volume", volume_result.get(Property.ZONE2_VOLUME)
                        )
                        self.update_state(zone2_volume=volume)
                        updated_properties["zone2_volume"] = volume
                        logger.debug(f"Synchronized Zone2 volume: {volume}")
                    except Exception as e:
                        logger.warning(f"Failed to synchronize Zone2 volume: {str(e)}")

                    # Zone2 mute: NO sync path. Emotiva protocol §4.2 doesn't include
                    # zone2_mute as a notification property; pymotivaxmc2's Property enum
                    # correctly omits it too — Property.ZONE2_MUTE doesn't exist, so any
                    # status(Property.ZONE2_MUTE) call would AttributeError. Mute (both
                    # zones) is optimistic-only in handle_mute_toggle.

                return updated_properties
            except Exception as e:
                logger.error(f"Error synchronizing Zone2 state: {str(e)}")
                return updated_properties

    async def handle_get_available_inputs(
        self, 
        cmd_config: StandardCommandConfig, 
        params: Dict[str, Any]
    ) -> CommandResult:
        """List the device's visible Input buttons (logical sources).

        Returns ``{input_id: "sourceN", input_name: <user-assigned label>}`` for each visible
        Input button, read live from the device via ``get_input_names()``.
        """
        if not self.client or not self.state.connected:
            try:
                await self.setup()
            except Exception as e:
                return await self._handle_command_error("reconnect device", e, {"action": "get_available_inputs"})
        try:
            await self._refresh_source_map()
            formatted_inputs = [
                {"input_id": f"source{idx}", "input_name": str(info.get("name", "")).strip()}
                for idx, info in sorted(self._source_buttons.items())
                if info.get("visible", True)
            ]
            logger.info(f"Found {len(formatted_inputs)} visible input sources")
            self._update_last_command("get_available_inputs", {})
            return self.create_command_result(
                success=True,
                message=f"Retrieved {len(formatted_inputs)} input sources",
                data=formatted_inputs,
            )
        except Exception as e:
            return await self._handle_command_error("retrieve input sources", e, {"action": "get_available_inputs"})

