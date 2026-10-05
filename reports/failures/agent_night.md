# H-NIGHT: long memecoin perps in fixed UTC windows (overnight seasonality). Verdict: FAIL

_Agent run 2026-10-05. Real data, `is_synthetic = false`. The data sources are data.binance.vision 1h klines and
fundingRate for 2022-01 to 2026-03, plus the Lighter public REST order book. All numbers are our own computations.
The paper is a lead (`document` modality), and its primary text was not obtained._

Scope: memecoins only (`reports/scope_memecoins_20261005.md`). The lead is `sources/leads/documented_edges_round11.md`,
idea 2. The pre-registration was frozen before any price data was downloaded: `reports/hypotheses/night_preregistration.json`.

## Verdict

**FAIL on train. None of the 12 configs passes the bar.**
- Net is −0.8 to −11.9 bp per trade.
- PF is 0.76–0.99.
- Every net-ex-top-3 is negative.
- Daily t is −0.16 to −2.99.

As pre-registered, validation was run **once**, for information only, on the config with the highest train daily t
(W2224_PC). It loses more:
- gross −2.7 bp, net −8.9 bp;
- PF 0.83, daily t −1.32;
- placebo rank 14 of 24.

The holdout (2026-04 onward) was never downloaded. The last bar on disk is 2026-03-31 23:00 UTC, and the code asserts this.

**The placebo says the 22–24 UTC window is not special on memecoins.**
- In per-coin trades it ranks 9th of 24 start hours by mean gross (+5.6 bp, against +2.3 bp for the other 23 hours).
  Its z against the other hours is 0.67.
- What gross there is is mostly beta: the coins drifted up about 1.2 bp per hour on train.
- The 14–16 "US session" arm is among the worst hours (rank 17–22).

## 1. The paper (lead, not verified in primary)

Padyšák and Vojtko, "Seasonality, Trend-following, and Mean reversion in Bitcoin", SSRN 4081000 (2022).
- **The primary text was not read.** SSRN (both the abstract page and Delivery.cfm) and ResearchGate return HTTP 403
  to curl and WebFetch.
- **No page reference could be verified.** Quantpedia attributes the performance figures to "page 9". That label
  appears in the raw HTML only; the trafilatura snapshot drops it, so it is not quote-verified.

Verified quotes from secondary pages (snapshots in the DB, `quote_verified = true`):

| obs | source | verbatim |
|---|---|---|
| obs_e730826faf724388 | Quantpedia (src_45b943f55dc1cad7) | "In particular, the returns for 22:00 and 23:00 (UTC +0) seem to be the most economically significant." |
| obs_8740801b76f44f50 | Quantpedia | "To exploit the seasonality, open a long position in the BTC at 22:00 (UTC +0) and hold it for two hours." |
| obs_7de3a1648d674f16 | Quantpedia, reproducing the abstract | "The results point to a simple seasonality strategy that is based on holding BTC only for two hours per day." |
| obs_1e492151f8414b4d | TradingView script IzFZxayj (src_695ea3e78239ffd0) | "Bitcoin exhibits higher-than-average returns from 21:00 UTC to 23:00 UTC" |
| obs_edb6e6c68a7042af | TradingView IzFZxayj | "maximum drawdown of -22.45%" |

**The secondary sources contradict each other** (`research/observations/evidence_night_paper_20261005.json`):
- **The window.** Quantpedia says 22:00 → 24:00. TradingView and the paperswithbacktest blog say 21:00 → 23:00.
  This is probably an ambiguity over whether "22:00" labels the bar's open or its close. We pre-registered both
  readings as arms.
- **The drawdown.** Quantpedia gives −34.04% (raw HTML, unverified). TradingView gives −22.45%.
- **The round-11 lead.** Its "33%/yr, Sharpe 1.58, MDD −34%" matches Quantpedia only.

Two quote attempts on Quantpedia's figures did not verify against the snapshot text and were set to `rejected`:
obs_88315d2e8fcb4875 and obs_7684df1570844ede.

## 2. Pre-registration (frozen first)

**Grid: 12 configs.** Four windows × three variants.
- **Windows (UTC):**
  - W2224: 22–24, the Quantpedia reading;
  - W2123: 21–23, the TradingView reading, added because of the discrepancy;
  - W2324: 23–24;
  - W1416: 14–16.
- **Variants:**
  - PC: per-coin trades;
  - BK: an equal-weight basket, one trade per day;
  - BKH: the basket with a 1:1 short in BTCUSDT.
- **Why this differs from the lead's grid.** The lead's universe and hedge axes were replaced by the caller's basket
  vs per-coin request and by the 21–23 arm. This change was made before any data was downloaded.

**Universe.**
- Coins: PUMP, DOGE, FARTCOIN, 1000SHIB, TRUMP, 1000PEPE, PENGU, WIF and 1000BONK.
- A coin is eligible from its 8th day of history.
- PUMPUSDT is used only from 2025-07-10. Earlier archive bars belong to a different contract, as found in
  `agent_pumppulse.md`.

