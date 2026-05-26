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
6. **d9a909b9 hash file fix** — `timing/timing_manager.py` `__init__`: removed `track_count() == 0` guard. Seed always runs (idempotent via INSERT OR REPLACE). Root cause was Jetson DuckDB had 1 GPS-learned track → seed skipped → Mission Raceway Park absent → name match failed → hash fallback. Now confirmed: `Seeded 18 tracks, ztracks matching: 19 tracks in DB`, only `a1b2c3d4` in `data/track_outlines/`.

## IMMEDIATE TODO (start here in order)

### 1. RS3 AiM Strada Configuration (BLOCKED on hardware)
- Bind Status element to CAN ID 0x6C2 when AiM Strada 7" arrives
- RS3 Track Maps Import blocked on AiM .mpl sample files

### 3. Brake Quality Feed
- Wire `update_brake_quality()` to track screen from main.py
- See `ui/sharp_screen_track.py` — function exists, not connected

## Jetson State
- Runs: `Parsed mission_raceway_park.ztracks: name='Mission Raceway Park' city='Mission BC' points=156`
- Runs: `Seeded 18 tracks from tracks_seed.json`
- Runs: `ztracks matching: 19 tracks in DB`
- Runs: `Pre-loaded outline from a1b2c3d4-1006-4000-8006-000000000006.json (63 pts)`
- Only `a1b2c3d4-*.json` in `data/track_outlines/` — `d9a909b9` hash file is gone
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
