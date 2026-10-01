"""Live checks for the network-dependent stages. Skipped unless RR_NETWORK_TESTS=1.

They only check that each external dependency is reachable and returns the
shape the pipeline expects; they don't keep or assert any content.
Override the probe targets with RR_TEST_VIDEO_URL / RR_TEST_WEB_URL.
"""

import os

import pytest

from pipeline.ingest_transcript import FasterWhisperTranscriber
from pipeline.sources import get_video_adapter, get_web_adapter

pytestmark = [
    pytest.mark.network,
    pytest.mark.skipif(os.environ.get("RR_NETWORK_TESTS") != "1", reason="set RR_NETWORK_TESTS=1 to run"),
]

# "Me at the zoo" — the first YouTube upload; a long-lived public probe target.
VIDEO_URL = os.environ.get("RR_TEST_VIDEO_URL", "https://www.youtube.com/watch?v=jNQXAC9IVRw")
WEB_URL = os.environ.get("RR_TEST_WEB_URL", "https://example.com/")


def test_ytdlp_metadata_reachable():
    rec = get_video_adapter("ytdlp").fetch_metadata(VIDEO_URL)
    assert rec.external_id and rec.duration_s


def test_ytdlp_captions_reachable(tmp_path):
    adapter = get_video_adapter("ytdlp")
    rec = adapter.fetch_metadata(VIDEO_URL)
    tracks = adapter.fetch_captions(rec, tmp_path, ["en", "en-*"])
    assert all(t.path.exists() for t in tracks)


def test_http_reachable():
    page = get_web_adapter("http").fetch(WEB_URL)
    assert page.status_code == 200 and page.content


def test_whisper_model_download(tmp_path):
    t = FasterWhisperTranscriber(model="tiny", device="cpu", download_root=str(tmp_path))
    assert t._load() is not None
