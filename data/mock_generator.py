"""KiSTI - Mock Data Generator

Generates plausible telemetry data at 10Hz (temps) and 1Hz (GPS/session).
Replace this class with CAN/IR/GPS adapter for real sensors.
"""

import math
import random
import time
import uuid

from PySide6.QtCore import QObject, QTimer, Signal

from data.models import (
    CornerData, GPSData, SessionData, SystemState,
    VehicleState, KistiFinding, OilPressureData, FrontSensorSuite,
)
from config import (
    FAST_TICK_MS, SLOW_TICK_MS,
    TIRE_TEMP_BASELINE, BRAKE_TEMP_BASELINE, LAP_DURATION_S,
    OIL_PSI_BASELINE, OIL_TEMP_BASELINE,
)

# A simple closed loop route (Laguna Seca inspired, normalized 0-1 coords)
_ROUTE_POINTS = [
    (0.15, 0.80), (0.25, 0.70), (0.40, 0.55), (0.55, 0.40),
    (0.65, 0.30), (0.75, 0.25), (0.85, 0.30), (0.90, 0.45),
    (0.85, 0.60), (0.75, 0.70), (0.60, 0.75), (0.45, 0.80),
    (0.30, 0.85), (0.15, 0.80),
]

_FINDING_TEMPLATES = [
    ("FL tire overheating", "Front-left tire exceeding optimal range. Consider adjusting camber.", "warning", ["FL"]),
    ("Brake fade detected", "Rear brakes showing elevated temps. Plan for cooldown lap.", "critical", ["RL", "RR"]),
    ("Uneven tire wear", "Right-side tires running hotter than left. Check alignment.", "warning", ["FR", "RR"]),
    ("Optimal tire window", "All tires within optimal grip temperature range.", "info", ["FL", "FR", "RL", "RR"]),
    ("Hard braking zone", "Heavy braking into Turn 6 causing front brake spikes.", "warning", ["FL", "FR"]),
    ("Rear instability risk", "Rear tire temps diverging. Monitor oversteer tendency.", "critical", ["RL", "RR"]),
]


