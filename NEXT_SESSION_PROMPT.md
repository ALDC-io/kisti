# KiSTI — Next Session Prompt (kisti-23: Screen Redesign Polish + Icon Overlap Fix)

**Working dir**: `/home/aldc/repos/kisti/`
**Jetson**: `192.168.22.131` (user `aldc`). SSH: `ssh aldc@192.168.22.131`
**Test baseline**: 804+ tests, all passing
**Branch**: current session work not yet committed
**Last deployed**: earlier version on Jetson (needs refresh with redesign)

## Section 1: What Was Done (kisti-22 session — Screen Redesign)

### "Less Is More" Redesign — Simplify for Arm's Length Readability
Applied "one question per screen" principle to 800x480 Excelon at arm's length. Stripped accumulated clutter. User confirmed Sport is perfect; Sport# and Intelligent need simplification.

**Sport** (`ui/sport_screen.py`) — "How am I driving?" ✓ LOCKED
- User confirmed perfect — no changes
- G-force circle: r=140, centered (575, 270), fills y=100..440
- Performance bars: LAT G, BRAKE, STEER, YAW (bar_h=28px, spacing=70px, font=13pt)
- DCCD bar + FLIR temps (top-left, 2x2 grid)
- ✓ Removed dead code: `_paint_wheel_speeds()` + `_paint_brake_steering_trace()` (~111 lines)
- 462 lines, 804+ tests passing

**Sport#** (`ui/sharp_screen.py`) — "Am I faster?" → TIMING-FOCUSED (awaiting canyon feedback)
- 4 clean sections: delta bar (y=0..90), lap time (y=90..280), sectors (y=280..380), safety vitals (y=380..480)
- Delta bar: green=faster, red=slower, ±seconds format
- Lap time: huge 60pt Courier, best lap + lap count
- Sectors: 4 blocks, 100px tall, green/red coloring
- Safety vitals: 4 zones (OIL PSI, COOLANT, OIL TEMP, BRK TEMP) — removed DCCD zone
- ⚠ **User feedback**: "sport sharp... just a big lap time? remember we'll be driving canyons as well right?" — **needs G-force circle redesign**
- 457 lines, 804+ tests passing

**Intelligent** (`ui/intelligent_screen.py`) — "What are the conditions?" ✓ MOSTLY DONE
- 3 sections: weather (y=0..160), FLIR (y=160..340), status strip (y=340..480)
- Weather: huge temp 56pt bold (left), humidity/pressure 36pt bold (right)
- FLIR: full-width 2x2 grid, 370px cells, heat-color backgrounds, warm-up badge overlay (COLD/WARMING/READY)
- Status strip: DCCD bar + surface badge + SLIP delta 40pt
- ✓ Removed: sparklines, wheel deltas, health panel, density altitude, dew point
- ⚠ **Icon overlaps remain** (see Pending below)
- 525 lines, 804+ tests passing

### Main Window Fixes
- Removed TopStatusBar instantiation (was creating ghost text)
- Hidden legacy mode widgets: KistiModeWidget, DiffModeWidget, TrackModeWidget (z-order battles)

### Mock Data Optimization
- Reduced update rates: 50Hz→20Hz dynamics, 20Hz→10Hz context, 9Hz→5Hz FLIR (eliminate jitter)
- Reduced steering noise: ±15°→±3° per tick
- SI-Drive rotation: 15s cycle (show all 3 screens in 45s)

### DiffState FLIR Fields
`model/vehicle_state.py`: `brake_temp_fl/fr/rl/rr`, `flir_available`, `flir_frame_ts`, `update_flir()`, `is_flir_stale(timeout=2.0)`

### FLIR Lepton Reader
`sensors/flir_lepton_reader.py`: PureThermal USB reader. Auto-detects 160x120 thermal camera on /dev/video0-4. ROI-based brake temp extraction. Radiometric centi-Kelvin conversion. Follows Yoctopuce QObject+QTimer+Signal pattern. Currently shows "FLIR NOT CONNECTED" — no hardware wired yet.

