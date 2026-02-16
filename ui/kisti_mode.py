"""KiSTI - Voice/Chat Interaction Mode

KITT 2.0-inspired voice modulator waveform + Zeus typewriter chat.
Waveform activates only while KiSTI is "speaking" (typewriter running).
Periodic idle prompts keep the personality alive without being always-on.

Design ref: Zeus Memory 233bf5c9 (KITT Voice Waveform)
             Zeus Memory 62215456 (Zeus Chat System)
"""

import random
import time

from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import QPainter, QPen, QColor, QBrush, QFont, QLinearGradient
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
)

from data.models import RadarBand, AlertDirection
from ui.theme import BG_DARK, BG_PANEL, HIGHLIGHT, GRAY, WHITE, CHROME_DARK, DIM

# KiSTI logo red (sampled from actual logo)
KISTI_RED = "#C80A33"

# Intro dialogue — played on first launch
_INTRO_LINES = [
    "Initializing KiSTI subsystems...",
    "Link ECU connected. 42 channels streaming.",
    "Teledyne FLIR online. Thermal array nominal.",
    "Zeus Memory sync active — 3.6M records available.",
    "All systems green. I'm ready when you are.",
    "",
    "I'm KiSTI — your AI co-driver.",
    "I watch every sensor so you can focus on the apex.",
    "Ask me anything, or just drive. I'll speak up when it matters.",
]

