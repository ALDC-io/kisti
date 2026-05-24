# KiSTI Companion App — Architecture & Implementation Plan

**Status:** Planning / architecture review. No code changes proposed in this document — it defines the contract, the Jetson-side server work, and the iOS/CarPlay client work to be done in later sessions.

**Scope:** A **CarPlay-first, map- and track-centric** display for KiSTI. The **road map** and the **live track map** are the primary views on the car screen; **gauges and stats are secondary pages**. A full iPhone companion UI (and a mounted-iPad path) carries the richer dashboard, voice, and session review. All of it connects to the Jetson over the local link defined below.

**Product framing (non-negotiable):** KiSTI is a **vehicle telemetry display, mapping, logging, and session review system for supported vehicle hardware.** It is JARVIS-in-the-car / Enterprise-computer / motorsport-logger in personality and capability. It is **not** a radar-detector app, a police-alert app, a street-racing app, or a public-road performance-coaching app. The App Store listing, in-app copy, and CarPlay category request must all reflect the telemetry/mapping/logging framing. See [§12 Non-goals & framing guardrails](#12-non-goals--framing-guardrails).

**Product direction (important):** Today KiSTI runs on the Jetson in the car and renders to the Kenwood Excelon head unit via the PySide6 UI. This app is the **display/interface pane**, and the intended trajectory is for it to **supersede the Jetson→Excelon output** over time: the Jetson evolves into a (eventually headless) telemetry brain / server / logger, and the iOS surface (iPhone, a mounted iPad, and CarPlay) becomes the **primary display and control interface**. The phases below stand the surface up as a companion first, but every architecture choice here is made so the app can *grow into the primary display* rather than stay a secondary screen — this is why the wire contract anticipates a control channel and video transport, not just read-only telemetry. See [§18 Long-term: the app as primary display](#18-long-term-the-app-as-primary-display).

**Surface priority:** The first-class surface is **CarPlay, map- and track-centric**. The road map and the live track map are the headline views; **gauges and stats are secondary pages** (CarPlay info tabs and the iPhone/iPad dashboard). The roadmap ([§15](#15-phased-roadmap)) sequences the CarPlay map/track surface **ahead of** the gauge dashboard, and the CarPlay design is detailed in [§11](#11-carplay-surface-the-primary-maptrack-view).

---

## 1. System roles (target architecture)

```text
Link G5 Neo 4 ECU ──CAN──┐
AiM GPS09 Pro (GPS/IMU) ──┤
Razor PDM ────────────────┤
OEM ABS / VDC ────────────┤
                          ▼
                  Jetson Orin Nano ── "KiSTI vehicle brain"
                   ├─ CAN listener  → DiffStateBridge (authoritative state)
                   ├─ Voice pipeline (STT → LLM persona → TTS)
                   ├─ DuckDB (session log, laps, tracks, ambient)
                   ├─ Kenwood Excelon 800×480 head-unit UI (PySide6)
                   └─ NEW: net/ telemetry server  ◄── this plan
                          │  (WebSocket live + REST history + mDNS)
                          ▼
         iPhone personal hotspot (shared L2 subnet, Jetson auto-joins)
                          ▼
              ┌───────────────────────────┐
   iPhone app │ full companion UI / map /  │   CarPlay │ simplified,
   (SwiftUI)  │ voice / session review     │  (templates)│ driving-safe map + info
              └───────────────────────────┘
```

- **Jetson** = telemetry server + logger + brain (authoritative). Trends toward **headless** as the display migrates to the app — `main.py --headless` already exists, and `DiffStateBridge`/DuckDB are already decoupled from the UI.
- **iPhone app** = full UI: live dashboard, road map, track map, voice, session review. **On track to become the primary display/control surface** that supersedes the Excelon ([§18](#18-long-term-the-app-as-primary-display)).
- **CarPlay** = the **primary, map/track-centric surface** — road map + live track map as the headline views, gauges/stats as secondary pages, all within Apple's CarPlay template rules ([§11](#11-carplay-surface-the-primary-maptrack-view)). Those rules **cap** dense gauge clusters, so the *gauge-rich* fidelity lives on a mounted iPhone/iPad ([§18](#18-long-term-the-app-as-primary-display)); the map and track views are CarPlay's job.
- **Link ECU** = authoritative vehicle sensor source (via CAN → `DiffState`).
- **Razor PDM** = power/status source (**currently not represented in `DiffState`** — see [§13](#13-gaps-found-in-the-current-codebase)).
- **GPS09 Pro** = position/session source (via CAN → `DiffState.gps_*`, `imu_*`).

---

## 2. Current-state review (grounded in the code)

### 2.1 What exists today

| Layer | Module(s) | Notes |
|-------|-----------|-------|
| Authoritative state | `model/vehicle_state.py` — `DiffState` (~90 fields), `DiffStateBridge` | Thread-safe. CAN thread writes via `update_*()`; UI reads `snapshot()` (a `copy.copy`). Emits `state_changed`. **This is the single source of truth to serialize.** |
| CAN ingest | `can/can_config.py`, `can/kisti_can.py` | Full G5 Neo 4 frame map (DCCD, context, wheel speeds, dynamics, Generic Dash, SI Drive, keypad, GPS09 Pro GPS/IMU). 1 Mbps socketcan. |
| Local store | `data/duckdb_store.py` | `sessions`, `telemetry`, `thermal_state`, `events`, `alerts`, `lap_times`, `tracks`, `track_sectors`, `ambient_conditions`, `summaries`, `service_events`, `voice_latency`. |
| Timing / tracks | `timing/` — `lap_timer.py`, `timing_manager.py`, `track_db.py`, `track_learner.py`, `geo.py` | Circuit + point-to-point lap timing, GPS line-crossing, auto-detect track by GPS, learn unknown tracks, sector splits, delta, predicted/theoretical best. Keeps per-lap `distance_trace`/`time_trace`. |
| Voice | `voice/voice_manager.py` (+ `llm_engine`, `stt_engine`, `tts_engine`, `mic_capture`, `audio_player`, `led_waveform`) | `handle_voice_query(text)`, `set_telemetry(state)`, `speak(text)`. ~86 persona responses, ECU/ambient/timing answer handlers, mode tiers (Intelligent/Sport/Sport Sharp). |
| Head-unit UI | `ui/` — `main_window.py` + mode widgets | Modes: KiSTI, STREET, TRACK, DIFF, VIDEO, (LOG stub), SETTINGS. All QPainter. |
| Cloud sync | `sync/sync_manager.py`, `scripts/sync_to_cloud.py` | **One-way batch** export DuckDB → Parquet → Nextcloud via rclone when WiFi is up. Not a live link. |
| Networking | `scripts/jetson/wifi-hotspot.sh` | Jetson auto-joins the iPhone personal hotspot (priority 10). **Both devices end up on the same hotspot subnet.** |
| Tests | `tests/` | 687 test functions; pure-Python decode/timing/store/voice well covered. |

### 2.2 The two findings that drive this plan

1. **There is no live telemetry egress.** Searching the codebase for `websocket|fastapi|aiohttp|flask|socketio|zeroconf|grpc` returns only the *inbound* whisper.cpp STT HTTP client and the *outbound* rclone/Zeus batch pushes. To feed a live phone UI, the Jetson must gain a **live telemetry server** ([§4](#4-jetson-side-telemetry-server-the-new-net-package)). This is the critical new component.

2. **The existing maps are decorative, not data-driven.** `ui/widgets/map_widget.py` (road) and `ui/widgets/track_map_widget.py` (track) draw a *hardcoded* Laguna-Seca-style illustration with a synthetic moving dot; they ignore real GPS. The real geometry the companion app needs is:
   - **Track outline & sectors:** `tracks` / `track_sectors` DuckDB tables (seeded shape in `data/tracks_seed.json`: `center_lat/lon`, `start_finish` line, `sectors[].line_*`, `length_m`).
   - **Live position & trace:** `DiffState.gps_latitude/longitude/heading/speed` + `LapTimer` per-lap `distance_trace`/`time_trace`.
   So the companion app builds *real* maps from these, and does **not** mirror the Jetson's illustrative QPainter widgets.

---

## 3. Transport decision

The companion needs both **live** (driving) and **review** (after the session) data paths.

| Option | Live? | Verdict |
|--------|-------|---------|
| **A. Direct local link over the iPhone hotspot** (WebSocket + REST on the Jetson; iPhone connects to Jetson's hotspot IP) | Yes, low-latency, works with no internet at a track | **Recommended for live.** The hotspot model already exists; both devices share the subnet. |
| B. Cloud relay (Nextcloud/Zeus) | No (batch only) | **Use for off-network session review/backup**, reusing the existing sync. Not for live. |
| C. BLE / MFi | Marginal | Low bandwidth, MFi friction, no benefit over A on the hotspot. Reject. |

**Recommendation: hybrid.** (A) direct local WebSocket+REST for everything live and at-track; (B) the existing cloud sync for cross-device history when the phone is not on the car's network. The phone app reads cloud history via the same REST shapes ([§5](#5-telemetry-data-contract)) served either by the Jetson (live) or hydrated from synced Parquet/JSON (review).

**Hotspot reachability notes (must be validated early):**
- When iOS shares a personal hotspot, the iPhone is the gateway (typically `172.20.10.1`) and the Jetson gets `172.20.10.x`. The app connects **out** to the Jetson's IP — supported.
- iOS 14+ requires the **Local Network privacy permission** (`NSLocalNetworkUsageDescription`) and declared **Bonjour services** (`NSBonjourServices`) for both mDNS discovery and direct local connections. This must be in the app from day one.
- mDNS over personal hotspot can be unreliable; ship **mDNS discovery + manual IP entry fallback + last-known-IP cache** ([§6.4](#64-discovery--connection)).

---

## 4. Jetson-side telemetry server (the new `net/` package)

Follow existing project conventions: a new top-level package `net/` as a sibling of `sync/`, `timing/`, `voice/`, wired into `main.py` behind a `--no-net` flag that mirrors `--no-sync`, with `start()`/`stop()` lifecycle and graceful-degradation logging.

### 4.1 New files

```text
net/__init__.py
net/telemetry_server.py   # async HTTP + WebSocket server, runs in its own thread
net/serializers.py        # DiffState → wire dict; DuckDB rows → wire dict
net/discovery.py          # mDNS/Bonjour advertisement of _kisti._tcp
tests/test_serializers.py
tests/test_telemetry_server.py
```

Plus additions to `config.py`:

```python
# Companion telemetry server
NET_ENABLED = True
NET_BIND_ADDR = "0.0.0.0"      # reachable on the hotspot subnet
NET_PORT = 8765
NET_BROADCAST_HZ = 15          # live WebSocket push rate (throttled from 20–50 Hz bridge)
NET_SERVICE_NAME = "KiSTI"     # mDNS instance name
```

### 4.2 Threading model (important)

The Qt event loop owns the main thread. Match the existing pattern (`CanListenerThread`, `sounddevice` capture) and run the server on a **dedicated daemon thread with its own asyncio loop**:

- The server thread **polls `bridge.snapshot()`** on a timer at `NET_BROADCAST_HZ` and broadcasts to all connected WebSocket clients. Polling the thread-safe snapshot avoids cross-thread Qt signal hazards and naturally throttles the 20–50 Hz bridge down to ~15 Hz.
- **Library choice:** `aiohttp` (single dependency serving both HTTP REST and WebSocket) is the recommended pick; `websockets` + `http.server` is a lighter fallback. Either must be **optional** — if the import fails, log a warning and continue (same pattern as `python-can`, `duckdb`).

### 4.3 DuckDB access from the server thread (decision needed)

DuckDB is single-writer and its connections are **not** thread-safe. The main app already holds a read-write connection (`db_store._conn`). For REST history reads from the server thread, choose one (recommend the first):

1. **Marshal reads onto the owning thread** via a small thread-safe request queue drained by a Qt `QTimer` — REST history is low-frequency, so latency is fine. *(Recommended: no second connection, no file copy.)*
2. Open a **read-only copy** of the DB file on demand, reusing `scripts/sync_to_cloud.py::_open_db_readonly` (copy-on-lock). Simple but stale and I/O-heavy.
3. Periodically **snapshot session/lap/track summaries into memory** on the main thread and serve those.

### 4.4 Wiring in `main.py` (sketch, mirrors SyncManager)

```python
net_server = None
if not args.no_net and config.NET_ENABLED:
    try:
        from net.telemetry_server import TelemetryServer
        net_server = TelemetryServer(bridge=bridge, db_store=db_store,
                                     voice_mgr=voice_mgr, timing_mgr=timing_mgr)
        net_server.start()
        log.info("Companion telemetry server on :%d", config.NET_PORT)
    except Exception as exc:
        log.warning("Telemetry server failed to start: %s", exc)
# ... and net_server.stop() in the shutdown block.
```

---

## 5. Telemetry data contract

One versioned JSON shape, served live (WebSocket) and for review (REST). Keep it a **curated subset** of `DiffState` — only what the phone renders — so the wire format is stable even as `DiffState` grows.

### 5.1 Live frame (WebSocket push, ~15 Hz)

```jsonc
{
  "v": 1,                     // schema version
  "t": 1716500000.123,        // unix seconds (server clock)
  "conn": { "can": true, "gps_fix": 2, "ambient": true, "stale": false },
  "drive": { "rpm": 4200, "speed_kph": 88.4, "gear": 3,
             "throttle_pct": 62.0, "si_drive": "Sport", "surface": "DRY" },
  "engine": { "coolant_c": 92.0, "oil_temp_c": 110.0, "oil_psi": 58.0,
              "iat_c": 31.0, "map_kpa": 180.0, "lambda": 0.86,
              "fuel_press_kpa": 400.0, "battery_v": 13.9, "ethanol_pct": 30.0,
              "injector_duty_pct": 64.0 },
  "diff": { "dccd_cmd_pct": 47.0, "dccd_dial_pct": null, "slip_kph": 1.2 },
  "dynamics": { "steering_deg": -12.0, "yaw_dps": 8.0, "lat_g": 0.9,
                "brake_bar": 14.0,
                "wheels_kph": { "fl": 88.1, "fr": 88.3, "rl": 87.9, "rr": 90.2 } },
  "imu": { "ax": 0.31, "ay": 0.92, "az": 1.00, "gx": 1.1, "gy": 0.4, "gz": 7.8 },
  "gps": { "lat": 36.5847, "lon": -121.7534, "alt_m": 30.0,
           "heading_deg": 212.0, "sats": 11 },
  "ambient": { "temp_c": 18.0, "humidity_pct": 52.0, "pressure_hpa": 1013.0,
               "density_alt_ft": 1200.0, "dew_point_c": 8.0 },
  "timing": { "track": "WeatherTech Raceway Laguna Seca", "mode": "circuit",
              "lap": 4, "sector": 1, "sector_count": 3,
              "lap_time_ms": 41230, "delta_ms": -380,
              "predicted_ms": 98120, "theoretical_best_ms": 96900,
              "lap_distance_m": 1820.0 },
  "flags": { "brake": false, "handbrake": false, "abs": false, "vdc_tc": false },
  "pdm": null,                // reserved — see §13
  "warmup": "READY"
}
```

`serializers.diffstate_to_dict(state)` builds this from a `DiffState`. Reuse `.label` on the `IntEnum`s (`SurfaceState`, `SIDriveMode`, `WarmUpState`) exactly as `duckdb_store.record_telemetry` does. `None` means "signal not available" (e.g. `dccd_dial_pct`, `slip_kph`).

### 5.2 REST (history & definitions)

| Endpoint | Backed by | Returns |
|----------|-----------|---------|
| `GET /api/v1/health` | — | server version, schema `v`, uptime, CAN/GPS state |
| `GET /api/v1/state` | `bridge.snapshot()` | one live frame (for polling clients / cold start) |
| `GET /api/v1/sessions?limit=N` | `DuckDBStore.list_sessions` | session list (id, times, type, si_drive, synced) |
| `GET /api/v1/sessions/{id}/laps` | `DuckDBStore.get_session_laps` | per-lap times + `sector_times` JSON + deltas |
| `GET /api/v1/sessions/{id}/telemetry?downsample=...` | `telemetry` table | session trace for replay (GPS path + channels) |
| `GET /api/v1/tracks` | `TrackDatabase.list_tracks` | track defs (center, start/finish, sectors, length) |
| `GET /api/v1/tracks/{id}` | `TrackDatabase` + sectors | single track outline + sectors for the track-map renderer |
| `POST /api/v1/voice/query` | `voice_mgr.handle_voice_query` | JARVIS text answer (see [§9](#9-voicejarvis-integration)) |

The track shape returned mirrors `data/tracks_seed.json` so the iOS track-map renderer has one stable schema for seeded, learned, and live tracks.

### 5.3 WebSocket protocol

- Client connects `ws://<jetson>:8765/api/v1/stream`.
- On connect: server sends one full frame immediately, then pushes at `NET_BROADCAST_HZ`.
- Optional client→server control messages (small, JSON): `{ "op": "subscribe", "rate_hz": 5 }` to let CarPlay request a slower rate; `{ "op": "ping" }` heartbeat.
- Server tags each frame with `conn.stale=true` when `DiffState.is_any_stale()` so the UI can grey out values instead of showing frozen numbers.

---

## 6. iOS app architecture

### 6.1 Platform choice

- **Native Swift + SwiftUI** for the iPhone UI, **MapKit** for the road map, and a **Swift Package** for the shared networking/model layer. Native is effectively required because **CarPlay is iOS-native-only** (template frameworks have no cross-platform binding). A React Native / Flutter shell would force a native CarPlay module anyway — not worth it.
- Minimum target: iOS 16 (CarPlay template maturity, `Map` SwiftUI improvements, async/await `URLSession.WebSocketTask`).

### 6.2 Module layout (Xcode workspace)

```text
KiSTICompanion/                 # iOS app target (SwiftUI)
  App/                          # entry, scene, app-state
  Features/
    Dashboard/                  # live numeric/gauge dashboard (DIFF-equivalent)
    RoadMap/                    # MapKit street view
    TrackMap/                   # custom track-map canvas
    SessionReview/              # history list + replay
    Voice/                      # JARVIS push-to-talk / chat
    Settings/                   # connection, units, theme
  CarPlay/                      # CPTemplateApplicationSceneDelegate + scene
KiSTIKit/                       # Swift Package (shared, testable, no UIKit)
  Models/                       # Codable mirror of the §5 contract (Telemetry, TrackDef, Lap, Session)
  Net/                          # WebSocketClient, RESTClient, Discovery (Bonjour)
  Store/                        # connection state, reconnect, last-known frame
```

`KiSTIKit` holds the `Codable` structs matching [§5](#5-telemetry-data-contract) and is unit-tested against captured JSON fixtures (mirror the Jetson `tests/test_serializers.py` fixtures so both ends share golden samples).

### 6.3 Live data flow

`URLSession.WebSocketTask` → decode `Codable` frame → publish to an `@Observable` `TelemetryStore` → SwiftUI views update. Throttle UI redraw to display refresh; keep the latest frame only (drop, don't queue, stale frames). Show a clear **connection state machine**: `searching → connecting → live → stale → disconnected`, with the `conn.stale` flag greying values.

### 6.4 Discovery & connection

1. Browse Bonjour for `_kisti._tcp` (declared in `NSBonjourServices`).
2. If found, connect to the advertised host/port; cache the resolved IP.
3. Fallback chain: cached last-known IP → manual IP entry in Settings → the conventional hotspot gateway range hint.
4. Auto-reconnect with backoff when the link drops (track sessions = lots of WiFi churn).

---

## 7. Road map (STREET) — iPhone

- **Renderer:** MapKit (`Map` in SwiftUI) — real road tiles, unlike the Jetson's decorative `map_widget.py`.
- **Overlays:** car position annotation (heading-rotated), a breadcrumb **`MKPolyline` trail** from the live GPS stream, and a bottom info bar (speed, heading, coordinates) echoing the head-unit style but using real map data.
- **Camera:** follow-with-heading mode (map rotates to travel direction) with a toggle for north-up.
- **Telemetry coloring:** color the trail/segments by a selectable channel (speed, coolant, etc.) for at-a-glance context — framed as data visualization, not coaching.

---

## 8. Track map (TRACK) — iPhone

This is the motorsport-logger view and the most novel renderer.

- **Source geometry:** `GET /api/v1/tracks/{id}` (outline = closed GPS polygon from the learned/seeded trace; `start_finish` and `sectors[].line` segments). Project lat/lon to a local planar frame (reuse the same flat-earth scaling `timing/geo.py` uses: `m_per_deg_lat = 111320`, `m_per_deg_lon = 111320·cos(lat)`), then fit to the view.
- **Renderer:** SwiftUI `Canvas` (or SpriteKit if we want 60 fps trails) drawing: track ribbon, start/finish + sector lines, turn markers, and the **live car dot** from the GPS stream.
- **Live timing band:** lap number, current lap time, **delta vs best** (green/red), predicted lap, sector splits — all from `timing` in the live frame. This is the data the Jetson already computes in `LapTimer`/`TimingManager`; the phone only displays it.
- **Per-lap traces:** for replay/compare, fetch `…/telemetry` and draw historical racing lines colored by speed/throttle, with a lap picker.
- **Track learning:** if `timing.track` is empty (unknown track), show a "learning track…" state that draws the raw breadcrumb until the Jetson's `TrackLearner` closes the loop and a real outline appears.

---

## 9. Voice / JARVIS integration

The Jetson already owns the full persona + STT + LLM + TTS pipeline. **Do not re-implement it on the phone.** Two practical patterns:

1. **Text relay (simplest, do first):** phone sends `POST /api/v1/voice/query {"text": "..."}` → server calls `voice_mgr.handle_voice_query(text)` (already returns/produces a response) → return the text answer; the phone shows it and optionally speaks it with `AVSpeechSynthesizer`. iOS on-device speech recognition (`SFSpeechRecognizer`) does the phone-side STT.
2. **Audio relay (later):** stream mic audio to a Jetson STT endpoint so the *same* whisper pipeline and echo handling are used. Heavier; only if on-device STT proves inadequate.

The persona ("JARVIS / Enterprise computer / droid") lives entirely in the Jetson's `llm_engine` persona set and system prompt — the phone is a thin client to it. CarPlay voice should use a single push-to-talk button or a SiriKit intent (free-form mic UI is restricted while driving).

---

## 10. Session review & logging

- **List:** `GET /api/v1/sessions` → table of sessions (date, track, laps, best lap), `synced` badge.
- **Detail:** lap table (`…/laps`) with sector splits and deltas; tap a lap to load its trace.
- **Replay:** scrub the GPS path on road map + track map with synced channel readouts (`…/telemetry`, downsampled). Pure display of recorded data.
- **Off-network review:** when the phone isn't on the car's hotspot, hydrate the same `Codable` models from the cloud-synced Parquet/JSON the existing `sync_manager` already produces (Nextcloud "Project KiSTI/sessions"). One model layer, two sources.
- **Logging note:** the Jetson remains the logger of record (DuckDB). The phone never becomes the authority — it visualizes and reviews.

---

## 11. CarPlay surface: the primary map/track view

**CarPlay is the first-class surface, and it is map-centric and track-centric.** The headline CarPlay views are the **road map** and the **live track map**; gauges and stats are **secondary pages**. CarPlay is also the highest-risk part of the project (entitlement + App Review), so it must be planned realistically.

**How CarPlay actually works (and why map/track fits):**

- CarPlay is **template-only**, plus one optional **map scene**. Access requires a **CarPlay entitlement granted by Apple per app category** (requested via the developer portal; approval is discretionary and slow — start early).
- The **Navigation** category is special: it grants a **custom full-screen map drawing surface** — your own root view controller in the CarPlay `CPWindow`, exactly how Google Maps/Waze render bespoke maps. **Both the road map and the track map are "map content" drawn into this surface**, so the track-map renderer (outline + sectors + car dot + delta) can run on CarPlay, not only on the iPhone. `CPMapTemplate` overlays buttons/panels on top.
- A **tab bar** (`CPTabBarTemplate`) hosts secondary pages as `CPInformationTemplate` / `CPListTemplate` — glanceable rows (speed, lap, delta, one critical temp). These are the **secondary gauges/stats** pages.
- **What CarPlay still won't allow:** dense custom *gauge clusters* and racing/performance dashboards (rejected as distracting). Gauge-rich fidelity therefore lives on the iPhone / mounted iPad ([§18](#18-long-term-the-app-as-primary-display)); CarPlay shows the **map/track surface + a few glanceable stats**.

**Recommended CarPlay scope (map/track-first):**

1. **Primary surface — the map scene:** render the **road map** (live car position + breadcrumb) and the **track map** (circuit outline + sectors + car dot + delta band) into the Navigation map window. Switch road↔track via a `CPMapButton`, or auto-switch when a track is detected (`timing.track` non-empty).
2. **Secondary pages — stats:** a tab (or map panel) of `CPInformationTemplate` rows for lap / delta / speed / one critical temp. **No gauge clusters.**
3. **Frame it as navigation / trip mapping**, never racing/performance — in both the entitlement request and the App Store copy.

- **Review risk to manage:** a track map with a car dot is map-like and defensible, but App Review may scrutinize anything that reads as a performance instrument. Lead with the road map + trip framing; keep the track map presented as a *map of the circuit*, not a timing instrument cluster.
- **Action item:** file the **CarPlay Navigation entitlement request in Phase 0** (longest lead item). Build the map/track renderers as **shared code** used by both the CarPlay map scene and the iPhone, so the iPhone app stays shippable even if CarPlay approval lags.

---

## 12. Non-goals & framing guardrails

- **Not** a radar detector / speed-trap / police-alert app. The existing repo has Valentine One radar widgets (`data/models.py::RadarState`, `ui/widgets/radar_alert_widget.py`); the companion app should **not** surface these as alerts in any form that reads as a detector product. If radar hardware status is shown at all, it is only as generic "connected device" status, and it must be excluded from the App Store description. (Apple bans radar/speed-trap-style apps in many regions.)
- **Not** a street-racing or public-road performance-coaching app. Lap timing, deltas, and racing lines are framed as **track/session telemetry review**, not real-time public-road coaching.
- **Driving safety:** while moving, CarPlay and the iPhone foreground view default to large, glanceable, low-interaction surfaces. No text entry, no dense gauge fiddling while in motion.
- The personality (JARVIS / Enterprise / droid voice) is allowed and is a *display/voice* feature; it does not change the product category.

---

## 13. Gaps found in the current codebase

These should be resolved (or explicitly deferred) as part of, or before, the companion work:

1. **Razor PDM is not in `DiffState`.** It appears only in persona text (`voice/llm_engine.py`) and `data/build_record.py`, with **no CAN frame, no fields, no decoder.** The `pdm` key in the wire contract ([§5.1](#51-live-frame-websocket-push-15-hz)) is reserved as `null` until PDM telemetry is onboarded via `docs/sensor_onboarding.md` (CAN frame → `DiffState` fields → bridge update → serializer).
2. **GPS09 Pro frame IDs are placeholders** (`0x6A4`–`0x6A7`) pending hardware; the wire `gps`/`imu` fields will read zero/`gps_fix=0` until then. The app must handle "no GPS fix" gracefully (both maps show "acquiring GPS").
3. **Jetson maps are not GPS-driven** ([§2.2](#22-the-two-findings-that-drive-this-plan)) — fine to leave as-is for the head unit, but it means there is no existing GPS→screen projection to reuse; the iOS renderers build from the timing/geo primitives and track defs directly.
4. **DuckDB single-writer / thread-safety** must be handled for REST reads ([§4.3](#43-duckdb-access-from-the-server-thread-decision-needed)).
5. **No auth on the local link** today (there's nothing to authenticate). The server is on a private hotspot, but see [§14](#14-security).

---

## 14. Security

- The link rides the **private iPhone hotspot** (WPA2, small subnet), so exposure is limited, but the server still binds `0.0.0.0`. Add a lightweight **shared-token handshake** (token shown in the head-unit SETTINGS screen / generated on first boot, entered once in the app and cached) before a WebSocket upgrade or REST access is granted. Keep it simple; this is pairing, not enterprise auth.
- REST history endpoints are **read-only**; the only write path is `POST /voice/query`, which must validate/escape input before it reaches `handle_voice_query` (it feeds the LLM, not a shell).
- Do not expose the DuckDB file or arbitrary SQL over the network — only the curated endpoints in [§5.2](#52-rest-history--definitions).
- Bind to the hotspot interface only if feasible; otherwise rely on the token + the private subnet.

---

## 15. Phased roadmap

Each phase is independently shippable and keeps the Jetson app fully functional (everything behind `--no-net`, mirroring `--no-sync`). Maintain the **687-test baseline** and add tests per phase.

| Phase | Deliverable | Jetson | iOS / CarPlay | Exit criteria |
|------:|-------------|--------|---------------|---------------|
| **0** | Contract + fixtures **+ file CarPlay Navigation entitlement** (longest lead) | Finalize [§5](#5-telemetry-data-contract) JSON; `net/serializers.py` + `tests/test_serializers.py`; export golden JSON fixtures | `KiSTIKit` `Codable` models decoding the same fixtures; **submit CarPlay entitlement request** (map/trip framing) | Round-trip `DiffState` → JSON → Swift on shared fixtures; entitlement requested |
| **1** | Live server | `net/telemetry_server.py` (WS live frame + REST `/state`, `/health`, `/tracks` via [§4.3](#43-duckdb-access-from-the-server-thread-decision-needed)), `--no-net`, `config.py`, `net/discovery.py` mDNS | — | `wscat`/curl on the hotspot shows live frames + track defs; clean start/stop |
| **2** | **CarPlay road map** (first car-screen deliverable) | — | iOS shell + connection (discovery + manual IP) + `TelemetryStore`; **CarPlay Navigation map scene**: live road map, car dot, breadcrumb (shared MapKit renderer also shown on iPhone) | Car position + trail live on the **CarPlay** screen |
| **3** | **CarPlay track map** (centerpiece) | serve `/tracks/{id}` | **Track-map renderer in the CarPlay map window**: circuit outline + sectors + car dot + delta band (shared with iPhone) | Live track map + delta on the **CarPlay** screen at a known track |
| **4** | Secondary pages — gauges/stats | — | CarPlay secondary tabs (`CPInformationTemplate`/`CPListTemplate`: speed / lap / delta / one critical temp) + iPhone gauge dashboard (DIFF-equivalent) | Glanceable stats as CarPlay tabs; full gauges on iPhone |
| **5** | Session review | `/sessions`, `/sessions/{id}/laps`, `/sessions/{id}/telemetry` (downsampled) | History list, lap table, GPS replay on road + track map; off-network hydration from synced Parquet | Replay a past session on both maps (Jetson + cloud) |
| **6** | Voice / JARVIS | `POST /voice/query` → `handle_voice_query` (input-validated) | Push-to-talk (on-device STT) + transcript + spoken reply; single PTT button on CarPlay | "oil temp / last lap" answered on the phone |
| **7** | Hardening + supersession groundwork | Token pairing ([§14](#14-security)); `POST /command` stub ([§18](#18-long-term-the-app-as-primary-display)) | Backoff/reconnect, units/theme, stale/error states, WS backpressure | 30+ min drive soak; clean reconnects; no leaks |

**Parallelization:** Phase 0 unblocks both ends. The map/track renderers (Phases 2–3) are **shared code** used by both the CarPlay map scene and the iPhone, so building them once serves both surfaces; Jetson server work (Phase 1, plus the `/tracks` and history DB reads) proceeds in parallel against the shared fixtures and a recorded-frame mock server.

**Beyond Phase 7 — the supersession path ([§18](#18-long-term-the-app-as-primary-display)):** an app→Jetson **command channel** (replicating keypad K1–K6 actions), **camera/video transport** for VIDEO mode, **full mode parity**, and finally reducing the Jetson UI to `--headless`. These are larger efforts gated on v1 proving out and are scoped in §18, not above.

---

## 16. Decisions needed (before Phase 1)

1. **Server library:** `aiohttp` (HTTP+WS in one dep — recommended) vs `websockets`+stdlib HTTP. Confirm we can add a dep on the Jetson image.
2. **DuckDB read strategy** for REST ([§4.3](#43-duckdb-access-from-the-server-thread-decision-needed)): marshal-to-owning-thread (recommended) vs read-only copy vs in-memory summaries.
3. **CarPlay category — decided:** **Navigation** (custom map scene), because the surface is map/track-centric ([§11](#11-carplay-surface-the-primary-maptrack-view)). Open sub-question: how aggressively to present the *track* map under review vs leading purely with the road map. Entitlement request goes out in Phase 0.
4. **iOS minimum version** (recommend 16) and whether an iPad layout is in scope.
5. **Pairing/auth:** token handshake now ([§14](#14-security)) vs deferred to Phase 7. Recommended: stub the token field in Phase 1, enforce in 7.
6. **PDM onboarding timing:** is Razor PDM telemetry in scope for v1, or shipped `null` until the CAN frame exists?

---

## 17. Documentation & conventions to follow

- New Jetson code follows `docs/sensor_onboarding.md` for any new sensor (PDM), and the existing module style (dataclasses, `from __future__ import annotations`, `logging.getLogger("kisti...")`, optional-dependency guards, `start()`/`stop()` lifecycle, thread-safe `snapshot()` reads).
- Log each session's work in `PROGRESS.md` and hand off via the `NEXT_SESSION_PROMPT.md` / `claude-next-step-kisti-*.md` pattern already in the repo.
- Keep the wire contract versioned (`v`) and the `KiSTIKit` models in lockstep with `net/serializers.py` via shared JSON fixtures.

---

## 18. Long-term: the app as primary display

The app is not just a second screen — the intended end state is that it **supersedes the Jetson→Excelon output**, with the Jetson reduced to a headless brain/server/logger. This section scopes what "primary display" actually requires beyond the v1 companion in [§15](#15-phased-roadmap).

### 18.1 What already enables it

- **`main.py --headless`** runs the full stack (CAN, voice, DuckDB, timing, sync) with **no display** (`QCoreApplication`, `QT_QPA_PLATFORM=offscreen`). The Jetson can already operate UI-less; the telemetry server ([§4](#4-jetson-side-telemetry-server-the-new-net-package)) is what makes a headless Jetson *useful* to an external display.
- **`DiffStateBridge` + DuckDB are UI-independent.** Telemetry, logging, alerts, timing, and voice do not depend on the PySide6 widgets — only `ui/` does. The display layer can be lifted out without touching the brain.

### 18.2 What "primary display" additionally requires

1. **A control channel (app → Jetson).** The v1 contract is read-only telemetry + `POST /voice/query`. To replace the head unit, the app must drive what the **Link 8-button keypad** and head-unit controls do today (`can/can_config.py` K1–K8, surfaced via `ModeManager`):
   - K1 = session start/stop, K2 = mark segment, K3 = analyze run, K4 = voice toggle, K5 = coaching level, K6 = display-mode cycle.
   - Add `POST /api/v1/command { "op": "session_toggle" | "mark_segment" | "analyze_run" | "voice_toggle" | "set_mode" , ... }` that emits the **same signals** `ModeManager`/`main.py` already wire (e.g. `session_toggle`, `analyze_run`). This keeps one code path whether the trigger is the physical keypad or the app.
   - This is a **write** path — it needs the pairing/token from [§14](#14-security) enforced.
2. **Full mode parity.** The app must eventually cover every head-unit mode: KiSTI (overview/voice), STREET (road map), TRACK (track map + timing), DIFF (driveline), VIDEO (camera feeds), SETTINGS (config + sensor status). The maps and dashboard from [§6–§10](#6-ios-app-architecture) cover most; the two non-trivial gaps are **VIDEO** (below) and **SETTINGS** as an editable control surface.
3. **Camera / video transport.** VIDEO mode streams Teledyne IR / LiDAR-cam / RGB / weather feeds (`data/models.py::FrontSensorSuite`, `ui/widgets/camera_feeds.py`). These cannot ride the JSON telemetry channel — superseding the Excelon means a **separate media path** (WebRTC or RTSP/MJPEG over the local hotspot link), with bandwidth/latency validation on the hotspot. Large effort; later phase.
4. **Editable settings.** SETTINGS becomes a two-way surface (units, theme, sensor status, pairing, mode config) — extends the control channel.

### 18.3 The CarPlay ceiling (what it can and can't be)

CarPlay's Navigation map scene ([§11](#11-carplay-surface-the-primary-maptrack-view)) **can** host map-like surfaces — which is exactly the priority: the **road map and the live track map run on CarPlay**. What it **cannot** host is the Excelon's dense custom gauges, the DIFF driveline visual, or arbitrary instrument layouts. Therefore:

- **Map/track = CarPlay primary.** The headline driving views (road map, track map, delta) live on CarPlay.
- **Gauge-rich fidelity = iPhone / mounted iPad.** The DIFF driveline visual and dense gauge clusters run full-screen on a mounted iOS device — taking the Excelon's place or sitting beside it.
- If a gauge-dense in-dash display is a hard requirement, plan around a **mounted iPad** for that fidelity; CarPlay stays the map/track + glanceable-stats surface.

### 18.4 Migration path (low-risk, reversible)

1. **Dual display** (v1): Excelon keeps the PySide6 UI; the app runs alongside as companion. Both read the same brain. Nothing removed.
2. **Parity build**: app reaches mode parity + control channel + video. Excelon and app are interchangeable.
3. **Primary swap**: mount the iOS device as the main display; run the Jetson `--headless` (or keep a minimal Excelon fallback). The head unit becomes optional.
4. **Reversible at every step** — the Jetson UI is never deleted as part of this plan; it is *demoted* to fallback. Retiring `ui/` is a separate, explicit decision only after the app is proven in the car.

### 18.5 Open questions for the supersession path

- Target in-dash device: mounted **iPhone vs iPad** (screen size, mounting, the Excelon's physical slot)?
- Does the Excelon stay as a **fallback display**, or is it removed once parity is reached?
- VIDEO transport choice (WebRTC vs RTSP/MJPEG) and whether camera feeds are even in scope for the in-car display v1.
- Is the physical **Link keypad** retained as the primary control (with the app mirroring it), or does the touchscreen become primary?
