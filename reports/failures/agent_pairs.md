# H-PAIRS: 5-min cointegrated pairs on HL-listed perps, two taker legs. Verdict: FAIL

**Family.** This is a weekly-formed Engle–Granger pairs strategy on the top 30 Binance USDⓈ-M perps that are also listed on Hyperliquid. It trades z-score reversion of a frozen-hedge log spread at 5-min resolution, using two taker legs.

**Lead.** `sources/leads/documented_edges_round6.md` idea 3 (Fil and Kristoufek 2020; Tadi and Kortchemski 2021). These are leads, not validated findings.

**Pre-registration.** See `reports/hypotheses/pairs_preregistration.json`. It was frozen before any 5-min data was downloaded. One amendment was made, also before any computation: statsmodels is not installed, so the MacKinnon p-value was replaced by the equivalent test, t < −3.3368 (the 5% critical value for N = 2), with pairs ranked by t-stat.

**Bar (per split, HL costs).** n ≥ 50, net > 0, PF > 1.2, and net > 0 without the 3 best trades.

## Result

No config is profitable even before costs on train. Average gross per trade is −11.0 to −0.1 bp of gross notional, against a cost of 11 bp per round trip. The chosen config also fails on validation.

| split | config | n | gross bp/trade | net bp/trade (HL) | net USD (HL) | PF (HL) | ex-top-3 (HL) | net USD (Binance 5 bp) | pass |
|---|---|---|---|---|---|---|---|---|---|
| train 2024-07..2025-06, all 12 configs | — | 2,543–4,520 | −11.0 to −0.1 | −22.0 to −11.1 | −12,342 to −8,256 | 0.75–0.82 | all < 0 | −13,234 to −8,798 | 0 of 12 |
| train | **z3.0_o0.5_h2** (chosen: highest train net) | 2,713 | −4.2 | −15.2 | −8,256 | 0.79 | −8,805 | −8,798 | no |
| train 2024 (H2) | chosen | 1,207 | −10.3 | −21.3 | −5,152 | 0.75 | −5,507 | | no |
| train 2025 (H1) | chosen | 1,506 | +0.7 | −10.3 | −3,104 | 0.84 | −3,629 | | no |
| **validation 2025-07..2026-03 (run once)** | chosen | 3,347 | +4.3 | −6.7 | −4,464 | 0.85 | −4,792 | −5,134 | **no** |
| validation 2025 (H2) | chosen | 2,364 | +1.8 | −9.2 | −4,332 | 0.81 | −4,660 | | no |
| validation 2026 (Q1) | chosen | 983 | +10.3 | −0.7 | −133 | 0.98 | −348 | | no |

Trade size is $2,000 gross notional per pair trade, so 11 bp is $2.20 per round trip.

**Informational sensitivities** (none was selected on):
- **2 bp slippage:** validation net −5,803.
- **One more 5-min bar of fill delay:**
  - train: −8,465, gross −4.6 bp per trade;
  - validation: −3,980, gross +5.1 bp per trade.

  Fill timing is not what kills the strategy. The gross edge is too small at any fill time.

**Frequency.** The chosen config trades about 7.5 times a day on train and 12 a day on validation. The other train configs trade 7–12 a day, so the n requirement is easily met.

## Why it fails (observed in the trade files)

The reverting trades do revert. Their wins are wiped out by the trades whose spread keeps diverging.

| exit reason, chosen config, gross bp | train n | train mean | validation n | validation mean |
|---|---|---|---|---|
| reverted to \|z\| ≤ 0.5 | 2,113 | +59.5 | 2,773 | +38.3 |
| stop (\|z\| ≥ 5) | 311 | −194.5 | 268 | −156.3 |
| time stop (2 × half-life) | 139 | −493.7 | 154 | −284.1 |
| week end (re-formation) | 142 | −56.7 | 151 | −40.1 |

- **Win rate is about 60%,** but losers are 3–8 times larger than winners. A 30-day, 5-min cointegration test does not identify pairs whose relationship holds through the next week. Within-week breaks dominate: these are the stop and time-stop exits.
- **The gross edge, where it exists,** is +0.7 to +10 bp per trade in 2025–26, against an 11 bp HL round-trip cost. It would need a maker or rebate structure, as in Tadi and Kortchemski's BitMEX −2.5 bp rebate, to approach zero. That structure is not available on HL or Binance at our tier.
- **2026 Q1 validation is close to break-even** (−0.7 bp net, n = 983). This is not evidence of an edge: it is one quarter, the chosen config was never profitable on train, and it still has PF < 1.

## What was not done

- **1-min:** not run. 1-min zips are about 4–5 times the 5-min size, so the universe would need about 1.7 GB of downloads against the 1 GB budget. This was stated in the pre-registration before any result. The 5-min result alone does not say that 1-min fails. However, the loss mechanism here is cointegration breaks, which are not a resolution problem, and costs per trade would be the same.
- **The maker-entry variant** in the lead's grid needs book or trade-through data. It is not testable on klines.
- **Funding** was not modelled. With two opposite legs held for a median of about 5–8 hours, it is small either way.
- **Holdout** (2026-04-01 onward) was never downloaded.

## Limitations

- The HL listing date is proxied by the first HL daily candle (the info API `candleSnapshot`, which starts at our 2022-01-01 request start).
- The universe is ranked on Binance volume, not HL volume.
- Fills are taken at the next 5-min open plus 1 bp. Real HL fills on smaller coins may be worse, which would only deepen the failure.

## Files

- Pre-registration: `reports/hypotheses/pairs_preregistration.json`
- Evidence:
  - `research/observations/evidence_pairs_train_20261005.json` (all 12 configs, by year, exit reasons, delay sensitivity, formation summary)
  - `research/observations/evidence_pairs_validation_20261005.json`
- Code:
  - `scripts/research/pairs_universe.py`
  - `scripts/research/pairs_hl_listing.py`
  - `scripts/research/pairs_fetch.py`
  - `scripts/research/pairs_sim.py`
- Data (`data/raw/web/pairs/`):
  - `k5m/` (128 symbols, open and close prices, 121 MB; 367 MB downloaded; zips never written to disk)
  - `universe.json`, `formation.json`
  - `results_*.json`, `trades_*.csv`
  - `hl_meta_20261005.json`, `hl_first_day.json`
