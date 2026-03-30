"""Tests for TrackDatabase — DuckDB-backed track definitions and sector boundaries."""

import json
import sys
import uuid
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

duckdb = pytest.importorskip("duckdb")

from data.duckdb_store import SCHEMA_DDL
from timing.track_db import (
    SectorDefinition,
    StartFinishLine,
    TrackDatabase,
    TrackDefinition,
)


@pytest.fixture
def conn():
    """In-memory DuckDB connection with schema initialized."""
    c = duckdb.connect(":memory:")
    c.execute(SCHEMA_DDL)
    yield c
    c.close()


@pytest.fixture
def db(conn):
    """TrackDatabase backed by in-memory DuckDB."""
    return TrackDatabase(conn)


def _make_track(
    track_id: str | None = None,
    name: str = "Area 27",
    center_lat: float = 49.4500,
    center_lon: float = -119.5500,
    radius_m: float = 2000.0,
    track_type: str = "circuit",
    start_finish: StartFinishLine | None = None,
    country: str = "CA",
    region: str = "BC",
    length_m: float = 4200.0,
    source: str = "manual",
) -> TrackDefinition:
    """Helper to build a TrackDefinition with sensible defaults."""
    return TrackDefinition(
        track_id=track_id or str(uuid.uuid4()),
        name=name,
        center_lat=center_lat,
        center_lon=center_lon,
        radius_m=radius_m,
        track_type=track_type,
        start_finish=start_finish,
        country=country,
        region=region,
        length_m=length_m,
        source=source,
    )


def _make_sf() -> StartFinishLine:
    return StartFinishLine(lat1=49.4501, lon1=-119.5501, lat2=49.4502, lon2=-119.5502)


def _make_sectors(track_id: str, count: int = 3) -> list[SectorDefinition]:
    sectors = []
    for i in range(count):
        sectors.append(SectorDefinition(
            sector_id=str(uuid.uuid4()),
            track_id=track_id,
            sector_index=i,
            line=StartFinishLine(
                lat1=49.4500 + i * 0.001,
                lon1=-119.5500 + i * 0.001,
                lat2=49.4500 + i * 0.001 + 0.0005,
                lon2=-119.5500 + i * 0.001 + 0.0005,
            ),
            name=f"Sector {i + 1}",
        ))
    return sectors


class TestSaveAndFindTrack:

    def test_save_track_and_find_within_radius(self, db):
        """Save a track then find it by GPS position near center."""
        track = _make_track()
        db.save_track(track)

        found = db.find_track(49.4501, -119.5501)
        assert found is not None
        assert found.track_id == track.track_id
        assert found.name == "Area 27"
        assert found.country == "CA"
        assert found.region == "BC"

    def test_find_track_returns_none_when_far_away(self, db):
        """GPS point far outside radius returns None."""
        track = _make_track()
        db.save_track(track)

        # ~500 km away
        found = db.find_track(54.0, -125.0)
        assert found is None

    def test_find_track_returns_closest_when_multiple(self, db):
        """When multiple tracks overlap, closest center wins."""
        track_a = _make_track(name="Track A", center_lat=49.4500, center_lon=-119.5500, radius_m=5000.0)
        track_b = _make_track(name="Track B", center_lat=49.4510, center_lon=-119.5510, radius_m=5000.0)
        db.save_track(track_a)
        db.save_track(track_b)

        # Query point is closer to track_b center
        found = db.find_track(49.4512, -119.5512)
        assert found is not None
        assert found.name == "Track B"


class TestSectors:

    def test_save_and_get_sectors_ordered(self, db):
        """Sectors come back ordered by sector_index."""
        track = _make_track()
        db.save_track(track)

        # Insert out of order
        sectors = _make_sectors(track.track_id, count=3)
        reversed_sectors = list(reversed(sectors))
        db.save_sectors(track.track_id, reversed_sectors)

        got = db.get_sectors(track.track_id)
        assert len(got) == 3
        for i, s in enumerate(got):
            assert s.sector_index == sectors[i].sector_index

    def test_save_sectors_replaces_existing(self, db):
        """Saving sectors a second time replaces the first set."""
        track = _make_track()
        db.save_track(track)

        db.save_sectors(track.track_id, _make_sectors(track.track_id, count=3))
        assert len(db.get_sectors(track.track_id)) == 3

        db.save_sectors(track.track_id, _make_sectors(track.track_id, count=2))
        assert len(db.get_sectors(track.track_id)) == 2

    def test_get_sectors_empty(self, db):
        """No sectors returns empty list."""
        track = _make_track()
        db.save_track(track)
        assert db.get_sectors(track.track_id) == []


