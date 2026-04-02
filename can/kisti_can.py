"""KiSTI - CAN Listener, Decoder & Output

Reads Link ECU CAN frames on socketcan, decodes all frame types, and
pushes updates to DiffStateBridge. Supports G4X (4 frames) and G5 Neo 4
(4 + Generic Dash + SI Drive + sensors + keypad).

Also provides CAN output for LED waveform control on the MXG Strada dash.

Falls back to mock data generation if python-can is unavailable or
the CAN interface doesn't exist.
"""

from __future__ import annotations

import logging
import math
import random
import struct
import threading
import time
from typing import Optional

from PySide6.QtCore import QObject, QTimer

from can.can_config import (
    ACTIVE_ECU,
    CAN_BUSTYPE,
    CAN_INTERFACE,
    CONTEXT_FRAME_ID,
    CTX_GEAR_OFFSET,
    CTX_SPEED_OFFSET,
    CTX_SPEED_SCALE,
    CTX_THROTTLE_OFFSET,
    CTX_THROTTLE_SCALE,
    DIFF_DCCD_CMD_OFFSET,
    DIFF_DCCD_CMD_SCALE,
    DIFF_DCCD_DIAL_NA,
    DIFF_DCCD_DIAL_OFFSET,
    DIFF_DCCD_DIAL_SCALE,
    DIFF_FLAG_ABS,
    DIFF_FLAG_BRAKE,
    DIFF_FLAG_HANDBRAKE,
    DIFF_FLAG_VDC_TC,
    DIFF_FLAGS_OFFSET,
    DIFF_FRAME_ID,
    DIFF_SLIP_NA,
    DIFF_SLIP_OFFSET,
    DIFF_SLIP_SCALE,
    DIFF_SURFACE_OFFSET,
    DYN_BRAKE_OFFSET,
    DYN_BRAKE_SCALE,
    DYN_LATG_OFFSET,
    DYN_LATG_SCALE,
    DYN_STEER_OFFSET,
    DYN_STEER_SCALE,
    DYN_YAW_OFFSET,
    DYN_YAW_SCALE,
    DYNAMICS_FRAME_ID,
    GD1_CLT_OFFSET,
    GD1_CLT_SCALE,
    GD1_MAP_OFFSET,
    GD1_MAP_SCALE,
    GD1_RPM_OFFSET,
    GD1_RPM_SCALE,
    GD1_TPS_OFFSET,
    GD1_TPS_SCALE,
    GD2_IAT_OFFSET,
    GD2_IAT_SCALE,
    GD2_LAMBDA_OFFSET,
    GD2_LAMBDA_SCALE,
    GD2_OIL_PRESS_OFFSET,
    GD2_OIL_PRESS_SCALE,
    GD2_OIL_TEMP_OFFSET,
    GD2_OIL_TEMP_SCALE,
    GD3_BATT_OFFSET,
    GD3_BATT_SCALE,
    GD3_ETHANOL_OFFSET,
    GD3_ETHANOL_SCALE,
    GD3_FUEL_PRESS_OFFSET,
    GD3_FUEL_PRESS_SCALE,
    GD3_INJ_DUTY_OFFSET,
    GD3_INJ_DUTY_SCALE,
    GENERIC_DASH_BASE_ID,
    KEYPAD_FRAME_ID,
    KEYPAD_PREV_OFFSET,
    KEYPAD_STATE_OFFSET,
    KISTI_CAN_IDS,
    KISTI_CAN_OUTPUT_IDS,
    LED2_BRIGHTNESS_START,
    LED2_COLOR_B_OFFSET,
    LED2_COLOR_G_OFFSET,
    LED2_COLOR_R_OFFSET,
    LED_BRIGHTNESS_START,
    LED_COUNT,
    LED_MODE_OFFSET,
    LED_OUTPUT_FRAME_2_ID,
    LED_OUTPUT_FRAME_ID,
    LED_OUTPUT_HZ,
    GPS_ALT_OFFSET,
    GPS_ALT_SCALE,
    GPS_COORD_SCALE,
    GPS_EXT_FRAME_ID,
    GPS_FIX_OFFSET,
    GPS_FRAME_ID,
    GPS_HEADING_OFFSET,
    GPS_HEADING_SCALE,
    GPS_LAT_OFFSET,
    GPS_LON_OFFSET,
    GPS_SATS_OFFSET,
    GPS_SPEED_OFFSET,
    GPS_SPEED_SCALE,
    IMU_ACCEL_SCALE,
    IMU_AX_OFFSET,
    IMU_AY_OFFSET,
    IMU_AZ_OFFSET,
    IMU_FRAME_ID,
    IMU_GYRO_FRAME_ID,
    IMU_GYRO_SCALE,
    IMU_GX_OFFSET,
    IMU_GY_OFFSET,
    IMU_GZ_OFFSET,
    MOCK_CONTEXT_HZ,
    MOCK_DIFF_HZ,
    MOCK_DYNAMICS_HZ,
    MOCK_ENABLED,
    MOCK_FLIR_HZ,
    MOCK_GENERIC_DASH_HZ,
    MOCK_GPS_HZ,
    MOCK_IMU_HZ,
    MOCK_SENSOR_HZ,
    MOCK_SI_DRIVE_HZ,
    MOCK_WHEEL_HZ,
    SENS_ETHANOL_OFFSET,
    SENS_ETHANOL_SCALE,
    SENS_IAT_EXT_OFFSET,
    SENS_IAT_EXT_SCALE,
    SENS_MAP_4BAR_OFFSET,
    SENS_MAP_4BAR_SCALE,
    SENS_OIL_PSI_OFFSET,
    SENS_OIL_PSI_SCALE,
    SENSOR_FRAME_ID,
    SI_DRIVE_FRAME_ID,
    SI_DRIVE_MODE_OFFSET,
    STALE_TIMEOUT_S,
    WHEEL_SPEED_FRAME_ID,
    WS_FL_OFFSET,
    WS_FR_OFFSET,
    WS_RL_OFFSET,
    WS_RR_OFFSET,
    WS_SCALE,
)
from model.vehicle_state import DiffStateBridge, SurfaceState

log = logging.getLogger("kisti.can")


# ---------------------------------------------------------------------------
# Pure decoding functions (no side effects — unit-testable)
# ---------------------------------------------------------------------------

def decode_diff_frame(data: bytes) -> dict:
    """Decode a DIFF frame (0x6A0, 8 bytes) into a dict of typed values.

    Returns:
        dict with keys: dccd_command_pct, dccd_dial_pct (or None),
        surface_state, brake, handbrake, abs_active, vdc_tc,
        slip_delta (or None).

    Raises:
        ValueError: if data is too short.
    """
    if len(data) < 8:
        raise ValueError(f"DIFF frame too short: {len(data)} bytes (need 8)")

    # DCCD command %
    raw_cmd = struct.unpack_from(">H", data, DIFF_DCCD_CMD_OFFSET)[0]
    dccd_command_pct = raw_cmd * DIFF_DCCD_CMD_SCALE

    # DCCD dial % (optional)
    raw_dial = struct.unpack_from(">H", data, DIFF_DCCD_DIAL_OFFSET)[0]
    dccd_dial_pct: Optional[float] = None
    if raw_dial != DIFF_DCCD_DIAL_NA:
        dccd_dial_pct = raw_dial * DIFF_DCCD_DIAL_SCALE

    # Surface state
    raw_surface = data[DIFF_SURFACE_OFFSET]
    try:
        surface_state = SurfaceState(raw_surface)
    except ValueError:
        surface_state = SurfaceState.DRY  # fallback

    # Flags
    flags = data[DIFF_FLAGS_OFFSET]
    brake = bool(flags & DIFF_FLAG_BRAKE)
    handbrake = bool(flags & DIFF_FLAG_HANDBRAKE)
    abs_active = bool(flags & DIFF_FLAG_ABS)
    vdc_tc = bool(flags & DIFF_FLAG_VDC_TC)

    # Slip delta (signed)
    raw_slip = struct.unpack_from(">h", data, DIFF_SLIP_OFFSET)[0]
    slip_delta: Optional[float] = None
    if raw_slip != DIFF_SLIP_NA:
        slip_delta = raw_slip * DIFF_SLIP_SCALE

    return {
        "dccd_command_pct": dccd_command_pct,
        "dccd_dial_pct": dccd_dial_pct,
        "surface_state": surface_state,
        "brake": brake,
        "handbrake": handbrake,
        "abs_active": abs_active,
        "vdc_tc": vdc_tc,
        "slip_delta": slip_delta,
    }


