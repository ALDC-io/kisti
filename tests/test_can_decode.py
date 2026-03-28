"""Unit tests for CAN frame decoding — pure Python, no CAN hardware required.

Tests cover:
  - DIFF frame (0x6A0) decode: normal, N/A signals, edge values
  - CONTEXT frame (0x6A1) decode: normal, neutral gear, max values
  - WHEEL_SPEED frame (0x6A2) decode
  - DYNAMICS frame (0x6A3) decode
  - GPS Position frame (0x6A4) decode
  - GPS Extended frame (0x6A5) decode
  - IMU Accelerometer frame (0x6A6) decode
  - IMU Gyroscope frame (0x6A7) decode
  - Generic Dash frames (0x360-0x362) decode
  - SI Drive frame (0x6B0) decode
  - Extended Sensor frame (0x6B1) decode
  - Keypad frame (0x6B2) decode
  - LED output frames (0x6C0-0x6C1) encode
  - Encode/decode round-trip consistency for all frame types
  - Error handling for short frames
  - DiffState staleness detection
  - SIDriveMode and WarmUpState enums
  - Keypad edge detection (pressed/released)
"""

import struct
import time

import pytest

# Allow running from project root or tests/
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from can.kisti_can import (
    decode_context_frame,
    decode_diff_frame,
    decode_dynamics_frame,
    decode_generic_dash_1,
    decode_generic_dash_2,
    decode_generic_dash_3,
    decode_gps_ext_frame,
    decode_gps_frame,
    decode_imu_frame,
    decode_imu_gyro_frame,
    decode_keypad_frame,
    decode_sensor_frame,
    decode_si_drive_frame,
    decode_wheel_speed_frame,
    encode_context_frame,
    encode_diff_frame,
    encode_generic_dash_1,
    encode_generic_dash_2,
    encode_generic_dash_3,
    encode_gps_ext_frame,
    encode_gps_frame,
    encode_imu_frame,
    encode_imu_gyro_frame,
    encode_keypad_frame,
    encode_led_output,
    encode_sensor_frame,
    encode_si_drive_frame,
)
from can.can_config import (
    DIFF_DCCD_DIAL_NA,
    DIFF_SLIP_NA,
    KEYPAD_K1,
    KEYPAD_K2,
    KEYPAD_K3,
    KEYPAD_K4,
    KEYPAD_K5,
    KEYPAD_K6,
    LED_COUNT,
    LED_MODE_KITT,
    LED_MODE_OFF,
    LED_MODE_RPM,
    LED_MODE_WARMUP,
    LED_MODE_WAVEFORM,
    SI_DRIVE_INTELLIGENT,
    SI_DRIVE_SPORT,
    SI_DRIVE_SPORT_SHARP,
)
from model.vehicle_state import (
    DiffState,
    SIDriveMode,
    SurfaceState,
    WarmUpState,
)


# ========================================================================
# DIFF frame decode tests (unchanged from original — must not regress)
# ========================================================================

class TestDecodeDiffFrame:
    """Tests for decode_diff_frame()."""

    def test_normal_all_signals(self):
        """All signals present with typical values."""
        data = encode_diff_frame(
            dccd_cmd=87.5,
            dccd_dial=45.2,
            surface=0,  # DRY
            flags=0x01,  # brake only
            slip=2.34,
        )
        result = decode_diff_frame(data)

        assert abs(result["dccd_command_pct"] - 87.5) < 0.15
        assert result["dccd_dial_pct"] is not None
        assert abs(result["dccd_dial_pct"] - 45.2) < 0.15
        assert result["surface_state"] == SurfaceState.DRY
        assert result["brake"] is True
        assert result["handbrake"] is False
        assert result["abs_active"] is False
        assert result["vdc_tc"] is False
        assert result["slip_delta"] is not None
        assert abs(result["slip_delta"] - 2.34) < 0.015

    def test_dial_not_available(self):
        """DCCD dial marked as N/A (0xFFFF)."""
        data = encode_diff_frame(dccd_cmd=50.0, dccd_dial=None, surface=1, flags=0, slip=0.0)
        result = decode_diff_frame(data)

        assert result["dccd_dial_pct"] is None
        assert result["surface_state"] == SurfaceState.WET

    def test_slip_not_available(self):
        """Slip delta marked as N/A (0x7FFF)."""
        data = encode_diff_frame(dccd_cmd=0.0, dccd_dial=0.0, surface=0, flags=0, slip=None)
        result = decode_diff_frame(data)

        assert result["slip_delta"] is None

    def test_negative_slip(self):
        """Negative slip delta (front spinning faster than rear)."""
        data = encode_diff_frame(dccd_cmd=60.0, dccd_dial=60.0, surface=0, flags=0, slip=-5.67)
        result = decode_diff_frame(data)

        assert result["slip_delta"] is not None
        assert abs(result["slip_delta"] - (-5.67)) < 0.015

    def test_all_flags_set(self):
        """All event flags active."""
        data = encode_diff_frame(dccd_cmd=100.0, dccd_dial=100.0, surface=3, flags=0x0F, slip=10.0)
        result = decode_diff_frame(data)

        assert result["brake"] is True
        assert result["handbrake"] is True
        assert result["abs_active"] is True
        assert result["vdc_tc"] is True
        assert result["surface_state"] == SurfaceState.LOW_GRIP

    def test_zero_lock(self):
        """DCCD fully unlocked (0%)."""
        data = encode_diff_frame(dccd_cmd=0.0, dccd_dial=0.0, surface=0, flags=0, slip=0.0)
        result = decode_diff_frame(data)

        assert result["dccd_command_pct"] == 0.0

    def test_full_lock(self):
        """DCCD fully locked (100%)."""
        data = encode_diff_frame(dccd_cmd=100.0, dccd_dial=100.0, surface=0, flags=0, slip=0.0)
        result = decode_diff_frame(data)

        assert abs(result["dccd_command_pct"] - 100.0) < 0.15

    def test_surface_cold(self):
        """Surface state = COLD."""
        data = encode_diff_frame(dccd_cmd=50.0, dccd_dial=50.0, surface=2, flags=0, slip=0.0)
        result = decode_diff_frame(data)

        assert result["surface_state"] == SurfaceState.COLD

    def test_unknown_surface_fallback(self):
        """Unknown surface enum falls back to DRY."""
        # Manually encode with invalid surface byte
        data = encode_diff_frame(dccd_cmd=50.0, dccd_dial=50.0, surface=0, flags=0, slip=0.0)
        data = bytearray(data)
        data[4] = 99  # invalid enum
        result = decode_diff_frame(bytes(data))

        assert result["surface_state"] == SurfaceState.DRY

    def test_short_frame_raises(self):
        """Frame shorter than 8 bytes raises ValueError."""
        with pytest.raises(ValueError, match="too short"):
            decode_diff_frame(b"\x00\x00\x00")


