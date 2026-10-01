import json
from datetime import datetime, timezone

import pytest

from pipeline import annotations, frames, observations
from pipeline.ingest_video import ingest_video
from pipeline.ingest_web import ingest_document
from pipeline.sources import get_video_adapter
from tests.conftest import FIXTURES


@pytest.fixture
def video(archive, synthetic_video):
    res = ingest_video(archive, str(synthetic_video), get_video_adapter("local"), media="video",
                       languages=["en"], is_synthetic=True)
    return archive, res.source_id, res.transcript_ids[0]


def test_observation_from_transcript_segment_fills_times_and_verifies_quote(video):
    con, sid, tid = video
    oid = observations.add_observation(
        con, source_id=sid, kind="quote", content="SYNTHETIC: speaker says the test sentence",
        quote="The quick brown   FOX is a test sentence", transcript_id=tid, segment_seq=2,
        extractor="script:test", is_synthetic=True)
    start, end, verified = con.execute(
        "SELECT start_s, end_s, quote_verified FROM observations WHERE observation_id=?", [oid]).fetchone()
    assert (start, end, verified) == (3.0, 4.5, True)


def test_unverifiable_quote_is_flagged_false(video):
    con, sid, tid = video
    oid = observations.add_observation(
        con, source_id=sid, kind="quote", content="SYNTHETIC", quote="words never said",
        transcript_id=tid, extractor="script:test", is_synthetic=True)
    assert con.execute("SELECT quote_verified FROM observations WHERE observation_id=?", [oid]).fetchone()[0] is False


def test_frame_locator_and_ownership_checks(video, tmp_path):
    con, sid, tid = video
    fid = frames.extract_frames(con, sid, timestamps=[1.0])[0]
    oid = observations.add_observation(con, source_id=sid, kind="screenshot", content="SYNTHETIC frame note",
                                       frame_id=fid, extractor="human", is_synthetic=True)
    assert con.execute("SELECT start_s FROM observations WHERE observation_id=?", [oid]).fetchone()[0] == 1.0

    other, _ = ingest_document(con, str(FIXTURES / "synthetic_page.html"), is_synthetic=True)
    with pytest.raises(ValueError, match="belongs to"):
        observations.add_observation(con, source_id=other, kind="x", content="SYNTHETIC", frame_id=fid,
                                     extractor="human", is_synthetic=True)


@pytest.mark.parametrize("kwargs,match", [
    ({"source_id": "src_nope"}, "unknown source_id"),
    ({"content": "  "}, "content is required"),
    ({"status": "final"}, "status must be"),
    ({"confidence": 1.5}, "confidence"),
    ({"segment_seq": 0}, "requires transcript_id"),
    ({"trader_id": "trd_nope"}, "unknown trader_id"),
    ({"start_s": 5.0, "end_s": 1.0}, "end_s < start_s"),
])
def test_observation_validation(video, kwargs, match):
    con, sid, _ = video
    base = dict(source_id=sid, kind="claim", content="SYNTHETIC", extractor="human", is_synthetic=True)
    with pytest.raises(ValueError, match=match):
        observations.add_observation(con, **{**base, **kwargs})


def test_snapshot_quote_verification(archive):
    sid, snap = ingest_document(archive, str(FIXTURES / "synthetic_page.html"), is_synthetic=True)
    oid = observations.add_observation(archive, source_id=sid, snapshot_id=snap, kind="quote",
                                       content="SYNTHETIC", quote="alpha bravo charlie delta echo",
                                       extractor="human", is_synthetic=True)
    assert archive.execute("SELECT quote_verified FROM observations WHERE observation_id=?", [oid]).fetchone()[0]


def test_import_jsonl_is_atomic(video, tmp_path):
    con, sid, tid = video
    good = {"source_id": sid, "kind": "claim", "content": "SYNTHETIC a", "extractor": "script:test"}
    bad = {"source_id": "src_nope", "kind": "claim", "content": "SYNTHETIC b", "extractor": "script:test"}
    f = tmp_path / "obs.jsonl"
    f.write_text("\n".join(json.dumps(x) for x in (good, bad)))
    with pytest.raises(ValueError, match="line 2"):
        observations.import_jsonl(con, f, is_synthetic=True)
    assert con.execute("SELECT count(*) FROM observations").fetchone()[0] == 0

    f.write_text("\n".join(json.dumps(x) for x in (good, good)))
    assert len(observations.import_jsonl(con, f, is_synthetic=True)) == 2
    assert con.execute("SELECT bool_and(is_synthetic) FROM observations").fetchone()[0]


def test_traders_trades_evidence_and_annotations(video):
    con, sid, tid = video
    trader = annotations.add_trader(con, "SYNTHETIC-TRADER-A", aliases=["syn-a"], is_synthetic=True)
    annotations.add_trader_identity(con, trader, "synthetic-platform", handle="@synthetic",
                                    evidence_source_id=sid, is_synthetic=True)
    obs = observations.add_observation(con, source_id=sid, kind="trade_claim", content="SYNTHETIC entry",
                                       trader_id=trader, transcript_id=tid, segment_seq=1,
                                       extractor="human", is_synthetic=True)

    with pytest.raises(ValueError, match="requires at least one evidence"):
        annotations.add_trade(con, trader_id=trader, status="verified", is_synthetic=True)
    with pytest.raises(ValueError, match="exit_time before entry_time"):
        annotations.add_trade(con, trader_id=trader, entry_time=datetime(2001, 1, 2, tzinfo=timezone.utc),
                              exit_time=datetime(2001, 1, 1, tzinfo=timezone.utc), is_synthetic=True)

    trade = annotations.add_trade(con, trader_id=trader, instrument="TEST-XYZ", direction="long",
                                  entry_price=100.0, exit_price=110.0, outcome="win", status="corroborated",
                                  evidence=[(obs, "entry")], is_synthetic=True)
    row = con.execute("SELECT trader, evidence_count FROM v_trade_summary WHERE trade_id=?", [trade]).fetchone()
    assert row == ("SYNTHETIC-TRADER-A", 1)

    annotations.annotate(con, "trade", trade, "review_note", {"checked": False}, annotator="human",
                         is_synthetic=True)
    with pytest.raises(ValueError):
        annotations.annotate(con, "trade", "trade_nope", "k", 1, annotator="human")
    with pytest.raises(ValueError):
        annotations.annotate(con, "planet", trade, "k", 1, annotator="human")

    prov = con.execute("SELECT trader, source_kind, is_synthetic FROM v_observation_provenance").fetchone()
    assert prov == ("SYNTHETIC-TRADER-A", "video", True)
    assert observations.list_observations(con).empty                  # synthetic hidden by default
    assert len(observations.list_observations(con, include_synthetic=True, trader_id=trader)) == 1
