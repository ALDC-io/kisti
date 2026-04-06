# NEXT SESSION PROMPT — KiSTI

**Branch**: `kisti-headless` | **Dir**: `/home/aldc/repos/kisti` | **Jetson**: `ssh aldc@192.168.22.131` (pw: `aldc1234`)
**Tests**: `python3 -m pytest tests/ -q --tb=short --ignore=tests/test_voice_integration.py --ignore=tests/test_voice_pipeline.py`
**Test baseline**: 1247 tests
**Project tracker**: `/home/jkadmin/projects/active/2026-04-05-kisti-weather-intelligence/`

## What Was Done (2026-04-06 — Gemma 4 Evaluation + Demo Mode + Road Weather Abstraction)

### Gemma 4 Evaluation (COMPLETE — separate project)
- **Project**: `/home/aldc/projects/active/2026-04-06-kisti-gemma4-evaluation/`
- **Archived**: `Nextcloud/CCE_projects/06-kisti/2026-04-06-kisti-gemma4-evaluation/`
- **Finding**: Gemma 4 E4B (8.0B actual) needs 9.9 GiB — OOM. E2B (5.1B actual) needs 7.3 GiB — OOM. Both too large for 8GB Jetson with full sensor stack
- **Decision**: Keep llama3.2:3b. Persona-first + frontier (Claude Haiku via WiFi) is correct architecture
- **Side win**: Ollama updated 0.18.2 → 0.20.2 on Jetson

### Demo Mode Improvements
- **`.demo-mode` flag file** — touch `~/repos/kisti/.demo-mode` to enable demo without editing session script. Auto-enables `--demo`, `--sim-ambient`, `--lock-mode`
- **`--lock-mode`** — locks SI-Drive mode (no auto-cycling), use SIGUSR1 to change manually
- **Event simulator** (`sensors/event_simulator.py`) — replaces real EC + DriveBC pollers in demo mode with scripted weather scenarios on a loop

### Road Weather Abstraction (new files, not yet wired)
- `sensors/road_weather_base.py` — base class for multi-province road weather providers
- `sensors/road_weather_manager.py` — manages multiple providers, GPS-based auto-selection
- `sensors/us_state_lookup.py` — US state detection for future cross-border road weather
- `model/vehicle_state.py` — added `road_weather_source` field to DiffState

### Benchmark Script
- `scripts/llm_benchmark.py` — 20 KiSTI driving prompts, TTFT + total latency measurement, quality A/B pairs. Created for Gemma 4 eval but reusable for future model testing

## Prioritized TODO

1. **Sport Sharp polish** — road test bottom strip readability, verify DCCD arc renders correctly with real IMU data
2. **Sport screen review** — voice ticker at y=370 may conflict with coaching text at y=418; needs road testing
3. **DriveBC highway auto-detect** — wire GPS09 position to auto-detect highway corridor and call `drivebc_poller.update_highway()`
4. **DriveBC ahead-only filtering** — wire `drivebc_poller.update_heading()` from GPS09 heading data
5. **Wire road weather manager** — connect `road_weather_manager.py` to main.py so GPS auto-selects province provider
6. **S# canyon polish** — consider adding ambient temp display (currently only on Intelligent screen)
7. **K6 sub-page toggle** — wire mode_manager to switch between canyon/track S# variants

## Key Files
- `main.py` — demo mode flag file, lock-mode, event simulator wiring
- `sensors/event_simulator.py` — demo weather event loop
- `sensors/road_weather_base.py` — multi-provider base class (NEW, not wired)
- `sensors/road_weather_manager.py` — GPS-based provider selection (NEW, not wired)
- `scripts/llm_benchmark.py` — LLM benchmark tool (NEW)
- `ui/sharp_screen.py` — canyon S# (dark cockpit)
- `ui/sharp_screen_track.py` — track S# (preserved)
- `sensors/drivebc_weather.py` — DriveBC RWIS + events
- `sensors/ec_weather.py` — Environment Canada poller
- `model/vehicle_state.py` — DiffState with road_weather_source field

## Architecture Notes
- Alert severity: STORM(50) > CLOSURE(48) > EC warning(45) > ICY(42) > RAIN_LIKELY(25) > MAJOR(22) > EC advisory(20) > DriveBC WET(15) > EC statement(10)
- Demo mode event simulator runs independent of real pollers — no network needed for trade show
- Road weather manager designed for multi-province: DriveBC (BC), 511AB (AB), IEM-IA (Iowa), 511ON (Ontario). GPS determines active provider
- `paint_g_ellipse()` in `ui/g_force_ellipse.py` is radius-parametric — works at r=80 (Sport) and r=170 (S# canyon)
