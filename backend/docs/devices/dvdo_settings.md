### Cable & signal chain first

| Step                                                                                                                     | Why                                                                                                                                                                                                                                                | Do this on the Edge Green                                                                                                     |
| ------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| Use **composite (yellow RCA)** from the player *unless* you own a late-elite Pioneer/HLD with a high-quality Y/C filter. | Most LD decks have mediocre S-Video output; the Edge’s own **3-D comb filter** is usually better at separating chroma/luma than the player’s filter. Forums consistently report composite looking cleaner on modern scalers. ([forum.lddb.com][1]) | Connect LD composite → “Video 1” (or any CVBS jack). If you want to check, A/B composite vs S-Video and keep the cleaner one. |

Add a **line-TBC** only if you see vertical jitter (rare with LD; common with VHS).

---

## Best Edge-Green menu settings for LaserDisc

(Everything is per-input, so create *one preset for “Movies”* and *one for “Concerts/NTSC-video”*).

| Menu path                                                      | Movies (24 fps telecined)                                                                                   | Concerts, music videos (native 60 i) | Comment                                                                                                                            |
| -------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- | ------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------- |
| **Input Adjust → De-interlacing mode**                         | **Film** (or *Forced 3 : 2* if the disc is pure film)                                                       | **Video** (or *Auto*)                | Film mode lets the ABT2010 reconstruct perfect 24 p; Video mode avoids cadence hunting on live material. ([soundandvision.com][2]) |
| **Settings → Advanced → 1 : 1 Frame Rate**<br>(firmware v1.1+) | **On**                                                                                                      | Off                                  | Passes 24 Hz straight to the TV for judder-free playback. Your set must accept 24 p. ([media.onecall.com][3])                      |
| **Settings → Output Format**                                   | 1080p 24 Hz (if 1 : 1 FR on) or 1080p 60 Hz                                                                 | 1080p 60 Hz                          | Edge tops out at 1080p; modern 4 K TVs handle the 2× upscale cleanly.                                                              |
| **Advanced → Output Color Space**                              | YCbCr 4 : 4 : 4                                                                                             | same                                 | Keeps full chroma resolution; “Auto” is OK if unsure. ([media.onecall.com][3])                                                     |
| **Advanced → Output Colorimetry**                              | Auto                                                                                                        | Auto                                 | Edge switches BT.601 for SD automatically.                                                                                         |
| **Picture Controls**                                           | <ul><li>Mosquito NR = **1–2**</li><li>Detail Enhancement = **1**</li><li>Edge Enhancement = **0**</li></ul> | Same                                 | Keeps tape noise in check without smearing fine detail. Manual & fw 1.1 doubled NR granularity.                                    |
| **Game Mode**                                                  | Off                                                                                                         | Off                                  | Disables low-lag “bob” so you get full motion-adaptive processing. ([videogameperfection.com][4])                                  |
| **Aspect Ratio**                                               | “Source” (pillar-box 4 : 3)<br>Use **Zoom 2** for letter-boxed Scope films                                  | “Source”                             | Edge remembers aspect/zoom per input, so you can map the ZOOM button to toggle.                                                    |
| **Audio → AV LipSync**                                         | Delay ≈ 40–60 ms                                                                                            | same                                 | Tilts audio to match \~1-frame video latency when Game Mode is off.                                                                |

*All other items—Underscan = 0, Input/Output Levels = Auto—may stay at factory defaults unless your TV expects PC-levels.*

---

### Quick setup walk-through

1. **Run the Display Wizard** and pick *Auto*; Edge will handshake the TV’s EDID.
2. Enter **Input Wizard → Video 1 → Rename** → “LaserDisc”.
3. In **De-interlace** choose *Film* → press **OK** to store.
4. Go to **Settings → Advanced** and enable *1 : 1 Frame Rate* (for films) and set *Output Color Space* to **YCbCr 4 : 4 : 4**.
5. Open **Picture Controls** → set Mosquito NR = 2, Detail = 1, Edge = 0.
6. Press the **Info** button → verify incoming 480 i 59.94 Hz and outgoing 1080 p 24 Hz (or 60 Hz).
7. Save the profile. Create a second profile with *Video mode* and 1080 p 60 Hz for concert discs.

---

### Why these choices work

* **Film / Forced 3 : 2** engages the ABT2010’s five-field cadence lock, eliminating “combing” and giving you original 24 p frames. ([soundandvision.com][2])
* **Video mode** skips cadence detection completely, so fast interlaced camera moves in concerts stay crisp.
* 1080 p → 2160 p is a simple 2× integer scale in both axes; your TV’s scaler does not introduce ringing.
* The Edge’s 3-D comb plus moderate Mosquito NR suppresses dot-crawl and rainbow streaks that plague composite LD, without softening the picture.&#x20;
* Keeping Game Mode off preserves full motion-adaptive interpolation (lag is irrelevant for movies). ([videogameperfection.com][4])

---

### Final touches

* **Calibrate once** with the Edge’s built-in 35 test patterns (Settings → Advanced → Test Patterns) to set TV brightness/contrast. ([media.onecall.com][3])
* If the TV occasionally loses sync when you swap 24 Hz ↔ 60 Hz, remember the **GUIDE** button enters “Safe Mode” and forces a picture so you can recover. ([media.onecall.com][3])
* For letter-boxed widescreen discs, program a remote macro that sends *ZOOM 2* on the Edge and *Zoom Off* on the TV—one button fixes the bars.

With those tweaks the Edge Green wrings every last line of detail from your LDs, hands the TV a rock-solid 1080 p signal, and your 4 K panel does the low-effort up-step to full UHD. Enjoy the analog glow without the artifacts!

[1]: https://forum.lddb.com/viewtopic.php?f=30&t=5344&utm_source=chatgpt.com "LaserDisc Database • View topic - S-Video or Composite?"
[2]: https://www.soundandvision.com/content/dvdo-edge-video-processor-setup-tests "DVDO Edge Video Processor Setup & Tests | Sound & Vision"
[3]: https://media.onecall.com/Image_Products/DVDO/EDGE_Manual_Supplement_v1.1.pdf "new in v1.1.cwk (WP)"
[4]: https://videogameperfection.com/2011/10/26/dvdo-edge-faq/?utm_source=chatgpt.com "DVDO Edge – A rough guide/FAQ - VideoGamePerfection.com"
