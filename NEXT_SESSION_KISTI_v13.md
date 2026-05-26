# KiSTI Next Session — v13 (kisti-road-09)

## Working Directory
`/home/aldc/repos/kisti/` (dev machine) | Jetson: `ssh aldc@192.168.22.131` (pw: aldc1234)
Branch: `kisti-headless` | Test baseline: **1513 passed**

## Display Info (changes each reboot)
- Check: `ssh aldc@192.168.22.131 "ls /tmp/.X*-lock /tmp/serverauth.*"`
- Last confirmed: `DISPLAY=:0`, `XAUTHORITY=/tmp/serverauth.ik2VYbBsyP` (will change after reboot)
- Screenshot: check XAUTHORITY first, then:
  `ssh aldc@192.168.22.131 "DISPLAY=:0 XAUTHORITY=/tmp/serverauth.ik2VYbBsyP import -window root /tmp/s.png" && scp aldc@192.168.22.131:/tmp/s.png /tmp/s.png`
- Switch screen: `ssh aldc@192.168.22.131 "DISPLAY=:0 XAUTHORITY=... xdotool key N"` (1=I, 2=Sport, 3=S#, 4=track)

## What Was Done Last Session (2026-04-18 NAS Backup Expansion)
1. **NAS backup now covers 3 types** — DuckDB (existing), sessions/Parquet queue daily 2AM, system image weekly Sunday 3AM
2. **sync_to_cloud.py expanded** — `_nas_pick_iface()` WiFi-first routing, `_nas_put()` reusable helper, `sync_nas_sessions()`, `sync_nas_image()`. `sync_all` includes sessions automatically.
3. **Shell wrapper fixed** — `jetson_sync_cloud.sh` now passes `"$@"` to Python
4. **Jetson crontab updated** — One new Sunday 3AM entry for `--nas-image`

## IMMEDIATE TODO (start here in order)

### 1. RS3 AiM Strada Configuration (BLOCKED on hardware)
- Bind Status element to CAN ID 0x6C2 when AiM Strada 7" arrives
- RS3 Track Maps Import blocked on AiM .mpl sample files

### 2. Track Timing Activation
- Lap beacon / timing gate configuration (when hardware ready)
- Brake quality dots will activate automatically on track with timing data

## Jetson State
- KiSTI running on `DISPLAY=:0`
- `Seeded 18 tracks from tracks_seed.json`
- `ztracks matching: 19 tracks in DB`
- `Pre-loaded outline from a1b2c3d4-1006-4000-8006-000000000006.json (63 pts)`
- Only `a1b2c3d4-*.json` in `data/track_outlines/`
- EC weather: disabled
- Sport screen labels: BLNCE, TRAILB, DCCD, F GRIP, R GRIP
- NAS backup: daily 2AM (DuckDB + sessions), Sunday 3AM (system image) → NAS at 192.168.22.220

## Key Files
- `scripts/sync_to_cloud.py` — _nas_pick_iface(), _nas_put(), sync_nas_sessions(), sync_nas_image()
- `scripts/jetson_sync_cloud.sh` — now forwards `"$@"` to Python
- `ui/sport_screen.py:429,437` — BLNCE / TRAILB labels
- `main.py:234` — EC poller disabled
- `tools/ztracks_parser.py` — `_extract_string()` alphabetic scan
- `timing/timing_manager.py` — always-seed fix, `_auto_import_ztracks()`
- `data/track_outlines/a1b2c3d4-1006-4000-8006-000000000006.json` — canonical outline (63 pts)

## Jetson Commands
- Deploy: `ssh aldc@192.168.22.131 "cd ~/repos/kisti && git fetch origin && git reset --hard origin/kisti-headless && bash ~/repos/kisti/scripts/jetson/relaunch.sh"`
- Log: `ssh aldc@192.168.22.131 "strings /tmp/kisti-session.log | tail -40"`
- Short deploy alias: `ssh aldc@192.168.22.131 "~/k"`
- Check NAS backup log: `ssh aldc@192.168.22.131 "tail -20 /tmp/kisti_sync_cloud.log"`

## Gotchas
- NEVER `git pull` on Jetson — always `git fetch origin && git reset --hard origin/kisti-headless`
- `DISPLAY` number changes per reboot — always check `ls /tmp/.X*-lock`
- EC in code = Environment Canada weather (NOT enterprise or demo)
- `_extract_string` uses `.isalpha()` scan — NOT fixed skip offsets
- DuckDB single-writer: can't query while KiSTI running — use `strings /tmp/kisti-session.log | grep`
- Test run: `python3 -m pytest tests/ -q --tb=short --ignore=tests/test_voice_integration.py --ignore=tests/test_voice_pipeline.py`
- mode_manager defaults to SPORT — if showing Intelligent after restart, it's a manual key press
- CCX flood: if daily brief re-appears on every tool use, run `curl -X POST "http://localhost:7432/admin/pause?user=jkadmin"` to suppress for session
- NAS backup: only ONE new Sunday cron needed — sync_all already includes sessions; don't add redundant daily --nas-sessions cron