**Splits.**
- Train: 2022-01-01 to 2025-06-30.
- Validation: 2025-07-01 to 2026-03-31.
- Holdout: 2026-04-01 onward, not downloaded.

**Trades.**
- Long at the open of the entry hour's bar.
- Exit at the close of the last bar in the window.
- Prices are Binance USDT-M, used as a proxy for Lighter.

**Cost.** Each coin is charged its own Lighter round trip, measured now:
- The measure is the median $1,000 round-trip VWAP cost (it is ≥ the quoted spread). It comes from 30 rounds × 10
  markets of `orderBookOrders`, sampled 2026-10-05 10:35–10:45 UTC.
- The Lighter fee is 0 bp (`orderBooks` taker_fee 0.0000).
- Funding is charged per hour held, at that coin's monthly mean Binance funding per hour (archive proxy).
- Variants: 1.5× stress; a Binance taker variant at 5 bp per side (information only).

| Lighter market | quoted median (bp) | $1k round-trip median (bp) | $1k p90 (bp) |
|---|---|---|---|
| DOGE | 3.3 | 3.5 | 4.3 |
| PUMP | 3.1 | 3.8 | 4.8 |
| 1000PEPE | 4.4 | 4.4 | 7.1 |
| FARTCOIN | 4.8 | 4.8 | 6.5 |
| TRUMP | 4.8 | 6.5 | 7.2 |
| WIF | 6.9 | 6.9 | 12.5 |
| PENGU | 7.2 | 7.3 | 8.6 |
| 1000SHIB | 5.0 | 8.0 | 10.0 |
| 1000BONK | 10.0 | 10.1 | 12.6 |
| BTC (hedge) | 0.4 | 0.5 | 0.6 |

**The bar, for each split:** n ≥ 50, mean net > 0, PF > 1.2 and net ex-top-3 > 0, all at base cost.

**Placebo.** Each config was rerun at all 24 entry hours. A config is labelled "seasonal" only if the arm ranks in
the top 3 of 24 by mean gross.

## 3. Train (2022-01-01 to 2025-06-30)

Units:
- gross, cost, funding and net are means in bp per trade;
- ex-top-3 is a sum in % of notional;
- "other hrs" is the mean gross of the other 23 entry hours.

| config | n | gross | cost | funding | net | net 1.5× | net Binance | PF | ex-top-3 % | daily t | placebo rank | other hrs | label |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| W2224_PC | 4956 | +5.6 | 6.2 | +0.24 | −0.8 | −3.9 | −4.6 | 0.99 | −123 | −0.16 | 9/24 | +2.3 | beta/noise |
| W2224_BK | 1270 | +5.3 | 6.0 | +0.22 | −0.9 | −3.9 | −4.9 | 0.98 | −43 | −0.22 | 5/24 | +1.8 | beta/noise |
| W2224_BKH | 1270 | +2.5 | 6.5 | +0.05 | −4.1 | −7.3 | −7.6 | 0.89 | −75 | −1.35 | 8/24 | +0.9 | beta/noise |
| W2123_PC | 4956 | +3.7 | 6.2 | +0.24 | −2.8 | −5.9 | −6.6 | 0.96 | −198 | −0.47 | 12/24 | +2.4 | beta/noise |
| W2123_BK | 1270 | +1.5 | 6.0 | +0.22 | −4.8 | −7.8 | −8.8 | 0.92 | −95 | −1.03 | 15/24 | +1.9 | beta/noise |
| W2123_BKH | 1270 | −2.8 | 6.5 | +0.05 | −9.4 | −12.6 | −12.9 | 0.78 | −146 | −2.77 | 20/24 | +1.2 | beta/noise |
| W2324_PC | 4956 | +3.3 | 6.2 | +0.12 | −3.0 | −6.1 | −6.8 | 0.92 | −204 | −0.98 | 6/24 | +1.1 | beta/noise |
| W2324_BK | 1270 | +2.6 | 6.0 | +0.11 | −3.5 | −6.6 | −7.5 | 0.89 | −62 | −1.32 | 8/24 | +0.9 | beta/noise |
| W2324_BKH | 1270 | +3.8 | 6.5 | +0.02 | −2.7 | −6.0 | −6.2 | 0.89 | −53 | −1.31 | 3/24 | +0.4 | seasonal* |
| W1416_PC | 4953 | +0.3 | 6.2 | +0.24 | −6.2 | −9.3 | −10.0 | 0.93 | −373 | −0.90 | 17/24 | +2.5 | beta/noise |
| W1416_BK | 1270 | −2.5 | 6.0 | +0.22 | −8.7 | −11.7 | −12.7 | 0.88 | −149 | −1.54 | 20/24 | +2.1 | beta/noise |
| W1416_BKH | 1270 | −5.4 | 6.5 | +0.05 | −11.9 | −15.2 | −15.4 | 0.76 | −183 | −2.99 | 22/24 | +1.3 | beta/noise |

\*W2324_BKH reaches rank 3 by the pre-registered rule, but its z against the other hours is only 1.31, after 24
hours were looked at. It still loses 2.7 bp net. Read it as information, not as an effect.

**W2224 by half-year (per coin):**

