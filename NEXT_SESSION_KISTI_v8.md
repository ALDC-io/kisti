# NEXT SESSION PROMPT — KiSTI v8

**Branch**: `kisti-headless` | **Dir**: `/home/aldc/repos/kisti` | **Jetson**: `ssh aldc@192.168.22.131` (pw: `aldc1234`)
**Tests**: `python3 -m pytest tests/ -q --tb=short --ignore=tests/test_voice_integration.py --ignore=tests/test_voice_pipeline.py`
**Test baseline**: 1408 passed, 0 failures, 11 skipped
**Project tracker**: `/home/jkadmin/projects/active/2026-04-05-kisti-weather-intelligence/`
**Prior version**: `NEXT_SESSION_KISTI_v7.md` (archived)

## What Was Done (Session 7 — 2026-04-06)

### Track Database Seed on Startup (Priority 1 COMPLETE)
- `seed_tracks()` now called in `TimingManager.__init__` when `track_count() == 0`
- 18 tracks from `data/tracks_seed.json` (Mission Raceway, Area 27, PIR, Laguna Seca, etc.) load on first boot
- GPS-based track detection immediately has real names instead of "New track"
- Files changed: `timing/timing_manager.py` (+4 lines, Path import + seed call)

### K6 Sub-Page Toggle (Priority 6 COMPLETE)
- K6 button now toggles between canyon (`sharp_screen.py`) and track (`sharp_screen_track.py`) S# variants
- **mode_manager.py**: K6 handler cycles `_sharp_subpage` (0=canyon, 1=track) when in S# mode, emits `subpage_changed` signal. Ignored in I/S modes
- **main_window.py**: Track screen added to stack (index 3). SI-Drive mapping routes S# to index 2 or 3 based on subpage. VIDEO moved to index 4. Keyboard shortcuts updated (1-5)
- **main.py**: All data feeds (timing, coaching, balance, grip, voice ticker, repaint) now go to both `_sharp_screen` and `_sharp_screen_track`
- 2 new tests replace old `test_k6_reserved` no-op: `test_k6_toggles_sharp_subpage_in_sport_sharp` + `test_k6_ignored_outside_sport_sharp`
- Test count: 1407 → 1408 (+1 net)

### All Prior Sessions (1-6)
- **Multi-provider road weather**: DriveBC + Alberta 511 + Ontario 511 + IEM RWIS, GPS-based activation
- **Voice UX**: Star Trek brevity, priority queue, time-of-day greeting, startup quiet period
- **AiM Strada**: 0x6C2 alert frame at 10Hz, enum encoding (OK/WET/ICY/RAIN/STORM/CLOSURE)
- **Dark cockpit**: All 3 screens compliant, status bar pattern consistent
- **Demo mode**: EventSimulator, `.demo-mode` flag, SIGUSR1 screen cycling
- **FLIR Nextcloud Sync**: Daily 2 AM rclone push to Nextcloud
- **Sharp screen consolidation**: Single 18px status line, dark cockpit compliant

## Prioritized TODO

### 1. Race Studio 3 Track Maps Import (RESEARCH)
RS3 has named track maps with GPS outlines in proprietary .xrk/.mpl formats. No RS3 track files exist on the system yet. No `~/.aim/` directory.
- **Option A**: Export tracks from RS3 GPS Manager tool as waypoints, convert to `tracks_seed.json` format
- **Option B**: Reverse-engineer .mpl binary format from hex dumps (needs sample files from AiM)
- **Option C**: Use RS3's track center coordinates + radius from its UI, manually add to seed JSON
- **Blocked until**: AiM Strada hardware arrives and RS3 generates track files on the Jetson

### 2. RS3 AiM Strada Configuration
Bind Status element to CAN ID 0x6C2 byte 0 in Race Studio 3:
- Text labels: OK(0), WET(1), ICY(2), RAIN(3), STORM(4), CLOSURE(5)
- Alarm thresholds: ICY(2), STORM(4), CLOSURE(5) for visual overlays
- Requires RS3 access with Strada connected

### 3. Jetson Deployment Validation
- Restart KiSTI on Jetson, verify all 3 screens render correctly
- Test K6 toggle between canyon and track S# screens
- Verify cron sync runs at 2 AM, check Nextcloud for new files next day
- Test Sharp screen status line vs old bottom strip — road test comparison

### 4. Sport Screen Voice Ticker Review
Voice ticker at y=370 may conflict with coaching text at y=418 (only 48px gap). Needs road testing to verify readability.

### 5. Brake Quality Feed to Track Screen
`update_brake_quality(sector_qualities)` exists on both screen widgets but is never called from main.py. Wire it once brake analysis module is ready.

## Key Files
- `timing/timing_manager.py:56-62` — Track DB init + seed call (NEW)
- `modes/mode_manager.py:187-194` — K6 handler, `_sharp_subpage` toggle (NEW)
- `modes/mode_manager.py:253-255` — `sharp_subpage` property (NEW)
- `ui/main_window.py:90-96` — Stack: I(0), S(1), S#canyon(2), S#track(3), VIDEO(4) (CHANGED)
- `ui/main_window.py:156-178` — `_si_drive_to_index()`, `_on_subpage_changed()` (NEW)
- `ui/sharp_screen.py` — Canyon S# variant (G-force focused)
- `ui/sharp_screen_track.py` — Track S# variant (timing/delta focused)
- `data/tracks_seed.json` — 18 tracks with GPS, sectors, names
- `main.py` — All data feeds now go to both sharp screens

## Architecture Notes
- **S# sub-page model**: `mode_manager._sharp_subpage` (0 or 1) + `subpage_changed` signal. Main window maps S# to stack index 2+subpage. K6 only toggles in S# mode; ignored in I/S
- **Both screens always receive data**: Both canyon and track variants get timing, coaching, balance, grip, and voice feeds at all times. Only the visible one paints
- **Stack layout**: [Intelligent=0, Sport=1, S#Canyon=2, S#Track=3, VIDEO=4]. SI Drive maps 0→0, 1→1, 2→2+subpage. Invalid modes (99) are rejected
- **Provider pattern**: each provider extends `RoadWeatherProvider`, implements `_poll_loop()` and `_push_to_bridge()`. DriveBCProvider wraps legacy DriveBCPoller via adapter
- **Track seeding**: On first boot (track_count==0), `seed_tracks()` imports 18 tracks from JSON. Uses `Path(__file__).parent.parent / "data" / "tracks_seed.json"` for relocatable path

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
