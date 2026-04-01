"""KiSTI - Mode Manager

Listens to SI Drive CAN state and switches all subsystems between:
  - Intelligent ("KiSTI Guide"): Full voice, waveform LEDs, proactive
  - Sport ("KiSTI Co-Driver"): Short alerts, RPM LEDs, buzzer
  - Sport Sharp ("KiSTI Race Engineer"): Critical only, RPM LEDs

Also manages:
  - Warm-up state machine (Cold → Warming → Ready)
  - Sub-page cycling within each SI-Drive mode (K6 button)
  - Coaching level cycling (Intelligent mode only)
  - Keypad K1-K6 command routing
  - SI-Drive staleness fallback (→ Intelligent after 5s)
"""

from __future__ import annotations

import logging
import time
from enum import IntEnum
from typing import Optional

from PySide6.QtCore import QObject, QTimer, Signal

from can.can_config import (
    KEYPAD_K1,
    KEYPAD_K2,
    KEYPAD_K3,
    KEYPAD_K4,
    KEYPAD_K5,
    KEYPAD_K6,
)
from model.vehicle_state import (
    DiffState,
    DiffStateBridge,
    SIDriveMode,
    WarmUpState,
)

log = logging.getLogger("kisti.modes")

# Warm-up thresholds (°C)
WARMUP_OIL_READY = 70.0      # Oil temp threshold for "ready"
WARMUP_COOLANT_READY = 75.0   # Coolant temp threshold for "ready"
WARMUP_OIL_WARMING = 40.0     # Oil temp threshold for "warming" (past cold)
WARMUP_COOLANT_WARMING = 50.0  # Coolant threshold for "warming"


class DisplayMode(IntEnum):
    """Display mode cycle (K6 button)."""
    KISTI = 0    # Main KiSTI dashboard
    STREET = 1   # Street driving telemetry
    TRACK = 2    # Track telemetry
    DIFF = 3     # DCCD/differential focus

    @property
    def label(self) -> str:
        return _DISPLAY_LABELS[self]


_DISPLAY_LABELS = {
    DisplayMode.KISTI: "KiSTI",
    DisplayMode.STREET: "STREET",
    DisplayMode.TRACK: "TRACK",
    DisplayMode.DIFF: "DIFF",
}


class CoachingLevel(IntEnum):
    """Coaching verbosity level (K5 button, Intelligent mode only)."""
    MINIMAL = 0   # Just alerts and answers
    MODERATE = 1  # + Periodic observations
    FULL = 2      # + Proactive commentary, tips

    @property
    def label(self) -> str:
        return _COACHING_LABELS[self]


_COACHING_LABELS = {
    CoachingLevel.MINIMAL: "Minimal",
    CoachingLevel.MODERATE: "Moderate",
    CoachingLevel.FULL: "Full",
}