| half-year | gross (bp) | net (bp) |
|---|---|---|
| 2022H1 | −9.5 | −15.2 |
| 2022H2 | −13.0 | −18.7 |
| 2023H1 | +19.7 | +14.0 |
| 2023H2 | +25.5 | +19.7 |
| 2024H1 | +7.3 | 0.0 |
| 2024H2 | +4.5 | −2.3 |
| 2025H1 | +1.5 | −5.0 |

The window looked good in 2023 and **decayed every half-year after that**. 2022 was negative.

**The lead's own kill test fails.** W2224_PC's gross (+5.6 bp) is below 2 × cost (12.4 bp). It is positive in 5 of
7 half-years.

**W2224_PC by coin:**
- The best coins were 1000PEPE (+14.7 bp gross, n = 781), PENGU (+19.2, n = 189) and 1000BONK (+11.5).
- FARTCOIN lost (−43.0, n = 186), and so did WIF (−4.1).
- Weekend legs gross +9.5 bp and weekday legs +4.1 bp (information only).

**Placebo (W2224_PC, 2h windows, mean gross by entry hour, train).**
- Most hours sit between −9 and +9.5 bp.
- **Asia morning is higher.** 03:00 gives +9.0 and 08:00 gives +9.5.
- **US midday is negative.** 11:00 gives −5.9 and 12:00 gives −8.9.
- 22:00 gives +5.6.
- The best placebo net is +3.0 bp (08:00), picked after looking at all 24 hours. It is not a pre-registered
  candidate and must not be re-tested on this train split.

## 4. Validation (2025-07-01 to 2026-03-31; W2224_PC; run once, information only)

| n | days | gross | cost | funding | net | net 1.5× | net Binance | PF | net sum % | ex-top-3 % | daily t | placebo rank |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2450 | 274 | −2.7 | 6.2 | −0.01 | −8.9 | −12.0 | −12.7 | 0.83 | −218 | −255 | −1.32 | 14/24 (other hours −1.8) |

- **By half-year:** 2025H2 grossed +4.7 bp and netted −1.6; 2026Q1 grossed −17.7 and netted −23.7.
- **By coin:** only PENGU was net positive (+4.2). PUMP grossed −15.8.
- **The placebo hours are unstable on validation.** 01:00 gave +17.2, 21:00 +16.3 and 23:00 −20.8. That is noise
  with an sd of about 9 bp across hours.

## Reading

- **Stated (lead, secondary):** BTC 2015–2021 earned its best hourly returns at "22:00 and 23:00 (UTC +0)". The
  secondary sources disagree on what that window is.
- **Observed (ours):**
  - On memecoin perps from 2022 to 2025H1, the 22–24 UTC long grossed about +5.6 bp per coin-leg. That is below a
    6.2 bp Lighter round trip.
  - It was not distinguishable from the other hours (placebo rank 9/24), and it decayed after 2023.
  - It turned negative on validation.
  - Hedging out BTC cuts the 2h-window gross: 22–24 drops from +5.3 to +2.5 bp, and 21–23 from +1.5 to −2.8 bp.
    The 1h 23–24 window is the exception: its gross rises from +2.6 to +3.8 bp, but it still nets −2.7 bp. The
    night drift that exists is mostly crypto beta plus the memes' upward drift, not a meme-specific clock effect.
- **Inferred:**
  - This matches ITSM and FUNDCLOCK. Intraday clock effects on liquid perps are worth 0 to a few bp gross, and that
    does not survive even zero-fee Lighter spreads.
  - Cheaper execution would not rescue it. The 1.5× stress, and the possibility that night-time spreads are wider
    than our 10:35 UTC snapshot, both work against the strategy.

## Caveats

- **Costs come from one 10-minute REST sample** on Monday 10:35–10:45 UTC. Spreads at 22:00 UTC may be wider, which
  would make the result worse.
- **Prices are Binance's, used as a proxy for Lighter execution.** Lighter 1m candles were not used.
- **Funding uses the same month's mean Binance rate**, a cost proxy that is not point in time. It is small: about
  0.1–0.25 bp per trade.
- **The 2022 basket holds only DOGE and 1000SHIB.** Universe breadth grows over time.
- **The basket's n is days.** Per-coin legs on the same day are one correlated bet, so the daily t is the honest
  statistic.

## Files

- Pre-registration: `reports/hypotheses/night_preregistration.json`
- Evidence:
  - `research/observations/evidence_night_train_20261005.json`
  - `research/observations/evidence_night_validation_W2224_PC_20261005.json`
  - `research/observations/evidence_night_paper_20261005.json`
- Scripts:
  - `scripts/research/night_spreads.py` (Lighter sampler)
  - `scripts/research/night_fetch.py` (archive download: 11.4 MB, 0 errors, 0 missing)
  - `scripts/research/night_sim.py`
- Data in `data/raw/web/night/`:
  - `k1h_*.parquet`, `funding_*.parquet`;
  - `lighter_spreads_20261005T1035Z.jsonl`;
  - `trades_*.parquet`;
  - `VALIDATION_RUN.lock`.
- DB observations (document modality): the five verified quotes above, plus two rejected ones.
