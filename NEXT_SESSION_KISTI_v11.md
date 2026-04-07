# KiSTI Next Session — v11 (kisti-road-06)

## Working Directory
`/home/aldc/repos/kisti/` (dev machine) | Jetson: `ssh aldc@192.168.22.131` (pw: aldc1234)
Branch: `kisti-headless` | Test baseline: **1513 passed**

## Display Info (changes each reboot)
- Check which display is active: `ssh aldc@192.168.22.131 "ls /tmp/.X*-lock /tmp/serverauth.*"`
- Last confirmed: `DISPLAY=:1` (may change after reboot)
- Screenshot: `ssh aldc@192.168.22.131 "DISPLAY=:1 XAUTHORITY=/tmp/serverauth.EuPe245HQJ import -window root /tmp/s.png" && scp aldc@192.168.22.131:/tmp/s.png /tmp/s.png`
  (Verify XAUTHORITY path with ls command above first)

## What Was Done This Session (kisti-road-06 continuation)
1. **EC weather poller disabled** — `main.py:234` `ec_poller.start()` → `pass # EC disabled for now`. Deployed + confirmed: no EC banner on any screen.
2. **Sport screen verified** — Screenshot confirmed Sport screen default: DCCD bar top, technique panel left, friction ellipse right, L/C/R zones.
3. **Canonical track outline pre-committed** — `data/track_outlines/a1b2c3d4-1006-4000-8006-000000000006.json` (63 pts). Logs confirm: `Pre-loaded outline from a1b2c3d4-1006-4000-8006-000000000006.json (63 pts)`.
4. **`_extract_string` fixed** — `tools/ztracks_parser.py`. Scans byte-by-byte for first alphabetic char run. Now parses `name='Mission Raceway Park'  city='Mission BC'` correctly. Deployed and confirmed in Jetson logs.
5. **Silent exception fix** — `timing/timing_manager.py` `_auto_import_ztracks` now logs a warning instead of swallowing exception when track name lookup fails.

## IMMEDIATE TODO (start here in order)

### 1. Fix `_auto_import_ztracks` canonical track_id match (LOW PRIORITY — cosmetic)
The hash file `d9a909b9-0000-0000-0000-000000000000.json` is still written alongside the canonical `a1b2c3d4` file on each restart. Root cause: track `list_tracks()` fails or returns empty when `_auto_import_ztracks()` runs at startup (DuckDB not yet seeded, or timing race). Functionally benign since canonical is committed to git and always loaded.

**If you want to fix it:**
- Check `timing/timing_manager.py` `_auto_import_ztracks()` — the `tdb.list_tracks()` call
- Check if `TrackDatabase.list_tracks()` throws when `tracks` table doesn't exist
- Check `data/tracks_seed.json` — is Mission Raceway Park there? Does the seed run before `_auto_import_ztracks`?
- Warning in log: `Could not load track names for ztracks matching: <exception text>`

### 2. RS3 AiM Strada Configuration (BLOCKED on hardware)
- Bind Status element to CAN ID 0x6C2 when AiM Strada 7" arrives
- RS3 Track Maps Import blocked on AiM .mpl sample files

### 3. Brake Quality Feed
- Wire `update_brake_quality()` to track screen from main.py
- See `ui/sharp_screen_track.py` — function exists, not connected

## Jetson State
- Runs: `Parsed mission_raceway_park.ztracks: name='Mission Raceway Park' city='Mission BC' points=156`
- Runs: `Pre-loaded outline from a1b2c3d4-1006-4000-8006-000000000006.json (63 pts)`
- Two outline files in `data/track_outlines/`: `a1b2c3d4-*.json` (canonical, correct) + `d9a909b9-*.json` (hash, written by broken name match — benign)
- EC weather: disabled (no EC banner anywhere)
- Sport screen: confirmed default on startup

## Key Files
- `main.py:234` — EC poller disabled (`pass  # EC disabled for now`)
- `tools/ztracks_parser.py` — `_extract_string()` alphabetic scan fix
- `timing/timing_manager.py` — `_auto_import_ztracks()`, `_load_first_available_outline()`
- `data/track_outlines/a1b2c3d4-1006-4000-8006-000000000006.json` — pre-committed canonical outline (63 pts)
- `data/tracks_seed.json` — Mission Raceway Park seed entry

## Jetson Commands
- Deploy: `ssh aldc@192.168.22.131 "cd ~/repos/kisti && git fetch origin && git reset --hard origin/kisti-headless && bash ~/repos/kisti/scripts/jetson/relaunch.sh"`
- Log: `ssh aldc@192.168.22.131 "strings /tmp/kisti-session.log | tail -40"`
- Switch screen: `ssh aldc@192.168.22.131 "DISPLAY=:1 XAUTHORITY=/tmp/serverauth.EuPe245HQJ xdotool key 2"` (1=I, 2=Sport, 3=S#, 4=track)
- Short deploy alias: `ssh aldc@192.168.22.131 "~/k"` (if ~/k script exists)

## Gotchas
- NEVER `git pull` on Jetson — always `git fetch origin && git reset --hard origin/kisti-headless`
- `DISPLAY` number changes per reboot — always check `ls /tmp/.X*-lock`
- EC in code = Environment Canada weather (NOT "enterprise" or "demo" EC)
- `_extract_string` now uses `.isalpha()` scan — NOT fixed skip offsets (committed to `tools/ztracks_parser.py`)
- DuckDB single-writer: can't query DuckDB while KiSTI is running — use `strings /tmp/kisti-session.log | grep` instead
- Test run: `python3 -m pytest tests/ -q --tb=short --ignore=tests/test_voice_integration.py --ignore=tests/test_voice_pipeline.py`
- mode_manager defaults to SPORT — if showing Intelligent after restart, it's a manual key press, not a bug
