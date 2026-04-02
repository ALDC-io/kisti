# KiSTI — Next Session Prompt (kisti-26: Coaching Screens)

**Working dir**: `/home/aldc/repos/kisti/`
**Jetson**: `192.168.22.131` (user `aldc`). SSH: `ssh aldc@192.168.22.131`
**Test baseline**: 895 tests, all passing
**Branch**: `kisti-headless`
**Deploy**: `bash scripts/deploy-to-jetson.sh`
**Project Plan**: `/home/aldc/projects/active/2026-04-02-kisti-coaching-screens/README.md`

---

## What Was Done (kisti-25b)

Screen redesign complete. All 3 SI-Drive screens are clean, readable, deployed:
- **Sport**: G-force circle (r=140, 100-dot trail) + 4 perf bars + DCCD/FLIR top strip
- **Sport#**: Delta bar + timing panel (left) + G-force circle (right) + sectors + safety vitals
- **Intelligent**: Weather card + road surface temp + status strip (Surface primary, SLIP, DCCD compact)
- Full-page FLIR tint (alpha 15) on all 3 screens
- FLIR is single forward-facing road camera (grill-mounted), uses `brake_temp_fl` as proxy field

## What Needs Doing (6 Phases)

The screens show numbers. They don't coach. We have 15+ AI/sensor capabilities wired and operational — but invisible on the display. This project transforms the screens from passive telemetry gauges into an active AI co-driver.

### Phase 1: Wire TimingManager to Sport# (THE #1 GAP)
**Problem**: `SportSharpScreenWidget.update_timing(data)` exists but is NEVER CALLED from main.py. The timing panel permanently shows "--:--.---".

**Key files**:
- `main.py` ~line 375-445: TimingManager wired, emits `lap_completed` / `sector_completed` signals
- `ui/sharp_screen.py` line 196-205: `update_timing(timing_data: dict)` accepts timing dict
- `timing/timing_manager.py`: GPS-based lap/sector detection
- `can/kisti_can.py`: MockCanGenerator needs mock timing data for demo mode

**Approach**:
1. Find where TimingManager signals connect in main.py
2. Add slot that calls `sharp_screen.update_timing()` with the timing dict
3. Add mock timing data to MockCanGenerator (fake laps ~90s, 4 sectors, delta +/-2s)
4. Test: Sport# displays live timing during demo rotation

### Phase 2: Voice Activity Ticker (All 3 Screens)
**Problem**: Voice pipeline speaks via TTS but nothing appears on screen.

**Approach**:
- Add `text_output` signal to VoiceManager (check if `speak()` already emits one)
- Shared `deque[str](maxlen=3)` in main.py, route to all 3 screens
- Paint as dim text overlay (14pt minimum)

### Phase 3: Sport Technique Feedback
**Problem**: Sport shows raw G/brake/steer values but doesn't analyze driving technique.

**Approach**:
- New `coaching/technique_analyzer.py` — 30s rolling window of telemetry
- Metrics: brake consistency (std dev), steering smoothness (jerk), trail braking quality
- 1Hz refresh, single coaching line on Sport screen

### Phase 4: Intelligent Coaching + Conditions to Actions
**Problem**: CoachingLevel exists (K5 cycles FULL/MODERATE/MINIMAL) but screen ignores it.

**Approach**:
- Coaching text panel on Intelligent
- FULL: proactive tips ("Road 3C — reduce corner speed, grip down ~15%")
- MODERATE: observations ("Smooth braking that corner")
- MINIMAL: alerts only
- Surface edge memory trends (last 3 sessions)

### Phase 5: Sport# Sector Analysis
**Problem**: Sectors show green/red time blocks but don't say WHERE time was lost.

**Approach**:
- Compare brake point / corner speed to best lap
- Small insight text below each sector block

### Phase 6: Integration + Jetson Verification
- Full test suite (895+ tests), deploy, arm's-length readability check

## Architecture Notes

- **QPainter only** — no QWidget/QLabel (compositorless X11, TopStatusBar ghost text bug)
- **1Hz coaching refresh** — cache in instance var, QTimer at 1000ms, don't query DuckDB in paintEvent
- **Voice ticker as shared deque** — main.py owns the deque, screens paint from it

## Don't Repeat
- Widget with parent=self but not in layout paints at (0,0). Remove instead of hide.
- Always clear `__pycache__` on Jetson deploy
- Color IS the indicator — no redundant text labels
- Full-page tint > partial colored strips
- QPainter drawRect() inherits current brush — always setBrush(NoBrush) before border-only rects
- Pycache race condition: old .pyc loads instead of new .py on Jetson