class TestDeleteTrack:

    def test_delete_removes_track_and_sectors(self, db):
        """Deleting a track also removes its sectors."""
        track = _make_track()
        db.save_track(track)
        db.save_sectors(track.track_id, _make_sectors(track.track_id, count=2))

        db.delete_track(track.track_id)

        assert db.find_track(track.center_lat, track.center_lon) is None
        assert db.get_sectors(track.track_id) == []
        assert db.track_count() == 0


class TestListTracks:

    def test_list_tracks_returns_all(self, db):
        """list_tracks returns every saved track."""
        for name in ["Alpha", "Bravo", "Charlie"]:
            db.save_track(_make_track(name=name))

        tracks = db.list_tracks()
        assert len(tracks) == 3

    def test_list_tracks_ordered_by_name(self, db):
        """Tracks come back sorted alphabetically by name."""
        for name in ["Zolder", "Area 27", "Mission Raceway"]:
            db.save_track(_make_track(name=name))

        tracks = db.list_tracks()
        names = [t.name for t in tracks]
        assert names == ["Area 27", "Mission Raceway", "Zolder"]

    def test_list_tracks_respects_limit(self, db):
        """Limit parameter caps the result count."""
        for i in range(5):
            db.save_track(_make_track(name=f"Track {i}"))

        tracks = db.list_tracks(limit=2)
        assert len(tracks) == 2


class TestTrackCount:

    def test_track_count_empty(self, db):
        assert db.track_count() == 0

    def test_track_count_after_inserts(self, db):
        db.save_track(_make_track(name="One"))
        db.save_track(_make_track(name="Two"))
        assert db.track_count() == 2


class TestSeedTracks:

    def test_seed_tracks_from_json(self, db, tmp_path):
        """Bulk import from a JSON seed file."""
        seed_data = [
            {
                "track_id": str(uuid.uuid4()),
                "name": "Area 27",
                "center_lat": 49.45,
                "center_lon": -119.55,
                "radius_m": 2000.0,
                "country": "CA",
                "region": "BC",
                "length_m": 4200.0,
            },
            {
                "name": "Mission Raceway",
                "center_lat": 49.13,
                "center_lon": -122.30,
            },
        ]
        json_file = tmp_path / "tracks.json"
        json_file.write_text(json.dumps(seed_data))

        count = db.seed_tracks(json_file)
        assert count == 2
        assert db.track_count() == 2

        # Verify seeded source
        tracks = db.list_tracks()
        for t in tracks:
            assert t.source == "seed"

    def test_seed_tracks_with_sectors(self, db, tmp_path):
        """Seed file with sectors imports both tracks and sectors."""
        tid = str(uuid.uuid4())
        seed_data = [
            {
                "track_id": tid,
                "name": "Area 27",
                "center_lat": 49.45,
                "center_lon": -119.55,
                "sectors": [
                    {"line_lat1": 49.451, "line_lon1": -119.551, "line_lat2": 49.452, "line_lon2": -119.552, "name": "S1"},
                    {"line_lat1": 49.453, "line_lon1": -119.553, "line_lat2": 49.454, "line_lon2": -119.554, "name": "S2"},
                ],
            },
        ]
        json_file = tmp_path / "tracks_sectors.json"
        json_file.write_text(json.dumps(seed_data))

        count = db.seed_tracks(json_file)
        assert count == 1

        sectors = db.get_sectors(tid)
        assert len(sectors) == 2
        assert sectors[0].name == "S1"
        assert sectors[1].name == "S2"
        assert sectors[0].sector_index == 0
        assert sectors[1].sector_index == 1

    def test_seed_generates_track_id_when_missing(self, db, tmp_path):
        """If track_id is omitted from JSON, a UUID is generated."""
        seed_data = [{"name": "Unknown Track", "center_lat": 50.0, "center_lon": -120.0}]
        json_file = tmp_path / "no_id.json"
        json_file.write_text(json.dumps(seed_data))

        db.seed_tracks(json_file)
        tracks = db.list_tracks()
        assert len(tracks) == 1
        assert len(tracks[0].track_id) == 36  # UUID format

    def test_seed_with_start_finish(self, db, tmp_path):
        """Seed file with start_finish dict creates StartFinishLine."""
        seed_data = [
            {
                "name": "Track With SF",
                "center_lat": 49.45,
                "center_lon": -119.55,
                "start_finish": {"lat1": 49.451, "lon1": -119.551, "lat2": 49.452, "lon2": -119.552},
            },
        ]
        json_file = tmp_path / "sf.json"
        json_file.write_text(json.dumps(seed_data))

        db.seed_tracks(json_file)
        tracks = db.list_tracks()
        assert tracks[0].start_finish is not None
        assert tracks[0].start_finish.lat1 == 49.451


