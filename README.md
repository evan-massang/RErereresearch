# RErereresearch — research archive pipeline

Infrastructure for collecting sources (videos, web pages, documents),
turning them into searchable text and stills, and recording **evidence-linked**
observations, traders and trade-level annotations in DuckDB + Parquet.

This repository currently contains **infrastructure only**: no research
data and no findings. Anything in the test suite is synthetic and flagged
`is_synthetic`.

## Quick start

```bash
scripts/setup.sh              # installs apt + pip deps, creates archive/ and the DB (idempotent)
python -m pytest              # offline test suite (live-network tests skip unless RR_NETWORK_TESTS=1)
python -m pipeline status     # table counts, fetch outcomes, tool versions, adapters
python -m pipeline check-network   # which hosts this environment can reach
```

In a Claude Code cloud session, `.claude/settings.json` runs
`scripts/session_start.sh` automatically, which runs `scripts/setup.sh`.

## Layout

```
pipeline/                  python package (python -m pipeline <command>)
  sources/                 swappable adapters
    base.py                VideoAdapter / WebAdapter protocols, records, SourceUnavailable
    ytdlp_adapter.py       yt-dlp (YouTube + other sites yt-dlp supports)
    local_adapter.py       local media files / saved HTML (offline fallback)
    http_adapter.py        httpx for pages and APIs
    __init__.py            adapter registry
  config.py                archive paths (RR_ARCHIVE overrides the root)
  ids.py                   deterministic + random IDs
  schema.sql               DuckDB schema (tables + views)
  db.py                    connect/apply schema, upsert, Parquet export/import, purge-synthetic
  provenance.py            hashing, artifact registry, fetch-event log, blocked/error classification
  media.py                 ffmpeg/ffprobe wrappers
  ingest_video.py          video metadata (+ optional media + captions)
  ingest_transcript.py     VTT/SRT/JSON/TXT parsing; pluggable speech-to-text (faster-whisper)
  frames.py                frames by timestamp / interval / scene change; clips
  ingest_web.py            page + document snapshots, main-text extraction, outbound links
  observations.py          evidence-linked observations with quote verification
  annotations.py           traders, identities, trades, trade evidence, annotations
  cli.py                   command-line interface
scripts/setup.sh           dependency installer (also --check)
scripts/session_start.sh   SessionStart hook for cloud sessions
tests/                     offline tests + opt-in live-network tests; fixtures are synthetic
archive/                   data root (see archive/README.md); only parquet/ is committed
```

## Modularity: swapping a source

Stages depend on the **adapter protocols**, not on a site:

| stage | interface | adapters today | fallback without network |
|---|---|---|---|
| video metadata / media / captions | `VideoAdapter` | `ytdlp`, `local` | `--adapter local` on files obtained another way (a yt-dlp `*.info.json` sidecar is used if present; `*.vtt`/`*.srt` next to the file are imported) |
| web pages / APIs | `WebAdapter` | `http`, `file` | `ingest-web --adapter file page.html --canonical-url <original URL>` |
| speech-to-text | `Transcriber` | `faster-whisper` | `ingest-captions` with an existing transcript |
| documents | — | `ingest-doc` | always local |

To add one, implement the protocol in `pipeline/sources/` (or a `Transcriber`
in `ingest_transcript.py`) and add it to the registry dict. Every adapter
raises `SourceUnavailable` with status `blocked` (network policy, proxy, bot
wall, rate limit) or `error`, and every attempt, successful or not, is
logged in `fetch_events`, so a blocked source is visible and can be retried
with another adapter.

## Commands

```
init | status | check-network
list-entries URI                    expand channel / playlist / 'ytsearchN:query' / directory
ingest-video URI [--adapter ytdlp|local] [--media video|audio] [--no-captions] [--lang en]
ingest-captions SOURCE_ID FILE      import VTT/SRT/JSON/TXT
transcribe SOURCE_ID [--model small] [--language en]
extract-frames SOURCE_ID (--at 1,2 | --every 10 | --scene 0.3) [--width 640]
extract-clip SOURCE_ID START END
ingest-web URI [--adapter http|file] [--canonical-url URL]
ingest-doc PATH [--title T]
add-observation --source-id ... --kind ... --content ... --extractor ... [locators]
import-observations FILE.jsonl      all-or-nothing bulk import
set-observation-status ID draft|reviewed|rejected
add-trader NAME | add-identity TRADER PLATFORM | add-trade ... | link-evidence TRADE OBS
annotate TYPE ID KEY VALUE --annotator WHO
export-parquet | import-parquet | purge-synthetic [--yes] | query SQL
```

All commands print JSON. Creation commands accept `--synthetic` for test data.

## Data integrity rules (enforced in code)

* Every observation references a source; locators (transcript segment, frame,
  snapshot) must belong to that same source.
* Quotes are checked verbatim (case/whitespace-insensitive) against the linked
  transcript or snapshot; the result is stored in `quote_verified`.
* A trade can be `corroborated`/`verified` only with linked evidence observations.
* Raw bytes are stored and SHA-256 hashed (`artifacts`); page re-fetches create
  new snapshots only when content changes.
* Synthetic rows are flagged and removable with `purge-synthetic --yes`.

## Persistence

Cloud containers are temporary. Raw media and the live DB are git-ignored;
`python -m pipeline export-parquet` writes `archive/parquet/*.parquet`, which
is committed and restored into a fresh DB by `scripts/setup.sh`.
