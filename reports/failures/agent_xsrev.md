# H-XSREV: 1–4 h cross-sectional residual reversal on HL-listed Binance USDT-M perps. Verdict: FAIL

Source idea: `sources/leads/documented_edges_round6.md`, idea 4 (Zaremba et al. 2021; Kozlowski et al. 2020;
Wen et al. 2022). Pre-registration, frozen before any 1h kline was downloaded:
`reports/hypotheses/xsrev_preregistration.json`.

**Bar** (per split, primary costs, coin-leg round trips): n ≥ 50, net > 0, PF > 1.2, net > 0 without the 3 best trades.

**Result.** All 12 configs fail on train. The gross edge is 0–2.5 bp per leg round trip, against 13 bp of cost.
As pre-registered, validation was run once on the config with the best train mean (`ew_resid_L4_H4_B`), for
information only. It also loses: −10.0 bp per leg, PF 0.91. The holdout (2026-04-01 onward) was never downloaded.

## Data

| item | source | cache |
|---|---|---|
| 1h klines, 208 HL-listed symbols + BTCUSDT, 2023-01..2026-03 | data.binance.vision `futures/um/monthly/klines/<SYM>/1h` (147 MB downloaded, zips never written) | `data/raw/web/xsrev/k1h/` |
| daily quote volume, all 678 archive USDT perps incl. delisted (for ranking) | read-only reuse of `data/raw/web/momentum/klines` | `data/raw/web/xsrev/daily_qv.parquet` |
| funding | read-only reuse of `data/raw/web/momentum/funding` (Binance fundingRate archive) | `data/raw/web/xsrev/funding/` |
| HL listing | HL `info` `meta` (234 perps incl. `isDelisted`) × archive symbols → 216 pairs, 42 HL-delisted | `data/raw/web/xsrev/hl_bn_pairs.json` |

The ffdiff_wide mapping named in an early draft was deleted by another job mid-run, so the mapping was rebuilt from
HL meta. It has the same 216 pairs.

Scripts: `scripts/research/xsrev_lib.py` (tiers), `xsrev_fetch.py`, `xsrev_sim.py`.

## Method (as pre-registered)

- **Tiers (point in time):** rank each day by 30d quote volume (days d−30..d−1). Tier A = ranks 11–50, tier B = ranks 51–150.
  - Coins must be HL-listed, have ≥ 60 daily bars and have a beta. That leaves about 30 coins in tier A and about 50 in tier B per day.
- **Beta:** from 720 hourly bars before each 00:00.
- **Signal:** residual over L ∈ {1, 4} h, measured against BTC beta or against the equal-weight tier mean.
- **Portfolio:**
  - Long the 5 lowest and short the 5 highest; rebalance every H ∈ {1, 4} h.
  - Enter at the open of the bar starting at t.
  - Legs that stay in their bucket are kept without trading.
  - 15% stop. Delisted legs exit at the last close with a 2% charge.
  - Binance funding is charged as a proxy for HL funding.
- **Costs:** 4.5 bp HL taker + 2 bp slippage per side per leg (13 bp per round trip). The Binance sensitivity uses 5 + 2 bp (14 bp).

## Train (2023-02-01 .. 2025-06-30)

Means are bp per coin-leg round trip.

