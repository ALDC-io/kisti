"""KiSTI - CAN Listener & Decoder

Reads Link ECU CAN frames on socketcan, decodes DIFF (0x6A0) and
CONTEXT (0x6A1) messages, and pushes updates to DiffStateBridge.

Falls back to mock data generation if python-can is unavailable or
the CAN interface doesn't exist.  Mock mode uses QTimers on the
main thread so no real threading is involved.
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
    KISTI_CAN_IDS,
    MOCK_CONTEXT_HZ,
    MOCK_DIFF_HZ,
    MOCK_ENABLED,
    STALE_TIMEOUT_S,
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
                    if msg.arbitration_id == DIFF_FRAME_ID:
                        d = decode_diff_frame(msg.data)
                        self._bridge.update_diff(**d)
                    elif msg.arbitration_id == CONTEXT_FRAME_ID:
                        d = decode_context_frame(msg.data)
                        self._bridge.update_context(**d)
                except (ValueError, struct.error) as exc:
                    log.debug("Decode error on 0x%03X: %s", msg.arbitration_id, exc)
        finally:
            bus.shutdown()
            log.info("CAN bus closed")


# ---------------------------------------------------------------------------
# Mock Data Generator (runs on Qt main thread via QTimer)
# ---------------------------------------------------------------------------

class MockCanGenerator(QObject):
    """Generates plausible DCCD / context telemetry when no CAN bus.

    Simulates spirited canyon driving: varying DCCD lock, throttle,
    speed, occasional braking and slip events.
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

        self._diff_timer = QTimer(self)
        self._diff_timer.setInterval(1000 // MOCK_DIFF_HZ)
        self._diff_timer.timeout.connect(self._diff_tick)

        self._ctx_timer = QTimer(self)
        self._ctx_timer.setInterval(1000 // MOCK_CONTEXT_HZ)
        self._ctx_timer.timeout.connect(self._ctx_tick)

    def start(self) -> None:
        self._diff_timer.start()
        self._ctx_timer.start()
        log.info("Mock CAN generator started")

    def stop(self) -> None:
        self._diff_timer.stop()
        self._ctx_timer.stop()

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