# Periodic idle lines — one picked randomly every ~30s
_IDLE_LINES = [
    # Personality / check-ins
    "Are you still there? The tires are getting cold.",
    "Anything you need? I've been watching the brake temps — looking stable.",
    "I feel like going for a drive. Who's in?",
    "If you're not driving, I'm just sitting here counting thermal pixels.",
    "Ready for another session? I'll reset the lap timer when you hit pit out.",
    "Just checking in. All systems nominal on my end.",
    "I'm here if you need me. Not going anywhere.",
    "Quiet out there. I like it. Gives me time to think.",
    "You know, I never get tired. One of the perks.",
    "I've been running diagnostics in the background. Everything checks out.",
    "Still here. Still watching. Still learning.",
    "Is it just me, or does this car smell like race fuel? Oh wait, I can't smell.",
    "I wonder what it's like to actually feel G-forces. Must be something.",
    "If I had a body, I'd be tapping my fingers on the dash right now.",
    "I've been listening to the engine idle. It has a nice rhythm to it.",
    "Don't mind me — just running 14 million calculations per second over here.",
    "I could talk about turbo dynamics all day. Literally. I don't need sleep.",
    "You're unusually quiet. Planning something aggressive for the next session?",
    "I appreciate the silence. It lets me optimize my neural pathways.",
    "Fun fact about me: I process telemetry faster than you can blink.",
    # STI / Subaru knowledge
    "Did you know the STI hood scoop feeds the top-mount intercooler directly?",
    "The EJ257's unequal-length headers give the STI that signature rumble.",
    "Subaru's symmetrical AWD puts the drivetrain in a straight line. Pure engineering.",
    "The STI's DCCD center diff can split torque 41/59 front to rear.",
    "Fun fact: STI stands for Subaru Tecnica International — founded in 1988.",
    "The 2014 STI hatch weighs about 3,395 lbs. Every pound matters on track.",
    "That EJ257 block has been in production since 2004. Battle-tested.",
    "The STI's 6-speed is one of the strongest OEM transmissions ever made.",
    "Brembo brakes from the factory. Subaru doesn't mess around with stopping power.",
    "The intercooler sits right on top of the engine. Short piping, fast spool.",
    "Boxer engines have a lower center of gravity than inline or V configs.",
    "The STI's suspension geometry was designed for rally. It shows on track.",
    "That turbo is a VF48. Small but responsive — perfect for a 2.5L.",
    "The STI's oil cooler is working overtime in this heat. Doing its job though.",
    "Subaru ran the WRC from 1990 to 2008. That DNA is in every STI.",
    "The ring gear in this trans is straight-cut in some gears. You can hear it.",
    "Top-mount intercoolers heat-soak faster, but the response is worth it on track.",
    "The EJ's twin-scroll turbo setup reduces lag by separating exhaust pulses.",
    # Boost Barn / build
    "Boost Barn built this motor to handle 450whp. We're only using 380.",
    "Boost Barn spec'd the fuel system for E85 capability. Flex fuel ready.",
    "The Boost Barn tune has 3 maps — pump gas, E85, and anti-lag.",
    "Boost Barn's dyno sheets show peak torque at 4,200 RPM. Flat curve after that.",
    "That intercooler upgrade was Boost Barn's recommendation. 30% more core volume.",
    "Boost Barn welded the up-pipe in-house. Full 3-inch, no cats, no restrictions.",
    "The turbo-back exhaust is Boost Barn's own design. Mandrel bent, equal length.",
    "Boost Barn's clutch setup handles 500 ft-lbs. We've got headroom.",
    "The oil catch can was Boost Barn's idea. Keeps the intake valves clean.",
    "Boost Barn data-logged 200 pulls before signing off on this tune.",
    # Analytic Labs / ALDC / KiSTI
    "Analytic Labs designed me to learn from every lap. I'm always getting better.",
    "ALDC's Zeus Memory system gives me access to 3.6 million data points.",
    "Analytic Labs built the thermal imaging pipeline. Every pixel means something.",
    "The ALDC team tested me at Laguna Seca, Thunderhill, and Sonoma.",
    "My neural architecture was designed by Analytic Labs for edge computing.",
    "ALDC's philosophy: racing improves the breed. I take that personally.",
    "Analytic Labs trains my models on real telemetry, not simulated data.",
    "The KiSTI system runs on NVIDIA Jetson. GPU-accelerated AI at the edge.",
    "ALDC built the Link ECU integration from scratch. 42 channels, real-time.",
    "Analytic Labs' first principle: no hallucinations. I only report what I see.",
    # Teledyne FLIR / thermal
    "The Teledyne IR is picking up heat soak from the turbo. Normal for this config.",
    "Thermal imaging shows the exhaust manifold at 847°F. Within spec.",
    "The FLIR array updates at 30Hz. I see heat changes before you feel them.",
    "IR sensors show the brake rotors cooling evenly. Good pad contact.",
    "Teledyne's thermal camera has 0.05°C sensitivity. I can see a fingerprint cool.",
    "The thermal array is tracking 12 zones simultaneously. All within tolerance.",
    "Heat signature from the diff is nominal. Fluid temp holding steady.",
    "The FLIR is showing ambient at 78°F. Track surface will be grippy.",
    "Thermal imaging caught a hot spot on the left-front last session. Resolved now.",
    "The turbo housing glows orange on IR after a hard lap. Beautiful, actually.",
    # Track / driving
    "Fun fact: Laguna Seca's Corkscrew drops 5.5 stories in just 450 feet.",
    "I've been thinking about your last lap. Turn 6 entry could be 2mph faster.",
    "Your best lap was 1:32.4. I think we can find a tenth in the esses.",
    "I've analyzed 847 laps at this track. Want to talk racing lines?",
    "Trail braking into Turn 3 could save you two tenths. Data supports it.",
    "The racing line through the carousel is counterintuitive. Late apex, early throttle.",
    "Sector 2 is where you're strongest. Sector 3 has the most room to improve.",
    "Tire temps suggest you're understeering mid-corner. Try more trail brake.",
    "Your throttle application out of Turn 9 is textbook. Smooth and progressive.",
    "I've compared your line to the fastest lap in my database. Sending overlay to TRACK.",
    "The ideal brake point for Turn 1 is the 200-meter board. You're braking at 180.",
    "Your corner speed through the sweeper has improved 3mph over the last 10 laps.",
    "Apex speed in Turn 7 is limited by rear grip. We might need more rear wing.",
    "The data shows you lift before Turn 4. Trust the aero — you can go flat.",
    "Your reaction time off pit lane is 1.2 seconds. Room for improvement there.",
    "Thunderhill's Turn 5 is deceptively fast. The camber helps more than you think.",
    "Sonoma's Turn 3a is blind. Commit to the braking zone and trust the car.",
    "Track temp dropped 4 degrees in the last hour. Grip levels will change.",
    # Tire / brake telemetry
    "All four tires within 3 degrees of each other. That's a well-set-up car.",
    "Quick thought — the right-rear has been trending 2 degrees warmer. Worth watching.",
    "The rear brakes are running cooler than the fronts. Bias looks good.",
    "Left-front tire pressure is up 2 PSI from cold. Normal heat build.",
    "Tire temps show the outer edge is hotter. Might need more negative camber.",
    "Brake pad thickness is still above 60%. Plenty of life left this session.",
    "The fronts are doing most of the work. 68/32 brake bias by temperature.",
    "Tire surface temp vs core temp delta is 12°F. Good heat penetration.",
    "Right-front is the hardest-working tire on this track. Clockwise layouts do that.",
    "Brake fluid temp is 380°F. We flush at 450°F, so we've got margin.",
    "The tires need two more laps to reach optimal window. Be patient.",
    "Cross-weight is 50.2%. Almost perfectly balanced.",
    "Camber wear pattern looks even across all four tires. Setup is dialed.",
    # Engine / powertrain
    "The EJ257 is holding steady. Oil pressure right in the sweet spot.",
    "Oil temp stabilized at 220°F. The cooler is doing its job.",
    "Boost is hitting 18.5 PSI on the top end. Right on target.",
    "Knock sensors are quiet. The tune is clean on this fuel.",
    "Coolant temp is 195°F. Thermostat is cycling normally.",
    "AFR is 10.8:1 at full boost. Rich enough for safety, lean enough for power.",
    "The wideband O2 sensor confirms fueling is spot-on across the RPM range.",
    "Intake air temp is 42°F over ambient. The intercooler could be more efficient.",
    "Oil pressure at idle is 28 PSI. Healthy bearing clearances.",
    "Exhaust gas temps are symmetric across all four cylinders. Even combustion.",
    "The turbo is spooling to full boost by 3,800 RPM. That's the VF48 sweet spot.",
    "Fuel pressure is rock-solid at 43.5 PSI base. The Boost Barn fuel system is solid.",
    # Zeus Memory / data
    "Zeus just flagged a new insight. Check the findings panel on TRACK view.",
    "Zeus Memory correlated your brake temps with lap times. Interesting pattern.",
    "I've stored 847 telemetry snapshots from today's session in Zeus Memory.",
    "Zeus found a similar thermal signature from last month. Comparing now.",
    "The Zeus correlation engine found that your fastest laps have 2° cooler rears.",
    "Zeus Memory just indexed a new pattern in your driving style. Getting smarter.",
    "I cross-referenced today's data with 3 previous track days. Trends emerging.",
    "Zeus flagged an anomaly in cylinder 3 EGT. Minor, but I'm tracking it.",
    "The memory federation has data from 47 track days. That's a deep dataset.",
    "Zeus auto-tagged this session as 'high-performance testing'. Accurate.",
    # Tech / general knowledge
    # Valentine One / radar awareness
    "V1 Gen2 is linked and listening. I'll let you know if anything lights up.",
    "The Valentine One is scanning X, K, Ka, and Laser. Full spectrum coverage.",
    "Quiet on the radar front. No bogeys in any direction.",
    "V1's been silent for a while. Either it's clear, or we're in a dead zone.",
    "The Gen2's directional arrows are my favorite feature. I always know where they are.",
    "Ka band at 34.7 GHz is the most common police frequency. I watch it closely.",
    "I cross-reference V1 alerts with GPS to build a threat heatmap. Learning every mile.",
    "K-band door openers are the bane of my existence. I filter what I can.",
    "The V1 Gen2's ESP protocol gives me band, frequency, and direction. Full picture.",
    "Laser is instant — no ramp-up. If V1 sees it, you need to react immediately.",
    "V1 has been running clean. No false alerts in the last 10 minutes.",
    "I've catalogued 847 Ka sources in Zeus Memory. Most are fixed positions.",
    "The V1's rear antenna is underrated. I've caught more trailing threats than you'd expect.",
    "Fun fact: the Valentine One was first released in 1992. The Gen2 is a worthy successor.",
    "BLE gives me raw ESP packets from the V1. Band, frequency, signal, direction — all mine.",
    # Tech / general knowledge
    "Did you know F1 cars generate enough downforce to drive upside down at 130mph?",
    "The first turbocharger was patented in 1905 by Alfred Buchi. Long history.",
    "Carbon fiber is 5x stronger than steel but weighs 1/3 as much.",
    "Michelin invented the radial tire in 1946. Changed everything.",
    "The Nurburgring Nordschleife is 12.9 miles long with 154 turns.",
    "Ayrton Senna once said, 'If you no longer go for a gap, you're no longer a racer.'",
    "The first land speed record was set in 1898 at 39.245 mph. Electric car.",
    "Brake rotors can reach 1,800°F in heavy braking zones. Glowing red is normal.",
    "Aerodynamic drag increases with the square of speed. Double speed, quadruple drag.",
    "The McLaren F1's engine bay is lined with gold foil. Best heat reflector.",
    "Group B rally cars made 500+ HP with no traction control. Wild era.",
    "Colin Chapman's philosophy: simplify, then add lightness.",
    "The Porsche 917 was so fast it was effectively banned from Le Mans.",
    "A Formula 1 engine revs to 15,000 RPM. Ours peaks at 7,200. Different worlds.",
    "Rain tires can disperse 65 liters of water per second at 186 mph.",
]