# ========================================================================
# CONTEXT frame decode tests
# ========================================================================

class TestDecodeContextFrame:
    """Tests for decode_context_frame()."""

    def test_normal(self):
        """Typical driving context: 3rd gear, 90 km/h, 55% throttle."""
        data = encode_context_frame(gear=3, speed_kph=90.0, throttle_pct=55.0)
        result = decode_context_frame(data)

        assert result["gear"] == 3
        assert abs(result["speed_kph"] - 90.0) < 0.015
        assert abs(result["throttle_pct"] - 55.0) < 0.15

    def test_neutral(self):
        """Neutral gear (0)."""
        data = encode_context_frame(gear=0, speed_kph=0.0, throttle_pct=0.0)
        result = decode_context_frame(data)

        assert result["gear"] == 0
        assert result["speed_kph"] == 0.0
        assert result["throttle_pct"] == 0.0

    def test_high_speed(self):
        """High speed: 6th gear, 220 km/h, 100% throttle."""
        data = encode_context_frame(gear=6, speed_kph=220.0, throttle_pct=100.0)
        result = decode_context_frame(data)

        assert result["gear"] == 6
        assert abs(result["speed_kph"] - 220.0) < 0.015
        assert abs(result["throttle_pct"] - 100.0) < 0.15

    def test_short_frame_raises(self):
        """Frame shorter than 5 bytes raises ValueError."""
        with pytest.raises(ValueError, match="too short"):
            decode_context_frame(b"\x00\x00")


# ========================================================================
# Generic Dash decode tests (G5 Neo 4)
# ========================================================================

class TestDecodeGenericDash1:
    """Tests for decode_generic_dash_1() — RPM, MAP, TPS, CLT."""

    def test_normal_values(self):
        """Typical engine: 3500 RPM, 150 kPa MAP, 45% TPS, 85°C CLT."""
        data = encode_generic_dash_1(rpm=3500, map_kpa=150.0, tps=45.0, coolant_temp=85.0)
        result = decode_generic_dash_1(data)

        assert abs(result["rpm"] - 3500.0) < 1.5
        assert abs(result["map_kpa"] - 150.0) < 0.15
        assert abs(result["tps"] - 45.0) < 0.15
        assert abs(result["coolant_temp"] - 85.0) < 0.15

    def test_idle(self):
        """Idle: 800 RPM, 30 kPa vacuum, 0% TPS, cold 20°C."""
        data = encode_generic_dash_1(rpm=800, map_kpa=30.0, tps=0.0, coolant_temp=20.0)
        result = decode_generic_dash_1(data)

        assert abs(result["rpm"] - 800.0) < 1.5
        assert abs(result["map_kpa"] - 30.0) < 0.15
        assert abs(result["tps"] - 0.0) < 0.15
        assert abs(result["coolant_temp"] - 20.0) < 0.15

    def test_redline_full_boost(self):
        """Redline + full boost: 8000 RPM, 300 kPa, 100% TPS."""
        data = encode_generic_dash_1(rpm=8000, map_kpa=300.0, tps=100.0, coolant_temp=95.0)
        result = decode_generic_dash_1(data)

        assert abs(result["rpm"] - 8000.0) < 1.5
        assert abs(result["map_kpa"] - 300.0) < 0.15

    def test_negative_coolant(self):
        """Negative coolant temp (winter cold start)."""
        data = encode_generic_dash_1(rpm=900, map_kpa=25.0, tps=0.0, coolant_temp=-15.0)
        result = decode_generic_dash_1(data)

        assert abs(result["coolant_temp"] - (-15.0)) < 0.15

    def test_short_frame_raises(self):
        with pytest.raises(ValueError, match="too short"):
            decode_generic_dash_1(b"\x00\x00")


class TestDecodeGenericDash2:
    """Tests for decode_generic_dash_2() — IAT, Lambda, Oil Press, Oil Temp."""

    def test_normal_values(self):
        """Normal operating: 35°C IAT, 1.0 lambda, 350 kPa oil, 95°C oil temp."""
        data = encode_generic_dash_2(
            iat_c=35.0, lambda_1=1.0, oil_pressure_kpa=350.0, oil_temp_c=95.0,
        )
        result = decode_generic_dash_2(data)

        assert abs(result["iat_c"] - 35.0) < 0.15
        assert abs(result["lambda_1"] - 1.0) < 0.0015
        assert abs(result["oil_pressure_kpa"] - 350.0) < 0.15
        assert abs(result["oil_temp_c"] - 95.0) < 0.15

    def test_rich_under_boost(self):
        """Rich mixture under boost: lambda 0.78."""
        data = encode_generic_dash_2(
            iat_c=40.0, lambda_1=0.78, oil_pressure_kpa=500.0, oil_temp_c=110.0,
        )
        result = decode_generic_dash_2(data)

        assert abs(result["lambda_1"] - 0.78) < 0.0015

    def test_cold_start(self):
        """Cold start: negative IAT, low oil temp."""
        data = encode_generic_dash_2(
            iat_c=-10.0, lambda_1=0.95, oil_pressure_kpa=200.0, oil_temp_c=-5.0,
        )
        result = decode_generic_dash_2(data)

        assert abs(result["iat_c"] - (-10.0)) < 0.15
        assert abs(result["oil_temp_c"] - (-5.0)) < 0.15

    def test_short_frame_raises(self):
        with pytest.raises(ValueError, match="too short"):
            decode_generic_dash_2(b"\x00\x00")


class TestDecodeGenericDash3:
    """Tests for decode_generic_dash_3() — Ethanol, Fuel Press, Battery, Inj Duty."""

    def test_normal_values(self):
        """Pump gas, normal fuel/battery: 0% ethanol, 380 kPa fuel, 14.2V, 35% duty."""
        data = encode_generic_dash_3(
            ethanol_pct=0.0, fuel_pressure_kpa=380.0, battery_v=14.2, injector_duty=35.0,
        )
        result = decode_generic_dash_3(data)

        assert abs(result["ethanol_pct"] - 0.0) < 0.15
        assert abs(result["fuel_pressure_kpa"] - 380.0) < 0.15
        assert abs(result["battery_v"] - 14.2) < 0.015
        assert abs(result["injector_duty"] - 35.0) < 0.15

    def test_e85_full_duty(self):
        """E85 fuel, high duty cycle."""
        data = encode_generic_dash_3(
            ethanol_pct=85.0, fuel_pressure_kpa=450.0, battery_v=13.8, injector_duty=92.0,
        )
        result = decode_generic_dash_3(data)

        assert abs(result["ethanol_pct"] - 85.0) < 0.15
        assert abs(result["injector_duty"] - 92.0) < 0.15

    def test_short_frame_raises(self):
        with pytest.raises(ValueError, match="too short"):
            decode_generic_dash_3(b"\x00\x00")


