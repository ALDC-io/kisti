"""KiSTI - Deterministic Alert Engine (Tier 1)

No LLM required. Evaluates telemetry thresholds and generates alerts.
Alerts are routed through the mode manager for voice/LED/buzzer output.

Alert severity levels:
  - info: Engine Ready, warm-up status
  - advisory: Fuel Low, minor concerns
  - warning: Cooldown Required, Oil Temp High, Overtemp
  - critical: Oil Pressure Low, Fuel Pressure Low (immediate action)
"""

from __future__ import annotations

import logging
import math
import time
from collections import Counter
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional

from PySide6.QtCore import QObject, QTimer, Signal

from data.build_record import BASELINES
from model.vehicle_state import DiffState, DiffStateBridge, SIDriveMode, SurfaceState, WarmUpState

log = logging.getLogger("kisti.alerts")


class AlertSeverity(IntEnum):
    """Alert severity levels, ordered by escalation."""
    INFO = 0
    ADVISORY = 1
    WARNING = 2
    CRITICAL = 3

    @property
    def label(self) -> str:
        return self.name.lower()


@dataclass
class Alert:
    """A single alert instance."""
    alert_type: str            # e.g., "oil_low", "overtemp"
    severity: AlertSeverity
    message: str               # Human-readable message for voice/display
    short_message: str         # Short version for Sport mode
    timestamp: float = field(default_factory=time.monotonic)
    acknowledged: bool = False
    value: Optional[float] = None  # The triggering sensor value


# ---------------------------------------------------------------------------
# Threshold definitions — sourced from BaselineTargets (data/build_record.py)
# ---------------------------------------------------------------------------

# Oil Pressure (PSI) — from IAG 750 build spec
OIL_PRESS_WARNING_PSI = BASELINES.oil_idle_warm_high   # 25.0 PSI
OIL_PRESS_CRITICAL_PSI = BASELINES.oil_idle_warm_low   # 15.0 PSI

# Oil Temperature (°C) — no baseline target; conservative limit for EJ257
OIL_TEMP_WARNING_C = 130.0

# Coolant Temperature (°C) — from build spec (with cyl 4 cooling mod)
COOLANT_TEMP_WARNING_C = BASELINES.coolant_alert       # 105.0°C
COOLANT_TEMP_CRITICAL_C = 115.0                        # 10°C above alert

# Fuel Pressure (kPa) — derived from build spec (43.5 PSI base = ~300 kPa)
# Warning at ~83% of base, critical at ~67% of base
_FUEL_BASE_KPA = BASELINES.fuel_base_psi * 6.89476     # PSI → kPa
FUEL_PRESS_WARNING_KPA = _FUEL_BASE_KPA * 0.83         # ~249 kPa
FUEL_PRESS_CRITICAL_KPA = _FUEL_BASE_KPA * 0.67        # ~201 kPa

# Battery Voltage
BATTERY_LOW_V = 12.5

# Cooldown detection: high oil temp + engine off/idle
COOLDOWN_OIL_THRESHOLD_C = 110.0
COOLDOWN_RPM_THRESHOLD = 1200.0

# Minimum RPM to consider engine running (for alert suppression)
ENGINE_RUNNING_RPM = 500.0

# G-force thresholds (combined lateral + longitudinal)
HIGH_G_ADVISORY = 1.0   # g — spirited driving
HIGH_G_WARNING = 1.3    # g — aggressive, potential loss of control

# GPS staleness
GPS_STALE_TIMEOUT_S = 2.0  # seconds without GPS frame

# Debounce: each alert type fires ONCE per session via voice.
# Screen + Link ECU dash handle persistent display. Voice announces once.
ALERT_DEBOUNCE_S = 0.0  # disabled — _fired_types set handles once-per-session


