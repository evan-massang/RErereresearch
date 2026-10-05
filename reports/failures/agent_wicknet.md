# H-WICKNET: deep resting orders to catch liquidation wicks on HL meme perps (agent_wicknet, 2026-10-05). FAIL on train

**Verdict: FAIL on train. Validation was not run and the holdout was not touched.**
- None of the 12 pre-registered configs passes both the kill test and the bar.
- Every config whose +30 s markout is positive has **n < 50** round trips (3–39 on 22 coin-days), and its net is negative once the 3 best trades are removed.
- The configs with enough trades (filter off, d = 50 bp) fail the kill test (−9 bp at 30 s) and lose money (PF 0.44–0.55).
- The pre-registration says validation runs only on a config that passes train, so validation was not examined.

Lead: `sources/leads/documented_edges_round8.md`, idea 6.

## Pre-registration
`reports/hypotheses/wicknet_preregistration.json` was frozen before any simulation was run.

**Reference.** The reference is a Binance-implied fair value: the Binance-futures mid × (1 + the trailing 10-minute median HL/Binance basis). It comes from `hlanchor_lib`, which was imported read-only and is unchanged (sha256 98166e5f…c3ad).

**Quotes.** A post-only $1k bid sits at F(1 − d) and a post-only $1k ask at F(1 + d), rounded away from F to 5 significant figures.
- Every R seconds the quotes are refreshed if F has moved more than d/5.
- Every place and cancel takes 300 ms. Arrival is measured against HL exchange time, which runs about 175 ms behind local time, so the latency is conservative.
- An order that would cross the book on arrival is rejected (post-only).

**Fill model.** An order fills at its own limit price, and only when one of these happens:
- a print trades strictly through our price; or
- prints at our price exceed the displayed queue at arrival plus our own size.

Orders behind the touch have no visible queue, so only trade-throughs can fill them. That covers every d ≥ 50 bp quote: all fills in this run were trade-throughs and none were queue fills.

**Exits.** There are two exit variants. Both use a hard stop: a taker exit when the HL mid moves d against the entry. Positions are flattened at day end.
- **MK:** a post-only take-profit at F, with a 60-second time stop.
- **TK:** a taker exit after 30 seconds.

**Fees.** HL maker 1.5 bp and taker 4.5 bp.

**Market-wide filter.** While the filter is on, entries are cancelled and no new ones are placed if either holds:
- |BTCUSDT spot 60-second return| ≥ 30 bp, from data.binance.vision 1-second klines (15 MB, train and validation days only); or
- |the coin's own Binance mid 10-second return| ≥ d/2.

**Grid (12 configs).**
- d ∈ {50, 100} bp × exit ∈ {MK, TK} × filter ∈ {off, on}, all at R = 2 s.
- Plus R = 5 s for the four filter-on configs.

**Data.** Train has 22 coin-days: WIF and kBONK on 8 days, and FARTCOIN on 6. PUMP has no train days.

## Train results (all 12 configs)
| config | n | net $ | PF | net ex top-3 | markout 1/5/30/60 s (bp) | gross bp per trade | days positive | kill test | bar |
|---|---|---|---|---|---|---|---|---|---|
| d50_R2_MK_off | 132 | −231.0 | 0.44 | −249.7 | +7.5 / −1.8 / **−9.1** / −9.3 | −12.5 | 2/7 | fail | fail |
| d50_R2_MK_on | 39 | +5.8 | 1.09 | −10.6 | +22.7 / +14.4 / +7.2 / −0.7 | +6.6 | 4/6 | pass | fail (n, PF, ex3) |
| d50_R2_TK_off | 124 | −164.0 | 0.55 | −224.3 | +7.9 / −2.8 / **−9.1** / −14.3 | −7.2 | 2/7 | fail | fail |
| d50_R2_TK_on | 39 | +4.2 | 1.07 | −22.2 | +22.8 / +14.7 / +7.5 / −0.3 | +7.1 | 3/6 | pass | fail (n, PF, ex3) |
| d100_R2_MK_off | 9 | −10.0 | 0.77 | −34.5 | +52 / +16 / +26 / +55 | −6.1 | 1/3 | pass | fail |
| d100_R2_MK_on | 3 | +18.2 | inf | 0.0 | +67 / +63 / +65 / +55 | +65.5 | 2/2 | pass | fail (n) |
| d100_R2_TK_off | 9 | +13.0 | 1.43 | −18.6 | +52 / +16 / +26 / +55 | +20.5 | 2/3 | pass | fail (n, ex3) |
| d100_R2_TK_on | 3 | +17.5 | inf | 0.0 | +67 / +63 / +65 / +55 | +64.4 | 2/2 | pass | fail (n) |
| d50_R5_MK_on | 35 | +4.1 | 1.10 | −11.2 | +22.0 / +17.9 / +12.4 / +5.1 | +6.4 | 4/6 | pass | fail (n, PF, ex3) |
| d50_R5_TK_on | 36 | +14.4 | 1.43 | −2.6 | +21.2 / +17.5 / +12.3 / +5.1 | +10.0 | 4/6 | pass | fail (n, ex3) |
| d100_R5_MK_on | 4 | +8.0 | 1.77 | −10.4 | +50 / +45 / +45 / −50 | +25.4 | 2/3 | pass | fail (n) |
| d100_R5_TK_on | 4 | +15.1 | 10.8 | −1.5 | +50 / +45 / +45 / −50 | +43.8 | 3/3 | pass | fail (n) |