def decode_context_frame(data: bytes) -> dict:
    """Decode a CONTEXT frame (0x6A1, 8 bytes) into a dict of typed values.

    Returns:
        dict with keys: gear, speed_kph, throttle_pct.
    """
    if len(data) < 5:
        raise ValueError(f"CONTEXT frame too short: {len(data)} bytes (need 5)")

    gear = data[CTX_GEAR_OFFSET]
    raw_speed = struct.unpack_from(">H", data, CTX_SPEED_OFFSET)[0]
    speed_kph = raw_speed * CTX_SPEED_SCALE
    raw_throttle = struct.unpack_from(">H", data, CTX_THROTTLE_OFFSET)[0]
    throttle_pct = raw_throttle * CTX_THROTTLE_SCALE

    return {
        "gear": gear,
        "speed_kph": speed_kph,
        "throttle_pct": throttle_pct,
    }


def encode_diff_frame(
    dccd_cmd: float,
    dccd_dial: Optional[float],
    surface: int,
    flags: int,
    slip: Optional[float],
) -> bytes:
    """Encode a DIFF frame for testing / mock generation.

    Args:
        dccd_cmd: DCCD command 0.0-100.0
        dccd_dial: DCCD dial 0.0-100.0 or None
        surface: surface state enum int
        flags: bitfield
        slip: slip delta in km/h or None
    """
    raw_cmd = int(round(dccd_cmd / DIFF_DCCD_CMD_SCALE))
    raw_dial = DIFF_DCCD_DIAL_NA if dccd_dial is None else int(round(dccd_dial / DIFF_DCCD_DIAL_SCALE))
    raw_slip = DIFF_SLIP_NA if slip is None else int(round(slip / DIFF_SLIP_SCALE))
    return struct.pack(">HHBBh", raw_cmd, raw_dial, surface, flags, raw_slip)


def encode_context_frame(gear: int, speed_kph: float, throttle_pct: float) -> bytes:
    """Encode a CONTEXT frame for testing / mock generation."""
    raw_speed = int(round(speed_kph / CTX_SPEED_SCALE))
    raw_throttle = int(round(throttle_pct / CTX_THROTTLE_SCALE))
    return struct.pack(">BHH", gear, raw_speed, raw_throttle) + b"\x00\x00\x00"


def decode_wheel_speed_frame(data: bytes) -> dict:
    """Decode a WHEEL_SPEED frame (0x6A2, 8 bytes).

    Returns:
        dict with keys: fl, fr, rl, rr (all km/h).
    """
    if len(data) < 8:
        raise ValueError(f"WHEEL_SPEED frame too short: {len(data)} bytes (need 8)")

    fl = struct.unpack_from(">H", data, WS_FL_OFFSET)[0] * WS_SCALE
    fr = struct.unpack_from(">H", data, WS_FR_OFFSET)[0] * WS_SCALE
    rl = struct.unpack_from(">H", data, WS_RL_OFFSET)[0] * WS_SCALE
    rr = struct.unpack_from(">H", data, WS_RR_OFFSET)[0] * WS_SCALE

    return {"fl": fl, "fr": fr, "rl": rl, "rr": rr}


def decode_dynamics_frame(data: bytes) -> dict:
    """Decode a DYNAMICS frame (0x6A3, 8 bytes).

    Returns:
        dict with keys: steering_angle (deg), yaw_rate (deg/s),
        lateral_g (g), brake_pressure (bar).
    """
    if len(data) < 8:
        raise ValueError(f"DYNAMICS frame too short: {len(data)} bytes (need 8)")

    steering_angle = struct.unpack_from(">h", data, DYN_STEER_OFFSET)[0] * DYN_STEER_SCALE
    yaw_rate = struct.unpack_from(">h", data, DYN_YAW_OFFSET)[0] * DYN_YAW_SCALE
    lateral_g = struct.unpack_from(">h", data, DYN_LATG_OFFSET)[0] * DYN_LATG_SCALE
    brake_pressure = struct.unpack_from(">H", data, DYN_BRAKE_OFFSET)[0] * DYN_BRAKE_SCALE

    return {
        "steering_angle": steering_angle,
        "yaw_rate": yaw_rate,
        "lateral_g": lateral_g,
        "brake_pressure": brake_pressure,
    }


# ---------------------------------------------------------------------------
# G5 Neo 4 decode functions
# ---------------------------------------------------------------------------

def decode_generic_dash_1(data: bytes) -> dict:
    """Decode Generic Dash frame 1 (0x360, 8 bytes).

    Returns:
        dict with keys: rpm, map_kpa, tps, coolant_temp.
    """
    if len(data) < 8:
        raise ValueError(f"GenDash1 frame too short: {len(data)} bytes (need 8)")

    rpm = struct.unpack_from(">H", data, GD1_RPM_OFFSET)[0] * GD1_RPM_SCALE
    map_kpa = struct.unpack_from(">H", data, GD1_MAP_OFFSET)[0] * GD1_MAP_SCALE
    tps = struct.unpack_from(">H", data, GD1_TPS_OFFSET)[0] * GD1_TPS_SCALE
    coolant_temp = struct.unpack_from(">h", data, GD1_CLT_OFFSET)[0] * GD1_CLT_SCALE

    return {"rpm": rpm, "map_kpa": map_kpa, "tps": tps, "coolant_temp": coolant_temp}


def decode_generic_dash_2(data: bytes) -> dict:
    """Decode Generic Dash frame 2 (0x361, 8 bytes).

    Returns:
        dict with keys: iat_c, lambda_1, oil_pressure_kpa, oil_temp_c.
    """
    if len(data) < 8:
        raise ValueError(f"GenDash2 frame too short: {len(data)} bytes (need 8)")

    iat_c = struct.unpack_from(">h", data, GD2_IAT_OFFSET)[0] * GD2_IAT_SCALE
    lambda_1 = struct.unpack_from(">H", data, GD2_LAMBDA_OFFSET)[0] * GD2_LAMBDA_SCALE
    oil_pressure_kpa = struct.unpack_from(">H", data, GD2_OIL_PRESS_OFFSET)[0] * GD2_OIL_PRESS_SCALE
    oil_temp_c = struct.unpack_from(">h", data, GD2_OIL_TEMP_OFFSET)[0] * GD2_OIL_TEMP_SCALE

    return {
        "iat_c": iat_c,
        "lambda_1": lambda_1,
        "oil_pressure_kpa": oil_pressure_kpa,
        "oil_temp_c": oil_temp_c,
    }


