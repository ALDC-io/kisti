# NEXT SESSION PROMPT — KiSTI v7

**Branch**: `kisti-headless` | **Dir**: `/home/aldc/repos/kisti` | **Jetson**: `ssh aldc@192.168.22.131` (pw: `aldc1234`)
**Tests**: `python3 -m pytest tests/ -q --tb=short --ignore=tests/test_voice_integration.py --ignore=tests/test_voice_pipeline.py`
**Test baseline**: 1407 passed, 0 failures, 11 skipped
**Project tracker**: `/home/jkadmin/projects/active/2026-04-05-kisti-weather-intelligence/`
**Prior version**: `NEXT_SESSION_KISTI_v6.md` (archived)

## What Was Done (Session 6 — 2026-04-06)

### FLIR Nextcloud Sync (Priority 5 COMPLETE)
- Created `scripts/jetson_sync_cloud.sh` wrapper (follows `jetson_auto_commit.sh` pattern)
- Cron: daily at 2 AM — `0 2 * * * /home/aldc/repos/kisti/scripts/jetson_sync_cloud.sh`
- Fixed `scripts/sync_to_cloud.py`: sys.path setup, PERSONA_RESPONSES 3-tuple unpacking, graceful import fallbacks for voice/build_record modules
- Tested: 9,759 ambient readings + full DB backup + LLM config synced to Nextcloud `Project KiSTI/`

### Sharp Screen Bottom Strip Consolidation (Priority 6 COMPLETE)
- **Before**: 60px strip (y=400-460) with 5 elements (BARO|zone bar|road temp|air temp|voice ticker) — overcrowded
- **After**: Single 18px status line (y=440-458) matching Intelligent + Sport screens
- `_draw_status_line()` priority: coaching > weather alert (abnormal only) > voice ticker > empty
- `_weather_status_text()` surfaces BARO/road temp/air temp/fog risk only when abnormal (dark cockpit compliant)
- Wired coaching text from technique analyzer to Sharp screen (`main.py` line ~959) — was missing
- Removed unused `paint_zone_bar` import
- Hero G-force area gained 40px vertical space (y=30-440 instead of y=30-400)

### All Prior Sessions (1-5)
- **Multi-provider road weather**: DriveBC + Alberta 511 + Ontario 511 + IEM RWIS, GPS-based activation
- **Voice UX**: Star Trek brevity, priority queue, time-of-day greeting, startup quiet period
- **AiM Strada**: 0x6C2 alert frame at 10Hz, enum encoding (OK/WET/ICY/RAIN/STORM/CLOSURE)
- **Dark cockpit**: All 3 screens compliant, status bar pattern consistent
- **Demo mode**: EventSimulator, `.demo-mode` flag, SIGUSR1 screen cycling

## Prioritized TODO

### 1. Track Database Seed on Startup (QUICK WIN)
**`seed_tracks()` is never called.** 18 tracks exist in `data/tracks_seed.json` (Mission Raceway, Area 27, PIR, Laguna Seca, etc.) but are never loaded. TrackLearner creates "New track" because the DB is empty.

**Fix** (~10 lines in main.py):
- In timing_manager init block, call `track_db.seed_tracks(Path("data/tracks_seed.json"))` if `track_db.track_count() == 0`
- This gives GPS-based track detection real names immediately
- Key files: `timing/track_db.py:189` (seed_tracks), `data/tracks_seed.json` (18 tracks), `timing/timing_manager.py:56` (track_db init)

### 2. Race Studio 3 Track Maps Import (RESEARCH)
RS3 has named track maps with GPS outlines in proprietary .xrk/.mpl formats. No RS3 track files exist on the system yet. No `~/.aim/` directory.
- **Option A**: Export tracks from RS3 GPS Manager tool as waypoints, convert to `tracks_seed.json` format
- **Option B**: Reverse-engineer .mpl binary format from hex dumps (needs sample files from AiM)
- **Option C**: Use RS3's track center coordinates + radius from its UI, manually add to seed JSON
- **Blocked until**: AiM Strada hardware arrives and RS3 generates track files on the Jetson

### 3. RS3 AiM Strada Configuration
Bind Status element to CAN ID 0x6C2 byte 0 in Race Studio 3:
- Text labels: OK(0), WET(1), ICY(2), RAIN(3), STORM(4), CLOSURE(5)
- Alarm thresholds: ICY(2), STORM(4), CLOSURE(5) for visual overlays
- Requires RS3 access with Strada connected

### 4. Jetson Deployment Validation
- Restart KiSTI on Jetson, verify all 3 screens render correctly
- Verify cron sync runs at 2 AM, check Nextcloud for new files next day
- Test Sharp screen status line vs old bottom strip — road test comparison

### 5. Sport Screen Voice Ticker Review
Voice ticker at y=370 may conflict with coaching text at y=418 (only 48px gap). Needs road testing to verify readability.

### 6. K6 Sub-Page Toggle
Wire mode_manager to switch between canyon (`sharp_screen.py`) and track (`sharp_screen_track.py`) S# variants via K6 button press.

## Key Files
- `ui/sharp_screen.py` — Dark cockpit DONE. `_draw_status_line()` + `_weather_status_text()` (y=440-458)
- `ui/sport_screen.py` — Dark cockpit DONE (`_draw_status_line` at y=405-420)
- `ui/intelligent_screen.py` — Reference dark cockpit pattern (status line at y=448-466)
- `timing/track_db.py:189` — `seed_tracks()` method, never called on startup
- `data/tracks_seed.json` — 18 tracks with GPS, sectors, names (Mission Raceway, Area 27, PIR, etc.)
- `timing/timing_manager.py:56` — TrackDatabase init (where seed call should go)
- `scripts/sync_to_cloud.py` — Nextcloud sync (weather, FLIR, DB, memories, LLM config)
- `scripts/jetson_sync_cloud.sh` — Cron wrapper for sync
- `sensors/road_weather_manager.py` — GPS-based provider activation (wired into main.py)
- `can/kisti_can.py` — `encode_kisti_alert()` + `CanOutputThread.set_alert_state()` for 0x6C2
- `main.py` — Central orchestration. Coaching timer feeds all 3 screens

## Architecture Notes
- **Provider pattern**: each provider extends `RoadWeatherProvider`, implements `_poll_loop()` and `_push_to_bridge()`. DriveBCProvider wraps legacy DriveBCPoller via adapter.
- **DiffState approach**: generic `road_weather_source` field. Providers write to existing `drivebc_*` fields. UI reads same fields regardless.
- **Status bar pattern** (all 3 screens): `_draw_status_line()` — single line, priority: coaching > weather/road alert > voice > empty. Sharp screen adds `_weather_status_text()` for inline weather (abnormal only).
- **Demo mode**: `.demo-mode` flag file in repo root. EventSimulator replaces road_mgr + ec_poller.
- **SIGUSR1**: cycles I->S->S# and syncs mock CAN generator's `_si_drive` so mode sticks.
- **AiM Strada**: numeric CAN channel (0x6C2) + RS3 Status element + Alarm thresholds. No text-over-CAN.
- **Cloud sync**: Daily 2 AM rclone push to Nextcloud. DuckDB copy-on-read handles lock contention.
- **Track detection**: `find_track(lat, lon)` haversine within radius. Seed file has 18 tracks. TrackLearner creates "New track" when no match — fix by seeding on startup.

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
