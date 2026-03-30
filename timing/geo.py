"""GPS geometry primitives for lap/sector timing.

Pure functions — no Qt, no DiffState, no external dependencies.
All angles in degrees, distances in meters, coordinates in WGS84.
"""

from __future__ import annotations

import math
from typing import Optional

# Earth radius in meters (WGS84 mean)
_R = 6_371_000.0


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two GPS points in meters."""
    rlat1, rlon1 = math.radians(lat1), math.radians(lon1)
    rlat2, rlon2 = math.radians(lat2), math.radians(lon2)
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return _R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def line_segment_crossing(
    prev_lat: float, prev_lon: float,
    curr_lat: float, curr_lon: float,
    line_lat1: float, line_lon1: float,
    line_lat2: float, line_lon2: float,
) -> Optional[float]:
    """Check if the vehicle path crossed a line segment since last GPS update.

    Uses 2D line-segment intersection in a local Cartesian approximation.
    Returns the interpolation fraction (0.0–1.0) along the vehicle path
    if a crossing occurred, or None if no crossing.

    The fraction can be used to interpolate the exact crossing time:
        crossing_time = prev_ts + (curr_ts - prev_ts) * fraction
    """
    # Convert to local Cartesian (meters) centered on prev position.
    # At typical track scales (<5 km) the flat-earth approximation is fine.
    cos_lat = math.cos(math.radians(prev_lat))
    m_per_deg_lat = 111_320.0
    m_per_deg_lon = 111_320.0 * cos_lat

    # Vehicle path: A → B
    ax, ay = 0.0, 0.0
    bx = (curr_lon - prev_lon) * m_per_deg_lon
    by = (curr_lat - prev_lat) * m_per_deg_lat

    # Line segment: C → D
    cx = (line_lon1 - prev_lon) * m_per_deg_lon
    cy = (line_lat1 - prev_lat) * m_per_deg_lat
    dx = (line_lon2 - prev_lon) * m_per_deg_lon
    dy = (line_lat2 - prev_lat) * m_per_deg_lat

    # Solve for intersection of AB and CD using parametric form.
    # AB: P = A + t * (B - A),  t in [0, 1]
    # CD: P = C + u * (D - C),  u in [0, 1]
    abx = bx - ax
    aby = by - ay
    cdx = dx - cx
    cdy = dy - cy

    denom = abx * cdy - aby * cdx
    if abs(denom) < 1e-12:
        return None  # Parallel or coincident

    acx = cx - ax
    acy = cy - ay

    t = (acx * cdy - acy * cdx) / denom
    u = (acx * aby - acy * abx) / denom

    if 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0:
        return t
    return None


def interpolate_crossing_time(prev_ts: float, curr_ts: float, fraction: float) -> float:
    """Interpolate the exact crossing time given timestamps and crossing fraction."""
    return prev_ts + (curr_ts - prev_ts) * fraction


def perpendicular_line(
    lat: float, lon: float, heading_deg: float, half_width_m: float = 15.0,
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Generate a line segment perpendicular to heading at a GPS point.

    Used to auto-generate start/finish lines and sector boundaries.
    Returns ((lat1, lon1), (lat2, lon2)).
    """
    # Perpendicular heading: +90 degrees
    perp_deg = (heading_deg + 90.0) % 360.0
    perp_rad = math.radians(perp_deg)

    cos_lat = math.cos(math.radians(lat))
    dlat = (half_width_m * math.cos(perp_rad)) / 111_320.0
    dlon = (half_width_m * math.sin(perp_rad)) / (111_320.0 * cos_lat)

    lat1 = lat + dlat
    lon1 = lon + dlon
    lat2 = lat - dlat
    lon2 = lon - dlon
    return ((lat1, lon1), (lat2, lon2))


def point_in_radius(
    lat: float, lon: float,
    center_lat: float, center_lon: float,
    radius_m: float,
) -> bool:
    """Check if a GPS point is within radius_m of a center point."""
    return haversine_distance(lat, lon, center_lat, center_lon) <= radius_m


def cumulative_distance(gps_trace: list[tuple[float, float]]) -> list[float]:
    """Compute cumulative distance along a GPS trace.

    Args:
        gps_trace: List of (lat, lon) tuples.

    Returns:
        List of cumulative distances in meters (same length as input).
        First element is always 0.0.
    """
    if not gps_trace:
        return []
    distances = [0.0]
    for i in range(1, len(gps_trace)):
        prev_lat, prev_lon = gps_trace[i - 1]
        curr_lat, curr_lon = gps_trace[i]
        d = haversine_distance(prev_lat, prev_lon, curr_lat, curr_lon)
        distances.append(distances[-1] + d)
    return distances


def bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial bearing from point 1 to point 2 in degrees (0–360)."""
    rlat1 = math.radians(lat1)
    rlat2 = math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    x = math.sin(dlon) * math.cos(rlat2)
    y = math.cos(rlat1) * math.sin(rlat2) - math.sin(rlat1) * math.cos(rlat2) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360
