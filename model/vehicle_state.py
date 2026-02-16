"""KiSTI - Diff State Model & Qt Signal Bridge

Thread-safe vehicle state for the DIFF tab. The CAN listener thread
writes via DiffStateBridge; the UI reads snapshots via copy().

DiffState is intentionally separate from the existing VehicleState
to keep the CAN→UI pipeline independent of the mock data generator.
"""

from __future__ import annotations

import copy
import threading
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional

from PySide6.QtCore import QObject, Signal


class SurfaceState(IntEnum):
    """Surface condition enum — matches CAN byte encoding."""
    DRY = 0
    WET = 1
    COLD = 2
    LOW_GRIP = 3

    @property
    def label(self) -> str:
        return _SURFACE_LABELS[self]

    @property
    def color(self) -> str:
        """Hex color for UI rendering."""
        return _SURFACE_COLORS[self]


_SURFACE_LABELS = {
    SurfaceState.DRY: "DRY",
    SurfaceState.WET: "WET",
    SurfaceState.COLD: "COLD",
    SurfaceState.LOW_GRIP: "LOW GRIP",
}

_SURFACE_COLORS = {
    SurfaceState.DRY: "#00CC66",   # Green — good grip
    SurfaceState.WET: "#00AAFF",   # Blue — wet
    SurfaceState.COLD: "#AA88FF",  # Purple — cold
    SurfaceState.LOW_GRIP: "#FF3333",  # Red — danger
}


@dataclass
class DiffState:
    """Snapshot of center diff telemetry from Link ECU via CAN.

    All fields use native Python types for thread-safe copying.
    Optional[float] = None means signal not available.
    """

    # DCCD
    dccd_command_pct: float = 0.0          # 0.0 – 100.0
    dccd_dial_pct: Optional[float] = None  # None = not available

    # Surface
    surface_state: SurfaceState = SurfaceState.DRY

    # Event flags
    brake: bool = False
    handbrake: bool = False
    abs_active: bool = False
    vdc_tc: bool = False

    # Slip
    slip_delta: Optional[float] = None  # km/h; None = N/A

    # Context
    gear: int = 0              # 0 = neutral, 1-6
    speed_kph: float = 0.0
    throttle_pct: float = 0.0

    # Individual wheel speeds (km/h) — from ABS sensors via Link
    wheel_speed_fl: float = 0.0
    wheel_speed_fr: float = 0.0
    wheel_speed_rl: float = 0.0
    wheel_speed_rr: float = 0.0

    # Vehicle dynamics — from VDC module via Link
    steering_angle: float = 0.0      # degrees (negative = right)
    yaw_rate: float = 0.0            # deg/s
    lateral_g: float = 0.0           # g
    brake_pressure: float = 0.0      # bar

    # Staleness tracking (monotonic timestamps)
    diff_frame_ts: float = 0.0
    context_frame_ts: float = 0.0
    wheel_frame_ts: float = 0.0
    dynamics_frame_ts: float = 0.0

    # CAN bus connection status
    can_connected: bool = False

    def is_diff_stale(self, now: Optional[float] = None, timeout: float = 0.5) -> bool:
        """True if no DIFF frame received within timeout seconds."""
        if self.diff_frame_ts == 0.0:
            return True
        t = now if now is not None else time.monotonic()
        return (t - self.diff_frame_ts) > timeout

    def is_context_stale(self, now: Optional[float] = None, timeout: float = 0.5) -> bool:
        """True if no CONTEXT frame received within timeout seconds."""
        if self.context_frame_ts == 0.0:
            return True
        t = now if now is not None else time.monotonic()
        return (t - self.context_frame_ts) > timeout

    def is_wheel_stale(self, now: Optional[float] = None, timeout: float = 0.5) -> bool:
        """True if no WHEEL_SPEED frame received within timeout seconds."""
        if self.wheel_frame_ts == 0.0:
            return True
        t = now if now is not None else time.monotonic()
        return (t - self.wheel_frame_ts) > timeout

    def is_dynamics_stale(self, now: Optional[float] = None, timeout: float = 0.5) -> bool:
        """True if no DYNAMICS frame received within timeout seconds."""
        if self.dynamics_frame_ts == 0.0:
            return True
        t = now if now is not None else time.monotonic()
        return (t - self.dynamics_frame_ts) > timeout

    def is_any_stale(self, now: Optional[float] = None, timeout: float = 0.5) -> bool:
        return self.is_diff_stale(now, timeout) or self.is_context_stale(now, timeout)


class DiffStateBridge(QObject):
    """Thread-safe bridge between CAN listener thread and Qt UI.

    The CAN thread calls update_diff() / update_context() which acquire
    a lock and update the internal DiffState.  The UI thread calls
    snapshot() from a QTimer to get a copy without blocking.

    Optionally emits state_changed when a CAN frame is decoded, but
    the recommended pattern is polling via QTimer at 20 Hz.
    """

    state_changed = Signal()  # lightweight notification (no payload)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._state = DiffState()
        self._lock = threading.Lock()

    def snapshot(self) -> DiffState:
        """Return a thread-safe copy of the current state."""
        with self._lock:
            return copy.copy(self._state)

    def update_diff(
        self,
        dccd_command_pct: float,
        dccd_dial_pct: Optional[float],
        surface_state: SurfaceState,
        brake: bool,
        handbrake: bool,
        abs_active: bool,
        vdc_tc: bool,
        slip_delta: Optional[float],
    ) -> None:
        """Called from CAN listener thread with decoded DIFF frame."""
        with self._lock:
            self._state.dccd_command_pct = dccd_command_pct
            self._state.dccd_dial_pct = dccd_dial_pct
            self._state.surface_state = surface_state
            self._state.brake = brake
            self._state.handbrake = handbrake
            self._state.abs_active = abs_active
            self._state.vdc_tc = vdc_tc
            self._state.slip_delta = slip_delta
            self._state.diff_frame_ts = time.monotonic()
            self._state.can_connected = True
        self.state_changed.emit()

    def update_context(
        self,
        gear: int,
        speed_kph: float,
        throttle_pct: float,
    ) -> None:
        """Called from CAN listener thread with decoded CONTEXT frame."""
        with self._lock:
            self._state.gear = gear
            self._state.speed_kph = speed_kph
            self._state.throttle_pct = throttle_pct
            self._state.context_frame_ts = time.monotonic()
            self._state.can_connected = True
        self.state_changed.emit()

    def update_wheel_speeds(
        self,
        fl: float,
        fr: float,
        rl: float,
        rr: float,
    ) -> None:
        """Called from CAN listener thread with decoded WHEEL_SPEED frame."""
        with self._lock:
            self._state.wheel_speed_fl = fl
            self._state.wheel_speed_fr = fr
            self._state.wheel_speed_rl = rl
            self._state.wheel_speed_rr = rr
            self._state.wheel_frame_ts = time.monotonic()
            self._state.can_connected = True
        self.state_changed.emit()

    def update_dynamics(
        self,
        steering_angle: float,
        yaw_rate: float,
        lateral_g: float,
        brake_pressure: float,
    ) -> None:
        """Called from CAN listener thread with decoded DYNAMICS frame."""
        with self._lock:
            self._state.steering_angle = steering_angle
            self._state.yaw_rate = yaw_rate
            self._state.lateral_g = lateral_g
            self._state.brake_pressure = brake_pressure
            self._state.dynamics_frame_ts = time.monotonic()
            self._state.can_connected = True
        self.state_changed.emit()

    def set_disconnected(self) -> None:
        """Mark CAN bus as disconnected."""
        with self._lock:
            self._state.can_connected = False
        self.state_changed.emit()
