# Zappiti Neo Driver — Control Contract & Implementation Spec

**Status:** living document. Part I (device control) fully reverse-engineered and verified. Part II
(catalog & indexing) designed; the formerly deferred host/DB-crossing choices were **resolved
2026-07-07** — browser-native indexer, bridge-owned catalog (§13).

**Audience:** an implementing agent (Claude Code) building a Zappiti driver inside the
`locveil-bridge` system. This is the authoritative hardware-facing contract.

**Conventions**
- ✅ = tested live against the actual device. Anything not ✅ is inferred; every inferred item is
  listed in §8 (Open items). Proven ∪ open = the whole surface.
- `<DEVICE_IP>` and other `<...>` are config placeholders; concrete values for this install are in §7.

**Document structure (MECE).** Each concern lives in exactly one section.
*Part I — device control:* §1 what the device is · §2 how to connect · §3 commands you send · §4 how
to build the `media_url` argument · §5 state you read back · §6 file metadata obtained out-of-band ·
§7 this install's values · §8 open items (unverified device behavior).
*Part II — catalog & indexing:* §9 role & boundary · §10 the indexing pipeline (incl. how parsing
runs) · §11 source model · §12 SQLite schema · §13 resolved design decisions & open items · §14 repo reuse &
retirement.

---

# PART I — Device control contract

## 1. Device identity

- Sold as **Zappiti Player Neo**; underneath the skin it is a **Dune HD** player (Realtek
  RTD1619DR, Android 9, Dune shell package `com.dunehd.shell`).
- Zappiti the company is defunct (liquidated Oct 2023) and its cloud is dead. **The driver depends
  on nothing from Zappiti** — only on the **Dune HD IP Control** HTTP API, which runs locally in the
  box and is fully alive.
- This unit: `product_id=zap014`, `firmware_version=221103_1928_r17`, IP Control `protocol_version=6`.

## 2. Connecting to the device

Transport-level facts only (what a command *is* carried over). What to send is §3; what comes back is §5.

- **Single endpoint:** `GET http://<DEVICE_IP>/cgi-bin/do?cmd=<CMD>&<params>`
- **Port:** `80`. (ATV-certified Dune models use `11080`; this box uses `80`.) ✅
- **Auth:** none. No token, no login, no per-client authorization — any LAN host that can reach
  port 80 controls the box. ✅
- **No ADB at runtime.** ADB / developer mode were *bench tools* for discovery only (§4). The
  runtime driver needs **only HTTP to port 80**. Do not build ADB into the service.
- **Response body:** XML — `<command_result>` with `<param name="..." value="..."/>` rows (§5).
- **Encoding:** `media_url` values contain spaces, commas, `/` and `:`. URL-encode the whole
  `media_url` value as one query param. Bench reference: `curl -s -G "http://<DEVICE_IP>/cgi-bin/do"
  --data-urlencode "cmd=..." --data-urlencode "media_url=..."`.

## 3. Commands (the send side)

All commands are `cmd=<name>` on the §2 endpoint. Grouped by function; each command documented once.

### 3.0 Capability → command index (navigation only; specs below)
| I want to… | cmd | § |
|---|---|---|
| play / resume a title | `start_file_playback` (+dvd/bluray/launch_media_url) | 3.1 |
| pause / play / FF / RW | `set_playback_state` (`speed`) | 3.2 |
| seek / jump to chapter | `set_playback_state` (`position`) | 3.2 |
| choose audio track | `set_playback_state` (`audio_track`) | 3.2 |
| choose subtitle track | `set_playback_state` (`subtitles_track`) | 3.2 |
| stop | `black_screen` / `main_screen` / `standby` | 3.3 |
| power off | `standby` | 3.3 |
| power on / wake | `main_screen` | 3.3 |
| navigate a DVD/BD menu | `dvd_navigation` | 3.4 |
| anything without an API command | `ir_code` | 3.5 |
| read current state | `status` | §5 |

### 3.1 Launch playback
| cmd | Purpose |
|---|---|
| `start_file_playback` | Plain media file (MKV/MP4/TS/remux). ✅ |
| `start_dvd_playback` | DVD-Video folder or ISO. |
| `start_bluray_playback` | Blu-ray folder or ISO. |
| `launch_media_url` | Autodetect kind (file/DVD/BD) from the media_url. |
| `start_playlist_playback` | `.m3u` or a folder as playlist; add `&start_index=N`. |

