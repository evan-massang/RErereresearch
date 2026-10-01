"""Archive locations.

Everything lives under one archive root so the whole archive can be moved,
synced, or swapped for a test directory. Override with ``RR_ARCHIVE``.
Paths stored in the database are relative to the archive root.
"""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Sub-directories of the archive root, keyed by purpose.
LAYOUT = {
    "db": "db",                      # research.duckdb
    "parquet": "parquet",            # one Parquet file per table (portable snapshot)
    "raw_video": "raw/video",        # <platform>/<external_id>/ media + info.json
    "raw_subtitles": "raw/subtitles",  # <source_id>/ caption files as downloaded
    "raw_web": "raw/web",            # <source_id>/ HTML snapshots
    "raw_documents": "raw/documents",  # manually supplied files (PDF, CSV, ...)
    "audio": "derived/audio",        # <source_id>/ 16 kHz mono WAV for ASR
    "transcripts": "derived/transcripts",  # <source_id>/ transcript JSON
    "frames": "derived/frames",      # <source_id>/ extracted stills
    "clips": "derived/clips",        # <source_id>/ extracted clips
    "exports": "exports",            # ad-hoc analysis outputs
}


def archive_root() -> Path:
    return Path(os.environ.get("RR_ARCHIVE", REPO_ROOT / "archive")).resolve()


def path(kind: str, *parts: str) -> Path:
    """Return (and create) a directory inside the archive."""
    p = archive_root() / LAYOUT[kind]
    for part in parts:
        p = p / part
    p.mkdir(parents=True, exist_ok=True)
    return p


def db_path() -> Path:
    return path("db") / "research.duckdb"


def ensure_layout() -> Path:
    root = archive_root()
    for kind in LAYOUT:
        path(kind)
    return root


def rel(p: Path | str) -> str:
    """Store paths relative to the archive root when possible."""
    p = Path(p).resolve()
    try:
        return str(p.relative_to(archive_root()))
    except ValueError:
        return str(p)


def resolve(stored: str) -> Path:
    p = Path(stored)
    return p if p.is_absolute() else archive_root() / p
