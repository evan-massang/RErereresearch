# Research loop (2026-10-03): iterations that failed before reaching paper trading

The bar (agreed 2026-10-03, enforced by `pipeline/paper.py`): at least 50 forward paper trades, net profit after costs, profit factor above 1.2, and still profitable without the 3 best trades.

## Iteration 1: blind LLM judgement on Decu's candidate set

**Idea.** Decu's picks among creator-dump candidates make +0.27 SOL per simulated trade, against −0.15 for all candidates. Can an AI shown exactly what was visible at the trigger pick like them? It saw the coin, its description, the linked X post with its author stats, and the live tape numbers.

**Method.** `scripts/research/llm_choice_batches.py`:
- 706 train cards (before 16:15 UTC), shuffled, with opaque ids and no outcomes.
- Scored 1–5 card by card by 12 independent agents.
- The first round was discarded because agents had used threshold scripts instead of judging. Those scores are kept in `research/observations/llm_choice_train/discarded_scripted/` for the record.

**Result: FAIL on train** (`research/observations/evidence_llm_choice_train.json`).

| group | cards | SOL per trade |
|---|---|---|
| AI-rated buys (score 4) | 22 | −0.10 |
| score 3 | 57 | −0.13 |
| all candidates | 706 | −0.15 |
| Decu's picks | 8 | +0.27 |

The AI agreed with 2 of Decu's 8 picks. Its buys were only marginally better than buying everything.

## Iteration 2: front-running KOL followers

**Idea.** After a famous KOL buys, followers push the price 10–18% up within seconds. Buy 1 s after the KOL and sell into the followers.

**Method.** `scripts/research/kol_frontrun.py`, costs not yet applied:
- Train: 401 first buys by 99 KOLs.
- Validation: 554 first buys by 110 KOLs.

**Result: FAIL.**
- By the time a 1 s-late entry fills, the price is already up 16% (train median) or 13% (validation) from before the KOL's buy.
- After that, the median return is 0 at 5 s and negative from 10 s on: −1.3% / −0.5% at 10 s and −3.8% / −6.2% at 20 s.
- KOLs whose followers looked slower on train (mean +8% or more at 10 s) reversed on validation: 61 entries, −3.7% at 10 s and −15% at 20 s.

## Also checked (train, no hypothesis)

Good-dev launches inside Decu's candidate set: only 7, at −0.13 SOL per trade.

## What the misses point to

Decu's train picks are launches promoted by small dev accounts whose post points to something trending at that moment: OpenAI's "Todd" toad, a "Dead Internet Theory" post going viral, Phantom's Halloween post, a protest starting that day. Whether the referenced post is *actually spreading right now* is not in any historical data. So iteration 3 collects it live: `pipeline/recorder.py` now snapshots the linked post's views, likes and reposts at launch and again about 60 s later (`tweet_snaps` feed).

## Iteration 3: live engagement of the launch's own X post (2026-10-03)

**Method.** The recorder's `tweet_snaps` feed records each linked post's counters about 1 s after launch and again about 60 s later (`scripts/research/tweet_velocity.py`). Train: 1,169 launches between 00:40 and 03:30 UTC, of which only 16 migrated.

**Result: FAIL on train** (`research/observations/evidence_tweet_velocity_train_20261003.txt`).
- Views at launch, views per minute and the 60 s views gain do not order migration or 2× peaks.
- The top fifth by likes gained in the first 60 s migrated 3.1% of the time vs 1.4% overall: too weak and too few to trade.
- Only on-chain activity in the first minute separates outcomes, and that was already tested in H1 and H2.

## Iteration 4: live engagement of the post the launch's post quotes or links

**Method.** The recorder now also snapshots the referenced post. Train: launches between 04:33 and 07:25 UTC; 127 had a referenced post.

**Result: FAIL on train** (`research/observations/evidence_ref_post_train_20261003.txt`).
- None of the 127 migrated.
- Neither the referenced post's views, views per minute, 60 s gain, age nor author follower count changes 2×-peak rates.
- The market was cold over this window: 0.79% of all launches migrated.

## Iteration 5: gradient-boosted model of net PnL from point-in-time snapshots

**Method.** `scripts/research/ml_snapshots.py` takes 275k snapshots: every token at ages 5, 10, 20, 30, 60, 120 and 300 s, with 24 tape features.
- **Label:** an exact constant-product round trip of 0.5 SOL. It includes 1.25% protocol fee per side, 1 s latency and 0.01 SOL per transaction.
- **Split:** train on Oct 1 (before the holdout) plus Oct 2; validate on Oct 3 00:00–06:00 (`ml_model.py`).

**Result: FAIL** (`research/observations/evidence_ml_model_20261003.json`).
- **Regression on net PnL:** the top predicted 0.1–1% lose more than the base, on train out-of-fold and on validation alike.
- **Win-probability classifier:** it ranks well (AUC 0.84–0.86 on validation), mostly by spotting tokens that will never move. Its top 1% at 120 s is +0.018 SOL per trade before fixed costs and −0.015 after.

## Iteration 6: win-probability model with take-profit / stop-loss exits, priced at a 0.001 SOL tip

**Exits:** take-profit/stop-loss of 20/10, 30/15, 50/20 and 100/30%, each with a 120 s or 300 s maximum hold (`ml_exits.py`).

**Tip level:** an on-chain sample of pump.fun trades (only 7 transactions returned by the public RPC) paid a median of about 0.0001 SOL in fee plus Jito tip. That makes 0.001 SOL per transaction a conservative main case (`research/observations/evidence_trade_fees_sample_20261003.json`).

**Result: FAIL** (`research/observations/evidence_ml_exits_20261003.json`).
- All 24 setups (8 exits × 3 cutoffs) lose on train out-of-fold, at −0.02 to −0.06 SOL per trade.
- The few setups slightly positive on validation (n = 20–191) lost on train, so they are noise and were not frozen.

## Iteration 7: the same models with a 0.25 s delay instead of 1 s (paid RPC + Jito speed)

**Result: FAIL** (`research/observations/evidence_ml_exits_lat025_20261003.json`). Average net PnL by age barely moves. All 24 setups lose on train out-of-fold, at −0.02 to −0.06 SOL per trade. Faster infrastructure does not by itself open an edge in these features. Note that our own receive time already lags the chain, so "0.25 s" is measured from when *we* saw the trade.

## Iteration 8: hour-scale trading of migrated tokens (no speed race)

**Method.** `scripts/research/fetch_pool_ohlcv.py` fetched 15-minute USD OHLCV from GeckoTerminal for every recorded migration (1,124 pools, so no survivorship bias). `scripts/research/post_migration_hours.py` then makes decisions 1–24 h after migration using only completed bars, enters at the next bar's open, holds 4 h or 24 h, and charges 2% per side.

**Train:** 172 tokens that migrated on Oct 1 before the holdout.

**Result: FAIL on train** (`research/observations/evidence_post_migration_hours_train_20261003.txt`).
- Every decision time and hold length has a negative mean, with only 14–23% of trades up.
- **Momentum** (4 h return above +50%), **near the all-time high**, and **market cap above $1M**:
  - over 4 h: medians of −2% to +2% and 42–55% up, but means of −13% to −16% because of collapses;
  - over 24 h: medians of −61% to −99%.
- **Deep dips and high volume:** worse still.
- Tokens that keep running after migration are usually dumped within the day.
