"""Local-file adapters: the offline fallback for every stage.

LocalVideoAdapter ingests a media file already on disk (downloaded by hand,
from another tool, from a mirror). If a yt-dlp style ``<stem>.info.json``
sits next to it, its metadata is used; caption files named ``<stem>*.vtt`` /
``<stem>*.srt`` are picked up as imported captions.

FileWebAdapter ingests saved HTML (browser "Save page", archive.org dumps, ...).
"""

from __future__ import annotations

import json
import mimetypes
import shutil
from pathlib import Path

from ..media import ffprobe
from ..provenance import sha256_file
from .base import CaptionTrack, SourceUnavailable, VideoRecord, WebPage
from .ytdlp_adapter import normalize_info


class LocalVideoAdapter:
    name = "local"

    def fetch_metadata(self, uri: str) -> VideoRecord:
        p = Path(uri.removeprefix("file://")).expanduser().resolve()
        if not p.is_file():
            raise SourceUnavailable(f"no such file: {p}", status="error")
        probe = ffprobe(p)
        duration = probe.get("format", {}).get("duration")
        sidecar = p.with_name(p.stem + ".info.json")
        if sidecar.exists():
            rec = normalize_info(json.loads(sidecar.read_text()), uri)
        else:
            tags = probe.get("format", {}).get("tags", {}) or {}
            rec = VideoRecord(
                platform="local",
                external_id=sha256_file(p)[:16],
                uri=str(p),
                title=tags.get("title") or p.stem,
                raw={"ffprobe": probe, "filename": p.name},
            )
        if rec.duration_s is None and duration is not None:
            rec.duration_s = float(duration)
        rec.local_media_path = p
        return rec

    def list_entries(self, uri: str, limit: int | None = None) -> list[str]:
        d = Path(uri).expanduser()
        exts = {".mp4", ".mkv", ".webm", ".mov", ".m4a", ".mp3", ".wav", ".opus", ".flac"}
        files = sorted(str(f.resolve()) for f in d.iterdir() if f.suffix.lower() in exts) if d.is_dir() else [str(d)]
        return files[:limit] if limit else files

    def download_media(self, record: VideoRecord, dest_dir: Path, audio_only: bool = False) -> Path:
        if record.local_media_path is None:
            raise SourceUnavailable("record has no local media path", status="error")
        dest_dir.mkdir(parents=True, exist_ok=True)
        target = dest_dir / record.local_media_path.name
        if target.resolve() != record.local_media_path.resolve():
            shutil.copy2(record.local_media_path, target)
        return target

    def fetch_captions(self, record: VideoRecord, dest_dir: Path, languages: list[str]) -> list[CaptionTrack]:
        if record.local_media_path is None:
            return []
        src = record.local_media_path
        stem = src.stem
        dest_dir.mkdir(parents=True, exist_ok=True)
        tracks = []
        for c in sorted(src.parent.glob(stem + "*")):
            if c.suffix.lower() not in {".vtt", ".srt"}:
                continue
            parts = c.name[len(stem):].split(".")
            lang = parts[-2] if len(parts) >= 3 and parts[-2] else None
            if languages and lang and not any(lang.startswith(l.rstrip("*").split("-")[0]) for l in languages):
                continue
            target = dest_dir / c.name
            shutil.copy2(c, target)
            tracks.append(CaptionTrack(language=lang, kind="imported", path=target))
        return tracks


class FileWebAdapter:
    name = "file"

    def fetch(self, uri: str) -> WebPage:
        p = Path(uri.removeprefix("file://")).expanduser().resolve()
        if not p.is_file():
            raise SourceUnavailable(f"no such file: {p}", status="error")
        return WebPage(
            uri=uri, final_url=p.as_uri(), status_code=None, content=p.read_bytes(),
            content_type=mimetypes.guess_type(p.name)[0] or "text/html",
        )
