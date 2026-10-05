# H-CBPREM: KILLED on train (2026-10-05)

**Verdict: KILLED.** No train config has net > 0 at primary cost (best PF 0.758), and the kill test fails.
Validation (2025-07-01..2026-03-31) was **not run**, per the preregistration. Holdout (2026-04-01+) was never downloaded.

- Preregistration: `reports/hypotheses/cbprem_preregistration.json` (sha256 a3042f81…e175). It was written before any
  price data was fetched.
- Evidence: `research/observations/evidence_cbprem_train_20261005.json`. Simulator: `scripts/research/cbprem_sim.py`.
- Data: `data/raw/web/cbprem/` (160 MB). Coinbase 1m from the Coinbase Exchange public candles API through
  `pipeline/sources/coinbase.py`. Binance USD-M 1m klines and funding from data.binance.vision through
  `pipeline/sources/binance_vision.py`. Covers 2024-09-20..2026-03-31; nothing was sampled out.
- Lighter cost: $1,000 round trip, median of 15 orderBookOrders snapshots taken 2026-10-05 10:37Z
  (`data/raw/web/cbprem/lighter_spreads_20261005T1037Z.jsonl`). Costs in bp:
  - DOGE 3.4, PEPE 4.4, TRUMP 6.6, WIF 7.3, PENGU 7.5, SHIB 8.5, BONK 10.1, FLOKI 31.1, POPCAT 38.7.
  - The primary cost is 1.5× these.

## Universe
The rule required a first Coinbase 1m candle no later than 2025-05-31.

- **IN (9):** DOGE, PEPE, WIF, POPCAT, FLOKI, PENGU, TRUMP, BONK, SHIB.
- **OUT:** FARTCOIN (Coinbase listing 2025-06-12), PUMP (2025-07-15), SPX (2025-09-09), USELESS (2025-08-20).

Coinbase minute coverage after each coin's start: DOGE 99.7%, BONK 90%, PENGU 89%, PEPE 88%, SHIB 83%, POPCAT 71%,
TRUMP 65%, WIF 64%, FLOKI 37%. The thin pairs carry the staleness risk named in the leads file.

## Train results (2024-10-01..2025-06-30, $1,000 per trade)
Net USD and PF are given at each cost. The Binance taker cost is 10 bp per round trip.

| config | n | net 1.5× | PF 1.5× | net ex-top3 | net 1.0× | PF 1.0× | Binance taker net | gross USD | gross PF |
|---|---|---|---|---|---|---|---|---|---|
| W3d k1.5 H15 | 15266 | −24430 | 0.540 | −24649 | −16099 | 0.662 | −14703 | +565 | 1.015 |
| W3d k1.5 H30 | 12827 | −21746 | 0.623 | −22012 | −14659 | 0.725 | −13311 | −482 | 0.989 |
| W3d k1.5 H60 | 10250 | −17271 | 0.712 | −17737 | −11552 | 0.796 | −10364 | −112 | 0.998 |
| W3d k2.5 H15 | 2506 | −4261 | 0.578 | −4426 | −2830 | 0.692 | −2476 | +29 | 1.004 |
| W3d k2.5 H30 | 2244 | −3196 | 0.699 | −3394 | −1905 | 0.807 | −1567 | +675 | 1.079 |
| W3d k2.5 H60 (selected, highest PF) | 1975 | −2991 | 0.758 | −3265 | −1845 | 0.843 | −1528 | +445 | 1.042 |
| W7d k1.5 H15 | 13514 | −20769 | 0.564 | −20988 | −13386 | 0.687 | −12135 | +1379 | 1.040 |
| W7d k1.5 H30 | 11333 | −18348 | 0.640 | −18612 | −12089 | 0.744 | −10905 | +427 | 1.011 |
| W7d k1.5 H60 | 9084 | −14401 | 0.728 | −14729 | −9347 | 0.813 | −8323 | +759 | 1.017 |
| W7d k2.5 H15 | 2268 | −4025 | 0.579 | −4189 | −2692 | 0.691 | −2296 | −28 | 0.996 |
| W7d k2.5 H30 | 2000 | −3467 | 0.661 | −3682 | −2290 | 0.760 | −1938 | +62 | 1.007 |
| W7d k2.5 H60 | 1733 | −2722 | 0.757 | −3024 | −1704 | 0.840 | −1401 | +330 | 1.034 |

- Gross edge is between −0.4 and +3.0 bp per trade.
- The mean cost at 1.5× is about 15–17 bp per trade.
- The funding proxy is about 0 bp.
- Every config fails at every cost variant, including the 1.0× Lighter cost and the Binance taker cost.

**Selected config W3d k2.5 H60, by coin (net USD at 1.5×, mean gross bp):**
- Only DOGE is net positive: +77, PF 1.06, gross +8.2 bp. Its net ex-top-3 is −112.
- The rest are negative:
  - BONK −238 (+7.1)
  - SHIB −185 (+5.8)
  - FLOKI −415 (+24.8 on n = 191, against a 46.6 bp cost)
  - PEPE −480 (−14.6)
  - PENGU −489 (−21.1)
  - POPCAT −755 (+5.6)
  - TRUMP −160 (+0.4)
  - WIF −345 (−1.4)

## Kill test (W = 3d, H = 60, all train boundaries with a valid z, n = 154,353)
- IC(z, fwd 60m) = +0.0023. The momentum control IC is −0.0047.
- By half-year, IC_z is +0.0206 in 2024-10..2025-02-14 and −0.0097 in 2025-02-15..06-30.
- The sign flips between halves, so the test **FAILS**.

## Interpretation and limits
- The Coinbase premium carried no economically usable information about the Binance perp's next 15–60 min in
  2024-10..2025-06. ICs are ≤ 0.02 and flip sign, below the leads file's assumed 0.04–0.08.
- The cost is 2026-10 Lighter spreads applied to history. Even zero cost would leave a gross PF of about 1.0–1.08.
- Not tested (by the preregistration): the US-hours gate, and validation-period-only coins (FARTCOIN, PUMP, SPX, USELESS).
- Do not retry without new evidence: a different horizon or threshold on the same data is tuning on a failed run.
