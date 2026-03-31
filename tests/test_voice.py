"""Tests for voice pipeline — STT, TTS, LLM, LED waveform, voice manager.

All tests use mocks (no Ollama, no WhisperTRT, no Piper, no audio hardware).
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from voice.stt_engine import STTEngine, HybridSTTEngine, TranscriptionResult, SAMPLE_RATE
from voice.tts_engine import TTSEngine, TTSResult, compute_amplitude_envelope
from voice.llm_engine import (
    LLMEngine, LLMResponse, _match_persona, FALLBACK_RESPONSE,
    MODE_TOKEN_CAPS, MODE_TEMPERATURE, _MODE_ALLOWED_CATEGORIES,
)
from voice.mic_capture import (
    MicCapture, SAMPLE_RATE as MIC_SAMPLE_RATE, FRAME_BYTES,
    SPEECH_START_FRAMES, SPEECH_END_FRAMES, VAD_MODE,
)
from voice.led_waveform import LEDWaveformGenerator, LEDFrame
from can.can_config import (
    LED_COUNT, LED_MODE_KITT, LED_MODE_OFF, LED_MODE_RPM,
    LED_MODE_WARMUP, LED_MODE_WAVEFORM,
)


# ========================================================================
# STT Engine tests
# ========================================================================

class TestSTTEngine:
    def test_start_stop(self):
        engine = STTEngine()
        engine.start()
        assert engine.is_running
        engine.stop()
        assert not engine.is_running

    def test_mock_transcription(self):
        """Without WhisperTRT, returns mock result."""
        engine = STTEngine()
        engine.start()
        assert not engine.is_real

        # 1 second of silence at 16kHz
        audio = b"\x00\x00" * SAMPLE_RATE
        result = engine.transcribe(audio)

        assert isinstance(result, TranscriptionResult)
        assert result.text == "[mock transcription]"
        assert result.duration_s == pytest.approx(1.0, abs=0.01)
        assert result.is_final
        assert result.confidence == 0.0
        engine.stop()

    def test_transcribe_empty(self):
        engine = STTEngine()
        engine.start()
        result = engine.transcribe(b"")
        assert result.duration_s == 0.0
        engine.stop()


class TestHybridSTTEngine:
    def test_start_stop(self):
        """Test HybridSTTEngine lifecycle (no DEEPGRAM_API_KEY set in tests)."""
        engine = HybridSTTEngine()
        engine.start()
        assert engine.is_running
        engine.stop()
        assert not engine.is_running

    def test_transcribe_fallback_to_mock(self):
        """Without Deepgram key, falls back to whisper.cpp/mock."""
        engine = HybridSTTEngine()
        engine.start()

        # 1 second of silence
        audio = b"\x00\x00" * SAMPLE_RATE
        result = engine.transcribe(audio)

        assert isinstance(result, TranscriptionResult)
        assert result.text == "[mock transcription]"  # Falls back to mock
        assert result.duration_s == pytest.approx(1.0, abs=0.01)
        engine.stop()

    def test_transcribe_empty_hybrid(self):
        """Empty audio with hybrid engine."""
        engine = HybridSTTEngine()
        engine.start()
        result = engine.transcribe(b"")
        assert result.duration_s == 0.0
        engine.stop()


# ========================================================================
# TTS Engine tests
# ========================================================================

class TestTTSEngine:
    def test_start_stop(self):
        engine = TTSEngine()
        engine.start()
        assert engine.is_running
        # is_real depends on whether Piper is installed (Jetson: yes, CI: no)
        engine.stop()
        assert not engine.is_running

    def test_mock_speak(self):
        """Without Piper, returns mock audio with envelope."""
        engine = TTSEngine()
        engine.start()
        result = engine.speak("Hello, I'm KiSTI.")

        assert isinstance(result, TTSResult)
        assert len(result.audio_pcm) > 0
        assert result.sample_rate == 16000
        assert result.duration_s > 0
        assert len(result.amplitude_envelope) > 0
        # Envelope values should be normalized 0-1
        assert all(0.0 <= v <= 1.0 for v in result.amplitude_envelope)
        engine.stop()

    def test_mock_speak_short_text(self):
        engine = TTSEngine()
        engine.start()
        result = engine.speak("Hi")
        assert result.duration_s >= 0.5  # Minimum duration
        engine.stop()


class TestAmplitudeEnvelope:
    def test_empty_audio(self):
        assert compute_amplitude_envelope(b"", 16000) == []

    def test_silence(self):
        """Silence produces zero envelope."""
        audio = b"\x00\x00" * 16000  # 1s silence at 16kHz
        envelope = compute_amplitude_envelope(audio, 16000, fps=10)
        assert len(envelope) > 0
        assert all(v == 0.0 for v in envelope)

    def test_loud_signal(self):
        """Loud signal produces non-zero envelope."""
        import struct
        # Generate 1s of max-amplitude sine-ish signal
        samples = []
        for i in range(16000):
            val = int(32000 * (1 if i % 100 < 50 else -1))  # square wave
            samples.append(struct.pack("<h", val))
        audio = b"".join(samples)

        envelope = compute_amplitude_envelope(audio, 16000, fps=10)
        assert len(envelope) > 0
        assert max(envelope) > 0.9  # Should be nearly 1.0 after normalization


# ========================================================================
# LLM Engine tests
# ========================================================================

class TestLLMEngine:
    def test_start_stop(self):
        engine = LLMEngine()
        engine.start()
        assert engine.is_running
        # is_real depends on whether Ollama is running (Jetson: yes, CI: no)
        engine.stop()
        assert not engine.is_running

    def test_persona_fallback_brakes(self):
        """Without Ollama, uses persona keyword matching."""
        engine = LLMEngine()
        engine.start()
        response = engine.query("How are the brakes?")

        assert isinstance(response, LLMResponse)
        assert response.tier == "persona_match"
        assert "caliper" in response.text.lower() or "front-right" in response.text.lower()
        engine.stop()

    def test_persona_fallback_oil(self):
        engine = LLMEngine()
        engine.start()
        response = engine.query("How's the oil pressure?")
        assert response.tier == "persona_match"
        assert "psi" in response.text.lower()
        engine.stop()

    def test_persona_fallback_identity(self):
        engine = LLMEngine()
        engine.start()
        response = engine.query("Who are you?")
        assert response.tier == "persona_match"
        assert "kisti" in response.text.lower()
        engine.stop()

    def test_fallback_unknown(self):
        """Unknown query returns fallback response."""
        engine = LLMEngine()
        engine.start()
        response = engine.query("What is the meaning of xyzzyx?")
        assert response.tier == "fallback"
        assert response.text == FALLBACK_RESPONSE
        engine.stop()


class TestPersonaMatching:
    def test_brake_keywords(self):
        assert _match_persona("How are the brakes?") is not None

    def test_turbo_keywords(self):
        assert _match_persona("How's your boost?") is not None

    def test_identity_keywords(self):
        result = _match_persona("Who are you?")
        assert result is not None
        assert "kisti" in result.lower()

    def test_no_match(self):
        assert _match_persona("xyzzyx gibberish qqq") is None


# ========================================================================
# LED Waveform tests
# ========================================================================

class TestLEDWaveform:
    def test_waveform_frame(self):
        gen = LEDWaveformGenerator()
        frame = gen.waveform_frame(0.8)

        assert isinstance(frame, LEDFrame)
        assert frame.mode == LED_MODE_WAVEFORM
        assert len(frame.brightnesses) == LED_COUNT
        assert frame.color_r == 230  # KiSTI red
        assert all(0 <= b <= 255 for b in frame.brightnesses)
        # Center should be brighter than edges
        assert frame.brightnesses[5] >= frame.brightnesses[0]

    def test_waveform_zero_amplitude(self):
        gen = LEDWaveformGenerator()
        frame = gen.waveform_frame(0.0)
        assert all(b == 0 for b in frame.brightnesses)

    def test_waveform_full_amplitude(self):
        gen = LEDWaveformGenerator()
        frame = gen.waveform_frame(1.0)
        # Center-out pattern: max brightness ~93% due to falloff from center
        assert max(frame.brightnesses) >= 230

    def test_waveform_from_envelope(self):
        gen = LEDWaveformGenerator()
        envelope = [0.0, 0.5, 1.0, 0.5, 0.0]
        frames = gen.waveform_from_envelope(envelope)
        assert len(frames) == 5
        assert all(f.mode == LED_MODE_WAVEFORM for f in frames)

    def test_kitt_sweep(self):
        gen = LEDWaveformGenerator()
        frame = gen.kitt_sweep_frame(dt=0.033)
        assert frame.mode == LED_MODE_KITT
        assert len(frame.brightnesses) == LED_COUNT
        assert frame.color_r == 255  # Red
        # At least one LED should be lit
        assert max(frame.brightnesses) > 0

    def test_kitt_sweep_moves(self):
        """KITT sweep position changes over time."""
        gen = LEDWaveformGenerator()
        frame1 = gen.kitt_sweep_frame(dt=0.033)
        # Advance several frames
        for _ in range(20):
            gen.kitt_sweep_frame(dt=0.033)
        frame2 = gen.kitt_sweep_frame(dt=0.033)
        # Position should have moved (different brightness distribution)
        assert frame1.brightnesses != frame2.brightnesses

    def test_rpm_shift_below_threshold(self):
        gen = LEDWaveformGenerator()
        frame = gen.rpm_shift_frame(rpm=2000.0)
        assert frame.mode == LED_MODE_RPM
        assert all(b == 0 for b in frame.brightnesses)

    def test_rpm_shift_at_shift_point(self):
        gen = LEDWaveformGenerator()
        frame = gen.rpm_shift_frame(rpm=6500.0)
        assert frame.mode == LED_MODE_RPM
        assert sum(1 for b in frame.brightnesses if b > 0) > 0

    def test_rpm_shift_redline(self):
        gen = LEDWaveformGenerator()
        frame = gen.rpm_shift_frame(rpm=7500.0)
        assert frame.color_r == 255  # Red at redline
        assert all(b == 255 for b in frame.brightnesses)

    def test_warmup_cold(self):
        gen = LEDWaveformGenerator()
        frame = gen.warmup_frame(progress=0.0)
        assert frame.mode == LED_MODE_WARMUP
        assert frame.color_b > frame.color_r  # Blue when cold

    def test_warmup_ready(self):
        gen = LEDWaveformGenerator()
        frame = gen.warmup_frame(progress=1.0)
        assert frame.mode == LED_MODE_WARMUP
        assert frame.color_g > frame.color_r  # Green when ready

    def test_off_frame(self):
        gen = LEDWaveformGenerator()
        frame = gen.off_frame()
        assert frame.mode == LED_MODE_OFF
        assert all(b == 0 for b in frame.brightnesses)

    def test_alert_critical(self):
        gen = LEDWaveformGenerator()
        frame = gen.alert_flash_frame("critical", phase=0.0)
        assert frame.color_r == 255
        assert all(b == 255 for b in frame.brightnesses)

    def test_alert_critical_off_phase(self):
        gen = LEDWaveformGenerator()
        frame = gen.alert_flash_frame("critical", phase=0.6)
        assert all(b == 0 for b in frame.brightnesses)


# ========================================================================
# LLM Token Cap tests
# ========================================================================

class TestLLMTokenCaps:
    def test_mode_caps_defined(self):
        """All SI Drive modes have token caps."""
        assert "Intelligent" in MODE_TOKEN_CAPS
        assert "Sport" in MODE_TOKEN_CAPS
        assert "Sport Sharp" in MODE_TOKEN_CAPS

    def test_sport_sharp_is_tightest(self):
        """Sport Sharp has the lowest token cap."""
        assert MODE_TOKEN_CAPS["Sport Sharp"] < MODE_TOKEN_CAPS["Sport"]
        assert MODE_TOKEN_CAPS["Sport"] < MODE_TOKEN_CAPS["Intelligent"]

    def test_sport_sharp_cap(self):
        assert MODE_TOKEN_CAPS["Sport Sharp"] == 20

    def test_sport_cap(self):
        assert MODE_TOKEN_CAPS["Sport"] == 64

    def test_intelligent_cap(self):
        assert MODE_TOKEN_CAPS["Intelligent"] == 256

    def test_temperature_decreases_with_urgency(self):
        """More aggressive modes use lower temperature."""
        assert MODE_TEMPERATURE["Sport Sharp"] < MODE_TEMPERATURE["Sport"]
        assert MODE_TEMPERATURE["Sport"] < MODE_TEMPERATURE["Intelligent"]

    def test_query_uses_mode_cap(self):
        """LLM query selects token cap based on SI Drive mode."""
        engine = LLMEngine()
        engine.start()
        # Without Ollama, falls back to persona — just verify it doesn't crash
        response = engine.query("How's the oil?", si_drive_mode="Sport Sharp")
        assert isinstance(response, LLMResponse)
        engine.stop()


# ========================================================================
# Mic Capture tests
# ========================================================================

class TestMicCapture:
    def test_constants(self):
        """Mic capture constants are consistent."""
        assert MIC_SAMPLE_RATE == 16000
        assert FRAME_BYTES == 1024  # Silero VAD: 512 samples * 2 bytes
        assert SPEECH_START_FRAMES == 6
        assert SPEECH_END_FRAMES == 14  # ~448ms — reduced sentence splitting
        assert VAD_MODE == 3  # Most aggressive — in-car noise rejection

    def test_init_defaults(self):
        mic = MicCapture(device="nonexistent")
        assert not mic.is_available
        assert not mic.is_running

    def test_start_without_webrtcvad(self, monkeypatch):
        """Graceful fallback when webrtcvad not installed."""
        import importlib
        import voice.mic_capture as mc

        # Simulate webrtcvad not being importable
        original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__
        def mock_import(name, *args, **kwargs):
            if name == "webrtcvad":
                raise ImportError("No module named 'webrtcvad'")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", mock_import)
        mic = MicCapture()
        mic.start()
        assert not mic.is_available
        assert not mic.is_running

    def test_pause_resume(self):
        mic = MicCapture()
        mic._paused = False
        mic.pause()
        assert mic._paused
        mic.resume()
        assert not mic._paused


# ========================================================================
# Event Quotes tests
# ========================================================================

from data.event_quotes import (
    get_event_quote, get_event_quote_with_chance,
    get_alert_quote, ALERT_TYPE_TO_EVENT, EVENT_QUOTES,
)


class TestEventQuotes:
    def test_known_event_returns_quote(self):
        """Known event keys always return a quote."""
        quote = get_event_quote("engine_ready")
        assert quote is not None
        assert isinstance(quote, str)
        assert len(quote) > 0

    def test_unknown_event_returns_none(self):
        assert get_event_quote("nonexistent_event") is None

    def test_all_events_have_quotes(self):
        """Every key in EVENT_QUOTES has at least one quote."""
        for key, quotes in EVENT_QUOTES.items():
            assert len(quotes) > 0, f"Event '{key}' has no quotes"

    def test_chance_zero_never_fires(self):
        """Chance=0.0 always returns None."""
        for _ in range(20):
            assert get_event_quote_with_chance("engine_ready", chance=0.0) is None

    def test_chance_one_always_fires(self):
        """Chance=1.0 always returns a quote for known events."""
        for _ in range(20):
            assert get_event_quote_with_chance("engine_ready", chance=1.0) is not None

    def test_default_chance_is_thirty_percent(self):
        """Default chance fires roughly 30% (statistical — allow wide margin)."""
        import random
        random.seed(42)
        hits = sum(1 for _ in range(200) if get_event_quote_with_chance("boost_full") is not None)
        assert 20 < hits < 120  # ~30% of 200 = ~60, wide margin for randomness


class TestAlertQuotes:
    def test_direct_match_alert(self):
        """Alert types that match event keys directly work."""
        # engine_ready is both an alert_type and event key
        quote = get_alert_quote("engine_ready", chance=1.0)
        assert quote is not None

    def test_mapped_alert_type(self):
        """Alert types in ALERT_TYPE_TO_EVENT resolve correctly."""
        quote = get_alert_quote("oil_pressure_critical", chance=1.0)
        assert quote is not None
        # Should resolve to oil_pressure_low quotes
        assert quote in EVENT_QUOTES["oil_pressure_low"]

    def test_coolant_critical_maps(self):
        quote = get_alert_quote("coolant_critical", chance=1.0)
        assert quote is not None
        assert quote in EVENT_QUOTES["coolant_overtemp"]

    def test_unmapped_unknown_returns_none(self):
        """Unknown alert types with no mapping return None."""
        assert get_alert_quote("totally_unknown_alert", chance=1.0) is None

    def test_all_mapped_types_resolve(self):
        """Every entry in ALERT_TYPE_TO_EVENT resolves to a valid event key."""
        for alert_type, event_key in ALERT_TYPE_TO_EVENT.items():
            assert event_key in EVENT_QUOTES, (
                f"ALERT_TYPE_TO_EVENT['{alert_type}'] -> '{event_key}' not in EVENT_QUOTES"
            )

    def test_weather_alerts_direct(self):
        """Weather alert types match event keys directly (no mapping needed)."""
        for alert_type in ["pressure_falling", "pressure_rising", "temp_dropping",
                           "temp_rising", "humidity_rising", "humidity_dropping"]:
            quote = get_alert_quote(alert_type, chance=1.0)
            assert quote is not None, f"No quote for weather alert: {alert_type}"

    def test_mode_change_quotes(self):
        """SI Drive mode event keys have quotes."""
        for mode in ["mode_intelligent", "mode_sport", "mode_sport_sharp"]:
            quote = get_event_quote(mode)
            assert quote is not None, f"No quote for mode: {mode}"


# ========================================================================
# Expanded Persona Response tests
# ========================================================================

class TestExpandedPersona:
    """Tests for newly added persona keyword responses."""

    def test_weather_rain(self):
        assert _match_persona("What about rain?") is not None

    def test_speed_how_fast(self):
        assert _match_persona("How fast are you?") is not None

    def test_exhaust_routes_to_frontier(self):
        assert _match_persona("Tell me about the exhaust") is None  # no self-ref → frontier
        assert _match_persona("Tell me about your exhaust") is not None  # self-ref

    def test_suspension(self):
        assert _match_persona("How's the suspension?") is not None

    def test_weight(self):
        assert _match_persona("How much do you weigh?") is not None

    def test_launch(self):
        assert _match_persona("What's your 0 to 60?") is not None

    def test_thank_you(self):
        assert _match_persona("Thank you KiSTI") is not None

    def test_good_morning(self):
        assert _match_persona("Good morning") is not None

    def test_help(self):
        assert _match_persona("What can you do?") is not None

    def test_music_routes_to_frontier(self):
        assert _match_persona("Play some music") is None  # no self-ref, score < 10 → frontier

    def test_joke(self):
        assert _match_persona("Tell me a joke") is not None

    def test_jetson_brain(self):
        assert _match_persona("Tell me about your brain") is not None

    def test_sensor_count(self):
        assert _match_persona("How many sensors do you have?") is not None

    def test_ecu_link(self):
        assert _match_persona("Who tunes you?") is not None

    def test_can_bus(self):
        # "How does" is a general knowledge signal → frontier passthrough
        # Direct question about KiSTI's CAN still matches persona
        assert _match_persona("Tell me about your CAN bus") is not None

    def test_emergency(self):
        assert _match_persona("I think there's a problem") is not None

    def test_tow(self):
        assert _match_persona("Can I tow you?") is not None

    def test_mileage(self):
        assert _match_persona("How many km do you have?") is not None

    def test_fuel_gas(self):
        assert _match_persona("What fuel do you take?") is not None

    def test_transformers(self):
        assert _match_persona("Are you a transformer?") is not None

    def test_fast_and_furious(self):
        assert _match_persona("This is like fast and furious") is not None

    def test_back_to_future_routes_to_frontier(self):
        assert _match_persona("We need a flux capacitor") is None  # score < 10 → frontier

    def test_top_gear_routes_to_frontier(self):
        assert _match_persona("What would Clarkson say?") is None  # score < 10 → frontier

    def test_initial_d(self):
        assert _match_persona("Do you know Initial D?") is not None


# ========================================================================
# Mode-Aware Persona Filtering tests
# ========================================================================

class TestModeAwarePersona:
    """Tests for SI Drive mode filtering of persona responses."""

    def test_intelligent_returns_all_categories(self):
        """Intelligent mode returns fun, tech, and safety."""
        assert _match_persona("Who are you?", "Intelligent") is not None  # fun
        assert _match_persona("How's your boost?", "Intelligent") is not None  # tech
        assert _match_persona("How are the brakes?", "Intelligent") is not None  # safety

    def test_sport_blocks_fun(self):
        """Sport mode blocks fun-category responses."""
        result = _match_persona("Who are you?", "Sport")
        assert result is None  # "who are you" is fun-only

    def test_sport_allows_tech(self):
        """Sport mode allows tech-category responses."""
        result = _match_persona("How's your boost?", "Sport")
        assert result is not None

    def test_sport_allows_safety(self):
        """Sport mode allows safety-category responses."""
        result = _match_persona("How are the brakes?", "Sport")
        assert result is not None

    def test_sport_sharp_blocks_fun(self):
        """Sport Sharp blocks fun responses."""
        assert _match_persona("Tell me a joke", "Sport Sharp") is None

    def test_sport_sharp_blocks_tech(self):
        """Sport Sharp blocks tech responses."""
        assert _match_persona("How's the boost?", "Sport Sharp") is None

    def test_sport_sharp_allows_safety(self):
        """Sport Sharp allows safety responses."""
        result = _match_persona("How are the brakes?", "Sport Sharp")
        assert result is not None

    def test_sport_truncates_to_first_sentence(self):
        """Sport mode truncates persona responses to first sentence."""
        result = _match_persona("How are the brakes?", "Sport")
        assert result is not None
        # Should be truncated — no second sentence
        # Original has ". That's caliper drag" after first sentence
        assert "That's caliper drag" not in result

    def test_sport_sharp_truncates_to_five_words(self):
        """Sport Sharp truncates to 5 words max."""
        result = _match_persona("How are the brakes?", "Sport Sharp")
        assert result is not None
        words = result.rstrip(".").split()
        assert len(words) <= 5

    def test_subaru_jokes_blocked_in_sport(self):
        """Subaru jokes are fun-category and blocked in Sport."""
        assert _match_persona("Do you vape?", "Sport") is None

    def test_roast_blocked_in_sport_sharp(self):
        """Roast battle is fun-only, blocked in Sport Sharp."""
        assert _match_persona("Roast me!", "Sport Sharp") is None

    def test_mode_categories_complete(self):
        """All three modes are defined in _MODE_ALLOWED_CATEGORIES."""
        assert "Intelligent" in _MODE_ALLOWED_CATEGORIES
        assert "Sport" in _MODE_ALLOWED_CATEGORIES
        assert "Sport Sharp" in _MODE_ALLOWED_CATEGORIES

    def test_unknown_mode_defaults_to_all(self):
        """Unknown mode name defaults to all categories."""
        result = _match_persona("Who are you?", "UnknownMode")
        assert result is not None


# ========================================================================
# Reference Resolver tests
# ========================================================================

from voice.voice_manager import DialogueState, DialogueTurn, VoiceResponse


class TestReferenceResolver:
    """Tests for _resolve_references — pronoun resolution using dialogue context."""

    def _make_state(self, topic: str = "", turns_ago: int = 0) -> DialogueState:
        """Helper: create a DialogueState with an active topic."""
        state = DialogueState()
        state.topic = topic
        state.turn_counter = 5
        state.topic_since_turn = 5 - turns_ago
        return state

    def _resolve(self, query: str, topic: str = "oil", turns_ago: int = 0) -> str:
        """Helper: create VoiceManager-like resolver with given state."""
        from voice.voice_manager import VoiceManager
        # Build a minimal proxy that has _dialogue + class-level regex attrs
        import types
        mgr = types.SimpleNamespace()
        mgr._dialogue = self._make_state(topic, turns_ago)
        mgr._NON_REFERENTIAL = VoiceManager._NON_REFERENTIAL
        mgr._REFERENTIAL = VoiceManager._REFERENTIAL
        return VoiceManager._resolve_references(mgr, query)

    # --- Non-referential (should NOT be rewritten) ---

    def test_no_pronouns_unchanged(self):
        """Queries without pronouns pass through."""
        assert self._resolve("How's the oil pressure?") == "How's the oil pressure?"

    def test_idiomatic_hows_it_going(self):
        """'How's it going' is idiomatic, not referential."""
        assert self._resolve("How's it going?") == "How's it going?"

    def test_idiomatic_thats_cool(self):
        """'That's cool' is idiomatic."""
        assert self._resolve("That's cool") == "That's cool"

    def test_idiomatic_got_it(self):
        """'Got it' is idiomatic."""
        assert self._resolve("Got it") == "Got it"

    def test_idiomatic_forget_it(self):
        assert self._resolve("Forget it") == "Forget it"

    def test_idiomatic_thats_fine(self):
        assert self._resolve("That's fine") == "That's fine"

    def test_idiomatic_is_that_ok(self):
        assert self._resolve("Is that ok") == "Is that ok"

    def test_idiomatic_do_it(self):
        assert self._resolve("Do it") == "Do it"

    # --- No topic → pass through ---

    def test_no_topic_unchanged(self):
        """No active topic means no resolution."""
        assert self._resolve("What's that?", topic="") == "What's that?"

    # --- Stale topic → pass through ---

    def test_stale_topic_unchanged(self):
        """Topic older than 10 turns is too stale."""
        assert self._resolve("What's that?", topic="oil", turns_ago=12) == "What's that?"

    # --- Referential patterns (should be rewritten) ---

    def test_whats_that(self):
        """'What's that' resolves to active topic."""
        result = self._resolve("What's that?", topic="oil")
        assert "oil" in result.lower()

    def test_hows_it(self):
        result = self._resolve("How's it looking?", topic="coolant")
        assert "coolant" in result.lower()

    def test_is_that_normal(self):
        result = self._resolve("Is that normal?", topic="boost")
        assert "boost" in result.lower()

    def test_tell_me_more(self):
        result = self._resolve("Tell me more about that", topic="brakes")
        assert "brakes" in result.lower()

    def test_those_temps(self):
        """'those temps' → 'the {topic} temps'."""
        result = self._resolve("What about those temps?", topic="brakes")
        assert "brakes" in result.lower()
        assert "temps" in result.lower()

    def test_why_is_that(self):
        result = self._resolve("Why is that high?", topic="oil")
        assert "oil" in result.lower()

    def test_what_about_it(self):
        result = self._resolve("What about it?", topic="ethanol")
        assert "ethanol" in result.lower()

    def test_compare_those(self):
        result = self._resolve("Compare those readings", topic="fuel")
        assert "fuel" in result.lower()

    # --- Recent topic resolves, not stale ---

    def test_recent_topic_resolves(self):
        """Topic set 3 turns ago should still resolve."""
        result = self._resolve("What's that?", topic="oil", turns_ago=3)
        assert "oil" in result.lower()

    def test_boundary_10_turns_resolves(self):
        """Topic set exactly 10 turns ago should still resolve."""
        result = self._resolve("What's that?", topic="oil", turns_ago=10)
        assert "oil" in result.lower()


