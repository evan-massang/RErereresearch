from pathlib import Path

import pytest

from pipeline import config
from pipeline.ingest_transcript import (
    Segment, ingest_caption_file, load_transcript_file, parse_cues, parse_plain_text, transcribe,
    transcript_text,
)
from pipeline.ingest_video import ingest_video
from pipeline.sources import get_video_adapter
from tests.conftest import FIXTURES


def test_vtt_rollup_duplicates_and_tags_are_cleaned():
    segs = load_transcript_file(FIXTURES / "synthetic_captions.vtt")
    texts = [s.text for s in segs]
    assert texts == [
        "synthetic caption line one",
        "placeholder & test line two",
        "the quick brown fox is a test sentence",
        "end of synthetic fixture",
    ]
    assert segs[0].start_s == 0.0 and segs[0].end_s == 1.5
    assert segs[-1].start_s == 4.5


def test_srt_parsing_including_hours():
    segs = load_transcript_file(FIXTURES / "synthetic_captions.srt")
    assert [s.text for s in segs] == [
        "SYNTHETIC srt line one",
        "SYNTHETIC srt line two continued on a second line",
        "an hour in",
    ]
    assert segs[1].end_s == 4.25
    assert segs[2].start_s == 3600.0


def test_short_vtt_timestamps():
    segs = parse_cues("WEBVTT\n\n01:02.500 --> 01:03.000\nhi\n")
    assert segs[0].start_s == 62.5


def test_plain_text_is_untimed():
    segs = parse_plain_text("para one\nwraps\n\npara two")
    assert [s.text for s in segs] == ["para one wraps", "para two"]
    assert segs[0].start_s is None


def test_ingest_caption_file_requires_known_source(archive):
    with pytest.raises(ValueError):
        ingest_caption_file(archive, "src_missing", FIXTURES / "synthetic_captions.vtt")


class FakeTranscriber:
    """Stands in for faster-whisper so ASR plumbing is testable offline. Output is SYNTHETIC."""

    name = "fake"
    model_name = "synthetic-v0"

    def __init__(self):
        self.seen = None

    def transcribe(self, audio_path: Path, language):
        self.seen = audio_path
        return [Segment(0.0, 2.0, "synthetic asr one", -0.1), Segment(2.0, 4.0, "synthetic asr two", -0.2)], \
               {"language": "en", "duration": 6.0}


def test_transcribe_pipeline_with_fake_engine(archive, synthetic_video):
    res = ingest_video(archive, str(synthetic_video), get_video_adapter("local"), media="video",
                       captions=False, is_synthetic=True)
    fake = FakeTranscriber()
    tid = transcribe(archive, res.source_id, transcriber=fake)
    assert fake.seen.suffix == ".wav" and fake.seen.exists()
    assert transcript_text(archive, tid) == "synthetic asr one\nsynthetic asr two"
    row = archive.execute("SELECT method, model, language, segment_count FROM transcripts WHERE transcript_id=?",
                          [tid]).fetchone()
    assert row == ("asr", "fake:synthetic-v0", "en", 2)
    path = archive.execute("SELECT a.local_path FROM transcripts t JOIN artifacts a USING (artifact_id) "
                           "WHERE transcript_id=?", [tid]).fetchone()[0]
    assert config.resolve(path).exists()
    # re-running replaces rather than duplicates
    transcribe(archive, res.source_id, transcriber=fake)
    assert archive.execute("SELECT count(*) FROM transcript_segments WHERE transcript_id=?", [tid]).fetchone()[0] == 2