class ModeManager(QObject):
    """Central mode controller — connects SI Drive to all subsystems.

    Signals:
        si_drive_changed(int): SI Drive mode changed (SIDriveMode value)
        warmup_changed(int): Warm-up state changed (WarmUpState value)
        display_changed(int): Display mode changed (DisplayMode value)
        coaching_changed(int): Coaching level changed (CoachingLevel value)
        session_toggle(): K1 pressed — toggle session recording
        segment_mark(): K2 pressed — mark a segment
        analyze_run(): K3 pressed — "Analyze that run"
        voice_toggle(): K4 pressed — toggle voice
    """

    si_drive_changed = Signal(int)
    warmup_changed = Signal(int)
    display_changed = Signal(int)
    subpage_changed = Signal(int)
    coaching_changed = Signal(int)
    session_toggle = Signal()
    segment_mark = Signal()
    analyze_run = Signal()
    voice_toggle = Signal()

    def __init__(
        self,
        bridge: DiffStateBridge,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._bridge = bridge

        self._si_drive = SIDriveMode.INTELLIGENT
        self._warmup = WarmUpState.COLD
        self._display = DisplayMode.KISTI
        self._coaching = CoachingLevel.FULL

        self._session_active = False

        # Connect bridge signals
        self._bridge.si_drive_changed.connect(self._on_si_drive_changed)
        self._bridge.keypad_pressed.connect(self._on_keypad_pressed)

        # Warm-up check timer (1 Hz)
        self._warmup_timer = QTimer(self)
        self._warmup_timer.setInterval(1000)
        self._warmup_timer.timeout.connect(self._check_warmup)

    def start(self) -> None:
        """Start mode manager."""
        self._warmup_timer.start()
        log.info("Mode manager started (SI Drive: %s, Display: %s)",
                 self._si_drive.label, self._display.label)

    def stop(self) -> None:
        """Stop mode manager."""
        self._warmup_timer.stop()

    def _on_si_drive_changed(self, mode_int: int) -> None:
        """Handle SI Drive mode change from CAN."""
        try:
            new_mode = SIDriveMode(mode_int)
        except ValueError:
            return

        if new_mode != self._si_drive:
            old = self._si_drive
            self._si_drive = new_mode
            log.info("SI Drive: %s → %s", old.label, new_mode.label)
            self.si_drive_changed.emit(int(new_mode))

    def _on_keypad_pressed(self, buttons: int) -> None:
        """Handle keypad button press events."""
        if buttons & KEYPAD_K1:
            self._session_active = not self._session_active
            log.info("Session %s (K1)", "started" if self._session_active else "stopped")
            self.session_toggle.emit()

        if buttons & KEYPAD_K2:
            log.info("Segment marked (K2)")
            self.segment_mark.emit()

        if buttons & KEYPAD_K3:
            log.info("Analyze run requested (K3)")
            self.analyze_run.emit()

        if buttons & KEYPAD_K4:
            log.info("Voice toggle (K4)")
            self.voice_toggle.emit()

        if buttons & KEYPAD_K5:
            if self._si_drive == SIDriveMode.INTELLIGENT:
                self._coaching = CoachingLevel((self._coaching + 1) % 3)
                log.info("Coaching level: %s (K5)", self._coaching.label)
                self.coaching_changed.emit(int(self._coaching))
            else:
                log.debug("K5 ignored — coaching only in Intelligent mode")

        if buttons & KEYPAD_K6:
            # K6 reserved — SI-Drive handles mode selection, no sub-pages
            log.debug("K6 pressed — reserved (SI-Drive handles mode selection)")

    def _check_warmup(self) -> None:
        """Check engine temperatures, warm-up state, and SI-Drive staleness."""
        state = self._bridge.snapshot()

        # SI-Drive staleness fallback: if no SI-Drive frame for 5s, go Intelligent
        self._check_si_drive_staleness(state)

        # Need engine data to determine warm-up state
        if state.is_engine_stale():
            return

        oil_t = state.oil_temp_c
        clt_t = state.coolant_temp

        old_warmup = self._warmup

        if oil_t >= WARMUP_OIL_READY and clt_t >= WARMUP_COOLANT_READY:
            self._warmup = WarmUpState.READY
        elif oil_t >= WARMUP_OIL_WARMING or clt_t >= WARMUP_COOLANT_WARMING:
            self._warmup = WarmUpState.WARMING
        else:
            self._warmup = WarmUpState.COLD

        if self._warmup != old_warmup:
            log.info("Warm-up: %s → %s (oil=%.0f°C, clt=%.0f°C)",
                     old_warmup.label, self._warmup.label, oil_t, clt_t)
            self.warmup_changed.emit(int(self._warmup))

    # SI-Drive staleness threshold (seconds without 0x6B0 frame)
    SI_DRIVE_STALE_TIMEOUT_S = 5.0

    def _check_si_drive_staleness(self, state: DiffState) -> None:
        """Fall back to Intelligent if SI-Drive signal is stale."""
        if state.si_drive_frame_ts == 0.0:
            return  # Never received — stay in default (Intelligent)
        elapsed = time.monotonic() - state.si_drive_frame_ts
        if elapsed > self.SI_DRIVE_STALE_TIMEOUT_S and self._si_drive != SIDriveMode.INTELLIGENT:
            log.warning("SI Drive stale (%.1fs) — falling back to Intelligent", elapsed)
            self._si_drive = SIDriveMode.INTELLIGENT
            self.si_drive_changed.emit(int(SIDriveMode.INTELLIGENT))

    @property
    def si_drive_mode(self) -> SIDriveMode:
        return self._si_drive

    @property
    def warmup_state(self) -> WarmUpState:
        return self._warmup

    @property
    def display_mode(self) -> DisplayMode:
        return self._display

    @property
    def coaching_level(self) -> CoachingLevel:
        return self._coaching

    @property
    def session_active(self) -> bool:
        return self._session_active
