# Data model

The database (`data/research.duckdb`, schema in `pipeline/schema.sql`) is the
source of truth. Everything under `research/`, `reports/` and `sources/` is
generated from it by `python -m pipeline export-all` (except hand-written
notes such as `research/traders/<slug>/notes.md`). `data/parquet/` is the
committed snapshot that `scripts/setup.sh` restores into a fresh container.

## Evidence layers

```
sources ──► artifacts (raw files, hashed)        source_candidates (queue, not yet ingested)
   │        transcripts ─► transcript_segments ─► candidate_moments (triage only)
   │        frames (stills at timestamps; decision windows)
   │        web_snapshots (page text per fetch)
   ▼
observations   one atomic piece of evidence, pinned to a locator, with a MODALITY:
               said | screen | action | onchain | document
   ▼
decisions      one observed BUY/ADD/SKIP/WATCH/HOLD/PARTIAL_SELL/SELL/MISSED
   └─ decision_metrics   metric readings with provenance (screen+frame / said+observation / onchain / derived)
   ▼
findings       rule-level conclusions with a fixed EVIDENCE TYPE:
               stated | observed | inferred | validated   (+ finding_evidence links)
   ▼
hypotheses     measurable statements; lineage via parent_id; every iteration has a rationale
   ▼
sim_runs       strategy runs on a named split; imitation and performance metrics stored separately
data_splits / holdout_log   chronological splits; holdout evaluated once, then burned
```

## Rules enforced in code

| rule | where |
|---|---|
| A value not visible is NULL — a missing reading is a missing row, never a guess | `decisions.add_reading` |
| A screen reading must cite the frame it was read from (same source as the decision) | `decisions.add_reading` |
| A said reading must cite the observation holding the quote | `decisions.add_reading` |
| Quotes are checked verbatim against the linked transcript/page (`quote_verified`) | `observations.verify_quote` |
| Search-derived quotes stay `quote_verified = NULL` until the cited page is fetched | `candidates.import_leads`, `observations.reverify_quotes` |
| Stated finding ⇒ ≥1 supporting `said` observation by that trader | `findings._rule_problems` |
| Observed finding ⇒ supporting decisions or screen/action/onchain observations, with `n_supporting` of `n_observable` | same |
| Inferred finding ⇒ `derived_from` ≥1 stated/observed finding | same |
| Validated finding ⇒ `validated_by` a sim run on validation/holdout data, and `derived_from` what it validates | same |
| A finding's evidence type never changes; `check-findings` catches out-of-band edits | `findings.check_integrity` |
| Root hypothesis ⇒ rests on ≥1 finding; refinement ⇒ cites the failing run or new findings | `findings.add_hypothesis` |
| Identities start as `lead`; `probable` needs high agent confidence + ≥2 independent domains; `verified` needs a primary source and a written reason | `annotations`, `candidates.import_leads` |
| Splits are chronological and never redefined; a holdout needs pre-registered pass criteria and is burned after one evaluation | `sim.splits` |
| Strategies only ever see a `PointInTimeView`; reading past `now` raises `LookaheadError` | `sim.pit` |
| Synthetic rows are flagged and purged with `purge-synthetic --yes`; exports exclude them | `db.purge_synthetic`, `exports` |

## Metric vocabulary

`pipeline/decisions.py: METRICS` holds canonical names and default units
(`market_cap_usd`, `liquidity_usd`, `token_age_s`, `txns`, `buys`, `sells`,
`unique_buyers`, `volume_usd`, `holders`, `top10_pct`, `dev_pct`,
`snipers_pct`, `insiders_pct`, `bundles_pct`, `pro_traders`, `kols`,
`viewers`, `bonding_curve_pct`, `social_posts_per_min`, ...). A field a tool
shows that does not map cleanly goes in as `x_<tool>_<field>` rather than
being forced into the wrong column. `metric_window` records the tool's window
("5m", "lifetime", "unknown") because the same label means different things
in different tools.

Several readings of the same metric at different `as_of_offset_s` (frames
before the decision) are how velocity and acceleration are reconstructed from
video. `v_decisions_wide` shows, per metric, the reading closest to and not
after the decision.

## Time

- `decisions.video_ts_s`: position in the recording.
- `decisions.decision_wallclock` + `wallclock_basis`: real time, from an
  on-chain transaction (best), stream start + offset (`videos.live_start_at`),
  or a clock visible on screen.
- Simulator events carry `ts` (when it happened) and `available_at` (when a
  live feed could have seen it). Strategies see an event at
  `available_at + detection_latency`.
