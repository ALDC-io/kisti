"""Track outline — normalize GPS points to screen coords and cache to disk.

Used to convert raw .ztracks GPS data into a form suitable for QPainter:
  - Normalize (lat, lon) → (x, y) in 0-1 space with y flipped for screen
  - Downsample with Ramer-Douglas-Peucker to keep ~80 representative points
  - Save/load as JSON keyed by track_id

No numpy — pure Python math only (Jetson RAM constraint).
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path

log = logging.getLogger("kisti.timing.track_outline")

# Default outlines directory (relative to repo root)
_DEFAULT_OUTLINES_DIR = Path(__file__).parent.parent / "data" / "track_outlines"


def normalize_outline(
    points: list[tuple[float, float]],
) -> list[tuple[float, float]]:
    """Convert (lat, lon) GPS points → (x, y) normalized to 0-1 range.

    Longitude maps to x (east = higher x).
    Latitude maps to y flipped (north = lower y, for screen coordinates).
    Returns empty list if fewer than 2 points.
    """
    if len(points) < 2:
        return []

    lats = [p[0] for p in points]
    lons = [p[1] for p in points]

    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)

    lat_span = max_lat - min_lat
    lon_span = max_lon - min_lon

    # Correct longitude for latitude (degrees of lon are shorter at higher latitudes)
    center_lat = (min_lat + max_lat) / 2
    lon_scale = math.cos(math.radians(center_lat))

    # Use the larger dimension so the track fills the bounding box proportionally
    effective_lon_span = lon_span * lon_scale
    if lat_span == 0 and effective_lon_span == 0:
        return [(0.5, 0.5)] * len(points)

    scale = max(lat_span, effective_lon_span) or 1.0

    normalized: list[tuple[float, float]] = []
    for lat, lon in points:
        # Centre within a 0-1 box with a 5% margin
        nx = 0.05 + 0.90 * ((lon - min_lon) * lon_scale) / scale
        # Y flipped: north (high lat) → small y (top of screen)
        ny = 0.05 + 0.90 * ((max_lat - lat)) / scale
        # Clamp to [0, 1]
        nx = max(0.0, min(1.0, nx))
        ny = max(0.0, min(1.0, ny))
        normalized.append((nx, ny))

    return normalized


def downsample_rdp(
    points: list[tuple[float, float]],
    epsilon: float = 0.002,
    max_points: int = 100,
) -> list[tuple[float, float]]:
    """Ramer-Douglas-Peucker simplification of a polyline.

    Args:
        points: List of (x, y) normalized points.
        epsilon: Perpendicular distance threshold for point removal.
        max_points: Hard cap on output count; epsilon is increased if needed.

    Returns:
        Simplified point list (always includes first and last point).
    """
    if len(points) <= 2:
        return list(points)

    result = _rdp(points, epsilon)

    # If still too many, increase epsilon and retry
    if len(result) > max_points:
        result = _rdp(points, epsilon * 2)
    if len(result) > max_points:
        # Last-resort uniform subsample: pick max_points evenly spaced indices
        indices = [int(i * (len(result) - 1) / (max_points - 1)) for i in range(max_points - 1)]
        indices.append(len(result) - 1)
        result = [result[i] for i in indices]

    return result


def _rdp(
    points: list[tuple[float, float]],
    epsilon: float,
) -> list[tuple[float, float]]:
    """Recursive Ramer-Douglas-Peucker."""
    if len(points) <= 2:
        return list(points)

    # Find point with maximum perpendicular distance from the line start→end
    start, end = points[0], points[-1]
    max_dist = 0.0
    max_idx = 0

    for i in range(1, len(points) - 1):
        dist = _perp_distance(points[i], start, end)
        if dist > max_dist:
            max_dist = dist
            max_idx = i

    if max_dist > epsilon:
        left = _rdp(points[: max_idx + 1], epsilon)
        right = _rdp(points[max_idx:], epsilon)
        return left[:-1] + right
    else:
        return [start, end]


def _perp_distance(
    point: tuple[float, float],
    line_start: tuple[float, float],
    line_end: tuple[float, float],
) -> float:
    """Perpendicular distance from point to line segment start→end."""
    x0, y0 = point
    x1, y1 = line_start
    x2, y2 = line_end

    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(x0 - x1, y0 - y1)

    # Distance from point to infinite line
    return abs(dy * x0 - dx * y0 + x2 * y1 - y2 * x1) / math.hypot(dx, dy)


def save_outline(
    track_id: str,
    outline: list[tuple[float, float]],
    outlines_dir: Path = _DEFAULT_OUTLINES_DIR,
) -> None:
    """Persist a normalized outline to {outlines_dir}/{track_id}.json."""
    outlines_dir.mkdir(parents=True, exist_ok=True)
    target = outlines_dir / f"{track_id}.json"
    target.write_text(json.dumps(outline))
    log.info("Saved outline %s (%d pts) → %s", track_id[:8], len(outline), target.name)


def load_outline(
    track_id: str,
    outlines_dir: Path = _DEFAULT_OUTLINES_DIR,
) -> list[tuple[float, float]] | None:
    """Load a cached outline. Returns None if not found."""
    target = outlines_dir / f"{track_id}.json"
    if not target.exists():
        return None
    try:
        data = json.loads(target.read_text())
        return [(float(x), float(y)) for x, y in data]
    except Exception as exc:
        log.warning("Failed to load outline %s: %s", track_id[:8], exc)
        return None


def import_ztracks_outline(
    ztracks_path: Path,
    track_id: str,
    outlines_dir: Path = _DEFAULT_OUTLINES_DIR,
) -> list[tuple[float, float]]:
    """Parse a .ztracks file, normalize, downsample, and cache the outline.

    Returns the normalized outline (may be empty if parsing fails).
    """
    from tools.ztracks_parser import parse_ztracks  # avoid circular at module level

    try:
        result = parse_ztracks(ztracks_path)
    except Exception as exc:
        log.warning("Failed to parse %s: %s", ztracks_path.name, exc)
        return []

    if not result.points:
        log.warning("No GPS points in %s", ztracks_path.name)
        return []

    # Drop altitude, keep (lat, lon)
    latlon = [(p[0], p[1]) for p in result.points]
    normalized = normalize_outline(latlon)
    outline = downsample_rdp(normalized)

    save_outline(track_id, outline, outlines_dir)
    log.info(
        "Imported %s → %d pts (from %d raw)",
        result.name, len(outline), len(latlon),
    )
    return outline