**Params** (append to a launch cmd):
| param | meaning |
|---|---|
| `media_url` | **required** — construction in §4. |
| `position` | initial position, **seconds** — this is "resume". |
| `speed` | initial speed (§3.2 scale); `0` = start paused. |
| `black_screen` | `0\|1` start with video+OSD hidden (resettable). Not for Blu-ray. |
| `hide_osd` | `0\|1` start with OSD hidden (resettable). Not for Blu-ray. |
| `action_on_finish` | `exit` \| `restart_playback`. |
| `timeout` | command timeout, seconds (default 20, min 1). |

> Success of a launch is **not** signalled by the HTTP response — it must be verified by polling
> `status`. See §5.2. This is mandatory.

### 3.2 Playback control — `cmd=set_playback_state`
One command; params grouped by function.

*Transport:*
| param | values / meaning |
|---|---|
| `speed` | `-1024,-512,-256,-128,-64,0,64,128,256,512,1024`. **`0`=pause, `256`=1× play**, `512/1024`=FF, negatives=RW, `64`=¼×. ✅ |
| `position` | seek to absolute **seconds**. ✅ (also the mechanism for chapter jump — §6.6) |
| `skip_frames` | `-1\|1` prev/next **keyframe**; only while paused (`speed=0`); MKV & DVD only. |

*Track selection:*
| param | values / meaning |
|---|---|
| `audio_track` | select audio track by **index N**. ✅ confirmed (protocol 6). |
| `subtitles_track` | select subtitle by **index N**; `-1` = off. (inferred by symmetry — §8) |

> "Index N" is the box's own track index, which may differ from your stored ffprobe order — bind by
> lang+codec, not by position. See §6.5.

*OSD / video / audio output:*
| param | values / meaning |
|---|---|
| `hide_osd` | `0\|1`. Some `set_playback_state` calls raise the OSD; chain `hide_osd=1` to suppress. |
| `black_screen` | `0\|1`. |
| `volume` / `mute` | 0–100 / `0\|1`. **Don't wire in this install** — audio authority is the AV processor/amp (§7). |
| `video_enabled`,`video_zoom`,`video_fullscreen`,`video_x/y/width/height` | video window (protocol 2+). |

### 3.3 Stop & power — state commands
| cmd | Effect |
|---|---|
| `standby` | Stop playback, enter **standby**. This is "power off". ✅ |
| `main_screen` | Stop playback, go to main menu. Doubles as "power on / wake". ✅ |
| `black_screen` | Stop playback, go to global black-screen state. |

**Power model (verified):** standby is **soft** — HTTP server and network stay up; `status` still
answers with `player_state=standby`. ✅ So power-off = `standby`, power-on = `main_screen` (or fire
a launch straight at the standby box — confirm clean wake, §8). **No Wake-on-LAN or IR blaster
needed for power.** `standby` is a reachable state, not "offline" (see the state machine, §5.3).

### 3.4 DVD/BD menu navigation — `cmd=dvd_navigation`
`&action=LEFT|RIGHT|UP|DOWN|ENTER`. For menu-driven disc playback (also a fallback for chapter
navigation on menu-based ISOs — §6.6).

### 3.5 Escape hatch — emulate a remote button — `cmd=ir_code`
`&ir_code=<4-byte NEC code, byte-reversed>` (e.g. RC "1" `00 BF 0B F4` → `F40BBF00`). Injects a
remote keypress **over HTTP** — no physical blaster, no IR in the air. Use for anything lacking a
first-class command. NEC code list: `dune-hd.com/support/rc`.
**A physical IR blaster is only ever needed for OTHER gear (TV/AVR), never the Neo.**

## 4. Building the `media_url` argument

The launch commands (§3.1) take a `media_url` with a **scheme**. The box does **not** accept raw
internal paths (`/tmp/mnt/...`) through the API. The driver turns an indexed file into scheme + relpath.

### 4.1 Schemes
| Source type | media_url syntax | Status |
|---|---|---|
| **NFS** | `nfs://<host>:/<export>:/<relpath>` (note the `:/` between export and path) | ✅ tested |
| **SMB** | `smb://[<user>[:<pass>]@]<host>/<share>/<relpath>` | inferred (NFS family works) — §8 |
| **Local HDD** | `storage_name://<name>/<relpath>`, `<name>` = folder under `/tmp/mnt/storage/` | ✅ tested |
| HTTP / UPnP | `http://<host>[:<port>]/<path>` | — |

> **Do NOT use `storage_label://` on this box.** It returned `ok` but silently failed — the drive's
> Dune *name* (`HD-3TB-Green`) is what `storage_name://` keys on, and the label differs. ✅ (learned
> the hard way — the exact case that proves §5.2). `storage_uuid://` is theoretically most robust but
> the UUID needs root to read (`blkid` blocked under unprivileged adb); `storage_name://` is stable
> for an internal drive and is the confirmed choice.

