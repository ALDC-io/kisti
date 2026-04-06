# NEXT SESSION PROMPT — KiSTI

**Branch**: `kisti-headless` | **Dir**: `/home/aldc/repos/kisti` | **Jetson**: `ssh aldc@192.168.22.131` (pw: `aldc1234`)
**Tests**: `python3 -m pytest tests/ -q --tb=short --ignore=tests/test_voice_integration.py --ignore=tests/test_voice_pipeline.py`
**Test baseline**: 1361 tests
**Project tracker**: `/home/jkadmin/projects/active/2026-04-05-kisti-weather-intelligence/`

## What Was Done (2026-04-06 — Multi-Provider Road Weather + UI Fixes)

### Multi-Provider Road Weather System
- **RoadWeatherProvider base** (`sensors/road_weather_base.py`) — shared boilerplate, haversine, thread lifecycle
- **RoadWeatherManager** (`sensors/road_weather_manager.py`) — GPS-based provider activation (BC/AB/ON/US regions)
- **511 Alberta poller** (`sensors/alberta511_weather.py`) — Castle Rock API, events year-round, 43 tests
- **IEM RWIS poller** (`sensors/iem_rwis.py`) — 33 US states, 2198 stations, F→C conversion, 65 tests
- **US state lookup** (`sensors/us_state_lookup.py`) — lat/lon → state code for IEM network selection
- **road_weather_source** field added to DiffState for provider attribution
- **Ontario 511 poller** — NOT YET BUILT (Phase 4 of plan)
- **Wiring into main.py** — NOT YET DONE (Phase 5 — replace individual pollers with RoadWeatherManager)

### Demo Mode Overhaul
- **EventSimulator** (`sensors/event_simulator.py`) — 7-phase DriveBC+EC scenario, loops continuously
- `.demo-mode` flag file toggles demo without editing kisti-session script
- `--lock-mode` flag prevents SI-Drive auto-cycling in demo
- SIGUSR1 now syncs with mock CAN generator (was reverting to Intelligent on every tick)

### UI Fixes (Intelligent Screen)
- Consolidated voice ticker + coaching into single status line at y=448 (`_draw_status_line`)
- Removed separate alert log / voice ticker stack
- Fixed DCCD percentage text clipping (height 22→28)
- GPS text repositioned below DCCD (no overlap)
- Mini G-dot shrunk r=40→25, repositioned

### Startup + Voice
- Default SI-Drive: Sport (STI default, was Intelligent)
- ModeManager emits initial mode on start()
- Track learner: "New track" not GPS coordinates
- Sim announcements shortened

## Prioritized TODO

### 1. CRITICAL: Dark Cockpit Audit Fixes (Sport + Sharp screens)

Full audit completed. Intelligent screen is the reference pattern. Sport and Sharp need these fixes:

**Sport screen (`ui/sport_screen.py`):**
- **Remove `_paint_voice_ticker()`** (lines 557-570) — voice renders as 3-line floating stack
- **Remove coaching text at y=418-438** (lines 576-589) — overlaps alert bar (y=422-440) by 16px
- **Add single status line** at y=405-420: ALERT > COACHING > VOICE priority

**Sharp screen (`ui/sharp_screen.py`):**
- **Voice ticker (lines 559-569)** visible when nominal — add 2-second timestamp decay
- **BARO/ROAD/AIR** (y=400-460) overcrowded — consider consolidating or minimizing

**GPS widgets (dark cockpit violations):**
- `ui/widgets/gps_status_line.py` lines 49-54 — GPS coords always visible. Deprecate or add staleness check
- `ui/widgets/map_widget.py` lines 194-200 — GPS coords in map bottom bar. Remove, keep speed dot only

### 2. Hardcoded "DriveBC:" Prefixes → `snap.road_weather_source`

16 instances across 4 files:
- `intelligent_screen.py`: lines 66, 71, 584, 589
- `sport_screen.py`: lines 65, 69, 348, 351
- `sharp_screen.py`: lines 72, 76, 619, 622
- `sharp_screen_track.py`: lines 65, 69, 693, 696

Replace `f"DriveBC: {cond}..."` with `f"{snap.road_weather_source or 'ROAD'}: {cond}..."`

### 3. Wire RoadWeatherManager into main.py (Plan Phase 5)

