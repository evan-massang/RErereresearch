"""Adapter interfaces.

Each pipeline stage talks to these protocols, never to a specific site or
tool. To substitute a source (a different video host, an archive mirror, a
folder of manually downloaded files, an API) implement the protocol and
register it in ``pipeline/sources/__init__.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from ..provenance import SourceUnavailable  # re-exported for adapters

__all__ = [
    "VideoRecord", "CaptionTrack", "WebPage",
    "VideoAdapter", "WebAdapter", "SourceUnavailable",
]


@dataclass
class VideoRecord:
    platform: str                      # e.g. "youtube", "local", "vimeo"
    external_id: str                   # platform-native ID (or file hash for local files)
    uri: str                           # what was requested
    canonical_url: str | None = None
    title: str | None = None
    channel_id: str | None = None
    channel_name: str | None = None
    uploader: str | None = None
    upload_date: date | None = None
    published_at: datetime | None = None
    duration_s: float | None = None
    view_count: int | None = None
    like_count: int | None = None
    description: str | None = None
    tags: list[str] = field(default_factory=list)
    language: str | None = None
    chapters: list[dict[str, Any]] | None = None
    manual_caption_langs: list[str] = field(default_factory=list)
    auto_caption_langs: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)   # full adapter payload
    local_media_path: Path | None = None                # set when media is already on disk


@dataclass
class CaptionTrack:
    language: str | None
    kind: str          # "manual" | "auto" | "imported"
    path: Path


@dataclass
class WebPage:
    uri: str
    final_url: str
    status_code: int | None
    content: bytes
    content_type: str | None
    headers: dict[str, str] = field(default_factory=dict)


@runtime_checkable
class VideoAdapter(Protocol):
    name: str

    def fetch_metadata(self, uri: str) -> VideoRecord:
        """Return metadata for one video. Raise SourceUnavailable on failure."""

    def list_entries(self, uri: str, limit: int | None = None) -> list[str]:
        """Expand a channel/playlist/search URI into individual video URIs."""

    def download_media(self, record: VideoRecord, dest_dir: Path, audio_only: bool = False) -> Path:
        """Fetch the media file into dest_dir and return its path."""

    def fetch_captions(self, record: VideoRecord, dest_dir: Path, languages: list[str]) -> list[CaptionTrack]:
        """Fetch available caption tracks into dest_dir (may return [])."""


@runtime_checkable
class WebAdapter(Protocol):
    name: str

    def fetch(self, uri: str) -> WebPage:
        """Return the raw page. Raise SourceUnavailable on failure."""