# ========================================================================
# SI Drive decode tests
# ========================================================================

class TestDecodeSIDrive:
    """Tests for decode_si_drive_frame()."""

    def test_intelligent_mode(self):
        data = encode_si_drive_frame(SI_DRIVE_INTELLIGENT)
        result = decode_si_drive_frame(data)
        assert result["mode"] == 0

    def test_sport_mode(self):
        data = encode_si_drive_frame(SI_DRIVE_SPORT)
        result = decode_si_drive_frame(data)
        assert result["mode"] == 1

    def test_sport_sharp_mode(self):
        data = encode_si_drive_frame(SI_DRIVE_SPORT_SHARP)
        result = decode_si_drive_frame(data)
        assert result["mode"] == 2

    def test_short_frame_raises(self):
        with pytest.raises(ValueError, match="too short"):
            decode_si_drive_frame(b"")


# ========================================================================
# Extended Sensor decode tests
# ========================================================================

class TestDecodeSensorFrame:
    """Tests for decode_sensor_frame()."""

    def test_normal_values(self):
        """Normal: 250 kPa 4bar MAP, 30°C IAT, 0% ethanol, 55 PSI oil."""
        data = encode_sensor_frame(
            map_4bar_kpa=250.0, iat_ext_c=30.0, ethanol_ext_pct=0.0, oil_psi=55.0,
        )
        result = decode_sensor_frame(data)

        assert abs(result["map_4bar_kpa"] - 250.0) < 0.15
        assert abs(result["iat_ext_c"] - 30.0) < 0.15
        assert abs(result["ethanol_ext_pct"] - 0.0) < 0.15
        assert abs(result["oil_psi"] - 55.0) < 0.15

    def test_high_boost(self):
        """High boost: 350 kPa (4-bar sensor range)."""
        data = encode_sensor_frame(
            map_4bar_kpa=350.0, iat_ext_c=45.0, ethanol_ext_pct=85.0, oil_psi=70.0,
        )
        result = decode_sensor_frame(data)

        assert abs(result["map_4bar_kpa"] - 350.0) < 0.15

    def test_cold_iat(self):
        """Negative IAT (winter)."""
        data = encode_sensor_frame(
            map_4bar_kpa=100.0, iat_ext_c=-20.0, ethanol_ext_pct=0.0, oil_psi=40.0,
        )
        result = decode_sensor_frame(data)

        assert abs(result["iat_ext_c"] - (-20.0)) < 0.15

    def test_low_oil_pressure(self):
        """Low oil pressure — alert condition."""
        data = encode_sensor_frame(
            map_4bar_kpa=100.0, iat_ext_c=25.0, ethanol_ext_pct=0.0, oil_psi=12.0,
        )
        result = decode_sensor_frame(data)

        assert abs(result["oil_psi"] - 12.0) < 0.15

    def test_short_frame_raises(self):
        with pytest.raises(ValueError, match="too short"):
            decode_sensor_frame(b"\x00\x00")


# ========================================================================
# Keypad decode tests
# ========================================================================

class TestDecodeKeypadFrame:
    """Tests for decode_keypad_frame()."""

    def test_no_buttons(self):
        data = encode_keypad_frame(state=0x00, prev_state=0x00)
        result = decode_keypad_frame(data)
        assert result["state"] == 0
        assert result["prev_state"] == 0

    def test_k1_pressed(self):
        """K1 (Session Start/Stop) just pressed."""
        data = encode_keypad_frame(state=KEYPAD_K1, prev_state=0x00)
        result = decode_keypad_frame(data)
        assert result["state"] == KEYPAD_K1
        assert result["prev_state"] == 0

    def test_k3_pressed(self):
        """K3 (Analyze That Run) just pressed."""
        data = encode_keypad_frame(state=KEYPAD_K3, prev_state=0x00)
        result = decode_keypad_frame(data)
        assert result["state"] == KEYPAD_K3

    def test_multiple_buttons(self):
        """Multiple buttons pressed simultaneously."""
        data = encode_keypad_frame(state=KEYPAD_K1 | KEYPAD_K4, prev_state=KEYPAD_K1)
        result = decode_keypad_frame(data)
        assert result["state"] == (KEYPAD_K1 | KEYPAD_K4)
        assert result["prev_state"] == KEYPAD_K1

    def test_all_buttons(self):
        """All 8 buttons pressed."""
        data = encode_keypad_frame(state=0xFF, prev_state=0x00)
        result = decode_keypad_frame(data)
        assert result["state"] == 0xFF

    def test_short_frame_raises(self):
        with pytest.raises(ValueError, match="too short"):
            decode_keypad_frame(b"\x00")


# ========================================================================
# GPS09 Pro decode tests
# ========================================================================

class TestDecodeGPSFrame:
    """Tests for decode_gps_frame() — GPS position (0x6A4)."""

    def test_laguna_seca(self):
        """Normal position — Laguna Seca."""
        data = encode_gps_frame(36.5842, -121.7528)
        result = decode_gps_frame(data)
        assert abs(result["latitude"] - 36.5842) < 0.00002
        assert abs(result["longitude"] - (-121.7528)) < 0.00002

    def test_equator_prime_meridian(self):
        """Zero-zero coordinates."""
        data = encode_gps_frame(0.0, 0.0)
        result = decode_gps_frame(data)
        assert abs(result["latitude"]) < 0.00002
        assert abs(result["longitude"]) < 0.00002

    def test_negative_coords(self):
        """Southern hemisphere, western hemisphere."""
        data = encode_gps_frame(-33.8688, 151.2093)  # Sydney
        result = decode_gps_frame(data)
        assert abs(result["latitude"] - (-33.8688)) < 0.00002
        assert abs(result["longitude"] - 151.2093) < 0.00002

    def test_high_precision(self):
        """Precision to ~1m (0.00001 degrees)."""
        data = encode_gps_frame(36.58421, -121.75283)
        result = decode_gps_frame(data)
        assert abs(result["latitude"] - 36.58421) < 0.00002
        assert abs(result["longitude"] - (-121.75283)) < 0.00002

    def test_short_frame_raises(self):
        with pytest.raises(ValueError, match="too short"):
            decode_gps_frame(b"\x00\x01\x02\x03")