### 4.2 Deriving `<relpath>` — the mountpoint-stripping rule
The box reports the current file as an internal path in `status.playback_url`:
- `/tmp/mnt/network/<N>/<relpath>` → network source N
- `/tmp/mnt/storage/<name>/<relpath>` → local storage `<name>`

`<relpath>` is everything **after** the mountpoint. Each mountpoint maps to one source (scheme +
host/export/share, or storage name). The driver stores that mapping and templates
`scheme://.../<relpath>`. (Formalizing this mapping into a source table is the next document section.)

### 4.3 Worked examples (verbatim — these actually played) ✅
```
# NFS — Synology export /volume1/Movies, mounted on box at /tmp/mnt/network/0
cmd=start_file_playback
media_url=nfs://192.168.110.219:/volume1/Movies:/04 - Horror, Giallo, Grindhouse/Dario Argento/Cat.o.Nine.Tails.1971.1080p.Bluray.AVC.Remux.mkv

# Local internal HDD
cmd=start_file_playback
media_url=storage_name://HD-3TB-Green/Movies/Zhizn.prekrasna.1997.BDRip.mkv
```

### 4.4 Bench discovery of the mount→source mapping (ADB, one-time, NOT runtime)
```
adb shell cat /proc/mounts | grep -iE '/tmp/mnt/(network|storage)'
```
Reveals, per mountpoint, the real backing `host:/export` (NFS) or `//host/share` (SMB). Run once
from a laptop; transcribe into source config. The Wirenboard never does this.

## 5. Reading device state — `cmd=status`

The single read model. Poll it for now-playing, resume position, current tracks, power state, and
launch verification.

### 5.1 Fields
| field | meaning |
|---|---|
| `command_status` | `ok\|failed\|timeout` — **parse-level only** (see 5.2). |
| `player_state` | `file_playback\|dvd_playback\|bluray_playback\|black_screen\|standby\|navigator\|osd_screen`. |
| `playback_state` | `playing\|paused\|stopped\|initializing`. |
| `playback_url` | internal path of current media; **empty = nothing playing / launch failed**. |
| `playback_position` | current position, **seconds**. |
| `playback_duration` | total seconds (`-1`/`0` if unknown). |
| `playback_speed` | current speed (§3.2 scale). |
| `playback_is_buffering` | `0\|1`. |
| `playback_current_bitrate` | bps. |
| `audio_track` | index of **currently selected** audio track. |
| `subtitles_track` | index of current subtitle (`-1` = none). |
| `playback_volume` / `playback_mute` | 0–100 / `0\|1`. |
| `playback_video_width` / `_height` | current decoded dimensions. |
| `playback_caption` | OSD title text, e.g. `"...mkv (4 of 21)"` (position within folder). |
| `playback_extra_caption` | OSD extra, e.g. `"Chapter 4"` or a timecode. |
| `error_kind` / `error_description` | present only when `command_status=failed`. |

**Track enumeration is playback-only.** While a file plays, `status` also emits indexed rows
`audio_track.<N>.lang\|pid\|codec\|type` and `subtitles_track.<N>.lang\|pid\|codec\|type`. **These
do not exist when the box is idle** — you cannot ask a stopped box what a file contains. This is the
reason §6 exists (pre-parse) and the input to the §6.5 reconciliation.

### 5.2 Launch success verification (mandatory) ⚠️
`command_status=ok` means **"the command parsed"**, NOT "playback started." An unresolvable
`media_url` still returns `ok`, then the box drops to the folder screen.

**Never trust `command_status` for launch success. Fire-then-poll instead:**
1. Send the `start_*` command (§3.1).
2. Poll `cmd=status` every ~300–500 ms.
3. **Success** as soon as `playback_url` is non-empty (`playback_state` → `initializing`→`playing`).
4. **Failure** if `playback_url` is still empty after a ~3–5 s timeout.

The immediate launch response always has `playback_url=""` / `playback_state=initializing` even on
success; the URL populates ~1 s later — hence the poll, not a single check.

### 5.3 Derived state machine
From `status`, four states — only the last is an error:
- `standby` — powered down but **reachable** (HTTP answers). Wake via `main_screen`.
- `navigator` — idle at the menu.
- `file_playback` (± transient `osd_screen`) — watching.
- **timeout / connection refused** — the only true "unreachable" (unplugged/crashed).

Build the power button and now-playing widget on this. A sleeping box is not offline.

**Polling policy (driver requirement):** the 300–500 ms cadence is the *launch burst* only (§5.2).
Steady-state, poll `status` at a slow cadence (~5–10 s) with **transition-only logging** — a poll is
not an event; log state *changes* at INFO, never each cycle (lesson of the Auralic reconnect churn).

