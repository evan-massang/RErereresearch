# H-QHOI (quarter-hour opening taker imbalance → 4–12 h continuation on meme perps): FAIL on train; validation (information only) is a control-arm config concentrated in one day

Agent "qhoi", 2026-10-05. Memecoins only (scope decision 2026-10-05). The data is real (`is_synthetic = false`) and
every number below is our own computation, except the quoted paper figures.

- **Pre-registration:** `reports/hypotheses/qhoi_preregistration.json` (sha256 `fa42bdfc…5945b`), written before any
  aggTrades, kline or funding archive was downloaded and before any imbalance or return was computed.
- **Scripts:** `scripts/research/qhoi_fetch.py`, `scripts/research/qhoi_sim.py`.
- **Evidence:** `research/observations/evidence_qhoi_paper.json`, `evidence_qhoi_train.json`, `evidence_qhoi_validation.json`.
- **Data:** `data/raw/web/qhoi/` (7.4 MB): `qh/` per-quarter-hour buy/sell sums, `klines1h/`, `funding/`, manifests,
  `trades_{train,validation}.parquet`.

## 1. The paper (lead, preprint)

Chan Kim and Peter Reinhard Hansen, "The Quarter-Hour Effect: Periodic Algorithmic Trading and Return Predictability in
Cryptocurrency Futures", arXiv 2607.09426v2 [q-fin.TR], 16 Jul 2026. The paper exists and says what the round-11 lead says.
It is archived as pipeline source `src_f890c7862a8da268`, and the quotes are observations with `quote_verified = true`.
- p. 1 (abstract): "opening order imbalance predicts returns over four to twelve hours, with much weaker effects at finer clock-time frequencies".
- p. 36: "the coefficient is small or negative at short horizons but becomes positive at medium horizons in every market".
- p. 36: "Between four and twelve hours the estimates are significant at the 95% confidence level for four of the six contracts at every horizon".
- p. 36: "this pattern should not be interpreted as the causal price impact of trades executed during the opening 10 seconds".
- p. 7, the imbalance definition: "A trade is classified as buyer-initiated if the buyer is the taker (isBuyerMaker is False)". OI = signed volume ÷ volume in the interval.
- p. 62, Table A.4: the effect is reported "in basis points per unit of order imbalance". For DOGE it is 5.02 bp at 4 h, 8.49 bp at 8 h and 11.33 bp at 12 h (t 3.6–4.1). The sample is six large perps, 2021-01 to 2024-10.
- **Our inference (not stated in the paper):** 1 SD of the DOGE opening OI (0.56, Table A.8, p. 66) maps to about 3–6 bp over 4–12 h per boundary. That is a regression slope, not trading P&L, and the paper reports no strategy P&L for this result.

## 2. Data

- **memelead s1 tables:** they hold only `quote_vol` per second, with no buy/sell split, so they could not be used.
- **Binance USD-M daily aggTrades:** the 5th and 20th of each month, 2025-01 to 2026-03, fixed in the pre-registration.
  - 2025-01-20 was replaced by 2025-01-26. The reason was size only: the 01-20 archives total 414 MB in TRUMP launch week. No prices had been seen.
  - The planned 2024-12-20 warm-up day was dropped for budget.
- **Volume:** 256 coin-days downloaded, **1,188 MB**, 0 errors. TRUMP 2025-01-05 returned 404 because it was not listed yet. PUMP before 2025-07-11 is a different token and was excluded.
- **Archive handling:** the zips were deleted after reduction. Each file's URL, bytes and sha256 are in `data/raw/web/qhoi/manifest.jsonl`. Disk free stayed at 3.8 GB.
- **Reduced data:** 96 rows per coin-day: buy and sell base quantity in [b, b+10 s) and over the whole quarter hour.
  - Sanity check: DOGE OI₁₀ has SD 0.51 over our days, against the paper's 0.56.
- **Prices and funding:** monthly 1h klines and monthly fundingRate archives, 2025-01 to 2026-03.
- **Holdout (2026-04-01 onward):** never downloaded.

## 3. Rule (as pre-registered)

- **Signal:** S = mean OI over the 16 boundaries T−4 h … T−15 min.
  - The control arm uses whole-quarter-hour OI instead of the first 10 s.
- **z-score:** z = (S − mean) ÷ sd, computed point in time against all S of that coin and arm in the trailing 30 days (≥ 100 values).
- **Decisions:** at 04, 08, 12, 16, 20 and 24 UTC of each sampled day. If |z| ≥ k, take sign(z) (continuation).
- **Execution:** entry at the 1h open at T, exit at the 1h open at T+H, one position per coin.
- **Cost:**
  - Primary: 1.5 × the median Lighter $1,000 round-trip spread (memelead file: DOGE 4.8, PUMP 4.9, FARTCOIN 5.3, 1000PEPE 6.6, PENGU 9.4, TRUMP 9.3, WIF 11.0, 1000SHIB 11.6, 1000BONK 15.0 bp), plus Binance funding as a proxy.
  - Binance variant (information only): 10 bp round trip plus funding.
- **Grid:** arm {open10s, all_control} × k {1, 2} × H {4, 8, 12} h = 12 configs.
- **Bar per split:** n ≥ 50, net > 0, PF > 1.2, and net without the top 3 trades > 0.

## 4. Train (12 sampled days, 2025-01-05 .. 2025-06-20; 11 with a z history): no config meets the bar

All figures are mean bp per trade at the primary cost.

