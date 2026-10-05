# H-FUNDCLOCK: price pressure around funding settlements on Binance USDT-M perps. FAIL on train (validation not examined)

_Agent run 2026-10-05. Real data (data.binance.vision), `is_synthetic = false`. All numbers are our own
computations; the literature items below are leads (`document` modality) only._

## Verdict

**FAIL on train. All 12 pre-registered configs fail.** PF is 0.39–0.83, every net sum is negative, and every
net-ex-top-3 is negative. Because no config met the bar on train, **no config was selected and validation
(2025-07-01 to 2026-03-31) was not run**. Holdout data (2026-04 onward) was never downloaded.

**What we found:**
- **Pre-settlement leg.** The pressure the hypothesis predicts is faintly present: going against the side that
  pays funding into the settlement earns +2 to +11 bp gross on average. That is below the 14 bp taker round trip.
- **Post-settlement leg.** The predicted rebound is not there. Gross returns are −3 to −10 bp, so the move goes the
  wrong way for the hypothesis.

## Pre-registration (frozen before any data was downloaded)

The full rules are in `reports/hypotheses/fundclock_preregistration.json`.

- **Universe.** Each month M takes the top 20 Binance USDT-M perps by M-1 futures quote volume (1d archive).
  - A symbol needs at least 28 days of data in M-1.
  - Stablecoins are excluded.
  - That gives 39 months (2023-01 to 2026-03) and 158 symbols; train uses 129 of them.
  - In 2026 the rule admitted the commodity perps XAU, XAG and PAXG. This is the frozen rule and affects
    validation only.
- **Settlements.** The settlement times T are the fundingRate `calc_time` values. Train has 67,713 symbol-settlements:
  - 43,648 on 8h intervals;
  - 21,223 on 4h intervals;
  - 2,823 on 1h intervals.
- **PRE leg.**
  - Signal: the previous settled rate (point in time). Its correlation with the rate at T is 0.70.
  - If f ≥ +thr, short; if f ≤ −thr, long.
  - Entry is the open of the 1m bar at T−k; exit is the close of the bar at T−1m.
- **POST leg.**
  - Signal: the rate settled at T.
  - If f ≥ +thr, long (the payers re-enter); if f ≤ −thr, short.
  - Entry is the open of the bar at T+1m; exit is the close of the bar at T+m.
- **Grid (12 configs):** mode {PRE, POST} × window {5, 15, 30} min × |f| threshold {0.03%, 0.10%} per settlement.
  - At most one trade per symbol per settlement.
- **Costs:** Binance taker 5 bp plus 2 bp slippage per side, so 14 bp a round trip.
  - No funding is exchanged, since both legs are flat at T.
  - The maker variant was not run, because maker non-fills cannot be modelled honestly from 1m bars.
- **Bar:** n ≥ 50, net > 0, PF > 1.2 and net without the top 3 trades > 0.
- **Selection:** the best passing train config was to go to validation once. None passed.

## Train results (settlements 2023-01-01 to 2025-06-30)

Net sums are in % of notional, summed over trades.

| config | n | net sum % | mean bp | gross mean bp | PF | net ex-top3 % | day-t |
|---|---|---|---|---|---|---|---|
| PRE_w5_thr0.03pct | 5995 | −704.3 | −11.8 | +2.3 | 0.39 | −713.1 | −10.1 |
| PRE_w5_thr0.10pct | 782 | −26.5 | −3.4 | **+10.6** | 0.83 | −35.1 | −1.0 |
| PRE_w15_thr0.03pct | 5995 | −695.5 | −11.6 | +2.4 | 0.60 | −713.3 | −6.6 |
| PRE_w15_thr0.10pct | 782 | −51.3 | −6.6 | +7.5 | 0.82 | −65.4 | −1.6 |
| PRE_w30_thr0.03pct | 5995 | −784.8 | −13.1 | +0.9 | 0.68 | −808.2 | −4.8 |
| PRE_w30_thr0.10pct | 782 | −125.7 | −16.1 | −2.1 | 0.73 | −143.2 | −2.6 |
| POST_w5_thr0.03pct | 6018 | −1011.6 | −16.8 | −2.8 | 0.43 | −1028.4 | −8.1 |
| POST_w5_thr0.10pct | 782 | −188.6 | −24.1 | −10.1 | 0.43 | −198.2 | −4.2 |
| POST_w15_thr0.03pct | 6018 | −1295.1 | −21.5 | −7.5 | 0.51 | −1329.4 | −7.2 |
| POST_w15_thr0.10pct | 782 | −180.2 | −23.0 | −9.0 | 0.58 | −210.0 | −3.5 |
| POST_w30_thr0.03pct | 6018 | −1140.5 | −19.0 | −5.0 | 0.64 | −1176.8 | −6.1 |
| POST_w30_thr0.10pct | 782 | −170.3 | −21.8 | −7.8 | 0.68 | −196.3 | −3.0 |