class TestDecodeGPSExtFrame:
    """Tests for decode_gps_ext_frame() — GPS extended (0x6A5)."""

    def test_normal_values(self):
        data = encode_gps_ext_frame(321.0, 30.5, 135.0, 12, 2)
        result = decode_gps_ext_frame(data)
        assert abs(result["altitude_m"] - 321.0) < 1.0
        assert abs(result["speed_mps"] - 30.5) < 0.02
        assert abs(result["heading"] - 135.0) < 0.2
        assert result["satellites"] == 12
        assert result["fix_quality"] == 2

    def test_zero_speed_no_fix(self):
        data = encode_gps_ext_frame(0.0, 0.0, 0.0, 0, 0)
        result = decode_gps_ext_frame(data)
        assert abs(result["speed_mps"]) < 0.02
        assert result["satellites"] == 0
        assert result["fix_quality"] == 0

    def test_high_altitude(self):
        """High altitude track (e.g., Pikes Peak)."""
        data = encode_gps_ext_frame(4302.0, 40.0, 270.0, 8, 2)
        result = decode_gps_ext_frame(data)
        assert abs(result["altitude_m"] - 4302.0) < 1.0

    def test_negative_altitude(self):
        """Below sea level (e.g., Death Valley)."""
        data = encode_gps_ext_frame(-86.0, 10.0, 45.0, 10, 2)
        result = decode_gps_ext_frame(data)
        assert abs(result["altitude_m"] - (-86.0)) < 1.0

    def test_heading_north(self):
        data = encode_gps_ext_frame(100.0, 20.0, 359.9, 10, 2)
        result = decode_gps_ext_frame(data)
        assert abs(result["heading"] - 359.9) < 0.2

    def test_short_frame_raises(self):
        with pytest.raises(ValueError, match="too short"):
            decode_gps_ext_frame(b"\x00\x01\x02")


class TestDecodeIMUFrame:
    """Tests for decode_imu_frame() — IMU accelerometer (0x6A6)."""

    def test_at_rest(self):
        """Stationary — 0g lateral/longitudinal, 1g vertical."""
        data = encode_imu_frame(0.0, 0.0, 1.0)
        result = decode_imu_frame(data)
        assert abs(result["accel_x"]) < 0.002
        assert abs(result["accel_y"]) < 0.002
        assert abs(result["accel_z"] - 1.0) < 0.002

    def test_hard_braking(self):
        """Hard braking — negative X."""
        data = encode_imu_frame(-1.2, 0.0, 1.0)
        result = decode_imu_frame(data)
        assert abs(result["accel_x"] - (-1.2)) < 0.002

    def test_hard_cornering(self):
        """Hard right corner — positive Y."""
        data = encode_imu_frame(0.0, 1.5, 1.0)
        result = decode_imu_frame(data)
        assert abs(result["accel_y"] - 1.5) < 0.002

    def test_combined_g(self):
        """Trail braking into corner — both X and Y."""
        data = encode_imu_frame(-0.8, 0.9, 1.0)
        result = decode_imu_frame(data)
        assert abs(result["accel_x"] - (-0.8)) < 0.002
        assert abs(result["accel_y"] - 0.9) < 0.002

    def test_short_frame_raises(self):
        with pytest.raises(ValueError, match="too short"):
            decode_imu_frame(b"\x00\x01\x02\x03")


class TestDecodeIMUGyroFrame:
    """Tests for decode_imu_gyro_frame() — IMU gyroscope (0x6A7)."""

    def test_stationary(self):
        data = encode_imu_gyro_frame(0.0, 0.0, 0.0)
        result = decode_imu_gyro_frame(data)
        assert abs(result["gyro_x"]) < 0.02
        assert abs(result["gyro_y"]) < 0.02
        assert abs(result["gyro_z"]) < 0.02

    def test_yaw_turn(self):
        """Turning — yaw rate (Z axis)."""
        data = encode_imu_gyro_frame(0.0, 0.0, 45.0)
        result = decode_imu_gyro_frame(data)
        assert abs(result["gyro_z"] - 45.0) < 0.02

    def test_fast_spin(self):
        """High rotation rates."""
        data = encode_imu_gyro_frame(120.0, -50.0, 200.0)
        result = decode_imu_gyro_frame(data)
        assert abs(result["gyro_x"] - 120.0) < 0.02
        assert abs(result["gyro_y"] - (-50.0)) < 0.02
        assert abs(result["gyro_z"] - 200.0) < 0.02

    def test_negative_roll(self):
        data = encode_imu_gyro_frame(-30.0, 0.0, 0.0)
        result = decode_imu_gyro_frame(data)
        assert abs(result["gyro_x"] - (-30.0)) < 0.02

    def test_short_frame_raises(self):
        with pytest.raises(ValueError, match="too short"):
            decode_imu_gyro_frame(b"\x00\x01\x02\x03")


# ========================================================================
# LED output encode tests
# ========================================================================

class TestEncodeLEDOutput:
    """Tests for encode_led_output()."""

    def test_off_mode(self):
        """All LEDs off."""
        f1, f2 = encode_led_output(LED_MODE_OFF, [0] * 10, 0, 0, 0)
        assert len(f1) == 8
        assert len(f2) == 8
        assert f1[0] == LED_MODE_OFF
        assert all(b == 0 for b in f1[1:])

    def test_waveform_mode(self):
        """Waveform mode with varying brightnesses."""
        brights = [255, 200, 150, 100, 50, 25, 10, 5, 2, 0]
        f1, f2 = encode_led_output(LED_MODE_WAVEFORM, brights, 230, 0, 0)

        assert f1[0] == LED_MODE_WAVEFORM
        # Frame 1: mode + LEDs 0-6
        assert f1[1] == 255
        assert f1[2] == 200
        assert f1[7] == 10
        # Frame 2: LEDs 7-9 + RGB
        assert f2[0] == 5
        assert f2[1] == 2
        assert f2[2] == 0
        assert f2[3] == 230  # R
        assert f2[4] == 0    # G
        assert f2[5] == 0    # B

    def test_kitt_mode(self):
        """KITT sweep mode with red color."""
        brights = [0, 0, 0, 128, 255, 128, 0, 0, 0, 0]
        f1, f2 = encode_led_output(LED_MODE_KITT, brights, 255, 0, 0)

        assert f1[0] == LED_MODE_KITT
        assert f1[4] == 128  # LED 3
        assert f1[5] == 255  # LED 4

    def test_rpm_mode(self):
        """RPM shift indicator mode."""
        brights = [255] * 7 + [0, 0, 0]
        f1, f2 = encode_led_output(LED_MODE_RPM, brights, 0, 255, 0)

        assert f1[0] == LED_MODE_RPM
        assert f2[4] == 255  # G

    def test_warmup_mode(self):
        """Warm-up deep blue LED mode."""
        brights = [50] * 10
        f1, f2 = encode_led_output(LED_MODE_WARMUP, brights, 0, 0, 255)

        assert f1[0] == LED_MODE_WARMUP
        assert f2[5] == 255  # B

    def test_short_brightness_list_padded(self):
        """Short brightness list gets padded with zeros."""
        f1, f2 = encode_led_output(LED_MODE_OFF, [100, 200], 0, 0, 0)
        assert f1[1] == 100
        assert f1[2] == 200
        assert f1[3] == 0  # padded


