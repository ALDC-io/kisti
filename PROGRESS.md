# KiSTI - Progress

## Session: 2026-02-10

### Completed
- Project structure created (~20 Python files)
- Data layer: models.py (8 dataclasses), mock_generator.py (10Hz/1Hz)
- UI theme: dark automotive palette (2014 STI inspired), QSS stylesheet
- Status bar: mode, clock, GPS/LOG/NET indicators, Nvidia + Link ECU logos
- Softkey bar: STREET/TRACK/AUDIO/LOG/SETTINGS (all modes switchable)
- STREET mode: mock map, corner grid, oil gauge, sensor status, alerts, pit summary modal
- TRACK mode: thermal quadrant + sparklines, track map, oil gauge + brake strip, sensor status, findings list, session widget
- SETTINGS mode: corporate branding (KiSTI + Nvidia + Link ECU), system info, sensor connection status
- Splash screen: 3-second boot screen with logos and branding
- Main window: QStackedWidget mode switching, F11 fullscreen, CLI args
- Branding utility: SVG/PNG logo loader with caching (ui/branding.py)
- Oil pressure: PSI + temp + sparkline with color-coded thresholds
- Front sensor suite: Teledyne IR, LiDAR, RGB, Weather camera status display
- Corporate logos: Link ECU (SVG), Nvidia (PNG) in status bar, settings, splash
- README with install/run/display instructions

### Architecture
- `data/models.py`: VehicleState, CornerData, GPSData, OilPressureData, FrontSensorSuite, CameraStatus, SessionData, SystemState, KistiFinding
- `data/mock_generator.py`: 10Hz temps/oil/sensors + 1Hz GPS/session/findings
- `ui/branding.py`: Logo loader (Nvidia PNG + Link ECU SVG)
- `ui/splash_screen.py`: 3s boot screen with corporate logos
- `ui/settings_mode.py`: System info + sensor status + branding
- `ui/widgets/oil_gauge.py`: Oil pressure gauge with sparkline
- `ui/widgets/sensor_status.py`: Front camera array status

### Session 2 Updates (2026-02-10, evening)
- GT7-style tire indicators: Redesigned CornerCell from segmented bar graphs to rounded tire-shaped indicators with internal fill bars
- GT7 color palette: Blue (cold) → Green (optimal) → Yellow (warm) → Red (overheating) temperature transitions
- Tire wear system: Added tire_wear_pct to CornerData model, wear simulation in mock generator (degrades faster when hot)
- Brake temp strip: Thin vertical bar beside each tire shape
- Visual polish: Gradient fills, tread line overlays, glossy highlights, wear notch marks at 25/50/75%
- Theme additions: TIRE_BLUE, TIRE_BLUE_DARK, TIRE_GREEN, TIRE_YELLOW, TIRE_RED

## Session: 2026-02-16

### DIFF Mode — Center Differential Telemetry (MapDCCD 2014 STI)

Full DIFF tab build from detailed prompt. 7 files added/modified in one session.

### New Files
- `model/vehicle_state.py`: `DiffState` dataclass (13 fields), `DiffStateBridge` (thread-safe QObject with `threading.Lock` + Qt `Signal`), `SurfaceState` IntEnum (DRY/WET/COLD/LOW_GRIP with label + color properties)
- `can/can_config.py`: CAN bus constants — frame IDs (`0x6A0` DIFF @ 50Hz, `0x6A1` CONTEXT @ 20Hz), all byte offsets/scales/bitmasks, stale timeout (500ms), UI refresh (20Hz), mock rates, socketcan config (`can0`, 500kbps)
- `can/kisti_can.py`: Pure decode functions (`decode_diff_frame`, `decode_context_frame`), encode helpers for testing, `CanListenerThread` (daemon thread, reads socketcan, updates bridge), `MockCanGenerator` (QTimer-based canyon driving sim), `create_can_source()` factory (auto-detects real CAN vs mock fallback)
- `ui/diff_mode.py`: Full QPainter DIFF page — `_HeaderBar` (surface state word + CAN status dot), `_BigNumericPanel` (large LOCK% + smaller DIAL%), `_ContextPanel` (gear/speed/throttle/slip with color-coded slip magnitude), `_StatusPills` (BRAKE/H-BRAKE/ABS/VDC active-highlight pills), `DiffModeWidget` (20Hz refresh timer, MARK button → JSONL to `~/kisti/logs/`, 0.6s flash feedback)
- `ui/widgets/diff_sparkline.py`: `DiffSparkline` — ring-buffer QPainter widget (200 samples @ 20Hz = 10s), filled area under curve with alpha, optional zero-line for signed signals, auto-expanding Y-axis
- `tests/test_can_decode.py`: 18 pytest cases across 5 classes — DIFF decode (normal/N-A/negative slip/all flags/zero+full lock/surface fallback/short frame), CONTEXT decode (normal/neutral/high speed/short frame), round-trip encode→decode, DiffState staleness detection, SurfaceState enum validation

### Modified Files
- `ui/main_window.py`: DIFF as stack index 3, `DiffStateBridge` creation, `create_can_source()` wired into splash/close lifecycle, CAN listener start/stop
- `ui/softkey_bar.py`: Added DIFF between TRACK and VIDEO in `_BUTTONS` list

### Architecture Decisions
- **Separate data pipeline**: DIFF tab reads from CAN bus (or mock) via `DiffStateBridge`, independent of existing `MockDataGenerator` — no coupling between telemetry sources
- **Thread-safe bridge pattern**: CAN listener thread writes via lock-protected `update_diff()`/`update_context()`; UI reads via `snapshot()` copy at 20Hz QTimer — no per-frame UI updates
- **Graceful degradation**: Auto-detects `python-can` + `can0` availability; falls back to `MockCanGenerator` with simulated canyon driving (random walk + sinusoidal DCCD, correlated throttle/speed/gear, occasional slip spikes)
- **Editable CAN constants**: All arbitration IDs, byte offsets, scaling factors, flag bitmasks in single `can/can_config.py` — ready for real Link G4X CAN config

### Prompt
The DIFF tab was built from a detailed Claude Code prompt specifying:
- MapDCCD center diff telemetry for 2014 STI
- CAN message layout (0x6A0 DIFF, 0x6A1 CONTEXT) with byte-level spec
- QPainter sparklines (10s rolling, 200 samples @ 20Hz)
- MARK segment marker → JSONL logging
- python-can socketcan listener with mock fallback
- WVGA 800x480 layout optimized for in-motion readability

### Next Steps
- Finalize Link G4X CAN publish bus IDs (currently placeholder 0x6A0/0x6A1)
- Real CAN testing on bench with Link ECU + MapDCCD
- Teledyne IR camera feed integration
- LiDAR point cloud visualization
- Voice integration (KiSTI spoken insights)
- LOG mode page (session recording/playback)
- Touch optimization for Excelon capacitive screen
- Performance profiling on Jetson GPU
