# KiSTI

Visual telemetry prototype for ALDC motorsport. Targets Kenwood Excelon head unit (800x480 HDMI) running on Jetson Orin.

## Install

```bash
pip install PySide6
sudo apt-get install libxcb-cursor0   # Required for X11 display
```

If you don't have sudo, the library is already installed to `~/.local/lib/` and `run.sh` handles it automatically.

## Run

```bash
./run.sh                    # Recommended - handles all env setup
./run.sh --fullscreen       # Fullscreen mode
```

Or manually:

```bash
export DISPLAY=:0
export LD_LIBRARY_PATH=$HOME/.local/lib:$LD_LIBRARY_PATH
python3 main.py
```

### Options

```
--fullscreen         Start in fullscreen mode
--display :0         Specify X11 display
--platform eglfs     Use eglfs platform (alternative to xcb)
```

### Keyboard

- **F11** - Toggle fullscreen

## Display Setup (Kenwood Excelon)

```bash
xrandr --output HDMI-0 --mode 800x480
```

## Modes

- **KiSTI** - Home / overview
- **STREET** - Map + corner temps + alerts + pit summary
- **TRACK** - Thermal quadrant with sparklines + track map + brake strip + findings + session timing
- **DIFF** - Center differential telemetry (MapDCCD 2014 STI): DCCD lock/dial %, surface state, slip delta, event flags, 10s sparklines, segment marker
- **VIDEO** - Camera feeds
- **LOG** - (Coming soon)
- **SETTINGS** - System info, sensor status, corporate branding

## Architecture

- `data/` - Dataclasses and mock data generator (replace with CAN/IR/GPS for production)
- `model/` - Thread-safe state models (`DiffState`, `DiffStateBridge`)
- `can/` - CAN bus config, decoder, listener thread, mock generator
- `ui/` - PySide6 widgets, dark automotive theme
- `ui/widgets/` - Reusable QPainter custom widgets
- All rendering is QPainter-based (no external map APIs)

## CAN Bus (DIFF Mode)

The DIFF tab reads Link ECU CAN data via python-can (socketcan). Falls back to mock data automatically.

```bash
pip install python-can    # Optional — mock mode works without it
sudo ip link set can0 up type can bitrate 500000   # Real CAN setup
```

CAN message layout (editable in `can/can_config.py`):
- `0x6A0` @ 50Hz: DCCD command/dial %, surface state, flags, slip delta
- `0x6A1` @ 20Hz: Gear, speed, throttle %

## Mock Data

The `MockDataGenerator` produces:
- 10Hz: tire temps (80-110C), brake temps (200-450C), GPS position
- 1Hz: session time, lap counting (~90s laps), KiSTI findings refresh

The `MockCanGenerator` (DIFF mode fallback) produces:
- 50Hz: simulated canyon driving — DCCD lock/dial with sinusoidal base + noise, random slip spikes, correlated brake/ABS/VDC flags
- 20Hz: throttle random walk, speed correlated to throttle, gear mapped from speed

## Tests

```bash
cd /path/to/project && python3 -m pytest tests/ -v
```
