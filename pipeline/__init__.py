"""Research archive pipeline.

Stages (each usable on its own, each with swappable source adapters):

    sources/        adapters that fetch raw material (yt-dlp, local files, HTTP, ...)
    ingest_video    video metadata (+ optional media download and captions)
    ingest_transcript  subtitle parsing and speech-to-text transcription
    frames          frame / clip / audio extraction with FFmpeg
    ingest_web      webpage fetch + main-text extraction
    observations    evidence-linked observations extracted from sources
    annotations     traders, trader identities, trades, free-form annotations
    provenance      hashing, fetch events, tool versions
    db              DuckDB schema + Parquet export/import
"""

__version__ = "0.1.0"