# Typewriter speed (ms per character)
_CHAR_MS = 30


class _KittWaveform(QWidget):
    """KITT 2.0 voice modulator: 3 columns x 14 horizontal dash segments."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(120, 100)
        self._active = False
        self._levels = [0, 0, 0]

        self._timer = QTimer(self)
        self._timer.setInterval(80)
        self._timer.timeout.connect(self._randomize)
        self._timer.start()

    def set_active(self, active):
        self._active = active
        if not active:
            self._levels = [0, 0, 0]
            self.update()

    def _randomize(self):
        if self._active:
            center = random.randint(2, 7)
            left = max(0, int(center * random.uniform(0.4, 1.0)))
            right = max(0, int(center * random.uniform(0.4, 1.0)))
            self._levels = [left, center, right]
        else:
            self._levels = [0, 0, 0]
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        p.fillRect(0, 0, w, h, QColor(BG_DARK))

        num_segments = 7
        num_cols = 3
        seg_gap = 3
        col_gap = 8

        total_col_width = (w - (num_cols + 1) * col_gap) / num_cols
        seg_h = max(3, (h / 2 - num_segments * seg_gap) / num_segments)
        center_y = h / 2
        base_color = QColor(KISTI_RED)

        for col_idx in range(num_cols):
            level = self._levels[col_idx]
            col_x = col_gap + col_idx * (total_col_width + col_gap)

            for seg in range(num_segments):
                dist = seg
                lit = seg < level
                opacity = max(0.4, 1.0 - dist * 0.08) if lit else 0.08

                seg_color = QColor(base_color)
                seg_color.setAlphaF(opacity)

                if lit and dist < 3:
                    glow_alpha = max(0.0, 0.3 - dist * 0.1)
                    glow_color = QColor(base_color)
                    glow_color.setAlphaF(glow_alpha)
                    glow_expand = 2
                    gy_top = center_y - (seg + 1) * (seg_h + seg_gap) - glow_expand
                    p.setPen(Qt.NoPen)
                    p.setBrush(glow_color)
                    p.drawRoundedRect(
                        QRectF(col_x - glow_expand, gy_top,
                               total_col_width + 2 * glow_expand,
                               seg_h + 2 * glow_expand), 2, 2)
                    gy_bot = center_y + seg * (seg_h + seg_gap) - glow_expand
                    p.drawRoundedRect(
                        QRectF(col_x - glow_expand, gy_bot,
                               total_col_width + 2 * glow_expand,
                               seg_h + 2 * glow_expand), 2, 2)

                p.setPen(Qt.NoPen)
                p.setBrush(seg_color)
                y_top = center_y - (seg + 1) * (seg_h + seg_gap)
                p.drawRoundedRect(QRectF(col_x, y_top, total_col_width, seg_h), 1, 1)
                y_bot = center_y + seg * (seg_h + seg_gap)
                p.drawRoundedRect(QRectF(col_x, y_bot, total_col_width, seg_h), 1, 1)

        p.end()


class _ScanBar(QWidget):
    """KITT scanning light bar — always sweeping."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(4)
        self._pos = 0.0
        self._direction = 1
        self._active = True

        self._timer = QTimer(self)
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def set_active(self, active):
        self._active = active
        self.update()

    def _tick(self):
        if self._active:
            self._pos += 0.03 * self._direction
            if self._pos >= 1.0:
                self._direction = -1
            elif self._pos <= 0.0:
                self._direction = 1
            self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor(BG_DARK))
        if self._active:
            center_x = self._pos * w
            grad = QLinearGradient(center_x - 40, 0, center_x + 40, 0)
            grad.setColorAt(0.0, QColor(0, 0, 0, 0))
            grad.setColorAt(0.5, QColor(KISTI_RED))
            grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            p.fillRect(0, 0, w, h, grad)
        else:
            p.fillRect(0, 0, w, h, QColor(KISTI_RED + "15"))
        p.end()


