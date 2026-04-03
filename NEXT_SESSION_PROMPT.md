# KiSTI Next Session Handoff — kisti-23

**Repo**: `/home/aldc/repos/kisti/` | **Branch**: `kisti-headless`
**Jetson**: `192.168.22.131` (SSH user: `aldc`, pw: `aldc1234`)
**942 tests passing** — `python3 -m pytest tests/ -x -q`

---

## What Was Done (This Session — kisti-22)

### Coaching Upgrades Batch 2 — ALL 4 SCs SHIPPED (commits 3e577bd, ac4664c, dc9877e)

| SC | Change | Status |
|----|--------|--------|
| SC-1 | `SessionLapTracker`: lap trend voice summaries after lap 2+ | DONE |
| SC-2 | Sport screen condition override: ICE/LOW_GRIP replaces technique text in `_coaching_tick()` | DONE |
| SC-3 | Sharp screen sector insight: 9pt → 11pt, rect height 14 → 16 | DONE |
| SC-4 | Sport coaching font: 13pt → 14pt | DONE |

**New files:** `coaching/session_lap_tracker.py`, `tests/test_session_lap_tracker.py` (7 tests)
**Modified:** `main.py`, `ui/sport_screen.py`, `ui/sharp_screen.py`
**Project:** `/home/aldc/projects/active/2026-04-02-kisti-coaching-upgrades/` — COMPLETE

### Korlan USB2CAN Investigation

**Hardware confirmed:** `0483:1234 STMicroelectronics / 8devices Korlan USB2CAN DB9`

**Critical finding:** The Korlan is a **native USB CAN device** — NOT serial/slcan.
- It does NOT create `/dev/ttyUSB0`
- `slcand` / `slcan` will NOT work for this device
- Correct driver: **`usb_8dev`** (SocketCAN, mainline since kernel 3.9)
- The Tegra 5.15.148 kernel has `usb_8dev` disabled (`# CONFIG_CAN_8DEV_USB is not set`)
- Must build as out-of-tree module — script is ready

**Build script:** `scripts/jetson/install-gs-usb.sh` (updated — now fetches `usb_8dev.c`)

**CAN bus specs:**
- Link G5 Voodoo Neo 4: 1 Mbit/s (default), CAN base address `0x600`
- AiM GPS09 IMU/GPS: 1 Mbit/s, CAN IDs `0x6A4–0x6A7`
- `can0` (onboard mttcan) is already at 1 Mbit/s — correct
- USB adapter will appear as `can1` once driver is loaded

---

## Priority 1: Run USB2CAN Driver Install on Jetson

This requires sudo on the Jetson — must be run interactively.

```bash
ssh aldc@192.168.22.131
cd ~/repos/kisti && git pull --ff-only
bash scripts/jetson/install-gs-usb.sh
```

Script does: download `usb_8dev.c` from kernel 5.15.148 → OOT build → install →
`modprobe usb_8dev` → udev rule (auto-bringup at 1Mbit/s on plug-in) → bring up `can1`.

**Expected output ends with:**
```
2: can0: ... mttcan ... bitrate 1000000 ... state UP
3: can1: ... usb_8dev ... bitrate 1000000 ... state UP
```

If the build fails, paste the error — the kernel tree is at
`/lib/modules/5.15.148-tegra/build` and the source goes in `~/usb_8dev_build/`.

---

## Priority 2: Wire KiSTI to Read ECU Data via can1

Once `can1` is up, KiSTI needs to read from it. Check current CAN interface binding:

```bash
grep -n 'can0\|can_bus\|channel' /home/aldc/repos/kisti/bridge/can_bus.py | head -20
```

The Link G5 CAN stream (base address `0x600`) needs a parser. This is new territory —
no existing KiSTI code handles ECU CAN frames. Key questions to answer first:

1. What CAN IDs does the G5 actually broadcast? (PC Link help file → CAN setup → generic dash stream)
2. Does KiSTI use `can0` or auto-detect? Check `bridge/can_bus.py`
3. Link G5 default CAN output frame layout (bytes 0-7 per message ID)

**Do NOT wire main.py to can1 until we know the G5 frame layout.** Start with a raw
listener first:

```python
import can
bus = can.interface.Bus(channel='can1', bustype='socketcan')
for msg in bus:
    print(f"0x{msg.arbitration_id:03X} [{msg.dlc}] {msg.data.hex()}")
```

Run this with the G5 powered and CAN connected — paste the output to identify frame IDs.

---

## Priority 3: Post-Boost Barn — SC-6 Session Trends

**Do NOT implement until after Boost Barn tune (WO #15562, Aaron).**
Real ECU brake_pressure data must be flowing into DuckDB first.

- DuckDB path on Jetson: `/data/duckdb/kisti.duckdb`
- `telemetry` table: 18 tables, 0 rows pre-Boost Barn
- New file needed: `coaching/session_trend_analyzer.py`

---

## Key Files

| File | Role |
|------|------|
| `scripts/jetson/install-gs-usb.sh` | **Run this first** — builds usb_8dev OOT module |
| `bridge/can_bus.py` | CAN interface binding — check for hardcoded `can0` |
| `coaching/session_lap_tracker.py` | New: within-session lap trend tracker (kisti-22) |
| `coaching/condition_rules.py` | Condition rules, now includes LOW_GRIP action text |
| `ui/sport_screen.py` | Coaching: 14pt bold, full-width QRectF(0,398,800,20) |
| `ui/sharp_screen.py` | Sector insight: 11pt, rect height 16 |
| `main.py` | `_coaching_tick()` now overrides with conditions; `_on_lap_complete()` appends trend |
| `data/duckdb_store.py` | Telemetry table — brake_pressure/steering per session |
| `data/build_record.py` | Alert thresholds (single source of truth) |

## Architecture Reminders
- Paint pattern: coaching cached in instance vars (1Hz), painted at 20Hz
- No Qt in coaching modules — pure Python, fully testable
- Tests baseline: **942** (was 935, +7 session_lap_tracker tests). Must not regress.
- **1 pre-existing test failure**: `test_timing_after_lap` in `test_timing_manager.py` — NOT our regression, pre-dates this branch
- **Deploy command**: `ssh aldc@192.168.22.131 "cd ~/repos/kisti && git pull --ff-only && ~/k"`
- **DuckDB path on Jetson**: `/data/duckdb/kisti.duckdb` (not in repo dir)
- **NEVER use `systemctl restart gdm`** — breaks headless display setup

## Context on the Korlan Setup Notes
JK has a separate setup script for a `~/can-bridge` standalone Claude Code project on the Jetson.
That script uses `slcand`/`slcan0` — **this will not work** for the Korlan (0483:1234).
The corrected approach is `can1` via `usb_8dev`. The python-can call is:
```python
bus = can.interface.Bus(channel='can1', bustype='socketcan')
```
Everything else in that script (python-can install, CLAUDE.md structure, systemd concept) is fine.