class AlertEngine(QObject):
    """Deterministic Tier 1 alert engine.

    Evaluates telemetry at 2 Hz and emits alerts when thresholds are crossed.
    No LLM involved — pure threshold logic.

    Signals:
        alert_fired(Alert): New alert generated
    """

    alert_fired = Signal(object)       # Alert dataclass — all alerts (for DuckDB logging)
    voice_alert = Signal(object)       # Alert — safety-critical only (for TTS)
    display_alert = Signal(object)     # Alert — display-only (ABS/VDC, ambient, etc)

    # Voice-eligible alert types — only these produce voice output while driving.
    # Everything else is logged silently or displayed without voice.
    VOICE_ALERT_TYPES = frozenset({
        "oil_pressure_low",
        "oil_pressure_critical",
        "coolant_critical",       # safety: overtemp requires immediate action
        "fuel_pressure_critical", # safety: fuel starvation
        "ice_risk_imminent",      # safety: road temp approaching dew point
        "grip_low_grip",          # safety: LOW_GRIP entry only (RWR/TCAS principle:
                                  # most critical transition needs audio, not just visual)
        # grip_wet, grip_cold, grip_cleared are visual-only — no voice chatter.
    })

    # Display-only alert types (shown on screen, no voice)
    DISPLAY_ALERT_TYPES = frozenset({
        "grip_wet", "grip_cold",
        "high_g_advisory", "high_g_warning",
    })

    def __init__(
        self,
        bridge: DiffStateBridge,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._bridge = bridge

        # Track last alert time per type to debounce
        self._last_alert: dict[str, float] = {}

        # Track warm-up state for Engine Ready alert
        self._engine_ready_announced = False
        self._warmup_announced = False

        # Track previous ambient state for delta detection
        self._prev_ambient_pressure: float = 0.0
        self._prev_ambient_temp: float = 0.0
        self._prev_ambient_humidity: float = 0.0
        self._ambient_baseline_set: bool = False

        # SI Drive mode for alert suppression
        self._si_drive_mode: SIDriveMode = SIDriveMode.INTELLIGENT

        # GPS live tracking — dedicated attribute (not in _last_alert dict)
        self._gps_was_live: bool = False

        # Ice risk: fire once, reset only when conditions clear (delta > 3°C)
        self._ice_risk_active: bool = False

        # Once-per-session: each alert type fires voice ONCE then never again
        self._fired_types: set[str] = set()

        # Smart grip: rolling 10s window (2Hz × 20 = 20 samples)
        # Announces when >50% of window shifts to new dominant state.
        # 10s = responsive enough for mountain passes, filters single-frame noise.
        from collections import deque
        self._surface_history: deque = deque(maxlen=20)
        self._announced_grip: Optional[SurfaceState] = None

        # Check timer (2 Hz)
        self._timer = QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._evaluate)

    def start(self) -> None:
        """Start alert evaluation."""
        self._timer.start()
        log.info("Alert engine started (2 Hz evaluation)")

    def stop(self) -> None:
        self._timer.stop()

    def set_si_drive_mode(self, mode: int) -> None:
        """Update SI Drive mode for alert suppression.

        Suppression matrix:
          Intelligent: all severities fire
          Sport: INFO suppressed
          Sport Sharp: INFO + ADVISORY suppressed
        """
        try:
            self._si_drive_mode = SIDriveMode(mode)
        except ValueError:
            return
        log.info("Alert engine mode: %s", self._si_drive_mode.label)

    def _evaluate(self) -> None:
        """Evaluate all alert thresholds against current telemetry."""
        state = self._bridge.snapshot()

        # Sensor-independent checks — run even without ECU
        self._check_gps_stale(state)
        self._check_high_g(state)
        self._check_ambient_change(state)
        self._check_ice_risk(state)
        self._check_grip(state)

        # Engine-dependent checks — skip if no ECU data
        if state.is_engine_stale():
            return
        if state.rpm < ENGINE_RUNNING_RPM:
            return

        self._check_oil_pressure(state)
        self._check_oil_temp(state)
        self._check_coolant_temp(state)
        self._check_fuel_pressure(state)
        self._check_battery(state)
        self._check_cooldown_needed(state)
        self._check_warmup_state(state)

    def _check_oil_pressure(self, state: DiffState) -> None:
        """Oil pressure alerts. Checks dedicated 150 PSI sensor (0x6B1)
        first, falls back to Generic Dash oil pressure (0x361)."""
        psi = state.oil_psi
        if psi <= 0 and state.oil_pressure_kpa > 0:
            psi = state.oil_pressure_kpa * 0.145038  # kPa → PSI
        if psi <= 0:
            return  # No data from either source

        if psi < OIL_PRESS_CRITICAL_PSI:
            self._fire(Alert(
                alert_type="oil_pressure_critical",
                severity=AlertSeverity.CRITICAL,
                message=f"Oil pressure critical: {psi:.0f} PSI. Shut down immediately.",
                short_message=f"Oil pressure {psi:.0f} PSI!",
                value=psi,
            ))
        elif psi < OIL_PRESS_WARNING_PSI:
            self._fire(Alert(
                alert_type="oil_pressure_low",
                severity=AlertSeverity.WARNING,
                message=f"Oil pressure low: {psi:.0f} PSI. Monitor closely.",
                short_message=f"Oil low {psi:.0f} PSI",
                value=psi,
            ))

    def _check_oil_temp(self, state: DiffState) -> None:
        """Oil temperature alerts."""
        temp = state.oil_temp_c
        if temp <= 0:
            return

        if temp > OIL_TEMP_WARNING_C:
            self._fire(Alert(
                alert_type="oil_temp_high",
                severity=AlertSeverity.WARNING,
                message=f"Oil temperature high: {temp:.0f} degrees C. Consider backing off.",
                short_message=f"Oil temp {temp:.0f}°C",
                value=temp,
            ))

    def _check_coolant_temp(self, state: DiffState) -> None:
        """Coolant temperature alerts."""
        temp = state.coolant_temp
        if temp <= 0:
            return

        if temp > COOLANT_TEMP_CRITICAL_C:
            self._fire(Alert(
                alert_type="coolant_critical",
                severity=AlertSeverity.CRITICAL,
                message=f"Coolant overtemp: {temp:.0f} degrees C! Pull over safely.",
                short_message=f"Overtemp {temp:.0f}°C!",
                value=temp,
            ))
        elif temp > COOLANT_TEMP_WARNING_C:
            self._fire(Alert(
                alert_type="coolant_high",
                severity=AlertSeverity.WARNING,
                message=f"Coolant temperature elevated: {temp:.0f} degrees C.",
                short_message=f"Coolant {temp:.0f}°C",
                value=temp,
            ))

    def _check_fuel_pressure(self, state: DiffState) -> None:
        """Fuel pressure alerts — critical under boost."""
        fp = state.fuel_pressure_kpa
        if fp <= 0:
            return

        if fp < FUEL_PRESS_CRITICAL_KPA:
            self._fire(Alert(
                alert_type="fuel_pressure_critical",
                severity=AlertSeverity.CRITICAL,
                message=f"Fuel pressure critical: {fp:.0f} kPa. Lean condition risk.",
                short_message=f"Fuel press {fp:.0f} kPa!",
                value=fp,
            ))
        elif fp < FUEL_PRESS_WARNING_KPA:
            self._fire(Alert(
                alert_type="fuel_pressure_low",
                severity=AlertSeverity.WARNING,
                message=f"Fuel pressure low: {fp:.0f} kPa. Monitor under boost.",
                short_message=f"Fuel press {fp:.0f} kPa",
                value=fp,
            ))

    def _check_battery(self, state: DiffState) -> None:
        """Battery voltage alert."""
        v = state.battery_v
        if v <= 0:
            return

        if v < BATTERY_LOW_V:
            self._fire(Alert(
                alert_type="battery_low",
                severity=AlertSeverity.ADVISORY,
                message=f"Battery voltage low: {v:.1f}V. Check alternator.",
                short_message=f"Battery {v:.1f}V",
                value=v,
            ))

    def _check_cooldown_needed(self, state: DiffState) -> None:
        """Cooldown advisory after hard driving."""
        if state.oil_temp_c > COOLDOWN_OIL_THRESHOLD_C and state.rpm < COOLDOWN_RPM_THRESHOLD:
            self._fire(Alert(
                alert_type="cooldown_required",
                severity=AlertSeverity.WARNING,
                message="Cooldown required. Let the engine idle before shutdown.",
                short_message="Cooldown required",
                value=state.oil_temp_c,
            ))

    def _check_warmup_state(self, state: DiffState) -> None:
        """Warm-up state announcements."""
        if state.warmup_state == WarmUpState.COLD and not self._warmup_announced:
            self._warmup_announced = True
            self._fire(Alert(
                alert_type="warmup_engaged",
                severity=AlertSeverity.INFO,
                message="Warm-up sequence engaged. Good morning.",
                short_message="Warming up",
            ))

        if state.warmup_state == WarmUpState.READY and not self._engine_ready_announced:
            self._engine_ready_announced = True
            self._fire(Alert(
                alert_type="engine_ready",
                severity=AlertSeverity.INFO,
                message="Engine ready. Oil and coolant at operating temperature.",
                short_message="Engine ready",
            ))

    def _check_grip(self, state: DiffState) -> None:
        """Smart grip: rolling 10s window (20 samples at 2Hz), 50% dominance.

        Tracks surface state at 2Hz. When >50% of the window is a new
        dominant state, announces the transition once. Brief excursions
        (tunnels, bridges) are filtered out. Bypasses _fire()/_fired_types
        since it manages its own lifecycle via _announced_grip.

        Note: grip_low_grip is no longer voice-routed — screen visual
        (zone bars + edge glow) is the primary channel. This method still
        emits alert_fired for DuckDB logging.
        """
        self._surface_history.append(state.surface_state)

        if len(self._surface_history) < 10:  # need 5s of data minimum
            return

        counts = Counter(self._surface_history)
        dominant, count = counts.most_common(1)[0]
        pct = count / len(self._surface_history)

        if pct < 0.5:
            return  # no clear dominant state — mixed conditions

        if dominant == self._announced_grip:
            return  # already announced this condition

        prev = self._announced_grip
        self._announced_grip = dominant

        if dominant == SurfaceState.LOW_GRIP:
            alert = Alert(
                alert_type="grip_low_grip",
                severity=AlertSeverity.ADVISORY,
                message="Low grip.",
                short_message="LOW GRIP",
            )
            log.info("GRIP [%.0f%%] → LOW GRIP", pct * 100)
            self.alert_fired.emit(alert)
            if alert.alert_type in self.VOICE_ALERT_TYPES:
                self.voice_alert.emit(alert)
        elif dominant in (SurfaceState.WET, SurfaceState.COLD):
            alert = Alert(
                alert_type=f"grip_{dominant.label.lower()}",
                severity=AlertSeverity.ADVISORY,
                message=f"{dominant.label} surface.",
                short_message=f"Grip: {dominant.label}",
            )
            log.info("GRIP [%.0f%%] → %s", pct * 100, dominant.label)
            self.alert_fired.emit(alert)
        elif dominant == SurfaceState.DRY and prev in (SurfaceState.LOW_GRIP, SurfaceState.WET, SurfaceState.COLD):
            alert = Alert(
                alert_type="grip_cleared",
                severity=AlertSeverity.INFO,
                message="Grip restored.",
                short_message="DRY",
            )
            log.info("GRIP [%.0f%%] → DRY (cleared)", pct * 100)
            self.alert_fired.emit(alert)

    def _check_high_g(self, state: DiffState) -> None:
        """High G-force alert from IMU accelerometer."""
        if state.is_imu_stale():
            return
        combined_g = math.sqrt(state.imu_accel_x ** 2 + state.imu_accel_y ** 2)
        if combined_g >= HIGH_G_WARNING:
            self._fire(Alert(
                alert_type="high_g_warning",
                severity=AlertSeverity.WARNING,
                message=f"High G-force: {combined_g:.1f}g. Approaching grip limit.",
                short_message=f"G: {combined_g:.1f}g",
                value=combined_g,
            ))
        elif combined_g >= HIGH_G_ADVISORY:
            self._fire(Alert(
                alert_type="high_g_advisory",
                severity=AlertSeverity.ADVISORY,
                message=f"G-force at {combined_g:.1f}g. Spirited driving detected.",
                short_message=f"G: {combined_g:.1f}g",
                value=combined_g,
            ))

    def _check_gps_stale(self, state: DiffState) -> None:
        """GPS signal loss alert — fires on transition from live to stale."""
        is_stale = state.is_gps_stale(timeout=GPS_STALE_TIMEOUT_S)

        if self._gps_was_live and is_stale:
            self._fire(Alert(
                alert_type="gps_signal_lost",
                severity=AlertSeverity.WARNING,
                message="GPS signal lost. Position tracking unavailable.",
                short_message="GPS lost",
            ))
        elif not is_stale and not self._gps_was_live:
            self._fire(Alert(
                alert_type="gps_signal_acquired",
                severity=AlertSeverity.INFO,
                message="GPS signal acquired. Tracking position.",
                short_message="GPS lock",
            ))

        self._gps_was_live = not is_stale

    def _check_ice_risk(self, state: DiffState) -> None:
        """Ice risk alert from FLIR road temp vs dew point.

        Fires ONCE when road temp enters the danger zone (within 1°C of dew
        point). Only re-fires after conditions clear (delta > 3°C) and
        return to danger. No repeated alerts while driving in sustained cold.
        """
        if not state.ambient_available:
            return
        road_temp = state.road_temp_center
        if road_temp == 0.0 and state.road_temp_left == 0.0:
            return  # no FLIR data
        dew_point = state.dew_point_c
        delta = road_temp - dew_point

        if 0 < delta < 1.0:
            if not self._ice_risk_active:
                self._ice_risk_active = True
                self._fire(Alert(
                    alert_type="ice_risk_imminent",
                    severity=AlertSeverity.CRITICAL,
                    message="Reduce speed. Ice risk.",
                    short_message=f"ICE RISK {delta:.1f}°C",
                    value=delta,
                ))
        elif delta > 3.0:
            # Conditions cleared — allow re-fire on next entry
            self._ice_risk_active = False

    def _check_ambient_change(self, state: DiffState) -> None:
        """Ambient weather change alerts — runs without ECU."""
        if not state.ambient_available:
            return

        # Set baseline on first reading
        if not self._ambient_baseline_set:
            self._prev_ambient_pressure = state.ambient_pressure_hpa
            self._prev_ambient_temp = state.ambient_temp_c
            self._prev_ambient_humidity = state.ambient_humidity_pct
            self._ambient_baseline_set = True
            return

        # Pressure change — weather system movement
        p_delta = state.ambient_pressure_hpa - self._prev_ambient_pressure
        if abs(p_delta) >= 5.0:
            if p_delta < 0:
                self._fire(Alert(
                    alert_type="pressure_falling",
                    severity=AlertSeverity.ADVISORY,
                    message=f"Barometric pressure dropping: {p_delta:+.1f} hPa. Weather changing.",
                    short_message=f"Pressure {p_delta:+.1f} hPa",
                    value=state.ambient_pressure_hpa,
                ))
            else:
                self._fire(Alert(
                    alert_type="pressure_rising",
                    severity=AlertSeverity.INFO,
                    message=f"Barometric pressure rising: {p_delta:+.1f} hPa. Conditions stabilising.",
                    short_message=f"Pressure {p_delta:+.1f} hPa",
                    value=state.ambient_pressure_hpa,
                ))
            self._prev_ambient_pressure = state.ambient_pressure_hpa

        # Temperature change
        t_delta = state.ambient_temp_c - self._prev_ambient_temp
        if abs(t_delta) >= 3.0:
            if t_delta < 0:
                self._fire(Alert(
                    alert_type="temp_dropping",
                    severity=AlertSeverity.ADVISORY,
                    message=f"Temperature dropped {abs(t_delta):.1f} degrees. Grip may decrease.",
                    short_message=f"Temp {t_delta:+.1f}°C",
                    value=state.ambient_temp_c,
                ))
            else:
                self._fire(Alert(
                    alert_type="temp_rising",
                    severity=AlertSeverity.INFO,
                    message=f"Temperature up {t_delta:.1f} degrees. Conditions improving.",
                    short_message=f"Temp {t_delta:+.1f}°C",
                    value=state.ambient_temp_c,
                ))
            self._prev_ambient_temp = state.ambient_temp_c

        # Humidity change
        h_delta = state.ambient_humidity_pct - self._prev_ambient_humidity
        if abs(h_delta) >= 15.0:
            if h_delta > 0:
                self._fire(Alert(
                    alert_type="humidity_rising",
                    severity=AlertSeverity.ADVISORY,
                    message=f"Humidity up {h_delta:.0f} percent. Condensation risk increasing.",
                    short_message=f"Humidity {h_delta:+.0f}%",
                    value=state.ambient_humidity_pct,
                ))
            else:
                self._fire(Alert(
                    alert_type="humidity_dropping",
                    severity=AlertSeverity.INFO,
                    message=f"Humidity down {abs(h_delta):.0f} percent. Drier conditions.",
                    short_message=f"Humidity {h_delta:+.0f}%",
                    value=state.ambient_humidity_pct,
                ))
            self._prev_ambient_humidity = state.ambient_humidity_pct

    def _fire(self, alert: Alert) -> None:
        """Fire an alert if not suppressed by mode. Each type fires once per session."""
        # Mode-aware suppression
        if self._si_drive_mode == SIDriveMode.SPORT_SHARP:
            if alert.severity < AlertSeverity.WARNING:
                return
        elif self._si_drive_mode == SIDriveMode.SPORT:
            if alert.severity == AlertSeverity.INFO:
                return

        # Once per session — voice announces once, screen/Link ECU handle persistence
        if alert.alert_type in self._fired_types:
            return
        self._fired_types.add(alert.alert_type)

        self._last_alert[alert.alert_type] = time.monotonic()
        log.info("ALERT [%s] %s: %s", alert.severity.label, alert.alert_type, alert.short_message)
        self.alert_fired.emit(alert)

        # Route: voice for safety-critical, display for visual-only, silent for the rest
        if alert.alert_type in self.VOICE_ALERT_TYPES:
            self.voice_alert.emit(alert)
        elif alert.alert_type in self.DISPLAY_ALERT_TYPES:
            self.display_alert.emit(alert)