def decode_generic_dash_3(data: bytes) -> dict:
    """Decode Generic Dash frame 3 (0x362, 8 bytes).

    Returns:
        dict with keys: ethanol_pct, fuel_pressure_kpa, battery_v, injector_duty.
    """
    if len(data) < 8:
        raise ValueError(f"GenDash3 frame too short: {len(data)} bytes (need 8)")

    ethanol_pct = struct.unpack_from(">H", data, GD3_ETHANOL_OFFSET)[0] * GD3_ETHANOL_SCALE
    fuel_pressure_kpa = struct.unpack_from(">H", data, GD3_FUEL_PRESS_OFFSET)[0] * GD3_FUEL_PRESS_SCALE
    battery_v = struct.unpack_from(">H", data, GD3_BATT_OFFSET)[0] * GD3_BATT_SCALE
    injector_duty = struct.unpack_from(">H", data, GD3_INJ_DUTY_OFFSET)[0] * GD3_INJ_DUTY_SCALE

    return {
        "ethanol_pct": ethanol_pct,
        "fuel_pressure_kpa": fuel_pressure_kpa,
        "battery_v": battery_v,
        "injector_duty": injector_duty,
    }


def decode_si_drive_frame(data: bytes) -> dict:
    """Decode SI Drive frame (0x6B0, 8 bytes).

    Returns:
        dict with key: mode (int: 0=I, 1=S, 2=S#).
    """
    if len(data) < 1:
        raise ValueError(f"SI Drive frame too short: {len(data)} bytes (need 1)")

    mode = data[SI_DRIVE_MODE_OFFSET]
    return {"mode": mode}


def decode_sensor_frame(data: bytes) -> dict:
    """Decode extended sensor frame (0x6B1, 8 bytes).

    Returns:
        dict with keys: map_4bar_kpa, iat_ext_c, ethanol_ext_pct, oil_psi.
    """
    if len(data) < 8:
        raise ValueError(f"Sensor frame too short: {len(data)} bytes (need 8)")

    map_4bar_kpa = struct.unpack_from(">H", data, SENS_MAP_4BAR_OFFSET)[0] * SENS_MAP_4BAR_SCALE
    iat_ext_c = struct.unpack_from(">h", data, SENS_IAT_EXT_OFFSET)[0] * SENS_IAT_EXT_SCALE
    ethanol_ext_pct = struct.unpack_from(">H", data, SENS_ETHANOL_OFFSET)[0] * SENS_ETHANOL_SCALE
    oil_psi = struct.unpack_from(">H", data, SENS_OIL_PSI_OFFSET)[0] * SENS_OIL_PSI_SCALE

    return {
        "map_4bar_kpa": map_4bar_kpa,
        "iat_ext_c": iat_ext_c,
        "ethanol_ext_pct": ethanol_ext_pct,
        "oil_psi": oil_psi,
    }


def decode_keypad_frame(data: bytes) -> dict:
    """Decode keypad frame (0x6B2, 8 bytes).

    Returns:
        dict with keys: state (int bitfield), prev_state (int bitfield).
    """
    if len(data) < 2:
        raise ValueError(f"Keypad frame too short: {len(data)} bytes (need 2)")

    state = data[KEYPAD_STATE_OFFSET]
    prev_state = data[KEYPAD_PREV_OFFSET]
    return {"state": state, "prev_state": prev_state}


# ---------------------------------------------------------------------------
# GPS09 Pro decode functions
# ---------------------------------------------------------------------------

def decode_gps_frame(data: bytes) -> dict:
    """Decode GPS position frame (0x6A4, 8 bytes).

    Returns:
        dict with keys: latitude (degrees), longitude (degrees).
    """
    if len(data) < 8:
        raise ValueError(f"GPS frame too short: {len(data)} bytes (need 8)")

    lat_raw = struct.unpack_from(">i", data, GPS_LAT_OFFSET)[0]
    lon_raw = struct.unpack_from(">i", data, GPS_LON_OFFSET)[0]
    return {
        "latitude": lat_raw * GPS_COORD_SCALE,
        "longitude": lon_raw * GPS_COORD_SCALE,
    }


def decode_gps_ext_frame(data: bytes) -> dict:
    """Decode GPS extended frame (0x6A5, 8 bytes).

    Returns:
        dict with keys: altitude_m, speed_mps, heading, satellites, fix_quality.
    """
    if len(data) < 8:
        raise ValueError(f"GPS ext frame too short: {len(data)} bytes (need 8)")

    altitude_m = struct.unpack_from(">h", data, GPS_ALT_OFFSET)[0] * GPS_ALT_SCALE
    speed_mps = struct.unpack_from(">H", data, GPS_SPEED_OFFSET)[0] * GPS_SPEED_SCALE
    heading = struct.unpack_from(">H", data, GPS_HEADING_OFFSET)[0] * GPS_HEADING_SCALE
    satellites = data[GPS_SATS_OFFSET]
    fix_quality = data[GPS_FIX_OFFSET]

    return {
        "altitude_m": altitude_m,
        "speed_mps": speed_mps,
        "heading": heading,
        "satellites": satellites,
        "fix_quality": fix_quality,
    }


def decode_imu_frame(data: bytes) -> dict:
    """Decode IMU accelerometer frame (0x6A6, 8 bytes).

    Returns:
        dict with keys: accel_x, accel_y, accel_z (all in g).
    """
    if len(data) < 6:
        raise ValueError(f"IMU frame too short: {len(data)} bytes (need 6)")

    accel_x = struct.unpack_from(">h", data, IMU_AX_OFFSET)[0] * IMU_ACCEL_SCALE
    accel_y = struct.unpack_from(">h", data, IMU_AY_OFFSET)[0] * IMU_ACCEL_SCALE
    accel_z = struct.unpack_from(">h", data, IMU_AZ_OFFSET)[0] * IMU_ACCEL_SCALE
    return {"accel_x": accel_x, "accel_y": accel_y, "accel_z": accel_z}


def decode_imu_gyro_frame(data: bytes) -> dict:
    """Decode IMU gyroscope frame (0x6A7, 8 bytes).

    Returns:
        dict with keys: gyro_x, gyro_y, gyro_z (all in deg/s).
    """
    if len(data) < 6:
        raise ValueError(f"IMU gyro frame too short: {len(data)} bytes (need 6)")

    gyro_x = struct.unpack_from(">h", data, IMU_GX_OFFSET)[0] * IMU_GYRO_SCALE
    gyro_y = struct.unpack_from(">h", data, IMU_GY_OFFSET)[0] * IMU_GYRO_SCALE
    gyro_z = struct.unpack_from(">h", data, IMU_GZ_OFFSET)[0] * IMU_GYRO_SCALE
    return {"gyro_x": gyro_x, "gyro_y": gyro_y, "gyro_z": gyro_z}


# ---------------------------------------------------------------------------
# G5 Neo 4 encode functions (for testing / mock generation)
# ---------------------------------------------------------------------------

def encode_generic_dash_1(
    rpm: float, map_kpa: float, tps: float, coolant_temp: float,
) -> bytes:
    """Encode Generic Dash frame 1 for testing."""
    raw_rpm = int(round(rpm / GD1_RPM_SCALE))
    raw_map = int(round(map_kpa / GD1_MAP_SCALE))
    raw_tps = int(round(tps / GD1_TPS_SCALE))
    raw_clt = int(round(coolant_temp / GD1_CLT_SCALE))
    return struct.pack(">HHHh", raw_rpm, raw_map, raw_tps, raw_clt)


