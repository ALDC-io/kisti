"""KiSTI - LED Waveform Generator

Converts TTS audio amplitude envelope into LED brightness patterns
for the MXG Strada dash shift lights (10 RGB LEDs).

Supports multiple LED modes:
  - Waveform: Voice visualization (Intelligent mode)
  - RPM: Shift indicator (Sport/Sport Sharp)
  - KITT: Red sweep idle pattern (Intelligent idle)
  - Warm-up: Temperature-based color gradient
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Optional

from can.can_config import (
    LED_COUNT,
    LED_MODE_KITT,
    LED_MODE_OFF,
    LED_MODE_RPM,
    LED_MODE_WARMUP,
    LED_MODE_WAVEFORM,
)


@dataclass
class LEDFrame:
    """Single frame of LED state for CAN output."""
    mode: int                          # LED_MODE_*
    brightnesses: list[int]            # 10 values, 0-255
    color_r: int = 0                   # Base color R
    color_g: int = 0                   # Base color G
    color_b: int = 0                   # Base color B


class LEDWaveformGenerator:
    """Generates LED patterns for the MXG Strada dash shift lights."""

    def __init__(self) -> None:
        self._kitt_phase: float = 0.0
        self._warmup_phase: float = 0.0

    def waveform_frame(self, amplitude: float) -> LEDFrame:
        """Generate a voice waveform LED frame.

        Args:
            amplitude: Normalized amplitude 0.0-1.0 from TTS envelope.

        Returns:
            LEDFrame with KiSTI red waveform pattern.
        """
        # Center-out pattern: center LEDs are brightest, edges fade
        center = (LED_COUNT - 1) / 2.0
        brightnesses = []
        for i in range(LED_COUNT):
            dist = abs(i - center) / center  # 0.0 at center, 1.0 at edge
            # Amplitude scales height; distance from center scales falloff
            b = amplitude * (1.0 - dist * 0.6)
            brightnesses.append(max(0, min(255, int(b * 255))))

        return LEDFrame(
            mode=LED_MODE_WAVEFORM,
            brightnesses=brightnesses,
            color_r=230, color_g=0, color_b=0,  # KiSTI red
        )

    def waveform_from_envelope(
        self, envelope: list[float], fps: int = 30,
    ) -> list[LEDFrame]:
        """Convert a full TTS amplitude envelope to LED frames."""
        return [self.waveform_frame(amp) for amp in envelope]

    def kitt_sweep_frame(self, dt: float = 1.0 / 30.0) -> LEDFrame:
        """Generate KITT-style red sweep pattern (idle in Intelligent mode).

        Args:
            dt: Time delta since last frame (seconds).

        Returns:
            LEDFrame with red sweep pattern.
        """
        self._kitt_phase += dt * 2.5  # sweep speed
        # Ping-pong: position oscillates 0 → LED_COUNT-1 → 0
        pos = (math.sin(self._kitt_phase) + 1.0) / 2.0 * (LED_COUNT - 1)

        brightnesses = []
        for i in range(LED_COUNT):
            dist = abs(i - pos)
            # Sharp falloff: bright at position, fading to neighbors
            if dist < 1.0:
                b = int(255 * (1.0 - dist))
            elif dist < 2.0:
                b = int(80 * (2.0 - dist))
            elif dist < 3.0:
                b = int(20 * (3.0 - dist))
            else:
                b = 0
            brightnesses.append(b)

        return LEDFrame(
            mode=LED_MODE_KITT,
            brightnesses=brightnesses,
            color_r=255, color_g=0, color_b=0,  # Red
        )

    def rpm_shift_frame(
        self, rpm: float, shift_rpm: float = 6500.0, redline_rpm: float = 7500.0,
    ) -> LEDFrame:
        """Generate RPM-based shift indicator pattern.

        Args:
            rpm: Current engine RPM.
            shift_rpm: RPM to start shift warning.
            redline_rpm: Redline RPM (all red).

        Returns:
            LEDFrame with green→amber→red shift pattern.
        """
        # Scale RPM to 0.0-1.0 across the shift range
        if rpm < shift_rpm * 0.6:
            # Below display threshold — off
            return LEDFrame(mode=LED_MODE_RPM, brightnesses=[0] * LED_COUNT)

        # Map RPM to number of active LEDs (1-10)
        frac = max(0.0, min(1.0, (rpm - shift_rpm * 0.6) / (redline_rpm - shift_rpm * 0.6)))
        active_leds = max(1, int(frac * LED_COUNT))

        brightnesses = []
        for i in range(LED_COUNT):
            brightnesses.append(255 if i < active_leds else 0)

        # Color: green → amber → red based on RPM fraction
        if frac < 0.5:
            r, g, b = 0, 255, 0       # Green
        elif frac < 0.8:
            r, g, b = 255, 165, 0     # Amber
        else:
            r, g, b = 255, 0, 0       # Red

        return LEDFrame(
            mode=LED_MODE_RPM,
            brightnesses=brightnesses,
            color_r=r, color_g=g, color_b=b,
        )

    def warmup_frame(self, progress: float) -> LEDFrame:
        """Generate warm-up state LED pattern.

        Args:
            progress: Warm-up progress 0.0 (cold) to 1.0 (ready).

        Returns:
            LEDFrame with blue→red→green color transition.
        """
        self._warmup_phase += 1.0 / 30.0

        # Gentle pulse
        pulse = 0.5 + 0.5 * math.sin(self._warmup_phase * 2.0)
        base_brightness = int(80 + 120 * pulse)

        brightnesses = [base_brightness] * LED_COUNT

        # Color transitions: deep blue → cherry red → green
        if progress < 0.5:
            # Cold → warming: blue to red
            t = progress * 2.0
            r = int(204 * t)
            g = 0
            b = int(255 * (1.0 - t))
        else:
            # Warming → ready: red to green
            t = (progress - 0.5) * 2.0
            r = int(204 * (1.0 - t))
            g = int(204 * t)
            b = 0

        return LEDFrame(
            mode=LED_MODE_WARMUP,
            brightnesses=brightnesses,
            color_r=r, color_g=g, color_b=b,
        )

    def off_frame(self) -> LEDFrame:
        """All LEDs off."""
        return LEDFrame(
            mode=LED_MODE_OFF,
            brightnesses=[0] * LED_COUNT,
        )

    def alert_flash_frame(
        self, severity: str, phase: float,
    ) -> LEDFrame:
        """Generate alert flash pattern.

        Args:
            severity: "info" | "advisory" | "warning" | "critical"
            phase: Flash phase 0.0-1.0 (for blinking).
        """
        on = phase < 0.5

        if severity == "critical":
            # Red flash — all LEDs
            b = 255 if on else 0
            return LEDFrame(
                mode=LED_MODE_WAVEFORM,
                brightnesses=[b] * LED_COUNT,
                color_r=255, color_g=0, color_b=0,
            )
        elif severity == "warning":
            # Amber pulse
            b = int(200 * (0.5 + 0.5 * math.sin(phase * math.pi * 2)))
            return LEDFrame(
                mode=LED_MODE_WAVEFORM,
                brightnesses=[b] * LED_COUNT,
                color_r=255, color_g=165, color_b=0,
            )
        elif severity == "advisory":
            # Amber steady
            return LEDFrame(
                mode=LED_MODE_WAVEFORM,
                brightnesses=[150] * LED_COUNT,
                color_r=255, color_g=165, color_b=0,
            )
        else:
            # Info — green brief
            b = 120 if on else 0
            return LEDFrame(
                mode=LED_MODE_WAVEFORM,
                brightnesses=[b] * LED_COUNT,
                color_r=0, color_g=200, color_b=0,
            )
