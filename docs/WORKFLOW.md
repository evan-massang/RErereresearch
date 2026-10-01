# Research workflow

How a source becomes evidence, and evidence becomes a tested rule. Commands
are `python -m pipeline <command>`; every command prints JSON.

## 0. Before anything

```bash
python -m pipeline check-network      # what this container can reach today
python -m pipeline status
```

## 1. Identity first

Seeds are names, not accounts. `research/traders/<slug>/identity.md` lists
every account/wallet lead with its sources and doubts. Promote an identity
only with a primary source (the trader's own profile linking the account, a
post claiming the wallet) and say why:

```bash
python -m pipeline set-identity-status <identity_id> verified \
  --notes "Linktree fetched 2026-10-02 links this channel" --evidence-source <source_id>
```

Record lookalikes as `rejected` so nobody studies the wrong person.

## 2. Choose sources

`python -m pipeline candidates --trader decu` shows the queue. Prefer, in order:
long recorded trading sessions (stream VODs) > recorded sessions > trade
recaps > interviews/podcasts > tutorials. A session is most valuable when the
trader's wallet is known, because on-chain transactions give exact entry/exit
times, mints and sizes to align with the footage.

## 3. Ingest a video

```bash
python -m pipeline ingest-video <url> --media video --candidate-id <cand_id>
# no captions? transcribe:
python -m pipeline transcribe <source_id> --model small
python -m pipeline find-moments <transcript_id>          # triage: entry/exit/skip/rug... language
python -m pipeline worksheet <source_id>                 # research/videos/<source_id>.md
```

If a platform is unreachable, obtain the file another way and use
`--adapter local` (a yt-dlp `.info.json` beside it is used for metadata).

## 4. Inspect each decision moment (say / see / do)

For every candidate moment (start with `busiest_windows` on long streams, then
sweep the rest — rejections and quiet stretches matter too):

1. Read the transcript around it (`research/transcripts/<trader>/...`).
2. Extract frames before, at and after it, densified where the screen changes:
   ```bash
   python -m pipeline extract-window <source_id> <t> --before 20 --after 30
   ```
   Look at the frames *before* the action for what the trader saw, and after
   it for what they did next. Widen the window when a decision builds slowly.
3. Record what happened, keeping the three evidence forms apart:
   - what they **said** → `add-observation --modality said --quote "..." --transcript-id ... --segment N`
   - what the **screen** showed → `add-observation --modality screen --frame-id ...`
   - what they **did** → `add-decision --decision BUY|SKIP|... --at <t>` with
     `--stated-reason` (their words), `--observed-context` (screen), and
     `--inferred-reason` (ours, clearly separate)
4. Attach every metric visible before the decision, one reading per frame:
   ```bash
   python -m pipeline add-reading <decision_id> market_cap_usd --via screen --text '$12.4K' --frame-id <frame>
   ```
   Not visible → no reading. Never estimate a number that is not on screen or said.
5. Mark the moment reviewed: `review-moment <moment_id> confirmed --decision-id <decision_id>`
   (or `false_positive`).

Skips count as much as buys: when the trader looks at several tokens and
picks one, record a SKIP decision for each rejected token with the metrics
visible at that moment.

Batch work: write one JSONL line per decision (with readings) and load it with
`import-decisions` (all-or-nothing).

## 5. From decisions to findings

- **stated**: the trader said it (`--evidence observation:<said_obs>:supports`).
- **observed**: counted across coded decisions (`--n-supporting 35 --n-observable 42`).
- **inferred**: our interpretation, `derived_from` stated/observed findings.
- **validated**: only after a validation/holdout run supports it.

Add contradicting cases with `link-finding ... contradicts`. Re-run
`check-findings` before committing. Build each trader's model separately
(`reports/trader_profiles/<slug>.md`), funnel stage by funnel stage, before
comparing traders.

## 6. Hypotheses and simulation

1. `add-hypothesis` with a measurable definition, a rationale, and the
   findings it rests on.
2. `define-splits` once per dataset, chronologically. Never redefine.
3. Implement the strategy against `PointInTimeView` only (`pipeline/sim`).
   Fees must be explicit (`ExecutionModel(fee_bps=...)`) and sourced.
4. Iterate on train/validation (`sim.splits.run_on_split`); sweep latencies
   with `sweep_latency` (delays finer than the data resolution are flagged).
5. When a refinement is needed, create a child hypothesis that cites the run
   that failed or the new evidence. "Higher PnL" is not a reason.
6. Final test: `evaluate_holdout` with pass criteria registered up front. It
   runs once; the split is then burned. If it fails, write it up in
   `reports/failures/` and define a new, later holdout before testing again.

Objective A (imitation: agreement, precision/recall, timing) and Objective B
(performance: expectancy, profit factor, drawdown, fee/slippage drag, outlier
dependence) are stored and reported separately.

## 7. Before ending a session

```bash
python -m pipeline check-findings
python -m pipeline export-all
git add data/parquet research reports sources && git commit
```
