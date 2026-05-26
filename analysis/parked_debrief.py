"""KiSTI — Parked Analysis Mode (Claude Haiku Session Debrief)

When session ends and WiFi is available, generates a 3-point insight summary
from the session's DuckDB data via Claude Haiku.

This is the ONLY moment LLM runs. Not while driving.

Usage:
    debrief = ParkedDebrief(db_store, api_key)
    result = debrief.generate(session_id)
    # result is a dict with 'summary', 'insights', 'raw_response'
"""

from __future__ import annotations

import json
import logging
import urllib.request
from typing import Optional

log = logging.getLogger("kisti.analysis.debrief")

CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-haiku-4-5-20251001"
API_TIMEOUT_S = 15


class ParkedDebrief:
    """Generate post-session analysis via Claude Haiku."""

    def __init__(
        self,
        db_store,
        api_key: str = "",
        model: str = DEFAULT_MODEL,
    ) -> None:
        self._db = db_store
        self._api_key = api_key
        self._model = model

    def build_session_summary(self, session_id: str) -> dict:
        """Build a structured summary from DuckDB session data."""
        conn = self._db._conn
        summary = {}

        # Session metadata
        session = self._db.get_session(session_id)
        if session:
            summary["session_name"] = session.get("session_name", "")
            summary["route_tag"] = session.get("route_tag", "")
            summary["start_time"] = str(session.get("start_time", ""))
            summary["end_time"] = str(session.get("end_time", ""))

        # Telemetry stats
        telem_stats = conn.execute(
            "SELECT COUNT(*) as rows, "
            "MIN(rpm) as min_rpm, MAX(rpm) as max_rpm, AVG(rpm) as avg_rpm, "
            "MIN(coolant_temp) as min_coolant, MAX(coolant_temp) as max_coolant, "
            "MIN(oil_temp_c) as min_oil, MAX(oil_temp_c) as max_oil, "
            "MAX(speed_kph) as max_speed "
            "FROM telemetry WHERE session_id = ?",
            [session_id],
        ).fetchone()
        if telem_stats and telem_stats[0] > 0:
            summary["telemetry_rows"] = telem_stats[0]
            summary["rpm"] = {"min": telem_stats[1], "max": telem_stats[2], "avg": round(telem_stats[3] or 0, 0)}
            summary["coolant_c"] = {"min": telem_stats[4], "max": telem_stats[5]}
            summary["oil_temp_c"] = {"min": telem_stats[6], "max": telem_stats[7]}
            summary["max_speed_kph"] = telem_stats[8]

        # Knock events
        knock_stats = conn.execute(
            "SELECT COUNT(*) as total, SUM(knock_count_delta) as total_knocks, "
            "AVG(rpm) as avg_rpm, AVG(boost_psi) as avg_boost, "
            "MIN(iam) as min_iam, AVG(iam) as avg_iam "
            "FROM knock_events WHERE session_id = ?",
            [session_id],
        ).fetchone()
        if knock_stats and knock_stats[0] > 0:
            summary["knock_events"] = {
                "count": knock_stats[0],
                "total_knocks": knock_stats[1],
                "avg_rpm": round(knock_stats[2] or 0, 0),
                "avg_boost_psi": round(knock_stats[3] or 0, 1),
                "min_iam": knock_stats[4],
                "avg_iam": round(knock_stats[5] or 0, 3),
            }

        # Surface transitions
        transitions = conn.execute(
            "SELECT from_state, to_state, road_temp_c, dew_point_c, delta_c "
            "FROM surface_transitions WHERE session_id = ? "
            "ORDER BY timestamp",
            [session_id],
        ).fetchall()
        if transitions:
            summary["surface_transitions"] = [
                {"from": t[0], "to": t[1], "road_temp": t[2], "dew_point": t[3], "delta": t[4]}
                for t in transitions
            ]

        # FLIR thermal stats
        flir_stats = conn.execute(
            "SELECT COUNT(*) as rows, "
            "AVG(road_temp_center) as avg_center, "
            "MIN(road_temp_center) as min_center, "
            "MAX(road_temp_center) as max_center "
            "FROM flir_readings WHERE session_id = ?",
            [session_id],
        ).fetchone()
        if flir_stats and flir_stats[0] > 0:
            summary["flir"] = {
                "readings": flir_stats[0],
                "road_temp_center": {
                    "avg": round(flir_stats[1] or 0, 1),
                    "min": flir_stats[2],
                    "max": flir_stats[3],
                },
            }

        # Detected patterns
        patterns = conn.execute(
            "SELECT pattern_type, severity, value, context_json "
            "FROM patterns WHERE session_id = ? "
            "ORDER BY timestamp",
            [session_id],
        ).fetchall()
        if patterns:
            summary["patterns"] = [
                {"type": p[0], "severity": p[1], "value": p[2]}
                for p in patterns
            ]

        # Alerts
        alert_stats = conn.execute(
            "SELECT alert_type, COUNT(*) "
            "FROM alerts WHERE session_id = ? "
            "GROUP BY alert_type ORDER BY COUNT(*) DESC",
            [session_id],
        ).fetchall()
        if alert_stats:
            summary["alerts"] = {a[0]: a[1] for a in alert_stats}

        return summary

    def generate(self, session_id: str) -> Optional[dict]:
        """Generate a Haiku debrief for a completed session.

        Returns dict with 'summary', 'raw_response', or None on failure.
        """
        if not self._api_key:
            log.warning("No API key — cannot generate debrief")
            return None

        session_summary = self.build_session_summary(session_id)
        if not session_summary.get("telemetry_rows"):
            log.info("No telemetry data for session %s — skipping debrief", session_id[:8])
            return None

        # Build prompt
        prompt = (
            "You are KiSTI, an AI co-driver analyzing session data from a 2014 Subaru WRX STI "
            "with an IAG 750 engine build. Here is this session's data:\n\n"
            f"{json.dumps(session_summary, indent=2, default=str)}\n\n"
            "Give me the 3 most important patterns or findings from this session. "
            "Focus on: safety concerns (ice risk, knock events, oil/coolant), "
            "tune health (IAM, AFR, knock patterns), and surface conditions. "
            "Be specific with numbers. Plain text, no markdown."
        )

        payload = {
            "model": self._model,
            "max_tokens": 500,
            "temperature": 0.3,
            "system": "You are a data analyst for a motorsport telemetry system. "
                      "Analyze the session data and provide actionable insights. "
                      "Be concise and specific.",
            "messages": [{"role": "user", "content": prompt}],
        }

        try:
            body = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                CLAUDE_API_URL,
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": self._api_key,
                    "anthropic-version": ANTHROPIC_VERSION,
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=API_TIMEOUT_S) as resp:
                data = json.loads(resp.read())

            content_blocks = data.get("content", [])
            text = " ".join(
                b["text"] for b in content_blocks if b.get("type") == "text"
            ).strip()

            if not text:
                log.warning("Haiku returned empty response")
                return None

            # Store to DuckDB
            self._db.save_summary(session_id, text, tier="haiku")
            log.info("Haiku debrief generated for session %s (%d chars)", session_id[:8], len(text))

            return {
                "session_id": session_id,
                "summary": session_summary,
                "insights": text,
                "raw_response": data,
            }

        except Exception as exc:
            log.warning("Haiku debrief failed: %s", exc)
            return None
