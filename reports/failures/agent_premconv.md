# H-PREMCONV: perp-spot premium-spike convergence. FAIL on train (validation not examined)

_Agent run 2026-10-05. Real data (data.binance.vision), `is_synthetic = false`. Lead:
`sources/leads/documented_edges_round5.md`, "Idea 3. Premium-spike convergence" (the task calls it idea 4), and
He, Manela, Ross & von Wachter, arXiv 2212.06888 v6. All are leads (`document` modality); nothing here upgrades them._

## Verdict

**FAIL on train. All 12 pre-registered configs fail at every latency (0, 1 and 2 min).** The best config, BAS_B+50_X5_H4,
has PF 0.91 at L=0 and PF 0.54 at the primary L=1. Because no config met the bar on train, **validation (2025-07..2026-03)
was not run**. Holdout data (2026-04 onward) was never downloaded.

The mechanism fails before costs. **1-minute premium spikes revert within the same minute, before a next-open fill.**
The frictionless gross capture (no fees, no slippage) is about 0 bp per trade for the PI signal at L=1. Costs are about 50 bp.

## What was frozen first

`reports/hypotheses/premconv_preregistration.json` was frozen at 2026-10-05 04:34 UTC, before any P&L. Only one DOGE file was opened, to check its format.

**Universe.** Each month M takes the top 30 Binance USDT perps by M-1 futures quote volume, using the 1d archive.
- Each needs a Binance spot USDT pair; 1000/1000000/1M multiplier prefixes are mapped.
- Each needs at least 28 days of data on both venues in M-1.
- Stablecoins are excluded; memes are included.
- This gives 39 months (2023-01..2026-03) and 185 unique symbols. Train covers 898 symbol-months and 157 symbols.
- No files were missing. Two symbol-months were dropped by the pre-declared data-validity rule (median |BAS| > 1%):
  - MATIC 2024-09, the POL migration;
  - ALPACA 2025-05, delisting.
- Script: `scripts/research/premconv_universe.py`.

**Signals.**
- **PI** is the 1m `premiumIndexKlines` close.
- **BAS** is the same-minute perp close / spot close − 1.

**Entry.** Enter on an onset, defined as signal ≥ B (+0 or +50 bp).
- B = 0.30% taker fees (spot 0.10%, Binance fee schedule; USDⓈ-M 0.05%, Binance FAQ 360033544231) + 4 × slippage + 10 bp.
- Slippage is set by trailing-7d min(spot, perp) ADV:
  - 3 bp at ≥ $100M;
  - 5 bp at $20–100M;
  - 15 bp at $2–20M;
  - no trade below $2M.
- So B = 0.52%, 0.60% or 1.00%.

**Trade.** Short the perp and buy spot at the open of bar t+1+L, both legs.

**Exit.** The first of: signal ≤ 0.05% (or ≤ 0.20%), the max hold (4h or 24h), or perp high ≥ 1.3× entry. The exit fills at the next+L open.
- Funding prints during the hold are credited.
- One position per symbol, with a 60-min cooldown.
- Positions are force-closed at the split boundary.

**Negative premium.** The negative-premium mirror is excluded, because spot borrow is not in the public archive.

## Train results (2023-01-01 .. 2025-06-30), P&L in units of one leg's notional

| config | L0 n / mean bp / PF | L1 (primary) n / net / mean bp / PF / net ex-top3 | L2 n / mean bp / PF |
|---|---|---|---|
| PI_B0_X5_H4 | 921 / −54.8 / 0.04 | 919 / −4.952 / −53.9 / 0.03 / −5.039 | 911 / −60.5 / 0.02 |
| PI_B0_X5_H24 | 921 / −54.8 / 0.04 | 919 / −4.951 / −53.9 / 0.03 / −5.037 | 911 / −60.5 / 0.02 |
| PI_B0_X20_H24 | 929 / −55.1 / 0.04 | 927 / −4.998 / −53.9 / 0.03 / −5.095 | 919 / −60.3 / 0.03 |
| PI_B+50_X5_H4 | 382 / −65.6 / 0.07 | 382 / −2.584 / −67.6 / 0.03 / −2.643 | 381 / −79.3 / 0.02 |
| PI_B+50_X5_H24 | 382 / −65.6 / 0.07 | 382 / −2.584 / −67.6 / 0.03 / −2.643 | 381 / −79.3 / 0.02 |
| PI_B+50_X20_H24 | 382 / −66.3 / 0.07 | 382 / −2.578 / −67.5 / 0.03 / −2.637 | 382 / −79.4 / 0.02 |
| BAS_B0_X5_H4 | 2852 / −37.5 / 0.28 | 2785 / −14.581 / −52.4 / 0.16 / −14.669 | 2723 / −55.0 / 0.15 |
| BAS_B0_X5_H24 | 2852 / −37.4 / 0.28 | 2785 / −14.576 / −52.3 / 0.16 / −14.665 | 2723 / −55.0 / 0.15 |
| BAS_B0_X20_H24 | 2861 / −38.4 / 0.26 | 2801 / −14.864 / −53.1 / 0.15 / −14.943 | 2736 / −55.2 / 0.15 |
| BAS_B+50_X5_H4 | 90 / −4.6 / 0.91 | 89 / −0.276 / −31.0 / 0.54 / −0.372 | 89 / −51.6 / 0.31 |
| BAS_B+50_X5_H24 | 90 / −4.6 / 0.91 | 89 / −0.276 / −31.0 / 0.54 / −0.372 | 89 / −51.6 / 0.31 |
| BAS_B+50_X20_H24 | 90 / −16.5 / 0.71 | 89 / −0.299 / −33.6 / 0.50 / −0.385 | 89 / −53.7 / 0.29 |

