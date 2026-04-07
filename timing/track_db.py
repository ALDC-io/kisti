"""Track database — DuckDB-backed track definitions and sector boundaries.

Provides track auto-recognition (find_track by GPS position), sector lookup,
and track persistence for learned/manual/seeded tracks.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

log = logging.getLogger("kisti.timing.track_db")


@dataclass
class StartFinishLine:
    """GPS line segment defining start/finish or sector boundary."""
    lat1: float
    lon1: float
    lat2: float
    lon2: float


@dataclass
class SectorDefinition:
    """A sector boundary within a track."""
    sector_id: str
    track_id: str
    sector_index: int
    line: StartFinishLine
    name: str = ""


@dataclass
class TrackDefinition:
    """A complete track definition."""
    track_id: str
    name: str
    center_lat: float
    center_lon: float
    radius_m: float = 2000.0
    track_type: str = "circuit"  # 'circuit' | 'point_to_point'
    start_finish: Optional[StartFinishLine] = None
    country: str = ""
    region: str = ""
    length_m: float = 0.0
    source: str = "manual"  # 'manual' | 'learned' | 'seed'
    sectors: list[SectorDefinition] = field(default_factory=list)
    outline: list[tuple[float, float]] = field(default_factory=list)
    """Normalized (0-1) track outline points — runtime only, not persisted to DuckDB."""


class TrackDatabase:
    """DuckDB-backed track storage with GPS-based lookup."""

    def __init__(self, conn) -> None:
        """Initialize with an open DuckDB connection (from DuckDBStore)."""
        self._conn = conn

    def find_track(self, lat: float, lon: float) -> Optional[TrackDefinition]:
        """Find a track by GPS position (within radius of track center).

        Uses haversine approximation via DuckDB math functions.
        Returns the closest matching track, or None.
        """
        # DuckDB has no haversine built-in, so use Euclidean on degree-scaled coords.
        # At typical track scales (<5 km) this is sufficient for recognition.
        # 1 degree lat ≈ 111320m, 1 degree lon ≈ 111320 * cos(lat) m
        rows = self._conn.execute(
            """
            SELECT track_id, name, center_lat, center_lon, radius_m,
                   track_type, start_lat1, start_lon1, start_lat2, start_lon2,
                   country, region, length_m, source,
                   SQRT(
                       POW((center_lat - ?) * 111320, 2) +
                       POW((center_lon - ?) * 111320 * COS(RADIANS(?)), 2)
                   ) AS dist_m
            FROM tracks
            WHERE SQRT(
                POW((center_lat - ?) * 111320, 2) +
                POW((center_lon - ?) * 111320 * COS(RADIANS(?)), 2)
            ) <= radius_m
            ORDER BY dist_m ASC
            LIMIT 1
            """,
            [lat, lon, lat, lat, lon, lat],
        ).fetchall()

        if not rows:
            return None

        r = rows[0]
        track = TrackDefinition(
            track_id=r[0], name=r[1],
            center_lat=r[2], center_lon=r[3], radius_m=r[4],
            track_type=r[5],
            start_finish=StartFinishLine(r[6], r[7], r[8], r[9]) if r[6] is not None else None,
            country=r[10] or "", region=r[11] or "",
            length_m=r[12] or 0.0, source=r[13] or "manual",
        )

        # Load sectors
        track.sectors = self.get_sectors(track.track_id)
        return track

    def get_sectors(self, track_id: str) -> list[SectorDefinition]:
        """Get sector boundaries for a track, ordered by sector_index."""
        rows = self._conn.execute(
            "SELECT sector_id, track_id, sector_index, "
            "line_lat1, line_lon1, line_lat2, line_lon2, name "
            "FROM track_sectors WHERE track_id = ? ORDER BY sector_index",
            [track_id],
        ).fetchall()

        return [
            SectorDefinition(
                sector_id=r[0], track_id=r[1], sector_index=r[2],
                line=StartFinishLine(r[3], r[4], r[5], r[6]),
                name=r[7] or "",
            )
            for r in rows
        ]

    def save_track(self, track: TrackDefinition) -> None:
        """Save or update a track definition."""
        sf = track.start_finish
        self._conn.execute(
            """
            INSERT OR REPLACE INTO tracks (
                track_id, name, center_lat, center_lon, radius_m,
                track_type, start_lat1, start_lon1, start_lat2, start_lon2,
                country, region, length_m, source, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            [
                track.track_id, track.name,
                track.center_lat, track.center_lon, track.radius_m,
                track.track_type,
                sf.lat1 if sf else None, sf.lon1 if sf else None,
                sf.lat2 if sf else None, sf.lon2 if sf else None,
                track.country, track.region, track.length_m, track.source,
            ],
        )

    def save_sectors(self, track_id: str, sectors: list[SectorDefinition]) -> None:
        """Save sector boundaries for a track (replaces existing)."""
        self._conn.execute(
            "DELETE FROM track_sectors WHERE track_id = ?", [track_id],
        )
        for s in sectors:
            self._conn.execute(
                "INSERT INTO track_sectors VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    s.sector_id, track_id, s.sector_index,
                    s.line.lat1, s.line.lon1, s.line.lat2, s.line.lon2,
                    s.name,
                ],
            )

    def delete_track(self, track_id: str) -> None:
        """Delete a track and its sectors."""
        self._conn.execute("DELETE FROM track_sectors WHERE track_id = ?", [track_id])
        self._conn.execute("DELETE FROM tracks WHERE track_id = ?", [track_id])

    def list_tracks(self, limit: int = 50) -> list[TrackDefinition]:
        """List all tracks."""
        rows = self._conn.execute(
            "SELECT track_id, name, center_lat, center_lon, radius_m, "
            "track_type, start_lat1, start_lon1, start_lat2, start_lon2, "
            "country, region, length_m, source "
            "FROM tracks ORDER BY name LIMIT ?",
            [limit],
        ).fetchall()

        return [
            TrackDefinition(
                track_id=r[0], name=r[1],
                center_lat=r[2], center_lon=r[3], radius_m=r[4],
                track_type=r[5],
                start_finish=StartFinishLine(r[6], r[7], r[8], r[9]) if r[6] is not None else None,
                country=r[10] or "", region=r[11] or "",
                length_m=r[12] or 0.0, source=r[13] or "manual",
            )
            for r in rows
        ]

    def seed_tracks(self, json_path: Path) -> int:
        """Bulk import tracks from a JSON seed file.

        JSON format: list of objects with keys matching TrackDefinition fields.
        Returns count of tracks imported.
        """
        data = json.loads(json_path.read_text())
        count = 0

        for entry in data:
            track_id = entry.get("track_id", str(uuid.uuid4()))
            sf = entry.get("start_finish")
            start_finish = StartFinishLine(**sf) if sf else None

            track = TrackDefinition(
                track_id=track_id,
                name=entry["name"],
                center_lat=entry["center_lat"],
                center_lon=entry["center_lon"],
                radius_m=entry.get("radius_m", 2000.0),
                track_type=entry.get("track_type", "circuit"),
                start_finish=start_finish,
                country=entry.get("country", ""),
                region=entry.get("region", ""),
                length_m=entry.get("length_m", 0.0),
                source="seed",
            )
            self.save_track(track)

            # Import sectors if present
            sectors_data = entry.get("sectors", [])
            sectors = []
            for i, sd in enumerate(sectors_data):
                sectors.append(SectorDefinition(
                    sector_id=sd.get("sector_id", str(uuid.uuid4())),
                    track_id=track_id,
                    sector_index=i,
                    line=StartFinishLine(
                        sd["line_lat1"], sd["line_lon1"],
                        sd["line_lat2"], sd["line_lon2"],
                    ),
                    name=sd.get("name", f"Sector {i + 1}"),
                ))
            if sectors:
                self.save_sectors(track_id, sectors)

            count += 1

        log.info("Seeded %d tracks from %s", count, json_path.name)
        return count

    def track_count(self) -> int:
        """Return total number of tracks in database."""
        return self._conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]