def encode_generic_dash_2(
    iat_c: float, lambda_1: float, oil_pressure_kpa: float, oil_temp_c: float,
) -> bytes:
    """Encode Generic Dash frame 2 for testing."""
    raw_iat = int(round(iat_c / GD2_IAT_SCALE))
    raw_lambda = int(round(lambda_1 / GD2_LAMBDA_SCALE))
    raw_oil_p = int(round(oil_pressure_kpa / GD2_OIL_PRESS_SCALE))
    raw_oil_t = int(round(oil_temp_c / GD2_OIL_TEMP_SCALE))
    return struct.pack(">hHHh", raw_iat, raw_lambda, raw_oil_p, raw_oil_t)


def encode_generic_dash_3(
    ethanol_pct: float, fuel_pressure_kpa: float, battery_v: float, injector_duty: float,
) -> bytes:
    """Encode Generic Dash frame 3 for testing."""
    raw_eth = int(round(ethanol_pct / GD3_ETHANOL_SCALE))
    raw_fuel = int(round(fuel_pressure_kpa / GD3_FUEL_PRESS_SCALE))
    raw_batt = int(round(battery_v / GD3_BATT_SCALE))
    raw_inj = int(round(injector_duty / GD3_INJ_DUTY_SCALE))
    return struct.pack(">HHHH", raw_eth, raw_fuel, raw_batt, raw_inj)


def encode_si_drive_frame(mode: int) -> bytes:
    """Encode SI Drive frame for testing."""
    return struct.pack(">B", mode) + b"\x00" * 7


def encode_sensor_frame(
    map_4bar_kpa: float, iat_ext_c: float, ethanol_ext_pct: float, oil_psi: float,
) -> bytes:
    """Encode extended sensor frame for testing."""
    raw_map = int(round(map_4bar_kpa / SENS_MAP_4BAR_SCALE))
    raw_iat = int(round(iat_ext_c / SENS_IAT_EXT_SCALE))
    raw_eth = int(round(ethanol_ext_pct / SENS_ETHANOL_SCALE))
    raw_oil = int(round(oil_psi / SENS_OIL_PSI_SCALE))
    return struct.pack(">HhHH", raw_map, raw_iat, raw_eth, raw_oil)


def encode_keypad_frame(state: int, prev_state: int) -> bytes:
    """Encode keypad frame for testing."""
    return struct.pack(">BB", state, prev_state) + b"\x00" * 6


# ---------------------------------------------------------------------------
# GPS09 Pro encode functions (for testing / mock generation)
# ---------------------------------------------------------------------------

def encode_gps_frame(latitude: float, longitude: float) -> bytes:
    """Encode GPS position frame (0x6A4) for testing."""
    raw_lat = int(round(latitude / GPS_COORD_SCALE))
    raw_lon = int(round(longitude / GPS_COORD_SCALE))
    return struct.pack(">ii", raw_lat, raw_lon)


def encode_gps_ext_frame(
    altitude_m: float, speed_mps: float, heading: float,
    satellites: int, fix_quality: int,
) -> bytes:
    """Encode GPS extended frame (0x6A5) for testing."""
    raw_alt = int(round(altitude_m / GPS_ALT_SCALE))
    raw_speed = int(round(speed_mps / GPS_SPEED_SCALE))
    raw_heading = int(round(heading / GPS_HEADING_SCALE))
    return struct.pack(">hHHBB", raw_alt, raw_speed, raw_heading, satellites, fix_quality)


def encode_imu_frame(accel_x: float, accel_y: float, accel_z: float) -> bytes:
    """Encode IMU accelerometer frame (0x6A6) for testing."""
    raw_ax = int(round(accel_x / IMU_ACCEL_SCALE))
    raw_ay = int(round(accel_y / IMU_ACCEL_SCALE))
    raw_az = int(round(accel_z / IMU_ACCEL_SCALE))
    return struct.pack(">hhh", raw_ax, raw_ay, raw_az) + b"\x00\x00"


def encode_imu_gyro_frame(gyro_x: float, gyro_y: float, gyro_z: float) -> bytes:
    """Encode IMU gyroscope frame (0x6A7) for testing."""
    raw_gx = int(round(gyro_x / IMU_GYRO_SCALE))
    raw_gy = int(round(gyro_y / IMU_GYRO_SCALE))
    raw_gz = int(round(gyro_z / IMU_GYRO_SCALE))
    return struct.pack(">hhh", raw_gx, raw_gy, raw_gz) + b"\x00\x00"


def encode_led_output(
    mode: int, brightnesses: list[int], color_r: int, color_g: int, color_b: int,
) -> tuple[bytes, bytes]:
    """Encode LED output frames (0x6C0 + 0x6C1) for the MXG Strada dash.

    Args:
        mode: LED mode (0=off, 1=waveform, 2=rpm, 3=kitt, 4=warmup)
        brightnesses: list of 10 brightness values (0-255)
        color_r, color_g, color_b: base color (0-255 each)

    Returns:
        Tuple of (frame_1_bytes, frame_2_bytes).
    """
    b = brightnesses + [0] * (LED_COUNT - len(brightnesses))  # pad to 10
    frame1 = struct.pack(">BBBBBBB B", mode, b[0], b[1], b[2], b[3], b[4], b[5], b[6])
    frame2 = struct.pack(">BBB BBB BB", b[7], b[8], b[9], color_r, color_g, color_b, 0, 0)
    return frame1, frame2


# ---------------------------------------------------------------------------
# CAN Listener Thread
# ---------------------------------------------------------------------------

