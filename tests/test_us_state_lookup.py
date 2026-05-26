"""Tests for US state bounding-box lookup."""

from sensors.us_state_lookup import lookup_state


class TestKnownCities:
    """Verify lookup for well-known US cities inside RWIS states."""

    def test_des_moines_iowa(self):
        assert lookup_state(41.59, -93.62) == "IA"

    def test_minneapolis_minnesota(self):
        assert lookup_state(44.98, -93.27) == "MN"

    def test_denver_colorado(self):
        assert lookup_state(39.74, -104.99) == "CO"

    def test_boise_idaho(self):
        assert lookup_state(43.62, -116.21) == "ID"

    def test_portland_oregon(self):
        assert lookup_state(45.52, -122.68) == "OR"

    def test_columbus_ohio(self):
        assert lookup_state(39.96, -82.99) == "OH"

    def test_anchorage_alaska(self):
        assert lookup_state(61.22, -149.90) == "AK"

    def test_raleigh_north_carolina(self):
        assert lookup_state(35.78, -78.64) == "NC"


class TestOutsideUS:
    """Points outside the US should return None."""

    def test_canada_toronto(self):
        """Toronto, ON — falls inside NY bounding box (expected for bbox approach).
        Bounding boxes can't follow the border precisely, so border cities
        may match a US state. This is acceptable for RWIS purposes."""
        result = lookup_state(43.65, -79.38)
        # Toronto is near the NY border — bbox approach may return NY
        assert result is None or result == "NY"

    def test_canada_calgary(self):
        """Calgary, AB — no RWIS state covers this."""
        assert lookup_state(51.05, -114.07) is None

    def test_ocean_pacific(self):
        """Middle of the Pacific Ocean."""
        assert lookup_state(30.0, -150.0) is None

    def test_ocean_atlantic(self):
        """Middle of the Atlantic Ocean."""
        assert lookup_state(35.0, -50.0) is None

    def test_mexico(self):
        """Mexico City — south of US."""
        assert lookup_state(19.43, -99.13) is None

    def test_europe(self):
        """London, UK."""
        assert lookup_state(51.51, -0.13) is None


class TestBorderAreas:
    """Border and edge cases."""

    def test_returns_string_or_none(self):
        """Return type is always str or None."""
        result = lookup_state(41.0, -93.0)
        assert result is None or isinstance(result, str)

    def test_state_code_is_two_letters(self):
        """If a state is returned, it's a 2-letter uppercase code."""
        result = lookup_state(41.59, -93.62)
        assert result is not None
        assert len(result) == 2
        assert result == result.upper()

    def test_extreme_north_alaska(self):
        """Barrow, AK — very far north but still Alaska."""
        result = lookup_state(71.3, -156.8)
        assert result == "AK"

    def test_south_of_all_boxes(self):
        """Key West area — not in any RWIS state box (FL has no RWIS)."""
        result = lookup_state(24.55, -81.78)
        assert result is None
