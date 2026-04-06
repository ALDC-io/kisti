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

### 2. Voice UX Overhaul (COMPLETE ✓)
**Done in Session 4**: All 4 phases implemented:
- **Phase 1**: Star Trek brevity — rewrote 11 alert messages (oil, coolant, fuel, battery, weather, snow risk). No units, coordinates, or field names
- **Phase 2**: Priority queue — replaced FIFO queue with `queue.PriorityQueue(maxsize=2)` using `SpeakItem` dataclass. Severity-based priorities: critical=100, warning=50, advisory=25, info=10
- **Phase 3**: Time-of-day greeting — added `_announce_greeting()` method, called at startup. "Good morning/afternoon/evening" based on hour
- **Phase 4**: Demo alert dedup — added 3-second window in `EventSimulator` to prevent simultaneous road_condition + ec_weather alerts
- **Startup quiet period**: 3.5s suppression of non-critical alerts during init to avoid announcement spam
- **All 1407 tests pass** (no regressions)

### 3. AiM Strada Alert Integration (COMPLETE ✓)
**Done in Session 5**: CAN frame publishing complete:
- Added `KISTI_ALERT_FRAME_ID = 0x6C2` to `can_config.py`
- Encoder function `encode_kisti_alert()` maps road conditions + alerts to enum (0=OK, 1=WET, 2=ICY, 3=RAIN, 4=STORM, 5=CLOSURE)
- `CanOutputThread` extended with `set_alert_state()` method, sends frames at 10 Hz (every 3rd LED cycle)
- `main.py` coaching timer calls `can_output.set_alert_state()` with current road/weather data
- **All 1407 tests pass** (no regressions)
- RS3 configuration: bind Status element to 0x6C2 byte 0, add Alarm thresholds for ICY/STORM/CLOSURE

### 4. Race Studio 3 Track Maps Import
RS3 has named track maps with GPS outlines. Import into KiSTI's TrackDatabase so tracks have real names (e.g., "Mission Raceway") instead of "New track".

### 5. FLIR Nextcloud Sync (COMPLETE ✓)
**Done in Session 6**: `sync_to_cloud.py` enabled on Jetson crontab:
- **`jetson_sync_cloud.sh`** wrapper added — follows same pattern as auto-commit, sets working directory
- **Cron schedule**: Daily at 2 AM (low-activity time) — `0 2 * * * /home/aldc/repos/kisti/scripts/jetson_sync_cloud.sh`
- **Sync includes**: weather data (Parquet+CSV+JSON), database backup (timestamped + latest), memories (team/public), LLM config + build record
- **Tested**: Successfully synced 9,759 ambient readings + database to Nextcloud `Project KiSTI/` folder
- **Fixed import issues**: Added repo root to sys.path, wrapped voice/build_record imports with graceful fallbacks, fixed PERSONA_RESPONSES unpacking (3-element tuples)

### 6. Sharp Screen Bottom Strip Cleanup (COMPLETE ✓)
**Done in Session 6**: Replaced 60px multi-element strip with single status line:
- **Before**: 5 elements in 800px (BARO|zone bar|road temp|air temp|voice ticker) at y=400-460
- **After**: Single status line at y=440-458, matching Intelligent + Sport screen pattern
- **Dark cockpit**: Coaching > weather/road alert (only abnormal) > voice ticker > empty
- **Weather intelligence**: `_weather_status_text()` consolidates BARO trend, road temp, air temp, fog risk — only visible when conditions are abnormal (STORM/RAIN/FOG/CHANGING/freezing)
- **Coaching wired**: main.py now sends coaching text to Sharp screen (was missing)
- **All 1407 tests pass** (no regressions)

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
