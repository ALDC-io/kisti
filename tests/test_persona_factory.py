"""Tests for new persona responses — pistons, factory specs, and build comparisons."""
import pytest
from voice.llm_engine import _match_persona, PERSONA_RESPONSES
from data.build_record import (
    ENGINE, FACTORY, BASELINES, FactorySpec,
    build_summary, build_detail, factory_vs_build,
)


class TestNewPersonaEntries:
    """Test new persona keyword matches."""

    def test_piston_persona(self):
        result = _match_persona("tell me about the pistons", "Intelligent")
        assert result is not None
        assert "Manley" in result

    def test_bore_stroke_persona(self):
        result = _match_persona("what's the bore and stroke", "Intelligent")
        assert result is not None
        assert "99.75" in result or "bore" in result.lower()

    def test_internals_persona(self):
        result = _match_persona("what internals do you have", "Intelligent")
        assert result is not None
        assert "Manley" in result or "forged" in result.lower()

    def test_short_block_persona(self):
        result = _match_persona("tell me about the short block", "Intelligent")
        assert result is not None

    def test_spark_plug_persona(self):
        result = _match_persona("tell me about the spark plugs", "Intelligent")
        assert result is not None
        assert "plug" in result.lower() or "NGK" in result

    def test_ignition_persona(self):
        result = _match_persona("how's the ignition system", "Intelligent")
        assert result is not None

    def test_oil_level_persona(self):
        result = _match_persona("how's the oil level", "Intelligent")
        assert result is not None
        assert "break-in" in result.lower() or "level" in result.lower() or "ring seal" in result.lower()

    def test_burning_oil_persona(self):
        result = _match_persona("are you burning oil", "Intelligent")
        assert result is not None

    def test_battery_persona(self):
        result = _match_persona("tell me about the battery", "Intelligent")
        assert result is not None
        assert "PDM" in result or "alternator" in result.lower()

    def test_electrical_persona(self):
        result = _match_persona("how's the electrical system", "Intelligent")
        assert result is not None


class TestFactorySpecPersona:
    """Test factory spec comparison persona responses."""

    def test_factory_query(self):
        result = _match_persona("what did the car come with from factory", "Intelligent")
        assert result is not None
        assert "305" in result or "factory" in result.lower()

    def test_stock_query(self):
        result = _match_persona("what was the stock setup", "Intelligent")
        assert result is not None

    def test_power_difference(self):
        result = _match_persona("how much more power do you have now", "Intelligent")
        assert result is not None
        assert "305" in result or "double" in result.lower()

    def test_factory_turbo(self):
        result = _match_persona("what was the factory turbo", "Intelligent")
        assert result is not None
        assert "VF48" in result

    def test_factory_brakes(self):
        result = _match_persona("what are the factory brakes", "Intelligent")
        assert result is not None
        assert "Brembo" in result

    def test_factory_suspension(self):
        result = _match_persona("tell me about the factory suspension", "Intelligent")
        assert result is not None
        assert "MacPherson" in result or "inverted" in result.lower()

    def test_curb_weight(self):
        result = _match_persona("what's the curb weight", "Intelligent")
        assert result is not None
        # Existing weight entry matches "curb weight" — either response is valid
        assert "kg" in result.lower()

    def test_gear_ratios(self):
        result = _match_persona("what are the gear ratios", "Intelligent")
        assert result is not None
        assert "3.636" in result

    def test_dccd_modes(self):
        result = _match_persona("what are the dccd modes", "Intelligent")
        assert result is not None
        assert "Auto" in result

    def test_front_rear_diff(self):
        # "front diff" and "rear diff" are more specific keywords
        result = _match_persona("what type of front diff and rear diff", "Intelligent")
        assert result is not None
        assert "Torsen" in result or "helical" in result.lower() or "limited-slip" in result.lower()

    def test_fuel_tank(self):
        result = _match_persona("how big is the fuel tank", "Intelligent")
        assert result is not None
        assert "60" in result

    def test_factory_weakness(self):
        result = _match_persona("what are the known issues with the ej", "Intelligent")
        assert result is not None
        assert "ringland" in result.lower() or "failure" in result.lower()


class TestFactorySpecDataclass:
    """Test FactorySpec dataclass and comparison function."""

    def test_factory_spec_exists(self):
        assert FACTORY is not None
        assert isinstance(FACTORY, FactorySpec)

    def test_factory_hp(self):
        assert FACTORY.hp == 305

    def test_factory_turbo(self):
        assert "VF48" in FACTORY.turbo

    def test_factory_bore(self):
        assert FACTORY.bore_mm == 99.5

    def test_factory_displacement(self):
        assert FACTORY.displacement_cc == 2457

    def test_factory_gear_ratios(self):
        assert FACTORY.gear_1 == 3.636
        assert FACTORY.final_drive == 3.900

    def test_factory_brakes(self):
        assert "Brembo" in FACTORY.front_brake
        assert "4-piston" in FACTORY.front_brake

    def test_factory_known_weaknesses(self):
        assert len(FACTORY.known_weaknesses) == 4
        assert any("ringland" in w.lower() for w in FACTORY.known_weaknesses)

    def test_engine_piston_fields(self):
        """EngineSpec now has piston/bore/stroke fields."""
        assert ENGINE.pistons == "Manley H-Tuff Plus Forged"
        assert ENGINE.bore_mm == 99.75
        assert ENGINE.stroke_mm == 79.0

    def test_factory_vs_build_output(self):
        """factory_vs_build() generates comparison text."""
        text = factory_vs_build()
        assert "305" in text  # factory hp
        assert "IAG 750" in text  # current build
        assert "VF48" in text or "factory" in text.lower()
        assert "BCP X400" in text or ENGINE.turbo in text

    def test_build_summary_still_works(self):
        """Existing build_summary() unaffected by changes."""
        text = build_summary()
        assert "IAG-14894" in text
        assert ENGINE.vin in text

    def test_build_detail_still_works(self):
        """Existing build_detail() unaffected by changes."""
        text = build_detail()
        assert "IAG Performance 750" in text
        assert str(ENGINE.serial) in text
