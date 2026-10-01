"""Adapter registry.

To add a source: write a class implementing VideoAdapter or WebAdapter
(see base.py) and add it to the dict below. Every CLI command takes
``--adapter <name>``, so nothing downstream changes.
"""

from __future__ import annotations

from typing import Callable

from .base import CaptionTrack, SourceUnavailable, VideoAdapter, VideoRecord, WebAdapter, WebPage
from .http_adapter import HttpWebAdapter
from .local_adapter import FileWebAdapter, LocalVideoAdapter
from .ytdlp_adapter import YtDlpAdapter

VIDEO_ADAPTERS: dict[str, Callable[..., VideoAdapter]] = {
    "ytdlp": YtDlpAdapter,
    "local": LocalVideoAdapter,
}

WEB_ADAPTERS: dict[str, Callable[..., WebAdapter]] = {
    "http": HttpWebAdapter,
    "file": FileWebAdapter,
}


def get_video_adapter(name: str, **kwargs) -> VideoAdapter:
    try:
        return VIDEO_ADAPTERS[name](**kwargs)
    except KeyError:
        raise ValueError(f"unknown video adapter {name!r}; known: {sorted(VIDEO_ADAPTERS)}") from None


def get_web_adapter(name: str, **kwargs) -> WebAdapter:
    try:
        return WEB_ADAPTERS[name](**kwargs)
    except KeyError:
        raise ValueError(f"unknown web adapter {name!r}; known: {sorted(WEB_ADAPTERS)}") from None


__all__ = [
    "VIDEO_ADAPTERS", "WEB_ADAPTERS", "get_video_adapter", "get_web_adapter",
    "VideoAdapter", "WebAdapter", "VideoRecord", "CaptionTrack", "WebPage", "SourceUnavailable",
]
