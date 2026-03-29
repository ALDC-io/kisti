"""Tests for voice pipeline — STT, TTS, LLM, LED waveform, voice manager.

All tests use mocks (no Ollama, no WhisperTRT, no Piper, no audio hardware).
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from voice.stt_engine import STTEngine, TranscriptionResult, SAMPLE_RATE
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
        assert _match_persona("How's the boost?") is not None

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
        assert MODE_TOKEN_CAPS["Sport"] == 32

    def test_intelligent_cap(self):
        assert MODE_TOKEN_CAPS["Intelligent"] == 64

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
        assert SPEECH_END_FRAMES == 12
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

    def test_exhaust(self):
        assert _match_persona("Tell me about the exhaust") is not None

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

    def test_music(self):
        assert _match_persona("Play some music") is not None

    def test_joke(self):
        assert _match_persona("Tell me a joke") is not None

    def test_jetson_brain(self):
        assert _match_persona("Tell me about your brain") is not None

    def test_sensor_count(self):
        assert _match_persona("How many sensors do you have?") is not None

    def test_ecu_link(self):
        assert _match_persona("Who tunes you?") is not None

    def test_can_bus(self):
        assert _match_persona("How does the CAN bus work?") is not None

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

    def test_back_to_future(self):
        assert _match_persona("We need a flux capacitor") is not None

    def test_top_gear(self):
        assert _match_persona("What would Clarkson say?") is not None

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
        assert _match_persona("How's the boost?", "Intelligent") is not None  # tech
        assert _match_persona("How are the brakes?", "Intelligent") is not None  # safety

    def test_sport_blocks_fun(self):
        """Sport mode blocks fun-category responses."""
        result = _match_persona("Who are you?", "Sport")
        assert result is None  # "who are you" is fun-only

    def test_sport_allows_tech(self):
        """Sport mode allows tech-category responses."""
        result = _match_persona("How's the boost?", "Sport")
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
