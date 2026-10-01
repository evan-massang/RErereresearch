"""yt-dlp adapter: YouTube and the ~1,800 other sites yt-dlp supports.

Nothing here is YouTube-specific except the defaults; the platform is taken
from yt-dlp's extractor name.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .base import CaptionTrack, SourceUnavailable, VideoRecord

# Bulky keys dropped from the stored raw payload (they are re-derivable).
_DROP_KEYS = {"formats", "thumbnails", "automatic_captions", "subtitles", "requested_formats",
              "requested_downloads", "heatmap", "http_headers", "_format_sort_fields"}


def _parse_upload_date(s: str | None) -> date | None:
    if not s or len(s) != 8:
        return None
    try:
        return datetime.strptime(s, "%Y%m%d").date()
    except ValueError:
        return None


def normalize_info(info: dict[str, Any], uri: str) -> VideoRecord:
    """Convert a yt-dlp info dict into a VideoRecord (pure; unit-testable offline)."""
    ts = info.get("timestamp") or info.get("release_timestamp")
    published = datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None
    platform = (info.get("extractor_key") or info.get("extractor") or "unknown").lower()
    return VideoRecord(
        platform=platform,
        external_id=str(info.get("id")),
        uri=uri,
        canonical_url=info.get("webpage_url") or info.get("original_url"),
        title=info.get("title"),
        channel_id=info.get("channel_id"),
        channel_name=info.get("channel"),
        uploader=info.get("uploader"),
        upload_date=_parse_upload_date(info.get("upload_date")),
        published_at=published,
        duration_s=float(info["duration"]) if info.get("duration") is not None else None,
        view_count=info.get("view_count"),
        like_count=info.get("like_count"),
        description=info.get("description"),
        tags=list(info.get("tags") or []),
        language=info.get("language"),
        chapters=info.get("chapters"),
        manual_caption_langs=sorted((info.get("subtitles") or {}).keys()),
        auto_caption_langs=sorted((info.get("automatic_captions") or {}).keys()),
        raw={k: v for k, v in info.items() if k not in _DROP_KEYS},
    )


class YtDlpAdapter:
    name = "ytdlp"

    def __init__(self, cookies_file: str | None = None, extra_opts: dict[str, Any] | None = None):
        self.cookies_file = cookies_file
        self.extra_opts = extra_opts or {}

    def _opts(self, **kw: Any) -> dict[str, Any]:
        opts: dict[str, Any] = {"quiet": True, "no_warnings": True, "noprogress": True, "retries": 3}
        if self.cookies_file:
            opts["cookiefile"] = self.cookies_file
        opts.update(self.extra_opts)
        opts.update(kw)
        return opts

    def _run(self, uri: str, download: bool, **opts: Any) -> dict[str, Any]:
        import yt_dlp

        try:
            with yt_dlp.YoutubeDL(self._opts(**opts)) as ydl:
                info = ydl.extract_info(uri, download=download)
                return ydl.sanitize_info(info)
        except yt_dlp.utils.DownloadError as e:
            raise SourceUnavailable(str(e)) from e

    def fetch_metadata(self, uri: str) -> VideoRecord:
        info = self._run(uri, download=False, skip_download=True)
        if info.get("_type") == "playlist":
            raise SourceUnavailable(
                f"{uri} is a playlist/channel; expand it with list_entries first", status="error")
        return normalize_info(info, uri)

    def list_entries(self, uri: str, limit: int | None = None) -> list[str]:
        """Channel / playlist URL, or a search like 'ytsearch20:<query>'."""
        opts: dict[str, Any] = {"extract_flat": "in_playlist", "skip_download": True}
        if limit:
            opts["playlistend"] = limit
        info = self._run(uri, download=False, **opts)
        entries = info.get("entries") or [info]
        urls = [e.get("url") or e.get("webpage_url") for e in entries if e]
        return [u for u in urls if u][:limit] if limit else [u for u in urls if u]

    def download_media(self, record: VideoRecord, dest_dir: Path, audio_only: bool = False) -> Path:
        dest_dir.mkdir(parents=True, exist_ok=True)
        fmt = "bestaudio/best" if audio_only else "bv*[height<=720]+ba/b[height<=720]/b"
        info = self._run(
            record.canonical_url or record.uri, download=True,
            format=fmt, outtmpl=str(dest_dir / "%(id)s.%(ext)s"),
            merge_output_format=None if audio_only else "mp4",
        )
        downloads = info.get("requested_downloads") or []
        if downloads and downloads[0].get("filepath"):
            return Path(downloads[0]["filepath"])
        candidates = sorted(p for p in dest_dir.glob(f"{record.external_id}.*")
                            if p.suffix not in {".json", ".vtt", ".srt", ".part"})
        if not candidates:
            raise SourceUnavailable("yt-dlp reported success but no media file was written", status="error")
        return candidates[0]

    def fetch_captions(self, record: VideoRecord, dest_dir: Path, languages: list[str]) -> list[CaptionTrack]:
        dest_dir.mkdir(parents=True, exist_ok=True)
        self._run(
            record.canonical_url or record.uri, download=True,
            skip_download=True, writesubtitles=True, writeautomaticsub=True,
            subtitleslangs=languages, subtitlesformat="vtt/srt/best",
            outtmpl=str(dest_dir / "%(id)s.%(ext)s"),
        )
        tracks = []
        for p in sorted(dest_dir.glob(f"{record.external_id}.*")):
            if p.suffix not in {".vtt", ".srt"}:
                continue
            lang = p.suffixes[-2].lstrip(".") if len(p.suffixes) >= 2 else None
            # yt-dlp prefers manual subs over auto for the same language.
            kind = "manual" if lang in record.manual_caption_langs else "auto"
            tracks.append(CaptionTrack(language=lang, kind=kind, path=p))
        return tracks
