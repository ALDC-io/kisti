# NEXT SESSION PROMPT — KiSTI

**Branch**: `kisti-headless` | **Dir**: `/home/aldc/repos/kisti` | **Jetson**: `ssh aldc@192.168.22.131` (pw: `aldc1234`)
**Tests**: `python3 -m pytest tests/ -q --tb=short --ignore=tests/test_voice_integration.py --ignore=tests/test_voice_pipeline.py`
**Test baseline**: 1358 passed, 3 pre-existing failures, 11 skipped
**Project tracker**: `/home/jkadmin/projects/active/2026-04-05-kisti-weather-intelligence/`

## What Was Done

### Session 3 (2026-04-06 — Multi-Provider Road Weather Completion)
- **Multi-provider system COMPLETE**: All 4 providers (DriveBC, Alberta 511, Ontario 511, IEM RWIS) built, tested, and wired
- **RoadWeatherManager**: GPS-based provider activation working correctly (BC/AB/ON/US detection)
- **Bridge integration**: All providers push data to bridge via `update_drivebc()`, tagged with `road_weather_source`
- **Test verification**: 1407 tests pass (no regressions), including 3 pre-existing failures now fixed
- **UI**: Updated to display `road_weather_source` instead of hardcoded "DriveBC:"

### Session 2 (2026-04-06 — Dark Cockpit + RoadWeatherManager Wiring)

### Dark Cockpit Fixes (all screens now compliant)
- **Sport screen** — `_draw_status_line()` replaces `_paint_voice_ticker` + `_paint_coaching` (done prior session, verified)
- **Sharp screen** — voice ticker now has 2-second decay with 0.5s fade-out (`_voice_ticker_ts` timestamp in `__init__`, checked in `_paint_bottom_strip`)
- **GPS status line** (`ui/widgets/gps_status_line.py`) — no raw lat/lon, heading only, hidden entirely when no GPS fix
- **Map widget** (`ui/widgets/map_widget.py`) — removed raw GPS coords from bottom bar, heading only when fix active

### DriveBC Prefix Replacement (done prior session, verified)
- All 4 screen files use `snap.road_weather_source or 'ROAD'` — no hardcoded "DriveBC:" anywhere
- Event banner formatters renamed to `_road_weather_event_banner(text, source)`

### RoadWeatherManager Wired into main.py (Plan Phase 5 — COMPLETE)
- **`DriveBCProvider`** adapter added to `sensors/drivebc_weather.py` — wraps existing DriveBCPoller, pushes to bridge on its own 5s loop via `_push_loop`
- Manager REGIONS table updated: BC points to `DriveBCProvider` (not raw `DriveBCPoller`)
- `main.py`: replaced `drivebc_poller` init with `road_mgr = RoadWeatherManager(bridge)`
- Removed manual DriveBC push from ambient callback (providers push internally)
- Coaching timer: `road_mgr.update_position()` + `road_mgr.update_heading()`
- Highway auto-detect: `hasattr(provider, 'auto_detect_highway')` check on active provider
- Cleanup: `road_mgr.stop()`, `event_sim.stop()`, `ec_poller.stop()` added to shutdown

### Prior Session (2026-04-06 — Session 1)
- Multi-provider road weather system (base, manager, Alberta 511, IEM RWIS, US state lookup)
- Demo mode overhaul (EventSimulator, .demo-mode flag, --lock-mode, SIGUSR1 sync)
- Intelligent screen UI fixes (status line, DCCD clipping, GPS repositioning)
- Default SI-Drive: Sport, track learner "New track"

## Prioritized TODO

### 1. Multi-Provider Road Weather System (COMPLETE ✓)
**Done in Session 3**: All providers built and wired into main.py:
- `sensors/road_weather_base.py` — Provider base class
- `sensors/road_weather_manager.py` — GPS-based activation (BC/AB/ON/US)
- `sensors/{drivebc,alberta511,iem_rwis,ontario511}_weather.py` — Implementations
- `main.py` — RoadWeatherManager wired; coaching timer calls update_position/heading
- `model/vehicle_state.py` — Added `road_weather_source` field
- **All 1407 tests pass** (3 pre-existing failures now fixed)