## 6. File metadata (out-of-band, from the files — not the box)

The box enumerates tracks only during playback (§5.1) and never exposes chapter *titles* (only a
generic "Chapter N" caption). So all browse-time content — track lists, chapter names, forced-sub
flags, filtering inputs — must be extracted from the files at index time. Two authorities, joined at
play time.

### 6.1 The two authorities
- **Pre-parsed (stored) — authoritative for CONTENT:** track lists and chapter list (names,
  languages, codecs, flags, timestamps). Extracted at index time (§10.2). Drives detail pages,
  filtering, chapter menus.
- **Live from `status` — authoritative for STATE:** currently selected `audio_track` /
  `subtitles_track`, `playback_position`, power state. Never stored.

### 6.2 Extraction reference
The **reference semantics** for what must be extracted are ffprobe's — one invocation yields streams
(audio+subtitle+video), chapters, and container/duration, the whole record per file:
```
ffprobe -v quiet -print_format json -show_streams -show_chapters -show_format "<file>"
```
The §6.3 field tables are keyed to this output. The *actual* extraction runs in the browser via
mediainfo.js (§10.2), mapped onto these semantics through the §10.2 parity gate; ffprobe remains the
bench-side oracle for that mapping. Resolution/HDR/codec/runtime for the catalog come from the same
pass.

### 6.3 Stored record schemas

**Audio track** (from `streams[]` where `codec_type=audio`):
| field | ffprobe source | notes |
|---|---|---|
| `index` | `index` | stream order; **not** necessarily the box's select index (§6.5). |
| `language` | `tags.language` | ISO 639-2 (`eng`,`rus`); absent → `und`. |
| `title` | `tags.title` | human label when present (e.g. "Director's Commentary"). |
| `codec` | `codec_name` | `dts`,`ac3`,`truehd`,`eac3`,`aac`,`flac`… |
| `profile` | `profile` | e.g. `DTS-HD MA` vs `DTS-HD HRA` — distinguishes lossless from lossy. |
| `channels` | `channels` | e.g. `6`. |
| `channel_layout` | `channel_layout` | e.g. `5.1(side)`. |
| `default` | `disposition.default` | store as **bool**. |
| `forced` | `disposition.forced` | store as **bool**. |

**Subtitle track** (from `streams[]` where `codec_type=subtitle`):
| field | ffprobe source | notes |
|---|---|---|
| `index` | `index` | as above. |
| `language` | `tags.language` | absent → `und`. |
| `title` | `tags.title` | human label when present. |
| `codec` | `codec_name` | `subrip`,`ass` (text) vs `hdmv_pgs_subtitle`,`dvd_subtitle` (image). |
| `forced` | `disposition.forced` | **bool** — foreign-dialogue-only vs full subs. |
| `default` | `disposition.default` | **bool**. |
| `hearing_impaired` | `disposition.hearing_impaired` | **bool** — SDH; useful filter. |

**Chapter** (from `chapters[]`):
| field | ffprobe source | notes |
|---|---|---|
| `ordinal` | array position | 1-based for display. |
| `start_time` | `start_time` | **seconds** (float) — this is what you feed to `position=`. |
| `end_time` | `end_time` | seconds. |
| `title` | `tags.title` | **often absent** → fall back to `Chapter {ordinal}` at display. |

### 6.4 Display vs. identity rule
- **`title` is the label; `language`+`codec`+`profile` is the identity.**
- Display `title` when present; else compose e.g. `{language} {profile or codec} {channel_layout}`.
- Store `forced` / `default` / `hearing_impaired` as **real booleans** (they are filter and
  auto-select inputs — auto-pick the forced sub for a foreign film, default audio on launch).

### 6.5 Live reconciliation (join stored ↔ box)
Do **not** assume stored ffprobe index N == the box's `audio_track=N`. Usually they agree (both
stream-order) but it is not guaranteed — Dune may filter/reorder.

Pattern: **label** buttons from stored metadata; when playback starts, read the box's own
enumeration once from `status` and **match by language+codec** (not title, not index) to bind e.g.
"the ENG DTS-HD button" to whatever index the box assigned. **Set with the box's index; label with
your metadata.**

### 6.6 Chapters — list vs. select
- **List:** stored ffprobe chapters (§6.3) — names + timestamps.
- **Select:** `set_playback_state&position=<chapter start_time>` (§3.2). Richer than the remote's
  blind +/−.
- **Menu-based DVD/BD ISOs:** position-seek is unreliable; fall back to `dvd_navigation` (§3.4) or
  `ir_code` (§3.5).

