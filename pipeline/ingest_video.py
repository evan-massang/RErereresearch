"""Video metadata ingestion (+ optional media download and captions).

Each sub-stage is logged separately in fetch_events, and a failure in an
optional sub-stage (media, captions) does not undo the metadata that did
succeed — the result reports per-stage status instead.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import duckdb

from . import config, db
from .ids import stable_id
from .ingest_transcript import ingest_caption_file
from .provenance import SourceUnavailable, register_artifact, tracked
from .sources.base import VideoAdapter, VideoRecord


@dataclass
class VideoIngestResult:
    source_id: str | None
    stages: dict[str, str] = field(default_factory=dict)       # stage -> ok | blocked | error | skipped
    errors: dict[str, str] = field(default_factory=dict)
    transcript_ids: list[str] = field(default_factory=list)
    media_path: str | None = None


def video_source_id(rec: VideoRecord) -> str:
    return stable_id("src", "video", rec.platform, rec.external_id)


def _store_metadata(con, rec: VideoRecord, adapter_name: str, source_id: str,
                    is_synthetic: bool, notes: str | None) -> None:
    prev = con.execute("SELECT first_seen_at FROM sources WHERE source_id = ?", [source_id]).fetchone()
    now = db.now()
    db.upsert(con, "sources", {
        "source_id": source_id, "source_kind": "video", "platform": rec.platform,
        "external_id": rec.external_id, "uri": rec.uri, "canonical_url": rec.canonical_url,
        "title": rec.title, "author": rec.channel_name or rec.uploader,
        "published_at": rec.published_at, "first_seen_at": prev[0] if prev else now,
        "last_fetched_at": now, "adapter": adapter_name, "metadata": rec.raw,
        "is_synthetic": is_synthetic, "notes": notes,
    })
    db.upsert(con, "videos", {
        "source_id": source_id, "channel_id": rec.channel_id, "channel_name": rec.channel_name,
        "uploader": rec.uploader, "upload_date": rec.upload_date, "duration_s": rec.duration_s,
        "view_count": rec.view_count, "like_count": rec.like_count, "description": rec.description,
        "tags": rec.tags, "language": rec.language, "chapters": rec.chapters,
        "available_captions": {"manual": rec.manual_caption_langs, "auto": rec.auto_caption_langs},
        "was_live": rec.was_live, "live_status": rec.live_status, "live_start_at": rec.live_start_at,
    })


def ingest_video(
    con: duckdb.DuckDBPyConnection,
    uri: str,
    adapter: VideoAdapter,
    *,
    media: str | None = None,            # None | "video" | "audio"
    captions: bool = True,
    languages: list[str] | None = None,
    is_synthetic: bool = False,
    notes: str | None = None,
) -> VideoIngestResult:
    languages = languages or ["en", "en-*"]
    result = VideoIngestResult(source_id=None)

    # 1. metadata (required) -------------------------------------------------
    try:
        with tracked(con, stage="video_metadata", adapter=adapter.name, uri=uri) as ev:
            rec = adapter.fetch_metadata(uri)
            source_id = video_source_id(rec)
            ev.source_id = result.source_id = source_id
            _store_metadata(con, rec, adapter.name, source_id, is_synthetic, notes)
            raw_dir = config.path("raw_video", rec.platform, rec.external_id)
            info_path = raw_dir / "info.json"
            info_path.write_text(json.dumps(rec.raw, default=str, ensure_ascii=False, indent=1))
            register_artifact(con, source_id, "info_json", info_path)
    except SourceUnavailable as e:
        result.stages["video_metadata"], result.errors["video_metadata"] = e.status, str(e)
        return result
    result.stages["video_metadata"] = "ok"

    # 2. media (optional) ------------------------------------------------------
    if media:
        try:
            with tracked(con, stage="media", adapter=adapter.name, uri=uri, source_id=source_id) as ev:
                path = adapter.download_media(rec, raw_dir, audio_only=(media == "audio"))
                aid = register_artifact(con, source_id, media, path)
                ev.details = {"artifact_id": aid}
                result.media_path = str(path)
            result.stages["media"] = "ok"
        except SourceUnavailable as e:
            result.stages["media"], result.errors["media"] = e.status, str(e)
    else:
        result.stages["media"] = "skipped"

    # 3. captions (optional) ---------------------------------------------------
    if captions:
        try:
            with tracked(con, stage="captions", adapter=adapter.name, uri=uri, source_id=source_id) as ev:
                tracks = adapter.fetch_captions(rec, config.path("raw_subtitles", source_id), languages)
                ev.details = {"tracks": [t.path.name for t in tracks]}
            for t in tracks:
                method = {"manual": "platform_manual", "auto": "platform_auto"}.get(t.kind, "imported")
                result.transcript_ids.append(
                    ingest_caption_file(con, source_id, t.path, method=method, language=t.language))
            result.stages["captions"] = "ok" if tracks else "none_available"
        except SourceUnavailable as e:
            result.stages["captions"], result.errors["captions"] = e.status, str(e)
    else:
        result.stages["captions"] = "skipped"

    return result