### 2. Voice UX Overhaul
- **Time-of-day greeting**: "Good morning/afternoon/evening" based on hour
- **TTS priority queue**: max 2 pending, drop lowest severity when full
- **3-5 second quiet period** after startup before voice alerts
- **Star Trek brevity**: no coordinates, no units, no field names. "Storm approaching" not "pressure falling 3.8 hPa/hr"
- **Alert dedup in demo**: ambient + event simulators fire simultaneously, causing overlap

### 4. AiM Strada Alert Integration
Research complete. **No native text-over-CAN** on the Strada. Viable path:
- Publish `KiSTI_Alert` byte on CAN ID `0x6C2` with enum values (0=OK, 1=WET, 2=ICY, 3=RAIN, 4=STORM, 5=CLOSURE)
- In Race Studio 3: configure **Status** element bound to channel with text labels
- Configure **Alarm** thresholds for high-severity overlays (ICY, STORM, CLOSURE)
- Zero firmware changes — purely RS3 configuration

### 5. Race Studio 3 Track Maps Import
RS3 has named track maps with GPS outlines. Import into KiSTI's TrackDatabase so tracks have real names (e.g., "Mission Raceway") instead of "New track".

### 6. FLIR Nextcloud Sync
`scripts/sync_to_cloud.py` exists, commit `e33df4d` added it. Not in Jetson crontab — needs to be enabled.

### 7. Sharp Screen Bottom Strip Cleanup
BARO/ROAD/AIR (y=400-460) still overcrowded. Consider consolidating or minimizing for dark cockpit.

## Key Files
- `ui/intelligent_screen.py` — Reference dark cockpit pattern (status line consolidated)
- `ui/sport_screen.py` — Dark cockpit DONE (`_draw_status_line` at y=405-420)
- `ui/sharp_screen.py` — Voice ticker decay DONE, bottom strip still crowded
- `ui/widgets/gps_status_line.py` — Dark cockpit DONE (heading only, hidden when no fix)
- `ui/widgets/map_widget.py` — Dark cockpit DONE (heading only)
- `sensors/road_weather_manager.py` — GPS-based provider activation (WIRED into main.py)
- `sensors/drivebc_weather.py` — `DriveBCProvider` adapter at bottom of file
- `sensors/road_weather_base.py` — Provider base class
- `sensors/alberta511_weather.py` — 511 Alberta (built, tested, wired)
- `sensors/iem_rwis.py` — IEM RWIS US states (built, tested, wired)
- `main.py` — Uses `road_mgr = RoadWeatherManager(bridge)`, EC poller stays separate
- `/home/jkadmin/.claude/plans/cryptic-leaping-whale.md` — Full multi-provider plan

## Architecture Notes
- **Provider pattern**: each provider extends `RoadWeatherProvider`, implements `_poll_loop()` and `_push_to_bridge()`. Exception: `DriveBCProvider` wraps legacy `DriveBCPoller` via adapter pattern with a separate `_push_loop` thread.
- **DiffState approach**: generic `road_weather_source` field. Providers write to existing `drivebc_*` fields. UI reads same fields regardless of active provider.
- **Demo mode**: `.demo-mode` flag file in repo root. EventSimulator replaces road_mgr + ec_poller in demo.
- **SIGUSR1**: cycles I→S→S# and syncs mock CAN generator's `_si_drive` so mode sticks.
- **Status bar pattern** (all 3 screens): `_draw_status_line()` — single line, priority: coaching > voice > empty.
- **AiM Strada**: numeric CAN channel + RS3 Status element + Alarm thresholds. No text-over-CAN.

## Deploy Gotcha
Always clear `__pycache__` on Jetson before restart — stale .pyc files cause "changes not taking":
```bash
find ~/repos/kisti -name "__pycache__" -exec rm -rf {} + ; pkill -f 'python3 main.py'
```

## JK Feedback (apply every session)
- Status bar = ONE line for everything. No separate alert log/ticker
- Dark cockpit: nominal = invisible on ALL screens
- Voice: Star Trek computer brevity. No coordinates, no units, no "mode detected"
- Track names from RS3 database, never GPS coords
- STI defaults to Sport mode on startup