## 7. This install (concrete values)

Lift these into config; everything else in the document is device-general.
| Thing | Value |
|---|---|
| Device IP | `192.168.110.178` — DHCP reservation pinned on the router ✅ |
| Runtime host | Wirenboard 7 controller — HTTP-only to port 80 |
| NAS | Synology `192.168.110.219`, NFS v3 |
| Movies export | `/volume1/Movies` → box mountpoint `/tmp/mnt/network/0` |
| Further NFS exports | **several more to mount** — enumerate at the bench (§4.4) and transcribe into §11 sources, one row each |
| Internal HDD | Dune storage name `HD-3TB-Green` → `/tmp/mnt/storage/HD-3TB-Green` |
| product_id / firmware / protocol | `zap014` / `221103_1928_r17` / `6` |

**Bridge integration impact** (what building this driver ripples into):
- Replaces the existing `video` device (WirenboardIRDevice, 15 Broadlink ROM codes) — the IR path for
  the Neo retires entirely; even remote-key fallbacks go over HTTP (§3.5).
- Power becomes **discrete** (`standby`/`main_screen`) — the current power-toggle special-casing in the
  configs goes away; the reconciler gets honest state instead of optimism.
- Device + capability configs and the `movie_zappiti` scenario roles change; the canonical catalog
  golden changes with them → the voice repo must re-pin `contracts/`.
- A status-reporting Neo makes the topology's 5 s `processor.input → video.power` delay upgradeable to
  a real feedback gate (the SCN-10 mechanism) — the HDMI-loss quirk gets an evidence-based guard.

## 8. Open items (inferred, not yet verified)

- [ ] **IP Control persistence across a full power-cycle.** Answers from cold today and is a
  persistent setting, but the whole architecture rests on port 80 always being up — do one
  power-cycle test before committing. (The driver uses no ADB, so TCP-ADB's reboot fragility is
  irrelevant here.)
- [ ] Cold `start_file_playback` from `standby` wakes cleanly, or `main_screen` must precede it (§3.3).
- [ ] `subtitles_track=N` setter on a subbed title (assumed by symmetry with audio — §3.2).
- [ ] SMB scheme end-to-end (only NFS + local tested; assume parity — §4.1).
- [ ] `/tmp/mnt/network/<N>` mountpoint **ordering stability across reboots** once several network
  shares are mounted (§7) — §4.2's `playback_url`→source mapping depends on it.
- [ ] Chapter/track index reconciliation behavior for DVD/BD ISOs specifically (§6.5–6.6).

---

# PART II — Catalog & indexing

## 9. Catalog role & producer/consumer boundary

The catalog is the browse/search/metadata store that fronts the Part I driver: one row per playable
title, holding editorial metadata, artwork, technical tracks/chapters (§6), and — critically — the
`media_url` needed to launch it (§4). Three roles act on it (resolved 2026-07-07 — rationale in §13):

- **Indexer (producer): the catalog panel in indexing mode, in a desktop browser.** Scans a source as
  mounted on the operator's laptop, probes file headers in-page (mediainfo.js/WASM — §10.2), matches
  against TMDb (§10.3), and POSTs normalized rows to the bridge's ingest API (§10.5). No daemon, no
  container, no ffprobe binary, no ADB — nothing to install anywhere.
- **Bridge (owner + serving layer):** sole writer of the catalog SQLite (§12); templates `media_url`
  at ingest (§10.4); fetches and serves artwork (§10.5); serves browse/search; fires Part I HTTP
  commands using the stored `media_url` and live `status` (§5).
- **Catalog UI (consumer):** a panel on the Zappiti **device page** and the movie **scenario page** in
  the bridge UI — browse/search/detail → launch; the §10.3 match-resolution queue is a view of the
  same panel. Indexing needs a desktop browser (`showDirectoryPicker`); browsing and launching work
  everywhere, iPad included.

**Productization direction.** Zappiti's shutdown orphaned a large user base with dead catalogs; this
architecture is deliberately **zero-install** so it can one day serve them: a web page + the box + a
TMDb key. Keep device-general logic cleanly separated from this-install specifics with that future in
mind.

## 10. Indexing pipeline

Five stages. 10.1–10.3 run **in the browser**, 10.4–10.5 **in the bridge** at ingest. The
acquisition/matching *logic* comes from `github.com/droman42/zappiti_updater`, ported to TypeScript
(the panel is the host — §14).

