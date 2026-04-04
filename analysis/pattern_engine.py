"""KiSTI — Pattern Detection Engine

Lightweight, CPU-bound analysis running on a 1Hz cycle alongside the sensor pipeline.
No GPU. No LLM. Pure numpy + DuckDB SQL.

Reads recent telemetry from DuckDB, detects thermal/drivetrain/dynamics patterns,
and records them back to the patterns table.

Architecture:
    PatternEngine is wired into the Qt event loop via QTimer (1s interval).
    Each tick, it queries the last N seconds of data from DuckDB, runs all
    pattern detectors, and stores any findings.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import QObject, QTimer, Signal

log = logging.getLogger("kisti.analysis")

# Analysis window: how far back to look (seconds)
WINDOW_SECONDS = 30
# Minimum rows needed before running analysis
MIN_ROWS = 5


@dataclass
class DetectedPattern:
    """A pattern detected by the engine."""
    pattern_type: str
    severity: str  # info, advisory, warning, critical
    value: float
    context: dict


class PatternEngine(QObject):
    """CPU-only pattern detection engine running at 1Hz.

    Usage:
        engine = PatternEngine(db_store, session_id_getter)
        engine.start()  # begins 1Hz analysis cycle
        engine.stop()
    """

    pattern_detected = Signal(object)  # emits DetectedPattern

    def __init__(
        self,
        db_store,
        get_session_id,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._db = db_store
        self._get_sid = get_session_id  # callable returning current session_id or None
        self._timer = QTimer(self)
        self._timer.setInterval(1000)  # 1Hz
        self._timer.timeout.connect(self._tick)
        self._last_emit: dict[str, float] = {}  # debounce per pattern type

    def start(self) -> None:
        self._timer.start()
        log.info("Pattern engine started (1Hz analysis cycle)")

    def stop(self) -> None:
        self._timer.stop()
        log.info("Pattern engine stopped")

    def _tick(self) -> None:
        sid = self._get_sid()
        if not sid:
            return
        try:
            self._run_thermal_patterns(sid)
            self._run_drivetrain_patterns(sid)
            self._run_dynamics_patterns(sid)
        except Exception as exc:
            log.debug("Pattern tick error: %s", exc)

    # -----------------------------------------------------------------
    # Thermal patterns
    # -----------------------------------------------------------------

    def _run_thermal_patterns(self, sid: str) -> None:
        """Detect thermal patterns from FLIR + ambient data."""
        conn = self._db._conn

        # Ice risk delta trending toward zero
        rows = conn.execute(
            "SELECT road_temp_center, f.timestamp "
            "FROM flir_readings f "
            "WHERE f.session_id = ? "
            "ORDER BY f.timestamp DESC LIMIT ?",
            [sid, WINDOW_SECONDS * 3],  # ~3Hz * window
        ).fetchall()

        if len(rows) < MIN_ROWS:
            return

        # Get latest ambient dew point
        ambient = conn.execute(
            "SELECT dew_point_c FROM ambient_conditions "
            "ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
        if not ambient or ambient[0] is None:
            return

        dew_point = ambient[0]
        road_temps = [r[0] for r in rows if r[0] is not None]
        if not road_temps:
            return

        # Current delta
        current_delta = road_temps[0] - dew_point

        # Ice risk: delta < 1C
        if 0 < current_delta < 1.0:
            self._emit_pattern(sid, "ice_risk_imminent", "critical", current_delta, {
                "road_temp": road_temps[0], "dew_point": dew_point,
            })
        elif 1.0 <= current_delta <= 3.0:
            # Check if trending down
            if len(road_temps) >= 10:
                older = sum(road_temps[-5:]) / 5
                newer = sum(road_temps[:5]) / 5
                if newer < older - 0.5:  # dropping by > 0.5C
                    self._emit_pattern(sid, "ice_risk_trending", "warning", current_delta, {
                        "road_temp": road_temps[0], "dew_point": dew_point,
                        "trend": "decreasing",
                    })

        # L/C/R variance (shaded sections, wet patches)
        lcr_rows = conn.execute(
            "SELECT road_temp_left, road_temp_center, road_temp_right "
            "FROM flir_readings WHERE session_id = ? "
            "ORDER BY timestamp DESC LIMIT 10",
            [sid],
        ).fetchall()
        if len(lcr_rows) >= 5:
            variances = []
            for l, c, r in lcr_rows:
                if l is not None and c is not None and r is not None:
                    avg = (l + c + r) / 3
                    var = ((l - avg) ** 2 + (c - avg) ** 2 + (r - avg) ** 2) / 3
                    variances.append(var)
            if variances:
                avg_var = sum(variances) / len(variances)
                if avg_var > 4.0:  # > 2C spread between zones
                    self._emit_pattern(sid, "road_temp_variance", "advisory", avg_var, {
                        "description": "Significant temperature variation across road zones",
                    })

    # -----------------------------------------------------------------
    # Drivetrain patterns
    # -----------------------------------------------------------------

    def _run_drivetrain_patterns(self, sid: str) -> None:
        """Detect drivetrain patterns from telemetry + knock events."""
        conn = self._db._conn

        # Knock clustering: 3+ events in last 10 seconds
        knock_count = conn.execute(
            "SELECT COUNT(*) FROM knock_events "
            "WHERE session_id = ? AND timestamp > (NOW() - INTERVAL '10 seconds')",
            [sid],
        ).fetchone()[0]

        if knock_count >= 3:
            # Get RPM/boost distribution of recent knocks
            knock_rows = conn.execute(
                "SELECT rpm, boost_psi, gear, iam FROM knock_events "
                "WHERE session_id = ? "
                "ORDER BY timestamp DESC LIMIT 10",
                [sid],
            ).fetchall()
            if knock_rows:
                avg_rpm = sum(r[0] for r in knock_rows) / len(knock_rows)
                avg_boost = sum(r[1] for r in knock_rows) / len(knock_rows)
                self._emit_pattern(sid, "knock_burst", "warning", knock_count, {
                    "avg_rpm": avg_rpm, "avg_boost_psi": avg_boost,
                    "gear": knock_rows[0][2], "iam": knock_rows[0][3],
                })

        # IAM decay over session
        iam_rows = conn.execute(
            "SELECT iam FROM knock_events WHERE session_id = ? ORDER BY timestamp",
            [sid],
        ).fetchall()
        if len(iam_rows) >= 5:
            first_iam = sum(r[0] for r in iam_rows[:3]) / 3
            last_iam = sum(r[0] for r in iam_rows[-3:]) / 3
            if first_iam > 0 and last_iam < first_iam - 0.05:
                self._emit_pattern(sid, "iam_decay", "advisory", last_iam, {
                    "start_iam": first_iam, "current_iam": last_iam,
                    "decay": first_iam - last_iam,
                })
            if last_iam < 0.9:
                self._emit_pattern(sid, "iam_low", "warning", last_iam, {
                    "threshold": 0.9,
                })

        # AFR excursion under load (boost > 5 PSI)
        afr_rows = conn.execute(
            "SELECT lambda_1, map_kpa, rpm FROM telemetry "
            "WHERE session_id = ? AND map_kpa > 135 "  # ~5 PSI boost
            "ORDER BY timestamp DESC LIMIT 50",
            [sid],
        ).fetchall()
        if len(afr_rows) >= 10:
            from data.build_record import BASELINES
            target_low = BASELINES.afr_boost_gas_low  # 11.0
            target_high = BASELINES.afr_boost_gas_high  # 11.8
            lean_count = 0
            for lam, mkpa, rpm in afr_rows:
                if lam and lam > 0:
                    afr = lam * 14.7
                    if afr > target_high + 0.5:  # significantly lean
                        lean_count += 1
            if lean_count > len(afr_rows) * 0.3:  # >30% of samples lean
                self._emit_pattern(sid, "afr_lean_under_boost", "warning",
                                   lean_count / len(afr_rows), {
                    "lean_samples": lean_count, "total_samples": len(afr_rows),
                })

    # -----------------------------------------------------------------
    # Dynamics patterns
    # -----------------------------------------------------------------

    def _run_dynamics_patterns(self, sid: str) -> None:
        """Detect dynamics patterns from wheel speeds and ABS/VDC."""
        conn = self._db._conn

        # Wheel speed spread
        ws_rows = conn.execute(
            "SELECT wheel_fl, wheel_fr, wheel_rl, wheel_rr FROM telemetry "
            "WHERE session_id = ? "
            "ORDER BY timestamp DESC LIMIT 50",
            [sid],
        ).fetchall()

        if len(ws_rows) >= 10:
            high_spread_count = 0
            for fl, fr, rl, rr in ws_rows:
                if all(v is not None for v in (fl, fr, rl, rr)):
                    spread = max(abs(fl - fr), abs(rl - rr))
                    if spread > 5.0:  # > 5 km/h spread
                        high_spread_count += 1
            if high_spread_count > len(ws_rows) * 0.2:  # >20% of samples
                self._emit_pattern(sid, "wheel_speed_spread_high", "advisory",
                                   high_spread_count / len(ws_rows), {
                    "high_spread_samples": high_spread_count,
                    "total_samples": len(ws_rows),
                })

    # -----------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------

    def _emit_pattern(self, sid: str, ptype: str, severity: str,
                      value: float, context: dict) -> None:
        """Emit and record a pattern, with 30-second debounce per type."""
        now = time.monotonic()
        if ptype in self._last_emit and now - self._last_emit[ptype] < 30:
            return
        self._last_emit[ptype] = now

        pattern = DetectedPattern(ptype, severity, value, context)
        self._db.record_pattern(sid, ptype, severity, value, context)
        self.pattern_detected.emit(pattern)
        log.info("Pattern: %s [%s] value=%.2f", ptype, severity, value)
