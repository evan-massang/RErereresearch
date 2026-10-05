# H-SOLLEAD (SOL/USD leads memecoin prices): FAIL on train, validation not opened

Agent "sollead", 2026-10-05. Source idea: `sources/leads/documented_edges_round3.md`, idea 1 (a lead: Guo et al. JEDC 2024,
Hansen-Kim-Kimbrough arXiv 2109.12142; nothing memecoin-specific). Scripts: `scripts/research/sollead_lib.py`,
`sollead_describe.py`, `sollead_sim.py`. Evidence: `research/observations/evidence_sollead_describe.json`,
`research/observations/evidence_sollead_sim.json`.

## Data
- SOL/USDT 1-minute klines (Binance public market-data API, cached in `data/raw/web/solusd/`, nothing fetched after
  1791072000). SOL was very quiet: train 1-min return sd 0.081%, |r| 99th percentile 0.26%. Over train, no 1-minute
  move reached ±1% and only one reached ±0.5%.
- Curve: trusted states only (|vsol − rsol − 30| < 0.01), Mayhem tokens excluded, prints after completion dropped.
  AMM: post-trade mid with true reserve = logged + 17.585, Mayhem mints excluded.
- The train tape has gaps (Oct 2 00:00–01:00 and 08:00–16:00 UTC have no curve trades; 20:00–24:00 is also empty), so only **881 train minutes**
  have an index value (median 69 curve tokens, 52 pools per minute). Holdout and ≥ 1791072000 never loaded.

## Step 1: description (train only)
Equal-weight index = mean of clipped 1-min log returns of tokens priced in consecutive minutes.
- **Cross-correlation** of SOL return (minute t) with index return (minute t+k), SE ≈ 0.034:
  - curve: k=0 +0.045; k=1..10 between −0.022 and +0.067 (largest k=9, ~2 SE, isolated);
  - AMM: k=0 +0.011; k=1..10 between −0.017 and +0.048.
  Not even the contemporaneous SOL-terms correlation is significant. USD-terms correlations differ only by the SOL leg.
- **Distributed-lag OLS (lags 0–10, Newey-West):** no beta has |t| > 1.92 (curve) or 1.49 (AMM).
- **Event study** (SOL h-min return beyond train 1st/99th percentile, h = 1/3/5, 10-min cooldown): 10–20 events per
  cell; ±0.5% thresholds 1–12 events; ±1% 0–1. Abnormal cumulative index responses over 1–10 min are ±0.1–2% with
  |t| mostly < 2; the few |t| ≈ 2–2.6 cells (e.g. AMM after SOL drops at h=3: −0.7% / −2.1% at 1/2 min) are what
  ~100 tests produce by chance, and are small next to round-trip costs (≥ 2.5% fees on the curve).

Verdict of step 1: **no lead-lag detectable** at 1-minute resolution in this sample.

## Step 2: rules (pre-registered, 12 configs)
Buy the top-5 tokens by trailing-5-min SOL volume (≥ 10 trades, traded in the signal minute; AMM pools need ≥ 50 SOL
true reserve) at kline close + 1 s after SOL h-min return ≥ train p99 (h=1: +0.217%, h=3: +0.384%); exit after N
minutes. venue {curve, amm} × h {1, 3} × N {2, 5, 10}. Exact fills (curve `event_studies.rt`, AMM
`amm_flow_lib.round_trip`), 0.5 SOL, 1 s latency.

Train signals: h=1 19 (11 with a live universe → 55 trades), h=3 15 (8 → 40 trades).

| config (tip 0.001) | n | net SOL | PF | net ex top 3 |
|---|---|---|---|---|
| curve h1 N2/N5/N10 | 55 | −1.10 / −2.16 / −2.20 | 0.76 / 0.62 / 0.69 | all < −3 |
| curve h3 N2/N5/N10 | 40 | −1.93 / −1.54 / −1.73 | 0.52 / 0.67 / 0.71 | all < −3 |
| amm h1 N2/N5/N10 | 55 | −0.98 / −0.66 / −0.67 | 0.72 / 0.88 / 0.92 | all < −1.8 |
| amm h3 N2/N5 | 40 | −2.48 / −0.93 | 0.28 / 0.78 | < −2.5 |
| **amm h3 N10** | 40 | **+2.90** | **1.76** | **−0.10** |

At tip 0.01 everything is worse (amm h3 N10: +2.18, PF 1.53, ex-top-3 −0.76). Baseline (same universe/exits at every
10th train minute, no SOL condition): curve −0.025 to −0.033 SOL/trade, AMM −0.024 to −0.065 SOL/trade.

The only positive cell (amm h3 N10) fails the bar on two counts (n = 40 < 50; negative without the 3 best trades),
rests on 8 SOL events whose 5 trades each are not independent, and its N2/N5 neighbours are negative. **No config
passed train, so validation was not scored.**

## Verdict
FAIL. SOL/USD did not lead SOL-denominated memecoin prices in a measurable way on Oct 1–2, and conditioning entries
on SOL jumps does not beat costs. Caveat: SOL barely moved (no ±1% minute), so the hypothesis is weakly tested for
large SOL shocks; a re-test would need a volatile SOL period, not a parameter change.
