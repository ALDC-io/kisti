"""RS3 Track Import — convert GPS data to KiSTI tracks_seed.json format.

Accepts GPX, CSV, or manual center-point entry. Outputs JSON matching the
tracks_seed.json schema consumed by TrackDatabase.seed_tracks().

Usage:
    # GPX file (e.g., exported from RS3 GPS Manager)
    python3 -m tools.rs3_track_import --input track.gpx --name "Area 27" --country CA --region BC

    # CSV file (lat,lon per row)
    python3 -m tools.rs3_track_import --input track.csv --name "Mission Raceway"

    # Manual entry from RS3 UI center coordinates
    python3 -m tools.rs3_track_import --manual --center-lat 49.45 --center-lon -119.55 --name "Area 27"

    # Merge output into existing seed file
    python3 -m tools.rs3_track_import --input track.gpx --name "Area 27" --merge data/tracks_seed.json
"""

from __future__ import annotations

import argparse
import bisect
import json
import logging
import sys
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

# Add repo root to path so timing.geo is importable
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from timing.geo import (
    bearing,
    cumulative_distance,
    haversine_distance,
    perpendicular_line,
)

log = logging.getLogger("kisti.tools.rs3_track_import")

# GPS trace must have at least this many points for sector generation
MIN_TRACE_POINTS = 10

# Margin added to max distance from centroid for radius_m
RADIUS_MARGIN_M = 200.0

# Default half-width for start/finish and sector lines (meters)
DEFAULT_HALF_WIDTH_M = 15.0


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------


def parse_gpx(path: Path) -> list[tuple[float, float]]:
    """Parse GPX file and extract GPS trace as (lat, lon) tuples.

    Handles GPX 1.1 (with namespace) and GPX 1.0 (without namespace).
    Prefers <trkpt> elements; falls back to <wpt> waypoints.
    """
    tree = ET.parse(path)
    root = tree.getroot()

    # Try GPX 1.1 namespace first, then bare tags
    namespaces = [
        "{http://www.topografix.com/GPX/1/1}",
        "{http://www.topografix.com/GPX/1/0}",
        "",
    ]

    points: list[tuple[float, float]] = []

    for ns in namespaces:
        # Try track points
        for trkpt in root.iter(f"{ns}trkpt"):
            lat = float(trkpt.attrib["lat"])
            lon = float(trkpt.attrib["lon"])
            points.append((lat, lon))
        if points:
            break

        # Fallback to waypoints
        for wpt in root.iter(f"{ns}wpt"):
            lat = float(wpt.attrib["lat"])
            lon = float(wpt.attrib["lon"])
            points.append((lat, lon))
        if points:
            break

    if not points:
        raise ValueError(f"No GPS points found in {path}")

    return points


def parse_csv(path: Path) -> list[tuple[float, float]]:
    """Parse CSV with lat,lon per row. Auto-detects and skips header."""
    lines = path.read_text().strip().splitlines()
    if not lines:
        raise ValueError(f"Empty CSV file: {path}")

    points: list[tuple[float, float]] = []
    for i, line in enumerate(lines):
        parts = line.strip().split(",")
        if len(parts) < 2:
            continue
        try:
            lat = float(parts[0].strip())
            lon = float(parts[1].strip())
            points.append((lat, lon))
        except ValueError:
            if i == 0:
                continue  # Skip header row
            raise

    if not points:
        raise ValueError(f"No valid GPS points in {path}")

    return points


# ---------------------------------------------------------------------------
# Track generation
# ---------------------------------------------------------------------------


def _smoothed_bearing(trace: list[tuple[float, float]], idx: int) -> float:
    """Compute bearing at trace index using a 5-point window for stability."""
    n = len(trace)
    i0 = max(0, idx - 2)
    i1 = min(n - 1, idx + 2)
    if i0 == i1:
        i0 = max(0, idx - 1)
    lat0, lon0 = trace[i0]
    lat1, lon1 = trace[i1]
    return bearing(lat0, lon0, lat1, lon1)


