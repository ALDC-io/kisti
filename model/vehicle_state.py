"""KiSTI - Vehicle State Model & Qt Signal Bridge

Thread-safe vehicle state for KiSTI. The CAN listener thread
writes via DiffStateBridge; the UI reads snapshots via snapshot().

Supports both G4X (DCCD/context only) and G5 Neo 4 (full telemetry
including SI Drive mode, Generic Dash, extended sensors, keypad).
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


class SIDriveMode(IntEnum):
    """SI Drive mode — matches Link G5 User CAN output values."""
    INTELLIGENT = 0   # "KiSTI Guide" — full voice, waveform LEDs
    SPORT = 1         # "KiSTI Co-Driver" — short alerts, RPM LEDs
    SPORT_SHARP = 2   # "KiSTI Race Engineer" — critical only, RPM LEDs

    @property
    def label(self) -> str:
        return _SI_DRIVE_LABELS[self]

    @property
    def short_label(self) -> str:
        return _SI_DRIVE_SHORT_LABELS[self]

    @property
    def color(self) -> str:
        return _SI_DRIVE_COLORS[self]


_SI_DRIVE_LABELS = {
    SIDriveMode.INTELLIGENT: "Intelligent",
    SIDriveMode.SPORT: "Sport",
    SIDriveMode.SPORT_SHARP: "Sport Sharp",
}

_SI_DRIVE_SHORT_LABELS = {
    SIDriveMode.INTELLIGENT: "I",
    SIDriveMode.SPORT: "S",
    SIDriveMode.SPORT_SHARP: "S#",
}

_SI_DRIVE_COLORS = {
    SIDriveMode.INTELLIGENT: "#00AAFF",  # Blue — calm
    SIDriveMode.SPORT: "#FF8800",        # Amber — spirited
    SIDriveMode.SPORT_SHARP: "#FF0000",  # Red — maximum attack
}


class WarmUpState(IntEnum):
    """Engine warm-up state machine."""
    COLD = 0       # Deep blue LEDs, "Warm-up sequence engaged"
    WARMING = 1    # Cherry red LEDs, monitoring temps
    READY = 2      # Green LEDs, "Engine Ready"

    @property
    def label(self) -> str:
        return _WARMUP_LABELS[self]

    @property
    def color(self) -> str:
        return _WARMUP_COLORS[self]


_WARMUP_LABELS = {
    WarmUpState.COLD: "COLD",
    WarmUpState.WARMING: "WARMING",
    WarmUpState.READY: "READY",
}

_WARMUP_COLORS = {
    WarmUpState.COLD: "#0044FF",     # Deep blue
    WarmUpState.WARMING: "#CC2200",  # Cherry red
    WarmUpState.READY: "#00CC66",    # Green
}


@dataclass
class DiffState:
    """Snapshot of vehicle telemetry from Link ECU via CAN.

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

    # --- G5 Neo 4 additions ---

    # SI Drive mode (analog input to ECU, output via User CAN)
    si_drive_mode: SIDriveMode = SIDriveMode.INTELLIGENT

    # Generic Dash stream (0x360-0x362)
    rpm: float = 0.0                   # RPM
    map_kpa: float = 0.0              # Manifold Absolute Pressure (kPa)
    tps: float = 0.0                  # Throttle Position (%)
    coolant_temp: float = 0.0         # °C
    iat_c: float = 0.0                # Intake Air Temp (°C)
    lambda_1: float = 0.0             # Lambda (air-fuel ratio)
    oil_pressure_kpa: float = 0.0     # Oil pressure (kPa) from Generic Dash
    oil_temp_c: float = 0.0           # Oil temp (°C)
    ethanol_pct: float = 0.0          # Ethanol content (%)
    fuel_pressure_kpa: float = 0.0    # Fuel pressure (kPa)
    battery_v: float = 0.0            # Battery voltage (V)
    injector_duty: float = 0.0        # Injector duty cycle (%)

    # Extended sensors (0x6B1) — dedicated analog inputs
    map_4bar_kpa: float = 0.0         # 4-bar MAP sensor (kPa)
    iat_ext_c: float = 0.0            # External IAT sensor (°C)
    ethanol_ext_pct: float = 0.0      # Flex Fuel sensor (%)
    oil_psi: float = 0.0              # 150 PSI oil pressure sensor

    # Keypad (0x6B2)
    keypad_state: int = 0             # Current button bitfield
    keypad_prev_state: int = 0        # Previous button bitfield

    # GPS09 Pro — GPS (0x6A4, 0x6A5)
    gps_latitude: float = 0.0         # degrees (WGS84)
    gps_longitude: float = 0.0        # degrees (WGS84)
    gps_altitude_m: float = 0.0       # meters above sea level
    gps_speed_mps: float = 0.0        # m/s
    gps_heading: float = 0.0          # degrees (0-360, true north)
    gps_satellites: int = 0           # satellite count
    gps_fix_quality: int = 0          # 0=none, 1=2D, 2=3D

    # GPS09 Pro — IMU (0x6A6, 0x6A7)
    imu_accel_x: float = 0.0          # g (longitudinal, +ve = acceleration)
    imu_accel_y: float = 0.0          # g (lateral, +ve = right)
    imu_accel_z: float = 0.0          # g (vertical, +ve = up = 1.0 at rest)
    imu_gyro_x: float = 0.0           # deg/s (roll rate)
    imu_gyro_y: float = 0.0           # deg/s (pitch rate)
    imu_gyro_z: float = 0.0           # deg/s (yaw rate)

    # Lap timing (computed from GPS + track definition)
    lap_count: int = 0
    lap_time_ms: int = 0

    # Race analysis timing (from TimingManager)
    current_sector: int = 0
    sector_count: int = 0
    current_lap_time_ms: int = 0
    last_sector_time_ms: int = 0
    delta_ms: int = 0                     # +ve = slower than reference
    predicted_lap_ms: int = 0
    theoretical_best_ms: int = 0
    track_name: str = ""
    timing_mode: str = ""                 # 'circuit' | 'point_to_point' | ''
    lap_distance_m: float = 0.0

    # Ambient weather (Yoctopuce Yocto-Meteo-V2, exterior)
    ambient_temp_c: float = 0.0           # °C
    ambient_humidity_pct: float = 0.0     # %RH
    ambient_pressure_hpa: float = 0.0     # hPa (barometric)
    density_altitude_ft: float = 0.0      # feet
    dew_point_c: float = 0.0             # °C
    ambient_available: bool = False

    # Warm-up state (computed, not from CAN)
    warmup_state: WarmUpState = WarmUpState.COLD

    # Staleness tracking (monotonic timestamps)
    diff_frame_ts: float = 0.0
    context_frame_ts: float = 0.0
    wheel_frame_ts: float = 0.0
    dynamics_frame_ts: float = 0.0
    si_drive_frame_ts: float = 0.0
    generic_dash_1_ts: float = 0.0
    generic_dash_2_ts: float = 0.0
    generic_dash_3_ts: float = 0.0
    sensor_frame_ts: float = 0.0
    keypad_frame_ts: float = 0.0
    gps_frame_ts: float = 0.0
    gps_ext_frame_ts: float = 0.0
    imu_frame_ts: float = 0.0
    imu_gyro_frame_ts: float = 0.0

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

    def is_engine_stale(self, now: Optional[float] = None, timeout: float = 0.5) -> bool:
        """True if no Generic Dash frame 1 received within timeout seconds."""
        if self.generic_dash_1_ts == 0.0:
            return True
        t = now if now is not None else time.monotonic()
        return (t - self.generic_dash_1_ts) > timeout

    def is_gps_stale(self, now: Optional[float] = None, timeout: float = 1.0) -> bool:
        """True if no GPS frame received within timeout seconds (default 1s for 10 Hz)."""
        if self.gps_frame_ts == 0.0:
            return True
        t = now if now is not None else time.monotonic()
        return (t - self.gps_frame_ts) > timeout

    def is_imu_stale(self, now: Optional[float] = None, timeout: float = 0.5) -> bool:
        """True if no IMU frame received within timeout seconds."""
        if self.imu_frame_ts == 0.0:
            return True
        t = now if now is not None else time.monotonic()
        return (t - self.imu_frame_ts) > timeout

    def is_any_stale(self, now: Optional[float] = None, timeout: float = 0.5) -> bool:
        return self.is_diff_stale(now, timeout) or self.is_context_stale(now, timeout)

    def keypad_pressed(self, button_mask: int) -> bool:
        """True if button was just pressed (rising edge)."""
        return bool(self.keypad_state & button_mask) and not bool(
            self.keypad_prev_state & button_mask
        )

    def keypad_released(self, button_mask: int) -> bool:
        """True if button was just released (falling edge)."""
        return not bool(self.keypad_state & button_mask) and bool(
            self.keypad_prev_state & button_mask
        )


