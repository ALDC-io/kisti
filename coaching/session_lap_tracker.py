"""Within-session lap trend tracker for KiSTI coaching.

Accumulates 1Hz coaching tick outputs per lap and produces a voice-ready
trend summary at lap completion. Pure Python — no Qt dependency.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class _LapRecord:
    lap_number: int
    sentiment_counts: dict[str, int] = field(default_factory=lambda: {"green": 0, "amber": 0})
    issue_texts: set[str] = field(default_factory=set)
    tick_count: int = 0

    def green_frac(self) -> float:
        if self.tick_count == 0:
            return 0.0
        return self.sentiment_counts.get("green", 0) / self.tick_count

    def amber_frac(self) -> float:
        if self.tick_count == 0:
            return 0.0
        return self.sentiment_counts.get("amber", 0) / self.tick_count


class SessionLapTracker:
    """Tracks coaching output across laps and surfaces spoken trend summaries."""

    _MIN_TICKS = 3
    _TREND_THRESHOLD = 0.15  # 15-point shift triggers a trend message
    _AMBER_WARN_FRAC = 0.30  # first-lap threshold to surface an issue
    _CLEAN_LAP_FRAC = 0.10   # amber below this → "Clean lap"

    def __init__(self) -> None:
        self._current: _LapRecord = _LapRecord(lap_number=0)
        self._previous: _LapRecord | None = None

    def record_tick(self, text: str, sentiment: str) -> None:
        """Accumulate one coaching tick (call at 1Hz during a lap)."""
        self._current.tick_count += 1
        key = sentiment if sentiment in ("green", "amber") else "amber"
        self._current.sentiment_counts[key] = self._current.sentiment_counts.get(key, 0) + 1
        if sentiment == "amber" and text:
            self._current.issue_texts.add(text)

    def complete_lap(self, lap_number: int, time_s: float) -> str:
        """Call on lap completion. Returns a voice-ready trend string or ''.

        Resets accumulators for the next lap regardless of return value.
        """
        record = self._current
        record.lap_number = lap_number

        try:
            if record.tick_count < self._MIN_TICKS:
                return ""
            return self._build_summary(record, self._previous)
        finally:
            self._previous = record
            self._current = _LapRecord(lap_number=lap_number + 1)

    def _build_summary(self, current: _LapRecord, previous: _LapRecord | None) -> str:
        amber_frac = current.amber_frac()
        green_frac = current.green_frac()

        if previous is None:
            # First lap: only speak if conditions were notably bad
            if amber_frac > self._AMBER_WARN_FRAC and current.issue_texts:
                issue = next(iter(current.issue_texts))
                # Trim to ≤6 words for voice brevity
                words = issue.split()[:6]
                return " ".join(words) + "."
            return ""

        prev_amber = previous.amber_frac()
        prev_green = previous.green_frac()
        amber_delta = amber_frac - prev_amber
        green_delta = green_frac - prev_green

        if amber_frac < self._CLEAN_LAP_FRAC:
            return "Clean lap. Keep it."

        if green_delta > self._TREND_THRESHOLD:
            return "Technique improving."

        if amber_delta > self._TREND_THRESHOLD:
            if current.issue_texts:
                issue = next(iter(current.issue_texts))
                words = issue.split()[:4]
                return "Watch " + " ".join(words).lower().rstrip(".") + "."
            return "Technique rougher than last lap."

        return ""
