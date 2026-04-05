# KiSTI - Development Conventions

KiSTI is a visual telemetry + AI co-driver system for a 2014 STI. Runs on Jetson Orin Nano, outputs to Kenwood Excelon 800x480 HDMI. All rendering is QPainter-based (PySide6). No external map APIs.

## Architecture

- **Offline Zeus Memory edge node** — all data stored locally in DuckDB, syncs to ALDC Zeus Memory when WiFi available
- **Pure QPainter rendering** — no composite QWidget layouts. All screens are single QPainter paint loops
- **Shared paint functions** — `ui/road_condition.py`, `ui/g_force_ellipse.py` are module-level functions, not QWidgets
- **1Hz coaching timer** — analysis runs at 1Hz via QTimer, results cached and rendered at 20Hz paint rate
- **CAN bus** — Link ECU via python-can (socketcan). Mock fallback for development

## Key Rules

### Rendering
- All 3 screens (Intelligent, Sport, Sport Sharp) are pure QPainter — follow existing paint function pattern
- Shared rendering: module-level functions in `ui/` (see `road_condition.py` pattern)
- No numpy in paint path — pure Python math only (Jetson 344MB RAM constraint)
- Dark cockpit: normal state invisible, only abnormal demands attention

### Testing
- `python3 -m pytest tests/ -q --tb=short --ignore=tests/test_voice_integration.py --ignore=tests/test_voice_pipeline.py`
- Test count must only go up — check `PROGRESS.md` for current baseline
- `_snap()` test helpers: DiffState with minimal fields. Guard analysis code for zero/missing fields

### Analysis Modules
- Pure Python, no Qt dependencies — `coaching/balance_analyzer.py`, `coaching/grip_analyzer.py`, `coaching/technique_analyzer.py`
- Speed gates: balance 30 km/h, grip 10 km/h
- Rolling averages at 1Hz — trend indicators, not instant values

### Data Flow
```
DiffStateBridge (20-50Hz CAN) -> bridge.snapshot()
    -> 1Hz QTimer (_coaching_timer in main.py)
        -> TechniqueAnalyzer.feed(snap)
        -> BalanceAnalyzer.feed(snap)
        -> GripAnalyzer.feed(snap)
    -> Screen.update_coaching/balance/grip()
    -> paintEvent (20Hz)
```

### Deployment
- Jetson: `ssh aldc@192.168.22.131` (pw: `aldc1234`)
- Rsync to `~/repos/kisti` on Jetson (NOT `~/kisti`)
- Kill existing instances before restart: `pkill -f 'python3 main.py'`
- Branch: `kisti-headless`

### Don't Repeat (Critical)
- FLIR `temps_updated` sends `RoadSurfaceTemps` object, not 3 floats
- `_last_emit` must be instance-level on PatternEngine, not class-level
- Two KiSTI instances will deadlock on FLIR/DuckDB — always kill before restart
- PulseAudio: paplay → explicit sink. Use plughw:0 for mono USB speakers
- OpenCV Y16: `.view(uint16).reshape(120,160)` for PureThermal radiometric
- Test fixtures: `longitudinal_g` defaults to 0.0 — guard brake G analysis with `if peak_g > 0.1`
- Rolling window outliers must be mild (10-20% deviation) or they'll flip classification

### Session Workflow
- **Start**: Read `PROGRESS.md` + `NEXT_SESSION_PROMPT.md`
- **End**: Update `PROGRESS.md`, run `/learn` to capture to Zeus Memory, update `NEXT_SESSION_PROMPT.md`
- **Learnings**: Use `/learn` command (works in both CLI and web via MCP tools)