| config | n | gross | net | net (BN 5 bp) | PF | net ex top-3 | 2023 net | 2024 net | 2025H1 net |
|---|---|---|---|---|---|---|---|---|---|
| btc_resid L1 H1 A | 166,356 | +0.2 | −12.8 | −13.8 | 0.77 | −214.7 | −12.0 | −13.9 | −12.2 |
| btc_resid L1 H4 A | 41,890 | 0.0 | −13.1 | −14.1 | 0.88 | −55.7 | −10.6 | −12.0 | −19.8 |
| btc_resid L4 H1 A | 89,171 | −1.0 | −14.1 | −15.1 | 0.80 | −126.6 | −13.0 | −14.4 | −15.3 |
| btc_resid L4 H4 A | 41,914 | −1.9 | −15.0 | −16.0 | 0.86 | −63.7 | −14.3 | −13.7 | −18.8 |
| btc_resid L1 H1 B | 174,958 | +1.2 | −11.8 | −12.8 | 0.79 | −208.4 | −11.9 | −12.5 | −10.5 |
| btc_resid L1 H4 B | 44,113 | +2.0 | −11.1 | −12.1 | 0.90 | −50.8 | −13.0 | −12.9 | −4.2 |
| btc_resid L4 H1 B | 97,051 | +1.5 | −11.7 | −12.7 | 0.83 | −115.1 | −13.2 | −11.3 | −9.9 |
| btc_resid L4 H4 B | 44,171 | +2.1 | −11.1 | −12.1 | 0.89 | −50.5 | −13.5 | −10.8 | −7.3 |
| ew_resid L1 H1 A | 166,701 | +0.4 | −12.6 | −13.6 | 0.77 | −211.5 | −11.9 | −13.7 | −11.7 |
| ew_resid L4 H4 A | 42,048 | −1.5 | −14.6 | −15.6 | 0.86 | −62.2 | −14.6 | −12.3 | −19.2 |
| ew_resid L1 H1 B | 174,830 | +1.5 | −11.6 | −12.6 | 0.79 | −203.6 | −11.7 | −12.0 | −10.4 |
| **ew_resid L4 H4 B** (best mean) | 44,163 | +2.5 | −10.7 | −11.7 | 0.90 | −48.8 | −13.1 | −11.1 | −5.7 |

Net ex top-3 is a sum of fractions of leg notional.

Other train facts:
- **Volume:** 47–199 leg trades a day.
- **Funding:** small, about −0.03 to −0.15 bp per leg.
- **Stops:** 343–664 per config.
- **Baskets:** entry-cohort basket returns are negative with t from −8 to −35.

## Validation (2025-07-01 .. 2026-03-31), run once: ew_resid L4 H4 B

The selected config failed train, so this is information only.

| | n | gross bp | net bp | net BN bp | PF | net ex top-3 | win |
|---|---|---|---|---|---|---|---|
| all | 13,823 | +3.4 | −10.0 | −11.0 | 0.91 | −15.2 | 51% |
| 2025 H2 | 9,340 | +4.7 | −8.6 | −9.6 | 0.93 | −9.3 | 52% |
| 2026 Q1 | 4,483 | +0.8 | −13.0 | −14.0 | 0.88 | −6.5 | 51% |

- **By side:** long −16.7 bp, short −3.4 bp.
- **Activity:** 50.6 leg trades a day; 285 stops.
- **Baskets:** basket t = −3.4.

## Reading

- **The reversal is tiny and fully inside costs.**
  - Its sign matches the literature: the less liquid tier B is mildly reverting (+1 to +2.5 bp gross per leg), while tier A at L = 4 h is slightly momentum (−1 to −2 bp gross). This is consistent with Zaremba et al.'s liquid-coin momentum.
  - The size is about 1/5 to 1/10 of the 13 bp round trip.
  - No config, year or tier comes close to the bar: the best year cell is −4.2 bp net.
- **A maker-entry variant** (the doc's stated follow-up) would need to save more than about 10 bp per round trip with no adverse selection. HLANCHOR already showed passive HL quotes get picked off. Not pursued.
- **Caveats:**
  - HL listing status is HL's current meta, not point-in-time listing dates.
  - Entry is at the hourly open with no extra latency, which favours the strategy. The verdict is a fail even so.

Evidence: `research/observations/evidence_xsrev_train_20261005.json`, `research/observations/evidence_xsrev_validation_20261005.json`.
Trade-level parquet: `data/raw/web/xsrev/trades_{train,validation}_*.parquet`.