The 4h and 24h holds give near-identical results, because the median hold is 2–3 minutes and almost every exit is a signal exit.

## Why it fails (train diagnostics)

**1. PI spikes are not tradable dislocations between Binance perp and Binance spot.**
- At the PI onset bar, the median PI is 0.83% while the median same-minute Binance close basis is **0.00%**.
- By the next bar's close the median PI is 0.06%.
- The spike lives in the impact-price/index construction, not in prices we can trade. The frictionless gross capture is +0.4 bp per trade (median 0).
- The result is −54 bp per trade, which is simply fees plus slippage. The win rate is 3%.

**2. BAS spikes revert inside one minute.**
- The median close basis falls from 0.72% at signal to 0.02% at the next close.
- The basis at the next open is 0.06%, so the spike is already gone at the L=0 fill.

**3. 97% of BAS_B0 trades are a tick-size artifact on 1000PEPEUSDT.**
- PEPE spot ticks at 1e-8 against a price of about 1e-6, i.e. a tick of about 1% of price.
- 2,712 of 2,785 trades come from it, concentrated in 2023Q3–2024Q1.

**4. Post-hoc, train only, NOT a tested variant.** Even with PEPE removed, nothing passes:
- BAS_B0 at L=1: n = 73, net −0.032, PF 0.84.
- BAS_B+50: n = 21, PF 3.4, carried by BNX (6 trades). That fails n by a wide margin.

## Concentration, decay and event counts (PI_B0_X5_H4, L=1)

- **Coverage.** 102 symbols on 741 symbol-event-days.
- **Largest loss.** 1000PEPE has the largest net loss (130 trades, −0.52), and losses are broad across coins.
- **By liquidity tier:**
  - 3 bp tier: −42 bp per trade;
  - 5 bp tier: −49 bp;
  - 15 bp tier: −95 bp.
- **Quarterly trade counts decay sharply.** 2023Q1 had 258 trades, against 3–41 per quarter from 2024Q2 on. Every quarter is negative (−16 to −68 bp).
- **Consistent with the literature.** He et al. report deviations shrinking over time.
- **Small n late in the sample.** The BAS_B+50 quarters 2024Q4–2025Q1 are positive, but on 8 trades.

## What would justify a revisit (a new pre-registration, not a re-tune)

- **Sub-minute data.** bookTicker or aggTrades with a realistic sub-second latency model. 1m bars cannot capture a spike that lives for less than a minute.
- **Maker execution on the spot leg.** This needs queue modelling, which the archive cannot support.
- **A price-tick filter** (tick/price ≤ 5 bp) declared before any test.

Without these, the 1m premium-spike rule has no gross edge to protect.

## Files

- **Pre-registration:** `reports/hypotheses/premconv_preregistration.json` (written by `scripts/research/premconv_prereg.py`).
- **Scripts:**
  - `scripts/research/premconv_universe.py`
  - `scripts/research/premconv_fetch.py`
  - `scripts/research/premconv_sim.py`
- **Evidence:** `research/observations/evidence_premconv_train.json`. It holds:
  - per config × latency stats, skips, exit reasons;
  - per-quarter, per-symbol and per-tier breakdowns;
  - top and worst trades;
  - dropped symbol-months.
- **Cache (147 MB):** `data/raw/web/binance_prem/`. It holds universe.json, monthly_vol.parquet and fetch_log.json; event windows plus daily and funding parquet under win/, daily/ and funding/; and trades_train.parquet. No zips or CSVs are kept.
