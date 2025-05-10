Perfect, thanks! I'll look for any official or unofficial (including reverse-engineered) REST APIs or libraries that can help you integrate your Auralic Altair streamer into your Wirenboard-based smart home system, focusing both on control (playback, volume, input switching) and metadata (current track, browsing, etc.). I'll also check for any public libraries or projects you might reuse.

I'll get started and update you shortly!

# Integrating Auralic Altair into a Smart Home (Wirenboard) Environment

Integrating an AURALiC Altair streamer into a custom smart home setup (e.g. with Wirenboard) is certainly possible, even though Auralic doesn't publish a simple REST API. The key is to leverage the **OpenHome (UPnP)** network protocol that Auralic's "Lightning" platform is built on, and any available community libraries or integrations that use it. Below we outline the available methods – both official and unofficial – to control the Altair (playback, volume, inputs) and retrieve metadata (current track info, library browsing, etc.), along with examples and comparisons of each approach.

## 1. **Official Control Methods: Lightning DS & OpenHome Compatibility**

**Lightning DS (iOS App):** Auralic's official control app is Lightning DS, available only on iOS. It provides full control over playback (play/pause/stop, next/prev), volume, input selection, and library browsing (including streaming services like Tidal/Qobuz, Internet radio, and local UPnP/DLNA servers). However, Lightning DS is **not cross-platform** and has no exposed public API. It's meant for human use via the app, not automation. Auralic has kept it iOS-exclusive for stability reasons.

**Lightning Web Interface:** The Altair also hosts a built-in web interface, accessible by pointing a browser to the device's IP address on your network. This **web UI** is mainly for setup and configuration (network settings, device settings) rather than day-to-day playback control. It allows changing hardware settings via a browser, but does not offer a documented API for programmatic control of playback or metadata. (It's essentially a GUI for settings; the **Now Playing/Queue** view is on the device's front panel or in apps, not fully in the web UI.)

**OpenHome / UPnP:** Fortunately, Auralic's streaming platform is built on **OpenHome**, an open extension of UPnP AV specifically for audio streaming ([What is AURALiC Lightning? – AURALIC LIMITED](https://support.auralic.com/hc/en-us/articles/206073478-What-is-AURALiC-Lightning#:~:text=AURALiC%20Lightning%20is%20an%20open,extension%20of%20existing%20OpenHome%20standard)). In fact, Auralic states that *"Lightning OS can be controlled by any OpenHome based control software"*. This means the Altair acts as a standard OpenHome Media Renderer on your network. Any third-party OpenHome controller or app can discover it and send it commands. For example, Auralic devices are compatible with control apps like **BubbleUPnP, Linn Kazoo, Lumin, or Kinsky** on Android/PC. This open standard is the key to integration: **OpenHome exposes network services for transport control, volume, source selection, and now-playing info**. In addition, the Altair is "uPnP A/V compatible", meaning it can also work with generic UPnP/DLNA controllers (though with some limitations – see below).

**Roon, Spotify Connect, etc.:** Besides OpenHome, the Altair supports other network streaming protocols **for specific ecosystems**: it is a Roon Ready endpoint, and supports Spotify Connect, TIDAL Connect, AirPlay, and Bluetooth as inputs. These can be useful in integration (for example, you could drive it via the Spotify API or AirPlay), but keep in mind these methods hand off control to those services (e.g. Spotify's API or Roon's API) rather than controlling the device directly. They may not give you full feedback of local library tracks or the ability to browse all sources. They are alternatives if you primarily use those services, but **the most general solution for custom integration remains the OpenHome/UPnP interface**, which works for **all sources and local content** on the Altair.

**Summary:** There is no **official REST/HTTP JSON API** documented by Auralic specifically for the Altair. Instead, the device is controlled via open standards (OpenHome UPnP) and proprietary apps. The lack of a published REST API means we have to use these open protocols or reverse-engineered solutions.

## 2. **OpenHome UPnP API – The Primary Integration Method**

Because the Altair adheres to OpenHome, you can control it using standard UPnP control protocols (SOAP/XML based) or libraries that abstract those protocols. This gives programmatic access to all the important functions:

