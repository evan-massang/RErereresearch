from pipeline import annotations, db
from pipeline.ingest_web import ingest_document
from tests.conftest import FIXTURES


def test_schema_is_idempotent(archive):
    db.apply_schema(archive)
    db.apply_schema(archive)
    tables = {r[0] for r in archive.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_type = 'BASE TABLE'").fetchall()}
    assert set(db.TABLES) <= tables
    assert archive.execute("SELECT value FROM schema_meta WHERE key='schema_version'").fetchone()[0] == str(db.SCHEMA_VERSION)


def test_every_table_starts_empty(archive):
    assert all(v == 0 for v in db.table_counts(archive).values())


def _seed(con):
    sid, _ = ingest_document(con, str(FIXTURES / "synthetic_page.html"), is_synthetic=True)
    tid = annotations.add_trader(con, "SYNTHETIC-TRADER-A", aliases=["syn-a"], is_synthetic=True)
    annotations.annotate(con, "source", sid, "note", {"k": 1}, annotator="test", is_synthetic=True)
    return sid, tid


def test_parquet_roundtrip(archive, tmp_path):
    _seed(archive)
    before = db.table_counts(archive)
    written = db.export_parquet(archive, tmp_path / "pq")
    assert len(written) == len(db.TABLES)

    fresh = db.connect(tmp_path / "fresh.duckdb")
    added = db.import_parquet(fresh, tmp_path / "pq")
    assert db.table_counts(fresh) == before
    assert added["sources"] == 1
    # list and JSON columns survive the trip
    assert fresh.execute("SELECT aliases FROM traders").fetchone()[0] == ["syn-a"]
    assert fresh.execute("SELECT value->>'k' FROM annotations").fetchone()[0] == "1"
    # importing again is an upsert, not a duplicate
    db.import_parquet(fresh, tmp_path / "pq")
    assert db.table_counts(fresh) == before


def test_purge_synthetic_removes_everything_flagged(archive):
    _seed(archive)
    real = annotations.add_trader(archive, "non-synthetic placeholder")
    assert db.synthetic_counts(archive)["sources"] == 1
    db.purge_synthetic(archive)
    counts = db.table_counts(archive)
    assert counts["traders"] == 1
    assert archive.execute("SELECT trader_id FROM traders").fetchone()[0] == real
    for t in ("sources", "web_snapshots", "artifacts", "annotations", "fetch_events"):
        assert counts[t] == 0, t