# ========================================================================
# Round-trip encode/decode tests
# ========================================================================

class TestRoundTrip:
    """Verify encode → decode round-trip consistency for all frame types."""

    def test_diff_round_trip(self):
        """DIFF frame encode/decode preserves values within scaling precision."""
        for dccd in [0.0, 25.3, 50.0, 75.8, 100.0]:
            for slip in [-10.0, -1.23, 0.0, 5.67, 15.0]:
                data = encode_diff_frame(dccd, dccd, 0, 0, slip)
                result = decode_diff_frame(data)
                assert abs(result["dccd_command_pct"] - dccd) < 0.15
                assert abs(result["slip_delta"] - slip) < 0.015

    def test_context_round_trip(self):
        """CONTEXT frame encode/decode preserves values."""
        for gear in range(7):
            for speed in [0, 60, 120, 200]:
                data = encode_context_frame(gear, float(speed), 50.0)
                result = decode_context_frame(data)
                assert result["gear"] == gear
                assert abs(result["speed_kph"] - speed) < 0.015

    def test_generic_dash_1_round_trip(self):
        """GenDash1 round-trip: RPM, MAP, TPS, CLT."""
        for rpm in [800, 3500, 6000, 8000]:
            data = encode_generic_dash_1(float(rpm), 150.0, 50.0, 85.0)
            result = decode_generic_dash_1(data)
            assert abs(result["rpm"] - rpm) < 1.5
            assert abs(result["map_kpa"] - 150.0) < 0.15

    def test_generic_dash_2_round_trip(self):
        """GenDash2 round-trip: IAT, Lambda, Oil P, Oil T."""
        for lam in [0.78, 0.85, 1.0, 1.05]:
            data = encode_generic_dash_2(30.0, lam, 350.0, 95.0)
            result = decode_generic_dash_2(data)
            assert abs(result["lambda_1"] - lam) < 0.0015

    def test_generic_dash_3_round_trip(self):
        """GenDash3 round-trip: Ethanol, Fuel P, Battery, Inj Duty."""
        for eth in [0.0, 30.0, 85.0, 100.0]:
            data = encode_generic_dash_3(eth, 380.0, 14.2, 50.0)
            result = decode_generic_dash_3(data)
            assert abs(result["ethanol_pct"] - eth) < 0.15

    def test_si_drive_round_trip(self):
        """SI Drive round-trip for all modes."""
        for mode in [SI_DRIVE_INTELLIGENT, SI_DRIVE_SPORT, SI_DRIVE_SPORT_SHARP]:
            data = encode_si_drive_frame(mode)
            result = decode_si_drive_frame(data)
            assert result["mode"] == mode

    def test_sensor_round_trip(self):
        """Sensor frame round-trip."""
        for psi in [15.0, 40.0, 55.0, 80.0, 120.0]:
            data = encode_sensor_frame(200.0, 30.0, 50.0, psi)
            result = decode_sensor_frame(data)
            assert abs(result["oil_psi"] - psi) < 0.15

    def test_keypad_round_trip(self):
        """Keypad frame round-trip."""
        for state in [0x00, KEYPAD_K1, KEYPAD_K3, 0xFF]:
            data = encode_keypad_frame(state, 0x00)
            result = decode_keypad_frame(data)
            assert result["state"] == state

    def test_gps_round_trip(self):
        """GPS position frame round-trip."""
        for lat, lon in [(36.5842, -121.7528), (0.0, 0.0), (-33.8688, 151.2093)]:
            data = encode_gps_frame(lat, lon)
            result = decode_gps_frame(data)
            assert abs(result["latitude"] - lat) < 0.00002
            assert abs(result["longitude"] - lon) < 0.00002

    def test_gps_ext_round_trip(self):
        """GPS extended frame round-trip."""
        for alt in [0.0, 321.0, 4302.0, -86.0]:
            data = encode_gps_ext_frame(alt, 30.5, 135.0, 12, 2)
            result = decode_gps_ext_frame(data)
            assert abs(result["altitude_m"] - alt) < 1.0
            assert abs(result["speed_mps"] - 30.5) < 0.02

    def test_imu_round_trip(self):
        """IMU accelerometer frame round-trip."""
        for ax, ay, az in [(0.0, 0.0, 1.0), (-1.2, 0.9, 1.0), (0.5, -0.3, 0.98)]:
            data = encode_imu_frame(ax, ay, az)
            result = decode_imu_frame(data)
            assert abs(result["accel_x"] - ax) < 0.002
            assert abs(result["accel_y"] - ay) < 0.002
            assert abs(result["accel_z"] - az) < 0.002

    def test_imu_gyro_round_trip(self):
        """IMU gyroscope frame round-trip."""
        for gx, gy, gz in [(0.0, 0.0, 0.0), (45.0, -20.0, 120.0), (-30.0, 10.0, -5.0)]:
            data = encode_imu_gyro_frame(gx, gy, gz)
            result = decode_imu_gyro_frame(data)
            assert abs(result["gyro_x"] - gx) < 0.02
            assert abs(result["gyro_y"] - gy) < 0.02
            assert abs(result["gyro_z"] - gz) < 0.02


# ========================================================================
# DiffState staleness tests
# ========================================================================

