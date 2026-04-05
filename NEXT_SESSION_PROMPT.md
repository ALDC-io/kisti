# NEXT SESSION PROMPT — KiSTI Screen Redesign (Phases 3-6)

**Branch**: `kisti-headless` | **Dir**: `/home/aldc/repos/kisti` | **Jetson**: `ssh aldc@192.168.22.131` (pw: `aldc1234`)
**Tests**: `python3 -m pytest tests/ -q --tb=short --ignore=tests/test_voice_integration.py --ignore=tests/test_voice_pipeline.py`
**Baseline**: 1173 tests (1162 passed, 11 skipped) — up from 1125 after Phase 1-2

---

## Before starting work
1. Read `docs/SCREEN_REDESIGN_PLAN.md` — full research + design spec (500 lines)
2. Read the plan at `~/.claude/plans/steady-dreaming-kitten.md` — 6-phase implementation plan
3. Run tests: `pytest tests/ -q --tb=short --ignore=tests/test_voice_integration.py --ignore=tests/test_voice_pipeline.py`

## What was built (this session — kisti-screen-redesign Phase 1-2)

### Research Phase (6 parallel agents)
- Professional motorsport displays (AiM, MoTeC, F1)
- G-force visualization best practices
- Understeer/oversteer detection methods
- Brake quality + traction loss visualization
- Altitude/corner classification/sector G profiling
- Driver feedback loops (sports science, coaching theory)
- **Key findings**: dark cockpit, friction ellipse not circle, understeer as trend not instant, coach not dashboard, delta timer is #1 proven real-time tool
- Full research in `docs/SCREEN_REDESIGN_PLAN.md`

### Phase 1: Analysis Modules (COMPLETE)
- **`coaching/balance_analyzer.py`** — understeer/oversteer via bicycle model (gyro Z vs expected yaw from steering+speed). BalanceAnalyzer class with 5-sample rolling average, speed gate 30 km/h. 28 tests.
- **`coaching/grip_analyzer.py`** — per-axle grip from wheel speed vs GPS ground truth. GripAnalyzer class with slip ratio, advisory at 10%/20%. 20 tests.
- **`coaching/technique_analyzer.py`** — EXTENDED: added `longitudinal_g` to `_Sample`, brake G quality analysis (peak G, consistency), enhanced trail braking detection (G-based, not just steering angle). All 8 existing tests pass.

### Phase 2: Shared Component + Bug Fix (COMPLETE)
- **`ui/g_force_ellipse.py`** — friction ellipse paint function. Asymmetric envelope (1.0g lat, 1.2g brake, 0.7g accel), fading trail, color-coded dot (green/yellow/red by G% of envelope), understeer/oversteer background tint. Follows `road_condition.py` paint function pattern.
- **`ui/sport_screen.py`** — Fixed `badge_tw` bug at line 237 (was undefined, set to 60).

## TODO — Phases 3-6 (prioritized)

### Phase 3: Intelligent Screen — Minor Enhancements
- [ ] Add GPS altitude + satellite count to status section (right side)
  - `snap.gps_altitude_m` as "ELEV XXX m", `snap.gps_satellites` with green/gray dot
  - Stale: "---" when `snap.is_gps_stale()`
- [ ] Add mini G-dot (radius=40, no trail) in lower-right of status section
  - Call `paint_g_ellipse(p, cx, cy, 40, snap, deque(), max_trail_dots=0)`
- **File**: `ui/intelligent_screen.py`

### Phase 4: Sport Screen — Major Redesign (BIGGEST TASK)
- [ ] Replace `_paint_performance_bars()` with new technique panel:
  - Brake G bar with peak hold (replaces brake pressure bar)
  - Balance bar — centered, green/yellow/red (replaces yaw rate bar)
  - Trail brake % bar (new)
  - Remove lateral G bar (redundant with G-ellipse)
- [ ] Add drivetrain cluster — DCCD + front/rear grip bars in top band
- [ ] Replace `_paint_g_force_circle()` with `paint_g_ellipse()` call (radius=130, 20 trail dots)
- [ ] Add public methods: `update_balance()`, `update_grip()`, `update_brake_analysis()`
- **File**: `ui/sport_screen.py`
- **Dependencies**: Phase 1 analyzers + Phase 2 ellipse (both done)

