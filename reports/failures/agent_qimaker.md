# H-QIMAKER: queue-imbalance-gated passive quoting on HL perps (agent_qimaker, 2026-10-05). FAIL

**Verdict: FAIL on train and on validation.**
- **Train.** None of the 12 pre-registered configs comes near the bar: PF 0.002 to 0.010, 0 of 8 days positive.
- **Validation.** The one config selected on train (θ = 0.85, T = 30 s, no stop) was run once and also fails: n = 21,760, net −$16,407, PF 0.017, 0 of 9 days positive.
- **Holdout.** The holdout (2026-04-01 onward) was not downloaded or examined.

**Main finding.** The imbalance does predict the next mid move. That is consistent with Gould and Bonart. But the move is about 1 bp, and the maker round trip costs 3 bp. On top of that, under an honest fill model our fills are adversely selected.

## Pre-registration
`reports/hypotheses/qimaker_preregistration.json`, frozen before any signal or P&L was computed.

**Amendment 1** was made after only the outcome-free coin statistics had been computed.
- **Cached coins.**
  - WIF, kBONK and FARTCOIN are not large-tick. They sit at exactly one tick on only 37.7%, 26.9% and 6.2% of 1-s samples.
  - PUMP qualifies (71.5%), but it has no train days.
- **New candidates.** The amendment added the top 15 HL perps by today's 24-h notional and applied the same rule on each coin's first train day.
  - BTC (93%), ETH (93% one-tick) and SOL (91%) qualify.
  - HYPE, NEAR, XRP, SAND, SUI, ENA, WLD and DOGE fail the rule.
  - ZEC, LIT and PONS have no train day.
- **Final set.** BTC, ETH and SOL on train and validation, plus PUMP on validation only.
- **Download.** About 0.33 GB of raw data, all deleted after extraction to parquet in `data/raw/web/tardis/parquet_qimaker/` (310 MB).

## Rule and fill model (as pre-registered)
- **Signal.** I = (bid_sz − ask_sz)/(bid_sz + ask_sz) from the last *received* snapshot. A signal needs a one-tick spread.
- **Quote.** When |I| ≥ θ, post-only at the favoured touch for $1k, one unit per coin.
- **Cancel.** Cancel when |I| < θ/2, when I flips sign, or when the touch moves.
- **Exit.** A passive exit rests at the opposite touch and is repriced when that touch moves. It becomes a reduce-only taker after T, or after a 2-tick adverse mid move in the stop variants.
- **Latency.** Every place or cancel takes 300 ms. Arrival is measured on the local clock, while prints carry HL exchange timestamps. The exchange clock runs about 175 ms behind local, so this adds conservative extra latency.
- **Maker fill.** A resting order fills only on a print **strictly through** our price. It also fills once cumulative prints **at** our price exceed the displayed queue ahead of us at arrival plus our own size. We assume no one ahead of us cancels.
- **Taker fill.** Taker fills use `hlanchor_lib.taker_fill`, imported read-only. The module is unchanged: sha256 98166e5f…c3ad.
- **Fees.** 1.5 bp maker and 4.5 bp taker, with no rebates.

## Results (selected config θ0.85_T30_nostop; full grid in the evidence files)
| split | n | net $ | mean $/trade | PF | net ex top-3 | days + | fill markout 1/5/30 s (bp) | gross bp/trade before fees |
|---|---|---|---|---|---|---|---|---|
| train (BTC, ETH, SOL) | 5,988 | −3,783 | −0.63 | 0.010 | −3,787 | 0/8 | −1.04 / −1.31 / −1.52 | −2.66 |
| **validation** (+ PUMP) | 21,760 | −16,407 | −0.75 | 0.017 | −16,421 | 0/9 | −1.93 / −2.25 / −2.26 | −4.22 |