| config | n | gross | cost | net | PF | net ex top-3 (sum) | days + / days | day-cluster t |
|---|---|---|---|---|---|---|---|---|
| open10s_k1_H4 | 151 | −24.1 | 9.3 | −33.4 | 0.71 | −7,230 | 3/11 | −1.11 |
| open10s_k1_H8 | 116 | +1.8 | 9.5 | −7.7 | 0.94 | −4,056 | 7/11 | −0.17 |
| open10s_k1_H12 | 100 | +4.8 | 9.4 | −4.7 | 0.97 | −4,644 | 5/11 | −0.08 |
| open10s_k2_H4 | 34 | −80.9 | 9.7 | −90.5 | 0.28 | −3,683 | 3/10 | −1.93 |
| open10s_k2_H8 | 30 | −102.8 | 10.0 | −112.8 | 0.48 | −4,924 | 2/10 | −1.76 |
| open10s_k2_H12 | 29 | −1.8 | 10.0 | −11.8 | 0.94 | −2,755 | 4/10 | −0.11 |
| all_control_k1_H4 | 158 | +1.3 | 9.3 | −8.0 | 0.92 | −4,437 | 5/11 | −0.24 |
| all_control_k1_H8 | 125 | −16.3 | 9.4 | −25.7 | 0.84 | −6,594 | 4/11 | −0.39 |
| **all_control_k1_H12** | 109 | +6.0 | 9.3 | −3.3 | 0.98 | −4,829 | 6/11 | −0.04 |
| all_control_k2_H4 | 33 | +7.6 | 9.7 | −2.1 | 0.98 | −1,713 | 5/10 | −0.05 |
| all_control_k2_H8 | 32 | +32.6 | 9.8 | +22.9 | 1.18 | −1,464 | 4/10 | 0.27 |
| all_control_k2_H12 | 32 | +59.9 | 10.1 | +49.8 | 1.35 | −798 | 4/10 | 0.53 |

- **k = 2 configs fail on n.** They have 29–34 trades, below 50. They also fail net ex top-3, so they are noise on 10 days.
- **The Binance 10 bp variant is no better.** Its means are within 1 bp of the primary.
- **IC kill test (from the lead): fails.** Spearman IC of z against the forward return, n = 428 decision points:

  | horizon | open10s IC | all_control IC |
  |---|---|---|
  | 4 h | −0.068 | +0.037 |
  | 8 h | −0.017 | +0.002 |
  | 12 h | −0.011 | +0.035 |

  - The opening arm never beats the control arm, and its sign is wrong at every horizon.
  - At k = 1, H = 4 h its gross is −24 bp, against the required ≥ 2 × the 9.3 bp cost.
  - With n = 428, the standard error of an IC is about 0.05, so none of these ICs differs from zero.
- **The quarter-hour-specific mechanism does not appear in meme perps on these days.**

## 5. Validation (18 days, 2025-07-05 .. 2026-03-20): run once, information only

The pre-registration says: if nothing passes train, run the highest-train-PF config with n ≥ 50 for information. That
config is **all_control_k1_H12**, the control arm and not the paper's mechanism.

| n | gross | cost | net | PF | net ex top-3 | win | days + | day-cluster t | IC (all decisions) |
|---|---|---|---|---|---|---|---|---|---|
| 184 | +35.5 bp | 8.9 bp | **+26.6 bp** | 1.26 | +1,096 bp | 52% | **6/18** | 0.52 | +0.024 (n 780) |

- **The bar is met numerically, but the result is not evidence.**
  - The config failed train (−3.3 bp, PF 0.98), so the rule says FAIL whatever validation shows.
  - **One day, 2025-11-20, contributes +8,621 bp** of the +4,889 bp total. Without it, validation nets −3,731 bp.
  - Only 6 of 18 days are positive, and the day-clustered t is 0.52.
  - The 4–12 h meme moves have an SD of 352 bp, so a +27 bp mean on 18 clustered days is indistinguishable from zero.
  - Same-day trades across coins are highly correlated, because memes co-move.
- **By coin** (post hoc, not evidence): BONK +155, DOGE +136, PEPE +68 and FARTCOIN +53 bp; TRUMP −81, WIF −34, PUMP −32 and SHIB −15 bp.
- **Other costs** (information only): at 1.0× spread, +29.5 bp and PF 1.29; Binance 10 bp, +25.4 bp and PF 1.24.

## Verdict

**FAIL.** No configuration meets the bar on train, and the lead's own kill test fails.
- The 10-s opening imbalance has an IC of −0.07 to −0.01 against 4–12 h meme returns. That is the wrong sign, and it is never above the all-window control.
- The information-only validation run of the control arm looks positive, but one day drives it and train contradicts it. It does not reopen the idea.
- The paper's effect (3–6 bp per SD per boundary, on large-cap perps) is too small to be seen against 350 bp of meme return noise on 30 sampled days. Even if it is real, it would sit at or below the 5–15 bp Lighter round-trip cost.

## Caveats

- **Small sample.** Two sampled days a month (budget 1.2 GB) give 11 train days with a z history. Paper-sized effects are not detectable at this n either way, so this is a "not tradeable here" result and does not refute the paper's regression.
- **Point-in-time z on a sparse history.** The trailing 30-day pool holds only 1–2 earlier sampled days plus the same day. The first sampled day of each coin trades nothing.
- **Proxies.** Lighter fills are proxied by Binance 1h opens, Lighter funding by Binance funding, and spreads measured on 2026-10-05 are applied to 2025–26.
- **The S construction is ours.** S is a 4 h mean of 16 boundaries, as the round-11 lead specifies. The paper regresses single-boundary OI at 10-s frequency with controls, so S is our adaptation, not the paper's exact estimator.
- **Do not retry** without full-daily (not sampled) data and a single-boundary design. Even then, the paper's magnitude sits below one Lighter spread.