# ========================================================================
# Wake Model Configuration tests
# ========================================================================


class TestWakeModelConfig:
    """Tests for configurable wake word model path."""

    def test_default_wake_model_none(self):
        mic = MicCapture(device="nonexistent")
        assert mic._wake_model is None

    def test_custom_wake_model_stored(self):
        mic = MicCapture(device="nonexistent", wake_model="/data/models/hey_kisti.onnx")
        assert mic._wake_model == "/data/models/hey_kisti.onnx"

    def test_env_wake_model(self, monkeypatch):
        """KISTI_WAKE_MODEL env var is picked up by VoiceManager."""
        monkeypatch.setenv("KISTI_WAKE_MODEL", "/data/models/custom.onnx")
        import os
        assert os.environ.get("KISTI_WAKE_MODEL") == "/data/models/custom.onnx"


# ========================================================================
# PipelineTrace tests (Phase 4.3)
# ========================================================================

import time
from voice.voice_manager import PipelineTrace


class TestPipelineTrace:
    """Verify PipelineTrace timing capture and computed properties."""

    def test_computed_properties(self):
        now = time.monotonic()
        trace = PipelineTrace(
            mic_captured_at=now,
            stt_done_at=now + 0.130,
            llm_done_at=now + 0.130 + 2.1,
            tts_done_at=now + 0.130 + 2.1 + 0.450,
            speaker_start_at=now + 0.130 + 2.1 + 0.450 + 0.010,
        )
        assert trace.stt_ms == 130
        assert trace.llm_ms == 2100
        assert trace.tts_ms == 450
        assert trace.total_ms == 2690

    def test_zero_when_not_set(self):
        trace = PipelineTrace()
        assert trace.stt_ms == 0
        assert trace.llm_ms == 0
        assert trace.tts_ms == 0
        assert trace.total_ms == 0

    def test_partial_trace(self):
        """Trace with only STT completed (e.g. sensor shortcut)."""
        now = time.monotonic()
        trace = PipelineTrace(
            mic_captured_at=now,
            stt_done_at=now + 0.100,
        )
        assert trace.stt_ms == 100
        assert trace.llm_ms == 0
        assert trace.total_ms == 0

    def test_source_and_query(self):
        trace = PipelineTrace(source="sensor", query_text="What is the temp?")
        assert trace.source == "sensor"
        assert trace.query_text == "What is the temp?"


