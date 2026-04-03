"""KiSTI - CAN Bus Configuration

Editable constants for the KiSTI publish bus from Link ECU.
Supports G4X and G5 Neo 4 ECU configurations.

Update these when the real Link CAN configuration is finalized.

All arbitration IDs, byte offsets, scaling, and enums are defined here.
The decoder in kisti_can.py imports only from this module.
"""

# ---------------------------------------------------------------------------
# ECU Profile Selection
# ---------------------------------------------------------------------------

ACTIVE_ECU: str = "G5"  # "G4X" or "G5" — determines available CAN frames

# ---------------------------------------------------------------------------
# Arbitration IDs — KiSTI Custom Frames (all ECUs)
# ---------------------------------------------------------------------------

DIFF_FRAME_ID: int = 0x6A0         # 50 Hz from Link ECU
CONTEXT_FRAME_ID: int = 0x6A1      # 20 Hz from Link ECU
WHEEL_SPEED_FRAME_ID: int = 0x6A2  # 50 Hz — individual wheel speeds
DYNAMICS_FRAME_ID: int = 0x6A3     # 50 Hz — steering, yaw, lat-G, brake

# ---------------------------------------------------------------------------
# Arbitration IDs — AiM GPS09 Pro (via Strada CAN)
# ---------------------------------------------------------------------------
# Placeholder IDs — update from Race Studio 3 when hardware arrives.

GPS_FRAME_ID: int = 0x6A4          # 10 Hz — lat/lon position
GPS_EXT_FRAME_ID: int = 0x6A5     # 10 Hz — altitude, speed, heading, sats
IMU_FRAME_ID: int = 0x6A6         # 50 Hz — 3-axis accelerometer
IMU_GYRO_FRAME_ID: int = 0x6A7    # 50 Hz — 3-axis gyroscope

# ---------------------------------------------------------------------------
# Arbitration IDs — G5 Neo 4 Additional Frames
# ---------------------------------------------------------------------------

GENERIC_DASH_BASE_ID: int = 0x3E8  # Single multiplexed CAN ID (PCLink default 1000/0x3E8)
                                   # VERIFY against your PCLink CAN Setup before enabling
GENERIC_DASH_COUNT: int = 14       # 14 sub-frames multiplexed on single ID (byte[0] = frame index)

# G5 Generic Dash sub-frame indices (byte[0] of each message)
# Layout: byte[0]=frame_idx, byte[1]=0x00, bytes[2:8]=three LE int16 signals
# PCLink defaults — confirm against raw CAN sniff before trusting scaling
GD_FRAME_RPM_MAP_TPS: int = 0      # RPM (raw), MAP (kPa×10), TPS (%×10)
GD_FRAME_CLT_IAT_LAMBDA: int = 1   # CLT (°C×10), IAT (°C×10), Lambda1 (λ×1000)
GD_FRAME_OIL_FUEL: int = 2         # OilPress (kPa×10), OilTemp (°C×10), FuelPress (kPa×10)
GD_FRAME_BATT_INJ_ETHANOL: int = 3  # Battery (V×100), InjDuty (%×10), Ethanol (%×10)
GD_FRAME_GEAR_WHEEL_LF_RF: int = 4  # Gear (raw), WheelSpeed_LF (km/h×10), WheelSpeed_RF (km/h×10)
GD_FRAME_WHEEL_LR_RR: int = 5      # WheelSpeed_LR (km/h×10), WheelSpeed_RR (km/h×10), reserved

SI_DRIVE_FRAME_ID: int = 0x6B0    # User CAN: SI Drive state, 10 Hz
SENSOR_FRAME_ID: int = 0x6B1      # User CAN: extended sensors, 20 Hz
KEYPAD_FRAME_ID: int = 0x6B2      # 8-Button Keypad state, on-change

LED_OUTPUT_FRAME_ID: int = 0x6C0   # LED waveform output frame 1, 30 Hz
LED_OUTPUT_FRAME_2_ID: int = 0x6C1 # LED waveform output frame 2, 30 Hz

# ---------------------------------------------------------------------------
# CAN ID Sets
# ---------------------------------------------------------------------------

_BASE_CAN_IDS: set[int] = {
    DIFF_FRAME_ID, CONTEXT_FRAME_ID,
    WHEEL_SPEED_FRAME_ID, DYNAMICS_FRAME_ID,
}