### RS3 Shift LED Investigation
`rs3/shift_led_investigation.md`: AiM MXG shift LEDs are firmware-controlled (NOT CAN-addressable). Solution: RS3 math channels read SI-Drive CAN frame (0x6B0) for mode-aware shift thresholds (I=off, S=5500, S#=6800 RPM).

### Test Fixes
- Fixed 2 pre-existing stack index failures (default = Sport index 1, not Intelligent index 0)
- Added 10 FLIR tests: field defaults, staleness, snapshot copy, heat colors, all 3 screens accept data
- 885 → 895 tests, all passing

## Section 2: Prioritized TODO (kisti-23)

### Priority 1: Fix Icon Overlaps ⚠️ CRITICAL BEFORE DEPLOY
**Files**: `ui/intelligent_screen.py` (status strip), `ui/sport_screen.py` (DCCD/FLIR top bar)

**User reported**:
- "there is still something top left that is over top of some other numbers?"
- "sport still has...dccd in orange and something behind it? not sure"
- Intelligent & Sport both have text/badge positioning issues

**Likely culprits**:
1. **Intelligent status strip** (y=340..480): DCCD bar (orange pill) overlapping surface badge or SLIP delta label
2. **Sport top-left**: DCCD bar text overlapping FLIR zone labels

**Action**:
- Deploy to Jetson, take closeup screenshots (zoom in on top-left areas)
- Measure exact x,y bounding boxes of overlapping elements
- Adjust padding/sizing to prevent overlap (shrink DCCD pill? shift surface badge right?)
- Re-test and screenshot both screens

**Acceptance**: Cleap, readable text at arm's length with zero overlap.

### Priority 2: Sport# Must Be Canyon-Capable, Not Just Timing ⚠️ DESIGN DECISION
**File**: `ui/sharp_screen.py`

**User feedback**: "sport sharp... just a big lap time? remember we'll be driving canyons as well right?"

**Current state**: Sport# is timing-focused (lap time, delta, sectors) — great for track but doesn't help during canyon driving.

**Options**:
- **Option A**: Add G-force circle back to Sport# (smaller than Sport's r=140, maybe r=90)
  - Where? Replace sector strip (y=280..380) with G-force circle?
  - Or split lap time panel horizontally (G-force left, timing right)?
  
- **Option B**: Keep timing-focused, but confirm "lap time" includes canyon segment tracking (not just track times)
  
- **Option C**: Hybrid — add small G-force circle to corner of safety vitals for intensity feedback

**Decision deferred**: Review screenshots tomorrow, decide with user. If adding G-force, redesign layout to fit 4 sections + circle.

### Priority 3: Deprioritize DCCD if Overlapping
**User feedback**: "i think we may be focusing too much on dccd lock up — it's not that primary is it?"

**Current placement**: 
- Sport: DCCD bar top-left (orange pill)
- Intelligent: DCCD bar in status strip (left side)
- Sport#: removed entirely

**Action**: If DCCD is causing overlaps (Priority 1), consider:
- Making DCCD bar narrower/smaller text
- Moving it lower on Sport (below FLIR grid instead of above)
- Removing it entirely from Intelligent status strip if it's just repeating Sport

### Priority 4: Deploy & Verify
- Commit redesign changes (files already modified)
- Push to origin
- Deploy to Jetson: `~/k` or manual SSH pull + relaunch
- Cycle through all 3 screens (use SI-Drive knob or 1/2/3 keyboard keys)
- Verify: readable fonts, no overlaps, colors clear on Excelon
- Check all 804+ tests still pass: `python3 -m pytest tests/ -x -q`

## Section 3: Key Files (Changed in kisti-23)

| File | What It Does | Changes |
|------|-------------|---------|
| `ui/sharp_screen.py` | Sport# — timing-focused (delta, lap time, sectors, vitals) | 457 lines, redesigned 4-section layout, removed DCCD zone from safety vitals |
| `ui/sport_screen.py` | Sport — G-force circle, performance bars, DCCD/FLIR top bar | 462 lines, removed dead methods `_paint_wheel_speeds()` + `_paint_brake_steering_trace()` |
| `ui/intelligent_screen.py` | Intelligent — weather, FLIR 2x2 grid, status strip | 525 lines, 3-section redesign, removed sparklines/wheel deltas/health panel |
| `ui/main_window.py` | Main app window, stacked widget manager | Fixed: removed TopStatusBar, hid legacy mode widgets |
| `data/mock_generator.py` | Mock CAN data generator | Reduced update rates (50Hz→20Hz, etc.), reduced steering noise, 15s SI-Drive rotation |
| `model/vehicle_state.py` | DiffState + DiffStateBridge — all telemetry | No changes this session |
| `tests/test_modes.py` | 39 tests: modes, FLIR, data flow | All 804+ tests passing |

## Section 4: Architecture

### Screen data flow
```
CAN bus (1 Mbps)  →  kisti_can.py  →  DiffStateBridge.update_*()
Yoctopuce USB     →  yoctopuce_reader.py  →  DiffStateBridge.update_ambient()
FLIR USB          →  flir_lepton_reader.py  →  DiffStateBridge.update_flir()
TimingManager     →  DiffStateBridge.update_timing()

DiffStateBridge.snapshot()  →  MainWindow (20Hz QTimer)
  → active_screen.update_state(snap)
  → sharp_screen.update_timing(timing_dict)
```

### Screen design philosophy
- **MXG Strada** = critical instruments (RPM, speed, gear, boost, shift lights, oil, coolant, lambda)
- **KiSTI Excelon** = context the MXG can't show (FLIR thermal, G-forces, DCCD/AWD, wheel dynamics, timing, weather, steering analysis, AI insights)

### FLIR integration gap
The reader (`flir_lepton_reader.py`) is built but not wired into `main.py`. The connection point is:
```python
flir = FLIRLeptonReader()
flir.temps_updated.connect(lambda t: bridge.update_flir(t.fl, t.fr, t.rl, t.rr))
flir.start()
```

## Section 5: Don't Repeat (kisti-22/23)
- **Widget z-order battle**: TopStatusBar + legacy widgets (KistiModeWidget, etc.) created with parent=self cause ghost text even if hide(). Remove entirely, don't just hide.
- **Pycache race condition**: Deploy scripts must remove `__pycache__` AFTER git pull (old .pyc files compiled before new code lands). Add: `find . -name "__pycache__" -type d -exec rm -rf {} +`
- **Icon overlap debugging**: closeup screenshots needed (zoom in on top-left areas). Measure exact bounding boxes before repositioning.
- **Sport# canyon vs track**: User drives both — needs G-force circle feedback for canyon intensity, lap timing for track. Design must serve both modes.
- **DCCD not primary**: User said "i think we may be focusing too much on dccd lock up". Deprioritize via size/positioning if it's causing overlaps.
- **Arm's length readability**: Min font ~13pt for performance bars, ~40pt for large numbers. Excelon 800x480 at ~1m requires big, clear fonts.
- AiM MXG shift LEDs are NOT CAN-addressable — RS3 math channels only
- SI-Drive OEM values (1/2/3) differ from Link remapped values (0/1/2) — RS3 uses remapped
- `_heat_color` pattern: blue (<150) → green (<300) → yellow (<450) → red (>500) for brakes
- Stack default index = 1 (Sport), not 0 (Intelligent) — tests updated to match
- Never give multi-step SSH commands — use `~/k` for deploy