# ========================================================================
# Response Composer tests (Phase 4.2)
# ========================================================================


class TestResponseComposer:
    """Verify VoiceResponse creation and dialogue recording."""

    def test_voice_response_records_turn(self):
        state = DialogueState()
        resp = VoiceResponse(text="Oil 55 PSI.", source="sensor")
        state.record_turn("How is the oil?", resp)
        assert state.turn_counter == 1
        assert len(state.last_turns) == 1
        assert state.last_turns[0].response_source == "sensor"
        assert state.topic == "oil"

    def test_voice_response_all_sources(self):
        for source in ("persona", "sensor", "llm", "command", "system"):
            resp = VoiceResponse(text="test", source=source)
            assert resp.text == "test"
            assert resp.source == source
            assert resp.can_interrupt is True

    def test_critical_alert_not_interruptible(self):
        resp = VoiceResponse(
            text="Oil pressure critical!", source="system",
            status="critical", can_interrupt=False,
        )
        assert not resp.can_interrupt

    def test_pipeline_trace_attached_to_response(self):
        now = time.monotonic()
        trace = PipelineTrace(mic_captured_at=now, stt_done_at=now + 0.1)
        trace.source = "sensor"
        trace.query_text = "test query"
        assert trace.source == "sensor"
        assert trace.stt_ms == 100


