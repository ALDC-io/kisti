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
    DYN_BRAKE_OFFSET,
    DYN_BRAKE_SCALE,
    DYN_LATG_OFFSET,
    DYN_LATG_SCALE,
    DYN_STEER_OFFSET,
    DYN_STEER_SCALE,
    DYN_YAW_OFFSET,
    DYN_YAW_SCALE,
    DYNAMICS_FRAME_ID,
    KISTI_CAN_IDS,
    MOCK_CONTEXT_HZ,
    MOCK_DIFF_HZ,
    MOCK_DYNAMICS_HZ,
    MOCK_ENABLED,
    MOCK_WHEEL_HZ,
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
                    elif msg.arbitration_id == WHEEL_SPEED_FRAME_ID:
                        d = decode_wheel_speed_frame(msg.data)
                        self._bridge.update_wheel_speeds(**d)
                    elif msg.arbitration_id == DYNAMICS_FRAME_ID:
                        d = decode_dynamics_frame(msg.data)
                        self._bridge.update_dynamics(**d)
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
        self._steering = 0.0
        self._yaw = 0.0
        self._lat_g = 0.0
        self._brake_press = 0.0

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

    def start(self) -> None:
        self._diff_timer.start()
        self._ctx_timer.start()
        self._ws_timer.start()
        self._dyn_timer.start()
        log.info("Mock CAN generator started")

    def stop(self) -> None:
        self._diff_timer.stop()
        self._ctx_timer.stop()
        self._ws_timer.stop()
        self._dyn_timer.stop()

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