def trace_to_track(
    gps_trace: list[tuple[float, float]],
    name: str,
    country: str = "",
    region: str = "",
    track_type: str = "circuit",
    num_sectors: int = 3,
    half_width_m: float = DEFAULT_HALF_WIDTH_M,
) -> dict:
    """Convert GPS trace to a tracks_seed.json entry dict.

    Computes center, radius, length, start/finish line, and sector boundaries
    from the GPS trace. Mirrors TrackLearner._generate_track() algorithm.

    Args:
        gps_trace: List of (lat, lon) tuples (minimum 10 points).
        name: Track display name.
        country: ISO country code (e.g., "CA", "US").
        region: Province/state name.
        track_type: "circuit" or "point_to_point".
        num_sectors: Number of sector boundaries to generate.
        half_width_m: Half-width of S/F and sector lines in meters.

    Returns:
        Dict matching tracks_seed.json schema.
    """
    if len(gps_trace) < MIN_TRACE_POINTS:
        raise ValueError(
            f"GPS trace has {len(gps_trace)} points, need at least {MIN_TRACE_POINTS}"
        )

    n = len(gps_trace)

    # Center (centroid)
    center_lat = sum(p[0] for p in gps_trace) / n
    center_lon = sum(p[1] for p in gps_trace) / n

    # Radius (max distance from centroid + margin)
    max_dist = max(
        haversine_distance(center_lat, center_lon, p[0], p[1])
        for p in gps_trace
    )
    radius_m = max_dist + RADIUS_MARGIN_M

    # Length
    cum_dists = cumulative_distance(gps_trace)
    length_m = cum_dists[-1]

    # Start/finish line at first point
    sf_heading = _smoothed_bearing(gps_trace, 0)
    (sf_lat1, sf_lon1), (sf_lat2, sf_lon2) = perpendicular_line(
        gps_trace[0][0], gps_trace[0][1], sf_heading, half_width_m,
    )

    # Sector boundaries at equal-distance fractions
    sectors = []
    for i in range(num_sectors):
        frac = (i + 1) / (num_sectors + 1)
        target_dist = length_m * frac

        idx = bisect.bisect_right(cum_dists, target_dist) - 1
        idx = max(1, min(idx, n - 2))

        # Interpolate position
        d0 = cum_dists[idx]
        d1 = cum_dists[idx + 1]
        seg_frac = (target_dist - d0) / (d1 - d0) if d1 > d0 else 0.0
        lat0, lon0 = gps_trace[idx]
        lat1, lon1 = gps_trace[idx + 1]
        sec_lat = lat0 + seg_frac * (lat1 - lat0)
        sec_lon = lon0 + seg_frac * (lon1 - lon0)

        sec_heading = _smoothed_bearing(gps_trace, idx)
        (s_lat1, s_lon1), (s_lat2, s_lon2) = perpendicular_line(
            sec_lat, sec_lon, sec_heading, half_width_m,
        )

        sectors.append({
            "line_lat1": round(s_lat1, 6),
            "line_lon1": round(s_lon1, 6),
            "line_lat2": round(s_lat2, 6),
            "line_lon2": round(s_lon2, 6),
            "name": f"Sector {i + 1}",
        })

    return {
        "track_id": str(uuid.uuid4()),
        "name": name,
        "center_lat": round(center_lat, 6),
        "center_lon": round(center_lon, 6),
        "radius_m": round(radius_m, 1),
        "track_type": track_type,
        "country": country,
        "region": region,
        "length_m": round(length_m, 1),
        "start_finish": {
            "lat1": round(sf_lat1, 6),
            "lon1": round(sf_lon1, 6),
            "lat2": round(sf_lat2, 6),
            "lon2": round(sf_lon2, 6),
        },
        "sectors": sectors,
    }


def manual_entry(
    name: str,
    center_lat: float,
    center_lon: float,
    radius_m: float = 2000.0,
    country: str = "",
    region: str = "",
    track_type: str = "circuit",
) -> dict:
    """Create minimal track entry from RS3 GPS Manager center coordinates.

    No start/finish line or sectors — just center + radius for GPS recognition.
    """
    return {
        "track_id": str(uuid.uuid4()),
        "name": name,
        "center_lat": round(center_lat, 6),
        "center_lon": round(center_lon, 6),
        "radius_m": round(radius_m, 1),
        "track_type": track_type,
        "country": country,
        "region": region,
        "length_m": 0.0,
        "start_finish": None,
        "sectors": [],
    }


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------


def merge_to_seed(new_track: dict, seed_path: Path) -> None:
    """Append a track entry to an existing tracks_seed.json file.

    Warns if a track with the same name already exists but still merges.
    """
    data = json.loads(seed_path.read_text()) if seed_path.exists() else []

    for existing in data:
        if existing.get("name") == new_track["name"]:
            log.warning("Track '%s' already exists in seed file — adding anyway", new_track["name"])
            break

    data.append(new_track)
    seed_path.write_text(json.dumps(data, indent=2) + "\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Import RS3 track data into KiSTI tracks_seed.json format.",
    )
    parser.add_argument("--input", type=Path, help="GPX or CSV file path")
    parser.add_argument("--manual", action="store_true", help="Manual center-point entry mode")
    parser.add_argument("--name", required=True, help="Track name")
    parser.add_argument("--country", default="", help="ISO country code (e.g., CA, US)")
    parser.add_argument("--region", default="", help="Province/state name")
    parser.add_argument("--track-type", default="circuit", choices=["circuit", "point_to_point"])
    parser.add_argument("--sectors", type=int, default=3, help="Number of sector boundaries")
    parser.add_argument("--center-lat", type=float, help="Center latitude (manual mode)")
    parser.add_argument("--center-lon", type=float, help="Center longitude (manual mode)")
    parser.add_argument("--radius", type=float, default=2000.0, help="Recognition radius in meters (manual mode)")
    parser.add_argument("--merge", type=Path, help="Merge output into existing seed JSON file")

    args = parser.parse_args(argv)

    if args.manual:
        if args.center_lat is None or args.center_lon is None:
            parser.error("--manual requires --center-lat and --center-lon")
        track = manual_entry(
            name=args.name,
            center_lat=args.center_lat,
            center_lon=args.center_lon,
            radius_m=args.radius,
            country=args.country,
            region=args.region,
            track_type=args.track_type,
        )
    elif args.input:
        suffix = args.input.suffix.lower()
        if suffix == ".gpx":
            points = parse_gpx(args.input)
        elif suffix == ".csv":
            points = parse_csv(args.input)
        else:
            parser.error(f"Unsupported file format: {suffix} (use .gpx or .csv)")
        track = trace_to_track(
            gps_trace=points,
            name=args.name,
            country=args.country,
            region=args.region,
            track_type=args.track_type,
            num_sectors=args.sectors,
        )
    else:
        parser.error("Provide --input <file> or --manual")

    if args.merge:
        merge_to_seed(track, args.merge)
        print(f"Merged '{args.name}' into {args.merge}")
    else:
        print(json.dumps(track, indent=2))


if __name__ == "__main__":
    main()