_GPS_IMU_IDS: set[int] = {
    GPS_FRAME_ID, GPS_EXT_FRAME_ID,
    IMU_FRAME_ID, IMU_GYRO_FRAME_ID,
}

_G5_INPUT_IDS: set[int] = {
    GENERIC_DASH_BASE_ID,  # single multiplexed ID — NOT a range
    SI_DRIVE_FRAME_ID,
    SENSOR_FRAME_ID,
    KEYPAD_FRAME_ID,
} | _GPS_IMU_IDS

# IDs we listen for (input)
KISTI_CAN_IDS: set[int] = _BASE_CAN_IDS | (
    _G5_INPUT_IDS if ACTIVE_ECU == "G5" else set()
)

# IDs we send (output) — excluded from listener filter
KISTI_CAN_OUTPUT_IDS: set[int] = {LED_OUTPUT_FRAME_ID, LED_OUTPUT_FRAME_2_ID}

# ---------------------------------------------------------------------------
# CAN interface
# ---------------------------------------------------------------------------

CAN_INTERFACE: str = "can0"
CAN_BUSTYPE: str = "socketcan"
CAN_BITRATE: int = 1_000_000  # 1 Mbps — required by AiM MXG Strada dash

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
# DEPRECATED — Generic Dash offset/scale constants (pre-sniff design)
# ---------------------------------------------------------------------------
# These constants assumed sequential IDs (0x360-0x362) with big-endian uint16,
# 4 signals per frame. The actual G5 Generic Dash protocol is:
#   - Single CAN ID (0x3E8), multiplexed on byte[0], LE int16, 3 signals/frame
#
# These constants are KEPT to avoid import errors in kisti_can.py.
# decode_generic_dash_1/2/3() in kisti_can.py are also incorrect and will be
# replaced post-sniff when real frame IDs and byte order are confirmed.
# Use g5_generic_dash.py (G5GenericDashParser) for new code.

GD1_RPM_OFFSET: int = 0
GD1_RPM_SCALE: float = 1.0

GD1_MAP_OFFSET: int = 2
GD1_MAP_SCALE: float = 0.1

GD1_TPS_OFFSET: int = 4
GD1_TPS_SCALE: float = 0.1

GD1_CLT_OFFSET: int = 6
GD1_CLT_SCALE: float = 0.1

GD2_IAT_OFFSET: int = 0
GD2_IAT_SCALE: float = 0.1

GD2_LAMBDA_OFFSET: int = 2
GD2_LAMBDA_SCALE: float = 0.001

GD2_OIL_PRESS_OFFSET: int = 4
GD2_OIL_PRESS_SCALE: float = 0.1

GD2_OIL_TEMP_OFFSET: int = 6
GD2_OIL_TEMP_SCALE: float = 0.1

GD3_ETHANOL_OFFSET: int = 0
GD3_ETHANOL_SCALE: float = 0.1

GD3_FUEL_PRESS_OFFSET: int = 2
GD3_FUEL_PRESS_SCALE: float = 0.1

GD3_BATT_OFFSET: int = 4
GD3_BATT_SCALE: float = 0.01

GD3_INJ_DUTY_OFFSET: int = 6
GD3_INJ_DUTY_SCALE: float = 0.1

# ---------------------------------------------------------------------------
# 0x6B0 — SI Drive frame layout (8 bytes)
# ---------------------------------------------------------------------------
# Link G5 reads SI Drive switch as analog voltage input, outputs via User CAN.
# Configured in PCLink G5: User CAN Transmit.
#
# Byte0:   SI_Drive_Mode     uint8    0=Intelligent, 1=Sport, 2=Sport Sharp
# Byte1-7: reserved
#
# NOTE: Link ECU OEM CAN reads SI Drive as: 1=Sport Sharp, 2=Intelligent,
# 3=Sport. These values are RE-MAPPED in the Link User CAN stream to our
# simpler 0/1/2 encoding. Verify mapping in PCLink G5 User CAN config.

SI_DRIVE_MODE_OFFSET: int = 0

SI_DRIVE_INTELLIGENT: int = 0
SI_DRIVE_SPORT: int = 1
SI_DRIVE_SPORT_SHARP: int = 2

