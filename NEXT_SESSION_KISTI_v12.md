# KiSTI Next Session — v12 (kisti-road-07)

## Working Directory
`/home/aldc/repos/kisti/` (dev machine) | Jetson: `ssh aldc@192.168.22.131` (pw: aldc1234)
Branch: `kisti-headless` | Test baseline: **1513 passed**

## Display Info (changes each reboot)
- Check: `ssh aldc@192.168.22.131 "ls /tmp/.X*-lock /tmp/serverauth.*"`
- Last confirmed: `DISPLAY=:0`, `XAUTHORITY=/tmp/serverauth.ik2VYbBsyP` (will change after reboot)
- Screenshot: check XAUTHORITY first, then:
  `ssh aldc@192.168.22.131 "DISPLAY=:0 XAUTHORITY=/tmp/serverauth.ik2VYbBsyP import -window root /tmp/s.png" && scp aldc@192.168.22.131:/tmp/s.png /tmp/s.png`
- Switch screen: `ssh aldc@192.168.22.131 "DISPLAY=:0 XAUTHORITY=... xdotool key N"` (1=I, 2=Sport, 3=S#, 4=track)

## What Was Done This Session (kisti-road-07)
1. **Sport screen bar labels renamed** — `ui/sport_screen.py`: `BALANCE` → `BLNCE`, `TRAIL %` → `TRAILB`. Committed, deployed, screenshot confirmed.
2. **CCX daily brief flood fixed (temporary)** — CCX sidecar was re-injecting the Zeus daily brief as a `block` decision on every tool use (PostToolUse hook). Root cause: `format_stop_block()` in `message_poller.py` returns ALL unread messages; Zeus poller re-adds them on every poll cycle even after `/api/inbox` clears in-memory state (mark_as_read on Zeus not taking effect). Temporary fix: `curl -X POST "http://localhost:7432/admin/pause?user=jkadmin"` — pauses CCX notifications for this session only. Will need a proper fix (see TODO #1 below).

## IMMEDIATE TODO (start here in order)

### 1. Fix CCX daily brief re-flooding (LOW PRIORITY — dev annoyance)
**Symptom**: Zeus daily brief appears as a `block` decision on every PostToolUse and Stop hook, flooding the conversation.
**Root cause**: `message_poller.py` `_poll_loop()` unconditionally re-adds all messages from Zeus on every poll — so even after `/api/inbox` marks them read in memory, next poll re-fetches and re-adds them. The Zeus `mark_messages_read()` fire-and-forget call (`/api/inbox` → `mark_messages_read`) is apparently not removing them from Zeus's `GET /api/presence/messages?unread=true` response.
**Fix approach**:
- Check `/home/aldc/repos/ccx/src/ccx/workers/message_poller.py` `_poll_loop()` — add a `_read_ids` set and skip already-seen IDs even if Zeus returns them again
- OR check Zeus API `/api/presence/messages` — verify `mark_messages_read()` actually filters them from subsequent polls
- Repo: `/home/aldc/repos/ccx/`
- CCX sidecar running at `http://localhost:7432`
- Re-pause if needed: `curl -X POST "http://localhost:7432/admin/pause?user=jkadmin"`

### 2. RS3 AiM Strada Configuration (BLOCKED on hardware)
- Bind Status element to CAN ID 0x6C2 when AiM Strada 7" arrives
- RS3 Track Maps Import blocked on AiM .mpl sample files

### 3. Brake Quality Feed
- Wire `update_brake_quality()` to track screen from main.py
- See `ui/sharp_screen_track.py` — function exists, not connected

## Jetson State
- KiSTI running on `DISPLAY=:0`
- `Seeded 18 tracks from tracks_seed.json`
- `ztracks matching: 19 tracks in DB`
- `Pre-loaded outline from a1b2c3d4-1006-4000-8006-000000000006.json (63 pts)`
- Only `a1b2c3d4-*.json` in `data/track_outlines/`
- EC weather: disabled
- Sport screen labels: BLNCE, TRAILB, DCCD, F GRIP, R GRIP

## Key Files
- `ui/sport_screen.py:429,437` — BLNCE / TRAILB labels
- `main.py:234` — EC poller disabled
- `tools/ztracks_parser.py` — `_extract_string()` alphabetic scan
- `timing/timing_manager.py` — always-seed fix, `_auto_import_ztracks()`
- `data/track_outlines/a1b2c3d4-1006-4000-8006-000000000006.json` — canonical outline (63 pts)

## Jetson Commands
- Deploy: `ssh aldc@192.168.22.131 "cd ~/repos/kisti && git fetch origin && git reset --hard origin/kisti-headless && bash ~/repos/kisti/scripts/jetson/relaunch.sh"`
- Log: `ssh aldc@192.168.22.131 "strings /tmp/kisti-session.log | tail -40"`
- Short deploy alias: `ssh aldc@192.168.22.131 "~/k"`

## Gotchas
- NEVER `git pull` on Jetson — always `git fetch origin && git reset --hard origin/kisti-headless`
- `DISPLAY` number changes per reboot — always check `ls /tmp/.X*-lock`
- EC in code = Environment Canada weather (NOT enterprise or demo)
- `_extract_string` uses `.isalpha()` scan — NOT fixed skip offsets
- DuckDB single-writer: can't query while KiSTI running — use `strings /tmp/kisti-session.log | grep`
- Test run: `python3 -m pytest tests/ -q --tb=short --ignore=tests/test_voice_integration.py --ignore=tests/test_voice_pipeline.py`
- mode_manager defaults to SPORT — if showing Intelligent after restart, it's a manual key press
- CCX flood: if daily brief re-appears on every tool use, run `curl -X POST "http://localhost:7432/admin/pause?user=jkadmin"` to suppress for session