### Phase 5: Sport Sharp Screen — Targeted Upgrades
- [ ] Replace `_draw_g_force_circle()` with `paint_g_ellipse()` (radius=80, 10 trail dots, MODE_SS_ACCENT)
- [ ] Replace ROAD vital with GRIP mini-bar (3-zone color bar from `surface_state_*`)
- [ ] Add sector brake quality dots (green/yellow/red per sector based on peak brake G vs best)
- [ ] Dark cockpit safety vitals — dim gray when normal, bright on warning only
- **File**: `ui/sharp_screen.py`

### Phase 6: Main.py Integration
- [ ] Import + instantiate `BalanceAnalyzer`, `GripAnalyzer` in main.py
- [ ] Extend `_coaching_tick()` (~line 832) — feed analyzers, pass results to screens
- [ ] Wire `update_balance()` and `update_grip()` to Sport + Sharp screens
- [ ] Run full test suite — verify >= 1173 tests, no regressions
- **File**: `main.py` (~line 832-854 coaching timer section)

## Key files
- `docs/SCREEN_REDESIGN_PLAN.md` — research + design (ASCII layouts, element specs, cross-screen consistency)
- `coaching/balance_analyzer.py` — BalanceAnalyzer (feed, current_ratio, coaching_text)
- `coaching/grip_analyzer.py` — GripAnalyzer (feed, front_grip_pct, rear_grip_pct, advisory)
- `coaching/technique_analyzer.py` — TechniqueAnalyzer (feed, analyze) — extended this session
- `ui/g_force_ellipse.py` — `paint_g_ellipse()` shared paint function
- `ui/road_condition.py` — existing shared paint functions (pattern to follow)
- `ui/theme.py` — color constants
- `model/vehicle_state.py` — DiffState (all sensor fields, staleness checks)
- `main.py:832-854` — coaching timer wiring (where to add new analyzers)

## Architecture notes

### How coaching data flows
```
DiffStateBridge (20-50Hz CAN) → bridge.snapshot()
    ↓
1Hz QTimer (_coaching_timer in main.py)
    ├── TechniqueAnalyzer.feed(snap) → analyze() → (text, sentiment)
    ├── BalanceAnalyzer.feed(snap) → current_ratio(), coaching_text()   [NEW - wire in Phase 6]
    ├── GripAnalyzer.feed(snap) → front/rear_grip_pct(), advisory()     [NEW - wire in Phase 6]
    ↓
Screen.update_coaching(text, sentiment)      — existing
Screen.update_balance(ratio, text, sentiment) — NEW method needed on Sport/Sharp
Screen.update_grip(front_pct, rear_pct)       — NEW method needed on Sport/Sharp
```

### paint_g_ellipse() API
```python
paint_g_ellipse(
    p: QPainter,          # active painter
    cx, cy: float,        # center coords
    radius: float,        # pixels for 1.0g lateral reference
    snap: DiffState,      # current state (or None)
    trail: deque,         # (lat_g, lon_g) ring buffer — caller-owned
    balance_ratio=1.0,    # from BalanceAnalyzer (1.0=neutral)
    max_trail_dots=20,    # 0=no trail (Intelligent mini), 10=Sharp, 20=Sport
    accent_color=CYAN,    # trail dot color (CYAN for Sport, MODE_SS_ACCENT for Sharp)
)
```

## Don't Repeat
- FLIR `temps_updated` sends `RoadSurfaceTemps` object, not 3 floats
- `_last_emit` must be instance-level on PatternEngine, not class-level
- `badge_tw` was undefined in sport_screen.py — FIXED this session (set to 60)
- Existing `_snap()` test helpers don't set `imu_accel_x` — new brake G code must guard with `peak_g > 0.1` before suggesting "brake harder" (already implemented)
- Enhanced trail brake detection uses `or` (not `and`) with the existing steering check — both paths should detect trail braking
- All 3 screens are pure QPainter — no composite QWidget layouts. Follow `road_condition.py` paint function pattern for shared rendering
- Balance analyzer uses 5-sample rolling average at 1Hz — trend indicator, not instant. Single outlier doesn't flip classification
- Grip analyzer speed gate is 10 km/h (lower than balance's 30 km/h) — wheel speed comparison works at lower speeds
- `classify_surface()` is the single source of truth for surface classification thresholds
- Rsync to `~/repos/kisti` on Jetson, NOT `~/kisti`
