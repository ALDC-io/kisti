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
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional

from PySide6.QtCore import QObject, QTimer, Signal

from model.vehicle_state import DiffState, DiffStateBridge, SIDriveMode, WarmUpState

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
# Threshold definitions
# ---------------------------------------------------------------------------

# Oil Pressure (PSI)
OIL_PRESS_WARNING_PSI = 25.0
OIL_PRESS_CRITICAL_PSI = 15.0

# Oil Temperature (°C)
OIL_TEMP_WARNING_C = 130.0

# Coolant Temperature (°C)
COOLANT_TEMP_WARNING_C = 105.0
COOLANT_TEMP_CRITICAL_C = 115.0

# Fuel Pressure (kPa) — low fuel pressure is dangerous under boost
FUEL_PRESS_WARNING_KPA = 250.0
FUEL_PRESS_CRITICAL_KPA = 200.0

# Battery Voltage
BATTERY_LOW_V = 12.5

# Cooldown detection: high oil temp + engine off/idle
COOLDOWN_OIL_THRESHOLD_C = 110.0
COOLDOWN_RPM_THRESHOLD = 1200.0

# Minimum RPM to consider engine running (for alert suppression)
ENGINE_RUNNING_RPM = 500.0

# Debounce: minimum time between repeated alerts of the same type (seconds)
ALERT_DEBOUNCE_S = 30.0


class AlertEngine(QObject):
    """Deterministic Tier 1 alert engine.

    Evaluates telemetry at 2 Hz and emits alerts when thresholds are crossed.
    No LLM involved — pure threshold logic.

    Signals:
        alert_fired(Alert): New alert generated
    """

    alert_fired = Signal(object)  # Alert dataclass

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

    def _evaluate(self) -> None:
        """Evaluate all alert thresholds against current telemetry."""
        state = self._bridge.snapshot()

        # Skip if no engine data
        if state.is_engine_stale():
            return

        # Skip if engine not running
        if state.rpm < ENGINE_RUNNING_RPM:
            return

        self._check_oil_pressure(state)
        self._check_oil_temp(state)
        self._check_coolant_temp(state)
        self._check_fuel_pressure(state)
        self._check_battery(state)
        self._check_cooldown_needed(state)
        self._check_warmup_state(state)
        self._check_grip(state)

    def _check_oil_pressure(self, state: DiffState) -> None:
        """Oil pressure alerts."""
        psi = state.oil_psi
        if psi <= 0:
            return  # No data

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
        """Grip/surface change advisory."""
        from model.vehicle_state import SurfaceState
        if state.surface_state in (SurfaceState.WET, SurfaceState.COLD, SurfaceState.LOW_GRIP):
            self._fire(Alert(
                alert_type=f"grip_{state.surface_state.label.lower().replace(' ', '_')}",
                severity=AlertSeverity.ADVISORY,
                message=f"Surface condition: {state.surface_state.label}. Grip reduced.",
                short_message=f"Grip: {state.surface_state.label}",
            ))

    def _fire(self, alert: Alert) -> None:
        """Fire an alert if not debounced."""
        now = time.monotonic()
        last = self._last_alert.get(alert.alert_type, 0.0)

        if now - last < ALERT_DEBOUNCE_S:
            return  # Debounced

        self._last_alert[alert.alert_type] = now
        log.info("ALERT [%s] %s: %s", alert.severity.label, alert.alert_type, alert.short_message)
        self.alert_fired.emit(alert)