Replace individual DriveBC/EC poller initialization with RoadWeatherManager. See plan at `/home/jkadmin/.claude/plans/cryptic-leaping-whale.md`.

### 4. Ontario 511 Poller (Plan Phase 4)

Same Castle Rock platform as Alberta. Road conditions year-round (546 records). `sensors/ontario511_weather.py`.

### 5. Voice UX Overhaul

- **Time-of-day greeting**: "Good morning/afternoon/evening" based on hour
- **TTS priority queue**: max 2 pending, drop lowest severity when full
- **3-5 second quiet period** after startup before voice alerts
- **Star Trek brevity**: no coordinates, no units, no field names. "Storm approaching" not "pressure falling 3.8 hPa/hr"
- **Alert dedup in demo**: ambient + event simulators fire simultaneously, causing overlap

### 6. AiM Strada Alert Integration

Research complete. **No native text-over-CAN** on the Strada. Viable path:
- Publish `KiSTI_Alert` byte on CAN ID `0x6C2` with enum values (0=OK, 1=WET, 2=ICY, 3=RAIN, 4=STORM, 5=CLOSURE)
- In Race Studio 3: configure **Status** element bound to channel with text labels
- Configure **Alarm** thresholds for high-severity overlays (ICY, STORM, CLOSURE)
- Zero firmware changes — purely RS3 configuration

### 7. Race Studio 3 Track Maps Import

RS3 has named track maps with GPS outlines. Import into KiSTI's TrackDatabase so tracks have real names (e.g., "Mission Raceway") instead of "New track".

### 8. FLIR Nextcloud Sync

`scripts/sync_to_cloud.py` exists, commit `e33df4d` added it. Not in Jetson crontab — needs to be enabled.

## Key Files
- `ui/intelligent_screen.py` — Reference dark cockpit pattern (status line consolidated)
- `ui/sport_screen.py` — Needs consolidation (voice ticker + coaching + alert overlap)
- `ui/sharp_screen.py` — Needs voice decay + weather strip cleanup
- `sensors/road_weather_manager.py` — GPS-based provider activation (not yet wired)
- `sensors/road_weather_base.py` — Provider base class
- `sensors/alberta511_weather.py` — 511 Alberta (built, tested, not yet wired)
- `sensors/iem_rwis.py` — IEM RWIS US states (built, tested, not yet wired)
- `sensors/event_simulator.py` — Demo mode event cycling
- `modes/mode_manager.py` — Default Sport mode, emits on start()
- `can/kisti_can.py` — Mock CAN default Sport, SIGUSR1 sync
- `/home/jkadmin/.claude/plans/cryptic-leaping-whale.md` — Full multi-provider plan

## Architecture Notes
- **Provider pattern**: each provider extends `RoadWeatherProvider`, implements `_poll_loop()` and `_push_to_bridge()`. Bridge methods unchanged.
- **DiffState approach**: generic `road_weather_source` field. Providers write to existing `drivebc_*` fields via `_push_to_bridge()`. UI reads same fields regardless of active provider.
- **Demo mode**: `.demo-mode` flag file in repo root. Remove to disable. Session script reads it on restart.
- **SIGUSR1**: cycles I→S→S# and syncs mock CAN generator's `_si_drive` so mode sticks.
- **Status bar pattern** (Intelligent = reference): `_draw_status_line()` shows coaching > voice > empty. Single line at y=448. No separate ticker/log.
- **AiM Strada**: numeric CAN channel + RS3 Status element + Alarm thresholds. No text-over-CAN protocol exists.

## JK Feedback (captured in memory, apply next session)
- Status bar = ONE line for everything. No separate alert log/ticker
- Dark cockpit: nominal = invisible on ALL screens
- Voice: Star Trek computer brevity. No coordinates, no units, no "mode detected"
- Track names from RS3 database, never GPS coords
- STI defaults to Sport mode on startup
- Intelligent screen DCCD bottom-right numbers were clipped (fixed)
- EC banner + DriveBC alert showing simultaneously in different locations (consolidate)
- Intelligent screen "cold surface" coaching text still showing bottom-left (may need pycache clear on deploy)
- Deploy tip: always `find ~/repos/kisti -name "__pycache__" -exec rm -rf {} +` before kill/restart