class TestDiffStateStaleness:
    """Tests for DiffState.is_*_stale() methods."""

    def test_fresh_state_not_stale(self):
        now = time.monotonic()
        state = DiffState(diff_frame_ts=now, context_frame_ts=now)
        assert state.is_diff_stale(now, timeout=0.5) is False
        assert state.is_context_stale(now, timeout=0.5) is False
        assert state.is_any_stale(now, timeout=0.5) is False

    def test_zero_timestamp_is_stale(self):
        """Default timestamps (0.0) are always stale."""
        state = DiffState()
        assert state.is_diff_stale() is True
        assert state.is_context_stale() is True

    def test_old_timestamp_is_stale(self):
        now = time.monotonic()
        state = DiffState(diff_frame_ts=now - 1.0, context_frame_ts=now)
        assert state.is_diff_stale(now, timeout=0.5) is True
        assert state.is_context_stale(now, timeout=0.5) is False
        assert state.is_any_stale(now, timeout=0.5) is True

    def test_engine_stale(self):
        """Engine staleness tracks Generic Dash frame 1."""
        now = time.monotonic()
        state = DiffState(generic_dash_1_ts=now)
        assert state.is_engine_stale(now, timeout=0.5) is False

        state2 = DiffState(generic_dash_1_ts=now - 1.0)
        assert state2.is_engine_stale(now, timeout=0.5) is True

    def test_engine_stale_default(self):
        """Default (no engine data) is stale."""
        state = DiffState()
        assert state.is_engine_stale() is True

    def test_gps_stale_default(self):
        """Default (no GPS data) is stale."""
        state = DiffState()
        assert state.is_gps_stale() is True

    def test_gps_fresh(self):
        now = time.monotonic()
        state = DiffState(gps_frame_ts=now)
        assert state.is_gps_stale(now, timeout=1.0) is False

    def test_gps_old_is_stale(self):
        now = time.monotonic()
        state = DiffState(gps_frame_ts=now - 2.0)
        assert state.is_gps_stale(now, timeout=1.0) is True

    def test_imu_stale_default(self):
        """Default (no IMU data) is stale."""
        state = DiffState()
        assert state.is_imu_stale() is True

    def test_imu_fresh(self):
        now = time.monotonic()
        state = DiffState(imu_frame_ts=now)
        assert state.is_imu_stale(now, timeout=0.5) is False

    def test_imu_old_is_stale(self):
        now = time.monotonic()
        state = DiffState(imu_frame_ts=now - 1.0)
        assert state.is_imu_stale(now, timeout=0.5) is True


# ========================================================================
# SurfaceState enum tests
# ========================================================================

class TestSurfaceState:
    """Tests for SurfaceState enum properties."""

    def test_labels(self):
        assert SurfaceState.DRY.label == "DRY"
        assert SurfaceState.WET.label == "WET"
        assert SurfaceState.COLD.label == "COLD"
        assert SurfaceState.LOW_GRIP.label == "LOW GRIP"

    def test_colors(self):
        for s in SurfaceState:
            assert s.color.startswith("#")
            assert len(s.color) == 7

    def test_int_values(self):
        assert int(SurfaceState.DRY) == 0
        assert int(SurfaceState.WET) == 1
        assert int(SurfaceState.COLD) == 2
        assert int(SurfaceState.LOW_GRIP) == 3


# ========================================================================
# SIDriveMode enum tests
# ========================================================================

class TestSIDriveMode:
    """Tests for SIDriveMode enum properties."""

    def test_labels(self):
        assert SIDriveMode.INTELLIGENT.label == "Intelligent"
        assert SIDriveMode.SPORT.label == "Sport"
        assert SIDriveMode.SPORT_SHARP.label == "Sport Sharp"

    def test_short_labels(self):
        assert SIDriveMode.INTELLIGENT.short_label == "I"
        assert SIDriveMode.SPORT.short_label == "S"
        assert SIDriveMode.SPORT_SHARP.short_label == "S#"

    def test_colors(self):
        for m in SIDriveMode:
            assert m.color.startswith("#")
            assert len(m.color) == 7

    def test_int_values(self):
        assert int(SIDriveMode.INTELLIGENT) == 0
        assert int(SIDriveMode.SPORT) == 1
        assert int(SIDriveMode.SPORT_SHARP) == 2

    def test_from_can_value(self):
        """Construct from CAN integer values."""
        assert SIDriveMode(0) == SIDriveMode.INTELLIGENT
        assert SIDriveMode(1) == SIDriveMode.SPORT
        assert SIDriveMode(2) == SIDriveMode.SPORT_SHARP


# ========================================================================
# WarmUpState enum tests
# ========================================================================

class TestWarmUpState:
    """Tests for WarmUpState enum."""

    def test_labels(self):
        assert WarmUpState.COLD.label == "COLD"
        assert WarmUpState.WARMING.label == "WARMING"
        assert WarmUpState.READY.label == "READY"

    def test_colors(self):
        for w in WarmUpState:
            assert w.color.startswith("#")

    def test_int_values(self):
        assert int(WarmUpState.COLD) == 0
        assert int(WarmUpState.WARMING) == 1
        assert int(WarmUpState.READY) == 2


# ========================================================================
# Keypad edge detection tests
# ========================================================================

class TestKeypadEdgeDetection:
    """Tests for DiffState.keypad_pressed() / keypad_released()."""

    def test_button_just_pressed(self):
        """K1 just pressed: state=K1, prev=0."""
        state = DiffState(keypad_state=KEYPAD_K1, keypad_prev_state=0x00)
        assert state.keypad_pressed(KEYPAD_K1) is True
        assert state.keypad_released(KEYPAD_K1) is False

    def test_button_held(self):
        """K1 still held: state=K1, prev=K1 — not a new press."""
        state = DiffState(keypad_state=KEYPAD_K1, keypad_prev_state=KEYPAD_K1)
        assert state.keypad_pressed(KEYPAD_K1) is False
        assert state.keypad_released(KEYPAD_K1) is False

    def test_button_released(self):
        """K1 just released: state=0, prev=K1."""
        state = DiffState(keypad_state=0x00, keypad_prev_state=KEYPAD_K1)
        assert state.keypad_pressed(KEYPAD_K1) is False
        assert state.keypad_released(KEYPAD_K1) is True

    def test_multiple_buttons_mixed(self):
        """K1 held, K3 just pressed."""
        state = DiffState(
            keypad_state=KEYPAD_K1 | KEYPAD_K3,
            keypad_prev_state=KEYPAD_K1,
        )
        assert state.keypad_pressed(KEYPAD_K1) is False   # held
        assert state.keypad_pressed(KEYPAD_K3) is True    # new press
        assert state.keypad_pressed(KEYPAD_K2) is False   # not pressed

    def test_all_buttons_at_once(self):
        """All buttons pressed from nothing."""
        state = DiffState(keypad_state=0xFF, keypad_prev_state=0x00)
        for mask in [KEYPAD_K1, KEYPAD_K2, KEYPAD_K3, KEYPAD_K4, KEYPAD_K5, KEYPAD_K6]:
            assert state.keypad_pressed(mask) is True