| # | Stage | In → Out | Runs in | Source |
|---|---|---|---|---|
| 10.1 | Scan | picked folder → candidate files (relpath, title/year guess) | browser | **port** `FilenameParser` (+ `MediaScanner` walk semantics) |
| 10.2 | Probe | file → audio/subtitle/chapter rows + AV facts | browser | **new** (mediainfo.js) |
| 10.3 | Match | title/year → TMDb editorial + artwork refs | browser | **port** TMDb client + `tmdb_url_parser` |
| 10.4 | Template | (source, relpath) → `media_url` | bridge | **new** (§4) |
| 10.5 | Persist | rows → catalog SQLite + artwork fetch | bridge | **new** (ingest API) |

### 10.1 Scan
The operator selects the **source** (a §11 row) and picks its **content root** as mounted on the
laptop (`showDirectoryPicker`; the handle persists in IndexedDB, so a re-scan is one click plus a
permission re-grant). Every source is reachable this way: NAS exports as ordinary laptop mounts, the
internal HDD via the box's own SMB server. Walk the tree; for each video file emit a candidate —
`relpath`, `title_guess`, `year_guess`, `is_tv`/`season`/`episode` — via the ported regex parser
(quality-token stripping, `Title (Year)` and `S##E##` extraction).

**The picked folder MUST be the source content root** (the export/share/storage root), because
**`relpath` is the join key**, defined identically to §4.2: the file's path relative to that root.
The box derives it from `playback_url` (`/tmp/mnt/<mount>/<relpath>`); the indexer derives it from
the walk. They must agree — that identity is what lets §10.4 build a `media_url` the box can resolve.

**Incremental by construction** — "add a movie/season later" is not a special case: drop the files on
the source and re-run the scan. Unchanged files are skipped by fingerprint (§10.2), new ones flow
through, vanished ones are marked missing (§10.5).

### 10.2 Probe — how the parsing is executed
- **Library:** `mediainfo.js` (MediaInfoLib compiled to WASM, ~2.5 MB) — **not** ffmpeg.wasm (25–30 MB,
  wants whole buffers in memory). It takes a `readChunk(size, offset)` callback and *seeks*, reading
  only header regions via `Blob.slice` — a few MB per MKV, including the end-of-file hops Matroska
  needs for SeekHead/Chapters. **No external binary anywhere in the system.**
- **Addressing:** the probe reads the file as the **laptop** sees it (the §10.1 mount) — **not** the
  Dune `media_url`. Same file, two addressings: the indexer reads bytes here; the driver plays via
  `media_url` later.
- **Extraction → schema (§12), same semantics as §6.3:** audio tracks (language, title, codec +
  commercial profile e.g. "DTS-HD Master Audio", channels, layout, default/forced), subtitle tracks
  (+ hearing-impaired), chapters (names + start seconds), container duration, video
  width/height/codec/HDR. Flags stored as booleans.
- **Parity gate (open — §13):** MediaInfo's field naming differs from ffprobe's (§6.3 was specified
  against ffprobe). Before building, probe 1–2 reference MKVs with both and lock a mapping table onto
  the §6.3 semantics. If parity fails, fall back to the rejected container-batch alternative (§13).
- **Robustness:**
  - Unreadable / non-media file → set `media.probe_status=failed`, write no track rows, **continue the
    batch** (never abort on one bad file).
  - Per-file **timeout** (a slow SMB read can hang) → mark failed, move on.
  - **Idempotent:** key on `(source_id, relpath)` with a cheap `fingerprint` (size +
    `File.lastModified`); re-probe only when the fingerprint changes, so re-scans skip unchanged files.
  - **Bounded concurrency:** a small worker pool (I/O-bound); cap it so a scan doesn't saturate the
    share or the box's SMB server.

### 10.3 Match — TMDb-first
TMDb is the primary and only default authority. Its API is CORS-enabled, so matching runs in the page
with the operator's own key (a panel setting, stored locally); the ported locale + English-fallback
logic stays intact. Per file:
- **Confident single hit** → `match_status=auto`; copy editorial fields + artwork refs to `media`.
- **Multiple / low-confidence** → `match_status=ambiguous`; write candidates to `match_queue` for human
  resolution in the panel (paste a TMDb URL/ID → ported `tmdb_url_parser` → fetch by ID).
- **No hit** → `match_status=unmatched` — and the fix is **upstream**: the operator is a TMDb
  contributor, so a missing title gets *added to TMDb*, then re-matched. Unmatched titles remain fully
  playable meanwhile (they have a `media_url` + probe data), just without editorial metadata.
- **OMDb is an optional fallback module**, excluded from the default build — post-release the project
  introduces optional components/modules (in the spirit of the voice project); OMDb is one of them.

