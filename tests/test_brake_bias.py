"""Tests for dual brake pressure integration — CAN decode, DiffState, bias."""

from __future__ import annotations

import struct
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from can.can_config import BRK_FRONT_OFFSET, BRK_PDM_PUMP_ON, BRK_PDM_PUMP_FAULT, BRK_REAR_OFFSET, BRK_SCALE
from can.kisti_can import decode_brake_pressure_frame
from model.vehicle_state import DiffState, DiffStateBridge


def _encode_brake_frame(front_bar: float, rear_bar: float, pdm: int = 1) -> bytes:
    """Build a raw 8-byte CAN frame for dual brake pressure."""
    data = bytearray(8)
    struct.pack_into(">H", data, BRK_FRONT_OFFSET, int(front_bar / BRK_SCALE))
    struct.pack_into(">H", data, BRK_REAR_OFFSET, int(rear_bar / BRK_SCALE))
    data[4] = pdm
    return bytes(data)


class TestDecodeBrakePressureFrame:
    def test_basic_decode(self):
        frame = _encode_brake_frame(42.0, 22.0)
        d = decode_brake_pressure_frame(frame)
        assert abs(d["brake_front"] - 42.0) < 0.2
        assert abs(d["brake_rear"] - 22.0) < 0.2
        assert d["fuel_pump_active"] is True
        assert d["fuel_pump_fault"] is False

    def test_zero_pressure(self):
        frame = _encode_brake_frame(0.0, 0.0)
        d = decode_brake_pressure_frame(frame)
        assert d["brake_front"] == 0.0
        assert d["brake_rear"] == 0.0

    def test_pump_fault(self):
        frame = _encode_brake_frame(30.0, 15.0, pdm=BRK_PDM_PUMP_FAULT)
        d = decode_brake_pressure_frame(frame)
        assert d["fuel_pump_fault"] is True
        assert d["fuel_pump_active"] is False

    def test_pump_off(self):
        frame = _encode_brake_frame(0.0, 0.0, pdm=0)
        d = decode_brake_pressure_frame(frame)
        assert d["fuel_pump_active"] is False
        assert d["fuel_pump_fault"] is False

    def test_frame_too_short(self):
        import pytest
        with pytest.raises(ValueError, match="too short"):
            decode_brake_pressure_frame(b"\x00\x01\x02\x03")

    def test_high_pressure(self):
        frame = _encode_brake_frame(80.0, 45.0)
        d = decode_brake_pressure_frame(frame)
        assert abs(d["brake_front"] - 80.0) < 0.2
        assert abs(d["brake_rear"] - 45.0) < 0.2


class TestDiffStateBrakeFields:
    def test_default_values(self):
        state = DiffState()
        assert state.brake_pressure_front == 0.0
        assert state.brake_pressure_rear == 0.0
        assert state.brake_bias_pct == 0.0
        assert state.fuel_pump_active is True

    def test_fields_populate(self):
        state = DiffState()
        state.brake_pressure_front = 42.0
        state.brake_pressure_rear = 22.0
        state.brake_bias_pct = 65.6
        assert state.brake_pressure_front == 42.0
        assert state.brake_pressure_rear == 22.0
        assert state.brake_bias_pct == 65.6


class TestDiffStateBridgeBrakePressures:
    def test_update_brake_pressures_computes_bias(self):
        bridge = DiffStateBridge.__new__(DiffStateBridge)
        bridge._lock = __import__("threading").Lock()
        bridge._state = DiffState()
        bridge.state_changed = MagicMock()

        bridge.update_brake_pressures(front=42.0, rear=22.0)

        snap = bridge._state
        assert snap.brake_pressure_front == 42.0
        assert snap.brake_pressure_rear == 22.0
        assert snap.brake_pressure == 42.0  # max(front, rear)
        assert abs(snap.brake_bias_pct - 65.625) < 0.01  # 42/(42+22)*100

    def test_zero_pressure_no_division_error(self):
        bridge = DiffStateBridge.__new__(DiffStateBridge)
        bridge._lock = __import__("threading").Lock()
        bridge._state = DiffState()
        bridge.state_changed = MagicMock()

        bridge.update_brake_pressures(front=0.0, rear=0.0)
        assert bridge._state.brake_bias_pct == 0.0

    def test_low_pressure_threshold(self):
        """Below 1.0 bar total, bias should be 0 (not meaningful)."""
        bridge = DiffStateBridge.__new__(DiffStateBridge)
        bridge._lock = __import__("threading").Lock()
        bridge._state = DiffState()
        bridge.state_changed = MagicMock()

        bridge.update_brake_pressures(front=0.3, rear=0.2)
        assert bridge._state.brake_bias_pct == 0.0

    def test_backward_compat_single_pressure(self):
        """update_dynamics still works with single brake_pressure."""
        bridge = DiffStateBridge.__new__(DiffStateBridge)
        bridge._lock = __import__("threading").Lock()
        bridge._state = DiffState()
        bridge.state_changed = MagicMock()

        bridge.update_dynamics(
            steering_angle=10.0, yaw_rate=5.0,
            lateral_g=0.3, brake_pressure=35.0,
        )
        assert bridge._state.brake_pressure == 35.0
        # front/rear untouched
        assert bridge._state.brake_pressure_front == 0.0
        assert bridge._state.brake_pressure_rear == 0.0