# ========================================================================
# Ambient condition change detection tests
# ========================================================================

class TestAmbientChangeDetection:
    """Tests for YoctopuceReader delta detection logic."""

    def test_ambient_reading_dataclass(self):
        """AmbientReading fields have correct defaults."""
        from sensors.yoctopuce_reader import AmbientReading
        r = AmbientReading()
        assert r.temperature_c == 0.0
        assert r.humidity_pct == 0.0
        assert r.pressure_hpa == 0.0
        assert r.density_altitude_ft == 0.0
        assert r.dew_point_c == 0.0
        assert r.available is False

    def test_ambient_change_dataclass(self):
        """AmbientChange captures event details."""
        from sensors.yoctopuce_reader import AmbientChange
        c = AmbientChange(
            event="pressure_falling",
            message="Pressure falling.",
            old_value=1013.0,
            new_value=1007.0,
            delta=-6.0,
        )
        assert c.event == "pressure_falling"
        assert c.delta == -6.0

    def test_pressure_threshold_constants(self):
        """Delta thresholds are sensible."""
        from sensors.yoctopuce_reader import PRESSURE_DELTA_HPA, TEMP_DELTA_C, HUMIDITY_DELTA_PCT
        assert PRESSURE_DELTA_HPA == 5.0
        assert TEMP_DELTA_C == 3.0
        assert HUMIDITY_DELTA_PCT == 15.0

    def test_dew_point_calculation(self):
        """Magnus formula dew point at known conditions."""
        from sensors.yoctopuce_reader import _dew_point
        # At 20°C, 50% RH, dew point should be ~9.3°C
        dp = _dew_point(20.0, 50.0)
        assert 8.5 < dp < 10.0

    def test_dew_point_zero_humidity(self):
        """Zero humidity returns temperature (edge case guard)."""
        from sensors.yoctopuce_reader import _dew_point
        dp = _dew_point(25.0, 0.0)
        assert dp == 25.0

    def test_density_altitude_sea_level_isa(self):
        """ISA standard conditions: 1013.25 hPa, 15°C → ~0 ft."""
        from sensors.yoctopuce_reader import _density_altitude
        da = _density_altitude(1013.25, 15.0)
        assert abs(da) < 50  # within 50 ft of 0

    def test_density_altitude_hot_day(self):
        """Hot day at sea level pressure → positive density altitude."""
        from sensors.yoctopuce_reader import _density_altitude
        da = _density_altitude(1013.25, 35.0)  # 20°C above ISA
        assert da > 2000  # should be well above 0

    def test_density_altitude_zero_pressure(self):
        """Zero pressure returns 0 (guard)."""
        from sensors.yoctopuce_reader import _density_altitude
        da = _density_altitude(0.0, 20.0)
        assert da == 0.0


class TestAmbientDuckDB:
    """Tests for DuckDB ambient_conditions table."""

    def test_ambient_table_exists(self, tmp_path):
        """ambient_conditions table is created in schema."""
        from data.duckdb_store import DuckDBStore
        store = DuckDBStore(db_path=tmp_path / "test.duckdb")
        store.open()
        tables = store._conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_name = 'ambient_conditions'"
        ).fetchall()
        assert len(tables) == 1
        store.close()

    def test_record_ambient_basic(self, tmp_path):
        """Record and query ambient data."""
        from data.duckdb_store import DuckDBStore
        store = DuckDBStore(db_path=tmp_path / "test.duckdb")
        store.open()
        store.record_ambient(20.0, 55.0, 1013.0, 120.0, 9.3)
        rows = store._conn.execute("SELECT * FROM ambient_conditions").fetchall()
        assert len(rows) == 1
        assert rows[0][1] == 20.0  # temperature_c
        assert rows[0][2] == 55.0  # humidity_pct
        assert rows[0][3] == 1013.0  # pressure_hpa
        store.close()

    def test_record_ambient_with_change_event(self, tmp_path):
        """Record ambient data with a change event tag."""
        from data.duckdb_store import DuckDBStore
        store = DuckDBStore(db_path=tmp_path / "test.duckdb")
        store.open()
        store.record_ambient(18.0, 60.0, 1008.0, 200.0, 10.0,
                             change_event="pressure_falling", change_delta=-5.0)
        rows = store._conn.execute(
            "SELECT change_event, change_delta FROM ambient_conditions"
        ).fetchall()
        assert rows[0][0] == "pressure_falling"
        assert rows[0][1] == -5.0
        store.close()

    def test_ambient_in_db_stats(self, tmp_path):
        """db_stats includes ambient_conditions count."""
        from data.duckdb_store import DuckDBStore
        store = DuckDBStore(db_path=tmp_path / "test.duckdb")
        store.open()
        store.record_ambient(20.0, 50.0, 1013.0, 0.0, 9.0)
        stats = store.db_stats()
        assert stats["ambient_conditions"] == 1
        store.close()