The `MovieData`/`TVShowData`/`EpisodeData` shapes map 1:1 onto the §12 editorial columns. **Expect
the ambiguous queue to be non-trivial for transliterated titles** (e.g. `Zhizn.prekrasna.1997` on the
internal HDD) — treat manual resolution as a first-class UI workflow, not a rare fallback.

### 10.4 Template — server-side, at ingest
The browser sends only `(source_id, relpath)`; the **bridge** templates the `media_url` (§4.1) from
its own §11 source row, by `kind`:
- `nfs` → `nfs://<host>:/<export>:/<relpath>`
- `smb` → `smb://<host>/<share>/<relpath>`
- `storage` → `storage_name://<storage_name>/<relpath>`

Stored on the `media` row so nothing ever recomputes it. The browser never constructs device URLs —
source facts live in bridge config only.

### 10.5 Persist — the ingest API (bridge = sole writer)
The browser POSTs to a small bridge endpoint (`/catalog/ingest`, batched): upserts keyed
`(source_id, relpath)` into the catalog SQLite (§12) via the bridge's existing async persistence
layer. Fingerprint-unchanged rows are no-ops. This replaces the repo's `NFOGenerator` entirely — **no
`.nfo`/`.jpg` sidecars are ever written to the NAS** (that sidecar path is exactly what broke the
original Zappiti-Server attempt).

- **Artwork:** the browser sends TMDb `poster_path`/`backdrop_path` refs; the **bridge fetches small
  variants server-side** from the TMDb image CDN (no API key needed): **poster `w500`, fanart `w780`**
  — sized for phone/iPad, ~50–100 MB per 1000 titles — into a **catalog-owned image directory** on
  `/mnt/data` (referenced by `media.poster_ref`/`fanart_ref`), served statically to the panel. Never
  beside the media files.
- **Scan lifecycle & pruning** (the other half of "incremental", §10.1): scan start stamps a session;
  every ingested row refreshes `last_seen_at`; scan finalize marks that source's untouched rows
  **`missing`** — hidden from browse, revived if a later scan sees the `relpath` again. A rename shows
  up as missing + new; acceptable.

## 11. Source model (manual definitions)

Sources are declared **manually** in bridge config (decided earlier) so the runtime stays HTTP-only
with no ADB. One row per NFS export / SMB share / internal storage — this install has **several** NFS
exports (§7). Source facts are discovered once at the bench via `adb … /proc/mounts` (§4.4) and
transcribed here.

`sources` columns: `id`, `kind` (`nfs|smb|storage`), `label`, `host` (null for `storage`), `root` (the
export path / share name / storage name), `enabled`, `last_indexed_at`. (The earlier `index_root`
column is gone — the indexer's path to the bytes is whatever folder the operator picks at scan time,
§10.1.)

The `media_url` scheme is a **function of `kind`** (§10.4), not stored per source. `relpath` (§10.1) is
the file's path under `root`.

## 12. SQLite schema

A **separate `catalog.sqlite`** on `/mnt/data` — never inside `state_store.sqlite` — read and written
**only by the bridge**, through its existing async SQLite persistence layer (plain SQL; no ORM — with
no producer-side database left, the earlier Peewee idea is moot). Schema versioning via
`PRAGMA user_version`.

- **`sources`** — §11.
- **`series`** — one per TV show: `id`, `tmdb_id`, `imdb_id`, `title`, `year`, `status`
  (Ended/Continuing), `plot`, `poster_ref`, `fanart_ref`, `match_status`.
- **`media`** — one per playable title: `id`, `source_id`→`sources`, `relpath`, `kind`
  (`movie|episode`), `media_url`; episode linkage `series_id`→`series`, `season`, `episode` (null for
  movies); filename guesses `title_guess`, `year_guess`; identity `tmdb_id`, `imdb_id`; editorial
  `title` (the episode title for episodes), `year`, `plot`, `director`, `runtime_seconds`; technical
  `container`, `video_width`, `video_height`, `video_codec`, `hdr`; artwork `poster_ref`, `fanart_ref`
  (movies — episodes inherit series artwork); status `match_status`, `probe_status`; `fingerprint`,
  `last_seen_at` (drives the §10.5 `missing` marking); `created_at`, `updated_at`. Unique
  `(source_id, relpath)`.
- **`audio_tracks`** — `media_id`, `stream_index`, `language`, `title`, `codec`, `profile`, `channels`,
  `channel_layout`, `is_default`, `is_forced`.
- **`subtitle_tracks`** — `media_id`, `stream_index`, `language`, `title`, `codec`, `is_forced`,
  `is_default`, `is_hearing_impaired`.