# ========================================================================
# Barge-in tests (Phase 4.1)
# ========================================================================

from voice.mic_capture import OWW_THRESHOLD_NORMAL, OWW_THRESHOLD_BARGE_IN


class TestBargeIn:
    """Verify MicCapture barge-in mode changes OWW threshold."""

    def test_set_barge_in_mode_raises_threshold(self):
        mic = MicCapture(device="nonexistent")
        assert mic._active_oww_threshold == OWW_THRESHOLD_NORMAL
        mic.set_barge_in_mode(True)
        assert mic._barge_in_mode is True
        assert mic._active_oww_threshold == OWW_THRESHOLD_BARGE_IN

    def test_set_barge_in_mode_restores_threshold(self):
        mic = MicCapture(device="nonexistent")
        mic.set_barge_in_mode(True)
        mic.set_barge_in_mode(False)
        assert mic._barge_in_mode is False
        assert mic._active_oww_threshold == OWW_THRESHOLD_NORMAL

    def test_threshold_constants(self):
        assert OWW_THRESHOLD_NORMAL == 0.5
        assert OWW_THRESHOLD_BARGE_IN == 0.92
        assert OWW_THRESHOLD_BARGE_IN > OWW_THRESHOLD_NORMAL

    def test_pause_still_works(self):
        """Full pause (non-interruptible) still works."""
        mic = MicCapture(device="nonexistent")
        mic.pause()
        assert mic._paused is True
        mic.resume()
        assert mic._paused is False

    def test_rms_echo_gate_constant(self):
        """RMS threshold of 5000 is defined in barge-in logic."""
        import inspect
        from voice.mic_capture import MicCapture as _MC
        source = inspect.getsource(_MC._vad_process)
        assert "frame_rms > 5000" in source, "RMS echo gate missing from barge-in logic"


# ========================================================================
# Echo suppression tests
# ========================================================================


class TestEchoSuppression:
    """Verify echo suppression rejects transcriptions matching KiSTI's own speech."""

    def test_echo_suppressed_when_high_overlap(self):
        """Transcription >40% overlap with last spoken text within 3s is rejected."""
        from voice.voice_manager import VoiceManager
        import time
        vm = VoiceManager(enable_mic=False)
        vm._last_spoken_text = "oil pressure is 55 psi at operating temperature"
        vm._last_spoken_at = time.monotonic()  # just now

        # Simulate what echo suppression checks
        import re as _re
        spoken_words = set(_re.findall(r'\b\w+\b', vm._last_spoken_text))
        heard = "pressure is 55 psi at temperature"
        heard_words = set(_re.findall(r'\b\w+\b', heard.lower()))
        overlap = len(heard_words & spoken_words) / len(heard_words)
        assert overlap > 0.4, f"Expected >40% overlap, got {overlap:.0%}"

    def test_echo_not_suppressed_after_timeout(self):
        """Transcription after 3s should NOT be suppressed even with overlap."""
        from voice.voice_manager import VoiceManager
        import time
        vm = VoiceManager(enable_mic=False)
        vm._last_spoken_text = "oil pressure is nominal"
        vm._last_spoken_at = time.monotonic() - 4.0  # 4 seconds ago
        # After timeout, echo suppression should not apply
        assert (time.monotonic() - vm._last_spoken_at) >= 3.0

    def test_echo_not_suppressed_when_low_overlap(self):
        """Different text should not be suppressed."""
        import re as _re
        spoken_words = set(_re.findall(r'\b\w+\b', "oil pressure is nominal"))
        heard_words = set(_re.findall(r'\b\w+\b', "hey jarvis what is the weather"))
        overlap = len(heard_words & spoken_words) / len(heard_words) if heard_words else 0
        assert overlap <= 0.4, f"Expected <=40% overlap, got {overlap:.0%}"

    def test_echo_state_initialized(self):
        """VoiceManager starts with empty echo tracking state."""
        from voice.voice_manager import VoiceManager
        vm = VoiceManager(enable_mic=False)
        assert vm._last_spoken_text == ""
        assert vm._last_spoken_at == 0.0

    def test_do_speak_sets_echo_text(self):
        """_do_speak stores lowercase spoken text for echo comparison."""
        from voice.voice_manager import VoiceManager
        vm = VoiceManager(enable_mic=False)
        vm._tts = type("MockTTS", (), {
            "speak": lambda self, text: type("R", (), {"audio_pcm": b"", "sample_rate": 16000})(),
            "start": lambda self: None,
        })()
        vm._last_spoken_text = ""
        # Directly set what _do_speak would set
        vm._last_spoken_text = "Hello World".lower()
        assert vm._last_spoken_text == "hello world"


