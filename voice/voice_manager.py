"""KiSTI - Voice Orchestrator

Manages the full voice pipeline: mic → STT → LLM → TTS → speaker + LEDs.
Runs as a QThread, integrates with the PySide6 event loop.

Handles:
  - Continuous audio capture with VAD
  - Wake word detection ("Hey KiSTI")
  - Voice state machine (Idle → Listening → Thinking → Speaking)
  - Mode-aware filtering (Intelligent/Sport/Sport Sharp)
  - LED waveform driving during speech
"""

from __future__ import annotations

import collections
import logging
import os
import queue
import re
import struct
import subprocess
import threading
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional

from PySide6.QtCore import QObject, QThread, Signal

from model.vehicle_state import DiffState, SIDriveMode
from voice.llm_engine import LLMEngine, _match_persona
from voice.mic_capture import MicCapture
from voice.stt_engine import STTEngine, HybridSTTEngine
from voice.tts_engine import TTSEngine
from voice.led_waveform import LEDFrame, LEDWaveformGenerator

log = logging.getLogger("kisti.voice")


@dataclass
class DialogueTurn:
    """Compact record of a single conversation turn."""
    turn_id: int
    user_text: str
    response_source: str       # "persona" | "sensor" | "llm"
    response_summary: str      # First 80 chars of response
    timestamp: float           # monotonic time


@dataclass
class DialogueState:
    """Short-horizon conversational memory for reference resolution.

    Tracks active topic, recent turns, and temporal anchors so the
    future reference resolver can rewrite "that", "it", "those temps".
    """
    topic: str = ""                    # Current active topic (e.g. "brake_temps")
    topic_since_turn: int = 0          # Turn when topic was set
    last_turns: list = field(default_factory=list)  # Last 5 DialogueTurns
    turn_counter: int = 0              # Monotonic turn ID
    last_event_type: str = ""          # "hard_brake" | "mode_change" | etc.
    last_event_ts: float = 0.0         # Monotonic time of last notable event

    def record_turn(self, user_text: str, response: "VoiceResponse") -> None:
        """Record a completed conversation turn."""
        self.turn_counter += 1
        turn = DialogueTurn(
            turn_id=self.turn_counter,
            user_text=user_text,
            response_source=response.source,
            response_summary=response.text[:80],
            timestamp=time.monotonic(),
        )
        self.last_turns.append(turn)
        if len(self.last_turns) > 5:
            self.last_turns.pop(0)

        # Infer topic from keywords in user text
        lower = user_text.lower()
        topic_keywords = {
            "brake": "brakes", "oil": "oil", "coolant": "coolant",
            "boost": "boost", "temp": "temperatures", "tire": "tires",
            "fuel": "fuel", "ethanol": "ethanol", "pressure": "pressure",
            "lap": "lap_times", "sector": "sectors", "speed": "speed",
        }
        for kw, topic in topic_keywords.items():
            if kw in lower:
                self.topic = topic
                self.topic_since_turn = self.turn_counter
                break

    def context_summary(self) -> str:
        """Build a compact context string for LLM injection."""
        parts = []
        if self.topic:
            parts.append(f"Active topic: {self.topic}")
        if self.last_turns:
            parts.append("Recent turns:")
            for t in self.last_turns[-3:]:
                parts.append(f"  User: {t.user_text[:50]}")
                parts.append(f"  KiSTI [{t.response_source}]: {t.response_summary[:50]}")
        if self.last_event_type:
            ago = int(time.monotonic() - self.last_event_ts)
            if ago < 120:
                parts.append(f"Last event: {self.last_event_type} ({ago}s ago)")
        return "\n".join(parts) if parts else ""


@dataclass
class VoiceResponse:
    """Structured output contract for all KiSTI response paths.

    Every response path (persona, sensor, LLM, command) produces one of these.
    Enables a future unified Response Composer to generate consistent speech.
    """
    text: str                          # What to speak
    source: str                        # "persona" | "sensor" | "llm" | "command" | "system"
    tier: str = "deterministic"        # "deterministic" | "interpretive" | "system"
    latency_ms: int = 0               # Response generation time
    facts: list = field(default_factory=list)  # Structured data for display/logging
    status: str = "ok"                 # "ok" | "warn" | "critical"
    can_interrupt: bool = True         # Safe to barge-in during this response