# ---------------------------------------------------------------------------
# 0x6B1 — Extended Sensor frame (8 bytes)
# ---------------------------------------------------------------------------
# User CAN: additional sensors not in Generic Dash or alternative readings.
#
# Byte0-1: MAP_4bar_kPa_x10    uint16 BE  kPa × 10 (4-bar sensor, 0-400 kPa)
# Byte2-3: IAT_ext_x10         int16 BE   °C × 10 (external IAT sensor)
# Byte4-5: EthanolPct_ext_x10  uint16 BE  % × 10 (Flex Fuel sensor)
# Byte6-7: OilPSI_150_x10      uint16 BE  PSI × 10 (150 PSI sensor)

SENS_MAP_4BAR_OFFSET: int = 0
SENS_MAP_4BAR_SCALE: float = 0.1  # kPa

SENS_IAT_EXT_OFFSET: int = 2
SENS_IAT_EXT_SCALE: float = 0.1  # °C

SENS_ETHANOL_OFFSET: int = 4
SENS_ETHANOL_SCALE: float = 0.1  # %

SENS_OIL_PSI_OFFSET: int = 6
SENS_OIL_PSI_SCALE: float = 0.1  # PSI

# ---------------------------------------------------------------------------
# 0x6B2 — Keypad frame (8 bytes)
# ---------------------------------------------------------------------------
# Link 8-Button Keypad — button state as bitfield. Sent on-change.
#
# Byte0:   ButtonState      uint8  bit0=K1 .. bit7=K8 (1=pressed)
# Byte1:   PrevButtonState  uint8  previous state (for edge detection)
# Byte2-7: reserved

KEYPAD_STATE_OFFSET: int = 0
KEYPAD_PREV_OFFSET: int = 1

KEYPAD_K1: int = 0x01  # Session Start/Stop
KEYPAD_K2: int = 0x02  # Mark Segment
KEYPAD_K3: int = 0x04  # Analyze That Run
KEYPAD_K4: int = 0x08  # Voice Toggle
KEYPAD_K5: int = 0x10  # Coaching Level Cycle
KEYPAD_K6: int = 0x20  # Display Mode Cycle
KEYPAD_K7: int = 0x40  # Reserved
KEYPAD_K8: int = 0x80  # Reserved

# ---------------------------------------------------------------------------
# 0x6A4 — GPS Position frame layout (8 bytes)
# ---------------------------------------------------------------------------
# AiM GPS09 Pro — position data via Strada CAN.
# Placeholder layout — update from Race Studio 3 when hardware arrives.
#
# Byte0-3: Latitude_x100000   int32 BE   degrees × 100000 (±0.00001° ≈ 1m)
# Byte4-7: Longitude_x100000  int32 BE   degrees × 100000

GPS_LAT_OFFSET: int = 0
GPS_LON_OFFSET: int = 4
GPS_COORD_SCALE: float = 0.00001  # raw / 100000 → degrees

# ---------------------------------------------------------------------------
# 0x6A5 — GPS Extended frame layout (8 bytes)
# ---------------------------------------------------------------------------
# Byte0-1: Altitude_m          int16 BE   meters (1m resolution)
# Byte2-3: Speed_mps_x100     uint16 BE  m/s × 100
# Byte4-5: Heading_x10        uint16 BE  degrees × 10 (0-3599)
# Byte6:   Satellites          uint8      0-15
# Byte7:   GPS_Fix_Quality     uint8      0=no fix, 1=2D, 2=3D

GPS_ALT_OFFSET: int = 0
GPS_ALT_SCALE: float = 1.0       # raw → meters (1m resolution)

GPS_SPEED_OFFSET: int = 2
GPS_SPEED_SCALE: float = 0.01    # raw / 100 → m/s

GPS_HEADING_OFFSET: int = 4
GPS_HEADING_SCALE: float = 0.1   # raw / 10 → degrees

GPS_SATS_OFFSET: int = 6
GPS_FIX_OFFSET: int = 7

GPS_FIX_NONE: int = 0
GPS_FIX_2D: int = 1
GPS_FIX_3D: int = 2

# ---------------------------------------------------------------------------
# 0x6A6 — IMU Accelerometer frame layout (8 bytes)
# ---------------------------------------------------------------------------
# AiM GPS09 Pro — 3-axis accelerometer.
#
# Byte0-1: Accel_X_x1000   int16 BE   g × 1000 (longitudinal, +ve = accel)
# Byte2-3: Accel_Y_x1000   int16 BE   g × 1000 (lateral, +ve = right)
# Byte4-5: Accel_Z_x1000   int16 BE   g × 1000 (vertical, +ve = up)
# Byte6-7: reserved

