# Round USD market-cap levels on the bonding curve (agent round_levels, 2026-10-05): FAIL on train

**Bar:** at least 50 trades, net profit after costs, profit factor above 1.2, and still profitable without the 3 best trades.

## Idea

pump.fun's UI and most bots show market cap in USD, and traders set take-profits and limits at round levels. If so:
- sell pressure and reversals should cluster 0–5% below round levels (resistance);
- clean breaks above a level with continued buying might run (breakout).

## Data

**SOL/USD:** Binance SOLUSDT 1-minute klines for Oct 1–3 2026 (4,320 bars, none missing; SOL $116.78–$123.57).
- Source: Binance's public market-data endpoint `data-api.binance.vision/api/v3/klines`. `api.binance.com` refuses this container's location.
- Cached verbatim under `data/raw/web/solusd/`, with `SOURCE.txt`; fetched by `scripts/research/round_levels_solusd.py`.
- USDT is treated as USD.
- Point in time: each print uses the close of the last *completed* minute.

**Market cap:** mcap = vsol / vtok × 1e9 × SOL/USD.
- Trusted states only (|vsol − rsol − 30| < 0.01).
- Mayhem and unflagged tokens are excluded.
- The curve runs from about $3.3k at launch to about $49k at completion, so $50k, $69k and $100k are unreachable on the curve. The study uses $6k–$46k.

**Hygiene:**
- A token counts only if it was created inside a gap-free recording segment (no global gap over 60 s) of allowed data.
- A trigger counts only if trigger + 1 s + max hold also lies inside that segment.
- Segments are cut at the holdout and at the train/validation boundary.
- Holdout data (1790882100–1790899200) and anything at or after 1791072000 were never read.
- Train is about 14.4 h of recorded tape (Oct 1 pre-holdout plus Oct 2 segments), with 48,976 tokens in total across splits.

## Part 1: describe (train only)

**Levels:**
- **Round (R10):** $10k, $20k, $30k, $40k.
- **Half-round:** $15k, $25k, $35k, $45k.
- **Placebo:** every other whole $1k from $6k to $46k (33 levels, including $13k, $17k, $23k, $27k, $33k, $37k and $43k).

Each level's metric is compared with the mean of its neighbours at ±$1k and ±$2k (the "excess"), and the round levels are ranked against the 33 placebo excesses.

| metric | $10k | $20k | $30k | $40k | placebo SD |
|---|---|---|---|---|---|
| pass rate (first print ≥ 0.95L reaches L within 600 s) | 88.6% (n = 1046), excess −0.1 pp | 92.3% (375), +0.3 pp | 88.7% (275), −3.4 pp | 85.9% (191), −6.4 pp | 1.7 pp |
| sell share of trades in [0.95L, L) | 45.2%, excess −0.6 pp | 44.8%, +0.1 pp | 44.5%, +0.2 pp | 41.1%, −0.6 pp | 1.1 pp |
| token ATH below / above L (±5%) | 102/98 | 21/19 | 16/9 | 14/7 | (too few to read) |

- **Sell clustering below round levels: none.** The sell share in the 5% band below each round level is the same as at placebo levels. The excess is −0.2 pp on average, inside the placebo spread. The sell share just above levels, where take-profit orders would fire, does not differ either.
- **Reversals:** at $10k and $20k (the two levels with most data) the chance of breaking through is the same as at placebo levels.
  - At $30k and $40k, the failure-to-break excess is larger than at any of the 33 placebo levels (−3.4 and −6.4 pp; binomial SE about 2 pp).
  - This is a weak, small-sample sign of resistance. $40k sits just below completion (about $49k), so it is confounded with the approach to migration.
  - It does not show up in sell shares, and the half-round levels show nothing.
- **ATH piling below levels:** too sparse above $20k to read. At $10k it is in line with placebo levels.

## Part 2: rules (20 eligible configs, fixed before any outcome was computed)

**Rules:**
- **A, breakout:** the first print with mcap in [L(1+X), 1.05·L(1+X)) and at least N distinct buyers in the trailing 10 s, with L in R10. X is 1% or 3%; N is 3 or 6. Three exits: TP/SL 30/15 300 s, 50/20 300 s, 100/30 1800 s. **12 configs.**
- **B, retest breakout:** as A with X = 1%, but only after a rejection, meaning the token printed in [0.95L, L) and then fell to 0.85L or below without printing L. N is 3 or 6, with the same 3 exits. **6 configs.**
- **C, front-run the resistance (long only):** the first print in [0.85L, 0.88L) with at least 3 buyers in 10 s. Take profit at the price of mcap 0.97L; SL 10% or 20%; max hold 600 s. **2 configs.**
- **Controls (not eligible):** rule A on the placebo levels, 12 configs.

**Fills and positions:**
- Fills are exact constant-product. `exit_path` reproduces `event_studies.outcomes()` exactly (315 checks, max difference 0).
- 0.5 SOL, 1.25% fee per side, 1 s latency, completion handling.
- One position per token at a time.

**Result:** at a 0.001 SOL tip, **all 20 configs lose on train** (`research/observations/evidence_round_levels_train_20261005.json`). Validation was not looked at.

| rule | trades | SOL per trade | PF | total | without best 3 |
|---|---|---|---|---|---|
| best overall: B, N = 6, TP30/SL15 300 s | 221 | −0.016 | 0.77 | −3.49 | −4.60 |
| best A: X 1%, N 6, TP30/SL15 300 s | 1462 | −0.027 | 0.65 | −39.2 | −41.1 |
| C, SL 20% | 1763 | −0.032 | 0.52 | −56.4 | −58.0 |
| A on placebo levels (control), range | 903–1469 | −0.027 to −0.038 | 0.59–0.76 | | |

- At a 0.01 SOL tip every config is worse: the best is −7.5 SOL.
- Losses hold on Oct 1 and on Oct 2 separately for every A and C config.
- **Breakouts above round levels do no better than breakouts above arbitrary levels** (control row).
- Rule B is positive per trade only at $20k, on a small subset. That was found after the fact and is not a selectable config.

## Reading

Round USD levels leave no measurable footprint in curve order flow at $10k–$20k, where most tokens trade. The hint of stalling at $30k/$40k is small-sample and confounded with the run-up to completion. Trading the levels, by breakout, retest or front-run, carries the same round-trip cost drag as every other public tape signal: about −0.03 SOL per 0.5 SOL trade. Verdict: **FAIL on train; family closed.**

## Files

- `scripts/research/round_levels_solusd.py`: SOL/USD fetch.
- `scripts/research/round_levels_build.py`: description, triggers and fills.
- `scripts/research/round_levels_eval.py`: scoring.
- `research/observations/evidence_round_levels_train_20261005.json`
- `data/raw/web/solusd/`

**Note:** the fill-equivalence unit check ran `exit_path` and `outcomes()` on a few Oct 3 token tapes. It compared the two functions' numbers only; no strategy or trigger outcome on validation was computed.
