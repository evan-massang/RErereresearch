# Failure: H-HLLAG on kSHIB, DOGE and kPEPE, each coin on its own (agent, 2026-10-05)

- **Pre-registration:** `reports/hypotheses/hllag_newcoins_addendum.json` (parent: `hllag_newcoins_preregistration.json`).
- **Rule:** frozen `hlanchor_lib.sim_lag` with θ = 40 bp, L = 300 ms, H = 30 s, 4.5 bp taker per side.
- **Bar:** applied per split. A split passes only if n ≥ 50, net > 0, PF > 1.2 and net ex top-3 > 0.

The primary addendum test, PENGU and kSHIB pooled, passed. These are the parts that failed.

| coin or group | train n / net $ / PF / ex-top3 | validation n / net $ / PF / ex-top3 | why it fails |
|---|---|---|---|
| kSHIB | 63 / +23.5 / 1.31 / −7.7 | 7 / +3.2 / 1.77 / −4.0 | Train ex-top3 is below 0, because one day (2024-12-01) gives +$22.4. Validation has only 7 trades. |
| DOGE | 7 / −15.2 / 0.00 / −13.7 | 15 / +9.0 / 1.40 / −13.2 | The rule rarely fires. Train loses money. Validation net comes from one day (2026-01-01, +$21.8). |
| kPEPE | 36 / +56.7 / 4.40 / +36.4 | 25 / −13.5 / 0.68 / −28.9 | Train has n < 50 and is concentrated in 2024-12 and 2025-01. Validation net is negative. |
| DOGE+kPEPE pooled | 43 / +41.5 / 2.31 / +21.3 | 40 / −4.5 / 0.93 / −27.3 | n < 50 on both splits, and validation net is negative. |

At L = 800 ms every row above loses, except kPEPE train at +$6.8 with PF 1.20.

**What this means.** On the most liquid meme perps (DOGE, kPEPE), Hyperliquid follows Binance closely.
40 bp lead moves are rare there, and the ones that do occur do not pay after costs. The lag edge, if it
exists, sits in thinner and newer listings: TRUMP, SPX and PENGU. No parameters were changed in response.
The holdout was not touched.

Data: `research/observations/evidence_hllag_newcoins_addendum_20261005.json`.
Per-trade results: `data/raw/web/tardis/results/newcoins_addendum/` (gitignored).
