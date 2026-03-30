"""Shared test fixtures for KiSTI test suite."""

import sys
import time
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def voice_manager_proxy():
    """Minimal VoiceManager proxy for testing methods that only need
    _dialogue, _NON_REFERENTIAL, _REFERENTIAL (avoids full Qt init).
    """
    from voice.voice_manager import VoiceManager, DialogueState
    mgr = types.SimpleNamespace()
    mgr._dialogue = DialogueState()
    mgr._NON_REFERENTIAL = VoiceManager._NON_REFERENTIAL
    mgr._REFERENTIAL = VoiceManager._REFERENTIAL
    return mgr


@pytest.fixture
def mock_dialogue_state():
    """DialogueState with configurable topic/turns."""
    from voice.voice_manager import DialogueState
    state = DialogueState()
    state.topic = "oil"
    state.turn_counter = 5
    state.topic_since_turn = 5
    return state


@pytest.fixture
def mock_pipeline_trace():
    """PipelineTrace with realistic timing values."""
    from voice.voice_manager import PipelineTrace
    now = time.monotonic()
    return PipelineTrace(
        mic_captured_at=now,
        stt_done_at=now + 0.130,
        llm_done_at=now + 0.130 + 2.1,
        tts_done_at=now + 0.130 + 2.1 + 0.450,
        speaker_start_at=now + 0.130 + 2.1 + 0.450 + 0.010,
        source="local_llm",
        query_text="How is the oil pressure?",
    )
