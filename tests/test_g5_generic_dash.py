"""Tests for can/g5_generic_dash.py — G5GenericDashParser"""

import struct
import time

import pytest

from can.g5_generic_dash import G5GenericDashParser

_CAN_ID = 0x3E8


def _make_frame(frame_idx: int, s0: int, s1: int, s2: int) -> bytes:
    """Build a valid 8-byte Generic Dash message."""
    return bytes([frame_idx, 0x00]) + struct.pack("<hhh", s0, s1, s2)


# ---------------------------------------------------------------------------
# Frame rejection
# ---------------------------------------------------------------------------

class TestFeedRejection:
    def setup_method(self):
        self.p = G5GenericDashParser()

    def test_wrong_can_id_rejected(self):
        frame = _make_frame(0, 6000, 1500, 500)
        assert self.p.feed(0x3E7, frame) is False

    def test_short_data_rejected(self):
        assert self.p.feed(_CAN_ID, b"\x00\x00\x00\x00\x00\x00\x00") is False

    def test_long_data_rejected(self):
        assert self.p.feed(_CAN_ID, b"\x00" * 9) is False

    def test_byte1_nonzero_rejected(self):
        bad = bytes([0, 0xFF]) + struct.pack("<hhh", 1000, 200, 300)
        assert self.p.feed(_CAN_ID, bad) is False

    def test_frame_idx_14_rejected(self):
        frame = bytes([14, 0x00]) + struct.pack("<hhh", 0, 0, 0)
        assert self.p.feed(_CAN_ID, frame) is False

    def test_frame_idx_255_rejected(self):
        frame = bytes([255, 0x00]) + struct.pack("<hhh", 0, 0, 0)
        assert self.p.feed(_CAN_ID, frame) is False

    def test_valid_frame_accepted(self):
        frame = _make_frame(0, 6000, 1200, 450)
        assert self.p.feed(_CAN_ID, frame) is True


# ---------------------------------------------------------------------------
# Properties return None before frame received
# ---------------------------------------------------------------------------

class TestNoneBeforeReceived:
    def setup_method(self):
        self.p = G5GenericDashParser()

    def test_rpm_none(self):
        assert self.p.rpm is None

    def test_map_none(self):
        assert self.p.map_kpa is None

    def test_tps_none(self):
        assert self.p.tps_pct is None

    def test_coolant_none(self):
        assert self.p.coolant_temp_c is None

    def test_lambda_none(self):
        assert self.p.lambda1 is None

    def test_lambda_afr_none(self):
        assert self.p.lambda1_afr is None

    def test_gear_none(self):
        assert self.p.gear is None

    def test_wheel_speed_lf_none(self):
        assert self.p.wheel_speed_lf_kph is None


# ---------------------------------------------------------------------------
# Frame 0: RPM, MAP, TPS
# ---------------------------------------------------------------------------

class TestFrame0:
    def setup_method(self):
        self.p = G5GenericDashParser()
        # RPM=7500 raw, MAP=1050 (→105.0 kPa), TPS=850 (→85.0%)
        self.p.feed(_CAN_ID, _make_frame(0, 7500, 1050, 850))

    def test_rpm(self):
        assert self.p.rpm == pytest.approx(7500.0)

    def test_map_kpa(self):
        assert self.p.map_kpa == pytest.approx(105.0)

    def test_tps_pct(self):
        assert self.p.tps_pct == pytest.approx(85.0)

    def test_negative_map_not_possible_but_signed_roundtrips(self):
        """int16 is signed — negative raw values should propagate as negative floats."""
        p = G5GenericDashParser()
        p.feed(_CAN_ID, _make_frame(0, 800, -10, 0))
        assert p.map_kpa == pytest.approx(-1.0)


# ---------------------------------------------------------------------------
# Frame 1: CLT, IAT, Lambda1
# ---------------------------------------------------------------------------

class TestFrame1:
    def setup_method(self):
        self.p = G5GenericDashParser()
        # CLT=850 (→85.0°C), IAT=250 (→25.0°C), Lambda=1000 (→1.000)
        self.p.feed(_CAN_ID, _make_frame(1, 850, 250, 1000))

    def test_coolant_temp_c(self):
        assert self.p.coolant_temp_c == pytest.approx(85.0)

    def test_iat_c(self):
        assert self.p.iat_c == pytest.approx(25.0)

    def test_lambda1(self):
        assert self.p.lambda1 == pytest.approx(1.000)

    def test_lambda1_afr_stoich(self):
        assert self.p.lambda1_afr == pytest.approx(14.7)

    def test_lambda1_rich(self):
        p = G5GenericDashParser()
        p.feed(_CAN_ID, _make_frame(1, 900, 300, 850))  # λ=0.850
        assert p.lambda1 == pytest.approx(0.850)
        assert p.lambda1_afr == pytest.approx(0.850 * 14.7)


# ---------------------------------------------------------------------------
# Frame 2: OilPress, OilTemp, FuelPress
# ---------------------------------------------------------------------------