class MockDataGenerator(QObject):
    """Generates mock vehicle telemetry at configurable rates.

    Signals:
        data_updated(VehicleState): Emitted on every fast tick with current state.
    """

    data_updated = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = VehicleState()
        self._state.system.logging = True
        self._state.system.network = True
        self._state.system.gps_fix = True

        self._route_idx = 0.0
        self._start_time = time.monotonic()
        self._lap_start = time.monotonic()
        self._finding_timer = 0

        # Initialize temps with some variance
        for key in self._state.corners:
            c = self._state.corners[key]
            c.tire_temp_c = random.uniform(*TIRE_TEMP_BASELINE)
            c.brake_temp_c = random.uniform(*BRAKE_TEMP_BASELINE)
            c.trend = [c.tire_temp_c] * 30

        # Initialize oil pressure
        self._state.oil.psi = random.uniform(*OIL_PSI_BASELINE)
        self._state.oil.temp_c = random.uniform(*OIL_TEMP_BASELINE)
        self._state.oil.trend = [self._state.oil.psi] * 30

        # Initialize sensor suite (mock connected state)
        self._sensor_jitter_counter = 0

        self._generate_findings()

        self._fast_timer = QTimer(self)
        self._fast_timer.setInterval(FAST_TICK_MS)
        self._fast_timer.timeout.connect(self._fast_tick)

        self._slow_timer = QTimer(self)
        self._slow_timer.setInterval(SLOW_TICK_MS)
        self._slow_timer.timeout.connect(self._slow_tick)

    def start(self):
        self._fast_timer.start()
        self._slow_timer.start()

    def stop(self):
        self._fast_timer.stop()
        self._slow_timer.stop()

    def _fast_tick(self):
        """10Hz update: temperature random walk + position interpolation."""
        for key in self._state.corners:
            c = self._state.corners[key]
            # Random walk temps
            c.tire_temp_c += random.uniform(-2.0, 2.0)
            c.tire_temp_c = max(TIRE_TEMP_BASELINE[0] - 10,
                                min(TIRE_TEMP_BASELINE[1] + 15, c.tire_temp_c))
            c.brake_temp_c += random.uniform(-5.0, 5.0)
            c.brake_temp_c = max(BRAKE_TEMP_BASELINE[0] - 30,
                                 min(BRAKE_TEMP_BASELINE[1] + 50, c.brake_temp_c))
            # Tire wear: slow sawtooth cycle for demo
            # Degrades over ~5 min, then "pit stop" resets to fresh
            wear_rate = 0.000035
            if c.tire_temp_c > 105:
                wear_rate = 0.00008
            elif c.tire_temp_c > 95:
                wear_rate = 0.00005
            c.tire_wear_pct -= wear_rate
            if c.tire_wear_pct < 0.15:
                # Simulate pit stop - fresh tires
                c.tire_wear_pct = 1.0
            # Update trend
            c.trend.append(c.tire_temp_c)
            if len(c.trend) > 30:
                c.trend.pop(0)

        # Interpolate position along route
        n = len(_ROUTE_POINTS)
        idx_int = int(self._route_idx) % n
        idx_next = (idx_int + 1) % n
        frac = self._route_idx - int(self._route_idx)
        p0 = _ROUTE_POINTS[idx_int]
        p1 = _ROUTE_POINTS[idx_next]
        x = p0[0] + (p1[0] - p0[0]) * frac
        y = p0[1] + (p1[1] - p0[1]) * frac
        self._state.gps.lat = 36.57 + (y - 0.5) * 0.01
        self._state.gps.lon = -121.95 + (x - 0.5) * 0.01
        self._state.gps.speed_kph = 80 + random.uniform(-10, 30)
        self._state.gps.heading = math.degrees(
            math.atan2(p1[1] - p0[1], p1[0] - p0[0])
        )

        # Oil pressure random walk
        oil = self._state.oil
        oil.psi += random.uniform(-1.5, 1.5)
        oil.psi = max(OIL_PSI_BASELINE[0] - 15, min(OIL_PSI_BASELINE[1] + 10, oil.psi))
        oil.temp_c += random.uniform(-0.5, 0.5)
        oil.temp_c = max(OIL_TEMP_BASELINE[0] - 10, min(OIL_TEMP_BASELINE[1] + 15, oil.temp_c))
        oil.trend.append(oil.psi)
        if len(oil.trend) > 30:
            oil.trend.pop(0)

        # Sensor suite - jitter FPS slightly
        self._sensor_jitter_counter += 1
        if self._sensor_jitter_counter >= 5:
            self._sensor_jitter_counter = 0
            for cam in self._state.sensors.all_cameras():
                base_fps = {"Teledyne IR": 30.0, "LiDAR": 10.0, "RGB": 60.0, "Weather": 15.0}
                target = base_fps.get(cam.name, 30.0)
                cam.fps = target + random.uniform(-2.0, 2.0)
                cam.connected = random.random() > 0.02  # 2% chance of dropout

        # Advance route position (speed depends on mode)
        speed = 0.02 if self._state.session.mode == "STREET" else 0.05
        self._route_idx += speed
        if self._route_idx >= n:
            self._route_idx -= n

        self.data_updated.emit(self._state)

    def _slow_tick(self):
        """1Hz update: session time, lap counting, periodic findings refresh."""
        now = time.monotonic()
        self._state.session.session_time_s = now - self._start_time

        # Lap counting
        lap_elapsed = now - self._lap_start
        if lap_elapsed >= LAP_DURATION_S:
            lap_time = lap_elapsed
            self._state.session.lap_count += 1
            self._state.session.lap_times.append(lap_time)
            if self._state.session.best_lap == 0 or lap_time < self._state.session.best_lap:
                self._state.session.best_lap = lap_time
            self._lap_start = now

        # Refresh findings periodically
        self._finding_timer += 1
        if self._finding_timer >= 15:
            self._finding_timer = 0
            self._generate_findings()

    def _generate_findings(self):
        """Pick 2-4 random findings from templates."""
        count = random.randint(2, 4)
        selected = random.sample(_FINDING_TEMPLATES, count)
        self._state.findings = [
            KistiFinding(
                id=uuid.uuid4().hex[:8],
                title=t[0],
                detail=t[1],
                severity=t[2],
                related_corners=list(t[3]),
            )
            for t in selected
        ]