class KistiModeWidget(QWidget):
    """KiSTI AI voice/chat interaction page with typewriter dialogue."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._speaking = False
        self._char_queue = []        # Characters waiting to be typed
        self._current_line = ""      # Line being typed
        self._line_queue = []        # Lines waiting to be spoken
        self._intro_done = False
        self._idle_timer_s = 0       # Seconds since last speech ended
        self._pause_ticks = 0        # Ticks to wait between lines
        self._last_radar_alert_id = None  # Track which alert we last spoke about
        self._radar_cooldown = 0     # Seconds to wait before next radar speech

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(0)

        # Top section: voice waveform + status
        top = QHBoxLayout()
        top.setSpacing(16)

        self._waveform = _KittWaveform(self)
        self._waveform.setFixedSize(100, 100)
        top.addWidget(self._waveform)

        top.addStretch()

        layout.addLayout(top)

        self._scan_bar = _ScanBar(self)
        layout.addWidget(self._scan_bar)

        layout.addSpacing(8)

        # Chat transcript area (scrollable)
        self._chat_label = QLabel("")
        self._chat_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self._chat_label.setWordWrap(True)
        self._chat_label.setStyleSheet(
            f"color: {WHITE}; font-size: 11px; "
            f"font-family: 'JetBrains Mono', 'Courier', monospace; "
            f"background-color: {BG_PANEL}; "
            f"padding: 10px;"
        )

        scroll = QScrollArea()
        scroll.setWidget(self._chat_label)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            f"QScrollArea {{ border: 1px solid {CHROME_DARK}; "
            f"border-radius: 4px; background: {BG_PANEL}; }}"
        )
        layout.addWidget(scroll, stretch=1)

        # Transcript accumulator (list of completed lines)
        self._transcript = []

        # Typewriter timer — fires every _CHAR_MS to type one character
        self._type_timer = QTimer(self)
        self._type_timer.setInterval(_CHAR_MS)
        self._type_timer.timeout.connect(self._type_tick)
        self._type_timer.start()

        # Idle check timer — fires every second to count idle time
        self._idle_check = QTimer(self)
        self._idle_check.setInterval(1000)
        self._idle_check.timeout.connect(self._idle_tick)
        self._idle_check.start()

        # Queue intro dialogue
        self._queue_lines(_INTRO_LINES)

    def _queue_lines(self, lines):
        """Queue a list of lines to be spoken sequentially."""
        for line in lines:
            self._line_queue.append(line)

    def _start_speaking(self, text):
        """Begin typewriter output of a line."""
        self._speaking = True
        self._char_queue = list(text)
        self._current_line = ""
        self._waveform.set_active(True)

    def _stop_speaking(self):
        """End speech — commit line to transcript. Scanner keeps sweeping."""
        self._speaking = False
        self._waveform.set_active(False)
        if self._current_line.strip():
            self._transcript.append(self._current_line)
        self._current_line = ""
        self._idle_timer_s = 0
        self._update_display()

    def _type_tick(self):
        """Called every _CHAR_MS — type one character or advance to next line."""
        if self._pause_ticks > 0:
            self._pause_ticks -= 1
            return

        if self._speaking and self._char_queue:
            # Type next character
            ch = self._char_queue.pop(0)
            self._current_line += ch
            self._update_display()
        elif self._speaking and not self._char_queue:
            # Line finished
            self._stop_speaking()
            # Pause between lines (500ms = ~17 ticks at 30ms)
            self._pause_ticks = int(500 / _CHAR_MS)
        elif not self._speaking and self._line_queue:
            # Start next queued line
            next_line = self._line_queue.pop(0)
            if next_line.strip():
                self._start_speaking(next_line)
            else:
                # Empty line = pause (~1s)
                self._transcript.append("")
                self._pause_ticks = int(1000 / _CHAR_MS)
                self._update_display()

    def _idle_tick(self):
        """Called every second. After ~60s idle, say something."""
        if self._radar_cooldown > 0:
            self._radar_cooldown -= 1
        if not self._speaking and not self._line_queue:
            self._idle_timer_s += 1
            # Random interval 25-35 seconds
            threshold = random.randint(25, 35)
            if self._idle_timer_s >= threshold:
                line = random.choice(_IDLE_LINES)
                self._queue_lines([line])
                self._idle_timer_s = 0

    def _update_display(self):
        """Refresh the chat label — newest lines at top, oldest scroll below."""
        lines = list(self._transcript)
        if self._current_line:
            lines.append(self._current_line + "\u2588")

        # Reverse so newest is first
        html_parts = []
        for i, line in enumerate(reversed(lines)):
            if not line.strip():
                html_parts.append("<br>")
                continue
            is_current = (i == 0 and self._speaking)
            color = KISTI_RED if is_current else GRAY
            escaped = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            html_parts.append(f'<span style="color:{color};">{escaped}</span><br>')

        self._chat_label.setText("".join(html_parts))

        # Keep scroll at top so newest line is always visible
        scroll = self._chat_label.parent()
        if scroll and hasattr(scroll, 'verticalScrollBar'):
            sb = scroll.verticalScrollBar()
            sb.setValue(sb.minimum())

    def update_data(self, vehicle_state):
        """Process radar state and trigger KiSTI persona speech on alerts."""
        if self._radar_cooldown > 0:
            return
        self._handle_radar_alert(vehicle_state.radar)

    def _handle_radar_alert(self, radar_state):
        """Generate escalating first-person speech based on radar threat level."""
        if not radar_state or not radar_state.has_alerts:
            return

        alert = radar_state.priority_alert
        if not alert:
            return

        # Don't repeat for the same alert
        if alert.alert_id == self._last_radar_alert_id:
            return

        signal = max(alert.front_signal, alert.rear_signal)
        if signal < 1:
            return

        self._last_radar_alert_id = alert.alert_id
        # Cooldown: don't spam — wait 8 seconds between radar speeches
        self._radar_cooldown = 8

        band = alert.band.value
        direction = alert.direction.value

        if alert.band == RadarBand.LASER:
            line = f"LASER! {direction.upper()}! You're being painted right now."
        elif signal <= 2:
            line = f"Heads up — weak {band} detected, {direction}."
        elif signal <= 4:
            ghz = alert.frequency_mhz / 1000.0
            line = f"I'm picking up {band} at {ghz:.1f} GHz, {direction}. Signal is building."
        elif signal <= 6:
            ghz = alert.frequency_mhz / 1000.0
            line = f"Strong {band} {direction}, {ghz:.1f} GHz. Slow it down."
        else:
            ghz = alert.frequency_mhz / 1000.0
            line = f"Very strong {band} signal, {ghz:.1f} GHz! Brake check."

        self._queue_lines([line])
