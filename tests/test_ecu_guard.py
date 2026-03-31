"""Tests for ECU keyword guard — live-data vs knowledge query split.

Verifies that bare component words (brake, tire, speed, boost) fall through
to persona responses when CAN is disconnected, while explicit live-data
phrases and bare-word + live-indicator combos still block correctly.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from unittest.mock import MagicMock
from voice.voice_manager import VoiceManager


NO_ECU_MSG = "No ECU connected. Link G five not installed yet."


def _make_vm(can_connected: bool = False) -> VoiceManager:
    """Create a VoiceManager with mocked telemetry snapshot."""
    vm = VoiceManager.__new__(VoiceManager)
    snap = MagicMock()
    snap.can_connected = can_connected
    snap.ambient_available = False
    snap.ambient_temp_c = 0.0
    snap.dew_point_c = 0.0
    # ECU fields (only relevant when CAN connected)
    snap.oil_temp_c = 95.0
    snap.oil_psi = 45.0
    snap.coolant_temp = 88.0
    snap.iat_c = 35.0
    snap.map_kpa = 200.0
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
    vm._telemetry_snapshot = snap
    return vm


# ========================================================================
# Bare component words fall through when CAN disconnected
# ========================================================================


class TestBareWordsFallThrough:
    """Bare component words without live-data indicators should return None
    (fall through to persona) when CAN is disconnected."""

    @pytest.mark.parametrize("query", [
        "tell me about the brakes",
        "how do tires work",
        "what suspension do you have",
        "tell me about boost",
        "tell me about speed",
        "what about the battery",
    ])
    def test_bare_component_falls_through(self, query: str):
        vm = _make_vm(can_connected=False)
        result = vm._answer_from_sensors(query)
        assert result is None, f"Expected None (fall-through) for '{query}', got: {result}"


# ========================================================================
# Live-data phrases still block when CAN disconnected
# ========================================================================


class TestLivePhraseBlock:
    """Multi-word live-data phrases should return 'No ECU connected'
    when CAN is disconnected."""

    @pytest.mark.parametrize("query", [
        "oil temp",
        "boost psi",
        "brake pressure",
        "what gear",
    ])
    def test_live_phrase_blocks(self, query: str):
        vm = _make_vm(can_connected=False)
        result = vm._answer_from_sensors(query)
        assert result == NO_ECU_MSG, f"Expected ECU block for '{query}', got: {result}"


# ========================================================================
# Bare component + live indicator blocks when CAN disconnected
# ========================================================================


class TestBareWithIndicatorBlocks:
    """Bare component word + live-data indicator should return 'No ECU connected'
    when CAN is disconnected."""

    @pytest.mark.parametrize("query", [
        "current speed",
        "what's my boost",
        "what is my rpm",
    ])
    def test_bare_plus_indicator_blocks(self, query: str):
        vm = _make_vm(can_connected=False)
        result = vm._answer_from_sensors(query)
        assert result == NO_ECU_MSG, f"Expected ECU block for '{query}', got: {result}"


# ========================================================================
# CAN connected — guard does not block (returns None from guard section)
# ========================================================================


class TestCANConnectedPassThrough:
    """When CAN IS connected, the guard should not fire — queries proceed
    to the specific CAN handler block."""

    @pytest.mark.parametrize("query", [
        "tell me about the brakes",
        "oil temp",
        "current speed",
        "what's my boost",
    ])
    def test_can_connected_no_guard_block(self, query: str):
        vm = _make_vm(can_connected=True)
        result = vm._answer_from_sensors(query)
        # Should NOT be the guard message — either None or a real sensor response
        assert result != NO_ECU_MSG, f"Guard fired with CAN connected for '{query}'"
