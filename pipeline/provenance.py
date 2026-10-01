"""Provenance: content hashing, artifact registration, fetch-event logging."""

from __future__ import annotations

import hashlib
import mimetypes
import shutil
import subprocess
from contextlib import contextmanager
from functools import lru_cache
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any, Iterator

import duckdb

from . import config, db
from .ids import new_id, stable_id

# Substrings that mean "the network/policy refused us" rather than "the thing is broken".
_BLOCKED_MARKERS = (
    "tunnel connection failed: 403",
    "connect tunnel failed",
    "unable to connect to proxy",
    "proxyerror",
    "connect_rejected",
    "407 proxy authentication",
    "name or service not known",
    "temporary failure in name resolution",
    "network is unreachable",
    "connection refused",
    "sign in to confirm you",      # YouTube bot wall
    "http error 429",
)


def classify_error(err: BaseException | str) -> str:
    """Return 'blocked' for network/policy/bot-wall failures, else 'error'."""
    text = f"{type(err).__name__}: {err}" if isinstance(err, BaseException) else str(err)
    text = text.lower()
    return "blocked" if any(m in text for m in _BLOCKED_MARKERS) else "error"


class SourceUnavailable(RuntimeError):
    """Raised by adapters when a source cannot be reached or read.

    ``status`` is 'blocked' (network policy, proxy, bot wall, rate limit) or
    'error' (anything else). Callers can catch this and fall back to another
    adapter without knowing which adapter failed.
    """

    def __init__(self, message: str, status: str | None = None):
        super().__init__(message)
        self.status = status or classify_error(message)


def sha256_file(p: Path | str, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while block := f.read(chunk):
            h.update(block)
    return h.hexdigest()


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


@lru_cache(maxsize=1)
def tool_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for pkg in ("yt-dlp", "faster-whisper", "trafilatura", "beautifulsoup4", "httpx", "duckdb"):
        try:
            versions[pkg] = importlib_metadata.version(pkg)
        except importlib_metadata.PackageNotFoundError:
            versions[pkg] = "missing"
    if shutil.which("ffmpeg"):
        out = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True).stdout
        versions["ffmpeg"] = out.split("\n", 1)[0].split(" ")[2] if out else "unknown"
    else:
        versions["ffmpeg"] = "missing"
    from . import __version__

    versions["pipeline"] = __version__
    return versions


def register_artifact(
    con: duckdb.DuckDBPyConnection,
    source_id: str,
    role: str,
    file_path: Path | str,
    *,
    derived_from: str | None = None,
    details: dict[str, Any] | None = None,
) -> str:
    """Hash a file that now lives in the archive and record it."""
    file_path = Path(file_path)
    digest = sha256_file(file_path)
    artifact_id = stable_id("art", source_id, role, digest)
    db.upsert(con, "artifacts", {
        "artifact_id": artifact_id,
        "source_id": source_id,
        "role": role,
        "local_path": config.rel(file_path),
        "sha256": digest,
        "bytes": file_path.stat().st_size,
        "mime": mimetypes.guess_type(file_path.name)[0],
        "derived_from": derived_from,
        "created_at": db.now(),
        "details": details,
    })
    return artifact_id


def record_event(
    con: duckdb.DuckDBPyConnection,
    *,
    stage: str,
    adapter: str,
    requested_uri: str,
    status: str,
    started_at,
    source_id: str | None = None,
    error: str | None = None,
    details: dict[str, Any] | None = None,
) -> str:
    event_id = new_id("evt")
    db.upsert(con, "fetch_events", {
        "event_id": event_id,
        "source_id": source_id,
        "stage": stage,
        "adapter": adapter,
        "requested_uri": requested_uri,
        "status": status,
        "error": (error or "")[:4000] or None,
        "started_at": started_at,
        "finished_at": db.now(),
        "tool_versions": tool_versions(),
        "details": details,
    })
    return event_id


class _Event:
    def __init__(self) -> None:
        self.source_id: str | None = None
        self.details: dict[str, Any] = {}


@contextmanager
def tracked(con, *, stage: str, adapter: str, uri: str, source_id: str | None = None) -> Iterator[_Event]:
    """Log one fetch_events row for the enclosed block, success or failure.

    Set ``ev.source_id`` / ``ev.details`` inside the block. Exceptions are
    re-raised after logging; SourceUnavailable keeps its blocked/error status.
    """
    ev = _Event()
    ev.source_id = source_id
    started = db.now()
    try:
        yield ev
    except SourceUnavailable as e:
        record_event(con, stage=stage, adapter=adapter, requested_uri=uri, status=e.status,
                     started_at=started, source_id=ev.source_id, error=str(e), details=ev.details)
        raise
    except Exception as e:
        record_event(con, stage=stage, adapter=adapter, requested_uri=uri, status=classify_error(e),
                     started_at=started, source_id=ev.source_id, error=f"{type(e).__name__}: {e}",
                     details=ev.details)
        raise
    record_event(con, stage=stage, adapter=adapter, requested_uri=uri, status="ok",
                 started_at=started, source_id=ev.source_id, details=ev.details)
