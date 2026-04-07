"""ZTracks Parser — decode AiM .ztracks files to GPS outline points.

.ztracks is a ZIP archive containing a .tkk binary file.
TKK binary sections are delimited by `<h` markers:
  <hPtkk  — track name string
  <hVnfo  — venue info string
  <hpts   — GPS outline points (12 bytes each: lat/lon/alt as int32 / 1e7)
"""

from __future__ import annotations

import logging
import struct
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger("kisti.tools.ztracks_parser")

# Valid GPS bounds for sanity filtering
_LAT_MIN, _LAT_MAX = -90.0, 90.0
_LON_MIN, _LON_MAX = -180.0, 180.0


@dataclass
class ZtracksResult:
    """Parsed contents of a .ztracks file."""
    name: str
    city: str
    country: str
    points: list[tuple[float, float, float]] = field(default_factory=list)
    """GPS outline: list of (lat_deg, lon_deg, alt_m)."""


def parse_ztracks(path: Path) -> ZtracksResult:
    """Parse a .ztracks file and extract track name, venue, and GPS outline.

    Args:
        path: Path to the .ztracks file (ZIP archive).

    Returns:
        ZtracksResult with name, city, country, and GPS points.

    Raises:
        ValueError: If the file is not a valid .ztracks archive.
        FileNotFoundError: If the path does not exist.
    """
    if not path.exists():
        raise FileNotFoundError(f"Not found: {path}")

    try:
        with zipfile.ZipFile(path, 'r') as zf:
            tkk_names = [n for n in zf.namelist() if n.endswith('.tkk')]
            if not tkk_names:
                raise ValueError(f"No .tkk entry in {path.name}")
            data = zf.read(tkk_names[0])
    except zipfile.BadZipFile as exc:
        raise ValueError(f"Not a valid .ztracks archive: {path.name}") from exc

    name = _extract_string(data, b'<hPtkk')
    city = _extract_string(data, b'<hVnfo')
    points = _extract_gps_points(data)

    log.info(
        "Parsed %s: name=%r city=%r points=%d",
        path.name, name, city, len(points),
    )
    return ZtracksResult(name=name, city=city, country='', points=points)


# ---------------------------------------------------------------------------
# Internal parsers
# ---------------------------------------------------------------------------

def _find_section(data: bytes, tag: bytes) -> int:
    """Return byte offset of tag in data, or -1."""
    return data.find(tag)


def _section_data(data: bytes, tag: bytes) -> bytes:
    """Return the bytes between tag and the next <h section (or end of data)."""
    start = _find_section(data, tag)
    if start == -1:
        return b''
    payload_start = start + len(tag)
    next_tag = data.find(b'<h', payload_start)
    if next_tag == -1:
        return data[payload_start:]
    return data[payload_start:next_tag]


def _extract_string(data: bytes, tag: bytes) -> str:
    """Extract a null-terminated or section-bounded UTF-8 string after tag."""
    raw = _section_data(data, tag)
    if not raw:
        return ''
    # Strip any leading length/type byte if the first byte is non-printable
    # and the rest looks like a string
    for skip in (0, 1, 2, 4):
        candidate = raw[skip:]
        nul = candidate.find(b'\x00')
        chunk = candidate[:nul] if nul != -1 else candidate[:64]
        try:
            text = chunk.decode('utf-8', errors='replace').strip()
            if text and text.isprintable():
                return text
        except Exception:
            continue
    return ''


def _extract_gps_points(data: bytes) -> list[tuple[float, float, float]]:
    """Extract GPS outline points from the <hpts section.

    Points are encoded as 12-byte little-endian int32 triples:
        (lat_int, lon_int, alt_int) — divide by 1e7 for degrees / metres.

    Handles optional 4-byte count prefix before the point data.
    """
    raw = _section_data(data, b'<hpts')
    if not raw:
        return []

    # Try two starting offsets: 0 (no count prefix) and 4 (count prefix).
    # Pick whichever yields the most valid GPS-coordinate points.
    best: list[tuple[float, float, float]] = []
    for skip in (0, 4):
        candidate = _parse_points(raw[skip:])
        if len(candidate) > len(best):
            best = candidate

    return best


def _parse_points(raw: bytes) -> list[tuple[float, float, float]]:
    """Parse 12-byte int32 triples into (lat, lon, alt) tuples, filtering invalid coords."""
    points: list[tuple[float, float, float]] = []
    n = len(raw) // 12
    for i in range(n):
        chunk = raw[i * 12:(i + 1) * 12]
        lat_int, lon_int, alt_int = struct.unpack('<iii', chunk)
        lat = lat_int / 1e7
        lon = lon_int / 1e7
        alt = alt_int / 1e7
        if (_LAT_MIN < lat < _LAT_MAX and _LON_MIN < lon < _LON_MAX
                and not (lat == 0.0 and lon == 0.0)):
            points.append((lat, lon, alt))
    return points
