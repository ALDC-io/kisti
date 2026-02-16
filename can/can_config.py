"""KiSTI - CAN Bus Configuration

Editable constants for the KiSTI publish bus from Link ECU.
Update these when the real Link G4X CAN configuration is finalized.

All arbitration IDs, byte offsets, scaling, and enums are defined here.
The decoder in kisti_can.py imports only from this module.
"""

# ---------------------------------------------------------------------------
# Arbitration IDs
# ---------------------------------------------------------------------------

DIFF_FRAME_ID: int = 0x6A0         # 50 Hz from Link ECU
CONTEXT_FRAME_ID: int = 0x6A1      # 20 Hz from Link ECU
WHEEL_SPEED_FRAME_ID: int = 0x6A2  # 50 Hz — individual wheel speeds
DYNAMICS_FRAME_ID: int = 0x6A3     # 50 Hz — steering, yaw, lat-G, brake

# Set of all IDs we care about (for CAN filter mask)
KISTI_CAN_IDS: set[int] = {
    DIFF_FRAME_ID, CONTEXT_FRAME_ID,
    WHEEL_SPEED_FRAME_ID, DYNAMICS_FRAME_ID,
}

# ---------------------------------------------------------------------------
# CAN interface
# ---------------------------------------------------------------------------

CAN_INTERFACE: str = "can0"
CAN_BUSTYPE: str = "socketcan"
CAN_BITRATE: int = 500_000  # 500 kbps — standard Link ECU CAN speed

# ---------------------------------------------------------------------------
# 0x6A0 — DIFF frame layout (8 bytes)
# ---------------------------------------------------------------------------
# Byte0-1: DCCD_Command_pct_x10   uint16 BE  0..1000 → 0.0..100.0%
# Byte2-3: DCCD_Dial_pct_x10      uint16 BE  0..1000; 0xFFFF = not available
# Byte4:   Surface_State           uint8       0=DRY, 1=WET, 2=COLD, 3=LOW_GRIP
# Byte5:   Flags                   uint8       bit0=brake, bit1=handbrake,
#                                               bit2=abs, bit3=vdc_tc
# Byte6-7: SlipDelta_x100         int16 BE    signed, units = km/h × 100
#                                               0x7FFF = not available

DIFF_DCCD_CMD_OFFSET: int = 0
DIFF_DCCD_CMD_LEN: int = 2
DIFF_DCCD_CMD_SCALE: float = 0.1  # raw / 10

DIFF_DCCD_DIAL_OFFSET: int = 2
DIFF_DCCD_DIAL_LEN: int = 2
DIFF_DCCD_DIAL_SCALE: float = 0.1
DIFF_DCCD_DIAL_NA: int = 0xFFFF

DIFF_SURFACE_OFFSET: int = 4

DIFF_FLAGS_OFFSET: int = 5
DIFF_FLAG_BRAKE: int = 0x01
DIFF_FLAG_HANDBRAKE: int = 0x02
DIFF_FLAG_ABS: int = 0x04
DIFF_FLAG_VDC_TC: int = 0x08

DIFF_SLIP_OFFSET: int = 6
DIFF_SLIP_LEN: int = 2
DIFF_SLIP_SCALE: float = 0.01  # raw / 100
DIFF_SLIP_NA: int = 0x7FFF  # as signed int16

# ---------------------------------------------------------------------------
# 0x6A1 — CONTEXT frame layout (8 bytes)
# ---------------------------------------------------------------------------
# Byte0:   Gear                    int8   0..6 (0 = neutral)
# Byte1-2: Speed_kph_x100         uint16 BE
# Byte3-4: Throttle_pct_x10       uint16 BE
# Byte5-7: reserved

CTX_GEAR_OFFSET: int = 0

CTX_SPEED_OFFSET: int = 1
CTX_SPEED_LEN: int = 2
CTX_SPEED_SCALE: float = 0.01  # raw / 100

CTX_THROTTLE_OFFSET: int = 3
CTX_THROTTLE_LEN: int = 2
CTX_THROTTLE_SCALE: float = 0.1  # raw / 10

# ---------------------------------------------------------------------------
# 0x6A2 — WHEEL_SPEED frame layout (8 bytes)
# ---------------------------------------------------------------------------
# Link ECU forwards OEM ABS wheel speed data (OEM CAN ID 0xD4 / 212)
# Re-encoded by Link into KiSTI publish bus format.
#
# Byte0-1: FL_speed_x100   uint16 BE   km/h × 100
# Byte2-3: FR_speed_x100   uint16 BE   km/h × 100
# Byte4-5: RL_speed_x100   uint16 BE   km/h × 100
# Byte6-7: RR_speed_x100   uint16 BE   km/h × 100

WS_FL_OFFSET: int = 0
WS_FR_OFFSET: int = 2
WS_RL_OFFSET: int = 4
WS_RR_OFFSET: int = 6
WS_SCALE: float = 0.01  # raw / 100 → km/h

# ---------------------------------------------------------------------------
# 0x6A3 — DYNAMICS frame layout (8 bytes)
# ---------------------------------------------------------------------------
# Link ECU forwards OEM VDC/steering sensor data.
#
# Byte0-1: Steering_angle_x10   int16 BE   degrees × 10 (negative = right)
# Byte2-3: Yaw_rate_x100        int16 BE   deg/s × 100
# Byte4-5: Lateral_G_x1000      int16 BE   g × 1000
# Byte6-7: Brake_pressure_x10   uint16 BE  bar × 10

DYN_STEER_OFFSET: int = 0
DYN_STEER_SCALE: float = 0.1  # raw / 10 → degrees

DYN_YAW_OFFSET: int = 2
DYN_YAW_SCALE: float = 0.01  # raw / 100 → deg/s

DYN_LATG_OFFSET: int = 4
DYN_LATG_SCALE: float = 0.001  # raw / 1000 → g

DYN_BRAKE_OFFSET: int = 6
DYN_BRAKE_SCALE: float = 0.1  # raw / 10 → bar

# ---------------------------------------------------------------------------
# Staleness / timing
# ---------------------------------------------------------------------------

STALE_TIMEOUT_S: float = 0.5  # Mark data stale after 500 ms with no frame
UI_REFRESH_HZ: int = 20       # UI poll rate
UI_REFRESH_MS: int = 1000 // UI_REFRESH_HZ  # 50 ms

# ---------------------------------------------------------------------------
# Mock mode
# ---------------------------------------------------------------------------

MOCK_ENABLED: bool = True      # Use mock data when CAN bus unavailable
MOCK_DIFF_HZ: int = 50        # Mock DIFF frame rate
MOCK_CONTEXT_HZ: int = 20     # Mock CONTEXT frame rate
MOCK_WHEEL_HZ: int = 50       # Mock wheel speed frame rate
MOCK_DYNAMICS_HZ: int = 50    # Mock dynamics frame rate