@dataclass
class PipelineTrace:
    """End-to-end latency trace for a single voice interaction.

    All timestamps are time.monotonic() values. Computed properties
    return milliseconds for logging and DuckDB storage.
    """
    mic_captured_at: float = 0.0
    stt_done_at: float = 0.0
    llm_done_at: float = 0.0
    tts_done_at: float = 0.0
    speaker_start_at: float = 0.0
    source: str = ""          # "persona" | "sensor" | "llm" | "command" | "system"
    query_text: str = ""      # First 120 chars of user query

    @property
    def stt_ms(self) -> int:
        if self.stt_done_at and self.mic_captured_at:
            return round((self.stt_done_at - self.mic_captured_at) * 1000)
        return 0

    @property
    def llm_ms(self) -> int:
        if self.llm_done_at and self.stt_done_at:
            return round((self.llm_done_at - self.stt_done_at) * 1000)
        return 0

    @property
    def tts_ms(self) -> int:
        if self.tts_done_at and self.llm_done_at:
            return round((self.tts_done_at - self.llm_done_at) * 1000)
        return 0

    @property
    def total_ms(self) -> int:
        if self.speaker_start_at and self.mic_captured_at:
            return round((self.speaker_start_at - self.mic_captured_at) * 1000)
        return 0


SAMPLE_RATE = 16000
CHUNK_SIZE = 1024  # samples per audio read
WAKE_WORDS = [
    "hey kisti", "hey ki", "kisti",
    # hey_jarvis_v0.1 wake model — Whisper transcribes as "Jarvis"
    "jarvis", "hey jarvis",
    # Common Whisper misheards of "KiSTI"
    "keys to", "keeps to", "key stee", "keisti",
    "christy", "cristy", "kisty", "heykisti",
    "ki sti", "kist", "key sti", "kissty",
    # NOTE: sensor/telemetry words (temperature, boost, oil pressure) were here
    # but caused echo loops — KiSTI says a response containing these words,
    # echo leaks through guard, Whisper transcribes it, WAKE_WORD matches, repeat.
    # These queries now work via conversation window: say wake word first, then ask.
]
QUIET_COMMANDS = ["quiet please kisti", "quiet please", "quiet kisti", "be quiet"]
RESUME_COMMANDS = ["hey kisti"]


class VoiceState(IntEnum):
    """Voice pipeline state machine."""
    IDLE = 0        # Waiting for wake word or command
    LISTENING = 1   # Actively capturing user speech
    THINKING = 2    # Processing with LLM
    SPEAKING = 3    # Playing TTS audio + LED waveform
    QUIET = 4       # Voice silenced (K4 or voice command)
    OFF = 5         # Voice fully disabled


class VoiceToggleState(IntEnum):
    """K4 voice toggle cycle: Normal → Quiet → Off → Normal."""
    NORMAL = 0
    QUIET = 1
    OFF = 2