Notes on the table:
- n counts round trips. "Days positive" counts only days that had trades.
- Exit mix for d50_R2_MK_off: 51 stops, 46 maker take-profits, 35 time stops.
- Exit mix for d50_R2_MK_on: 20 time stops, 12 maker take-profits, 7 stops.
- The filter blocks quoting on about 2% of 250 ms ticks at d = 50, and on 0.3% at d = 100.

## What the run shows (observed; in-sample)
**1. The wicks are mostly not local.** Measured against the Binance reference, a d = 50 bp order is traded through only 132 times in 22 coin-days, and 107 of those are FARTCOIN.
- The precheck in the leads file counted about 129 per day for FARTCOIN alone, against the coin's own trailing 2-minute median.
- Most HL "wicks" that count against HL's own median are moves Binance shares. That is the falling-knife case.

**2. The market-wide filter separates the two kinds of fill, as Brogaard et al. predict.** In the d50_R2_MK_off run, entry fills were split by whether the filter-on run also took them. This split is informational and in-sample.

| fills | n | +1 s | +5 s | +30 s | +60 s |
|---|---|---|---|---|---|
| kept by the filter | 38 | +22.4 | +13.7 | +7.5 | −0.1 |
| removed by the filter | 94 | +1.5 | −8.0 | −15.9 | −13.0 |

- The filter blocks only about 2% of the time, yet it removes about 70% of the fills. Those removed fills are the informed, trending ones.

**3. The local wicks do revert, but they are too rare and the reversion is too small.**
- After filtering, a d = 50 bp fill earns about 6–10 bp gross per round trip against 3–6 bp of fees. That is a net mean of $0.11–$0.40 per trade.
- There are about 1.6–1.8 fills per coin-day, so 35–39 on train, short of n ≥ 50.
- With the 3 best trades removed, every filtered config is negative.
- At d = 100 bp there are only 3–9 fills in 22 coin-days.

**4. Concentration.** The losses in the filter-off configs come mainly from FARTCOIN on 2025-02-01: 68 of 132 fills, and −$147 of −$231.

## Why the fail is robust, and its limits
**Robust.**
- The kill-test passers are economically tiny: their total train net is ≤ $18 on $1k clips.
- A more generous fill model could not lift n to 50 and keep PF above 1.2. Queue fills are impossible behind the touch, and every fill in this run was already a trade-through.

**Limits.**
1. **Snapshot cadence.** HL quotes are snapshots about 0.5 s apart. The post-only checks, the stops and the taker fills inherit that resolution.
2. **Missing trade-throughs at our level.** The model assumes nobody ahead of us cancels. It cannot see the deep-level queue at all, so it may miss fills where the print hit exactly our price. That would add fills at the worst point of a wick, not better ones.
3. **Small sample.** There are only 22 coin-days (first of the month only), on 3 coins. Bursty wick days could be under-sampled.
4. **Order-action volume.** The configs send about 41k–137k orders on train (up to ≈ 6k per coin-day), with about as many cancels. HL rate limits on orders relative to traded volume were **not** checked in this run. They could bind for a deployment before the edge question does.
5. **BTC proxy.** BTC spot 1-second klines stand in for Binance-futures BTC. The close of second s is treated as known at s + 1.
6. **Exit-order handling.** When an opposite stale entry closes a position, the maker exit order is dropped at once rather than 300 ms later. This affects very few trades.

## Do not iterate on
- **Lowering d below 50 bp to raise n.** That approaches HLANCHOR's touch quoting, which was killed by −2.5 to −4.4 bp 30-second markouts.
- **Dropping the filter.** The unfiltered fills are strongly toxic: −16 bp at 30 s.
- **Re-tuning d, R or the exit on these 22 coin-days.** That would be fitting about 39 trades.

## A different hypothesis (needs its own pre-registration; not tested)
- The filtered local-wick fill has a markout of +22 bp at 1 s and +14 bp at 5 s, which decays to about 0 by 60 s.
- A faster exit (≤ 5 s) on a wider universe could be tested forward, from recorder data, using HL `trades`/`l2Book` for many coins.
- This is an inferred lead from in-sample train numbers only.

## Files
- `reports/hypotheses/wicknet_preregistration.json`
- `scripts/research/wicknet_sim.py`, `scripts/research/wicknet_fetch_btc.py`
- `research/observations/evidence_wicknet_train_20261005.json`
- Per-config trades, fills and summary: `data/raw/web/tardis/results/wicknet/`
- BTC filter data: `data/raw/web/binance_spot/klines1s/` (15 MB)
