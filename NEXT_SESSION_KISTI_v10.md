# KiSTI Next Session — v10 (kisti-road-06)

## Working Directory
`/home/aldc/repos/kisti/` (dev machine) | Jetson: `ssh aldc@192.168.22.131` (pw: aldc1234)
Branch: `kisti-headless` | Test baseline: **1513 passed**

## Display Info (changes each reboot)
- `DISPLAY=:0` (startx session, NOT GDM)
- `XAUTHORITY=/tmp/serverauth.YqyAI50FSy` (verify with `ls /tmp/serverauth.*`)
- Screenshot: `ssh aldc@192.168.22.131 "DISPLAY=:0 XAUTHORITY=/tmp/serverauth.YqyAI50FSy import -window root /tmp/s.png" && scp aldc@192.168.22.131:/tmp/s.png /tmp/s.png`

## What Was Done This Session
1. **Deployed kisti-session fix to Jetson** — `git reset --hard origin/kisti-headless` + `sudo cp scripts/kisti-session /usr/local/bin/kisti-session`
   - Fix 1: Ollama warmup model `llama3.2:3b` → `phi4-mini:latest` (3b not on Jetson)
   - Fix 2: startx XAUTHORITY detection + `XDG_RUNTIME_DIR` export for SSH launch mode
2. **Confirmed KiSTI running on Sport mode** — `kisti-session.log` confirms `Mode manager started (SI Drive: Sport)`
3. **Confirmed FLIR → Nextcloud**: `flir_readings` in export list (`duckdb_store.py:618`), syncs same as all telemetry
4. **Confirmed `mode_manager.py:119`** already defaults to `SIDriveMode.SPORT` — Sport screen default is already correct

## IMMEDIATE TODO (start here in order)

### 1. Remove EC weather data display (USER REQUEST — "for now")
EC = Environment Canada weather. Currently fetching and displaying regional weather advisories even while parked.

**Single-point disable**: In `main.py`, comment out the EC poller start (lines 232-236):
```python
# lines 232-236 in main.py
try:
    from sensors.ec_weather import ECWeatherPoller
    ec_poller = ECWeatherPoller()
    ec_poller.start()           # <-- comment this out
except Exception as exc:
    log.info("EC weather poller unavailable: %s", exc)
```

Just change `ec_poller.start()` to `pass  # EC disabled for now`. This leaves `ec_poller = None`, so `ec_available` stays False, and all 4 screens' EC display blocks are automatically silenced.

EC display exists in all 4 screens (guard is `if snap.ec_available and ...`):
- `ui/intelligent_screen.py:482` — ec_forecast_condition top-left text
- `ui/intelligent_screen.py:563` — EC block in `_draw_ec_banner`
- `ui/sport_screen.py:335` — EC block in `_paint_weather_threat`
- `ui/sharp_screen.py:358,609` — EC pill + EC block
- `ui/sharp_screen_track.py:677,732` — EC indicator + block

**After fix**: deploy + restart KiSTI. EC banner gone, baro/pressure threat indicators still work (they use local sensors only).

### 2. Verify Sport screen default looks correct on Jetson
The mode is already Sport at startup (confirmed in logs). But screenshot from this session showed what appears to be Intelligent screen — likely because someone pressed key "1" (Intelligent) earlier.
- After restart from task 1: take a screenshot and confirm Sport screen is showing
- Sport screen shows: DCCD bar (top), technique panel (left 350px), friction ellipse (right), road zones
- If still showing Intelligent despite mode = Sport: check `ui/main_window.py:115` — `_on_si_drive_changed(int(mode_manager.si_drive_mode))` should sync at init

### 3. Fix canonical track_id in auto-import (from v9 — still needed)
**Problem**: `data/track_outlines/` has `d9a909b9-0000-0000-0000-000000000000.json` (hash file) instead of `a1b2c3d4-1006-4000-8006-000000000006.json` (canonical Mission Raceway Park ID).

