# RErereresearch

Research into how skilled Solana memecoin traders make short-duration
decisions: observe them trading (stream recordings, videos, on-chain
activity), reconstruct what they saw and did, turn it into measurable
features, and test those features without lookahead.

- **Brief (governing document):** [`docs/RESEARCH_BRIEF.md`](docs/RESEARCH_BRIEF.md)
- **Status, plan, blocked items:** [`docs/RESEARCH_PLAN.md`](docs/RESEARCH_PLAN.md)
- **How to do the research with the tools:** [`docs/WORKFLOW.md`](docs/WORKFLOW.md)
- **Tables and evidence rules:** [`docs/DATA_MODEL.md`](docs/DATA_MODEL.md)

No research findings exist yet. Trader identities are search-derived leads
(`research/traders/<slug>/identity.md`); test data is synthetic and flagged.

## Quick start

```bash
scripts/setup.sh                    # deps + data layout + DB (idempotent; runs automatically in cloud sessions)
python -m pytest                    # offline suite; live-network tests opt in with RR_NETWORK_TESTS=1
python -m pipeline check-network    # what this environment can reach
python -m pipeline status
python -m pipeline candidates --trader decu
```

## Layout

```
docs/                     brief, plan, workflow, data model
pipeline/                 python package: python -m pipeline <command>
  sources/                swappable adapters: yt-dlp, local files, HTTP, saved HTML
  ingest_video.py         video metadata (+ media, captions); live-stream start time
  ingest_transcript.py    VTT/SRT/JSON/TXT parsing; pluggable speech-to-text (faster-whisper)
  moments.py              transcript triage: candidate entry/exit/skip/rug moments
  frames.py               frames by time/interval/scene; decision windows densified on screen change
  ingest_web.py           page/document snapshots, main text, outbound links
  candidates.py           source queue, search citations, lead import, source ledger
  observations.py         evidence with modality (said/screen/action/onchain/document), quote checks
  decisions.py            tokens, narratives, decisions, metric readings with provenance
  findings.py             stated/observed/inferred/validated findings, hypotheses, features
  annotations.py          traders, identities (lead→verified), trades, annotations
  exports.py              research/ + reports/ + sources/ generated from the DB
  sim/                    point-in-time view, execution model, engine, metrics, splits/holdout
  schema.sql, db.py, provenance.py, media.py, config.py, cli.py
data/                     raw/ processed/ (git-ignored) · parquet/ (committed) · research.duckdb (ignored)
research/                 traders/ videos/ transcripts/ frames/ trades/ rejected_tokens/ narratives/ observations/
reports/                  trader_profiles/ cross_trader_analysis/ hypotheses/ simulations/ failures/
sources/                  source_ledger.csv · leads/ (raw search-agent outputs)
scripts/                  setup.sh, session_start.sh
tests/                    offline tests with synthetic fixtures; opt-in live-network tests
```

## Modularity

Stages depend on adapter protocols, not sites. If a platform is unreachable,
the same stage runs from another adapter: `--adapter local` for media obtained
elsewhere (with a yt-dlp `.info.json` beside it if available), `--adapter file`
for saved pages, `ingest-captions` for an existing transcript. New sources go
in `pipeline/sources/` and the registry in `pipeline/sources/__init__.py`.
Every fetch attempt is logged in `fetch_events` as `ok`, `blocked` or `error`.

## Simulation guarantees

- Strategies receive only a `PointInTimeView`; asking for data past the
  current simulated time raises `LookaheadError`. Data at or after a run's end
  does not exist for that run.
- Fills happen at `decision + latencies` against the true pool state on the
  AMM curve with our size, after an explicit protocol fee; slippage tolerance
  failures and random failures revert and still cost network fees.
- Latency sweeps flag delays finer than the data's time resolution.
- Splits are chronological; the holdout runs once with pre-registered pass
  criteria and is then burned.
- Imitation metrics and performance metrics are stored separately.

## Persistence

The cloud container is temporary. Run `python -m pipeline export-all` and
commit `data/parquet`, `research`, `reports` and `sources` before stopping;
`scripts/setup.sh` restores the DB from `data/parquet` in a new container.
Raw media is not committed (size, licensing).
