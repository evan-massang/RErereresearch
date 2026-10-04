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

## Iteration 9: Raydium LaunchLab as a less crowded venue (shelved, not tested)

**Method.** The recorder logs LaunchLab events (`pipeline/launchlab.py`, using Raydium's published IDL), and each pool config's quote mint was read on-chain (`sources/launchlab_configs.json`).

**Finding.** Over 5 hours (10:24–15:25 UTC) only one config is priced in SOL: 84 of 505 new pools, about 17 an hour. Of those:
- 77 traded at all, with a median of 4 trades per pool;
- none reached migration;
- 13% doubled at some point and 5% reached 5×.

The rest are paired with other tokens (BONK, tokenized stocks and others). The venue is too thin to give the 50 trades the bar needs, or the liquidity to trade in it. Recording continues at negligible cost.

## Iteration 10: snapshot models plus market-regime features

**Method.** `scripts/research/ml_regime.py` adds launches in the last 10 and 60 min, completions in the last 60 min, completion rate and market-wide trades per minute to the iteration-6 models.

**Result: FAIL** (`research/observations/evidence_ml_regime_20261003.json`).
- All 24 setups lose on train out-of-fold, at −0.025 to −0.06 SOL per trade.
- Isolated positive validation results (for example 49 trades at +0.07) come from setups that lost on train, so they were not frozen.

## Where the loop stands after 10 iterations

No idea has yet earned a forward paper test. Across 23 tests (H1–H8, the good-dev hold, 4 follow-ups and these 10 iterations), the pattern is consistent:
- signals on public on-chain or X data are priced in before a 0.25–1 s trader can act;
- rules that look positive depend on a few runners and collapse out of sample.

The one persistent edge is a skilled human's selection: Decu, +10.7 SOL on Oct 2, and +0.27 SOL per simulated trade on their candidate picks. With 15 recorded picks it cannot be modelled. The recorder keeps collecting their trades so an imitation model can be tested once a few hundred picks exist.

## Iteration 11: can imitating Decu work at all? (oracle test)

**Method.** `scripts/research/decu_oracle.py`. Take all 124 of Decu's curve buys over Oct 1–3. A bot that knew every pick enters 1 s or 3 s after Decu's first buy, with exact curve fills, 0.5 SOL size and 1.25% fee per side. It exits with take-profit/stop-loss pairs from 20/10% to 200/40% (maximum 10 min), or 1 s after Decu's own last sell.

**Result: FAIL even as an oracle** (`research/observations/evidence_decu_oracle_2026-10-03.json`).
- At 1 s and a 0.001 SOL tip, every exit loses; the best is −0.006 SOL per trade (PF 0.85).
- Following Decu out (selling 1 s after they sell) loses −0.17 SOL per trade.
- At 3 s everything is worse.

**Correction to an earlier finding.** In the choice-set study the simulated bot entered at the trigger, *before* Decu, in 12 of 15 picks, and so profited from Decu's own 3–5 SOL buys. On the 3 picks where Decu bought first, the bot lost all 3 (−1.02 SOL). The "+0.27 SOL per trade on Decu's picks" finding is marked **weakened**.

Decu's edge is being first: selecting before the crowd and selling into it. A copier, or a model that imitates their choices, arrives after that flow. An imitation model therefore cannot pass the bar, and this thread is closed.

## Iteration 13: late-life tokens (10–60 min old), where launch bots are gone

**Method.** The `ml_snapshots.py` features at ages of 600, 1,200, 1,800 and 3,600 s (266k snapshots), with the iteration-6 exits and model.

**Result: FAIL** (`research/observations/evidence_ml_late_20261004.json`). All 24 setups lose on train out-of-fold (−0.007 to −0.04 SOL per trade) and on validation.

## Iteration 12 (collecting): pump.fun livestream viewer counts

From 2026-10-04 08:54 UTC the recorder polls pump.fun's public currently-live list every 15 s. That gives each coin's viewer count (`num_participants`), stamped with the time it was seen. The hypothesis is that rising viewers lead buy flow by minutes. It is studied once there are enough hours of data.

## Iteration 14: holder-reward carry (collect a share of trading fees while holding)

**Background.** Since 2026-09-12, pump.fun "Holder Rewards" tokens pay their trading fees pro rata to holders above $20, several times an hour ([The Defiant](https://thedefiant.io/news/defi/pump-fun-drops-cashback-for-new-launches-adds-holder-rewards), [Crypto Briefing](https://cryptobriefing.com/pumpfun-holder-rewards-cashback-deprecated/)). The creator-fee tier runs from 0.30% on the curve, to 0.95% from 420 SOL market cap, down to 0.05% above 98,240 SOL ([Blockworks](https://blockworks.com/news/pumpdotfun-fee-model)).

**Check.** Two parts:
- **Large holder-reward tokens** (7 in the top 100 by market cap, $2.4M–7.3M): daily volume is 0–10% of market cap (DexScreener), which pays holders about 0.02% a day or less.
- **Every migrated pool in our PumpSwap tape, generously assumed to pay holder rewards:** creator fees over a 4 h hold average 0.1–0.55% of market cap (90th percentile about 1.2%). The highest-yield fifth falls by a median of −12% to −32% over the same 4 h.

**Result: FAIL before any rule.** The yield is an order of magnitude smaller than both the round-trip costs and the price decay of the tokens that generate it.