**Debug step first** — on Jetson:
```bash
ssh aldc@192.168.22.131 "python3 -c \"
import sys; sys.path.insert(0, '/home/aldc/repos/kisti')
from data.duckdb_store import DuckDBStore
from timing.timing_db import TrackDatabase
db = DuckDBStore(); db.open()
tdb = TrackDatabase(db._conn)
for t in tdb.list_tracks(): print(t.track_id, t.name)
\""
```

Then:
1. `ssh aldc@192.168.22.131 "rm ~/repos/kisti/data/track_outlines/d9a909b9-*.json 2>/dev/null; echo deleted"`
2. Restart KiSTI (relaunch.sh)
3. Check: `ssh aldc@192.168.22.131 "ls ~/repos/kisti/data/track_outlines/"` — should be `a1b2c3d4-*.json`

File: `timing/timing_manager.py` — `_auto_import_ztracks()` — the name lookup is `stem_words="mission raceway park"` vs `db_name`. If still saves as hash, trace name matching there.

### 4. Fix track name not showing in ztracks_parser
`name='' city=''` in parser log. The `_extract_string` function tries skips 0,1,2,4 but Mission Raceway `.ztracks` uses a different offset.

**Investigate raw bytes**:
```bash
ssh aldc@192.168.22.131 "python3 -c \"import zipfile; d=zipfile.ZipFile('/home/aldc/tracks/mission_raceway_park.ztracks').read([n for n in zipfile.ZipFile('/home/aldc/tracks/mission_raceway_park.ztracks').namelist() if n.endswith('.tkk')][0]); print(repr(d[0:400]))\""
```
Look for ASCII runs near `<hPtkk` and `<hVnfo` section markers — find the byte offset of the actual track name string.

## Key Files
- `main.py:232-236` — EC poller start (disable here)
- `main.py:119` (`_si_drive = SIDriveMode.SPORT`) — mode_manager default (already correct)
- `ui/main_window.py:115` — `_on_si_drive_changed` sync at init
- `ui/intelligent_screen.py:482,563` — EC forecast text + EC banner block
- `ui/sport_screen.py:335` — EC warning block in `_paint_weather_threat`
- `ui/sharp_screen.py:358,609` — EC pill + EC block
- `ui/sharp_screen_track.py:677,732` — EC indicator + EC block
- `timing/timing_manager.py` — `_auto_import_ztracks()`, name matching
- `tools/ztracks_parser.py` — `_extract_string()` function

## Jetson Commands
- Deploy: `ssh aldc@192.168.22.131 "cd ~/repos/kisti && git fetch origin && git reset --hard origin/kisti-headless && bash ~/repos/kisti/scripts/jetson/relaunch.sh"`
- Log: `ssh aldc@192.168.22.131 "tail -30 /tmp/kisti-session.log"`
- Switch screen: `ssh aldc@192.168.22.131 "DISPLAY=:0 XAUTHORITY=/tmp/serverauth.YqyAI50FSy xdotool key 2"` (1=I, 2=Sport, 3=S#, 4=track)
- Check display: `ssh aldc@192.168.22.131 "ls /tmp/.X*-lock /tmp/serverauth.*"`

## Gotchas
- NEVER `git pull` on Jetson — always `git fetch origin && git reset --hard origin/kisti-headless`
- `DISPLAY=:0` after the latest reboot (was `:1` in v9 — verify on each session start with `ls /tmp/.X*-lock`)
- `XDG_RUNTIME_DIR=/run/user/1000` needed for pactl in SSH sessions
- EC in code = Environment Canada weather (NOT "enterprise" or "demo" EC)
- Test run: `python3 -m pytest tests/ -q --tb=short --ignore=tests/test_voice_integration.py --ignore=tests/test_voice_pipeline.py`
- Sport screen layout: DCCD bar top, technique left 350px, friction ellipse right — no weather temps at top (those are I-screen)
- KiSTI auto-starts after reboot via GDM kisti-session, takes ~60s (Ollama phi4-mini warmup)