class TestNullStartFinish:

    def test_save_track_with_no_start_finish(self, db):
        """Track with start_finish=None stores NULLs in DB."""
        track = _make_track(start_finish=None)
        db.save_track(track)

        found = db.find_track(track.center_lat, track.center_lon)
        assert found is not None
        assert found.start_finish is None

    def test_save_track_with_start_finish(self, db):
        """Track with start_finish stores the line and round-trips."""
        sf = _make_sf()
        track = _make_track(start_finish=sf)
        db.save_track(track)

        found = db.find_track(track.center_lat, track.center_lon)
        assert found is not None
        assert found.start_finish is not None
        assert found.start_finish.lat1 == sf.lat1
        assert found.start_finish.lon2 == sf.lon2


class TestTrackTypes:

    def test_find_track_circuit(self, db):
        track = _make_track(track_type="circuit")
        db.save_track(track)

        found = db.find_track(track.center_lat, track.center_lon)
        assert found.track_type == "circuit"

    def test_find_track_point_to_point(self, db):
        track = _make_track(track_type="point_to_point")
        db.save_track(track)

        found = db.find_track(track.center_lat, track.center_lon)
        assert found.track_type == "point_to_point"

    def test_list_tracks_preserves_track_type(self, db):
        db.save_track(_make_track(name="Circuit", track_type="circuit"))
        db.save_track(_make_track(name="Point", track_type="point_to_point"))

        tracks = db.list_tracks()
        types = {t.name: t.track_type for t in tracks}
        assert types["Circuit"] == "circuit"
        assert types["Point"] == "point_to_point"


class TestDataclassDefaults:

    def test_track_definition_defaults(self):
        """TrackDefinition has correct default values."""
        t = TrackDefinition(track_id="tid", name="Test", center_lat=0.0, center_lon=0.0)
        assert t.radius_m == 2000.0
        assert t.track_type == "circuit"
        assert t.start_finish is None
        assert t.country == ""
        assert t.region == ""
        assert t.length_m == 0.0
        assert t.source == "manual"
        assert t.sectors == []

    def test_sector_definition_fields(self):
        """SectorDefinition stores all required fields."""
        line = StartFinishLine(lat1=1.0, lon1=2.0, lat2=3.0, lon2=4.0)
        s = SectorDefinition(
            sector_id="sid",
            track_id="tid",
            sector_index=0,
            line=line,
            name="Turn 1",
        )
        assert s.sector_id == "sid"
        assert s.track_id == "tid"
        assert s.sector_index == 0
        assert s.line.lat1 == 1.0
        assert s.line.lon2 == 4.0
        assert s.name == "Turn 1"

    def test_sector_definition_default_name(self):
        """SectorDefinition name defaults to empty string."""
        s = SectorDefinition(
            sector_id="sid", track_id="tid", sector_index=0,
            line=StartFinishLine(0, 0, 0, 0),
        )
        assert s.name == ""

    def test_start_finish_line_fields(self):
        """StartFinishLine stores four GPS coordinates."""
        sf = StartFinishLine(lat1=10.1, lon1=20.2, lat2=30.3, lon2=40.4)
        assert sf.lat1 == 10.1
        assert sf.lon1 == 20.2
        assert sf.lat2 == 30.3
        assert sf.lon2 == 40.4