- **Playback control:** Play, Pause, Stop, Next/Previous track, etc.  
- **Transport state and metadata:** Get the current status (Playing/Paused/Stopped/Buffering) and now-playing track info (title, artist, album, etc).  
- **Volume and mute:** Both absolute volume set and incremental up/down, plus mute toggle (the Altair has a built-in preamp with digital volume).  
- **Source selection:** Switch inputs or "sources" (e.g. Altair's **OpenHome playlist** source vs. other inputs like AirPlay, Bluetooth, analog/digital inputs). Auralic exposes these as a list of sources you can query and set.  
- **Queue management:** OpenHome uses an *on-device playlist/queue*. You can add tracks to the queue, skip to next/previous, or even directly play a given track URL. (Standard UPnP "AV Transport" is slightly different; OpenHome's on-device queue is an improvement so the controller need not remain connected.)  
- **Library browsing:** If you are accessing local music, typically a UPnP **Media Server** is involved. The Altair's Lightning OS includes an optional "Lightning Server" (DLNA/UPnP media server) that can index an internal drive or network share. You can use UPnP ContentDirectory calls to browse that library. Alternatively, if you use an external NAS with a UPnP server (MinimServer, Plex DLNA, etc.), you would browse that server. In either case, the browsing can be done via standard UPnP browse/search actions. (OpenHome itself focuses on rendering and playlist; library navigation is typically via the media server's API.)

**Using Existing Libraries:** Rather than implementing the UPnP/SOAP calls from scratch, you can save time by using community libraries or integrations:

- **Home Assistant OpenHome Integration:** Home Assistant has a built-in *"Linn / OpenHome"* integration that works with any OpenHome-compliant streamer (not just Linn – it works for Auralic too). This integration auto-discovers the device and exposes it as a `media_player` entity with full control. You can play/pause, seek, change volume, switch source, and it will show the current track metadata in Home Assistant's UI ([Linn / OpenHome - Home Assistant](https://www.home-assistant.io/integrations/openhome/#:~:text=The%20Linn%20%2F%20OpenHome%20integration,see%20the%20current%20playing%20item)). Users have reported that this integration works for Auralic devices, enabling control of playback and volume, and showing "now playing" info. For example, Home Assistant can call services like `media_player.play_media` to play a given URL or stream on the Altair ([Linn / OpenHome - Home Assistant](https://www.home-assistant.io/integrations/openhome/#:~:text=actions%3A%20,media_content_type%3A%20music)). It also supports features like **pins** (Auralic's preset shortcuts) via an `invoke_pin` action ([Linn / OpenHome - Home Assistant](https://www.home-assistant.io/integrations/openhome/#:~:text=Media%20control%20actions)). This is a **practical example** of using the OpenHome API under the hood – Home Assistant uses a Python UPnP client to talk to the device. Even if you don't use Home Assistant outright, its existence confirms that the OpenHome interface is accessible and has been implemented in code.

- **Python OpenHome Library (openhomedevice):** There is an open-source Python library by Barry Williams (`bazwilliams` on GitHub) called **`openhomedevice`** which specifically provides a friendly API to control OpenHome renderers (like Linn and Auralic). Using this library, you can script control of the Altair in a Python environment (which Wirenboard can likely support). The library uses an async UPnP client internally to communicate with the device. It exposes methods that map closely to the device's capabilities. For example: 

  - `device.play()`, `device.pause()`, `device.stop()` – transport controls  
  - `device.set_volume(x)`, `device.increase_volume()`, `device.set_mute(True/False)` – volume control  
  - `device.set_source(index)` – change input/source by index (you can retrieve the list via `device.sources()`)  
  - `device.track_info()` – get current track metadata (likely returns a dictionary with fields like title, artist, album, track URI, etc.)  
  - `device.transport_state()` – get the state ("Playing", "Paused", etc.)  
  - `device.is_in_standby()` – check power state (some Auralic units have a standby mode)  
  - And many more (e.g. firmware update checks, retrieving the device's name, list of preset *pins*, etc.).

  Using `openhomedevice` is straightforward: you initialize a `Device` with the Altair's device URL or via discovery, then call these async methods. This library was [used in Home Assistant's integration as well](https://www.home-assistant.io/integrations/openhome/), so it's fairly mature. With this, you can integrate the Altair into automation scripts – for example, adjust volume or pause music when a phone call comes in, or fetch the current song info to display on a dashboard.

- **Other Languages/Tools:** If Python isn't suitable, you can use other UPnP control libraries. For instance, **JavaScript/Node.js** has libraries for UPnP (though not Auralic-specific). One example is using a generic UPnP control point library or the Node package `upnp-client` to send SOAP commands. The OpenHome spec defines services like `AVTransport`, `RenderingControl`, or OpenHome's extended `Playlist` and `Product` services. Some enthusiasts have added OpenHome support to open-source renderers; e.g., the gmrender project on GitHub shows implementation of OpenHome "Playlist" service, which can guide how to form the commands. If needed, you could also manually send SOAP requests (using `curl` or HTTP libraries) to the Altair's service endpoints (obtained from its UPnP device description XML). This is low-level, but possible. 

  > *Note:* Auralic devices often implement **both** the standard UPnP AV services **and** the OpenHome services. OpenHome's `Playlist` service replaces the traditional UPnP `AVTransport` for better queue handling. If you use a generic DLNA controller or library, the Altair might appear as a standard *Digital Media Renderer*. Basic commands (play/pause, etc.) could work via AVTransport, but you might miss out on the on-device queue features and advanced metadata. Wherever possible, use the OpenHome extensions for full functionality.

**Metadata retrieval:** Both Home Assistant's integration and `openhomedevice` will give you **current track metadata** programmatically. For example, Home Assistant shows the *media_title*, *media_artist*, etc., and `openhomedevice.device.track_info()` returns a dictionary with track info. This data comes from the Altair's OpenHome **Info** service (which provides the now playing details, including album art URI if available, track duration, etc.) and the **Time** service (for track elapsed time). By polling or subscribing to those (the library likely handles subscription), you can keep your smart home in sync with what's playing. This is great for displaying "Now Playing" on a touch panel or triggering actions based on song changes.

**Browsing the library:** If you want to browse a music library (e.g. folders, albums, playlists), you typically interact with a **Media Server**. If the Altair is configured with Lightning Server (for an internal drive or NAS share), it effectively acts as a UPnP MediaServer on the network. You could use standard **ContentDirectory** calls (`Browse` action) to retrieve the music list. This isn't specific to Auralic – it's the same as browsing any DLNA media server. Some open-source tools (e.g., `python-dlnalib` or the `async_upnp_client` used by openhomedevice) can perform ContentDirectory browse. Alternatively, you could run a separate media server on your NAS and query that. In short, **browsing is possible via UPnP**; it's just not part of the "renderer control" API but rather the server side. Lightning DS app handles this behind the scenes (presenting you the library and then enqueuing tracks to the renderer). In a custom setup, you might script browsing or pre-define favorite paths/IDs to play via the OpenHome `play_media` command.

**Example:** To tie it together, here's a conceptual example using Python (pseudocode for brevity):

```python
from openhomedevice import Device

device = Device("http://<Altair-IP>:<port>/DeviceDescription.xml")
await device.init()  # initialize and fetch services

# Control examples
await device.set_volume(50)              # set volume to 50%
await device.play()                      # play (if paused/stopped)
info = await device.track_info()         # get current track metadata
print(info.get("title"), "by", info.get("artist"))

sources = await device.sources()         # get input sources
print("Sources:", [s["name"] for s in sources])
await device.set_source(0)               # select first source (e.g., "Playlist")

queue = await device.track_info()        # (OpenHome manages queue internally; for full queue listing, another service call would be needed)
```

This is just illustrative – in practice you might use callbacks or Home Assistant's services. But it shows that **virtually all functions you need (playback, volume, source, info)** are accessible via network commands using OpenHome UPnP.

## 3. **No Official REST API (and Workarounds)**

Auralic has not released an official RESTful API documentation for their streamers. Unlike some other audio devices (e.g., **Arylic** or **Linkplay**-based devices which have HTTP APIs for developers), the Auralic Altair doesn't have a documented JSON/HTTP endpoint for third-party control. (Be careful not to confuse **Auralic** with **Arylic** – Arylic's DIY boards have an HTTP API, but that's a different product line entirely.)

**Community Reverse Engineering:** Despite the lack of official REST docs, the good news is we don't really need a proprietary API – the OpenHome interface *is* the API. The community has leveraged this: the Home Assistant integration and `openhomedevice` library (mentioned above) were essentially built by reverse-engineering the UPnP services (using standard UPnP inspection, not a true "hack" since OpenHome specs are public). There hasn't been much need for Wireshark packet captures beyond that, because the device announces its services via SSDP like any UPnP device. For completeness: if one did sniff the Lightning DS app's traffic, one would mostly see UPnP SOAP calls to services like `urn:av-openhome-org:service:Playlist:1` and `...:Product:1` etc., confirming that it's standard OpenHome commands under the hood.

**Potential HTTP Bridge:** If your automation environment *really* needs a REST interface (for example, if you prefer to send HTTP commands from Wirenboard scripts), you could create a small middleware. For instance, you could run a Python Flask server on the Wirenboard that exposes simple REST endpoints (like `/altair/play`, `/altair/volume/50`, etc.), and inside those handlers call the `openhomedevice` methods. This way, your smart home talks REST to your script, and the script translates to UPnP for the Altair. This isn't available off-the-shelf but would be a few dozen lines of code using the library. 

As of now, there are **no known official or unofficial all-in-one REST API packages** specifically for Auralic. The integration is achieved through the methods above. The **OpenHome approach is robust and supported**, even if it requires a bit of initial setup to use.

## 4. **Other Integration Notes and Community Projects**

- **IR Control (Smart-IR):** The Altair (especially newer models or the G series) have an IR remote (Auralic RC-1) and even a "Smart-IR" learning feature to map functions to any remote. In a pinch, one could use an IR blaster from the Wirenboard to send commands (play/pause, volume up/down, etc.). However, this is a one-way control and won't give you feedback or metadata. Given that network control is available, IR is usually unnecessary except for power on/off in some cases. (OpenHome does have a `setStandby()` function to put the unit in standby or wake it, so even power can be managed via network.)

- **Roon API:** If you use Roon in your home, the Altair as a RoonReady device can be controlled via Roon. Roon's API (Node.js or Python) would let you play music on the Altair, adjust volume, and get track info – but this is going through Roon's system rather than direct to the Altair. It adds complexity (you need Roon Core running and your automation talking to Roon Core). This approach is typically only useful if you *already* use Roon for multi-room audio and want your smart home to interface with that. For most users who just want to integrate the Altair, using OpenHome directly is more straightforward.

- **Logitech Media Server (LMS) / Others:** Some community discussions have revolved around using LMS or other servers with OpenHome renderers. For example, the **UPnP Bridge** plugin for LMS can make the Altair appear as a Squeezebox player. Similarly, Audirvana (a music player) users have tried to use the Altair, but ran into the incompatibility of Audirvana's UPnP with OpenHome. The consensus was that a true OpenHome controller or a bridge is needed since Auralic doesn't "speak" plain UPnP AV transport in the same way. These are niche use-cases; in a Wirenboard home setup, you likely wouldn't go this route, but it's good to know the Altair might not respond to every generic UPnP controller unless it supports OpenHome or uses the device's "compatibility" mode (if any).

- **Firmware and Updates:** Auralic provides frequent firmware updates (Lightning DS updates, etc.), but these typically don't remove OpenHome functionality – it's core to the platform. If anything, they **added features** like new streaming services (Amazon Music, etc.) and improvements. Should you see any API changes (unlikely), the community usually adapts (Home Assistant updates its integration if needed – e.g., it was introduced in HA 0.39 and improved over time ([Linn / OpenHome - Home Assistant](https://www.home-assistant.io/integrations/openhome/#:~:text=Linn%20%2F%20OpenHome)) ([Version 3.1 - AURALIC LIMITED](https://support.auralic.com/hc/en-us/articles/222833848-Version-3-1#:~:text=Version%203.1%20,API%20by%20using%20HTTPS%20connection))).

- **Comparison of Approaches:** In summary, here's how the approaches stack up:

  - *Using OpenHome (UPnP) via libraries or HA:* **Pros:** Full control and feedback, supports all Altair features (queue, streaming services, local files), real-time metadata, two-way communication. **Cons:** Requires a bit of coding or setup (but existing libraries ease this). Uses SOAP/XML under the hood (abstracted by libraries).  
  - *Using Roon or Spotify Connect APIs:* **Pros:** Can leverage high-level APIs (Roon's rich library management or Spotify's web API) and multi-room features. **Cons:** Limited to those ecosystems; you *must* use Roon or Spotify app for content selection. Doesn't cover all inputs (e.g., can't switch the Altair to a different source via Spotify API). Adds extra components to your system.  
  - *Using AirPlay:* **Pros:** Simple – Altair appears as an AirPlay speaker. You could script AirPlay playback (e.g., with `ffmpeg` or shairport). **Cons:** No metadata feedback to your automation (AirPlay is mostly one-way), lower audio quality for high-res content, and cannot control Altair's other functions (like toggling a DSP filter or browsing its library).  
  - *Using IR (Smart-IR):* **Pros:** Doesn't require network setup; can map any IR remote code to Altair functions. **Cons:** One-way (no feedback), need line-of-sight or IR blasters in each zone, and limited command set. Not useful for metadata or automation logic based on track info.  

In practice, **leveraging the OpenHome network API is the most comprehensive solution** for a smart home. It's effectively the "unofficial API" for Auralic devices, used by many in the community. For instance, Auralic owners who are Android or PC users often use BubbleUPnP or Linn Kazoo as their controller instead of Lightning DS – your automation can act like one of those controllers.

## 5. **Practical Example and Resources**

- **Home Assistant Example:** One user reported that after adding the Linn/OpenHome integration, they could control their Auralic device in Home Assistant – play/pause worked, track skipping and volume worked, and the current track info was visible. Initially, they noted the lack of a "play_media" feature to start a specific track/URL, but a contributor responded and added that feature to Home Assistant. This demonstrates how community support has filled gaps. Now, as shown in Home Assistant's docs, you can directly call `media_player.play_media` with a URL and the Altair will start playing it ([Linn / OpenHome - Home Assistant](https://www.home-assistant.io/integrations/openhome/#:~:text=actions%3A%20,media_content_type%3A%20music)). *Tip:* If you have Home Assistant running or can run it in Docker on Wirenboard, you might integrate through it; otherwise, replicate what it does using the library.

- **GitHub Repos:** 
  - The **`openhomedevice`** library (Python) – highly recommended if you plan to script in Python. It's open source (MIT license) and supports all essential OpenHome services. 
  - Auralic's own GitHub has low-level code (e.g., a "Lightning-ohNet" C++ repo), but that's their internal firmware stack, not directly useful for integration except as reference. 
  - If you are interested in building something in C/C++, the **OpenHome organization** provides the ohNet SDK and sample code on openhome.org ([What is OpenHome? – AURALIC LIMITED](https://support.auralic.com/hc/en-us/articles/206073458-What-is-OpenHome#:~:text=OpenHome%20Networking%20,Windows%2C%20Mac%2C%20iOS%20and%20Android)) ([What is OpenHome? – AURALIC LIMITED](https://support.auralic.com/hc/en-us/articles/206073458-What-is-OpenHome#:~:text=For%20more%20information%20about%20OpenHome%2C,please%20refer%20to%20the%20following%C2%A0link)). But using a pre-made library or HA integration is much easier.

- **Documentation:** Since Auralic doesn't have an official API doc for Lightning, you can refer to **Linn's OpenHome documentation** for technical details. The OpenHome standard defines services like `Playlist`, `Radio`, `Product`, `Volume`, etc., which Auralic implements similarly. For example, the **OpenHome "Product" service** will list the sources (inputs) and allow source switching; the **"Volume" service** handles volume/mute; **"Info" service** gives track metadata. Linn's docs or the openhomedevice code can serve as documentation for these. 

- **Community Forums:** Auralic's own forums or places like AudiophileStyle have discussions, though mostly from a user perspective. There isn't much in terms of published reverse-engineering projects specific to Auralic (likely because the open standard sufficed). If you search forums, you'll mostly find that the advice for integrating without iOS is to use BubbleUPnP or similar (i.e., use OpenHome control). 

To conclude, **integrating Auralic Altair into Wirenboard** involves using the *network control capabilities built into the device via OpenHome*. While there's no out-of-the-box REST endpoint, the rich OpenHome UPnP API can be accessed using existing tools. Many have effectively treated their Auralic like any other UPnP media player in home automation systems. By using these methods, you can achieve: power on/off (standby), input selection (e.g., switch to a different source like AirPlay vs the internal streamer), transport controls (for any playing source, whether local files or Tidal, etc.), volume adjustment, and real-time metadata retrieval for display or logic. 

**References:**

- Auralic documentation noting OpenHome control compatibility.  
- Stereophile specs confirming Altair is OpenHome and UPnP AV compliant.  
- Home Assistant integration docs for Linn/OpenHome, illustrating control and metadata features ([Linn / OpenHome - Home Assistant](https://www.home-assistant.io/integrations/openhome/#:~:text=The%20Linn%20%2F%20OpenHome%20integration,see%20the%20current%20playing%20item)) ([Linn / OpenHome - Home Assistant](https://www.home-assistant.io/integrations/openhome/#:~:text=actions%3A%20,media_content_type%3A%20music)).  
- OpenHome Python library README showing available control methods (play, pause, volume, source, track_info, etc.).  
- Auralic support forum article "Non-iOS device solutions" emphasizing third-party OpenHome apps for control.  
- Community discussion (Home Assistant forum) about adding play_media and controlling OpenHome devices.  

# Add after the other device state models like LgTvState, EmotivaXMC2State, etc.
class AuralicDeviceState(BaseDeviceState):
    """Schema for Auralic device state."""
    power: str = "unknown"  # on/off/unknown
    volume: int = 0
    mute: bool = False
    source: Optional[str] = None
    connected: bool = False
    ip_address: Optional[str] = None
    track_title: Optional[str] = None
    track_artist: Optional[str] = None
    track_album: Optional[str] = None
    transport_state: Optional[str] = None  # Playing, Paused, Stopped, Buffering, etc.