class CanListenerThread(threading.Thread):
    """Background thread that reads CAN frames and updates DiffStateBridge.

    Runs until stop() is called.  Handles connection errors gracefully.
    """

    def __init__(self, bridge: DiffStateBridge, interface: str = CAN_INTERFACE) -> None:
        super().__init__(daemon=True, name="kisti-can-listener")
        self._bridge = bridge
        self._interface = interface
        self._running = threading.Event()
        self._running.set()

    def stop(self) -> None:
        self._running.clear()

    def run(self) -> None:
        try:
            import can as python_can  # type: ignore[import-untyped]
        except ImportError:
            log.warning("python-can not installed — CAN listener not started")
            self._bridge.set_disconnected()
            return

        bus = None
        try:
            bus = python_can.Bus(
                interface=CAN_BUSTYPE,
                channel=self._interface,
                receive_own_messages=False,
            )
            log.info("CAN bus opened on %s", self._interface)
        except Exception as exc:
            log.warning("Failed to open CAN bus %s: %s", self._interface, exc)
            self._bridge.set_disconnected()
            return

        try:
            while self._running.is_set():
                msg = bus.recv(timeout=0.1)
                if msg is None:
                    continue
                if msg.arbitration_id not in KISTI_CAN_IDS:
                    continue

                try:
                    self._dispatch_frame(msg.arbitration_id, msg.data)
                except (ValueError, struct.error) as exc:
                    log.debug("Decode error on 0x%03X: %s", msg.arbitration_id, exc)
        finally:
            bus.shutdown()
            log.info("CAN bus closed")

    def _dispatch_frame(self, arb_id: int, data: bytes) -> None:
        """Route a CAN frame to the appropriate decoder and bridge update."""
        if arb_id == DIFF_FRAME_ID:
            d = decode_diff_frame(data)
            self._bridge.update_diff(**d)
        elif arb_id == CONTEXT_FRAME_ID:
            d = decode_context_frame(data)
            self._bridge.update_context(**d)
        elif arb_id == WHEEL_SPEED_FRAME_ID:
            d = decode_wheel_speed_frame(data)
            self._bridge.update_wheel_speeds(**d)
        elif arb_id == DYNAMICS_FRAME_ID:
            d = decode_dynamics_frame(data)
            self._bridge.update_dynamics(**d)
        # G5 Neo 4 frames
        elif arb_id == GENERIC_DASH_BASE_ID:
            d = decode_generic_dash_1(data)
            self._bridge.update_generic_dash_1(**d)
        elif arb_id == GENERIC_DASH_BASE_ID + 1:
            d = decode_generic_dash_2(data)
            self._bridge.update_generic_dash_2(**d)
        elif arb_id == GENERIC_DASH_BASE_ID + 2:
            d = decode_generic_dash_3(data)
            self._bridge.update_generic_dash_3(**d)
        elif arb_id == SI_DRIVE_FRAME_ID:
            d = decode_si_drive_frame(data)
            self._bridge.update_si_drive(**d)
        elif arb_id == SENSOR_FRAME_ID:
            d = decode_sensor_frame(data)
            self._bridge.update_sensors(**d)
        elif arb_id == KEYPAD_FRAME_ID:
            d = decode_keypad_frame(data)
            self._bridge.update_keypad(**d)
        # GPS09 Pro frames
        elif arb_id == GPS_FRAME_ID:
            d = decode_gps_frame(data)
            self._bridge.update_gps(**d)
        elif arb_id == GPS_EXT_FRAME_ID:
            d = decode_gps_ext_frame(data)
            self._bridge.update_gps_ext(**d)
        elif arb_id == IMU_FRAME_ID:
            d = decode_imu_frame(data)
            self._bridge.update_imu(**d)
        elif arb_id == IMU_GYRO_FRAME_ID:
            d = decode_imu_gyro_frame(data)
            self._bridge.update_imu_gyro(**d)


# ---------------------------------------------------------------------------
# CAN Output Thread (LED waveform → MXG Strada dash)
# ---------------------------------------------------------------------------

class CanOutputThread(threading.Thread):
    """Background thread that sends LED waveform frames to the MXG Strada dash.

    Reads LED state from a shared buffer and sends CAN frames at LED_OUTPUT_HZ.
    """

    def __init__(self, interface: str = CAN_INTERFACE) -> None:
        super().__init__(daemon=True, name="kisti-can-output")
        self._interface = interface
        self._running = threading.Event()
        self._running.set()
        self._lock = threading.Lock()
        self._mode: int = 0
        self._brightnesses: list[int] = [0] * LED_COUNT
        self._color: tuple[int, int, int] = (0, 0, 0)

    def stop(self) -> None:
        self._running.clear()

    def set_leds(
        self,
        mode: int,
        brightnesses: list[int],
        color_r: int = 0,
        color_g: int = 0,
        color_b: int = 0,
    ) -> None:
        """Update LED state (thread-safe). Called from voice/mode managers."""
        with self._lock:
            self._mode = mode
            self._brightnesses = list(brightnesses[:LED_COUNT])
            while len(self._brightnesses) < LED_COUNT:
                self._brightnesses.append(0)
            self._color = (color_r, color_g, color_b)

    def run(self) -> None:
        try:
            import can as python_can  # type: ignore[import-untyped]
        except ImportError:
            log.warning("python-can not installed — CAN output not started")
            return

        bus = None
        try:
            bus = python_can.Bus(
                interface=CAN_BUSTYPE,
                channel=self._interface,
                receive_own_messages=False,
            )
            log.info("CAN output bus opened on %s", self._interface)
        except Exception as exc:
            log.warning("Failed to open CAN output bus: %s", exc)
            return

        interval = 1.0 / LED_OUTPUT_HZ
        try:
            while self._running.is_set():
                with self._lock:
                    mode = self._mode
                    brights = list(self._brightnesses)
                    r, g, b = self._color

                frame1, frame2 = encode_led_output(mode, brights, r, g, b)

                try:
                    msg1 = python_can.Message(
                        arbitration_id=LED_OUTPUT_FRAME_ID,
                        data=frame1,
                        is_extended_id=False,
                    )
                    msg2 = python_can.Message(
                        arbitration_id=LED_OUTPUT_FRAME_2_ID,
                        data=frame2,
                        is_extended_id=False,
                    )
                    bus.send(msg1)
                    bus.send(msg2)
                except Exception as exc:
                    log.debug("CAN output send error: %s", exc)

                time.sleep(interval)
        finally:
            bus.shutdown()
            log.info("CAN output bus closed")


# ---------------------------------------------------------------------------
# Mock Data Generator (runs on Qt main thread via QTimer)
# ---------------------------------------------------------------------------

# Simplified Laguna Seca circuit waypoints (clockwise direction).
# Designed to cross the seed S/F line and all 3 sector lines in order.
# S/F:  (36.58432, -121.75560) → (36.58406, -121.75525)
# Sec1: (36.58680, -121.75710) → (36.58650, -121.75680)
# Sec2: (36.58220, -121.74960) → (36.58195, -121.74925)
# Sec3: (36.58510, -121.75370) → (36.58480, -121.75345)
_LAGUNA_SECA_WAYPOINTS: list[tuple[float, float]] = [
    (36.58450, -121.75490),  # 0: Past S/F, heading NE
    (36.58550, -121.75580),  # 1: T1-T2, heading NW
    (36.58620, -121.75680),  # 2: Before Sector 1 (S of line)
    (36.58720, -121.75720),  # 3: Past Sector 1 (N of line)
    (36.58700, -121.75500),  # 4: T5-T6, heading E
    (36.58550, -121.75100),  # 5: Back straight, heading SE
    (36.58270, -121.74910),  # 6: Before Sector 2 (NE of line)
    (36.58170, -121.74970),  # 7: Past Sector 2 (SW of line)
    (36.58200, -121.75100),  # 8: Rainey Curve, heading W
    (36.58350, -121.75200),  # 9: Heading NW
    (36.58540, -121.75340),  # 10: Before Sector 3 (NE of line)
    (36.58450, -121.75380),  # 11: Past Sector 3 (SW of line)
    (36.58390, -121.75590),  # 12: Final approach to S/F
]

# Precompute segment distances and cumulative distance for interpolation
def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371_000.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

_CIRCUIT_SEG_DIST: list[float] = []
_CIRCUIT_CUM_DIST: list[float] = [0.0]
for _i in range(len(_LAGUNA_SECA_WAYPOINTS)):
    _j = (_i + 1) % len(_LAGUNA_SECA_WAYPOINTS)
    _d = _haversine_m(
        _LAGUNA_SECA_WAYPOINTS[_i][0], _LAGUNA_SECA_WAYPOINTS[_i][1],
        _LAGUNA_SECA_WAYPOINTS[_j][0], _LAGUNA_SECA_WAYPOINTS[_j][1],
    )
    _CIRCUIT_SEG_DIST.append(_d)
    _CIRCUIT_CUM_DIST.append(_CIRCUIT_CUM_DIST[-1] + _d)
_CIRCUIT_TOTAL_M: float = _CIRCUIT_CUM_DIST[-1]


