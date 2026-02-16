"""KiSTI - Mock Radar Generator

Simulates Valentine One Gen2 radar detector output at 2Hz.
Generates realistic scenarios: quiet stretches, K-band door openers,
Ka-band threats, multi-bogey, laser hits, X-band.

Replace with real V1 BLE driver for production.
"""

import random
import time
import uuid

from PySide6.QtCore import QObject, QTimer, Signal

from data.models import RadarAlert, RadarState, RadarBand, AlertDirection
from config import (
    RADAR_TICK_MS, RADAR_BAND_X, RADAR_BAND_K, RADAR_BAND_Ka,
)


# Scenario definitions: (name, weight, generator_func_name)
# Weights control probability of scenario selection during quiet periods
_SCENARIO_WEIGHTS = {
    "quiet": 40,
    "k_door_opener": 20,
    "ka_threat": 15,
    "ka_rear": 8,
    "multi_bogey": 7,
    "laser_hit": 3,
    "x_band": 7,
}


class MockRadarGenerator(QObject):
    """Generates mock Valentine One Gen2 radar alerts.

    Signals:
        radar_updated(RadarState): Emitted at 2Hz with current radar state.
    """

    radar_updated = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._state = RadarState(connected=True)
        self._active_scenarios = []  # List of running scenario dicts
        self._quiet_remaining = 0    # Ticks of quiet time remaining
        self._tick_count = 0

        self._timer = QTimer(self)
        self._timer.setInterval(RADAR_TICK_MS)
        self._timer.timeout.connect(self._tick)

        # Start with a quiet period
        self._quiet_remaining = random.randint(20, 40)  # 10-20 seconds

    def start(self):
        self._timer.start()

    def stop(self):
        self._timer.stop()

    def _tick(self):
        """Called at 2Hz — update scenarios and emit state."""
        self._tick_count += 1
        now = time.monotonic()

        # If quiet, count down and maybe start a new scenario
        if self._quiet_remaining > 0 and not self._active_scenarios:
            self._quiet_remaining -= 1
            if self._quiet_remaining <= 0:
                self._start_random_scenario()
        elif not self._active_scenarios:
            # No active scenarios and no quiet timer — start quiet period
            self._quiet_remaining = random.randint(20, 40)

        # Tick all active scenarios
        finished = []
        alerts = []
        for scenario in self._active_scenarios:
            alert = self._tick_scenario(scenario)
            if alert:
                alerts.append(alert)
            if scenario.get("done"):
                finished.append(scenario)

        # Remove finished scenarios
        for s in finished:
            self._active_scenarios.remove(s)

        # If all scenarios finished, schedule quiet period
        if not self._active_scenarios and not self._quiet_remaining:
            self._quiet_remaining = random.randint(20, 40)

        # Build state
        self._state.active_alerts = alerts
        self._state.alert_count = len(alerts)
        self._state.last_update = now
        self._state.connected = True

        self.radar_updated.emit(self._state)

    def _start_random_scenario(self):
        """Pick a weighted random scenario and start it."""
        names = list(_SCENARIO_WEIGHTS.keys())
        weights = [_SCENARIO_WEIGHTS[n] for n in names]
        chosen = random.choices(names, weights=weights, k=1)[0]

        if chosen == "quiet":
            self._quiet_remaining = random.randint(20, 40)
            return

        scenario = self._create_scenario(chosen)
        if scenario:
            self._active_scenarios.append(scenario)

    def _create_scenario(self, name):
        """Create a scenario dict with initial parameters."""
        alert_id = uuid.uuid4().hex[:6]

        if name == "k_door_opener":
            return {
                "type": "k_door_opener",
                "id": alert_id,
                "band": RadarBand.K,
                "freq": random.uniform(*RADAR_BAND_K),
                "direction": AlertDirection.FRONT,
                "phase": "ramp_up",
                "signal": 0,
                "max_signal": random.randint(2, 4),
                "ticks": 0,
                "total_ticks": random.randint(12, 20),  # 6-10 seconds
                "done": False,
            }
        elif name == "ka_threat":
            return {
                "type": "ka_threat",
                "id": alert_id,
                "band": RadarBand.Ka,
                "freq": random.choice([34700, 35500, 33800]) + random.uniform(-50, 50),
                "direction": AlertDirection.FRONT,
                "phase": "ramp_up",
                "signal": 0,
                "max_signal": random.randint(6, 8),
                "ticks": 0,
                "total_ticks": random.randint(16, 30),  # 8-15 seconds
                "done": False,
            }
        elif name == "ka_rear":
            return {
                "type": "ka_rear",
                "id": alert_id,
                "band": RadarBand.Ka,
                "freq": random.choice([34700, 35500]) + random.uniform(-50, 50),
                "direction": AlertDirection.REAR,
                "phase": "ramp_up",
                "signal": 0,
                "max_signal": random.randint(5, 8),
                "ticks": 0,
                "total_ticks": random.randint(14, 24),
                "done": False,
            }
        elif name == "multi_bogey":
            # Start first alert, second will be added a few ticks later
            return {
                "type": "multi_bogey",
                "id": alert_id,
                "band": RadarBand.Ka,
                "freq": 34700 + random.uniform(-50, 50),
                "direction": AlertDirection.FRONT,
                "phase": "ramp_up",
                "signal": 0,
                "max_signal": random.randint(5, 7),
                "ticks": 0,
                "total_ticks": random.randint(20, 30),
                "second_id": uuid.uuid4().hex[:6],
                "second_freq": 35500 + random.uniform(-50, 50),
                "second_signal": 0,
                "second_started": False,
                "done": False,
            }
        elif name == "laser_hit":
            return {
                "type": "laser_hit",
                "id": alert_id,
                "band": RadarBand.LASER,
                "freq": 0,
                "direction": AlertDirection.FRONT,
                "phase": "instant",
                "signal": 8,
                "max_signal": 8,
                "ticks": 0,
                "total_ticks": random.randint(4, 8),  # 2-4 seconds (brief)
                "done": False,
            }
        elif name == "x_band":
            return {
                "type": "x_band",
                "id": alert_id,
                "band": RadarBand.X,
                "freq": random.uniform(*RADAR_BAND_X),
                "direction": AlertDirection.FRONT,
                "phase": "ramp_up",
                "signal": 0,
                "max_signal": random.randint(2, 4),
                "ticks": 0,
                "total_ticks": random.randint(10, 16),
                "done": False,
            }
        return None

    def _tick_scenario(self, scenario):
        """Advance a scenario by one tick and return an alert (or list for multi)."""
        scenario["ticks"] += 1
        t = scenario["ticks"]
        total = scenario["total_ticks"]
        max_sig = scenario["max_signal"]
        stype = scenario["type"]

        if stype == "laser_hit":
            # Laser: instant max, then done
            if t >= total:
                scenario["done"] = True
                return None
            return self._make_alert(scenario, 8)

        if stype == "multi_bogey":
            # Primary alert follows ramp_up_down pattern
            signal = self._ramp_up_down(t, total, max_sig)
            if t >= total:
                scenario["done"] = True
                return None
            # The multi_bogey returns the primary; the second alert is
            # handled by adding a second scenario after a delay.
            # For simplicity, embed both alerts by returning primary here.
            # The secondary is tracked within the same scenario dict.
            primary = self._make_alert(scenario, signal)

            # Start second bogey after 30% of total ticks
            if t > total * 0.3 and not scenario["second_started"]:
                scenario["second_started"] = True
                second = self._create_scenario("ka_threat")
                if second:
                    second["id"] = scenario["second_id"]
                    second["freq"] = scenario["second_freq"]
                    second["direction"] = AlertDirection.SIDE
                    self._active_scenarios.append(second)
            return primary

        # Standard ramp_up_down for other types
        signal = self._ramp_up_down(t, total, max_sig)

        # Add frequency jitter
        scenario["freq"] += random.uniform(-5, 5)

        if t >= total:
            scenario["done"] = True
            return None

        return self._make_alert(scenario, signal)

    def _ramp_up_down(self, tick, total, max_signal):
        """Signal envelope: ramp up first half, ramp down second half."""
        mid = total / 2
        if tick <= mid:
            # Ramp up
            frac = tick / mid
            signal = int(round(frac * max_signal))
        else:
            # Ramp down
            frac = (total - tick) / mid
            signal = int(round(frac * max_signal))
        return max(0, min(8, signal))

    def _make_alert(self, scenario, signal):
        """Build a RadarAlert from scenario state."""
        direction = scenario["direction"]
        front_sig = signal if direction != AlertDirection.REAR else max(0, signal - 3)
        rear_sig = signal if direction == AlertDirection.REAR else max(0, signal - 4)

        # Priority: Laser > Ka > K > X, scaled by signal strength
        band_priority = {
            RadarBand.LASER: 100,
            RadarBand.Ka: 50,
            RadarBand.K: 20,
            RadarBand.X: 10,
        }
        priority = band_priority.get(scenario["band"], 0) + signal * 5

        return RadarAlert(
            alert_id=scenario["id"],
            band=scenario["band"],
            frequency_mhz=scenario["freq"],
            front_signal=front_sig,
            rear_signal=rear_sig,
            direction=direction,
            priority=priority,
            timestamp=time.monotonic(),
        )
