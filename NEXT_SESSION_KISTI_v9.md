# KiSTI Next Session — v9 (kisti-road-05)

## Working Directory
`/home/aldc/repos/kisti/` (dev machine) | Jetson: `ssh aldc@192.168.22.131` (pw: aldc1234)

## What Was Done (this session)
1. **Fixed `.ztracks` GPS parser** (`tools/ztracks_parser.py`) — root cause: `<hpts` section has 7-byte header before GPS int32 data. Old code tried skip=0 and skip=4, picked "most points" — garbage bytes won. Fixed: try skips (0,4,7,8,12), discard spread > 5°, pick most points among plausible candidates.
2. **Mission Raceway track map working** — 156 real GPS pts → 63 after RDP → clean circuit shape on S# Track screen.
3. **Added GT map style** (`ui/track_map.py`) — `style="schematic"` (thin outline, default) or `style="gt"` (thick road band). Tap map panel (x=480..800, y=90..280) to toggle.
4. **Reverted default to schematic** — GT style was too cluttered; schematic overhead view is cleaner.

## IMMEDIATE TODO (start here)

### 1. Login screen on HDMI — resolve display VT mismatch
**Symptom**: After latest relaunch, HDMI shows a login prompt instead of KiSTI.
**What happened**: relaunch.sh killed existing X on :1, startx restarted on :0 but something messed up the VT assignment.
**Fix attempt**: `ssh aldc@192.168.22.131 "DISPLAY=:0 xdotool key 4"` — may already be working.
**If still broken**: `ssh aldc@192.168.22.131 "sudo chvt 7"` to switch to the VT where X is running. Or check `/tmp/kisti-session.log` for `DISPLAY=:X` line to know which display to use.
**Nuclear option**: `ssh aldc@192.168.22.131 "pkill -f 'python3 main.py'; pkill Xorg; bash ~/repos/kisti/scripts/jetson/relaunch.sh"`

### 2. Fix canonical track_id in auto-import (ordering bug)
**Problem**: `_auto_import_ztracks()` runs before `seed_tracks()` in `__init__`, so `self._track_db` is empty when the hash-based fallback ID is computed. Outline saves as `d9a909b9-0000-0000-0000-000000000000.json` instead of canonical `a1b2c3d4-1006-4000-8006-000000000006.json`.
**Fix**: In `timing/timing_manager.py`, move `_auto_import_ztracks()` call to AFTER `self._track_db.seed_tracks()`. Then the name lookup will find "Mission Raceway Park" and use the canonical ID.
**File**: `timing/timing_manager.py` — look for `_auto_import_ztracks` and `seed_tracks` in `__init__`.
**Test**: After fix, restart Jetson KiSTI, check `data/track_outlines/` — should have `a1b2c3d4-1006-4000-8006-000000000006.json`, not the hash file.

### 3. Track map name not showing
**Problem**: `name='' city=''` in parser log — track name isn't extracted from the `.ztracks` binary.
**Why**: The `_extract_string` function skips=0,1,2,4 looking for printable ASCII, but the Mission Raceway `.ztracks` may use a different encoding or the name is in a different section.
**Investigate**: `ssh aldc@192.168.22.131 "python3 -c \"from tools.ztracks_parser import _section_data; import zipfile; d=zipfile.ZipFile('/home/aldc/tracks/mission_raceway_park.ztracks').read([n for n in zipfile.ZipFile('/home/aldc/tracks/mission_raceway_park.ztracks').namelist() if n.endswith('.tkk')][0]); print(repr(d[0:300]))\""` to inspect raw bytes near name sections.

## Key Files
- `ui/track_map.py` — `paint_track_map(style="schematic"|"gt")` — schematic is default
- `ui/sharp_screen_track.py` — `_map_style`, `mousePressEvent` toggle at `_G_PANEL_X`..`_W`, `_MID_Y0`..`_MID_Y1`
- `timing/timing_manager.py` — `_auto_import_ztracks()`, `_load_first_available_outline()`, `get_timing_data()`
- `tools/ztracks_parser.py` — fixed parser, 43 tests
- `data/track_outlines/` — cached outline JSON files (delete to force regeneration)
- `~/tracks/mission_raceway_park.ztracks` — on Jetson only

## Architecture Notes
- Jetson auto-commits diverge from origin — ALWAYS `git fetch origin && git reset --hard origin/kisti-headless` (never `git pull`)
- Outline pre-load: `_load_first_available_outline()` grabs the first alphabetically sorted `.json` in `data/track_outlines/` — shows map without GPS lock
- GT style: 22px white kerb stroke → 14px dark asphalt overlay → tap panel to toggle
- Test baseline: **1513 passed** (was 1214 at session start)
- Run tests: `python3 -m pytest tests/ -q --tb=short --ignore=tests/test_voice_integration.py --ignore=tests/test_voice_pipeline.py`

## Jetson Commands
- Deploy: `ssh aldc@192.168.22.131 "cd ~/repos/kisti && git fetch origin && git reset --hard origin/kisti-headless && bash ~/repos/kisti/scripts/jetson/relaunch.sh"`
- Screenshot: `ssh aldc@192.168.22.131 "DISPLAY=:0 import -window root /tmp/s.png" && scp aldc@192.168.22.131:/tmp/s.png /tmp/s.png`
- Switch screen: `ssh aldc@192.168.22.131 "DISPLAY=:0 xdotool key 4"` (4=track, 1=intelligent)
- Log: `ssh aldc@192.168.22.131 "tail -30 /tmp/kisti-session.log"`