class DiffStateBridge(QObject):
    """Thread-safe bridge between CAN listener thread and Qt UI.

    The CAN thread calls update_*() methods which acquire a lock and
    update the internal DiffState. The UI thread calls snapshot() from
    a QTimer to get a copy without blocking.

    Emits state_changed when a CAN frame is decoded. Recommended
    pattern is polling via QTimer at 20 Hz.
    """

    state_changed = Signal()       # lightweight notification (no payload)
    si_drive_changed = Signal(int) # emitted when SI Drive mode changes (new mode int)
    keypad_pressed = Signal(int)   # emitted on keypad button press (button mask)

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

    def update_si_drive(self, mode: int) -> None:
        """Called from CAN listener thread with decoded SI Drive frame."""
        changed = False
        with self._lock:
            try:
                new_mode = SIDriveMode(mode)
            except ValueError:
                new_mode = SIDriveMode.INTELLIGENT
            if self._state.si_drive_mode != new_mode:
                changed = True
            self._state.si_drive_mode = new_mode
            self._state.si_drive_frame_ts = time.monotonic()
            self._state.can_connected = True
        self.state_changed.emit()
        if changed:
            self.si_drive_changed.emit(int(new_mode))

    def update_generic_dash_1(
        self,
        rpm: float,
        map_kpa: float,
        tps: float,
        coolant_temp: float,
    ) -> None:
        """Called from CAN listener with decoded Generic Dash frame 1 (0x360)."""
        with self._lock:
            self._state.rpm = rpm
            self._state.map_kpa = map_kpa
            self._state.tps = tps
            self._state.coolant_temp = coolant_temp
            self._state.generic_dash_1_ts = time.monotonic()
            self._state.can_connected = True
        self.state_changed.emit()

    def update_generic_dash_2(
        self,
        iat_c: float,
        lambda_1: float,
        oil_pressure_kpa: float,
        oil_temp_c: float,
    ) -> None:
        """Called from CAN listener with decoded Generic Dash frame 2 (0x361)."""
        with self._lock:
            self._state.iat_c = iat_c
            self._state.lambda_1 = lambda_1
            self._state.oil_pressure_kpa = oil_pressure_kpa
            self._state.oil_temp_c = oil_temp_c
            self._state.generic_dash_2_ts = time.monotonic()
            self._state.can_connected = True
        self.state_changed.emit()

    def update_generic_dash_3(
        self,
        ethanol_pct: float,
        fuel_pressure_kpa: float,
        battery_v: float,
        injector_duty: float,
    ) -> None:
        """Called from CAN listener with decoded Generic Dash frame 3 (0x362)."""
        with self._lock:
            self._state.ethanol_pct = ethanol_pct
            self._state.fuel_pressure_kpa = fuel_pressure_kpa
            self._state.battery_v = battery_v
            self._state.injector_duty = injector_duty
            self._state.generic_dash_3_ts = time.monotonic()
            self._state.can_connected = True
        self.state_changed.emit()

    def update_sensors(
        self,
        map_4bar_kpa: float,
        iat_ext_c: float,
        ethanol_ext_pct: float,
        oil_psi: float,
    ) -> None:
        """Called from CAN listener with decoded extended sensor frame (0x6B1)."""
        with self._lock:
            self._state.map_4bar_kpa = map_4bar_kpa
            self._state.iat_ext_c = iat_ext_c
            self._state.ethanol_ext_pct = ethanol_ext_pct
            self._state.oil_psi = oil_psi
            self._state.sensor_frame_ts = time.monotonic()
            self._state.can_connected = True
        self.state_changed.emit()

    def update_keypad(self, state: int, prev_state: int) -> None:
        """Called from CAN listener with decoded keypad frame (0x6B2)."""
        pressed_buttons = 0
        with self._lock:
            self._state.keypad_state = state
            self._state.keypad_prev_state = prev_state
            self._state.keypad_frame_ts = time.monotonic()
            self._state.can_connected = True
            # Detect rising edges (newly pressed buttons)
            pressed_buttons = state & ~prev_state
        self.state_changed.emit()
        if pressed_buttons:
            self.keypad_pressed.emit(pressed_buttons)

    def update_gps(self, latitude: float, longitude: float) -> None:
        """Called from CAN listener with decoded GPS position frame (0x6A4)."""
        with self._lock:
            self._state.gps_latitude = latitude
            self._state.gps_longitude = longitude
            self._state.gps_frame_ts = time.monotonic()
            self._state.can_connected = True
        self.state_changed.emit()

    def update_gps_ext(
        self,
        altitude_m: float,
        speed_mps: float,
        heading: float,
        satellites: int,
        fix_quality: int,
    ) -> None:
        """Called from CAN listener with decoded GPS extended frame (0x6A5)."""
        with self._lock:
            self._state.gps_altitude_m = altitude_m
            self._state.gps_speed_mps = speed_mps
            self._state.gps_heading = heading
            self._state.gps_satellites = satellites
            self._state.gps_fix_quality = fix_quality
            self._state.gps_ext_frame_ts = time.monotonic()
            self._state.can_connected = True
        self.state_changed.emit()

    def update_imu(self, accel_x: float, accel_y: float, accel_z: float) -> None:
        """Called from CAN listener with decoded IMU accelerometer frame (0x6A6)."""
        with self._lock:
            self._state.imu_accel_x = accel_x
            self._state.imu_accel_y = accel_y
            self._state.imu_accel_z = accel_z
            self._state.imu_frame_ts = time.monotonic()
            self._state.can_connected = True
        self.state_changed.emit()

    def update_imu_gyro(self, gyro_x: float, gyro_y: float, gyro_z: float) -> None:
        """Called from CAN listener with decoded IMU gyroscope frame (0x6A7)."""
        with self._lock:
            self._state.imu_gyro_x = gyro_x
            self._state.imu_gyro_y = gyro_y
            self._state.imu_gyro_z = gyro_z
            self._state.imu_gyro_frame_ts = time.monotonic()
            self._state.can_connected = True
        self.state_changed.emit()

    def update_ambient(
        self,
        temp_c: float,
        humidity_pct: float,
        pressure_hpa: float,
        density_altitude_ft: float,
        dew_point_c: float,
    ) -> None:
        """Called from Yoctopuce reader with ambient weather data."""
        with self._lock:
            self._state.ambient_temp_c = temp_c
            self._state.ambient_humidity_pct = humidity_pct
            self._state.ambient_pressure_hpa = pressure_hpa
            self._state.density_altitude_ft = density_altitude_ft
            self._state.dew_point_c = dew_point_c
            self._state.ambient_available = True

    def update_timing(
        self,
        lap_count: int = 0,
        current_sector: int = 0,
        sector_count: int = 0,
        current_lap_time_ms: int = 0,
        last_sector_time_ms: int = 0,
        delta_ms: int = 0,
        predicted_lap_ms: int = 0,
        theoretical_best_ms: int = 0,
        track_name: str = "",
        timing_mode: str = "",
        lap_distance_m: float = 0.0,
    ) -> None:
        """Called from TimingManager with race analysis timing data."""
        with self._lock:
            self._state.lap_count = lap_count
            self._state.current_sector = current_sector
            self._state.sector_count = sector_count
            self._state.current_lap_time_ms = current_lap_time_ms
            self._state.last_sector_time_ms = last_sector_time_ms
            self._state.delta_ms = delta_ms
            self._state.predicted_lap_ms = predicted_lap_ms
            self._state.theoretical_best_ms = theoretical_best_ms
            self._state.track_name = track_name
            self._state.timing_mode = timing_mode
            self._state.lap_distance_m = lap_distance_m
        self.state_changed.emit()

    def set_disconnected(self) -> None:
        """Mark CAN bus as disconnected."""
        with self._lock:
            self._state.can_connected = False
        self.state_changed.emit()