class TestFrame2:
    def setup_method(self):
        self.p = G5GenericDashParser()
        # OilPress=4500 (→450.0 kPa), OilTemp=1200 (→120.0°C), FuelPress=3800 (→380.0 kPa)
        self.p.feed(_CAN_ID, _make_frame(2, 4500, 1200, 3800))

    def test_oil_pressure_kpa(self):
        assert self.p.oil_pressure_kpa == pytest.approx(450.0)

    def test_oil_temp_c(self):
        assert self.p.oil_temp_c == pytest.approx(120.0)

    def test_fuel_pressure_kpa(self):
        assert self.p.fuel_pressure_kpa == pytest.approx(380.0)


# ---------------------------------------------------------------------------
# Frame 3: Battery, InjDuty, Ethanol
# ---------------------------------------------------------------------------

class TestFrame3:
    def setup_method(self):
        self.p = G5GenericDashParser()
        # Battery=1390 (→13.90V), InjDuty=420 (→42.0%), Ethanol=100 (→10.0%)
        self.p.feed(_CAN_ID, _make_frame(3, 1390, 420, 100))

    def test_battery_v(self):
        assert self.p.battery_v == pytest.approx(13.90)

    def test_injector_duty_pct(self):
        assert self.p.injector_duty_pct == pytest.approx(42.0)

    def test_ethanol_pct(self):
        assert self.p.ethanol_pct == pytest.approx(10.0)


# ---------------------------------------------------------------------------
# Frame 4: Gear, WheelSpeed LF, WheelSpeed RF
# ---------------------------------------------------------------------------

class TestFrame4:
    def setup_method(self):
        self.p = G5GenericDashParser()
        # Gear=3, LF=1250 (→125.0 km/h), RF=1248 (→124.8 km/h)
        self.p.feed(_CAN_ID, _make_frame(4, 3, 1250, 1248))

    def test_gear(self):
        assert self.p.gear == 3

    def test_gear_returns_int(self):
        assert isinstance(self.p.gear, int)

    def test_wheel_speed_lf_kph(self):
        assert self.p.wheel_speed_lf_kph == pytest.approx(125.0)

    def test_wheel_speed_rf_kph(self):
        assert self.p.wheel_speed_rf_kph == pytest.approx(124.8)

    def test_gear_neutral(self):
        p = G5GenericDashParser()
        p.feed(_CAN_ID, _make_frame(4, 0, 0, 0))
        assert p.gear == 0


# ---------------------------------------------------------------------------
# Frame 5: WheelSpeed LR, WheelSpeed RR
# ---------------------------------------------------------------------------

class TestFrame5:
    def setup_method(self):
        self.p = G5GenericDashParser()
        # LR=1252 (→125.2 km/h), RR=1255 (→125.5 km/h)
        self.p.feed(_CAN_ID, _make_frame(5, 1252, 1255, 0))

    def test_wheel_speed_lr_kph(self):
        assert self.p.wheel_speed_lr_kph == pytest.approx(125.2)

    def test_wheel_speed_rr_kph(self):
        assert self.p.wheel_speed_rr_kph == pytest.approx(125.5)

    def test_unrelated_frame_still_none(self):
        # Frame 3 not fed — battery should still be None
        assert self.p.battery_v is None


# ---------------------------------------------------------------------------
# Stale detection
# ---------------------------------------------------------------------------

class TestStaleDetection:
    def test_stale_before_any_frame(self):
        p = G5GenericDashParser(stale_timeout=0.5)
        assert p.is_stale() is True

    def test_not_stale_immediately_after_feed(self):
        p = G5GenericDashParser(stale_timeout=0.5)
        p.feed(_CAN_ID, _make_frame(0, 5000, 1000, 500))
        assert p.is_stale() is False

    def test_stale_after_timeout(self, monkeypatch):
        fake_time = [0.0]
        monkeypatch.setattr(time, "monotonic", lambda: fake_time[0])
        p = G5GenericDashParser(stale_timeout=0.5)
        p.feed(_CAN_ID, _make_frame(0, 5000, 1000, 500))
        assert p.is_stale() is False
        fake_time[0] = 0.6
        assert p.is_stale() is True


# ---------------------------------------------------------------------------
# Custom CAN ID
# ---------------------------------------------------------------------------

class TestCustomCanId:
    def test_custom_id_accepted(self):
        p = G5GenericDashParser(can_id=0x400)
        frame = _make_frame(0, 6000, 1200, 500)
        assert p.feed(0x400, frame) is True
        assert p.rpm == pytest.approx(6000.0)

    def test_default_id_rejected_when_custom_set(self):
        p = G5GenericDashParser(can_id=0x400)
        frame = _make_frame(0, 6000, 1200, 500)
        assert p.feed(0x3E8, frame) is False


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------

class TestReset:
    def test_reset_clears_values(self):
        p = G5GenericDashParser()
        p.feed(_CAN_ID, _make_frame(0, 6000, 1200, 500))
        assert p.rpm is not None
        p.reset()
        assert p.rpm is None
        assert p.is_stale() is True
