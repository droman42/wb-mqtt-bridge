import logging
import asyncio
import socket
import time
from typing import Dict, Any, List, Optional, cast, Tuple
from datetime import datetime
from urllib.parse import urlparse
import xml.etree.ElementTree as ET
import aiohttp

from openhomedevice.device import Device as OpenHomeDevice

from locveil_bridge.infrastructure.devices.base import BaseDevice
from locveil_bridge.domain.devices.models import AuralicDeviceState
from locveil_bridge.infrastructure.config.models import AuralicDeviceConfig, BaseCommandConfig
from locveil_bridge.infrastructure.mqtt.client import MQTTClient
from locveil_bridge.domain.devices.types import CommandResult

logger = logging.getLogger(__name__)

# Note about Auralic devices:
# All control is UPnP/OpenHome over the network (DRV-14) — including power. The
# unit's power ladder: on <-> standby (Product.SetStandby), standby <-> halted
# (HardwareConfig.SetHaltStatus — AURALiC-proprietary, wrapped by the
# openhomedevice fork). In the halted state the network stays up and only
# HardwareConfig keeps being served, so the driver *detects* halt (description
# reachable, Product absent) and wakes it without IR. There is no network-dead
# state short of the rear rocker switch.

class AuralicDevice(BaseDevice[AuralicDeviceState]):
    # Narrow self.config so pyright sees AuralicDeviceConfig-shaped fields.
    config: AuralicDeviceConfig
    """
    Implementation of an Auralic device controlled entirely through OpenHome UPnP.
    
    This class provides control for Auralic audio devices, supporting:
    - UPnP/OpenHome control for all functions, power included (DRV-14)
    - Automatic discovery of devices on the network
    - Robust handling of Auralic's dynamic port assignment
    - State tracking for on / standby / halted (deep sleep, network-alive)
    """
    
    def __init__(self, config: AuralicDeviceConfig, mqtt_client: Optional[MQTTClient] = None) -> None:
        # Call the base class constructor first
        super().__init__(config, mqtt_client)
        
        # Initialize state with typed Pydantic model AFTER super().__init__
        self.state = AuralicDeviceState(
            device_id=config.device_id,
            device_name=config.names.ru,
            ip_address=config.auralic.ip_address,
            # Initialize all remaining fields from the schema
            volume=0,
            mute=False,
            source=None,
            connected=False,
            track_title=None,
            track_artist=None,
            track_album=None,
            transport_state=None,
            deep_sleep=False,
            message=None,
            warning=None
        )
        
        # Store configuration and initialize instance variables
        self.config = cast(AuralicDeviceConfig, config)
        self.ip_address = self.config.auralic.ip_address
        self.update_interval = self.config.auralic.update_interval
        self.discovery_mode = self.config.auralic.discovery_mode
        self.device_url = self.config.auralic.device_url
        self.op_timeout = self.config.auralic.op_timeout
        self.reconnect_interval = self.config.auralic.reconnect_interval
        self.openhome_device = None
        self._update_task = None
        self._deep_sleep_mode = False  # Track if device is in deep sleep mode
        self._last_reconnect_probe = 0.0  # Monotonic time of the last cadenced discovery probe
        self._was_connected = False  # For rate-limited transition logging in the periodic loop
        
        self.device_boot_time = getattr(self.config.auralic, 'device_boot_time', 15)  # Default 15 seconds
        self._discovery_task = None
        
        # Source caching variables
        self._sources_cache = []  # Cache for available sources
        self._sources_cache_timestamp = None  # When the cache was last updated
        self.sources_cache_ttl = 300  # Cache validity in seconds (5 minutes)
        
    
    async def setup(self) -> bool:
        """Initialize the device."""
        try:
            # Initialize openhomedevice
            device = await self._create_openhome_device()

            # Even if discovery fails, continue with setup — the periodic loop
            # keeps probing on the reconnect cadence (DRV-12). Unreachable is NOT
            # assumed to be deep sleep any more (DRV-14): the halted state is
            # *detected* (description up, Product absent), never guessed.
            if not device:
                logger.warning(f"Auralic device unreachable at {self.ip_address} — will keep probing")
                self.update_state(error=f"Device unreachable at {self.ip_address}", connected=False, deep_sleep=False)
                await self.emit_progress(f"{self.device_name} unreachable — will keep probing", "action_progress")
            else:
                await self._adopt_openhome_device(device)

            # Start periodic state updates regardless of discovery success
            self._update_task = asyncio.create_task(self._update_state_periodically())
            
            # Force a full state-change notification so registered callbacks (persistence +
            # WB-publish) see every field — solves the AuralicDeviceState not-fully-serialized
            # case at first boot and republishes all WB controls to the discovered state.
            if self._state_change_callbacks:
                self._notify_state_change(list(self.state.dict().keys()))
            
            logger.info(f"Auralic device {self.get_name()} initialized")
            await self.emit_progress(f"Auralic device {self.device_name} initialized successfully", "action_progress")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Auralic device {self.get_name()}: {str(e)}")
            self.update_state(error=str(e), connected=False, deep_sleep=False)
            await self.emit_progress(f"Failed to initialize {self.device_name}: {str(e)}", "action_error")
            return False
    
    async def shutdown(self) -> bool:
        """Cleanup device resources."""
        try:
            # Cancel update task
            if self._update_task:
                self._update_task.cancel()
                try:
                    await self._update_task
                except asyncio.CancelledError:
                    pass
            
            # Cancel discovery task if running
            if self._discovery_task and not self._discovery_task.done():
                self._discovery_task.cancel()
                try:
                    await self._discovery_task
                except asyncio.CancelledError:
                    pass
            
            logger.info(f"Auralic device {self.get_name()} shutdown complete")
            self.update_state(connected=False)
            await self.emit_progress(f"Auralic device {self.device_name} shutdown complete", "action_success")
            return True
        except Exception as e:
            logger.error(f"Error during device shutdown: {str(e)}")
            return False
    
    async def _op(self, coro, timeout: Optional[float] = None):
        """Await an OpenHome call under a per-operation timeout.

        Auralic enforces a ~10s UPnP subscription timeout and can wedge/stand-by mid-call; without
        a bound a single hung call would stall the polling loop (and pile up behind the interval) or
        block an action indefinitely. Raises asyncio.TimeoutError on expiry."""
        return await asyncio.wait_for(coro, timeout=timeout if timeout is not None else self.op_timeout)

    async def _get_device_properties_async(
        self, device_url: str
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Extract device type, friendly name, and manufacturer from the device description XML.

        Async (aiohttp) so it never blocks the event loop during discovery (discovery can fan out
        across several candidate locations).

        Args:
            device_url: The URL to the device's XML description

        Returns:
            Tuple containing (device_type, friendly_name, manufacturer)
        """
        try:
            timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(device_url) as response:
                    if response.status != 200:
                        logger.debug(f"Failed to fetch device XML: HTTP {response.status}")
                        return None, None, None
                    text = await response.text()

            # Parse XML
            root = ET.fromstring(text)

            # Find namespace
            ns = {"": root.tag.split("}")[0].strip("{") if "}" in root.tag else "urn:schemas-upnp-org:device-1-0"}

            # Extract device type and friendly name
            device_node = root.find(".//device", ns)
            if device_node is None:
                return None, None, None

            device_type = device_node.findtext("deviceType", "", ns)
            friendly_name = device_node.findtext("friendlyName", "", ns)
            manufacturer = device_node.findtext("manufacturer", "", ns)

            return device_type, friendly_name, manufacturer
        except Exception as e:
            logger.debug(f"Error extracting device properties: {str(e)}")
            return None, None, None
    
    @staticmethod
    def _extract_ssdp_locations(responses: List[Tuple[bytes, str]], target_ip: str) -> List[str]:
        """Pull unique LOCATION urls out of raw SSDP datagrams from the target IP.

        Pure parsing (testable): `responses` is [(datagram, sender_ip), ...].
        """
        locations: List[str] = []
        for data, sender_ip in responses:
            if sender_ip != target_ip:
                continue
            for line in data.decode(errors="replace").splitlines():
                if line.lower().startswith("location:"):
                    loc = line.split(":", 1)[1].strip()
                    if loc and urlparse(loc).hostname == target_ip and loc not in locations:
                        locations.append(loc)
        return locations

    @staticmethod
    def _msearch_sync(target_ip: str, timeout: float = 4.0) -> List[Tuple[bytes, str]]:
        """Blocking raw-socket SSDP M-SEARCH; returns raw (datagram, sender_ip) pairs.

        DRV-13: async_upnp_client's SsdpSearchListener received ZERO responses on the
        real network (verified against 0.44.0 with every callback/source/search-target
        variant) while this plain M-SEARCH gets answers from every UPnP device in the
        house, the Auralic included. Runs in an executor from the async path.
        """
        msearch = "\r\n".join([
            "M-SEARCH * HTTP/1.1",
            "HOST: 239.255.255.250:1900",
            'MAN: "ssdp:discover"',
            "MX: 2",
            "ST: upnp:rootdevice",
            "", "",
        ]).encode()
        responses: List[Tuple[bytes, str]] = []
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        try:
            sock.settimeout(1.0)
            sock.sendto(msearch, ("239.255.255.250", 1900))
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                try:
                    data, addr = sock.recvfrom(4096)
                except socket.timeout:
                    continue
                responses.append((data, addr[0]))
        except OSError as e:
            logger.warning(f"SSDP M-SEARCH failed: {e}")
        finally:
            sock.close()
        return responses

    async def _discover_device_url_async(self) -> Optional[str]:
        """Discover the Auralic device URL via raw SSDP M-SEARCH, filtered by IP address."""
        try:
            logger.info(f"Discovering UPnP devices at IP {self.ip_address}...")

            # Raw M-SEARCH in an executor (bounded ~4 s), then parse out candidate
            # locations at our target IP.
            loop = asyncio.get_event_loop()
            responses = await loop.run_in_executor(None, self._msearch_sync, self.ip_address)
            candidate_locations = self._extract_ssdp_locations(responses, self.ip_address)
            for loc in candidate_locations:
                logger.debug(f"Found device at {self.ip_address}: {loc}")

            # Fetch + classify each candidate's description XML asynchronously.
            discovered_devices = []
            for location in candidate_locations:
                device_type, friendly_name, manufacturer = await self._get_device_properties_async(location)
                is_auralic_by_manufacturer = (manufacturer and "AURALIC" in str(manufacturer).upper())
                is_matching_name = (friendly_name and self.device_name.lower() in str(friendly_name).lower())
                if is_auralic_by_manufacturer or is_matching_name:
                    logger.info(f"Found potential device: {friendly_name or 'Unknown'} ({device_type}) at {location}")
                    discovered_devices.append({
                        "location": location,
                        "friendly_name": friendly_name or 'Unknown',
                        "manufacturer": manufacturer or 'Unknown',
                        "device_type": device_type,
                    })

            if not discovered_devices:
                logger.error(f"No Auralic devices found at IP {self.ip_address}")
                return None

            logger.debug(f"Found {len(discovered_devices)} matching devices, applying prioritization")
            
            # Prioritize devices by device type and name match (same logic as before)
            media_renderer_devices = []
            name_matching_devices = []
            
            for device in discovered_devices:
                # Check if it's a MediaRenderer
                if device.get("device_type") and "MediaRenderer" in device.get("device_type", ""):
                    media_renderer_devices.append(device)
                
                # Check if name matches exactly
                if self.device_name.lower() in device.get("friendly_name", "").lower():
                    name_matching_devices.append(device)
            
            # Priority 1: MediaRenderer device that matches the name
            for device in media_renderer_devices:
                if device in name_matching_devices:
                    logger.info(f"Selected MediaRenderer device matching name: {device['friendly_name']} at {device['location']}")
                    return device["location"]
            
            # Priority 2: Any MediaRenderer device
            if media_renderer_devices:
                logger.info(f"Selected MediaRenderer device: {media_renderer_devices[0]['friendly_name']} at {media_renderer_devices[0]['location']}")
                return media_renderer_devices[0]["location"]
            
            # Priority 3: Any device matching the name
            if name_matching_devices:
                logger.info(f"Selected device matching name: {name_matching_devices[0]['friendly_name']} at {name_matching_devices[0]['location']}")
                return name_matching_devices[0]["location"]
            
            # Fallback: Use the first device
            logger.info(f"Using first discovered device: {discovered_devices[0]['friendly_name']} at {discovered_devices[0]['location']}")
            return discovered_devices[0]["location"]
            
        except Exception as e:
            logger.error(f"Error during device discovery: {str(e)}")
            return None

    async def _create_openhome_device(self) -> Optional[OpenHomeDevice]:
        """Create and initialize openhomedevice connection."""
        try:
            device_url = None

            if self.discovery_mode:
                # Use async_upnp_client to discover the device
                logger.info(f"Using discovery mode to find Auralic device at {self.ip_address}")
                device_url = await self._discover_device_url_async()

                if not device_url:
                    logger.error(f"Failed to discover Auralic device at {self.ip_address}")
                    return None
            else:
                # Connect directly using IP address or custom URL
                if self.device_url:
                    logger.info(f"Connecting to Auralic device using custom URL: {self.device_url}")
                    device_url = self.device_url
                else:
                    # NOTE: We can't use a fixed URL format for Auralic devices
                    # They change their port number on each boot, so discovery is required
                    logger.warning("No fixed URL will work reliably with Auralic devices as they use dynamic ports")
                    logger.info(f"Attempting to discover Auralic device at {self.ip_address}")
                    device_url = await self._discover_device_url_async()

                    if not device_url:
                        logger.error(f"Failed to discover Auralic device at {self.ip_address}")
                        return None
            
            # Log the discovered URL - this contains the dynamic port needed for reliable connection
            parsed_url = urlparse(device_url)
            logger.info(f"Connecting to Auralic device at {parsed_url.netloc} (note the dynamic port)")
                    
            # Initialize the OpenHome device with the URL
            device = OpenHomeDevice(device_url)
            
            # Handle the device initialization (which sets up event subscriptions)
            try:
                await self._op(device.init(), timeout=self.op_timeout * 2)
                logger.info("Successfully initialized OpenHome device connection")
            except Exception as e:
                if "412" in str(e):
                    # This is likely due to the 10-second subscription timeout issue
                    logger.warning("Got 412 error during initialization - likely due to Auralic's 10-second event subscription limit")
                    logger.warning("Continuing anyway as basic control functions should still work")
                else:
                    # Reraise other errors
                    raise

            # Halted units (DRV-14) serve the description + HardwareConfig but
            # deregister Product — the standby check can never work there, so
            # classification is the caller's job (_adopt_openhome_device).
            if device.product_service is None:
                logger.info("Device description reachable but Product service absent — likely halted (deep sleep)")
                return device

            # Quick check to see if we can communicate with the device
            try:
                standby = await self._op(device.is_in_standby())
                logger.info(f"Successfully connected to Auralic device, standby state: {standby}")
            except Exception as e:
                logger.warning(f"Connected to device but got error checking standby state: {e}")
                if "412" in str(e):
                    logger.warning("This is likely due to the 10-second event subscription limit")
                    logger.warning("Basic control functions should still work despite these errors")

            return device
                
        except Exception as e:
            logger.error(f"Error connecting to Auralic device: {str(e)}")
            return None
    
    async def _attempt_reconnect(self) -> bool:
        """Re-discover the device and rebuild the OpenHome client.

        Auralic reassigns its HTTP port on every boot, so a connection that goes stale (device
        rebooted, returned from standby, or briefly dropped) can only be recovered by a fresh SSDP
        discovery — not by reusing the old location. Returns True on success."""
        logger.info(f"Attempting to (re)discover Auralic device {self.get_name()}")
        device = await self._create_openhome_device()
        if not device:
            return False
        if not await self._adopt_openhome_device(device):
            return False
        logger.info(f"Reconnected to Auralic device {self.get_name()}")
        return True

    async def _adopt_openhome_device(self, device: OpenHomeDevice) -> bool:
        """Classify a freshly discovered device and take it as the live handle.

        Returns True when fully connected (OpenHome Product present). A device
        without Product is the Auralic **halted** state (DRV-14): network up,
        HardwareConfig served, everything else deregistered — the handle is kept
        anyway so power_on can wake it via SetHaltStatus without re-discovery.
        """
        self.openhome_device = device
        if device.product_service is None:
            already_halted = self._deep_sleep_mode
            self._deep_sleep_mode = True
            self.update_state(
                connected=False,
                power="off",
                deep_sleep=True,
                error=None,
                message="Device is halted (deep sleep) — wake via power_on or the Auralic app",
            )
            # Transition-only INFO — repeats (the cadenced probe re-adopting a
            # still-halted unit) stay at DEBUG to keep the log quiet.
            log = logger.debug if already_halted else logger.info
            log(f"Auralic device {self.get_name()} is halted (deep sleep, network alive)")
            return False
        self._deep_sleep_mode = False
        # Refresh the state's ip_address — a persisted snapshot can carry a
        # pre-DHCP-move address (rack finding: state said .16 long after the
        # config and the unit moved to .142).
        self.update_state(ip_address=self.ip_address)
        await self._update_device_state()      # sets connected=True so the sources refresh below runs
        await self._refresh_sources_cache()
        return True

    async def _probe_halted(self) -> None:
        """Cadenced check of a halted unit — cheap before loud.

        The halted unit's ports move per TRANSITION, not per minute, so the
        stored handle usually stays valid between probes: one GetHaltStatus
        answers "still halted" without any discovery (the old full M-SEARCH
        every 60 s read like a reconnect-failure loop in the log). Only when
        the handle stops answering — or reports not-halted — has the unit
        transitioned, and THAT is the wake signal worth a full rediscovery.
        """
        device = self.openhome_device
        if device is not None:
            try:
                halted = await self._op(device.is_halted())
                if halted:
                    logger.debug(f"Auralic device {self.get_name()} still halted (quiet probe)")
                    return
            except Exception as e:
                logger.debug(f"Halted handle stopped answering ({e}) — rediscovering")
        await self._attempt_reconnect()

    async def _wake_from_halt(self) -> bool:
        """Wake a halted unit over the network (DRV-14; replaced the IR path).

        HardwareConfig.SetHaltStatus(false) transitions the unit into standby
        and the OpenHome services re-register on NEW dynamic ports. The halted
        unit's OWN ports also move on every transition (rack finding: the
        stored handle's port was already dead by power_on time — the wake call
        got connection-refused and never reached the unit), so every attempt
        REDISCOVERS first and sends the wake to the freshest handle. The unit
        may close the connection while acting on the call, so transport errors
        never abort — the next rediscovery is the real success check.
        Re-sending to a unit already waking is harmless (idempotent target).
        """
        for attempt in range(4):
            device = await self._create_openhome_device()
            if device is None and attempt == 0:
                device = self.openhome_device  # last resort: the stored handle
            if device is not None:
                if device.product_service is not None:
                    # Awake (fully re-registered) — adopt and done.
                    return await self._adopt_openhome_device(device)
                try:
                    await self._op(device.set_halt(False))
                except Exception as e:
                    logger.debug(f"set_halt(False) transport hiccup (normal during the transition): {e}")
            await asyncio.sleep(3)
        device = await self._create_openhome_device()
        if device is not None and device.product_service is not None:
            return await self._adopt_openhome_device(device)
        logger.warning("Device did not leave the halted state after SetHaltStatus(false)")
        return False

    async def _update_state_periodically(self) -> None:
        """Periodically update device state in background.

        On a wired LAN the device should normally be reachable; when it isn't (powered off, or a
        reboot changed its port) we keep state honest and attempt a bounded SSDP re-discovery every
        `reconnect_interval` seconds rather than giving up. Logging is rate-limited to the
        connected<->unreachable transitions so a long-offline device doesn't flood the log."""
        loop = asyncio.get_event_loop()

        while True:
            try:
                await self._periodic_tick(loop.time())
                await asyncio.sleep(self.update_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"Auralic periodic update error: {e}")
                await asyncio.sleep(self.update_interval)

    async def _periodic_tick(self, now: float) -> None:
        """One iteration of the periodic loop (extracted for testability)."""
        if self._deep_sleep_mode:
            # Keep state honest — but STILL probe on the reconnect cadence. Deep
            # sleep can end without the bridge's involvement (front panel, the
            # Auralic app), and a boot-time discovery failure sets this flag as a
            # guess, not a fact — the old "stay quiet" branch left a physically
            # woken unit invisible forever (observed live at the rack, DRV-12).
            self.update_state(connected=False, power="off", deep_sleep=True)
            if now - self._last_reconnect_probe >= self.reconnect_interval:
                self._last_reconnect_probe = now
                await self._probe_halted()
        elif self.openhome_device is None:
            # Never connected (e.g. offline at boot) — retry discovery on the cadence.
            if now - self._last_reconnect_probe >= self.reconnect_interval:
                self._last_reconnect_probe = now
                await self._attempt_reconnect()
        else:
            await self._update_device_state()
            if not self.state.connected and now - self._last_reconnect_probe >= self.reconnect_interval:
                # Connection went stale (likely a reboot → new port) — rediscover.
                self._last_reconnect_probe = now
                await self._attempt_reconnect()

        # Rate-limited transition logging.
        if self.state.connected and not self._was_connected:
            logger.info(f"Auralic device {self.get_name()} is reachable")
        elif not self.state.connected and self._was_connected:
            logger.warning(f"Auralic device {self.get_name()} is unreachable — will keep retrying every {self.reconnect_interval}s")
        self._was_connected = self.state.connected
    
    async def _update_device_state(self) -> None:
        """Update current device state.

        A cheap liveness probe (is_in_standby) runs first under a timeout; if it fails, the device
        is unreachable and we bail immediately (marking disconnected) instead of firing five more
        calls that would each have to time out. Every OpenHome call is bounded by `_op`.
        track_info is isolated so a single bad/garbled DIDL payload can't drop the whole device to
        disconnected — we keep the rest of the state and leave the track fields stale."""
        if not self.openhome_device:
            self.update_state(connected=False, deep_sleep=self._deep_sleep_mode)
            return

        # A halted handle (DRV-14) has no Product service — nothing to poll.
        if self.openhome_device.product_service is None:
            self.update_state(connected=False, power="off", deep_sleep=True)
            return

        # Liveness probe — fast-fail when unreachable.
        try:
            in_standby = await self._op(self.openhome_device.is_in_standby())
        except Exception as e:
            self.update_state(connected=False, error=str(e), deep_sleep=self._deep_sleep_mode)
            return

        try:
            power_state = "off" if in_standby else "on"
            transport_state = await self._op(self.openhome_device.transport_state())

            # Volume/mute may be absent on this unit (no Volume service) — the lib returns None;
            # don't write None into the non-optional state fields.
            volume = await self._op(self.openhome_device.volume())
            mute = await self._op(self.openhome_device.is_muted())

            # Current source. Two dead ends, verified live 2026-07-07: the lib's
            # source() returns a dict (never an int — the old isinstance check
            # silently kept source at None), and on this unit its name/type are
            # EMPTY even mid-playback. The reliable route is the raw Product
            # SourceIndex matched against the sources list (real names from
            # SourceXml, carrying true device indices).
            sources = await self._op(self.openhome_device.sources())
            current_source = None
            try:
                idx_action = self.openhome_device.product_service.action("SourceIndex")
                source_index = (await self._op(idx_action.async_call()))["Value"]
                current_source = next(
                    (s["name"] for s in sources if s.get("index") == source_index), None
                )
            except Exception as e:
                logger.debug(f"Could not get current source: {str(e)}")

            updates: Dict[str, Any] = {
                "connected": True,
                "power": power_state,
                "source": current_source,
                "transport_state": transport_state,
                "deep_sleep": False,  # Device is connected, so not in deep sleep
            }
            if volume is not None:
                updates["volume"] = volume
            if mute is not None:
                updates["mute"] = mute

            # Track metadata in its own guard — a bad DIDL payload shouldn't disconnect the device.
            try:
                track_info = await self._op(self.openhome_device.track_info())
                updates["track_title"] = self._didl_text(track_info.get("title"))
                updates["track_artist"] = self._didl_text(track_info.get("artist"))
                updates["track_album"] = self._didl_text(track_info.get("album"))
            except Exception as e:
                logger.debug(f"Could not parse track info (keeping prior values): {str(e)}")

            self.update_state(**updates)

        except Exception as e:
            logger.debug(f"Error updating device state: {str(e)}")
            self.update_state(connected=False, error=str(e), deep_sleep=self._deep_sleep_mode)

    @staticmethod
    def _didl_text(value: Any) -> Optional[str]:
        """Flatten a DIDL-Lite text field to a plain string.

        openhomedevice parses `upnp:artist` with many=True, so multi-artist
        tracks arrive as a LIST — which the str-typed state fields reject
        (rack finding 2026-07-07: `['AC/DC']` knocked the device to
        disconnected via a validation error raised OUTSIDE the parse guard).
        """
        if value is None:
            return None
        if isinstance(value, (list, tuple)):
            joined = ", ".join(str(v) for v in value if v)
            return joined or None
        return str(value)

    async def _refresh_sources_cache(self) -> bool:
        """Refresh the internal cache of available sources.
        
        This method queries the device for available sources and stores 
        them in the internal cache for future use.
        
        Returns:
            bool: True if refresh was successful, False otherwise
        """
        if not self.openhome_device or not self.state.connected:
            logger.debug("Cannot refresh sources: device not connected")
            return False
            
        try:
            # Get sources from OpenHome API
            sources = await self.openhome_device.sources()
            
            # Process sources into the options dialect the UI dropdown maps
            # (input_id/input_name — same fields the LG driver emits). The id is
            # the library-reported TRUE device index: sources() filters out
            # invisible sources but invisible ones still occupy index slots, so
            # a filtered-list position would select the wrong source on the
            # device (SetSourceIndex takes the raw index).
            formatted_sources = []
            for idx, source in enumerate(sources):
                formatted_sources.append({
                    "input_id": str(source.get("index", idx)),
                    "input_name": source.get("name", f"Unknown Source {idx}"),
                    "type": source.get("type", "unknown"),
                })
            
            # Store in cache
            self._sources_cache = formatted_sources
            self._sources_cache_timestamp = datetime.now()
            
            logger.debug(f"Refreshed sources cache, found {len(formatted_sources)} sources")
            return True
        except Exception as e:
            logger.error(f"Failed to refresh sources cache: {str(e)}")
            # Clear cache on error
            self._sources_cache = []
            self._sources_cache_timestamp = None
            return False
    
    async def _get_available_sources(self) -> List[Dict[str, Any]]:
        """Get available sources, using cache if available and valid.
        
        This method returns the list of available input sources from the
        cache if it's valid, or refreshes the cache if needed.
        
        Returns:
            List[Dict[str, Any]]: List of available sources
        """
        # Check if cache is valid
        cache_valid = (
            self._sources_cache and
            self._sources_cache_timestamp and
            (datetime.now() - self._sources_cache_timestamp).total_seconds() < self.sources_cache_ttl
        )
        
        # Refresh cache if necessary
        if not cache_valid:
            logger.debug("Sources cache invalid or expired, refreshing")
            await self._refresh_sources_cache()
            
        return self._sources_cache

    # Handler methods

    async def handle_power_on(self, cmd_config: BaseCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """
        Handle power on command.
        
        All-network (DRV-14): a halted unit is woken via HardwareConfig
        SetHaltStatus(false) into standby, then SetStandby(false) completes.
        
        Args:
            cmd_config: Command configuration
            params: Command parameters
                
        Returns:
            CommandResult: Result of the command
        """
        # CASE 1: Device is halted (deep sleep) — wake over the network (DRV-14;
        # replaced the IR path): SetHaltStatus(false) moves it to standby, then
        # CASE 2 below completes the standby exit on the fresh handle.
        if self._deep_sleep_mode:
            logger.info("Device is halted — waking via HardwareConfig.SetHaltStatus")
            self.update_state(message="Waking from deep sleep (halt)...")
            if not await self._wake_from_halt():
                return self.create_command_result(
                    success=False,
                    error="Failed to wake device from the halted state"
                )

        # CASE 2: Device is connected but in standby, use OpenHome API
        if self.openhome_device is not None:
            logger.info("Device in standby mode, using OpenHome API to wake")
            
            try:
                # Idempotence guard (honors `force` — DRV-5; live-query based, so
                # LOW force value, but forcing SetStandby(false) is harmless —
                # idempotent target). NB the _deep_sleep_mode check above is an
                # AVAILABILITY branch, never force-bypassed.
                in_standby = await self.openhome_device.is_in_standby()
                skip = self.idempotence_skip(
                    params, not in_standby, "Device is already powered on"
                )
                if skip is not None:
                    logger.info("Device already powered on")
                    return skip
                    
                # Wake the device from standby
                await self.openhome_device.set_standby(False)
                
                # Refresh sources cache after waking from standby
                logger.debug("Refreshing sources cache after waking from standby")
                await self._refresh_sources_cache()
                
                # Update state
                await self._update_device_state()
                
                return self.create_command_result(
                    success=True,
                    message="Device woken from standby mode"
                )
            except Exception as e:
                logger.error(f"Error using OpenHome API to wake device: {str(e)}")
                return self.create_command_result(
                    success=False,
                    error=f"Failed to wake device from standby: {str(e)}"
                )

        # Device unreachable (no handle at all) — nothing to send a wake to.
        # The periodic loop keeps probing; there is no IR fallback any more
        # (DRV-14: every reachable power state is network-controllable).
        return self.create_command_result(
            success=False,
            error="Device unreachable — cannot power on"
        )

    async def handle_power_off(self, cmd_config: BaseCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """
        Handle power off command.
        
        All-network (DRV-14): full power off = SetStandby(true) + SetHaltStatus(true)
        ("halted" — the deepest state reachable without the rear rocker; network stays up).
        
        Args:
            cmd_config: Command configuration
            params: Command parameters
                standby_only: If True, only put the device in standby mode (no IR)
                
        Returns:
            CommandResult: Result of the command
        """
        try:
            # Check if we should only put the device in standby mode
            standby_only = params.get("standby_only", False)
            
            # If device already appears to be in deep sleep mode
            if self._deep_sleep_mode and not self.openhome_device:
                logger.info("Device already appears to be in deep sleep/off mode")
                return self.create_command_result(
                    success=True,
                    message="Device already appears to be powered off"
                )
            
            # CASE 1: Standby only mode requested and device is connected
            if standby_only and self.openhome_device:
                logger.info("Standby-only mode requested, putting device in standby mode")
                
                try:
                    # First try to stop playback if it's running
                    try:
                        transport_state = await self.openhome_device.transport_state()
                        if transport_state != "Stopped":
                            logger.info("Stopping playback before standby")
                            await self.openhome_device.stop()
                            await asyncio.sleep(0.5)  # Short delay after stopping playback
                    except Exception as e:
                        logger.warning(f"Error stopping playback: {e}")
                    
                    # Put the device in standby mode
                    await self.openhome_device.set_standby(True)
                    logger.info("Device put in standby mode")
                    
                    # Update state
                    await self._update_device_state()
                    
                    return self.create_command_result(
                        success=True,
                        message="Device put into standby mode as requested",
                        info="Use power_off without standby_only=true for full power off"
                    )
                except Exception as e:
                    logger.error(f"Error putting device in standby: {e}")
                    return self.create_command_result(
                        success=False,
                        error=f"Failed to put device in standby mode: {str(e)}"
                    )
            
            # CASE 2: Full power off = standby + halt, all over the network
            # (DRV-14; replaced the IR toggle). "Halted" is the deepest state the
            # unit can reach without the rear rocker: network stays up, only
            # HardwareConfig keeps being served.
            if self._deep_sleep_mode:
                return self.create_command_result(
                    success=True,
                    message="Device is already halted (deep sleep)"
                )
            if not self.openhome_device:
                return self.create_command_result(
                    success=False,
                    error="Device unreachable — cannot power off"
                )

            # Stop playback first, then standby, then halt.
            try:
                transport_state = await self.openhome_device.transport_state()
                if transport_state != "Stopped":
                    logger.info("Stopping playback before power off")
                    await self.openhome_device.stop()
                    await asyncio.sleep(0.5)
            except Exception as e:
                logger.warning(f"Error stopping playback: {e}")

            try:
                await self.openhome_device.set_standby(True)
            except Exception as e:
                logger.error(f"Failed to put device in standby: {e}")
                return self.create_command_result(
                    success=False,
                    error=f"Failed to power off: {str(e)}"
                )

            try:
                await self._op(self.openhome_device.set_halt(True))
            except Exception as e:
                # The unit closes the connection while acting on the halt call
                # (observed live) — treat transport errors as the transition
                # starting. The periodic probe self-corrects either way: it
                # rediscovers the unit and classifies halted vs standby from
                # what the device actually serves.
                logger.debug(f"set_halt(True) transport hiccup (normal during the transition): {e}")

            self._deep_sleep_mode = True
            self.update_state(
                connected=False,
                power="off",
                message="Device halted (deep sleep) — network wake available",
                deep_sleep=True
            )

            return self.create_command_result(
                success=True,
                message="Device powered off (standby + halt)",
                info="Halted state keeps the network up; power_on wakes it without IR"
            )

        except Exception as e:
            logger.error(f"Error executing power off: {str(e)}")
            return self.create_command_result(
                success=False,
                error=f"Failed to power off: {str(e)}"
            )

    async def handle_play(self, cmd_config: BaseCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """Handle play command."""
        try:
            if not self.openhome_device:
                return self.create_command_result(
                    success=False,
                    error="Device not connected"
                )
                
            await self._op(self.openhome_device.play())
            await self._update_device_state()

            return self.create_command_result(
                success=True,
                message="Playback started"
            )
        except Exception as e:
            logger.error(f"Error executing play: {str(e)}")
            return self.create_command_result(
                success=False,
                error=f"Failed to start playback: {str(e)}"
            )

    async def handle_pause(self, cmd_config: BaseCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """Handle pause command."""
        try:
            if not self.openhome_device:
                return self.create_command_result(
                    success=False,
                    error="Device not connected"
                )
                
            await self._op(self.openhome_device.pause())
            await self._update_device_state()

            return self.create_command_result(
                success=True,
                message="Playback paused"
            )
        except Exception as e:
            logger.error(f"Error executing pause: {str(e)}")
            return self.create_command_result(
                success=False,
                error=f"Failed to pause playback: {str(e)}"
            )

    async def handle_stop(self, cmd_config: BaseCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """Handle stop command."""
        try:
            if not self.openhome_device:
                return self.create_command_result(
                    success=False,
                    error="Device not connected"
                )
                
            await self._op(self.openhome_device.stop())
            await self._update_device_state()

            return self.create_command_result(
                success=True,
                message="Playback stopped"
            )
        except Exception as e:
            logger.error(f"Error executing stop: {str(e)}")
            return self.create_command_result(
                success=False,
                error=f"Failed to stop playback: {str(e)}"
            )

    async def handle_next(self, cmd_config: BaseCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """Handle next track command."""
        try:
            if not self.openhome_device:
                return self.create_command_result(
                    success=False,
                    error="Device not connected"
                )

            # OpenHome's skip takes a signed offset: +1 = next, -1 = previous.
            await self._op(self.openhome_device.skip(1))
            await self._update_device_state()

            return self.create_command_result(
                success=True,
                message="Skipped to next track"
            )
        except Exception as e:
            logger.error(f"Error executing next: {str(e)}")
            return self.create_command_result(
                success=False,
                error=f"Failed to skip to next track: {str(e)}"
            )

    async def handle_previous(self, cmd_config: BaseCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """Handle previous track command."""
        try:
            if not self.openhome_device:
                return self.create_command_result(
                    success=False,
                    error="Device not connected"
                )

            # OpenHome's skip takes a signed offset: -1 = previous.
            await self._op(self.openhome_device.skip(-1))
            await self._update_device_state()

            return self.create_command_result(
                success=True,
                message="Skipped to previous track"
            )
        except Exception as e:
            logger.error(f"Error executing previous: {str(e)}")
            return self.create_command_result(
                success=False,
                error=f"Failed to skip to previous track: {str(e)}"
            )

    async def handle_set_volume(self, cmd_config: BaseCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """Handle set volume command."""
        try:
            if not self.openhome_device:
                return self.create_command_result(
                    success=False,
                    error="Device not connected"
                )
                
            # Check for both parameter names for backward compatibility
            volume = params.get("volume")
            if volume is None:
                volume = params.get("level")  # Check old parameter name
                
            if volume is None:
                return self.create_command_result(
                    success=False,
                    error="Volume parameter is required"
                )
            
            # Ensure volume is within range (0-100)
            volume = max(0, min(100, int(volume)))
            
            # Set volume
            await self._op(self.openhome_device.set_volume(volume))

            # Update state
            await self._update_device_state()
            
            return self.create_command_result(
                success=True,
                message=f"Volume set to {volume}"
            )
        except Exception as e:
            logger.error(f"Error setting volume: {str(e)}")
            return self.create_command_result(
                success=False,
                error=f"Failed to set volume: {str(e)}"
            )

    async def handle_volume_up(self, cmd_config: BaseCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """Handle volume up command."""
        try:
            if not self.openhome_device:
                return self.create_command_result(
                    success=False,
                    error="Device not connected"
                )
                
            await self._op(self.openhome_device.increase_volume())
            await self._update_device_state()

            return self.create_command_result(
                success=True,
                message="Volume increased"
            )
        except Exception as e:
            logger.error(f"Error increasing volume: {str(e)}")
            return self.create_command_result(
                success=False,
                error=f"Failed to increase volume: {str(e)}"
            )

    async def handle_volume_down(self, cmd_config: BaseCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """Handle volume down command."""
        try:
            if not self.openhome_device:
                return self.create_command_result(
                    success=False,
                    error="Device not connected"
                )
                
            await self._op(self.openhome_device.decrease_volume())
            await self._update_device_state()

            return self.create_command_result(
                success=True,
                message="Volume decreased"
            )
        except Exception as e:
            logger.error(f"Error decreasing volume: {str(e)}")
            return self.create_command_result(
                success=False,
                error=f"Failed to decrease volume: {str(e)}"
            )

    async def handle_mute(self, cmd_config: BaseCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """Handle mute toggle command."""
        try:
            if not self.openhome_device:
                return self.create_command_result(
                    success=False,
                    error="Device not connected"
                )
                
            # Get current mute state
            is_muted = await self._op(self.openhome_device.is_muted())

            # A unit with no Volume service returns None — there's nothing to mute.
            if is_muted is None:
                return self.create_command_result(
                    success=False,
                    error="Mute/volume control is not available on this device"
                )

            # Toggle mute state
            await self._op(self.openhome_device.set_mute(not is_muted))

            # Update state
            await self._update_device_state()

            return self.create_command_result(
                success=True,
                message=f"Device {'unmuted' if is_muted else 'muted'}"
            )
        except Exception as e:
            logger.error(f"Error toggling mute: {str(e)}")
            return self.create_command_result(
                success=False,
                error=f"Failed to toggle mute: {str(e)}"
            )

    async def handle_set_input(self, cmd_config: BaseCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """Handle set input command."""
        try:
            if not self.openhome_device:
                return self.create_command_result(
                    success=False,
                    error="Device not connected"
                )
                
            source = params.get("input")
            if source is None:
                return self.create_command_result(
                    success=False,
                    error="Input parameter is required"
                )
            
            # Resolve against the cached options (input_id = TRUE device index —
            # SetSourceIndex takes the raw index; filtered-list positions would
            # select the wrong source because invisible sources occupy slots).
            sources = await self._get_available_sources()

            if isinstance(source, (int, str)) and str(source).isdigit():
                match = next((s for s in sources if s["input_id"] == str(int(source))), None)
                if match is None:
                    return self.create_command_result(
                        success=False,
                        error=f"Invalid source index: {source}"
                    )
            else:
                match = next(
                    (s for s in sources if s["input_name"].lower() == str(source).lower()),
                    None,
                )
                if match is None:
                    return self.create_command_result(
                        success=False,
                        error=f"Source not found: {source}"
                    )

            await self.openhome_device.set_source(int(match["input_id"]))
            source_name = match["input_name"]
            
            # Update state
            await self._update_device_state()
            
            return self.create_command_result(
                success=True,
                message=f"Source set to {source_name}"
            )
        except Exception as e:
            logger.error(f"Error setting source: {str(e)}")
            return self.create_command_result(
                success=False,
                error=f"Failed to set source: {str(e)}"
            )

    async def handle_track_info(self, cmd_config: BaseCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """Handle track info command."""
        try:
            if not self.openhome_device:
                return self.create_command_result(
                    success=False,
                    error="Device not connected"
                )
                
            # Get current track info
            track_info = await self.openhome_device.track_info()
            
            # Update state
            await self._update_device_state()
            
            return self.create_command_result(
                success=True,
                message="Track information retrieved",
                track_info=track_info
            )
        except Exception as e:
            logger.error(f"Error getting track info: {str(e)}")
            return self.create_command_result(
                success=False,
                error=f"Failed to get track info: {str(e)}"
            )

    async def handle_get_available_inputs(self, cmd_config: BaseCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """
        Handle retrieving available inputs from the device.
        
        Returns a list of available inputs as pairs of input_id and input_name.
        
        Args:
            cmd_config: Command configuration
            params: Command parameters
                refresh_cache: If True, force a cache refresh
                
        Returns:
            CommandResult: Result with list of available inputs
        """
        try:
            logger.info("Retrieving available inputs from device")
            
            # Check if device is connected
            if not self.openhome_device or not self.state.connected:
                # Check if we're in deep sleep mode
                if self._deep_sleep_mode:
                    return self.create_command_result(
                        success=False,
                        error="Device is powered off (deep sleep mode)"
                    )
                else:
                    return self.create_command_result(
                        success=False,
                        error="Device not connected"
                    )
            
            # Check if we should force a refresh
            force_refresh = params.get("refresh_cache", False)
            if force_refresh:
                logger.info("Forcing refresh of sources cache")
                await self._refresh_sources_cache()
            
            # Get available sources
            sources = await self._get_available_sources()
            
            if not sources:
                logger.warning("No sources found on device")
                return self.create_command_result(
                    success=True,
                    message="No sources found on device",
                    data=[]
                )
            
            logger.info(f"Found {len(sources)} sources")
            
            return self.create_command_result(
                success=True,
                message=f"Retrieved {len(sources)} sources",
                data=sources
            )
                
        except Exception as e:
            error_msg = f"Error retrieving sources: {str(e)}"
            logger.error(error_msg)
            return self.create_command_result(
                success=False, 
                error=error_msg
            )
    
    async def handle_refresh_inputs(self, cmd_config: BaseCommandConfig, params: Dict[str, Any]) -> CommandResult:
        """
        Handle manual refresh of inputs cache.
        
        Args:
            cmd_config: Command configuration
            params: Command parameters
                
        Returns:
            CommandResult: Result of refresh operation
        """
        try:
            logger.info("Manually refreshing sources cache")
            
            # Check if device is connected
            if not self.openhome_device or not self.state.connected:
                if self._deep_sleep_mode:
                    return self.create_command_result(
                        success=False,
                        error="Device is powered off (deep sleep mode)"
                    )
                else:
                    return self.create_command_result(
                        success=False,
                        error="Device not connected"
                    )
            
            # Perform the refresh
            success = await self._refresh_sources_cache()
            
            if success:
                sources_count = len(self._sources_cache)
                return self.create_command_result(
                    success=True,
                    message=f"Successfully refreshed sources cache, found {sources_count} sources"
                )
            else:
                return self.create_command_result(
                    success=False,
                    error="Failed to refresh sources cache"
                )
                
        except Exception as e:
            error_msg = f"Error refreshing sources: {str(e)}"
            logger.error(error_msg)
            return self.create_command_result(
                success=False, 
                error=error_msg
            )


    async def _delayed_discovery(self, delay: Optional[float] = None) -> None:
        """
        Perform device discovery after a delay to allow device to boot.
        
        Args:
            delay: Delay in seconds before attempting discovery. If None, use device_boot_time.
        """
        # Resolve delay to a concrete float; device_boot_time may be Optional in
        # the config schema, fall back to 15 (the Auralic default boot window).
        if delay is None:
            boot_time = self.device_boot_time
            delay = float(boot_time) if boot_time is not None else 15.0
        else:
            delay = float(delay)

        try:
            logger.info(f"Waiting {delay} seconds for device to boot before discovery")
            await asyncio.sleep(delay)
            
            logger.info("Attempting device discovery after boot delay")
            await self.emit_progress(f"Attempting to reconnect to {self.device_name} after power on", "action_progress")
            self.openhome_device = await self._create_openhome_device()
            
            if self.openhome_device:
                logger.info("Device successfully discovered after power on")
                await self.emit_progress(f"Successfully reconnected to {self.device_name}", "action_progress")
                self._deep_sleep_mode = False
                
                # Refresh sources cache after power on
                logger.debug("Refreshing sources cache after power on")
                await self._refresh_sources_cache()
                
                await self._update_device_state()
            else:
                logger.error("Failed to discover device after power on")
                self._deep_sleep_mode = True  # Still consider it in deep sleep mode
        except asyncio.CancelledError:
            logger.info("Delayed discovery cancelled")
        except Exception as e:
            logger.error(f"Error during delayed discovery: {str(e)}")
            
    def _start_delayed_discovery(self, delay: Optional[float] = None) -> None:
        """
        Start a background task for delayed discovery.
        Cancels any existing discovery task first.
        
        Args:
            delay: Delay in seconds before discovery
        """
        # Cancel existing task if it exists
        if self._discovery_task and not self._discovery_task.done():
            self._discovery_task.cancel()
            
        # Create new task
        self._discovery_task = asyncio.create_task(self._delayed_discovery(delay)) 
        
    async def refresh_sources(self) -> bool:
        """Public method to manually refresh the sources cache.
        
        This can be called from external code to update the cache.
        
        Returns:
            bool: True if refresh was successful, False otherwise
        """
        logger.info(f"Manually refreshing sources for device {self.get_name()}")
        return await self._refresh_sources_cache() 