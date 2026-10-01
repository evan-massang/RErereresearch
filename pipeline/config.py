"""Project layout.

Everything lives under one project root (the repo by default) so the archive
can be moved or swapped for a test directory. Override with ``RR_ROOT``.
Paths stored in the database are relative to the root.

    data/        machine data: raw downloads, processed media, DuckDB, Parquet
    research/    human-readable research archive (committed)
    reports/     trader profiles, cross-trader analysis, hypotheses, simulations, failures
    sources/     source ledger (generated from the DB, committed)
"""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

LAYOUT = {
    # data/ — large or regenerable; only data/parquet is committed
    "data": "data",
    "parquet": "data/parquet",
    "raw_video": "data/raw/video",              # <platform>/<external_id>/ media + info.json
    "raw_subtitles": "data/raw/subtitles",      # <source_id>/ caption files as fetched
    "raw_web": "data/raw/web",                  # <source_id>/ page/document snapshots
    "raw_documents": "data/raw/documents",      # files supplied by hand
    "raw_streams": "data/raw/streams",          # <feed>/YYYYMMDD_HH.jsonl live recordings
    "audio": "data/processed/audio",            # <source_id>/ 16 kHz mono WAV for ASR
    "asr": "data/processed/transcripts",        # <source_id>/ ASR output JSON
    "frames": "data/processed/frames",          # <source_id>/ extracted stills
    "clips": "data/processed/clips",            # <source_id>/ cut clips
    "exports": "data/exports",                  # scratch analysis outputs
    # research/ — committed, human-readable
    "traders": "research/traders",              # <slug>/ identity.md, notes, model.md
    "videos": "research/videos",                # per-video worksheets (generated)
    "transcripts": "research/transcripts",      # <trader>/<source>.txt, rg-searchable (generated)
    "evidence_frames": "research/frames",       # <source_id>/ frames cited as evidence (copied)
    "trades": "research/trades",                # trade episodes CSV (generated)
    "rejected_tokens": "research/rejected_tokens",  # SKIP decisions CSV (generated)
    "narratives": "research/narratives",
    "observations": "research/observations",    # observations / findings CSV (generated)
    # reports/
    "trader_profiles": "reports/trader_profiles",
    "cross_trader": "reports/cross_trader_analysis",
    "hypothesis_reports": "reports/hypotheses",
    "simulation_reports": "reports/simulations",
    "failure_reports": "reports/failures",
    # sources/
    "ledger": "sources",
}


def root() -> Path:
    return Path(os.environ.get("RR_ROOT", REPO_ROOT)).resolve()


def path(kind: str, *parts: str) -> Path:
    """Return (and create) a directory inside the project root."""
    p = root() / LAYOUT[kind]
    for part in parts:
        p = p / part
    p.mkdir(parents=True, exist_ok=True)
    return p


def db_path() -> Path:
    return path("data") / "research.duckdb"


def ensure_layout() -> Path:
    for kind in LAYOUT:
        path(kind)
    return root()


def rel(p: Path | str) -> str:
    """Store paths relative to the project root when possible."""
    p = Path(p).resolve()
    try:
        return str(p.relative_to(root()))
    except ValueError:
        return str(p)


def resolve(stored: str) -> Path:
    p = Path(stored)
    return p if p.is_absolute() else root() / p