class MockCanGenerator(QObject):
    """Generates plausible telemetry when no CAN bus.

    Simulates spirited canyon driving with G5 Neo 4 telemetry:
    DCCD, context, wheel speeds, dynamics, Generic Dash engine data,
    SI Drive mode cycling, extended sensors, and keypad events.
    """

    def __init__(self, bridge: DiffStateBridge, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._bridge = bridge
        self._t = 0.0

        # Internal state for smooth random walk
        self._dccd_cmd = 40.0
        self._dccd_dial = 45.0
        self._throttle = 50.0
        self._speed = 80.0
        self._gear = 3
        self._slip = 0.0
        self._surface = SurfaceState.DRY
        self._steering = 0.0
        self._yaw = 0.0
        self._lat_g = 0.0
        self._brake_press = 0.0

        # G5 engine state
        self._rpm = 3500.0
        self._map_kpa = 100.0
        self._coolant_temp = 20.0  # starts cold for warm-up demo
        self._iat = 25.0
        self._lambda = 1.0
        self._oil_press_kpa = 350.0
        self._oil_temp = 20.0
        self._ethanol = 0.0
        self._fuel_press = 380.0
        self._battery_v = 14.2
        self._inj_duty = 30.0
        self._oil_psi = 55.0

        # GPS09 Pro — simulated Laguna Seca circuit (waypoint interpolation)
        self._gps_lat = _LAGUNA_SECA_WAYPOINTS[0][0]
        self._gps_lon = _LAGUNA_SECA_WAYPOINTS[0][1]
        self._gps_alt = 321.0       # meters
        self._gps_heading = 135.0   # SE
        self._gps_speed_mps = 0.0
        self._gps_progress = 0.0    # meters along circuit loop

        # IMU state
        self._imu_ax = 0.0
        self._imu_ay = 0.0
        self._imu_az = 1.0  # 1g at rest (gravity)
        self._imu_gx = 0.0
        self._imu_gy = 0.0
        self._imu_gz = 0.0
        self._prev_heading = 135.0

        # FLIR brake temp state (°C)
        self._flir_fl = 180.0
        self._flir_fr = 175.0
        self._flir_rl = 160.0
        self._flir_rr = 155.0

        # SI Drive state
        self._si_drive = 0  # Intelligent
        self._si_drive_timer = 0.0

        self._diff_timer = QTimer(self)
        self._diff_timer.setInterval(1000 // MOCK_DIFF_HZ)
        self._diff_timer.timeout.connect(self._diff_tick)

        self._ctx_timer = QTimer(self)
        self._ctx_timer.setInterval(1000 // MOCK_CONTEXT_HZ)
        self._ctx_timer.timeout.connect(self._ctx_tick)

        self._ws_timer = QTimer(self)
        self._ws_timer.setInterval(1000 // MOCK_WHEEL_HZ)
        self._ws_timer.timeout.connect(self._ws_tick)

        self._dyn_timer = QTimer(self)
        self._dyn_timer.setInterval(1000 // MOCK_DYNAMICS_HZ)
        self._dyn_timer.timeout.connect(self._dyn_tick)

        # G5 timers
        self._gd_timer = QTimer(self)
        self._gd_timer.setInterval(1000 // MOCK_GENERIC_DASH_HZ)
        self._gd_timer.timeout.connect(self._generic_dash_tick)

        self._si_timer = QTimer(self)
        self._si_timer.setInterval(1000 // MOCK_SI_DRIVE_HZ)
        self._si_timer.timeout.connect(self._si_drive_tick)

        self._sens_timer = QTimer(self)
        self._sens_timer.setInterval(1000 // MOCK_SENSOR_HZ)
        self._sens_timer.timeout.connect(self._sensor_tick)

        # GPS09 Pro timers
        self._gps_timer = QTimer(self)
        self._gps_timer.setInterval(1000 // MOCK_GPS_HZ)
        self._gps_timer.timeout.connect(self._gps_tick)

        self._imu_timer = QTimer(self)
        self._imu_timer.setInterval(1000 // MOCK_IMU_HZ)
        self._imu_timer.timeout.connect(self._imu_tick)

        self._flir_timer = QTimer(self)
        self._flir_timer.setInterval(1000 // MOCK_FLIR_HZ)
        self._flir_timer.timeout.connect(self._flir_tick)

    def start(self) -> None:
        self._diff_timer.start()
        self._ctx_timer.start()
        self._ws_timer.start()
        self._dyn_timer.start()
        if ACTIVE_ECU == "G5":
            self._gd_timer.start()
            self._si_timer.start()
            self._sens_timer.start()
            self._gps_timer.start()
            self._imu_timer.start()
        self._flir_timer.start()
        log.info("Mock CAN generator started (ECU: %s)", ACTIVE_ECU)

    def stop(self) -> None:
        self._diff_timer.stop()
        self._ctx_timer.stop()
        self._ws_timer.stop()
        self._dyn_timer.stop()
        self._gd_timer.stop()
        self._si_timer.stop()
        self._sens_timer.stop()
        self._gps_timer.stop()
        self._imu_timer.stop()
        self._flir_timer.stop()

    def _diff_tick(self) -> None:
        self._t += 0.02  # 50 Hz

        # DCCD command — sinusoidal base + noise (canyon switchbacks)
        self._dccd_cmd += random.uniform(-3.0, 3.0)
        self._dccd_cmd += 2.0 * math.sin(self._t * 0.5)
        self._dccd_cmd = max(0.0, min(100.0, self._dccd_cmd))

        # Dial tracks command loosely
        self._dccd_dial += (self._dccd_cmd - self._dccd_dial) * 0.1 + random.uniform(-1, 1)
        self._dccd_dial = max(0.0, min(100.0, self._dccd_dial))

        # Slip delta — normally small, occasional spikes during hard cornering
        self._slip += random.uniform(-0.5, 0.5)
        if random.random() < 0.02:
            self._slip += random.uniform(-5.0, 8.0)  # spike
        self._slip *= 0.95  # decay toward zero
        self._slip = max(-15.0, min(15.0, self._slip))

        # Flags — brake correlates with throttle drop
        braking = self._throttle < 15.0
        handbrake = False
        abs_active = braking and abs(self._slip) > 5.0
        vdc_tc = abs(self._slip) > 8.0

        # Surface change occasionally
        if random.random() < 0.001:
            self._surface = random.choice(list(SurfaceState))

        self._bridge.update_diff(
            dccd_command_pct=self._dccd_cmd,
            dccd_dial_pct=self._dccd_dial,
            surface_state=self._surface,
            brake=braking,
            handbrake=handbrake,
            abs_active=abs_active,
            vdc_tc=vdc_tc,
            slip_delta=self._slip,
        )

    def _ctx_tick(self) -> None:
        # Throttle — random walk with occasional lift-off
        self._throttle += random.uniform(-5.0, 5.0)
        if random.random() < 0.05:
            self._throttle = random.uniform(0.0, 20.0)  # lift
        elif random.random() < 0.05:
            self._throttle = random.uniform(70.0, 100.0)  # stomp
        self._throttle = max(0.0, min(100.0, self._throttle))

        # Speed — correlates loosely with throttle
        target_speed = 40.0 + self._throttle * 1.2
        self._speed += (target_speed - self._speed) * 0.05 + random.uniform(-2, 2)
        self._speed = max(0.0, min(220.0, self._speed))

        # Gear — simple mapping from speed
        if self._speed < 20:
            self._gear = 1
        elif self._speed < 45:
            self._gear = 2
        elif self._speed < 75:
            self._gear = 3
        elif self._speed < 110:
            self._gear = 4
        elif self._speed < 150:
            self._gear = 5
        else:
            self._gear = 6

        self._bridge.update_context(
            gear=self._gear,
            speed_kph=self._speed,
            throttle_pct=self._throttle,
        )

    def _ws_tick(self) -> None:
        """Mock individual wheel speeds with realistic L-R differential."""
        base_speed = self._speed
        # Front wheels: slight difference in turns (steering-based)
        steer_factor = self._steering / 540.0  # normalize to ±1
        fl = base_speed * (1.0 - steer_factor * 0.03) + random.uniform(-0.5, 0.5)
        fr = base_speed * (1.0 + steer_factor * 0.03) + random.uniform(-0.5, 0.5)

        # Rear wheels: LSD effect — when DCCD is locked, rears match more
        lock_frac = self._dccd_cmd / 100.0
        # Base rear diff: open = 3% L-R split in turns, locked = <0.5%
        rear_diff_max = 0.03 * (1.0 - lock_frac * 0.85)
        rl = base_speed * (1.0 - steer_factor * rear_diff_max) + random.uniform(-0.3, 0.3)
        rr = base_speed * (1.0 + steer_factor * rear_diff_max) + random.uniform(-0.3, 0.3)

        # Clamp
        fl = max(0.0, fl)
        fr = max(0.0, fr)
        rl = max(0.0, rl)
        rr = max(0.0, rr)

        self._bridge.update_wheel_speeds(fl=fl, fr=fr, rl=rl, rr=rr)

    def _dyn_tick(self) -> None:
        """Mock vehicle dynamics: steering, yaw, lateral G, brake pressure."""
        # Steering — sinusoidal canyon driving
        self._steering += random.uniform(-15.0, 15.0)
        self._steering += 30.0 * math.sin(self._t * 0.3)  # slow sweeps
        self._steering *= 0.95  # decay toward center
        self._steering = max(-540.0, min(540.0, self._steering))

        # Yaw rate — correlates with steering and speed
        target_yaw = self._steering * self._speed / 5000.0
        self._yaw += (target_yaw - self._yaw) * 0.3 + random.uniform(-1.0, 1.0)
        self._yaw = max(-60.0, min(60.0, self._yaw))

        # Lateral G — correlates with yaw rate
        target_lat = self._yaw * self._speed / 3000.0
        self._lat_g += (target_lat - self._lat_g) * 0.3 + random.uniform(-0.02, 0.02)
        self._lat_g = max(-1.5, min(1.5, self._lat_g))

        # Brake pressure — correlates with braking state
        if self._throttle < 15.0:
            target_brake = (15.0 - self._throttle) * 3.0  # up to ~45 bar
        else:
            target_brake = 0.0
        self._brake_press += (target_brake - self._brake_press) * 0.3
        self._brake_press = max(0.0, min(80.0, self._brake_press))

        self._bridge.update_dynamics(
            steering_angle=self._steering,
            yaw_rate=self._yaw,
            lateral_g=self._lat_g,
            brake_pressure=self._brake_press,
        )

    def _generic_dash_tick(self) -> None:
        """Mock Generic Dash engine telemetry (3 frames)."""
        # RPM correlates with speed and gear
        gear_ratio = [0, 3.636, 2.235, 1.521, 1.137, 0.971, 0.756]
        if self._gear > 0:
            self._rpm = self._speed * gear_ratio[self._gear] * 45.0 + random.uniform(-50, 50)
        else:
            self._rpm = 800.0 + random.uniform(-20, 20)
        self._rpm = max(700.0, min(8500.0, self._rpm))

        # MAP — correlates with throttle + boost
        target_map = 30.0 + self._throttle * 2.7  # 30 kPa idle → 300 kPa WOT
        self._map_kpa += (target_map - self._map_kpa) * 0.15 + random.uniform(-2, 2)
        self._map_kpa = max(20.0, min(350.0, self._map_kpa))

        # Coolant temp — slowly warms up from cold
        if self._coolant_temp < 85.0:
            self._coolant_temp += 0.02  # ~7 min warm-up at 50Hz
        self._coolant_temp += random.uniform(-0.05, 0.05)
        self._coolant_temp = max(0.0, min(120.0, self._coolant_temp))

        self._bridge.update_generic_dash_1(
            rpm=self._rpm,
            map_kpa=self._map_kpa,
            tps=self._throttle,
            coolant_temp=self._coolant_temp,
        )

        # IAT — ambient + heat soak
        self._iat += random.uniform(-0.1, 0.1)
        self._iat = max(-10.0, min(60.0, self._iat))

        # Lambda — rich under boost, stoich otherwise
        if self._map_kpa > 100.0:
            target_lambda = 0.78 + random.uniform(-0.02, 0.02)
        else:
            target_lambda = 1.0 + random.uniform(-0.02, 0.02)
        self._lambda += (target_lambda - self._lambda) * 0.2
        self._lambda = max(0.6, min(1.2, self._lambda))

        # Oil pressure — correlates with RPM
        target_oil = 200.0 + self._rpm * 0.05
        self._oil_press_kpa += (target_oil - self._oil_press_kpa) * 0.1 + random.uniform(-5, 5)
        self._oil_press_kpa = max(50.0, min(700.0, self._oil_press_kpa))

        # Oil temp — slowly warms
        if self._oil_temp < 95.0:
            self._oil_temp += 0.015
        self._oil_temp += random.uniform(-0.05, 0.05)
        self._oil_temp = max(0.0, min(140.0, self._oil_temp))

        self._bridge.update_generic_dash_2(
            iat_c=self._iat,
            lambda_1=self._lambda,
            oil_pressure_kpa=self._oil_press_kpa,
            oil_temp_c=self._oil_temp,
        )

        # Ethanol content
        self._ethanol += random.uniform(-0.1, 0.1)
        self._ethanol = max(0.0, min(100.0, self._ethanol))

        # Fuel pressure
        self._fuel_press += random.uniform(-2, 2)
        self._fuel_press = max(300.0, min(500.0, self._fuel_press))

        # Battery
        self._battery_v += random.uniform(-0.05, 0.05)
        self._battery_v = max(12.0, min(15.0, self._battery_v))

        # Injector duty — correlates with throttle/boost
        target_inj = self._throttle * 0.7 + (self._map_kpa - 100) * 0.1
        self._inj_duty += (target_inj - self._inj_duty) * 0.15 + random.uniform(-1, 1)
        self._inj_duty = max(0.0, min(100.0, self._inj_duty))

        self._bridge.update_generic_dash_3(
            ethanol_pct=self._ethanol,
            fuel_pressure_kpa=self._fuel_press,
            battery_v=self._battery_v,
            injector_duty=self._inj_duty,
        )

    def _si_drive_tick(self) -> None:
        """Mock SI Drive mode — cycles every 30 seconds for demo."""
        self._si_drive_timer += 1.0 / MOCK_SI_DRIVE_HZ
        if self._si_drive_timer > 30.0:
            self._si_drive_timer = 0.0
            self._si_drive = (self._si_drive + 1) % 3
        self._bridge.update_si_drive(mode=self._si_drive)

    def _sensor_tick(self) -> None:
        """Mock extended sensor data."""
        # 4-bar MAP — similar to GD1 MAP but from dedicated sensor
        map_4bar = self._map_kpa + random.uniform(-1, 1)

        # External IAT
        iat_ext = self._iat + random.uniform(-0.5, 0.5)

        # Flex Fuel ethanol
        ethanol_ext = self._ethanol + random.uniform(-0.2, 0.2)

        # Oil PSI — convert from kPa mock + some variation
        self._oil_psi += random.uniform(-0.5, 0.5)
        target_psi = self._oil_press_kpa * 0.145038  # kPa to PSI
        self._oil_psi += (target_psi - self._oil_psi) * 0.2
        self._oil_psi = max(0.0, min(150.0, self._oil_psi))

        self._bridge.update_sensors(
            map_4bar_kpa=max(0.0, map_4bar),
            iat_ext_c=iat_ext,
            ethanol_ext_pct=max(0.0, ethanol_ext),
            oil_psi=self._oil_psi,
        )

    def _gps_tick(self) -> None:
        """Mock GPS — simulate laps around Laguna Seca waypoint circuit.

        Advances along :data:`_LAGUNA_SECA_WAYPOINTS` by vehicle speed,
        crossing the seed start/finish line and all 3 sector lines each lap.
        """
        dt = 1.0 / MOCK_GPS_HZ

        # Speed follows vehicle speed (convert km/h to m/s)
        self._gps_speed_mps = self._speed / 3.6

        # Advance distance along circuit loop
        if self._gps_speed_mps > 0.1:
            self._gps_progress += self._gps_speed_mps * dt
            if self._gps_progress >= _CIRCUIT_TOTAL_M:
                self._gps_progress -= _CIRCUIT_TOTAL_M

        # Interpolate position along waypoint chain
        n = len(_LAGUNA_SECA_WAYPOINTS)
        for seg_idx in range(n):
            if self._gps_progress < _CIRCUIT_CUM_DIST[seg_idx + 1]:
                seg_len = _CIRCUIT_SEG_DIST[seg_idx]
                frac = (
                    (self._gps_progress - _CIRCUIT_CUM_DIST[seg_idx]) / seg_len
                    if seg_len > 0 else 0.0
                )
                j = (seg_idx + 1) % n
                lat1, lon1 = _LAGUNA_SECA_WAYPOINTS[seg_idx]
                lat2, lon2 = _LAGUNA_SECA_WAYPOINTS[j]
                self._gps_lat = lat1 + frac * (lat2 - lat1)
                self._gps_lon = lon1 + frac * (lon2 - lon1)

                # Heading from segment direction (true north bearing)
                dlat = lat2 - lat1
                dlon = (lon2 - lon1) * math.cos(math.radians(lat1))
                self._prev_heading = self._gps_heading
                self._gps_heading = math.degrees(math.atan2(dlon, dlat)) % 360.0
                break

        # Altitude varies with position (Laguna Seca has ~30m elevation change)
        progress_frac = self._gps_progress / _CIRCUIT_TOTAL_M
        self._gps_alt = 321.0 + 30.0 * math.sin(progress_frac * 2 * math.pi)

        self._bridge.update_gps(
            latitude=self._gps_lat,
            longitude=self._gps_lon,
        )
        self._bridge.update_gps_ext(
            altitude_m=self._gps_alt,
            speed_mps=self._gps_speed_mps,
            heading=self._gps_heading,
            satellites=12,
            fix_quality=2,  # 3D fix
        )

    def _imu_tick(self) -> None:
        """Mock IMU — derive from vehicle dynamics."""
        dt = 1.0 / MOCK_IMU_HZ

        # Longitudinal acceleration from speed change (approximate)
        speed_mps = self._speed / 3.6
        accel_from_throttle = (self._throttle - 50.0) / 50.0 * 0.5  # ~0.5g full throttle
        brake_decel = self._brake_press / 80.0 * 1.2  # ~1.2g max braking at 80 bar
        self._imu_ax = accel_from_throttle - brake_decel + random.uniform(-0.02, 0.02)

        # Lateral acceleration from cornering (use existing dynamics lateral_g)
        self._imu_ay = self._lat_g + random.uniform(-0.02, 0.02)

        # Vertical — 1g + bumps
        self._imu_az = 1.0 + random.uniform(-0.05, 0.05)

        # Gyro — yaw rate from heading change, roll/pitch from dynamics
        heading_delta = self._gps_heading - self._prev_heading
        if heading_delta > 180:
            heading_delta -= 360
        elif heading_delta < -180:
            heading_delta += 360
        self._imu_gz = heading_delta / dt if dt > 0 else 0.0  # deg/s

        # Roll rate approximated from lateral g change
        self._imu_gx = self._lat_g * 5.0 + random.uniform(-0.5, 0.5)
        # Pitch rate approximated from longitudinal g change
        self._imu_gy = self._imu_ax * 3.0 + random.uniform(-0.5, 0.5)

        self._bridge.update_imu(
            accel_x=self._imu_ax,
            accel_y=self._imu_ay,
            accel_z=self._imu_az,
        )
        self._bridge.update_imu_gyro(
            gyro_x=self._imu_gx,
            gyro_y=self._imu_gy,
            gyro_z=self._imu_gz,
        )

    def _flir_tick(self) -> None:
        """Mock FLIR Lepton — brake disc temps correlated with braking."""
        # Braking heats up front more than rear (60/40 bias)
        heat_rate = self._brake_press / 80.0 * 8.0  # max ~8°C/tick at 80 bar
        cool_rate = 0.3  # radiative cooling per tick

        self._flir_fl += heat_rate * 0.35 - cool_rate + random.uniform(-1.0, 1.0)
        self._flir_fr += heat_rate * 0.35 - cool_rate + random.uniform(-1.0, 1.0)
        self._flir_rl += heat_rate * 0.15 - cool_rate + random.uniform(-0.8, 0.8)
        self._flir_rr += heat_rate * 0.15 - cool_rate + random.uniform(-0.8, 0.8)

        # Clamp to plausible brake disc range (50–650°C)
        self._flir_fl = max(50.0, min(650.0, self._flir_fl))
        self._flir_fr = max(50.0, min(650.0, self._flir_fr))
        self._flir_rl = max(50.0, min(650.0, self._flir_rl))
        self._flir_rr = max(50.0, min(650.0, self._flir_rr))

        self._bridge.update_flir(
            fl=self._flir_fl,
            fr=self._flir_fr,
            rl=self._flir_rl,
            rr=self._flir_rr,
        )


# ---------------------------------------------------------------------------
# Factory: create the right listener based on environment
# ---------------------------------------------------------------------------

def create_can_source(
    bridge: DiffStateBridge,
    parent: Optional[QObject] = None,
) -> tuple[Optional[CanListenerThread], Optional[MockCanGenerator]]:
    """Try to open real CAN; fall back to mock if unavailable.

    Returns (listener_thread, mock_generator).  Exactly one will be non-None.
    The caller is responsible for starting/stopping the returned object.
    """
    if not MOCK_ENABLED:
        # Attempt real CAN only
        listener = CanListenerThread(bridge)
        return listener, None

    # Try real CAN first, fall back to mock
    try:
        import can as python_can  # type: ignore[import-untyped]
        # Quick probe: try to create bus, then close immediately
        bus = python_can.Bus(
            interface=CAN_BUSTYPE,
            channel=CAN_INTERFACE,
            receive_own_messages=False,
        )
        bus.shutdown()
        log.info("CAN bus available — using real CAN listener")
        listener = CanListenerThread(bridge)
        return listener, None
    except Exception:
        log.info("CAN bus unavailable — using mock generator")
        mock = MockCanGenerator(bridge, parent)
        return None, mock
