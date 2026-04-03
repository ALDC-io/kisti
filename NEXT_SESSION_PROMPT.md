# KiSTI Next Session Handoff — kisti-25

**Repo**: `/home/aldc/repos/kisti/` | **Branch**: `kisti-headless`
**Jetson**: `192.168.22.131` (SSH user: `aldc`, pw: `aldc1234`)
**991 tests passing** — `python3 -m pytest tests/ -q` (1 pre-existing failure: `test_timing_after_lap`)

---

## What Was Done (This Session — kisti-24)

### kisti-24: G5GenericDashParser dispatch integration — DONE (commit 75390fb)

Integrated `G5GenericDashParser` into `CanListenerThread._dispatch_frame()` in `can/kisti_can.py`.

| File | Change |
|------|--------|
| `can/kisti_can.py` | Added G5GenericDashParser import + `_g5_parser` instance; replaced old wrong dispatch (sequential IDs 0x3E9/0x3EA, big-endian) with parser-based dispatch at lines 684-692 |
| `can/can_config.py` | Updated deprecation comment — old decode functions kept for test compat only |
| `tests/test_can_decode.py` | Added `TestG5DispatchIntegration` (6 tests: partial frame gating, full 4-frame cycle, pre-frame-0 guard, wrong ID rejection, malformed frame rejection) |

**Key fact**: `MOCK_ENABLED = True` and `CAN_INTERFACE = "can0"` remain unchanged. The live CAN path is wired correctly but dormant until hardware arrives and sniff confirms the CAN ID.

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
1. CAN ID — should be `0x3E8` (1000 decimal) if PCLink default. If different, update `GENERIC_DASH_BASE_ID` in `can/can_config.py`
2. That byte[0] cycles 0–13 on repeating messages
3. That byte[1] is always 0x00
4. Pick frame 0 (byte[0]=0x00) at idle and decode: `struct.unpack('<hhh', data[2:8])` should give ~[idle_rpm, idle_map, 0]

---

## Priority 3: Flip to Live

After sniff confirms ID=0x3E8 and LE int16:

1. `can/can_config.py`: `CAN_INTERFACE: str = "can0"` → `"can1"`
2. `can/can_config.py`: `MOCK_ENABLED: bool = True` → `False`
3. Start KiSTI with G5 running and verify dashboard signals update (rpm, coolant_temp, etc.)
4. If CAN ID differs from 0x3E8 — also update `GENERIC_DASH_BASE_ID`

No kisti_can.py changes needed — dispatch is already wired correctly.

---

## Priority 4: Post-Boost Barn — SC-6 Session Trends

**Do NOT implement until after Boost Barn tune (WO #15562, Aaron).**
Real ECU brake_pressure data must be flowing into DuckDB first.

- DuckDB path on Jetson: `/data/duckdb/kisti.duckdb`
- `telemetry` table: 18 columns, 0 rows pre-Boost Barn
- New file needed: `coaching/session_trend_analyzer.py`

---

## Priority 5: RS3 Theme Flash

Flash cfg_20260401_152932 to MXG Strada. Requires Windows + physical access to car.
Separate from software track — no Jetson/code work involved.

---

## Key Files

| File | Role |
|------|------|
| `can/can_config.py` | CAN constants — GENERIC_DASH_BASE_ID=0x3E8, MOCK_ENABLED=True (flip post-sniff) |
| `can/g5_generic_dash.py` | G5GenericDashParser — mux decode, 6 sub-frames, all properties |
| `can/kisti_can.py` | CAN listener — dispatch at line ~684, _g5_parser instance wired in |
| `tests/test_can_decode.py` | TestG5DispatchIntegration (6 tests) — new in kisti-24 |
| `tests/test_g5_generic_dash.py` | 44 parser unit tests — added in kisti-23 |
| `model/vehicle_state.py` | DiffStateBridge — update_generic_dash_1/2/3 signatures |
| `data/build_record.py` | Alert thresholds (single source of truth) |

## Architecture Reminders

- Paint pattern: coaching cached in instance vars (1Hz), painted at 20Hz
- No Qt in coaching modules — pure Python, fully testable
- Tests baseline: **991** (was 942 → 985 → 991). 1 pre-existing failure: `test_timing_after_lap`
- **Deploy command**: `ssh aldc@192.168.22.131 "cd ~/repos/kisti && git pull --ff-only && ~/k"`
- **DuckDB path on Jetson**: `/data/duckdb/kisti.duckdb` (not in repo dir)
- **NEVER use `systemctl restart gdm`** — breaks headless display setup
- **G5 sub-frame grouping**: bridge gd1 spans frames 0+1 (rpm+coolant_temp), gd2 spans frames 1+2, gd3 spans frames 2+3. Each bridge call gated on its primary field being non-None.

## Korlan USB2CAN Setup (COMPLETE — kisti-23)

- Driver: `usb_8dev` at `/lib/modules/5.15.148-tegra/updates/usb_8dev.ko`
- Auto-loads: `/etc/modules-load.d/usb_8dev.conf`
- Auto-bringup: `/etc/udev/rules.d/80-can-usb.rules` (1Mbit/s on plug-in)
- Interface appears as `can1` when Korlan plugged in
- python-can call: `can.interface.Bus(channel='can1', bustype='socketcan')`
- **NOT slcand/slcan** — Korlan 0483:1234 is native USB CAN, not serial
