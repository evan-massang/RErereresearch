# H-LSRATIO: crowd vs top-trader long/short positioning, fade the crowd (2026-10-05): FAIL on train

- **Pre-registration (frozen before any data was fetched):** `reports/hypotheses/lsratio_preregistration.json`
- **Lead:** `sources/leads/documented_edges_round6.md` idea 6. It was adapted to a per-symbol time series at the requester's instruction.
- **Code:**
  - `scripts/research/lsratio_fetch.py`
  - `scripts/research/lsratio_sim.py`
- **Evidence:**
  - `research/observations/evidence_lsratio_train_20261005.json`
  - `research/observations/evidence_lsratio_validation_20261005.json`
- **Data:** `data/raw/web/lsratio/`, about 93 MB of parquet; no zips were kept.
  - Metrics: data.binance.vision `futures/um/daily/metrics`. That is 39,540 symbol-days, with 10 days missing in the archive.
  - Prices: 1h klines for 170 symbols.
  - Total download was 547 MB.
  - Nothing dated 2026-04-01 or later was requested or read, so the holdout is untouched.

## Setup (as pre-registered)

**Universe.** Each day, the top 30 HL-listed USDT-M perps by trailing 30-day volume.
- 170 distinct symbols appear over the period, giving 854k symbol-hours.
- HL listing comes from the 2026-10 meta, so it is not point-in-time.

**Signals.** Decisions are made hourly. Each uses the metrics row stamped t − 5 min, treated as known only at t.
- **z-scores:** each change is z-scored against its own trailing 168 hourly values.
- **`div`:** the change over L h in ln(crowd account ratio) minus the change in ln(top-trader position ratio), z-scored. A value of ±2 or beyond means fade the crowd.
- **`oi_crowd`:** z of the OI change ≥ 1.5 together with |z of the crowd-ratio change| ≥ 1.5. Fade the crowd's side.

**Grid.** 12 configs: 2 signals × L ∈ {1, 4} h × H ∈ {1, 4, 8} h.

**Trading rules:**
- Enter at the next 1h open.
- 5% stop.
- One position per symbol.
- Costs are 13 bp per round trip (HL 4.5 bp taker + 2 bp slippage per side), plus Binance funding.

**Splits:**
- Train: 2023-01-01 to 2025-06-30. The archive starts around 2021-12, but the start was moved to 2023-01-01 to stay within the download budget.
- Validation: 2025-07-01 to 2026-03-31.

**Bar per split:** n ≥ 50, net > 0, PF > 1.2, and net without the top 3 trades > 0.

## Train results (fade the crowd, net per trade)

| config | n | mean net | gross | PF | net sum ex top 3 |
|---|---|---|---|---|---|
| div L1 H1 | 37,888 | −12.5 bp | +0.5 | 0.78 | −48.2 |
| div L1 H4 | 29,250 | −13.8 | −0.7 | 0.86 | −41.7 |
| div L1 H8 | 24,616 | −12.8 | +0.3 | 0.91 | −32.6 |
| div L4 H1 | 41,447 | −11.9 | +1.1 | 0.77 | −50.1 |
| div L4 H4 | 18,818 | −11.1 | +2.1 | 0.89 | −22.1 |
| div L4 H8 | 16,203 | −6.2 | +7.1 | 0.95 | −11.1 |
| oi_crowd L1 H1 | 9,541 | −14.1 | −1.0 | 0.79 | −14.0 |
| oi_crowd L1 H4 | 8,159 | −11.9 | +1.6 | 0.89 | −10.6 |
| oi_crowd L1 H8 | 7,601 | −6.8 | +7.0 | 0.95 | −6.3 |
| oi_crowd L4 H1 | 12,318 | −10.1 | +3.0 | 0.83 | −13.1 |
| oi_crowd L4 H4 | 5,986 | −4.8 | +8.7 | 0.96 | −3.8 |
| oi_crowd L4 H8 | 5,463 | −0.5 | +13.3 | 1.00 | −1.3 |

**No config passes on train.** By the pre-registered rule, validation was then run once, for the best config on train (oi_crowd L4 H8), as information only:

| split | n | mean net | gross | PF | net sum | ex top 3 |
|---|---|---|---|---|---|---|
| validation (oi_crowd L4 H8) | 1,625 | −3.9 bp | +10.5 | 0.97 | −0.63 | −1.91 |

## Informational checks (never selected on)

**Follow the crowd** (side flipped) is worse in every config:
- on train, −13.8 to −31.5 bp per trade net, with gross between −0.9 and −19.3 bp;
- on validation, −26.7 bp net and −15.0 bp gross.

So the direction of the effect is real: the crowd is on average wrong. It is just small.

**Residual check.** Train, pooled over all symbol-hours, with day-clustered standard errors and a control for the trailing return:
- the signal coefficient is negative (contrarian) and not just a past-return proxy:
  - div L4 H8: −6.2 bp per 1 SD, t = −3.8;
  - oi_crowd L4 H4: −6.9 bp, t = −3.0;
- at H = 1 h the coefficient is about −1 to −3.5 bp per SD.

**Binance cost sensitivity** (14 bp round trip) is slightly worse.

## Why it fails

- Fading the crowd earns a gross 0–13 bp per trade, and it is largest at the slowest setting (L4, H8).
- That is at or below the 13 bp round-trip cost.
- The win rate is about 45%, and PF stays below 1 net in every config and both splits.

The positioning metrics contain a statistically detectable contrarian signal of a few bp per SD. At 1–8 h horizons on liquid perps, it is too small to pay taker costs.

**Not tested** (would be new hypotheses that need their own rationale):
- maker execution;
- longer holds (24 h+);
- the lead's original cross-sectional market-neutral form.
