"""Adapter behaviour that must hold without network access."""

import json

import httpx
import pytest

from pipeline.ingest_video import ingest_video
from pipeline.ingest_web import ingest_web
from pipeline.provenance import SourceUnavailable, classify_error
from pipeline.sources import (
    VIDEO_ADAPTERS, WEB_ADAPTERS, VideoAdapter, WebAdapter, get_video_adapter, get_web_adapter,
)
from pipeline.sources.http_adapter import HttpWebAdapter
from pipeline.sources.ytdlp_adapter import YtDlpAdapter, normalize_info
from tests.conftest import FIXTURES

PROXY_403 = ("ERROR: [youtube] X: Unable to download API page: ('Unable to connect to proxy', "
             "OSError('Tunnel connection failed: 403 Forbidden'))")


def test_registered_adapters_satisfy_protocols():
    for name in VIDEO_ADAPTERS:
        assert isinstance(get_video_adapter(name), VideoAdapter), name
    for name in WEB_ADAPTERS:
        assert isinstance(get_web_adapter(name), WebAdapter), name
    with pytest.raises(ValueError):
        get_video_adapter("nope")


@pytest.mark.parametrize("msg,expected", [
    (PROXY_403, "blocked"),
    ("curl: (56) CONNECT tunnel failed, response 403", "blocked"),
    ("Sign in to confirm you're not a bot", "blocked"),
    ("HTTP Error 429: Too Many Requests", "blocked"),
    ("Video unavailable. This video is private", "error"),
    ("KeyError: 'id'", "error"),
])
def test_classify_error(msg, expected):
    assert classify_error(msg) == expected


def test_normalize_ytdlp_info():
    info = json.loads((FIXTURES / "synthetic_ytdlp_info.json").read_text())
    rec = normalize_info(info, "https://youtu.be/SYNTHETIC01")
    assert rec.platform == "youtube" and rec.external_id == "SYNTHETIC01"
    assert rec.upload_date.isoformat() == "2001-02-03"
    assert rec.published_at.year == 2001
    assert rec.duration_s == 6.0
    assert rec.manual_caption_langs == ["en"] and rec.auto_caption_langs == ["de", "en"]
    assert "formats" not in rec.raw and "thumbnails" not in rec.raw
    assert rec.raw["title"].startswith("[SYNTHETIC]")


def test_ytdlp_proxy_block_is_logged_as_blocked(archive, monkeypatch):
    import yt_dlp

    class Boom:
        def __init__(self, *a, **k): ...
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def extract_info(self, *a, **k): raise yt_dlp.utils.DownloadError(PROXY_403)

    monkeypatch.setattr(yt_dlp, "YoutubeDL", Boom)
    res = ingest_video(archive, "https://www.youtube.com/watch?v=SYNTHETIC01", YtDlpAdapter())
    assert res.source_id is None
    assert res.stages["video_metadata"] == "blocked"
    row = archive.execute("SELECT stage, adapter, status FROM fetch_events").fetchone()
    assert row == ("video_metadata", "ytdlp", "blocked")
    assert archive.execute("SELECT count(*) FROM sources").fetchone()[0] == 0


def test_ytdlp_metadata_through_ingest_with_stubbed_extractor(archive, monkeypatch):
    """The full ingest path for a yt-dlp source, with the network call replaced by a SYNTHETIC info dict."""
    info = json.loads((FIXTURES / "synthetic_ytdlp_info.json").read_text())
    monkeypatch.setattr(YtDlpAdapter, "_run", lambda self, uri, download, **kw: info)
    res = ingest_video(archive, "https://youtu.be/SYNTHETIC01", YtDlpAdapter(), captions=False,
                       is_synthetic=True)
    assert res.stages["video_metadata"] == "ok"
    row = archive.execute("SELECT s.platform, s.author, v.channel_id, v.tags, v.available_captions->>'auto' "
                          "FROM sources s JOIN videos v USING (source_id)").fetchone()
    assert row[:4] == ("youtube", "Synthetic Channel", "UC_SYNTHETIC_CHANNEL", ["synthetic", "test"])


def _mock_adapter(handler):
    return HttpWebAdapter(transport=httpx.MockTransport(handler))


def test_http_adapter_success_and_redirect(archive):
    page = (FIXTURES / "synthetic_page.html").read_bytes()

    def handler(req):
        if req.url.path == "/old":
            return httpx.Response(301, headers={"location": "https://synthetic.invalid/new"})
        return httpx.Response(200, content=page, headers={"content-type": "text/html; charset=utf-8"})

    sid, snap = ingest_web(archive, "https://synthetic.invalid/old", _mock_adapter(handler), is_synthetic=True)
    final_url, status = archive.execute("SELECT final_url, http_status FROM web_snapshots").fetchone()
    assert final_url == "https://synthetic.invalid/new" and status == 200
    links = json.loads(archive.execute("SELECT links FROM web_snapshots").fetchone()[0])
    assert "https://synthetic.invalid/relative/page.html" in links       # resolved against final URL


@pytest.mark.parametrize("code,status", [(403, "blocked"), (429, "blocked"), (404, "error"), (500, "error")])
def test_http_adapter_status_mapping(archive, code, status):
    adapter = _mock_adapter(lambda req: httpx.Response(code))
    with pytest.raises(SourceUnavailable) as e:
        ingest_web(archive, "https://synthetic.invalid/x", adapter)
    assert e.value.status == status
    assert archive.execute("SELECT status FROM fetch_events").fetchone()[0] == status


def test_http_adapter_proxy_error_is_blocked():
    def handler(req):
        raise httpx.ProxyError("Tunnel connection failed: 403 Forbidden")

    with pytest.raises(SourceUnavailable) as e:
        _mock_adapter(handler).fetch("https://synthetic.invalid/")
    assert e.value.status == "blocked"