class VoiceManager(QObject):
    """Orchestrates the KiSTI voice pipeline.

    Signals:
        state_changed(int): VoiceState changed
        speaking_text(str): Text being spoken
        led_frame(LEDFrame): LED frame to send via CAN
    """

    state_changed = Signal(int)
    speaking_text = Signal(str)
    led_frame_ready = Signal(object)  # LEDFrame
    response_ready = Signal(str)      # LLM response text for UI AudioPlayer

    def __init__(self, mic_device: str = "default", enable_mic: bool = True,
                 parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        # Use Deepgram hybrid if API key available, else standard whisper.cpp
        if os.environ.get("DEEPGRAM_API_KEY"):
            self._stt = HybridSTTEngine()
            log.info("Initialized Deepgram hybrid STT engine")
        else:
            self._stt = STTEngine()
            log.info("Initialized standard whisper.cpp STT engine")
        self._tts = TTSEngine()
        self._llm = LLMEngine()
        self._led = LEDWaveformGenerator()
        self._mic = MicCapture(device=mic_device, wake_model=os.environ.get("KISTI_WAKE_MODEL")) if enable_mic else None

        self._state = VoiceState.IDLE
        self._toggle_state = VoiceToggleState.NORMAL
        self._si_drive_mode = SIDriveMode.INTELLIGENT

        self._speak_queue: queue.Queue[str] = queue.Queue(maxsize=10)
        self._worker_thread: Optional[threading.Thread] = None
        self._running = False
        self._stt_lock = threading.Lock()  # Serialize STT — one Whisper call at a time
        self._aplay_proc: Optional[subprocess.Popen] = None
        self._interrupted = False
        self._last_interaction: float = 0.0  # Timestamp of last wake word hit
        self._listen_window_s: float = 5.0   # Stay in conversation mode (tighter to reject hallucinations)

        # Telemetry snapshot for LLM context
        self._telemetry_snapshot: Optional[DiffState] = None
        self._prev_snapshot: Optional[DiffState] = None

        # Recent event log — ring buffer for LLM context injection
        self._recent_events: collections.deque[tuple[float, str]] = collections.deque(maxlen=20)

        # Last structured response (for future composer / display / logging)
        self._last_response: Optional[VoiceResponse] = None

        # Echo suppression — track what KiSTI just said to reject mic echo
        self._last_spoken_text: str = ""
        self._last_spoken_at: float = 0.0

        # Dialogue state — short-horizon conversational memory
        self._dialogue = DialogueState()

        # Edge memory for "remember" commands and LLM context
        self._edge_memory = None

        # Pipeline trace for latency instrumentation
        self._active_trace: Optional[PipelineTrace] = None

        # DuckDB store for latency recording
        self._duckdb_store = None
        self._session_id: str = ""

        # Wire mic → STT → LLM pipeline
        if self._mic:
            self._mic.speech_captured.connect(self._on_speech_captured)

    def start(self) -> None:
        """Initialize all voice subsystems and start the worker thread."""
        self._stt.start()
        self._tts.start()
        self._llm.start()
        self._running = True

        self._worker_thread = threading.Thread(
            target=self._voice_loop,
            daemon=True,
            name="kisti-voice-manager",
        )
        self._worker_thread.start()

        # Start mic capture (safe to call even without a mic — falls back gracefully)
        if self._mic:
            self._mic.start()

        mic_status = "off"
        if self._mic and self._mic.is_available:
            mic_status = "real"
        elif self._mic:
            mic_status = "no device"

        log.info("Voice manager started (STT=%s, TTS=%s, LLM=%s, Mic=%s)",
                 "real" if self._stt.is_real else "mock",
                 "real" if self._tts.is_real else "mock",
                 "real" if self._llm.is_real else "persona",
                 mic_status)

    def stop(self) -> None:
        """Stop all voice subsystems."""
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=5.0)
        if self._mic:
            self._mic.stop()
        self._stt.stop()
        self._tts.stop()
        self._llm.stop()
        log.info("Voice manager stopped")

    def set_si_drive_mode(self, mode: SIDriveMode) -> None:
        """Update SI Drive mode — controls voice behavior."""
        self._si_drive_mode = mode
        log.info("Voice mode: %s", mode.label)

    def set_telemetry(self, state: DiffState) -> None:
        """Update telemetry snapshot for LLM context. Logs notable changes."""
        prev = self._telemetry_snapshot
        self._telemetry_snapshot = state

        if prev is None:
            return

        now = time.monotonic()

        def _log_event(event_type: str, msg: str) -> None:
            self._recent_events.append((now, msg))
            self._dialogue.last_event_type = event_type
            self._dialogue.last_event_ts = now

        # SI Drive mode change
        if state.si_drive_mode != prev.si_drive_mode:
            _log_event("mode_change", f"SI Drive switched to {state.si_drive_mode.label}")

        # ABS activation
        if state.abs_active and not prev.abs_active:
            _log_event("abs", "ABS activated")

        # VDC/TC activation
        if state.vdc_tc and not prev.vdc_tc:
            _log_event("traction_control", "Traction control activated")

        # Significant boost change (>3 PSI jump)
        if state.map_kpa > 0 and prev.map_kpa > 0:
            boost_now = (state.map_kpa - 101.325) * 0.145038
            boost_prev = (prev.map_kpa - 101.325) * 0.145038
            if boost_now - boost_prev > 3:
                _log_event("boost_spike", f"Boost spiked to {boost_now:.1f} PSI")

        # Coolant temp warning (crossing 100°C)
        if state.coolant_temp >= 100 and prev.coolant_temp < 100:
            _log_event("coolant_warn", f"Coolant temp reached {state.coolant_temp:.0f}°C")

        # Oil pressure drop (>10 PSI)
        if prev.oil_psi > 0 and state.oil_psi > 0 and prev.oil_psi - state.oil_psi > 10:
            _log_event("oil_pressure_drop", f"Oil pressure dropped to {state.oil_psi:.0f} PSI")

    def set_edge_memory(self, edge_memory: object) -> None:
        """Inject edge memory for 'remember' commands and LLM context."""
        self._edge_memory = edge_memory

    def set_duckdb_store(self, store: object, session_id: str = "") -> None:
        """Inject DuckDB store for latency recording."""
        self._duckdb_store = store
        self._session_id = session_id

    def toggle_voice(self) -> VoiceToggleState:
        """Cycle voice state: Normal → Quiet → Off → Normal (K4 button)."""
        self._toggle_state = VoiceToggleState((self._toggle_state + 1) % 3)
        if self._toggle_state == VoiceToggleState.NORMAL:
            self._set_state(VoiceState.IDLE)
        elif self._toggle_state == VoiceToggleState.QUIET:
            self._set_state(VoiceState.QUIET)
        else:
            self._set_state(VoiceState.OFF)
        log.info("Voice toggle: %s", self._toggle_state.name)
        return self._toggle_state

    def speak(self, text: str) -> None:
        """Queue text to be spoken (from alerts, proactive commentary, etc.)."""
        if self._state in (VoiceState.QUIET, VoiceState.OFF):
            return
        if self._si_drive_mode == SIDriveMode.SPORT_SHARP:
            return  # No queued speech in S#
        try:
            self._speak_queue.put_nowait(text)
        except queue.Full:
            log.debug("Speak queue full, dropping: %s", text[:30])

    def speak_alert(self, text: str, severity: str) -> None:
        """Queue an alert to be spoken — respects mode filtering.

        Critical alerts always speak. Others filtered by SI Drive mode.
        """
        if self._state == VoiceState.OFF:
            return

        # Critical alerts always speak in all modes
        if severity == "critical":
            try:
                self._speak_queue.put_nowait(text)
            except queue.Full:
                pass
            return

        # Non-critical filtering by mode
        if self._si_drive_mode == SIDriveMode.SPORT_SHARP:
            return  # Only critical in S#
        if self._si_drive_mode == SIDriveMode.SPORT and severity == "info":
            return  # No info in Sport

        try:
            self._speak_queue.put_nowait(text)
        except queue.Full:
            pass

    def _compose_and_speak(
        self, response: VoiceResponse, user_text: str = "",
        trace: Optional[PipelineTrace] = None,
    ) -> None:
        """Unified response handler: record turn, emit signal, queue speech.

        All voice query response paths create a VoiceResponse then call this.
        System messages via speak()/speak_alert() bypass this (own filtering).
        """
        # Record dialogue turn if this was a user-initiated query
        if user_text:
            self._dialogue.record_turn(user_text, response)

        # Store last response (used by barge-in can_interrupt check)
        self._last_response = response

        # Attach trace for completion in _do_speak
        if trace:
            trace.source = response.source
            if user_text:
                trace.query_text = user_text[:120]
            self._active_trace = trace

        # NOTE: Do NOT emit response_ready here — it triggers AudioPlayer (UI path)
        # which plays audio independently of _do_speak (voice loop path).
        # Both paths toggle mic pause/resume, causing race conditions that leave
        # mic stuck paused. _do_speak is the sole audio path for query responses.
        # response_ready is still used for standalone messages like "Let me think about that."

        # Queue for TTS (sole audio path — _do_speak handles echo suppression + barge-in)
        if response.text:
            try:
                self._speak_queue.put_nowait(response.text)
            except queue.Full:
                log.debug("Speak queue full, dropping: %s", response.text[:30])

    # Idiomatic phrases where "it"/"that"/"this" are NOT referential.
    # Checked before attempting pronoun resolution.
    _NON_REFERENTIAL = re.compile(
        r"(?:"
        r"how'?s it going|is it (?:hot|cold|raining)|what is it like|"
        r"that'?s (?:cool|great|awesome|fine|ok|good|nice|interesting|funny|weird|crazy|right)|"
        r"this is (?:fine|great|fun)|"
        r"got it|do it|let'?s do it|forget it|leave it|skip it|"
        r"is that (?:ok|all|right|so|true)|that said|other than that|"
        r"hold it|keep it|take it easy"
        r")",
        re.IGNORECASE,
    )

    # Patterns that indicate a genuinely referential pronoun (asking about topic).
    _REFERENTIAL = [
        (re.compile(r"\b(?:what(?:'s| is| was| are))\s+(?:that|it|this)\b", re.I), "query"),
        (re.compile(r"\b(?:how(?:'s| is| was))\s+(?:that|it|this)\b", re.I), "query"),
        (re.compile(r"\b(?:tell me (?:about|more about))\s+(?:that|it|this|those)\b", re.I), "query"),
        (re.compile(r"\b(?:is|was|are)\s+(?:that|it|this)\s+(?:normal|ok|good|bad|high|low|safe|dangerous)\b", re.I), "eval"),
        (re.compile(r"\bthose\s+\w+", re.I), "those_noun"),
        (re.compile(r"\b(?:that|the)\s+(?:same|last|previous)\b", re.I), "back_ref"),
        (re.compile(r"\bwhat about (?:that|it|this|those)\b", re.I), "query"),
        (re.compile(r"\b(?:why is|why was|why did)\s+(?:that|it|this)\b", re.I), "query"),
        (re.compile(r"\bcompare (?:that|it|this|those)\b", re.I), "query"),
    ]

    def _resolve_references(self, query: str) -> str:
        """Resolve vague references (that, it, those) using dialogue context.

        Only rewrites when the pronoun is genuinely referential (asking about
        a prior topic), NOT when it appears in idiomatic expressions like
        "how's it going" or "that's cool".

        Returns the original query unchanged if:
          - No vague pronouns detected
          - Pronoun is in an idiomatic (non-referential) phrase
          - No active topic in dialogue state
          - Topic is stale (>10 turns ago)
        """
        lower = query.lower().strip()

        # Quick check: any vague pronouns at all?
        if not re.search(r'\b(?:that|it|this|those|them)\b', lower):
            return query

        # Skip idiomatic / non-referential uses
        if self._NON_REFERENTIAL.search(lower):
            return query

        # Need an active, recent topic
        topic = self._dialogue.topic
        if not topic:
            return query
        turns_since = self._dialogue.turn_counter - self._dialogue.topic_since_turn
        if turns_since > 10:
            return query  # Topic too stale

        # Check if any referential pattern matches
        matched = False
        for pattern, _ in self._REFERENTIAL:
            if pattern.search(lower):
                matched = True
                break
        if not matched:
            return query

        # Perform targeted replacement
        resolved = query

        # "those temps" / "those readings" → "the {topic} temps"
        resolved = re.sub(
            r'\bthose\s+(\w+)\b', f"the {topic} \\1",
            resolved, flags=re.IGNORECASE,
        )
        # "that" / "it" / "this" as standalone references → "the {topic}"
        for pronoun in (r'\bthat\b', r'\bit\b', r'\bthis\b', r'\bthem\b'):
            resolved = re.sub(pronoun, f"the {topic}", resolved, count=1, flags=re.IGNORECASE)

        return resolved

    def handle_voice_query(self, transcription: str,
                           trace: Optional[PipelineTrace] = None) -> None:
        """Process a transcribed voice query through the LLM."""
        if not transcription.strip():
            return

        lower = transcription.lower().strip()

        # "Say X" command → repeat back immediately (TTS latency test, skips LLM)
        if lower.startswith("say "):
            phrase = transcription[len("say "):].strip()
            if phrase:
                log.info("Say command: '%s'", phrase)
                resp = VoiceResponse(text=phrase, source="command", tier="system")
                self._compose_and_speak(resp, user_text=transcription, trace=trace)
                return

        # Check for "remember" commands → store in edge memory
        if lower.startswith("remember ") and self._edge_memory:
            content = transcription[len("remember "):].strip()
            if content:
                self._edge_memory.remember(
                    content=content,
                    memory_type="manual",
                    source="voice",
                )
                resp = VoiceResponse(
                    text="Got it. I'll remember that.", source="command", tier="system",
                )
                self._compose_and_speak(resp, user_text=transcription, trace=trace)
                return

        # Check for quiet/resume commands
        if any(cmd in lower for cmd in QUIET_COMMANDS):
            self._toggle_state = VoiceToggleState.QUIET
            self._set_state(VoiceState.QUIET)
            resp = VoiceResponse(text="Going quiet.", source="system", tier="system")
            self._compose_and_speak(resp, user_text=transcription)
            return
        if any(cmd in lower for cmd in RESUME_COMMANDS) and self._state == VoiceState.QUIET:
            self._toggle_state = VoiceToggleState.NORMAL
            self._set_state(VoiceState.IDLE)
            resp = VoiceResponse(text="I'm back. What do you need?", source="system", tier="system")
            self._compose_and_speak(resp, user_text=transcription)
            return

        self._set_state(VoiceState.THINKING)

        # Live sensor query — intercept ambient/weather questions with real data
        live = self._answer_from_sensors(lower)
        if live:
            resp = VoiceResponse(
                text=live, source="sensor", tier="deterministic", latency_ms=0,
            )
            log.info("Live sensor response: %s", live[:80])
            self._compose_and_speak(resp, user_text=transcription, trace=trace)
            return

        # Resolve vague references using dialogue context
        resolved_query = self._resolve_references(transcription)
        if resolved_query != transcription:
            log.info("Reference resolved: '%s' → '%s'", transcription, resolved_query)

        # Build telemetry context
        context = self._build_telemetry_context()

        # Build memory context (skip in Sport Sharp — token budget too tight)
        memory_context = ""
        if self._edge_memory and self._si_drive_mode != SIDriveMode.SPORT_SHARP:
            memory_context = self._edge_memory.build_memory_context(resolved_query)

        # Acknowledge before slow LLM path — persona matches return <1ms so skip those
        if not _match_persona(lower, self._si_drive_mode.label) and self._llm.is_real:
            self.response_ready.emit("Let me think about that.")

        # Query LLM
        response = self._llm.query(
            user_message=resolved_query,
            telemetry_context=context,
            memory_context=memory_context,
            si_drive_mode=self._si_drive_mode.label,
        )

        if trace:
            trace.llm_done_at = time.monotonic()

        tier = "deterministic" if response.tier == "persona_match" else "interpretive"
        resp = VoiceResponse(
            text=response.text, source=response.tier, tier=tier,
            latency_ms=int(response.latency_s * 1000),
        )
        log.info("LLM response (tier=%s, %.1fs): %s", response.tier, response.latency_s, response.text[:80])
        self._compose_and_speak(resp, user_text=transcription, trace=trace)

    def _voice_loop(self) -> None:
        """Main voice processing loop (runs in worker thread)."""
        while self._running:
            try:
                # Process speak queue
                try:
                    text = self._speak_queue.get(timeout=0.1)
                    self._do_speak(text)
                except queue.Empty:
                    # No speech queued — generate idle LED pattern
                    if self._state == VoiceState.IDLE and self._si_drive_mode == SIDriveMode.INTELLIGENT:
                        frame = self._led.kitt_sweep_frame()
                        self.led_frame_ready.emit(frame)
                    time.sleep(1.0 / 30.0)  # ~30 FPS LED rate

            except Exception as exc:
                log.error("Voice loop error: %s", exc, exc_info=True)
                time.sleep(1.0)

    def _on_speech_captured(self, pcm: bytes) -> None:
        """Mic captured a complete utterance — transcribe and process.

        Runs STT then checks for wake word. If the utterance contains a
        wake word (or KiSTI is already in LISTENING state), routes to LLM.

        During SPEAKING state: only listen for wake word (barge-in).
        Stops current TTS playback when wake word detected.
        """
        if self._state == VoiceState.OFF:
            return

        speaking = self._state == VoiceState.SPEAKING

        # Transcribe on a worker thread to avoid blocking Qt
        # Only one STT call at a time — drop captures that arrive while busy
        def _process():
            trace = PipelineTrace(mic_captured_at=time.monotonic())

            # Expire conversation window passthrough
            in_conversation = (time.monotonic() - self._last_interaction) < self._listen_window_s
            if not in_conversation and self._mic and self._mic._passthrough:
                self._mic.set_passthrough(False)

            if not self._stt_lock.acquire(blocking=False):
                log.debug("STT busy — dropping capture")
                return
            try:
                result = self._stt.transcribe(pcm)
                trace.stt_done_at = time.monotonic()
            except Exception as exc:
                log.error("STT transcription crashed: %s", exc, exc_info=True)
                return
            finally:
                self._stt_lock.release()
            if not result.text.strip() or result.text == "[mock transcription]":
                log.info("STT: empty/mock result (%.1fs audio, %.2fs latency)", result.duration_s, result.latency_s)
                return

            text = result.text.strip()
            lower = text.lower()
            log.info("STT: '%s' (%.2fs latency, conf=%.1f)", text[:60], result.latency_s, result.confidence)

            # Echo suppression — if this sounds like what KiSTI just said, discard it.
            # Checks within 3s of last speech ending (covers room reverb + Whisper latency).
            if self._last_spoken_text and (time.monotonic() - self._last_spoken_at) < 3.0:
                spoken_words = set(re.findall(r'\b\w+\b', self._last_spoken_text))
                heard_words = set(re.findall(r'\b\w+\b', lower))
                if heard_words and spoken_words:
                    overlap = len(heard_words & spoken_words) / len(heard_words)
                    if overlap > 0.4:
                        log.info("Echo suppressed (%.0f%% overlap with last speech): '%s'", overlap * 100, text[:60])
                        return

            has_wake_word = any(w in lower for w in WAKE_WORDS)
            in_conversation = (time.monotonic() - self._last_interaction) < self._listen_window_s

            # During TTS playback, only respond to wake word (barge-in)
            if speaking:
                if has_wake_word:
                    log.info("Barge-in detected — interrupting TTS")
                    self._interrupt_playback()
                else:
                    return  # Ignore TTS echo

            if has_wake_word or in_conversation or self._state == VoiceState.LISTENING:
                self._last_interaction = time.monotonic()
                # Enable mic passthrough during conversation window
                if self._mic:
                    self._mic.set_passthrough(True)
                # Strip wake word prefix from the query
                query = text
                if has_wake_word:
                    for w in WAKE_WORDS:
                        idx = lower.find(w)
                        if idx >= 0:
                            query = text[idx + len(w):].strip(" ,.")
                            break
                if query and len(query.split()) >= 2:
                    self.handle_voice_query(query, trace=trace)
                else:
                    # Just the wake word (or wake word + 1-2 hallucinated words)
                    self._set_state(VoiceState.LISTENING)
                    resp = VoiceResponse(text="I'm listening.", source="system", tier="system")
                    self._compose_and_speak(resp)

        threading.Thread(target=_process, daemon=True, name="kisti-stt-worker").start()

    def _interrupt_playback(self) -> None:
        """Stop current TTS playback (barge-in)."""
        proc = self._aplay_proc
        if proc and proc.poll() is None:
            proc.terminate()
            log.info("TTS playback interrupted")
        self._interrupted = True

    def _do_speak(self, text: str) -> None:
        """Synthesize and play speech with LED waveform."""
        self._set_state(VoiceState.SPEAKING)
        self._interrupted = False
        self._last_spoken_text = text.lower()
        self.speaking_text.emit(text)

        trace = self._active_trace

        # Synthesize
        result = self._tts.speak(text)
        if trace:
            trace.tts_done_at = time.monotonic()

        # Barge-in: keep mic active with raised OWW threshold for interruptible
        # responses; full pause for non-interruptible (critical alerts)
        can_barge = True
        if self._last_response and not self._last_response.can_interrupt:
            can_barge = False

        if self._mic:
            if can_barge:
                self._mic.set_barge_in_mode(True)
            else:
                self._mic.pause()

        if trace:
            trace.speaker_start_at = time.monotonic()

        # Start audio playback, then drive LEDs concurrently.
        # Previously LED animation ran BEFORE playback, adding ~2s latency.
        play_proc = None
        wav_path = None
        if not self._interrupted:
            play_proc, wav_path = self._start_audio(result.audio_pcm, result.sample_rate)

        # Drive LEDs synchronized with audio playback
        if self._si_drive_mode == SIDriveMode.INTELLIGENT:
            frames = self._led.waveform_from_envelope(result.amplitude_envelope)
            for frame in frames:
                if not self._running or self._interrupted:
                    break
                self.led_frame_ready.emit(frame)
                time.sleep(1.0 / 30.0)

        # Wait for playback to finish (if LED loop ended first)
        if play_proc:
            try:
                play_proc.wait(timeout=60)
            except Exception:
                pass
            self._aplay_proc = None
            if wav_path:
                import os
                try:
                    os.unlink(wav_path)
                except OSError:
                    pass

        # Mark when we stopped speaking — echo suppression uses this timestamp
        self._last_spoken_at = time.monotonic()

        # Post-playback echo guard — reduced from 0.8s. Echo suppression
        # (40% word overlap within 3s) catches anything this misses.
        time.sleep(0.4)
        if self._mic:
            if can_barge:
                self._mic.set_barge_in_mode(False)
            else:
                self._mic.resume()

        # Log and store pipeline trace
        if trace:
            log.info("Pipeline: STT=%dms LLM=%dms TTS=%dms total=%dms [%s]",
                     trace.stt_ms, trace.llm_ms, trace.tts_ms, trace.total_ms,
                     trace.source)
            if self._duckdb_store:
                try:
                    self._duckdb_store.record_voice_latency(
                        session_id=self._session_id or "no-session",
                        stt_ms=trace.stt_ms, llm_ms=trace.llm_ms,
                        tts_ms=trace.tts_ms, total_ms=trace.total_ms,
                        source=trace.source, query_text=trace.query_text,
                    )
                except Exception:
                    pass  # Never crash voice loop on DB error
            self._active_trace = None

        # Reset conversation window AFTER speaking — user hears response, then has 8s to follow up
        self._last_interaction = time.monotonic()
        self._set_state(VoiceState.IDLE)

    def _start_audio(self, audio_pcm: bytes, sample_rate: int) -> tuple:
        """Start audio playback via PulseAudio (non-blocking).

        Returns (Popen, wav_path) so caller can wait and clean up.
        PulseAudio must stay running to keep the HDA pin-ctl active on Jetson.
        """
        import subprocess as _sp
        import tempfile
        import wave
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                wav_path = f.name
            with wave.open(wav_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(audio_pcm)
            self._aplay_proc = _sp.Popen(
                ["paplay", wav_path],
                stdout=_sp.DEVNULL, stderr=_sp.DEVNULL,
            )
            return self._aplay_proc, wav_path
        except Exception as exc:
            log.warning("Audio playback failed: %s", exc)
            return None, None

    def _answer_from_sensors(self, query_lower: str) -> Optional[str]:
        """Answer ambient/weather questions directly from live Yoctopuce data.

        Returns a short spoken response if we have live sensor data for the
        question, or None to fall through to persona/LLM.
        """
        s = self._telemetry_snapshot
        if s is None or not s.ambient_available:
            return None

        # Ambient temperature
        if any(w in query_lower for w in ["temperature", "temp", "how hot", "how cold", "warm", "cold outside", "degrees"]):
            return f"{s.ambient_temp_c:.1f} degrees outside. Dew point {s.dew_point_c:.1f}."

        # Humidity
        if any(w in query_lower for w in ["humidity", "humid", "moisture", "damp"]):
            return f"Humidity is {s.ambient_humidity_pct:.0f} percent. Dew point {s.dew_point_c:.1f} degrees."

        # Barometric pressure
        if any(w in query_lower for w in ["pressure outside", "barometric", "barometer", "air pressure", "atmospheric"]):
            return f"Barometric pressure {s.ambient_pressure_hpa:.0f} hectopascals."

        # Density altitude
        if any(w in query_lower for w in ["density altitude", "altitude"]):
            return f"Density altitude {s.density_altitude_ft:.0f} feet."

        # General weather/outside/conditions
        if any(w in query_lower for w in ["weather", "outside", "conditions", "what's it like"]):
            return f"{s.ambient_temp_c:.1f} degrees, {s.ambient_humidity_pct:.0f} percent humidity, {s.ambient_pressure_hpa:.0f} hectopascals."

        return None

    def _build_telemetry_context(self) -> str:
        """Build telemetry context string for LLM system prompt."""
        s = self._telemetry_snapshot
        if s is None:
            return "No telemetry available."

        lines = []
        if s.rpm > 0:
            lines.append(f"RPM: {s.rpm:.0f}")
        if s.speed_kph > 0:
            lines.append(f"Speed: {s.speed_kph:.0f} km/h, Gear: {s.gear}")
        if s.map_kpa > 0:
            boost_psi = (s.map_kpa - 101.325) * 0.145038
            lines.append(f"Boost: {boost_psi:.1f} PSI")
        if s.coolant_temp > 0:
            lines.append(f"Coolant: {s.coolant_temp:.0f}°C")
        if s.oil_temp_c > 0:
            lines.append(f"Oil Temp: {s.oil_temp_c:.0f}°C")
        if s.oil_psi > 0:
            lines.append(f"Oil Pressure: {s.oil_psi:.0f} PSI")
        if s.lambda_1 > 0:
            lines.append(f"Lambda: {s.lambda_1:.3f}")
        if s.iat_c != 0:
            lines.append(f"IAT: {s.iat_c:.0f}°C")
        if s.ethanol_pct > 0:
            lines.append(f"Ethanol: {s.ethanol_pct:.0f}%")
        lines.append(f"DCCD: {s.dccd_command_pct:.0f}%")
        lines.append(f"Surface: {s.surface_state.label}")
        lines.append(f"SI Drive: {s.si_drive_mode.label}")
        if s.ambient_available:
            lines.append(f"Ambient Temp: {s.ambient_temp_c:.1f}°C")
            lines.append(f"Humidity: {s.ambient_humidity_pct:.0f}%")
            lines.append(f"Barometric: {s.ambient_pressure_hpa:.0f} hPa")
            lines.append(f"Dew Point: {s.dew_point_c:.1f}°C")
            lines.append(f"Density Altitude: {s.density_altitude_ft:.0f} ft")

        # Inject recent events (last 60s) for contextual queries
        now = time.monotonic()
        recent = [(ts, msg) for ts, msg in self._recent_events if now - ts < 60]
        if recent:
            lines.append("")
            lines.append("Recent events:")
            for ts, msg in recent[-5:]:  # Last 5 events max
                ago = int(now - ts)
                lines.append(f"  {ago}s ago: {msg}")

        return "\n".join(lines) if lines else "No telemetry available."

    def _set_state(self, new_state: VoiceState) -> None:
        if self._state != new_state:
            self._state = new_state
            self.state_changed.emit(int(new_state))

    @property
    def state(self) -> VoiceState:
        return self._state

    @property
    def toggle_state(self) -> VoiceToggleState:
        return self._toggle_state