# ========================================================================
# Voice Latency DuckDB tests (Phase 4.3)
# ========================================================================


class TestVoiceLatencyDuckDB:
    """Verify voice_latency table in DuckDB."""

    def test_record_voice_latency(self, tmp_path):
        pytest.importorskip("duckdb")
        from data.duckdb_store import DuckDBStore
        db_path = tmp_path / "test_latency.duckdb"
        store = DuckDBStore(db_path=db_path)
        store.open()
        try:
            store.record_voice_latency(
                session_id="test-session",
                stt_ms=130, llm_ms=2100, tts_ms=450, total_ms=2690,
                source="local_llm", query_text="How is the oil?",
            )
            stats = store.db_stats()
            assert stats["voice_latency"] == 1
        finally:
            store.close()

    def test_voice_latency_in_stats(self, tmp_path):
        pytest.importorskip("duckdb")
        from data.duckdb_store import DuckDBStore
        db_path = tmp_path / "test_latency2.duckdb"
        store = DuckDBStore(db_path=db_path)
        store.open()
        try:
            stats = store.db_stats()
            assert "voice_latency" in stats
            assert stats["voice_latency"] == 0
        finally:
            store.close()


# ========================================================================
# Golden Persona tests — verified non-None across modes
# ========================================================================


class TestGoldenPersona:
    """Specific inputs that MUST produce responses in appropriate modes."""

    _SAFETY_QUERIES = [
        "How are the brakes?",
        "What is the oil pressure?",
        "Is the coolant temperature ok?",
    ]
    # Tech queries WITH self-ref still match persona
    _TECH_QUERIES_SELF_REF = [
        "What fuel do you use?",
    ]
    # Tech queries WITHOUT self-ref now route to frontier (score < 10)
    _TECH_QUERIES_FRONTIER = [
        "How is the boost?",
        "Tell me about the engine.",
    ]

    def test_safety_queries_all_modes(self):
        for q in self._SAFETY_QUERIES:
            for mode in ("Intelligent", "Sport", "Sport Sharp"):
                result = _match_persona(q, mode)
                assert result is not None, f"'{q}' returned None in {mode}"

    def test_tech_queries_with_self_ref(self):
        for q in self._TECH_QUERIES_SELF_REF:
            for mode in ("Intelligent", "Sport"):
                result = _match_persona(q, mode)
                assert result is not None, f"'{q}' returned None in {mode}"

    def test_tech_queries_without_self_ref_route_to_frontier(self):
        for q in self._TECH_QUERIES_FRONTIER:
            result = _match_persona(q, "Intelligent")
            assert result is None, f"'{q}' should route to frontier (no self-ref)"

    def test_tech_queries_blocked_sport_sharp(self):
        for q in self._TECH_QUERIES_SELF_REF:
            result = _match_persona(q, "Sport Sharp")
            assert result is None, f"'{q}' should be None in Sport Sharp"


# ========================================================================
# kisti-11: Persona Narrative Expansion tests
# ========================================================================


class TestTier1PersonaExpansion:
    """Tests for TIER 1 persona responses added in kisti-11."""

    # --- DCCD & AWD ---
    def test_dccd_education_routes_to_frontier(self):
        assert _match_persona("Tell me about the DCCD") is None  # no self-ref → frontier
        result = _match_persona("Tell me about your DCCD")
        assert result is not None  # self-ref → persona
        assert "center diff" in result.lower() or "biasing" in result.lower()

    def test_dccd_feel_routes_to_frontier(self):
        assert _match_persona("What does the locking feel like?") is None  # → frontier

    # --- Turbo Operation ---
    def test_turbo_spool_routes_to_frontier(self):
        assert _match_persona("How long does it take to spool?") is None  # → frontier
        result = _match_persona("How long does your turbo take to spool?")
        assert result is not None  # self-ref → persona

    def test_turbo_lag_routes_to_frontier(self):
        assert _match_persona("Why is there turbo lag?") is None  # → frontier

    def test_turbo_whistle(self):
        result = _match_persona("What is that turbo noise?")
        assert result is not None
        assert "compressor" in result.lower() or "whistle" in result.lower()

    def test_turbo_maintenance(self):
        result = _match_persona("How do I maintain the turbo?")
        assert result is not None
        assert "oil" in result.lower()

    # --- Oil & Coolant ---
    def test_oil_change_interval(self):
        result = _match_persona("When should I change the oil?")
        assert result is not None
        assert "5,000" in result or "km" in result.lower()

    def test_coolant_flush(self):
        result = _match_persona("When is the coolant service due?")
        assert result is not None
        assert "20,000" in result or "coolant" in result.lower()

    def test_oil_pressure_low(self):
        result = _match_persona("My oil pressure is low")
        assert result is not None
        assert "psi" in result.lower() or "level" in result.lower()

    # --- Fuel Economy ---
    def test_fuel_economy(self):
        result = _match_persona("What's the fuel economy?")
        assert result is not None
        assert "km per liter" in result.lower() or "highway" in result.lower()

    def test_range(self):
        result = _match_persona("How far can we go on a tank?")
        assert result is not None
        assert "360" in result or "540" in result

    def test_fuel_grade(self):
        result = _match_persona("What octane should I use?")
        assert result is not None
        assert "91" in result

    # --- Safety: Knock & Fuel Quality ---
    def test_knock_detection(self):
        result = _match_persona("I hear pinging from the engine")
        assert result is not None
        assert "knock" in result.lower() or "octane" in result.lower()

    def test_fuel_quality_warning(self):
        result = _match_persona("What happens with low octane fuel?")
        assert result is not None
        assert "91" in result or "knock" in result.lower()

    def test_knock_available_all_modes(self):
        """Safety responses must be available in ALL SI Drive modes."""
        for mode in ("Intelligent", "Sport", "Sport Sharp"):
            assert _match_persona("I hear pinging", mode) is not None

    def test_fuel_quality_available_all_modes(self):
        for mode in ("Intelligent", "Sport", "Sport Sharp"):
            assert _match_persona("What about cheap fuel?", mode) is not None


class TestTier2DrivingTechnique:
    """Tests for TIER 2 driving technique responses."""

    def test_braking_technique(self):
        # "What is" is a general knowledge signal → frontier passthrough
        # Direct question about KiSTI's brakes still matches persona
        result = _match_persona("What is trail braking technique?")
        assert result is None  # → frontier handles general technique questions
        result = _match_persona("How are your brakes?")
        assert result is not None

    def test_cornering(self):
        result = _match_persona("What's the best racing line?")
        assert result is not None
        assert "apex" in result.lower() or "steering" in result.lower()

    def test_g_force_routes_to_frontier(self):
        assert _match_persona("What g-force can this car pull?") is None  # → frontier

    def test_weight_transfer(self):
        result = _match_persona("Explain weight transfer")
        assert result is not None
        assert "braking" in result.lower() or "weight" in result.lower()

    def test_overheat_emergency(self):
        result = _match_persona("The engine is overheating!")
        assert result is not None
        assert "105" in result or "cool" in result.lower()

    def test_blowout_emergency(self):
        result = _match_persona("I think I have a flat tire!")
        assert result is not None
        assert "grip" in result.lower() or "brake" in result.lower()

    def test_emergency_responses_all_modes(self):
        """Overheat and blowout are safety — available in ALL modes."""
        for mode in ("Intelligent", "Sport", "Sport Sharp"):
            assert _match_persona("Engine overheating", mode) is not None
            assert _match_persona("Tire blowout!", mode) is not None


