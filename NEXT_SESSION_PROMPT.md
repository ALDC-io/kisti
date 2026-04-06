# NEXT SESSION PROMPT — KiSTI

**Branch**: `kisti-headless` | **Dir**: `/home/aldc/repos/kisti` | **Jetson**: `ssh aldc@192.168.22.131` (pw: `aldc1234`)
**Tests**: `python3 -m pytest tests/ -q --tb=short --ignore=tests/test_voice_integration.py --ignore=tests/test_voice_pipeline.py`
**Test baseline**: 1247 tests
**Project tracker**: `/home/jkadmin/projects/active/2026-04-05-kisti-weather-intelligence/`

## What Was Done (2026-04-05/06 — Weather Intelligence + Canyon Redesign)

### Weather Intelligence (complete)
- **EC weather poller** (`sensors/ec_weather.py`) — Environment Canada regional alerts, 10-15 min poll
- **Barometric weather engine** (`sensors/weather_engine.py`) — pressure trend → STORM/RAIN_LIKELY/CHANGING
- **DriveBC RWIS poller** (`sensors/drivebc_weather.py`) — 258 road weather stations + road events, highway-aware filtering, ahead-only ready for GPS09
- **Unified alert banners** on all 3 screens — severity-driven, full-width, 20s rotation on Intelligent
- **EC alerts** show actual description with "EC:" prefix (not just "special weather statement")
- **DriveBC events** show "DriveBC: {what} ahead — {detail}" format (point-first, stripped boilerplate via `optimized_description`)
- **Voice/banner sync** — forced repaint before TTS queue so banner is visible when driver hears alert
- Color scheme: white-on-red (STORM/CLOSURE), white-on-blue (EC statement/DriveBC WET), white-on-orange (RAIN_LIKELY/MAJOR)

### Sport Sharp Canyon Redesign (complete)
- **Rewrote `ui/sharp_screen.py`** from track-focused (lap timer, sectors) to canyon-first (dark cockpit)
- **G-force ellipse dominates** — r=170 (2.1x larger), center 400,215, 30-dot trail
- **Dark cockpit**: nearly black when nominal. Escalating visibility on anomaly
- **Header**: balance indicator (L), DCCD arc gauge (C), weather pill (R) — all ghost-dim
- **Left edge**: vertical F/R grip bars (invisible when healthy, yellow/red when degraded)
- **Right edge**: vertical L/C/R road zone bars (surface state from FLIR)
- **Bottom strip**: BARO trend, road zone bar, DriveBC road temp, voice ticker
- **Alert bar**: unchanged severity-driven full-width at y=460..480
- **Track version preserved** as `ui/sharp_screen_track.py` (`SportSharpTrackScreenWidget`) for future K6 toggle

### Other Fixes
- Sport screen: voice ticker moved from top-right (was overlapping FLIR) to y=370 right-aligned
- DriveBC: highway-aware filtering (`DRIVEBC_HIGHWAY` env var), `update_heading()` for GPS09
- DriveBC: `update_position()` for dynamic GPS updates
- Note: Hwy 7 (Lougheed) has zero RWIS stations in DriveBC network

## Prioritized TODO

1. **Sport Sharp polish** — check bottom strip readability, verify DCCD arc renders correctly, test with real IMU data on the road
2. **Sport screen review** — voice ticker at y=370 may still conflict with coaching text at y=418. Needs road testing
3. **DriveBC highway auto-detect** — when GPS09 is installed, match GPS position to highway corridor and call `drivebc_poller.update_highway()` automatically
4. **DriveBC ahead-only** — wire `drivebc_poller.update_heading()` from GPS09 heading data
5. **S# canyon polish** — consider adding ambient temp somewhere (currently only on Intelligent screen)
6. **K6 sub-page toggle** — wire mode_manager to switch between canyon and track S# variants

## Key Files
- `ui/sharp_screen.py` — canyon S# (new, the default)
- `ui/sharp_screen_track.py` — track S# (preserved copy)
- `ui/sport_screen.py` — Sport screen (voice ticker fix)
- `ui/intelligent_screen.py` — Intelligent screen (alert rotation, EC banner)
- `sensors/drivebc_weather.py` — DriveBC RWIS + events poller
- `sensors/ec_weather.py` — Environment Canada poller
- `sensors/weather_engine.py` — barometric trend analysis
- `model/vehicle_state.py` — DiffState with DriveBC + EC fields
- `main.py` — all wiring (DriveBC poller, EC poller, voice/banner sync)

## Architecture Notes
- Alert severity ranking: STORM(50) > CLOSURE(48) > EC warning(45) > ICY road(42) > RAIN_LIKELY(25) > MAJOR event(22) > EC advisory(20) > DriveBC WET(15) > EC statement(10)
- DriveBC: `optimized_description` field has the at-a-glance text. Raw `description` has highway/direction boilerplate
- DriveBC: nearest RWIS station to Coquitlam = Port Mann Bridge Mid Span (Hwy 1, 7.1km)
- `_drivebc_event_banner()` helper duplicated in all 3 screen files (small, not worth a shared module)
- `paint_g_ellipse()` in `ui/g_force_ellipse.py` is radius-parametric — works at r=80 (Sport) and r=170 (S# canyon)