- **`chapters`** — `media_id`, `ordinal`, `start_seconds`, `end_seconds`, `title`.
- **`media_genres`** (movies) / **`series_genres`** (shows) — child tables for filtering.
- **`match_queue`** — `media_id`, `candidates` (JSON list of `{tmdb_id,title,year,score}`), `status`
  (`pending|resolved`).

**Runtime state is NOT in the catalog.** Resume position, now-playing, and power state are volatile —
read live from the box per §5 (or held in a small separate driver table). The catalog stays
read-mostly: ingest writes in bursts, browse reads fast, nothing else touches it.

## 13. Design decisions — resolved 2026-07-07 — and open items

Distinct from §8 (unverified *device* behavior). The two formerly deferred choices were resolved
together, in favor of the **browser-native indexer**:

- **Where the indexer runs → the operator's desktop browser** (the catalog panel in indexing mode,
  §9/§10). Rationale: zero-install (the §9 productization direction), no container or daemon anywhere,
  and the laptop's ordinary mounts already reach every source — including the internal HDD via the
  box's SMB. Consequence accepted: scans are interactive and manual; there is **no scheduled
  re-index** (a non-goal for a hand-grown library). The Synology-container batch (ffprobe + vendored
  Python, WB7 pulls a snapshot) was evaluated and rejected; it remains the documented fallback
  **only** if the §10.2 parity gate fails.
- **How the catalog crosses producer → consumer → it doesn't.** The browser POSTs rows to the bridge
  ingest API (§10.5) and the bridge is the sole SQLite writer. No DB file ever crosses hosts; the
  SQLite-over-NFS locking hazard disappears by construction.
- **Catalog UI home** → a panel on the Zappiti device page + the movie scenario page (§9).
- **Artwork** → small variants (`w500`/`w780`) fetched server-side by the bridge (§10.5).

Open items (Part II — design-level):
- [ ] **mediainfo.js ↔ ffprobe parity bench** (the §10.2 gate) — lock the field-mapping table on 1–2
  reference MKVs before building anything.
- [ ] `is_hearing_impaired` flag coverage in MediaInfoLib against the library's real files.
- [ ] Ingest API auth posture — LAN-open like the rest of the bridge API for the house install;
  revisit with the productization pass.

## 14. Repo reuse & retirement

The indexer host is TypeScript, so reuse means **porting the logic, not vendoring the code** (trust
the code as the porting reference; the README/docs are stale — e.g. version drift 2.0.0 vs 2.3.0). The
repo's tests are the porting oracle for the regex parser.

| Repo module | Disposition |
|---|---|
| `api_client.py` — TMDb side (search, get-by-id, dataclass shapes, locale + English fallback, `choose_localized_image`) | **port to TS** — core of §10.3 |
| `api_client.py` — OMDb side | **port later** as the optional fallback module (§10.3); not in the default build |
| `tmdb_url_parser.py` | **port to TS** — match-queue resolution (§10.3) |
| `media_processor.py` → `FilenameParser` (+ `MediaScanner` walk semantics) | **port to TS** — §10.1; the regexes transfer near-verbatim |
| `media_processor.py` → `ImageDownloader` | **drop** — replaced by the bridge's trivial server-side fetch (§10.5); its size-variant URL scheme (`w500`/`w1280`) confirms the §10.5 sizing approach |
| `media_processor.py` → `NFOGenerator` | **drop** — replaced by §10.5 DB persist |
| `generate_nfo.py` (`NFOGeneratorApp`) + `user_interface.py` | **drop** — interactive CLI; disambiguation moves to the catalog panel |
| `config.py` | **drop** — API-key/locale handling becomes panel settings |

**Retirement:** once the parser + matching logic is ported (with the repo's tests re-expressed in TS
as the acceptance check), `zappiti_updater` is **archived and dropped** — nothing runtime depends on
it. Its lasting contributions are the acquisition/matching logic and the lesson that the NFO-sidecar
output was the dead end.

---

## Appendix A — reference sources
- Dune IP Control overview (commands, params, response syntax):
  `dune-hd.com/resources/support/additional_features/ip_control/dune_ip_control_overview.txt`
- Dune media_url concept (all schemes): `files.dune-hd.com/sdk/doc/html/media_url.html`
- Dune remote-control plugin HTTP API (folder/source enumeration, if ever wanted):
  `dune-hd.com/support/ip_control/remote_control_plugin_http_api.txt`
- NEC IR codes: `dune-hd.com/support/rc`
- mediainfo.js (MediaInfoLib as WASM, chunked-read API): `github.com/buzz/mediainfo.js`
- File System Access API (`showDirectoryPicker`, persistable handles): MDN — desktop Chromium only;
  absent on iPad Safari (hence: index from a desktop browser, browse from anywhere)