- **Full train grid.** Net runs from −$3.8k to −$8.6k, and every config has 0 positive days. Higher θ loses less, and so do configs without a stop.
- **Trade-through-only fills (informational).** The result is unchanged: train PF 0.009 and validation PF 0.015.
- **Queue fills.** Only about 20% of train entry fills came from the queue being consumed at our price. The rest were trade-throughs.
- **Validation by coin (net $).**

  | BTC | ETH | SOL | PUMP |
  |---|---|---|---|
  | −3,771 | −5,496 | −4,916 | −2,225 |

  PUMP is the only real large-tick book (tick ≈ 3.6 bp). Its gross was −5.5 bp on maker exits and −10.2 bp on taker exits.

**The signal is real but too small.** The table shows the mean mid move after an imbalance signal starts, at θ = 0.85, signed in the signal's direction. It is measured with no latency and no fill required.

| split | coin | 1 s (bp) | 5 s (bp) | 30 s (bp) | 30 s (ticks) | tick (bp) |
|---|---|---|---|---|---|---|
| train | BTC | +0.29 | +0.70 | +1.06 | 9.5 | 0.11 |
| train | ETH | +0.48 | +0.88 | +1.05 | 2.7 | 0.41 |
| train | SOL | +0.52 | +0.91 | +1.11 | 1.9 | 0.61 |
| valid | PUMP | +1.64 | +2.25 | +2.64 | 0.9 | 3.59 |

Even a fill at the signal itself, with no adverse selection, earns about half a spread plus 1 bp on BTC, ETH and SOL. That is well below the 3 bp maker/maker fees. The actual fills come when the queue is swept: the fill markout is −1.3 bp at 5 s on train and −2.2 bp on validation. The passive exits then follow a falling touch, so maker exits also lose gross. This is the adverse selection that the leads file named as the main kill risk.

## Limits (why a fail here is strong for HL at 300 ms, weaker in general)
- **Snapshot resolution.** Tardis HL quotes are top-of-book snapshots at about 0.6 s cadence. The book at arrival is usually the decision snapshot itself, so post-only rejects are under-counted.
- **Queue position.** The queue ahead of us is the displayed level size. Cancellations ahead of us, intra-snapshot changes and depth below the touch are unknown. HL L2 is aggregated by level, so it would not reveal our true position either.
- **A real queue-front maker could do better.** The fill model treats us as never at the front of the queue. A maker with sub-100 ms reaction and true queue position could do better than this test shows.
- **The gap is structural, not marginal.**
  - The predicted move on BTC, ETH and SOL (about 1 bp at 30 s) is a third of the round-trip fee.
  - PUMP (2.6 bp at 30 s with a 3.6 bp tick) is the only coin where spread capture could cover fees, and there its fills were the most toxic.
- **Coin ranking.** The amendment ranks coins by today's 24-h volume, which carries survivorship. It says nothing about the outcome.

## Bug fix (disclosed)
- **The bug.** The first run's tick rule gave BTC a $10 tick above $100k, but HL allows integer prices.
- **The fix.** The sig-fig tick is now capped at 1.0. The full train grid and the selected validation config were re-run after the fix.
- **Effect.** Selection was unchanged. The pre-fix validation result was n = 20,324, net −$15,547, PF 0.018.
- **Two looks at validation.** The pre-fix outputs are kept in `data/raw/web/tardis/results/qimaker/prefix_run/`. Both looks fail by a wide margin, so the second look changes nothing.

## Do not iterate on
- Lowering θ or adding a stop: both are strictly worse on train.
- More coins of the same kind: the fee-to-signal gap is about 3×.

A maker-rebate fee tier or real queue-front access would be different hypotheses. Neither is available to us at tier 0, and the rebate tiers were not verified in this run.

## Files
- `reports/hypotheses/qimaker_preregistration.json`
- `scripts/research/qimaker_coins.py`, `qimaker_fetch.py`, `qimaker_sim.py`
- `research/observations/evidence_qimaker_train_20261005.json`, `evidence_qimaker_valid_20261005.json`
- Per-trade parquet and summaries: `data/raw/web/tardis/results/qimaker/`; coin selection: `data/raw/web/tardis/results/qimaker_coin_selection.json`, `qimaker_fetch_log.json`
