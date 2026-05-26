"""Tests for STT whisper.cpp server request parameters and hallucination filter."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from unittest.mock import patch, MagicMock
from voice.stt_engine import STTEngine, SAMPLE_RATE, _is_hallucination


class TestWhisperServerParams:
    """Verify whisper.cpp server request includes language and initial_prompt."""

    def test_server_request_contains_language(self):
        """The multipart body should include language=en."""
        engine = STTEngine()
        engine._backend = "whisper-cpp-server"
        engine._running = True

        # Generate minimal PCM audio (1 second of silence)
        audio_pcm = b"\x00\x00" * SAMPLE_RATE

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.__enter__ = MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_resp.status = 200
            mock_resp.read.return_value = b'{"text": "hello"}'
            mock_urlopen.return_value = mock_resp

            engine.transcribe(audio_pcm)

            # Check that the request body contains language field
            call_args = mock_urlopen.call_args
            request_obj = call_args[0][0]
            body = request_obj.data
            assert b'name="language"' in body
            assert b"\r\nen\r\n" in body

    def test_server_request_contains_initial_prompt(self):
        """The multipart body should include initial_prompt with automotive terms."""
        engine = STTEngine()
        engine._backend = "whisper-cpp-server"
        engine._running = True

        audio_pcm = b"\x00\x00" * SAMPLE_RATE

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.__enter__ = MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_resp.status = 200
            mock_resp.read.return_value = b'{"text": "test"}'
            mock_urlopen.return_value = mock_resp

            engine.transcribe(audio_pcm)

            call_args = mock_urlopen.call_args
            request_obj = call_args[0][0]
            body = request_obj.data
            assert b'name="initial_prompt"' in body
            assert b"KiSTI" in body or b"Keesty" in body
            assert b"Boost" in body or b"boost" in body


class TestHallucinationFilter:
    """Verify hallucination filter uses exact match, not startswith."""

    @pytest.mark.parametrize("text", [
        "yeah what about the boost",
        "well check the oil",
        "oh check the oil pressure",
        "right give me brake temps",
    ])
    def test_filler_prefix_not_filtered(self, text: str):
        """Queries starting with filler words should NOT be filtered."""
        assert not _is_hallucination(text)

    @pytest.mark.parametrize("text", [
        "yeah",
        "oh",
        "well",
        "right",
        "okay",
        "so",
        "um",
        "thank you",
        "bye",
    ])
    def test_exact_hallucination_still_caught(self, text: str):
        """Bare filler words (exact match) should still be filtered."""
        assert _is_hallucination(text)