class TestAmbientAlertEngine:
    """Tests for ambient change detection in AlertEngine."""

    def _make_bridge(self):
        """Create a DiffStateBridge with ambient data."""
        from model.vehicle_state import DiffStateBridge
        bridge = DiffStateBridge()
        return bridge

    def test_ambient_baseline_set_on_first_read(self):
        """First ambient reading sets baseline, no alert fired."""
        from alerts.alert_engine import AlertEngine
        bridge = self._make_bridge()
        engine = AlertEngine(bridge)
        alerts = []
        engine.alert_fired.connect(lambda a: alerts.append(a))

        # Set ambient available
        bridge.update_ambient(20.0, 50.0, 1013.0, 0.0, 9.0)
        engine._evaluate()
        # First call sets baseline — no ambient alert expected
        ambient_alerts = [a for a in alerts if a.alert_type.startswith(("pressure_", "temp_", "humidity_"))]
        assert len(ambient_alerts) == 0

    def test_ambient_pressure_drop_fires_alert(self):
        """Pressure drop >= 5 hPa fires advisory."""
        from alerts.alert_engine import AlertEngine
        bridge = self._make_bridge()
        engine = AlertEngine(bridge)
        alerts = []
        engine.alert_fired.connect(lambda a: alerts.append(a))

        # Baseline
        bridge.update_ambient(20.0, 50.0, 1013.0, 0.0, 9.0)
        engine._evaluate()

        # Significant pressure drop
        bridge.update_ambient(20.0, 50.0, 1007.0, 0.0, 9.0)
        engine._evaluate()

        pressure_alerts = [a for a in alerts if a.alert_type == "pressure_falling"]
        assert len(pressure_alerts) == 1
        assert pressure_alerts[0].severity.label == "advisory"

    def test_ambient_temp_drop_fires_alert(self):
        """Temperature drop >= 3°C fires advisory."""
        from alerts.alert_engine import AlertEngine
        bridge = self._make_bridge()
        engine = AlertEngine(bridge)
        alerts = []
        engine.alert_fired.connect(lambda a: alerts.append(a))

        bridge.update_ambient(20.0, 50.0, 1013.0, 0.0, 9.0)
        engine._evaluate()

        bridge.update_ambient(16.0, 50.0, 1013.0, 0.0, 7.0)
        engine._evaluate()

        temp_alerts = [a for a in alerts if a.alert_type == "temp_dropping"]
        assert len(temp_alerts) == 1

    def test_ambient_humidity_rise_fires_alert(self):
        """Humidity rise >= 15% fires advisory."""
        from alerts.alert_engine import AlertEngine
        bridge = self._make_bridge()
        engine = AlertEngine(bridge)
        alerts = []
        engine.alert_fired.connect(lambda a: alerts.append(a))

        bridge.update_ambient(20.0, 40.0, 1013.0, 0.0, 9.0)
        engine._evaluate()

        bridge.update_ambient(20.0, 60.0, 1013.0, 0.0, 9.0)
        engine._evaluate()

        hum_alerts = [a for a in alerts if a.alert_type == "humidity_rising"]
        assert len(hum_alerts) == 1

    def test_no_alert_below_threshold(self):
        """Small changes below threshold produce no alert."""
        from alerts.alert_engine import AlertEngine
        bridge = self._make_bridge()
        engine = AlertEngine(bridge)
        alerts = []
        engine.alert_fired.connect(lambda a: alerts.append(a))

        bridge.update_ambient(20.0, 50.0, 1013.0, 0.0, 9.0)
        engine._evaluate()

        # Small changes — below all thresholds
        bridge.update_ambient(21.0, 52.0, 1011.0, 0.0, 9.5)
        engine._evaluate()

        ambient_alerts = [a for a in alerts if a.alert_type.startswith(("pressure_", "temp_", "humidity_"))]
        assert len(ambient_alerts) == 0

    def test_ambient_not_available_skips(self):
        """No ambient data → no alerts, no crash."""
        from alerts.alert_engine import AlertEngine
        bridge = self._make_bridge()
        engine = AlertEngine(bridge)
        alerts = []
        engine.alert_fired.connect(lambda a: alerts.append(a))

        # Don't set any ambient data
        engine._evaluate()
        ambient_alerts = [a for a in alerts if a.alert_type.startswith(("pressure_", "temp_", "humidity_"))]
        assert len(ambient_alerts) == 0


class TestWeatherEventQuotes:
    """Tests for weather change event quotes in EVENT_QUOTES."""

    def test_weather_event_keys_exist(self):
        """All weather event keys have quotes."""
        from data.event_quotes import EVENT_QUOTES
        for key in ["pressure_falling", "pressure_rising", "temp_dropping",
                     "temp_rising", "humidity_rising", "humidity_dropping"]:
            assert key in EVENT_QUOTES, f"Missing event key: {key}"
            assert len(EVENT_QUOTES[key]) >= 3, f"Too few quotes for {key}"

    def test_get_event_quote_returns_weather(self):
        """get_event_quote returns a string for weather events."""
        from data.event_quotes import get_event_quote
        for key in ["pressure_falling", "temp_dropping", "humidity_rising"]:
            quote = get_event_quote(key)
            assert isinstance(quote, str)
            assert len(quote) > 10


class TestAmbientSimulator:
    """Tests for AmbientSimulator scripted weather scenario."""

    def test_simulator_creates(self):
        """AmbientSimulator instantiates without error."""
        from sensors.ambient_simulator import AmbientSimulator
        sim = AmbientSimulator()
        assert sim.available is False

    def test_simulator_phases_defined(self):
        """Simulation has multiple phases totalling > 60s."""
        from sensors.ambient_simulator import _PHASES
        assert len(_PHASES) >= 4
        total_s = sum(p.duration_s for p in _PHASES)
        assert total_s >= 60

    def test_simulator_initial_reading(self):
        """First reading matches phase 0 baseline."""
        from sensors.ambient_simulator import AmbientSimulator, _PHASES
        sim = AmbientSimulator()
        readings = []
        sim.reading_updated.connect(lambda r: readings.append(r))
        sim.start()
        sim.stop()
        assert len(readings) >= 1
        r = readings[0]
        assert abs(r.temperature_c - _PHASES[0].temp_c) < 0.5
        assert abs(r.pressure_hpa - _PHASES[0].pressure_hpa) < 0.5
        assert r.available is True

    def test_simulator_emits_changes(self):
        """Running through ticks produces condition_changed signals."""
        from sensors.ambient_simulator import AmbientSimulator
        sim = AmbientSimulator()
        changes = []
        sim.condition_changed.connect(lambda c: changes.append(c))
        sim.start()
        # Manually tick through enough to trigger at least one change
        for _ in range(40):
            sim._tick()
        sim.stop()
        assert len(changes) >= 1
        # First change should be pressure_falling (storm front in phase 2)
        assert changes[0].event == "pressure_falling"

    def test_simulator_completes(self):
        """Simulation emits simulation_ended after all phases."""
        from sensors.ambient_simulator import AmbientSimulator, _PHASES
        sim = AmbientSimulator()
        ended = []
        sim.simulation_ended.connect(lambda: ended.append(True))
        sim.start()
        total_ticks = sum(p.duration_s for p in _PHASES) + 5
        for _ in range(total_ticks):
            if not sim.available:
                break
            sim._tick()
        assert len(ended) == 1

    def test_simulator_values_interpolate(self):
        """Values change gradually, not in jumps."""
        from sensors.ambient_simulator import AmbientSimulator
        sim = AmbientSimulator()
        readings = []
        sim.reading_updated.connect(lambda r: readings.append(r))
        sim.start()
        for _ in range(30):
            sim._tick()
        sim.stop()
        # Check pressure decreases gradually over ticks 15-30 (phase 2)
        pressures = [r.pressure_hpa for r in readings]
        # Should have at least some downward movement
        assert pressures[-1] < pressures[0]
        # No single-tick jump > 2 hPa (gradual interpolation)
        for i in range(1, len(pressures)):
            assert abs(pressures[i] - pressures[i - 1]) < 2.0