IMU_AX_OFFSET: int = 0
IMU_AY_OFFSET: int = 2
IMU_AZ_OFFSET: int = 4
IMU_ACCEL_SCALE: float = 0.001   # raw / 1000 → g

# ---------------------------------------------------------------------------
# 0x6A7 — IMU Gyroscope frame layout (8 bytes)
# ---------------------------------------------------------------------------
# AiM GPS09 Pro — 3-axis gyroscope.
#
# Byte0-1: Gyro_X_x100   int16 BE   deg/s × 100 (roll rate)
# Byte2-3: Gyro_Y_x100   int16 BE   deg/s × 100 (pitch rate)
# Byte4-5: Gyro_Z_x100   int16 BE   deg/s × 100 (yaw rate)
# Byte6-7: reserved

IMU_GX_OFFSET: int = 0
IMU_GY_OFFSET: int = 2
IMU_GZ_OFFSET: int = 4
IMU_GYRO_SCALE: float = 0.01    # raw / 100 → deg/s

# ---------------------------------------------------------------------------
# 0x6C0-0x6C1 — LED Waveform Output (2 × 8 bytes)
# ---------------------------------------------------------------------------
# KiSTI → external LED controller (Arduino/ESP32) via CAN.
# 10 RGB LEDs controlled via brightness + base color.
#
# NOTE: AiM MXG Strada shift lights are NOT directly addressable via CAN.
# AiM uses internal firmware thresholds configured in Race Studio 3.
# These LED output frames drive a SEPARATE controller for the voice
# waveform visualizer, independent of the AiM dash shift lights.
# AiM shift lights should be configured in RS3 to respond to RPM from
# the Link ECU Generic Dash stream (or a Jetson-published virtual channel).
#
# Frame 0x6C0:
#   Byte0:   LED_Mode         uint8   0=off, 1=waveform, 2=rpm, 3=kitt, 4=warmup
#   Byte1-7: Brightness[0-6]  uint8   0-255 per LED
#
# Frame 0x6C1:
#   Byte0-2: Brightness[7-9]  uint8   0-255 per LED
#   Byte3:   Color_R          uint8   base color red
#   Byte4:   Color_G          uint8   base color green
#   Byte5:   Color_B          uint8   base color blue
#   Byte6-7: reserved

LED_MODE_OFFSET: int = 0
LED_BRIGHTNESS_START: int = 1   # frame 1: bytes 1-7 = LEDs 0-6

LED2_BRIGHTNESS_START: int = 0  # frame 2: bytes 0-2 = LEDs 7-9
LED2_COLOR_R_OFFSET: int = 3
LED2_COLOR_G_OFFSET: int = 4
LED2_COLOR_B_OFFSET: int = 5

LED_MODE_OFF: int = 0
LED_MODE_WAVEFORM: int = 1
LED_MODE_RPM: int = 2
LED_MODE_KITT: int = 3
LED_MODE_WARMUP: int = 4
LED_MODE_GFORCE: int = 5

LED_COUNT: int = 10
LED_OUTPUT_HZ: int = 30  # 30 Hz output rate

# ---------------------------------------------------------------------------
# Staleness / timing
# ---------------------------------------------------------------------------

STALE_TIMEOUT_S: float = 0.5  # Mark data stale after 500 ms with no frame
UI_REFRESH_HZ: int = 20       # UI poll rate
UI_REFRESH_MS: int = 1000 // UI_REFRESH_HZ  # 50 ms

# ---------------------------------------------------------------------------
# Mock mode
# ---------------------------------------------------------------------------

MOCK_ENABLED: bool = True      # Mock data for demo/development (set False for real CAN)
MOCK_DIFF_HZ: int = 20        # Mock DIFF frame rate
MOCK_CONTEXT_HZ: int = 10     # Mock CONTEXT frame rate
MOCK_WHEEL_HZ: int = 20       # Mock wheel speed frame rate
MOCK_DYNAMICS_HZ: int = 20    # Mock dynamics frame rate
MOCK_GENERIC_DASH_HZ: int = 20  # Mock Generic Dash rate
MOCK_SI_DRIVE_HZ: int = 10    # Mock SI Drive rate
MOCK_SENSOR_HZ: int = 10      # Mock extended sensor rate
MOCK_GPS_HZ: int = 10         # Mock GPS frame rate (GPS09 Pro)
MOCK_IMU_HZ: int = 20         # Mock IMU frame rate (GPS09 Pro)
MOCK_FLIR_HZ: int = 5         # Mock FLIR Lepton frame rate
