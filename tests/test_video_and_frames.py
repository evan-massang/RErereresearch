import pytest

from pipeline import config, frames
from pipeline.ingest_video import ingest_video
from pipeline.sources import get_video_adapter


def test_local_video_ingest_with_media_and_captions(archive, synthetic_video):
    res = ingest_video(archive, str(synthetic_video), get_video_adapter("local"), media="video",
                       languages=["en", "de"], is_synthetic=True)
    assert res.stages == {"video_metadata": "ok", "media": "ok", "captions": "ok"}
    src = archive.execute("SELECT source_kind, platform, title, is_synthetic FROM sources").fetchone()
    assert src == ("video", "local", "SYNTHETIC test clip", True)
    assert archive.execute("SELECT round(duration_s) FROM videos").fetchone()[0] == 6
    assert len(res.transcript_ids) == 2
    langs = {r[0] for r in archive.execute("SELECT language FROM transcripts").fetchall()}
    assert langs == {"en", "de"}
    roles = {r[0] for r in archive.execute("SELECT role FROM artifacts").fetchall()}
    assert {"info_json", "video", "subtitle"} <= roles
    statuses = archive.execute("SELECT stage, status FROM fetch_events ORDER BY started_at").fetchall()
    assert all(s == "ok" for _, s in statuses)


def test_reingest_is_idempotent(archive, synthetic_video):
    a = ingest_video(archive, str(synthetic_video), get_video_adapter("local"), captions=False, is_synthetic=True)
    first_seen = archive.execute("SELECT first_seen_at FROM sources").fetchone()[0]
    b = ingest_video(archive, str(synthetic_video), get_video_adapter("local"), captions=False, is_synthetic=True)
    assert a.source_id == b.source_id
    assert archive.execute("SELECT count(*) FROM sources").fetchone()[0] == 1
    assert archive.execute("SELECT first_seen_at FROM sources").fetchone()[0] == first_seen


def test_caption_language_filter(archive, synthetic_video):
    res = ingest_video(archive, str(synthetic_video), get_video_adapter("local"), languages=["en"],
                       is_synthetic=True)
    assert archive.execute("SELECT list(language) FROM transcripts").fetchone()[0] == ["en"]
    assert len(res.transcript_ids) == 1


def test_missing_file_is_reported_not_raised(archive):
    res = ingest_video(archive, "/nonexistent/clip.mp4", get_video_adapter("local"))
    assert res.source_id is None and res.stages["video_metadata"] == "error"
    assert archive.execute("SELECT status FROM fetch_events").fetchone()[0] == "error"


@pytest.fixture
def ingested(archive, synthetic_video):
    res = ingest_video(archive, str(synthetic_video), get_video_adapter("local"), media="video",
                       captions=False, is_synthetic=True)
    return archive, res.source_id


def test_frames_at_timestamps(ingested):
    con, sid = ingested
    ids = frames.extract_frames(con, sid, timestamps=[0.5, 4.0], width=80)
    rows = con.execute("SELECT timestamp_s, width, local_path FROM frames ORDER BY timestamp_s").fetchall()
    assert len(ids) == 2 and [r[0] for r in rows] == [0.5, 4.0]
    assert rows[0][1] == 80
    assert all(config.resolve(r[2]).exists() for r in rows)


def test_frames_every_interval(ingested):
    con, sid = ingested
    ids = frames.extract_frames(con, sid, every_s=2.0)
    ts = [r[0] for r in con.execute("SELECT timestamp_s FROM frames ORDER BY 1").fetchall()]
    assert ts == [0.0, 2.0, 4.0] and len(ids) == 3


def test_frames_scene_change_detects_the_cut(ingested):
    con, sid = ingested
    frames.extract_frames(con, sid, scene_threshold=0.3)
    ts = [r[0] for r in con.execute("SELECT timestamp_s FROM frames").fetchall()]
    assert len(ts) == 1 and abs(ts[0] - 3.0) < 0.2
    leftovers = list(config.path("frames", sid).glob("_scene_*"))
    assert leftovers == []


def test_frame_args_are_exclusive(ingested):
    con, sid = ingested
    with pytest.raises(ValueError):
        frames.extract_frames(con, sid, timestamps=[1.0], every_s=1.0)


def test_clip(ingested):
    con, sid = ingested
    aid = frames.extract_clip(con, sid, 1.0, 2.5)
    path, details = con.execute("SELECT local_path, details FROM artifacts WHERE artifact_id=?", [aid]).fetchone()
    from pipeline import media
    assert abs(media.duration_s(config.resolve(path)) - 1.5) < 0.2


def test_audio_only_media_rejects_frames(archive, synthetic_audio):
    res = ingest_video(archive, str(synthetic_audio), get_video_adapter("local"), media="audio",
                       captions=False, is_synthetic=True)
    with pytest.raises(ValueError, match="no video stream"):
        frames.extract_frames(archive, res.source_id, timestamps=[1.0])
