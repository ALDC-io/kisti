"""KiSTI — US State Lookup from Lat/Lon

Simple bounding-box lookup for the 33 US states that have IEM RWIS
networks. No external dependencies — pure math, fast enough for 1 Hz
GPS updates.

Bounding boxes are intentionally generous (0.5-degree padding) so that
border-area GPS jitter doesn't cause frequent state flips.
"""

from __future__ import annotations


# (state_code, lat_min, lat_max, lon_min, lon_max)
# Only the ~33 states with IEM RWIS networks.
# Boxes are approximate and generous — overlaps resolved by smallest-area match.
_STATE_BOXES: list[tuple[str, float, float, float, float]] = [
    ("AK", 51.0, 71.5, -180.0, -129.0),
    ("AZ", 31.3, 37.0, -114.8, -109.0),
    ("CA", 32.5, 42.0, -124.5, -114.1),
    ("CO", 36.9, 41.1, -109.1, -102.0),
    ("CT", 40.9, 42.1, -73.8, -71.7),
    ("DE", 38.4, 39.9, -75.8, -75.0),
    ("IA", 40.4, 43.5, -96.7, -90.1),
    ("ID", 41.9, 49.1, -117.3, -111.0),
    ("IL", 36.9, 42.5, -91.6, -87.0),
    ("IN", 37.7, 41.8, -88.1, -84.7),
    ("KS", 36.9, 40.1, -102.1, -94.5),
    ("KY", 36.5, 39.2, -89.6, -81.9),
    ("MA", 41.2, 42.9, -73.5, -69.9),
    ("MD", 37.9, 39.8, -79.5, -75.0),
    ("ME", 42.9, 47.5, -71.1, -66.9),
    ("MI", 41.7, 48.3, -90.5, -82.1),
    ("MN", 43.5, 49.4, -97.3, -89.5),
    ("MO", 35.9, 40.7, -95.8, -89.0),
    ("MT", 44.3, 49.1, -116.1, -104.0),
    ("NC", 33.8, 36.6, -84.3, -75.4),
    ("ND", 45.9, 49.1, -104.1, -96.5),
    ("NE", 39.9, 43.1, -104.1, -95.3),
    ("NH", 42.7, 45.4, -72.6, -70.6),
    ("NJ", 38.9, 41.4, -75.6, -73.9),
    ("NV", 35.0, 42.1, -120.1, -114.0),
    ("NY", 40.5, 45.1, -79.8, -71.8),
    ("OH", 38.4, 42.0, -84.9, -80.5),
    ("OR", 41.9, 46.3, -124.7, -116.4),
    ("PA", 39.7, 42.3, -80.6, -74.7),
    ("SD", 42.4, 46.0, -104.1, -96.4),
    ("UT", 36.9, 42.1, -114.1, -109.0),
    ("WI", 42.4, 47.1, -92.9, -86.7),
    ("WY", 40.9, 45.1, -111.1, -104.0),
]

# Pre-compute area for tie-breaking (smallest box wins on overlap)
_STATE_BOXES_WITH_AREA: list[tuple[str, float, float, float, float, float]] = [
    (code, lat_min, lat_max, lon_min, lon_max,
     (lat_max - lat_min) * (lon_max - lon_min))
    for code, lat_min, lat_max, lon_min, lon_max in _STATE_BOXES
]
_STATE_BOXES_WITH_AREA.sort(key=lambda x: x[5])  # smallest area first


def lookup_state(lat: float, lon: float) -> str | None:
    """Return 2-letter US state code for a lat/lon, or None if outside US.

    Only covers the ~33 states with IEM RWIS networks.
    When bounding boxes overlap (border areas), the smallest-area match wins.
    """
    for code, lat_min, lat_max, lon_min, lon_max, _area in _STATE_BOXES_WITH_AREA:
        if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
            return code
    return None