Notes on the table:
- Day-t is the t-statistic on daily net sums.
- **Skipped trades** (a missing 1m bar): 33 in the PRE configs at 0.03% and 8 at 0.10%, mostly settlements at the
  start of a month whose pre-window falls in a month when the symbol was not in the universe. No POST trades were
  skipped.

### Best config (closest to passing): PRE_w5_thr0.10pct

**By year:**

| Year | n | Net sum % | Gross mean bp |
|---|---|---|---|
| 2023 | 359 | −27.8 | +6.3 |
| 2024 | 199 | +3.3 | +15.6 |
| 2025 H1 | 224 | −2.0 | +13.1 |

**Shape of the edge:**
- The gross median is +6.3 bp and the gross win rate 58%, against a net win rate of 42%.
- **Negative funding dominates.** 664 of the 782 trades are longs ahead of a negative-funding print (gross +7.3 bp).
  The 118 shorts ahead of a positive print gross +29 bp, but that is a small sample.
- **By funding interval:** 1h-interval symbols gross +19 bp (n = 103), 8h +12 bp (n = 363) and 4h +6 bp (n = 316).

**Concentration:**
- The trades span 60 symbols. The most traded is TRBUSDT with 103 trades (13.2%).
- **Net is driven by one coin and one day.** LAYERUSDT is +9.6% over 75 trades, and the best day (2024-03-05)
  is +21.2%.
- The top 3 trades are +4.1%, +2.3% and +2.2%.
- The worst symbols are LINA −9.9%, TIA −7.8% and BLZ −6.9%.

The best train cell would need a gross mean above +14 bp just to break even. In 2024–25 it got close, at +13 to +16
bp. The lower threshold (0.03%), with 7.7× the trades, has almost no pressure: +2 bp gross.

## Interpretation

- **Stated or claimed (leads):** practitioners describe managing positions around funding times, and Binance's
  schedule is public. Our web search (2026-10-05) found no published study quantifying minute-level price moves
  just before or after settlements. The closest lead, an MDPI 2026 microstructure paper (snippet only; the page
  returned 403), concerns funding-rate *spreads* peaking about 2h after settlement, not prices.
- **Observed (train):**
  - With large |funding|, the last 5–15 minutes before settlement drift slightly against the paying side
    (+7 to +11 bp gross).
  - After settlement the drift does **not** reverse. The POST "re-entry" leg loses even before costs, and the long
    side after positive funding loses −49 bp gross (n = 118).
- **Inferred (not tested):** this looks less like avoid-and-reopen flow and more like a one-way move. Possibilities
  include basis or premium compression into the print, or extreme-funding coins simply trending in the direction
  funding is trying to correct.
- **Not tradable at taker costs.** A maker-entry version would need a fill model that the 1m archive cannot support.
  Testing it would be a new pre-registration and could not reuse these train results to pick a threshold.

## Data and budget

- **Source:** data.binance.vision only. fapi.binance.com returns HTTP 451 and was not used.
- **Data fetched:**
  - 1m klines for 780 symbol-months, streamed into memory and cut to ±35 min windows around each settlement;
  - funding prints for 158 symbols;
  - 1d klines for the ranking.
- **Transfer volume:**
  - The first window pass (1.33 GB) was discarded because of a timestamp-unit bug: windows came out empty, so no
    results were affected.
  - The re-fetch used another 1.32 GB.
  - Total network transfer was therefore about 2.7 GB, over the 1.5 GB target. **Disk** use stayed within budget:
    195 MB stored and no zips kept. Free space was 3.4 GB at the end, and the 2.5 GB stop guard never tripped.
- **Holdout guard:** nothing for 2026-04 or later was requested. Funding prints are cut at 2026-03-31.

## Files

- `reports/hypotheses/fundclock_preregistration.json`: the frozen rules.
- `scripts/research/fundclock_fetch.py`: universe, funding, 1m windows, holdout guard.
- `scripts/research/fundclock_sim.py`: simulator and stats. Validation is gated on the train selection.
- `research/observations/evidence_fundclock_train.json`: all 12 configs, by year, by symbol, by interval, top days.
- `data/raw/web/fundclock/`:
  - `universe.json`;
  - `monthly_vol.parquet`;
  - `funding/`;
  - `win/` (1m windows);
  - `trades/train_*.csv`.