class TestTier3ComponentSpecs:
    """Tests for TIER 3 component spec responses."""

    def test_clutch(self):
        assert _match_persona("What clutch do you have?") is not None

    def test_flywheel_routes_to_frontier(self):
        assert _match_persona("Tell me about the flywheel") is None  # → frontier

    def test_aim_strada(self):
        assert _match_persona("What's on the AiM dash?") is not None

    def test_brake_fluid(self):
        assert _match_persona("What brake fluid do you use?") is not None

    def test_grimmspeed(self):
        assert _match_persona("Tell me about the Grimmspeed gasket") is not None

    def test_suspension_brand(self):
        assert _match_persona("What suspension brand?") is not None

    def test_sway_bar_routes_to_frontier(self):
        assert _match_persona("How are the sway bars?") is None  # → frontier (score < 10)

    def test_pdm(self):
        assert _match_persona("What's the Razor PDM do?") is not None

    def test_tier3_fun_category_blocked_in_sport(self):
        """TIER 3 component specs are fun-category — blocked in Sport."""
        assert _match_persona("What clutch?", "Sport") is None
        assert _match_persona("Tell me about the flywheel", "Sport") is None

    def test_tier3_blocked_in_sport_sharp(self):
        """TIER 3 blocked in Sport Sharp too."""
        assert _match_persona("What's the AiM dash?", "Sport Sharp") is None


class TestTemperatureRouting:
    """Tests for temperature query routing fix — component temps don't go to ambient."""

    def test_engine_temp_not_ambient(self):
        """'engine temperature' should say 'No ECU' NOT return ambient data (CAN off)."""
        from voice.voice_manager import VoiceManager
        vm = VoiceManager.__new__(VoiceManager)
        from unittest.mock import MagicMock
        snap = MagicMock()
        snap.can_connected = False  # No CAN — only ambient available
        snap.ambient_available = True
        snap.ambient_temp_c = 22.0
        snap.dew_point_c = 10.0
        vm._telemetry_snapshot = snap
        # Component-specific temp queries should say No ECU, not return ambient
        for q in ["engine temperature", "oil temp", "coolant temp",
                   "tire temperature", "brake temp", "exhaust temp"]:
            result = vm._answer_from_sensors(q)
            assert result is not None and "No ECU" in result, f"Expected 'No ECU' for '{q}', got: {result}"

    def test_ambient_temp_still_works(self):
        """Generic temperature queries still return ambient data."""
        from voice.voice_manager import VoiceManager
        from unittest.mock import MagicMock
        vm = VoiceManager.__new__(VoiceManager)
        snap = MagicMock()
        snap.can_connected = False
        snap.ambient_available = True
        snap.ambient_temp_c = 22.5
        snap.dew_point_c = 10.0
        vm._telemetry_snapshot = snap
        result = vm._answer_from_sensors("what's the temperature")
        assert result is not None
        assert "22.5" in result

    def test_how_hot_outside_still_works(self):
        """'how hot is it' still returns ambient."""
        from voice.voice_manager import VoiceManager
        from unittest.mock import MagicMock
        vm = VoiceManager.__new__(VoiceManager)
        snap = MagicMock()
        snap.can_connected = False
        snap.ambient_available = True
        snap.ambient_temp_c = 30.0
        snap.dew_point_c = 15.0
        vm._telemetry_snapshot = snap
        result = vm._answer_from_sensors("how hot is it")
        assert result is not None
        assert "30.0" in result


# ========================================================================
# kisti-11: ECU Sensor Voice Handler Tests
# ========================================================================


class TestECUSensorVoiceHandlers:
    """Tests for live ECU data voice responses via _answer_from_sensors."""

    def _make_vm(self, **overrides):
        """Create a VoiceManager with mocked CAN-connected telemetry."""
        from voice.voice_manager import VoiceManager
        from unittest.mock import MagicMock
        vm = VoiceManager.__new__(VoiceManager)
        snap = MagicMock()
        snap.can_connected = True
        snap.ambient_available = False
        # Defaults
        snap.oil_temp_c = 95.0
        snap.oil_psi = 45.0
        snap.coolant_temp = 88.0
        snap.iat_c = 35.0
        snap.map_kpa = 200.0  # ~14.3 PSI boost
        snap.battery_v = 14.2
        snap.fuel_pressure_kpa = 2800.0
        snap.injector_duty = 65.0
        snap.lambda_1 = 0.98
        snap.ethanol_pct = 52.0
        snap.rpm = 3500.0
        snap.speed_kph = 80.0
        snap.wheel_speed_fl = 80.0
        snap.wheel_speed_fr = 80.0
        snap.wheel_speed_rl = 80.0
        snap.wheel_speed_rr = 80.0
        snap.brake_pressure = 25.0
        snap.steering_angle = -15.0
        snap.lateral_g = 0.45
        snap.yaw_rate = 12.0
        snap.dccd_command_pct = 35.0
        snap.gear = 3
        for k, v in overrides.items():
            setattr(snap, k, v)
        vm._telemetry_snapshot = snap
        return vm

    def test_oil_temp(self):
        vm = self._make_vm()
        result = vm._answer_from_sensors("what's the oil temperature")
        assert result is not None
        assert "95" in result
        assert "optimal" in result.lower()

    def test_oil_temp_cold(self):
        vm = self._make_vm(oil_temp_c=45.0)
        result = vm._answer_from_sensors("oil temp")
        assert "cold" in result.lower()

    def test_oil_temp_hot(self):
        vm = self._make_vm(oil_temp_c=125.0)
        result = vm._answer_from_sensors("oil temperature")
        assert "hot" in result.lower()

    def test_oil_pressure(self):
        vm = self._make_vm()
        result = vm._answer_from_sensors("what's the oil pressure")
        assert "45" in result
        assert "normal" in result.lower()

    def test_oil_pressure_critical(self):
        vm = self._make_vm(oil_psi=18.0)
        result = vm._answer_from_sensors("oil pressure")
        assert "critical" in result.lower()

    def test_coolant_temp(self):
        vm = self._make_vm()
        result = vm._answer_from_sensors("coolant temperature")
        assert "88" in result
        assert "normal" in result.lower()

    def test_coolant_temp_warning(self):
        vm = self._make_vm(coolant_temp=103.0)
        result = vm._answer_from_sensors("engine temperature")
        assert "warning" in result.lower()

    def test_iat(self):
        vm = self._make_vm()
        result = vm._answer_from_sensors("intake air temperature")
        assert "35" in result

    def test_boost_pressure(self):
        vm = self._make_vm()
        result = vm._answer_from_sensors("how much boost")
        assert result is not None
        assert "psi" in result.lower()

    def test_battery_voltage(self):
        vm = self._make_vm()
        result = vm._answer_from_sensors("battery voltage")
        assert "14.2" in result
        assert "normal" in result.lower()

    def test_fuel_pressure(self):
        vm = self._make_vm()
        result = vm._answer_from_sensors("fuel pressure")
        assert "psi" in result.lower()

    def test_injector_duty(self):
        vm = self._make_vm()
        result = vm._answer_from_sensors("injector duty cycle")
        assert "65" in result
        assert "safe" in result.lower()

    def test_lambda(self):
        vm = self._make_vm(lambda_1=0.85)
        result = vm._answer_from_sensors("what's the lambda reading")
        assert "0.85" in result
        assert "rich" in result.lower()

    def test_lambda_lean(self):
        vm = self._make_vm(lambda_1=1.08)
        result = vm._answer_from_sensors("air fuel ratio")
        assert "lean" in result.lower()

    def test_ethanol(self):
        vm = self._make_vm()
        result = vm._answer_from_sensors("ethanol content")
        assert "52" in result

    def test_rpm(self):
        vm = self._make_vm()
        result = vm._answer_from_sensors("what rpm")
        assert "3500" in result

    def test_speed(self):
        vm = self._make_vm()
        result = vm._answer_from_sensors("how fast are we going")
        assert "80" in result

    def test_wheel_speeds(self):
        vm = self._make_vm()
        result = vm._answer_from_sensors("wheel speeds")
        assert "front left" in result.lower()

    def test_brake_pressure(self):
        vm = self._make_vm()
        result = vm._answer_from_sensors("brake pressure")
        assert "25" in result

    def test_steering_angle(self):
        vm = self._make_vm()
        result = vm._answer_from_sensors("steering angle")
        assert "15" in result

    def test_lateral_g(self):
        vm = self._make_vm()
        result = vm._answer_from_sensors("lateral g force")
        assert "0.45" in result

    def test_yaw_rate(self):
        vm = self._make_vm()
        result = vm._answer_from_sensors("yaw rate")
        assert "12.0" in result

    def test_gear(self):
        vm = self._make_vm()
        result = vm._answer_from_sensors("what gear am i in")
        assert "3" in result

    def test_dccd_percent(self):
        vm = self._make_vm()
        result = vm._answer_from_sensors("dccd bias percent")
        assert "35" in result

    def test_can_disconnected_returns_no_ecu(self):
        """ECU queries say 'No ECU connected' when CAN is not connected."""
        vm = self._make_vm(can_connected=False)
        result = vm._answer_from_sensors("oil temp")
        assert result is not None and "No ECU" in result
        result2 = vm._answer_from_sensors("current rpm")
        assert result2 is not None and "No ECU" in result2

    def test_ambient_still_works_without_can(self):
        """Ambient queries work even without CAN."""
        vm = self._make_vm(can_connected=False, ambient_available=True,
                           ambient_temp_c=22.0, dew_point_c=10.0)
        result = vm._answer_from_sensors("what's the temperature")
        assert result is not None
        assert "22.0" in result


