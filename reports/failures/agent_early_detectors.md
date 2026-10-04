# Early-detector wallets on the bonding curve: FAIL on train (2026-10-04)

**Idea.** Some wallets repeatedly buy tokens at low market cap shortly before those tokens run. Choose them by
early-entry *precision*, not PnL, and copy their first buy 1 s later while the token's tape is still quiet,
before any follower flow arrives. This differs from H4 (PnL-ranked copying), from Decu copying, from
smart_convergence (k PnL winners) and from KOL front-running.

**Scripts.**
- `scripts/research/early_detectors_build.py` builds per-buy tables.
- `scripts/research/early_detectors_eval.py` builds the detector lists, runs the grid and evaluates.

**Evidence.** `research/observations/evidence_early_detectors_20261004.json`

## Definitions

**Data and splits.**
- Read-only `data/market.duckdb`.
- Train fold A is Oct 1 before 19:15 UTC. Train fold B is Oct 2. Validation is Oct 3.
- Nothing from the holdout (1790882100–1790899200) or at or after 1791072000 was loaded.

**Qualifying first buy.** A wallet's first buy in a token counts only if all of these hold:
- The buyer is not the token's creator and has not created any token.
- Its slot is after the create slot + 1, so launch-block snipers are excluded.
- The token was created inside the segment and has a standard initial market cap of 25–40 SOL.
- Market cap after the buy is 50 SOL or less.
- Token age is 900 s or less.

**Run label.** This label is used only to rank wallets. A buy "ran" if, within 30 min of it, the token printed at least 2× the post-buy market cap or migrated. Buys whose label window crosses a data gap are dropped.

**Detector list.** Wallets with at least 8 label-complete qualifying buys and precision of at least P, for P = 0.3 or 0.5.
- Train results are cross-fitted: the list from A is scored on B, and the list from B is scored on A. No trade is scored with a list built from its own fold.
- Validation would use the list built from A+B.

**Trigger.**
- The first qualifying buy by any detector in a token.
- Optionally a quiet tape: in the previous 30 s, other wallets bought 1 SOL or less, from at most 2 distinct wallets.

**Entry and exit.**
- Entry 1 s after the detector's buy.
- Exact constant-product fills via `event_studies.outcomes`: 0.5 SOL, 1.25% fee per side.
- Take-profit / stop-loss of 20/10, 30/15, 50/20, 100/30 or 200/50%, with a 300 s or 1800 s maximum hold.
- Tip of 0.001 or 0.01 SOL per transaction, two transactions per trade.

**Grid.** 2 values of P × quiet on/off × 5 exits × 2 holds = **40 configs**, fixed before any result was seen.

## Results

**Precision is real and persistent.** Among 502 wallets active in both folds, the top fifth by fold-A precision ran 41.7% of the time on fold B. The fold-B base rate was 23.3%, and the bottom fifth ran 10.6%.

**There is no follower flow to front-run.** The median price change from the detector's buy to the 1 s entry is about 0. At 30 s, the median return after the trigger is −17% to −28%. The few big runs keep the mean near zero, but the typical trigger token falls.

**The quiet filter selects fresh-launch scatter buyers.** In the P0.5 + quiet set, the median trigger is at about 28 SOL market cap (the launch price) and 21 s after creation, with a 0.04 SOL buy. Just 34 wallets fired these triggers, and 5 of them account for 40%.

**Running is not catchable with take-profit / stop-loss.** Of the tokens that ran, 39% still lost on a 20/10 exit because they dipped through the stop first. The round-trip cost of 2.5% fees plus about 1.5% price impact per side at about 30 SOL also eats the small wins.

**All 40 configs fail on train at both tip levels**, so validation was never read.

The best train config was P0.5 + quiet with a 200/50 exit and a 300 s hold:

| tip per tx | trades | net SOL | profit factor | win rate | net without best 3 |
|---|---|---|---|---|---|
| 0.001 | 190 | −3.80 | 0.90 | 24% | −8.93 |
| 0.01 | 190 | −7.22 | 0.82 | 23% | −12.30 |

Every other config's train net was between −7.1 and −343 SOL at a 0.001 tip.

## Verdict

**FAIL.** Early-entry precision is a persistent trait of wallets, but it does not make a tradable copy signal. Their low-cap entries come in clusters at the launch price. Those tokens usually dip before any run, and the runs are too rare and too gappy for take-profit / stop-loss exits after costs. No config advanced to validation.

## Follow-up: exits with no stop-loss (train only, 12 configs)

**Why.** Runners dip first, so the coordinator asked whether removing the stop-loss rescues the idea.

**What was tested.** Script: `scripts/research/early_detectors_nostop.py`. Evidence: `research/observations/evidence_early_detectors_nostop_20261004.json`.
- The detector lists and triggers are the same cross-fitted ones as above: P ≥ 0.3 or ≥ 0.5, quiet tape on or off.
- **Exits:**
  - take-profit 100% with no stop, 1800 s maximum hold;
  - take-profit 200% with no stop, 1800 s maximum hold;
  - hold with no take-profit and no stop, to 1800 s or to the last curve state before completion.
- Fills follow the same conventions as before: 1 s latency, exact curve round trip, 0.5 SOL, 1.25% fee per side.
- Trades whose window crosses a data gap are dropped.

**Results.** Net and net without the 3 best trades are in SOL.

| config | n | net @0.001 | PF @0.001 | without top 3 @0.001 | net @0.01 | PF @0.01 | without top 3 @0.01 |
|---|---|---|---|---|---|---|---|
| P0.3, any tape, TP 100% | 5372 | −301.5 | 0.71 | −306.6 | −398.2 | 0.64 | −403.2 |
| P0.3, any tape, TP 200% | 5372 | −360.2 | 0.70 | −366.7 | −456.9 | 0.64 | −463.3 |
| P0.3, any tape, hold | 5372 | −538.5 | 0.59 | −631.0 | −635.2 | 0.55 | −727.7 |
| P0.3, quiet, TP 100% | 3461 | −162.8 | 0.77 | −167.9 | −225.1 | 0.69 | −230.1 |
| P0.3, quiet, TP 200% | 3461 | −195.9 | 0.75 | −202.4 | −258.2 | 0.69 | −264.7 |
| P0.3, quiet, hold | 3461 | −282.7 | 0.68 | −353.8 | −345.0 | 0.63 | −416.0 |
| P0.5, any tape, TP 100% | 931 | −174.2 | 0.33 | −177.9 | −191.0 | 0.30 | −194.6 |
| P0.5, any tape, TP 200% | 931 | −165.2 | 0.41 | −171.4 | −182.0 | 0.38 | −188.1 |
| P0.5, any tape, hold | 931 | −240.6 | 0.24 | −256.2 | −257.3 | 0.22 | −272.9 |
| P0.5, quiet, TP 100% | 161 | −11.9 | 0.64 | −14.3 | −14.8 | 0.58 | −17.1 |
| P0.5, quiet, TP 200% | 161 | −7.9 | 0.79 | −13.8 | −10.8 | 0.73 | −16.6 |
| P0.5, quiet, hold | 161 | −13.5 | 0.69 | −27.3 | −16.4 | 0.65 | −30.1 |

**Verdict.** All 12 configs fail on train at both tip levels, so validation was not read. Removing the stop makes results worse, not better. Most trigger tokens never recover: with the hold exit, only 9–26% of trades are winners.

**Grid count.** The family's total is now 52 configs: 40 in the original grid plus these 12.
