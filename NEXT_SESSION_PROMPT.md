# KiSTI Next Session Handoff — kisti-24

**Repo**: `/home/aldc/repos/kisti/` | **Branch**: `kisti-headless`
**Jetson**: `192.168.22.131` (SSH user: `aldc`, pw: `aldc1234`)
**985 tests passing** — `python3 -m pytest tests/ -q` (1 pre-existing failure: `test_timing_after_lap`)

---

## What Was Done (This Session — kisti-23)

### kisti-23a: usb_8dev kernel module — DONE

- Built `usb_8dev` OOT kernel module on Jetson against Tegra 5.15.148 headers
- Installed to `/lib/modules/5.15.148-tegra/updates/usb_8dev.ko`
- Auto-loads on boot: `/etc/modules-load.d/usb_8dev.conf`
- Udev rule auto-brings up `can1` at 1Mbit/s on plug-in: `/etc/udev/rules.d/80-can-usb.rules`
- Loopback test passed: `0x600 [8] 12345678abcdef00` — hardware works
- KiSTI restarted; running on PID ~94583

### kisti-23b: Sector strip fix — DONE (commit d139dd7)

- `ui/sharp_screen.py:449`: Added `and sector_times[i] > 0` guard
- Unrun sectors (time=0) now stay dark, not pre-populated as red blocks

### kisti-23c: G5 Generic Dash parser — DONE (commit 38ccf36)

**Critical protocol correction**: G5 Generic Dash is NOT sequential IDs 0x360-0x362 (big-endian).
Actual protocol: single CAN ID (default 0x3E8), multiplexed on byte[0], LE int16, 3 signals/frame.

| File | Change |
|------|--------|
| `can/can_config.py` | GENERIC_DASH_BASE_ID 0x360→0x3E8, COUNT 3→14, _G5_INPUT_IDS single ID, GD_FRAME_* constants, GD1/GD2/GD3 deprecated (kept for import compat) |
| `can/g5_generic_dash.py` | **NEW**: G5GenericDashParser — mux decode, 6 sub-frames, all properties, stale detection |
| `tests/test_g5_generic_dash.py` | **NEW**: 44 tests (rejection, None-before-recv, all signals, stale, custom ID, reset) |

---

## Priority 1: Order CAN Hardware (JK Action Required)

Cannot do a real CAN sniff until this hardware arrives:

| Item | Part # | Est. Cost |
|------|--------|-----------|
| Link G5 CAN cable | PN 101-5104 | ~$75 CAD |
| DB9 breakout board | generic | ~$14 CAD |
| 120Ω DB9 terminator | generic | ~$13 CAD |

**DTM4 wiring (once cable arrives)**:
- Pin 4 → DB9 Pin 7 (CAN H)
- Pin 3 → DB9 Pin 2 (CAN L)
- Pin 2 → DB9 Pin 3 (GND)
- Pin 1 = 12V — **DO NOT CONNECT** to DB9

---

## Priority 2: CAN Sniff → Confirm G5 Frame Layout

Once CAN cable arrives, connect G5 to Korlan (can1), then:

```python
import can
bus = can.interface.Bus(channel='can1', bustype='socketcan')
for msg in bus:
    print(f"0x{msg.arbitration_id:03X} [{msg.dlc}] {msg.data.hex()}")
```

**What to verify**:
1. The CAN ID printed — should be `0x3E8` (1000 decimal) if PCLink default. If different, update `GENERIC_DASH_BASE_ID` in `can/can_config.py`
2. That byte[0] cycles 0–13 on repeating messages
3. That byte[1] is always 0x00
4. Pick one frame (e.g. frame 0 at idle — byte[0]=0x00) and decode: `struct.unpack('<hhh', data[2:8])` should give ~[idle_rpm, idle_map, 0] which confirms LE int16

---

## Priority 3: Integrate G5GenericDashParser into kisti_can.py

**Only after sniff confirms CAN ID and byte order.**

Steps:
1. `can/can_config.py`: change `CAN_INTERFACE: str = "can0"` → `"can1"`
2. `can/kisti_can.py`: import `G5GenericDashParser` from `can.g5_generic_dash`
3. Replace `decode_generic_dash_1/2/3()` calls with `parser.feed()` in the CAN listener loop
4. Bridge the parser properties into DiffStateBridge (check which fields it exposes)
5. Change `MOCK_ENABLED: bool = True` → `False`
6. Test live with G5 running

**kisti_can.py current state** (do NOT touch until post-sniff):
- Lines 59-100: imports all GD1/GD2/GD3 deprecated constants by name — will need cleanup
- Has `decode_generic_dash_1()`, `decode_generic_dash_2()`, `decode_generic_dash_3()` — big-endian, wrong
- These functions are used in the CAN dispatch; replace the calls, not just the imports

---

## Priority 4: Post-Boost Barn — SC-6 Session Trends

**Do NOT implement until after Boost Barn tune (WO #15562, Aaron).**
Real ECU brake_pressure data must be flowing into DuckDB first.

- DuckDB path on Jetson: `/data/duckdb/kisti.duckdb`
- `telemetry` table: 18 tables, 0 rows pre-Boost Barn
- New file needed: `coaching/session_trend_analyzer.py`

---

## Priority 5: RS3 Theme Flash

Flash cfg_20260401_152932 to MXG Strada. Requires Windows + physical access to car.
Separate from software track — no Jetson/code work involved.

---

## Key Files

| File | Role |
|------|------|
| `can/can_config.py` | CAN constants — GENERIC_DASH_BASE_ID now 0x3E8, GD_FRAME_* added |
| `can/g5_generic_dash.py` | **NEW**: G5GenericDashParser (use this, not old decode_ functions) |
| `can/kisti_can.py` | CAN listener — still uses old decode_generic_dash_1/2/3 (pre-sniff) |
| `scripts/jetson/install-gs-usb.sh` | usb_8dev OOT build script — DONE, not needed again |
| `ui/sharp_screen.py` | Sector strip fix at line 449 |
| `coaching/session_lap_tracker.py` | Within-session lap trend tracker (kisti-22) |
| `data/build_record.py` | Alert thresholds (single source of truth) |

## Architecture Reminders

- Paint pattern: coaching cached in instance vars (1Hz), painted at 20Hz
- No Qt in coaching modules — pure Python, fully testable
- Tests baseline: **985** (was 942, +44 g5_generic_dash tests, +1 sector_insight from kisti-23)
- **1 pre-existing test failure**: `test_timing_after_lap` in `test_timing_manager.py` — NOT our regression
- **Deploy command**: `ssh aldc@192.168.22.131 "cd ~/repos/kisti && git pull --ff-only && ~/k"`
- **DuckDB path on Jetson**: `/data/duckdb/kisti.duckdb` (not in repo dir)
- **NEVER use `systemctl restart gdm`** — breaks headless display setup
- **MOCK_ENABLED = True**: KiSTI running on mock data. Flip False after CAN sniff + integration
- **G5 Generic Dash CAN ID**: default 0x3E8 — VERIFY against actual PCLink config before flip

## Korlan USB2CAN Setup (COMPLETE)

- Driver: `usb_8dev` at `/lib/modules/5.15.148-tegra/updates/usb_8dev.ko`
- Auto-loads: `/etc/modules-load.d/usb_8dev.conf`
- Auto-bringup: `/etc/udev/rules.d/80-can-usb.rules` (1Mbit/s on plug-in)
- Interface appears as `can1` when Korlan plugged in
- python-can call: `can.interface.Bus(channel='can1', bustype='socketcan')`
- **NOT slcand/slcan** — Korlan 0483:1234 is native USB CAN, not serial