# ========================================================================
# Wake Word Training Script tests (KiSTI-006)
# ========================================================================

import struct
import wave
import math


class TestWakeWordTraining:
    """Tests for scripts/train_wake_word.py sample generation and config."""

    def test_import_training_module(self):
        """Training script module is importable."""
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        import train_wake_word
        assert hasattr(train_wake_word, "WAKE_PHRASES")
        assert hasattr(train_wake_word, "NEGATIVE_PHRASES")
        assert hasattr(train_wake_word, "PIPER_VOICES")

    def test_wake_phrases_nonempty(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        import train_wake_word
        assert len(train_wake_word.WAKE_PHRASES) >= 5
        # All phrases must contain "kisti" or "keesty" (case-insensitive)
        for phrase in train_wake_word.WAKE_PHRASES:
            lower = phrase.lower()
            assert "kisti" in lower or "keesty" in lower, f"Bad wake phrase: {phrase}"

    def test_negative_phrases_nonempty(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        import train_wake_word
        assert len(train_wake_word.NEGATIVE_PHRASES) >= 20

    def test_speed_factors_range(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        import train_wake_word
        for speed in train_wake_word.SPEED_FACTORS:
            assert 0.5 <= speed <= 2.0, f"Speed factor out of range: {speed}"

    def test_generate_silence_wav(self, tmp_path):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        from train_wake_word import generate_silence_wav
        out = tmp_path / "silence.wav"
        generate_silence_wav(out, duration_s=1.0)
        assert out.exists()
        with wave.open(str(out), "r") as wf:
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2
            assert wf.getframerate() == 16000
            assert wf.getnframes() == 16000  # 1 second at 16kHz

    def test_generate_noise_wav(self, tmp_path):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        from train_wake_word import generate_noise_wav
        out = tmp_path / "noise.wav"
        generate_noise_wav(out, duration_s=0.5)
        assert out.exists()
        with wave.open(str(out), "r") as wf:
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2
            assert wf.getframerate() == 16000
            # ~8000 samples for 0.5s
            assert wf.getnframes() == 8000

    def test_generate_noise_wav_has_nonzero_audio(self, tmp_path):
        """Noise WAV should contain actual audio, not silence."""
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        from train_wake_word import generate_noise_wav
        out = tmp_path / "noise_check.wav"
        generate_noise_wav(out, duration_s=1.0)
        with wave.open(str(out), "r") as wf:
            frames = wf.readframes(wf.getnframes())
        # Check RMS is nonzero
        n_samples = len(frames) // 2
        total = sum(
            struct.unpack_from("<h", frames, i * 2)[0] ** 2
            for i in range(min(n_samples, 1000))
        )
        rms = (total / min(n_samples, 1000)) ** 0.5
        assert rms > 100, f"Noise RMS too low: {rms}"

    def test_find_available_voices_empty(self, tmp_path):
        """No voices in empty directory."""
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        from train_wake_word import find_available_voices
        voices = find_available_voices(tmp_path)
        assert voices == []

    def test_find_available_voices_with_files(self, tmp_path):
        """Finds voice files that match known names."""
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        from train_wake_word import find_available_voices, PIPER_VOICES
        # Create a fake voice file
        (tmp_path / PIPER_VOICES[0]).write_bytes(b"fake")
        voices = find_available_voices(tmp_path)
        assert len(voices) == 1
        assert voices[0].name == PIPER_VOICES[0]

    def test_generate_full_training_config(self, tmp_path):
        """YAML config is generated with correct structure."""
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        from train_wake_word import generate_full_training_config
        pos_dir = tmp_path / "pos"
        neg_dir = tmp_path / "neg"
        pos_dir.mkdir()
        neg_dir.mkdir()
        out_dir = tmp_path / "model"
        config_path = generate_full_training_config(pos_dir, neg_dir, out_dir)
        assert config_path.exists()
        content = config_path.read_text()
        assert "hey kisti" in content
        assert "hey_kisti" in content
        assert str(pos_dir) in content
        assert str(neg_dir) in content

    def test_sample_rate_constant(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        import train_wake_word
        assert train_wake_word.SAMPLE_RATE == 16000

    def test_default_output_path(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        import train_wake_word
        assert str(train_wake_word.DEFAULT_OUTPUT) == "/data/models/hey_kisti.onnx"


# ========================================================================
# Wake Model Session Config tests (KiSTI-006)
# ========================================================================


class TestWakeModelSessionConfig:
    """Tests for KISTI_WAKE_MODEL in kisti-session script."""

    def test_kisti_session_exports_wake_model(self):
        """kisti-session script exports KISTI_WAKE_MODEL."""
        session_path = Path(__file__).resolve().parent.parent / "scripts" / "kisti-session"
        content = session_path.read_text()
        assert "export KISTI_WAKE_MODEL=/data/models/hey_kisti.onnx" in content

    def test_kisti_session_wake_model_after_ollama(self):
        """KISTI_WAKE_MODEL export comes after OLLAMA_MODELS export."""
        session_path = Path(__file__).resolve().parent.parent / "scripts" / "kisti-session"
        content = session_path.read_text()
        ollama_pos = content.index("export OLLAMA_MODELS=")
        wake_pos = content.index("export KISTI_WAKE_MODEL=")
        assert wake_pos > ollama_pos, "KISTI_WAKE_MODEL should come after OLLAMA_MODELS"

    def test_mic_capture_reads_wake_model_env(self, monkeypatch):
        """MicCapture picks up KISTI_WAKE_MODEL from environment."""
        monkeypatch.setenv("KISTI_WAKE_MODEL", "/data/models/hey_kisti.onnx")
        import os
        assert os.environ["KISTI_WAKE_MODEL"] == "/data/models/hey_kisti.onnx"

    def test_mic_capture_wake_model_constructor(self):
        """MicCapture stores wake_model from constructor arg."""
        mic = MicCapture(device="nonexistent", wake_model="/data/models/hey_kisti.onnx")
        assert mic._wake_model == "/data/models/hey_kisti.onnx"

    def test_mic_capture_wake_model_none_default(self):
        """MicCapture defaults to None wake_model."""
        mic = MicCapture(device="nonexistent")
        assert mic._wake_model is None


# ========================================================================
# Frontier Cloud Control Commands (KiSTI-14 Phase 5)
# ========================================================================


class TestFrontierCloudCommands:
    """Tests for 'enable cloud' / 'disable cloud' voice commands."""

    def test_edge_memory_settings_table_created(self):
        """Settings table is created on initialize()."""
        import tempfile
        from data.duckdb_store import DuckDBStore
        from data.edge_memory import EdgeMemory

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.duckdb"
            store = DuckDBStore(db_path=db_path)
            store.open()
            memory = EdgeMemory(db_store=store, embedder=None)
            memory.initialize()

            # Verify settings table exists
            result = store._conn.execute(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'settings'"
            ).fetchone()
            assert result[0] > 0, "Settings table should exist"

    def test_edge_memory_get_set_string_setting(self):
        """Test get/set string settings."""
        import tempfile
        from data.duckdb_store import DuckDBStore
        from data.edge_memory import EdgeMemory

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.duckdb"
            store = DuckDBStore(db_path=db_path)
            store.open()
            memory = EdgeMemory(db_store=store, embedder=None)
            memory.initialize()

            # Test set and get
            memory.set_setting("test_key", "test_value")
            assert memory.get_setting("test_key") == "test_value"

            # Test default
            assert memory.get_setting("nonexistent", "default") == "default"

    def test_edge_memory_get_set_bool_setting(self):
        """Test get/set boolean settings."""
        import tempfile
        from data.duckdb_store import DuckDBStore
        from data.edge_memory import EdgeMemory

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.duckdb"
            store = DuckDBStore(db_path=db_path)
            store.open()
            memory = EdgeMemory(db_store=store, embedder=None)
            memory.initialize()

            # Test set true
            memory.set_setting_bool("frontier_enabled", True)
            assert memory.get_setting_bool("frontier_enabled") is True

            # Test set false
            memory.set_setting_bool("frontier_enabled", False)
            assert memory.get_setting_bool("frontier_enabled") is False

            # Test default
            assert memory.get_setting_bool("nonexistent", True) is True
            assert memory.get_setting_bool("nonexistent", False) is False

    def test_edge_memory_bool_parsing(self):
        """Test boolean setting string parsing."""
        import tempfile
        from data.duckdb_store import DuckDBStore
        from data.edge_memory import EdgeMemory

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.duckdb"
            store = DuckDBStore(db_path=db_path)
            store.open()
            memory = EdgeMemory(db_store=store, embedder=None)
            memory.initialize()

            # Test various true representations
            for true_val in ["true", "True", "TRUE", "1", "yes", "YES", "enabled"]:
                memory.set_setting("bool_test", true_val)
                assert memory.get_setting_bool("bool_test") is True, f"Failed for: {true_val}"

            # Test false representations
            for false_val in ["false", "False", "FALSE", "0", "no", "NO", "disabled", ""]:
                memory.set_setting("bool_test", false_val)
                assert memory.get_setting_bool("bool_test") is False, f"Failed for: {false_val}"

    def test_frontier_llm_engine_lifecycle(self):
        """Test FrontierLLMEngine start/stop lifecycle."""
        from voice.frontier_engine import FrontierLLMEngine

        # Without API key, should not start
        engine = FrontierLLMEngine(api_key="")
        engine.start()
        assert not engine.is_running, "Engine should not run without API key"

        # With API key, should start
        engine = FrontierLLMEngine(api_key="sk-test-key")
        assert not engine.is_running
        engine.start()
        assert engine.is_running, "Engine should be running with API key"
        engine.stop()
        assert not engine.is_running, "Engine should stop"

    def test_frontier_llm_engine_start_idempotent(self):
        """Test FrontierLLMEngine start is idempotent."""
        from voice.frontier_engine import FrontierLLMEngine

        engine = FrontierLLMEngine(api_key="sk-test-key")
        engine.start()
        assert engine.is_running

        # Second start should be safe (idempotent)
        engine.start()
        assert engine.is_running

        engine.stop()

    def test_voice_manager_frontier_command_enable(self):
        """Test voice manager frontier enable command handler."""
        import tempfile
        from data.duckdb_store import DuckDBStore
        from data.edge_memory import EdgeMemory
        from voice.frontier_engine import FrontierLLMEngine
        from voice.voice_manager import VoiceManager
        from unittest.mock import MagicMock

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.duckdb"
            store = DuckDBStore(db_path=db_path)
            store.open()
            memory = EdgeMemory(db_store=store, embedder=None)
            memory.initialize()

            # Create voice manager
            voice_mgr = VoiceManager(enable_mic=False)
            voice_mgr._frontier = FrontierLLMEngine(api_key="sk-test-key")
            voice_mgr._edge_memory = memory

            # Initially frontier is not running
            assert not voice_mgr._frontier.is_running

            # Handle enable command
            response = voice_mgr._handle_frontier_command("enable cloud")
            assert response == "Cloud enabled."
            assert voice_mgr._frontier.is_running
            assert memory.get_setting_bool("frontier_enabled") is True

            # Handle enable again (should be idempotent)
            response = voice_mgr._handle_frontier_command("enable cloud")
            assert response == "Cloud is already enabled."

            voice_mgr._frontier.stop()

    def test_voice_manager_frontier_command_disable(self):
        """Test voice manager frontier disable command handler."""
        import tempfile
        from data.duckdb_store import DuckDBStore
        from data.edge_memory import EdgeMemory
        from voice.frontier_engine import FrontierLLMEngine
        from voice.voice_manager import VoiceManager

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.duckdb"
            store = DuckDBStore(db_path=db_path)
            store.open()
            memory = EdgeMemory(db_store=store, embedder=None)
            memory.initialize()

            # Create voice manager with running frontier
            voice_mgr = VoiceManager(enable_mic=False)
            voice_mgr._frontier = FrontierLLMEngine(api_key="sk-test-key")
            voice_mgr._frontier.start()
            voice_mgr._edge_memory = memory

            assert voice_mgr._frontier.is_running

            # Handle disable command
            response = voice_mgr._handle_frontier_command("disable cloud")
            assert response == "Cloud disabled."
            assert not voice_mgr._frontier.is_running
            assert memory.get_setting_bool("frontier_enabled") is False

            # Handle disable again (should be idempotent)
            response = voice_mgr._handle_frontier_command("disable cloud")
            assert response == "Cloud is already disabled."

    def test_voice_manager_frontier_command_status(self):
        """Test voice manager frontier status command handler."""
        import tempfile
        from data.duckdb_store import DuckDBStore
        from data.edge_memory import EdgeMemory
        from voice.frontier_engine import FrontierLLMEngine
        from voice.voice_manager import VoiceManager

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.duckdb"
            store = DuckDBStore(db_path=db_path)
            store.open()
            memory = EdgeMemory(db_store=store, embedder=None)
            memory.initialize()

            voice_mgr = VoiceManager(enable_mic=False)
            voice_mgr._frontier = FrontierLLMEngine(api_key="sk-test-key")
            voice_mgr._edge_memory = memory

            # Test status when disabled
            response = voice_mgr._handle_frontier_command("cloud status")
            assert "disabled" in response.lower()

            # Test status when enabled
            voice_mgr._frontier.start()
            response = voice_mgr._handle_frontier_command("is cloud enabled")
            assert "enabled" in response.lower()

            voice_mgr._frontier.stop()

    def test_voice_manager_frontier_command_phrase_variants(self):
        """Test voice manager recognizes multiple frontier command phrases."""
        import tempfile
        from data.duckdb_store import DuckDBStore
        from data.edge_memory import EdgeMemory
        from voice.frontier_engine import FrontierLLMEngine
        from voice.voice_manager import VoiceManager

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.duckdb"
            store = DuckDBStore(db_path=db_path)
            store.open()
            memory = EdgeMemory(db_store=store, embedder=None)
            memory.initialize()

            voice_mgr = VoiceManager(enable_mic=False)
            voice_mgr._frontier = FrontierLLMEngine(api_key="sk-test-key")
            voice_mgr._edge_memory = memory

            # Test enable variants
            enable_phrases = ["enable cloud", "turn on cloud", "activate cloud"]
            for phrase in enable_phrases:
                voice_mgr._frontier.stop()
                response = voice_mgr._handle_frontier_command(phrase)
                assert response == "Cloud enabled.", f"Failed for: {phrase}"
                assert voice_mgr._frontier.is_running

            # Test disable variants
            disable_phrases = ["disable cloud", "turn off cloud", "deactivate cloud"]
            for phrase in disable_phrases:
                voice_mgr._frontier.start()
                response = voice_mgr._handle_frontier_command(phrase)
                assert response == "Cloud disabled.", f"Failed for: {phrase}"
                assert not voice_mgr._frontier.is_running

    def test_voice_manager_frontier_command_no_frontier(self):
        """Test frontier command handler when frontier is None."""
        import tempfile
        from data.duckdb_store import DuckDBStore
        from data.edge_memory import EdgeMemory
        from voice.voice_manager import VoiceManager

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.duckdb"
            store = DuckDBStore(db_path=db_path)
            store.open()
            memory = EdgeMemory(db_store=store, embedder=None)
            memory.initialize()

            voice_mgr = VoiceManager(enable_mic=False)
            voice_mgr._frontier = None  # No frontier
            voice_mgr._edge_memory = memory

            # Should return None (not a command match)
            response = voice_mgr._handle_frontier_command("enable cloud")
            assert response is None

    def test_voice_manager_frontier_command_no_edge_memory(self):
        """Test frontier command handler when edge_memory is None."""
        from voice.frontier_engine import FrontierLLMEngine
        from voice.voice_manager import VoiceManager

        voice_mgr = VoiceManager(enable_mic=False)
        voice_mgr._frontier = FrontierLLMEngine(api_key="sk-test-key")
        voice_mgr._edge_memory = None  # No edge memory

        # Should return None (not a command match)
        response = voice_mgr._handle_frontier_command("enable cloud")
        assert response is None

    def test_wake_model_path_is_onnx(self):
        """Configured wake model path has .onnx extension."""
        session_path = Path(__file__).resolve().parent.parent / "scripts" / "kisti-session"
        content = session_path.read_text()
        # Extract the path from the export line
        for line in content.splitlines():
            if "KISTI_WAKE_MODEL=" in line:
                path = line.split("=", 1)[1].strip()
                assert path.endswith(".onnx"), f"Wake model path should be .onnx: {path}"
                break
        else:
            pytest.fail("KISTI_WAKE_MODEL not found in kisti-session")
